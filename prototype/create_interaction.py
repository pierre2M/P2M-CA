"""
Creer une interaction P2M-CA v2 a partir d'un fichier YAML.
Version avec RAG + support du chainage ecriture_anterieure_uri.

Usage :
    python3 create_interaction.py mon_interaction.yaml
    python3 create_interaction.py mon_interaction.yaml --no-rag

Prerequis :
    - Base initialisee et migree
    - Acteurs et agents crees
    - RAG indexe : python3 build_rag.py --all
    - pip3 install pyyaml chromadb sentence-transformers anthropic
"""

import sys, os, json, uuid, sqlite3, argparse
from datetime import datetime
from collections import defaultdict

try:
    import yaml
except ImportError:
    print("PyYAML manquant. Lance : pip3 install pyyaml")
    sys.exit(1)

DB_PATH  = os.path.expanduser("~/p2mca/registre/p2mca.db")
RAG_PATH = os.path.expanduser("~/p2mca/rag/chroma")


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
        raise ValueError(f"Acteur introuvable : '{slug}'.")
    return {"uri": row["uri"], "slug": row["slug"], "label": row["label"]}

def get_agent_for_acteur(con, acteur_uri):
    return con.execute(
        "SELECT * FROM agents WHERE acteur_uri = ?", (acteur_uri,)
    ).fetchone()

def make_ecriture_uri(interaction_slug, acteur_slug, sens, couche_slug, index):
    couche_norm = couche_slug.replace("/", "-").replace(" ", "-")
    return f"{interaction_slug}#{acteur_slug}#{sens}#{couche_norm}#{index}"

def resoudre_ecriture_anterieure(con, ref):
    """
    Resout une reference a une ecriture anterieure.
    Accepte : un URI complet, ou un slug d'interaction (retourne
    la premiere ecriture VALIDATED de cette interaction).
    Retourne l'URI de l'ecriture, ou None si introuvable.
    """
    if not ref:
        return None
    # Essai 1 : URI direct
    row = con.execute(
        "SELECT uri FROM ecritures WHERE uri = ?", (ref,)
    ).fetchone()
    if row:
        return row["uri"]
    # Essai 2 : slug d'interaction → premiere ecriture VALIDATED
    row = con.execute("""
        SELECT e.uri FROM ecritures e
        JOIN interactions i ON e.interaction_uri = i.uri
        WHERE i.slug = ? AND e.statut_enregistrement = 'VALIDATED'
        ORDER BY e.date_proposition
        LIMIT 1
    """, (ref,)).fetchone()
    if row:
        return row["uri"]
    print(f"  ⚠ ecriture_anterieure introuvable : '{ref}' — champ laisse null.")
    return None


# ── Contexte pour l'agent ─────────────────────────────────────────────────

def construire_contexte(slug, couches, ecritures_acteur):
    lignes = [
        f"Interaction : {slug}",
        f"Couches mobilisees : {', '.join(couches)}",
        f"Nombre d'ecritures pour cet acteur : {len(ecritures_acteur)}",
        "",
    ]
    for e in ecritures_acteur[:3]:
        lignes.append(
            f"[{e['sens']}] couche={e.get('couche','?')} : "
            f"{str(e.get('contenu',''))[:120]}"
        )
    return "\n".join(lignes)


# ── Interrogation des agents avec RAG ────────────────────────────────────

