# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Non-régression des constats de la passe L (cession d'un bien).

La cession est le moment où un bien quitte le patrimoine, et rien ne
viendra plus le corriger : ce que la sortie écrit reste. D'où le fil rouge
de cette passe — **solder, c'est ramener un compte à zéro**, donc partir de
ce qui s'y trouve et non de ce que le plan théorique prévoyait. La sortie
reprenait le cumul du plan ; sur un historique repris d'un cabinet, elle
laissait des amortissements en compte pour un actif qui n'existait plus, et
gonflait d'autant la valeur nette passée en charge.

Les trois autres constats tiennent à ce que le déclarant REÇOIT : le
tableau des immobilisations effaçait l'ouverture et les mouvements du bien
vendu au lieu de montrer sa sortie, une vente antérieure à l'acquisition
était acceptée sans un mot, et le PDF neutralisait la plus-value sans
rappeler qu'elle se déclare ailleurs.

Aucune donnée réelle : exploitant fictif, bases blanches.

Lancer :  pytest -q tests/test_passe_l.py
"""
import os
import shutil
import subprocess
import tempfile

import pytest

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import cession
import ecritures
import fiscal
import init_db
import liasse
import operations
import reprise


# ── Fabriques de pièces fictives ──────────────────────────────────────────

def _dossier(tmp_path, nom, annee=2026, acquisition="2026-01-01"):
    conn = init_db.init_blanc(str(tmp_path / nom), annee)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Exploitant fictif','000000000','Adresse fictive')")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total,"
                 "date_acquisition) VALUES (1,1,'Bien fictif',12000,?)",
                 (acquisition,))
    cession.assurer_schema(conn)
    conn.commit()
    return conn


def composant(conn, libelle, valeur, duree=10, dms="2026-01-01",
              immo="218400", amort="281840", bien_id=1):
    conn.execute(
        "INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,"
        "date_mise_service,compte_immo,compte_amort,amortissable) "
        "VALUES (?,?,?,?,?,?,?,1)",
        (bien_id, libelle, valeur, duree, dms, immo, amort))
    conn.commit()


def acquisition(conn, compte, montant, annee=2026, date=None):
    ecritures.inserer(conn, journal="OD", date=date or f"{annee}-01-01",
                      annee=annee, libelle="Acquisition", piece_ref="ACQ",
                      lignes=[(compte, montant, 0.0),
                              ("108000", 0.0, montant)])


def a_nouveaux(conn, lignes, annee=2026):
    ecritures.inserer(conn, journal="AN", date=f"{annee}-01-01", annee=annee,
                      libelle="A Nouveaux", piece_ref="AN", lignes=lignes)


def solde(conn, compte, annee=2026):
    return round(conn.execute(
        "SELECT COALESCE(SUM(l.debit - l.credit),0) FROM ligne l "
        "JOIN ecriture e ON e.id = l.ecriture_id "
        "WHERE e.exercice_annee=? AND l.compte_num=?",
        (annee, compte)).fetchone()[0], 2)


def texte_pdf(conn, annee, tmp_path, nom="liasse.pdf"):
    import liasse_pdf
    chemin = str(tmp_path / nom)
    liasse_pdf.generer_pdf(liasse.generer(conn, annee), chemin)
    return subprocess.run(["pdftotext", "-layout", chemin, "-"],
                          capture_output=True, text=True, timeout=60).stdout


# ═══ L-01 — solder, c'est ramener le compte à zéro ════════════════════

def test_l01_la_sortie_solde_le_cumul_comptabilise(tmp_path):
    """3 000 € d'amortissements repris en à-nouveaux, pour un plan qui n'en
    prévoit que 1 200 € — un historique de cabinet, ou une durée corrigée
    après coup. La sortie soldait le cumul THÉORIQUE : 1 800 €
    d'amortissements restaient en compte pour un actif qui n'existe plus,
    et la valeur nette passée en charge de cession était surévaluée
    d'autant."""
    conn = _dossier(tmp_path, "l01.db", acquisition="2025-01-01")
    try:
        composant(conn, "Gros œuvre", 12000, dms="2025-01-01",
                  immo="213150", amort="281315")
        a_nouveaux(conn, [("213150", 12000, 0.0), ("281315", 0.0, 3000),
                          ("108000", 0.0, 9000)])
        r = cession.ceder_bien(conn, 1, "2026-06-30", 15000)
        assert r["dotation_complementaire"] == 595.07
        assert r["vnc_sortie"] == 8404.93         # 12 000 − (3 000 + 595,07)
        assert r["pv_comptable"] == 6595.07
        assert solde(conn, "281315") == 0.0       # le compte est soldé
    finally:
        conn.close()


