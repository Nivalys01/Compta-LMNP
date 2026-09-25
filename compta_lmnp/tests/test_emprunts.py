# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Emprunts : tableau de remboursement, tableau de la banque, génération des
échéances, contrôles, affichage, persistance.

Un test par règle et par refus. Scénarios sur le jeu de démonstration
anonymisé (2025 clôturé, 2026 ouvert, un bien) et des prêts FICTIFS ;
horloge injectée. Les oracles de calcul sont indépendants du module :
fractions exactes et somme géométrique, pas la formule qu'il emploie.

Lancer :  pytest -q tests/test_emprunts.py
"""
import importlib
import os
import re
import shutil
import sqlite3
import sys
from datetime import date
from decimal import Decimal as D
from fractions import Fraction

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import controles
import echeancier
import emprunts
import export_fec
import init_db
import liasse
import migrations
import operations
import perennite
import recurrentes
import rejeu_fec
import valider_fec

FEC_DEMO = os.path.join(HERE, "demo", "FEC_DEMO_2025.txt")
FEC_REF_2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")
MI_MAI = date(2026, 5, 15)
ANNEE = (date(2026, 1, 1), date(2026, 12, 31))


@pytest.fixture(autouse=True)
def horloge(monkeypatch):
    monkeypatch.setattr(echeancier, "_aujourd_hui", lambda: MI_MAI)


@pytest.fixture()
def chemin(tmp_path):
    return str(tmp_path / "compta.db")


@pytest.fixture()
def conn(chemin):
    c = init_db.init_demo(chemin, FEC_DEMO, 2026)
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()


def _champs(**kw):
    champs = dict(bien_id=1, preteur="Banque fictive", capital="1200",
                  taux="12", nb_echeances=12, periodicite="mensuelle",
                  date_deblocage="2025-12-15",
                  date_premiere_echeance="2026-01-31")
    champs.update(kw)
    return champs


def _emprunt(conn, **kw):
    return emprunts.creer(conn, **_champs(**kw))


def _apercu(conn, auj=MI_MAI, du=ANNEE[0], au=ANNEE[1]):
    return emprunts.apercu(conn, du, au, aujourd_hui=auj)


def _generer(conn, retenues=None, auj=MI_MAI, **kw):
    if retenues is None:
        retenues = {x.cle for x in _apercu(conn, auj) if x.cochee_par_defaut}
    return emprunts.generer(conn, *ANNEE, retenues, aujourd_hui=auj, **kw)


def _instantane(conn, eid):
    return [(x.rang, x.date, x.capital, x.interets, x.assurance, x.crd,
             x.origine) for x in emprunts.tableau(conn, eid)]


def _oracle_annuite(capital, taux_annuel, n, mois=1) -> D:
    """Échéance constante SANS la formule fermée : C = a × Σ (1+i)^-k,
    en fractions exactes, puis arrondi commercial au centime."""
    i = Fraction(taux_annuel) * mois / 12
    if i == 0:
        a = Fraction(capital) / n
    else:
        a = Fraction(capital) / sum((1 + i) ** -k for k in range(1, n + 1))
    centimes = a * 100
    entier = int(centimes)
    if centimes - entier >= Fraction(1, 2):
        entier += 1
    return D(entier) / 100


def _csv(lignes, sep=";"):
    return "\n".join(sep.join(x) for x in lignes).encode("utf-8")


def _csv_du_tableau(lignes):
    """Tableau → CSV façon banque : CRD APRÈS l'échéance, virgule décimale."""
    f = lambda v: f"{v:.2f}".replace(".", ",")          # noqa: E731
    return _csv([["Date", "Échéance", "Capital", "Intérêts", "Assurance",
                  "CRD"]] + [[x.date.strftime("%d/%m/%Y"), f(x.echeance),
                              f(x.capital), f(x.interets), f(x.assurance),
                              f(x.crd)] for x in lignes])


# ── Calcul : lot 1 ───────────────────────────────────────────────────────

def test_mensualite_1200_a_12_pourcent_sur_12_mois():
    oracle = _oracle_annuite(1200, Fraction(12, 100), 12)
    assert oracle == D("106.62")
    lignes = emprunts.calculer(D("1200"), D("0.12"), 12, "mensuelle",
                               date(2026, 1, 31))
    assert lignes[0].echeance == oracle
    assert all(x.echeance == oracle for x in lignes[:-1])


def test_echeance_constante_est_un_decimal_exact():
    a = emprunts.echeance_constante(D("1200"), D("0.01"), 12)
    assert isinstance(a, D) and a == D("106.62")


def test_taux_nul_capital_divise_derniere_ajustee():
    lignes = emprunts.calculer(D("1000"), D("0"), 3, "mensuelle",
                               date(2026, 1, 31))
    assert [x.capital for x in lignes] == [D("333.33"), D("333.33"),
                                           D("333.34")]
    assert all(x.interets == 0 for x in lignes)


def test_200000_a_3_5_sur_240_mois_somme_exacte_derniere_ajustee():
    lignes = emprunts.calculer(D("200000"), D("0.035"), 240, "mensuelle",
                               date(2026, 1, 5))
    a = _oracle_annuite(200000, Fraction(35, 1000), 240)
    assert lignes[0].echeance == a
    assert sum(x.capital for x in lignes) == D("200000.00")
    assert lignes[-1].crd == 0
    assert lignes[-1].capital == lignes[-2].crd          # CRD exact soldé
    assert lignes[-1].echeance != a                       # échéance ajustée


def test_interets_de_chaque_ligne_crd_fois_taux_au_centime():
    lignes = emprunts.calculer(D("200000"), D("0.035"), 240, "mensuelle",
                               date(2026, 1, 5))
    crd = Fraction(200000)
    i = Fraction(35, 1000) / 12
    for x in lignes:
        attendu = crd * i * 100
        c = int(attendu) + (1 if attendu - int(attendu) >= Fraction(1, 2)
                            else 0)
        assert x.interets == D(c) / 100
        crd -= Fraction(str(x.capital))


def test_invariants_de_tout_tableau_calcule():
    for capital, taux, n, per in (("1200", "0.12", 12, "mensuelle"),
                                  ("200000", "0.035", 240, "mensuelle"),
                                  ("50000", "0.02", 40, "trimestrielle"),
                                  ("80000", "0.041", 15, "annuelle"),
                                  ("10000", "0", 7, "mensuelle")):
        lignes = emprunts.calculer(D(capital), D(taux), n, per,
                                   date(2026, 1, 31))
        emprunts.verifier_tableau(lignes, D(capital))
        crds = [D(capital)] + [x.crd for x in lignes]
        assert all(a > b for a, b in zip(crds, crds[1:]))
        assert all(x.interets >= 0 and x.capital > 0 for x in lignes)


def test_taux_periodique_proportionnel():
    assert emprunts.taux_periodique(D("0.04"), "mensuelle") == D("0.04") / 12
    assert emprunts.taux_periodique(D("0.04"), "trimestrielle") == D("0.01")
    assert emprunts.taux_periodique(D("0.04"), "annuelle") == D("0.04")


# ── Dates ────────────────────────────────────────────────────────────────

def _dates(premiere, per="mensuelle", n=5):
    return emprunts.dates_echeances(premiere, per, n)


def test_mensuelle_ancree_au_31_janvier_fevrier_bissextile():
    assert _dates(date(2028, 1, 31)) == [
        date(2028, 1, 31), date(2028, 2, 29), date(2028, 3, 31),
        date(2028, 4, 30), date(2028, 5, 31)]


def test_trimestrielle_depuis_le_31_janvier():
    assert _dates(date(2027, 1, 31), "trimestrielle", 4) == [
        date(2027, 1, 31), date(2027, 4, 30), date(2027, 7, 31),
        date(2027, 10, 31)]


