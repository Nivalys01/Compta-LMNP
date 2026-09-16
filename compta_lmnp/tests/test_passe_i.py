# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Non-régression des constats de la passe I (article 39 C).

Deux fils rouges, et ils se ressemblent : le logiciel identifiait des
choses par une CHAÎNE au lieu de les identifier par ce qu'elles sont.

  - Les comptes, par égalité stricte. Le plan livré tient sur six
    chiffres, un cabinet en utilise sept : une dotation arrivée en 6811200
    n'était plus une dotation, un produit de cession en 7750000 n'était
    plus neutralisé. Rien ne tombait, aucun total ne bougeait — seule la
    QUALIFICATION FISCALE changeait, en silence. Un compte se reconnaît
    désormais à sa racine PCG, dont les subdivisions héritent.

  - Les biens, par le libellé de leurs composants. Deux logements meublés
    dont un composant s'appelle pareil, et chacun se voyait attribuer la
    dotation de l'autre. La référence de pièce porte maintenant
    l'identifiant du bien.

S'y ajoute une question de propriété : à qui appartient le report ? Il
naît des biens dont la dotation dépasse leur marge locative, et c'est eux
qu'il doit suivre — car il part définitivement avec le bien le jour où
celui-ci est vendu. Le répartir au prorata des dotations en donnait une
part à un bien qui n'en produisait pas, laquelle disparaissait ensuite au
détriment de celui qui l'avait produite.

Aucune donnée réelle : exploitant fictif, bases blanches, FEC construits
ici. Les scénarios chiffrés reprennent ceux du rapport.

Lancer :  pytest -q tests/test_passe_i.py
"""
import os
import shutil
import sqlite3
import subprocess
import tempfile
from urllib.parse import parse_qs, urlparse

import pytest

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import cession
import controles
import ecritures
import fiscal
import init_db
import liasse
import operations


# ── Fabriques de pièces fictives ──────────────────────────────────────────

def _base(tmp_path, nom, biens=(("Bien fictif", 20000),)):
    conn = init_db.init_blanc(str(tmp_path / nom), 2026)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Exploitant fictif','000000000','Adresse fictive')")
    for i, (libelle, prix) in enumerate(biens, start=1):
        conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) "
                     "VALUES (?,1,?,?)", (i, libelle, prix))
    cession.assurer_schema(conn)
    conn.commit()
    return conn


@pytest.fixture
def base(tmp_path):
    conn = _base(tmp_path, "fictif.db")
    yield conn
    conn.close()


_TYPES = {"1": "passif", "2": "actif", "6": "charge", "7": "produit"}


def ecrire(conn, lignes, date="2026-06-30", piece="P-1", annee=2026):
    """Une écriture fictive ; les comptes absents sont créés à la volée,
    comme le ferait la reprise d'un FEC de cabinet."""
    for numero, _d, _c in lignes:
        conn.execute(
            "INSERT OR IGNORE INTO compte(numero,libelle,type,classe) "
            "VALUES (?,?,?,?)",
            (numero, numero, _TYPES.get(numero[0], "actif"), int(numero[0])))
    conn.commit()
    ecritures.inserer(conn, journal="OD", date=date, annee=annee,
                      libelle="Fait fictif", piece_ref=piece, lignes=lignes)


def composant(conn, bien_id, libelle, valeur, duree=10,
              dms="2026-01-01", immo="218400", amort="281840"):
    conn.execute(
        "INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,"
        "date_mise_service,compte_immo,compte_amort,amortissable) "
        "VALUES (?,?,?,?,?,?,?,1)",
        (bien_id, libelle, valeur, duree, dms, immo, amort))
    conn.commit()


def loyer(conn, bien_id, montant):
    operations.saisir(conn, type="loyer", montant=montant, bien_id=bien_id,
                      date_operation="2026-03-10", periode="2026-03")


