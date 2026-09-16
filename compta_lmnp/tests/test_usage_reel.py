# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Constats d'usage réel (v8.11.0) — premier dossier tenu de bout en bout.

Le plus important : la liasse signalait « 2033-C : amortissements fin =
case 030 du bilan → ANOMALIE 12 219,29 / 0,00 ». Ce n'était pas un faux
positif. Le bien, acquis en 2021, avait été saisi à sa seule valeur BRUTE
(117 000 €) : les ~9 879 € d'amortissements déjà courus n'avaient jamais
été comptabilisés. Le bilan présentait donc un bien neuf pendant que le
tableau 2033-C déroulait son plan depuis l'origine — écart permanent, et
valeur nette comptable fausse pour une future plus-value.

Le logiciel n'offrait AUCUN moyen de reprendre ce cumul : c'est pourtant
le cas le plus fréquent en LMNP (on achète des années avant d'ouvrir une
comptabilité). D'où `reprendre_amortissements_anterieurs`.

Lancer :  pytest -q tests/test_usage_reel.py
"""
import os
import sys

import conftest

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import controles
import fiscal
import gabarits
import init_db
import liasse
import operations
import veille_fiscale

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def dossier(tmp_path):
    """Le dossier réel : bien acquis le 13/10/2021, saisi au brut en 2026."""
    c = init_db.init(str(tmp_path / "reel.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('EXPLOITANT', '123456789', 'ORLEAT')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'appartement 3p', '2021-10-13', 117000, 0)")
    c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
              "duree_annees, date_mise_service, compte_immo, compte_amort, "
              "amortissable) VALUES "
              "(1, 'gros oeuvre', 117000, 50, '2021-10-13', '213150', "
              "'281315', 1)")
    c.commit()
    operations.saisir_acquisition(c, compte_immo="213150", montant=117000,
                                  date_operation="2026-01-01",
                                  libelle="Acquisition - gros oeuvre")
    for m in range(7, 13):
        operations.saisir(c, type="loyer", montant=670, periode=f"2026-{m:02d}",
                          date_operation=f"2026-{m:02d}-22", bien_id=1)
    c.commit()
    yield c
    c.close()


# === Amortissements antérieurs ============================================

def test_ecart_2033c_detecte_et_explique(dossier):
    resultat = liasse.generer(dossier, 2026)
    ctl = {c["nom"]: c for c in resultat["controles"]}
    c = ctl["2033-C : amortissements fin = case 030 du bilan"]
    assert not c["ok"]                              # l'écart est bien vu
    # …et le message DIT quoi faire, au lieu d'aligner deux nombres muets
    assert ("amortissements déjà courus" in c["detail"]
            or "clôturé" in c["detail"])
    assert "Immobilisations" in c["detail"]


def test_controle_signale_les_amortissements_non_repris(dossier):
    codes = [a.code for a in controles.controler(dossier, 2026)]
    assert "AMORT_ANTERIEURS" in codes


def test_reprise_resout_l_ecart_sans_toucher_au_resultat(dossier):
    avant = liasse.generer(dossier, 2026)["f2033b"]["benefice_ou_perte_310"]
    r = operations.reprendre_amortissements_anterieurs(dossier, 2026)
    assert r["total"] == pytest.approx(9872.88, abs=1.0)
    apres = liasse.generer(dossier, 2026)
    # le résultat de l'exercice est INTACT : ce n'est pas une dotation
    assert apres["f2033b"]["benefice_ou_perte_310"] == pytest.approx(avant)
    # le bilan porte désormais le cumul d'ouverture
    assert apres["f2033a"]["amortissements_030"] == pytest.approx(r["total"])
    fiscal.cloturer(dossier, 2026, forcer=True)
    fin = liasse.generer(dossier, 2026)
    ecart = (fin["f2033c"]["totaux"]["amort_fin"]
             - fin["f2033a"]["amortissements_030"])
    assert abs(ecart) < 0.01, "l'écart doit être clos après reprise + clôture"
    assert fin["conforme"], [c["nom"] for c in fin["controles"] if not c["ok"]]


def test_reprise_refusee_deux_fois(dossier):
    operations.reprendre_amortissements_anterieurs(dossier, 2026)
    with pytest.raises(ValueError, match="Aucun amortissement"):
        operations.reprendre_amortissements_anterieurs(dossier, 2026)


def test_pas_de_faux_positif_sur_un_bilan_repris(tmp_path):
    """Une base dont les à-nouveaux viennent d'un ancien prestataire diffère
    du plan de quelques euros (arrondis) : ce bruit ne doit rien déclencher."""
    c = init_db.init_demo(str(tmp_path / "demo.db"), FEC2025, 2026)
    assert operations.amortissements_anterieurs_manquants(c, 2026)["total"] == 0
    assert "AMORT_ANTERIEURS" not in [a.code for a in
                                      controles.controler(c, 2026)]
    c.close()


# === Autres constats d'usage ==============================================

def test_duplication_nomme_la_piece_lisiblement(dossier):
    ops = dossier.execute("SELECT id FROM operation WHERE type='loyer' "
                          "ORDER BY id LIMIT 1").fetchone()
    r = operations.dupliquer(dossier, ops[0])
    piece = dossier.execute("SELECT e.piece_ref FROM ecriture e "
                            "JOIN operation o ON o.ecriture_id = e.id "
                            "WHERE o.id=?", (r["operation_id"],)).fetchone()[0]
    assert piece.startswith("Relevé bancaire ")
    assert piece.split()[-1].isdigit()          # …suivi du mois concerné


def test_teom_rappelee_avec_la_taxe_fonciere(dossier):
    operations.saisir(dossier, type="taxe_fonciere", montant=1000,
                      date_operation="2026-07-22", bien_id=1)
    codes = [a.code for a in controles.controler(dossier, 2026)]
    assert "TEOM_ABSENTE" in codes
    operations.saisir(dossier, type="teom", montant=150,
                      date_operation="2026-07-22", bien_id=1)
    codes = [a.code for a in controles.controler(dossier, 2026)]
    assert "TEOM_ABSENTE" not in codes


def test_libelle_taxe_fonciere_distingue_la_teom():
    assert "TEOM" in gabarits.GABARITS["taxe_fonciere"]["libelle"]


def test_adhesion_oga_retiree():
    """Majoration pour non-adhésion supprimée à compter de 2025 : le
    gabarit n'a plus lieu d'être proposé."""
    assert "adhesion_oga" not in gabarits.GABARITS


def test_veille_interroge_les_modeles_declaratifs():
    p = veille_fiscale.prompt_veille(2026)
    assert "MODÈLES DÉCLARATIFS" in p
    assert "2033-A" in p and "2042-C-PRO" in p


# === Liasse provisoire : même règle fiscale que la clôture ================
# Constat sur le dossier réel : la liasse provisoire affichait un résultat
# fiscal ÉGAL au résultat comptable, en ignorant le fonds ALUR pourtant
# déjà saisi et non déductible. Le chiffre consulté toute l'année était
# donc sous-évalué, puis sautait à la clôture. La règle est désormais
# portée par une seule fonction (fiscal.retraitement_automatique),
# appelée aux deux moments.

def test_liasse_provisoire_reintegre_l_alur(dossier):
    operations.saisir_appel_charges(dossier, date_operation="2026-07-22",
                                    periode="2026-07", charges_courantes=630,
                                    fonds_alur=25, travaux=500)
    prov = liasse.generer(dossier, 2026)["f2033b"]
    assert prov["reintegration_divers_330"] == pytest.approx(25.0)
    assert prov["resultat_fiscal_lmnp"] == pytest.approx(
        prov["benefice_ou_perte_310"] + 25.0)


def test_la_projection_annonce_exactement_la_cloture(dossier):
    """Les TABLEAUX restent factuels (ils reflètent les écritures), mais le
    bloc de projection doit annoncer le résultat de la clôture au centime —
    sinon le déclarant lit toute l'année un chiffre qui saute au 31/12."""
    operations.saisir_appel_charges(dossier, date_operation="2026-07-22",
                                    periode="2026-07", charges_courantes=630,
                                    fonds_alur=25, travaux=500)
    proj = liasse.generer(dossier, 2026)["projection_cloture"]
    assert proj["dotation_previsionnelle"] > 0      # dotation pas encore écrite
    apres = fiscal.cloturer(dossier, 2026, forcer=True)["resultat_fiscal"]
    assert proj["resultat_fiscal_projete"] == pytest.approx(apres)


def test_projection_absente_si_exercice_clos(dossier):
    fiscal.cloturer(dossier, 2026, forcer=True)
    assert liasse.generer(dossier, 2026)["projection_cloture"] is None


def test_regle_alur_a_une_source_unique():
    """La clôture ne doit pas recopier la règle : elle doit l'appeler."""
    src = open(conftest.source("fiscal.py"), encoding="utf-8").read()
    corps_cloturer = src.split("def cloturer(")[1]
    assert "_calcul_fiscal(" in corps_cloturer
    assert "retraitement_alur_auto" not in corps_cloturer, \
        "la règle est recopiée dans cloturer au lieu d'être appelée"
    assert "calculer_39c(" not in corps_cloturer, \
        "la chaîne 39 C doit vivre dans _calcul_fiscal, appelée aussi par simuler()"


def test_alur_annule_nest_pas_reintegre_dans_le_provisoire(dossier):
    r = operations.saisir_appel_charges(
        dossier, date_operation="2026-07-22", periode="2026-07",
        charges_courantes=630, fonds_alur=25, travaux=500)
    alur = [o for o in r["operations"]][1]
    operations.annuler(dossier, alur["operation_id"])
    prov = liasse.generer(dossier, 2026)["f2033b"]
    assert prov["reintegration_divers_330"] == pytest.approx(0.0)


# === Dossier de démonstration anonymisé ===================================
# Constat d'usage : la réinitialisation du bac à sable en mode démo échouait
# chez le client. Cause — le seed livré (seed_exemple.sql) réclamait un FEC
# volontairement exclu du paquet. Et cause plus grave découverte au passage :
# ce seed portait une identité RÉELLE et partait pourtant dans chaque
# paquet, alors qu'il porte la mention « NE JAMAIS LIVRER ».

def _voie_reelle() -> str:
    """Nom de la rue de l'exploitant, LU dans le seed privé.

    Il était écrit en clair dans ce fichier suivi par git,
    et la garde de dépôt ne le voyait pas puisqu'elle ne cherche que
    l'adresse entière : un test anti-fuite qui publiait lui-même ce qu'il
    protège (constat F-11).
    """
    import re
    reel = open(os.path.join(HERE, "seed_exemple.sql"), encoding="utf-8").read()
    adr = re.search(r"'(\d+\s+[Rr]ue\s+([^,']+))", reel)
    return adr.group(2).strip() if adr else ""


def test_dossier_demo_ne_contient_aucune_donnee_reelle():
    conftest.exiger_dossier_prive()
    demo = open(os.path.join(HERE, "seed_demo.sql"), encoding="utf-8").read()
    fec = open(os.path.join(HERE, "demo", "FEC_DEMO_2025.txt"),
               encoding="utf-8").read()
    reel = open(os.path.join(HERE, "seed_exemple.sql"), encoding="utf-8").read()
    import re
    nom = re.search(r"INSERT INTO exploitant.*?'([^']+)'", reel, re.S).group(1)
    siren = re.search(r"'(\d{9})'", reel).group(1)
    for contenu in (demo, fec):
        assert nom not in contenu
        assert siren not in contenu
        voie = _voie_reelle()
        assert voie and voie not in contenu


def test_fec_demo_conforme_et_equilibre():
    import reprise
    import valider_fec
    chemin = os.path.join(HERE, "demo", "FEC_DEMO_2025.txt")
    assert valider_fec.valider(chemin) == []
    bal = reprise.lire_balance_fec(chemin)
    assert round(sum(bal.values()), 2) == 0.0
    # le compte d'attente doit être SOLDÉ : un résidu d'arrondi y laissait
    # un centime, écarté de l'à-nouveau, d'où un contrôle bloquant sur un
    # dossier de démonstration tout neuf
    assert round(bal.get("472000", 0.0), 2) == 0.0


def test_demo_coherente_sans_le_dossier_reel(tmp_path, monkeypatch):
    """Simule le poste client : dossier de référence absent."""
    import init_db as m
    monkeypatch.setattr(m, "FEC_REF_DEFAUT", str(tmp_path / "absent.txt"))
    seed, fec = m.dossier_demonstration()
    assert seed == "seed_demo.sql"
    c = m.init(str(tmp_path / "demo.db"), "demo", annee_cible=2026)
    L = liasse.generer(c, 2026)
    assert L["f2033a"]["equilibre"]
    # 2033-C et bilan doivent s'accorder au centime malgré la mise à l'échelle
    assert L["f2033c"]["totaux"]["brut_fin"] == pytest.approx(
        L["f2033a"]["immo_corporelles_brut_028"], abs=0.01)
    assert L["conforme"], [x["nom"] for x in L["controles"] if not x["ok"]]
    assert not [a for a in controles.controler(c, 2026)
                if a.niveau != "INFO"]
    c.close()


def test_paquet_client_sans_identite_reelle(tmp_path):
    conftest.exiger_dossier_prive()
    import construire_distribution as cd
    import zipfile
    anciens = os.getcwd()
    os.chdir(HERE)
    try:
        chemin = cd.construire()
    finally:
        os.chdir(anciens)
    del tmp_path
    with zipfile.ZipFile(chemin) as z:
        noms = z.namelist()
        assert not any("seed_exemple" in n for n in noms)
        assert any("seed_demo" in n for n in noms)
        assert any("FEC_DEMO" in n for n in noms)
        contenu = b"".join(z.read(n) for n in noms
                           if n.endswith((".sql", ".txt")))
    assert b"123456789" not in contenu
    voie = _voie_reelle()
    assert voie and voie.encode() not in contenu


# === Pense-bête : oublis récurrents =======================================

def test_checklist_des_oublis_frequents():
    import pense_bete
    groupes = pense_bete.oublis_frequents()
    assert len(groupes) >= 4
    points = [p for g in groupes for p in g["points"]]
    assert len(points) >= 14
    assert all(p["titre"] and len(p["detail"]) > 80 for p in points)
    titres = " ".join(p["titre"].lower() for p in points)
    for attendu in ("frais d'acquisition", "cfe", "terrain", "siret"):
        assert attendu in titres, attendu


def test_rappels_detectent_les_oublis_du_dossier(dossier):
    import pense_bete
    titres = " ".join(r["titre"] for r in pense_bete.rappels(dossier))
    assert "Frais d'acquisition" in titres     # aucun composant de frais
    assert "mobilier" in titres.lower()        # aucun 2184xx enregistré


# === Composant amortissable sans compte d'amortissement ===================
# Blocage réel : un composant créé avec une durée sur un compte qui ne
# s'amortit pas (terrain) faisait échouer TOUTE clôture sur
# « NOT NULL constraint failed: ligne.compte_num » — message
# incompréhensible. Et rien, dans l'interface, ne permettait de le
# corriger : les composants étaient créables, jamais modifiables.

@pytest.fixture()
def bien_nu(tmp_path):
    c = init_db.init(str(tmp_path / "b.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'T3', '2026-01-15', 117000, 0.0735)")
    c.commit()
    yield c
    c.close()


def _composant_bancal(conn):
    conn.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
                 "duree_annees, date_mise_service, compte_immo, "
                 "compte_amort, amortissable) VALUES "
                 "(1, 'Terrain', 20000, 20, '2026-01-01', '211550', NULL, 1)")
    conn.commit()


