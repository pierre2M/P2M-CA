"""
Creer une interaction P2M-CA v2 a partir d'un fichier YAML.

Usage :
    python3 create_interaction.py mon_interaction.yaml

Le fichier YAML decrit les acteurs, couches, ecritures et
validations requises. Voir exemple_interaction.yaml pour le format.
Les ecritures peuvent contenir un champ 'champs_couche' (dict YAML)
qui sera stocke en JSON dans la colonne champs_couche de la base.

Prerequis :
    - Base initialisee et migree (init_db.py + migrate_add_layers.py)
    - Acteurs concernes deja crees
    - PyYAML installe : pip3 install pyyaml
"""

import sys, os, json, uuid, sqlite3
from datetime import datetime

try:
    import yaml
except ImportError:
    print("PyYAML manquant. Lance : pip3 install pyyaml")
    sys.exit(1)

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")


# ── Helpers ────────────────────────────────────────────────────────────────

def make_did_key():
    return f"did:key:z{uuid.uuid4().hex}"

def now():
    return datetime.now().isoformat()

def get_acteur_by_slug(con, slug):
    row = con.execute(
        "SELECT uri, slug, label FROM acteurs WHERE slug = ?", (slug,)
    ).fetchone()
    if not row:
        raise ValueError(
            f"Acteur introuvable : '{slug}'. "
            f"Cree-le d'abord avec create_actor_ollama.py ou create_actor_claude.py."
        )
    return {"uri": row["uri"], "slug": row["slug"], "label": row["label"]}

def get_agent_for_acteur(con, acteur_uri):
    return con.execute(
        "SELECT * FROM agents WHERE acteur_uri = ?", (acteur_uri,)
    ).fetchone()


# ── Detection des regles de validation via l'agent ────────────────────────

def interroger_agent(con, acteur_uri, couches, ecritures_acteur):
    """
    Simule l'interrogation de l'agent associe a l'acteur.
    Dans le prototype complet, cette fonction appellerait le LLM via RAG.
    Ici elle lit les regles directement depuis la table agents.
    """
    agent = get_agent_for_acteur(con, acteur_uri)
    if agent is None:
        return []

    validations = []

    # Regle 1 : validation humaine systematique sur cet agent
    if agent["validation_humaine_requise"]:
        validations.append({
            "acteur_validateur_uri": acteur_uri,
            "type_validation": "HUMAIN",
            "couche_ref": couches[0] if couches else "C-BASE",
            "motif": f"Agent {agent['llm_type']} ({agent['llm_model']}) : validation humaine requise."
        })

    # Regle 2 : co-validation detectee dans le contenu des ecritures
    for e in ecritures_acteur:
        contenu = e.get("contenu", "") or ""
        champs  = e.get("champs_couche", {}) or {}
        if ("CO_VALIDATION" in contenu.upper() or
                champs.get("type_deliberation") == "CO_VALIDATION"):
            validations.append({
                "acteur_validateur_uri": acteur_uri,
                "type_validation": "CO_VALIDATION",
                "couche_ref": e.get("couche", "C-CONSENTEMENT"),
                "motif": "Clause CO_VALIDATION detectee dans l'ecriture."
            })
            break

    return validations


# ── Creation de l'interaction ──────────────────────────────────────────────

