# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Non-régression des constats de la passe E (import bancaire, liasse PDF, plan).

Chaque test reproduit le SCÉNARIO du rapport d'audit (docs/AUDIT_PASSE_E.md)
et fige le comportement corrigé. Un test qui casse ici signifie qu'un défaut
d'audit est revenu, pas qu'une convention a changé.

Lot traité : E-02 (export à colonnes débit/crédit accepté et inversé) et
E-03 (lignes de montant ignorées en silence).

Lancer :  pytest -q tests/test_passe_e.py
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import import_bancaire


def _releve(tmp_path, contenu, nom="releve.csv"):
    p = tmp_path / nom
    p.write_text(contenu, encoding="utf-8")
    return str(p)


# ═══ E-02 — un export à 4 colonnes ne doit plus être lu à l'envers ═══════

def test_e02_export_quatre_colonnes_refuse(tmp_path):
    """Le scénario exact du rapport.

    Avant : la colonne DÉBIT (non signée) était prise pour un montant, la
    charge de copropriété devenait une recette de loyer avec une période
    servie, et l'import « réussissait » sans un mot. Sur un relevé annuel,
    la totalité des charges basculait en produits.
    """
    p = _releve(tmp_path, "05/01/2026;PRLV SYNDIC;120,50;\n")
    with pytest.raises(ValueError, match="colonnes"):
        import_bancaire.analyser(p)


def test_e02_message_explique_quoi_faire(tmp_path):
    """Un refus qui n'explique pas est un mur : le message doit nommer le
    format attendu et la manœuvre de sortie."""
    p = _releve(tmp_path, "05/01/2026;PRLV SYNDIC;120,50;\n")
    with pytest.raises(ValueError) as exc:
        import_bancaire.analyser(p)
    texte = str(exc.value)
    assert "Ligne 1" in texte                       # où
    assert "4 colonnes au lieu de 3" in texte       # quoi
    assert "date;libelle;montant" in texte          # attendu
    assert "Réexportez" in texte                    # que faire


@pytest.mark.parametrize("ligne", [
    "05/01/2026;PRLV SYNDIC\n",                                  # 2 colonnes
    "05/01/2026;PRLV SYNDIC;120,50;;\n",                         # 5 colonnes
    "05/01/2026;PRLV SYNDIC;;120,50\n",                          # débit/crédit
])
def test_e02_tout_ce_qui_n_est_pas_trois_colonnes_est_refuse(tmp_path, ligne):
    """`len(r) < 3` acceptait 4, 5 ou 12 colonnes. Le compte est désormais
    exact, dans les deux sens."""
    with pytest.raises(ValueError, match="colonnes"):
        import_bancaire.analyser(_releve(tmp_path, ligne))


def test_e02_trois_colonnes_reste_accepte(tmp_path):
    """Le format documenté ne doit pas être emporté par le durcissement."""
    p = _releve(tmp_path, "date;libelle;montant\n"
                          "05/01/2026;PRLV SYNDIC;-120,50\n")
    r = import_bancaire.analyser(p)
    assert len(r["propositions"]) == 1
    assert r["propositions"][0]["montant"] == 120.50
    assert r["rejets"] == []


def test_e02_ligne_vide_finale_ne_fait_pas_echouer(tmp_path):
    """Un CSV se termine par un saut de ligne : la ligne vide qui en résulte
    n'a pas 3 colonnes, mais elle ne porte aucune donnée."""
    p = _releve(tmp_path, "05/01/2026;PRLV SYNDIC;-120,50\n\n")
    assert len(import_bancaire.analyser(p)["propositions"]) == 1


# ═══ E-03 — plus aucune ligne ignorée en silence ════════════════════════

@pytest.mark.parametrize("brut,attendu", [
    ("-120,50",       -120.50),   # forme documentée
    ("120,50-",       -120.50),   # signe suffixe (mainframes)
    ("(120,50)",      -120.50),   # convention anglo-saxonne
    ("-120,50 EUR",   -120.50),   # devise en toutes lettres
    ("-1 234,50 €",  -1234.50),   # milliers + symbole
    ("-1 234,50", -1234.50),  # espace insécable (acquis R6, non régressé)
    ("-1 234,50", -1234.50),  # fine insécable   (idem)
    ("795",            795.0),    # entier sans décimale
    ("+795,50",        795.50),   # signe explicite
])
def test_e03_formats_de_montant_lus(brut, attendu):
    """Les cinq formes du rapport, plus les acquis de la campagne R6."""
    assert import_bancaire._montant(brut) == pytest.approx(attendu)


