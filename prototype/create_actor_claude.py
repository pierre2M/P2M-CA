"""
Creer un acteur avec un agent API Claude (Anthropic).

Usage :
    python3 create_actor_claude.py "Nom de l'acteur"

Prerequis :
    - Variable d'environnement ANTHROPIC_API_KEY definie
    - Base initialisee (python3 init_db.py)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from create_actor_with_agent import create_actor_with_agent

if len(sys.argv) < 2:
    print("Usage : python3 create_actor_claude.py \"Nom de l'acteur\"")
    sys.exit(1)

label = sys.argv[1]

create_actor_with_agent(
    label              = label,
    llm_type           = "API_ANTHROPIC",
    llm_model          = "claude-sonnet-4-6",
    llm_endpoint       = "https://api.anthropic.com/v1",
    droits             = ["PROPOSER", "LIRE_SEUL"],
    validation_humaine = True,
)
