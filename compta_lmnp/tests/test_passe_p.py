# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Non-régression des constats de la passe P (quittances de loyer).

Une quittance n'est pas un état interne : c'est un document REMIS À UN
TIERS, qui le fera valoir contre le bailleur. Cela change tout — et c'est
le fil de cette passe.

Un document remis ne se recalcule pas : il était pourtant reconstruit par
jointure sur le référentiel courant, si bien que corriger le nom d'un
locataire réécrivait rétroactivement tous ses justificatifs, sous leurs
numéros d'origine. Un document remis ne s'invente pas : une attestation
pouvait être émise sans le moindre encaissement, ou transformer 80 € de
charges en loyer sans alerte, alors que l'article 21 de la loi du 6 juillet
1989 impose précisément cette ventilation. Et un numéro remis ne se
réattribue jamais : un compteur devenu illisible était pris pour un
compteur à zéro.

S'y ajoute une distinction que le droit fait et que le logiciel ignorait :
le REÇU d'un paiement partiel n'est pas la QUITTANCE d'un mois soldé.

Aucune donnée réelle : bailleur, locataires et logement fictifs.

Lancer :  pytest -q tests/test_passe_p.py
"""
import os
import sqlite3
import tempfile

import pytest

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import init_db
import operations
import outils_demo
import perennite
import quittances


# ── Fabriques de pièces fictives ──────────────────────────────────────────

def _bailleur(chemin, loyer_mensuel=800.0, adresse="1 rue Fictive"):
    conn = init_db.init_blanc(chemin, 2026)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Bailleur Fictif','000000000','Adresse bailleur fictive')")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total,adresse)"
                 " VALUES (1,1,'Logement Alpha Fictif',12000,?)", (adresse,))
    conn.commit()
    quittances.assurer_schema(conn)
    locataire = quittances.ajouter_locataire(
        conn, bien_id=1, nom="Locataire Alpha Fictif",
        date_entree="2025-01-01", loyer_mensuel=loyer_mensuel)
    return conn, locataire


@pytest.fixture
def bailleur(tmp_path):
    conn, locataire = _bailleur(str(tmp_path / "compta.db"))
    yield conn, locataire
    conn.close()


def encaisser(conn, montant, periode="2026-01", jour="05", type_op="loyer"):
    operations.saisir(conn, type=type_op, montant=montant, bien_id=1,
                      periode=periode,
                      date_operation=f"{periode}-{jour}")


# ═══ P-01 — on n'atteste que ce qui a été reçu ════════════════════════

def test_p01_pas_d_attestation_sans_encaissement(bailleur):
    """L'avertissement existait à la CONSULTATION ; l'émission, elle,
    n'était pas bloquée. 880 € pouvaient donc être attestés sans le moindre
    encaissement, et le locataire recevait une preuve opposable."""
    conn, locataire = bailleur
    with pytest.raises(ValueError, match="attesterait plus"):
        quittances.emettre(conn, locataire_id=locataire, periode="2026-01",
                           loyer=800, charges=80)
    assert conn.execute("SELECT COUNT(*) FROM quittance").fetchone()[0] == 0


def test_p01_la_ventilation_est_comparee_poste_par_poste(bailleur):
    """Seul le TOTAL était comparé : 800 € de loyer et 80 € de charges
    encaissés pouvaient devenir 880 € de loyer et 0 € de charges. Le total
    tombait juste, et la ventilation — celle que le locataire fera valoir,
    et que l'article 21 impose — était fausse."""
    conn, locataire = bailleur
    encaisser(conn, 800)
    encaisser(conn, 80, type_op="charges_locatives")
    with pytest.raises(ValueError, match="charges attestées|loyer attesté"):
        quittances.emettre(conn, locataire_id=locataire, periode="2026-01",
                           loyer=880, charges=0)


def test_p01_la_ventilation_exacte_passe(bailleur):
    """Contre-épreuve : les mêmes montants, correctement ventilés."""
    conn, locataire = bailleur
    encaisser(conn, 800)
    encaisser(conn, 80, type_op="charges_locatives")
    q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01",
                           loyer=800, charges=80)
    assert q["total"] == 880.0


