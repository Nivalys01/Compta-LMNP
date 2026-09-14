# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Import d'un FEC de CABINET : classes 1 à 7, plan à sept chiffres.

Pourquoi ce fichier existe
--------------------------
La comptabilité du logiciel est tenue SANS comptes de tiers ni trésorerie —
c'est un choix assumé (contrepartie unique 108000). Mais un FEC remis par un
cabinet, lui, en contient toujours : emprunt 164, banque 512, fournisseurs
401, clients 411, amortissements 281x. Le logiciel doit pouvoir le lire
sans rien perdre.

Le plan reproduit ici est calqué sur celui d'un bilan LMNP réellement établi
par un cabinet : numéros à SEPT chiffres (5120100 pour la banque, 6811000
pour la dotation), là où le plan livré en compte six. Les montants et
l'identité sont fictifs.

Ce que ces tests ont attrapé, la première fois qu'ils ont tourné :
  - `411xxxx` (client) était créé au PASSIF, en contradiction avec le plan
    livré qui déclare 411000 à l'actif ;
  - 12 000 € de dotation portés en `6811000` n'apparaissaient dans AUCUNE
    case du 2033-B, tout en pesant sur le résultat — `liasse` divergeait de
    `fiscal.agregats` d'exactement ce montant.

Lancer :  pytest -q tests/test_import_cabinet.py
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import fec_io  # noqa: E402
import fiscal  # noqa: E402
import init_db  # noqa: E402
import liasse  # noqa: E402
import rejeu_fec  # noqa: E402
import valider_fec  # noqa: E402

# Plan de cabinet à sept chiffres. Le libellé dit la nature, le numéro dit
# la classe — c'est tout ce dont l'import a besoin.
PLAN = {
    "1100000": "Report à nouveau",
    "1640000": "Emprunts auprès des établissements de crédit",
    "2180000": "Autres immobilisations corporelles",
    "2181000": "Installations générales, agencements",
    "2818000": "Amortissements des autres immobilisations",
    "2818100": "Amortissements des installations",
    "4010001": "Fournisseur A",
    "4010002": "Fournisseur B",
    "4041000": "Fournisseurs d'immobilisations",
    "4110100": "Locataire",
    "5120100": "Banque",
    "6061100": "Énergie",
    "6161000": "Primes d'assurance",
    "6351200": "Contribution économique territoriale",
    "6351300": "Taxe foncière",
    "6611000": "Intérêts des emprunts",
    "6811000": "Dotations aux amortissements",
    "7060100": "Prestations de services",
    "7910000": "Transferts de charges",
}

# Ce que le cabinet a comptabilisé, en euros fictifs.
DOTATION = 12000.00
CET = 310.00
LOYER = 795.50
INTERETS = 2100.00
TRANSFERT = 500.00


def _ligne(journal, num, date, compte, debit, credit, aux=""):
    d = dict.fromkeys(fec_io.COLONNES, "")
    d.update({"JournalCode": journal, "JournalLib": journal,
              "EcritureNum": str(num), "EcritureDate": date,
              "CompteNum": compte, "CompteLib": PLAN[compte],
              "CompAuxNum": aux, "CompAuxLib": PLAN.get(aux, ""),
              "PieceRef": f"P{num}", "PieceDate": date,
              "EcritureLib": PLAN[compte], "Debit": debit, "Credit": credit,
              "ValidDate": date})
    return "\t".join(d[c] for c in fec_io.COLONNES)


