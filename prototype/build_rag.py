"""
Indexer les ecritures d'un acteur dans ChromaDB pour le RAG.

Usage :
    python3 build_rag.py <acteur_slug>        # indexer un acteur
    python3 build_rag.py --all                # indexer tous les acteurs
    python3 build_rag.py <acteur_slug> --reset # reinitialiser l'index

L'index est stocke dans ~/p2mca/rag/chroma/
Chaque acteur a sa propre collection ChromaDB (nom = slug de l'acteur).

Prerequis :
    pip3 install chromadb sentence-transformers
"""

import sys, os, json, sqlite3, argparse
from datetime import datetime

DB_PATH  = os.path.expanduser("~/p2mca/registre/p2mca.db")
RAG_PATH = os.path.expanduser("~/p2mca/rag/chroma")

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:
    print("ChromaDB manquant. Lance : pip3 install chromadb sentence-transformers")
    sys.exit(1)


# ── Client ChromaDB persistant ────────────────────────────────────────────

def get_chroma_client():
    os.makedirs(RAG_PATH, exist_ok=True)
    return chromadb.PersistentClient(path=RAG_PATH)

def get_embedding_fn():
    """Modele d'embedding local — all-MiniLM-L6-v2 (~90 Mo, telecharge au 1er usage)."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


# ── Construction du texte a indexer pour une ecriture ────────────────────

def ecriture_to_text(row):
    """
    Convertit une ecriture SQLite en texte pour l'embedding.
    Combine le contenu, les champs de couche et les metadonnees.
    """
    parties = []

    # En-tete
    parties.append(
        f"[{row['sens']}] Acteur : {row['acteur_slug']} | "
        f"Couche : {row['couche_uri'] or 'base'} | "
        f"Interaction : {row['interaction_slug']}"
    )

    # Contenu principal
    if row["contenu"]:
        parties.append(row["contenu"].strip())

    # Champs de couche (JSON → texte lisible)
    if row["champs_couche"]:
        try:
            champs = json.loads(row["champs_couche"])
            for k, v in champs.items():
                if v is not None:
                    if isinstance(v, list):
                        parties.append(f"{k} : {', '.join(str(x) for x in v)}")
                    else:
                        parties.append(f"{k} : {v}")
        except Exception:
            pass

    return "\n".join(parties)


def ecriture_to_metadata(row):
    """Metadonnees stockees dans ChromaDB pour filtrage ulterieur."""
    return {
        "acteur_slug":             row["acteur_slug"],
        "interaction_slug":        row["interaction_slug"],
        "sens":                    row["sens"],
        "couche_uri":              row["couche_uri"] or "base",
        "statut_enregistrement":   row["statut_enregistrement"],
        "date_proposition":        row["date_proposition"] or "",
        "phase_traduction":        _champ(row, "phase_traduction"),
        "solidite_de_l_enonce":    _champ(row, "solidite_de_l_enonce"),
        "registre_valuation":      _champ(row, "registre_valuation"),
        "statut_consentement":     _champ(row, "statut_consentement"),
        "type_deliberation":       _champ(row, "type_deliberation"),
        "solidite_enonce":         _champ(row, "solidite_enonce"),
    }

def _champ(row, nom):
    """Extrait un champ depuis le JSON champs_couche, retourne '' si absent."""
    if not row["champs_couche"]:
        return ""
    try:
        champs = json.loads(row["champs_couche"])
        val = champs.get(nom, "")
        return str(val) if val is not None else ""
    except Exception:
        return ""


# ── Indexation d'un acteur ────────────────────────────────────────────────

def index_acteur(acteur_slug: str, reset: bool = False):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # Verifier que l'acteur existe
    acteur = con.execute(
        "SELECT uri, label FROM acteurs WHERE slug = ?", (acteur_slug,)
    ).fetchone()
    if not acteur:
        print(f"⚠ Acteur introuvable : {acteur_slug}")
        con.close()
        return

    # Recuperer toutes les ecritures VALIDATED de cet acteur
    rows = con.execute("""
        SELECT
            e.uri, e.sens, e.contenu, e.couche_uri,
            e.champs_couche, e.statut_enregistrement,
            e.date_proposition, e.ecriture_anterieure_uri,
            a.slug AS acteur_slug,
            i.slug AS interaction_slug
        FROM ecritures e
        JOIN acteurs a ON e.acteur_uri = a.uri
        JOIN interactions i ON e.interaction_uri = i.uri
        WHERE a.slug = ?
          AND e.statut_enregistrement = 'VALIDATED'
        ORDER BY e.date_proposition
    """, (acteur_slug,)).fetchall()

    con.close()

    if not rows:
        print(f"  Aucune ecriture VALIDATED pour '{acteur_slug}' — index vide.")
        return

    # Collection ChromaDB
    client   = get_chroma_client()
    embed_fn = get_embedding_fn()

    if reset:
        try:
            client.delete_collection(acteur_slug)
            print(f"  Collection '{acteur_slug}' reinitialise.")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name               = acteur_slug,
        embedding_function = embed_fn,
        metadata           = {"acteur_slug": acteur_slug, "updated_at": datetime.now().isoformat()}
    )

    # Recuperer les IDs deja indexes pour eviter les doublons
    existing = set()
    try:
        existing = set(collection.get()["ids"])
    except Exception:
        pass

    # Indexer les ecritures nouvelles
    ids_new, docs_new, metas_new = [], [], []
    for row in rows:
        if row["uri"] in existing:
            continue
        ids_new.append(row["uri"])
        docs_new.append(ecriture_to_text(row))
        metas_new.append(ecriture_to_metadata(row))

    if not ids_new:
        print(f"  '{acteur_slug}' : {len(existing)} ecriture(s) deja indexee(s), rien de nouveau.")
        return

    # Ajout par lots de 50 (limite ChromaDB recommandee)
    batch = 50
    for i in range(0, len(ids_new), batch):
        collection.add(
            ids       = ids_new[i:i+batch],
            documents = docs_new[i:i+batch],
            metadatas = metas_new[i:i+batch],
        )

    total = len(existing) + len(ids_new)
    print(f"  ✓ '{acteur_slug}' : +{len(ids_new)} ecriture(s) indexee(s) ({total} au total)")


# ── Indexation de tous les acteurs ────────────────────────────────────────

def index_all(reset: bool = False):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    acteurs = con.execute("SELECT slug FROM acteurs ORDER BY slug").fetchall()
    con.close()

    if not acteurs:
        print("Aucun acteur dans la base.")
        return

    print(f"\nIndexation de {len(acteurs)} acteur(s)...\n")
    for a in acteurs:
        index_acteur(a["slug"], reset=reset)
    print("\n✓ Indexation terminee.")


# ── Point d'entree ────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indexer les ecritures P2M-CA dans ChromaDB")
    parser.add_argument("acteur", nargs="?", help="Slug de l'acteur a indexer (ou --all)")
    parser.add_argument("--all",   action="store_true", help="Indexer tous les acteurs")
    parser.add_argument("--reset", action="store_true", help="Reinitialiser l'index avant indexation")
    args = parser.parse_args()

    if args.all:
        index_all(reset=args.reset)
    elif args.acteur:
        print(f"\nIndexation de '{args.acteur}'...")
        index_acteur(args.acteur, reset=args.reset)
        print("✓ Termine.")
    else:
        parser.print_help()
