"""
Lister les interactions et leur statut de validation.

Usage :
    python3 list_interactions.py              # toutes les interactions
    python3 list_interactions.py <slug>       # detail d'une interaction
"""

import sys, os, sqlite3, json

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

def list_all(con):
    rows = con.execute("""
        SELECT i.slug, i.created_at, i.couches_ref,
               COUNT(DISTINCT e.uri) AS nb_ecritures,
               SUM(CASE WHEN e.statut_enregistrement = 'VALIDATED' THEN 1 ELSE 0 END) AS nb_validated,
               SUM(CASE WHEN e.statut_enregistrement = 'PENDING_VALIDATION' THEN 1 ELSE 0 END) AS nb_pending
        FROM interactions i
        LEFT JOIN ecritures e ON i.uri = e.interaction_uri
        GROUP BY i.uri
        ORDER BY i.created_at DESC
    """).fetchall()

    if not rows:
        print("Aucune interaction dans le registre.")
        return

    print(f"\n{'SLUG':<45} {'ECRITURES':>9} {'VALIDATED':>9} {'PENDING':>8}  {'COUCHES'}")
    print("-" * 110)
    for r in rows:
        couches = ", ".join(json.loads(r[2])) if r[2] else ""
        print(f"{r[0]:<45} {r[3]:>9} {r[4]:>9} {r[5]:>8}  {couches[:40]}")

def detail(con, slug):
    interaction = con.execute(
        "SELECT uri, slug, created_at, couches_ref FROM interactions WHERE slug = ?", (slug,)
    ).fetchone()
    if not interaction:
        print(f"Interaction introuvable : {slug}")
        return

    print(f"\n{'='*65}")
    print(f"INTERACTION : {interaction[1]}")
    print(f"URI         : {interaction[0]}")
    print(f"Cree le     : {interaction[2]}")
    print(f"Couches     : {', '.join(json.loads(interaction[3]) if interaction[3] else [])}")

    # Ecritures
    ecritures = con.execute("""
        SELECT e.sens, e.couche_uri, a.slug AS acteur_slug,
               e.statut_enregistrement, e.contenu
        FROM ecritures e
        JOIN acteurs a ON e.acteur_uri = a.uri
        WHERE e.interaction_uri = ?
        ORDER BY a.slug, e.sens
    """, (interaction[0],)).fetchall()

    print(f"\n── Ecritures ({len(ecritures)}) ──────────────────────────────────")
    for e in ecritures:
        statut_label = "✓" if e[3] == "VALIDATED" else "⏳"
        contenu_court = (e[4] or "")[:60].replace("\n", " ").strip()
        print(f"  {statut_label} [{e[0]:<6}] {e[2]:<35} {e[1] or 'base':<25}  {contenu_court}")

    # Validations
    validations = con.execute("""
        SELECT vr.type_validation, a.slug, vr.statut, vr.date_obtention, vr.commentaire
        FROM validations_requises vr
        JOIN ecritures e ON vr.ecriture_uri = e.uri
        JOIN acteurs a ON vr.acteur_validateur_uri = a.uri
        WHERE e.interaction_uri = ?
        ORDER BY vr.statut DESC
    """, (interaction[0],)).fetchall()

    if validations:
        print(f"\n── Validations ({len(validations)}) ─────────────────────────────────")
        for v in validations:
            statut_label = "✓" if v[2] == "OBTENU" else "⏳"
            date = v[3] or "en attente"
            print(f"  {statut_label} {v[0]:<20} validateur : {v[1]:<35} {date}")
    else:
        print("\n── Aucune validation requise (enregistrement direct)")

    print(f"{'='*65}\n")


if __name__ == "__main__":
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    if len(sys.argv) >= 2:
        detail(con, sys.argv[1])
    else:
        list_all(con)

    con.close()
