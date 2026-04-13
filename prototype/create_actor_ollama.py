"""
Creer un acteur avec un agent LLM local (Ollama / Mistral).

Usage :
    python3 create_actor_ollama.py "Nom de l'acteur"

Prerequis :
    - Ollama installe et en cours d'execution (ollama serve)
    - Base initialisee (python3 init_db.py)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from create_actor_with_agent import create_actor_with_agent

if len(sys.argv) < 2:
    print("Usage : python3 create_actor_ollama.py \"Nom de l'acteur\"")
    sys.exit(1)

label = sys.argv[1]

create_actor_with_agent(
    label              = label,
    llm_type           = "LOCAL_OLLAMA",
    llm_model          = "mistral",
    llm_endpoint       = "http://localhost:11434/api",
    droits             = ["PROPOSER"],
    validation_humaine = False,
)
