"""
Enregistrer une validation en suspens pour une interaction.

Usage :
    python3 validate_interaction.py <interaction_slug> <acteur_slug> <type_validation> [commentaire]

Types disponibles : HUMAIN, CO_VALIDATION, VOTE, DELAI

Exemples :
    python3 validate_interaction.py restauration-zh-briere syndicat-mixte-du-bassin-versant HUMAIN
    python3 validate_interaction.py restauration-zh-briere association-naturaliste-loire CO_VALIDATION
    python3 validate_interaction.py restauration-zh-briere zone-humide-de-briere CO_VALIDATION

Quand TOUTES les validations d'une interaction sont obtenues,
le statut de toutes ses ecritures passe automatiquement a VALIDATED,
et le RAG est mis a jour.

Pour voir les validations en attente :
    python3 list_validations.py <interaction_slug>
"""

import sys, os, sqlite3
from datetime import datetime

DB_PATH  = os.path.expanduser("~/p2mca/registre/p2mca.db")
RAG_PATH = os.path.expanduser("~/p2mca/rag/chroma")

def now():
    return datetime.now().isoformat()

def validate(interaction_slug, acteur_slug, type_validation, commentaire=""):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # Recuperer l'interaction
    interaction = con.execute(
        "SELECT uri FROM interactions WHERE slug = ?", (interaction_slug,)
    ).fetchone()
    if not interaction:
        print(f"⚠ Interaction introuvable : {interaction_slug}")
        con.close(); sys.exit(1)

    # Recuperer l'acteur
    acteur = con.execute(
        "SELECT uri, label FROM acteurs WHERE slug = ?", (acteur_slug,)
    ).fetchone()
    if not acteur:
        print(f"⚠ Acteur introuvable : {acteur_slug}")
        con.close(); sys.exit(1)

    # Chercher la validation EN_ATTENTE correspondante
    val = con.execute("""
        SELECT vr.id, vr.ecriture_uri, vr.statut
        FROM validations_requises vr
        JOIN ecritures e ON vr.ecriture_uri = e.uri
        WHERE e.interaction_uri         = ?
          AND vr.acteur_validateur_uri  = ?
          AND vr.type_validation        = ?
          AND vr.statut                 = 'EN_ATTENTE'
    """, (interaction["uri"], acteur["uri"], type_validation)).fetchone()

    if not val:
        # Afficher ce qui est en attente pour aider
        attentes = con.execute("""
            SELECT vr.type_validation, a.slug AS val_slug, vr.statut
            FROM validations_requises vr
            JOIN ecritures e   ON vr.ecriture_uri         = e.uri
            JOIN acteurs a     ON vr.acteur_validateur_uri = a.uri
            WHERE e.interaction_uri = ?
            ORDER BY vr.statut DESC
        """, (interaction["uri"],)).fetchall()

        print(f"\n⚠ Aucune validation EN_ATTENTE trouvee pour :")
        print(f"   interaction : {interaction_slug}")
        print(f"   acteur      : {acteur_slug}")
        print(f"   type        : {type_validation}")
        if attentes:
            print(f"\n   Validations existantes pour cette interaction :")
            for a in attentes:
                icone = "✓" if a["statut"] == "OBTENU" else "⏳"
                print(f"     {icone} {a['type_validation']:<20} {a['val_slug']}")
        print(f"\n   Conseil : lance d'abord sync_covalidations.py si des co-validateurs")
        print(f"   sont declares dans les ecritures mais pas encore enregistres.")
        con.close(); sys.exit(1)

    # Enregistrer la validation
    con.execute("""
        UPDATE validations_requises
        SET statut = 'OBTENU', date_obtention = ?, commentaire = ?
        WHERE id = ?
    """, (now(), commentaire or f"Validation {type_validation} obtenue.", val["id"]))

    print(f"\n✓ Validation enregistree : {type_validation} par {acteur_slug}")

    # Verifier s'il reste des validations EN_ATTENTE pour cette interaction
    en_attente = con.execute("""
        SELECT COUNT(*) as n FROM validations_requises vr
        JOIN ecritures e ON vr.ecriture_uri = e.uri
        WHERE e.interaction_uri = ?
          AND vr.statut = 'EN_ATTENTE'
    """, (interaction["uri"],)).fetchone()["n"]

    if en_attente == 0:
        # Passer toutes les ecritures a VALIDATED
        con.execute("""
            UPDATE ecritures
            SET statut_enregistrement = 'VALIDATED', date_validation = ?
            WHERE interaction_uri = ?
        """, (now(), interaction["uri"]))
        print(f"✓ Toutes les validations obtenues.")
        print(f"  Interaction '{interaction_slug}' → VALIDATED")

        # Mettre a jour le RAG
        con.commit()
        _update_rag(interaction_slug, con)
    else:
        # Afficher ce qui reste
        restantes = con.execute("""
            SELECT vr.type_validation, a.slug AS val_slug
            FROM validations_requises vr
            JOIN ecritures e ON vr.ecriture_uri         = e.uri
            JOIN acteurs a   ON vr.acteur_validateur_uri = a.uri
            WHERE e.interaction_uri = ?
              AND vr.statut = 'EN_ATTENTE'
        """, (interaction["uri"],)).fetchall()

        print(f"\n  {en_attente} validation(s) encore EN_ATTENTE :")
        for r in restantes:
            print(f"    ⏳ {r['type_validation']:<20} {r['val_slug']}")
        print(f"\n  Pour valider :")
        for r in restantes:
            print(f"    python3 validate_interaction.py {interaction_slug} {r['val_slug']} {r['type_validation']}")

    con.commit()
    con.close()

def _update_rag(interaction_slug, con):
    """Mettre a jour le RAG apres validation."""
    acteurs = con.execute("""
        SELECT DISTINCT a.slug
        FROM acteurs_interaction ai
        JOIN interactions i ON ai.interaction_uri = i.uri
        JOIN acteurs a      ON ai.acteur_uri       = a.uri
        WHERE i.slug = ?
    """, (interaction_slug,)).fetchall()

    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(__file__))
        from build_rag import index_acteur
        print(f"\n  Mise a jour du RAG...")
        for a in acteurs:
            index_acteur(a["slug"])
        print(f"  ✓ RAG mis a jour pour {len(acteurs)} acteur(s).")
    except Exception as e:
        print(f"  [RAG] Mise a jour differee : {e}")
        print(f"  Lance manuellement : python3 build_rag.py --all")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage : python3 validate_interaction.py <interaction_slug> <acteur_slug> <type> [commentaire]")
        print()
        print("Pour voir les validations en attente :")
        print("  python3 list_validations.py <interaction_slug>")
        sys.exit(1)

    validate(
        interaction_slug = sys.argv[1],
        acteur_slug      = sys.argv[2],
        type_validation  = sys.argv[3],
        commentaire      = sys.argv[4] if len(sys.argv) > 4 else "",
    )
