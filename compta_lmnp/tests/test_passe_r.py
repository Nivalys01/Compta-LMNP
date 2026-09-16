# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Non-régression des constats de la passe R (licence, provenance, promesses).

Cette passe n'audite pas un calcul : elle audite ce que le dépôt AFFIRME. Le
fil rouge est donc différent des autres — **une promesse écrite doit être
vérifiable, et une garde ne doit jamais prouver moins que ce qu'elle a l'air
de prouver.**

Les deux tests de propriété intellectuelle qui existaient avant cette passe
illustrent exactement ce défaut : l'un cherchait une liste de motifs
interdits écrite à la main, et n'a pas vu les 25 fichiers qui gardaient la
dernière ligne de l'ancien en-tête propriétaire ; l'autre cherchait la
présence de la chaîne `github.com` dans `app.py` et présentait cela comme la
vérification de l'offre de source. Les deux passaient au vert pendant que
l'audit relevait les défauts.

D'où la règle appliquée ici : **vérifier la forme de ce qui doit être, plutôt
qu'énumérer ce qui ne doit pas être** — et, là où la vérification est hors de
portée d'un test (l'accessibilité réseau d'une URL), le DIRE au lieu de faire
semblant.

Aucune donnée réelle : aucun scénario comptable, uniquement des documents.

Lancer :  pytest -q tests/test_passe_r.py
"""
import glob
import hashlib
import os
import posixpath
import re
import sys
import zipfile

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RACINE = os.path.dirname(HERE)


def _lire(chemin):
    with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
        return f.read()


def _sources_python():
    """Tous les .py du logiciel, par LECTURE DU RÉPERTOIRE."""
    for f in glob.glob(os.path.join(HERE, "**/*.py"), recursive=True):
        if ".venv" in f or os.sep + "dist" + os.sep in f:
            continue
        yield f


# ═══ R-01 — l'offre de source doit être une URL, et l'être dit ═════════

ENTETE_ATTENDUE = (
    "# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.",
    "# SPDX-License-Identifier: AGPL-3.0-or-later",
)


def test_r01_le_pied_de_page_offre_une_url_de_source_bien_formee():
    """L'article 13 promet la source à qui utilise le logiciel par le réseau.
    L'ancien test se contentait de chercher « github.com » n'importe où dans
    `app.py` — une occurrence en commentaire l'aurait satisfait.

    **Ce test ne prouve toujours PAS que l'URL répond.** Un test hors ligne
    ne le peut pas, et le prétendre serait le défaut même que la passe R
    relève. Il vérifie la forme ; l'accessibilité anonyme est un geste de la
    liste de contrôle avant publication (voir `test_r01_…_liste_de_controle`).
    """
    src = _lire("compta_lmnp/app.py")
    liens = re.findall(r'href="([^"]+)"[^>]*>\s*code source\s*</a>', src)
    assert liens, "aucun lien « code source » dans le pied de page"
    for url in liens:
        assert url.startswith("https://"), url
        assert len(url.split("://", 1)[1].strip("/").split("/")) >= 2, (
            f"{url} ne désigne pas un dépôt précis")
    assert "AGPL" in src, "le pied de page doit nommer la licence"


def test_r01_la_liste_de_controle_avant_publication_est_ecrite():
    """Ce qu'un test ne peut pas vérifier doit être confié à un humain, par
    écrit. Sans cette liste, le 404 anonyme du lien resterait une découverte
    d'utilisateur."""
    readme = _lire("README.md")
    assert "Liste de contrôle avant ouverture du dépôt" in readme
    for geste in ("public", "tag", "anonymement"):
        assert geste in readme, geste
    # et la limite actuelle est dite, pas tue
    assert "404" in readme


# ═══ R-02 — pas de négation absolue sur les licences tierces ═══════════

def test_r02_aucune_affirmation_absolue_d_absence_de_reciprocite():
    """« Aucun composant sous licence à réciprocité n'est utilisé » était une
    négation universelle — invérifiable par construction, et fausse : le
    dépôt exécute Poppler, qui est sous GPL. Une assurance qu'on ne peut pas
    établir ne doit pas être écrite."""
    notices = _lire("NOTICES-TIERS.md")
    for negation in ("Aucun composant sous licence à réciprocité",
                     "aucun composant sous licence à réciprocité",
                     "aucune dépendance à licence contaminante"):
        assert negation not in notices, negation


