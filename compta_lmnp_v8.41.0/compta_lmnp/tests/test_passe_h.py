# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Non-régression des constats de la passe H (amortissements par composants).

Le fil rouge de cette passe est la CONFUSION ENTRE LE PLAN ET LES COMPTES.
Le plan théorique était recalculé à neuf depuis la durée actuelle du
composant, puis appliqué comme s'il décrivait ce qui avait été comptabilisé
— alors qu'une durée modifiée, une dotation saisie à la main ou un
historique repris en à-nouveaux le démentent. De là venaient le
dépassement de la valeur brute, le double amortissement d'un exercice, et
la réécriture des tableaux d'un exercice déjà clos.

Le principe retenu, et que ces tests figent :

  - **le plan est une cible, la comptabilité en est la mesure.** La
    dotation d'un exercice est ce qu'il faut écrire pour rejoindre le
    plan, jamais davantage que l'annuité qu'il prévoit ;
  - **un actif ne s'amortit jamais au-delà de ce qu'il a coûté**, quelle
    que soit la façon dont les comptes sont partagés ;
  - **un retard se constate, il ne se rattrape pas tout seul** —
    l'article 39 B du CGI tient l'amortissement insuffisant pour
    définitivement perdu ;
  - **ce qui a été arrêté à une clôture reste arrêté.**

Aucune donnée réelle : exploitant fictif, base blanche, composants créés
ici. Les fixtures qui passent par SQL sont identifiées comme telles.

Lancer :  pytest -q tests/test_passe_h.py
"""
import sqlite3
import tempfile
from urllib.parse import parse_qs, urlparse

import pytest

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import amortissement
import controles
import ecritures
import fiscal
import init_db
import liasse
import operations
import plan_immo
import reprise


# ── Fabriques de pièces fictives ──────────────────────────────────────────

@pytest.fixture
def base(tmp_path):
    """Base BLANCHE, exercice 2026 ouvert, exploitant et bien fictifs."""
    conn = init_db.init_blanc(str(tmp_path / "fictif.db"), 2026)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Exploitant fictif','000000000','Adresse fictive')")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) "
                 "VALUES (1,1,'Bien fictif',12000)")
    conn.commit()
    yield conn
    conn.close()


def prix_du_bien(conn, montant):
    conn.execute("UPDATE bien SET prix_total=?", (montant,))
    conn.commit()


def composant(conn, libelle, valeur, duree, compte_immo, compte_amort,
              dms="2026-01-01"):
    """Crée un composant. Les comptes absents du plan livré sont créés à la
    volée, comme le ferait la reprise d'un FEC de cabinet."""
    for numero, type_ in ((compte_immo, "actif"),
                          (compte_amort, "amortissement")):
        conn.execute("INSERT OR IGNORE INTO compte(numero,libelle,type,classe)"
                     " VALUES (?,?,?,2)", (numero, numero, type_))
    conn.execute(
        "INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,"
        "date_mise_service,compte_immo,compte_amort,amortissable) "
        "VALUES (1,?,?,?,?,?,?,1)",
        (libelle, valeur, duree, dms, compte_immo, compte_amort))
    conn.commit()


def acquisition(conn, compte_immo, montant):
    ecritures.inserer(conn, journal="OD", date="2026-01-01", annee=2026,
                      libelle="Acquisition", piece_ref="ACQ",
                      lignes=[(compte_immo, montant, 0.0),
                              ("108000", 0.0, montant)])


def dotation_manuelle(conn, compte_amort, montant, date="2026-06-30"):
    """Une OD passée à la main, hors du circuit de clôture."""
    ecritures.inserer(conn, journal="OD", date=date, annee=2026,
                      libelle="Dotation saisie à la main", piece_ref="MANUEL",
                      lignes=[("681120", montant, 0.0),
                              (compte_amort, 0.0, montant)])


