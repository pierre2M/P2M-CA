import sqlite3, os

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

def init():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS acteurs (
        uri         TEXT PRIMARY KEY,
        slug        TEXT UNIQUE NOT NULL,
        label       TEXT,
        created_at  TEXT,
        registre_archive_uri TEXT
    );

    CREATE TABLE IF NOT EXISTS interactions (
        uri         TEXT PRIMARY KEY,
        slug        TEXT UNIQUE NOT NULL,
        created_at  TEXT,
        couches_ref TEXT
    );

    CREATE TABLE IF NOT EXISTS acteurs_interaction (
        interaction_uri TEXT REFERENCES interactions(uri),
        acteur_uri      TEXT REFERENCES acteurs(uri),
        label           TEXT,
        PRIMARY KEY (interaction_uri, acteur_uri)
    );

    CREATE TABLE IF NOT EXISTS ecritures (
        uri                     TEXT PRIMARY KEY,
        interaction_uri         TEXT REFERENCES interactions(uri),
        acteur_uri              TEXT REFERENCES acteurs(uri),
        sens                    TEXT CHECK(sens IN ('DEBIT','CREDIT')),
        contenu                 TEXT,
        couche_uri              TEXT,
        ecriture_symetrique_uri TEXT,
        ecriture_anterieure_uri TEXT,
        statut_enregistrement   TEXT DEFAULT 'VALIDATED',
        date_proposition        TEXT,
        date_validation         TEXT,
        propose_par_uri         TEXT
    );

    CREATE TABLE IF NOT EXISTS validations_requises (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        ecriture_uri          TEXT REFERENCES ecritures(uri),
        acteur_validateur_uri TEXT,
        type_validation       TEXT,
        couche_ref            TEXT,
        statut                TEXT DEFAULT 'EN_ATTENTE',
        date_obtention        TEXT,
        commentaire           TEXT
    );

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
    print(f"Base initialisee : {DB_PATH}")

if __name__ == "__main__":
    os.makedirs(os.path.expanduser("~/p2mca/registre"), exist_ok=True)
    init()