def test_r02_poppler_est_nomme_avec_son_regime():
    """Ce qui est exécuté doit être inventorié comme tel, et la distinction
    qui commande les obligations doit être lisible."""
    notices = _lire("NOTICES-TIERS.md")
    assert "Poppler" in notices
    assert "GPL" in notices
    for regime in ("Redistribué", "Installé", "Exécuté"):
        assert regime in notices, regime
    assert "sous-processus" in notices


# ═══ R-03 — l'inventaire se déduit des métadonnées, pas de mémoire ═════

def test_r03_les_dependances_declarees_figurent_toutes_dans_les_notices():
    """L'inventaire est reconstruit depuis les MÉTADONNÉES des paquets
    installés, puis comparé au document. Une liste écrite à la main ne peut
    pas signaler ce qu'on a oublié d'y inscrire : Pillow et
    charset-normalizer, transitives sans condition de reportlab, manquaient."""
    import importlib.metadata as meta
    notices = _lire("NOTICES-TIERS.md").lower()
    manquantes = []
    for paquet in ("flask", "reportlab"):
        try:
            exigences = meta.distribution(paquet).requires or []
        except meta.PackageNotFoundError:
            pytest.skip(f"{paquet} absent de l'environnement")
        for exigence in exigences:
            # « pillow>=9.0.0 » ; on ignore les extras facultatifs
            if "extra ==" in exigence:
                continue
            nom = re.split(r"[<>=!;\s\[]", exigence.strip(), maxsplit=1)[0]
            if not nom:
                continue
            # Une exigence peut porter un marqueur d'environnement —
            # « importlib-metadata ; python_version < "3.10" » — qui ne
            # s'applique pas ici. Faute de `packaging` dans cet
            # environnement, le critère retenu est factuel plutôt que
            # théorique : ce qui est RÉELLEMENT installé est ce qui a
            # atterri sur la machine, donc ce que la notice doit couvrir.
            try:
                meta.distribution(nom)
            except meta.PackageNotFoundError:
                continue
            if nom.lower() not in notices:
                manquantes.append(f"{nom} (exigée par {paquet})")
    assert not manquantes, f"absentes de NOTICES-TIERS.md : {manquantes}"


def test_r03_la_dependance_conditionnelle_du_https_est_declaree():
    """`cryptography` n'est installé que si l'utilisateur demande HTTPS sans
    certificat : absent de l'environnement, donc invisible à `pip freeze`,
    et pourtant bel et bien installé chez lui."""
    notices = _lire("NOTICES-TIERS.md")
    assert "cryptography" in notices
    assert "generer_certificat.py" in _lire("NOTICES-TIERS.md")


# ═══ R-04 — aucun renvoi du paquet ne doit pendre ══════════════════════

def test_r04_aucun_lien_local_mort_dans_le_paquet():
    """Cinq liens du document d'accueil pendaient dans le zip, dont deux vers
    la licence et un vers la procédure de contribution : les documents de la
    racine sont un cran au-dessus du logiciel dans le dépôt, et à côté de lui
    dans le paquet.

    Le contrôle porte sur le CONTENU RÉEL de l'archive et sur la totalité de
    ses liens — pas sur la table de réécriture, qui est elle-même une liste
    écrite à la main."""
    conftest.exiger_dossier_prive()
    sys.path.insert(0, HERE)
    import construire_distribution as cd
    ancien = os.getcwd()
    os.chdir(HERE)
    try:
        chemin = cd.construire()
    finally:
        os.chdir(ancien)

    with zipfile.ZipFile(chemin) as z:
        presents = set(z.namelist())
        morts = []
        for entree in z.namelist():
            if not entree.endswith(".md"):
                continue
            texte = z.read(entree).decode("utf-8", "replace")
            for _libelle, vise in cd.LIEN_MD.findall(texte):
                if "://" in vise or vise.startswith(("#", "mailto:")):
                    continue
                resolu = posixpath.normpath(posixpath.join(
                    posixpath.dirname(entree), vise.split("#")[0]))
                if resolu not in presents:
                    morts.append(f"{entree} → {vise}")
    assert not morts, f"liens morts : {sorted(set(morts))}"