def par_bien(conn, annee=2026):
    return {v["bien_id"]: v for v in fiscal.suivi_39c_par_bien(conn, annee)}


def codes(conn, annee=2026):
    return sorted({a.code for a in controles.controler(conn, annee)})


def _scenario_dotation(conn, compte_dotation):
    """1 000 € de loyers, 2 000 € de dotation sur le compte indiqué."""
    ecrire(conn, [("708810", 0, 1000), ("108000", 1000, 0)])
    ecrire(conn, [(compte_dotation, 2000, 0), ("281840", 0, 2000)])
    return fiscal.cloturer(conn, 2026, generer_dotation=False)


# ═══ I-01 — une dotation reste une dotation, quel que soit son numéro ═══

@pytest.mark.parametrize("compte", ["681120", "6811200", "6811000"])
def test_i01_la_dotation_est_reconnue_a_sa_racine(tmp_path, compte):
    """En 6811200, la dotation tombait dans les charges ordinaires : son
    excédent devenait un DÉFICIT LMNP — imputable sur les seuls bénéfices
    de même nature et PÉRIMÉ à dix ans — au lieu d'un report 39 C, qui ne
    se périme jamais. Deux files aux règles opposées, et le montant
    changeait de file sans qu'un seul total ne bouge."""
    conn = _base(tmp_path, f"{compte}.db")
    try:
        r = _scenario_dotation(conn, compte)
        assert r["agregats"]["dotation"] == 2000.0
        assert r["agregats"]["plafond_39c"] == 1000.0
        assert r["suivi_39c"]["report_annee"] == 1000.0
        assert r["suivi_39c"]["stock_cloture"] == 1000.0
        assert r["resultat_fiscal"] == 0.0
        assert not r.get("deficit_cree")
    finally:
        conn.close()


def test_i01_la_racine_ne_deborde_pas_sur_les_provisions():
    """6815 (dotations aux PROVISIONS) n'est pas un amortissement."""
    assert fiscal.est_compte_dotation("681120")
    assert fiscal.est_compte_dotation("6811000")
    assert not fiscal.est_compte_dotation("681500")
    assert not fiscal.est_compte_dotation("686000")
    assert not fiscal.est_compte_dotation("")


# ═══ I-02 — les exclusions du plafond valent pour les subdivisions ═════

@pytest.mark.parametrize("compte", ["622610", "6226100"])
def test_i02_les_honoraires_comptables_restent_hors_plafond(tmp_path, compte):
    """La table des exclusions ne peut contenir que des comptes EXISTANTS
    (clé étrangère), donc ceux du plan livré. Les honoraires d'un cabinet
    arrivent en 6226100 : l'exclusion ne jouait pas, le plafond tombait de
    1 000 à 500 €, et 500 € passaient du déficit au report 39 C — deux
    régimes de reprise différents."""
    conn = _base(tmp_path, f"h{compte}.db")
    try:
        ecrire(conn, [("708810", 0, 1000), ("108000", 1000, 0)])
        ecrire(conn, [("681120", 2000, 0), ("281840", 0, 2000)])
        ecrire(conn, [(compte, 500, 0), ("108000", 0, 500)])
        r = fiscal.cloturer(conn, 2026, generer_dotation=False)
        assert r["agregats"]["plafond_39c"] == 1000.0
        assert r["suivi_39c"]["report_annee"] == 1000.0
        assert r["resultat_fiscal"] == -500.0        # les 500 € en déficit
    finally:
        conn.close()


def test_i02_les_racines_d_exclusion_sont_reduites(base):
    """675 est ajoutée d'office : la valeur comptable d'un élément cédé
    n'est jamais afférente à la location, même si le compte 675000 du plan
    livré est absent d'un référentiel minimal."""
    racines = fiscal.racines_hors_plafond_39c(base)
    assert "675" in racines
    assert "675000" not in racines               # la racine suffit


# ═══ I-03 — la cession se neutralise, quel que soit son numéro ═════════

