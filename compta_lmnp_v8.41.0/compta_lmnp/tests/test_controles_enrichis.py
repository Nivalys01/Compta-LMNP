# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Seconde salve de contrôles (6 → 19) : structurels bloquants, plausibilité
vs N-1, périodicité, cohérence fiscale, rappels de charges attendues.
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import pytest

import audit_cycle
import controles
import fiscal
import init_db
import operations
import parametres
import reprise

ANNEE = date.today().year


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init(str(tmp_path / "t.db"), "blanc", annee_cible=ANNEE)
    audit_cycle._creer_dossier(c, ANNEE)
    yield c
    c.close()


def codes(conn, annee):
    return {a.code for a in controles.controler(conn, annee)}


# ── Structurels bloquants ────────────────────────────────────────────────────

def test_date_hors_exercice_bloquant(conn):
    cur = conn.cursor()
    cur.execute("INSERT INTO ecriture (journal_code,ecriture_num,ecriture_date,"
                "exercice_annee,piece_ref,piece_date,libelle,valid_date) "
                "VALUES ('OD',900,?,?,'X',?,'hors bornes',?)",
                (f"{ANNEE+1}-02-01", ANNEE, f"{ANNEE+1}-02-01", f"{ANNEE+1}-02-01"))
    eid = cur.lastrowid
    cur.execute("INSERT INTO ligne (ecriture_id,compte_num,libelle,debit) "
                "VALUES (?,'628800','x',10)", (eid,))
    cur.execute("INSERT INTO ligne (ecriture_id,compte_num,libelle,credit) "
                "VALUES (?,'108000','x',10)", (eid,))
    conn.commit()
    anos = controles.controler(conn, ANNEE)
    assert any(a.code == "DATE_HORS_EXERCICE" and a.niveau == "BLOQUANT"
               for a in anos)


def test_compte_attente_non_solde_bloquant(conn):
    cur = conn.cursor()
    cur.execute("INSERT INTO ecriture (journal_code,ecriture_num,ecriture_date,"
                "exercice_annee,piece_ref,piece_date,libelle,valid_date) "
                "VALUES ('OD',901,?,?,'X',?,'attente',?)",
                (f"{ANNEE}-06-01", ANNEE, f"{ANNEE}-06-01", f"{ANNEE}-06-01"))
    eid = cur.lastrowid
    cur.execute("INSERT INTO ligne (ecriture_id,compte_num,libelle,debit) "
                "VALUES (?,'472000','x',100)", (eid,))
    cur.execute("INSERT INTO ligne (ecriture_id,compte_num,libelle,credit) "
                "VALUES (?,'108000','x',100)", (eid,))
    conn.commit()
    anos = controles.controler(conn, ANNEE)
    assert any(a.code == "COMPTE_ATTENTE" and a.niveau == "BLOQUANT" for a in anos)


def test_montant_invalide_bloquant(conn):
    conn.execute("INSERT INTO operation (exercice_annee,type,bien_id,"
                 "date_operation,montant,source) VALUES (?,?,1,?,0,'import')",
                 (ANNEE, "charge_copro", f"{ANNEE}-03-01"))
    conn.commit()
    assert "MONTANT_INVALIDE" in codes(conn, ANNEE)


# ── Plausibilité & périodicité ───────────────────────────────────────────────

def _exercice_complet(conn, annee, loyer=800.0, extra=()):
    audit_cycle._saisir_annee(conn, annee, loyer, list(extra))


def test_plausibilite_n1_detecte_les_ecarts(conn):
    _exercice_complet(conn, ANNEE,
                      extra=[("charge_copro", 500.0, "03")])
    fiscal.cloturer(conn, ANNEE)
    reprise.ouvrir_exercice(conn, ANNEE + 1)
    _exercice_complet(conn, ANNEE + 1,
                      extra=[("charge_copro", 1900.0, "03")])  # ×3,8
    anos = controles.controler(conn, ANNEE + 1)
    assert any(a.code == "PLAUSIBILITE_N1" and "charge_copro" in a.message
               for a in anos)