def test_r04_le_paquet_livre_la_licence_et_les_conditions():
    conftest.exiger_dossier_prive()
    sys.path.insert(0, HERE)
    import construire_distribution as cd
    ancien = os.getcwd()
    os.chdir(HERE)
    try:
        chemin = cd.construire()
    finally:
        os.chdir(ancien)
    noms = {n.split("compta_lmnp/", 1)[-1]
            for n in zipfile.ZipFile(chemin).namelist()}
    for attendu in ("LICENSE.txt", "NOTICES-TIERS.md", "CONTRIBUTING.md",
                    "README.md"):
        assert attendu in noms, f"{attendu} absent du paquet"


# ═══ R-05 — la FORME de l'en-tête, pas une liste de motifs ═════════════

def test_r05_chaque_source_porte_exactement_len_tete_attendue():
    """LE constat qui condamne la méthode précédente. L'ancien en-tête tenait
    sur TROIS lignes ; la migration en a supprimé deux, et la troisième —
    « sans autorisation écrite de l'auteur. » — est restée dans 25 fichiers,
    juste sous l'identifiant SPDX qui autorise la modification.

    La garde d'alors cherchait une liste de motifs interdits, où ce fragment
    ne figurait pas : elle passait au vert. Ce test vérifie donc la forme de
    ce qui DOIT être — le bloc de commentaires de tête vaut exactement les
    deux lignes attendues — et signale tout le reste, quel qu'en soit le
    texte. C'est « le total moins ce qui est identifié » de l'invariant n°5.
    """
    fautifs = []
    for chemin in _sources_python():
        with open(chemin, encoding="utf-8") as f:
            lignes = f.read().splitlines()
        tete = []
        for ligne in lignes:
            if ligne.startswith("#"):
                tete.append(ligne)
            else:
                break
        if tuple(tete) != ENTETE_ATTENDUE:
            fautifs.append((os.path.relpath(chemin, RACINE), tete))
    assert not fautifs, f"en-tête inattendu : {fautifs}"


# ═══ R-06 — le périmètre de la licence est dit, pas déduit ═════════════

def test_r06_le_perimetre_de_la_licence_couvre_chaque_categorie():
    """Une licence de code ne couvre pas d'elle-même la documentation ni les
    données, et le dépôt contient les trois. Le lecteur doit trouver la
    réponse écrite, pas avoir à la supposer."""
    readme = _lire("README.md")
    assert "Ce que la licence couvre" in readme
    for categorie in ("Documentation", "seed_referentiel.sql",
                      "Composants tiers", "Plan comptable général"):
        assert categorie in readme, categorie
    # ce qui appartient à l'utilisateur doit être dit explicitement
    assert "Vos** données comptables" in readme or "à vous" in readme


# ═══ R-07 — la licence est le texte canonique, à l'octet près ══════════

# SHA-256 de https://www.gnu.org/licenses/agpl-3.0.txt (édition 2026-09-16).
# Une comparaison de titres de sections ne distingue pas une copie fidèle
# d'une copie retouchée : seule l'empreinte de l'artefact complet le fait.
AGPL_CANONIQUE_SHA256 = (
    "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0")


def test_r07_la_licence_est_le_canonique_fsf_a_l_octet_pres():
    with open(os.path.join(RACINE, "LICENSE"), "rb") as f:
        octets = f.read()
    empreinte = hashlib.sha256(octets).hexdigest()
    assert empreinte == AGPL_CANONIQUE_SHA256, (
        "LICENSE diffère du texte canonique de la FSF. Trois URL en http:// "
        "au lieu de https:// suffisaient à produire cet écart — bénin, mais "
        "une licence se compare à l'octet, pas à l'esprit.")


def test_r07_la_copie_livree_est_identique_a_la_racine():
    conftest.exiger_dossier_prive()
    sys.path.insert(0, HERE)
    import construire_distribution as cd
    ancien = os.getcwd()
    os.chdir(HERE)
    try:
        chemin = cd.construire()
    finally:
        os.chdir(ancien)
    with open(os.path.join(RACINE, "LICENSE"), "rb") as f:
        racine = f.read()
    with zipfile.ZipFile(chemin) as z:
        livree = z.read("compta_lmnp/LICENSE.txt")
    assert livree == racine