@pytest.mark.parametrize("produit,vnc", [("775000", "675000"),
                                         ("7750000", "6750000")])
def test_i03_les_flux_de_cession_sont_neutralises(tmp_path, produit, vnc):
    """En LMNP la plus-value relève du régime des particuliers : le produit
    de cession est déduit du BIC, sa valeur comptable réintégrée, et ni
    l'un ni l'autre n'entre dans le plafond. Sur des comptes à sept
    chiffres, AUCUNE des deux neutralisations ne jouait : le produit de
    15 000 € gonflait le plafond comme un loyer, et 4 000 € de revenu
    imposable apparaissaient."""
    conn = _base(tmp_path, f"c{produit}.db")
    try:
        ecrire(conn, [("708810", 0, 1000), ("108000", 1000, 0)])
        ecrire(conn, [("681120", 2000, 0), ("281840", 0, 2000)])
        ecrire(conn, [("108000", 15000, 0), (produit, 0, 15000)])
        ecrire(conn, [(vnc, 10000, 0), ("218400", 0, 10000)])
        r = fiscal.cloturer(conn, 2026, generer_dotation=False)
        ag = r["agregats"]
        assert ag["produits_cession"] == 15000.0
        assert ag["vnc_cession"] == 10000.0
        assert ag["plafond_39c"] == 1000.0
        assert r["suivi_39c"]["report_annee"] == 1000.0
        assert r["resultat_fiscal"] == 0.0
    finally:
        conn.close()


# ═══ I-04 — le plafond se calcule sur les LOYERS acquis ═══════════════

def test_i04_un_produit_financier_ne_majore_pas_le_plafond(base):
    """Tous les produits de classe 7 entraient dans la base du plafond :
    1 000 € d'intérêts absorbaient immédiatement 1 000 € d'amortissement
    au lieu de les faire reporter. Le report ne se périme pas ; la
    déduction perdue, elle, ne revient jamais."""
    ecrire(base, [("708810", 0, 1000), ("108000", 1000, 0)])
    ecrire(base, [("768000", 0, 1000), ("108000", 1000, 0)])
    ecrire(base, [("681120", 2000, 0), ("281840", 0, 2000)])
    r = fiscal.cloturer(base, 2026, generer_dotation=False)
    ag = r["agregats"]
    assert ag["produits"] == 2000.0              # le produit reste un produit
    assert ag["loyers_acquis"] == 1000.0         # mais ce n'est pas un loyer
    assert ag["plafond_39c"] == 1000.0
    assert r["suivi_39c"]["report_annee"] == 1000.0
    assert r["suivi_39c"]["stock_cloture"] == 1000.0


@pytest.mark.parametrize("compte", ["768000", "775000", "781000", "791000"])
def test_i04_les_produits_hors_loyers_sont_ecartes(tmp_path, compte):
    conn = _base(tmp_path, f"p{compte}.db")
    try:
        ecrire(conn, [("708810", 0, 1000), ("108000", 1000, 0)])
        ecrire(conn, [(compte, 0, 500), ("108000", 500, 0)])
        assert fiscal.agregats(conn, 2026)["plafond_39c"] == 1000.0
    finally:
        conn.close()


def test_i04_un_vrai_loyer_majore_bien_le_plafond(base):
    """Contre-épreuve : la restriction ne doit pas amputer les loyers."""
    ecrire(base, [("708810", 0, 1000), ("108000", 1000, 0)])
    ecrire(base, [("706000", 0, 500), ("108000", 500, 0)])
    assert fiscal.agregats(base, 2026)["plafond_39c"] == 1500.0


# ═══ I-05 — le report suit le bien qui le produit ═════════════════════