def test_trimestrielle_par_un_fevrier_bissextile():
    assert _dates(date(2027, 11, 30), "trimestrielle", 3) == [
        date(2027, 11, 30), date(2028, 2, 29), date(2028, 5, 30)]


def test_jamais_de_debordement_sur_le_mois_suivant():
    d = _dates(date(2026, 1, 31), n=24)
    attendus = [(2026 + k // 12, k % 12 + 1) for k in range(24)]
    assert [(x.year, x.month) for x in d] == attendus


# ── Refus à la création ──────────────────────────────────────────────────

@pytest.mark.parametrize("champs, motif", [
    ({"capital": "0"}, "strictement positif"),
    ({"capital": "-1000"}, "strictement positif"),
    ({"nb_echeances": "0"}, "ENTIER"),
    ({"nb_echeances": "12.5"}, "ENTIER"),
    ({"nb_echeances": "481"}, "ENTIER"),
    ({"taux": "-1"}, "négatif"),
    ({"taux": "35"}, "TAEG"),
    ({"date_premiere_echeance": "2025-12-01"}, "précéder le déblocage"),
    ({"date_premiere_echeance": "2026-02-31"}, "invalide"),
    ({"periodicite": "semestrielle"}, "Périodicité inconnue"),
    ({"bien_id": 99}, "inconnu"),
    ({"preteur": ""}, "obligatoire"),
    ({"preteur": "Banque\tfictive"}, "tabulation"),
    ({"capital": "1,234"}, "ambigu"),
], ids=["capital-nul", "capital-negatif", "duree-nulle", "duree-non-entiere",
        "duree-trop-longue", "taux-negatif", "taux-hors-borne",
        "premiere-avant-deblocage", "date-inexistante", "periodicite",
        "bien-inconnu", "preteur-vide", "preteur-tabulation",
        "capital-ambigu"])
def test_refus_a_la_creation(conn, champs, motif):
    with pytest.raises(ValueError, match=motif):
        _emprunt(conn, **champs)
    assert conn.execute("SELECT COUNT(*) FROM emprunt").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM emprunt_ligne").fetchone()[0] == 0


def test_taux_a_la_borne_accepte_et_taux_nul_accepte(conn):
    _emprunt(conn, taux="20")
    _emprunt(conn, taux="0")
    assert conn.execute("SELECT COUNT(*) FROM emprunt").fetchone()[0] == 2


def test_creation_stocke_des_centimes_entiers(conn):
    eid = _emprunt(conn, capital="98 765,40", taux="1", nb_echeances=240,
                   assurance="8,04")
    types = conn.execute(
        "SELECT DISTINCT typeof(capital_c), typeof(interets_c), "
        "typeof(assurance_c), typeof(crd_c) FROM emprunt_ligne "
        "WHERE emprunt_id=?", (eid,)).fetchall()
    assert types == [("integer",) * 4]
    assert emprunts.emprunt(conn, eid)["taux"] == D("0.01")


# ── Remplacement ligne à ligne ───────────────────────────────────────────

def test_remplacement_capital_negatif_refuse_tableau_intact(conn):
    eid = _emprunt(conn)
    avant = _instantane(conn, eid)
    with pytest.raises(ValueError, match="capital amorti négatif"):
        emprunts.remplacer_ligne(conn, eid, 3, date_echeance="2026-03-31",
                                 capital="-5", interets="10")
    assert _instantane(conn, eid) == avant


def test_remplacement_somme_des_capitaux_fausse_refuse(conn):
    eid = _emprunt(conn)
    avant = _instantane(conn, eid)
    derniere = avant[-1]
    with pytest.raises(ValueError, match="ne solde pas le prêt"):
        emprunts.remplacer_ligne(conn, eid, 12, date_echeance=derniere[1],
                                 capital=derniere[2] - D("1"),
                                 interets=derniere[3])
    assert _instantane(conn, eid) == avant


def test_remplacement_differe_recalcule_la_suite_a_echeances_constantes(conn):
    """Un différé d'amortissement : la première échéance ne paie que les
    intérêts ; la banque amortit alors le capital sur les 11 restantes."""
    eid = _emprunt(conn)
    r = emprunts.remplacer_ligne(conn, eid, 1, date_echeance="2026-01-31",
                                 capital="0", interets="12")
    assert r["recalculees"] == 11 and r["ecart_interets"] is None
    lignes = emprunts.tableau(conn, eid)
    assert lignes[0].origine == "saisie" and lignes[0].crd == D("1200")
    a = _oracle_annuite(1200, Fraction(12, 100), 11)
    assert all(x.echeance == a for x in lignes[1:-1])
    emprunts.verifier_tableau(lignes, D("1200"))


def test_remplacement_interets_differents_accepte_et_signale(conn):
    eid = _emprunt(conn)
    r = emprunts.remplacer_ligne(conn, eid, 1, date_echeance="2026-01-31",
                                 capital="94.62", interets="6.10")
    assert r["ecart_interets"] == D("12.00")
    v = emprunts.vue(conn, eid)
    assert v["lignes"][0]["interets_attendus"] == D("12.00")


def test_remplacement_ligne_inexistante_refuse(conn):
    eid = _emprunt(conn)
    with pytest.raises(ValueError, match="n'existe pas"):
        emprunts.remplacer_ligne(conn, eid, 13, date_echeance="2027-01-31",
                                 capital="1", interets="0")


def test_remplacement_date_hors_ordre_refuse(conn):
    eid = _emprunt(conn)
    avant = _instantane(conn, eid)
    with pytest.raises(ValueError, match="antérieure ou égale"):
        emprunts.remplacer_ligne(conn, eid, 3, date_echeance="2026-02-15",
                                 capital="95", interets="10")
    assert _instantane(conn, eid) == avant


def test_lignes_de_la_banque_suivantes_jamais_recalculees(conn):
    eid = _emprunt(conn)
    emprunts.importer_csv(conn, eid, _csv_du_tableau(
        emprunts.tableau(conn, eid)))
    with pytest.raises(ValueError):
        emprunts.remplacer_ligne(conn, eid, 2, date_echeance="2026-02-28",
                                 capital="50", interets="10.94")
    assert all(x.origine == "import" for x in emprunts.tableau(conn, eid))


def test_modifier_les_parametres_recalcule(conn):
    eid = _emprunt(conn)
    emprunts.modifier(conn, eid, taux="0")
    assert emprunts.tableau(conn, eid)[0].echeance == D("100.00")


def test_modifier_refuse_si_lignes_de_la_banque(conn):
    eid = _emprunt(conn)
    emprunts.remplacer_ligne(conn, eid, 1, date_echeance="2026-01-31",
                             capital="0", interets="12")
    with pytest.raises(ValueError, match="effacerait"):
        emprunts.modifier(conn, eid, taux="3")


# ── Atomicité ────────────────────────────────────────────────────────────

def test_exception_pendant_le_remplacement_ancien_tableau_intact(conn,
                                                                 monkeypatch):
    eid = _emprunt(conn)
    avant = _instantane(conn, eid)
    origine = emprunts._inserer_ligne
    compte = {"n": 0}

    def panne(c, e, x):
        compte["n"] += 1
        if compte["n"] == 3:
            raise RuntimeError("panne simulée au milieu du remplacement")
        origine(c, e, x)
    monkeypatch.setattr(emprunts, "_inserer_ligne", panne)
    autre = emprunts.calculer(D("1200"), D("0"), 12, "mensuelle",
                              date(2026, 1, 31))
    with pytest.raises(RuntimeError):
        emprunts.importer_csv(conn, eid, _csv_du_tableau(autre))
    assert _instantane(conn, eid) == avant
    assert len(avant) == 12
    assert not conn.in_transaction


def test_exception_a_la_creation_rien_ne_reste(conn, monkeypatch):
    monkeypatch.setattr(emprunts, "_inserer_ligne",
                        lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        _emprunt(conn)
    assert conn.execute("SELECT COUNT(*) FROM emprunt").fetchone()[0] == 0


def test_dans_la_transaction_d_un_appelant_rien_n_est_committe(conn):
    eid = _emprunt(conn)
    conn.execute("BEGIN IMMEDIATE")
    emprunts.remplacer_ligne(conn, eid, 1, date_echeance="2026-01-31",
                             capital="0", interets="12")
    assert conn.in_transaction
    conn.rollback()
    assert emprunts.tableau(conn, eid)[0].origine == "calcul"


# ── Import du tableau de la banque ───────────────────────────────────────

def test_import_aller_retour_identique(conn):
    eid = _emprunt(conn)
    avant = [x[:6] for x in _instantane(conn, eid)]
    r = emprunts.importer_csv(conn, eid, emprunts.exporter_csv(conn, eid))
    assert r["nb"] == 12 and r["premier_rang"] == 1
    assert [x[:6] for x in _instantane(conn, eid)] == avant
    assert {x.origine for x in emprunts.tableau(conn, eid)} == {"import"}


def test_import_31_fevrier_fichier_rejete_tableau_inchange(conn):
    eid = _emprunt(conn)
    avant = _instantane(conn, eid)
    texte = _csv_du_tableau(emprunts.tableau(conn, eid)).decode()
    texte = texte.replace("28/02/2026", "31/02/2026")
    with pytest.raises(ValueError, match=r"Ligne 3 .*31/02/2026.*invalide"):
        emprunts.importer_csv(conn, eid, texte.encode())
    assert _instantane(conn, eid) == avant


@pytest.mark.parametrize("valeur", ["1,234", "1.234", "1.234,56",
                                    "1,234.56", "12,345", "douze"])
def test_import_separateur_ambigu_ou_illisible_refuse(conn, valeur):
    eid = _emprunt(conn)
    avant = _instantane(conn, eid)
    lignes = emprunts.tableau(conn, eid)
    texte = _csv_du_tableau(lignes).decode().splitlines()
    cellules = texte[4].split(";")
    cellules[3] = valeur
    texte[4] = ";".join(cellules)
    with pytest.raises(ValueError, match="Ligne 5"):
        emprunts.importer_csv(conn, eid, "\n".join(texte).encode())
    assert _instantane(conn, eid) == avant


def test_import_separateur_decimal_change_en_cours_de_fichier(conn):
    eid = _emprunt(conn)
    texte = _csv_du_tableau(emprunts.tableau(conn, eid)).decode().splitlines()
    texte[6] = texte[6].replace(",", ".")
    with pytest.raises(ValueError, match="Ligne 7 .*séparateur décimal"):
        emprunts.importer_csv(conn, eid, "\n".join(texte).encode())


def test_import_signe_conserve_ligne_negative_rejette_le_fichier(conn):
    """Une ligne cohérente en tout, sauf un capital NÉGATIF : il n'est pas
    pris en valeur absolue, et le fichier est rejeté en citant sa ligne."""
    eid = _emprunt(conn)
    avant = _instantane(conn, eid)
    lignes = emprunts.tableau(conn, eid)
    lignes[4].capital = D("-10")
    crd = D("1200")
    for x in lignes:
        crd -= x.capital
        x.crd = crd
    lignes[-1].capital += lignes[-1].crd
    lignes[-1].crd = D("0")
    with pytest.raises(ValueError, match="Ligne 6 : .*capital amorti négatif"):
        emprunts.importer_csv(conn, eid, _csv_du_tableau(lignes))
    assert _instantane(conn, eid) == avant


def test_import_colonne_manquante_refuse_avec_numero(conn):
    eid = _emprunt(conn)
    texte = _csv_du_tableau(emprunts.tableau(conn, eid)).decode().splitlines()
    texte[2] = ";".join(texte[2].split(";")[:5])
    with pytest.raises(ValueError, match="Ligne 3 : 5 colonne"):
        emprunts.importer_csv(conn, eid, "\n".join(texte).encode())


def test_import_presentation_banque_crd_avant_et_assurance_comprise(conn):
    """Présentation des tableaux réels examinés : capital restant dû « en
    début de période », échéance assurance comprise."""
    eid = _emprunt(conn, assurance="2")
    lignes = emprunts.tableau(conn, eid)
    f = lambda v: f"{v:.2f}".replace(".", ",")          # noqa: E731
    crd = D("1200")
    rows = [["Date", "Échéance assurance comprise", "Capital", "Intérêts",
             "Assurance", "Capital restant dû en début de période"]]
    for x in lignes:
        rows.append([x.date.strftime("%d-%m-%Y"), f(x.total), f(x.capital),
                     f(x.interets), f(x.assurance), f(crd)])
        crd = x.crd
    r = emprunts.importer_csv(conn, eid, _csv(rows, sep="\t"))
    assert r["crd_avant_echeance"] and r["assurance_comprise"]
    assert [x.crd for x in emprunts.tableau(conn, eid)] == \
        [x.crd for x in lignes]


def test_import_echeance_incoherente_refuse(conn):
    eid = _emprunt(conn)
    lignes = emprunts.tableau(conn, eid)
    texte = _csv_du_tableau(lignes).decode().splitlines()
    cellules = texte[3].split(";")
    cellules[1] = "999,99"
    texte[3] = ";".join(cellules)
    with pytest.raises(ValueError, match="Ligne 4 : échéance"):
        emprunts.importer_csv(conn, eid, "\n".join(texte).encode())


def test_import_crd_qui_ne_s_enchaine_pas_refuse(conn):
    eid = _emprunt(conn)
    texte = _csv_du_tableau(emprunts.tableau(conn, eid)).decode().splitlines()
    cellules = texte[6].split(";")
    cellules[5] = "1,00"
    texte[6] = ";".join(cellules)
    with pytest.raises(ValueError, match="ne s'enchaîne pas"):
        emprunts.importer_csv(conn, eid, "\n".join(texte).encode())


def _tableau_avec_reliquat(conn, eid, reliquat=D("100.00")):
    """Cas vu sur un tableau réel : la dernière ligne laisse un reliquat."""
    lignes = emprunts.tableau(conn, eid)
    lignes[-1].capital -= reliquat
    lignes[-1].crd = reliquat
    return lignes


def test_import_tableau_qui_ne_solde_pas_accepte_avec_alerte(conn):
    """Décision du 25/09/2026 : la banque fait foi, le reliquat est admis
    et signalé (le capital n'est pas comptabilisé)."""
    eid = _emprunt(conn)
    r = emprunts.importer_csv(conn, eid, _csv_du_tableau(
        _tableau_avec_reliquat(conn, eid)))
    assert r["reliquat"] == D("100.00")
    v = emprunts.vue(conn, eid)
    assert v["reliquat"] == D("100.00")
    assert "100,00 € restent dus" in emprunts.alerte_reliquat(v["reliquat"])
    assert emprunts.crd_au(v["emprunt"], emprunts.tableau(conn, eid),
                           date(2027, 6, 1)) == D("100.00")


def test_tableau_saisi_a_la_main_doit_solder(conn):
    """Le reliquat n'est admis que pour un tableau importé de la banque."""
    eid = _emprunt(conn)
    lignes = _tableau_avec_reliquat(conn, eid)
    for x in lignes:
        x.origine = "saisie"
    with pytest.raises(emprunts.TableauInvalide, match="restent dus"):
        emprunts.verifier_tableau(lignes, D("1200"))


def test_reliquat_puis_remplacement_d_une_ligne_de_la_banque(conn):
    eid = _emprunt(conn)
    emprunts.importer_csv(conn, eid, _csv_du_tableau(
        _tableau_avec_reliquat(conn, eid)))
    x = emprunts.tableau(conn, eid)[3]
    emprunts.remplacer_ligne(conn, eid, 4, date_echeance=x.date,
                             capital=x.capital, interets=x.interets + 1)
    assert emprunts.vue(conn, eid)["reliquat"] == D("100.00")


def test_import_capital_superieur_au_du_refuse(conn):
    eid = _emprunt(conn)
    lignes = _tableau_avec_reliquat(conn, eid, D("-5.00"))
    with pytest.raises(ValueError, match="négatif"):
        emprunts.importer_csv(conn, eid, _csv_du_tableau(lignes))


def test_import_d_un_emprunt_en_cours_a_partir_du_rang_k(conn):
    eid = _emprunt(conn, capital="10000", nb_echeances=24,
                   date_deblocage="2024-12-01",
                   date_premiere_echeance="2025-01-05")
    banque = emprunts.calculer(D("9500"), D("0.12"), 12, "mensuelle",
                               date(2026, 1, 5))
    r = emprunts.importer_csv(conn, eid, _csv_du_tableau(banque))
    assert r["premier_rang"] == 13 and r["crd_depart"] == D("9500")
    lignes = emprunts.tableau(conn, eid)
    assert lignes[0].rang == 13 and len(lignes) == 12
    e = emprunts.emprunt(conn, eid)
    assert (e["rang_depart"], e["crd_depart"]) == (13, D("9500.00"))


def test_import_premiere_date_inconnue_refuse(conn):
    eid = _emprunt(conn)
    banque = emprunts.calculer(D("1200"), D("0.12"), 12, "mensuelle",
                               date(2026, 2, 15))
    with pytest.raises(ValueError, match="n'est celle d'aucune échéance"):
        emprunts.importer_csv(conn, eid, _csv_du_tableau(banque))


def test_import_d_un_differe_reel_ecarts_d_interets_signales(conn):
    """Structure d'une offre réelle, montants fictifs : première échéance
    brisée, différé d'amortissement, puis échéances constantes."""
    eid = _emprunt(conn, capital="24000", taux="1,2", nb_echeances=36,
                   date_deblocage="2025-12-20")
    i = D("0.012") / 12
    lignes = [emprunts.LigneTableau(1, date(2026, 1, 31), D("0"), D("9.47"),
                                    D("0"), D("24000"), "import")]
    for k, jour in enumerate(emprunts.dates_echeances(
            date(2026, 2, 28), "mensuelle", 5), start=2):
        lignes.append(emprunts.LigneTableau(k, jour, D("0"), D("24.00"),
                                            D("0"), D("24000"), "import"))
    lignes += emprunts.amortir(D("24000"), i, emprunts.dates_echeances(
        date(2026, 7, 31), "mensuelle", 30), [D("0")] * 30, 7)
    r = emprunts.importer_csv(conn, eid, _csv_du_tableau(lignes))
    assert r["nb"] == 36 and r["ecarts_interets"] == 1   # l'échéance brisée
    assert emprunts.vue(conn, eid)["lignes"][0]["interets_attendus"] == \
        D("24.00")


# ── Déblocages successifs ────────────────────────────────────────────────

def _pret_apres_deblocages(conn):
    """Déblocages par tranches jusqu'en mai : intérêts saisis à la main,
    puis tableau de la banque importé à partir de l'échéance de juin, où
    le prêt suit son cours normal."""
    for mois in ("01", "02", "03", "04", "05"):
        operations.saisir(conn, type="interets_emprunt", montant=7.5,
                          date_operation=f"2026-{mois}-05")
    eid = _emprunt(conn, capital="1200", nb_echeances=17,
                   date_premiere_echeance="2026-01-05")
    banque = emprunts.calculer(D("900"), D("0.12"), 12, "mensuelle",
                               date(2026, 6, 5))
    emprunts.importer_csv(conn, eid, _csv_du_tableau(banque))
    return eid


def test_deblocages_seules_les_echeances_du_tableau_se_generent(conn):
    eid = _pret_apres_deblocages(conn)
    assert emprunts.tableau(conn, eid)[0].rang == 6
    lignes = emprunts.apercu(conn, *ANNEE, aujourd_hui=date(2026, 12, 31))
    assert {x.echeance.date.month for x in lignes} == set(range(6, 13))


def test_deblocages_interets_saisis_avant_le_tableau_pas_d_alerte(conn):
    _pret_apres_deblocages(conn)
    lignes = emprunts.apercu(conn, *ANNEE, aujourd_hui=date(2026, 12, 31))
    assert all(not x.echeance.alertes and x.cochee_par_defaut for x in lignes)


def test_deblocages_controle_limite_a_la_periode_du_tableau(conn,
                                                            monkeypatch):
    _pret_apres_deblocages(conn)
    monkeypatch.setattr(echeancier, "_aujourd_hui", lambda: date(2026, 12, 31))
    emprunts.generer(conn, *ANNEE, {x.cle for x in emprunts.apercu(
        conn, *ANNEE, aujourd_hui=date(2026, 12, 31))},
        aujourd_hui=date(2026, 12, 31))
    r = emprunts.ecart_interets(conn, 2026)
    assert r["du"] == date(2026, 6, 5) and r["ecart"] == 0
    assert "EMPRUNT_INTERETS" not in _codes(conn)


def test_aide_des_deblocages_affichee():
    assert "à partir de l'échéance où le prêt suit son cours normal" in \
        emprunts.AIDE_DEBLOCAGES


# ── Sources ──────────────────────────────────────────────────────────────

def test_sources_des_emprunts_au_corpus_de_la_veille_fiscale():
    import veille_fiscale
    refs = " ".join(r for r, *_ in veille_fiscale.CORPUS)
    for attendu in ("BOI-BIC-CHG-50", "art. 1121-1", "932-1", "L313-25",
                    "L314-1"):
        assert attendu in refs
    effets = " ".join(e for _, _, e, _ in veille_fiscale.CORPUS)
    for compte in ("164", "275", "616", "6611", "661100"):
        assert compte in effets


# ── Génération des échéances ─────────────────────────────────────────────

def test_une_seule_ecriture_par_echeance_interets_et_assurance(conn):
    eid = _emprunt(conn, assurance="2,50")
    r = _generer(conn)
    assert len(r["creees"]) == 4 and r["nb_operations"] == 8
    lignes = emprunts.tableau(conn, eid)
    for x, cree in zip(lignes, r["creees"]):
        ecr = {e for (e,) in conn.execute(
            "SELECT DISTINCT ecriture_id FROM operation WHERE id IN (?,?)",
            cree["operations"])}
        assert len(ecr) == 1
        mouvements = conn.execute(
            "SELECT compte_num, debit, credit FROM ligne WHERE ecriture_id=? "
            "ORDER BY id", (ecr.pop(),)).fetchall()
        assert mouvements == [("661100", float(x.interets), 0.0),
                              ("616110", 2.5, 0.0),
                              ("108000", 0.0, float(x.interets + x.assurance))]
    assert conn.execute("SELECT COUNT(*) FROM ligne WHERE compte_num='164000'"
                        ).fetchone()[0] == 0


def test_journal_piece_et_types_des_operations(conn):
    _emprunt(conn, assurance="2,50")
    _generer(conn)
    ops = conn.execute("SELECT type, source, periode FROM operation "
                       "WHERE source='emprunt' ORDER BY id").fetchall()
    assert [t for t, _, _ in ops[:2]] == ["interets_emprunt",
                                          "assurance_emprunteur"]
    assert ops[0][2] == "2026-01"
    assert conn.execute(
        "SELECT DISTINCT journal_code, piece_ref FROM ecriture e JOIN "
        "operation o ON o.ecriture_id=e.id WHERE o.source='emprunt' "
        "AND o.periode='2026-01'").fetchall() == [("BQ", "ECH 1-1")]


def test_rejeu_de_la_generation_zero_ecriture(conn):
    _emprunt(conn)
    _generer(conn)
    n = conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0]
    cles = {x.cle for x in _apercu(conn)}
    r = _generer(conn, retenues=cles)
    assert r["nb_operations"] == 0
    assert conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] == n


def test_idempotence_garantie_par_la_base_emprunt_et_rang(conn):
    _emprunt(conn)
    _generer(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO echeance_generee (source, source_id, "
                     "date_echeance, etat, genere_le, rang) VALUES "
                     "('emprunt', 1, '2031-01-01', 'generee', 'x', 1)")
    conn.rollback()


def test_seules_les_echeances_echues_d_un_exercice_ouvert(conn):
    _emprunt(conn, date_deblocage="2025-10-01",
             date_premiere_echeance="2025-11-30")
    statuts = {x.echeance.date: x.statut for x in emprunts.apercu(
        conn, date(2025, 1, 1), ANNEE[1], aujourd_hui=MI_MAI)}
    assert statuts[date(2025, 11, 30)] == echeancier.IGNOREE     # 2025 clos
    assert statuts[date(2026, 4, 30)] == echeancier.A_GENERER
    assert statuts[date(2026, 5, 30)] == echeancier.A_VENIR     # jour tenu


def test_echeance_deja_importee_du_releve_signalee_et_decochee(conn):
    eid = _emprunt(conn, assurance="2,50")
    total = float(emprunts.tableau(conn, eid)[1].total)
    operations.saisir(conn, type="attente_decaissement", montant=total,
                      date_operation="2026-03-02", source="import")
    fevrier = {x.echeance.date: x for x in _apercu(conn)}[date(2026, 2, 28)]
    assert fevrier.doublons and not fevrier.cochee_par_defaut


def test_interets_deja_saisis_a_la_main_alerte_et_decoche(conn):
    _emprunt(conn)
    operations.saisir(conn, type="autres_charges", montant=60.0,
                      date_operation="2026-03-10",
                      libelle="Intérêts emprunt premier trimestre")
    lignes = _apercu(conn)
    assert all(x.echeance.alertes and not x.cochee_par_defaut
               for x in lignes if x.statut == echeancier.A_GENERER)
    assert "compterait deux fois" in lignes[0].echeance.alertes[0]


def test_echeance_sans_charge_ignoree_avec_motif(conn):
    _emprunt(conn, taux="0")
    x = _apercu(conn)[0]
    assert x.statut == echeancier.IGNOREE and "aucune charge" in x.motif


def test_echeance_posterieure_a_la_cession_ignoree(conn):
    import cession
    cession.assurer_schema(conn)
    _emprunt(conn)
    conn.execute("UPDATE bien SET date_cession='2026-03-15' WHERE id=1")
    conn.commit()
    statuts = {x.echeance.date: x.statut for x in _apercu(conn)}
    assert statuts[date(2026, 3, 31)] == echeancier.IGNOREE
    assert statuts[date(2026, 2, 28)] == echeancier.A_GENERER


def test_exception_pendant_la_generation_rien_n_est_cree(conn, monkeypatch):
    _emprunt(conn)
    avant = conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0]
    origine = operations.saisir_ventilee
    compte = {"n": 0}

    def panne(*a, **kw):
        compte["n"] += 1
        if compte["n"] == 3:
            raise RuntimeError("panne simulée")
        return origine(*a, **kw)
    monkeypatch.setattr(operations, "saisir_ventilee", panne)
    with pytest.raises(echeancier.LotAnnule, match="Échéance 3/12"):
        _generer(conn)
    assert conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] == avant
    assert conn.execute("SELECT COUNT(*) FROM echeance_generee").fetchone()[0] \
        == 0


