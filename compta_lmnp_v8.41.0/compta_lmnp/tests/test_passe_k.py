# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Non-régression des constats de la passe K (clôture et continuité).

Trois constats, et une même question derrière : qu'est-ce qui est
IRRÉVERSIBLE ?

Un exercice clos a figé ses reports, archivé son FEC et peut-être servi à
une déclaration. Le logiciel le sait pour l'exercice qu'on lui demande de
clôturer — il refusait déjà de le rouvrir — mais pas pour ses voisins :
rien n'empêchait d'ajouter après coup un exercice ANCIEN et de le clore,
alors que les suivants avaient été scellés sans lui. De même, une reprise
d'à-nouveaux est un LOT : l'écriture AN et l'OD qui affecte le résultat.
En n'en gardant qu'une moitié, la reconstruction comptait le résultat deux
fois.

Le troisième constat est d'une autre nature : un contrôle qui tolère un
écart n'a pas le droit de le présenter comme une égalité.

Ces tests figent les refus, et surtout leurs contre-épreuves : un dossier
tenu dans l'ordre doit continuer de passer sans entrave.

Aucune donnée réelle : exploitant fictif, bases blanches, FEC construits
ici.

Lancer :  pytest -q tests/test_passe_k.py
"""
import os
import tempfile

import pytest

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import ecritures
import fec_io
import fiscal
import init_db
import migration_fec
import operations
import reprise

COLS = fec_io.COLONNES


# ── Fabriques de pièces fictives ──────────────────────────────────────────

def _dossier(tmp_path, nom, annee):
    conn = init_db.init_blanc(str(tmp_path / nom), annee)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Exploitant fictif','000000000','Adresse fictive')")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) "
                 "VALUES (1,1,'Bien fictif',12000)")
    conn.commit()
    return conn


def immobilisation(conn, annee, montant=12000):
    ecritures.inserer(conn, journal="OD", date=f"{annee}-01-02", annee=annee,
                      libelle="Acquisition", piece_ref="ACQ",
                      lignes=[("218400", montant, 0.0),
                              ("108000", 0.0, montant)])


def loyer(conn, annee, montant):
    operations.saisir(conn, type="loyer", montant=montant, bien_id=1,
                      date_operation=f"{annee}-03-10", periode=f"{annee}-03")


def maintenance(conn, annee, montant):
    operations.saisir(conn, type="maintenance", montant=montant, bien_id=1,
                      date_operation=f"{annee}-05-10", periode=f"{annee}-05")


def solde(conn, compte, annee):
    return round(conn.execute(
        "SELECT COALESCE(SUM(l.debit - l.credit),0) FROM ligne l "
        "JOIN ecriture e ON e.id = l.ecriture_id "
        "WHERE e.exercice_annee=? AND l.compte_num=?",
        (annee, compte)).fetchone()[0], 2)


def deficit_restant(conn):
    return round(conn.execute(
        "SELECT COALESCE(SUM(solde),0) FROM deficit_lmnp").fetchone()[0], 2)


def _ligne_fec(journal, num, date, compte, debit, credit):
    r = dict.fromkeys(COLS, "")
    r.update(JournalCode=journal, JournalLib=journal, EcritureNum=str(num),
             EcritureDate=date, CompteNum=compte, CompteLib=compte,
             PieceRef="P", PieceDate=date, EcritureLib="Fictif",
             ValidDate=date,
             Debit=f"{debit:.2f}".replace(".", ",") if debit else "",
             Credit=f"{credit:.2f}".replace(".", ",") if credit else "")
    return [r[k] for k in COLS]


def ecrire_fec(chemin, lignes):
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(COLS) + "\r\n")
        for ligne in lignes:
            f.write("\t".join(ligne) + "\r\n")
    return str(chemin)


def jonction(tmp_path, ecart=0.0):
    """Deux FEC fictifs qui se raccordent, à `ecart` près sur deux comptes."""
    f24 = ecrire_fec(tmp_path / "FEC2024.txt", [
        _ligne_fec("OD", 1, "20240315", "218400", 12000, 0),
        _ligne_fec("OD", 1, "20240315", "108000", 0, 12000)])
    f25 = ecrire_fec(tmp_path / "FEC2025.txt", [
        _ligne_fec("AN", 1, "20250101", "218400", 12000 + ecart, 0),
        _ligne_fec("AN", 1, "20250101", "108000", 0, 12000 + ecart),
        _ligne_fec("OD", 2, "20250315", "708810", 0, 500),
        _ligne_fec("OD", 2, "20250315", "108000", 500, 0)])
    return migration_fec.controler_jonctions(
        migration_fec.ordonner([f24, f25]))[0]


# ═══ K-01 — la chronologie des clôtures vaut aussi vers l'aval ═════════

def test_k01_cloturer_un_exercice_anterieur_a_un_exercice_clos_est_refuse(
        tmp_path):
    """La garde ne cherchait que les exercices antérieurs encore OUVERTS.
    Rien n'empêchait donc d'ajouter 2024 après coup et de le clore alors
    que 2025 était scellé : les 600 € de bénéfice 2025, déjà figés comme
    imposables, auraient dû être absorbés par le déficit que l'on vient de
    créer en 2024 — et le stock de déficits compte 600 € de trop. Deux
    représentations incompatibles de la même imputation."""
    conn = _dossier(tmp_path, "k01.db", 2025)
    try:
        immobilisation(conn, 2025)
        loyer(conn, 2025, 600)
        r25 = fiscal.cloturer(conn, 2025, generer_dotation=False, forcer=True)
        assert r25["revenu_imposable"] == 600.0
        reprise.ouvrir_exercice(conn, 2024, avec_reprise=False)
        maintenance(conn, 2024, 1000)
        with pytest.raises(ValueError, match="2025 est déjà clos"):
            fiscal.cloturer(conn, 2024, generer_dotation=False)
        assert conn.execute("SELECT statut FROM exercice WHERE annee=2024"
                            ).fetchone()[0] == "ouvert"
        assert deficit_restant(conn) == 0.0     # aucun déficit n'est créé
    finally:
        conn.close()


def test_k01_le_message_dit_quoi_faire(tmp_path):
    """Un refus qui n'indique pas la sortie est une impasse : le logiciel
    ne peut pas reclôturer les exercices postérieurs, il doit dire que le
    chemin passe par une sauvegarde."""
    conn = _dossier(tmp_path, "k01b.db", 2025)
    try:
        loyer(conn, 2025, 600)
        fiscal.cloturer(conn, 2025, generer_dotation=False, forcer=True)
        reprise.ouvrir_exercice(conn, 2024, avec_reprise=False)
        maintenance(conn, 2024, 1000)
        with pytest.raises(ValueError) as exc:
            fiscal.cloturer(conn, 2024, generer_dotation=False)
        assert "sauvegarde" in str(exc.value)
        assert "ordre chronologique" in str(exc.value)
    finally:
        conn.close()


def test_k01_l_ordre_chronologique_reste_praticable(tmp_path):
    """Contre-épreuve, et c'est elle qui compte : le même dossier tenu dans
    l'ordre doit produire l'imputation attendue, sans entrave."""
    conn = _dossier(tmp_path, "k01c.db", 2024)
    try:
        maintenance(conn, 2024, 1000)
        fiscal.cloturer(conn, 2024, generer_dotation=False, forcer=True)
        reprise.ouvrir_exercice(conn, 2025)
        immobilisation(conn, 2025)
        loyer(conn, 2025, 600)
        r = fiscal.cloturer(conn, 2025, generer_dotation=False, forcer=True)
        assert r["deficits"]["impute_sur_benefice"] == 600.0
        assert r["revenu_imposable"] == 0.0
        assert deficit_restant(conn) == 400.0
    finally:
        conn.close()


def test_k01_la_garde_amont_tient_toujours(tmp_path):
    """L'ancienne garde — un exercice antérieur encore ouvert — ne doit pas
    avoir été perdue en chemin."""
    conn = _dossier(tmp_path, "k01d.db", 2024)
    try:
        reprise.ouvrir_exercice(conn, 2025, avec_reprise=False)
        loyer(conn, 2025, 600)
        with pytest.raises(ValueError, match="Clôturez d'abord l'exercice 2024"):
            fiscal.cloturer(conn, 2025, generer_dotation=False)
    finally:
        conn.close()


def test_k01_un_exercice_posterieur_ouvert_ne_bloque_rien(tmp_path):
    """Seul un exercice postérieur CLOS bloque : en ouvrir un d'avance —
    geste ordinaire en début d'année — ne doit pas empêcher de clôturer
    celui qui précède."""
    conn = _dossier(tmp_path, "k01e.db", 2025)
    try:
        loyer(conn, 2025, 600)
        reprise.ouvrir_exercice(conn, 2026, avec_reprise=False)
        fiscal.cloturer(conn, 2025, generer_dotation=False, forcer=True)
        assert conn.execute("SELECT statut FROM exercice WHERE annee=2025"
                            ).fetchone()[0] == "clos"
    finally:
        conn.close()


# ═══ K-02 — une reprise est un lot, pas deux écritures séparées ═══════

def _dossier_avec_reprise_2026(tmp_path, nom):
    conn = _dossier(tmp_path, nom, 2025)
    immobilisation(conn, 2025)
    loyer(conn, 2025, 600)
    fiscal.cloturer(conn, 2025, generer_dotation=False, forcer=True)
    reprise.ouvrir_exercice(conn, 2026)
    return conn


def test_k02_supprimer_le_seul_an_ne_permet_pas_de_reconstruire(tmp_path):
    """L'OD d'affectation survivait à la suppression de l'écriture AN, et
    la reconstruction affectait le résultat une SECONDE fois : 600 € au
    crédit de 108000 et au débit de 120000 en double. Chaque OD étant
    elle-même équilibrée, aucun contrôle d'équilibre ne pouvait le voir —
    seule la reprise de l'année suivante butait, bien plus tard, sur un
    solde 120000 résiduel."""
    conn = _dossier_avec_reprise_2026(tmp_path, "k02.db")
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM ecriture WHERE exercice_annee=2026 "
                     "AND journal_code='AN'")
        conn.commit()
        assert "OD d'affectation" in reprise.reprise_deja_presente(conn, 2026)
        with pytest.raises(ValueError, match="contient déjà"):
            reprise.construire_an_interne(conn, 2026)
        assert conn.execute(
            "SELECT COUNT(*) FROM ecriture WHERE exercice_annee=2026 "
            "AND libelle=?", (reprise.LIBELLE_AFFECTATION,)).fetchone()[0] == 1
        assert solde(conn, "108000", 2026) == -600.0
        assert solde(conn, "120000", 2026) == 600.0
    finally:
        conn.close()


def test_k02_supprimer_la_seule_od_ne_permet_pas_davantage(tmp_path):
    """Le cas symétrique : l'AN subsiste, l'affectation a disparu."""
    conn = _dossier_avec_reprise_2026(tmp_path, "k02b.db")
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM ecriture WHERE exercice_annee=2026 "
                     "AND libelle=?", (reprise.LIBELLE_AFFECTATION,))
        conn.commit()
        assert "à-nouveaux" in reprise.reprise_deja_presente(conn, 2026)
        with pytest.raises(ValueError, match="contient déjà"):
            reprise.construire_an_interne(conn, 2026)
    finally:
        conn.close()


def test_k02_une_reprise_complete_reste_refusee(tmp_path):
    """La garde d'origine — deux reprises successives — n'a pas été perdue."""
    conn = _dossier_avec_reprise_2026(tmp_path, "k02c.db")
    try:
        assert reprise.reprise_deja_presente(conn, 2026) == (
            "des à-nouveaux et leur affectation du résultat")
        with pytest.raises(ValueError, match="contient déjà"):
            reprise.construire_an_interne(conn, 2026)
    finally:
        conn.close()


def test_k02_la_garde_couvre_aussi_la_reprise_depuis_un_fec(tmp_path):
    """Les deux chemins de reprise — interne et depuis un FEC externe —
    passent par la même mécanique : la garde y vit désormais, plutôt que
    dans chaque appelant."""
    conn = _dossier_avec_reprise_2026(tmp_path, "k02d.db")
    try:
        chemin = ecrire_fec(tmp_path / "externe.txt", [
            _ligne_fec("AN", 1, "20251231", "218400", 12000, 0),
            _ligne_fec("AN", 1, "20251231", "108000", 0, 12000)])
        with pytest.raises(ValueError, match="contient déjà"):
            reprise.construire_an(conn, chemin, 2026)
    finally:
        conn.close()


def test_k02_une_reprise_ordinaire_passe_toujours(tmp_path):
    """Contre-épreuve : sur un exercice vierge, la reprise fonctionne et
    solde bien le compte de résultat."""
    conn = _dossier(tmp_path, "k02e.db", 2025)
    try:
        immobilisation(conn, 2025)
        loyer(conn, 2025, 600)
        fiscal.cloturer(conn, 2025, generer_dotation=False, forcer=True)
        assert reprise.reprise_deja_presente(conn, 2026) == ""
        reprise.ouvrir_exercice(conn, 2026)
        # 108000 porte −11 400 € repris (12 000 € d'apport moins 600 € de
        # loyer encaissé), puis reçoit les 600 € de bénéfice affecté :
        # −12 000 € au crédit, et 120000 soldé — les deux chiffres du
        # rapport pour une reprise correcte.
        assert solde(conn, "120000", 2026) == 0.0
        assert solde(conn, "108000", 2026) == -12000.0
        assert conn.execute(
            "SELECT COUNT(*) FROM ecriture WHERE exercice_annee=2026 "
            "AND libelle=?", (reprise.LIBELLE_AFFECTATION,)).fetchone()[0] == 1
    finally:
        conn.close()


def test_k02_la_chaine_se_poursuit_sur_un_troisieme_exercice(tmp_path):
    """C'était le symptôme tardif du défaut : la reprise suivante butait
    sur un solde 120000 que les comptes repris n'expliquaient pas."""
    conn = _dossier(tmp_path, "k02f.db", 2025)
    try:
        immobilisation(conn, 2025)
        loyer(conn, 2025, 600)
        fiscal.cloturer(conn, 2025, generer_dotation=False, forcer=True)
        reprise.ouvrir_exercice(conn, 2026)
        fiscal.cloturer(conn, 2026, generer_dotation=False, forcer=True)
        reprise.ouvrir_exercice(conn, 2027)          # ne doit pas lever
        assert solde(conn, "120000", 2027) == 0.0
    finally:
        conn.close()