@pytest.mark.parametrize("contenu,montant", [
    ("05/01/2026;PRLV SYNDIC;120,50-\n",      120.50),
    ("05/01/2026;PRLV SYNDIC;(120,50)\n",     120.50),
    ("05/01/2026;PRLV SYNDIC;-120,50 EUR\n",  120.50),
    ("05/01/2026;PRLV SYNDIC;-1 234,50 €\n", 1234.50),
    ("05/01/2026\tPRLV SYNDIC\t-120,50\n",   120.50),
])
def test_e03_les_cinq_scenarios_ne_renvoient_plus_vide(tmp_path, contenu, montant):
    """Le tableau du rapport : cinq relevés, cinq fois `[]`. Un relevé
    entièrement au format « signe suffixe » produisait ZÉRO proposition et
    l'utilisateur concluait que son relevé ne contenait rien."""
    r = import_bancaire.analyser(_releve(tmp_path, contenu))
    assert len(r["propositions"]) == 1, r
    assert r["propositions"][0]["montant"] == pytest.approx(montant)
    assert r["rejets"] == []


def test_e03_tabulation_reconnue_comme_separateur(tmp_path):
    """Un export tabulé tombait dans une colonne unique, donc rejeté en
    bloc par le test de longueur."""
    p = _releve(tmp_path, "05/01/2026\tPRLV SYNDIC\t-120,50\n")
    props = import_bancaire.analyser(p)["propositions"]
    assert props[0]["libelle"] == "PRLV SYNDIC"
    assert props[0]["montant"] == 120.50


def test_e03_point_virgule_gagne_sur_la_virgule_decimale(tmp_path):
    """La virgule est d'abord un séparateur DÉCIMAL en France : elle ne doit
    pas emporter la détection sur un fichier à point-virgule."""
    p = _releve(tmp_path, "05/01/2026;VIR LOYER;795,50\n"
                          "06/01/2026;PRLV GMF PNO;-138,49\n")
    assert len(import_bancaire.analyser(p)["propositions"]) == 2


def test_e03_ligne_illisible_comptee_et_restituee(tmp_path):
    """Le cœur du constat : ce qui n'est pas lu doit être RENDU, avec son
    numéro de ligne. Le `continue` muet faisait passer un import partiel
    pour un import complet."""
    p = _releve(tmp_path, "date;libelle;montant\n"
                          "05/01/2026;VIR LOYER;795,50\n"
                          "06/01/2026;LIGNE CASSEE;non-un-montant\n"
                          "07/01/2026;PRLV SYNDIC;-120,50\n")
    r = import_bancaire.analyser(p)
    assert len(r["propositions"]) == 2
    assert len(r["rejets"]) == 1
    rejet = r["rejets"][0]
    assert rejet["ligne"] == 3                       # en-tête comprise
    assert "LIGNE CASSEE" in rejet["contenu"]
    assert "non-un-montant" in rejet["raison"]


def test_e03_montant_vide_est_un_rejet_pas_un_zero(tmp_path):
    """Une cellule vide ne vaut pas 0 € : inventer un montant nul serait
    une écriture fausse de plus."""
    r = import_bancaire.analyser(_releve(tmp_path, "05/01/2026;SOLDE;\n"))
    assert r["propositions"] == []
    assert len(r["rejets"]) == 1


def test_e03_proposer_reste_une_liste(tmp_path):
    """`proposer()` garde sa signature : app.py, cli.py et les tests
    existants la consomment comme une liste."""
    p = _releve(tmp_path, "05/01/2026;VIR LOYER;795,50\n")
    props = import_bancaire.proposer(p)
    assert isinstance(props, list) and props[0]["type"] == "loyer"


# ═══ E-10 — comptes manquants au plan livré ═════════════════════════════
#
# Le rapport ne relève AUCUNE erreur de type ni de classe dans les 33 comptes
# livrés : le défaut est fait d'absences. Sans dette financière ni compte de
# dépôt de garantie, une mensualité de prêt et un dépôt encaissé n'avaient
# aucune destination correcte — ils partaient en charge et en produit.

import sqlite3

import fiscal
import gabarits
import init_db
import migrations
import operations