def test_plausibilite_muette_si_n1_migre_sans_operations(conn, tmp_path):
    demo = init_db.init(str(tmp_path / "d.db"), "demo", annee_cible=2026)
    # Cas visé : un exercice N-1 REPRIS (écritures présentes) mais dont les
    # opérations de saisie n'existent pas — typiquement une migration
    # depuis un autre logiciel. La démo en fournit désormais, on les retire
    # pour retrouver exactement cette situation.
    demo.execute("DELETE FROM operation WHERE exercice_annee=2025")
    demo.commit()
    for m in range(1, 13):
        operations.saisir(demo, type="loyer", montant=795,
                          date_operation=f"2026-{m:02d}-05", periode=f"2026-{m:02d}")
    assert not any(a.code == "PLAUSIBILITE_N1"
                   for a in controles.controler(demo, 2026))
    demo.close()


def test_loyer_atypique(conn):
    for m in range(1, 13):
        montant = 80.0 if m == 7 else 800.0        # faute de frappe en juillet
        operations.saisir(conn, type="loyer", montant=montant,
                          date_operation=f"{ANNEE}-{m:02d}-05",
                          periode=f"{ANNEE}-{m:02d}")
    anos = controles.controler(conn, ANNEE)
    assert any(a.code == "LOYER_ATYPIQUE" and f"{ANNEE}-07" in a.message
               for a in anos)


def test_annuel_multiple(conn):
    for j in ("10", "20"):
        operations.saisir(conn, type="cfe", montant=341.0,
                          date_operation=f"{ANNEE}-12-{j}", periode=f"{ANNEE}-12")
    assert "ANNUEL_MULTIPLE" in codes(conn, ANNEE)


def test_periode_incoherente(conn):
    operations.saisir(conn, type="charge_copro", montant=100.0,
                      date_operation=f"{ANNEE}-04-15", periode=f"{ANNEE}-01")
    assert "PERIODE_INCOHERENTE" in codes(conn, ANNEE)


# ── Cohérence fiscale ────────────────────────────────────────────────────────

def test_an_absents_apres_cloture_precedente(conn):
    _exercice_complet(conn, ANNEE)
    fiscal.cloturer(conn, ANNEE)
    reprise.ouvrir_exercice(conn, ANNEE + 1, avec_reprise=False)
    assert "AN_ABSENTS" in codes(conn, ANNEE + 1)
    reprise.construire_an_interne(conn, ANNEE + 1)
    assert "AN_ABSENTS" not in codes(conn, ANNEE + 1)


def test_dotation_vs_plan(conn):
    _exercice_complet(conn, ANNEE)
    fiscal.cloturer(conn, ANNEE)                    # dotation conforme
    assert "DOTATION_PLAN" not in codes(conn, ANNEE)
    # Dotation parasite → écart signalé.
    cur = conn.cursor()
    cur.execute("INSERT INTO ecriture (journal_code,ecriture_num,ecriture_date,"
                "exercice_annee,piece_ref,piece_date,libelle,valid_date) "
                "VALUES ('OD',902,?,?,'X',?,'double dotation',?)",
                (f"{ANNEE}-12-31", ANNEE, f"{ANNEE}-12-31", f"{ANNEE}-12-31"))
    eid = cur.lastrowid
    cur.execute("INSERT INTO ligne (ecriture_id,compte_num,libelle,debit) "
                "VALUES (?,'681120','x',500)", (eid,))
    cur.execute("INSERT INTO ligne (ecriture_id,compte_num,libelle,credit) "
                "VALUES (?,'281315','x',500)", (eid,))
    conn.commit()
    assert "DOTATION_PLAN" in codes(conn, ANNEE)


def test_seuil_lmp_versionne(conn):
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=2000.0,   # CA 24 000
                          date_operation=f"{ANNEE}-{m:02d}-05",
                          periode=f"{ANNEE}-{m:02d}")
    assert "SEUIL_LMP" in codes(conn, ANNEE)
    parametres.definir(conn, "seuil_lmp_recettes", 30000.0, f"{ANNEE}-01-01")
    assert "SEUIL_LMP" not in codes(conn, ANNEE)    # règle du millésime