# ═══ K-03 — une tolérance n'est pas une égalité ══════════════════════

def test_k03_une_jonction_exacte_se_dit_exacte(tmp_path):
    rapport = jonction(tmp_path, ecart=0.0)
    assert rapport["type"] == "ok"
    assert "exactement" in rapport["message"]


def test_k03_un_centime_masque_est_desormais_annonce(tmp_path):
    """La tolérance vaut un centime, et le message annonçait « les bilans
    se raccordent au centime » : un décalage d'exactement un centime sur
    deux comptes était donc approuvé sous un libellé qui prétendait le
    contraire."""
    rapport = jonction(tmp_path, ecart=0.01)
    assert rapport["type"] == "tolere"
    assert "ne se raccordent pas exactement" in rapport["message"]
    assert "tolérance" in rapport["message"]
    assert len(rapport["ecarts_toleres"]) == 2
    assert {c for c, *_ in rapport["ecarts_toleres"]} == {"108000", "218400"}


def test_k03_un_ecart_franc_reste_une_rupture(tmp_path):
    """Au-delà de la tolérance, rien ne change : c'est toujours un écart."""
    rapport = jonction(tmp_path, ecart=5.0)
    assert rapport["type"] == "ecart"
    assert "ne se raccordent pas" in rapport["message"]


