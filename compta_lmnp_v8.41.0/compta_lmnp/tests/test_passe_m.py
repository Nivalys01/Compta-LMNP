# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Non-régression des constats de la passe M (le moteur de contrôles).

Cette passe n'audite pas la comptabilité : elle audite ce qui l'audite. Et
la question qui la traverse est celle de la VALEUR D'UN VERDICT POSITIF.

Un contrôle peut être atteignable et manquer le cas qui importe — un compte
d'attente à sept chiffres, deux flux qui se compensent sans avoir été
identifiés. Un contrôle peut échouer et rendre une liste vide, transformant
« je n'ai pas pu vérifier » en « rien à signaler ». Un document remis peut
afficher cinq validations vertes sans porter l'anomalie bloquante que le
moteur a trouvée. Et le refus de clôturer peut n'exister que dans les
interfaces, pas dans la fonction qui fige l'exercice.

Ces tests figent l'exigence commune : **un verdict positif ne vaut que si
la vérification a réellement eu lieu, et un refus ne vaut que là où la
mutation se produit.**

Aucune donnée réelle : exploitant fictif, bases blanches.

Lancer :  pytest -q tests/test_passe_m.py
"""
import os
import shutil
import subprocess
import tempfile

import pytest

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import controles
import ecritures
import fiscal
import gabarits
import init_db
import liasse
import operations
import parametres
import reprise


# ── Fabriques de pièces fictives ──────────────────────────────────────────

def _dossier(tmp_path, nom, annee=2026):
    conn = init_db.init_blanc(str(tmp_path / nom), annee)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Exploitant fictif','000000000','Adresse fictive')")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) "
                 "VALUES (1,1,'Bien fictif',12000)")
    conn.commit()
    return conn


@pytest.fixture
def base(tmp_path):
    conn = _dossier(tmp_path, "fictif.db")
    yield conn
    conn.close()


def composant(conn, dms="2026-01-01", valeur=12000):
    conn.execute(
        "INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,"
        "date_mise_service,compte_immo,compte_amort,amortissable) "
        "VALUES (1,'Mobilier',?,10,?,'218400','281840',1)", (valeur, dms))
    conn.commit()


def acquisition(conn, annee=2026, montant=12000):
    ecritures.inserer(conn, journal="OD", date=f"{annee}-01-01", annee=annee,
                      libelle="Acquisition", piece_ref="ACQ",
                      lignes=[("218400", montant, 0.0),
                              ("108000", 0.0, montant)])


def loyer(conn, mois, montant, annee=2026, type_op="loyer"):
    operations.saisir(conn, type=type_op, montant=montant, bien_id=1,
                      date_operation=f"{annee}-{mois:02d}-10",
                      periode=f"{annee}-{mois:02d}")


def anomalies(conn, annee=2026):
    return {(a.code, a.niveau) for a in controles.controler(conn, annee)}


def codes(conn, annee=2026):
    return {a.code for a in controles.controler(conn, annee)}


def texte_pdf(conn, annee, tmp_path, nom="m.pdf"):
    import liasse_pdf
    chemin = str(tmp_path / nom)
    liasse_pdf.generer_pdf(liasse.generer(conn, annee), chemin)
    return subprocess.run(["pdftotext", "-layout", chemin, "-"],
                          capture_output=True, text=True, timeout=60).stdout


# ═══ M-01 / M-02 — ce qu'est réellement un compte d'attente apuré ═══════

def test_m01_le_compte_d_attente_est_reconnu_a_sa_racine(base):
    """Le compte était désigné par égalité avec 472000. Un cabinet numérote
    en 4720000, et la reprise d'un FEC crée ce compte tel quel : 800 € non
    classés pouvaient être figés sans aucun signal."""
    base.execute("INSERT OR IGNORE INTO compte(numero,libelle,type,classe) "
                 "VALUES ('4720000','Attente','attente',4)")
    base.commit()
    ecritures.inserer(base, journal="OD", date="2026-03-10", annee=2026,
                      libelle="À identifier", piece_ref="P",
                      lignes=[("4720000", 800, 0.0), ("108000", 0.0, 800)])
    assert ("COMPTE_ATTENTE", controles.BLOQUANT) in anomalies(base)


def test_m02_deux_flux_qui_se_compensent_ne_sont_pas_apures(base):
    """Un encaissement et un décaissement de 800 € encore « à identifier »
    donnent un solde NUL. Le contrôle concluait « apuré », et 800 € de
    recette potentielle étaient figés sans qu'aucune décision n'ait été
    prise."""
    loyer(base, 3, 800, type_op="attente_encaissement")
    loyer(base, 4, 800, type_op="attente_decaissement")
    assert ("COMPTE_ATTENTE", controles.BLOQUANT) in anomalies(base)


def test_m02_un_compte_d_attente_regulierement_apure_ne_bloque_pas(base):
    """Contre-épreuve ESSENTIELLE : un compte d'attente correctement apuré
    porte, par construction, l'écriture d'origine et sa reclassification —
    un aller-retour de montants égaux pour un solde nul. Le dossier de
    référence en compte 287 847,78 €, tous régulièrement reclassés. Prendre
    le mouvement du compte pour signal les aurait tous condamnés."""
    ecritures.inserer(base, journal="OD", date="2026-03-10", annee=2026,
                      libelle="Encaissement à identifier", piece_ref="P1",
                      lignes=[("108000", 800, 0.0), ("472000", 0.0, 800)])
    ecritures.inserer(base, journal="OD", date="2026-03-20", annee=2026,
                      libelle="Reclassement en loyer", piece_ref="P2",
                      lignes=[("472000", 800, 0.0), ("708810", 0.0, 800)])
    assert "COMPTE_ATTENTE" not in codes(base)


def test_m02_un_solde_non_nul_reste_bloquant(base):
    ecritures.inserer(base, journal="OD", date="2026-03-10", annee=2026,
                      libelle="À identifier", piece_ref="P",
                      lignes=[("472000", 800, 0.0), ("108000", 0.0, 800)])
    assert ("COMPTE_ATTENTE", controles.BLOQUANT) in anomalies(base)


# ═══ M-03 — le document remis porte ce que le moteur a trouvé ══════════

def test_m03_la_liasse_transporte_les_anomalies_du_moteur(base):
    loyer(base, 3, 800, type_op="attente_decaissement")
    L = liasse.generer(base, 2026)
    codes_liasse = {a["code"] for a in L["anomalies"]}
    assert "COMPTE_ATTENTE" in codes_liasse
    assert any(a["niveau"] == "BLOQUANT" for a in L["anomalies"])


@pytest.mark.skipif(shutil.which("pdftotext") is None,
                    reason="pdftotext absent")
def test_m03_le_pdf_imprime_l_anomalie_bloquante(base, tmp_path):
    """Le PDF affichait cinq validations internes en vert et ne portait pas
    l'anomalie BLOQUANTE du moteur : les deux ensembles de contrôles
    n'étaient tout simplement pas reliés. Le destinataire du document ne
    pouvait pas savoir que 800 € restaient en attente."""
    loyer(base, 3, 800, type_op="attente_decaissement")
    texte = texte_pdf(base, 2026, tmp_path)
    assert "COMPTE_ATTENTE" in texte
    assert "BLOQUANTE" in texte


@pytest.mark.skipif(shutil.which("pdftotext") is None,
                    reason="pdftotext absent")
def test_m03_un_dossier_sain_affiche_l_absence_d_anomalie(base, tmp_path):
    """Contre-épreuve : le nouveau bloc ne doit pas alarmer pour rien. Les
    rappels de niveau INFO — « aucune taxe foncière saisie » — restent
    imprimés, mais sans l'avertissement d'anomalie bloquante."""
    for mois in range(1, 13):
        loyer(base, mois, 800)
    texte = texte_pdf(base, 2026, tmp_path, "sain.pdf")
    assert "Contrôles de cohérence du dossier" in texte
    assert "BLOQUANTE" not in texte
    assert not [a for a in liasse.generer(base, 2026)["anomalies"]
                if a["niveau"] == "BLOQUANT"]


# ═══ M-04 — un bilan démontrablement faux bloque ══════════════════════

def _exercice_precedent_clos(tmp_path, nom):
    conn = _dossier(tmp_path, nom, annee=2025)
    composant(conn, dms="2025-01-01")
    acquisition(conn, annee=2025)
    operations.saisir(conn, type="loyer", montant=2400, bien_id=1,
                      date_operation="2025-03-10", periode="2025-03")
    fiscal.cloturer(conn, 2025)
    return conn


def test_m04_ouvrir_sans_reprise_bloque_la_cloture(tmp_path):
    """Clôturer sans à-nouveaux fige un bilan dont on SAIT déjà qu'il est
    faux : actif net de −1 200 € au lieu de 9 600 € dans le cas reproduit.
    L'erreur est déterminée, pas soupçonnée — un avertissement ne lui
    convenait pas, et la liasse ne la signalait qu'après coup."""
    conn = _exercice_precedent_clos(tmp_path, "m04.db")
    try:
        reprise.ouvrir_exercice(conn, 2026, avec_reprise=False)
        assert ("AN_ABSENTS", controles.BLOQUANT) in anomalies(conn)
        with pytest.raises(ValueError, match="bloquante"):
            fiscal.cloturer(conn, 2026)
    finally:
        conn.close()


