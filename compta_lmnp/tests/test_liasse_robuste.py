# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Un champ manquant ne doit pas coûter la liasse entière.

Défaut remonté en usage réel (v8.53.0) : l'onglet Liasse répondait
« unsupported format string passed to Undefined.__format__ » et ne
s'affichait plus du tout, en saisie comme après clôture.

Le mécanisme : un gabarit qui demande un champ absent du modèle ne reçoit
pas `None` mais un `Undefined` de Jinja. `_eur` le passait à un f-string
avec spécification (`{x:,.2f}`), Python levait, l'exception remontait, et
la page entière tombait en 500 — **pour un seul champ**, sans jamais le
nommer, donc sans rien donner à diagnostiquer.

Les deux mauvaises réponses possibles sont figées ici en négatif :

- **planter** prive le déclarant de tous ses autres chiffres à cause d'un
  seul, et c'est ce qui se passait ;
- **rendre « — »** serait pire : sur un document fiscal, un montant ABSENT
  passerait pour un montant NUL, et rien ne distinguerait les deux.

La réponse retenue est la troisième : rendre le reste, et porter le manque
à l'endroit exact où il se produit, en le nommant.

Aucune donnée réelle : base blanche, exploitant fictif.

Lancer :  pytest -q tests/test_liasse_robuste.py
"""
import importlib
import os
import sqlite3
import sys

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import formats
import init_db
import operations


@pytest.fixture()
def dossier(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    conn = init_db.init(db, "blanc", annee_cible=2026)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Exploitant fictif','000000000','Adresse fictive')")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total,"
                 "date_acquisition) VALUES (1,1,'Bien fictif',100000,"
                 "'2026-01-01')")
    conn.commit()
    conn.close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))

    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    for mois in range(1, 13):
        operations.saisir(c, type="loyer", montant=800, bien_id=1,
                          date_operation=f"2026-{mois:02d}-05",
                          periode=f"2026-{mois:02d}")
    c.close()
    yield app_mod, app_mod.app.test_client()
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def test_un_champ_absent_ne_fait_plus_tomber_la_liasse(dossier, monkeypatch):
    """Le scénario du défaut : un champ disparaît du modèle, la page devait
    continuer d'exister."""
    app_mod, cl = dossier
    assert cl.get("/liasse").status_code == 200        # état de départ sain

    vraie = app_mod.liasse_mod.generer

    def amputee(conn, annee, *a, **k):
        L = vraie(conn, annee, *a, **k)
        L["page_garde"].pop("resultat_fiscal", None)
        return L

    monkeypatch.setattr(app_mod.liasse_mod, "generer", amputee)
    r = cl.get("/liasse")
    texte = r.get_data(as_text=True)

    assert r.status_code == 200, "la liasse tombe encore pour un seul champ"
    # le champ est NOMMÉ, là où il manque
    assert "champ absent : resultat_fiscal" in texte
    # et le reste de la liasse est bien rendu : 12 × 800 € de loyers
    assert "9 600,00" in texte


def test_un_champ_absent_nest_jamais_confondu_avec_un_zero(dossier,
                                                          monkeypatch):
    """Le point qui compte vraiment. Rendre « — » aurait suffi à faire
    passer le test précédent, et aurait transformé un défaut visible en
    défaut invisible : sur une liasse, un montant absent et un montant nul
    ne se ressemblent pas."""
    app_mod, cl = dossier
    vraie = app_mod.liasse_mod.generer

    def amputee(conn, annee, *a, **k):
        L = vraie(conn, annee, *a, **k)
        L["page_garde"].pop("resultat_fiscal", None)
        return L

    monkeypatch.setattr(app_mod.liasse_mod, "generer", amputee)
    texte = cl.get("/liasse").get_data(as_text=True)
    i = texte.index("champ absent : resultat_fiscal")
    cellule = texte[i - 30:i + 40]
    assert "0,00" not in cellule and "—" not in cellule, cellule


def test_le_champ_absent_laisse_une_trace_dans_le_journal(dossier,
                                                          monkeypatch):
    """Ce qui est visible à l'écran doit aussi être relisible à froid : un
    utilisateur décrit « une erreur », pas un nom de champ."""
    app_mod, cl = dossier
    vus = []
    monkeypatch.setattr(formats, "JOURNAL",
                        lambda motif, *a: vus.append(motif % a))
    vraie = app_mod.liasse_mod.generer

    def amputee(conn, annee, *a, **k):
        L = vraie(conn, annee, *a, **k)
        L["page_garde"].pop("resultat_fiscal", None)
        return L

    monkeypatch.setattr(app_mod.liasse_mod, "generer", amputee)
    cl.get("/liasse")
    assert any("resultat_fiscal" in m for m in vus), vus


