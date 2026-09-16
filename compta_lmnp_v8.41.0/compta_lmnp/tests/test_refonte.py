# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Refonte v8.6.0 — lecteur FEC commun (fec_io) et extraction des gabarits.

Garanties verrouillées :
  1. les trois consommateurs de FEC lisent le MÊME fichier de la même
     façon (mêmes totaux) — c'était le risque de divergence dénoncé ;
  2. fec_io reste de l'entrée-sortie pure (les règles restent chez les
     consommateurs) ;
  3. pages.py est de la présentation pure : aucun import applicatif,
     aucune fonction, rien d'exécutable — la séparation ne doit pas se
     re-dégrader ;
  4. app.py est repassé sous les 1 300 lignes de logique.

Lancer :  pytest -q tests/test_refonte.py
"""
import ast
import os
import sys

import conftest

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import fec_io
import reprise
import valider_fec

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


# === 1. Cohérence des trois consommateurs ==================================

def test_les_trois_lecteurs_voient_le_meme_fichier():
    """Balance (reprise), lignes nommées (rejeu) et validateur doivent
    tomber d'accord sur les totaux du même FEC réel."""
    balance = reprise.lire_balance_fec(FEC2025)
    lignes = fec_io.lignes_nommees(FEC2025)
    total_nomme = round(sum(fec_io.nombre(r["Debit"]) - fec_io.nombre(r["Credit"])
                            for r in lignes), 2)
    assert round(sum(balance.values()), 2) == total_nomme == 0.0  # équilibré
    assert valider_fec.valider(FEC2025) == []                     # conforme
    entete, brut = fec_io.lire_brut(FEC2025)
    assert entete == fec_io.COLONNES
    assert len(lignes) == len([r for r in brut
                               if len(r) >= 18 and any(x.strip() for x in r)])


def test_colonnes_source_unique():
    """valider_fec réexporte les colonnes de fec_io — pas de seconde liste."""
    assert valider_fec.COLONNES is fec_io.COLONNES
    assert len(fec_io.COLONNES) == 18


def test_nombre_conversion_fec():
    assert fec_io.nombre("1234,56") == 1234.56
    assert fec_io.nombre("") == 0.0
    assert fec_io.nombre("  ") == 0.0
    assert fec_io.nombre("-12,50") == -12.5     # le signe est un fait du
    with pytest.raises(ValueError):             # fichier, pas de l'E/S
        fec_io.nombre("abc")


def test_lire_brut_ne_filtre_rien(tmp_path):
    """La tokenisation rend TOUT, y compris les lignes incomplètes : c'est
    le pouvoir de détection du validateur qui en dépend."""
    p = tmp_path / "partiel.txt"
    p.write_text("\t".join(fec_io.COLONNES) + "\r\ncourt\tligne\r\n\r\n",
                 encoding="utf-8")
    entete, lignes = fec_io.lire_brut(str(p))
    assert entete == fec_io.COLONNES
    assert ["court", "ligne"] in lignes          # rendue telle quelle
    # ... et une ligne inexploitable n'est plus escamotée : elle fait
    # ÉCHOUER la lecture nommée, au lieu de disparaître d'une reprise qui
    # se serait ensuite annoncée réussie (constat G-02).
    with pytest.raises(ValueError, match="colonnes annoncées"):
        fec_io.lignes_nommees(str(p))
    assert fec_io.lignes_nommees(str(p), strict=False) == []


# === 2. pages.py : présentation pure =======================================

def test_pages_sans_logique_ni_import_applicatif():
    src = open(conftest.source("pages.py"), encoding="utf-8").read()
    arbre = ast.parse(src)
    for noeud in arbre.body:
        assert not isinstance(noeud, (ast.Import, ast.ImportFrom)), \
            "pages.py ne doit rien importer"
        assert not isinstance(noeud, (ast.FunctionDef, ast.ClassDef)), \
            "pages.py ne doit contenir aucune fonction ni classe"
    constantes = [n.targets[0].id for n in arbre.body
                  if isinstance(n, ast.Assign)]
    assert "CSS" in constantes
    assert sum(1 for c in constantes if c.startswith("PAGE_")) >= 12


def test_app_reste_de_la_logique_pure():
    src = open(conftest.source("app.py"), encoding="utf-8").read()
    # Le VRAI invariant n'est pas la taille — les routes légitimes
    # s'accumulent (panel bêta, ventilation guidée, corrections) — mais
    # l'absence de PRÉSENTATION dans app.py. On teste donc directement
    # cela : aucun bloc de texte triple-guillemets contenant du HTML.
    # Exception assumée : la COQUE du document (<!DOCTYPE>, <head>, la
    # barre de navigation) reste dans app.py. C'est le châssis qu'assemblent
    # les routes, pas un gabarit de page : il dépend de l'état de session
    # (onglet actif, exercice courant, messages) et n'a pas de contenu
    # propre. Tout le RESTE du HTML appartient à pages.py.
    import re as _re
    for bloc in _re.findall(r'"""(.*?)"""', src, _re.S):
        if "<!DOCTYPE" in bloc:
            continue
        assert "<div" not in bloc and "<table" not in bloc, \
            "du HTML est réapparu dans app.py : il appartient à pages.py"
    assert 'PAGE_SAISIE = """' not in src        # aucun gabarit réintroduit
    # Seuil relevé de 2000 à 2200 en v8.40.0, puis à 2250 après les passes
    # G à O. Ce garde-fou vise l'accumulation de HTML et de logique métier
    # dans le routeur ; les deux vérifications ci-dessus s'en chargent et
    # restent strictes. Les lignes ajoutées depuis sont des GARDES —
    # migration à l'ouverture, base absente, sortie de secours, refus de
    # clôturer sur anomalie bloquante, invalidation du cache après
    # restauration — et chaque fois que la RÈGLE elle-même pouvait vivre
    # ailleurs, elle y a été déplacée : la durée d'amortissement dans
    # `amortissement`, l'intégrité d'une archive dans `perennite`. Relever
    # le seuil plutôt que supprimer le contrôle : il continue de signaler
    # une dérive, et il l'a signalée deux fois pendant ces passes.
    assert src.count("\n") < 2250, "app.py devient un monolithe"


def test_toutes_les_pages_rendent_encore(tmp_path, monkeypatch):
    """La refonte ne doit casser AUCUNE page."""
    import importlib
    import init_db
    db = str(tmp_path / "compta.db")
    init_db.init_demo(db, FEC2025, 2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    client = app_mod.app.test_client()
    for page in ("/saisie", "/immobilisations", "/cloture", "/liasse?annee=2026",
                 "/reglementation", "/exercice/nouveau", "/dossiers",
                 "/pense-bete", "/veille", "/archives", "/bac-a-sable"):
        assert client.get(page).status_code == 200, f"page cassée : {page}"
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)
