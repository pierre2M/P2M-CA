"""
Migration : ajoute la table 'couches' et la colonne 'champs_couche'
dans la table 'ecritures'.

A lancer une seule fois sur une base deja initialisee.

Usage :
    python3 migrate_add_layers.py
"""
import sqlite3, os

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

con = sqlite3.connect(DB_PATH)

con.executescript("""
    -- Table des couches interpretatives
    -- Une couche est elle-meme un acteur du registre (principe P2M-CA)
    CREATE TABLE IF NOT EXISTS couches (
        uri                      TEXT PRIMARY KEY,
        slug                     TEXT UNIQUE NOT NULL,
        label                    TEXT,
        auteur_uri               TEXT REFERENCES acteurs(uri),
        interaction_conception_uri TEXT,
        couches_parentes_uri     TEXT,  -- JSON array des URI parents
        description              TEXT,
        champs_definis           TEXT,  -- JSON : {champ: {type, description}}
        created_at               TEXT
    );

    -- Index pour retrouver une couche par slug
    CREATE INDEX IF NOT EXISTS idx_couches_slug ON couches(slug);
""")

# Ajouter la colonne champs_couche a ecritures si elle n'existe pas
colonnes = [row[1] for row in con.execute("PRAGMA table_info(ecritures)").fetchall()]
if "champs_couche" not in colonnes:
    con.execute("ALTER TABLE ecritures ADD COLUMN champs_couche TEXT")
    print("✓ Colonne 'champs_couche' ajoutee a la table 'ecritures'.")
else:
    print("  Colonne 'champs_couche' deja presente.")

con.commit()
con.close()
print("✓ Table 'couches' creee (ou deja presente).")
print("  Tu peux maintenant lancer : python3 create_layer.py c_ant_layer.yaml")
