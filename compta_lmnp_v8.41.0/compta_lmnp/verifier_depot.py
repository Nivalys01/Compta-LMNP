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

Le périmètre est le DÉPÔT ENTIER, pas le paquet. `git ls-files` était lancé
depuis ce dossier-ci, donc ne listait que l'arborescence du logiciel : un
fichier placé à la racine du dépôt — un rapport d'audit dans docs/, une note
de travail — échappait au contrôle alors qu'un dépôt public l'expose comme
le reste. Le cas s'est produit : un rapport déposé dans docs/ portait le nom
réel de l'exploitant sans qu'aucun contrôle ne le voie.

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
#
# Les motifs s'ancrent sur un SEGMENT de chemin — « (^|/) » — et non sur le
# début de la chaîne : depuis que le contrôle porte sur le dépôt entier, les
# chemins sont relatifs à la RACINE du dépôt. Un « ^reference/ » ne verrait
# plus « compta_lmnp_v8.41.0/compta_lmnp/reference/ » — le contrôle serait
# devenu muet en donnant l'apparence de fonctionner, c'est-à-dire pire
# qu'absent.
CHEMINS_INTERDITS = [
    re.compile(r"(^|/)reference/"),
    re.compile(r"(^|/)seed_exemple\.sql$"),
    re.compile(r"\.db$"), re.compile(r"\.sqlite3?$"),
    re.compile(r"(^|/)certs/"), re.compile(r"\.pem$"), re.compile(r"\.key$"),
    re.compile(r"(^|/)sauvegardes/"), re.compile(r"(^|/)archives/"),
    re.compile(r"(^|/)logs/"), re.compile(r"(^|/)imports_tmp/"),
    re.compile(r"(^|/)dossiers\.json$"),
    # FEC : seul celui de démonstration est autorisé
    re.compile(r"(^|/)(?!FEC_DEMO_)[^/]*FEC\d{8}\.txt$"),
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


def racine_depot() -> str:
    """Racine du dépôt git, ou ce dossier si le dépôt n'existe pas.

    `git ls-files` ne liste que le sous-arbre du répertoire courant : lancé
    depuis le paquet, il rendait 87 fichiers là où le dépôt en suit 90, et
    docs/ n'était pas du nombre.
    """
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                           capture_output=True, text=True, check=True)
        return r.stdout.strip() or HERE
    except (subprocess.CalledProcessError, FileNotFoundError):
        return HERE


def _fichiers_publies(racine: str | None = None) -> list[str]:
    """Ce que git publierait : suivis + non suivis non ignorés.

    Chemins relatifs à la racine du dépôt, pas à ce dossier.
    """
    racine = racine or racine_depot()
    try:
        suivis = subprocess.run(
            ["git", "ls-files"], cwd=racine, capture_output=True, text=True,
            check=True).stdout.splitlines()
        autres = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=racine,
            capture_output=True, text=True, check=True).stdout.splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return sorted({f for f in suivis + autres if f})


def verifier(racine: str | None = None) -> dict:
    """`racine` n'est là que pour les tests : en usage réel, le contrôle
    trouve la racine du dépôt tout seul."""
    racine = racine or racine_depot()
    fichiers = _fichiers_publies(racine)
    alertes: list[dict] = []

    for f in fichiers:
        for motif in CHEMINS_INTERDITS:
            if motif.search(f):
                alertes.append({"gravite": "BLOQUANT", "fichier": f,
                                "motif": "chemin interdit de publication"})
                break

    empreintes = _empreintes()
    for f in fichiers:
        chemin = os.path.join(racine, f)
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
            len(empreintes), "alertes": alertes, "racine": racine}


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