def test_p01_la_derogation_explicite_reste_possible(bailleur):
    """Le logiciel ne voit pas tout — un paiement en espèces pas encore
    saisi, par exemple. Le rapprochement se force, il n'emprisonne pas."""
    conn, locataire = bailleur
    q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01",
                           loyer=800, forcer=True)
    assert q["numero"] == 1


# ═══ P-02 — le reçu d'un acompte n'est pas la quittance d'un mois ═════

def test_p02_un_paiement_partiel_donne_un_recu(bailleur):
    """400 € versés sur 800 € dus produisaient une QUITTANCE DE LOYER —
    titre qui solde la période. L'article 21 distingue expressément le reçu
    pour paiement partiel."""
    conn, locataire = bailleur
    encaisser(conn, 400)
    q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    assert q["type_document"] == "recu"
    assert q["total"] == 400.0
    assert q["reste_du"] == 400.0


def test_p02_le_solde_paye_devient_quittancable(bailleur):
    """Une fois le reçu émis, la quittance du mois soldé devenait
    impossible : 400 € supplémentaires restaient hors de tout justificatif,
    sans alerte ni parcours de complément."""
    conn, locataire = bailleur
    encaisser(conn, 400)
    recu = quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    encaisser(conn, 400, jour="20")
    quittance = quittances.emettre(conn, locataire_id=locataire,
                                   periode="2026-01", loyer=800)
    assert quittance["type_document"] == "quittance"
    assert quittance["total"] == 800.0
    assert quittance["numero"] != recu["numero"]
    # Les deux documents ont circulé : aucun n'est effacé.
    assert conn.execute("SELECT COUNT(*) FROM quittance").fetchone()[0] == 2


def test_p02_le_document_imprime_dit_ce_qu_il_est(bailleur):
    conn, locataire = bailleur
    encaisser(conn, 400)
    q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    detail = quittances.detail(conn, q["id"])
    assert detail["titre_document"] == "Reçu de paiement partiel"
    assert detail["reste_du"] == 400.0


def test_p02_un_mois_solde_donne_bien_une_quittance(bailleur):
    """Contre-épreuve : le cas ordinaire n'est pas dégradé en reçu."""
    conn, locataire = bailleur
    encaisser(conn, 800)
    q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    assert q["type_document"] == "quittance"
    assert quittances.detail(conn, q["id"])["titre_document"] \
        == "Quittance de loyer"


def test_p02_un_second_document_de_meme_type_reste_refuse(bailleur):
    conn, locataire = bailleur
    encaisser(conn, 800)
    quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    with pytest.raises(ValueError, match="existe déjà"):
        quittances.emettre(conn, locataire_id=locataire, periode="2026-01",
                           loyer=800, forcer=True)


# ═══ P-03 — la colocation est praticable, et bornée par l'encaissement ═

def test_p03_deux_colocataires_recoivent_chacun_leur_part(tmp_path):
    """Le refus conseillait de ventiler — « indiquez le montant revenant à
    chacun » — et refusait ensuite la seconde part : le parcours conseillé
    était interdit par le contrôle qui le conseillait."""
    conn, alpha = _bailleur(str(tmp_path / "coloc.db"), loyer_mensuel=400)
    try:
        beta = quittances.ajouter_locataire(
            conn, bien_id=1, nom="Locataire Beta Fictif",
            date_entree="2025-01-01", loyer_mensuel=400)
        encaisser(conn, 800)
        qa = quittances.emettre(conn, locataire_id=alpha, periode="2026-01",
                                loyer=400)
        qb = quittances.emettre(conn, locataire_id=beta, periode="2026-01",
                                loyer=400)
        assert {qa["numero"], qb["numero"]} == {1, 2}
        assert qa["total"] == qb["total"] == 400.0
    finally:
        conn.close()