def test_k03_la_tolerance_reste_reglable(tmp_path):
    """Le paramètre existe et fait ce qu'il dit : à tolérance nulle, le
    centime redevient une rupture franche."""
    f24 = ecrire_fec(tmp_path / "FEC2024.txt", [
        _ligne_fec("OD", 1, "20240315", "218400", 12000, 0),
        _ligne_fec("OD", 1, "20240315", "108000", 0, 12000)])
    f25 = ecrire_fec(tmp_path / "FEC2025.txt", [
        _ligne_fec("AN", 1, "20250101", "218400", 12000.01, 0),
        _ligne_fec("AN", 1, "20250101", "108000", 0, 12000.01)])
    ordre = migration_fec.ordonner([f24, f25])
    assert migration_fec.controler_jonctions(
        ordre, tolerance=0)[0]["type"] == "ecart"


# ═══ Ce qui tenait doit continuer de tenir ═══════════════════════════

def test_un_cycle_de_trois_exercices_traverse_les_nouvelles_gardes(tmp_path):
    """Garde générale : le cycle 2024-2026 du rapport, tenu dans l'ordre,
    ne doit rencontrer aucune des exigences ajoutées par cette passe."""
    conn = _dossier(tmp_path, "cycle.db", 2024)
    try:
        immobilisation(conn, 2024)
        attendu = [(2024, 1000, 1300), (2025, 2400, 200), (2026, 4000, 200)]
        for annee, recettes, charges in attendu:
            if annee > 2024:
                reprise.ouvrir_exercice(conn, annee)
            loyer(conn, annee, recettes)
            maintenance(conn, annee, charges)
            fiscal.cloturer(conn, annee, generer_dotation=False, forcer=True)
            assert conn.execute(
                "SELECT statut FROM exercice WHERE annee=?",
                (annee,)).fetchone()[0] == "clos"
        # Le résultat transite par 120000 puis est soldé à chaque ouverture.
        assert solde(conn, "120000", 2026) == 0.0
    finally:
        conn.close()


def test_une_cloture_deja_faite_reste_refusee(tmp_path):
    """La garde d'idempotence n'a pas bougé."""
    conn = _dossier(tmp_path, "idem.db", 2025)
    try:
        loyer(conn, 2025, 600)
        fiscal.cloturer(conn, 2025, generer_dotation=False, forcer=True)
        with pytest.raises(ValueError, match="déjà clos"):
            fiscal.cloturer(conn, 2025, generer_dotation=False)
    finally:
        conn.close()


def test_dossier_temporaire_nettoye():
    """Garde-fou de la suite elle-même : ces tests n'écrivent que dans le
    tmp_path de pytest, jamais à côté des fichiers du projet."""
    assert not os.path.exists(os.path.join(tempfile.gettempdir(), "k01.db"))