def test_l01_un_dossier_concordant_est_inchange(tmp_path):
    """Contre-épreuve : quand les comptes suivent le plan, rien ne bouge."""
    conn = _dossier(tmp_path, "l01b.db")
    try:
        composant(conn, "Mobilier", 12000)
        acquisition(conn, "218400", 12000)
        r = cession.ceder_bien(conn, 1, "2026-06-30", 15000)
        assert r["dotation_complementaire"] == 595.07
        assert r["vnc_sortie"] == 11404.93
        assert solde(conn, "281840") == 0.0
    finally:
        conn.close()


def test_l01_un_compte_partage_avec_un_bien_conserve_fait_refuser(tmp_path):
    """Quand le compte sert aussi à un composant qui n'est PAS cédé, l'écart
    entre comptes et plan ne peut être attribué ni aux uns ni aux autres :
    le logiciel refuse plutôt que de trancher à la place de l'utilisateur.
    """
    conn = _dossier(tmp_path, "l01c.db", acquisition="2025-01-01")
    try:
        conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total,"
                     "date_acquisition) VALUES (2,1,'Second bien',6000,"
                     "'2025-01-01')")
        composant(conn, "Gros œuvre A", 12000, dms="2025-01-01",
                  immo="213150", amort="281315")
        composant(conn, "Gros œuvre B", 6000, dms="2025-01-01",
                  immo="213150", amort="281315", bien_id=2)
        a_nouveaux(conn, [("213150", 18000, 0.0), ("281315", 0.0, 5000),
                          ("108000", 0.0, 13000)])
        with pytest.raises(ValueError, match="ne peut être attribué"):
            cession.ceder_bien(conn, 1, "2026-06-30", 15000)
        conn.commit()
        assert conn.execute("SELECT date_cession FROM bien WHERE id=1"
                            ).fetchone()[0] is None
    finally:
        conn.close()


def test_l01_un_compte_partage_concordant_passe(tmp_path):
    """…mais un compte partagé dont les soldes suivent le plan ne bloque
    rien : le refus vise l'écart, pas le partage."""
    conn = _dossier(tmp_path, "l01d.db")
    try:
        conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) "
                     "VALUES (2,1,'Second bien',6000)")
        composant(conn, "Gros œuvre A", 12000, immo="213150", amort="281315")
        composant(conn, "Gros œuvre B", 6000, immo="213150", amort="281315",
                  bien_id=2)
        acquisition(conn, "213150", 18000)
        r = cession.ceder_bien(conn, 1, "2026-06-30", 15000)
        assert r["vnc_sortie"] == 11404.93
    finally:
        conn.close()


# ═══ L-02 — l'exercice de la vente doit MONTRER la sortie ════════════

def _cycle_avec_cession(tmp_path, nom):
    conn = _dossier(tmp_path, nom, annee=2025, acquisition="2025-01-01")
    composant(conn, "Gros œuvre", 12000, dms="2025-01-01",
              immo="213150", amort="281315")
    acquisition(conn, "213150", 12000, annee=2025)
    fiscal.cloturer(conn, 2025)
    reprise.ouvrir_exercice(conn, 2026)
    cession.ceder_bien(conn, 1, "2026-06-30", 15000)
    fiscal.cloturer(conn, 2026)
    return conn


def test_l02_le_2033c_montre_l_ouverture_et_les_mouvements(tmp_path):
    """Le bien cédé était exclu du tableau dès l'année de sa vente :
    ouverture, dotation de sortie et diminution disparaissaient, et il ne
    restait que des zéros. Les soldes FINAUX étaient justes — et comme les
    contrôles ne comparent que les soldes finaux, ils approuvaient."""
    conn = _cycle_avec_cession(tmp_path, "l02.db")
    try:
        t = liasse.immobilisations_2033c(conn, 2026)["totaux"]
        assert t["brut_debut"] == 12000.0
        assert t["diminutions"] == 12000.0
        assert t["brut_fin"] == 0.0
        assert t["amort_debut"] == 1200.0
        assert t["dotation"] == 595.07
        assert t["amort_diminutions"] == 1795.07
        assert t["amort_fin"] == 0.0
    finally:
        conn.close()


def test_l02_la_sortie_est_portee_dans_la_bonne_rubrique(tmp_path):
    conn = _cycle_avec_cession(tmp_path, "l02b.db")
    try:
        rubriques = {r["libelle"]: r
                     for r in liasse.immobilisations_2033c(
                         conn, 2026)["rubriques"]}
        constructions = rubriques["Constructions"]
        assert constructions["brut_debut"] == 12000.0
        assert constructions["diminutions"] == 12000.0
        assert rubriques["Autres immobilisations corporelles"][
            "diminutions"] == 0.0
    finally:
        conn.close()