def cumul(conn, compte, annee):
    """Solde du compte DANS l'exercice — les à-nouveaux le reportent d'une
    année sur l'autre, sommer tous les exercices le doublerait."""
    return round(conn.execute(
        "SELECT COALESCE(SUM(l.credit - l.debit),0) FROM ligne l "
        "JOIN ecriture e ON e.id = l.ecriture_id "
        "WHERE l.compte_num=? AND e.exercice_annee=?",
        (compte, annee)).fetchone()[0], 2)


def ouvrir_exercice_suivant(conn, annee):
    """Ouvre `annee` et y reporte les à-nouveaux de l'exercice précédent."""
    conn.execute("INSERT INTO exercice(annee,date_debut,date_fin,statut) "
                 "VALUES (?,?,?,'ouvert')",
                 (annee, f"{annee}-01-01", f"{annee}-12-31"))
    reprise._construire_an_depuis_balance(
        conn, reprise.lire_balance_interne(conn, annee - 1), annee)


def codes(conn, annee):
    return sorted({a.code for a in controles.controler(conn, annee)})


# ═══ H-01 — le partage d'un compte ne désactive plus le plafonnement ════

def test_h01_deux_composants_sur_un_meme_compte_ne_depassent_pas_le_brut(base):
    """Deux composants de 8 000 € sur 281840, cinq ans, puis durée portée à
    huit ans en 2029. Le plafonnement ne savait raisonner que par composant
    et renonçait dès qu'un compte était partagé — précisément le cas des
    trois postes de bâtiment de la ventilation indicative. Résultat mesuré
    par l'audit : 19 600 € d'amortissements pour 16 000 € de valeur brute.
    """
    prix_du_bien(base, 16000)
    composant(base, "A", 8000, 5, "218400", "281840")
    composant(base, "B", 8000, 5, "218400", "281840")
    acquisition(base, "218400", 16000)
    for annee in range(2026, 2034):
        if annee == 2029:
            base.execute("UPDATE composant SET duree_annees=8")
            base.commit()
        if annee > 2026:
            ouvrir_exercice_suivant(base, annee)
        fiscal.cloturer(base, annee)
        assert cumul(base, "281840", annee) <= 16000.0 + 0.005, annee
    assert cumul(base, "281840", 2033) == 16000.0     # ni plus, ni moins


def test_h01_la_vnc_comptable_ne_devient_jamais_negative(base):
    prix_du_bien(base, 16000)
    composant(base, "A", 8000, 5, "218400", "281840")
    composant(base, "B", 8000, 5, "218400", "281840")
    acquisition(base, "218400", 16000)
    fiscal.cloturer(base, 2026)
    for annee in range(2027, 2032):
        ouvrir_exercice_suivant(base, annee)
        base.execute("UPDATE composant SET duree_annees=8")
        base.commit()
        fiscal.cloturer(base, annee)
        # 218400 est un compte d'ACTIF : son solde débiteur ressort négatif
        # de `cumul()`, qui mesure crédit − débit. La valeur nette est donc
        # le brut moins le cumul d'amortissement, et elle ne peut pas
        # devenir négative — c'était tout l'effet du constat.
        brut = -cumul(base, "218400", annee)
        assert round(brut - cumul(base, "281840", annee), 2) >= -0.005


# ═══ H-02 — l'historique de l'exercice courant est vu ══════════════════

def test_h02_une_dotation_manuelle_n_en_fait_pas_generer_une_seconde(base):
    """1 200 € déjà passés à la main, puis clôture normale. La génération
    cherchait une pièce OD « DAA » et ne voyait pas la dotation NETTE déjà
    présente : elle en ajoutait une seconde. Le revenu imposable tombait à
    zéro au lieu de 600 €, avec 600 € de report 39 C indu."""
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    acquisition(base, "218400", 12000)
    dotation_manuelle(base, "281840", 1200)
    operations.saisir(base, type="loyer", montant=1800, periode="2026-03",
                      date_operation="2026-03-10")
    r = fiscal.cloturer(base, 2026)
    assert cumul(base, "281840", 2026) == 1200.0      # et non 2400
    assert r["revenu_imposable"] == 600.0
    assert r["suivi_39c"]["stock_cloture"] == 0.0