def test_cloture_refuse_clairement_un_composant_sans_compte(bien_nu):
    _composant_bancal(bien_nu)
    operations.saisir(bien_nu, type="loyer", montant=1000, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    with pytest.raises(ValueError) as e:
        fiscal.cloturer(bien_nu, 2026)
    msg = str(e.value)
    assert "Terrain" in msg and "durée" in msg          # nomme le coupable
    assert "NOT NULL" not in msg                        # plus d'erreur SQLite


def test_controle_le_signale_avant_la_cloture(bien_nu):
    _composant_bancal(bien_nu)
    anomalies = {a.code: a for a in controles.controler(bien_nu, 2026)}
    assert "COMPOSANT_SANS_AMORT" in anomalies
    assert anomalies["COMPOSANT_SANS_AMORT"].niveau == controles.BLOQUANT


def test_duree_corrigeable_depuis_l_interface(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    c = init_db.init(db, "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total) VALUES (1, 'T3', '2026-01-15', 117000)")
    _composant_bancal(c)
    c.close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "s.db"))
    import importlib
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    cl = app_mod.app.test_client()
    cl.post("/immobilisations/composant/1/duree", data={"duree_annees": "0"},
            follow_redirects=True)
    import sqlite3
    cx = sqlite3.connect(db)
    assert cx.execute("SELECT amortissable FROM composant WHERE id=1"
                      ).fetchone()[0] == 0
    cx.row_factory = sqlite3.Row
    fiscal.cloturer(cx, 2026, forcer=True)                     # la clôture passe enfin
    cx.close()
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def test_creation_refuse_une_duree_sur_un_compte_non_amortissable(
        tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    c = init_db.init(db, "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total) VALUES (1, 'T3', '2026-01-15', 117000)")
    c.commit()
    c.close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "s.db"))
    import importlib
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    r = app_mod.app.test_client().post("/immobilisations/composant", data={
        "bien_id": "1", "libelle": "Terrain", "valeur_brute": "8600",
        "duree_annees": "25", "compte_immo": "211550"}, follow_redirects=True)
    assert "amortissable" in r.get_data(as_text=True)
    import sqlite3
    cx = sqlite3.connect(db)
    assert cx.execute("SELECT COUNT(*) FROM composant").fetchone()[0] == 0
    cx.close()
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


# === Ventilation guidée ===================================================

def test_ventilation_proposee_tombe_juste():
    import amortissement
    v = amortissement.ventilation_proposee(117000, 0.0735)
    assert sum(x["montant"] for x in v) == pytest.approx(117000, abs=0.01)
    terrain = next(x for x in v if x["cle"] == "terrain")
    assert terrain["montant"] == pytest.approx(117000 * 0.0735, abs=0.01)
    assert terrain["duree"] == 0                 # jamais amortissable
    assert all(x["note"] for x in v)             # chaque poste s'explique


def test_ventilation_sans_quote_part_connue():
    import amortissement
    v = amortissement.ventilation_proposee(200000)
    assert sum(x["montant"] for x in v) == pytest.approx(200000, abs=0.01)


def test_sous_ventilation_signalee(bien_nu):
    bien_nu.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
                    "duree_annees, date_mise_service, compte_immo, "
                    "compte_amort, amortissable) VALUES "
                    "(1, 'Gros oeuvre', 60000, 50, '2026-01-15', '213150', "
                    "'281315', 1)")
    bien_nu.commit()
    codes = [a.code for a in controles.controler(bien_nu, 2026)]
    assert "VENTILATION_INCOMPLETE" in codes


def test_depassement_par_travaux_nest_pas_une_anomalie_permanente(bien_nu):
    """Un bien avec travaux immobilisés dépasse son prix d'achat — et le
    reste définitivement. En faire une alerte permanente reviendrait à
    crier sur tout dossier vivant."""
    for lib, val in (("Gros oeuvre", 110000), ("Travaux 2027", 20000)):
        bien_nu.execute(
            "INSERT INTO composant (bien_id, libelle, valeur_brute, "
            "duree_annees, date_mise_service, compte_immo, compte_amort, "
            "amortissable) VALUES (1,?,?,25,'2026-01-15','213150',"
            "'281315',1)", (lib, val))
    bien_nu.commit()
    codes = [a.code for a in controles.controler(bien_nu, 2026)]
    assert "VENTILATION_INCOMPLETE" not in codes


# === Suivi des reports ====================================================

def test_liasse_recapitule_les_reports(dossier):
    """Les deux natures de report doivent figurer, avec leur détail."""
    rep = liasse.generer(dossier, 2026)["reports"]
    assert set(rep) >= {"suivi_39c", "deficits", "total_deficits",
                        "total_restant", "suivi_39c_par_bien"}
    s = rep["suivi_39c"]
    assert set(s) >= {"stock_ouverture", "report_annee", "utilisation_annee",
                      "stock_cloture"}


# === Bac à sable : une année de location déjà vécue =======================
# Le dossier de démonstration créait un exercice précédent « clos » mais
# VIDE. Le débutant qui basculait dessus ne voyait rien : le bac à sable ne
# montrait jamais à quoi ressemble une année tenue de bout en bout. Il
# porte désormais l'exercice précédent complet — à inspecter — en plus de
# l'exercice courant, laissé libre pour s'exercer.

def test_demo_contient_une_annee_complete(tmp_path):
    c = init_db.init(str(tmp_path / "d.db"), "demo", annee_cible=2026)
    n_ecritures = c.execute("SELECT COUNT(*) FROM ecriture "
                            "WHERE exercice_annee=2025").fetchone()[0]
    assert n_ecritures >= 30
    ops = dict(c.execute("SELECT type, COUNT(*) FROM operation "
                         "WHERE exercice_annee=2025 GROUP BY type"))
    # une année de location, ça se reconnaît : des loyers et des charges
    assert ops.get("loyer", 0) >= 6
    assert ops.get("charge_copro", 0) >= 3
    assert "taxe_fonciere" in ops and "cfe" in ops
    assert c.execute("SELECT statut FROM exercice WHERE annee=2025"
                     ).fetchone()[0] == "clos"
    assert c.execute("SELECT statut FROM exercice WHERE annee=2026"
                     ).fetchone()[0] == "ouvert"
    c.close()


def test_demo_les_operations_pointent_les_vraies_ecritures(tmp_path):
    """Les opérations reconstituées ne sont pas décoratives : chacune est
    rattachée à l'écriture qui la justifie, et les montants concordent."""
    c = init_db.init(str(tmp_path / "d.db"), "demo", annee_cible=2026)
    for op_id, montant, eid in c.execute(
            "SELECT id, montant, ecriture_id FROM operation "
            "WHERE exercice_annee=2025"):
        assert eid is not None, op_id
        total = c.execute(
            "SELECT ROUND(SUM(ABS(debit - credit)) / 2, 2) FROM ligne "
            "WHERE ecriture_id=?", (eid,)).fetchone()[0]
        assert abs(total - montant) < 0.01, (op_id, montant, total)
    c.close()


def test_exercice_courant_de_la_demo_reste_vierge(tmp_path):
    """L'exercice ouvert doit rester libre : c'est là qu'on s'exerce."""
    c = init_db.init(str(tmp_path / "d.db"), "demo", annee_cible=2026)
    assert c.execute("SELECT COUNT(*) FROM operation WHERE exercice_annee=2026"
                     ).fetchone()[0] == 0
    # …et l'exercice précédent ne doit PAS le polluer d'alertes
    assert not [a for a in controles.controler(c, 2026)
                if a.niveau != "INFO"]
    c.close()


def test_annee_precedente_ne_double_pas_les_a_nouveaux(tmp_path):
    """Piège : l'exercice précédent complet ET ses à-nouveaux coexistent.
    Les compter tous les deux doublerait le cumul d'amortissement."""
    c = init_db.init(str(tmp_path / "d.db"), "demo", annee_cible=2026)
    assert operations.amortissements_anterieurs_manquants(c, 2026)["total"] == 0
    L = liasse.generer(c, 2026)
    assert L["conforme"], [x["nom"] for x in L["controles"] if not x["ok"]]
    c.close()


def test_plausibilite_muette_sur_un_exercice_a_peine_ouvert(tmp_path):
    """Au 2 janvier, TOUTES les charges de l'an dernier sont « manquantes » :
    comparer n'a pas de sens et noierait l'utilisateur d'alertes."""
    c = init_db.init(str(tmp_path / "d.db"), "demo", annee_cible=2026)
    assert not [a for a in controles.controler(c, 2026)
                if a.code == "PLAUSIBILITE_N1"]
    c.close()


# === Audit v8.19.0 — deux défauts trouvés en revue =========================

def test_deficit_perime_exclu_des_reports_disponibles(bien_nu):
    """Un déficit LMNP s'impute dix ans, puis il est perdu. La clôture le
    purgeait bien, mais le suivi des reports le comptait encore parmi les
    reports disponibles : le total affiché surestimait ce qui reste
    réellement imputable."""
    for origine, montant in ((2014, 500), (2016, 800), (2024, 1200)):
        bien_nu.execute(
            "INSERT INTO deficit_lmnp (annee_origine, montant_initial, "
            "solde, annee_expiration) VALUES (?,?,?,?)",
            (origine, montant, montant, origine + 10))
    bien_nu.commit()
    rep = liasse.suivi_reports(bien_nu, 2026)
    perimes = [d for d in rep["deficits"] if d["perime"]]
    assert [d["annee_origine"] for d in perimes] == [2014]
    # 800 + 1200 imputables, les 500 de 2014 sont perdus
    assert rep["total_deficits"] == pytest.approx(2000.0)
    assert rep["total_deficits_perimes"] == pytest.approx(500.0)
    # …mais ils restent VISIBLES : disparaître sans explication serait pire
    assert len(rep["deficits"]) == 3


def test_quote_part_terrain_interpretee_au_lieu_d_etre_ignoree():
    """Le champ attend une fraction. Un pourcentage, un montant en euros ou
    la valeur 1 étaient ignorés SANS UN MOT, et la ventilation retombait
    sur sa part indicative de 15 % — ce qui fausse l'amortissement, le
    terrain n'étant pas amortissable."""
    import amortissement
    attendu = 117000 * 0.0735
    for saisie in (0.0735, 7.35, 8600):
        v = amortissement.ventilation_proposee(117000, saisie)
        terrain = next(x for x in v if x["cle"] == "terrain")["montant"]
        assert terrain == pytest.approx(attendu, abs=1.0), saisie
        assert sum(x["montant"] for x in v) == pytest.approx(117000, abs=0.01)
    # terrain nu : la borne haute stricte le renvoyait à 15 %
    v = amortissement.ventilation_proposee(117000, 1.0)
    assert next(x for x in v if x["cle"] == "terrain")["montant"] == \
        pytest.approx(117000, abs=0.01)
    # saisies inexploitables : on retombe sur l'indicatif, sans planter
    for saisie in ("abc", None, -1):
        assert amortissement.normaliser_quote_part(saisie, 117000)[0] is None


def test_imputation_des_deficits_du_plus_ancien_au_plus_recent(bien_nu):
    for origine, montant in ((2016, 800), (2024, 1200)):
        bien_nu.execute(
            "INSERT INTO deficit_lmnp (annee_origine, montant_initial, "
            "solde, annee_expiration) VALUES (?,?,?,?)",
            (origine, montant, montant, origine + 10))
    bien_nu.commit()
    operations.saisir(bien_nu, type="loyer", montant=900, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    fiscal.cloturer(bien_nu, 2026, forcer=True)
    soldes = dict(bien_nu.execute(
        "SELECT annee_origine, solde FROM deficit_lmnp"))
    assert soldes[2016] == pytest.approx(0.0)      # le plus ancien d'abord
    assert soldes[2024] == pytest.approx(1100.0)   # 900 − 800 = 100 imputés


# === Assistant d'aide (v8.21.0) ===========================================
# Un personnage qui lit les infobulles. Le précédent le plus célèbre du
# genre a été détesté pour une raison précise : il s'invitait. Celui-ci ne
# paraît QUE sur demande d'aide, se masque définitivement d'un clic, et ne
# remplace jamais l'infobulle CSS — qui reste seule maîtresse sans
# JavaScript.

def test_assistant_present_sans_ressource_externe(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "s.db"))
    import importlib
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    h = app_mod.app.test_client().get("/saisie").get_data(as_text=True)
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)
    assert 'id="assistant"' in h
    bloc = h.split('id="assistant"')[1][:3000]
    assert "<svg" in bloc                       # dessin en ligne
    assert "src=" not in bloc                   # aucun fichier à charger
    assert "<audio" not in h and "speechSynthesis" not in h   # aucun son


def test_assistant_ne_sinvite_pas():
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    bloc = p.split("ASSISTANT = ")[1].split('"""')[1]
    # masqué tant qu'aucune aide n'est demandée
    assert "#assistant { position: fixed" in p and "display: none" in p
    assert "montrer(a.dataset.aide" in bloc     # déclenché par l'infobulle
    assert "setInterval" not in bloc            # rien de périodique
    assert "assistant=0" in bloc                # masquage définitif possible


def test_infobulles_fonctionnent_sans_javascript():
    """Le personnage est un confort, pas le support de l'aide : la bulle
    CSS doit rester autonome."""
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    assert ".aide:hover::after" in p            # infobulle purement CSS
    assert "content: attr(data-aide)" in p


def test_assistant_respecte_le_mouvement_reduit():
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    assert "prefers-reduced-motion" in p
    bloc = p.split("prefers-reduced-motion")[1][:300]
    assert "animation: none" in bloc
    for anim in ("@keyframes flotte", "@keyframes salue", "@keyframes alerte"):
        assert anim in p, anim
    # …et les animations doivent être PAR PALIERS : un sprite qui glisse en
    # sous-pixels trahit le pixel art.
    assert "steps(" in p


# === Assistante : les trois états (v8.23.0) ===============================
# Redessinée d'après trois illustrations de référence fournies par l'auteur :
# une comptable ailée à visière verte, qui présente une tablette. Trois
# visages — elle explique, elle valide, elle alerte.

def test_assistante_a_bien_trois_etats():
    """Sprite en PIXEL ART depuis la v8.26.0 : le corps est dessiné une
    fois, seuls les pixels qui changent (écran de la tablette, bouche,
    sourcils) sont superposés par état."""
    import pages
    svg = pages.ASSISTANT
    for etat in ("sur-info", "sur-valide", "sur-anomalie"):
        assert etat in svg, etat
    assert 'class="corps"' in svg
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    # un seul état visible à la fois
    assert "#assistant .sur-info, #assistant .sur-valide" in p
    assert "#assistant.info     .sur-info     { display: block; }" in p
    # le pixel art ne doit pas être lissé par le navigateur
    assert "image-rendering: pixelated" in p
    assert 'shape-rendering="crispEdges"' in svg


def test_assistante_reagit_a_ce_qui_vient_de_se_passer():
    """Les trois visages n'ont de sens que s'ils sont déclenchés par quelque
    chose de réel : le message de confirmation ou d'erreur déjà affiché."""
    import pages
    js = pages.ASSISTANT.split("<script>")[1]
    assert 'querySelector(".flash-err")' in js
    assert 'querySelector(".flash-ok")' in js
    assert '"anomalie"' in js and '"valide"' in js
    # elle s'efface d'elle-même : jamais de commentaire permanent
    assert "cacher(6500)" in js


def test_assistante_nutilise_jamais_innerhtml():
    """Elle affiche des messages venus de la base : innerHTML ouvrirait une
    injection. Le mot ne doit apparaître que dans un commentaire."""
    import pages
    for ligne in pages.ASSISTANT.splitlines():
        nu = ligne.strip()
        if nu.startswith("//") or nu.startswith("<!--"):
            continue
        assert "innerHTML" not in nu, ligne