# ── Verrouillage ─────────────────────────────────────────────────────────

def test_rangs_generes_et_precedents_verrouilles(conn):
    eid = _emprunt(conn)
    cles = [x.cle for x in _apercu(conn)]
    _generer(conn, retenues={cles[2]})                   # la n° 3 seule
    assert emprunts.rang_verrouille(conn, eid) == 3
    for rang in (1, 3):
        with pytest.raises(ValueError, match="verrouillée"):
            emprunts.remplacer_ligne(conn, eid, rang,
                                     date_echeance="2026-01-31",
                                     capital="0", interets="12")
    emprunts.remplacer_ligne(conn, eid, 4, date_echeance="2026-04-30",
                             capital="90", interets="9.33")


def test_modifier_le_tableau_ne_reecrit_jamais_une_ecriture(conn):
    eid = _emprunt(conn)
    _generer(conn)
    avant = conn.execute("SELECT * FROM ligne ORDER BY id").fetchall()
    emprunts.remplacer_ligne(conn, eid, 6, date_echeance="2026-06-30",
                             capital="80", interets="7.00")
    assert conn.execute("SELECT * FROM ligne ORDER BY id").fetchall() == avant


def test_import_modifiant_un_rang_verrouille_refuse(conn):
    eid = _emprunt(conn)
    _generer(conn)
    lignes = emprunts.calculer(D("1200"), D("0.11"), 12, "mensuelle",
                               date(2026, 1, 31))
    avant = _instantane(conn, eid)
    with pytest.raises(ValueError, match="verrouillée"):
        emprunts.importer_csv(conn, eid, _csv_du_tableau(lignes))
    assert _instantane(conn, eid) == avant


