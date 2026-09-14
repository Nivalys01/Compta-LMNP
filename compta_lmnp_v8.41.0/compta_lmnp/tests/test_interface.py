# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Interface : défauts constatés à l'usage, figés en non-régression.

Ces quatre-là ne viennent pas d'une revue de code mais de l'usage — quelqu'un
a vu une infobulle coupée, un titre illisible, une navigation qui disparaît en
bas de page. Deux tiennent à une seule ligne de CSS, et le plus grave était
invisible à la lecture : un commentaire collé AU MILIEU d'un sélecteur, qui le
coupait en deux et annulait la règle entière.

Les contrôles portent sur la page RÉELLEMENT SERVIE, pas sur le fichier
source : c'est ce que le navigateur reçoit qui compte, et le CSS voyage dans
un gabarit interpolé.

Lancer :  pytest -q tests/test_interface.py
"""
import os
import sqlite3
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import conftest  # noqa: E402
import init_db  # noqa: E402


@pytest.fixture
def page(tmp_path, monkeypatch):
    """Une page réellement rendue, dossier CONFIGURÉ."""
    db = str(tmp_path / "compta.db")
    monkeypatch.setenv("COMPTA_DB", db)
    init_db.init(db, "blanc", annee_cible=2026).close()
    import app as webapp
    webapp.app.config["TESTING"] = True
    with webapp.app.test_request_context("/"):
        reel = webapp._db_path()
    if not os.path.exists(reel):
        init_db.init(reel, "blanc", annee_cible=2026).close()
    c = sqlite3.connect(reel)
    c.execute("INSERT OR IGNORE INTO exploitant (id, nom, siren) "
              "VALUES (1, 'MARTIN Jean', '000000000')")
    c.execute("INSERT OR IGNORE INTO bien (id, exploitant_id, libelle) "
              "VALUES (1, 1, 'Logement')")
    c.commit()
    c.close()
    cl = webapp.app.test_client()
    return cl.get("/saisie", follow_redirects=True).get_data(as_text=True)


# ═══ Titres illisibles sur fond coloré ══════════════════════════════════

def test_le_selecteur_du_bandeau_de_carte_nest_pas_coupe():
    """LE défaut, et il était invisible à la lecture rapide.

    Un commentaire avait été collé entre « .card- » et « header », coupant le
    sélecteur en deux : la règle ne s'appliquait jamais, et `.card-header` ne
    recevait pas son `color: #fff`. Seules les variantes de couleur
    s'appliquaient — elles posent un fond sans toucher au texte, qui héritait
    du noir du corps de page. D'où des titres noirs sur vert, ambre et rouge
    foncé. Un commentaire ne se place pas dans un sélecteur.
    """
    import re
    css = open(conftest.source("pages.py"), encoding="utf-8").read()
    assert not re.search(r"\.[A-Za-z-]+/\*", css), \
        "un commentaire coupe un sélecteur CSS"


def test_le_bandeau_de_carte_porte_sa_couleur_de_texte(page):
    regle = page.split(".card-header {")[1][:200]
    assert "color: #fff" in regle, "le texte du bandeau n'a pas de couleur"


@pytest.mark.parametrize("variante", ["green", "amber", "red"])
def test_les_variantes_ne_changent_que_le_fond(page, variante):
    """Si une variante redéclarait la couleur du texte, les quatre finiraient
    par diverger. Elle vient de la règle de base, et doit y rester."""
    regle = page.split(f".card-header.{variante}")[1].split("}")[0]
    assert "background" in regle
    assert "color" not in regle, f".{variante} redéclare la couleur du texte"


# ═══ Infobulles coupées ═════════════════════════════════════════════════

def test_la_carte_ne_rogne_plus_ses_infobulles(page):
    """`overflow: hidden` sur .card servait à faire respecter les coins
    arrondis par le bandeau coloré. Il rognait du même coup toute infobulle
    dépassant de la carte — soit la plupart. L'arrondi est reporté sur le
    bandeau lui-même."""
    regle = page.split(".card {")[1].split("}")[0]
    assert "overflow" not in regle, ".card rogne encore son contenu"
    bandeau = page.split(".card-header {")[1].split("}")[0]
    assert "border-radius" in bandeau, "l'arrondi du bandeau a été perdu"


def test_les_infobulles_sancrent_aux_bords(page):
    """Près d'un bord de fenêtre, une infobulle centrée sur sa pastille sort
    de l'écran. Les deux variantes d'ancrage sont servies, et le script les
    pose au survol."""
    assert ".aide.aide-gauche::after" in page
    assert ".aide.aide-droite::after" in page
    # La page porte plusieurs blocs <script> : on cherche l'appel lui-même
    # plutôt que de compter sur la position d'un bloc.
    assert 'classList.add("aide-droite")' in page, \
        "le script ne pose pas la classe d'ancrage"
    assert 'classList.add("aide-gauche")' in page


def test_sans_javascript_linfobulle_reste_lisible(page):
    """Amélioration progressive, jamais un prérequis : la position par défaut
    reste centrée, et l'infobulle se contente de dépasser."""
    defaut = page.split(".aide::after {")[1].split("}")[0]
    assert "left: 50%" in defaut
    assert "translateX(-50%)" in defaut


