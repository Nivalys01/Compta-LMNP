# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Réglementation future-proof : règles fiscales versionnées par date d'effet,
gabarits personnalisés en base, réintégration ALUR automatique, inventaire
des gabarits (articles 2023-2025 + charges déductibles LMNP).
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
import gabarits
import init_db
import liasse
import operations
import parametres

ANNEE = date.today().year


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init(str(tmp_path / "t.db"), "blanc", annee_cible=ANNEE)
    yield c
    c.close()


# ── Règles fiscales versionnées ─────────────────────────────────────────────

def test_regles_par_defaut_presentes(conn):
    assert parametres.valeur(conn, "seuil_immobilisation", ANNEE) == 500.0
    assert parametres.valeur(conn, "duree_report_deficit_lmnp", ANNEE) == 10
    assert parametres.valeur(conn, "seuil_lmp_recettes", ANNEE) == 23000.0
    assert parametres.valeur(conn, "retraitement_alur_auto", ANNEE) == 1


def test_nouvelle_version_respecte_les_millesimes(conn):
    parametres.definir(conn, "seuil_immobilisation", 800.0,
                       f"{ANNEE+1}-01-01", reference="LF test")
    assert parametres.valeur(conn, "seuil_immobilisation", ANNEE) == 500.0
    assert parametres.valeur(conn, "seuil_immobilisation", ANNEE + 1) == 800.0
    assert parametres.valeur(conn, "seuil_immobilisation", ANNEE + 5) == 800.0
    # L'ancienne version est close la veille de la date d'effet.
    h = [r for r in parametres.historique(conn)
         if r["cle"] == "seuil_immobilisation"]
    assert h[0]["date_fin"] == f"{ANNEE}-12-31"


def test_controle_immobilisable_suit_la_regle(conn):
    audit_cycle._creer_dossier(conn, ANNEE)
    operations.saisir(conn, type="petit_equipement", montant=650.0,
                      date_operation=f"{ANNEE}-05-10", periode=f"{ANNEE}-05")
    assert any(a.code == "IMMOBILISABLE"
               for a in controles.controler(conn, ANNEE))       # 650 > 500
    parametres.definir(conn, "seuil_immobilisation", 700.0, f"{ANNEE}-01-01")
    assert not any(a.code == "IMMOBILISABLE"
                   for a in controles.controler(conn, ANNEE))   # 650 < 700


def test_duree_report_deficit_versionnee(conn):
    parametres.definir(conn, "duree_report_deficit_lmnp", 6, f"{ANNEE}-01-01")
    audit_cycle._creer_dossier(conn, ANNEE)
    fiscal.cloturer(conn, ANNEE, autres_retraitements=-100.0)   # force un déficit
    exp = conn.execute("SELECT annee_expiration FROM deficit_lmnp "
                       "WHERE annee_origine=?", (ANNEE,)).fetchone()[0]
    assert exp == ANNEE + 6


# ── Gabarits ─────────────────────────────────────────────────────────────────

def test_inventaire_couvre_les_articles_historiques():
    """Chaque article constaté dans les exercices 2023-2025 a son gabarit."""
    attendus = ["loyer", "charges_locatives", "forfait_charges", "charge_copro",
                "fonds_travaux_alur", "energie", "telecom", "assurance",
                "assurance_emprunteur", "maintenance", "petit_equipement",
                "electromenager", "autres_equipements", "honoraires",
                "frais_bancaires", "interets_emprunt", "carburant",
                "peage_parking", "cfe", "taxe_fonciere", "teom",
                "autres_charges"]
    for cle in attendus:
        assert cle in gabarits.GABARITS, cle
    # 36 depuis la v8.11.0 : le gabarit « Adhésion OGA / CGA » a été retiré,
    # la majoration pour non-adhésion ayant été supprimée à compter de 2025.
    assert len(gabarits.GABARITS) >= 36
    assert "adhesion_oga" not in gabarits.GABARITS


def test_tous_les_comptes_des_gabarits_existent_au_plan(conn):
    for cle, g in gabarits.GABARITS.items():
        n = conn.execute("SELECT COUNT(*) FROM compte WHERE numero=?",
                         (g["compte"],)).fetchone()[0]
        assert n == 1, f"{cle} → compte {g['compte']} absent du plan"


def test_gabarit_personnalise_saisissable(conn):
    audit_cycle._creer_dossier(conn, ANNEE)
    gabarits.ajouter_personnalise(conn, cle="eco_contribution",
                                  libelle="Éco-contribution meublés",
                                  compte_num="635130", nature="charge")
    res = operations.saisir(conn, type="eco_contribution", montant=42.0,
                            date_operation=f"{ANNEE}-06-01",
                            periode=f"{ANNEE}-06")
    cpt = conn.execute("SELECT compte_num FROM ligne WHERE ecriture_id=? "
                       "AND debit>0", (res["ecriture_id"],)).fetchone()[0]
    assert cpt == "635130"
    assert "eco_contribution" in gabarits.tous(conn)
    assert "eco_contribution" not in gabarits.tous(None)   # hors base : absent


def test_gabarit_personnalise_refuse_compte_inconnu(conn):
    with pytest.raises(ValueError, match="absent du plan"):
        gabarits.ajouter_personnalise(conn, cle="x", libelle="X",
                                      compte_num="999999", nature="charge")


# ── Retraitement ALUR automatique & intérêts d'emprunt ──────────────────────