def test_import_identique_sur_les_rangs_verrouilles_accepte(conn):
    eid = _emprunt(conn)
    _generer(conn)
    emprunts.importer_csv(conn, eid, emprunts.exporter_csv(conn, eid))
    assert emprunts.rang_verrouille(conn, eid) == 4


def test_ecartee_verrouille_puis_retablir_deverrouille(conn):
    eid = _emprunt(conn)
    cle = _apercu(conn)[1].cle
    _generer(conn, retenues=set(), ecarter={cle})
    assert emprunts.rang_verrouille(conn, eid) == 2
    echeancier.retablir(conn, cle)
    assert emprunts.rang_verrouille(conn, eid) == 0
    emprunts.remplacer_ligne(conn, eid, 2, date_echeance="2026-02-28",
                             capital="95", interets="10.94")


def test_suppression_refusee_des_qu_une_echeance_est_passee(conn):
    eid = _emprunt(conn)
    _generer(conn)
    with pytest.raises(ValueError, match="ne peut plus être supprimé"):
        emprunts.supprimer(conn, eid)
    eid2 = _emprunt(conn)
    emprunts.supprimer(conn, eid2)
    assert conn.execute("SELECT COUNT(*) FROM emprunt_ligne WHERE "
                        "emprunt_id=?", (eid2,)).fetchone()[0] == 0


