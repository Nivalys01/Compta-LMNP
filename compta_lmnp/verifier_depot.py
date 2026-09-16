# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
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
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))

# Chemins qui ne doivent JAMAIS être publiés.
#
# Les motifs s'ancrent sur un SEGMENT de chemin — « (^|/) » — et non sur le
# début de la chaîne : depuis que le contrôle porte sur le dépôt entier, les
# chemins sont relatifs à la RACINE du dépôt. Un « ^reference/ » ne verrait
# plus « compta_lmnp/reference/ » — le contrôle serait
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

# Formats dont le texte est compressé ou encodé : les lire ne prouve rien.
# Le .pdf y reste pour le REPLI seulement : il est lu par extraction (voir
# texte_du_pdf), et ne retombe dans cette liste que lorsque l'extraction
# n'a pas pu avoir lieu.
OPAQUES = (".pdf", ".zip", ".gz", ".tar", ".7z", ".rar", ".docx", ".xlsx",
           ".pptx", ".odt", ".ods", ".png", ".jpg", ".jpeg", ".webp", ".db",
           ".sqlite", ".sqlite3")

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


def normaliser(texte: str) -> str:
    """Forme de comparaison : minuscules, accents repliés, espaces réduits.

    La recherche se faisait par sous-chaîne EXACTE (`valeur in contenu`).
    « Martin Camille », « MARTIN  CAMILLE » (deux espaces) et un nom coupé
    par un retour à la ligne passaient donc au travers — alors qu'un nom
    recopié dans une documentation ou un commentaire ne reprend presque
    jamais la casse exacte du seed. Le dédoublonnage juste au-dessus
    comparait pourtant déjà en minuscules : l'intention était là, la
    comparaison qui compte ne l'appliquait pas (constat F-09).
    """
    texte = unicodedata.normalize("NFD", (texte or "").lower())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(texte.split())


# Quantité de texte extrait en deçà de laquelle un PDF n'est PAS réputé
# inspecté. Un PDF scanné, ou fait d'images, rend zéro caractère ou trois
# parasites : l'extraction « réussit » sans rien montrer. Conclure au vert
# là-dessus reviendrait à dire « rien à voir » pour « rien vu » — l'erreur
# même que l'avertissement des formats opaques était censé empêcher.
TEXTE_PDF_MINIMUM = 40


def texte_du_pdf(chemin: str) -> tuple[str | None, str]:
    """(texte, réserve) — la réserve est vide quand la lecture fait foi.

    `texte` vaut None lorsque l'extraction n'a pas pu avoir lieu du tout :
    le motif dit alors pourquoi. Lorsqu'elle a eu lieu mais n'a presque rien
    rendu, le texte est renvoyé QUAND MÊME, avec une réserve : une empreinte
    trouvée dans ces quelques caractères reste une fuite, et un nom seul
    tient en moins de vingt signes. La réserve ne sert qu'à défaut — voir
    verifier().

    Le PDF était rangé parmi les formats opaques, au même titre qu'une
    archive ou une image. Il ne l'est pas : son texte s'extrait, et les
    preuves versionnées dans docs/ sont justement des PDF de texte. La
    solution de facilité — exempter docs/preuves_* par son chemin —
    rouvrait exactement le trou décrit dans verifier() : un PDF réel
    déposé là serait passé sans être vu, et c'est le dossier où l'on
    dépose des sorties fraîchement produites.

    L'extraction passe par pdftotext (poppler), dont la suite de tests
    dépend déjà. Absent, en échec ou muet, le PDF redevient un
    AVERTISSEMENT : le contrôle ne dit « inspecté » que lorsqu'il a
    effectivement lu quelque chose.
    """
    try:
        r = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8",
                            chemin, "-"], capture_output=True, timeout=60)
    except FileNotFoundError:
        return None, ("PDF non inspecté — pdftotext (poppler) absent de "
                      "cette machine : vérifiez à la main qu'il ne porte "
                      "aucune donnée personnelle")
    except (subprocess.TimeoutExpired, OSError):
        return None, ("PDF non inspecté — extraction interrompue : "
                      "vérifiez à la main qu'il ne porte aucune donnée "
                      "personnelle")
    if r.returncode != 0:
        return None, ("PDF non inspecté — extraction en échec (fichier "
                      "chiffré ou abîmé ?) : vérifiez à la main qu'il ne "
                      "porte aucune donnée personnelle")
    texte = (r.stdout or b"").decode("utf-8", "replace")
    if len("".join(texte.split())) < TEXTE_PDF_MINIMUM:
        return texte, ("PDF sans texte extractible (image ou document "
                       "scanné) — vérifiez à la main qu'il ne porte aucune "
                       "donnée personnelle")
    return texte, ""


