# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
La suite de tests ne touche plus au VRAI dist/.

Défaut constaté le 2026-09-25 : `construire_distribution.construire()`
écrivait dans dist/ sous le numéro de la version en cours. Chaque passage
de la suite remplaçait le paquet de cette version par le code de l'arbre de
travail, et le SUPPRIMAIT quand un test provoquait un refus de construction.
Les zips 8.56.0 et 8.57.0 de dist/ contenaient la version suivante.

Reproduit avant correctif : `pytest tests/test_j9_release.py` faisait
disparaître `dist/compta_lmnp_client_v8.58.0.zip`.

Lancer :  pytest -q tests/test_dist_jetable.py
"""
import os
import zipfile

import conftest
import pytest

import construire_distribution


def test_la_suite_construit_hors_du_vrai_dist():
    assert os.path.realpath(construire_distribution.DOSSIER_SORTIE) != \
        os.path.realpath(conftest._DIST_REEL)


def test_construire_ecrit_dans_le_dossier_jetable():
    conftest.exiger_dossier_prive()
    avant = conftest.etat_dist()
    chemin = construire_distribution.construire()
    assert os.path.dirname(chemin) == construire_distribution.DOSSIER_SORTIE
    assert zipfile.is_zipfile(chemin)
    assert conftest.etat_dist() == avant, "le vrai dist/ a été modifié"


def test_un_refus_de_construction_n_efface_rien_dans_le_vrai_dist(monkeypatch):
    """Le cas le plus grave : la garde efface « le zip fautif », homonyme du
    paquet réel de la version en cours."""
    conftest.exiger_dossier_prive()
    avant = conftest.etat_dist()
    # Refus APRÈS écriture du zip : un lanceur privé du fichier qu'il
    # appelle. La garde efface alors le zip — c'était le paquet réel.
    monkeypatch.setattr(
        construire_distribution, "LANCEURS",
        [f for f in construire_distribution.LANCEURS
         if f != "generer_certificat.py"])
    with pytest.raises(SystemExit, match="PAQUET INCOMPLET"):
        construire_distribution.construire()
    assert conftest.etat_dist() == avant, "le vrai dist/ a été modifié"


def test_dossier_de_sortie_explicite(tmp_path):
    conftest.exiger_dossier_prive()
    chemin = construire_distribution.construire(dossier_sortie=str(tmp_path))
    assert os.path.dirname(chemin) == str(tmp_path)


def test_la_garde_de_session_nomme_chaque_ecart():
    avant = {"a.zip": (1, 1), "b.zip": (2, 2), "c.zip": (3, 3)}
    apres = {"a.zip": (1, 1), "b.zip": (2, 9), "d.zip": (4, 4)}
    assert conftest.ecarts_dist(avant, apres) == [
        "supprimé : c.zip", "créé : d.zip", "modifié : b.zip"]
    assert conftest.ecarts_dist(avant, dict(avant)) == []


def test_les_paquets_publies_vivent_hors_de_toute_sortie_de_construction():
    """Un commit antérieur à 8.58.0 écrit encore dans dist/ ; les paquets
    publiés n'y sont plus. Aucune sortie de construction — réelle ou
    jetable — ne doit désigner leur dossier."""
    publies = os.path.realpath(conftest._PAQUETS_PUBLIES)
    assert publies != os.path.realpath(conftest._DIST_REEL)
    assert not os.path.realpath(
        construire_distribution.DOSSIER_SORTIE).startswith(publies)
    assert not os.path.realpath(os.path.join(
        construire_distribution.HERE, "dist")).startswith(publies)