def test_h02_dotation_manuelle_complete_ne_double_pas_la_valeur_brute(base):
    """Variante : composant d'un an, déjà doté manuellement de 12 000 €.
    L'audit mesurait 24 000 € en compte pour 12 000 € de brut."""
    composant(base, "Mobilier", 12000, 1, "218400", "281840")
    acquisition(base, "218400", 12000)
    dotation_manuelle(base, "281840", 12000)
    fiscal.cloturer(base, 2026)
    assert cumul(base, "281840", 2026) == 12000.0


def test_h02_amortissements_repris_en_a_nouveaux_sont_vus(base):
    """Premier exercice du dossier, 8 000 € d'amortissements repris en AN
    pour un composant de 8 000 €. Le cumul était lu sur le dernier exercice
    CLOS — il n'y en avait aucun — donc tenu pour nul, et la clôture
    ajoutait une annuité de plus par-dessus un actif déjà intégralement
    amorti."""
    prix_du_bien(base, 8000)
    composant(base, "Bati", 8000, 8, "213150", "281315", dms="2025-01-01")
    ecritures.inserer(base, journal="AN", date="2026-01-01", annee=2026,
                      libelle="A-nouveaux", piece_ref="AN",
                      lignes=[("213150", 8000, 0.0), ("281315", 0.0, 8000)])
    fiscal.cloturer(base, 2026)
    assert cumul(base, "281315", 2026) == 8000.0      # et non 9000


def test_h02_la_cloture_ordinaire_dote_toujours(base):
    """Contre-épreuve : sans rien de déjà passé, la dotation reste due."""
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    acquisition(base, "218400", 12000)
    fiscal.cloturer(base, 2026)
    assert cumul(base, "281840", 2026) == 1200.0


def test_h02_les_deux_lectures_du_moteur_sont_distinctes(base):
    """« Ce que le plan prévoit » et « ce qu'il reste à écrire » se
    séparent une fois la dotation passée — les confondre faisait rendre au
    contrôle un écart imaginaire après chaque clôture."""
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    acquisition(base, "218400", 12000)
    avant = amortissement.dotations_exercice(base, 2026)
    reste = amortissement.dotations_exercice(base, 2026, a_comptabiliser=True)
    assert [d["dotation"] for d in avant] == [d["dotation"] for d in reste]
    fiscal.cloturer(base, 2026)
    assert amortissement.dotations_exercice(base, 2026)[0]["dotation"] == 1200.0
    assert amortissement.dotations_exercice(
        base, 2026, a_comptabiliser=True) == []


# ═══ H-03 — une contre-passation est un fait comptable ════════════════

def test_h03_dotation_contre_passee_signalee_et_reprenable(base):
    """La DAA générée puis inversée laissait un effet net nul. Le contrôle
    ne totalisait que les DÉBITS de 681120 : il ne voyait rien. Et le
    verrou anti-doublon, qui ne regardait que la présence de la pièce,
    interdisait définitivement de refaire la dotation."""
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    acquisition(base, "218400", 12000)
    amortissement.generer_cloture(base, 2026)
    ecritures.inserer(base, journal="OD", date="2026-12-31", annee=2026,
                      libelle="Annulation de la DAA", piece_ref="INVERSE",
                      lignes=[("281840", 1200, 0.0), ("681120", 0.0, 1200)])
    assert "DOTATION_ANNULEE" in codes(base, 2026)
    r = amortissement.generer_cloture(base, 2026)     # plus de blocage
    assert r["total"] == 1200.0