def test_assistante_reste_un_confort():
    """Sans JavaScript — ou pour qui l'a masquée — l'aide doit fonctionner."""
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    assert ".aide:hover::after" in p and "content: attr(data-aide)" in p
    assert "assistant=0" in p                       # masquage définitif
    assert "prefers-reduced-motion" in p


def test_stock_39c_perdu_a_la_cession_est_visible():
    """Le stock 39 C rattaché à un bien cédé est définitivement perdu. Il
    était tracé par bien dans le PDF, mais à l'écran le stock tombait à
    zéro sans un mot — comme s'il avait été utilisé."""
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    assert "L.reports.sortie_39c" in p
    assert "perdu à la cession" in p
    src = open(conftest.source("liasse.py"), encoding="utf-8").read()
    assert '"sortie_39c"' in src


def test_ventilation_est_atomique(tmp_path, monkeypatch):
    """Audit v8.23.0 : un échec sur la 3e ligne laissait les deux premières
    ÉCRITES. L'utilisateur voyait une erreur, croyait que rien n'avait eu
    lieu, recommençait — et doublait composants et écritures."""
    import importlib
    import sqlite3
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "s.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    cl = app_mod.app.test_client()
    cl.post("/immobilisations/exploitant",
            data={"nom": "T", "siren": "123456789", "adresse": "X"})
    cl.post("/immobilisations/bien", data={
        "libelle": "B", "adresse": "Y", "date_acquisition": "2026-01-15",
        "prix_total": "117000"})
    r = cl.post("/immobilisations/ventiler", data={
        "bien_id": "1",
        "montant_terrain": "8600", "duree_terrain": "0",
        "montant_gros_oeuvre": "52000", "duree_gros_oeuvre": "50",
        "montant_facade": "PAS UN NOMBRE", "duree_facade": "25"},
        follow_redirects=True)
    corps = r.get_data(as_text=True)
    assert "n&#39;est pas un montant" in corps or "n'est pas un montant" in corps
    assert "could not convert" not in corps      # plus d'erreur Python brute
    cx = sqlite3.connect(db)
    assert cx.execute("SELECT COUNT(*) FROM composant").fetchone()[0] == 0
    assert cx.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] == 0
    cx.close()
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def test_ventilation_refuse_un_montant_hors_de_proportion():
    src = open(conftest.source("app.py"), encoding="utf-8").read()
    assert "montant hors de proportion" in src


def test_assistante_est_une_creation_originale():
    """L'illustration de référence apportée par l'auteur était un
    personnage de jeu vidéo appartenant à un éditeur. Le reproduire dans un
    logiciel diffusé sous son propre copyright aurait annulé le travail des
    versions 8.16 à 8.20, qui a précisément consisté à établir sa propriété
    et à retirer toute référence appartenant à un tiers.

    Seul le REGISTRE VISUEL a été repris — gros pixels, contour franc,
    palette contrastée : un style ne se protège pas, un personnage si. Ce
    test verrouille l'absence de toute marque tierce dans le sprite."""
    import pages
    svg = pages.ASSISTANT.lower()
    for marque in ("dota", "valve", "steam", "blizzard", "riot",
                   "nintendo", "warcraft"):
        assert marque not in svg, marque
    # sprite entièrement décrit par des rectangles : aucune image importée
    assert "<image" not in svg and "xlink:href" not in svg
    assert "url(" not in svg.split("<style")[0]


def test_sprite_est_genere_depuis_une_carte_lisible():
    """Le sprite est décrit par une carte de caractères, non par 92 balises
    écrites à la main : changer un pixel ou une couleur reste faisable."""
    import outils_sprite
    assert len(outils_sprite.SPRITE) > 15
    largeurs = {len(ligne) for ligne in outils_sprite.SPRITE}
    assert len(largeurs) == 1, f"carte non rectangulaire : {largeurs}"
    inconnus = {c for ligne in outils_sprite.SPRITE for c in ligne
                if c != "." and c not in outils_sprite.PALETTE}
    assert not inconnus, f"couleurs non définies : {inconnus}"
    for nom, pixels in outils_sprite.ETATS.items():
        for (x, y), c in pixels.items():
            assert c in outils_sprite.PALETTE, (nom, c)
            assert 0 <= y < len(outils_sprite.SPRITE), (nom, y)
            assert 0 <= x < len(outils_sprite.SPRITE[0]), (nom, x)
    # la fusion des pixels voisins doit rester rentable
    rects = outils_sprite._rects(outils_sprite.SPRITE)
    pleins = sum(1 for ligne in outils_sprite.SPRITE
                 for c in ligne if c != ".")
    assert len(rects) < pleins / 2


# === Pense-bête : actualités, notes, corrections fiscales (v8.28.0) =======

def test_deux_erreurs_fiscales_corrigees():
    """Signalées par l'auteur, inspecteur des finances publiques, et
    vérifiées contre le BOFiP et le CGI avant correction."""
    import pense_bete
    points = {p["titre"]: p for g in pense_bete.oublis_frequents()
              for p in g["points"]}

    # 1. Le barème KILOMÉTRIQUE ne s'applique pas aux BIC ; le barème
    #    CARBURANT ne couvre que le carburant — péages et stationnement se
    #    déduisent EN PLUS. L'ancien texte disait « c'est l'un ou l'autre ».
    d = next(p for t, p in points.items() if "déplacement" in t.lower())
    assert "barème CARBURANT" in d["detail"]
    assert "péages" in d["detail"]
    assert "EN PLUS" in d["detail"]
    assert any("BAREME-000003" in s for s in d["sources"])

    # 2. Le LMNP au réel simplifié tient une comptabilité de TRÉSORERIE en
    #    cours d'année (option super-simplifiée, case sur la 2031-SD), avec
    #    constatation des créances et dettes à la clôture. L'ancien texte
    #    affirmait l'engagement pur.
    r = next(p for t, p in points.items() if "attachement" in t)
    assert "trésorerie" in r["detail"] and "super-simplifiée" in r["detail"]
    assert "2031" in r["detail"]
    assert any("302 septies A ter A" in s for s in r["sources"])


def test_durees_de_conservation_chiffrees_et_sourcees():
    import pense_bete
    points = {p["titre"]: p for g in pense_bete.oublis_frequents()
              for p in g["points"]}
    j = next(p for t, p in points.items() if "Justificatifs" in t)
    assert "3 ans" in j["detail"] and "10 ans" in j["detail"]
    assert "6 ans" in j["detail"]
    assert any("L. 169" in s for s in j["sources"])
    assert any("L. 102 B" in s for s in j["sources"])


def test_depots_precisent_les_espaces_et_le_chemin():
    import pense_bete
    points = {p["titre"]: p for g in pense_bete.oublis_frequents()
              for p in g["points"]}
    d = next(p for t, p in points.items() if "dépôts" in t or "dates" in t.lower())
    assert "PROFESSIONNEL" in d["detail"] and "PARTICULIER" in d["detail"]
    assert "2031" in d["detail"] and "2042-C-PRO" in d["detail"]
    assert "impots.gouv.fr" in d["detail"]


def test_actualites_facturation_electronique():
    import pense_bete
    a = pense_bete.actualites()
    assert a["verifie_le"]                       # daté : ces faits périment
    fait = a["faits"][0]
    # le point contre-intuitif : l'exonération de TVA ne dispense PAS de la
    # réception
    assert "261 D" in fait["detail"]
    assert "1er septembre 2026" in fait["detail"]
    assert "1er septembre 2027" in fait["detail"]
    assert any("DGFiP" in s for s in fait["sources"])
    # aucune plateforme n'est imposée
    assert "choix vous appartient" in fait["detail"]
    assert len(a["echeances"]) >= 5
    assert all({"quand", "quoi", "ou"} <= set(e) for e in a["echeances"])


def test_bloc_notes_persiste_dans_le_dossier(bien_nu):
    import pense_bete
    assert pense_bete.lire_notes(bien_nu) == ""
    pense_bete.ecrire_notes(bien_nu, "  ma note de veille  ")
    assert pense_bete.lire_notes(bien_nu) == "ma note de veille"
    pense_bete.ecrire_notes(bien_nu, "corrigée")
    assert pense_bete.lire_notes(bien_nu) == "corrigée"
    # stocké dans la table meta : suit donc sauvegardes et restaurations
    n = bien_nu.execute("SELECT COUNT(*) FROM meta WHERE cle=?",
                        (pense_bete.CLE_NOTES,)).fetchone()[0]
    assert n == 1


def test_actualites_ne_nomment_aucun_prestataire():
    """Les actualités viennent d'une lettre commerciale ; elles ne doivent
    reprendre que le fait réglementaire, jamais la plateforme qu'elle
    recommande."""
    import pense_bete
    texte = str(pense_bete.ACTUALITES).lower()
    # Les noms proscrits sont lus dans le dossier PRIVÉ : les inscrire ici
    # reviendrait à publier ce que le test est chargé de traquer — le
    # garde-fou du dépôt l'a d'ailleurs signalé sur ce fichier même.
    liste = os.path.join(HERE, "reference", "termes_a_anonymiser.txt")
    proscrits = ["plateforme agréée recommandée"]
    if os.path.exists(liste):
        proscrits += [x.strip() for x in open(liste, encoding="utf-8")
                      if x.strip() and not x.strip().startswith("#")]
    for nom in proscrits:
        assert nom.lower() not in texte, nom
    # aucune plateforme commerciale mise en avant
    assert "recommandons" not in texte


# === Retours d'usage d'une profane (v8.30.0) =============================

def test_annulation_disponible_dans_la_liste_des_operations():
    """Le bouton avait DISPARU de la page — perdu lors d'une restauration —
    alors que la route existait toujours. Il est de nouveau là, dans sa
    propre colonne à côté de la duplication."""
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    assert "/annuler" in p
    assert "Dupliquer</th>" in p and "Annuler</th>" in p
    # une opération déjà annulée n'offre plus ni duplication ni annulation
    assert "{% if op['annulee'] %}" in p


def test_couleurs_lisibles_sur_le_bandeau():
    """Le nom du dossier était un lien SANS couleur explicite : bleu sur
    bleu, illisible. L'onglet courant ne se distinguait pas non plus."""
    a = open(conftest.source("app.py"), encoding="utf-8").read()
    assert "color:#ffd54f" in a                 # nom du dossier
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    bloc = p.split("nav a.active")[1][:200]
    assert "#ffd54f" in bloc and "font-weight: 700" in bloc
    assert "background: rgba(0,0,0,.22)" in bloc


def test_premier_lancement_guide(tmp_path, monkeypatch):
    """Dossier vierge : l'onglet « Démarrer » passe en tête et la
    configuration initiale s'affiche — au lieu d'une page Saisie vide."""
    import importlib
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "s.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    cl = app_mod.app.test_client()
    h = cl.get("/dossiers").get_data(as_text=True)
    assert "configurons votre dossier" in h
    assert h.index("Démarrer") < h.index(">Saisie<")
    # l'exercice est DÉJÀ ouvert : on doit le dire, la question revenait
    assert "L'exercice est déjà ouvert" in h
    assert "reprendre un historique" in h.lower()
    # la configuration se fait ICI, plus dans Immobilisations
    assert 'action="/immobilisations/exploitant"' in h
    r = cl.post("/immobilisations/exploitant", data={
        "nom": "MARTIN", "siren": "123456789", "adresse": "X",
        "retour": "saisie"}, follow_redirects=True)
    assert "déjà OUVERT" in r.get_data(as_text=True)
    # une fois configuré, l'écran de démarrage disparaît
    assert "configurons votre dossier" not in cl.get("/dossiers").get_data(as_text=True)
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def test_avertissements_des_le_premier_exercice(bien_nu):
    """Le contrôle de plausibilité compare à l'an dernier : sur un dossier
    neuf il se taisait, laissant sans filet celui qui en a le plus besoin."""
    for m in range(1, 5):
        operations.saisir(bien_nu, type="loyer", montant=700,
                          periode=f"2026-{m:02d}",
                          date_operation=f"2026-{m:02d}-05", bien_id=1)
    codes = [a.code for a in controles.controler(bien_nu, 2026)]
    assert "POSTE_HABITUEL_ABSENT" in codes
    messages = " ".join(a.message for a in controles.controler(bien_nu, 2026))
    for attendu in ("intérêt d'emprunt", "assurance", "taxe foncière", "CFE"):
        assert attendu in messages, attendu
    # ce sont des rappels, pas des reproches : jamais bloquants
    assert all(a.niveau == controles.INFO
               for a in controles.controler(bien_nu, 2026)
               if a.code == "POSTE_HABITUEL_ABSENT")


def test_champ_retraitements_previent_du_double_comptage():
    """L'ALUR était donné en EXEMPLE alors qu'il est déjà réintégré
    automatiquement : le saisir là le comptait deux fois."""
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    bloc = p.split('name="retraitements"')[1][:1400]
    assert "laissez 0" in bloc
    assert "DOUBLE RETRAITEMENT" in bloc
    assert "DEUX FOIS" in bloc
    assert "(ex. fonds de travaux ALUR)" not in bloc   # l'ancien libellé


def test_lisez_moi_donne_le_cd_avant_la_commande():
    """« Aucun fichier ou dossier de ce nom » vient presque toujours d'un
    lancement depuis le mauvais répertoire."""
    assert not os.path.exists(os.path.join(HERE, "INSTALLATION.md"))
    t = open(os.path.join(HERE, "LISEZ-MOI.md"), encoding="utf-8").read()
    assert "cd ~/Documents/compta_lmnp" in t
    assert t.index("cd ~") < t.index("bash Compta-LMNP-Linux-macOS.sh\n```")
    # Le texte est retourné à la ligne : on cherche l'idée, pas la mise
    # en page — un test qui casse au premier reformatage ne sert personne.
    compact = " ".join(t.split())
    assert "Ouvrir un terminal ici" in compact


# === Module quittances ====================================================