def test_i05_le_report_va_au_bien_en_insuffisance(tmp_path):
    """A (10 000 €, dotation 1 000 €) encaisse 2 000 € de loyers : il
    couvre sa dotation et ne produit aucun report. B (30 000 €, dotation
    3 000 €) n'encaisse que 1 000 €. Réparti au prorata des dotations, le
    report de 1 000 € donnait pourtant 250 € à A."""
    conn = _base(tmp_path, "i05.db", [("A", 10000), ("B", 30000)])
    try:
        composant(conn, 1, "cA", 10000)
        composant(conn, 2, "cB", 30000)
        loyer(conn, 1, 2000)
        loyer(conn, 2, 1000)
        r = fiscal.cloturer(conn, 2026)
        assert r["suivi_39c"]["report_annee"] == 1000.0
        pb = par_bien(conn)
        assert pb[1]["report_bien"] == 0.0
        assert pb[2]["report_bien"] == 1000.0
    finally:
        conn.close()


def test_i05_la_cession_d_un_bien_couvert_n_emporte_rien(tmp_path):
    """Conséquence : A cédé n'emporte rien, et les 1 000 € de B restent."""
    conn = _base(tmp_path, "i05b.db", [("A", 10000), ("B", 30000)])
    try:
        composant(conn, 1, "cA", 10000)
        composant(conn, 2, "cB", 30000)
        loyer(conn, 1, 2000)
        loyer(conn, 2, 1000)
        cession.ceder_bien(conn, 1, "2026-12-31", 10000)
        r = fiscal.cloturer(conn, 2026)
        pb = par_bien(conn)
        assert pb[1]["sortie_bien"] == 0.0
        assert pb[2]["stock_cloture"] == 1000.0
        assert r["suivi_39c"]["stock_cloture"] == 1000.0
    finally:
        conn.close()


def test_i05_sans_operations_on_retombe_sur_les_dotations(tmp_path):
    """Un historique repris d'un FEC n'a pas d'opérations : aucune marge
    n'est connue, et la répartition par dotations reste le seul repli."""
    conn = _base(tmp_path, "i05c.db", [("A", 10000), ("B", 30000)])
    try:
        composant(conn, 1, "cA", 10000)
        composant(conn, 2, "cB", 30000)
        ecrire(conn, [("708810", 0, 1000), ("108000", 1000, 0)])
        fiscal.cloturer(conn, 2026)
        pb = par_bien(conn)
        assert pb[1]["report_bien"] > 0 and pb[2]["report_bien"] > 0
        assert round(pb[1]["report_bien"] + pb[2]["report_bien"], 2) == 3000.0
    finally:
        conn.close()


# ═══ I-06 — un bien s'identifie, il ne se décrit pas ═════════════════

@pytest.mark.parametrize("libelles", [("cA", "cB", "cC"),
                                      ("Mobilier fictif",) * 3])
def test_i06_les_libelles_ne_changent_pas_les_montants(tmp_path, libelles):
    """Trois biens de 10 000, 20 000 et 30 000 €, A et B cédés. La dotation
    de cession d'un bien était retrouvée en comparant le LIBELLÉ des
    lignes au libellé de ses composants : avec trois composants nommés
    pareil, chaque bien cédé recevait la dotation des trois, et 1 000 € de
    stock conservé disparaissaient — pour un simple choix de mots."""
    conn = _base(tmp_path, f"i06{len(set(libelles))}.db",
                 [("A", 10000), ("B", 20000), ("C", 30000)])
    try:
        for i, (valeur, lib) in enumerate(zip((10000, 20000, 30000),
                                              libelles), start=1):
            composant(conn, i, lib, valeur)
        cession.ceder_bien(conn, 1, "2026-12-31", 10000)
        cession.ceder_bien(conn, 2, "2026-12-31", 20000)
        r = fiscal.cloturer(conn, 2026)
        pb = par_bien(conn)
        assert [round(pb[i]["dotation_bien"], 2) for i in (1, 2, 3)] \
            == [1000.0, 2000.0, 3000.0]
        assert r["suivi_39c"]["sorties_39c"] == 3000.0
        assert pb[3]["stock_cloture"] == 3000.0
    finally:
        conn.close()


