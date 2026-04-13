"""
Afficher l'etat de l'index RAG ChromaDB pour tous les acteurs.

Usage :
    python3 status_rag.py
    python3 status_rag.py <acteur_slug>   # detail d'un acteur

Prerequis :
    pip3 install chromadb sentence-transformers
"""

import sys, os, sqlite3

DB_PATH  = os.path.expanduser("~/p2mca/registre/p2mca.db")
RAG_PATH = os.path.expanduser("~/p2mca/rag/chroma")

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:
    print("ChromaDB manquant. Lance : pip3 install chromadb sentence-transformers")
    sys.exit(1)

SEP = "─" * 70

def get_client():
    if not os.path.exists(RAG_PATH):
        print(f"Dossier RAG introuvable : {RAG_PATH}")
        print("Lance d'abord : python3 build_rag.py --all")
        sys.exit(1)
    return chromadb.PersistentClient(path=RAG_PATH)

def get_embed_fn():
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

def count_validated(acteur_slug):
    """Nombre d'ecritures VALIDATED dans SQLite pour cet acteur."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    row = con.execute("""
        SELECT COUNT(*) as n FROM ecritures e
        JOIN acteurs a ON e.acteur_uri = a.uri
        WHERE a.slug = ? AND e.statut_enregistrement = 'VALIDATED'
    """, (acteur_slug,)).fetchone()
    con.close()
    return row["n"] if row else 0

def status_acteur(client, embed_fn, acteur_slug, verbose=False):
    n_sql = count_validated(acteur_slug)
    try:
        col     = client.get_collection(acteur_slug, embedding_function=embed_fn)
        n_chroma = col.count()
        sync    = "✓" if n_chroma == n_sql else "⚠"
        note    = "" if n_chroma == n_sql else f"(SQLite:{n_sql} vs Chroma:{n_chroma} — relance build_rag.py)"
        print(f"  {sync} {acteur_slug:<40} {n_chroma:>4} fragments indexes  {note}")

        if verbose and n_chroma > 0:
            # Afficher les 3 premiers documents indexes
            items = col.get(limit=3)
            print(f"\n    Exemples de fragments indexes :")
            for doc in items["documents"]:
                print(f"    · {doc[:100].replace(chr(10),' ')}")
            print()

    except Exception:
        sync = "✗" if n_sql > 0 else "·"
        note = f"(non indexe — {n_sql} ecriture(s) VALIDATED en attente)" if n_sql > 0 else "(aucune ecriture VALIDATED)"
        print(f"  {sync} {acteur_slug:<40}    - fragments         {note}")

def status_all(verbose=False):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    acteurs = con.execute("SELECT slug FROM acteurs ORDER BY slug").fetchall()
    con.close()

    if not acteurs:
        print("Aucun acteur dans la base.")
        return

    client   = get_client()
    embed_fn = get_embed_fn()

    print(f"\n{SEP}")
    print(f"ETAT DU RAG — {RAG_PATH}")
    print(f"{SEP}")
    print(f"  {'ACTEUR':<40} {'CHROMA':>10}  NOTES")
    print(f"  {'-'*38} {'-'*10}  {'-'*20}")

    for a in acteurs:
        status_acteur(client, embed_fn, a["slug"], verbose)

    print(f"{SEP}")
    print()
    print("Legende : ✓ indexe et synchronise  ⚠ desynchronise  ✗ non indexe  · sans ecriture")
    print("Pour indexer : python3 build_rag.py --all")
    print()

if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    args    = [a for a in sys.argv[1:] if not a.startswith("-")]

    if args:
        client   = get_client()
        embed_fn = get_embed_fn()
        status_acteur(client, embed_fn, args[0], verbose=True)
    else:
        status_all(verbose)