def test_l02_le_composant_sorti_figure_au_detail(tmp_path):
    conn = _cycle_avec_cession(tmp_path, "l02c.db")
    try:
        detail = liasse.immobilisations_2033c(conn, 2026)["detail_composants"]
        assert len(detail) == 1
        assert detail[0]["sorti"] is True
        assert detail[0]["dotation"] == 595.07
        assert detail[0]["vnc_fin"] == 0.0
    finally:
        conn.close()


def test_l02_l_exercice_suivant_ne_montre_plus_rien(tmp_path):
    """L'exclusion reste entière pour les exercices POSTÉRIEURS : le bien
    n'y a plus rien à faire."""
    conn = _cycle_avec_cession(tmp_path, "l02d.db")
    try:
        reprise.ouvrir_exercice(conn, 2027)
        t = liasse.immobilisations_2033c(conn, 2027)["totaux"]
        assert all(v == 0.0 for v in t.values())
    finally:
        conn.close()


def test_l02_un_exercice_sans_cession_a_ses_diminutions_nulles(tmp_path):
    """Contre-épreuve : les nouvelles colonnes ne doivent rien inventer."""
    conn = _dossier(tmp_path, "l02e.db")
    try:
        composant(conn, "Mobilier", 12000)
        acquisition(conn, "218400", 12000)
        fiscal.cloturer(conn, 2026)
        t = liasse.immobilisations_2033c(conn, 2026)["totaux"]
        assert t["diminutions"] == 0.0
        assert t["amort_diminutions"] == 0.0
        assert t["augmentations"] == 12000.0
        assert t["brut_fin"] == 12000.0
    finally:
        conn.close()


@pytest.mark.skipif(shutil.which("pdftotext") is None,
                    reason="pdftotext absent")
def test_l02_le_pdf_porte_une_colonne_diminutions(tmp_path):
    conn = _cycle_avec_cession(tmp_path, "l02f.db")
    try:
        texte = texte_pdf(conn, 2026, tmp_path)
        assert "Diminutions" in texte
        assert "12 000,00" in texte      # le brut sorti, désormais visible
    finally:
        conn.close()


# ═══ L-03 — on ne vend pas avant d'avoir acheté ═════════════════════

def test_l03_une_vente_anterieure_a_l_acquisition_est_refusee(tmp_path):
    """Seule la SYNTAXE de la date était contrôlée. Une vente datée de la
    veille de l'acquisition sortait 12 000 € d'actif et enregistrait
    15 000 € de produit sur une chronologie impossible — liasse déclarée
    conforme."""
    conn = _dossier(tmp_path, "l03.db", acquisition="2026-07-01")
    try:
        composant(conn, "Mobilier", 12000, dms="2026-07-01")
        acquisition(conn, "218400", 12000, date="2026-07-01")
        with pytest.raises(ValueError, match="antérieure à l'entrée du bien"):
            cession.ceder_bien(conn, 1, "2026-06-30", 15000)
        conn.commit()
        assert conn.execute("SELECT date_cession FROM bien").fetchone()[0] is None
        assert conn.execute("SELECT date_sortie FROM composant"
                            ).fetchone()[0] is None
        assert solde(conn, "775000") == 0.0
    finally:
        conn.close()


def test_l03_une_vente_le_jour_meme_reste_possible(tmp_path):
    """La borne est inclusive : acheter et revendre le même jour est
    étrange, mais ce n'est pas impossible — et ce n'est pas au logiciel
    d'en juger."""
    conn = _dossier(tmp_path, "l03b.db", acquisition="2026-07-01")
    try:
        composant(conn, "Mobilier", 12000, dms="2026-07-01")
        acquisition(conn, "218400", 12000, date="2026-07-01")
        r = cession.ceder_bien(conn, 1, "2026-07-01", 15000)
        assert r["valeur_brute_sortie"] == 12000.0
    finally:
        conn.close()


def test_l03_le_message_nomme_les_deux_dates(tmp_path):
    """Le logiciel ne peut pas savoir laquelle des deux dates est fausse :
    il doit les donner toutes les deux."""
    conn = _dossier(tmp_path, "l03c.db", acquisition="2026-07-01")
    try:
        composant(conn, "Mobilier", 12000, dms="2026-07-01")
        with pytest.raises(ValueError) as exc:
            cession.ceder_bien(conn, 1, "2026-06-30", 15000)
        assert "2026-06-30" in str(exc.value)
        assert "2026-07-01" in str(exc.value)
    finally:
        conn.close()


# ═══ L-04 — la plus-value se déclare ailleurs, et il faut le dire ═══

def _dossier_cede(tmp_path, nom, prix):
    conn = _dossier(tmp_path, nom)
    composant(conn, "Mobilier", 12000)
    acquisition(conn, "218400", 12000)
    operations.saisir(conn, type="loyer", montant=3000, bien_id=1,
                      date_operation="2026-03-10", periode="2026-03")
    cession.ceder_bien(conn, 1, "2026-06-30", prix)
    fiscal.cloturer(conn, 2026)
    return conn