def test_i06_la_piece_de_cession_porte_l_identifiant_du_bien(base):
    composant(base, 1, "Mobilier fictif", 12000)
    cession.ceder_bien(base, 1, "2026-12-31", 12000)
    pieces = {r[0] for r in base.execute(
        "SELECT piece_ref FROM ecriture WHERE exercice_annee=2026")}
    assert "DAA-CESSION-1" in pieces
    assert "CESSION-1" in pieces


# ═══ I-07 / I-08 — un stock sans propriétaire se dit ═════════════════

def _historique(conn, annee, stock):
    conn.execute("INSERT INTO exercice(annee,date_debut,date_fin,statut) "
                 "VALUES (?,?,?,'clos')",
                 (annee, f"{annee}-01-01", f"{annee}-12-31"))
    conn.execute("INSERT INTO suivi_39c(exercice_annee,stock_cloture) "
                 "VALUES (?,?)", (annee, stock))
    conn.commit()


def test_i07_le_stock_sans_detail_ne_part_pas_avec_un_bien_cede(tmp_path):
    """Dossier migré : stock global de 5 000 € en 2025, aucune ventilation.
    Le repli portait tout sur « le bien le plus ancien », sans regarder
    s'il était CÉDÉ — 6 000 € sortaient donc du suivi dès la clôture
    suivante, dont 1 000 € de report produits par le seul bien actif."""
    conn = _base(tmp_path, "i07.db", [("A", 10000), ("B", 10000)])
    try:
        _historique(conn, 2025, 5000)
        conn.execute("UPDATE bien SET date_cession='2025-12-31' WHERE id=1")
        composant(conn, 2, "cB", 10000)
        ecrire(conn, [("681120", 1000, 0), ("281840", 0, 1000)],
               date="2026-12-31", piece="DAA")
        assert "VENTILATION_39C" in codes(conn)
        r = fiscal.cloturer(conn, 2026, generer_dotation=False)
        pb = par_bien(conn)
        assert pb[1]["sortie_bien"] == 0.0          # rien ne sort du néant
        assert pb[2]["stock_cloture"] == 6000.0     # 5 000 hérités + 1 000
        assert r["suivi_39c"]["stock_cloture"] == 6000.0
    finally:
        conn.close()


def test_i08_le_detail_suit_le_millesime_du_stock_global(tmp_path):
    """Détail par bien en 2024 (2 × 1 000 €), stock global en 2025
    (5 000 €). Le détail du dernier exercice VENTILÉ était lu quel qu'il
    soit : les deux suivis partaient de millésimes différents, et 3 000 €
    n'avaient tout simplement pas de propriétaire — sans alerte."""
    conn = _base(tmp_path, "i08.db", [("A", 10000), ("B", 10000)])
    try:
        _historique(conn, 2024, 2000)
        _historique(conn, 2025, 5000)
        fiscal._table_39c_bien(conn)
        for b in (1, 2):
            conn.execute("INSERT INTO suivi_39c_bien(exercice_annee,bien_id,"
                         "stock_cloture) VALUES (2024,?,1000)", (b,))
        conn.commit()
        loyer(conn, 1, 1000)
        assert "VENTILATION_39C" in codes(conn)
        r = fiscal.cloturer(conn, 2026, generer_dotation=False)
        s, pb = r["suivi_39c"], par_bien(conn)
        assert s["stock_ouverture"] == 5000.0
        assert round(sum(v["stock_ouverture"] for v in pb.values()), 2) == 5000.0
        assert round(sum(v["utilisation_bien"] for v in pb.values()), 2) \
            == s["utilisation_annee"]
        assert round(sum(v["stock_cloture"] for v in pb.values()), 2) \
            == s["stock_cloture"] == 4000.0
    finally:
        conn.close()