# ── Opérations d'une échéance ────────────────────────────────────────────

def test_annuler_une_part_annule_toute_l_echeance(conn):
    _emprunt(conn, assurance="2,50")
    r = _generer(conn)
    interets, assurance = r["creees"][0]["operations"]
    n = conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0]
    res = operations.annuler(conn, assurance)
    assert res["operations_annulees"] == [interets, assurance]
    assert conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] == n + 1
    assert conn.execute("SELECT annulee FROM operation WHERE id IN (?,?)",
                        (interets, assurance)).fetchall() == [(1,), (1,)]
    with pytest.raises(ValueError, match="déjà annulée"):
        operations.annuler(conn, interets)


def test_une_part_d_echeance_ne_se_duplique_pas(conn):
    _emprunt(conn, assurance="2,50")
    oid = _generer(conn)["creees"][0]["operations"][0]
    with pytest.raises(ValueError, match="paiement ventilé"):
        operations.dupliquer(conn, oid)


def test_une_part_d_echeance_ne_devient_pas_un_modele_recurrent(conn):
    _emprunt(conn, assurance="2,50")
    oid = _generer(conn)["creees"][0]["operations"][1]
    with pytest.raises(ValueError, match="onglet Emprunts"):
        recurrentes.depuis_operation(conn, oid)


def test_fec_apres_generation_accepte_par_le_validateur(conn, tmp_path):
    _emprunt(conn, assurance="2,50")
    _generer(conn)
    fec = export_fec.exporter(conn, 2026, str(tmp_path / "fec.txt"))
    assert valider_fec.valider(fec) == []


