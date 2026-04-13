"""
Associer un agent LLM a un acteur existant dans la base.

Usage :
    python3 add_agent_to_actor.py <acteur_slug> <type_llm>

type_llm :
    ollama   → agent local Ollama / Mistral
    claude   → agent API Anthropic / Claude

Exemples :
    python3 add_agent_to_actor.py zone-humide-de-briere ollama
    python3 add_agent_to_actor.py syndicat-mixte-du-bassin-versant claude
    python3 add_agent_to_actor.py association-naturaliste-loire ollama

Options avancees (modifiables directement dans ce script) :
    OLLAMA_MODEL  : modele Ollama a utiliser (defaut : mistral)
    CLAUDE_MODEL  : modele Claude a utiliser (defaut : claude-sonnet-4-6)
    OLLAMA_URL    : endpoint Ollama local (defaut : http://localhost:11434/api)
"""

import sys, os, json, uuid, sqlite3
from datetime import datetime

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

# ── Configuration des LLM disponibles ─────────────────────────────────────
CONFIGS = {
    "ollama": {
        "llm_type":                   "LOCAL_OLLAMA",
        "llm_model":                  "mistral",
        "llm_endpoint":               "http://localhost:11434/api",
        "droits_agent":               ["PROPOSER"],
        "validation_humaine_requise": 0,
    },
    "claude": {
        "llm_type":                   "API_ANTHROPIC",
        "llm_model":                  "claude-sonnet-4-6",
        "llm_endpoint":               "https://api.anthropic.com/v1",
        "droits_agent":               ["PROPOSER", "LIRE_SEUL"],
        "validation_humaine_requise": 1,
    },
}

def make_did_key():
    return f"did:key:z{uuid.uuid4().hex}"

def now():
    return datetime.now().isoformat()

def add_agent(acteur_slug: str, llm_key: str):
    if llm_key not in CONFIGS:
        print(f"Type LLM inconnu : '{llm_key}'. Choix disponibles : {list(CONFIGS.keys())}")
        sys.exit(1)

    config = CONFIGS[llm_key]

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # Verifier que l'acteur existe
    acteur = con.execute(
        "SELECT uri, slug, label FROM acteurs WHERE slug = ?", (acteur_slug,)
    ).fetchone()
    if not acteur:
        print(f"⚠ Acteur introuvable : '{acteur_slug}'")
        print("  Verifie le slug avec : python3 list_actors.py")
        con.close()
        sys.exit(1)

    # Verifier si un agent existe deja pour cet acteur
    agent_existant = con.execute(
        "SELECT uri, llm_type, llm_model FROM agents WHERE acteur_uri = ?",
        (acteur["uri"],)
    ).fetchone()

    if agent_existant:
        print(f"\n⚠ Un agent existe deja pour '{acteur_slug}' :")
        print(f"   Type  : {agent_existant['llm_type']}")
        print(f"   Model : {agent_existant['llm_model']}")
        print()
        reponse = input("Remplacer cet agent ? (oui/non) : ").strip().lower()
        if reponse not in ("oui", "o", "yes", "y"):
            print("Operation annulee.")
            con.close()
            sys.exit(0)
        # Supprimer l'agent existant
        con.execute("DELETE FROM agents WHERE acteur_uri = ?", (acteur["uri"],))
        print(f"  Agent existant supprime.")

    # Creer le nouvel agent
    agent = {
        "uri":                        make_did_key(),
        "acteur_uri":                 acteur["uri"],
        "llm_type":                   config["llm_type"],
        "llm_endpoint":               config["llm_endpoint"],
        "llm_model":                  config["llm_model"],
        "rag_collection":             acteur_slug,
        "droits_agent":               json.dumps(config["droits_agent"]),
        "validation_humaine_requise": config["validation_humaine_requise"],
        "created_at":                 now(),
    }

    con.execute("""
        INSERT INTO agents
        (uri, acteur_uri, llm_type, llm_endpoint, llm_model,
         rag_collection, droits_agent, validation_humaine_requise, created_at)
        VALUES
        (:uri, :acteur_uri, :llm_type, :llm_endpoint, :llm_model,
         :rag_collection, :droits_agent, :validation_humaine_requise, :created_at)
    """, agent)

    con.commit()
    con.close()

    print(f"\n✓ Agent associe a '{acteur_slug}' :")
    print(f"  Type     : {config['llm_type']}")
    print(f"  Modele   : {config['llm_model']}")
    print(f"  Endpoint : {config['llm_endpoint']}")
    print(f"  Droits   : {config['droits_agent']}")
    print(f"  Validation humaine : {'oui' if config['validation_humaine_requise'] else 'non'}")
    print(f"  Collection RAG     : {acteur_slug}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage : python3 add_agent_to_actor.py <acteur_slug> <ollama|claude>")
        print()
        print("Exemple :")
        print("  python3 add_agent_to_actor.py zone-humide-de-briere ollama")
        print("  python3 add_agent_to_actor.py syndicat-mixte-du-bassin-versant claude")
        sys.exit(1)

    add_agent(
        acteur_slug = sys.argv[1],
        llm_key     = sys.argv[2],
    )