@pytest.fixture()
def bailleur(tmp_path):
    import quittances
    c = init_db.init(str(tmp_path / "q.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) VALUES "
              "('MARTIN Camille', '123456789', '14 Rue Gergovia')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, adresse, "
              "date_acquisition, prix_total) VALUES "
              "(1, 'T2 Vichy', '8 av Thermale, 03200 Vichy', "
              "'2026-01-01', 100000)")
    c.commit()
    loc = quittances.ajouter_locataire(
        c, bien_id=1, nom="DUPONT Jean", date_entree="2026-01-01",
        loyer_mensuel=670, charges_mensuelles=50)
    yield c, loc
    c.close()


def test_quittance_lit_les_montants_dans_les_ecritures(bailleur):
    """Une quittance qui reposerait sur une saisie parallèle finirait par
    diverger de la comptabilité — et c'est elle, remise à un tiers, qui
    ferait foi contre le bailleur."""
    import quittances
    conn, loc = bailleur
    operations.saisir(conn, type="loyer", montant=670, periode="2026-03",
                      date_operation="2026-03-05", bien_id=1)
    conn.commit()
    q = quittances.emettre(conn, locataire_id=loc, periode="2026-03", forcer=True)
    assert q["loyer"] == pytest.approx(670.0)
    assert q["numero"] == 1


def test_numerotation_incrementale_et_sans_trou(bailleur):
    import quittances
    conn, loc = bailleur
    numeros = []
    for mois in ("2026-01", "2026-02", "2026-03"):
        numeros.append(quittances.emettre(
            conn, locataire_id=loc, periode=mois, loyer=670, charges=50,
            forcer=True)["numero"])
    assert numeros == [1, 2, 3]
    assert quittances.prochain_numero(conn) == 4


def test_quittance_refuse_les_trois_cas_dangereux(bailleur):
    import quittances
    conn, loc = bailleur
    quittances.emettre(conn, locataire_id=loc, periode="2026-03", loyer=670, forcer=True)
    # 1. deux quittances pour le même mois = deux preuves du même paiement
    with pytest.raises(ValueError, match="existe déjà"):
        quittances.emettre(conn, locataire_id=loc, periode="2026-03",
                           loyer=670, forcer=True)
    # 2. une quittance atteste d'un paiement REÇU
    with pytest.raises(ValueError, match="Aucun encaissement"):
        quittances.emettre(conn, locataire_id=loc, periode="2026-07")
    # 3. hors période de présence
    with pytest.raises(ValueError, match="n'occupe pas"):
        quittances.emettre(conn, locataire_id=loc, periode="2025-06",
                           loyer=670, forcer=True)


def test_quittance_imprimable_est_conforme(bailleur):
    import quittances
    conn, loc = bailleur
    q = quittances.emettre(conn, locataire_id=loc, periode="2026-03",
                           loyer=670, charges=50, forcer=True)
    d = quittances.detail(conn, q["id"])
    # la distinction loyer / charges est une OBLIGATION légale
    assert d["loyer"] == 670.0 and d["charges"] == 50.0
    assert d["total"] == 720.0
    assert d["periode_lettres"] == "mars 2026"
    assert d["bailleur"]["nom"] == "MARTIN Camille"
    assert d["bien_adresse"].startswith("8 av Thermale")


def test_aucune_donnee_de_naissance_nest_collectee():
    """Ces champs ont existé un temps comme options. Ils sont RETIRÉS : un
    champ qui ne sert à rien finit par être rempli, et une donnée qu'on ne
    détient pas est une donnée qu'on n'a ni à protéger, ni à justifier, ni
    à effacer sur demande."""
    import quittances
    for cible in ("quittances.py", "pages.py", "app.py", "schema.sql"):
        src = open(conftest.source(cible), encoding="utf-8").read()
        corps = "\n".join(ligne for ligne in src.splitlines()
                          if "naissance" not in ligne
                          or "RETIRÉS" in ligne or "ont existé" in ligne)
        assert "date_naissance" not in corps, cible
        assert "lieu_naissance" not in corps, cible
    # la colonne n'existe pas non plus en base
    assert "date_naissance" not in quittances.SCHEMA
    assert "lieu_naissance" not in quittances.SCHEMA
    import inspect
    sig = inspect.signature(quittances.ajouter_locataire)
    assert "date_naissance" not in sig.parameters
    assert "lieu_naissance" not in sig.parameters

def test_locataire_exige_le_minimum(bailleur):
    import quittances
    conn, _ = bailleur
    with pytest.raises(ValueError, match="nom du locataire"):
        quittances.ajouter_locataire(conn, bien_id=1, nom="  ",
                                     date_entree="2026-01-01")
    with pytest.raises(ValueError, match="Bien introuvable"):
        quittances.ajouter_locataire(conn, bien_id=99, nom="X",
                                     date_entree="2026-01-01")
    with pytest.raises(ValueError, match="AAAA-MM-JJ"):
        quittances.ajouter_locataire(conn, bien_id=1, nom="X",
                                     date_entree="01/01/2026")


# === Quittances : multi-biens, historique, non-régression (v8.31.0) ======

def test_numerotation_unique_a_travers_plusieurs_biens(tmp_path):
    """Série UNIQUE partagée par tous les logements, et non une série par
    bien : c'est la continuité de la suite qui la rend vérifiable."""
    import quittances
    c = init_db.init(str(tmp_path / "m.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    for lib in ("T2 Vichy", "Studio Riom", "T3 Issoire"):
        c.execute("INSERT INTO bien (exploitant_id, libelle, adresse, "
                  "date_acquisition, prix_total) VALUES "
                  "(1, ?, 'Adr', '2024-01-01', 100000)", (lib,))
    c.commit()
    locs = [quittances.ajouter_locataire(c, bien_id=b, nom=f"LOC{b}",
                                         date_entree="2024-01-01")
            for b in (1, 2, 3)]
    numeros = []
    for periode in ("2026-01", "2026-02"):
        for loc in locs:
            numeros.append(quittances.emettre(
                c, locataire_id=loc, periode=periode, loyer=600,
                forcer=True)["numero"])
    assert numeros == list(range(1, 7))          # continue
    assert len(set(numeros)) == len(numeros)     # sans doublon
    c.close()


def test_quittances_anciennes_restent_accessibles(tmp_path):
    import quittances
    c = init_db.init(str(tmp_path / "h.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, adresse, "
              "date_acquisition, prix_total) VALUES "
              "(1, 'T2', 'Adr', '2023-01-01', 100000)")
    c.commit()
    loc = quittances.ajouter_locataire(c, bien_id=1, nom="DUPONT",
                                       date_entree="2023-01-01")
    for an in ("2023", "2024", "2025", "2026"):
        quittances.emettre(c, locataire_id=loc, periode=f"{an}-05", loyer=600, forcer=True)
    assert len(quittances.lister(c)) == 4          # aucune limite d'ancienneté
    assert len(quittances.lister(c, 2023)) == 1
    vieille = [q for q in quittances.lister(c)
               if q["periode"].startswith("2023")][0]
    d = quittances.detail(c, vieille["id"])        # réimprimable
    assert d["periode_lettres"] == "mai 2023"
    c.close()


def test_locataire_sorti_ne_peut_plus_etre_quittance(tmp_path):
    import quittances
    c = init_db.init(str(tmp_path / "s.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, adresse, "
              "date_acquisition, prix_total) VALUES "
              "(1, 'T2', 'Adr', '2024-01-01', 100000)")
    c.commit()
    parti = quittances.ajouter_locataire(
        c, bien_id=1, nom="PARTI", date_entree="2024-01-01",
        date_sortie="2026-06-30")
    quittances.emettre(c, locataire_id=parti, periode="2026-05", loyer=600, forcer=True)
    with pytest.raises(ValueError, match="n'occupe pas"):
        quittances.emettre(c, locataire_id=parti, periode="2026-09", loyer=600)
    c.close()


def test_quittances_sans_effet_sur_la_comptabilite(bien_nu):
    """Une quittance ATTESTE d'un encaissement, elle ne le crée pas : elle
    ne doit toucher ni écriture, ni ligne, ni opération."""
    import quittances
    for m in range(1, 4):
        operations.saisir(bien_nu, type="loyer", montant=700,
                          periode=f"2026-{m:02d}",
                          date_operation=f"2026-{m:02d}-05", bien_id=1)
    bien_nu.commit()
    avant = tuple(bien_nu.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("ecriture", "ligne", "operation"))
    loc = quittances.ajouter_locataire(bien_nu, bien_id=1, nom="DUPONT",
                                       date_entree="2026-01-01")
    for m in range(1, 4):
        quittances.emettre(bien_nu, locataire_id=loc, periode=f"2026-{m:02d}", forcer=True)
    apres = tuple(bien_nu.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("ecriture", "ligne", "operation"))
    assert avant == apres
    # …et la clôture doit continuer de fonctionner à l'identique
    r = fiscal.cloturer(bien_nu, 2026, forcer=True)
    assert r["resultat_fiscal"] is not None


def test_quittances_absentes_du_fec(tmp_path):
    """Le FEC ne doit contenir que des écritures comptables."""
    import export_fec
    import quittances
    import valider_fec
    c = init_db.init(str(tmp_path / "f.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, adresse, "
              "date_acquisition, prix_total) VALUES "
              "(1, 'T2', 'Adr', '2026-01-01', 100000)")
    c.commit()
    operations.saisir(c, type="loyer", montant=700, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    loc = quittances.ajouter_locataire(c, bien_id=1, nom="ZZTOPLOCATAIRE",
                                       date_entree="2026-01-01")
    quittances.emettre(c, locataire_id=loc, periode="2026-01", forcer=True)
    c.commit()
    chemin = str(tmp_path / "fec.txt")
    export_fec.exporter(c, 2026, chemin)
    assert valider_fec.valider(chemin) == []
    contenu = open(chemin, encoding="utf-8").read()
    assert "ZZTOPLOCATAIRE" not in contenu
    c.close()


def test_base_ancienne_migre_vers_les_quittances(tmp_path):
    """Une installation antérieure n'a pas les tables : la migration doit
    les créer, et la page ne doit pas tomber même sans migration."""
    import sqlite3 as sq
    import migrations
    chemin = str(tmp_path / "vieille.db")
    c = init_db.init(chemin, "blanc", annee_cible=2026)
    c.execute("DROP TABLE IF EXISTS quittance")
    c.execute("DROP TABLE IF EXISTS locataire")
    c.execute("UPDATE meta SET valeur='5' WHERE cle='version_schema'")
    c.commit()
    c.close()
    migrations.migrer(chemin)
    c = sq.connect(chemin)
    tables = {r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"locataire", "quittance"} <= tables
    assert init_db.version_base(c) == init_db.VERSION_SCHEMA
    c.close()


def test_bandeau_aux_couleurs_asm():
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    assert "header { background: #002b5c" in p      # bleu marine
    bloc = p.split("nav a.active")[1][:200]
    assert "#ffd54f" in bloc                        # jaune


# === Reprise de PLUSIEURS FEC (v8.32.0) ==================================
# Un FEC isolé est une photographie ; plusieurs FEC consécutifs sont un
# film, et le film se vérifie tout seul. Trois contrôles deviennent
# possibles qu'un fichier unique rend impossibles.

REF = os.path.join(HERE, "reference")


def _fecs_reels():
    import glob
    return sorted(glob.glob(os.path.join(REF, "FEC_REFERENCE_*.txt")))


def test_ordre_deduit_du_contenu_pas_du_nom():
    """Le nom de fichier est une convention que rien ne garantit ; les
    dates d'écriture, elles, sont dans le fichier."""
    import migration_fec
    fics = _fecs_reels()
    if not fics:
        pytest.skip("dossier de référence absent")
    # envoyés dans le désordre
    ordre = migration_fec.ordonner([fics[2], fics[0], fics[1]])
    assert [x["annee"] for x in ordre] == [2023, 2024, 2025]
    assert all(not x["erreurs"] for x in ordre)


def test_jonction_des_bilans_compare_cloture_et_ouverture():
    """Comparer deux CLÔTURES successives n'aurait aucun sens : leur écart
    est simplement l'activité de l'année. Et le compte de résultat (12)
    doit être exclu, sans quoi chaque jonction produit un faux écart."""
    import migration_fec
    fics = _fecs_reels()
    if not fics:
        pytest.skip("dossier de référence absent")
    obs = migration_fec.controler_jonctions(migration_fec.ordonner(fics))
    assert len(obs) == 2                       # 3 exercices → 2 jonctions
    assert all(o["type"] == "ok" for o in obs), [o["message"] for o in obs]
    # la comparaison porte bien sur l'ouverture, pas sur la clôture
    src = open(conftest.source("migration_fec.py"), encoding="utf-8").read()
    assert "ouverture=True" in src
    assert 'compte.startswith("12")' in src


def test_trou_d_annee_signale():
    import migration_fec
    fics = _fecs_reels()
    if not fics:
        pytest.skip("dossier de référence absent")
    obs = migration_fec.controler_jonctions(
        migration_fec.ordonner([fics[0], fics[2]]))   # 2023 puis 2025
    assert any(o["type"] == "trou" for o in obs)
    assert "2024" in " ".join(o["message"] for o in obs)


def test_autocontrole_des_amortissements(tmp_path):
    """Confronte le plan recalculé aux dotations réellement passées : le
    « test en or » du projet, appliqué au dossier de celui qui migre."""
    import migration_fec
    fics = _fecs_reels()
    if not fics:
        pytest.skip("dossier de référence absent")
    c = init_db.init(str(tmp_path / "a.db"), "blanc", annee_cible=2026)
    ordre = migration_fec.ordonner(fics)
    # sans composant enregistré : on le dit, on ne compare pas
    obs = migration_fec.controler_amortissements(c, ordre)
    assert obs and all(o["type"] == "info" for o in obs)
    assert "aucun composant" in obs[0]["message"]
    # les dotations sont bien lues dans les fichiers
    for x in ordre:
        assert migration_fec.dotations_du_fec(x["chemin"]) > 0
    c.close()


def test_reprise_multi_rejoue_du_plus_ancien_au_plus_recent(tmp_path,
                                                            monkeypatch):
    import glob
    import importlib
    import io
    import sqlite3 as sq
    fics = _fecs_reels()
    if not fics:
        pytest.skip("dossier de référence absent")
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2030).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "s.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    cl = app_mod.app.test_client()
    envoi = [fics[2], fics[0], fics[1]]           # désordre volontaire
    data = {"fecs": [(io.BytesIO(open(f, "rb").read()), os.path.basename(f))
                     for f in envoi]}
    h = cl.post("/exercice/analyser-fec", data=data,
                content_type="multipart/form-data").get_data(as_text=True)
    # « exactement » et non plus « au centime » : depuis la passe K, le
    # contrôle distingue une jonction sans le moindre écart d'une jonction
    # dont les écarts restent sous la tolérance — laquelle vaut justement
    # un centime. Sur les FEC de référence, les deux jonctions sont exactes.
    assert "se raccordent exactement" in h      # jonctions vérifiées
    import re as _re
    jeton = _re.search(r'name="jeton" value="([0-9a-f]{32})"', h)
    assert jeton, "aucun jeton : l'analyse n'a rien proposé"
    r = cl.post("/exercice/reprendre-fec-multi",
                data={"jeton": jeton.group(1)}, follow_redirects=True)
    corps = r.get_data(as_text=True)
    assert "2023" in corps and "2024" in corps and "2025" in corps
    cx = sq.connect(db)
    annees = [x[0] for x in cx.execute(
        "SELECT annee FROM exercice ORDER BY annee")]
    assert annees[:3] == [2023, 2024, 2025]
    # chaque exercice porte ses écritures
    for a in (2023, 2024, 2025):
        n = cx.execute("SELECT COUNT(*) FROM ecriture WHERE exercice_annee=?",
                       (a,)).fetchone()[0]
        assert n > 20, (a, n)
    cx.close()
    del glob
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def test_analyse_nécrit_rien(tmp_path, monkeypatch):
    """Deux temps volontairement séparés : on ne défait pas trois exercices
    d'un clic, donc l'analyse doit être blanche."""
    import importlib
    import io
    import sqlite3 as sq
    fics = _fecs_reels()
    if not fics:
        pytest.skip("dossier de référence absent")
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2030).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "s.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    cl = app_mod.app.test_client()
    data = {"fecs": [(io.BytesIO(open(f, "rb").read()), os.path.basename(f))
                     for f in fics]}
    cl.post("/exercice/analyser-fec", data=data,
            content_type="multipart/form-data")
    cx = sq.connect(db)
    assert cx.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] == 0
    assert [x[0] for x in cx.execute("SELECT annee FROM exercice")] == [2030]
    cx.close()
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


# === Revue adversariale externe n° 2 (v8.33.0) ===========================
# Onze défauts annoncés, dix réfutés par mesure directe. Les tests
# ci-dessous FIGENT les réfutations : si un jour l'un de ces comportements
# changeait vraiment, il faudrait le savoir.

def test_prorata_est_bien_en_jours_reels():
    """L'audit affirmait un prorata MENSUEL. C'est l'invariant n° 5 du
    projet, prouvé contre trois liasses réelles."""
    import amortissement
    f = float(amortissement.fraction_prorata("2020-06-15", "2020-12-31"))
    assert f == pytest.approx(200 / 365, abs=1e-9)
    assert f != pytest.approx(6.5 / 12, abs=1e-4)


def test_plafond_39c_derive_des_produits_reels(tmp_path):
    """L'audit réclamait un prorata du plafond sur exercice court. Le
    plafond dérive des produits RÉELLEMENT saisis : il n'y a aucun montant
    annuel à proratiser."""
    import fiscal
    c = init_db.init(str(tmp_path / "c.db"), "blanc", annee_cible=2025)
    c.execute("UPDATE exercice SET date_debut='2025-04-01' WHERE annee=2025")
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2025-04-01', 100000, 0)")
    c.commit()
    for m in range(4, 13):
        operations.saisir(c, type="loyer", montant=1000,
                          periode=f"2025-{m:02d}",
                          date_operation=f"2025-{m:02d}-05", bien_id=1)
    c.commit()
    ag = fiscal.agregats(c, 2025)
    assert ag["plafond_39c"] == pytest.approx(9000.0)   # 9 mois, pas 12
    c.close()


def test_stock_39c_est_bien_neutralise_a_la_cession(tmp_path):
    """L'audit l'annonçait « non neutralisé ». La sortie est tracée par
    bien depuis toujours, et rendue visible à l'écran en v8.23.0."""
    import cession
    import fiscal
    import reprise
    c = init_db.init(str(tmp_path / "s.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2020-01-01', 100000, 0)")
    c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
              "duree_annees, date_mise_service, compte_immo, compte_amort, "
              "amortissable) VALUES (1, 'B', 100000, 10, '2020-01-01', "
              "'213150', '281315', 1)")
    c.commit()
    operations.saisir(c, type="loyer", montant=2000, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    c.commit()
    r1 = fiscal.cloturer(c, 2026, forcer=True)
    assert r1["suivi_39c"]["stock_cloture"] > 0
    reprise.ouvrir_exercice(c, 2027)
    operations.saisir(c, type="loyer", montant=2000, periode="2027-01",
                      date_operation="2027-01-05", bien_id=1)
    cession.ceder_bien(c, bien_id=1, date_cession="2027-06-30",
                       prix_cession=150000)
    r2 = fiscal.cloturer(c, 2027, forcer=True)
    assert r2["suivi_39c"]["stock_cloture"] == pytest.approx(0.0)
    sortie = c.execute("SELECT COALESCE(SUM(sortie_bien), 0) FROM "
                       "suivi_39c_bien WHERE exercice_annee=2027"
                       ).fetchone()[0]
    assert sortie > 0                      # la perte est TRACÉE
    assert r2["resultat_fiscal"] == pytest.approx(0.0)   # PV neutralisée
    c.close()


def test_recloture_refusee_apres_reouverture(tmp_path):
    """L'audit annonçait un double compte des dotations. La deuxième
    clôture est refusée en nommant l'écriture déjà passée."""
    import fiscal
    c = init_db.init(str(tmp_path / "r.db"), "blanc", annee_cible=2024)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2024-01-01', 90000, 0)")
    c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
              "duree_annees, date_mise_service, compte_immo, compte_amort, "
              "amortissable) VALUES (1, 'B', 90000, 30, '2024-01-01', "
              "'213150', '281315', 1)")
    c.commit()
    operations.saisir(c, type="loyer", montant=20000, periode="2024-01",
                      date_operation="2024-01-05", bien_id=1)
    c.commit()
    fiscal.cloturer(c, 2024, forcer=True)
    c.execute("UPDATE exercice SET statut='ouvert' WHERE annee=2024")
    c.commit()
    with pytest.raises(Exception, match="déjà générée"):
        fiscal.cloturer(c, 2024)
    assert c.execute("SELECT COUNT(*) FROM ecriture WHERE exercice_annee=2024 "
                     "AND piece_ref='DAA'").fetchone()[0] == 1
    c.close()


def test_composant_ajoute_a_un_bien_deja_amorti(tmp_path):
    """L'audit annonçait une VNC incohérente. Chaque composant suit son
    propre plan, et la somme est exacte."""
    import amortissement
    c = init_db.init(str(tmp_path / "k.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2020-01-01', 120000, 0)")
    c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
              "duree_annees, date_mise_service, compte_immo, compte_amort, "
              "amortissable) VALUES (1, 'Bati', 100000, 30, '2020-01-01', "
              "'213150', '281315', 1)")
    c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
              "duree_annees, date_mise_service, compte_immo, compte_amort, "
              "amortissable) VALUES (1, 'Cuisine', 20000, 10, '2023-01-01', "
              "'218100', '281810', 1)")
    c.commit()
    dots = {x["libelle"]: x["dotation"]
            for x in amortissement.dotations_exercice(c, 2026)}
    assert dots["Bati"] == pytest.approx(100000 / 30, abs=0.01)
    assert dots["Cuisine"] == pytest.approx(20000 / 10, abs=0.01)
    c.close()


def test_deficit_menace_par_le_39c_est_signale(tmp_path):
    """LE défaut réel de la revue : les deux reports n'ont pas la même
    durée de vie, et le 39 C s'impute en premier par construction. Le
    logiciel ne change pas cet ordre — il le SIGNALE, chiffré."""
    import fiscal
    c = init_db.init(str(tmp_path / "m.db"), "blanc", annee_cible=2025)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2020-01-01', 100000, 0)")
    c.execute("INSERT INTO exercice (annee, date_debut, date_fin, statut) "
              "VALUES (2024, '2024-01-01', '2024-12-31', 'clos')")
    c.commit()
    c.execute("INSERT INTO deficit_lmnp (annee_origine, montant_initial, "
              "solde, annee_expiration) VALUES (2017, 5000, 5000, 2027)")
    c.execute("INSERT INTO suivi_39c (exercice_annee, stock_ouverture, "
              "report_annee, utilisation_annee, stock_cloture) "
              "VALUES (2024, 0, 5000, 0, 5000)")
    c.commit()
    operations.saisir(c, type="loyer", montant=5000, periode="2025-01",
                      date_operation="2025-01-05", bien_id=1)
    c.commit()
    fiscal.cloturer(c, 2025, forcer=True)
    alertes = [a for a in controles.controler(c, 2025)
               if a.code == "DEFICIT_MENACE_PAR_39C"]
    assert alertes, "le déficit menacé n'est pas signalé"
    m = alertes[0].message
    assert "2017" in m and "2027" in m          # millésime et péremption
    assert "dix ans" in m and "sans limite de temps" in m
    assert "professionnel" in m                 # on ne tranche pas seul
    c.close()


def test_le_logiciel_ne_reordonne_pas_silencieusement():
    """Savoir si la reprise du 39 C peut être différée se discute. Trancher
    en silence serait pire que le défaut lui-même."""
    src = open(conftest.source("controles.py"), encoding="utf-8").read()
    bloc = src.split("def c_deficit_menace_par_le_39c")[1][:2000]
    assert "ne CHANGE PAS cet ordre" in bloc
    assert "se discute" in bloc


# === Revue du catalogue de gabarits (v8.34.0) ============================
# Revue étroite et honnête : 36 lignes, verdicts nuancés, sources
# vérifiables, incertitude assumée. Quatre constats retenus, quatre
# réfutés PAR LA PRATIQUE PROFESSIONNELLE du dossier de référence.

def test_comptes_alignes_sur_la_pratique_du_cabinet():
    """La revue proposait de « corriger » quatre comptes au nom du PCG
    strict. Le cabinet dont les liasses servent d'étalon emploie
    exactement les nôtres : essence en 606200, toutes primes d'assurance
    en 616110, impôts locaux en 635130. Un plan comptable est un cadre que
    les cabinets adaptent ; changer nos comptes nous éloignerait de la
    seule référence vérifiée dont dispose le projet."""
    import gabarits
    attendus = {"carburant": "606200", "assurance": "616110",
                "assurance_emprunteur": "616110", "assurance_gli": "616110",
                "taxe_fonciere": "635130", "teom": "635130",
                "frais_bancaires": "627810"}
    for cle, compte in attendus.items():
        assert gabarits.GABARITS[cle]["compte"] == compte, cle
    # …et ces comptes existent bien au plan livré
    import init_db
    import tempfile
    c = init_db.init(tempfile.mkdtemp() + "/p.db", "blanc", annee_cible=2026)
    for compte in set(attendus.values()):
        assert c.execute("SELECT 1 FROM compte WHERE numero=?",
                         (compte,)).fetchone(), compte
    c.close()


def test_restitution_de_charges_au_locataire(bien_nu):
    """La revue signalait qu'une régularisation en faveur du locataire
    était impossible à saisir : les montants sont strictement positifs
    partout. La réponse n'est pas d'affaiblir cette garde — c'est elle qui
    protège des saisies inversées — mais d'ajouter la NATURE manquante."""
    import fiscal
    operations.saisir(bien_nu, type="regularisation_charges", montant=400,
                      periode="2026-06", date_operation="2026-06-30",
                      bien_id=1)
    r = operations.saisir(bien_nu, type="restitution_charges", montant=150,
                          periode="2026-12", date_operation="2026-12-31",
                          bien_id=1)
    lignes = bien_nu.execute(
        "SELECT compte_num, debit, credit FROM ligne l "
        "JOIN ecriture e ON e.id = l.ecriture_id WHERE e.ecriture_num=?",
        (r["ecriture_num"],)).fetchall()
    # le compte de PRODUIT est débité : son solde diminue
    assert ("708810", 150.0, 0.0) in [tuple(x) for x in lignes]
    # aucune valeur négative : un FEC n'en admet pas
    assert all(x[1] >= 0 and x[2] >= 0 for x in lignes)
    # les agrégats nettent d'eux-mêmes (ils raisonnent par classe)
    assert fiscal.agregats(bien_nu, 2026)["produits"] == pytest.approx(250.0)


def test_montant_negatif_toujours_refuse_ailleurs(bien_nu):
    with pytest.raises(ValueError, match="strictement positif"):
        operations.saisir(bien_nu, type="loyer", montant=-500,
                          periode="2026-06", date_operation="2026-06-30",
                          bien_id=1)
    # …et le message oriente vers la bonne nature
    try:
        operations.saisir(bien_nu, type="loyer", montant=-500,
                          periode="2026-06", date_operation="2026-06-30",
                          bien_id=1)
    except ValueError as e:
        assert "Restitution de charges" in str(e)
        assert "Annuler" in str(e)


def test_quatre_pieges_fiscaux_documentes():
    """Constats retenus de la revue, chacun sourcé."""
    import pense_bete
    points = {p["titre"]: p for g in pense_bete.oublis_frequents()
              for p in g["points"]}
    titres = " ".join(points)

    # 1. la part restituable d'une caution n'est pas une charge
    caution = next(p for t, p in points.items() if "Caution mutuelle" in t)
    assert "restituable" in caution["detail"] and "CRÉANCE" in caution["detail"]
    assert any("275" in s for s in caution["sources"])

    # 2. l'option sur les frais d'acquisition est globale et irrévocable,
    #    et un bien acquis avant affectation n'en fait pas profiter
    fa = next(p for t, p in points.items()
              if "Frais d'acquisition : deux conditions" in t)
    assert "GLOBALE" in fa["detail"] and "irrévocable" in fa["detail"]
    assert "AVANT" in fa["detail"] and "affectation" in fa["detail"]
    assert any("38 quinquies" in s for s in fa["sources"])

    # 3. la taxe d'habitation du propriétaire qui garde la jouissance
    assert "Taxe d'habitation" in titres

    # 4. l'indemnité sur bien détruit relève des plus-values
    ind = next(p for t, p in points.items() if "Indemnité d'assurance" in t)
    assert "plus-values" in ind["detail"]
    assert any("39 duodecies" in s for s in ind["sources"])


# === Revue adversariale externe n° 3 (v8.35.0) ===========================
# Huit défauts annoncés, HUIT confirmés — la première revue dont tous les
# constats tiennent. Elle avait rejoué les scénarios contre une vraie base
# et donnait les montants exacts.

def _dossier_cede(tmp_path, vb=8000, duree=8, dms="2022-01-01",
                  cession_date="2026-03-31", prix=0):
    import cession
    c = init_db.init(str(tmp_path / f"c{vb}.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) VALUES (1, 'A', ?, ?, 0)",
              (dms, vb))
    c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
              "duree_annees, date_mise_service, compte_immo, compte_amort, "
              "amortissable) VALUES (1, 'M', ?, ?, ?, '218400', '281840', 1)",
              (vb, duree, dms))
    c.commit()
    operations.saisir_acquisition(c, compte_immo="218400", montant=vb,
                                  date_operation="2026-01-01", libelle="M")
    operations.saisir(c, type="loyer", montant=6000, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    operations.saisir(c, type="assurance", montant=1000,
                      date_operation="2026-02-05", bien_id=1)
    c.commit()
    cession.ceder_bien(c, bien_id=1, date_cession=cession_date,
                       prix_cession=prix)
    return c


def test_charges_exceptionnelles_entrent_dans_le_resultat(tmp_path):
    """D8a — les produits étaient captés par le préfixe « 7 », donc le prix
    de cession y entrait, mais AUCUNE charge de classe 67 ne l'était : la
    ligne 310 comptait la recette de la vente sans sa contrepartie."""
    import fiscal
    c = _dossier_cede(tmp_path)
    rc = fiscal.cloturer(c, 2026, forcer=True)
    L = liasse.generer(c, 2026)
    assert L["f2033b"]["benefice_ou_perte_310"] == pytest.approx(
        rc["agregats"]["resultat_comptable"], abs=0.01)
    assert L["f2033b"]["charges_exceptionnelles_300"] > 0
    c.close()


def test_2033c_exclut_les_biens_cedes(tmp_path):
    """D8b — un composant sorti du bilan restait au tableau des
    immobilisations : les deux divergeaient définitivement."""
    import fiscal
    c = _dossier_cede(tmp_path, vb=9000)
    fiscal.cloturer(c, 2026, forcer=True)
    L = liasse.generer(c, 2026)
    assert L["f2033c"]["totaux"]["brut_fin"] == pytest.approx(0.0, abs=0.01)
    c.close()


def test_stock_39c_survit_a_une_annee_manquante(tmp_path):
    """D2 — la lecture stricte de N-1 remettait le stock à zéro dès qu'un
    exercice manquait, et cassait l'invariant « Σ par bien = global »."""
    import fiscal
    c = init_db.init(str(tmp_path / "m.db"), "blanc", annee_cible=2023)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2020-01-01', 100000, 0)")
    c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
              "duree_annees, date_mise_service, compte_immo, compte_amort, "
              "amortissable) VALUES (1, 'B', 100000, 25, '2020-01-01', "
              "'213150', '281315', 1)")
    c.commit()
    operations.saisir(c, type="loyer", montant=9000, periode="2023-01",
                      date_operation="2023-01-05", bien_id=1)
    operations.saisir(c, type="maintenance", montant=9000,
                      date_operation="2023-02-05", bien_id=1)
    c.commit()
    r23 = fiscal.cloturer(c, 2023, forcer=True)
    assert r23["suivi_39c"]["stock_cloture"] == pytest.approx(4000.0)
    # 2024 n'est JAMAIS ouvert
    c.execute("INSERT INTO exercice (annee, date_debut, date_fin, statut) "
              "VALUES (2025, '2025-01-01', '2025-12-31', 'ouvert')")
    c.commit()
    operations.saisir(c, type="loyer", montant=9000, periode="2025-01",
                      date_operation="2025-01-05", bien_id=1)
    operations.saisir(c, type="maintenance", montant=2000,
                      date_operation="2025-02-05", bien_id=1)
    c.commit()
    r25 = fiscal.cloturer(c, 2025, forcer=True)
    assert r25["suivi_39c"]["stock_ouverture"] == pytest.approx(4000.0)
    assert r25["resultat_fiscal"] == pytest.approx(0.0)   # et non 3 000
    par_bien = sum(x[0] for x in c.execute(
        "SELECT stock_cloture FROM suivi_39c_bien WHERE exercice_annee=2025"))
    assert par_bien == pytest.approx(r25["suivi_39c"]["stock_cloture"], abs=0.01)
    c.close()


def test_dotation_de_cession_nest_pas_proratisee_deux_fois():
    """D3 — l'annuité du plan est DÉJÀ proratisée ; la multiplier encore
    par la fraction 1er janvier → cession se trompait dans les deux sens."""
    import datetime
    import cession
    # mise en service en cours d'année de cession
    dot, _ = cession._dotation_prorata(10000, 10, "2026-03-01", 2026,
                                       datetime.date(2026, 9, 30))
    assert dot == pytest.approx(586.30, abs=0.01)      # et non 627,05
    # dernière annuité, tronquée par la fin de vie
    dot, _ = cession._dotation_prorata(8000, 8, "2018-07-01", 2026,
                                       datetime.date(2026, 6, 30))
    assert dot == pytest.approx(495.89, abs=0.01)      # et non 245,91
    # plan déjà terminé : plus rien à doter
    dot, _ = cession._dotation_prorata(8000, 8, "2018-07-01", 2027,
                                       datetime.date(2027, 6, 30))
    assert dot == pytest.approx(0.0)


def test_changement_de_duree_ne_sur_amortit_pas(tmp_path):
    """D4 — le plan se recalculait à neuf, sans borne sur ce qui avait
    déjà été comptabilisé : un allongement de durée après trois exercices
    aurait porté le cumul au-delà de la valeur brute."""
    import fiscal
    import reprise
    c = init_db.init(str(tmp_path / "d.db"), "blanc", annee_cible=2022)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2022-01-01', 8000, 0)")
    c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
              "duree_annees, date_mise_service, compte_immo, compte_amort, "
              "amortissable) VALUES (1, 'M', 8000, 5, '2022-01-01', "
              "'218400', '281840', 1)")
    c.commit()
    operations.saisir_acquisition(c, compte_immo="218400", montant=8000,
                                  date_operation="2022-01-01", libelle="M")
    for a in (2022, 2023, 2024):
        if a > 2022:
            reprise.ouvrir_exercice(c, a)
        operations.saisir(c, type="loyer", montant=9000, periode=f"{a}-01",
                          date_operation=f"{a}-01-05", bien_id=1)
        c.commit()
        fiscal.cloturer(c, a, forcer=True)
    c.execute("UPDATE composant SET duree_annees=8 WHERE id=1")
    c.commit()
    for a in range(2025, 2031):
        reprise.ouvrir_exercice(c, a)
        operations.saisir(c, type="loyer", montant=9000, periode=f"{a}-01",
                          date_operation=f"{a}-01-05", bien_id=1)
        c.commit()
        fiscal.cloturer(c, a, forcer=True)
    cumul = c.execute(
        "SELECT ROUND(SUM(l.credit - l.debit), 2) FROM ligne l "
        "JOIN ecriture e ON e.id = l.ecriture_id "
        "WHERE l.compte_num='281840' AND e.exercice_annee=2030").fetchone()[0]
    assert cumul <= 8000.01, f"sur-amortissement : {cumul}"
    assert cumul == pytest.approx(8000.0, abs=0.01)   # et il va bien au bout
    c.close()


def test_docstring_nencourage_plus_le_double_retraitement():
    """D5 — elle donnait le fonds ALUR en exemple de saisie manuelle,
    alors qu'il est réintégré automatiquement : les deux s'additionnaient."""
    src = open(conftest.source("fiscal.py"), encoding="utf-8").read()
    tete = src[:src.index('"""', src.index('"""') + 3)]
    assert "NE PAS y saisir le fonds de travaux ALUR" in tete
    assert "renseigné au cas par cas (ex. réintégration du fonds" not in tete


def test_bien_cede_emporte_sa_part_du_report(tmp_path):
    """D6 — les poids de ventilation venaient du plan d'amortissement, qui
    ignore les biens cédés : leur part de report restait attachée aux
    autres au lieu d'être perdue avec eux."""
    import cession
    import fiscal
    c = init_db.init(str(tmp_path / "v.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    for lib in ("A", "B"):
        c.execute("INSERT INTO bien (exploitant_id, libelle, "
                  "date_acquisition, prix_total, quote_part_terrain) "
                  "VALUES (1, ?, '2020-01-01', 200000, 0)", (lib,))
    for bid in (1, 2):
        c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
                  "duree_annees, date_mise_service, compte_immo, "
                  "compte_amort, amortissable) VALUES (?, 'c', 200000, 20, "
                  "'2020-01-01', '213150', '281315', 1)", (bid,))
    c.commit()
    # Loyers VOLONTAIREMENT insuffisants pour les deux biens : depuis la
    # passe I, le report se répartit selon l'insuffisance de chacun
    # (dotation moins marge locative), et non plus au prorata des seules
    # dotations. Un bien dont les loyers couvriraient sa dotation ne
    # produirait aucun report — ce test porte sur la SORTIE de la part d'un
    # bien cédé, il lui faut donc une part à emporter.
    for bid in (1, 2):
        operations.saisir(c, type="loyer", montant=1000, periode="2026-01",
                          date_operation="2026-01-05", bien_id=bid)
    c.commit()
    cession.ceder_bien(c, bien_id=1, date_cession="2026-06-30",
                       prix_cession=250000)
    r = fiscal.cloturer(c, 2026, forcer=True)
    lignes = {x[0]: x for x in c.execute(
        "SELECT bien_id, ROUND(report_bien,2), ROUND(sortie_bien,2), "
        "ROUND(stock_cloture,2) FROM suivi_39c_bien WHERE exercice_annee=2026")}
    assert lignes[1][1] > 0, "le bien cédé n'a reçu aucun report"
    assert lignes[1][2] > 0, "sa part n'est pas sortie avec lui"
    assert lignes[1][3] == pytest.approx(0.0)
    total = sum(x[3] for x in lignes.values())
    assert total == pytest.approx(r["suivi_39c"]["stock_cloture"], abs=0.01)
    c.close()


def test_cases_2042c_sur_la_meme_base(tmp_path):
    """D1 — 5NA était donné AVANT imputation et 5GJ APRÈS. L'administration
    imputait donc une seconde fois un déficit déjà consommé : impôt sur un
    bénéfice qui ne l'était pas, et reliquat perdu."""
    import fiscal
    import reprise
    c = init_db.init(str(tmp_path / "a.db"), "blanc", annee_cible=2025)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2025-01-01', 50000, 1.0)")
    c.commit()
    operations.saisir(c, type="loyer", montant=2000, periode="2025-01",
                      date_operation="2025-01-05", bien_id=1)
    operations.saisir(c, type="maintenance", montant=10000,
                      date_operation="2025-02-05", bien_id=1)
    c.commit()
    fiscal.cloturer(c, 2025, forcer=True)                    # déficit 8 000
    reprise.ouvrir_exercice(c, 2026)
    operations.saisir(c, type="loyer", montant=9000, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    operations.saisir(c, type="maintenance", montant=4000,
                      date_operation="2026-02-05", bien_id=1)
    c.commit()
    fiscal.cloturer(c, 2026, forcer=True)                    # bénéfice 5 000
    aide = liasse.generer(c, 2026)["aide_2042c"]
    assert aide["case_5NA"] == 5000             # bénéfice avant imputation
    deficits = {d["annee_origine"]: d["montant"]
                for d in aide["cases_deficits_anterieurs"]}
    assert deficits.get(2025) == 8000, deficits  # déficit avant imputation
    c.close()


# === Revue Passe A — lecture, validation, migration FEC (v8.36.0) ========
# 14 points signalés, 11 retenus, plus 2 défauts découverts en vérifiant.
# Le corpus le plus exposé du logiciel : une erreur ici contamine une
# migration entière en silence.

COLS_FEC = ["JournalCode", "JournalLib", "EcritureNum", "EcritureDate",
            "CompteNum", "CompteLib", "CompAuxNum", "CompAuxLib", "PieceRef",
            "PieceDate", "EcritureLib", "Debit", "Credit", "EcritureLet",
            "DateLet", "ValidDate", "Montantdevise", "Idevise"]


def _l_fec(journal, num, date, compte, debit=0, credit=0, lib="Lib"):
    return "\t".join([
        journal, journal, str(num), date, compte, "Lib", "", "", "P", date,
        lib,
        f"{debit:.2f}".replace(".", ",") if debit else "",
        f"{credit:.2f}".replace(".", ",") if credit else "",
        "", "", date, "", ""])


def _ecrire_fec(chemin, lignes, encodage="utf-8"):
    open(chemin, "w", encoding=encodage, newline="").write(
        "\t".join(COLS_FEC) + "\r\n" + "\r\n".join(lignes) + "\r\n")


def test_guillemet_navale_plus_les_lignes_suivantes(tmp_path):
    """Le format FEC ne donne AUCUN rôle au guillemet, mais le lecteur CSV
    de Python le traite comme un délimiteur : un seul guillemet non refermé
    faisait fusionner les lignes jusqu'au suivant, qui disparaissaient de
    la balance sans un mot."""
    import fec_io
    p = str(tmp_path / "g.txt")
    _ecrire_fec(p, [
        _l_fec("AC", 1, "20260105", "606300", 100, 0, "Achat"),
        _l_fec("AC", 1, "20260105", "401000", 0, 100, "Achat"),
        _l_fec("AC", 2, "20260110", "606300", 300, 0, '"Ravalement facade'),
        _l_fec("AC", 2, "20260110", "401000", 0, 300, "Rav"),
        _l_fec("BQ", 3, "20260125", "512000", 900, 0, 'Peinture "Salon'),
        _l_fec("BQ", 3, "20260125", "108000", 0, 900, "Peint"),
    ])
    _, lignes = fec_io.lire_brut(p)
    assert len(lignes) == 6
    assert lignes[2][10] == '"Ravalement facade'    # libellé intact


def test_encodages_autorises_par_l_arrete(tmp_path):
    """L'arrêté A47 A-1 autorise l'ISO-8859-15, et Excel ajoute une marque
    d'ordre des octets. Les deux rendaient le fichier illisible — y compris
    par le validateur, dont c'était le rôle de le dire."""
    import fec_io
    p = str(tmp_path / "bom.txt")
    _ecrire_fec(p, [_l_fec("AC", 1, "20260105", "606300", 100)], "utf-8-sig")
    entete, _ = fec_io.lire_brut(p)
    assert entete[0] == "JournalCode"               # BOM retiré
    p2 = str(tmp_path / "iso.txt")
    open(p2, "wb").write(
        ("\t".join(COLS_FEC) + "\r\n"
         + _l_fec("AC", 1, "20260105", "606300", 100, 0, "Réparation")
         + "\r\n").encode("iso-8859-15"))
    _, lignes = fec_io.lire_brut(p2)
    assert lignes[0][10] == "Réparation"


def test_a_nouveaux_reprennent_la_tresorerie(tmp_path):
    """Les classes 3 et 5 étaient omises du bilan d'ouverture. La 5 est
    celle de la BANQUE : tout dossier bancarisé — le cas ordinaire chez un
    cabinet — produisait des à-nouveaux déséquilibrés du montant exact du
    solde, et la reprise s'arrêtait en accusant une écriture que
    l'utilisateur n'avait jamais saisie."""
    import reprise
    p = str(tmp_path / "an.txt")
    _ecrire_fec(p, [
        _l_fec("AN", 1, "20250101", "213000", 90000, 0),
        _l_fec("AN", 1, "20250101", "281300", 0, 20000),
        _l_fec("AN", 1, "20250101", "164000", 0, 50000),
        _l_fec("AN", 1, "20250101", "512000", 4200, 0),
        _l_fec("AN", 1, "20250101", "108000", 0, 24200),
        _l_fec("OD", 2, "20251231", "606100", 5800, 0),
        _l_fec("OD", 2, "20251231", "512000", 0, 5800),
    ])
    c = init_db.init(str(tmp_path / "a.db"), "blanc", annee_cible=2026)
    reprise.construire_an(c, p, 2026)
    tresorerie = c.execute(
        "SELECT ROUND(SUM(debit - credit), 2) FROM ligne "
        "WHERE compte_num='512000'").fetchone()[0]
    assert tresorerie == pytest.approx(-1600.0)
    d, cr = c.execute(
        "SELECT ROUND(SUM(debit), 2), ROUND(SUM(credit), 2) FROM ligne l "
        "JOIN ecriture e ON e.id = l.ecriture_id "
        "WHERE e.journal_code='AN'").fetchone()
    assert d == pytest.approx(cr)
    # …et une seconde reprise doublerait le bilan : elle est refusée.
    # Le message a changé en passe K : la garde ne regarde plus seulement
    # le journal AN, mais le LOT complet (à-nouveaux + OD d'affectation),
    # dont la suppression d'une moitié permettait la reconstruction.
    with pytest.raises(ValueError, match="contient déjà"):
        reprise.construire_an(c, p, 2026)
    c.close()


def test_comptes_absents_du_plan_sont_crees_avec_leur_type(tmp_path):
    """Découvert en vérifiant : le rejeu créait les comptes sans `type`,
    colonne NOT NULL — et la reprise ne les créait pas du tout, échouant
    sur une contrainte de clé étrangère qui ne nommait même pas le compte."""
    import fec_io
    import rejeu_fec
    p = str(tmp_path / "f.txt")
    _ecrire_fec(p, [
        _l_fec("AC", 1, "20260110", "615000", 1200, 0),
        # 512000 : encore absent du plan livré. 401000 y est entré avec la
        # passe E (E-10) — il ne peut plus servir à tester la CRÉATION.
        _l_fec("AC", 1, "20260110", "512000", 0, 1200),
    ])
    c = init_db.init(str(tmp_path / "b.db"), "blanc", annee_cible=2026)
    r = rejeu_fec.rejouer(c, p, 2026)
    assert set(r["comptes_crees"]) >= {"615000", "512000"}
    types = dict(c.execute(
        "SELECT numero, type FROM compte WHERE numero IN ('615000','512000')"))
    assert types["615000"] == "charge" and types["512000"] == "actif"
    # les comptes d'amortissement ont leur type propre, pas « passif »
    assert fec_io.type_du_compte("281315") == "amortissement"
    assert fec_io.type_du_compte("512000") == "actif"
    c.close()


def test_rejeu_respecte_la_numerotation_par_journal(tmp_path):
    """Beaucoup de logiciels de cabinet numérotent PAR journal. Grouper sur
    le seul numéro fusionnait une facture d'achat et son règlement bancaire
    en une écriture unique — balances exactes, donc invisible, mais
    l'exercice rejoué n'était plus le FEC source."""
    import export_fec
    import rejeu_fec
    import valider_fec
    p = str(tmp_path / "j.txt")
    _ecrire_fec(p, [
        _l_fec("AC", 1, "20260110", "615000", 1200, 0),
        _l_fec("AC", 1, "20260110", "401000", 0, 1200),
        _l_fec("BQ", 1, "20260125", "401000", 1200, 0),
        _l_fec("BQ", 1, "20260125", "512000", 0, 1200),
    ])
    c = init_db.init(str(tmp_path / "c.db"), "blanc", annee_cible=2026)
    rejeu_fec.rejouer(c, p, 2026)
    ecr = [tuple(x) for x in c.execute(
        "SELECT ecriture_num, journal_code, ecriture_date FROM ecriture "
        "ORDER BY ecriture_num")]
    assert len(ecr) == 2, ecr
    assert ecr[0][1] == "AC" and ecr[1][1] == "BQ"
    assert ecr[0][2] == "2026-01-10" and ecr[1][2] == "2026-01-25"
    q = str(tmp_path / "re.txt")
    export_fec.exporter(c, 2026, q)
    assert valider_fec.valider(q) == []
    c.close()


def test_rejeu_interrompu_ne_laisse_rien(tmp_path):
    """Sans rollback, une reprise interrompue laissait une transaction
    ouverte que le premier commit venu d'ailleurs figeait : exercice à
    moitié repris, sans rapport et sans moyen de savoir où on en était."""
    import rejeu_fec
    p = str(tmp_path / "ko.txt")
    _ecrire_fec(p, [
        _l_fec("AC", 1, "20260110", "615000", 100, 0),
        _l_fec("AC", 1, "20260110", "401000", 0, 100),
        _l_fec("AC", 2, "20260111", "615000", 50, 0),
        _l_fec("AC", 2, "20260111", "401000", 0, 999),   # déséquilibrée
    ])
    c = init_db.init(str(tmp_path / "e.db"), "blanc", annee_cible=2026)
    with pytest.raises(Exception, match="déséquilibrée"):
        rejeu_fec.rejouer(c, p, 2026)
    c.commit()                       # un commit venu d'ailleurs
    assert c.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] == 0
    c.close()


def test_controle_amortissements_parle_quand_le_fec_est_muet(tmp_path):
    """Le contrôle « le plus utile d'une migration » se taisait justement
    quand le FEC ne portait aucune dotation — le cas où le cumul du
    logiciel s'apprête à dépasser durablement celui du cabinet."""
    import migration_fec
    c = init_db.init(str(tmp_path / "m.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2023-10-15', 100000, 0)")
    c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
              "duree_annees, date_mise_service, compte_immo, compte_amort, "
              "amortissable) VALUES (1, 'GO', 100000, 50, '2023-10-15', "
              "'213150', '281315', 1)")
    c.commit()
    p = str(tmp_path / "sansdot.txt")
    _ecrire_fec(p, [
        _l_fec("AC", 1, "20231110", "606300", 100, 0),
        _l_fec("AC", 1, "20231110", "401000", 0, 100),
    ])
    obs = migration_fec.controler_amortissements(
        c, [{"chemin": p, "annee": 2023, "erreurs": []}])
    assert obs, "le contrôle est resté muet"
    assert obs[0]["type"] == "ecart"
    assert "AUCUNE dotation" in obs[0]["message"]
    c.close()


def test_regle_a_date_identique_remplace(tmp_path):
    """Deux versions à la même date d'effet rendaient le choix arbitraire :
    le menu affichait la nouvelle règle, le moteur appliquait l'ancienne."""
    import parametres
    c = init_db.init(str(tmp_path / "r.db"), "blanc", annee_cible=2026)
    parametres.definir(c, "seuil_immobilisation", 500, "2023-01-01",
                       "test initial")
    parametres.definir(c, "seuil_immobilisation", 900, "2023-01-01",
                       "correction rétroactive")
    n = c.execute("SELECT COUNT(*) FROM regle_fiscale WHERE cle=? "
                  "AND date_debut=?",
                  ("seuil_immobilisation", "2023-01-01")).fetchone()[0]
    assert n == 1, "deux versions coexistent à date égale"
    assert parametres.valeur(c, "seuil_immobilisation", 2024) == 900
    c.close()


# === Revue Passe B — cycle de vie du dossier (v8.37.0) ===================
# 19 points signalés, 13 retenus. Trois chemins de PERTE DE DONNÉES.

def test_init_ne_detruit_pas_une_base_existante(tmp_path):
    """Le plus grave de la passe : `init()` supprimait le fichier sans un
    mot, et la ligne d'usage donnée en tête du mode d'emploi visait par
    défaut la base du dossier principal. La base neuve étant cohérente,
    rien ne distinguait la destruction d'un bug d'affichage."""
    import sqlite3 as sq
    db = str(tmp_path / "compta.db")
    c = init_db.init(db, "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total) VALUES (1, 'A', '2026-01-01', 100000)")
    c.commit()
    for m in range(1, 13):
        operations.saisir(c, type="loyer", montant=700, periode=f"2026-{m:02d}",
                          date_operation=f"2026-{m:02d}-05", bien_id=1)
    c.commit()
    c.close()
    with pytest.raises(FileExistsError, match="existe déjà"):
        init_db.init(db, "blanc", annee_cible=2026)
    assert sq.connect(db).execute(
        "SELECT COUNT(*) FROM ecriture").fetchone()[0] == 12
    # …et forcer prend une sauvegarde AVANT de détruire
    c = init_db.init(db, "blanc", annee_cible=2026, ecraser=True)
    c.close()
    sv = os.listdir(str(tmp_path / "sauvegardes"))
    assert any("avant-reinitialisation" in x for x in sv), sv


def test_annee_validee_avant_toute_destruction(tmp_path):
    """Le mode démo insère 2025 en dur : `--annee 2025` violait l'unicité
    APRÈS avoir supprimé la base."""
    with pytest.raises(ValueError, match="réserve l'exercice 2025"):
        init_db.init(str(tmp_path / "x.db"), "demo", annee_cible=2025)
    assert not os.path.exists(str(tmp_path / "x.db"))


def test_repli_du_dossier_de_demonstration(tmp_path):
    """« fec_path or fec_defaut » retenait une chaîne non vide même quand
    le fichier n'existait pas : le repli sur le jeu anonymisé — sa seule
    raison d'être — n'était jamais atteint."""
    src = open(conftest.source("init_db.py"), encoding="utf-8").read()
    assert "os.path.exists(fec_path)" in src
    assert 'p.add_argument("--fec", default=None)' in src


def _bailleur_quittances(tmp_path, nom="q"):
    import quittances
    c = init_db.init(str(tmp_path / f"{nom}.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, adresse, "
              "date_acquisition, prix_total) "
              "VALUES (1, 'T3', 'Adr', '2024-01-01', 100000)")
    c.commit()
    return c, quittances


def test_colocation_pas_deux_quittances_sur_un_encaissement(tmp_path):
    """Le montant est lu par LOGEMENT, l'unicité ne portait que sur le
    locataire : en colocation, chaque occupant recevait une quittance
    portant la TOTALITÉ du loyer — deux preuves opposables pour un seul
    paiement."""
    c, quittances = _bailleur_quittances(tmp_path)
    a = quittances.ajouter_locataire(c, bien_id=1, nom="DUPONT",
                                     date_entree="2025-09-01")
    b = quittances.ajouter_locataire(c, bien_id=1, nom="MARTIN",
                                     date_entree="2025-09-01")
    operations.saisir(c, type="loyer", montant=800, periode="2026-03",
                      date_operation="2026-03-05", bien_id=1)
    c.commit()
    # Depuis la passe P, la colocation est PRATICABLE : ce qui reste
    # interdit est d'attester plus que l'encaissement du logement. La part
    # de 400 € du second colocataire est donc légitime…
    quittances.emettre(c, locataire_id=a, periode="2026-03", loyer=400)
    quittances.emettre(c, locataire_id=b, periode="2026-03", loyer=400)
    # …mais pas un centime de plus : 800 € ont été encaissés, 800 € attestés.
    d = quittances.ajouter_locataire(c, bien_id=1, nom="DURAND",
                                     date_entree="2025-09-01")
    with pytest.raises(ValueError, match="déjà été quittancé|encaissé"):
        quittances.emettre(c, locataire_id=d, periode="2026-03", loyer=400)
    c.close()


def test_quittance_signale_un_encaissement_annule(tmp_path):
    """Les montants sont figés à l'émission. Après une contre-passation, la
    quittance attestait une somme jamais perçue et restait imprimable à
    l'identique, indéfiniment."""
    c, quittances = _bailleur_quittances(tmp_path, "o")
    loc = quittances.ajouter_locataire(c, bien_id=1, nom="D",
                                       date_entree="2024-01-01")
    operations.saisir(c, type="loyer", montant=800, periode="2026-03",
                      date_operation="2026-03-05", bien_id=1)
    c.commit()
    q = quittances.emettre(c, locataire_id=loc, periode="2026-03", forcer=True)
    assert quittances.detail(c, q["id"])["ecart_ecritures"] is None
    op = c.execute("SELECT id FROM operation LIMIT 1").fetchone()[0]
    operations.annuler(c, op)
    c.commit()
    ecart = quittances.detail(c, q["id"])["ecart_ecritures"]
    assert ecart is not None
    assert ecart["encaisse"] == pytest.approx(0.0)
    assert ecart["atteste"] == pytest.approx(800.0)
    c.close()


def test_restauration_refuse_de_reculer_la_numerotation(tmp_path):
    """Une restauration remettait MAX(numero) en arrière : les numéros
    déjà remis à des locataires étaient réattribués à d'autres documents,
    sans que la contrainte d'unicité n'y voie rien."""
    import perennite
    c, quittances = _bailleur_quittances(tmp_path, "r")
    loc = quittances.ajouter_locataire(c, bien_id=1, nom="D",
                                       date_entree="2024-01-01")
    quittances.emettre(c, locataire_id=loc, periode="2026-01", loyer=700, forcer=True)
    c.commit()
    db = str(tmp_path / "r.db")
    sv = perennite.sauvegarder(db, motif="demarrage")
    quittances.emettre(c, locataire_id=loc, periode="2026-02", loyer=700, forcer=True)
    c.commit()
    c.close()
    chemin = sv["chemin"] if isinstance(sv, dict) else sv
    with pytest.raises(ValueError, match="reculer la numérotation"):
        perennite.restaurer(db, chemin)


def test_sauvegarde_liee_a_son_dossier(tmp_path):
    """Tous les dossiers nomment leur base « compta.db » : leurs
    sauvegardes sont homonymes, et restaurer la mauvaise remplaçait une
    comptabilité par une autre, les deux contrôles passant sans broncher."""
    import perennite
    bases = {}
    for nom in ("nancy", "orleat"):
        rep = tmp_path / nom
        rep.mkdir()
        db = str(rep / "compta.db")
        c = init_db.init(db, "blanc", annee_cible=2026)
        c.execute("INSERT INTO exploitant (nom, siren, adresse) "
                  "VALUES (?, '123456789', 'Y')", (nom,))
        c.execute("INSERT INTO bien (exploitant_id, libelle, "
                  "date_acquisition, prix_total) "
                  "VALUES (1, ?, '2024-01-01', 100000)", (nom,))
        c.commit()
        operations.saisir(c, type="loyer", montant=700, periode="2026-01",
                          date_operation="2026-01-05", bien_id=1)
        c.commit()
        c.close()
        bases[nom] = db
    sv = perennite.sauvegarder(bases["nancy"], motif="demarrage")
    chemin = sv["chemin"] if isinstance(sv, dict) else sv
    with pytest.raises(ValueError, match="n'appartient pas au dossier"):
        perennite.restaurer(bases["orleat"], chemin)


def test_sauvegardes_de_surete_hors_rotation():
    """Elles précèdent une opération dangereuse et sont la seule chose qui
    permette d'y revenir : la rotation les effaçait précisément dans le
    scénario où elles servent."""
    import perennite
    assert "avant-migration" in perennite.MOTIFS_SURETE
    assert "avant-reinitialisation" in perennite.MOTIFS_SURETE
    src = open(conftest.source("perennite.py"), encoding="utf-8").read()
    bloc = src.split("def _rotation")[1][:600]
    assert "MOTIFS_SURETE" in bloc


def test_paliers_de_migration_couvrent_le_schema():
    """Un palier manquant était sauté en silence, puis la base marquée au
    niveau du logiciel : elle se déclarait à jour sans l'être et n'était
    plus jamais examinée."""
    import migrations
    assert set(migrations.PALIERS) == set(
        range(2, init_db.VERSION_SCHEMA + 1))


def test_quittance_refuse_periodes_et_montants_impossibles(tmp_path):
    c, quittances = _bailleur_quittances(tmp_path, "v")
    loc = quittances.ajouter_locataire(c, bien_id=1, nom="D",
                                       date_entree="2024-01-01")
    for periode in ("2026-00", "2026-13"):
        with pytest.raises(ValueError, match="mois de 01 à 12"):
            quittances.emettre(c, locataire_id=loc, periode=periode, loyer=700)
    with pytest.raises(ValueError, match="ne peuvent pas être négatifs"):
        quittances.emettre(c, locataire_id=loc, periode="2026-03",
                           loyer=-100, charges=50)
    with pytest.raises(ValueError, match="date de paiement"):
        quittances.emettre(c, locataire_id=loc, periode="2026-04", loyer=700,
                           date_paiement="31/02/2026")
    c.close()


def test_liste_des_quittances_montre_les_orphelines(tmp_path):
    """Jointures internes : la suppression d'un bien faisait disparaître
    ses quittances de la liste, alors que leurs numéros restaient
    consommés et que les documents circulaient chez des tiers."""
    c, quittances = _bailleur_quittances(tmp_path, "j")
    loc = quittances.ajouter_locataire(c, bien_id=1, nom="D",
                                       date_entree="2024-01-01")
    quittances.emettre(c, locataire_id=loc, periode="2026-01", loyer=700, forcer=True)
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute("DELETE FROM bien WHERE id=1")
    c.commit()
    liste = quittances.lister(c)
    assert len(liste) == 1, "la quittance a disparu de la liste"
    assert "supprimé" in liste[0]["bien"]
    c.close()


# === Revue Passe C — réexamen et passe libre (v8.38.0) ===================
# Deux constats NOUVEAUX et graves sur la liasse d'un exercice de cession,
# et la correction de mon propre correctif de la v8.35.0.

def _cession_simple(tmp_path, nom="c"):
    import cession
    c = init_db.init(str(tmp_path / f"{nom}.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2026-01-01', 100000, 0)")
    c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
              "duree_annees, date_mise_service, compte_immo, compte_amort, "
              "amortissable) VALUES (1, 'B', 100000, 25, '2026-01-01', "
              "'213150', '281315', 1)")
    c.commit()
    operations.saisir_acquisition(c, compte_immo="213150", montant=100000,
                                  date_operation="2026-01-01", libelle="B")
    operations.saisir(c, type="loyer", montant=20000, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    c.commit()
    cession.ceder_bien(c, bien_id=1, date_cession="2026-06-30",
                       prix_cession=110000)
    return c


def test_liasse_provisoire_neutralise_la_cession(tmp_path):
    """La 2033-B recalculait le résultat fiscal à la main en omettant la
    neutralisation de la cession, que `_calcul_fiscal` applique pourtant —
    et que son commentaire présente comme la « source unique » de la
    règle. La case 5NA, celle que le déclarant recopie, annonçait une base
    majorée de TOUTE la plus-value."""
    import fiscal
    c = _cession_simple(tmp_path)
    L = liasse.generer(c, 2026)
    attendu = fiscal.simuler(c, 2026)["resultat_fiscal"]
    assert L["f2033b"]["resultat_fiscal_lmnp"] == pytest.approx(attendu, abs=0.01)
    assert L["aide_2042c"]["case_5NA"] == round(attendu)
    c.close()


def test_ligne_352_vaut_zero_sur_un_exercice_de_cession(tmp_path):
    """Toute liasse d'exercice de cession sortait auto-déclarée non
    conforme — sur un montage parfaitement tenu."""
    import fiscal
    c = _cession_simple(tmp_path, "d")
    fiscal.cloturer(c, 2026, forcer=True)
    L = liasse.generer(c, 2026)
    assert L["f2033b"]["resultat_fiscal_352"] == pytest.approx(0.0, abs=0.01)
    assert L["conforme"], [x["nom"] for x in L["controles"] if not x["ok"]]
    c.close()


def test_chaque_bien_cede_porte_sa_propre_dotation(tmp_path):
    """Correction de mon propre correctif (v8.35.0) : la requête qui
    récupérait la dotation d'un bien cédé ne filtrait pas sur le bien, si
    bien que chaque cédé recevait la SOMME des dotations de tous les
    cédés — au détriment des biens conservés, dont la part de report
    partait avec les sortants."""
    import cession
    import fiscal
    c = init_db.init(str(tmp_path / "v.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    for lib, vb in (("A", 50000), ("B", 150000), ("C", 400000)):
        c.execute("INSERT INTO bien (exploitant_id, libelle, "
                  "date_acquisition, prix_total, quote_part_terrain) "
                  "VALUES (1, ?, '2020-01-01', ?, 0)", (lib, vb))
    # Trois comptes d'amortissement distincts — c'est ce qui permet de
    # vérifier l'attribution par bien. Chacun va donc avec SON compte
    # d'immobilisation : depuis la passe H, un compte 28 étranger au compte
    # d'immobilisation est refusé à la clôture (constat H-12).
    for bid, vb, immo, cpt in ((1, 50000, "213150", "281315"),
                               (2, 150000, "218100", "281810"),
                               (3, 400000, "218400", "281840")):
        c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
                  "duree_annees, date_mise_service, compte_immo, "
                  "compte_amort, amortissable) VALUES (?, ?, ?, 25, "
                  "'2020-01-01', ?, ?, 1)", (bid, f"c{bid}", vb, immo, cpt))
    c.commit()
    for bid in (1, 2, 3):
        operations.saisir(c, type="loyer", montant=4000, periode="2026-01",
                          date_operation="2026-01-05", bien_id=bid)
    c.commit()
    cession.ceder_bien(c, bien_id=1, date_cession="2026-06-30",
                       prix_cession=60000)
    cession.ceder_bien(c, bien_id=2, date_cession="2026-06-30",
                       prix_cession=170000)
    r = fiscal.cloturer(c, 2026, forcer=True)
    lignes = {x[0]: x for x in c.execute(
        "SELECT bien_id, ROUND(dotation_bien,2), ROUND(report_bien,2), "
        "ROUND(stock_cloture,2) FROM suivi_39c_bien WHERE exercice_annee=2026")}
    # les deux cédés portent des dotations DIFFÉRENTES (50k et 150k de brut)
    assert lignes[1][1] != lignes[2][1], "poids identiques : le filtre manque"
    assert lignes[1][1] < lignes[2][1]
    # le bien conservé garde le reste, et la somme reste égale au global
    assert lignes[3][3] == pytest.approx(r["suivi_39c"]["stock_cloture"], abs=0.01)
    c.close()


def test_pas_de_faux_positif_de_dotation_sur_une_cession(tmp_path):
    """La dotation de cession est passée hors clôture et n'apparaît pas au
    plan théorique : la compter garantissait un avertissement alarmant et
    faux à CHAQUE cession."""
    import fiscal
    c = _cession_simple(tmp_path, "f")
    fiscal.cloturer(c, 2026, forcer=True)
    codes = [a.code for a in controles.controler(c, 2026)]
    assert "DOTATION_PLAN" not in codes
    c.close()


def test_deficit_menace_signale_avant_la_cloture(tmp_path):
    """Le contrôle lisait une table écrite par la seule clôture : il se
    taisait jusqu'au moment où il n'est plus temps d'agir, alors que le
    rapport se lit AVANT de figer la liasse."""
    import fiscal
    c = init_db.init(str(tmp_path / "m.db"), "blanc", annee_cible=2025)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2020-01-01', 100000, 0)")
    c.execute("INSERT INTO exercice (annee, date_debut, date_fin, statut) "
              "VALUES (2024, '2024-01-01', '2024-12-31', 'clos')")
    c.commit()
    c.execute("INSERT INTO deficit_lmnp (annee_origine, montant_initial, "
              "solde, annee_expiration) VALUES (2017, 5000, 5000, 2027)")
    c.execute("INSERT INTO suivi_39c (exercice_annee, stock_ouverture, "
              "report_annee, utilisation_annee, stock_cloture) "
              "VALUES (2024, 0, 5000, 0, 5000)")
    c.commit()
    operations.saisir(c, type="loyer", montant=5000, periode="2025-01",
                      date_operation="2025-01-05", bien_id=1)
    c.commit()
    # AVANT clôture : le contrôle doit déjà parler
    codes = [a.code for a in controles.controler(c, 2025)]
    assert "DEFICIT_MENACE_PAR_39C" in codes, codes
    del fiscal
    c.close()


def test_plafond_39c_majore_par_le_manuel_est_signale(tmp_path):
    """Constat de la revue REFUSÉ sur le fond — le test en or, calé sur
    trois liasses réelles, passe l'ALUR en retraitement manuel et montre le
    plafond majoré d'autant. Le risque (charge non afférente au bien) est
    signalé au lieu d'être deviné."""
    import fiscal
    src = open(conftest.source("fiscal.py"), encoding="utf-8").read()
    assert 'max(0.0, autres)' in src           # comportement conservé
    assert "REFUSÉE" in src                    # et la raison écrite
    c = init_db.init(str(tmp_path / "p.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2026-01-01', 100000, 0)")
    c.commit()
    operations.saisir(c, type="loyer", montant=9000, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    c.commit()
    fiscal.cloturer(c, 2026, autres_retraitements=800, forcer=True)
    codes = [a.code for a in controles.controler(c, 2026)]
    assert "RETRAITEMENT_MANUEL_PLAFOND" in codes, codes
    c.close()


def test_cession_preserve_les_composants_deja_sortis():
    src = open(conftest.source("cession.py"), encoding="utf-8").read()
    assert "date_sortie IS NULL OR date_sortie=''" in src


def test_allongement_de_duree_signale_article_39b(tmp_path):
    """Signalé par l'auteur : on ne prolonge pas librement la durée de vie
    d'une immobilisation. L'article 39 B du CGI impose un amortissement
    minimum linéaire calculé sur la durée retenue à l'ORIGINE ; allonger
    la durée réduit l'annuité, fait décrocher le cumul de ce minimum, et
    l'écart est un amortissement irrégulièrement différé — définitivement
    perdu, à la différence du report de l'article 39 C.

    Le logiciel acceptait l'allongement en silence (dotation ramenée de
    1 600 à 1 000 €). Il le signale désormais, en rappelant l'exception :
    revenir à la durée normale après une réduction motivée est légitime."""
    import fiscal
    import reprise
    c = init_db.init(str(tmp_path / "d.db"), "blanc", annee_cible=2022)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('X', '123456789', 'Y')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'A', '2022-01-01', 8000, 0)")
    c.execute("INSERT INTO composant (bien_id, libelle, valeur_brute, "
              "duree_annees, date_mise_service, compte_immo, compte_amort, "
              "amortissable) VALUES (1, 'M', 8000, 5, '2022-01-01', "
              "'218400', '281840', 1)")
    c.commit()
    operations.saisir_acquisition(c, compte_immo="218400", montant=8000,
                                  date_operation="2022-01-01", libelle="M")
    for a in (2022, 2023):
        if a > 2022:
            reprise.ouvrir_exercice(c, a)
        operations.saisir(c, type="loyer", montant=9000, periode=f"{a}-01",
                          date_operation=f"{a}-01-05", bien_id=1)
        c.commit()
        fiscal.cloturer(c, a, forcer=True)
    # durée inchangée : rien à signaler
    reprise.ouvrir_exercice(c, 2024)
    assert not [a for a in controles.controler(c, 2024)
                if a.code == "DUREE_ALLONGEE"]
    c.execute("UPDATE composant SET duree_annees=8 WHERE id=1")
    c.commit()
    alertes = [a for a in controles.controler(c, 2024)
               if a.code == "DUREE_ALLONGEE"]
    assert alertes, "l'allongement passe inaperçu"
    m = alertes[0].message
    assert "39 B" in m
    assert "définitivement perdu" in m
    assert "RÉDUITE" in m            # l'exception est rappelée


# === Revue Passe D — couche web et ligne de commande (v8.40.0) ===========
# La couche jamais auditée. Les six premiers constats critiques.

def test_confirmations_ne_sont_pas_du_javascript_casse():
    """Deux confirmations — dont celle de la RESTAURATION — contenaient un
    saut de ligne réel et une apostrophe fermante dans leur littéral
    JavaScript. Le gestionnaire ne compilait pas, valait donc null, et
    l'opération partait SANS aucune boîte de dialogue. Les deux qui
    fonctionnaient étaient précisément celles écrites sans apostrophe."""
    import re
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    for m in re.finditer(r'(onclick|onsubmit)="return confirm\((.{0,240}?)\)"',
                         p, re.S):
        corps = m.group(2)
        assert "\n" not in corps, f"saut de ligne réel : {corps[:60]!r}"
        nu = corps.strip()
        if nu.startswith("'"):
            assert nu.count("'") <= 2, f"apostrophe fermante : {corps[:60]!r}"
    # les deux réparées passent par un attribut, échappé par Jinja
    assert p.count("data-confirmer") >= 2
    a = open(conftest.source("app.py"), encoding="utf-8").read()
    assert 'closest("[data-confirmer]")' in a


def test_bac_a_sable_a_ses_propres_annexes(tmp_path):
    """Sauvegardes et archives dérivaient du RÉPERTOIRE de la base, que le
    dossier principal et le bac à sable partagent : la page Archives du bac
    à sable servait les FEC de la comptabilité réelle, et chaque
    réinitialisation déposait une copie dans les sauvegardes réelles — que
    la protection des motifs de sûreté empêchait ensuite d'effacer."""
    import perennite
    reel = str(tmp_path / "compta.db")
    bac = str(tmp_path / "bac_a_sable.db")
    assert perennite.dossier_sauvegardes(reel) != \
        perennite.dossier_sauvegardes(bac)
    assert perennite.dossier_archives(reel) != perennite.dossier_archives(bac)
    # le dossier principal garde son emplacement historique
    assert perennite.dossier_sauvegardes(reel).endswith("sauvegardes")
    assert perennite.dossier_archives(reel).endswith("archives")


def test_imports_temporaires_cloisonnes(tmp_path, monkeypatch):
    """Un import préparé en bac à sable, puis validé après une bascule ou
    l'expiration du cookie, écrivait ses opérations dans la comptabilité
    RÉELLE : le jeton passait tous les contrôles, le fichier existait."""
    import importlib
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac_a_sable.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    with app_mod.app.test_request_context(
            "/", headers={"Cookie": "dossier=bac_a_sable"}):
        en_bac = app_mod._dossier_imports()
    with app_mod.app.test_request_context("/"):
        en_reel = app_mod._dossier_imports()
    assert en_bac != en_reel
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def test_cookie_du_bac_a_sable_ne_expire_pas_en_huit_heures():
    """Il durait 8 h là où les autres dossiers durent 180 jours : le cookie
    expirait souvent d'un jour à l'autre, et l'utilisateur se retrouvait
    dans le dossier PRINCIPAL en croyant être encore dans le bac à sable."""
    a = open(conftest.source("app.py"), encoding="utf-8").read()
    bloc = a.split('set_cookie("dossier", "bac_a_sable"')[1][:120]
    assert "180*24*3600" in bloc, bloc


def test_cli_annonce_sa_base_et_vise_le_bon_dossier():
    """La ligne de commande codait en dur le dossier principal, alors que
    l'interface résout le dossier courant : une clôture pouvait frapper un
    dossier qu'on ne regardait plus, et le chemin n'apparaissait nulle
    part."""
    c = open(conftest.source("cli.py"), encoding="utf-8").read()
    assert 'os.environ.get("COMPTA_DB")' in c
    assert 'add_argument("--dossier"' in c
    assert "_annoncer_base()" in c
    assert "def _resoudre_dossier" in c


def test_cli_cloturer_sauvegarde_avant():
    """Même opération irréversible que la clôture web, qui elle sauvegarde
    et archive."""
    c = open(conftest.source("cli.py"), encoding="utf-8").read()
    bloc = c.split("def cmd_cloturer")[1][:700]
    assert 'motif="avant-cloture"' in bloc
    assert "Clôture refusée" in bloc
    # …et le fonds ALUR n'est plus suggéré : il est réintégré automatiquement
    assert "ex. fonds de travaux ALUR)" not in c


def test_migration_a_l_ouverture_dun_dossier(tmp_path, monkeypatch):
    """D-07 — la migration ne tournait qu'au démarrage du serveur, sur les
    dossiers alors connus. Or le registre prévoit explicitement d'ADOPTER
    une base préexistante, qui conserve son schéma : ouverte en cours de
    session, elle était écrite dans un schéma périmé, sans la copie de
    sûreté que la migration produit. Le garde de version ne voyait rien —
    il ne refuse qu'une base plus RÉCENTE."""
    import importlib
    import sqlite3 as sq
    import perennite
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    cx = sq.connect(db)
    cx.execute("UPDATE meta SET valeur='4' WHERE cle='version_schema'")
    cx.commit()
    cx.close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "s.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    assert app_mod.app.test_client().get("/saisie").status_code == 200
    cx = sq.connect(db)
    assert init_db.version_base(cx) == init_db.VERSION_SCHEMA
    cx.close()
    sv = os.listdir(perennite.dossier_sauvegardes(db))
    assert any("avant-migration" in x for x in sv), sv
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def test_base_absente_nest_pas_remplacee_par_une_vierge():
    """D-09 — un dossier dont le fichier manquait était silencieusement
    remplacé par une base vierge : la comptabilité paraissait perdue, et le
    vrai fichier — souvent simplement pas encore disponible — se trouvait
    masqué."""
    a = open(conftest.source("app.py"), encoding="utf-8").read()
    assert "class FichierDossierAbsent" in a
    assert "raise FichierDossierAbsent" in a
    bloc = a.split("raise FichierDossierAbsent")[0][-700:]
    assert "temporaire" in bloc.lower() or "TEMPORAIRE" in bloc
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    assert "PAGE_DOSSIER_ABSENT" in p
    assert "Rien n'a été créé ni modifié" in p


def test_version_trop_recente_offre_une_issue(tmp_path, monkeypatch):
    """D-08 — la page 409 ne comportait ni lien ni formulaire, et chaque
    lien de la barre de navigation repassait par le même garde : le
    logiciel devenait inutilisable pour TOUS ses dossiers jusqu'à
    suppression manuelle d'un cookie."""
    import importlib
    import sqlite3 as sq
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    cx = sq.connect(db)
    cx.execute("UPDATE meta SET valeur='99' WHERE cle='version_schema'")
    cx.commit()
    cx.close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "s.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    cl = app_mod.app.test_client()
    r = cl.get("/saisie")
    assert r.status_code == 409
    assert "/dossiers/retour-principal" in r.get_data(as_text=True)
    # …et cette sortie doit rester joignable malgré le garde
    assert cl.post("/dossiers/retour-principal").status_code in (302, 303)
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)