def test_i08_un_dossier_ventile_ne_declenche_pas_l_alerte(tmp_path):
    """Contre-épreuve : quand le détail concorde, rien n'est signalé."""
    conn = _base(tmp_path, "i08b.db", [("A", 10000), ("B", 10000)])
    try:
        _historique(conn, 2025, 2000)
        fiscal._table_39c_bien(conn)
        for b in (1, 2):
            conn.execute("INSERT INTO suivi_39c_bien(exercice_annee,bien_id,"
                         "stock_cloture) VALUES (2025,?,1000)", (b,))
        conn.commit()
        assert "VENTILATION_39C" not in codes(conn)
    finally:
        conn.close()


# ═══ I-09 — une part de répartition n'est jamais négative ════════════

def test_i09_quatre_biens_deux_centimes(tmp_path):
    """L'ajustement portait sur la DERNIÈRE part, à qui l'on donnait le
    reste : quand les arrondis précédents dépassaient déjà le total, ce
    reste était négatif. Une reprise de −0,01 € était enregistrée, et la
    somme des stocks locaux dépassait le global d'un centime."""
    conn = _base(tmp_path, "i09.db", [(f"B{i}", 10) for i in range(1, 5)])
    try:
        for i in range(1, 5):
            composant(conn, i, f"c{i}", 10)
        loyer(conn, 1, 3.98)
        r = fiscal.cloturer(conn, 2026)
        pb = par_bien(conn)
        assert all(v["report_bien"] >= 0 for v in pb.values())
        assert all(v["utilisation_bien"] >= 0 for v in pb.values())
        assert all(v["stock_cloture"] >= 0 for v in pb.values())
        assert round(sum(v["report_bien"] for v in pb.values()), 2) \
            == r["suivi_39c"]["report_annee"]
        assert round(sum(v["stock_cloture"] for v in pb.values()), 2) \
            == r["suivi_39c"]["stock_cloture"]
    finally:
        conn.close()


@pytest.mark.parametrize("total,poids", [
    (0.02, {1: 1, 2: 1, 3: 1, 4: 1}),
    (0.01, {1: 5, 2: 5}),
    (100.0, {1: 1, 2: 2, 3: 7}),
    (0.03, {1: 0, 2: 1, 3: 1}),
])
def test_i09_la_repartition_conserve_et_ne_va_jamais_sous_zero(total, poids):
    parts = fiscal._repartir(total, poids)
    assert round(sum(parts.values()), 2) == total
    assert all(p >= 0 for p in parts.values())


def test_i09_la_repartition_bornee_conserve_aussi():
    """L'utilisation était répartie librement puis rabotée bien par bien :
    le total reparti n'était plus le total global."""
    parts = fiscal._repartir_borne(100.0, {1: 1, 2: 1},
                                   plafonds={1: 10.0, 2: 200.0})
    assert parts[1] == 10.0
    assert round(sum(parts.values()), 2) == 100.0


# ═══ I-10 — l'avertissement agit AVANT de figer l'exercice ══════════

def _dossier_web(tmp_path, nom):
    chemin = str(tmp_path / nom)
    conn = init_db.init_blanc(chemin, 2026)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Exploitant fictif','000000000','Adresse fictive')")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) "
                 "VALUES (1,1,'Bien fictif',12000)")
    conn.execute(
        "INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,"
        "date_mise_service,compte_immo,compte_amort,amortissable) "
        "VALUES (1,'Mobilier fictif',12000,10,'2026-01-01','218400',"
        "'281840',1)")
    conn.commit()
    operations.saisir(conn, type="loyer", montant=200, bien_id=1,
                      date_operation="2026-03-10", periode="2026-03")
    conn.close()
    return chemin