def test_interets_mal_classes(conn):
    operations.saisir(conn, type="frais_bancaires", montant=1159.02,
                      date_operation=f"{ANNEE}-12-28", periode=f"{ANNEE}-12",
                      libelle="Intérêts année 2024 et échéances")
    anos = controles.controler(conn, ANNEE)
    assert any(a.code == "INTERETS_MAL_CLASSES" and "661100" in a.message
               for a in anos)
    # Le gabarit dédié, lui, ne déclenche rien.
    operations.saisir(conn, type="interets_emprunt", montant=1106.0,
                      date_operation=f"{ANNEE}-12-01", periode=f"{ANNEE}-12",
                      libelle="Intérêts emprunt année")
    n = sum(1 for a in controles.controler(conn, ANNEE)
            if a.code == "INTERETS_MAL_CLASSES")
    assert n == 1


# ── Rappels (INFO) ───────────────────────────────────────────────────────────

def test_charges_attendues_absentes(conn):
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=800.0,
                          date_operation=f"{ANNEE}-{m:02d}-05",
                          periode=f"{ANNEE}-{m:02d}")
    infos = [a for a in controles.controler(conn, ANNEE)
             if a.code == "CHARGE_ATTENDUE"]
    assert len(infos) == 3 and all(a.niveau == "INFO" for a in infos)
    operations.saisir(conn, type="taxe_fonciere", montant=1162,
                      date_operation=f"{ANNEE}-10-15", periode=f"{ANNEE}-10")
    operations.saisir(conn, type="cfe", montant=341,
                      date_operation=f"{ANNEE}-12-15", periode=f"{ANNEE}-12")
    operations.saisir(conn, type="assurance_gli", montant=190,
                      date_operation=f"{ANNEE}-01-10", periode=f"{ANNEE}-01")
    assert "CHARGE_ATTENDUE" not in codes(conn, ANNEE)


def test_alur_absent_apres_annee_avec_alur(conn):
    operations.saisir_appel_charges(conn, date_operation=f"{ANNEE}-01-15",
                                    charges_courantes=484.50, fonds_alur=15.25)
    audit_cycle._saisir_annee(conn, ANNEE, 800.0, [])
    fiscal.cloturer(conn, ANNEE)
    reprise.ouvrir_exercice(conn, ANNEE + 1)
    operations.saisir_appel_charges(conn, date_operation=f"{ANNEE+1}-01-15",
                                    charges_courantes=484.50)   # ALUR oublié
    assert "ALUR_ABSENT" in codes(conn, ANNEE + 1)


# ── Import bancaire : suggestion par historique ──────────────────────────────

def test_import_suggere_le_type_de_l_historique(conn):
    """Un libellé déjà saisi reprend son type — même si les mots-clés
    génériques auraient conclu autrement."""
    import import_bancaire
    # Historique : « PRLV SEPA ENGIE » validé deux fois en énergie.
    for m in ("02", "05"):
        operations.saisir(conn, type="energie", montant=45.0,
                          date_operation=f"{ANNEE}-{m}-10", periode=f"{ANNEE}-{m}",
                          libelle="PRLV SEPA ENGIE")
    # Sans historique, aucun mot-clé ne matche → autres_charges.
    assert import_bancaire.categoriser("PRLV SEPA ENGIE", -45.0) == "autres_charges"
    # Avec l'historique, la suggestion suit les saisies validées.
    assert import_bancaire.categoriser("PRLV SEPA ENGIE", -45.0, conn) == "energie"
    assert import_bancaire.categoriser("prlv sepa engie ", -45.0, conn) == "energie"


def test_import_historique_ignore_les_fourre_tout(conn):
    """Un libellé historiquement en autres_charges ne fait pas suggestion :
    le comportement prudent (à requalifier) est conservé."""
    import import_bancaire
    operations.saisir(conn, type="autres_charges", montant=33.0,
                      date_operation=f"{ANNEE}-03-10", periode=f"{ANNEE}-03",
                      libelle="PRLV MYSTERE")
    assert import_bancaire.suggerer_depuis_historique(conn, "PRLV MYSTERE") is None
    assert import_bancaire.categoriser("PRLV MYSTERE", -33.0, conn) == "autres_charges"