def test_interets_mensuels_generes_pas_annuel_multiple(conn):
    _emprunt(conn)
    _generer(conn)
    codes = {a.code for a in controles.controler(conn, 2026)}
    assert "ANNUEL_MULTIPLE" not in codes


def test_interets_annuels_saisis_deux_fois_toujours_signales(conn):
    for d in ("2026-03-01", "2026-04-01"):
        operations.saisir(conn, type="interets_emprunt", montant=100.0,
                          date_operation=d)
    assert "ANNUEL_MULTIPLE" in {a.code for a in
                                 controles.controler(conn, 2026)}


# ── Contrôles ────────────────────────────────────────────────────────────

def _codes(conn, annee=2026):
    return {a.code: a for a in controles.controler(conn, annee)
            if a.code.startswith("EMPRUNT")}


def test_interets_concordants_aucune_alerte(conn):
    _emprunt(conn)
    _generer(conn)
    assert _codes(conn) == {}


def test_interets_non_generes_ecart_chiffre(conn):
    _emprunt(conn)
    cles = [x.cle for x in _apercu(conn)]
    _generer(conn, retenues=set(cles[:2]))
    a = _codes(conn)["EMPRUNT_INTERETS"]
    assert a.niveau == controles.AVERTISSEMENT
    assert "ne sont pas générées" in a.message and "écart -" in a.message


def test_interets_comptes_deux_fois_ecart_positif(conn):
    _emprunt(conn)
    _generer(conn)
    operations.saisir(conn, type="interets_emprunt", montant=40.0,
                      date_operation="2026-04-30")
    assert "deux fois" in _codes(conn)["EMPRUNT_INTERETS"].message


def test_ecart_sous_le_seuil_de_5_euros_tu(conn):
    _emprunt(conn)
    _generer(conn)
    operations.saisir(conn, type="interets_emprunt", montant=4.99,
                      date_operation="2026-04-30")
    assert _codes(conn) == {}


def test_crd_muet_sans_compte_164000(conn):
    _emprunt(conn)
    assert emprunts.ecart_crd(conn, 2026) is None


def _an_164(conn, montant):
    import ecritures
    ecritures.inserer(conn, journal="AN", date="2026-01-01", annee=2026,
                      libelle="A nouveaux emprunt", piece_ref="AN",
                      lignes=[("108000", montant, 0.0),
                              ("164000", 0.0, montant)])


def _capital_rembourse(conn, montant):
    operations.saisir(conn, type="emprunt_capital_rembourse", montant=montant,
                      date_operation="2026-12-31")


def test_crd_ouverture_et_cloture_concordants(conn):
    _emprunt(conn)
    _an_164(conn, 1200.0)
    _capital_rembourse(conn, 1200.0)
    codes = _codes(conn)
    assert "EMPRUNT_CRD" not in codes and "EMPRUNT_OUVERTURE" not in codes
    r = emprunts.ecart_crd(conn, 2026)
    assert (r["theorique_ouverture"], r["compte_ouverture"]) == (D("1200.00"),
                                                                D("1200.00"))
    assert (r["theorique_fin"], r["compte_fin"]) == (D("0.00"), D("0.00"))


def test_crd_ecart_a_l_ouverture_et_a_la_cloture(conn):
    _emprunt(conn)
    _an_164(conn, 1000.0)
    _capital_rembourse(conn, 800.0)
    codes = _codes(conn)
    assert "écart -200,00" in codes["EMPRUNT_OUVERTURE"].message
    assert "écart 200,00" in codes["EMPRUNT_CRD"].message


def test_emprunt_en_cours_concordance_puis_ecart_avec_les_a_nouveaux(conn):
    eid = _emprunt(conn, capital="10000", nb_echeances=24,
                   date_deblocage="2024-12-01",
                   date_premiere_echeance="2025-01-05")
    crd_ouverture = emprunts.tableau(conn, eid)[11].crd
    _an_164(conn, float(crd_ouverture))
    assert "EMPRUNT_OUVERTURE" not in _codes(conn)
    _an_164(conn, 100.0)
    assert "écart 100,00" in _codes(conn)["EMPRUNT_OUVERTURE"].message


# ── Garantie : un dossier sans emprunt ne voit rien changer ──────────────

def _etat(c, annee, tmp_path, nom):
    fec = export_fec.exporter(c, annee, str(tmp_path / f"{nom}.txt"))
    anos = [(a.niveau, a.code, a.message)
            for a in controles.controler(c, annee)]
    return (repr(liasse.generer(c, annee)), open(fec, "rb").read(), anos)


def _sans_tables_emprunt(chemin):
    c = sqlite3.connect(chemin)
    c.execute("DROP TABLE emprunt_ligne")
    c.execute("DROP TABLE emprunt")
    c.commit()
    c.close()


@pytest.mark.parametrize("source", ["demo", "reference_2025"])
def test_dossier_sans_emprunt_liasse_fec_controles_inchanges(tmp_path, source):
    etats = []
    for nom in ("avec_tables", "sans_tables"):
        chemin = str(tmp_path / f"{nom}.db")
        if source == "demo":
            init_db.init_demo(chemin, FEC_DEMO, 2026).close()
            annee = 2025
        else:
            init_db.init(chemin, "blanc", annee_cible=2025).close()
            c = sqlite3.connect(chemin)
            rejeu_fec.rejouer(c, FEC_REF_2025, 2025)
            c.close()
            annee = 2025
        if nom == "sans_tables":
            _sans_tables_emprunt(chemin)
        c = sqlite3.connect(chemin)
        c.row_factory = None
        try:
            etats.append(_etat(c, annee, tmp_path, nom))
        finally:
            c.close()
    assert etats[0] == etats[1]


def test_sans_emprunt_les_fonctions_se_taisent(conn):
    assert emprunts.lister(conn) == []
    assert emprunts.echeances(conn, *ANNEE) == []
    assert emprunts.ecart_interets(conn, 2026) is None
    assert emprunts.ecart_crd(conn, 2026) is None


def test_base_non_migree_traitee_comme_sans_emprunt(chemin):
    init_db.init_demo(chemin, FEC_DEMO, 2026).close()
    _sans_tables_emprunt(chemin)
    c = sqlite3.connect(chemin)
    try:
        assert emprunts.lister(c) == []
        assert emprunts.echeances(c, *ANNEE) == []
        assert not [a for a in controles.controler(c, 2026)
                    if a.code in ("CONTROLE_IMPOSSIBLE",)
                    or a.code.startswith("EMPRUNT")]
    finally:
        c.close()


# ── Persistance, migration ───────────────────────────────────────────────

def test_survie_a_une_sauvegarde_puis_restauration(chemin, conn):
    eid = _emprunt(conn)
    _generer(conn)
    etat = (conn.execute("SELECT * FROM emprunt").fetchall(),
            conn.execute("SELECT * FROM emprunt_ligne").fetchall(),
            conn.execute("SELECT * FROM echeance_generee").fetchall())
    conn.close()
    sauvegarde = perennite.sauvegarder(chemin, "manuel")
    c = sqlite3.connect(chemin)
    c.execute("DELETE FROM emprunt_ligne WHERE emprunt_id=?", (eid,))
    c.commit()
    c.close()
    perennite.restaurer(chemin, sauvegarde)
    c = sqlite3.connect(chemin)
    try:
        assert (c.execute("SELECT * FROM emprunt").fetchall(),
                c.execute("SELECT * FROM emprunt_ligne").fetchall(),
                c.execute("SELECT * FROM echeance_generee").fetchall()) == etat
    finally:
        c.close()