def test_m04_la_reprise_normale_ne_bloque_rien(tmp_path):
    conn = _exercice_precedent_clos(tmp_path, "m04b.db")
    try:
        reprise.ouvrir_exercice(conn, 2026)
        assert "AN_ABSENTS" not in codes(conn)
        fiscal.cloturer(conn, 2026)
    finally:
        conn.close()


def test_m04_un_exercice_precedent_sans_solde_ne_bloque_pas(tmp_path):
    """Nuance demandée par le rapport : un exercice antérieur dont tous les
    soldes de bilan sont nuls ne laisse rien à reprendre. Bloquer pour rien
    serait aussi mauvais que ne pas bloquer."""
    conn = _dossier(tmp_path, "m04c.db", annee=2025)
    try:
        fiscal.cloturer(conn, 2025, forcer=True)
        reprise.ouvrir_exercice(conn, 2026, avec_reprise=False)
        assert "AN_ABSENTS" not in codes(conn)
    finally:
        conn.close()


def test_m04_les_amortissements_anterieurs_manquants_bloquent(base):
    """Un bien entré dans le logiciel alors qu'il était déjà amorti : le
    bilan le présente comme neuf tandis que le 2033-C déroule son plan
    depuis la mise en service. L'écart ne se résorbe jamais de lui-même et
    fausse la plus-value à la revente."""
    composant(base, dms="2025-01-01")
    acquisition(base)
    assert ("AMORT_ANTERIEURS", controles.BLOQUANT) in anomalies(base)


