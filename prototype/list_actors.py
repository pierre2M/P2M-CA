"""
Lister tous les acteurs et leurs agents dans le registre.

Usage :
    python3 list_actors.py
"""
import sqlite3, os

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

con = sqlite3.connect(DB_PATH)
con.row_factory = sqlite3.Row
rows = con.execute("""
    SELECT
        a.slug,
        a.label,
        a.uri        AS acteur_uri,
        ag.llm_type,
        ag.llm_model,
        ag.rag_collection,
        ag.validation_humaine_requise
    FROM acteurs a
    LEFT JOIN agents ag ON a.uri = ag.acteur_uri
    ORDER BY a.created_at
""").fetchall()
con.close()

if not rows:
    print("Aucun acteur dans le registre.")
else:
    print(f"{'SLUG':<35} {'LABEL':<35} {'LLM':<18} {'MODELE':<25} {'VALID.HUMAINE'}")
    print("-" * 120)
    for r in rows:
        vh = "oui" if r["validation_humaine_requise"] else "non"
        llm = r["llm_type"] or "(aucun agent)"
        model = r["llm_model"] or ""
        print(f"{r['slug']:<35} {r['label']:<35} {llm:<18} {model:<25} {vh}")