COMPTES_E10 = {
    "164000": ("passif",  1),   # emprunts auprès des établissements de crédit
    "165000": ("passif",  1),   # dépôts et cautionnements reçus
    "401000": ("passif",  4),   # fournisseurs
    "411000": ("actif",   4),   # locataires (créance : actif, pas passif)
    "758000": ("produit", 7),   # produits divers de gestion COURANTE
}


@pytest.fixture
def base(tmp_path):
    chemin = str(tmp_path / "compta.db")
    init_db.init_blanc(chemin, 2026).close()
    conn = sqlite3.connect(chemin)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("INSERT OR IGNORE INTO exploitant (id, nom, siren) "
                 "VALUES (1, 'Exploitant test', '000000000')")
    conn.execute("INSERT INTO bien (id, exploitant_id, libelle) "
                 "VALUES (1, 1, 'Logement test')")
    conn.commit()
    yield conn
    conn.close()


@pytest.mark.parametrize("numero,attendu", sorted(COMPTES_E10.items()))
def test_e10_comptes_presents_dans_une_base_neuve(base, numero, attendu):
    row = base.execute("SELECT type, classe FROM compte WHERE numero=?",
                       (numero,)).fetchone()
    assert row is not None, f"compte {numero} absent du plan livré"
    assert (row[0], row[1]) == attendu


def test_e10_migration_cree_les_comptes_sur_une_base_existante(tmp_path):
    """Un dossier créé avant la passe E n'a pas ces comptes. Sans le palier,
    les nouveaux gabarits échoueraient sur la clé étrangère compte(numero)
    — chez l'utilisateur, pas ici."""
    chemin = str(tmp_path / "ancienne.db")
    init_db.init_blanc(chemin, 2026).close()
    conn = sqlite3.connect(chemin)
    conn.executemany("DELETE FROM compte WHERE numero=?",
                     [(n,) for n in COMPTES_E10])
    conn.execute("UPDATE meta SET valeur='6' WHERE cle='version_schema'")
    conn.commit()
    conn.close()

    migrations.migrer(chemin)

    conn = sqlite3.connect(chemin)
    presents = {n for (n,) in conn.execute(
        "SELECT numero FROM compte WHERE numero IN "
        "('164000','165000','401000','411000','758000')")}
    conn.close()
    assert presents == set(COMPTES_E10)


def test_e10_palier_7_est_rejouable(tmp_path):
    """INSERT OR IGNORE : rejouer le palier ne double ni n'écrase rien."""
    chemin = str(tmp_path / "compta.db")
    init_db.init_blanc(chemin, 2026).close()
    conn = sqlite3.connect(chemin)
    migrations._palier_7(conn)
    migrations._palier_7(conn)
    n = conn.execute("SELECT COUNT(*) FROM compte WHERE numero='165000'").fetchone()[0]
    conn.close()
    assert n == 1


def _resultat(conn, annee=2026):
    """Résultat comptable de l'exercice — fiscal.agregats agrège par CLASSE
    de compte (6 et 7), ce qui met d'office les classes 1 et 4 hors résultat."""
    return fiscal.agregats(conn, annee)["resultat_comptable"]


def test_e10_depot_de_garantie_est_une_dette_pas_un_loyer(base):
    """Le scénario d'E-01 vu depuis le plan : 700 € encaissés au titre d'un
    dépôt de garantie ne doivent pas bouger d'un centime le résultat."""
    avant = _resultat(base)
    operations.saisir(base, type="depot_garantie_recu", montant=700.0,
                      date_operation="2026-01-05", bien_id=1)
    apres = _resultat(base)
    assert apres == avant

    lignes = base.execute(
        "SELECT compte_num, debit, credit FROM ligne "
        "ORDER BY compte_num").fetchall()
    assert ("108000", 700.0, 0.0) in lignes      # trésorerie entrante
    assert ("165000", 0.0, 700.0) in lignes      # dette envers le locataire


def test_e10_remboursement_de_capital_nest_pas_une_charge(base):
    """Le redressement le plus classique en LMNP au réel : 890 € de capital
    remboursé passés en charge. Le compte 164000 les reçoit désormais, et
    la classe 1 est hors du résultat."""
    avant = _resultat(base)
    operations.saisir(base, type="emprunt_capital_rembourse", montant=890.0,
                      date_operation="2026-01-05", bien_id=1)
    apres = _resultat(base)
    assert apres == avant

    charge6 = base.execute(
        "SELECT COALESCE(SUM(l.debit),0) FROM ligne l "
        "JOIN compte c ON c.numero=l.compte_num WHERE c.classe=6").fetchone()[0]
    assert charge6 == 0.0


