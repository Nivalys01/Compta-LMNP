# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Une installation mélangée doit se dénoncer elle-même.

Cause du défaut de terrain v8.53.0 : l'onglet Liasse tombait entièrement,
et ni le gabarit ni le module de calcul n'étaient fautifs. Le gabarit
demandait un champ que le module installé À CÔTÉ ne produisait pas encore —
un paquet décompressé par-dessus un autre sans tout remplacer. Rien ne le
signalait : le logiciel démarrait, servait ses pages, et cassait à l'écran
le plus éloigné de sa cause.

Trois situations, trois réponses, et elles ne sont pas interchangeables :

- **fichier manquant** → refus, parce qu'il n'y a aucune ambiguïté ;
- **fichier différent** → avertissement visible, jamais refus : l'AGPL
  donne le droit de modifier ce code, et bloquer transformerait une
  liberté accordée par la licence en panne ;
- **manifeste absent** → dit dans l'arborescence d'un utilisateur, ignoré
  dans celle de développement, où il n'a jamais existé.

Le point le plus important est le MOMENT. Un module manquant fait échouer
l'import d'app.py : une garde branchée sur la requête n'a jamais la parole,
et le lanceur n'affiche qu'un `ModuleNotFoundError` nu.

Aucune donnée réelle : arborescences factices en répertoire temporaire.

Lancer :  pytest -q tests/test_integrite_installation.py
"""
import json
import os
import subprocess
import sys

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import integrite


def _installation(tmp_path, fichiers=None, version="9.9.9"):
    """Une arborescence livrée factice, avec son manifeste."""
    fichiers = fichiers or {"app.py": b"# faux point d'entree\n",
                            "modules/liasse.py": b"# faux module\n",
                            "schema.sql": b"-- faux schema\n"}
    racine = tmp_path / "installation"
    for relatif, contenu in fichiers.items():
        cible = racine / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(contenu)
    (racine / integrite.MANIFESTE).write_text(
        integrite.construire_manifeste(version, fichiers), encoding="utf-8")
    return str(racine)


def test_une_installation_complete_ne_dit_rien(tmp_path):
    r = integrite.verifier(_installation(tmp_path))
    assert r["statut"] == integrite.OK
    assert integrite.message(r) == ""


def test_un_fichier_manquant_rend_linstallation_incomplete(tmp_path):
    racine = _installation(tmp_path)
    os.remove(os.path.join(racine, "modules", "liasse.py"))
    r = integrite.verifier(racine)
    assert r["statut"] == integrite.INCOMPLETE
    assert r["manquants"] == ["modules/liasse.py"]
    msg = integrite.message(r)
    assert "modules/liasse.py" in msg          # le fichier est NOMMÉ
    assert "dossier VIDE" in msg               # et l'action est dite


def test_un_fichier_modifie_avertit_sans_bloquer(tmp_path):
    """La licence donne le droit de modifier ce code : un fork ne doit pas
    se retrouver en panne parce qu'il a modifié un module."""
    racine = _installation(tmp_path)
    with open(os.path.join(racine, "modules", "liasse.py"), "ab") as f:
        f.write(b"# modification volontaire\n")
    r = integrite.verifier(racine)
    assert r["statut"] == integrite.MODIFIEE
    assert r["manquants"] == []
    assert r["differents"] == ["modules/liasse.py"]
    assert "modules/liasse.py" in integrite.message(r)


def test_manquant_et_modifie_a_la_fois_donne_la_priorite_au_manquant(tmp_path):
    """Un fichier absent est plus grave qu'un fichier différent : c'est le
    refus qui doit l'emporter, pas l'avertissement."""
    racine = _installation(tmp_path)
    os.remove(os.path.join(racine, "schema.sql"))
    with open(os.path.join(racine, "modules", "liasse.py"), "ab") as f:
        f.write(b"# modif\n")
    r = integrite.verifier(racine)
    assert r["statut"] == integrite.INCOMPLETE


def test_manifeste_absent_chez_lutilisateur_est_signale(tmp_path):
    racine = _installation(tmp_path)
    os.remove(os.path.join(racine, integrite.MANIFESTE))
    r = integrite.verifier(racine)
    assert r["statut"] == integrite.ABSENT
    assert "INTROUVABLE" in integrite.message(r)


def test_manifeste_absent_en_developpement_ne_dit_rien(tmp_path):
    """Dans l'arborescence de développement il n'y a pas de manifeste : il
    est produit à la construction du paquet. Son absence y est normale, et
    `tests/` permet de reconnaître ce cas sans se tromper."""
    racine = _installation(tmp_path)
    os.remove(os.path.join(racine, integrite.MANIFESTE))
    os.makedirs(os.path.join(racine, "tests"))
    r = integrite.verifier(racine)
    assert r["statut"] == integrite.NON_APPLICABLE
    assert integrite.message(r) == ""