def test_p03_la_somme_des_parts_ne_depasse_pas_l_encaissement(tmp_path):
    """Ce qui doit rester interdit, c'est d'attester DEUX FOIS le même
    encaissement — pas d'émettre deux documents."""
    conn, alpha = _bailleur(str(tmp_path / "coloc2.db"), loyer_mensuel=400)
    try:
        beta = quittances.ajouter_locataire(
            conn, bien_id=1, nom="Locataire Beta Fictif",
            date_entree="2025-01-01", loyer_mensuel=400)
        gamma = quittances.ajouter_locataire(
            conn, bien_id=1, nom="Locataire Gamma Fictif",
            date_entree="2025-01-01", loyer_mensuel=400)
        encaisser(conn, 800)
        quittances.emettre(conn, locataire_id=alpha, periode="2026-01",
                           loyer=400)
        quittances.emettre(conn, locataire_id=beta, periode="2026-01",
                           loyer=400)
        with pytest.raises(ValueError, match="déjà été quittancé|attesterait"):
            quittances.emettre(conn, locataire_id=gamma, periode="2026-01",
                               loyer=400)
    finally:
        conn.close()


def test_p03_le_calcul_automatique_ne_propose_que_le_reste(tmp_path):
    """En automatique, le second occupant recevait la TOTALITÉ du loyer du
    logement — les fonds du premier compris."""
    conn, alpha = _bailleur(str(tmp_path / "coloc3.db"), loyer_mensuel=400)
    try:
        beta = quittances.ajouter_locataire(
            conn, bien_id=1, nom="Locataire Beta Fictif",
            date_entree="2025-01-01", loyer_mensuel=400)
        encaisser(conn, 800)
        quittances.emettre(conn, locataire_id=alpha, periode="2026-01",
                           loyer=400)
        q = quittances.emettre(conn, locataire_id=beta, periode="2026-01")
        assert q["total"] == 400.0
    finally:
        conn.close()


# ═══ P-04 — un numéro remis ne se réattribue jamais ═══════════════════

def test_p04_un_compteur_illisible_refuse_la_restauration(tmp_path):
    """L'échec de lecture était assimilé à l'absence de toute quittance :
    la garde ne voyait aucun recul de numérotation, et le n° 2 déjà remis
    pour février était réattribué à mars."""
    chemin = str(tmp_path / "compta.db")
    conn, locataire = _bailleur(chemin)
    encaisser(conn, 800)
    quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    conn.close()
    copie = perennite.sauvegarder(chemin)
    conn = sqlite3.connect(chemin)
    try:
        encaisser(conn, 800, periode="2026-02")
        quittances.emettre(conn, locataire_id=locataire, periode="2026-02")
        conn.execute("ALTER TABLE quittance "
                     "RENAME COLUMN numero TO numero_endommage")
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(ValueError, match="Impossible de lire la numérotation"):
        perennite.restaurer(chemin, copie)


def test_p04_un_dossier_sans_quittance_reste_restaurable(tmp_path):
    """Contre-épreuve : « aucune quittance » et « je n'ai pas pu lire » ne
    doivent surtout pas être confondus dans l'autre sens non plus."""
    chemin = str(tmp_path / "compta.db")
    conn, _locataire = _bailleur(chemin)
    encaisser(conn, 800)
    conn.close()
    copie = perennite.sauvegarder(chemin)
    perennite.restaurer(chemin, copie)
    assert perennite._max_quittance(chemin) == 0


def test_p04_le_recul_de_numerotation_reste_refuse(tmp_path):
    """Garde antérieure, qui ne doit pas avoir été perdue en chemin."""
    chemin = str(tmp_path / "compta.db")
    conn, locataire = _bailleur(chemin)
    encaisser(conn, 800)
    quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    conn.close()
    copie = perennite.sauvegarder(chemin)
    conn = sqlite3.connect(chemin)
    try:
        encaisser(conn, 800, periode="2026-02")
        quittances.emettre(conn, locataire_id=locataire, periode="2026-02")
    finally:
        conn.close()
    with pytest.raises(ValueError, match="reculer la numérotation"):
        perennite.restaurer(chemin, copie)


# ═══ P-05 — un document remis ne se recalcule pas ════════════════════

