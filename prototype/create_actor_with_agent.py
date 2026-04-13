import uuid, json, sys, sqlite3, os, re, unicodedata
from datetime import datetime

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

def make_did_key():
    return f"did:key:z{uuid.uuid4().hex}"

def make_slug(label: str) -> str:
    s = unicodedata.normalize('NFD', label.lower())
    s = s.encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')

def create_actor_with_agent(label: str, llm_type: str, llm_model: str,
                             llm_endpoint: str, droits: list,
                             validation_humaine: bool = False):
    acteur = {
        "uri":                  make_did_key(),
        "slug":                 make_slug(label),
        "label":                label,
        "created_at":           datetime.now().isoformat(),
        "registre_archive_uri": None,
    }
    agent = {
        "uri":                        make_did_key(),
        "acteur_uri":                 acteur["uri"],
        "llm_type":                   llm_type,
        "llm_endpoint":               llm_endpoint,
        "llm_model":                  llm_model,
        "rag_collection":             acteur["slug"],
        "droits_agent":               json.dumps(droits),
        "validation_humaine_requise": 1 if validation_humaine else 0,
        "created_at":                 datetime.now().isoformat(),
    }

    con = sqlite3.connect(DB_PATH)
    try:
        con.execute("""
            INSERT INTO acteurs (uri, slug, label, created_at, registre_archive_uri)
            VALUES (:uri, :slug, :label, :created_at, :registre_archive_uri)
        """, acteur)
        con.execute("""
            INSERT INTO agents
            (uri, acteur_uri, llm_type, llm_endpoint, llm_model,
             rag_collection, droits_agent, validation_humaine_requise, created_at)
            VALUES
            (:uri, :acteur_uri, :llm_type, :llm_endpoint, :llm_model,
             :rag_collection, :droits_agent, :validation_humaine_requise, :created_at)
        """, agent)
        con.commit()
        print(f"\n✓ Acteur cree : {acteur['slug']}")
        print(json.dumps(acteur, indent=2, ensure_ascii=False))
        print(f"\n✓ Agent associe ({llm_type}) :")
        print(json.dumps(agent, indent=2, ensure_ascii=False))
    except sqlite3.IntegrityError as e:
        print(f"⚠ Erreur : {e}")
    finally:
        con.close()

if __name__ == "__main__":
    print("Usage : importer ce module depuis create_actor_ollama.py ou create_actor_claude.py")
