# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Construit le paquet de DISTRIBUTION (à remettre à un tiers) :

    python construire_distribution.py   →  dist/compta_lmnp_client_vX.Y.Z.zip

Contenu : le code de production, les lanceurs et la documentation.
JAMAIS : les tests, le dossier reference/ (FEC réels = données personnelles,
SIREN et adresse de l'exploitant), ni aucune base .db, sauvegarde, archive
ou registre de dossiers. Une GARDE vérifie le zip après construction et
échoue s'il contient le moindre fichier interdit — la fuite de données
personnelles est bloquante, pas simplement évitée.
"""
from __future__ import annotations

import os
import posixpath
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Points d'entrée et outils : à la RACINE du paquet, comme les lanceurs et
# les documents. Les lanceurs appellent app.py par son nom.
ENTREES = ["app.py", "cli.py", "verifier_depot.py"]

# Modules métier : regroupés dans modules/ pour que LISEZ-MOI.md et les
# lanceurs ne soient plus noyés sous trente-cinq fichiers Python. Le paquet
# reproduit l'arborescence — sinon l'amorçage du chemin d'import, qui pointe
# sur modules/, ne trouverait rien chez le client.
# TOUT modules/ est embarqué, par LECTURE DU RÉPERTOIRE et non par liste
# écrite à la main. La liste énumérée a laissé échapper `plan_immo.py` le jour
# de sa création : le paquet se construisait sans erreur, et l'application
# échouait à l'import CHEZ LE CLIENT — pas ici. La garde « PAQUET INCOMPLET »
# ne couvrait pas ce cas, elle ne vérifie que les fichiers cités par les
# LANCEURS. Même défaut de principe que la garde anti-fuite d'avant la passe F :
# une liste rédigée à la main ne peut pas signaler ce qu'on a oublié d'y mettre.
MODULES_PROD = sorted(f for f in os.listdir(os.path.join(HERE, "modules"))
                      if f.endswith(".py"))
# Un SEUL document d'accueil : README.md et LISEZ-MOI.md disaient chacun
# une moitié de la même chose et se renvoyaient l'un à l'autre.
# Données et documents : racine du paquet.
DONNEES = ["schema.sql", "seed_referentiel.sql", "seed_demo.sql",
           "demo/FEC_DEMO_2025.txt",
           # Manifeste des dépendances d'exécution : les lanceurs
           # l'installent (`pip install -r requirements.txt`). Sans lui dans
           # le paquet, le premier démarrage chez l'utilisateur échoue
           # (constat T-06).
           "requirements.txt"]
# Documents : (nom dans le paquet, chemin sur le disque relatif à HERE).
#
# La licence et les notices tierces vivent à la RACINE du dépôt, pas ici —
# c'est là que GitHub les cherche pour afficher la licence du projet, et c'est
# là qu'un lecteur les attend. Le paquet en reçoit une copie parce que l'AGPL
# l'exige (article 4 : « give all recipients a copy of this License along with
# the Program ») : le zip est une distribution à part entière. Une SEULE
# source, copiée — et non deux fichiers à maintenir en phase, qui divergent
# toujours.
DOCS = [("LICENSE.txt", os.path.join("..", "LICENSE")),
        ("NOTICES-TIERS.md", os.path.join("..", "NOTICES-TIERS.md")),
        ("CONTRIBUTING.md", os.path.join("..", "CONTRIBUTING.md")),
        ("README.md", os.path.join("..", "README.md")),
        ("CHANGELOG.md", "CHANGELOG.md"),
        ("ARCHITECTURE.md", "ARCHITECTURE.md"),
        ("LISEZ-MOI.md", "LISEZ-MOI.md"),
        ("VERSION", "VERSION")]

# Les documents de la racine sont d'un cran au-dessus du logiciel DANS LE
# DÉPÔT, et à côté de lui DANS LE PAQUET. Les liens relatifs écrits pour l'un
# sont donc faux dans l'autre : `../LICENSE` ne menait nulle part une fois le
# zip décompressé, et c'est justement vers la licence et la procédure de
# contribution que ces liens pointaient (constat R-04).
#
# Ils sont réécrits à la construction. La table dit ce que devient chaque
# cible ; la garde plus bas vérifie qu'AUCUN lien local du paquet ne pend,
# celui-ci compris — parce qu'une table de réécriture est encore une liste
# écrite à la main, et qu'elle ne peut pas signaler le lien qu'on n'y a pas
# inscrit.
#
# Deux cas, et il faut les distinguer : ce que le paquet CONTIENT sous un
# autre nom se réécrit en local ; ce qu'il ne contient pas — les rapports
# d'audit, le hook — devient un lien vers le dépôt, parce qu'un renvoi
# honnête vaut mieux qu'un chemin qui pend.
DEPOT = "https://github.com/Nivalys01/Compta-LMNP/"
REECRITURES = {
    # présents dans le paquet, sous un autre chemin
    "../LICENSE": "LICENSE.txt",
    "LICENSE": "LICENSE.txt",
    "../NOTICES-TIERS.md": "NOTICES-TIERS.md",
    "../CONTRIBUTING.md": "CONTRIBUTING.md",
    "../README.md": "README.md",
    "compta_lmnp/CHANGELOG.md": "CHANGELOG.md",
    "compta_lmnp/LISEZ-MOI.md": "LISEZ-MOI.md",
    # absents du paquet : renvoyés vers le dépôt
    ".githooks/pre-push": DEPOT + "blob/main/.githooks/pre-push",
    "docs/": DEPOT + "tree/main/docs/",
    "docs/audit/": DEPOT + "tree/main/docs/audit/",
}

# Un lien Markdown : [texte](cible). On ne retient que les cibles locales —
# ni http(s), ni ancre pure.
LIEN_MD = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
# Un SEUL fichier .sh est livré. Le générateur de certificat existait en
# double (.sh et .py) et s'affichait juste à côté du lanceur : sur un
# bureau Linux, l'utilisateur ouvrait l'un pour l'autre (constaté en
# usage). Le générateur Python fait le même travail, sur toutes les
# plateformes, et ne ressemble pas à un lanceur.
LANCEURS = ["Compta-LMNP-Linux-macOS.sh", "Compta-LMNP-Windows.bat",
            "Compta-LMNP.desktop",
            "generer_certificat.py", "ouvrir_navigateur.py"]

# Fichiers locaux référencés par les lanceurs : le paquet DOIT les contenir,
# sinon l'installation neuve échoue chez le client (défaut trouvé en v8.0.0 :
# les générateurs de certificat manquaient, HTTPS tombait en panne).
REFERENCES_LANCEURS = re.compile(
    r"\b([A-Za-z0-9_\-]+\.(?:py|sh|sql))\b")

# Motifs interdits dans le paquet (données personnelles ou de travail).
INTERDITS = [
    re.compile(r"\.db$"), re.compile(r"^reference/"),
    # Le dossier de référence porte une identité RÉELLE. Il était livré
    # (constat v8.13.0) alors que le fichier lui-même portait la mention
    # « NE JAMAIS LIVRER » : c'est désormais impossible.
    re.compile(r"^seed_exemple\.sql$"),
    re.compile(r"^\d{9}FEC\d{8}\.txt$"), re.compile(r"^tests/"),
    re.compile(r"^dossiers(/|\.json$)"), re.compile(r"^sauvegardes/"),
    re.compile(r"^archives/"), re.compile(r"__pycache__"),
]


def construire() -> str:
    version = open(os.path.join(HERE, "VERSION"), encoding="utf-8").read().strip()
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    cible = os.path.join(HERE, "dist", f"compta_lmnp_client_v{version}.zip")

    # (chemin dans le paquet, chemin sur le disque)
    fichiers = ([(f"modules/{f}", f"modules/{f}") for f in MODULES_PROD]
                + [(f, f) for f in ENTREES + DONNEES + LANCEURS]
                + DOCS)
    manquants = [d for _, d in fichiers
                 if not os.path.exists(os.path.join(HERE, d))]
    if manquants:
        raise SystemExit(f"Fichiers manquants : {manquants}")

    # ── Garde Windows : un .bat DOIT etre en ASCII pur et en CRLF ────────
    #    cmd.exe lit un fichier de commandes octet par octet ; un caractere
    #    accentue (UTF-8, donc multi-octets) ou une fin de ligne Unix
    #    decale sa lecture et il avale le debut des lignes suivantes —
    #    « echo » devient « ho » puis « o », les variables ne sont jamais
    #    affectees, et le lanceur echoue de facon incomprehensible.
    #    Constate en conditions reelles sur Windows 10 (juillet 2026).
    for lanceur in LANCEURS:
        if not lanceur.lower().endswith(".bat"):
            continue
        octets = open(os.path.join(HERE, lanceur), "rb").read()
        non_ascii = [i for i, b in enumerate(octets) if b > 127]
        lf_seuls = octets.count(b"\n") - octets.count(b"\r\n")
        if non_ascii or lf_seuls:
            raise SystemExit(
                f"LANCEUR WINDOWS ILLISIBLE — {lanceur} : "
                f"{len(non_ascii)} octet(s) non-ASCII, {lf_seuls} fin(s) de "
                "ligne Unix. cmd.exe ne peut pas interpreter ce fichier : "
                "reecrivez-le en ASCII pur avec des fins de ligne CRLF.")

    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED) as z:
        for dans_paquet, sur_disque in fichiers:
            chemin = os.path.join(HERE, sur_disque)
            if dans_paquet.endswith(".md"):
                texte = open(chemin, encoding="utf-8").read()
                for avant, apres in REECRITURES.items():
                    texte = texte.replace(f"]({avant})", f"]({apres})")
                z.writestr(f"compta_lmnp/{dans_paquet}", texte)
            else:
                z.write(chemin, arcname=f"compta_lmnp/{dans_paquet}")

    # ── Garde anti-fuite n°1 : aucun NOM interdit ───────────────────────
    with zipfile.ZipFile(cible) as z:
        noms = [n.split("compta_lmnp/", 1)[-1] for n in z.namelist()]
    fuites = [n for n in noms for motif in INTERDITS if motif.search(n)]
    if fuites:
        os.remove(cible)
        raise SystemExit(f"FUITE BLOQUÉE — fichiers interdits : {fuites}")

    # ── Garde anti-lien mort : tout renvoi local doit aboutir ───────────
    #
    #    Cinq liens du document d'accueil pendaient dans le paquet, dont
    #    deux vers la licence et un vers la procédure de contribution
    #    (constat R-04). Aucune garde ne les voyait : le paquet se
    #    construisait, et c'est le lecteur du zip qui découvrait le trou.
    #
    #    Le contrôle porte sur le CONTENU RÉEL de l'archive et sur la
    #    totalité de ses liens — pas sur la table de réécriture, qui est
    #    une liste écrite à la main et ne peut donc pas signaler le lien
    #    qu'on a oublié d'y inscrire.
    with zipfile.ZipFile(cible) as z:
        presents = set(z.namelist())
        morts = []
        for entree in z.namelist():
            if not entree.endswith(".md"):
                continue
            texte = z.read(entree).decode("utf-8", "replace")
            for _libelle, vise in LIEN_MD.findall(texte):
                if "://" in vise or vise.startswith(("#", "mailto:")):
                    continue
                resolu = posixpath.normpath(posixpath.join(
                    posixpath.dirname(entree), vise.split("#")[0]))
                if resolu not in presents:
                    morts.append(f"{entree} → {vise}")
    if morts:
        os.remove(cible)
        raise SystemExit(
            "LIENS MORTS DANS LE PAQUET — un document livré renvoie vers "
            f"ce qu'il ne contient pas : {sorted(set(morts))}")

    # ── Garde anti-fuite n°2 : aucun CONTENU personnel ───────────────────
    #
    #    La garde ci-dessus compare des noms à une liste écrite à la main —
    #    or les fichiers du zip SONT cette liste. Elle vérifiait donc qu'une
    #    liste rédigée par l'auteur ne contenait pas ce qu'il n'y avait pas
    #    mis : structurellement incapable de rien détecter (constat F-03).
    #
    #    Le cas qu'elle laissait passer est précisément celui pour lequel
    #    elle existe : seed_demo.sql et le FEC de démonstration sont les
    #    seuls fichiers du paquet DÉRIVÉS des données réelles, leur nom est
    #    légitime, et personne ne relisait leur contenu (constat F-04).
    #
    #    Les empreintes viennent de verifier_depot, qui les lit dans le
    #    dossier privé : une seule définition de ce qui est sensible.
    #    HERE explicitement dans sys.path : ce script est aussi lancé par
    #    build_client.py via runpy, qui n'ajoute PAS le dossier du script
    #    aux chemins d'import. Sans cela la garde échouerait à l'import —
    #    donc bloquerait la construction, mais pour une mauvaise raison.
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import verifier_depot
    liste = verifier_depot.empreintes()
    if not liste:
        os.remove(cible)
        raise SystemExit(
            "CONSTRUCTION REFUSÉE — aucune empreinte n'a pu être chargée "
            "(dossier privé absent ?). Le contenu du paquet n'a donc pas pu "
            "être contrôlé : produire un paquet dans ces conditions "
            "reviendrait à affirmer sans avoir vérifié.")
    cherchees = [(quoi, verifier_depot.normaliser(v)) for quoi, v in liste]
    fuites_contenu = []
    with zipfile.ZipFile(cible) as z:
        for entree in z.namelist():
            brut = z.read(entree)
            texte = None
            for enc in ("utf-8", "cp1252"):
                try:
                    texte = brut.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if texte is None:
                continue
            norme = verifier_depot.normaliser(texte)
            for quoi, valeur in cherchees:
                if valeur and valeur in norme:
                    fuites_contenu.append(f"{entree} ({quoi})")
    if fuites_contenu:
        os.remove(cible)
        raise SystemExit("FUITE BLOQUÉE — donnée personnelle dans le "
                         f"contenu : {sorted(set(fuites_contenu))}")

    # ── Garde anti-oubli : tout fichier local invoqué par un lanceur doit
    #    être dans le paquet (sinon panne à l'installation chez le client).
    embarques = set(noms)
    manquants_lanceurs = set()
    for lanceur in LANCEURS:
        texte = open(os.path.join(HERE, lanceur), encoding="utf-8",
                     errors="ignore").read()
        for ref in REFERENCES_LANCEURS.findall(texte):
            embarque = (ref in embarques
                        or f"modules/{ref}" in embarques)
            if os.path.exists(os.path.join(HERE, ref)) and not embarque:
                manquants_lanceurs.add(ref)
    if manquants_lanceurs:
        os.remove(cible)
        raise SystemExit("PAQUET INCOMPLET — fichiers utilisés par les "
                         f"lanceurs mais absents : {sorted(manquants_lanceurs)}")

    taille = os.path.getsize(cible) // 1024
    print(f"✓ Paquet client : {cible} ({taille} Ko, {len(fichiers)} fichiers, "
          f"contenu contrôlé contre {len(liste)} empreinte(s) du dossier "
          "réel : aucune donnée personnelle)")
    return cible


if __name__ == "__main__":
    sys.exit(0 if construire() else 1)