def _cloturer_web(monkeypatch, chemin, forcer=""):
    import app as web
    monkeypatch.setattr(web, "_db_path", lambda *a, **k: chemin)
    monkeypatch.setattr(web, "_en_bac_a_sable", lambda *a, **k: True)
    with web.app.test_request_context("/", method="POST", data={
            "annee": "2026", "retraitements": "1000", "forcer": forcer}):
        reponse = web.cloturer()
    return parse_qs(urlparse(reponse.location).query)


def test_i10_le_retraitement_saisi_est_examine_avant_la_cloture(tmp_path,
                                                                monkeypatch):
    """Le contrôle ne lisait que les retraitements DÉJÀ enregistrés : il ne
    pouvait parler qu'après coup, sur un exercice déjà figé. Or 1 000 €
    saisis ici majorent le plafond de 200 à 1 200 € et font disparaître le
    report de 1 000 € — sans que le résultat fiscal immédiat ne bouge,
    donc sans que rien ne se voie."""
    chemin = _dossier_web(tmp_path, "i10.db")
    query = _cloturer_web(monkeypatch, chemin)
    assert "ok" not in query
    assert "PLAFOND" in query["warn"][0]
    verif = sqlite3.connect(chemin)
    try:
        assert verif.execute("SELECT statut FROM exercice WHERE annee=2026"
                             ).fetchone()[0] == "ouvert"
        assert verif.execute("SELECT COUNT(*) FROM suivi_39c").fetchone()[0] == 0
    finally:
        verif.close()


def test_i10_la_confirmation_explicite_reste_possible(tmp_path, monkeypatch):
    """L'avertissement informe, il n'interdit pas : un retraitement manuel
    légitime — le fonds ALUR du calage — doit rester praticable."""
    chemin = _dossier_web(tmp_path, "i10b.db")
    query = _cloturer_web(monkeypatch, chemin, forcer="1")
    assert "clôturé" in query["ok"][0]
    verif = sqlite3.connect(chemin)
    try:
        assert verif.execute("SELECT statut FROM exercice WHERE annee=2026"
                             ).fetchone()[0] == "clos"
    finally:
        verif.close()


def test_i10_une_cloture_sans_retraitement_passe_sans_avertissement(tmp_path,
                                                                    monkeypatch):
    import app as web
    chemin = _dossier_web(tmp_path, "i10c.db")
    monkeypatch.setattr(web, "_db_path", lambda *a, **k: chemin)
    monkeypatch.setattr(web, "_en_bac_a_sable", lambda *a, **k: True)
    with web.app.test_request_context("/", method="POST",
                                      data={"annee": "2026"}):
        reponse = web.cloturer()
    assert "ok" in parse_qs(urlparse(reponse.location).query)


# ═══ I-11 — l'état archivable se réconcilie ═════════════════════════

@pytest.mark.skipif(shutil.which("pdftotext") is None,
                    reason="pdftotext absent : le texte du PDF ne peut pas "
                           "être extrait pour vérification")
def test_i11_la_sortie_de_stock_figure_dans_le_pdf_mono_bien(tmp_path):
    """5 000 + 1 200 − 0 − 6 200 = 0. Seule la ligne de SORTIE manquait au
    tableau imprimé — elle ne vivait que dans le détail par bien, lequel
    n'est affiché qu'à partir de deux biens. Le lecteur d'un état
    archivable voyait donc un tableau qui ne tombe pas juste, et 6 200 €
    de mouvement sans explication."""
    import liasse_pdf
    conn = _base(tmp_path, "i11.db")
    try:
        _historique(conn, 2025, 5000)
        composant(conn, 1, "Mobilier fictif", 12000)
        ecrire(conn, [("218400", 12000, 0), ("108000", 0, 12000)],
               date="2026-01-01", piece="ACQ")
        cession.ceder_bien(conn, 1, "2026-12-31", 12000)
        r = fiscal.cloturer(conn, 2026, generer_dotation=False)
        assert r["suivi_39c"]["sorties_39c"] == 6200.0
        assert liasse.suivi_reports(conn, 2026)["sortie_39c"] == 6200.0
        pdf = str(tmp_path / "liasse.pdf")
        liasse_pdf.generer_pdf(liasse.generer(conn, 2026), pdf)
        texte = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                               capture_output=True, text=True,
                               timeout=60).stdout
        assert "Stock sorti avec un bien cédé" in texte
        assert "6 200,00" in texte
    finally:
        conn.close()