def test_p05_l_identite_est_figee_a_l_emission(bailleur):
    """Le justificatif changeait de bénéficiaire et de logement imprimé
    sans changer de numéro : le bailleur ne pouvait plus demander au
    logiciel une réédition fidèle du document qu'il avait remis."""
    conn, locataire = bailleur
    encaisser(conn, 800)
    q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    conn.execute("UPDATE locataire SET nom='Locataire Beta Fictif'")
    conn.execute("UPDATE bien SET adresse='Autre adresse fictive'")
    conn.commit()
    detail = quittances.detail(conn, q["id"])
    assert detail["locataire"] == "Locataire Alpha Fictif"
    assert detail["bien_adresse"] == "1 rue Fictive"


def test_p05_le_changement_de_referentiel_est_signale(bailleur):
    """Figer sans le dire cacherait l'écart : le lecteur doit savoir que le
    dossier a changé depuis."""
    conn, locataire = bailleur
    encaisser(conn, 800)
    q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    conn.execute("UPDATE locataire SET nom='Locataire Beta Fictif'")
    conn.commit()
    assert "locataire" in quittances.detail(conn, q["id"])["referentiel_modifie"]


def test_p05_un_dossier_inchange_ne_signale_rien(bailleur):
    conn, locataire = bailleur
    encaisser(conn, 800)
    q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    assert quittances.detail(conn, q["id"])["referentiel_modifie"] == []


def test_p05_le_bailleur_aussi_est_fige(bailleur):
    conn, locataire = bailleur
    encaisser(conn, 800)
    q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    conn.execute("UPDATE exploitant SET nom='Autre Bailleur Fictif'")
    conn.commit()
    assert quittances.detail(conn, q["id"])["bailleur"]["nom"] \
        == "Bailleur Fictif"


# ═══ P-06 — le justificatif situe et date ce qu'il atteste ═══════════

def test_p06_la_date_de_paiement_vient_de_l_encaissement(bailleur):
    """La date était connue dans l'opération, et le document ne la portait
    pas : l'émission ne la reprenait que si on la saisissait de nouveau."""
    conn, locataire = bailleur
    encaisser(conn, 800, jour="10")
    q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
    assert quittances.detail(conn, q["id"])["date_paiement"] == "2026-01-10"


def test_p06_une_date_saisie_prime_sur_celle_deduite(bailleur):
    conn, locataire = bailleur
    encaisser(conn, 800, jour="10")
    q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01",
                           date_paiement="2026-01-15")
    assert quittances.detail(conn, q["id"])["date_paiement"] == "2026-01-15"


def test_p06_une_adresse_absente_ne_devient_pas_un_libelle(tmp_path):
    """Le gabarit se rabattait sur le LIBELLÉ interne du bien et le
    présentait comme l'adresse du logement. Le document est conservé sans
    adresse, et l'écran le signale — un repli muet vaut moins qu'une
    mention absente."""
    conn, locataire = _bailleur(str(tmp_path / "sans.db"), adresse="")
    try:
        encaisser(conn, 800)
        q = quittances.emettre(conn, locataire_id=locataire, periode="2026-01")
        assert quittances.detail(conn, q["id"])["adresse_logement"] == ""
    finally:
        conn.close()


# ═══ P-07 — une promesse d'anonymisation ne tient pas d'un inventaire ═

def test_p07_les_tables_personnelles_sortent_du_jeu_de_demonstration():
    """Un locataire absent de la liste d'empreintes traversait intact
    jusque dans l'artefact distribué, sous un en-tête promettant « AUCUNE
    donnée personnelle ». Le contrôle final ne pouvait pas le rattraper :
    il cherche des termes inscrits à la main, et c'est justement d'un terme
    NON inscrit qu'il s'agissait."""
    seed = (
        "INSERT INTO exploitant (id, nom, siren, adresse) "
        "VALUES (1, 'NOM REEL', '123456789', 'Adresse reelle');\n"
        "INSERT INTO bien (id, exploitant_id, libelle) "
        "VALUES (1, 1, 'Appartement X');\n"
        "INSERT INTO locataire (id, bien_id, nom, date_entree) "
        "VALUES (1, 1, 'Locataire Secret Fictif', '2025-01-01');\n"
        "INSERT INTO quittance (numero, locataire_id, periode, "
        "date_emission, loyer) VALUES (1, 1, '2026-01', '2026-01-31', 800.0);\n")
    sortie = outils_demo._neutraliser_tables_personnelles(seed)
    assert "Locataire Secret Fictif" not in sortie
    assert "INSERT INTO quittance" not in sortie
    assert "tables personnelles" in sortie


