"""
Interface web P2M-CA v2 — FastAPI

Lance le serveur :
    python3 app.py
    puis ouvre http://localhost:8000 dans ton navigateur

Prerequis :
    pip3 install fastapi uvicorn pyyaml
"""

import os, sys, json, sqlite3, uuid
from datetime import datetime
from typing import Optional, List
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException, Request, Form
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("FastAPI manquant. Lance : pip3 install fastapi uvicorn")
    sys.exit(1)

# Ajouter le dossier p2mca au path pour importer les modules
sys.path.insert(0, os.path.dirname(__file__))

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")

app = FastAPI(title="P2M-CA v2", description="Registre relationnel P2M-CA")


# ── Helpers DB ────────────────────────────────────────────────────────────

def get_con():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con

def now():
    return datetime.now().isoformat()


# ── HTML de base ─────────────────────────────────────────────────────────

STYLE = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f4f6f9; color: #1a1a2e; font-size: 14px; }
  header { background: #1f3864; color: white; padding: 14px 28px;
           display: flex; align-items: center; gap: 20px; }
  header h1 { font-size: 20px; font-weight: 700; letter-spacing: 1px; }
  header nav a { color: #a8c4e0; text-decoration: none; margin-left: 18px;
                 font-size: 13px; }
  header nav a:hover { color: white; }
  .container { max-width: 1100px; margin: 28px auto; padding: 0 20px; }
  .card { background: white; border-radius: 8px; padding: 20px 24px;
          margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  .card h2 { font-size: 16px; color: #1f3864; margin-bottom: 14px;
             border-bottom: 2px solid #e8eef6; padding-bottom: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: #2e75b6; color: white; padding: 8px 12px;
       text-align: left; font-weight: 600; }
  td { padding: 7px 12px; border-bottom: 1px solid #e8eef6; vertical-align: top; }
  tr:hover td { background: #f0f5fb; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
           font-size: 11px; font-weight: 600; }
  .badge-ok  { background: #e2efda; color: #375623; }
  .badge-wait { background: #fff2cc; color: #7d5a00; }
  .badge-err { background: #fce4d6; color: #833c00; }
  .badge-base { background: #dae3f3; color: #1f3864; }
  a.btn { display: inline-block; padding: 6px 14px; border-radius: 5px;
          background: #2e75b6; color: white; text-decoration: none;
          font-size: 12px; font-weight: 600; }
  a.btn:hover { background: #1f3864; }
  a.btn-sm { padding: 3px 10px; font-size: 11px; }
  form input, form select, form textarea {
    border: 1px solid #cdd5e0; border-radius: 4px;
    padding: 6px 10px; font-size: 13px; width: 100%;
    margin-bottom: 10px; }
  form label { display: block; font-weight: 600; margin-bottom: 3px;
               color: #2e75b6; font-size: 12px; }
  form button { background: #2e75b6; color: white; border: none;
                padding: 8px 18px; border-radius: 5px; cursor: pointer;
                font-size: 13px; font-weight: 600; }
  form button:hover { background: #1f3864; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .mono { font-family: 'SF Mono', Consolas, monospace; font-size: 11px;
          color: #555; word-break: break-all; }
  .tag { background: #eef3fb; color: #2e75b6; padding: 1px 6px;
         border-radius: 3px; font-size: 11px; margin-right: 3px; }
  .alert { padding: 10px 14px; border-radius: 5px; margin-bottom: 14px;
           font-size: 13px; }
  .alert-ok  { background: #e2efda; color: #375623; }
  .alert-warn { background: #fff2cc; color: #7d5a00; }
  pre { background: #f5f7fa; border-radius: 4px; padding: 10px;
        font-size: 11px; overflow-x: auto; white-space: pre-wrap; }
</style>
"""

def page(title, content, active=""):
    nav_items = [
        ("Accueil", "/", "accueil"),
        ("Acteurs", "/acteurs", "acteurs"),
        ("Interactions", "/interactions", "interactions"),
        ("+ Interaction", "/interactions/nouvelle", "nouvelle"),
        ("Couches", "/couches", "couches"),
        ("Validations", "/validations", "validations"),
        ("R1 Symétrie", "/symetrie", "symetrie"),
    ]
    nav_html = "".join(
        f'<a href="{url}" style="{"color:white;font-weight:700" if k==active else ""}">{label}</a>'
        for label, url, k in nav_items
    )
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — P2M-CA</title>{STYLE}</head>
<body>
<header>
  <h1>P2M-CA v2</h1>
  <nav>{nav_html}</nav>
</header>
<div class="container">{content}</div>
</body></html>"""

def badge(statut):
    cls = {"VALIDATED": "badge-ok", "PENDING_VALIDATION": "badge-wait",
           "PROPOSED": "badge-wait", "REJECTED": "badge-err"}.get(statut, "badge-base")
    return f'<span class="badge {cls}">{statut}</span>'


# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def accueil():
    con = get_con()
    nb_acteurs       = con.execute("SELECT COUNT(*) FROM acteurs").fetchone()[0]
    nb_interactions  = con.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
    nb_ecritures     = con.execute("SELECT COUNT(*) FROM ecritures").fetchone()[0]
    nb_couches       = con.execute("SELECT COUNT(*) FROM couches").fetchone()[0]
    nb_en_attente    = con.execute(
        "SELECT COUNT(*) FROM validations_requises WHERE statut='EN_ATTENTE'"
    ).fetchone()[0]
    con.close()

    content = f"""
<div class="grid2">
  <div class="card">
    <h2>Registre P2M-CA</h2>
    <table>
      <tr><td>Acteurs</td><td><b>{nb_acteurs}</b></td>
          <td><a class="btn btn-sm" href="/acteurs">Voir</a></td></tr>
      <tr><td>Interactions</td><td><b>{nb_interactions}</b></td>
          <td><a class="btn btn-sm" href="/interactions">Voir</a></td></tr>
      <tr><td>Ecritures</td><td><b>{nb_ecritures}</b></td>
          <td></td></tr>
      <tr><td>Couches</td><td><b>{nb_couches}</b></td>
          <td><a class="btn btn-sm" href="/couches">Voir</a></td></tr>
      <tr><td>Validations en attente</td>
          <td><b style="color:{'#c00' if nb_en_attente else '#375623'}">{nb_en_attente}</b></td>
          <td><a class="btn btn-sm" href="/validations">Voir</a></td></tr>
    </table>
  </div>
  <div class="card">
    <h2>Actions rapides</h2>
    <p style="margin-bottom:10px">
      <a class="btn" href="/acteurs/nouveau">+ Nouvel acteur</a>
    </p>
    <p style="margin-bottom:10px">
      <a class="btn" href="/interactions">Voir les interactions</a>
    </p>
    <p>
      <a class="btn" href="/symetrie">Vérifier R1</a>
    </p>
  </div>
</div>"""
    return page("Accueil", content, "accueil")


# ── Acteurs ───────────────────────────────────────────────────────────────

@app.get("/acteurs", response_class=HTMLResponse)
def liste_acteurs():
    con = get_con()
    rows = con.execute("""
        SELECT a.slug, a.label, a.uri, a.created_at,
               ag.llm_type, ag.llm_model,
               COUNT(DISTINCT e.uri) AS nb_ecritures
        FROM acteurs a
        LEFT JOIN agents ag ON a.uri = ag.acteur_uri
        LEFT JOIN ecritures e ON a.uri = e.acteur_uri
        GROUP BY a.uri
        ORDER BY a.created_at DESC
    """).fetchall()
    con.close()

    lignes = ""
    for r in rows:
        llm = f'<span class="tag">{r["llm_type"]}</span><span class="tag">{r["llm_model"] or ""}</span>' if r["llm_type"] else '<span style="color:#999">—</span>'
        lignes += f"""<tr>
          <td><a href="/acteurs/{r['slug']}">{r['slug']}</a></td>
          <td>{r['label'] or ''}</td>
          <td>{llm}</td>
          <td style="text-align:center">{r['nb_ecritures']}</td>
          <td class="mono">{(r['created_at'] or '')[:16]}</td>
        </tr>"""

    content = f"""
<div class="card">
  <h2>Acteurs <a class="btn btn-sm" href="/acteurs/nouveau" style="float:right">+ Nouveau</a></h2>
  <table>
    <tr><th>Slug</th><th>Label</th><th>Agent LLM</th><th>Ecritures</th><th>Créé le</th></tr>
    {lignes or '<tr><td colspan="5" style="text-align:center;color:#999">Aucun acteur</td></tr>'}
  </table>
</div>"""
    return page("Acteurs", content, "acteurs")


@app.get("/acteurs/nouveau", response_class=HTMLResponse)
def form_nouvel_acteur():
    content = """
<div class="card">
  <h2>Créer un acteur</h2>
  <form method="post" action="/acteurs/nouveau">
    <label>Label (nom lisible)</label>
    <input name="label" placeholder="Zone humide de Brière" required>
    <label>Agent LLM</label>
    <select name="llm_type">
      <option value="">Sans agent</option>
      <option value="LOCAL_OLLAMA">Ollama / Mistral (local)</option>
      <option value="API_ANTHROPIC">Claude API (Anthropic)</option>
    </select>
    <button type="submit">Créer</button>
  </form>
</div>"""
    return page("Nouvel acteur", content, "acteurs")


@app.post("/acteurs/nouveau", response_class=HTMLResponse)
async def creer_acteur(label: str = Form(...), llm_type: str = Form("")):
    import re, unicodedata

    def make_slug(s):
        s = unicodedata.normalize("NFD", s.lower())
        s = s.encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

    slug = make_slug(label)
    uri  = f"did:key:z{uuid.uuid4().hex}"
    con  = get_con()

    try:
        con.execute(
            "INSERT INTO acteurs (uri, slug, label, created_at) VALUES (?,?,?,?)",
            (uri, slug, label, now())
        )
        if llm_type:
            configs = {
                "LOCAL_OLLAMA": ("http://localhost:11434/api", "mistral", 0),
                "API_ANTHROPIC": ("https://api.anthropic.com/v1", "claude-sonnet-4-6", 1),
            }
            endpoint, model, val_humaine = configs[llm_type]
            con.execute("""
                INSERT INTO agents (uri, acteur_uri, llm_type, llm_endpoint,
                  llm_model, rag_collection, droits_agent,
                  validation_humaine_requise, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (f"did:key:z{uuid.uuid4().hex}", uri, llm_type,
                  endpoint, model, slug,
                  json.dumps(["PROPOSER"]), val_humaine, now()))
        con.commit()
        con.close()
        return RedirectResponse(f"/acteurs/{slug}", status_code=303)
    except sqlite3.IntegrityError:
        con.close()
        content = f'<div class="card"><div class="alert alert-warn">Le slug <b>{slug}</b> existe déjà.</div><a class="btn" href="/acteurs/nouveau">Retour</a></div>'
        return HTMLResponse(page("Erreur", content, "acteurs"))


@app.get("/acteurs/{slug}", response_class=HTMLResponse)
def detail_acteur(slug: str):
    con = get_con()
    acteur = con.execute(
        "SELECT * FROM acteurs WHERE slug = ?", (slug,)
    ).fetchone()
    if not acteur:
        con.close()
        raise HTTPException(404, f"Acteur {slug} introuvable")

    agent = con.execute(
        "SELECT * FROM agents WHERE acteur_uri = ?", (acteur["uri"],)
    ).fetchone()

    ecritures = con.execute("""
        SELECT e.uri, e.sens, e.couche_uri, e.statut_enregistrement,
               i.slug AS inter_slug,
               substr(e.contenu, 1, 80) AS contenu_court
        FROM ecritures e
        JOIN interactions i ON e.interaction_uri = i.uri
        WHERE e.acteur_uri = ?
        ORDER BY e.date_proposition DESC
        LIMIT 20
    """, (acteur["uri"],)).fetchall()

    con.close()

    agent_html = ""
    if agent:
        agent_html = f"""
        <tr><td>LLM type</td><td><span class="tag">{agent['llm_type']}</span></td></tr>
        <tr><td>Modèle</td><td>{agent['llm_model']}</td></tr>
        <tr><td>Validation humaine</td><td>{'Oui' if agent['validation_humaine_requise'] else 'Non'}</td></tr>"""
    else:
        agent_html = "<tr><td colspan='2' style='color:#999'>Aucun agent associé</td></tr>"

    lignes_e = ""
    for e in ecritures:
        lignes_e += f"""<tr>
          <td><span class="tag">{e['sens']}</span></td>
          <td><a href="/interactions/{e['inter_slug']}">{e['inter_slug']}</a></td>
          <td>{e['couche_uri'] or '—'}</td>
          <td>{badge(e['statut_enregistrement'])}</td>
          <td style="color:#555">{(e['contenu_court'] or '').replace(chr(10),' ')[:70]}</td>
        </tr>"""

    content = f"""
<div class="grid2">
  <div class="card">
    <h2>{acteur['label'] or slug}</h2>
    <table>
      <tr><td>Slug</td><td class="mono">{slug}</td></tr>
      <tr><td>URI</td><td class="mono">{acteur['uri']}</td></tr>
      <tr><td>Créé le</td><td>{(acteur['created_at'] or '')[:16]}</td></tr>
      {agent_html}
    </table>
  </div>
  <div class="card">
    <h2>Dernières écritures</h2>
    <table>
      <tr><th>Sens</th><th>Interaction</th><th>Couche</th><th>Statut</th><th>Contenu</th></tr>
      {lignes_e or '<tr><td colspan="5" style="color:#999">Aucune écriture</td></tr>'}
    </table>
  </div>
</div>"""
    return page(f"Acteur — {slug}", content, "acteurs")


# ── Interactions ──────────────────────────────────────────────────────────

@app.get("/interactions", response_class=HTMLResponse)
def liste_interactions():
    con = get_con()
    rows = con.execute("""
        SELECT i.slug, i.created_at, i.couches_ref,
               COUNT(DISTINCT e.uri) AS nb_ecritures,
               SUM(CASE WHEN e.statut_enregistrement='VALIDATED' THEN 1 ELSE 0 END) AS nb_val,
               SUM(CASE WHEN e.statut_enregistrement='PENDING_VALIDATION' THEN 1 ELSE 0 END) AS nb_pend
        FROM interactions i
        LEFT JOIN ecritures e ON i.uri = e.interaction_uri
        GROUP BY i.uri
        ORDER BY i.created_at DESC
    """).fetchall()
    con.close()

    lignes = ""
    for r in rows:
        couches = ", ".join(json.loads(r["couches_ref"])) if r["couches_ref"] else ""
        statut  = "VALIDATED" if r["nb_pend"] == 0 else "PENDING_VALIDATION"
        lignes += f"""<tr>
          <td><a href="/interactions/{r['slug']}">{r['slug']}</a></td>
          <td>{badge(statut)}</td>
          <td style="text-align:center">{r['nb_ecritures']}</td>
          <td style="font-size:11px;color:#555">{couches[:60]}</td>
          <td class="mono">{(r['created_at'] or '')[:16]}</td>
        </tr>"""

    content = f"""
<div class="card">
  <h2>Interactions <a class="btn btn-sm" href="/interactions/nouvelle" style="float:right">+ Nouvelle</a></h2>
  <table>
    <tr><th>Slug</th><th>Statut</th><th>Ecritures</th><th>Couches</th><th>Créée le</th></tr>
    {lignes or '<tr><td colspan="5" style="text-align:center;color:#999">Aucune interaction</td></tr>'}
  </table>
</div>"""
    return page("Interactions", content, "interactions")


# ── Création d'interaction (formulaire multi-étapes) ─────────────────────
#
# Étape 1 GET  /interactions/nouvelle          → formulaire slug + couches + acteurs
# Étape 2 POST /interactions/nouvelle          → valide étape 1, stocke en session JSON
#              → redirige vers /interactions/nouvelle/ecritures?draft=<id>
# Étape 3 GET  /interactions/nouvelle/ecritures → formulaire d'ajout d'écritures
# Étape 4 POST /interactions/nouvelle/ecritures → ajoute une écriture au brouillon
# Étape 5 POST /interactions/nouvelle/enregistrer → enregistre l'interaction complète
#
# Le brouillon est stocké en mémoire (dict DRAFTS) identifié par un UUID.
# ─────────────────────────────────────────────────────────────────────────

DRAFTS: dict = {}   # draft_id → {slug, couches, acteurs, ecritures, validations}

COUCHES_CONNUES = ["C-ANT", "C-SOG", "C-SOG/biophysique", "C-SOG/monetaire",
                   "C-SOG/care", "C-CONSENTEMENT", "C-SOLIDITE", "C-GOUVERNANCE",
                   "C-BILAN", "C-LIFECYCLE", "C-AGENT"]

CHAMPS_PAR_COUCHE = {
    "C-ANT": [
        ("phase_traduction", "enum",
         "PROBLEMATISATION|INTERESSEMENT|ENROLEMENT|MOBILISATION|DISSIDENCE|CONTROVERSE|BOITE_NOIRE|CLOTURE"),
        ("ppo_uri",                  "text",  "URI du point de passage obligatoire"),
        ("auteur_effectif_uri",      "text",  "URI de l'auteur effectif (porte-parole)"),
        ("representativite_contestee","bool", "true / false"),
        ("sous_type_acteur_ant",     "enum",
         "TRADUCTEUR|PORTE_PAROLE|ACTANT_NON_HUMAIN|INTERMEDIAIRE|COLLECTEUR"),
        ("solidite_de_l_enonce",     "enum",
         "CONTROVERSE|PROVISOIRE|STABILISE|BOITE_NOIRE|IRREVERSIBLE"),
        ("role_negocie",             "text",  "Rôle accepté provisoirement"),
        ("modalite_negotiation",     "enum",
         "NEGOCIATION|COUP_DE_FORCE|PERSUASION|CONVENTION_TACITE"),
        ("convention_de_quantification", "textarea", "Présupposés de l'écriture"),
    ],
    "C-SOG": [
        ("registre_valuation",   "enum",     "BIOPHYSIQUE|MONETAIRE|CARE|HYBRIDE"),
        ("sous_type_outil",      "enum",     "VALUEMETER|PROCEDURE|SYSTEME_INFO|SCRIPT|METROLOGIE|CLASSEMENT"),
        ("fonction_outil",       "enum",     "EPISTEMIQUE|PRAGMATIQUE|POLITIQUE"),
        ("effet_premier_ordre",  "enum",     "VERIDICTION|VALORISATION|STRUCTURATION|SELECTION|REIFICATION|LEGITIMATION"),
        ("unite_mesure",         "text",     "Ex. : tCO2eq, ha, h/an, EUR"),
        ("valeur_quantitative",  "text",     "Valeur numérique"),
        ("periode_reference",    "text",     "Ex. : 2026, 2020-2025"),
        ("convention_de_quantification", "textarea", "Présupposés et exclusions"),
        ("effet_reactivite",     "textarea", "Effets de second ordre"),
    ],
    "C-CONSENTEMENT": [
        ("statut_consentement",  "enum",     "CONSENTI|CONTRAINT|INCONNU|EN_NEGOCIATION"),
        ("type_deliberation",    "enum",     "NEGOCIATION_EQUIVALENCE|CONTRO_VERIDICTION|CONTRE_INSCRIPTION|CO_VALIDATION"),
        ("acteurs_co_validateurs","text",    "Slugs séparés par des virgules"),
        ("contestation_convention","textarea","Description de la contestation"),
        ("convention_equivalence","textarea","Convention de conversion retenue"),
        ("effet_politique",      "textarea", "Effets de domination / émancipation"),
    ],
    "C-SOLIDITE": [
        ("solidite_enonce",      "enum",     "CONTROVERSE|PROVISOIRE|STABILISE|BOITE_NOIRE|IRREVERSIBLE"),
        ("seuil_non_retour",     "bool",     "true / false"),
        ("r1_suspendue",         "bool",     "true / false"),
        ("motif_suspension_r1",  "textarea", "Justification si r1_suspendue = true"),
        ("indicateur_vitalite",  "textarea", "Etat de l'asset-actif"),
    ],
}

def champs_form_html(couche):
    """Génère les champs HTML spécifiques à une couche."""
    champs = CHAMPS_PAR_COUCHE.get(couche, CHAMPS_PAR_COUCHE.get(couche.split("/")[0], []))
    if not champs:
        return ""
    html = '<div class="champs-couche" style="background:#f0f5fb;border-radius:6px;padding:14px;margin-top:8px">'
    html += f'<p style="font-size:11px;color:#2e75b6;font-weight:700;margin-bottom:10px">Champs spécifiques {couche}</p>'
    for nom, type_, aide in champs:
        html += f'<label>{nom} <span style="font-weight:400;color:#888">— {aide}</span></label>'
        if type_ == "textarea":
            html += f'<textarea name="champ__{nom}" rows="2" placeholder="{aide}"></textarea>'
        elif type_ == "enum":
            opts = "".join(f'<option value="{v}">{v}</option>' for v in aide.split("|"))
            html += f'<select name="champ__{nom}"><option value="">— choisir —</option>{opts}</select>'
        elif type_ == "bool":
            html += f'''<select name="champ__{nom}">
              <option value="">— choisir —</option>
              <option value="true">true</option>
              <option value="false">false</option>
            </select>'''
        else:
            html += f'<input name="champ__{nom}" placeholder="{aide}">'
    html += "</div>"
    return html


# ── Étape 1 : formulaire principal ────────────────────────────────────────

@app.get("/interactions/nouvelle", response_class=HTMLResponse)
def form_nouvelle_interaction():
    con = get_con()
    acteurs = con.execute(
        "SELECT slug, label FROM acteurs ORDER BY slug"
    ).fetchall()
    con.close()

    opts_acteurs = "".join(
        f'<option value="{a["slug"]}">{a["slug"]}'
        f'{" — " + a["label"] if a["label"] else ""}</option>'
        for a in acteurs
    )
    opts_couches = "".join(
        f'<option value="{c}">{c}</option>' for c in COUCHES_CONNUES
    )

    content = f"""
<div class="card">
  <h2>Nouvelle interaction — Étape 1 : définition</h2>
  <form method="post" action="/interactions/nouvelle">

    <label>Slug de l'interaction <span style="font-weight:400;color:#888">
      (identifiant unique, sans espaces ni accents)</span></label>
    <input name="slug" placeholder="restauration-zh-briere-2026-05" required
           pattern="[a-z0-9\\-]+" title="Minuscules, chiffres et tirets uniquement">

    <label>Couches mobilisées <span style="font-weight:400;color:#888">
      (Ctrl+clic pour sélection multiple)</span></label>
    <select name="couches" multiple size="6" style="height:auto">{opts_couches}</select>

    <label style="margin-top:10px">Acteurs concernés
      <span style="font-weight:400;color:#888">(Ctrl+clic pour sélection multiple)</span></label>
    <select name="acteurs" multiple size="6" style="height:auto">{opts_acteurs}</select>

    <label style="margin-top:10px">Validations requises explicites
      <span style="font-weight:400;color:#888">(optionnel — une par ligne, format :
      acteur_slug|TYPE — ex. : syndicat-mixte|HUMAIN)</span></label>
    <textarea name="validations" rows="3"
      placeholder="syndicat-mixte-du-bassin-versant|HUMAIN&#10;association-naturaliste-loire|CO_VALIDATION">
    </textarea>

    <button type="submit" style="margin-top:6px">Continuer → Ajouter les écritures</button>
  </form>
</div>"""
    return page("Nouvelle interaction", content, "nouvelle")


# ── Étape 2 : POST étape 1 → créer le brouillon ───────────────────────────

@app.post("/interactions/nouvelle", response_class=HTMLResponse)
async def creer_brouillon(request: Request):
    form    = await request.form()
    slug    = (form.get("slug") or "").strip().lower().replace(" ", "-")
    couches = form.getlist("couches")
    acteurs = form.getlist("acteurs")
    val_txt = (form.get("validations") or "").strip()

    # Validation basique
    errors = []
    if not slug:
        errors.append("Le slug est obligatoire.")
    if not couches:
        errors.append("Sélectionne au moins une couche.")
    if not acteurs:
        errors.append("Sélectionne au moins un acteur.")

    # Vérifier que le slug n'existe pas déjà
    con = get_con()
    existant = con.execute(
        "SELECT slug FROM interactions WHERE slug = ?", (slug,)
    ).fetchone()
    con.close()
    if existant:
        errors.append(f"Une interaction avec le slug '{slug}' existe déjà.")

    if errors:
        err_html = "".join(f'<div class="alert alert-warn">{e}</div>' for e in errors)
        content  = err_html + '<a class="btn" href="/interactions/nouvelle">Retour</a>'
        return HTMLResponse(page("Erreur", f'<div class="card">{content}</div>', "nouvelle"))

    # Parser les validations explicites
    validations = []
    for ligne in val_txt.splitlines():
        ligne = ligne.strip()
        if "|" in ligne:
            parts = ligne.split("|", 1)
            validations.append({"acteur_slug": parts[0].strip(), "type": parts[1].strip()})

    draft_id = uuid.uuid4().hex
    DRAFTS[draft_id] = {
        "slug":        slug,
        "couches":     couches,
        "acteurs":     acteurs,
        "ecritures":   [],
        "validations": validations,
    }
    return RedirectResponse(
        f"/interactions/nouvelle/ecritures?draft={draft_id}", status_code=303
    )


# ── Étape 3 : formulaire d'ajout d'écritures ──────────────────────────────

@app.get("/interactions/nouvelle/ecritures", response_class=HTMLResponse)
def form_ecritures(draft: str = ""):
    if draft not in DRAFTS:
        return RedirectResponse("/interactions/nouvelle", status_code=303)

    d       = DRAFTS[draft]
    slug    = d["slug"]
    couches = d["couches"]
    acteurs = d["acteurs"]
    ecritures_existantes = d["ecritures"]

    # Liste des écritures déjà saisies
    lignes_e = ""
    for i, e in enumerate(ecritures_existantes):
        champs_str = ""
        if e.get("champs_couche"):
            champs_str = " | ".join(
                f"{k}={v}" for k, v in e["champs_couche"].items() if v
            )[:80]
        lignes_e += f"""<tr>
          <td>{e['acteur_slug']}</td>
          <td><span class="tag">{e['sens']}</span></td>
          <td><span class="tag">{e['couche']}</span></td>
          <td style="font-size:11px;color:#555">{(e['contenu'] or '')[:60].replace(chr(10),' ')}</td>
          <td style="font-size:10px;color:#888">{champs_str}</td>
          <td>
            <form method="post" action="/interactions/nouvelle/ecritures/supprimer"
                  style="display:inline">
              <input type="hidden" name="draft" value="{draft}">
              <input type="hidden" name="index" value="{i}">
              <button type="submit"
                style="background:none;border:none;color:#c00;cursor:pointer;font-size:13px">✕</button>
            </form>
          </td>
        </tr>"""

    # Options pour les selects
    opts_acteurs = "".join(
        f'<option value="{a}">{a}</option>' for a in acteurs
    )
    opts_couches = "".join(
        f'<option value="{c}">{c}</option>' for c in couches
    )

    # Champs dynamiques par couche (affichés via JS selon la sélection)
    blocs_champs = ""
    for c in couches:
        html = champs_form_html(c)
        if html:
            blocs_champs += f'<div id="champs-{c.replace("/","-")}" class="couche-champs" style="display:none">{html}</div>'

    resume_val = ""
    if d["validations"]:
        items = ", ".join(f"{v['acteur_slug']} ({v['type']})" for v in d["validations"])
        resume_val = f'<p style="margin-top:6px;font-size:12px;color:#555">Validations prévues : {items}</p>'

    content = f"""
<div class="card">
  <h2>Nouvelle interaction <span style="color:#2e75b6">{slug}</span>
      — Étape 2 : écritures</h2>
  <p style="font-size:12px;color:#555;margin-bottom:12px">
    Couches : {'  '.join(f'<span class="tag">{c}</span>' for c in couches)} &nbsp;
    Acteurs : {'  '.join(f'<span class="tag">{a}</span>' for a in acteurs)}
  </p>
  {resume_val}
</div>

<div class="card">
  <h2>Écritures saisies ({len(ecritures_existantes)})</h2>
  {'<p style="color:#999">Aucune écriture pour l\'instant.</p>'
    if not ecritures_existantes else f"""
  <table>
    <tr><th>Acteur</th><th>Sens</th><th>Couche</th><th>Contenu</th><th>Champs couche</th><th></th></tr>
    {lignes_e}
  </table>"""}
</div>

<div class="card">
  <h2>Ajouter une écriture</h2>
  <form method="post" action="/interactions/nouvelle/ecritures" id="form-ecriture">
    <input type="hidden" name="draft" value="{draft}">

    <div class="grid2">
      <div>
        <label>Acteur</label>
        <select name="acteur_slug" required>{opts_acteurs}</select>
      </div>
      <div>
        <label>Sens</label>
        <select name="sens" required>
          <option value="DEBIT">DÉBIT — ce que l'acteur mobilise</option>
          <option value="CREDIT">CRÉDIT — ce que l'acteur fait ou doit</option>
        </select>
      </div>
    </div>

    <label>Couche</label>
    <select name="couche" required id="select-couche" onchange="afficherChamps(this.value)">
      {opts_couches}
    </select>

    <label style="margin-top:8px">Contenu <span style="font-weight:400;color:#888">
      (texte libre, markdown)</span></label>
    <textarea name="contenu" rows="4"
      placeholder="Description de la position de l'acteur..."></textarea>

    <label>Écriture antérieure <span style="font-weight:400;color:#888">
      (optionnel — slug d'interaction ou URI)</span></label>
    <input name="ecriture_anterieure_uri"
      placeholder="ex. : problematisation-baie-saint-brieuc-1974">

    {blocs_champs}

    <button type="submit" style="margin-top:10px">+ Ajouter cette écriture</button>
  </form>
</div>

<div class="card" style="background:#f0f8f0">
  <h2>Enregistrer l'interaction</h2>
  <p style="margin-bottom:12px;font-size:13px">
    {len(ecritures_existantes)} écriture(s) saisie(s).
    {'<b style="color:#c00">Attention : aucune écriture.</b> ' if not ecritures_existantes else ''}
    Clique sur "Enregistrer" pour créer l'interaction dans le registre.
  </p>
  <form method="post" action="/interactions/nouvelle/enregistrer">
    <input type="hidden" name="draft" value="{draft}">
    <button type="submit"
      style="background:#375623;padding:10px 24px;font-size:14px"
      {'disabled' if not ecritures_existantes else ''}>
      ✓ Enregistrer l'interaction
    </button>
    &nbsp;
    <a href="/interactions/nouvelle" style="font-size:12px;color:#888">Recommencer</a>
  </form>
</div>

<script>
function afficherChamps(couche) {{
  document.querySelectorAll('.couche-champs').forEach(el => el.style.display = 'none');
  const id = 'champs-' + couche.replace(/\\//g, '-');
  const el = document.getElementById(id);
  if (el) el.style.display = 'block';
}}
// Afficher les champs de la couche sélectionnée au chargement
window.addEventListener('DOMContentLoaded', () => {{
  const sel = document.getElementById('select-couche');
  if (sel) afficherChamps(sel.value);
}});
</script>"""

    return page("Nouvelle interaction", content, "nouvelle")


# ── Étape 4a : POST ajouter une écriture au brouillon ─────────────────────

@app.post("/interactions/nouvelle/ecritures", response_class=HTMLResponse)
async def ajouter_ecriture(request: Request):
    form  = await request.form()
    draft = form.get("draft", "")

    if draft not in DRAFTS:
        return RedirectResponse("/interactions/nouvelle", status_code=303)

    acteur_slug = (form.get("acteur_slug") or "").strip()
    sens        = (form.get("sens") or "").strip()
    couche      = (form.get("couche") or "").strip()
    contenu     = (form.get("contenu") or "").strip()
    ant_uri     = (form.get("ecriture_anterieure_uri") or "").strip() or None

    # Collecter les champs de couche (préfixés par "champ__")
    champs_couche = {}
    for key, val in form.items():
        if key.startswith("champ__") and val:
            nom = key[len("champ__"):]
            # Convertir les listes (acteurs_co_validateurs)
            if "," in val and "validateurs" in nom:
                champs_couche[nom] = [v.strip() for v in val.split(",")]
            elif val in ("true", "false"):
                champs_couche[nom] = val == "true"
            else:
                champs_couche[nom] = val

    ecriture = {
        "acteur_slug":             acteur_slug,
        "sens":                    sens,
        "couche":                  couche,
        "contenu":                 contenu,
        "ecriture_anterieure_uri": ant_uri,
        "champs_couche":           champs_couche if champs_couche else None,
    }
    DRAFTS[draft]["ecritures"].append(ecriture)

    return RedirectResponse(
        f"/interactions/nouvelle/ecritures?draft={draft}", status_code=303
    )


# ── Étape 4b : supprimer une écriture du brouillon ────────────────────────

@app.post("/interactions/nouvelle/ecritures/supprimer", response_class=HTMLResponse)
async def supprimer_ecriture(draft: str = Form(""), index: int = Form(0)):
    if draft in DRAFTS:
        ecritures = DRAFTS[draft]["ecritures"]
        if 0 <= index < len(ecritures):
            ecritures.pop(index)
    return RedirectResponse(
        f"/interactions/nouvelle/ecritures?draft={draft}", status_code=303
    )


# ── Étape 5 : enregistrer l'interaction complète ──────────────────────────

@app.post("/interactions/nouvelle/enregistrer", response_class=HTMLResponse)
async def enregistrer_interaction(draft: str = Form("")):
    if draft not in DRAFTS:
        return RedirectResponse("/interactions/nouvelle", status_code=303)

    d         = DRAFTS[draft]
    slug      = d["slug"]
    couches   = d["couches"]
    ecritures = d["ecritures"]
    val_decl  = d["validations"]

    from collections import defaultdict

    def make_uri():
        return f"did:key:z{uuid.uuid4().hex}"

    def ts():
        return datetime.now().isoformat()

    con = get_con()
    rapport = []
    try:
        # ── 1. Vérifier que les acteurs existent ──────────────────────
        acteur_slugs = list({e["acteur_slug"] for e in ecritures})
        acteurs_map  = {}
        for s in acteur_slugs:
            row = con.execute(
                "SELECT uri, slug, label FROM acteurs WHERE slug = ?", (s,)
            ).fetchone()
            if not row:
                raise ValueError(f"Acteur introuvable : '{s}'")
            acteurs_map[s] = dict(row)
            rapport.append(f"✓ Acteur trouvé : {s}")

        # ── 2. Créer l'interaction ────────────────────────────────────
        interaction_uri = make_uri()
        con.execute(
            "INSERT INTO interactions (uri, slug, created_at, couches_ref) VALUES (?,?,?,?)",
            (interaction_uri, slug, ts(), json.dumps(couches))
        )
        for s, a in acteurs_map.items():
            con.execute(
                "INSERT INTO acteurs_interaction (interaction_uri, acteur_uri, label) VALUES (?,?,?)",
                (interaction_uri, a["uri"], a["label"])
            )

        # ── 3. Déterminer les validations (déclarées + CO_VALIDATION détectées) ──
        toutes_val = []
        for v in val_decl:
            if not v:
                continue
            row = con.execute(
                "SELECT uri FROM acteurs WHERE slug = ?", (v["acteur_slug"],)
            ).fetchone()
            if row:
                toutes_val.append({
                    "acteur_validateur_uri": row["uri"],
                    "type_validation":       v["type"],
                    "couche_ref":            v.get("couche", "C-BASE"),
                    "motif":                 "Déclaré dans le formulaire.",
                })

        # Détecter CO_VALIDATION dans les écritures C-CONSENTEMENT
        for e in ecritures:
            champs = e.get("champs_couche") or {}
            if champs.get("type_deliberation") == "CO_VALIDATION":
                acteur_uri = acteurs_map[e["acteur_slug"]]["uri"]
                toutes_val.append({
                    "acteur_validateur_uri": acteur_uri,
                    "type_validation":       "CO_VALIDATION",
                    "couche_ref":            e.get("couche", "C-CONSENTEMENT"),
                    "motif":                 "CO_VALIDATION détectée dans écriture.",
                })
                break

        # Validation humaine si agent API_ANTHROPIC
        for s, a in acteurs_map.items():
            agent = con.execute(
                "SELECT validation_humaine_requise, llm_type FROM agents WHERE acteur_uri = ?",
                (a["uri"],)
            ).fetchone()
            if agent and agent["validation_humaine_requise"]:
                toutes_val.append({
                    "acteur_validateur_uri": a["uri"],
                    "type_validation":       "HUMAIN",
                    "couche_ref":            couches[0] if couches else "C-BASE",
                    "motif":                 f"Agent {agent['llm_type']} : validation humaine requise.",
                })

        # Déduplication
        seen, validations_uniques = set(), []
        for v in toutes_val:
            key = (v["acteur_validateur_uri"], v["type_validation"])
            if key not in seen:
                seen.add(key)
                validations_uniques.append(v)

        statut_global = "PENDING_VALIDATION" if validations_uniques else "VALIDATED"
        date_val      = ts() if statut_global == "VALIDATED" else None

        # ── 4. Créer les écritures ────────────────────────────────────
        compteur  = defaultdict(int)
        ecr_creees = []

        for e in ecritures:
            acteur      = acteurs_map[e["acteur_slug"]]
            couche_slug = e.get("couche", "")
            cle         = (e["acteur_slug"], e["sens"], couche_slug)
            index       = compteur[cle]
            compteur[cle] += 1

            couche_norm  = couche_slug.replace("/", "-").replace(" ", "-")
            ecriture_uri = f"{slug}#{e['acteur_slug']}#{e['sens']}#{couche_norm}#{index}"

            # Résoudre ecriture_anterieure
            ant_ref = e.get("ecriture_anterieure_uri")
            ant_uri = None
            if ant_ref:
                row = con.execute("SELECT uri FROM ecritures WHERE uri = ?", (ant_ref,)).fetchone()
                if not row:
                    row = con.execute("""
                        SELECT e2.uri FROM ecritures e2
                        JOIN interactions i2 ON e2.interaction_uri = i2.uri
                        WHERE i2.slug = ? AND e2.statut_enregistrement = 'VALIDATED'
                        ORDER BY e2.date_proposition LIMIT 1
                    """, (ant_ref,)).fetchone()
                ant_uri = row["uri"] if row else None

            champs = e.get("champs_couche")
            champs_json = json.dumps(champs, ensure_ascii=False) if champs else None

            rec = (ecriture_uri, interaction_uri, acteur["uri"],
                   e["sens"], e.get("contenu",""), couche_slug or None,
                   None, ant_uri, statut_global,
                   ts(), date_val, f"agent-de-{e['acteur_slug']}", champs_json)

            con.execute("""
                INSERT INTO ecritures
                (uri, interaction_uri, acteur_uri, sens, contenu, couche_uri,
                 ecriture_symetrique_uri, ecriture_anterieure_uri,
                 statut_enregistrement, date_proposition, date_validation,
                 propose_par_uri, champs_couche)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, rec)
            ecr_creees.append({"uri": ecriture_uri, "acteur_uri": acteur["uri"]})

        # ── 5. Enregistrer les validations ────────────────────────────
        for v in validations_uniques:
            ecriture_ref = next(
                (e["uri"] for e in ecr_creees
                 if e["acteur_uri"] == v["acteur_validateur_uri"]),
                ecr_creees[0]["uri"] if ecr_creees else None
            )
            con.execute("""
                INSERT INTO validations_requises
                (ecriture_uri, acteur_validateur_uri, type_validation,
                 couche_ref, statut, date_obtention, commentaire)
                VALUES (?,?,?,?,'EN_ATTENTE',NULL,?)
            """, (ecriture_ref, v["acteur_validateur_uri"],
                  v["type_validation"], v["couche_ref"], v.get("motif","")))

        con.commit()

        rapport.append(f"URI        : {interaction_uri}")
        rapport.append(f"Statut     : {statut_global}")
        rapport.append(f"Couches    : {', '.join(couches)}")
        rapport.append(f"Écritures  : {len(ecr_creees)}")
        if validations_uniques:
            rapport.append(f"Validations en suspens ({len(validations_uniques)}) :")
            for v in validations_uniques:
                row = con.execute(
                    "SELECT slug FROM acteurs WHERE uri = ?",
                    (v["acteur_validateur_uri"],)
                ).fetchone()
                aslug = row["slug"] if row else v["acteur_validateur_uri"]
                rapport.append(f"  ⏳ {v['type_validation']} — {aslug}")

    except Exception as e:
        con.close()
        content = f'''<div class="card">
  <div class="alert alert-warn">Erreur lors de l'enregistrement : {e}</div>
  <p style="margin-top:10px"><a class="btn" href="/interactions/nouvelle/ecritures?draft={draft}">Retour</a></p>
</div>'''
        return HTMLResponse(page("Erreur", content, "nouvelle"))

    con.close()

    # Nettoyer le brouillon
    del DRAFTS[draft]

    validated = statut_global == "VALIDATED"
    output    = "\n".join(rapport)

    content = f"""
<div class="card">
  <div class="alert {'alert-ok' if validated else 'alert-warn'}">
    {'✓ Interaction enregistrée directement (aucune validation requise).'
      if validated
      else '⏳ Interaction créée — validations en suspens.'}
  </div>
  <pre>{output}</pre>
  <p style="margin-top:14px">
    <a class="btn" href="/interactions/{slug}">Voir l'interaction</a>
    &nbsp;
    <a class="btn" href="/validations" style="background:#7d5a00">Voir les validations</a>
    &nbsp;
    <a class="btn" href="/interactions/nouvelle" style="background:#555">+ Nouvelle interaction</a>
  </p>
</div>"""
    return HTMLResponse(page("Interaction créée", content, "interactions"))



@app.get("/interactions/{slug}", response_class=HTMLResponse)
def detail_interaction(slug: str):
    con = get_con()
    inter = con.execute(
        "SELECT * FROM interactions WHERE slug = ?", (slug,)
    ).fetchone()
    if not inter:
        con.close()
        raise HTTPException(404)

    ecritures = con.execute("""
        SELECT e.uri, e.sens, e.couche_uri, e.contenu,
               e.statut_enregistrement, e.ecriture_anterieure_uri,
               e.champs_couche, a.slug AS acteur_slug
        FROM ecritures e
        JOIN acteurs a ON e.acteur_uri = a.uri
        WHERE e.interaction_uri = ?
        ORDER BY a.slug, e.sens, e.couche_uri
    """, (inter["uri"],)).fetchall()

    validations = con.execute("""
        SELECT vr.type_validation, vr.statut, vr.commentaire, vr.date_obtention,
               a.slug AS val_slug
        FROM validations_requises vr
        JOIN ecritures e ON vr.ecriture_uri = e.uri
        JOIN acteurs a   ON vr.acteur_validateur_uri = a.uri
        WHERE e.interaction_uri = ?
        ORDER BY vr.statut DESC
    """, (inter["uri"],)).fetchall()

    con.close()

    couches = json.loads(inter["couches_ref"]) if inter["couches_ref"] else []

    lignes_e = ""
    for e in ecritures:
        chaine = ""
        if e["ecriture_anterieure_uri"]:
            chaine = f'<br><span style="font-size:10px;color:#2e75b6">⇐ {e["ecriture_anterieure_uri"][:50]}</span>'

        champs_html = ""
        if e["champs_couche"]:
            try:
                champs = json.loads(e["champs_couche"])
                items  = [f"<b>{k}</b>: {str(v)[:60]}" for k, v in champs.items() if v]
                champs_html = "<br><small style='color:#666'>" + " | ".join(items[:4]) + "</small>"
            except Exception:
                pass

        contenu_court = (e["contenu"] or "").replace("\n", " ")[:100]
        lignes_e += f"""<tr>
          <td><a href="/acteurs/{e['acteur_slug']}">{e['acteur_slug']}</a></td>
          <td><span class="tag">{e['sens']}</span></td>
          <td><span class="tag">{e['couche_uri'] or 'base'}</span></td>
          <td>{badge(e['statut_enregistrement'])}</td>
          <td>{contenu_court}{champs_html}{chaine}</td>
        </tr>"""

    lignes_v = ""
    for v in validations:
        icone = "✓" if v["statut"] == "OBTENU" else "⏳"
        lignes_v += f"""<tr>
          <td>{icone}</td>
          <td>{v['type_validation']}</td>
          <td><a href="/acteurs/{v['val_slug']}">{v['val_slug']}</a></td>
          <td>{v['statut']}</td>
          <td>{v['date_obtention'] or '—'}</td>
        </tr>"""

    val_section = ""
    if validations:
        val_section = f"""
<div class="card">
  <h2>Validations</h2>
  <table>
    <tr><th></th><th>Type</th><th>Validateur</th><th>Statut</th><th>Date</th></tr>
    {lignes_v}
  </table>
</div>"""

    content = f"""
<div class="card">
  <h2>{slug}</h2>
  <div style="margin-bottom:10px">
    {''.join(f'<span class="tag">{c}</span>' for c in couches)}
  </div>
  <table>
    <tr><th>Acteur</th><th>Sens</th><th>Couche</th><th>Statut</th><th>Contenu</th></tr>
    {lignes_e or '<tr><td colspan="5" style="color:#999">Aucune écriture</td></tr>'}
  </table>
</div>
{val_section}"""
    return page(f"Interaction — {slug}", content, "interactions")


# ── Couches ───────────────────────────────────────────────────────────────

@app.get("/couches", response_class=HTMLResponse)
def liste_couches():
    con = get_con()
    rows = con.execute("""
        SELECT c.slug, c.label, c.couches_parentes_uri,
               c.created_at, c.description,
               (SELECT COUNT(*) FROM ecritures WHERE couche_uri = c.slug) AS nb_ecritures
        FROM couches c ORDER BY c.created_at
    """).fetchall()
    con.close()

    lignes = ""
    for r in rows:
        parents = ""
        if r["couches_parentes_uri"]:
            try:
                uris = json.loads(r["couches_parentes_uri"])
                parents = ", ".join(u[:20] for u in uris) if uris else "—"
            except Exception:
                pass
        desc = (r["description"] or "")[:80]
        lignes += f"""<tr>
          <td><b>{r['slug']}</b></td>
          <td>{r['label'] or ''}</td>
          <td style="color:#555;font-size:12px">{desc}</td>
          <td style="text-align:center">{r['nb_ecritures']}</td>
        </tr>"""

    content = f"""
<div class="card">
  <h2>Couches interprétatives</h2>
  <table>
    <tr><th>Slug</th><th>Label</th><th>Description</th><th>Ecritures</th></tr>
    {lignes or '<tr><td colspan="4" style="color:#999">Aucune couche</td></tr>'}
  </table>
</div>"""
    return page("Couches", content, "couches")


# ── Validations ───────────────────────────────────────────────────────────

@app.get("/validations", response_class=HTMLResponse)
def liste_validations():
    con = get_con()
    rows = con.execute("""
        SELECT vr.id, vr.type_validation, vr.statut,
               vr.couche_ref, vr.commentaire, vr.date_obtention,
               a_val.slug AS val_slug,
               i.slug     AS inter_slug
        FROM validations_requises vr
        JOIN ecritures e    ON vr.ecriture_uri         = e.uri
        JOIN interactions i ON e.interaction_uri        = i.uri
        JOIN acteurs a_val  ON vr.acteur_validateur_uri = a_val.uri
        ORDER BY vr.statut DESC, i.slug
    """).fetchall()
    con.close()

    lignes = ""
    for r in rows:
        icone = "✓" if r["statut"] == "OBTENU" else "⏳"
        form_val = ""
        if r["statut"] == "EN_ATTENTE":
            form_val = f"""
            <form method="post" action="/validations/{r['id']}/valider" style="display:inline">
              <button type="submit" style="padding:3px 10px;font-size:11px;
                background:#375623;color:white;border:none;border-radius:4px;cursor:pointer">
                Valider
              </button>
            </form>"""
        lignes += f"""<tr>
          <td>{icone}</td>
          <td><a href="/interactions/{r['inter_slug']}">{r['inter_slug']}</a></td>
          <td>{r['type_validation']}</td>
          <td><a href="/acteurs/{r['val_slug']}">{r['val_slug']}</a></td>
          <td>{r['statut']}</td>
          <td>{r['date_obtention'] or '—'}</td>
          <td>{form_val}</td>
        </tr>"""

    content = f"""
<div class="card">
  <h2>Validations</h2>
  <table>
    <tr><th></th><th>Interaction</th><th>Type</th><th>Validateur</th>
        <th>Statut</th><th>Date</th><th>Action</th></tr>
    {lignes or '<tr><td colspan="7" style="color:#999">Aucune validation</td></tr>'}
  </table>
</div>"""
    return page("Validations", content, "validations")


@app.post("/validations/{val_id}/valider", response_class=HTMLResponse)
def valider(val_id: int):
    con = get_con()
    val = con.execute(
        "SELECT * FROM validations_requises WHERE id = ?", (val_id,)
    ).fetchone()
    if not val:
        con.close()
        raise HTTPException(404)

    con.execute("""
        UPDATE validations_requises
        SET statut='OBTENU', date_obtention=?, commentaire='Validé via interface web.'
        WHERE id=?
    """, (now(), val_id))

    # Verifier si toutes les validations de l'interaction sont obtenues
    ecriture = con.execute(
        "SELECT interaction_uri FROM ecritures WHERE uri = ?",
        (val["ecriture_uri"],)
    ).fetchone()

    if ecriture:
        en_attente = con.execute("""
            SELECT COUNT(*) FROM validations_requises vr
            JOIN ecritures e ON vr.ecriture_uri = e.uri
            WHERE e.interaction_uri = ? AND vr.statut = 'EN_ATTENTE'
        """, (ecriture["interaction_uri"],)).fetchone()[0]

        if en_attente == 0:
            con.execute("""
                UPDATE ecritures SET statut_enregistrement='VALIDATED', date_validation=?
                WHERE interaction_uri=?
            """, (now(), ecriture["interaction_uri"]))

    con.commit()
    con.close()
    return RedirectResponse("/validations", status_code=303)


# ── Symétrie R1 ───────────────────────────────────────────────────────────

@app.get("/symetrie", response_class=HTMLResponse)
def symetrie():
    con = get_con()
    interactions = con.execute(
        "SELECT slug FROM interactions ORDER BY slug"
    ).fetchall()
    con.close()

    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from check_symmetry import analyser_interaction
    except ImportError:
        content = '<div class="card"><div class="alert alert-warn">check_symmetry.py introuvable.</div></div>'
        return page("Symétrie R1", content, "symetrie")

    con = get_con()
    lignes = ""
    total_anomalies = 0

    for i in interactions:
        r = analyser_interaction(con, i["slug"])
        if not r:
            continue
        nb_a   = len(r["anomalies"])
        nb_ok  = len(r["conformes"])
        nb_sus = len(r["suspensions"])
        total_anomalies += nb_a
        icone  = "✓" if nb_a == 0 else "⚠"
        detail = ""
        if nb_a:
            detail = "; ".join(a["message"] for a in r["anomalies"])
        lignes += f"""<tr>
          <td>{icone}</td>
          <td><a href="/interactions/{r['slug']}">{r['slug']}</a></td>
          <td style="text-align:center;color:#375623">{nb_ok}</td>
          <td style="text-align:center;color:#c00">{nb_a}</td>
          <td style="text-align:center;color:#7d5a00">{nb_sus}</td>
          <td style="font-size:11px;color:#c00">{detail}</td>
        </tr>"""

    con.close()

    alerte = (f'<div class="alert alert-warn">⚠ {total_anomalies} anomalie(s) R1 detectee(s).</div>'
              if total_anomalies
              else '<div class="alert alert-ok">✓ Toutes les interactions respectent R1.</div>')

    content = f"""
<div class="card">
  <h2>Vérification de la symétrie R1</h2>
  {alerte}
  <table>
    <tr><th></th><th>Interaction</th><th>Conformes</th>
        <th>Anomalies</th><th>R1 suspendues</th><th>Détail</th></tr>
    {lignes or '<tr><td colspan="6" style="color:#999">Aucune interaction</td></tr>'}
  </table>
</div>"""
    return page("Symétrie R1", content, "symetrie")


# ── API JSON (pour usage programmatique) ─────────────────────────────────

@app.get("/api/acteurs")
def api_acteurs():
    con = get_con()
    rows = con.execute("SELECT uri, slug, label, created_at FROM acteurs").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/api/interactions")
def api_interactions():
    con = get_con()
    rows = con.execute("SELECT uri, slug, created_at, couches_ref FROM interactions").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/api/interactions/{slug}/ecritures")
def api_ecritures(slug: str):
    con = get_con()
    rows = con.execute("""
        SELECT e.*, a.slug AS acteur_slug
        FROM ecritures e
        JOIN acteurs a ON e.acteur_uri = a.uri
        JOIN interactions i ON e.interaction_uri = i.uri
        WHERE i.slug = ?
    """, (slug,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Lancement ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\nServeur P2M-CA démarré : http://localhost:8000")
    print("Ctrl+C pour arrêter.\n")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