# ═══ M-05 — « je n'ai pas pu vérifier » n'est pas « rien à signaler » ══

def test_m05_un_controle_en_echec_est_nomme(base, monkeypatch):
    """L'exception était avalée et le contrôle rendait une liste vide : le
    déclarant recevait une assurance positive sur un cumul d'amortissement
    de 12 000 € qui n'avait pas été contrôlé."""
    composant(base, dms="2025-01-01")
    import operations as _ops

    def panne(*a, **k):
        raise RuntimeError("lecture impossible")

    monkeypatch.setattr(_ops, "amortissements_anterieurs_manquants", panne)
    trouvees = [a for a in controles.controler(base, 2026)
                if a.code == "CONTROLE_IMPOSSIBLE"]
    assert trouvees and trouvees[0].niveau == controles.BLOQUANT
    assert "c_amortissements_anterieurs" in trouvees[0].message


def test_m05_les_autres_controles_survivent_a_la_panne(base, monkeypatch):
    """L'isolation va dans les deux sens : un contrôle qui échoue ne doit
    pas emporter les vingt-six autres avec lui."""
    loyer(base, 3, 800, type_op="attente_decaissement")
    import operations as _ops
    monkeypatch.setattr(_ops, "amortissements_anterieurs_manquants",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))
    trouves = codes(base)
    assert "CONTROLE_IMPOSSIBLE" in trouves
    assert "COMPTE_ATTENTE" in trouves       # les autres ont bien tourné


