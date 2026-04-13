"""
Agent RAG Ollama/Mistral pour un acteur P2M-CA.

Interroge le RAG ChromaDB de l'acteur, puis appelle Mistral
via l'API REST locale d'Ollama pour produire une reponse
structuree sur les regles de validation applicables.

Usage (module) :
    from agent_ollama import interroger_agent_ollama
    result = interroger_agent_ollama(acteur_slug, contexte_interaction)

Usage (test direct) :
    python3 agent_ollama.py <acteur_slug> "description de l'interaction"

Prerequis :
    - Ollama en cours d'execution (ollama serve)
    - Modele installe : ollama pull mistral
    - RAG construit : python3 build_rag.py <acteur_slug>
    - pip3 install chromadb sentence-transformers
"""

import sys, os, json, sqlite3
import urllib.request, urllib.error

DB_PATH  = os.path.expanduser("~/p2mca/registre/p2mca.db")
RAG_PATH = os.path.expanduser("~/p2mca/rag/chroma")

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"
N_RESULTS    = 5   # nombre de fragments RAG a injecter dans le contexte


# ── ChromaDB ──────────────────────────────────────────────────────────────

def get_rag_fragments(acteur_slug: str, requete: str, n: int = N_RESULTS):
    """
    Recherche les N ecritures les plus pertinentes dans le RAG de l'acteur.
    Retourne une liste de textes.
    """
    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError:
        print("ChromaDB manquant. Lance : pip3 install chromadb sentence-transformers")
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


# ── Appel Ollama ──────────────────────────────────────────────────────────

def appeler_ollama(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """Appel synchrone a l'API Ollama. Retourne le texte genere."""
    payload = json.dumps({
        "model":  model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data    = payload,
        headers = {"Content-Type": "application/json"},
        method  = "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Ollama inaccessible ({OLLAMA_URL}). "
            f"Lance 'ollama serve' et verifie que le modele est installe. Erreur : {e}"
        )


# ── Prompt de detection des regles de validation ──────────────────────────

PROMPT_TEMPLATE = """Tu es l'agent du registre P2M-CA pour l'acteur '{acteur_slug}'.
Tu dois analyser une nouvelle interaction proposee et determiner si des
validations sont requises avant son enregistrement.

=== REGISTRE DE L'ACTEUR (ecritures existantes pertinentes) ===
{fragments}

=== NOUVELLE INTERACTION PROPOSEE ===
{contexte}

=== INSTRUCTION ===
En te basant UNIQUEMENT sur le registre de l'acteur ci-dessus,
reponds en JSON strict (sans texte avant ni apres) avec ce format :

{{
  "validation_requise": true ou false,
  "validations": [
    {{
      "type_validation": "HUMAIN" | "CO_VALIDATION" | "VOTE" | "DELAI",
      "couche_ref": "nom de la couche qui impose cette regle",
      "motif": "explication courte (1 phrase)"
    }}
  ],
  "resume": "synthese en 1-2 phrases du contexte trouve dans le registre"
}}

Si aucune regle de validation n'est trouvee dans le registre,
retourne {{"validation_requise": false, "validations": [], "resume": "Aucune regle trouvee."}}
"""

def construire_prompt(acteur_slug: str, contexte: str, fragments: list) -> str:
    if fragments:
        fragments_txt = "\n---\n".join(fragments)
    else:
        fragments_txt = "(Aucune ecriture existante dans le registre de cet acteur)"

    return PROMPT_TEMPLATE.format(
        acteur_slug = acteur_slug,
        fragments   = fragments_txt,
        contexte    = contexte,
    )


# ── Fonction principale ───────────────────────────────────────────────────

def interroger_agent_ollama(acteur_slug: str, contexte_interaction: str) -> dict:
    """
    Interroge l'agent Ollama de l'acteur.

    Retourne un dict :
    {
        "validation_requise": bool,
        "validations": [...],
        "resume": str,
        "source": "ollama/mistral"
    }
    """
    # 1. Recuperer les fragments RAG
    fragments = get_rag_fragments(acteur_slug, contexte_interaction)

    # 2. Construire le prompt
    prompt = construire_prompt(acteur_slug, contexte_interaction, fragments)

    # 3. Appeler Mistral
    try:
        reponse_brute = appeler_ollama(prompt)
    except ConnectionError as e:
        print(f"  [Ollama] {e}")
        # Fallback : pas de validation si Ollama inaccessible
        return {
            "validation_requise": False,
            "validations":        [],
            "resume":             "Agent Ollama inaccessible — validation ignoree.",
            "source":             "ollama/mistral (inaccessible)"
        }

    # 4. Parser la reponse JSON
    try:
        # Nettoyer les eventuels blocs markdown ```json ... ```
        texte = reponse_brute.strip()
        if texte.startswith("```"):
            texte = texte.split("```")[1]
            if texte.startswith("json"):
                texte = texte[4:]
        result = json.loads(texte.strip())
        result["source"] = f"ollama/{OLLAMA_MODEL}"
        result["fragments_utilises"] = len(fragments)
        return result
    except json.JSONDecodeError:
        # Si Mistral n'a pas produit du JSON valide, on retourne sans validation
        print(f"  [Ollama] Reponse non-JSON pour '{acteur_slug}' : {reponse_brute[:100]}")
        return {
            "validation_requise": False,
            "validations":        [],
            "resume":             f"Reponse non parseable : {reponse_brute[:80]}",
            "source":             f"ollama/{OLLAMA_MODEL}"
        }


# ── Test direct ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage : python3 agent_ollama.py <acteur_slug> <description_interaction>")
        print('Exemple : python3 agent_ollama.py zone-humide-de-briere "Nouvelle restauration 5ha"')
        sys.exit(1)

    acteur_slug = sys.argv[1]
    contexte    = sys.argv[2]

    print(f"\nInterrogation de l'agent Ollama pour '{acteur_slug}'...")
    print(f"Contexte : {contexte}\n")

    result = interroger_agent_ollama(acteur_slug, contexte)

    print(json.dumps(result, indent=2, ensure_ascii=False))