def test_e10_interets_restent_deductibles(base):
    """La contrepartie du test précédent : seuls les INTÉRÊTS se déduisent.
    Le gabarit existait déjà, il ne doit pas être emporté par la correction."""
    avant = _resultat(base)
    operations.saisir(base, type="interets_emprunt", montant=210.0,
                      date_operation="2026-01-05", bien_id=1)
    apres = _resultat(base)
    assert round(avant - apres, 2) == 210.0


def test_e10_ecritures_restent_equilibrees(base):
    """Un compte de bilan mal branché déséquilibrerait le FEC."""
    for type_op, montant in (("depot_garantie_recu", 700.0),
                             ("depot_garantie_restitue", 700.0),
                             ("emprunt_recu", 120000.0),
                             ("emprunt_capital_rembourse", 890.0),
                             ("attente_encaissement", 320.0),
                             ("attente_decaissement", 65.0)):
        operations.saisir(base, type=type_op, montant=montant,
                          date_operation="2026-01-05", bien_id=1)
    d, c = base.execute(
        "SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) "
        "FROM ligne").fetchone()
    assert round(d, 2) == round(c, 2)


def test_e10_depot_recu_puis_restitue_solde_la_dette(base):
    """E-01 signalait qu'un dépôt restitué « repartirait en charge », faute
    de compte d'accueil. Aller-retour : le 165000 revient à zéro."""
    operations.saisir(base, type="depot_garantie_recu", montant=700.0,
                      date_operation="2026-01-05", bien_id=1)
    operations.saisir(base, type="depot_garantie_restitue", montant=700.0,
                      date_operation="2026-11-30", bien_id=1)
    solde = base.execute(
        "SELECT COALESCE(SUM(credit),0) - COALESCE(SUM(debit),0) "
        "FROM ligne WHERE compte_num='165000'").fetchone()[0]
    assert round(solde, 2) == 0.0


def test_e10_attente_bloque_la_liasse(base):
    """La différence entre « signalé » et « bloquant » : 628800 est une
    charge déductible qui n'empêche rien ; 472000 déclenche le contrôle
    bloquant qui existait déjà dans controles.py."""
    import controles
    operations.saisir(base, type="attente_decaissement", montant=65.0,
                      date_operation="2026-01-05", bien_id=1)
    anomalies = controles.controler(base, 2026)
    bloquants = [a for a in anomalies
                 if a.code == "COMPTE_ATTENTE" and a.niveau == controles.BLOQUANT]
    assert bloquants, f"aucun contrôle bloquant sur 472000 : {anomalies}"
    assert "65.00" in bloquants[0].message


def test_e10_indemnite_assurance_en_produit_courant(base):
    """758 = produit COURANT de gestion. 778 est un compte EXCEPTIONNEL :
    y loger une indemnité d'assurance est une erreur de nature."""
    assert gabarits.GABARITS["indemnite_assurance"]["compte"] == "758000"
    operations.saisir(base, type="indemnite_assurance", montant=800.0,
                      date_operation="2026-01-05", bien_id=1)
    solde = base.execute(
        "SELECT COALESCE(SUM(credit),0) - COALESCE(SUM(debit),0) "
        "FROM ligne WHERE compte_num='758000'").fetchone()[0]
    assert round(solde, 2) == 800.0


def test_e10_gabarits_pointent_vers_des_comptes_existants(base):
    """Garde générale : un gabarit dont le compte n'est pas au plan échoue
    sur la clé étrangère au moment de la SAISIE, donc chez l'utilisateur."""
    plan = {n for (n,) in base.execute("SELECT numero FROM compte")}
    orphelins = {cle: g["compte"] for cle, g in gabarits.GABARITS.items()
                 if g["compte"] not in plan}
    assert not orphelins, f"gabarits sans compte au plan : {orphelins}"


# ═══ E-01 / E-04 / E-05 / E-06 — la catégorisation ══════════════════════

