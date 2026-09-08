# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
TEST EN OR — reproduction des liasses réelles de référence 2023-2025.

Les trois exercices réels sont rejoués en chaîne depuis leurs FEC (ceux-là
mêmes qui ont servi aux déclarations), avec pour seule donnée externe l'état
des reports au 01/01/2023. Le moteur doit alors retrouver, à l'euro près,
CHAQUE grandeur des liasses réellement télétransmises et acceptées par
l'administration : résultat comptable, mouvement 39 C, résultat fiscal,
revenu imposable, année par année, et l'état final des reports.

C'est la non-régression fiscale suprême : si une modification du moteur
fait dévier un seul de ces montants, ce test hurle.

Divergence historique corrigée grâce à ce test (v7.5.0) : le plafond 39 C
se calcule sur les charges AFFÉRENTES AU BIEN (art. 39 C, II-2), donc hors
honoraires comptables et CFE, et majoré des réintégrations de charges non
déductibles (fonds travaux ALUR) — l'ancienne formule prenait toutes les
charges et faussait le résultat fiscal (0 au lieu de -630 en 2025).

Lancer :  pytest -q tests/test_or_liasses_reelles.py
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import fiscal
import init_db
import rejeu_fec

FEC = {a: os.path.join(HERE, "reference", f"FEC_REFERENCE_{a}.txt")
       for a in (2023, 2024, 2025)}
RETRAITEMENTS = {2023: 26, 2024: 57, 2025: 61}   # fonds travaux ALUR (liasses)

# Cibles = liasses de référence réellement déclarées (historique § 1.4 + SUIV39C).
CIBLES = {
    #        rés. comptable, mouvement 39C, rés. fiscal, revenu imposable
    2023: {"rc": 1426, "m39": -723, "rf": 729, "ri": 0},
    2024: {"rc": -975, "m39": 297, "rf": -621, "ri": 0},
    2025: {"rc": -949, "m39": 258, "rf": -630, "ri": 0},
}


@pytest.fixture(scope="module")
def resultats(tmp_path_factory):
    db = str(tmp_path_factory.mktemp("or") / "chaine.db")
    conn = init_db.init(db, "blanc", annee_cible=2023)
    # Seule donnée externe : les reports au 01/01/2023 (historique liasse).
    conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, statut) "
                 "VALUES (2022,'2022-01-01','2022-12-31','clos')")
    conn.execute("INSERT INTO suivi_39c (exercice_annee, stock_cloture) "
                 "VALUES (2022, 723)")
    for origine, initial in ((2021, 12249), (2022, 249)):
        conn.execute("INSERT INTO deficit_lmnp (annee_origine, montant_initial,"
                     " solde, annee_expiration) VALUES (?,?,?,?)",
                     (origine, initial, initial, origine + 10))
    conn.commit()
    res = {}
    for annee in (2023, 2024, 2025):
        if annee > 2023:
            conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, "
                         "statut) VALUES (?,?,?,'ouvert')",
                         (annee, f"{annee}-01-01", f"{annee}-12-31"))
            conn.commit()
        rejeu_fec.rejouer(conn, FEC[annee], annee)
        res[annee] = fiscal.cloturer(conn, annee, generer_dotation=False,
                                     autres_retraitements=RETRAITEMENTS[annee])
    res["deficits_finaux"] = dict(conn.execute(
        "SELECT annee_origine, ROUND(solde) FROM deficit_lmnp WHERE solde>0"))
    conn.close()
    return res


@pytest.mark.parametrize("annee", [2023, 2024, 2025])
def test_annee_reproduite_a_l_euro(resultats, annee):
    r, c = resultats[annee], CIBLES[annee]
    s39 = r["suivi_39c"]
    assert abs(r["agregats"]["resultat_comptable"] - c["rc"]) <= 1
    assert abs((s39["report_annee"] - s39["utilisation_annee"]) - c["m39"]) <= 1
    assert abs(r["resultat_fiscal"] - c["rf"]) <= 1
    assert abs(r["revenu_imposable"] - c["ri"]) <= 1


def test_reports_finaux_au_31_12_2025(resultats):
    s = resultats[2025]["suivi_39c"]
    assert abs(s["stock_cloture"] - 556) <= 1          # 555,45 en centimes
    deficits = resultats["deficits_finaux"]
    assert deficits == {2021: 11520, 2022: 249, 2024: 621, 2025: 630}
    total = sum(deficits.values())
    assert abs(total - 13020) <= 1
    assert abs(s["stock_cloture"] + total - 13575) <= 1   # page 1 de la liasse


def test_imputation_2023_sur_deficit_2021(resultats):
    """Le bénéfice 2023 (729) s'impute sur le déficit 2021 (FIFO) : c'est
    exactement le mécanisme visible dans l'historique les acteurs payants actuels (12 249 → 11 520)."""
    assert abs(resultats[2023]["deficits"]["impute_sur_benefice"] - 729) <= 1
    assert resultats["deficits_finaux"][2021] == 11520


# === Convention de prorata — verrouillée sur la liasse réelle 2025 =========
#
# L'audit externe signalait un prorata au MOIS (risque de redressement).
# Vérification empirique contre la liasse 2025 réellement déclarée : la
# convention effective est le prorata en JOURS RÉELS (base 365, jour de mise
# en service inclus). Le prorata au mois se trompait de 2 à 6 € sur les
# acquisitions en cours de mois. Ces cumuls sont ceux du tableau
# « Immobilisations et amortissements » de la liasse (colonne Début 2025).

COMPOSANTS_LIASSE_2025 = [
    ("Gros oeuvre", 58500, 55, "2021-11-01", 3368),
    ("Aménagements intérieurs", 29905, 25, "2021-11-01", 3788),
    ("Etanchéité", 19995, 25, "2021-11-01", 2533),
    ("Installation électrique", 1666, 20, "2021-11-01", 264),
    ("Travaux - Carrelage", 1467, 20, "2021-11-01", 232),
    ("Electroménager - MDA", 1558, 5, "2021-11-01", 987),
    ("Cuisine équipée", 3301, 10, "2021-11-01", 1045),
    ("Mobilier chambres", 2518, 5, "2021-11-01", 1594),
    ("Mobilier Salon", 1923, 5, "2021-11-01", 1218),
    ("Huisseries coté Est", 2005, 25, "2022-03-11", 225),
    ("Huisseries coté OUEST", 6586, 25, "2022-05-25", 686),
    ("Porte d'entrée", 1885, 20, "2022-10-26", 206),
]


@pytest.mark.parametrize("libelle,brute,duree,mes,cumul_declare",
                         COMPOSANTS_LIASSE_2025)
def test_cumul_amortissement_conforme_liasse(libelle, brute, duree, mes,
                                             cumul_declare):
    import amortissement
    _dot, cumul, _vnc = amortissement.etat(brute, duree, mes, 2024)
    assert abs(round(cumul) - cumul_declare) <= 1, (
        f"{libelle}: moteur {cumul:.2f} vs liasse déclarée {cumul_declare}")


def test_prorata_en_jours_pas_en_mois():
    """Garde explicite : une entrée en fin de mois ne doit PAS donner un mois
    entier d'amortissement (surévaluation redressable)."""
    import amortissement
    fin_de_mois = amortissement.fraction_prorata("2026-12-28")   # 4 jours
    assert float(fin_de_mois) < 0.02
    assert float(amortissement.fraction_prorata("2026-01-01")) == 1.0