def create_interaction(yaml_path: str):
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    slug       = data["slug"]
    couches    = data.get("couches", [])
    ecritures  = data.get("ecritures", [])
    val_manual = data.get("validations_requises", []) or []

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # ── 1. Verifier que tous les acteurs existent ──────────────────────────
    acteur_slugs = list({e["acteur_slug"] for e in ecritures})
    acteurs_map  = {}
    for s in acteur_slugs:
        acteurs_map[s] = get_acteur_by_slug(con, s)
        print(f"  ✓ Acteur trouve : {s}")

    # ── 2. Creer l'interaction ─────────────────────────────────────────────
    interaction_uri = make_did_key()
    try:
        con.execute("""
            INSERT INTO interactions (uri, slug, created_at, couches_ref)
            VALUES (?, ?, ?, ?)
        """, (interaction_uri, slug, now(), json.dumps(couches)))
    except sqlite3.IntegrityError:
        print(f"\n⚠ Une interaction avec le slug '{slug}' existe deja.")
        con.close()
        sys.exit(1)

    # ── 3. Associer les acteurs ────────────────────────────────────────────
    for s, a in acteurs_map.items():
        con.execute("""
            INSERT INTO acteurs_interaction (interaction_uri, acteur_uri, label)
            VALUES (?, ?, ?)
        """, (interaction_uri, a["uri"], a["label"]))

    # ── 4. Interroger les agents ───────────────────────────────────────────
    toutes_validations = []
    for s, a in acteurs_map.items():
        ecritures_acteur = [e for e in ecritures if e["acteur_slug"] == s]
        regles = interroger_agent(con, a["uri"], couches, ecritures_acteur)
        for r in regles:
            r["source"] = f"agent de {s}"
            toutes_validations.append(r)

    # Validations declarees explicitement dans le YAML
    for v in val_manual:
        if not v:
            continue
        acteur = get_acteur_by_slug(con, v["acteur_slug"])
        toutes_validations.append({
            "acteur_validateur_uri": acteur["uri"],
            "type_validation": v["type"],
            "couche_ref": v.get("couche", "C-BASE"),
            "motif": v.get("motif", "Validation declaree dans le YAML."),
            "source": f"YAML explicite ({v['acteur_slug']})"
        })

    # Deduplication
    seen, validations_uniques = set(), []
    for v in toutes_validations:
        key = (v["acteur_validateur_uri"], v["type_validation"])
        if key not in seen:
            seen.add(key)
            validations_uniques.append(v)

    statut_global = "PENDING_VALIDATION" if validations_uniques else "VALIDATED"
    date_val      = now() if statut_global == "VALIDATED" else None

    # ── 5. Creer les ecritures ─────────────────────────────────────────────
    ecritures_creees = []
    for e in ecritures:
        acteur = acteurs_map[e["acteur_slug"]]
        couche_slug = e.get("couche", "")
        ecriture_uri = (
            f"{slug}#{e['acteur_slug']}#{e['sens']}"
            f"#{couche_slug.replace('/', '-')}"
        )

        # Champs de couche : dict YAML → JSON string
        champs_couche = e.get("champs_couche", None)
        champs_json   = json.dumps(champs_couche, ensure_ascii=False) if champs_couche else None

        rec = {
            "uri":                     ecriture_uri,
            "interaction_uri":         interaction_uri,
            "acteur_uri":              acteur["uri"],
            "sens":                    e["sens"],
            "contenu":                 e.get("contenu", ""),
            "couche_uri":              couche_slug or None,
            "ecriture_symetrique_uri": None,
            "ecriture_anterieure_uri": e.get("ecriture_anterieure_slug", None),
            "statut_enregistrement":   statut_global,
            "date_proposition":        now(),
            "date_validation":         date_val,
            "propose_par_uri":         f"agent-de-{e['acteur_slug']}",
            "champs_couche":           champs_json,
        }
        con.execute("""
            INSERT INTO ecritures
            (uri, interaction_uri, acteur_uri, sens, contenu, couche_uri,
             ecriture_symetrique_uri, ecriture_anterieure_uri,
             statut_enregistrement, date_proposition, date_validation,
             propose_par_uri, champs_couche)
            VALUES
            (:uri, :interaction_uri, :acteur_uri, :sens, :contenu, :couche_uri,
             :ecriture_symetrique_uri, :ecriture_anterieure_uri,
             :statut_enregistrement, :date_proposition, :date_validation,
             :propose_par_uri, :champs_couche)
        """, rec)
        ecritures_creees.append(rec)

    # ── 6. Enregistrer les validations en suspens ──────────────────────────
    for v in validations_uniques:
        ecriture_ref = next(
            (e["uri"] for e in ecritures_creees
             if e["acteur_uri"] == v["acteur_validateur_uri"]),
            ecritures_creees[0]["uri"] if ecritures_creees else None
        )
        con.execute("""
            INSERT INTO validations_requises
            (ecriture_uri, acteur_validateur_uri, type_validation,
             couche_ref, statut, date_obtention, commentaire)
            VALUES (?, ?, ?, ?, 'EN_ATTENTE', NULL, ?)
        """, (
            ecriture_ref,
            v["acteur_validateur_uri"],
            v["type_validation"],
            v["couche_ref"],
            v.get("motif", "")
        ))

    con.commit()
    con.close()

    # ── 7. Rapport ────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"INTERACTION CREEE : {slug}")
    print(f"URI               : {interaction_uri}")
    print(f"Statut            : {statut_global}")
    print(f"Couches           : {', '.join(couches)}")
    print(f"Acteurs           : {', '.join(acteur_slugs)}")
    print(f"Ecritures         : {len(ecritures_creees)}")
    if validations_uniques:
        print(f"\nValidations en suspens ({len(validations_uniques)}) :")
        for v in validations_uniques:
            print(f"  - {v['type_validation']:<20} source : {v.get('source','?')}")
            print(f"    {v.get('motif','')[:70]}")
    else:
        print("\n✓ Aucune validation requise — interaction enregistree directement.")
    print(f"{'='*65}\n")


# ── Point d'entree ────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python3 create_interaction.py mon_interaction.yaml")
        sys.exit(1)

    yaml_path = sys.argv[1]
    if not os.path.exists(yaml_path):
        print(f"Fichier introuvable : {yaml_path}")
        sys.exit(1)

    print(f"\nLecture de {yaml_path}...")
    create_interaction(yaml_path)
