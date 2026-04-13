"""
Lister et inspecter les ecritures d'une interaction ou d'un acteur.

Usage :
    python3 list_ecritures.py interaction <slug_interaction>
    python3 list_ecritures.py acteur <slug_acteur>
    python3 list_ecritures.py ecriture <uri_ecriture>

Exemples :
    python3 list_ecritures.py interaction restauration-zh-briere-2026-04
    python3 list_ecritures.py acteur zone-humide-de-briere
    python3 list_ecritures.py ecriture restauration-zh-briere-2026-04#zone-humide-de-briere#DEBIT#C-SOG-biophysique
"""
import sys, os, sqlite3, json

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

SEP = "─" * 70

def afficher_ecriture(e, verbose=True):
    statut = "✓" if e["statut_enregistrement"] == "VALIDATED" else "⏳"
    print(f"\n{SEP}")
    print(f"{statut} URI     : {e['uri']}")
    print(f"  Acteur  : {e['acteur_slug']} ({e['acteur_label']})")
    print(f"  Sens    : {e['sens']}")
    print(f"  Couche  : {e['couche_uri'] or 'base'}")
    print(f"  Statut  : {e['statut_enregistrement']}")
    if e["contenu"]:
        print(f"  Contenu :")
        for ligne in e["contenu"].strip().split("\n"):
            print(f"    {ligne}")
    if e["champs_couche"] and verbose:
        try:
            champs = json.loads(e["champs_couche"])
            if champs:
                print(f"  Champs de couche :")
                for k, v in champs.items():
                    print(f"    {k} : {v}")
        except Exception:
            pass
    if e["ecriture_anterieure_uri"]:
        print(f"  Chaine depuis : {e['ecriture_anterieure_uri']}")
    if e["ecriture_symetrique_uri"]:
        print(f"  Symetrique    : {e['ecriture_symetrique_uri']}")

def requete_base(con, where_clause, params):
    return con.execute(f"""
        SELECT
            e.uri, e.sens, e.couche_uri, e.contenu,
            e.statut_enregistrement, e.champs_couche,
            e.ecriture_anterieure_uri, e.ecriture_symetrique_uri,
            e.date_proposition, e.date_validation,
            a.slug AS acteur_slug, a.label AS acteur_label,
            i.slug AS interaction_slug
        FROM ecritures e
        JOIN acteurs a ON e.acteur_uri = a.uri
        JOIN interactions i ON e.interaction_uri = i.uri
        WHERE {where_clause}
        ORDER BY a.slug, e.sens, e.couche_uri
    """, params).fetchall()

def mode_interaction(con, slug):
    inter = con.execute(
        "SELECT uri, slug, couches_ref FROM interactions WHERE slug = ?", (slug,)
    ).fetchone()
    if not inter:
        print(f"Interaction introuvable : {slug}")
        return
    print(f"\n== Ecritures de l'interaction : {slug}")
    couches = json.loads(inter["couches_ref"]) if inter["couches_ref"] else []
    print(f"   Couches : {', '.join(couches)}")
    rows = requete_base(con, "e.interaction_uri = ?", (inter["uri"],))
    print(f"   {len(rows)} ecriture(s)")
    for r in rows:
        afficher_ecriture(r)

def mode_acteur(con, slug):
    acteur = con.execute(
        "SELECT uri, label FROM acteurs WHERE slug = ?", (slug,)
    ).fetchone()
    if not acteur:
        print(f"Acteur introuvable : {slug}")
        return
    print(f"\n== Ecritures de l'acteur : {slug} ({acteur['label']})")
    rows = requete_base(con, "a.slug = ?", (slug,))
    print(f"   {len(rows)} ecriture(s) au total")
    inter_courant = None
    for r in rows:
        if r["interaction_slug"] != inter_courant:
            inter_courant = r["interaction_slug"]
            print(f"\n  >> Interaction : {inter_courant}")
        afficher_ecriture(r, verbose=True)

def mode_ecriture(con, uri):
    rows = requete_base(con, "e.uri = ?", (uri,))
    if not rows:
        print(f"Ecriture introuvable : {uri}")
        return
    afficher_ecriture(rows[0], verbose=True)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]
    valeur = sys.argv[2]

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    if mode == "interaction":
        mode_interaction(con, valeur)
    elif mode == "acteur":
        mode_acteur(con, valeur)
    elif mode == "ecriture":
        mode_ecriture(con, valeur)
    else:
        print(f"Mode inconnu : {mode}. Utilise 'interaction', 'acteur' ou 'ecriture'.")

    con.close()
    print(f"\n{SEP}")
