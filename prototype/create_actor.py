import uuid, json, sys, sqlite3, os
from datetime import datetime
import unicodedata, re

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

def make_did_key():
    return f"did:key:z{uuid.uuid4().hex}"

def make_slug(label: str) -> str:
    s = unicodedata.normalize('NFD', label.lower())
    s = s.encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s

label = sys.argv[1] if len(sys.argv) > 1 else "acteur-sans-nom"
actor = {
    "uri":                  make_did_key(),
    "slug":                 make_slug(label),
    "label":                label,
    "created_at":           datetime.now().isoformat(),
    "registre_archive_uri": None
}

con = sqlite3.connect(DB_PATH)
try:
    con.execute("""
        INSERT INTO acteurs (uri, slug, label, created_at, registre_archive_uri)
        VALUES (:uri, :slug, :label, :created_at, :registre_archive_uri)
    """, actor)
    con.commit()
    print("✓ Acteur enregistré :")
    print(json.dumps(actor, indent=2, ensure_ascii=False))
except sqlite3.IntegrityError:
    print(f"⚠ Un acteur avec le slug '{actor['slug']}' existe déjà.")
finally:
    con.close()