def test_p07_les_tables_instructives_sont_conservees():
    """Contre-épreuve : le jeu de démonstration doit rester utile."""
    seed = ("INSERT INTO exploitant (id, nom) VALUES (1, 'NOM');\n"
            "INSERT INTO bien (id, libelle) VALUES (1, 'Appartement X');\n"
            "INSERT INTO composant (id, libelle) VALUES (1, 'Gros oeuvre');\n")
    sortie = outils_demo._neutraliser_tables_personnelles(seed)
    assert "INSERT INTO exploitant" in sortie
    assert "INSERT INTO bien" in sortie
    assert "INSERT INTO composant" in sortie


def test_p07_les_tables_visees_sont_nommees():
    assert "locataire" in outils_demo.TABLES_PERSONNELLES
    assert "quittance" in outils_demo.TABLES_PERSONNELLES


# ═══ Ce qui tenait doit continuer de tenir ═══════════════════════════

def test_la_numerotation_reste_continue(bailleur):
    conn, locataire = bailleur
    numeros = []
    for mois in ("01", "02", "03"):
        encaisser(conn, 800, periode=f"2026-{mois}")
        numeros.append(quittances.emettre(
            conn, locataire_id=locataire, periode=f"2026-{mois}")["numero"])
    assert numeros == [1, 2, 3]


def test_un_locataire_absent_du_mois_reste_refuse(bailleur):
    conn, locataire = bailleur
    conn.execute("UPDATE locataire SET date_sortie='2025-06-30'")
    conn.commit()
    encaisser(conn, 800)
    with pytest.raises(ValueError, match="n'occupe pas"):
        quittances.emettre(conn, locataire_id=locataire, periode="2026-01")


def test_les_montants_negatifs_restent_refuses(bailleur):
    conn, locataire = bailleur
    with pytest.raises(ValueError, match="négatifs"):
        quittances.emettre(conn, locataire_id=locataire, periode="2026-01",
                           loyer=-100, charges=50, forcer=True)


def test_le_schema_migre_les_bases_anciennes(tmp_path):
    """Une base créée avant cette version portait l'unicité (locataire,
    période) : un reçu y aurait interdit pour toujours la quittance du mois
    soldé. La table est reconstruite au premier accès."""
    chemin = str(tmp_path / "ancienne.db")
    conn = init_db.init_blanc(chemin, 2026)
    conn.execute("DROP TABLE quittance")
    conn.executescript(
        "CREATE TABLE quittance ("
        " id INTEGER PRIMARY KEY, numero INTEGER NOT NULL UNIQUE,"
        " locataire_id INTEGER NOT NULL REFERENCES locataire(id),"
        " periode TEXT NOT NULL, date_emission TEXT NOT NULL,"
        " date_paiement TEXT, loyer REAL NOT NULL,"
        " charges REAL NOT NULL DEFAULT 0,"
        " UNIQUE (locataire_id, periode));")
    conn.commit()
    quittances.assurer_schema(conn)
    colonnes = {r[1] for r in conn.execute("PRAGMA table_info(quittance)")}
    assert "type_document" in colonnes and "nom_locataire" in colonnes
    conn.close()


def test_dossier_temporaire_nettoye():
    """Garde-fou de la suite elle-même : ces tests n'écrivent que dans le
    tmp_path de pytest, jamais à côté des fichiers du projet."""
    assert not os.path.exists(os.path.join(tempfile.gettempdir(),
                                           "compta.db"))