def test_h03_pas_de_faux_double_amortissement(base):
    """Inverse : une dotation erronée proprement annulée, puis refaite.
    Le contrôle totalisait 24 000 € de débits pour un effet net de
    12 000 € et accusait un double amortissement inexistant."""
    composant(base, "Mobilier", 12000, 1, "218400", "281840")
    acquisition(base, "218400", 12000)
    dotation_manuelle(base, "281840", 12000, date="2026-06-30")
    ecritures.inserer(base, journal="OD", date="2026-07-01", annee=2026,
                      libelle="Annulation", piece_ref="INVERSE",
                      lignes=[("281840", 12000, 0.0), ("681120", 0.0, 12000)])
    dotation_manuelle(base, "281840", 12000, date="2026-12-31")
    assert "DOTATION_PLAN" not in codes(base, 2026)


def test_h03_le_verrou_anti_doublon_tient_toujours(base):
    """Contre-épreuve : une DAA bien vivante reste non reproductible."""
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    acquisition(base, "218400", 12000)
    amortissement.generer_cloture(base, 2026)
    with pytest.raises(ValueError, match="déjà générée"):
        amortissement.generer_cloture(base, 2026)


# ═══ H-04 / H-06 — un écart de cumul ne peut plus passer inaperçu ═════

def test_h04_omission_de_dotation_signalee_apres_cloture(base):
    """Clôture par l'option sans génération : les contrôles rendaient une
    liste vide sur un exercice clos où 1 200 € de minimum n'avaient pas été
    pratiqués. L'écart n'apparaissait que dans la liasse."""
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    acquisition(base, "218400", 12000)
    fiscal.cloturer(base, 2026, generer_dotation=False)
    anomalies = [a for a in controles.controler(base, 2026)
                 if a.code.startswith("AMORT_CUMUL")]
    assert anomalies, "l'omission du minimum d'amortissement doit se voir"
    assert "39 B" in anomalies[0].message


def test_h04_un_exercice_encore_ouvert_n_est_pas_accuse(base):
    """La dotation d'un exercice ouvert reste à venir : la signaler comme
    un retard crierait sur tout dossier en cours de saisie."""
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    acquisition(base, "218400", 12000)
    assert not [a for a in controles.controler(base, 2026)
                if a.code.startswith("AMORT_CUMUL")]


def test_h06_duree_raccourcie_plan_epuise_et_vnc_restante(base):
    """Durée ramenée de huit à quatre ans après 3 000 € amortis. Le plan
    s'achevait en laissant 3 000 € de valeur nette qu'aucune dotation ne
    viendrait plus jamais reprendre, et l'écart était présenté comme une
    reprise d'historique manquante."""
    prix_du_bien(base, 8000)
    composant(base, "Bati", 8000, 8, "213150", "281315")
    acquisition(base, "213150", 8000)
    for annee in (2026, 2027, 2028):
        if annee > 2026:
            ouvrir_exercice_suivant(base, annee)
        fiscal.cloturer(base, annee)
    assert cumul(base, "281315", 2028) == 3000.0
    ouvrir_exercice_suivant(base, 2029)
    base.execute("UPDATE composant SET duree_annees=4")
    base.commit()
    fiscal.cloturer(base, 2029)
    ouvrir_exercice_suivant(base, 2030)
    bloquants = [a for a in controles.controler(base, 2030)
                 if a.code == "AMORT_CUMUL_FIN"]
    assert bloquants, "un plan épuisé sur une VNC restante doit bloquer"
    assert bloquants[0].niveau == controles.BLOQUANT
    assert "ÉPUISÉ" in bloquants[0].message


def test_h04_un_retard_n_est_jamais_rattrape_d_office(base):
    """L'article 39 B tient l'amortissement insuffisant pour
    irrégulièrement différé, donc définitivement perdu : le moteur ne doit
    pas le déduire l'année suivante. Il le signale, il ne le répare pas."""
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    acquisition(base, "218400", 12000)
    fiscal.cloturer(base, 2026, generer_dotation=False)
    ouvrir_exercice_suivant(base, 2027)
    dotations = amortissement.dotations_exercice(base, 2027,
                                                 a_comptabiliser=True)
    assert [d["dotation"] for d in dotations] == [1200.0]   # et non 2400