def test_un_manifeste_illisible_ne_vaut_pas_un_manifeste_absent(tmp_path):
    """Il était là, et on ne sait plus ce qu'il disait : c'est un défaut,
    pas une absence de contrainte. Conclure au vert ici serait approuver
    faute de pouvoir vérifier."""
    racine = _installation(tmp_path)
    with open(os.path.join(racine, integrite.MANIFESTE), "w",
              encoding="utf-8") as f:
        f.write("{ ceci n'est pas du JSON")
    assert integrite.verifier(racine)["statut"] == integrite.ABSENT


def test_le_manifeste_ne_se_couvre_pas_lui_meme(tmp_path):
    """Sinon il faudrait le hacher après l'avoir écrit, ce qui est
    impossible, et la vérification échouerait toujours."""
    racine = _installation(tmp_path)
    with open(os.path.join(racine, integrite.MANIFESTE), encoding="utf-8") as f:
        manifeste = json.load(f)
    assert integrite.MANIFESTE not in manifeste["fichiers"]
    assert manifeste["version"] == "9.9.9"


# ── Le MOMENT : avant les imports métier ──────────────────────────────────

def test_une_installation_incomplete_arrete_avant_les_imports(tmp_path):
    """LE point du correctif. Un module manquant fait échouer l'import
    d'app.py ; une garde branchée sur la requête n'a jamais la parole, et
    le lanceur n'affiche qu'un `ModuleNotFoundError` nu, qui nomme le
    module sans dire ni pourquoi ni quoi faire.

    On vérifie donc dans un PROCESSUS séparé, seule façon d'observer ce qui
    se passe à l'import et le code de sortie."""
    racine = _installation(tmp_path)
    os.remove(os.path.join(racine, "modules", "liasse.py"))
    programme = (
        "import sys; sys.path.insert(0, %r)\n"
        "import integrite\n"
        "integrite.RACINE = %r\n"
        "integrite.exiger_installation_complete()\n"
        "print('JAMAIS ATTEINT')\n" % (os.path.join(HERE, "modules"), racine))
    r = subprocess.run([sys.executable, "-c", programme],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1, r.stdout
    assert "JAMAIS ATTEINT" not in r.stdout
    assert "INSTALLATION INCOMPLÈTE" in r.stderr
    assert "modules/liasse.py" in r.stderr


def test_une_installation_saine_nempeche_pas_de_demarrer(tmp_path):
    """Contre-épreuve : une garde qui arrête tout le monde n'est pas une
    garde."""
    racine = _installation(tmp_path)
    programme = (
        "import sys; sys.path.insert(0, %r)\n"
        "import integrite\n"
        "integrite.RACINE = %r\n"
        "integrite.exiger_installation_complete()\n"
        "print('DEMARRAGE OK')\n" % (os.path.join(HERE, "modules"), racine))
    r = subprocess.run([sys.executable, "-c", programme],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "DEMARRAGE OK" in r.stdout


# ── Le paquet livré porte bien son manifeste ──────────────────────────────

def test_le_paquet_construit_porte_un_manifeste_exact():
    """Le manifeste est calculé sur les octets RÉELLEMENT livrés : les
    documents Markdown voient leurs liens réécrits à la construction, et un
    manifeste calculé sur la source annoncerait une différence dès le
    premier démarrage chez l'utilisateur."""
    conftest.exiger_dossier_prive()
    import zipfile
    sys.path.insert(0, HERE)
    import construire_distribution as cd
    ancien = os.getcwd()
    os.chdir(HERE)
    try:
        chemin = cd.construire()
    finally:
        os.chdir(ancien)

    with zipfile.ZipFile(chemin) as z:
        noms = {n.split("compta_lmnp/", 1)[-1] for n in z.namelist()}
        assert integrite.MANIFESTE in noms
        manifeste = json.loads(
            z.read(f"compta_lmnp/{integrite.MANIFESTE}").decode("utf-8"))
        # tout ce qui est livré est couvert, le manifeste excepté
        assert set(manifeste["fichiers"]) == noms - {integrite.MANIFESTE}
        # et chaque empreinte correspond aux octets livrés
        for relatif, attendue in manifeste["fichiers"].items():
            reel = integrite.empreinte(z.read(f"compta_lmnp/{relatif}"))
            assert reel == attendue, relatif


def test_le_depot_lui_meme_na_pas_de_manifeste():
    """Il est produit à la construction. En trouver un ici signifierait
    qu'un paquet a été décompressé dans l'arborescence de travail."""
    assert not os.path.exists(os.path.join(HERE, integrite.MANIFESTE))
    assert integrite.verifier(HERE)["statut"] == integrite.NON_APPLICABLE