def test_l04_la_liasse_signale_la_cession_de_l_exercice(tmp_path):
    conn = _dossier_cede(tmp_path, "l04.db", 15000)
    try:
        signal = liasse.generer(conn, 2026)["cession_de_l_exercice"]
        assert signal["produit"] == 15000.0
        assert signal["valeur_comptable"] == 11404.93
    finally:
        conn.close()


def test_l04_aucun_signal_sans_cession(tmp_path):
    conn = _dossier(tmp_path, "l04b.db")
    try:
        composant(conn, "Mobilier", 12000)
        acquisition(conn, "218400", 12000)
        fiscal.cloturer(conn, 2026)
        assert liasse.generer(conn, 2026)["cession_de_l_exercice"] == {}
    finally:
        conn.close()


@pytest.mark.skipif(shutil.which("pdftotext") is None,
                    reason="pdftotext absent")
@pytest.mark.parametrize("prix", [15000, 0])
def test_l04_le_pdf_renvoie_a_la_declaration_immobiliere(tmp_path, prix):
    """Le destinataire du PDF voyait la vente neutralisée, sans indication
    du calcul et de la déclaration restant à faire. Le pense-bête le disait
    déjà ; le PDF est ce qui part chez le comptable ou reste au dossier. La
    cession à titre gratuit compte aussi : le prix est nul, mais la valeur
    comptable sort."""
    conn = _dossier_cede(tmp_path, f"l04c{prix}.db", prix)
    try:
        texte = texte_pdf(conn, 2026, tmp_path, f"l04c{prix}.pdf")
        assert "notaire" in texte
        assert "2048-IMM" in texte
        assert "150 U" in texte
    finally:
        conn.close()


@pytest.mark.skipif(shutil.which("pdftotext") is None,
                    reason="pdftotext absent")
def test_l04_un_exercice_sans_cession_ne_porte_pas_la_mention(tmp_path):
    """Contre-épreuve : la page de garde ne doit pas se charger d'un
    avertissement sans objet."""
    conn = _dossier(tmp_path, "l04d.db")
    try:
        composant(conn, "Mobilier", 12000)
        acquisition(conn, "218400", 12000)
        operations.saisir(conn, type="loyer", montant=3000, bien_id=1,
                          date_operation="2026-03-10", periode="2026-03")
        fiscal.cloturer(conn, 2026)
        texte = texte_pdf(conn, 2026, tmp_path, "sans.pdf")
        assert "2048-IMM" not in texte
    finally:
        conn.close()


# ═══ Ce qui tenait doit continuer de tenir ══════════════════════════

@pytest.mark.parametrize("prix,resultat_fiscal", [
    (15000, 2404.93), (5000, 2404.93), (0, 2404.93)])
def test_la_neutralisation_reste_symetrique(tmp_path, prix, resultat_fiscal):
    """Les trois scénarios de prix du rapport : le résultat fiscal vaut
    exactement les loyers moins la dotation, quel que soit le prix. Ni la
    plus-value ni la moins-value ne franchissent le BIC."""
    conn = _dossier_cede(tmp_path, f"neutre{prix}.db", prix)
    try:
        ex = conn.execute("SELECT resultat_fiscal FROM exercice WHERE annee=2026"
                          ).fetchone()[0]
        assert round(ex, 2) == resultat_fiscal
        assert abs(liasse.resultat_2033b(
            conn, 2026)["resultat_fiscal_352"]) < 0.005
    finally:
        conn.close()


def test_la_cession_sur_exercice_clos_reste_refusee(tmp_path):
    conn = _dossier(tmp_path, "clos.db")
    try:
        composant(conn, "Mobilier", 12000)
        acquisition(conn, "218400", 12000)
        fiscal.cloturer(conn, 2026)
        with pytest.raises(ValueError):
            cession.ceder_bien(conn, 1, "2026-06-30", 15000)
    finally:
        conn.close()


def test_le_prorata_de_sortie_est_inchange(tmp_path):
    """Les valeurs du rapport : 595,07 € au 30 juin, 3,29 € au 1er janvier,
    1 200 € au 31 décembre."""
    import datetime
    attendu = {"2026-01-01": 3.29, "2026-06-30": 595.07, "2026-12-31": 1200.0}
    for date, valeur in attendu.items():
        dot, _cumul = cession._dotation_prorata(
            12000, 10, "2026-01-01", 2026, datetime.date.fromisoformat(date))
        assert dot == valeur, date


def test_dossier_temporaire_nettoye():
    """Garde-fou de la suite elle-même : ces tests n'écrivent que dans le
    tmp_path de pytest, jamais à côté des fichiers du projet."""
    assert not os.path.exists(os.path.join(tempfile.gettempdir(), "l01.db"))