# ═══ M-07 — la garantie vit là où se produit la mutation ══════════════

def test_m07_l_api_refuse_de_cloturer_sur_un_bloquant(base):
    """Le refus était mis en œuvre par la route web et la CLI, mais pas par
    la fonction qui fige l'exercice. Un appel métier ordinaire figeait donc
    800 € non identifiés sans rien demander. Une garantie qui repose sur la
    discipline de ses appelants tombe au premier appelant nouveau."""
    loyer(base, 3, 800, type_op="attente_decaissement")
    assert controles.bloquants(controles.controler(base, 2026))
    with pytest.raises(ValueError, match="bloquante"):
        fiscal.cloturer(base, 2026, generer_dotation=False)
    assert base.execute("SELECT statut FROM exercice WHERE annee=2026"
                        ).fetchone()[0] == "ouvert"


def test_m07_la_derogation_explicite_reste_possible(base):
    """`forcer=True` est la dérogation que les deux interfaces proposent
    déjà par une case à cocher — le refus informe, il n'emprisonne pas."""
    loyer(base, 3, 800, type_op="attente_decaissement")
    fiscal.cloturer(base, 2026, generer_dotation=False, forcer=True)
    assert base.execute("SELECT statut FROM exercice WHERE annee=2026"
                        ).fetchone()[0] == "clos"


def test_m07_un_dossier_sain_cloture_sans_derogation(base):
    for mois in range(1, 13):
        loyer(base, mois, 800)
    fiscal.cloturer(base, 2026, generer_dotation=False)
    assert base.execute("SELECT statut FROM exercice WHERE annee=2026"
                        ).fetchone()[0] == "clos"


# ═══ M-08 — le code de retour est le verdict ═════════════════════════

def test_m08_la_cli_retourne_un_code_non_nul_sur_refus(tmp_path):
    """Un script appelant pouvait poursuivre comme si la clôture avait
    réussi. Le texte affiché était pourtant sans ambiguïté."""
    import sys
    chemin = str(tmp_path / "cli.db")
    conn = _dossier(tmp_path, "cli.db")
    operations.saisir(conn, type="attente_decaissement", montant=800,
                      bien_id=1, date_operation="2026-03-10",
                      periode="2026-03")
    conn.close()
    r = subprocess.run(
        [sys.executable, conftest.source("cli.py"), "cloturer",
         "--annee", "2026"],
        capture_output=True, text=True, timeout=120,
        env=dict(os.environ, COMPTA_DB=chemin))
    assert r.returncode != 0
    assert "refus" in (r.stdout + r.stderr).lower()


# ═══ M-10 — une opération annulée n'existe plus ══════════════════════

def test_m10_une_depense_annulee_n_alerte_plus(base):
    op = operations.saisir(base, type="petit_equipement", montant=780,
                           bien_id=1, date_operation="2026-03-10",
                           periode="2026-03")
    operations.annuler(base, op["operation_id"])
    assert "IMMOBILISABLE" not in codes(base)


def test_m10_une_charge_annuelle_annulee_puis_ressaisie_n_est_pas_un_doublon(base):
    op = operations.saisir(base, type="cfe", montant=300, bien_id=1,
                           date_operation="2026-12-10", periode="2026-12")
    operations.annuler(base, op["operation_id"])
    operations.saisir(base, type="cfe", montant=300, bien_id=1,
                      date_operation="2026-12-15", periode="2026-12")
    assert "ANNUEL_MULTIPLE" not in codes(base)


