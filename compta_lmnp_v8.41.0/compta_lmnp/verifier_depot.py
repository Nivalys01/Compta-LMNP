# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Contrôle AVANT publication : rien de personnel ne doit partir dans un commit.

Pourquoi ce script existe
-------------------------
Une fuite dans un dépôt public est IRRÉVERSIBLE. Un fichier committé reste
dans l'historique après suppression, et un dépôt public est cloné, indexé et
archivé en quelques minutes. Le `.gitignore` protège — mais il se corrige, et
il s'est déjà trompé : sa version initiale portait une ligne `!reference/*.txt`
qui *dés-ignorait* explicitement la comptabilité réelle de l'auteur.

Ce script ne fait pas confiance au .gitignore : il regarde ce que git
publierait RÉELLEMENT, et cherche dedans les empreintes du dossier réel.

Usage :
    python verifier_depot.py          # avant chaque push
    python verifier_depot.py --json   # sortie exploitable par la CI
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Chemins qui ne doivent JAMAIS être publiés.
CHEMINS_INTERDITS = [
    re.compile(r"^reference/"),
    re.compile(r"^seed_exemple\.sql$"),
    re.compile(r"\.db$"), re.compile(r"\.sqlite3?$"),
    re.compile(r"^certs/"), re.compile(r"\.pem$"), re.compile(r"\.key$"),
    re.compile(r"^sauvegardes/"), re.compile(r"^archives/"),
    re.compile(r"^logs/"), re.compile(r"^imports_tmp/"),
    re.compile(r"^dossiers\.json$"),
    # FEC : seul celui de démonstration est autorisé
    re.compile(r"^(?!demo/FEC_DEMO_).*FEC\d{8}\.txt$"),
]

# Empreintes du dossier réel, cherchées DANS le contenu publié. Elles sont
# lues depuis le dossier privé quand il est là : le script n'a donc pas
# besoin de contenir lui-même les données qu'il protège.
def _empreintes() -> list[tuple[str, str]]:
    empreintes: list[tuple[str, str]] = []
    seed = os.path.join(HERE, "seed_exemple.sql")
    if os.path.exists(seed):
        src = open(seed, encoding="utf-8").read()
        m = re.search(r"INSERT INTO exploitant[^;]*?'([^']{4,})'", src, re.S)
        if m:
            empreintes.append(("nom de l'exploitant", m.group(1)))
        for siren in re.findall(r"'(\d{9})'", src):
            empreintes.append(("SIREN", siren))
        for adr in re.findall(r"'(\d+\s+[Rr]ue[^']{4,})'", src):
            empreintes.append(("adresse", adr))
    # Termes nominatifs à ne jamais publier (nom d'un tiers, fournisseurs) :
    # listés dans le dossier privé, jamais dans ce script — sans quoi le
    # contrôle publierait lui-même ce qu'il est chargé de traquer.
    termes = os.path.join(HERE, "reference", "termes_a_anonymiser.txt")
    if os.path.exists(termes):
        for ligne in open(termes, encoding="utf-8"):
            t = ligne.strip()
            if t and not t.startswith("#"):
                empreintes.append(("terme interdit de publication", t))
    ref = os.path.join(HERE, "reference")
    if os.path.isdir(ref):
        for f in os.listdir(ref):
            m = re.match(r"(\d{9})FEC", f)
            if m:
                empreintes.append(("SIREN (nom de fichier FEC)", m.group(1)))
    # dédoublonnage en conservant l'ordre
    vus, uniques = set(), []
    for quoi, valeur in empreintes:
        if valeur.lower() not in vus:
            vus.add(valeur.lower())
            uniques.append((quoi, valeur))
    return uniques


def _fichiers_publies() -> list[str]:
    """Ce que git publierait : suivis + non suivis non ignorés."""
    try:
        suivis = subprocess.run(
            ["git", "ls-files"], cwd=HERE, capture_output=True, text=True,
            check=True).stdout.split()
        autres = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=HERE,
            capture_output=True, text=True, check=True).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return sorted(set(suivis + autres))


def verifier() -> dict:
    fichiers = _fichiers_publies()
    alertes: list[dict] = []

    for f in fichiers:
        for motif in CHEMINS_INTERDITS:
            if motif.search(f):
                alertes.append({"gravite": "BLOQUANT", "fichier": f,
                                "motif": "chemin interdit de publication"})
                break

    empreintes = _empreintes()
    for f in fichiers:
        chemin = os.path.join(HERE, f)
        if not os.path.isfile(chemin) or os.path.getsize(chemin) > 5_000_000:
            continue
        try:
            contenu = open(chemin, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for quoi, valeur in empreintes:
            if valeur in contenu:
                alertes.append({"gravite": "BLOQUANT", "fichier": f,
                                "motif": f"contient une donnée réelle ({quoi})"})

    return {"fichiers_publies": len(fichiers), "empreintes_cherchees":
            len(empreintes), "alertes": alertes}


def main() -> int:
    r = verifier()
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 1 if r["alertes"] else 0

    print(f"Fichiers qui seraient publiés : {r['fichiers_publies']}")
    print(f"Empreintes du dossier réel recherchées : "
          f"{r['empreintes_cherchees']}")
    if not r["fichiers_publies"]:
        print("\n⚠ Aucun fichier listé : dépôt git non initialisé ici ?")
        return 0
    if not r["empreintes_cherchees"]:
        print("  (dossier privé absent : contrôle des chemins uniquement)")
    if r["alertes"]:
        print(f"\n✗ {len(r['alertes'])} PROBLÈME(S) — NE PAS PUBLIER :")
        for a in r["alertes"]:
            print(f"    {a['fichier']} — {a['motif']}")
        print("\n  Corrigez le .gitignore, retirez le fichier de l'index "
              "(git rm --cached), et relancez ce contrôle.")
        return 1
    print("\n✓ Aucune donnée personnelle dans ce qui serait publié.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