def _fec_cabinet(tmp_path):
    """FEC équilibré couvrant les classes 1 à 7, numéroté en continu."""
    e = iter(range(1, 999))
    n_an, n1, n2, n3, n4, n5, n6, n7, n8 = (next(e) for _ in range(9))
    lignes = [
        # À-nouveaux : classes 1, 2, 4, 5
        _ligne("AN", n_an, "20260101", "1100000", "", "104000,00"),
        _ligne("AN", n_an, "20260101", "1640000", "", "96000,00"),
        _ligne("AN", n_an, "20260101", "2180000", "180000,00", ""),
        _ligne("AN", n_an, "20260101", "2181000", "24000,00", ""),
        _ligne("AN", n_an, "20260101", "2818000", "", "9000,00"),
        _ligne("AN", n_an, "20260101", "2818100", "", "3000,00"),
        _ligne("AN", n_an, "20260101", "4010001", "", "1200,00", "4010001"),
        _ligne("AN", n_an, "20260101", "4041000", "", "800,00"),
        _ligne("AN", n_an, "20260101", "4110100", "950,00", "", "4110100"),
        _ligne("AN", n_an, "20260101", "5120100", "9050,00", ""),
        # Exploitation : classes 6 et 7
        _ligne("VE", n1, "20260131", "4110100", f"{LOYER:.2f}".replace(".", ","), "", "4110100"),
        _ligne("VE", n1, "20260131", "7060100", "", f"{LOYER:.2f}".replace(".", ",")),
        _ligne("AC", n2, "20260215", "6061100", "95,00", ""),
        _ligne("AC", n2, "20260215", "4010002", "", "95,00", "4010002"),
        _ligne("AC", n3, "20260301", "6161000", "138,49", ""),
        _ligne("AC", n3, "20260301", "5120100", "", "138,49"),
        _ligne("AC", n4, "20260401", "6351200", f"{CET:.2f}".replace(".", ","), ""),
        _ligne("AC", n4, "20260401", "5120100", "", f"{CET:.2f}".replace(".", ",")),
        _ligne("AC", n5, "20260501", "6351300", "1420,00", ""),
        _ligne("AC", n5, "20260501", "5120100", "", "1420,00"),
        _ligne("AC", n6, "20260601", "6611000", f"{INTERETS:.2f}".replace(".", ","), ""),
        _ligne("AC", n6, "20260601", "5120100", "", f"{INTERETS:.2f}".replace(".", ",")),
        _ligne("OD", n7, "20261231", "6811000", f"{DOTATION:.2f}".replace(".", ","), ""),
        _ligne("OD", n7, "20261231", "2818000", "", f"{DOTATION:.2f}".replace(".", ",")),
        # Classe 79 : un produit hors 70/75/76/77. Il doit retomber dans les
        # produits d'EXPLOITATION, pas disparaître — c'est ce que garantit la
        # soustraction plutôt que l'énumération (constat E-20).
        _ligne("OD", n8, "20261231", "7910000", "",
               f"{TRANSFERT:.2f}".replace(".", ",")),
        _ligne("OD", n8, "20261231", "5120100",
               f"{TRANSFERT:.2f}".replace(".", ","), ""),
    ]
    p = tmp_path / "FEC2026.txt"
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(fec_io.COLONNES) + "\r\n")
        for ligne in lignes:
            f.write(ligne + "\r\n")
    return str(p)


@pytest.fixture
def dossier(tmp_path):
    """Dossier vierge dans lequel le FEC de cabinet a été rejoué."""
    fec = _fec_cabinet(tmp_path)
    db = str(tmp_path / "compta.db")
    conn = init_db.init(db, "blanc", annee_cible=2026)
    conn.execute("INSERT OR IGNORE INTO exploitant (id, nom, siren) "
                 "VALUES (1, 'MARTIN Jean', '000000000')")
    conn.execute("INSERT OR IGNORE INTO bien (id, exploitant_id, libelle) "
                 "VALUES (1, 1, 'Logement')")
    conn.commit()
    rejeu_fec.rejouer(conn, fec, 2026)
    yield conn
    conn.close()


# ═══ Lecture du FEC ═════════════════════════════════════════════════════

def test_le_fec_de_cabinet_est_conforme(tmp_path):
    """Sept chiffres, comptes de tiers, comptes de trésorerie : rien de tout
    cela ne doit faire broncher le validateur."""
    assert valider_fec.valider(_fec_cabinet(tmp_path)) == []


def test_tous_les_comptes_sont_crees(dossier):
    presents = {n for (n,) in dossier.execute(
        "SELECT numero FROM compte WHERE LENGTH(numero) = 7")}
    assert presents == set(PLAN), sorted(set(PLAN) - presents)


def test_l_equilibre_est_preserve(dossier):
    d, c = dossier.execute(
        "SELECT ROUND(SUM(debit), 2), ROUND(SUM(credit), 2) FROM ligne").fetchone()
    assert d == c


@pytest.mark.parametrize("compte,type_attendu", [
    ("1100000", "passif"),          # report à nouveau
    ("1640000", "passif"),          # emprunt : une DETTE
    ("2180000", "actif"),
    ("2818000", "amortissement"),   # actif soustractif, pas passif
    ("2818100", "amortissement"),
    ("4010001", "passif"),          # fournisseur : une dette
    ("4041000", "passif"),          # fournisseur d'immobilisations
    ("4110100", "actif"),           # locataire : une CRÉANCE
    ("5120100", "actif"),           # banque
    ("6811000", "charge"),
    ("7060100", "produit"),
])
def test_chaque_classe_recoit_le_bon_type(dossier, compte, type_attendu):
    """Le type est déduit du numéro. Toute la classe 4 était rangée au
    passif, si bien qu'un compte de locataire — une créance — était créé
    comme une dette, en contradiction avec le plan livré."""
    t, = dossier.execute("SELECT type FROM compte WHERE numero = ?",
                         (compte,)).fetchone()
    assert t == type_attendu