def test_h04_un_historique_absent_de_la_base_n_est_pas_une_omission(base):
    """Un dossier repris à partir de 2026 pour un bien mis en service en
    2020 ne contient pas ses exercices antérieurs. Conclure à six années
    omises — et les rattraper — serait faux."""
    composant(base, "Bati", 100000, 30, "213150", "281315", dms="2020-01-01")
    dotations = amortissement.dotations_exercice(base, 2026,
                                                 a_comptabiliser=True)
    assert dotations[0]["dotation"] == pytest.approx(100000 / 30, abs=0.01)
    assert not [a for a in controles.controler(base, 2026)
                if a.code.startswith("AMORT_CUMUL")]


# ═══ H-05 — ce qui a été arrêté à une clôture reste arrêté ═══════════

def test_h05_modifier_une_duree_ne_reecrit_pas_un_exercice_clos(base):
    """Le 2033-C était reconstruit depuis la durée ACTUELLE du composant :
    passer de dix à vingt ans faisait tomber la dotation de 2026 — exercice
    CLOS — de 1 200 € à 600 €, cependant que le bilan et le FEC, eux, ne
    bougeaient pas."""
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    acquisition(base, "218400", 12000)
    fiscal.cloturer(base, 2026)
    avant = liasse.immobilisations_2033c(base, 2026)["totaux"]
    base.execute("UPDATE composant SET duree_annees=20")
    base.commit()
    apres = liasse.immobilisations_2033c(base, 2026)["totaux"]
    assert avant["dotation"] == apres["dotation"] == 1200.0
    assert avant["amort_fin"] == apres["amort_fin"] == 1200.0


def test_h05_un_exercice_sans_trace_reste_calcule(base):
    """Contre-épreuve : sans clôture, aucune trace — le tableau se calcule
    depuis le plan, comme avant."""
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    acquisition(base, "218400", 12000)
    assert liasse.immobilisations_2033c(base, 2026)["totaux"]["dotation"] \
        == 1200.0


# ═══ H-07 — une durée d'amortissement est un entier positif ═══════════

@pytest.mark.parametrize("saisie,motif", [
    ("-1", "négative"),
    ("abc", "invalide"),
    ("500", "120 ans"),
])
def test_h07_durees_impossibles_refusees(saisie, motif):
    with pytest.raises(ValueError, match=motif):
        amortissement.duree_valide(saisie)


@pytest.mark.parametrize("saisie,attendu", [
    ("", None), ("0", None), ("10", 10), (" 25 ", 25), ("50", 50),
])
def test_h07_durees_usuelles_acceptees(saisie, attendu):
    assert amortissement.duree_valide(saisie) == attendu


def test_h07_la_route_web_refuse_la_duree_negative(tmp_path, monkeypatch):
    """La véritable route créait le composant `amortissable=1` avec un plan
    impossible, comptabilisait son acquisition de 12 000 €, ne générait
    jamais aucune dotation, et le 2033-C affichait −12 000 €."""
    import app as web
    chemin = str(tmp_path / "web.db")
    conn = init_db.init_blanc(chemin, 2026)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Exploitant fictif','000000000','Adresse fictive')")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) "
                 "VALUES (1,1,'Bien fictif',12000)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(web, "_db_path", lambda *a, **k: chemin)
    with web.app.test_request_context("/", method="POST", data={
            "bien_id": "1", "libelle": "Composant fictif",
            "valeur_brute": "12000", "duree_annees": "-1",
            "compte_immo": "218400", "date_mise_service": "2026-01-01",
            "annee": "2026"}):
        reponse = web.creer_composant()
    query = parse_qs(urlparse(reponse.location).query)
    assert "ok" not in query
    assert "négative" in query["err"][0]
    verif = sqlite3.connect(chemin)
    try:
        assert verif.execute("SELECT COUNT(*) FROM composant").fetchone()[0] == 0
        assert verif.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] == 0
    finally:
        verif.close()