def test_e01_encaissements_ne_sont_plus_tous_des_loyers():
    """Le tableau du rapport : quatre encaissements, quatre natures, trois
    comptes. `if montant > 0: return "loyer"` en faisait 6 820 € de recettes,
    dont 5 700 € qui ne sont pas des produits du tout."""
    attendus = {
        "VIREMENT DEPOT DE GARANTIE LOCATAIRE": "depot_garantie_recu",
        "VIR M DUPONT APPORT":           "attente_encaissement",
        "REMB SINISTRE GMF DEGAT DES EAUX":     "indemnite_assurance",
        "VIR CAF ALLOCATION LOGEMENT":          "loyer",
    }
    for libelle, attendu in attendus.items():
        assert import_bancaire.categoriser(libelle, 700.0) == attendu, libelle


def test_e01_un_encaissement_inconnu_va_en_attente_pas_en_loyer():
    """Le défaut de fond : l'inconnu ne doit plus créer d'impôt."""
    t = import_bancaire.categoriser("VIR RECU ORIGINE INDETERMINEE", 1500.0)
    assert t == "attente_encaissement"
    assert gabarits.GABARITS[t]["compte"] == "472000"


@pytest.mark.parametrize("libelle,montant", [
    ("ECHEANCE PRET IMMOBILIER 001234",       -890.0),
    ("AGENCE IMMOBILIERE HONORAIRES GESTION",  -65.0),
    ("VIR RECU PARENTS AIDE",                 -300.0),
])
def test_e04_plus_de_match_en_sous_chaine(libelle, montant):
    """« mobilier » ⊂ « IMMOBILIER » et « rent » ⊂ « PARENTS » : le filtrage
    par sous-chaîne faisait passer 10 680 €/an de capital en petit
    équipement, et un décaissement en loyer."""
    t = import_bancaire.categoriser(libelle, montant)
    assert t not in ("petit_equipement", "loyer")
    assert t == "attente_decaissement"


@pytest.mark.parametrize("libelle,attendu", [
    ("FACTURE CABINET COMPTABLE", "honoraires"),     # comptab ⊂ COMPTABLE
    ("DEVIS REPARATIONS TOITURE", "maintenance"),    # reparation ⊂ REPARATIONS
    ("PRLV ASSURANCES GMF",       "assurance"),      # assurance ⊂ ASSURANCES
])
def test_e04_les_terminaisons_flechies_matchent_toujours(libelle, attendu):
    """L'ancrage porte sur le DÉBUT du mot, pas sur sa fin : un `\\b` des deux
    côtés aurait fait tomber toutes les formes fléchies des libellés
    bancaires."""
    assert import_bancaire.categoriser(libelle, -100.0) == attendu


def test_e05_une_nature_de_charge_ne_prend_pas_un_encaissement(base):
    """Le scénario du rapport : l'historique dit « assurance » pour ce
    libellé, l'assureur rembourse un sinistre sous le même libellé. Sans
    contrôle du sens, 800 € encaissés devenaient 800 € de charge déductible
    — 1 600 € d'écart sur le résultat."""
    operations.saisir(base, type="assurance", montant=138.49,
                      date_operation="2026-01-15", bien_id=1,
                      libelle="PRLV GMF PNO", source="saisie")
    assert import_bancaire.categoriser("PRLV GMF PNO", -138.49, base) == "assurance"
    assert import_bancaire.categoriser("PRLV GMF PNO", 800.0, base) == "attente_encaissement"


def test_e05_une_nature_de_produit_ne_prend_pas_un_decaissement(base):
    """Le cas symétrique, celui qu'E-04 produisait : un décaissement
    libellé « loyer » ne peut pas être un produit."""
    assert import_bancaire.categoriser("VIR LOYER MARS", 795.0) == "loyer"
    assert import_bancaire.categoriser("REMB TROP PERCU LOYER", -795.0) \
        == "attente_decaissement"


def test_e06_le_fourre_tout_bloque_au_lieu_de_deduire(base):
    """628800 est une charge IMMÉDIATEMENT DÉDUCTIBLE : « signalé » n'empêche
    rien. 472000 déclenche le contrôle bloquant. C'est toute la différence
    entre un contrôle qui informe et un contrôle qui protège."""
    import controles
    t = import_bancaire.categoriser("PRLV FOURNISSEUR INCONNU", -95.0)
    assert t == "attente_decaissement"
    assert gabarits.GABARITS[t]["compte"] == "472000"

    operations.saisir(base, type=t, montant=95.0,
                      date_operation="2026-01-05", bien_id=1)
    codes = {a.code for a in controles.controler(base, 2026)
             if a.niveau == controles.BLOQUANT}
    assert "COMPTE_ATTENTE" in codes