# ═══ Bandeau supérieur verrouillé ═══════════════════════════════════════

def test_le_bandeau_superieur_reste_visible(page):
    """Sur les pages longues — grand livre, liasse, contrôles — la navigation
    et le sélecteur d'exercice disparaissaient : changer d'onglet demandait de
    remonter."""
    regle = page.split("\nheader {")[1].split("}")[0]
    assert "position: sticky" in regle
    assert "top: 0" in regle


def test_le_bandeau_passe_sous_les_infobulles(page):
    """Ordre de superposition à ne pas inverser : une infobulle déclenchée
    dans la première ligne d'un tableau doit passer PAR-DESSUS le bandeau.
    Le bandeau est donc au-dessus du contenu mais sous les infobulles."""
    import re
    bandeau = page.split("\nheader {")[1].split("}")[0]
    z_bandeau = int(re.search(r"z-index:\s*(\d+)", bandeau).group(1))
    bulle = page.split(".aide::after {")[1].split("}")[0]
    z_bulle = int(re.search(r"z-index:\s*(\d+)", bulle).group(1))
    assert z_bandeau < z_bulle, (z_bandeau, z_bulle)


# ═══ Premier démarrage sur « Démarrer » ═════════════════════════════════

def test_premier_demarrage_ouvre_sur_demarrer(tmp_path, monkeypatch):
    """L'ordre des onglets plaçait déjà « ▶ Démarrer » en tête quand aucun
    exploitant n'est enregistré, mais la racine redirigeait quand même vers la
    saisie : le débutant arrivait sur un formulaire inutilisable — il n'y a ni
    exploitant, ni bien à qui rattacher une opération — au lieu de la page qui
    lui dit par où commencer."""
    db = str(tmp_path / "vierge.db")
    monkeypatch.setenv("COMPTA_DB", db)
    init_db.init(db, "blanc", annee_cible=2026).close()
    import app as webapp
    webapp.app.config["TESTING"] = True
    with webapp.app.test_request_context("/"):
        reel = webapp._db_path()
    if not os.path.exists(reel):
        init_db.init(reel, "blanc", annee_cible=2026).close()
    c = sqlite3.connect(reel)
    c.execute("DELETE FROM exploitant")
    c.commit()
    c.close()

    r = webapp.app.test_client().get("/")
    assert r.status_code == 302
    assert r.headers["Location"].rstrip("/").endswith("/dossiers"), \
        r.headers["Location"]


def test_un_dossier_configure_ouvre_sur_la_saisie(page, tmp_path, monkeypatch):
    """Contrepartie : l'utilisateur installé ne doit pas être renvoyé sur la
    page de configuration à chaque lancement."""
    import app as webapp
    r = webapp.app.test_client().get("/")
    assert r.status_code == 302
    assert "/saisie" in r.headers["Location"], r.headers["Location"]
    del page, tmp_path, monkeypatch
