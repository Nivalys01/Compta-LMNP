# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Modules de routes (`modules/*_web.py`) et leur point d'enregistrement
unique (`routes.enregistrer_tous`).

Ce qui est figé ici :
  - chaque module `*_web.py` présent est réellement branché — par lecture
    du répertoire, sans liste à tenir ;
  - un module cassé, ou qui n'expose pas `enregistrer_routes`, fait échouer
    le démarrage en se nommant ;
  - `app.py` ne nomme aucun module de routes : une fonction nouvelle ne
    lui ajoute pas une ligne ;
  - TOUTES les routes POST, déplacées ou non, présentes ou à venir,
    refusent une requête d'origine étrangère ;
  - les routes extraites en 8.58.0 gardent leurs noms `url_for`.

Lancer :  pytest -q tests/test_routes_web.py
"""
import importlib
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import conftest
import init_db
import routes

FEC_DEMO = os.path.join(HERE, "demo", "FEC_DEMO_2025.txt")


@pytest.fixture()
def app_mod(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    init_db.init_demo(db, FEC_DEMO, 2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as module
    importlib.reload(module)
    monkeypatch.setattr(module, "HERE", str(tmp_path))
    yield module
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(module)


def _modules_des_routes(app):
    return {vue.__module__ for vue in app.view_functions.values()}


def test_chaque_module_web_est_branche(app_mod):
    presents = routes.modules_web()
    assert {"immobilisations_web", "exercices_web", "recurrentes_web",
            "depots_web"} <= set(presents)
    branches = _modules_des_routes(app_mod.app)
    for nom in presents:
        assert nom in branches, f"{nom}.py n'a enregistré aucune route"


def test_app_ne_nomme_aucun_module_de_routes():
    """Le point d'enregistrement est unique : ajouter une fonction ne doit
    pas ajouter de ligne au routeur."""
    src = open(conftest.source("app.py"), encoding="utf-8").read()
    assert not re.search(r"\b\w+_web\b", src), \
        "app.py nomme un module de routes : passez par routes.enregistrer_tous"
    assert "routes.enregistrer_tous(" in src


def _dossier_de_modules(tmp_path, monkeypatch, fichiers):
    d = tmp_path / "mods"
    d.mkdir()
    for nom, contenu in fichiers.items():
        (d / nom).write_text(contenu, encoding="utf-8")
    monkeypatch.syspath_prepend(str(d))
    return str(d)


class _AppFactice:
    def __init__(self):
        self.appels = []


def test_un_module_qui_ne_se_charge_pas_empeche_le_demarrage(tmp_path,
                                                             monkeypatch):
    d = _dossier_de_modules(tmp_path, monkeypatch, {
        "essai_casse_web.py": "raise ImportError('dépendance absente')\n"})
    with pytest.raises(RuntimeError, match="essai_casse_web.py.*ne se charge pas"):
        routes.enregistrer_tous(_AppFactice(), None, dossier=d)


def test_un_module_sans_enregistrer_routes_empeche_le_demarrage(tmp_path,
                                                               monkeypatch):
    d = _dossier_de_modules(tmp_path, monkeypatch, {
        "essai_muet_web.py": "X = 1\n"})
    with pytest.raises(RuntimeError, match="n'expose pas enregistrer_routes"):
        routes.enregistrer_tous(_AppFactice(), None, dossier=d)


def test_un_module_ajoute_est_branche_sans_toucher_au_routeur(tmp_path,
                                                             monkeypatch):
    d = _dossier_de_modules(tmp_path, monkeypatch, {
        "essai_nouveau_web.py": (
            "def enregistrer_routes(app, ctx):\n"
            "    app.appels.append(ctx)\n"),
        "pas_un_module.py": "raise RuntimeError('ne doit pas être importé')\n"})
    app, ctx = _AppFactice(), object()
    assert routes.enregistrer_tous(app, ctx, dossier=d) == ["essai_nouveau_web"]
    assert app.appels == [ctx]


def _url_exemple(regle) -> str:
    """URL concrète d'une règle : une valeur plausible par paramètre."""
    return re.sub(r"<(?:(\w+):)?(\w+)>",
                  lambda m: "1" if m.group(1) == "int" else "x", regle.rule)


def test_toutes_les_routes_post_refusent_une_origine_etrangere(app_mod):
    client = app_mod.app.test_client()
    regles = [r for r in app_mod.app.url_map.iter_rules()
              if "POST" in r.methods]
    assert len(regles) >= 35, "inventaire des routes POST anormalement court"
    for r in regles:
        rep = client.post(_url_exemple(r),
                          headers={"Origin": "https://exemple.invalid"})
        assert rep.status_code == 403, f"{r.rule} accepte une origine étrangère"


ROUTES_EXTRAITES = {
    "immobilisations_web": {
        "immobilisations", "creer_exploitant", "creer_bien",
        "creer_composant", "immo_ventiler", "composant_duree",
        "composant_supprimer", "immo_reprendre_amortissements", "bien_ceder"},
    "exercices_web": {
        "exercice_nouveau", "exercice_ouvrir", "exercice_analyser_fec",
        "exercice_reprendre_fec_multi", "exercice_reprendre_fec"},
}


def test_routes_extraites_gardent_leurs_noms(app_mod):
    """Les gabarits et les redirections les désignent par `url_for` : un
    renommage les casserait sans bruit."""
    for module, attendues in ROUTES_EXTRAITES.items():
        for nom in attendues:
            vue = app_mod.app.view_functions.get(nom)
            assert vue is not None, f"route « {nom} » disparue"
            assert vue.__module__ == module, (nom, vue.__module__)


def test_pages_extraites_servies(app_mod):
    client = app_mod.app.test_client()
    for page in ("/immobilisations?annee=2026", "/exercice/nouveau"):
        assert client.get(page).status_code == 200, page


def test_les_fonctions_du_routeur_sont_resolues_a_l_appel(app_mod,
                                                           monkeypatch):
    """Remplacer une fonction du routeur doit valoir pour les modules de
    routes : le contexte ne fige pas l'objet présent à l'enregistrement."""
    monkeypatch.setattr(app_mod, "_base", lambda *a, **k: "mise en page remplacée")
    rep = app_mod.app.test_client().get("/immobilisations?annee=2026")
    assert rep.get_data(as_text=True) == "mise en page remplacée"