def interroger_agent_rag(con, acteur_slug, acteur_uri, slug, couches, ecritures_acteur):
    agent = get_agent_for_acteur(con, acteur_uri)
    if agent is None:
        return []

    contexte = construire_contexte(slug, couches, ecritures_acteur)
    llm_type = agent["llm_type"]
    result   = None

    if llm_type == "LOCAL_OLLAMA":
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from agent_ollama import interroger_agent_ollama
            result = interroger_agent_ollama(acteur_slug, contexte)
            print(f"  [RAG/Ollama] '{acteur_slug}' : {result.get('resume','')[:70]}")
        except Exception as e:
            print(f"  [RAG/Ollama] Erreur '{acteur_slug}' : {e} — fallback statique")

    elif llm_type == "API_ANTHROPIC":
        try:
            from agent_claude import interroger_agent_claude
            result = interroger_agent_claude(acteur_slug, contexte)
            print(f"  [RAG/Claude] '{acteur_slug}' : {result.get('resume','')[:70]}")
        except Exception as e:
            print(f"  [RAG/Claude] Erreur '{acteur_slug}' : {e} — fallback statique")

    validations = []
    if result and result.get("validation_requise"):
        for v in result.get("validations", []):
            validations.append({
                "acteur_validateur_uri": acteur_uri,
                "type_validation":       v.get("type_validation", "HUMAIN"),
                "couche_ref":            v.get("couche_ref", couches[0] if couches else "C-BASE"),
                "motif":                 v.get("motif", ""),
                "source":                f"RAG/{llm_type} ({acteur_slug})"
            })

    if result is None:
        validations = _fallback_statique(agent, acteur_uri, couches, ecritures_acteur)

    return validations


def _fallback_statique(agent, acteur_uri, couches, ecritures_acteur):
    validations = []
    if agent["validation_humaine_requise"]:
        validations.append({
            "acteur_validateur_uri": acteur_uri,
            "type_validation":       "HUMAIN",
            "couche_ref":            couches[0] if couches else "C-BASE",
            "motif":                 "Validation humaine requise (fallback statique).",
            "source":                "fallback_statique"
        })
    for e in ecritures_acteur:
        contenu = e.get("contenu", "") or ""
        champs  = e.get("champs_couche", {}) or {}
        if ("CO_VALIDATION" in contenu.upper() or
                champs.get("type_deliberation") == "CO_VALIDATION"):
            validations.append({
                "acteur_validateur_uri": acteur_uri,
                "type_validation":       "CO_VALIDATION",
                "couche_ref":            e.get("couche", "C-CONSENTEMENT"),
                "motif":                 "CO_VALIDATION detectee (fallback statique).",
                "source":                "fallback_statique"
            })
            break
    return validations


# ── Creation de l'interaction ──────────────────────────────────────────────

