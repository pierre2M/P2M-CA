"""
Synchroniser les co-validateurs depuis les ecritures C-CONSENTEMENT.

Lit les champs 'acteurs_co_validateurs' dans les ecritures dont
couche_uri = 'C-CONSENTEMENT' et cree les entrees manquantes
dans la table validations_requises.

Usage :
    python3 sync_covalidations.py <interaction_slug>
    python3 sync_covalidations.py --all

A lancer quand des co-validateurs sont declares dans les ecritures
mais n'ont pas ete enregistres comme validations formelles
(cas des interactions creees avant cette fonctionnalite).
"""

import sys, os, json, sqlite3
from datetime import datetime

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

def now():
    return datetime.now().isoformat()

def sync_interaction(con, interaction_slug):
    interaction = con.execute(
        "SELECT uri FROM interactions WHERE slug = ?", (interaction_slug,)
    ).fetchone()
    if not interaction:
        print(f"⚠ Interaction introuvable : {interaction_slug}")
        return 0

    # Recuperer toutes les ecritures C-CONSENTEMENT de cette interaction
    ecritures = con.execute("""
        SELECT e.uri, e.champs_couche, e.acteur_uri, a.slug AS acteur_slug
        FROM ecritures e
        JOIN acteurs a ON e.acteur_uri = a.uri
        WHERE e.interaction_uri = ?
          AND e.couche_uri = 'C-CONSENTEMENT'
          AND e.champs_couche IS NOT NULL
    """, (interaction["uri"],)).fetchall()

    nb_crees = 0

    for e in ecritures:
        try:
            champs = json.loads(e["champs_couche"])
        except Exception:
            continue

        co_validateurs = champs.get("acteurs_co_validateurs", [])
        if not co_validateurs:
            continue

        type_deliberation = champs.get("type_deliberation", "CO_VALIDATION")

        for val_slug in co_validateurs:
            # Retrouver l'URI du co-validateur
            acteur_val = con.execute(
                "SELECT uri, slug FROM acteurs WHERE slug = ?", (val_slug,)
            ).fetchone()

            if not acteur_val:
                print(f"  ⚠ Co-validateur '{val_slug}' introuvable dans la base — ignore.")
                continue

            # Verifier si cette validation existe deja
            existant = con.execute("""
                SELECT id FROM validations_requises
                WHERE ecriture_uri          = ?
                  AND acteur_validateur_uri = ?
                  AND type_validation       = 'CO_VALIDATION'
            """, (e["uri"], acteur_val["uri"])).fetchone()

            if existant:
                continue  # deja enregistree

            # Creer la validation manquante
            con.execute("""
                INSERT INTO validations_requises
                (ecriture_uri, acteur_validateur_uri, type_validation,
                 couche_ref, statut, date_obtention, commentaire)
                VALUES (?, ?, 'CO_VALIDATION', 'C-CONSENTEMENT', 'EN_ATTENTE', NULL, ?)
            """, (
                e["uri"],
                acteur_val["uri"],
                f"Co-validation requise par l'ecriture de {e['acteur_slug']} "
                f"(type_deliberation : {type_deliberation})"
            ))
            nb_crees += 1
            print(f"  ✓ Validation CO_VALIDATION creee : {val_slug}")

    return nb_crees

def sync_all(con):
    interactions = con.execute(
        "SELECT slug FROM interactions ORDER BY slug"
    ).fetchall()
    total = 0
    for i in interactions:
        n = sync_interaction(con, i["slug"])
        if n > 0:
            print(f"  → {i['slug']} : {n} co-validation(s) ajoutee(s)")
        total += n
    return total

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage :")
        print("  python3 sync_covalidations.py <interaction_slug>")
        print("  python3 sync_covalidations.py --all")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    if sys.argv[1] == "--all":
        print("\nSynchronisation de toutes les interactions...")
        total = sync_all(con)
        con.commit()
        con.close()
        print(f"\n✓ Total : {total} co-validation(s) ajoutee(s).")
    else:
        slug = sys.argv[1]
        print(f"\nSynchronisation de '{slug}'...")
        n = sync_interaction(con, slug)
        con.commit()
        con.close()
        if n == 0:
            print("  Aucune co-validation manquante.")
        else:
            print(f"\n✓ {n} co-validation(s) ajoutee(s).")
        print()
        print(f"Pour voir l'etat complet :")
        print(f"  python3 list_validations.py {slug}")
