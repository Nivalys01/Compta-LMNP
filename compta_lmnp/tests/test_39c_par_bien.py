# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Suivi 39 C par bien — ventilation du stock logement par logement.

Règle (liasses de référence § 4.1.2) : limitation GLOBALE par exploitant, suivi du
stock PAR LOGEMENT. Invariant central : la somme des stocks par bien égale
le stock global, au centime, à chaque exercice — la limitation globale
(validée par le test en or) n'est jamais modifiée par la ventilation.

Lancer :  pytest -q tests/test_39c_par_bien.py
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import reprise
import fiscal
import init_db
import operations

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


def _somme_par_bien(conn, annee):
    return round(sum(v["stock_cloture"]
                     for v in fiscal.suivi_39c_par_bien(conn, annee)), 2)


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init_demo(str(tmp_path / "b.db"), FEC2025, 2026)
    yield c
    c.close()


def test_mono_bien_ventilation_egale_global(conn):
    """En mono-bien, la ventilation doit être strictement le suivi global."""
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=450,
                          date_operation=f"2026-{m:02d}-05", bien_id=1)
    r = fiscal.cloturer(conn, 2026, forcer=True)
    par_bien = fiscal.suivi_39c_par_bien(conn, 2026)
    assert len(par_bien) == 1
    v = par_bien[0]
    s = r["suivi_39c"]
    assert v["stock_ouverture"] == pytest.approx(s["stock_ouverture"])
    assert v["report_bien"] == pytest.approx(s["report_annee"])
    assert v["utilisation_bien"] == pytest.approx(s["utilisation_annee"])
    assert v["stock_cloture"] == pytest.approx(s["stock_cloture"])


def test_deux_biens_report_ventile_selon_leur_insuffisance(conn):
    """Deux biens avec dotations distinctes : le report global se répartit
    selon l'INSUFFISANCE de chacun — sa dotation moins sa marge locative —
    et la somme retombe sur le global au centime."""
    exp = conn.execute("SELECT id FROM exploitant LIMIT 1").fetchone()[0]
    conn.execute("INSERT INTO bien (id, exploitant_id, libelle, adresse) "
                 "VALUES (2, ?, 'Studio Riom', '1 rue des Fictifs, Riom')", (exp,))
    # composant du bien 2 : 12 000 sur 10 ans en service depuis 3 ans → 1 200/an
    conn.execute(
        "INSERT INTO composant (bien_id, code_immo, libelle, valeur_brute, "
        "duree_annees, date_mise_service, compte_immo, compte_amort) VALUES "
        "(2, 'TEST-B2', 'Aménagements studio', 12000, 10, '2023-01-01', "
        "'218100', '281810')")
    conn.commit()
    # loyers faibles → plafond < dotation totale → report à ventiler
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=300,
                          date_operation=f"2026-{m:02d}-05", bien_id=1)
    r = fiscal.cloturer(conn, 2026, forcer=True)
    s = r["suivi_39c"]
    assert s["report_annee"] > 0                     # scénario significatif
    par_bien = {v["bien_id"]: v for v in fiscal.suivi_39c_par_bien(conn, 2026)}
    assert set(par_bien) == {1, 2}
    dot_totale = sum(v["dotation_bien"] for v in par_bien.values())
    assert dot_totale == pytest.approx(s["dotation_exercice"], abs=0.01)
    # La clé n'est PLUS le prorata des dotations mais l'INSUFFISANCE de
    # chaque bien — ce que sa dotation dépasse de sa marge locative (passe
    # I, constat I-05). Le bien 1 perçoit 3 600 € de loyers, le bien 2
    # aucun : le report doit se concentrer là où il naît.
    loyers_b1 = 300 * 12
    insuffisances = {b: max(0.0, par_bien[b]["dotation_bien"]
                            - (loyers_b1 if b == 1 else 0.0))
                     for b in (1, 2)}
    masse = sum(insuffisances.values())
    attendu_b1 = round(s["report_annee"] * insuffisances[1] / masse, 2)
    assert par_bien[1]["report_bien"] == pytest.approx(attendu_b1, abs=0.011)
    assert par_bien[2]["report_bien"] > 0            # le bien sans loyer aussi
    assert round(par_bien[1]["report_bien"] + par_bien[2]["report_bien"], 2) \
        == pytest.approx(s["report_annee"])
    assert _somme_par_bien(conn, 2026) == pytest.approx(s["stock_cloture"])


def test_activation_en_cours_de_vie_historique_au_bien_ancien(conn):
    """Un dossier avec un stock 39 C historique JAMAIS ventilé (versions
    antérieures) active la ventilation à la clôture suivante : l'historique
    est hérité par le bien le plus ancien, le nouveau bien part de zéro."""
    # init_demo crée déjà l'exercice 2025 clos : on y greffe seulement un
    # stock 39 C historique global, jamais ventilé (versions antérieures).
    conn.execute("INSERT OR REPLACE INTO suivi_39c (exercice_annee, "
                 "stock_cloture) VALUES (2025, 500)")
    exp = conn.execute("SELECT id FROM exploitant LIMIT 1").fetchone()[0]
    conn.execute("INSERT INTO bien (id, exploitant_id, libelle) "
                 "VALUES (2, ?, 'Bien ajouté en cours de vie')", (exp,))
    conn.execute(
        "INSERT INTO composant (bien_id, code_immo, libelle, valeur_brute, "
        "duree_annees, date_mise_service, compte_immo, compte_amort) VALUES "
        "(2, 'TEST-B2V', 'Cuisine bien 2', 5000, 10, '2024-01-01', "
        "'218100', '281810')")
    conn.commit()
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=350,
                          date_operation=f"2026-{m:02d}-05", bien_id=2)
    r = fiscal.cloturer(conn, 2026, forcer=True)
    par_bien = {v["bien_id"]: v for v in fiscal.suivi_39c_par_bien(conn, 2026)}
    assert par_bien[1]["stock_ouverture"] == pytest.approx(500.0)   # héritage
    assert par_bien[2]["stock_ouverture"] == pytest.approx(0.0)
    assert _somme_par_bien(conn, 2026) \
        == pytest.approx(r["suivi_39c"]["stock_cloture"])


def test_utilisation_ventilee_au_prorata_des_stocks(conn):
    """Année de reprise (plafond large) : l'utilisation du stock se répartit
    au prorata des stocks d'ouverture de chaque bien."""
    # année 1 : report (loyers faibles)
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=300,
                          date_operation=f"2026-{m:02d}-05", bien_id=1)
    r1 = fiscal.cloturer(conn, 2026, forcer=True)
    assert r1["suivi_39c"]["stock_cloture"] > 0
    # année 2 : gros loyers → utilisation du stock
    reprise.ouvrir_exercice(conn, 2027)
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=1500,
                          date_operation=f"2027-{m:02d}-05", bien_id=1)
    r2 = fiscal.cloturer(conn, 2027, forcer=True)
    s = r2["suivi_39c"]
    assert s["utilisation_annee"] > 0
    par_bien = fiscal.suivi_39c_par_bien(conn, 2027)
    assert round(sum(v["utilisation_bien"] for v in par_bien), 2) \
        == pytest.approx(s["utilisation_annee"])
    assert _somme_par_bien(conn, 2027) == pytest.approx(s["stock_cloture"])