def create_interaction(yaml_path: str, use_rag: bool = True):
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    slug       = data["slug"]
    couches    = data.get("couches", [])
    ecritures  = data.get("ecritures", [])
    val_manual = data.get("validations_requises", []) or []

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # ── 1. Verifier les acteurs ────────────────────────────────────────
    acteur_slugs = list({e["acteur_slug"] for e in ecritures})
    acteurs_map  = {}
    for s in acteur_slugs:
        acteurs_map[s] = get_acteur_by_slug(con, s)
        print(f"  ✓ Acteur trouve : {s}")

    # ── 2. Creer l'interaction ─────────────────────────────────────────
    interaction_uri = make_did_key()
    try:
        con.execute("""
            INSERT INTO interactions (uri, slug, created_at, couches_ref)
            VALUES (?, ?, ?, ?)
        """, (interaction_uri, slug, now(), json.dumps(couches)))
    except sqlite3.IntegrityError:
        print(f"\n⚠ Une interaction avec le slug '{slug}' existe deja.")
        con.close(); sys.exit(1)

    for s, a in acteurs_map.items():
        con.execute("""
            INSERT INTO acteurs_interaction (interaction_uri, acteur_uri, label)
            VALUES (?, ?, ?)
        """, (interaction_uri, a["uri"], a["label"]))

    # ── 3. Interroger les agents ───────────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"Interrogation des agents "
          f"({'RAG actif' if use_rag else 'mode statique'})...")
    toutes_validations = []

    for s, a in acteurs_map.items():
        ecritures_acteur = [e for e in ecritures if e["acteur_slug"] == s]
        if use_rag:
            regles = interroger_agent_rag(
                con, s, a["uri"], slug, couches, ecritures_acteur
            )
        else:
            agent  = get_agent_for_acteur(con, a["uri"])
            regles = (_fallback_statique(agent, a["uri"], couches, ecritures_acteur)
                      if agent else [])
        toutes_validations.extend(regles)

    for v in val_manual:
        if not v:
            continue
        acteur = get_acteur_by_slug(con, v["acteur_slug"])
        toutes_validations.append({
            "acteur_validateur_uri": acteur["uri"],
            "type_validation":       v["type"],
            "couche_ref":            v.get("couche", "C-BASE"),
            "motif":                 v.get("motif", "Validation declaree dans le YAML."),
            "source":                f"YAML explicite ({v['acteur_slug']})"
        })

    seen, validations_uniques = set(), []
    for v in toutes_validations:
        key = (v["acteur_validateur_uri"], v["type_validation"])
        if key not in seen:
            seen.add(key)
            validations_uniques.append(v)

    statut_global = "PENDING_VALIDATION" if validations_uniques else "VALIDATED"
    date_val      = now() if statut_global == "VALIDATED" else None

    # ── 4. Creer les ecritures (avec chainage) ─────────────────────────
    compteur_uri     = defaultdict(int)
    ecritures_creees = []

    for e in ecritures:
        acteur      = acteurs_map[e["acteur_slug"]]
        couche_slug = e.get("couche", "")
        cle         = (e["acteur_slug"], e["sens"], couche_slug)
        index       = compteur_uri[cle]
        compteur_uri[cle] += 1

        ecriture_uri = make_ecriture_uri(
            slug, e["acteur_slug"], e["sens"], couche_slug, index
        )

        # ── Résolution du chainage ─────────────────────────────────────
        anterieure_ref = e.get("ecriture_anterieure_uri", None)
        anterieure_uri = resoudre_ecriture_anterieure(con, anterieure_ref)

        champs_couche = e.get("champs_couche", None)
        champs_json   = (json.dumps(champs_couche, ensure_ascii=False)
                         if champs_couche else None)

        rec = {
            "uri":                     ecriture_uri,
            "interaction_uri":         interaction_uri,
            "acteur_uri":              acteur["uri"],
            "sens":                    e["sens"],
            "contenu":                 e.get("contenu", ""),
            "couche_uri":              couche_slug or None,
            "ecriture_symetrique_uri": None,
            "ecriture_anterieure_uri": anterieure_uri,
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

    # ── 5. Enregistrer les validations ─────────────────────────────────
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

    # ── 6. Indexer dans le RAG si VALIDATED ───────────────────────────
    if use_rag and statut_global == "VALIDATED":
        print(f"\nMise a jour du RAG...")
        try:
            from build_rag import index_acteur
            for s in acteur_slugs:
                index_acteur(s)
        except Exception as e:
            print(f"  [RAG] Mise a jour differee : {e}")

    con.close()

    # ── 7. Rapport ────────────────────────────────────────────────────
    chaines = sum(1 for e in ecritures_creees if e["ecriture_anterieure_uri"])
    print(f"\n{'='*65}")
    print(f"INTERACTION CREEE : {slug}")
    print(f"URI               : {interaction_uri}")
    print(f"Statut            : {statut_global}")
    print(f"Couches           : {', '.join(couches)}")
    print(f"Acteurs           : {', '.join(acteur_slugs)}")
    print(f"Ecritures         : {len(ecritures_creees)}")
    if chaines:
        print(f"Ecritures chainees : {chaines} (ecriture_anterieure_uri resolu)")
    if validations_uniques:
        print(f"\nValidations en suspens ({len(validations_uniques)}) :")
        for v in validations_uniques:
            print(f"  - {v['type_validation']:<20} {v.get('source','?')}")
            print(f"    {v.get('motif','')[:70]}")
    else:
        print("\n✓ Aucune validation requise — enregistrement direct.")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("yaml_path", help="Fichier YAML de l'interaction")
    parser.add_argument("--no-rag", action="store_true",
                        help="Desactiver le RAG")
    args = parser.parse_args()

    if not os.path.exists(args.yaml_path):
        print(f"Fichier introuvable : {args.yaml_path}")
        sys.exit(1)

    print(f"\nLecture de {args.yaml_path}...")
    create_interaction(args.yaml_path, use_rag=not args.no_rag)
