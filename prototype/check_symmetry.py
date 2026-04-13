"""
Verifier la symetrie R1 dans le registre P2M-CA.

R1 : dans toute interaction entre acteurs A et B,
ce que A inscrit au DEBIT, B doit l'inscrire au CREDIT,
et vice-versa.

Le script detecte :
  - Les interactions ou un acteur a un DEBIT sans CREDIT (ou inverse)
  - Les interactions ou R1 est respectee (un DEBIT et un CREDIT par acteur)
  - Les cas legitimes de suspension de R1 (r1_suspendue = true dans C-SOLIDITE)

Usage :
    python3 check_symmetry.py                    # toutes les interactions
    python3 check_symmetry.py <interaction_slug> # une interaction
    python3 check_symmetry.py --fix              # propose des corrections
"""

import sys, os, json, sqlite3

DB_PATH = os.path.expanduser("~/p2mca/registre/p2mca.db")
SEP     = "─" * 70


def est_r1_suspendue(champs_couche_json):
    """Vrai si l'ecriture declare explicitement r1_suspendue = true."""
    if not champs_couche_json:
        return False
    try:
        champs = json.loads(champs_couche_json)
        return bool(champs.get("r1_suspendue", False))
    except Exception:
        return False


def analyser_interaction(con, interaction_slug):
    """
    Analyse la symetrie R1 d'une interaction.
    Retourne un dict avec les anomalies detectees.
    """
    interaction = con.execute(
        "SELECT uri, slug FROM interactions WHERE slug = ?",
        (interaction_slug,)
    ).fetchone()
    if not interaction:
        return None

    # Recuperer toutes les ecritures de cette interaction
    ecritures = con.execute("""
        SELECT
            e.uri, e.sens, e.couche_uri, e.champs_couche,
            a.slug AS acteur_slug, a.label AS acteur_label
        FROM ecritures e
        JOIN acteurs a ON e.acteur_uri = a.uri
        WHERE e.interaction_uri = ?
    """, (interaction["uri"],)).fetchall()

    # Construire un index {acteur_slug: {DEBIT: [...], CREDIT: [...]}}
    index = {}
    for e in ecritures:
        s = e["acteur_slug"]
        if s not in index:
            index[s] = {"DEBIT": [], "CREDIT": [], "r1_suspendue": False}
        index[s][e["sens"]].append(e)
        if est_r1_suspendue(e["champs_couche"]):
            index[s]["r1_suspendue"] = True

    # Analyser la symetrie
    anomalies   = []
    conformes   = []
    suspensions = []

    acteurs = list(index.keys())
    for acteur in acteurs:
        nb_debit  = len(index[acteur]["DEBIT"])
        nb_credit = len(index[acteur]["CREDIT"])
        suspendu  = index[acteur]["r1_suspendue"]

        if suspendu:
            suspensions.append({
                "acteur":    acteur,
                "nb_debit":  nb_debit,
                "nb_credit": nb_credit,
                "motif":     "r1_suspendue = true (C-SOLIDITE/IRREVERSIBLE)"
            })
        elif nb_debit == 0 and nb_credit == 0:
            pass  # acteur sans ecriture, ignore
        elif nb_debit == 0:
            anomalies.append({
                "acteur":    acteur,
                "type":      "CREDIT_SANS_DEBIT",
                "nb_debit":  nb_debit,
                "nb_credit": nb_credit,
                "message":   f"{acteur} a {nb_credit} CREDIT(s) mais 0 DEBIT"
            })
        elif nb_credit == 0:
            anomalies.append({
                "acteur":    acteur,
                "type":      "DEBIT_SANS_CREDIT",
                "nb_debit":  nb_debit,
                "nb_credit": nb_credit,
                "message":   f"{acteur} a {nb_debit} DEBIT(s) mais 0 CREDIT"
            })
        else:
            conformes.append({
                "acteur":    acteur,
                "nb_debit":  nb_debit,
                "nb_credit": nb_credit,
            })

    return {
        "slug":        interaction_slug,
        "uri":         interaction["uri"],
        "nb_acteurs":  len(acteurs),
        "conformes":   conformes,
        "anomalies":   anomalies,
        "suspensions": suspensions,
    }


def afficher_resultat(r, verbose=False):
    nb_anomalies = len(r["anomalies"])
    nb_suspend   = len(r["suspensions"])
    icone        = "✓" if nb_anomalies == 0 else "⚠"

    print(f"\n{icone} {r['slug']}")

    if r["conformes"] and verbose:
        for c in r["conformes"]:
            print(f"    ✓ {c['acteur']:<40} "
                  f"DEBIT:{c['nb_debit']}  CREDIT:{c['nb_credit']}")

    if nb_suspend:
        for s in r["suspensions"]:
            print(f"    ~ {s['acteur']:<40} R1 suspendue ({s['motif']})")

    if nb_anomalies:
        for a in r["anomalies"]:
            print(f"    ⚠ {a['message']}")
            print(f"      → Ajouter une ecriture {('DEBIT' if a['type'] == 'CREDIT_SANS_DEBIT' else 'CREDIT')} "
                  f"pour '{a['acteur']}' dans cette interaction.")


def check_all(con, verbose=False):
    interactions = con.execute(
        "SELECT slug FROM interactions ORDER BY slug"
    ).fetchall()

    if not interactions:
        print("Aucune interaction dans le registre.")
        return

    total_anomalies = 0
    print(f"\n{SEP}")
    print(f"VERIFICATION R1 — {len(interactions)} interaction(s)")
    print(f"{SEP}")

    for i in interactions:
        r = analyser_interaction(con, i["slug"])
        if r:
            afficher_resultat(r, verbose=verbose)
            total_anomalies += len(r["anomalies"])

    print(f"\n{SEP}")
    if total_anomalies == 0:
        print(f"✓ Toutes les interactions respectent R1.")
    else:
        print(f"⚠ {total_anomalies} anomalie(s) R1 detectee(s).")
        print(f"  Conseil : ajouter les ecritures manquantes dans les YAML")
        print(f"  ou verifier si R1 doit etre suspendue (r1_suspendue: true).")
    print(f"{SEP}\n")


def check_one(con, slug, verbose=True):
    r = analyser_interaction(con, slug)
    if not r:
        print(f"Interaction introuvable : {slug}")
        return

    print(f"\n{SEP}")
    print(f"VERIFICATION R1 — {slug}")
    print(f"{SEP}")
    afficher_resultat(r, verbose=verbose)

    if not r["anomalies"]:
        print(f"\n  ✓ R1 respectee pour tous les acteurs.")
    else:
        print(f"\n  ⚠ {len(r['anomalies'])} anomalie(s) detectee(s).")
        print(f"\n  Pour corriger : ajouter dans le YAML de l'interaction :")
        for a in r["anomalies"]:
            sens_manquant = "DEBIT" if a["type"] == "CREDIT_SANS_DEBIT" else "CREDIT"
            print(f"\n  - acteur_slug: \"{a['acteur']}\"")
            print(f"    sens: \"{sens_manquant}\"")
            print(f"    couche: \"...\"")
            print(f"    contenu: |")
            print(f"      [A completer]")
    print(f"{SEP}\n")


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    args    = [a for a in sys.argv[1:] if not a.startswith("-")]

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    if args:
        check_one(con, args[0], verbose=True)
    else:
        check_all(con, verbose=verbose)

    con.close()