def test_h07_duree_incoherente_en_base_est_bloquee(base):
    """Fixture injectée en SQL (durée 0 ou NULL avec `amortissable=1`) : la
    saisie web ne la produit pas, une base modifiée ou un référentiel mal
    repris, oui. Les contrôles rendaient [] et la clôture levait un
    `DivisionByZero` illisible."""
    composant(base, "Bancal", 12000, 10, "218400", "281840")
    base.execute("UPDATE composant SET duree_annees=0")
    base.commit()
    assert "DUREE_INVALIDE" in codes(base, 2026)
    assert amortissement.plan(12000, 0, "2026-01-01") == []   # plus d'exception
    base.execute("UPDATE composant SET duree_annees=NULL")
    base.commit()
    assert "DUREE_INVALIDE" in codes(base, 2026)


# ═══ H-08 — une ventilation vide est le cas le plus incomplet ════════

def test_h08_un_bien_sans_aucun_composant_est_signale(base):
    """Le contrôle sortait sur un total nul — une liste vide ne pouvant pas
    être « incohérente ». Les 12 000 € au bilan n'avaient alors aucun plan,
    et le 2033-C restait vide sans que rien ne l'annonce avant la liasse."""
    acquisition(base, "218400", 12000)
    anomalies = [a for a in controles.controler(base, 2026)
                 if a.code == "VENTILATION_ABSENTE"]
    assert anomalies and anomalies[0].niveau == controles.BLOQUANT
    assert "12000.00" in anomalies[0].message


def test_h08_une_ventilation_partielle_reste_signalee_comme_avant(base):
    """Contre-épreuve : le contrôle de sous-ventilation n'a pas changé."""
    composant(base, "Mobilier", 1000, 8, "218400", "281840")
    assert "VENTILATION_INCOMPLETE" in codes(base, 2026)


# ═══ H-09 — les subdivisions d'un cabinet trouvent leur rubrique ═════

@pytest.mark.parametrize("compte,resolu", [
    ("218100", "218100"), ("2181000", "218100"), ("2184000", "218400"),
    ("2131500", "213150"), ("2115500", "211550"), ("2180000", None),
    ("", None),
])
def test_h09_resolution_des_subdivisions(compte, resolu):
    assert plan_immo.resoudre(compte) == resolu


def test_h09_le_2033c_classe_la_subdivision_dans_sa_rubrique(base):
    """2181000 est une subdivision de 2181 : il relève des installations et
    agencements. La correspondance se faisait par égalité stricte, et ses
    12 000 € tombaient dans « Autres immobilisations corporelles ». Les
    totaux concordant, aucun contrôle ne pouvait voir ce classement."""
    prix_du_bien(base, 20000)
    composant(base, "Agencement", 12000, 10, "2181000", "2818100",
              dms="2025-01-01")
    rubriques = {r["libelle"]: r["brut_fin"]
                 for r in liasse.immobilisations_2033c(base, 2026)["rubriques"]}
    assert rubriques["Installations générales, agencements"] == 12000.0
    assert rubriques["Autres immobilisations corporelles"] == 0.0


def test_h09_un_compte_generique_est_annonce_et_non_devine(base):
    """2180000 ne dit pas de quelle nature physique relève le composant :
    le logiciel ne l'invente pas, mais ne se tait plus."""
    prix_du_bien(base, 8000)
    composant(base, "Générique", 8000, 10, "2180000", "2818000",
              dms="2025-01-01")
    anomalies = [a for a in controles.controler(base, 2026)
                 if a.code == "COMPTE_IMMO_INCONNU"]
    assert anomalies and "2180000" in anomalies[0].message