def test_migration_base_neuve(tmp_path):
    c = init_db.init(str(tmp_path / "neuve.db"), "blanc", annee_cible=2026)
    try:
        assert init_db.version_base(c) == init_db.VERSION_SCHEMA == 11
        for t in ("emprunt", "emprunt_ligne"):
            assert c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
        assert "rang" in {r[1] for r in c.execute(
            "PRAGMA table_info(echeance_generee)")}
    finally:
        c.close()


def _contenu(chemin, exclues):
    c = sqlite3.connect(chemin)
    try:
        tables = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            if r[0] not in exclues]
        return {t: c.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
                for t in tables}
    finally:
        c.close()


def test_migration_depuis_la_version_10_du_dossier_de_demo(tmp_path):
    chemin = str(tmp_path / "compta.db")
    c = init_db.init_demo(chemin, FEC_DEMO, 2026)
    recurrentes.creer(c, type="assurance", bien_id=1, montant=18.5,
                      periodicite="mensuelle", jour=31,
                      date_debut="2026-01-31")
    recurrentes.generer(c, *ANNEE, {"recurrent:1:2026-01-31"},
                        aujourd_hui=MI_MAI)
    c.close()
    # Retour à l'état d'une base au schéma 10.
    c = sqlite3.connect(chemin)
    c.execute("DROP TABLE emprunt_ligne")
    c.execute("DROP TABLE emprunt")
    c.execute("DROP INDEX ux_echeance_rang")
    c.execute("ALTER TABLE echeance_generee DROP COLUMN rang")
    c.execute("UPDATE meta SET valeur='10' WHERE cle='version_schema'")
    c.commit()
    avant_echeances = c.execute("SELECT * FROM echeance_generee").fetchall()
    c.close()
    exclues = {"meta", "echeance_generee", "emprunt", "emprunt_ligne"}
    avant = _contenu(chemin, exclues)

    r = migrations.migrer(chemin)
    assert (r["avant"], r["apres"]) == (10, 11)
    assert r["sauvegarde"] and os.path.exists(r["sauvegarde"])
    assert _contenu(chemin, exclues) == avant
    c = sqlite3.connect(chemin)
    try:
        assert c.execute("SELECT * FROM echeance_generee").fetchall() == \
            [x + (None,) for x in avant_echeances]
        for t in ("emprunt", "emprunt_ligne"):
            assert c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
    finally:
        c.close()
    assert migrations.migrer(chemin)["sauvegarde"] is None


# ── Interface web ────────────────────────────────────────────────────────

def _client(tmp_path, monkeypatch, principal, bac=None):
    monkeypatch.setenv("COMPTA_DB", principal)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", bac or str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    return app_mod.app.test_client(), app_mod


@pytest.fixture()
def web(tmp_path, monkeypatch):
    principal = str(tmp_path / "compta.db")
    init_db.init_demo(principal, FEC_DEMO, 2026).close()
    client, app_mod = _client(tmp_path, monkeypatch, principal)
    yield client, principal
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def _db(chemin):
    c = sqlite3.connect(chemin)
    c.execute("PRAGMA foreign_keys = ON")
    return c


def _form(**kw):
    d = {"annee": "2026", **{k: str(v) for k, v in _champs().items()},
         "assurance": "2,50", "reference": ""}
    d.update(kw)
    return d


def _tbody(page):
    debut = page.index("Capital restant dû avant")
    corps = page[page.index("<tbody>", debut):page.index("</tbody>", debut)]
    return re.sub(r"\s+", " ", corps)


def test_web_pages_sans_emprunt(web):
    client, _ = web
    for url in ("/emprunts?annee=2026", "/immobilisations?annee=2026"):
        r = client.get(url)
        assert r.status_code == 200
    page = client.get("/emprunts?annee=2026").get_data(as_text=True)
    assert "Aucun emprunt décrit" in page and 'href="/emprunts?' in page
    assert "Tableau de remboursement" not in client.get(
        "/immobilisations?annee=2026").get_data(as_text=True)


def test_web_base_non_migree_migree_a_l_ouverture(tmp_path, monkeypatch):
    principal = str(tmp_path / "compta.db")
    init_db.init_demo(principal, FEC_DEMO, 2026).close()
    _sans_tables_emprunt(principal)
    c = sqlite3.connect(principal)
    c.execute("DROP INDEX ux_echeance_rang")
    c.execute("ALTER TABLE echeance_generee DROP COLUMN rang")
    c.execute("UPDATE meta SET valeur='10' WHERE cle='version_schema'")
    c.commit()
    c.close()
    client, _ = _client(tmp_path, monkeypatch, principal)
    for url in ("/emprunts?annee=2026", "/immobilisations?annee=2026"):
        assert client.get(url).status_code == 200


def test_web_creer_puis_memes_montants_dans_les_deux_onglets(web):
    client, principal = web
    r = client.post("/emprunts/creer", data=_form())
    assert "ok=" in r.headers["Location"]
    emprunts_page = client.get("/emprunts?annee=2026").get_data(as_text=True)
    immo = client.get("/immobilisations?annee=2026").get_data(as_text=True)
    assert _tbody(emprunts_page) == _tbody(immo)
    assert "109,10" in _tbody(immo)          # 106,62 + 2,50 d'assurance
    # Lecture seule côté Immobilisations, lien vers l'onglet Emprunts.
    assert "/emprunts/1/ligne" not in immo and "/importer" not in immo
    assert "Modifier dans l" in immo and "/emprunts?annee=2026&emprunt=1" \
        in immo
    assert "Plan d&#39;amortissement du bien" in immo \
        or "Plan d'amortissement du bien" in immo
    assert "Tableau de remboursement de l" in immo
    for texte in ('data-confirmer="Passer en écriture', 'data-confirmer="Remplacer',
                  'data-confirmer="Supprimer cet emprunt'):
        assert texte in emprunts_page
    assert "pas le TAEG" in emprunts_page


def test_web_refus_avec_message(web):
    client, principal = web
    r = client.post("/emprunts/creer", data=_form(taux="35"))
    assert "err=" in r.headers["Location"]
    c = _db(principal)
    assert c.execute("SELECT COUNT(*) FROM emprunt").fetchone()[0] == 0
    c.close()


def test_web_generer_puis_rejeu_puis_verrou_affiche(web):
    client, principal = web
    client.post("/emprunts/creer", data=_form())
    page = client.get("/emprunts?annee=2026").get_data(as_text=True)
    cles = re.findall(r'name="retenir" value="([^"]+)"', page)
    assert len(cles) == 4
    data = {"annee": "2026", "du": "2026-01-01", "au": "2026-12-31",
            "retenir": cles}
    assert "ok=" in client.post("/emprunts/generer",
                                data=data).headers["Location"]
    client.post("/emprunts/generer", data=data)
    c = _db(principal)
    assert c.execute("SELECT COUNT(DISTINCT ecriture_id) FROM operation "
                     "WHERE source='emprunt'").fetchone()[0] == 4
    c.close()
    immo = client.get("/immobilisations?annee=2026").get_data(as_text=True)
    assert immo.count("🔒 écriture n°") == 4


def test_web_remplacer_ligne_et_import_et_export(web):
    client, principal = web
    client.post("/emprunts/creer", data=_form())
    r = client.post("/emprunts/1/ligne", data={
        "annee": "2026", "rang": "1", "date_echeance": "2026-01-31",
        "capital": "0", "interets": "12", "assurance": "2,50"})
    assert "ok=" in r.headers["Location"]
    export = client.get("/emprunts/1/export.csv")
    assert export.status_code == 200 and export.mimetype == "text/csv"
    import io
    r = client.post("/emprunts/1/importer", data={
        "annee": "2026", "tableau": (io.BytesIO(export.data), "t.csv")},
        content_type="multipart/form-data")
    assert "ok=" in r.headers["Location"]
    texte = export.data.decode("utf-8-sig").replace("28/02/2026", "31/02/2026")
    r = client.post("/emprunts/1/importer", data={
        "annee": "2026", "tableau": (io.BytesIO(texte.encode()), "t.csv")},
        content_type="multipart/form-data")
    assert "err=" in r.headers["Location"] and "tableau+inchang" in \
        r.headers["Location"]


