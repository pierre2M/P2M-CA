"""
Lister toutes les validations en suspens, par interaction.

Usage :
    python3 list_validations.py                  # toutes les interactions
    python3 list_validations.py <interaction_slug>  # une interaction
"""

import sys, os, sqlite3

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")
SEP     = "─" * 70

def afficher(con, interaction_slug=None):
    where  = "AND i.slug = ?" if interaction_slug else ""
    params = (interaction_slug,) if interaction_slug else ()

    rows = con.execute(f"""
        SELECT
            i.slug        AS interaction_slug,
            vr.id         AS val_id,
            vr.type_validation,
            vr.couche_ref,
            vr.statut,
            vr.commentaire,
            vr.date_obtention,
            a_val.slug    AS validateur_slug,
            a_val.label   AS validateur_label,
            e.uri         AS ecriture_uri
        FROM validations_requises vr
        JOIN ecritures e    ON vr.ecriture_uri          = e.uri
        JOIN interactions i ON e.interaction_uri         = i.uri
        JOIN acteurs a_val  ON vr.acteur_validateur_uri  = a_val.uri
        WHERE 1=1 {where}
        ORDER BY i.slug, vr.statut DESC, vr.type_validation
    """, params).fetchall()

    if not rows:
        msg = f"Aucune validation pour '{interaction_slug}'." if interaction_slug else "Aucune validation dans le registre."
        print(msg)
        return

    inter_courant = None
    nb_attente    = 0

    for r in rows:
        if r["interaction_slug"] != inter_courant:
            if inter_courant is not None:
                print()
            inter_courant = r["interaction_slug"]
            print(f"\n{SEP}")
            print(f"INTERACTION : {r['interaction_slug']}")
            print(f"{SEP}")

        icone  = "✓" if r["statut"] == "OBTENU"     else \
                 "✗" if r["statut"] == "REFUSE"      else "⏳"
        date   = r["date_obtention"] or "en attente"

        print(f"  {icone}  id={r['val_id']:<4} "
              f"{r['type_validation']:<20} "
              f"validateur : {r['validateur_slug']:<38} "
              f"{date}")
        if r["commentaire"]:
            print(f"       motif : {r['commentaire'][:80]}")

        if r["statut"] == "EN_ATTENTE":
            nb_attente += 1

    print(f"\n{SEP}")
    if nb_attente:
        print(f"  {nb_attente} validation(s) EN_ATTENTE")
        print()
        print("  Pour valider :")
        print("    python3 validate_interaction.py <interaction_slug> <acteur_slug> <type>")
        print()
        print("  Pour enregistrer les co-validateurs manquants :")
        print("    python3 sync_covalidations.py <interaction_slug>")
    else:
        print("  Toutes les validations sont obtenues.")
    print(f"{SEP}\n")

if __name__ == "__main__":
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    afficher(con, sys.argv[1] if len(sys.argv) > 1 else None)
    con.close()