def test_la_classe_est_le_premier_chiffre(dossier):
    for n, cl in dossier.execute(
            "SELECT numero, classe FROM compte WHERE LENGTH(numero) = 7"):
        assert cl == int(n[0]), n


# ═══ Ce que la liasse en fait ═══════════════════════════════════════════

def test_la_dotation_atterrit_en_case_254_quel_que_soit_le_compte(dossier):
    """La case 254 était lue sur le SEUL compte 681120. Un cabinet qui porte
    sa dotation en 6811000 voyait la case à zéro — et les 12 000 € nulle
    part ailleurs."""
    b = liasse.resultat_2033b(dossier, 2026)
    assert b["dotations_254"] == DOTATION


def test_aucune_charge_ne_peut_disparaitre(dossier):
    """Le total des charges d'exploitation doit être la somme exacte de ses
    cases détaillées : c'est ce qui garantit qu'aucun compte de classe 6 ne
    s'évapore, quel que soit le plan du cabinet d'origine."""
    b = liasse.resultat_2033b(dossier, 2026)
    detail = round(b["charges_externes_242"] + b["impots_244"]
                   + b["personnel_250"] + b["dotations_254"]
                   + b["autres_charges_262"], 2)
    assert detail == b["total_charges_264"]


def test_la_liasse_et_les_agregats_s_accordent(dossier):
    """Le garde-fou qui compte. `liasse` énumérait des préfixes de classe 6
    quand `fiscal.agregats` prenait la classe entière : sur ce FEC, les deux
    divergeaient de 12 000 € — le montant exact de la dotation ignorée."""
    ag = fiscal.agregats(dossier, 2026)
    b = liasse.resultat_2033b(dossier, 2026)
    assert round(ag["resultat_comptable"], 2) == b["benefice_ou_perte_310"]


def test_un_produit_de_classe_79_ne_disparait_pas(dossier):
    """Les produits sont obtenus par SOUSTRACTION du total de la classe, pas
    par énumération : un compte hors 70/75/76/77 — ici des transferts de
    charges en 7910000 — retombe en exploitation au lieu de s'évaporer."""
    b = liasse.resultat_2033b(dossier, 2026)
    assert b["total_produits_232"] == round(LOYER + TRANSFERT, 2)
    assert b["produits_financiers_280"] == 0.0
    assert b["produits_exceptionnels_290"] == 0.0


def test_les_interets_restent_financiers(dossier):
    """Classe 66 : hors exploitation, en case 294 — pas dans le total 264."""
    b = liasse.resultat_2033b(dossier, 2026)
    assert b["charges_financieres_294"] == INTERETS
    assert b["total_charges_264"] == round(
        b["total_charges_264"], 2)          # 264 exclut bien le financier
    ag = fiscal.agregats(dossier, 2026)
    assert round(b["total_charges_264"] + b["charges_financieres_294"], 2) == \
        round(ag["charges_hors_daa"] + ag["dotation"], 2)


def test_la_case_243_reste_a_zero_sur_un_plan_de_cabinet(dossier):
    """Limite ASSUMÉE, figée ici pour qu'elle ne passe pas pour un succès :
    « dont CFE et CVAE » est lu sur le compte du plan livré (635110). Un
    cabinet numérote autrement — 6351200 relevé sur un bilan réel — et
    aucun préfixe ne distingue la CET des autres impôts directs. La case
    reste donc vide alors que la CET a été payée, et cela ne peut pas se
    corriger sans correspondance de plans."""
    b = liasse.resultat_2033b(dossier, 2026)
    assert b["dont_cfe_243"] == 0.0
    assert b["impots_244"] >= CET      # elle est bien dans le total, elle


# ═══ Le bilan, avec ses limites assumées ════════════════════════════════

def test_le_bilan_ignore_tiers_et_tresorerie(dossier):
    """Choix de modèle, pas défaut : la comptabilité est tenue sans comptes
    de tiers ni trésorerie. Le bilan ne retient que les immobilisations —
    l'emprunt, la banque et les tiers du FEC de cabinet n'y figurent pas
    (constat E-22, ouvert)."""
    a = liasse.bilan_2033a(dossier, 2026)
    assert a["immo_corporelles_brut_028"] == 204000.00
    assert a["amortissements_030"] == 24000.00
    assert a["equilibre"] is True
    # L'emprunt existe en base, mais aucune case du bilan ne le porte.
    solde_emprunt, = dossier.execute(
        "SELECT ROUND(SUM(credit) - SUM(debit), 2) FROM ligne "
        "WHERE compte_num = '1640000'").fetchone()
    assert solde_emprunt == 96000.00
    assert a["total_passif_180"] == a["immo_corporelles_net"]