def test_e06_une_ligne_en_attente_reste_hors_du_resultat(base):
    """Une charge non identifiée ne doit plus se déduire toute seule."""
    avant = _resultat(base)
    operations.saisir(base, type="attente_decaissement", montant=890.0,
                      date_operation="2026-01-05", bien_id=1)
    assert _resultat(base) == avant


def test_e06_historique_ne_resuggere_pas_une_attente(base):
    """Resuggérer un fourre-tout reconduirait le doute indéfiniment. Le test
    porte sur le DRAPEAU `requalifier`, pas sur le nom du type : depuis la
    passe E, `autres_charges` n'est plus le seul concerné."""
    operations.saisir(base, type="attente_decaissement", montant=33.0,
                      date_operation="2026-01-05", bien_id=1,
                      libelle="PRLV MYSTERE", source="saisie")
    assert import_bancaire.suggerer_depuis_historique(base, "PRLV MYSTERE") is None


def test_e04_mensualite_de_pret_ne_propose_rien(base):
    """Une mensualité mêle capital (non déductible) et intérêts
    (déductibles) : aucune proposition automatique ne peut être juste."""
    for libelle in ("ECHEANCE PRET 001234", "REMBOURSEMENT EMPRUNT N.12345",
                    "MENSUALITE CREDIT IMMOBILIER"):
        assert import_bancaire.categoriser(libelle, -890.0) \
            == "attente_decaissement", libelle


def test_e01_import_complet_ne_cree_plus_de_recette_fictive(base, tmp_path):
    """Bout en bout : le relevé d'E-01 importé et validé ne doit ajouter au
    résultat que ce qui est réellement imposable — l'allocation logement."""
    p = tmp_path / "releve.csv"
    p.write_text("date;libelle;montant\n"
                 "05/01/2026;VIREMENT DEPOT DE GARANTIE LOCATAIRE;700,00\n"
                 "06/01/2026;VIR M DUPONT APPORT;5000,00\n"
                 "07/01/2026;REMB SINISTRE GMF DEGAT DES EAUX;800,00\n"
                 "08/01/2026;VIR CAF ALLOCATION LOGEMENT;320,00\n",
                 encoding="utf-8")
    avant = _resultat(base)
    import_bancaire.importer(base, str(p), valider=True)
    apres = _resultat(base)
    # 320 € d'APL (loyer) + 800 € d'indemnité (produit courant) = 1 120 €.
    # Le dépôt de garantie (dette) et l'apport (attente) restent dehors.
    assert round(apres - avant, 2) == 1120.00


# ═══ Contrôle de publication — le trou trouvé en traitant la passe E ════
#
# `git ls-files` était lancé depuis le dossier du paquet : il ne listait que
# l'arborescence du logiciel. Un fichier placé à la racine du dépôt — le
# rapport d'audit dans docs/ — échappait au contrôle, alors qu'un dépôt
# public l'expose comme le reste. Le cas s'est produit pour de bon.

import subprocess


@pytest.mark.parametrize("chemin,interdit", [
    ("compta_lmnp_v8.41.0/compta_lmnp/reference/FEC_REFERENCE_2023.txt", True),
    ("un/dossier/quelconque/compta.db",                                  True),
    ("compta_lmnp_v8.41.0/compta_lmnp/seed_exemple.sql",                 True),
    ("paquet/certs/serveur.pem",                                         True),
    ("a/b/sauvegardes/compta-20260101.db",                               True),
    ("compta_lmnp_v8.41.0/compta_lmnp/demo/FEC_DEMO_2025.txt",          False),
    ("compta_lmnp_v8.41.0/compta_lmnp/app.py",                          False),
    ("docs/AUDIT_PASSE_E.md",                                           False),
])
def test_chemins_interdits_reconnus_a_toute_profondeur(chemin, interdit):
    """Les motifs sont ancrés sur un SEGMENT de chemin. Ancrés sur le début
    de la chaîne, ils seraient devenus muets dès que les chemins sont
    devenus relatifs à la racine — un contrôle qui ne voit plus rien tout en
    ayant l'air de fonctionner est pire qu'un contrôle absent."""
    import verifier_depot
    touche = any(m.search(chemin) for m in verifier_depot.CHEMINS_INTERDITS)
    assert touche is interdit, chemin