def test_alur_reintegre_automatiquement(conn):
    audit_cycle._creer_dossier(conn, ANNEE)
    audit_cycle._saisir_annee(conn, ANNEE, 800.0, [])
    operations.saisir(conn, type="fonds_travaux_alur", montant=61.0,
                      date_operation=f"{ANNEE}-04-01", periode=f"{ANNEE}-04")
    res = fiscal.cloturer(conn, ANNEE)
    assert res["autres_retraitements"] == pytest.approx(61.0)
    # Résultat fiscal = comptable + 61 (l'ALUR est neutralisé fiscalement).
    assert res["resultat_fiscal"] == pytest.approx(
        res["agregats"]["resultat_comptable"] + 61.0
        + res["suivi_39c"]["report_annee"]
        - res["suivi_39c"]["utilisation_annee"])
    detail = liasse.generer(conn, ANNEE)["f2033b"]["reintegrations_detail"]
    assert any("Retraitements" in lib for lib, _ in detail)


def test_alur_desactivable_par_regle(conn):
    parametres.definir(conn, "retraitement_alur_auto", 0, f"{ANNEE}-01-01")
    audit_cycle._creer_dossier(conn, ANNEE)
    audit_cycle._saisir_annee(conn, ANNEE, 800.0, [])
    operations.saisir(conn, type="fonds_travaux_alur", montant=61.0,
                      date_operation=f"{ANNEE}-04-01", periode=f"{ANNEE}-04")
    res = fiscal.cloturer(conn, ANNEE)
    assert res["autres_retraitements"] == pytest.approx(0.0)


def test_interets_emprunt_en_charges_financieres(conn):
    audit_cycle._creer_dossier(conn, ANNEE)
    audit_cycle._saisir_annee(conn, ANNEE, 800.0, [])
    operations.saisir(conn, type="interets_emprunt", montant=1106.0,
                      date_operation=f"{ANNEE}-12-01", periode=f"{ANNEE}-12")
    fiscal.cloturer(conn, ANNEE)
    L = liasse.generer(conn, ANNEE)
    assert L["f2033b"]["charges_financieres_294"] == pytest.approx(1106.0)
    assert L["conforme"]


# ── Ventilation d'un appel de charges de copropriété ─────────────────────────

def test_appel_charges_ventile_en_composantes(conn):
    """Un appel = charges courantes (déductibles) + fonds ALUR (réintégré)
    + travaux, rattachés à la même pièce APPEL AAAA-MM."""
    audit_cycle._creer_dossier(conn, ANNEE)
    res = operations.saisir_appel_charges(
        conn, date_operation=f"{ANNEE}-01-15", periode=f"{ANNEE}-01",
        charges_courantes=484.50, fonds_alur=15.25, travaux=120.0)
    assert res["total"] == pytest.approx(619.75)
    assert len(res["operations"]) == 3
    rows = dict(conn.execute(
        "SELECT type, ROUND(SUM(montant),2) FROM operation "
        "WHERE exercice_annee=? GROUP BY type", (ANNEE,)).fetchall())
    assert rows["charge_copro"] == pytest.approx(484.50)
    assert rows["fonds_travaux_alur"] == pytest.approx(15.25)
    assert rows["maintenance"] == pytest.approx(120.0)
    refs = {r[0] for r in conn.execute(
        "SELECT e.piece_ref FROM ecriture e JOIN operation o ON o.ecriture_id=e.id "
        "WHERE o.exercice_annee=?", (ANNEE,)).fetchall()
        if r[0] and r[0].startswith("APPEL")}
    assert refs == {f"APPEL {ANNEE}-01"}


def test_appel_charges_symetrie_bic_et_alur(conn):
    """Reproduit la mécanique 2025 réelle : provisions locataire en produits,
    totalité de l'appel déductible SAUF l'ALUR, réintégré à la clôture."""
    audit_cycle._creer_dossier(conn, ANNEE)
    for m in range(1, 13):
        operations.saisir(conn, type="loyer", montant=758.33,
                          date_operation=f"{ANNEE}-{m:02d}-05",
                          periode=f"{ANNEE}-{m:02d}")
        operations.saisir(conn, type="charges_locatives", montant=93.75,
                          date_operation=f"{ANNEE}-{m:02d}-05",
                          periode=f"{ANNEE}-{m:02d}")
    for m in ("01", "04", "07", "10"):
        operations.saisir_appel_charges(
            conn, date_operation=f"{ANNEE}-{m}-15", periode=f"{ANNEE}-{m}",
            charges_courantes=484.50, fonds_alur=15.25)
    res = fiscal.cloturer(conn, ANNEE)
    # ALUR 4 × 15,25 = 61 € réintégré automatiquement (= liasses de référence 2025).
    assert res["autres_retraitements"] == pytest.approx(61.0)
    L = liasse.generer(conn, ANNEE)
    assert L["conforme"]
    # Produits = loyers + provisions (symétrie BIC) ; copro comptable = 1 999 €.
    assert L["f2033b"]["produits_218"] == pytest.approx(12 * (758.33 + 93.75))
    b = L["f2033b"]
    assert any("Retraitements" in lib for lib, _ in b["reintegrations_detail"])


def test_appel_charges_vide_refuse(conn):
    with pytest.raises(ValueError, match="vide"):
        operations.saisir_appel_charges(conn, date_operation=f"{ANNEE}-01-15")