def test_i11_le_tableau_ordinaire_reste_sans_ligne_de_sortie(base):
    """Contre-épreuve : la ligne n'apparaît que s'il y a une sortie."""
    composant(base, 1, "Mobilier fictif", 12000)
    loyer(base, 1, 5000)
    fiscal.cloturer(base, 2026)
    assert liasse.suivi_reports(base, 2026)["sortie_39c"] == 0.0


# ═══ Ce qui tenait doit continuer de tenir ═════════════════════════

def test_le_scenario_ordinaire_est_inchange(base):
    """Un dossier mono-bien ordinaire : loyers, charge afférente, charge de
    structure. Aucun des correctifs ne doit déplacer ces chiffres."""
    ecrire(base, [("708810", 0, 10000), ("108000", 10000, 0)])
    ecrire(base, [("615200", 2000, 0), ("108000", 0, 2000)])   # afférente
    ecrire(base, [("622610", 300, 0), ("108000", 0, 300)])     # structure
    ecrire(base, [("681120", 9000, 0), ("281840", 0, 9000)])
    ag = fiscal.agregats(base, 2026)
    assert ag["loyers_acquis"] == 10000.0
    assert ag["charges_afferentes"] == 2000.0
    assert ag["plafond_39c"] == 8000.0
    r = fiscal.cloturer(base, 2026, generer_dotation=False)
    assert r["suivi_39c"]["report_annee"] == 1000.0
    assert r["resultat_fiscal"] == -300.0


def test_les_deux_files_restent_distinctes(base):
    """Report 39 C et déficit LMNP ne se confondent jamais : le premier ne
    se périme pas, le second oui."""
    ecrire(base, [("708810", 0, 1000), ("108000", 1000, 0)])
    ecrire(base, [("615200", 500, 0), ("108000", 0, 500)])    # afférente
    ecrire(base, [("622610", 500, 0), ("108000", 0, 500)])    # de structure
    ecrire(base, [("681120", 2000, 0), ("281840", 0, 2000)])
    r = fiscal.cloturer(base, 2026, generer_dotation=False)
    # Plafond 1 000 − 500 = 500 ; dotation 2 000 ⇒ 1 500 € REPORTÉS, sans
    # terme. Le résultat comptable (−2 000) majoré du report réintégré
    # laisse −500 € : un DÉFICIT, lui périssable à dix ans. La charge de
    # structure creuse le déficit sans toucher au plafond — c'est
    # exactement ce qui sépare les deux files.
    assert r["suivi_39c"]["stock_cloture"] == 1500.0
    assert r["resultat_fiscal"] == -500.0


def test_le_moteur_39c_conserve_toujours(base):
    """Invariant du moteur : ouverture + report − utilisation = clôture."""
    for ouverture, dotation, plafond in [(0, 1200, 500), (5000, 1200, 1500),
                                         (5000, 0, 1500), (5000, 1200, -300)]:
        s = fiscal.calculer_39c(ouverture, dotation, plafond)
        assert round(s["stock_ouverture"] + s["report_annee"]
                     - s["utilisation_annee"], 2) == s["stock_cloture"]
        assert s["stock_cloture"] >= 0
        assert 0 <= s["report_annee"] <= dotation + 0.005


def test_dossier_temporaire_nettoye():
    """Garde-fou de la suite elle-même : ces tests n'écrivent que dans le
    tmp_path de pytest, jamais à côté des fichiers du projet."""
    assert not os.path.exists(os.path.join(tempfile.gettempdir(), "fictif.db"))