def test_web_import_avec_reliquat_accepte_et_signale(web):
    client, principal = web
    client.post("/emprunts/creer", data=_form(assurance=""))
    c = _db(principal)
    contenu = _csv_du_tableau(_tableau_avec_reliquat(c, 1))
    c.close()
    import io
    r = client.post("/emprunts/1/importer", data={
        "annee": "2026", "tableau": (io.BytesIO(contenu), "t.csv")},
        content_type="multipart/form-data")
    assert "ok=" in r.headers["Location"] and "warn=" in r.headers["Location"]
    for url in ("/emprunts?annee=2026", "/immobilisations?annee=2026"):
        assert "100,00 € restent dus" in client.get(url).get_data(as_text=True)


def test_web_ecarter_puis_retablir(web):
    client, principal = web
    client.post("/emprunts/creer", data=_form())
    cle = "emprunt:1:2026-02-28"
    client.post("/emprunts/generer", data={
        "annee": "2026", "du": "2026-01-01", "au": "2026-12-31",
        "ecarter": [cle]})
    page = client.get("/emprunts?annee=2026").get_data(as_text=True)
    assert "écartée" in page and "Rétablir" in page
    r = client.post("/emprunts/retablir", data={"annee": "2026", "cle": cle})
    assert "ok=" in r.headers["Location"]


def test_web_bien_cede_emprunt_toujours_consultable(web):
    client, principal = web
    client.post("/emprunts/creer", data=_form())
    import cession
    c = _db(principal)
    cession.assurer_schema(c)
    c.execute("UPDATE bien SET date_cession='2026-03-15' WHERE id=1")
    c.commit()
    c.close()
    page = client.get("/emprunts?annee=2026").get_data(as_text=True)
    assert "cédé le 2026-03-15" in page and "109,10" in page
    immo = client.get("/immobilisations?annee=2026").get_data(as_text=True)
    assert "Tableau de remboursement de l" in immo


def test_web_origine_etrangere_refusee(web):
    client, principal = web
    r = client.post("/emprunts/creer", data=_form(),
                    headers={"Origin": "https://exemple.invalid"})
    assert r.status_code == 403
    c = _db(principal)
    assert c.execute("SELECT COUNT(*) FROM emprunt").fetchone()[0] == 0
    c.close()


def test_web_annulation_d_une_echeance_le_dit(web):
    client, principal = web
    client.post("/emprunts/creer", data=_form())
    client.post("/emprunts/generer", data={
        "annee": "2026", "du": "2026-01-01", "au": "2026-12-31",
        "retenir": ["emprunt:1:2026-01-31"]})
    c = _db(principal)
    oid = c.execute("SELECT MIN(id) FROM operation WHERE source='emprunt'"
                    ).fetchone()[0]
    c.close()
    r = client.post(f"/operation/{oid}/annuler", data={"annee": "2026"})
    assert "paiement+ventil" in r.headers["Location"]


def test_cloisonnement_du_bac_a_sable(tmp_path, monkeypatch):
    principal, bac = str(tmp_path / "compta.db"), str(tmp_path / "bac.db")
    init_db.init_demo(principal, FEC_DEMO, 2026).close()
    shutil.copy(principal, bac)
    client, _ = _client(tmp_path, monkeypatch, principal, bac)
    client.set_cookie("dossier", "bac_a_sable")
    client.post("/emprunts/creer", data=_form())
    client.post("/emprunts/generer", data={
        "annee": "2026", "du": "2026-01-01", "au": "2026-12-31",
        "retenir": ["emprunt:1:2026-01-31"]})
    for chemin_db, attendu in ((bac, 1), (principal, 0)):
        c = sqlite3.connect(chemin_db)
        assert c.execute("SELECT COUNT(*) FROM emprunt").fetchone()[0] == \
            attendu, chemin_db
        assert c.execute("SELECT COUNT(DISTINCT ecriture_id) FROM operation "
                         "WHERE source='emprunt'").fetchone()[0] == attendu
        c.close()


# ── Ligne de commande ────────────────────────────────────────────────────

def _cli(monkeypatch, chemin, *args):
    import cli
    monkeypatch.setattr(cli, "DB", chemin)
    monkeypatch.setattr(sys, "argv", ["cli.py", *args])
    cli.main()


def test_cli_cycle_complet(chemin, monkeypatch, capsys, tmp_path):
    init_db.init_demo(chemin, FEC_DEMO, 2026).close()
    _cli(monkeypatch, chemin, "emprunt", "creer", "--bien", "1", "--preteur",
         "Banque fictive", "--capital", "1200", "--taux", "12", "--duree",
         "12", "--deblocage", "2025-12-15", "--premiere", "2026-01-31",
         "--assurance", "2,50")
    sortie = capsys.readouterr().out
    assert f"Dossier : {chemin}" in sortie and "Emprunt n° 1 créé" in sortie
    assert "106,62" in sortie and "pas le TAEG" in sortie
    _cli(monkeypatch, chemin, "emprunt", "lister")
    assert "1 200,00 € à 12 % nominal" in capsys.readouterr().out
    _cli(monkeypatch, chemin, "emprunt", "remplacer-ligne", "--id", "1",
         "--rang", "1", "--date", "2026-01-31", "--capital", "0",
         "--interets", "12")
    assert "11 échéance(s) suivante(s) recalculée(s)" in \
        capsys.readouterr().out
    _cli(monkeypatch, chemin, "emprunt", "apercu")
    assert "emprunt:1:2026-04-30" in capsys.readouterr().out
    _cli(monkeypatch, chemin, "emprunt", "generer", "--oui",
         "--exclure", "emprunt:1:2026-04-30")
    assert "3 échéance(s) passée(s) en écriture" in capsys.readouterr().out
    _cli(monkeypatch, chemin, "emprunt", "tableau", "--id", "1")
    assert "🔒" in capsys.readouterr().out
    out = str(tmp_path / "t.csv")
    _cli(monkeypatch, chemin, "emprunt", "exporter", "--id", "1", "--out", out)
    _cli(monkeypatch, chemin, "emprunt", "importer", "--id", "1", "--csv", out)
    assert "12 échéance(s) à partir de la n° 1" in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        _cli(monkeypatch, chemin, "emprunt", "supprimer", "--id", "1", "--oui")
    assert "ne peut plus être supprimé" in str(exc.value.code)


def test_cli_refus_code_de_retour(chemin, monkeypatch):
    init_db.init_demo(chemin, FEC_DEMO, 2026).close()
    with pytest.raises(SystemExit) as exc:
        _cli(monkeypatch, chemin, "emprunt", "creer", "--bien", "1",
             "--preteur", "B", "--capital", "1000", "--taux", "3",
             "--duree", "0", "--deblocage", "2026-01-01",
             "--premiere", "2026-02-01")
    assert "ENTIER" in str(exc.value.code)


def test_cli_generer_sans_confirmation_abandonne(chemin, monkeypatch, capsys):
    c = init_db.init_demo(chemin, FEC_DEMO, 2026)
    _emprunt(c)
    c.close()
    monkeypatch.setattr("builtins.input", lambda _: "n")
    _cli(monkeypatch, chemin, "emprunt", "generer")
    assert "rien n'a été généré" in capsys.readouterr().out
    c = sqlite3.connect(chemin)
    assert c.execute("SELECT COUNT(*) FROM operation WHERE source='emprunt'"
                     ).fetchone()[0] == 0
    c.close()


# ── Catalogue ────────────────────────────────────────────────────────────

def test_libelle_frais_de_garantie_exclut_la_part_restituable():
    import gabarits
    assert "hors part restituable" in \
        gabarits.GABARITS["frais_dossier_emprunt"]["libelle"]