# ── La fonction elle-même, hors contexte web ──────────────────────────────

def test_eur_formate_normalement():
    assert formats.eur(1234.5) == "1 234,50 €"
    assert formats.eur(0) == "0,00 €"
    assert formats.eur(None) == "—"          # absence ASSUMÉE par le modèle


def test_eur_nomme_un_undefined_au_lieu_de_lever():
    from jinja2 import Undefined
    rendu = formats.eur(Undefined(name="stock_39c"))
    assert "champ absent" in rendu and "stock_39c" in rendu


def test_eur_ne_leve_sur_aucune_valeur_inattendue():
    """Une chaîne, une liste, un objet : la liasse doit survivre à tout ce
    qu'un modèle mal formé peut lui présenter."""
    for valeur in ("douze", [1, 2], {"a": 1}, object()):
        rendu = formats.eur(valeur)
        assert "valeur inattendue" in rendu, (valeur, rendu)


# ── Exercice clos sans historique des déficits ───────────────────────────
#
# Un exercice clôturé ailleurs puis repris (ici le 2025 du jeu de
# démonstration) n'a pas de suivi des déficits par millésime. La liasse
# ENTIÈRE était refusée, alors que seuls les déficits en report sont
# inconnus — et que la page Liasse porte aussi le suivi des dépôts.

FEC_DEMO = os.path.join(HERE, "demo", "FEC_DEMO_2025.txt")


@pytest.fixture()
def demo(tmp_path):
    c = init_db.init_demo(str(tmp_path / "demo.db"), FEC_DEMO, 2026)
    yield c
    c.close()


def test_liasse_sans_historique_des_deficits_s_edite_avec_avertissement(demo):
    import liasse
    L = liasse.generer(demo, 2025)
    assert len(L["avertissements"]) == 1
    assert "Historique des déficits indisponible pour 2025" in L["avertissements"][0]
    assert "5GA à 5GJ" in L["avertissements"][0]
    # Inconnu n'est pas zéro : totaux à None, jamais 0.
    assert L["reports"]["deficits"] == []
    assert L["reports"]["total_deficits"] is None
    assert L["reports"]["total_restant"] is None
    assert L["page_garde"]["restant_deficits"] is None
    assert L["aide_2042c"]["cases_deficits_anterieurs"] == []
    assert L["aide_2042c"]["deficits_indisponibles"]
    # Le reste est calculé normalement.
    assert L["f2033b"]["produits_218"] > 0


def test_la_garde_des_deficits_reste_stricte_hors_liasse(demo):
    """Seule l'édition de la liasse tolère le manque : un appel direct lève
    toujours, pour qu'aucun autre usage ne prenne un vide pour un zéro."""
    import liasse
    with pytest.raises(liasse.HistoriqueDeficitsIndisponible):
        liasse.suivi_reports(demo, 2025)
    with pytest.raises(ValueError, match="Historique des déficits indisponible"):
        liasse.aide_2042c(demo, 2025)


def test_page_liasse_sans_historique_affiche_le_manque(demo, tmp_path,
                                                       monkeypatch):
    demo.close()
    monkeypatch.setenv("COMPTA_DB", str(tmp_path / "demo.db"))
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    try:
        r = app_mod.app.test_client().get("/liasse?annee=2025")
        page = r.get_data(as_text=True)
        assert r.status_code == 200
        assert "Liasse indisponible" not in page
        assert "Historique des déficits indisponible pour 2025" in page
        assert "non suivi" in page and "non calculable" in page
        assert "Aucun déficit LMNP en report" not in page
        assert 'id="depots"' in page          # le suivi des dépôts reste accessible
    finally:
        monkeypatch.delenv("COMPTA_DB")
        importlib.reload(app_mod)


def test_pdf_sans_historique_nomme_le_manque(demo):
    import io
    import liasse
    pytest.importorskip("reportlab")
    import liasse_pdf
    L = liasse.generer(demo, 2025)
    textes = []
    original = liasse_pdf.Paragraph

    def espion(texte, *a, **k):
        textes.append(texte)
        return original(texte, *a, **k)
    import unittest.mock
    with unittest.mock.patch.object(liasse_pdf, "Paragraph", espion):
        liasse_pdf.generer_pdf(L, io.BytesIO())
    tout = "\n".join(textes)
    assert "ATTENTION : Historique des déficits indisponible" in tout
    assert "Aucun déficit LMNP en stock." not in tout


def test_grid3_est_definie():
    """La grille à trois champs était utilisée sans être définie."""
    from pages import CSS
    assert ".grid3 {" in CSS