def empreintes() -> list[tuple[str, str]]:
    """Empreintes du dossier réel. Publique : la construction du paquet s'en
    sert aussi, pour ne pas dupliquer la définition de ce qui est sensible."""
    return _empreintes()


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

    # ── F-02 : ne rien pouvoir lister n'est pas « rien à signaler » ─────
    #    git absent du PATH, dépôt non initialisé, commande en échec :
    #    _fichiers_publies() rend [] et le contrôle concluait au vert.
    if not fichiers:
        alertes.append({"gravite": "BLOQUANT", "fichier": "(dépôt)",
                        "motif": "aucun fichier listé — dépôt git absent ou "
                                 "commande git en échec : le contrôle n'a rien "
                                 "pu examiner"})

    # ── F-01 : sans empreintes, le contrôle ne peut PAS conclure ────────
    #    Le dossier privé déplacé, un clone, un runner de CI : la liste est
    #    vide et le verdict restait « aucune donnée personnelle ». Un
    #    garde-fou qui approuve quand il ne peut pas travailler est pire
    #    que pas de garde-fou, parce qu'on lui fait confiance.
    liste = _empreintes()
    if not liste:
        alertes.append({"gravite": "BLOQUANT", "fichier": "(empreintes)",
                        "motif": "aucune empreinte chargée — dossier privé "
                                 "absent : le contrôle de CONTENU n'a pas eu "
                                 "lieu, seuls les chemins ont été vus"})

    cherchees = [(quoi, normaliser(valeur)) for quoi, valeur in liste]
    for f in fichiers:
        chemin = os.path.join(racine, f)
        if not os.path.isfile(chemin):
            continue
        # F-12 : un fichier trop gros ou illisible était sauté EN SILENCE.
        # Il est désormais signalé — un export comptable dépasse 5 Mo, et
        # aucun motif de chemin ne couvre un .txt volumineux à la racine.
        try:
            taille = os.path.getsize(chemin)
        except OSError:
            taille = 0
        if taille > 5_000_000:
            alertes.append({"gravite": "AVERTISSEMENT", "fichier": f,
                            "motif": f"non examiné ({taille // 1_000_000} Mo) "
                                     "— vérifiez son contenu à la main"})
            continue
        try:
            # F-12 : errors="ignore" en utf-8 SUPPRIMAIT les accents d'un
            # fichier cp1252 — « MARTÍN » devenait « MARTN » et l'empreinte
            # ne matchait plus. On tente cp1252 en repli, comme l'import.
            brut = open(chemin, "rb").read()
        except OSError as exc:
            alertes.append({"gravite": "AVERTISSEMENT", "fichier": f,
                            "motif": f"illisible ({exc.__class__.__name__}) "
                                     "— non examiné"})
            continue
        # Formats dont le contenu N'EST PAS inspectable : le texte y est
        # compressé (archives, bureautique, images) et la recherche
        # d'empreintes n'y trouverait rien — sans échouer pour autant. Le
        # cas s'est produit : un bilan comptable RÉEL, déposé en PDF à la
        # racine, n'était ni suivi ni ignoré ; le contrôle le lisait comme
        # du cp1252, n'y voyait aucune empreinte, et concluait au vert.
        # Un format qu'on ne sait pas lire doit être DIT, pas traversé.
        #
        # Le PDF fait exception depuis : son texte s'extrait vraiment, donc
        # il est lu comme les autres fichiers, et les empreintes y sont
        # cherchées. Ce n'est qu'à défaut d'extraction qu'il redevient un
        # avertissement — jamais un chemin exempté.
        reserve = ""
        if f.lower().endswith(".pdf"):
            contenu, reserve = texte_du_pdf(chemin)
            if contenu is None:
                alertes.append({"gravite": "AVERTISSEMENT", "fichier": f,
                                "motif": reserve})
                continue
        elif f.lower().endswith(OPAQUES):
            alertes.append({"gravite": "AVERTISSEMENT", "fichier": f,
                            "motif": "format dont le contenu n'est pas "
                                     "inspectable — vérifiez à la main qu'il "
                                     "ne porte aucune donnée personnelle"})
            continue
        else:
            contenu = None
            for enc in ("utf-8", "cp1252"):
                try:
                    contenu = brut.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if contenu is None:
                alertes.append({"gravite": "AVERTISSEMENT", "fichier": f,
                                "motif": "binaire non décodable — contenu "
                                         "non examiné"})
                continue
        normalise = normaliser(contenu)
        vu = False
        for quoi, valeur in cherchees:
            if valeur and valeur in normalise:
                vu = True
                alertes.append({"gravite": "BLOQUANT", "fichier": f,
                                "motif": f"contient une donnée réelle ({quoi})"})
        # La réserve d'un PDF presque muet ne se prononce qu'ici : ce qui a
        # été lu passe d'abord au tamis des empreintes, et l'avertissement
        # ne vient que si ce tamis n'a rien retenu. Dans l'autre ordre, une
        # page scannée portant le nom en clair dans son maigre texte aurait
        # été classée « à vérifier à la main » au lieu de BLOQUANTE.
        if reserve and not vu:
            alertes.append({"gravite": "AVERTISSEMENT", "fichier": f,
                            "motif": reserve})

    return {"fichiers_publies": len(fichiers), "empreintes_cherchees":
            len(liste), "alertes": alertes, "racine": racine}


def main() -> int:
    r = verifier()
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 1 if r["alertes"] else 0

    print(f"Fichiers qui seraient publiés : {r['fichiers_publies']}")
    print(f"Empreintes du dossier réel recherchées : "
          f"{r['empreintes_cherchees']}")
    bloquants = [a for a in r["alertes"] if a["gravite"] == "BLOQUANT"]
    autres = [a for a in r["alertes"] if a["gravite"] != "BLOQUANT"]
    if bloquants:
        print(f"\n✗ {len(bloquants)} PROBLÈME(S) — NE PAS PUBLIER :")
        for a in bloquants:
            print(f"    {a['fichier']} — {a['motif']}")
        for a in autres:
            print(f"    [{a['gravite']}] {a['fichier']} — {a['motif']}")
        print("\n  Corrigez le .gitignore, retirez le fichier de l'index "
              "(git rm --cached), rétablissez le dossier privé si c'est lui "
              "qui manque, et relancez ce contrôle.")
        return 1
    for a in autres:
        print(f"    [{a['gravite']}] {a['fichier']} — {a['motif']}")
    print(f"\n✓ {r['fichiers_publies']} fichier(s) examiné(s) avec "
          f"{r['empreintes_cherchees']} empreinte(s) : aucune donnée "
          "personnelle dans ce qui serait publié.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