def test_m10_un_loyer_corrige_n_est_plus_signale(base):
    """La première requête excluait les annulations, celle qui cherche les
    écarts les réintroduisait : il ne suffisait pas de corriger la première.
    """
    op = operations.saisir(base, type="loyer", montant=80, bien_id=1,
                           date_operation="2026-01-10", periode="2026-01")
    operations.annuler(base, op["operation_id"])
    for mois in range(1, 13):
        loyer(base, mois, 800)
    assert "LOYER_ATYPIQUE" not in codes(base)


# ═══ M-11 — calendrier complet n'est pas activité réelle ═════════════

def test_m11_deux_biens_au_meme_loyer_ne_sont_pas_un_doublon(base):
    """Deux studios identiques loués au même prix — le cas le plus banal
    d'un investisseur — étaient signalés comme un doublon chaque mois."""
    base.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) "
                 "VALUES (2,1,'Second bien fictif',12000)")
    base.commit()
    for bien_id in (1, 2):
        operations.saisir(base, type="loyer", montant=800, bien_id=bien_id,
                          date_operation="2026-01-10", periode="2026-01")
    assert "DOUBLON" not in codes(base)


def test_m11_un_vrai_doublon_reste_detecte(base):
    """Contre-épreuve : même bien, même période, même montant."""
    for _ in range(2):
        operations.saisir(base, type="loyer", montant=800, bien_id=1,
                          date_operation="2026-01-10", periode="2026-01")
    assert "DOUBLON" in codes(base)


def test_m11_un_exercice_court_n_attend_pas_douze_mois(base):
    """Un bien acquis en novembre donnait dix « loyers manquants » pour des
    mois antérieurs à l'ouverture de l'exercice — des mois où l'activité
    n'existait pas."""
    base.execute("UPDATE exercice SET date_debut='2026-11-01' WHERE annee=2026")
    base.commit()
    for mois in (11, 12):
        loyer(base, mois, 800)
    assert "LOYER_MANQUANT" not in codes(base)


def test_m11_un_mois_reellement_manquant_reste_signale(base):
    for mois in range(1, 12):            # il manque décembre
        loyer(base, mois, 800)
    assert "LOYER_MANQUANT" in codes(base)


# ═══ M-12 — un gabarit personnalisé n'est pas hors couverture ════════

def test_m12_un_loyer_personnalise_est_controle_comme_un_loyer(base):
    """Le type était écrit en dur : un gabarit créé par l'utilisateur —
    même compte, même nature, même périodicité — sortait des contrôles de
    complétude et d'écart sans que rien ne l'annonce, et une erreur de
    720 € sur un loyer n'était plus signalée."""
    gabarits.ajouter_personnalise(base, cle="loyer_fictif",
                                  libelle="Loyer fictif", compte_num="708810",
                                  nature="produit", periodicite="mensuel")
    for mois, montant in ((1, 800), (2, 800), (3, 80)):
        loyer(base, mois, montant, type_op="loyer_fictif")
    trouves = codes(base)
    assert "LOYER_ATYPIQUE" in trouves
    assert "LOYER_MANQUANT" in trouves


def test_m12_les_types_de_loyer_sont_reconnus_par_leur_compte(base):
    gabarits.ajouter_personnalise(base, cle="loyer_fictif",
                                  libelle="Loyer fictif", compte_num="708810",
                                  nature="produit", periodicite="mensuel")
    gabarits.ajouter_personnalise(base, cle="charge_fictive",
                                  libelle="Charge fictive",
                                  compte_num="614100", nature="charge",
                                  periodicite="mensuel")
    types = controles.types_de_loyer(base)
    assert "loyer" in types and "loyer_fictif" in types
    assert "charge_fictive" not in types


# ═══ M-13 — un seuil est un nombre fini ═════════════════════════════

@pytest.mark.parametrize("valeur", [float("inf"), float("-inf"),
                                    float("nan"), "1e309"])