def test_verifier_depot_voit_les_fichiers_hors_du_paquet(tmp_path, monkeypatch):
    """Le scénario réel : une donnée personnelle dans un fichier situé à la
    racine du dépôt, hors de l'arborescence du logiciel."""
    import verifier_depot
    repo = tmp_path / "depot"
    (repo / "docs").mkdir(parents=True)
    (repo / "paquet").mkdir()
    (repo / "docs" / "rapport.md").write_text(
        "| `VIR M MARTIN APPORT` | +5 000,00 |\n", encoding="utf-8")
    (repo / "paquet" / "app.py").write_text("# rien de personnel\n",
                                            encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    # Empreinte factice : le test n'a pas à manipuler la vraie identité.
    monkeypatch.setattr(verifier_depot, "_empreintes",
                        lambda: [("nom de l'exploitant", "MARTIN")])
    r = verifier_depot.verifier(str(repo))

    assert r["fichiers_publies"] == 2
    fautifs = {a["fichier"] for a in r["alertes"]}
    assert "docs/rapport.md" in fautifs, r["alertes"]


def test_verifier_depot_reste_muet_sur_un_depot_propre(tmp_path, monkeypatch):
    """Contrepartie : pas de faux positif."""
    import verifier_depot
    repo = tmp_path / "depot"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "rapport.md").write_text("| `VIR M DUPONT APPORT` |\n",
                                              encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    monkeypatch.setattr(verifier_depot, "_empreintes",
                        lambda: [("nom de l'exploitant", "MARTIN")])
    assert verifier_depot.verifier(str(repo))["alertes"] == []


def test_verifier_depot_couvre_bien_la_racine_du_depot_reel():
    """Sur ce dépôt-ci : le contrôle doit voir docs/, qui vit hors du paquet."""
    import verifier_depot
    fichiers = verifier_depot._fichiers_publies()
    if not fichiers:
        pytest.skip("pas de dépôt git ici")
    assert any(f.startswith("docs/") for f in fichiers), \
        "le contrôle ne voit pas docs/ — le trou est revenu"


# ═══ E-07 / E-08 / E-09 — les majeurs restants ══════════════════════════

@pytest.mark.parametrize("accentue,sans_accent,attendu", [
    ("PRELEVEMENT TAXE FONCIÈRE 2026",  "PRELEVEMENT TAXE FONCIERE 2026",  "impot_local"),
    ("ENTRETIEN CHAUDIÈRE ANNUEL",      "ENTRETIEN CHAUDIERE ANNUEL",      "maintenance"),
    ("APPEL COPROPRIÉTÉ T1",            "APPEL COPROPRIETE T1",            "charge_copro"),
    ("DEVIS RÉPARATION TOITURE",        "DEVIS REPARATION TOITURE",        "maintenance"),
])
def test_e07_accents_indifferents(accentue, sans_accent, attendu):
    """Les clés de REGLES sont écrites sans accent, les libellés SEPA des
    banques en ligne les conservent. Taxe foncière, entretien de chaudière
    et appels de copropriété sont l'essentiel des charges d'un dossier
    LMNP : c'est le volume qui fait la gravité de ce défaut."""
    assert import_bancaire.categoriser(accentue, -1420.0) == attendu
    assert import_bancaire.categoriser(sans_accent, -1420.0) == attendu


def test_e07_la_cle_de_l_historique_nest_pas_repliee():
    """E-07 replie les accents pour la recherche PAR MOTS-CLÉS uniquement.

    La clé de l'historique reste non repliée, et c'est délibéré : la
    comparaison se fait côté SQL (`LOWER(TRIM(libelle))`). Replier en Python
    seulement creuserait un écart de plus entre les deux côtés.
    """
    assert import_bancaire._norm("TAXE FONCIÈRE") == "taxe fonciere"
    assert import_bancaire._cle_libelle("TAXE FONCIÈRE") == "taxe foncière"


@pytest.mark.xfail(strict=True, reason=(
    "LOWER() de SQLite est ASCII : « CHAUDIÈRE » y reste « CHAUDIèRE » alors "
    "que Python rend « chaudière ». L'historique ne retrouve donc AUCUN "
    "libellé accentué. Cause supplémentaire d'E-12, non relevée par le "
    "rapport, à traiter avec ce constat — pas une régression d'E-07, le "
    "défaut préexiste."))
def test_e12_historique_sur_libelle_accentue_connu_pour_echouer(base):
    operations.saisir(base, type="maintenance", montant=210.0,
                      date_operation="2026-03-01", bien_id=1,
                      libelle="ENTRETIEN CHAUDIÈRE ANNUEL", source="saisie")
    assert import_bancaire.suggerer_depuis_historique(
        base, "ENTRETIEN CHAUDIÈRE ANNUEL") == "maintenance"


@pytest.mark.parametrize("libelle", [
    "DGFIP COTISATION FONCIERE DES ENTREPRISES",
    "TRESOR PUBLIC CFE 2026",
    "CFE 2026 DGFIP",
])
def test_e08_la_cfe_nest_plus_captee_par_les_impots_locaux(libelle):
    """Les trois libellés réalistes d'un avis de CFE contiennent « dgfip »
    ou « tresor public » : la règle `cfe`, placée après, était inatteignable
    en pratique. Le plan distingue pourtant 635110 de 635130, et la liasse
    imprime une ligne « dont CFE » qui restait à zéro."""
    assert import_bancaire.categoriser(libelle, -310.0) == "cfe"


def test_e08_la_taxe_fonciere_reste_un_impot_local():
    """Contrepartie du réordonnancement : ne pas tout capter en CFE."""
    for libelle in ("DGFIP TAXE FONCIERE", "PRELEVEMENT TEOM",
                    "TRESOR PUBLIC IMPOT LOCAL"):
        assert import_bancaire.categoriser(libelle, -1162.0) == "impot_local"


def test_e08_cfe_et_taxe_fonciere_vont_dans_des_comptes_distincts():
    """Le point qui compte pour le déclarant : deux comptes, deux lignes."""
    assert gabarits.GABARITS["cfe"]["compte"] == "635110"
    assert gabarits.GABARITS["impot_local"]["compte"] == "635130"


@pytest.mark.parametrize("montant,attendu", [
    (-180.0,  "petit_equipement"),        # sous le seuil : charge
    (-499.0,  "petit_equipement"),
    (-501.0,  "attente_decaissement"),    # au-dessus : immobilisation
    (-1850.0, "attente_decaissement"),    # le scénario du rapport
])
def test_e09_seuil_dimmobilisation_applique_a_l_import(montant, attendu):
    """Au-delà de 500 € HT, un meuble destiné au logement meublé est une
    IMMOBILISATION (218400), pas du petit équipement (606320). Aucun test
    de montant n'existait dans le module."""
    assert import_bancaire.categoriser("ACHAT MOBILIER CONFORAMA", montant) == attendu


def test_e09_le_seuil_est_la_regle_versionnee_pas_une_constante(base):
    """Le seuil vit dans « Réglementation » et se lit au millésime de
    l'exercice. Un import daté de 2026 doit suivre la valeur 2026."""
    import parametres
    parametres.definir(base, "seuil_immobilisation", 1000.0,
                       date_debut="2026-01-01", reference="test",
                       commentaire="relèvement fictif")
    # 800 € : au-dessus de 500 (défaut) mais sous le nouveau seuil 2026.
    assert import_bancaire.categoriser("ACHAT MOBILIER CONFORAMA", -800.0,
                                       base, 2026) == "petit_equipement"
    assert import_bancaire.categoriser("ACHAT MOBILIER CONFORAMA", -1200.0,
                                       base, 2026) == "attente_decaissement"


def test_e09_le_seuil_ne_touche_que_les_gabarits_concernes():
    """Une charge sans drapeau `seuil_immo` n'est pas plafonnée : une taxe
    foncière de 1 420 € reste une taxe foncière."""
    assert import_bancaire.categoriser("DGFIP TAXE FONCIERE", -1420.0) == "impot_local"
    assert import_bancaire.categoriser("PRLV SYNDIC APPEL T1", -2500.0) == "charge_copro"


def test_e09_analyser_sert_le_millesime_de_la_ligne(tmp_path):
    """Le seuil dépend de l'exercice : analyser() le déduit de la date de
    l'opération, pas de l'année courante."""
    p = tmp_path / "releve.csv"
    p.write_text("date;libelle;montant\n"
                 "15/06/2026;ACHAT MOBILIER CONFORAMA;-1850,00\n",
                 encoding="utf-8")
    props = import_bancaire.analyser(str(p))["propositions"]
    assert props[0]["type"] == "attente_decaissement"
