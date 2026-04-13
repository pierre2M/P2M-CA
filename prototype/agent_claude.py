"""
Agent RAG Claude (API Anthropic) pour un acteur P2M-CA.

Usage (module) :
    from agent_claude import interroger_agent_claude
    result = interroger_agent_claude(acteur_slug, contexte_interaction)

Usage (test direct) :
    python3 agent_claude.py <acteur_slug> "description de l'interaction"

Prerequis :
    - Variable ANTHROPIC_API_KEY definie
    - RAG construit : python3 build_rag.py <acteur_slug>
    - pip3 install anthropic chromadb sentence-transformers
"""

import sys, os, json

RAG_PATH = os.path.expanduser("~/p2mca/rag/chroma")

CLAUDE_MODEL = "claude-sonnet-4-6"
N_RESULTS    = 8


# ── ChromaDB ──────────────────────────────────────────────────────────────

def get_rag_fragments(acteur_slug: str, requete: str, n: int = N_RESULTS):
    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError:
        return []

    if not os.path.exists(RAG_PATH):
        return []

    try:
        client   = chromadb.PersistentClient(path=RAG_PATH)
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        collection = client.get_collection(
            name               = acteur_slug,
            embedding_function = embed_fn
        )
        results = collection.query(
            query_texts = [requete],
            n_results   = min(n, collection.count()),
        )
        return results["documents"][0] if results["documents"] else []
    except Exception as e:
        print(f"  [RAG] Collection '{acteur_slug}' inaccessible : {e}")
        return []


# ── Appel API Anthropic ───────────────────────────────────────────────────

def appeler_claude(system_prompt: str, user_message: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise ImportError("Package 'anthropic' manquant. Lance : pip3 install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("Variable ANTHROPIC_API_KEY non definie.")

    client  = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model      = CLAUDE_MODEL,
        max_tokens = 1024,
        system     = system_prompt,
        messages   = [{"role": "user", "content": user_message}],
    )
    return message.content[0].text


# ── Prompts ───────────────────────────────────────────────────────────────

# Regles strictes : ne signaler une validation QUE si le registre
# contient une regle explicite, pas par precaution generale.
SYSTEM_PROMPT = """Tu es l'agent du registre P2M-CA pour l'acteur '{acteur_slug}'.
Tu dois determiner si des validations sont requises avant d'enregistrer
une nouvelle interaction.

REGLE ABSOLUE : tu ne signales une validation requise QUE si le registre
de l'acteur contient une regle explicite qui l'impose.
- Si le registre est vide ou ne contient aucune regle de validation,
  tu retournes validation_requise: false, sans exception.
- Tu ne inventes pas de regles par prudence ou par precaution.
- Au maximum 1 validation par acteur sauf regle explicite contraire.

Reponds UNIQUEMENT en JSON valide, sans texte avant ni apres.
Format :
{{
  "validation_requise": true ou false,
  "validations": [
    {{
      "type_validation": "HUMAIN" | "CO_VALIDATION" | "VOTE" | "DELAI",
      "couche_ref": "nom de la couche source de la regle",
      "motif": "citation courte de la regle trouvee dans le registre"
    }}
  ],
  "resume": "1 phrase : ce que contient le registre de cet acteur"
}}"""

USER_TEMPLATE = """=== REGISTRE DE '{acteur_slug}' (ecritures existantes pertinentes) ===
{fragments}

=== NOUVELLE INTERACTION PROPOSEE ===
{contexte}

Y a-t-il dans le registre ci-dessus une regle explicite imposant
une validation pour cet acteur ? Reponds en JSON strict."""


def construire_messages(acteur_slug: str, contexte: str, fragments: list):
    system = SYSTEM_PROMPT.format(acteur_slug=acteur_slug)

    fragments_txt = (
        "\n---\n".join(fragments)
        if fragments
        else "(Registre vide — aucune ecriture existante pour cet acteur)"
    )

    user = USER_TEMPLATE.format(
        acteur_slug   = acteur_slug,
        fragments     = fragments_txt,
        contexte      = contexte,
    )
    return system, user


# ── Fonction principale ───────────────────────────────────────────────────

def interroger_agent_claude(acteur_slug: str, contexte_interaction: str) -> dict:
    fragments = get_rag_fragments(acteur_slug, contexte_interaction)
    system_prompt, user_message = construire_messages(
        acteur_slug, contexte_interaction, fragments
    )

    try:
        reponse_brute = appeler_claude(system_prompt, user_message)
    except (EnvironmentError, ImportError) as e:
        print(f"  [Claude] {e}")
        return {
            "validation_requise": False,
            "validations":        [],
            "resume":             f"Agent Claude inaccessible : {e}",
            "source":             "claude (inaccessible)"
        }

    try:
        texte = reponse_brute.strip()
        if texte.startswith("```"):
            texte = texte.split("```")[1]
            if texte.startswith("json"):
                texte = texte[4:]
        result = json.loads(texte.strip())
        result["source"]             = f"claude/{CLAUDE_MODEL}"
        result["fragments_utilises"] = len(fragments)
        return result
    except json.JSONDecodeError:
        print(f"  [Claude] Reponse non-JSON : {reponse_brute[:100]}")
        return {
            "validation_requise": False,
            "validations":        [],
            "resume":             f"Reponse non parseable : {reponse_brute[:80]}",
            "source":             f"claude/{CLAUDE_MODEL}"
        }


# ── Test direct ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage : python3 agent_claude.py <acteur_slug> <description>")
        sys.exit(1)

    result = interroger_agent_claude(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2, ensure_ascii=False))