def test_h09_un_compte_inconnu_ne_bloque_pas_la_cloture(base):
    """Un dossier repris d'un FEC de cabinet doit rester clôturable : un
    compte que le plan ne connaît pas est INJUGEABLE, pas incohérent."""
    prix_du_bien(base, 8000)
    composant(base, "Générique", 8000, 10, "2180000", "2818000")
    acquisition(base, "2180000", 8000)
    fiscal.cloturer(base, 2026)
    assert cumul(base, "2818000", 2026) == 800.0      # 8 000 € sur dix ans


# ═══ H-10 — une quote-part de terrain nulle est une donnée ═══════════

def test_h10_quote_part_zero_respectee():
    """Renseigner 0 est une AFFIRMATION, pas une absence de saisie. Elle
    était ignorée, et la proposition retombait sur sa part indicative de
    15 % — 15 000 € sortis de la base amortissable sur 100 000 €."""
    assert amortissement.normaliser_quote_part(0, 100000) == (0.0, "")
    lignes = amortissement.ventilation_proposee(100000, 0)
    terrain = next(x for x in lignes if x["cle"] == "terrain")
    assert terrain["montant"] == 0.0
    assert round(sum(x["montant"] for x in lignes), 2) == 100000.0


def test_h10_les_autres_lectures_de_quote_part_tiennent():
    """Contre-épreuve : les bornes documentées ne changent pas."""
    for saisie in (7.35, 0.0735):
        lignes = amortissement.ventilation_proposee(100000, saisie)
        assert next(x for x in lignes
                    if x["cle"] == "terrain")["montant"] == 7350.0
    lignes = amortissement.ventilation_proposee(100000, 1.0)
    assert next(x for x in lignes if x["cle"] == "terrain")["montant"] == 100000.0
    assert amortissement.normaliser_quote_part(None) == (None, "")


# ═══ H-11 — le plan vaut la valeur brute, sur sa durée ═══════════════

def test_h11_une_annuite_inferieure_au_centime_n_abandonne_pas_la_valeur():
    """0,24 € sur cinquante ans : l'annuité s'arrondissait à 0,00 €, la
    boucle n'avançait plus, le garde-fou anti-boucle la coupait, et le plan
    rendu ne portait RIEN — la valeur n'était jamais amortie."""
    p = amortissement.plan(0.24, 50, "2026-01-01")
    assert round(sum(d for _a, d in p), 2) == 0.24
    assert all(d > 0 for _a, d in p)


def test_h11_pas_d_annee_supplementaire_pour_un_reliquat():
    """100 000,01 € sur cinquante ans : le centime résiduel créait une
    cinquante-et-unième annuité, après les années 2026 à 2075."""
    p = amortissement.plan(100000.01, 50, "2026-01-01")
    assert len(p) == 50
    assert p[-1] == (2075, 2000.01)
    assert round(sum(d for _a, d in p), 2) == 100000.01


@pytest.mark.parametrize("valeur,duree,dms", [
    (1299.87, 15, "2026-06-17"), (2517.59, 5, "2021-11-01"),
    (58500.00, 55, "2021-11-01"), (12000, 10, "2026-01-01"),
    (100000.01, 50, "2026-12-31"), (0.05, 3, "2026-03-15"),
])
def test_h11_la_somme_des_annuites_vaut_toujours_la_valeur_brute(valeur, duree,
                                                                 dms):
    p = amortissement.plan(valeur, duree, dms)
    assert round(sum(d for _a, d in p), 2) == round(valeur, 2)
    assert len(p) <= duree + 1
    assert all(d > 0 for _a, d in p)


def test_h11_les_annuites_calees_sur_les_liasses_reelles_sont_inchangees():
    """Garde-fou du garde-fou : la convention de prorata en jours réels,
    établie contre des liasses réelles, ne doit pas bouger d'un centime."""
    assert amortissement.etat(58500.00, 55, "2021-11-01", 2025)[0] == 1063.64
    assert amortissement.etat(2517.59, 5, "2021-11-01", 2025)[0] == 503.52
    assert amortissement.etat(2517.59, 5, "2021-11-01", 2026)[0] == 419.36
    p = amortissement.plan(1299.87, 15, "2026-06-17")
    assert p[0][1] == 47.01 and p[-1][1] == 39.62


