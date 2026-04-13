"""
Creer une couche interpretative P2M-CA a partir d'un fichier YAML.
La couche est elle-meme enregistree comme acteur dans le registre.

Usage :
    python3 create_layer.py c_ant_layer.yaml

Prerequis :
    - Migration lancee : python3 migrate_add_layers.py
    - PyYAML installe : pip3 install pyyaml
"""
import sys, os, json, uuid, sqlite3
from datetime import datetime

try:
    import yaml
except ImportError:
    print("PyYAML manquant. Lance : pip3 install pyyaml")
    sys.exit(1)

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

def make_did_key():
    return f"did:key:z{uuid.uuid4().hex}"

def now():
    return datetime.now().isoformat()

def create_layer(yaml_path: str):
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    slug        = data["slug"]
    label       = data.get("label", slug)
    description = data.get("description", "")
    auteur_slug = data.get("auteur_slug", None)
    parents     = data.get("couches_parentes", [])
    champs      = data.get("champs_definis", {})

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # Recuperer l'auteur si specifie
    auteur_uri = None
    if auteur_slug:
        row = con.execute("SELECT uri FROM acteurs WHERE slug = ?", (auteur_slug,)).fetchone()
        if row:
            auteur_uri = row["uri"]
        else:
            print(f"⚠ Auteur '{auteur_slug}' introuvable — couche creee sans auteur.")

    # Resoudre les URI des couches parentes
    parents_uris = []
    for p_slug in parents:
        row = con.execute("SELECT uri FROM couches WHERE slug = ?", (p_slug,)).fetchone()
        if row:
            parents_uris.append(row["uri"])
        else:
            print(f"⚠ Couche parente '{p_slug}' introuvable — ignoree.")

    # Creer l'URI de la couche
    couche_uri = make_did_key()

    # Enregistrer aussi la couche comme acteur (principe P2M-CA)
    try:
        con.execute("""
            INSERT INTO acteurs (uri, slug, label, created_at, registre_archive_uri)
            VALUES (?, ?, ?, ?, NULL)
        """, (couche_uri, slug, label, now()))
    except sqlite3.IntegrityError:
        # L'acteur existe deja (couche deja definie)
        row = con.execute("SELECT uri FROM acteurs WHERE slug = ?", (slug,)).fetchone()
        if row:
            couche_uri = row["uri"]
            print(f"  Acteur existant reutilise pour la couche : {slug}")

    # Enregistrer dans la table couches
    try:
        con.execute("""
            INSERT INTO couches
            (uri, slug, label, auteur_uri, couches_parentes_uri,
             description, champs_definis, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            couche_uri, slug, label, auteur_uri,
            json.dumps(parents_uris),
            description,
            json.dumps(champs, ensure_ascii=False),
            now()
        ))
        con.commit()
        print(f"\n✓ Couche creee : {slug}")
        print(f"  URI     : {couche_uri}")
        print(f"  Label   : {label}")
        print(f"  Parents : {', '.join(parents) if parents else '(aucun)'}")
        print(f"  Champs  : {len(champs)} definis")
        if champs:
            for nom, meta in champs.items():
                t = meta.get("type", "?") if isinstance(meta, dict) else "?"
                print(f"    - {nom} ({t})")
    except sqlite3.IntegrityError:
        print(f"⚠ La couche '{slug}' existe deja dans la table couches.")

    con.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python3 create_layer.py ma_couche.yaml")
        sys.exit(1)

    yaml_path = sys.argv[1]
    if not os.path.exists(yaml_path):
        print(f"Fichier introuvable : {yaml_path}")
        sys.exit(1)

    create_layer(yaml_path)