def test_m13_un_seuil_non_fini_est_refuse(base, valeur):
    """Enregistrer un seuil infini rendait muets, pour toujours et sans un
    mot, les contrôles qui s'y comparent : aucune dépense ne dépasse
    l'infini. Un garde-fou qu'une saisie peut désactiver est pire qu'un
    garde-fou absent — on croit encore l'avoir."""
    with pytest.raises(ValueError, match="fini|nombre"):
        parametres.definir(base, "seuil_immobilisation", valeur, "2026-01-01")


def test_m13_un_seuil_ordinaire_reste_modifiable(base):
    parametres.definir(base, "seuil_immobilisation", 1000.0, "2026-01-01")
    assert parametres.valeur(base, "seuil_immobilisation", 2026,
                             defaut=500.0) == 1000.0
    operations.saisir(base, type="petit_equipement", montant=780, bien_id=1,
                      date_operation="2026-03-10", periode="2026-03")
    assert "IMMOBILISABLE" not in codes(base)   # 780 < 1000, alerte muette


# ═══ M-14 — on ne contrôle pas un exercice qui n'existe pas ═════════

def test_m14_un_exercice_inexistant_est_annonce(base):
    """Le rapport concluait « aucune anomalie ✓ » pour une année absente de
    la base : il prétendait avoir vérifié ce qu'il n'avait pas pu lire."""
    anos = controles.controler(base, 2099)
    assert [a.code for a in anos] == ["EXERCICE_INEXISTANT"]
    assert anos[0].niveau == controles.BLOQUANT
    assert "2099" in controles.rapport(base, 2099)
    assert "aucune anomalie" not in controles.rapport(base, 2099)


# ═══ M-09 — déjà corrigé par la passe J, et qui doit le rester ══════

def test_m09_un_emprunt_recu_n_est_pas_une_recette_locative(base):
    """Corrigé par la passe J, qui a fait porter le seuil sur les loyers
    acquis des écritures. Figé ici : un flux de bilan ne doit pas déclencher
    une alerte de changement de statut."""
    operations.saisir(base, type="emprunt_recu", montant=100000, bien_id=1,
                      date_operation="2026-03-10", periode="2026-03")
    assert "SEUIL_LMP" not in codes(base)


def test_m09_un_loyer_annule_ne_compte_pas_dans_le_seuil(base):
    op = operations.saisir(base, type="loyer", montant=24000, bien_id=1,
                           date_operation="2026-03-10", periode="2026-03")
    operations.annuler(base, op["operation_id"])
    assert "SEUIL_LMP" not in codes(base)


# ═══ Ce qui tenait doit continuer de tenir ═════════════════════════

def test_un_dossier_bien_tenu_ne_declenche_rien(base):
    """Garde générale : aucune des exigences ajoutées ne doit crier sur un
    dossier ordinaire."""
    for mois in range(1, 13):
        loyer(base, mois, 795)
    operations.saisir(base, type="taxe_fonciere", montant=1162, bien_id=1,
                      date_operation="2026-10-15", periode="2026-10")
    operations.saisir(base, type="teom", montant=163, bien_id=1,
                      date_operation="2026-10-15", periode="2026-10")
    nouveaux = {"COMPTE_ATTENTE", "CONTROLE_IMPOSSIBLE", "EXERCICE_INEXISTANT",
                "AN_ABSENTS", "AMORT_ANTERIEURS", "DOUBLON", "LOYER_MANQUANT"}
    assert not (codes(base) & nouveaux)


def test_les_vingt_sept_controles_restent_enregistres():
    """Le registre ne doit pas avoir perdu de contrôle en chemin."""
    assert len(controles.CONTROLES) >= 27
    assert len({c.__name__ for c in controles.CONTROLES}) == len(controles.CONTROLES)


def test_dossier_temporaire_nettoye():
    """Garde-fou de la suite elle-même : ces tests n'écrivent que dans le
    tmp_path de pytest, jamais à côté des fichiers du projet."""
    assert not os.path.exists(os.path.join(tempfile.gettempdir(), "fictif.db"))