# ═══ H-12 — le compte 28 doit être celui du compte d'immobilisation ══

@pytest.mark.parametrize("immo,amort,coherent", [
    ("211550", "", True),          # terrain : aucun amortissement
    ("211550", "281840", False),   # terrain amorti sur du mobilier
    ("213150", "281315", True),
    ("218100", "2818400", False),  # agencement amorti sur du mobilier
    ("2181000", "2818100", True),  # subdivisions des DEUX côtés
    ("2180000", "2818000", True),  # compte inconnu : injugeable
])
def test_h12_coherence_des_comptes(immo, amort, coherent):
    assert plan_immo.amortissement_coherent(immo, amort) is coherent


def test_h12_un_terrain_au_compte_28_errone_est_refuse(base):
    """Fixture injectée en SQL — la saisie web résout correctement le compte
    du terrain. La PRÉSENCE d'un compte 28 était tenue pour suffisante :
    1 200 € de dotation de terrain étaient effectivement enregistrés."""
    composant(base, "Terrain fictif", 12000, 10, "211550", "281840")
    anomalies = [a for a in controles.controler(base, 2026)
                 if a.code == "AMORT_INCOHERENT"]
    assert anomalies and anomalies[0].niveau == controles.BLOQUANT
    with pytest.raises(ValueError, match="ne correspond pas"):
        amortissement.generer_cloture(base, 2026)
    base.commit()
    assert cumul(base, "281840", 2026) == 0.0


def test_h12_le_terrain_sans_compte_28_reste_refuse(base):
    """Contre-épreuve : le correctif antérieur tient toujours."""
    composant(base, "Terrain fictif", 12000, 10, "211550", "281840")
    base.execute("UPDATE composant SET compte_amort=NULL")
    base.commit()
    assert "COMPOSANT_SANS_AMORT" in codes(base, 2026)


# ═══ Ce qui tenait doit continuer de tenir ═══════════════════════════

def test_un_exercice_ordinaire_traverse_tous_les_nouveaux_controles(base):
    """Garde générale : une comptabilité bien tenue ne doit déclencher
    aucune des exigences ajoutées par cette passe."""
    prix_du_bien(base, 12000)
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    acquisition(base, "218400", 12000)
    operations.saisir(base, type="loyer", montant=800, periode="2026-01",
                      date_operation="2026-01-10")
    nouveaux = {"VENTILATION_ABSENTE", "AMORT_INCOHERENT", "DUREE_INVALIDE",
                "COMPTE_IMMO_INCONNU", "AMORT_CUMUL", "AMORT_CUMUL_FIN",
                "DOTATION_ANNULEE"}
    assert not (set(codes(base, 2026)) & nouveaux)
    fiscal.cloturer(base, 2026)
    assert not (set(codes(base, 2026)) & nouveaux)
    assert cumul(base, "281840", 2026) == 1200.0


def test_le_terrain_ne_s_amortit_toujours_pas(base):
    prix_du_bien(base, 20000)
    base.execute(
        "INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,"
        "date_mise_service,compte_immo,compte_amort,amortissable) "
        "VALUES (1,'Terrain',8000,0,'2026-01-01','211550',NULL,0)")
    composant(base, "Mobilier", 12000, 10, "218400", "281840")
    base.commit()
    libelles = {d["libelle"] for d in amortissement.dotations_exercice(base, 2026)}
    assert libelles == {"Mobilier"}


def test_dossier_temporaire_nettoye():
    """Garde-fou de la suite elle-même : ces tests n'écrivent que dans le
    tmp_path de pytest, jamais à côté des fichiers du projet."""
    import os
    assert not os.path.exists(os.path.join(tempfile.gettempdir(), "fictif.db"))
