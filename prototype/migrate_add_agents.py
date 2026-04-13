"""
Migration : ajoute la table 'agents' si elle n'existe pas encore.
A lancer une seule fois sur une base deja initialisee.

Usage :
    python3 migrate_add_agents.py
"""
import sqlite3, os

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

con = sqlite3.connect(DB_PATH)
con.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        uri                       TEXT PRIMARY KEY,
        acteur_uri                TEXT REFERENCES acteurs(uri),
        llm_type                  TEXT,
        llm_endpoint              TEXT,
        llm_model                 TEXT,
        rag_collection            TEXT,
        droits_agent              TEXT,
        validation_humaine_requise INTEGER DEFAULT 0,
        created_at                TEXT
    );
""")
con.commit()
con.close()
print("✓ Table 'agents' ajoutee (ou deja presente).")
print("  Tu peux maintenant relancer create_actor_ollama.py ou create_actor_claude.py.")
