# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Non-régression des constats de la passe Q (atomicité et concurrence).

Le fil rouge de cette passe n'est pas le calcul : c'est l'INSTANT. Presque
tous les contrôles du logiciel étaient justes ; ils étaient seulement posés
au mauvais moment — avant la prise du verrou d'écriture, ou après le commit.

Entre le moment où l'on constate qu'un loyer n'est pas encore annulé et
celui où on l'annule, une seconde demande passe : deux contre-passations
pour une écriture. Entre le moment où l'on constate qu'un logement n'est pas
encore quittancé et celui où l'on émet, une seconde demande passe : 1 600 €
attestés pour 800 € encaissés. Entre le moment où un exercice est déclaré
ouvert et celui où l'on y écrit, une clôture passe : le résultat figé ne
vaut plus. Et la symétrique, de l'autre côté du commit : un import bel et
bien enregistré était annoncé « interrompu » parce que la suppression d'un
fichier temporaire avait échoué — l'utilisateur relançait, et saisissait
8 000 € de recettes une seconde fois.

S'y ajoute une famille voisine : les traitements en DEUX écritures, où la
première est validée et la seconde refusée. Un composant à 12 000 € sans
son écriture d'acquisition, un appel de charges amputé de sa dernière
composante, un exercice 2027 ouvert alors que sa reprise vient d'être
refusée — trois états que l'utilisateur n'a jamais demandés et dont rien ne
l'avertit.

Aucune donnée réelle : bailleur, locataires et logement fictifs.

Lancer :  pytest -q tests/test_passe_q.py
"""
import os
import sqlite3
import threading

import pytest

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import app as A
import ecritures
import fiscal
import import_bancaire
import init_db
import migrations
import operations
import perennite
import quittances


# ── Fabriques de pièces fictives ──────────────────────────────────────────

def _base(chemin, annee=2026):
    """Bailleur, logement et exercice fictifs — le socle de tous les essais."""
    conn = init_db.init_blanc(chemin, annee)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Bailleur Fictif','000000000','Adresse fictive')")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total,adresse)"
                 " VALUES (1,1,'Logement Fictif',12000,'1 rue Fictive')")
    conn.commit()
    return conn


@pytest.fixture
def dossier(tmp_path):
    """(connexion, chemin) sur une base fictive fraîche."""
    chemin = str(tmp_path / "compta.db")
    conn = _base(chemin)
    yield conn, chemin
    conn.close()


def _ouvrir(chemin, timeout_ms=5000):
    """Seconde connexion sur la MÊME base — l'outil de base de cette passe."""
    conn = sqlite3.connect(chemin, timeout=timeout_ms / 1000)
    conn.execute(f"PRAGMA busy_timeout={timeout_ms}")
    return conn


def _loyer(conn, montant=800.0, periode="2026-01", jour="05"):
    return operations.saisir(conn, type="loyer", montant=montant, bien_id=1,
                             periode=periode,
                             date_operation=f"{periode}-{jour}")


def _en_parallele(cible, arguments):
    """Lance `cible(clé, *args)` dans un fil par jeu d'arguments, avec une
    barrière pour que l'entrelacement soit réel et non successif."""
    resultats = {}
    barriere = threading.Barrier(len(arguments), timeout=10)

    def _tour(cle, args):
        try:
            barriere.wait()
            resultats[cle] = ("ok", cible(*args))
        except Exception as exc:                          # noqa: BLE001
            resultats[cle] = ("refus", exc)

    fils = [threading.Thread(target=_tour, args=(cle, args))
            for cle, args in arguments.items()]
    for f in fils:
        f.start()
    for f in fils:
        f.join(timeout=15)
    return resultats


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client Flask sur une base fictive, journal et migrations remis à zéro."""
    chemin = str(tmp_path / "compta.db")
    _base(chemin).close()
    monkeypatch.setattr(A, "DB", chemin)
    monkeypatch.setattr(A, "BAC_A_SABLE_DB", str(tmp_path / "bac.db"))
    A._MIGRES.clear()
    getattr(A, "_MIGRATIONS_EN_ECHEC", {}).clear()
    # Le journal est IDEMPOTENT par marqueur : un handler posé par un autre
    # module de test viserait encore son propre dossier, et `_assurer_journal`
    # n'en rebrancherait aucun. On repart donc d'un logger nu, puis on rend
    # exactement ce qu'on a trouvé.
    anciens = list(A.app.logger.handlers)
    for h in anciens:
        if getattr(h, "_journal_compta", False):
            A.app.logger.removeHandler(h)
    yield A.app.test_client(), chemin
    for h in list(A.app.logger.handlers):
        if h not in anciens:
            A.app.logger.removeHandler(h)
            h.close()
    for h in anciens:
        if h not in A.app.logger.handlers:
            A.app.logger.addHandler(h)
    A._MIGRES.clear()
    getattr(A, "_MIGRATIONS_EN_ECHEC", {}).clear()


# ═══ Q-01 — lire ne valide pas ════════════════════════════════════════

def test_q01_lister_les_quittances_ne_valide_pas_la_transaction(dossier):
    """`assurer_schema` exécutait un `executescript`, qui valide
    IMPLICITEMENT la transaction en cours. Consulter la liste des quittances
    au milieu d'une saisie composée rendait donc définitifs 800 € que
    l'appelant s'apprêtait peut-être à annuler."""
    conn, _ = dossier
    operations.saisir(conn, type="loyer", montant=800, bien_id=1,
                      periode="2026-01", date_operation="2026-01-05",
                      commit=False)
    quittances.lister(conn)
    quittances.prochain_numero(conn)
    quittances.locataires(conn)
    assert conn.in_transaction, "la transaction de l'appelant a été validée"
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM operation").fetchone()[0] == 0


def test_q01_le_schema_deja_a_jour_ne_declenche_aucun_script(dossier):
    """Contre-épreuve du correctif : ce n'est pas le `executescript` qui a
    été rendu inoffensif, c'est son APPEL qui a disparu quand il n'y a rien
    à créer. Sur une base déjà au niveau, `assurer_schema` sort avant."""
    conn, _ = dossier
    quittances.assurer_schema(conn)          # création initiale
    vus = []
    conn.set_trace_callback(vus.append)
    try:
        quittances.assurer_schema(conn)
    finally:
        conn.set_trace_callback(None)
    ecrits = [s for s in vus
              if any(m in s.upper() for m in ("CREATE ", "ALTER ", "COMMIT"))]
    assert ecrits == [], ecrits


def test_q01_le_schema_manquant_est_bien_cree(dossier):
    """…et le raccourci ne doit pas empêcher la création quand elle est due."""
    conn, _ = dossier
    conn.execute("DROP TABLE IF EXISTS quittance")
    conn.execute("DROP TABLE IF EXISTS locataire")
    conn.commit()
    quittances.assurer_schema(conn)
    assert quittances.lister(conn) == []


# ═══ Q-02 — une écriture ne s'annule qu'une fois ══════════════════════

def test_q02_la_seconde_annulation_est_refusee(dossier):
    """Le contrôle « déjà annulée ? » existait, mais lisait avant le verrou."""
    conn, chemin = dossier
    op = _loyer(conn)
    conn.close()
    a, b = _ouvrir(chemin), _ouvrir(chemin)
    try:
        operations.annuler(a, op["operation_id"])
        with pytest.raises(ValueError, match="déjà annulée"):
            operations.annuler(b, op["operation_id"])
    finally:
        a.close()
        b.close()
    controle = _ouvrir(chemin)
    solde = controle.execute(
        "SELECT ROUND(SUM(credit-debit),2) FROM ligne "
        "WHERE compte_num LIKE '708%'").fetchone()[0]
    controle.close()
    assert solde == 0.0, "le loyer a été contre-passé deux fois"


def test_q02_deux_annulations_concurrentes_nen_passent_quune(dossier):
    """Le cas réel : deux onglets, deux clics. Une seule contre-passation
    doit exister, sinon les produits sont minorés de 800 €."""
    conn, chemin = dossier
    op = _loyer(conn)
    conn.close()
    def _annuler():
        cx = _ouvrir(chemin)
        try:
            return operations.annuler(cx, op["operation_id"])
        finally:
            cx.close()

    res = _en_parallele(_annuler, {"a": (), "b": ()})
    etats = sorted(v[0] for v in res.values())
    assert etats == ["ok", "refus"], f"entrelacement inattendu : {res}"
    controle = _ouvrir(chemin)
    contre = controle.execute(
        "SELECT COUNT(*) FROM ecriture WHERE libelle LIKE 'Annulation%'"
    ).fetchone()[0]
    solde = controle.execute(
        "SELECT ROUND(SUM(credit-debit),2) FROM ligne "
        "WHERE compte_num LIKE '708%'").fetchone()[0]
    controle.close()
    assert contre == 1
    assert solde == 0.0


# ═══ Q-03 — on n'écrit pas dans un exercice qui vient d'être clos ═════

def test_q03_une_ecriture_ne_passe_pas_apres_la_cloture(dossier):
    """Le statut de l'exercice était lu AVANT `BEGIN IMMEDIATE` : une
    clôture pouvait s'intercaler entre la lecture et l'insertion, et
    800 € s'ajoutaient à un exercice dont le résultat était déjà figé."""
    conn, chemin = dossier
    _loyer(conn)
    conn.close()
    a, b = _ouvrir(chemin), _ouvrir(chemin)
    try:
        fiscal.cloturer(a, 2026, generer_dotation=False, forcer=True)
        with pytest.raises(ValueError, match="clos"):
            ecritures.inserer(b, journal="BQ", date="2026-02-10", annee=2026,
                              libelle="Loyer tardif fictif", piece_ref="P1",
                              lignes=[("108000", 800, 0), ("708810", 0, 800)])
    finally:
        a.close()
        b.close()


def test_q03_le_refus_ne_laisse_pas_de_transaction_ouverte(dossier):
    """Le contrôle a été DÉPLACÉ après la prise du verrou : s'il refuse, il
    doit défaire lui-même la transaction qu'il vient d'ouvrir, sinon la
    base reste verrouillée pour tous les autres."""
    conn, chemin = dossier
    _loyer(conn)
    fiscal.cloturer(conn, 2026, generer_dotation=False, forcer=True)
    with pytest.raises(ValueError, match="clos"):
        ecritures.inserer(conn, journal="BQ", date="2026-02-10", annee=2026,
                          libelle="Loyer tardif fictif", piece_ref="P2",
                          lignes=[("108000", 800, 0), ("708810", 0, 800)])
    assert not conn.in_transaction, "le verrou d'écriture n'a pas été relâché"
    autre = _ouvrir(str(chemin), timeout_ms=1000)
    try:
        autre.execute("BEGIN IMMEDIATE")     # doit être immédiatement possible
        autre.rollback()
    finally:
        autre.close()


def test_q03_une_transaction_deja_ouverte_nest_pas_annulee_par_le_refus(dossier):
    """Nuance du correctif : le rollback ne vaut que si c'est NOTRE appel
    qui a ouvert la transaction. Une saisie composée qui reçoit ce refus
    doit garder la main sur son propre retour arrière."""
    conn, _ = dossier
    _loyer(conn)
    fiscal.cloturer(conn, 2026, generer_dotation=False, forcer=True)
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total,adresse)"
                 " VALUES (2,1,'Second logement fictif',1000,'2 rue')")
    with pytest.raises(ValueError, match="clos"):
        ecritures.inserer(conn, journal="BQ", date="2026-02-10", annee=2026,
                          libelle="Loyer tardif fictif", piece_ref="P3",
                          lignes=[("108000", 800, 0), ("708810", 0, 800)])
    assert conn.in_transaction, "la transaction de l'appelant a été annulée"
    conn.rollback()


def test_q03_le_statut_est_relu_apres_la_prise_du_verrou(dossier):
    """Le cœur du correctif tient en un déplacement : le statut de
    l'exercice était lu AVANT `BEGIN IMMEDIATE`. Un contrôle pris avant le
    verrou ne décrit que le passé — il ne dit rien de ce qui se produit
    pendant qu'on écrit. On trace donc l'ordre réel des instructions."""
    conn, _ = dossier
    _loyer(conn)
    conn.commit()
    vus = []
    conn.set_trace_callback(vus.append)
    try:
        ecritures.inserer(conn, journal="BQ", date="2026-03-10", annee=2026,
                          libelle="Loyer fictif", piece_ref="P4",
                          lignes=[("108000", 800, 0), ("708810", 0, 800)])
    finally:
        conn.set_trace_callback(None)
    verrou = next(i for i, s in enumerate(vus) if "BEGIN IMMEDIATE" in s.upper())
    controle = next(i for i, s in enumerate(vus)
                    if "statut FROM exercice" in s)
    assert verrou < controle, ("le statut est lu avant la prise du verrou : "
                               f"{vus[:6]}")


# ═══ Q-04 — un logement, une quittance par période ════════════════════

def _deux_occupants(conn):
    conn.execute("INSERT INTO locataire(id,bien_id,nom,date_entree,"
                 "loyer_mensuel) VALUES (1,1,'Occupant A Fictif',"
                 "'2026-01-01',800)")
    conn.execute("INSERT INTO locataire(id,bien_id,nom,date_entree,"
                 "loyer_mensuel) VALUES (2,1,'Occupant B Fictif',"
                 "'2026-01-01',800)")
    conn.commit()


def test_q04_deux_quittances_concurrentes_ne_passent_pas(dossier):
    """Le contrôle « ce logement a-t-il déjà été quittancé ? » était juste
    en séquentiel ; deux demandes parallèles le franchissaient toutes les
    deux et attestaient 1 600 € pour 800 € encaissés. La contrainte
    d'unicité porte sur (locataire, période) : elle ne voit pas le logement."""
    conn, chemin = dossier
    quittances.assurer_schema(conn)
    _deux_occupants(conn)
    _loyer(conn, 800)
    conn.close()

    def _emettre(locataire_id):
        cx = _ouvrir(chemin)
        try:
            return quittances.emettre(cx, locataire_id=locataire_id,
                                      periode="2026-01",
                                      date_paiement="2026-01-05")
        finally:
            cx.close()

    res = _en_parallele(_emettre, {"a": (1,), "b": (2,)})
    assert sorted(v[0] for v in res.values()) == ["ok", "refus"], res
    controle = _ouvrir(chemin)
    nombre, total = controle.execute(
        "SELECT COUNT(*), COALESCE(ROUND(SUM(loyer+charges),2),0) "
        "FROM quittance").fetchone()
    controle.close()
    assert (nombre, total) == (1, 800.0)


def test_q04_lemission_prend_le_verrou_avant_ses_controles(dossier):
    """Preuve directe du déplacement : une émission ouvre une transaction
    d'écriture dès son entrée — une autre connexion ne peut plus écrire
    tant qu'elle n'a pas terminé."""
    conn, _ = dossier
    quittances.assurer_schema(conn)
    _deux_occupants(conn)
    _loyer(conn, 800)
    conn.commit()
    vus = []
    conn.set_trace_callback(vus.append)
    try:
        quittances.emettre(conn, locataire_id=1, periode="2026-01",
                           date_paiement="2026-01-05")
    finally:
        conn.set_trace_callback(None)
    verrou = next(i for i, s in enumerate(vus) if "BEGIN IMMEDIATE" in s.upper())
    controle = next(i for i, s in enumerate(vus) if "FROM locataire" in s)
    assert verrou < controle, ("le contrôle est lu avant la prise du "
                               f"verrou : {vus[:6]}")


# ═══ Q-05 — deux sauvegardes dans la même seconde ═════════════════════

def test_q05_deux_sauvegardes_simultanees_ne_secrasent_pas(dossier):
    """Le nom ne portait que la SECONDE : deux copies déclenchées dans la
    même seconde visaient le même fichier, et la seconde écrasait la
    première. Deux restaurations lancées ensemble faisaient donc disparaître
    l'état d'origine de la copie censée permettre le retour en arrière."""
    conn, chemin = dossier
    _loyer(conn, 800)
    conn.commit()
    premier = perennite.sauvegarder(chemin, "essai-fictif")
    second = perennite.sauvegarder(chemin, "essai-fictif")
    troisieme = perennite.sauvegarder(chemin, "essai-fictif")
    assert len({premier, second, troisieme}) == 3
    assert all(os.path.exists(c) for c in (premier, second, troisieme))


def test_q05_la_restauration_conserve_letat_courant(dossier):
    """Le scénario complet : 800 € sauvegardés, un second loyer de 800 €
    saisi, deux restaurations lancées ensemble. La base doit revenir à un
    loyer, et une copie de sûreté doit encore en contenir deux."""
    conn, chemin = dossier
    _loyer(conn, 800, periode="2026-01")
    conn.commit()
    source = perennite.sauvegarder(chemin, "avant-fictif")
    _loyer(conn, 800, periode="2026-02")
    conn.commit()
    conn.close()

    def _restaurer(_):
        return perennite.restaurer(chemin, source)

    res = _en_parallele(_restaurer, {"a": (1,), "b": (2,)})
    assert any(v[0] == "ok" for v in res.values()), res
    apres = _ouvrir(chemin)
    assert apres.execute("SELECT COUNT(*) FROM operation").fetchone()[0] == 1
    apres.close()
    surete = [os.path.join(perennite.dossier_sauvegardes(chemin), n)
              for n in os.listdir(perennite.dossier_sauvegardes(chemin))
              if "avant-restauration" in n]
    assert surete, "aucune copie de sûreté n'a été conservée"
    comptes = []
    for c in surete:
        cx = sqlite3.connect(c)
        comptes.append(cx.execute("SELECT COUNT(*) FROM operation").fetchone()[0])
        cx.close()
    assert 2 in comptes, ("l'état à deux loyers n'est plus nulle part : "
                          f"copies de sûreté = {comptes}")


# ═══ Q-06 — un appel de charges est indivisible ═══════════════════════

def test_q06_un_appel_de_charges_invalide_ne_laisse_rien(dossier):
    """Les trois composantes étaient saisies l'une après l'autre, chacune
    avec son commit : un montant non fini sur la dernière laissait 700 €
    de charges enregistrées, sans que le message d'erreur le dise."""
    conn, _ = dossier
    with pytest.raises(ValueError):
        operations.saisir_appel_charges(
            conn, date_operation="2026-01-10", periode="2026-01",
            charges_courantes=600, fonds_alur=100,
            travaux=float("inf"), bien_id=1)
    assert conn.execute("SELECT COUNT(*) FROM operation").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] == 0


def test_q06_un_appel_de_charges_valide_reste_complet(dossier):
    """Contre-épreuve : le tout-ou-rien ne doit pas empêcher le cas normal."""
    conn, _ = dossier
    res = operations.saisir_appel_charges(
        conn, date_operation="2026-01-10", periode="2026-01",
        charges_courantes=600, fonds_alur=100, travaux=300, bien_id=1)
    assert res
    assert conn.execute("SELECT COUNT(*) FROM operation").fetchone()[0] == 3


# ═══ Q-07 — un composant sans son acquisition ═════════════════════════

def test_q07_un_composant_a_date_invalide_nest_pas_enregistre(client):
    """Le composant était inséré et validé, PUIS l'écriture d'acquisition
    était tentée : une date inexistante (30 février) faisait échouer la
    seconde et laissait 12 000 € d'immobilisation au référentiel, sans
    écriture, avec une date durablement invalide."""
    cli, chemin = client
    rep = cli.post("/immobilisations/composant", data={
        "bien_id": "1", "libelle": "Mobilier Fictif", "valeur_brute": "12000",
        "duree_annees": "10", "compte_immo": "218400",
        "date_mise_service": "2026-02-30"}, follow_redirects=False)
    assert rep.status_code in (302, 303)
    cx = sqlite3.connect(chemin)
    try:
        assert cx.execute("SELECT COUNT(*) FROM composant").fetchone()[0] == 0
        assert cx.execute("SELECT COUNT(*) FROM ligne").fetchone()[0] == 0
    finally:
        cx.close()


def test_q07_un_composant_valide_est_bien_enregistre(client):
    """Contre-épreuve : la transaction unique ne doit rien casser du cas
    nominal — composant ET écriture d'acquisition."""
    cli, chemin = client
    cli.post("/immobilisations/composant", data={
        "bien_id": "1", "libelle": "Mobilier Fictif", "valeur_brute": "12000",
        "duree_annees": "10", "compte_immo": "218400",
        "date_mise_service": "2026-02-01"})
    cx = sqlite3.connect(chemin)
    try:
        assert cx.execute("SELECT COUNT(*) FROM composant").fetchone()[0] == 1
        assert cx.execute("SELECT COUNT(*) FROM ligne WHERE compte_num='218400'"
                          ).fetchone()[0] == 1
    finally:
        cx.close()


# ═══ Q-08 — un import enregistré ne s'annonce pas interrompu ══════════

def _releve(chemin, nombre=10, montant=800.0):
    lignes = [f"2026-01-{j:02d};VIREMENT LOYER FICTIF;{montant:.2f}"
              for j in range(1, nombre + 1)]
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes))
    return chemin


def _preparer_import(cli, tmp, nombre=10):
    """Passe par l'étape 1 réelle et rend le jeton d'import."""
    import io
    csv = _releve(str(tmp / "releve.csv"), nombre)
    with open(csv, "rb") as f:
        contenu = f.read()
    rep = cli.post("/import/proposer", data={
        "releve": (io.BytesIO(contenu), "releve.csv")},
        content_type="multipart/form-data")
    corps = rep.get_data(as_text=True)
    import re
    jeton = re.search(r'name="jeton"\s+value="([0-9a-f]{32})"', corps)
    assert jeton, "l'étape 1 n'a pas produit de jeton"
    return jeton.group(1)


def test_q08_lechec_du_nettoyage_navertit_pas_dune_annulation(client, tmp_path,
                                                              monkeypatch):
    """La panne se situe APRÈS le commit : les dix opérations sont en base.
    Annoncer « Import interrompu » poussait à relancer, et 8 000 € de
    recettes étaient saisis une seconde fois — l'import n'a aucune clé
    d'idempotence qui l'aurait rattrapé."""
    cli, chemin = client
    jeton = _preparer_import(cli, tmp_path)
    vrai_remove = os.remove

    def _refus(p, *a, **k):
        if p.endswith(jeton + ".csv"):
            raise PermissionError("suppression fictive refusée")
        return vrai_remove(p, *a, **k)

    monkeypatch.setattr(A.os, "remove", _refus)
    rep = cli.post("/import/valider",
                   data={"jeton": jeton, "ligne": [str(i) for i in range(10)]})
    cible = rep.headers["Location"]
    assert "err=" not in cible, f"un import enregistré est annoncé échoué : {cible}"
    assert "warn=" in cible
    cx = sqlite3.connect(chemin)
    try:
        assert cx.execute("SELECT COUNT(*) FROM operation").fetchone()[0] == 10
    finally:
        cx.close()


def test_q08_lavertissement_dit_de_ne_pas_relancer(client, tmp_path,
                                                   monkeypatch):
    """Un avertissement qui ne dit pas quoi faire ne vaut rien : le message
    doit nommer l'enregistrement réussi, interdire la relance et donner le
    fichier à supprimer à la main."""
    cli, _ = client
    jeton = _preparer_import(cli, tmp_path)
    vrai_remove = os.remove

    def _refus(p, *a, **k):
        if p.endswith(jeton + ".csv"):
            raise PermissionError("suppression fictive refusée")
        return vrai_remove(p, *a, **k)

    monkeypatch.setattr(A.os, "remove", _refus)
    rep = cli.post("/import/valider",
                   data={"jeton": jeton, "ligne": [str(i) for i in range(10)]},
                   follow_redirects=True)
    corps = rep.get_data(as_text=True)
    assert "enregistrée(s)" in corps
    assert "NE RELANCEZ PAS" in corps


def test_q08_une_vraie_annulation_reste_une_erreur(client, tmp_path,
                                                   monkeypatch):
    """Contre-épreuve : l'assouplissement ne vaut QUE pour le nettoyage. Un
    échec pendant la boucle d'insertion doit toujours tout annuler et le
    dire."""
    cli, chemin = client
    jeton = _preparer_import(cli, tmp_path)
    vrai_saisir = operations.saisir
    compteur = {"n": 0}

    def _panne(conn, **kw):
        compteur["n"] += 1
        if compteur["n"] == 7:
            raise ValueError("panne fictive à la septième ligne")
        return vrai_saisir(conn, **kw)

    monkeypatch.setattr(operations, "saisir", _panne)
    rep = cli.post("/import/valider",
                   data={"jeton": jeton, "ligne": [str(i) for i in range(10)]})
    assert "err=" in rep.headers["Location"]
    cx = sqlite3.connect(chemin)
    try:
        assert cx.execute("SELECT COUNT(*) FROM operation").fetchone()[0] == 0
    finally:
        cx.close()


# ═══ Q-09 — une reprise multiple est indivisible ══════════════════════

def _fec_fictif(chemin, annee, second_credit=800.0):
    """Deux loyers de 800 €, dont le second peut être rendu déséquilibré."""
    colonnes = ("JournalCode\tJournalLib\tEcritureNum\tEcritureDate\t"
                "CompteNum\tCompteLib\tCompAuxNum\tCompAuxLib\tPieceRef\t"
                "PieceDate\tEcritureLib\tDebit\tCredit\tEcritureLet\t"
                "DateLet\tValidDate\tMontantdevise\tIdevise")
    lignes = [colonnes]
    for n, (credit, jour) in enumerate(((800.0, "05"), (second_credit, "06")),
                                       start=1):
        for compte, debit, cred in (("512000", 800.0, 0.0),
                                    ("706000", 0.0, credit)):
            lignes.append("\t".join([
                "BQ", "Banque", str(n), f"{annee}01{jour}", compte,
                "Compte fictif", "", "", f"P{n}", f"{annee}01{jour}",
                "Loyer fictif", f"{debit:.2f}".replace(".", ","),
                f"{cred:.2f}".replace(".", ","), "", "",
                f"{annee}0131", "", ""]))
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")
    return chemin


def _preparer_multi(cli, tmp, credit_2025=801.0):
    import io
    a = _fec_fictif(str(tmp / "fec2024.txt"), 2024)
    b = _fec_fictif(str(tmp / "fec2025.txt"), 2025, second_credit=credit_2025)
    fichiers = []
    for c in (a, b):
        with open(c, "rb") as f:
            fichiers.append((io.BytesIO(f.read()), os.path.basename(c)))
    rep = cli.post("/exercice/analyser-fec", data={"fecs": fichiers},
                   content_type="multipart/form-data")
    import re
    corps = rep.get_data(as_text=True)
    jeton = re.search(r'name="jeton"\s+value="([0-9a-f]{32})"', corps)
    assert jeton, f"l'analyse n'a pas produit de jeton : {corps[:400]}"
    return jeton.group(1)


def test_q09_une_reprise_multiple_echouee_ne_laisse_rien(client, tmp_path):
    """Chaque rejeu committait le sien : l'échec sur 2025 laissait 1 600 €
    de recettes 2024 durablement reprises, alors que l'action globale se
    terminait en erreur."""
    cli, chemin = client
    jeton = _preparer_multi(cli, tmp_path)
    rep = cli.post("/exercice/reprendre-fec-multi", data={"jeton": jeton})
    assert "err=" in rep.headers["Location"]
    cx = sqlite3.connect(chemin)
    try:
        annees = [r[0] for r in cx.execute("SELECT annee FROM exercice "
                                           "ORDER BY annee")]
        assert annees == [2026], f"un exercice partiel subsiste : {annees}"
        assert cx.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] == 0
    finally:
        cx.close()


def test_q09_la_preparation_est_conservee_apres_echec(client, tmp_path):
    """…et le dossier téléversé était SUPPRIMÉ par le `finally` : l'action
    échouait et de quoi recommencer avait disparu. On doit pouvoir relancer
    avec le même jeton."""
    cli, chemin = client
    jeton = _preparer_multi(cli, tmp_path)
    cli.post("/exercice/reprendre-fec-multi", data={"jeton": jeton})
    prepare = os.path.join(os.path.dirname(chemin), "imports_tmp", jeton)
    assert os.path.isdir(prepare), "la préparation a été effacée par l'échec"
    rep = cli.post("/exercice/reprendre-fec-multi", data={"jeton": jeton},
                   follow_redirects=True)
    corps = rep.get_data(as_text=True)
    assert "Reprise interrompue" in corps, "le jeton n'est plus exploitable"


def test_q09_une_reprise_multiple_saine_reste_possible(client, tmp_path):
    """Contre-épreuve : les deux exercices équilibrés doivent passer."""
    cli, chemin = client
    jeton = _preparer_multi(cli, tmp_path, credit_2025=800.0)
    rep = cli.post("/exercice/reprendre-fec-multi", data={"jeton": jeton})
    assert "ok=" in rep.headers["Location"], rep.headers["Location"]
    cx = sqlite3.connect(chemin)
    try:
        annees = [r[0] for r in cx.execute("SELECT annee FROM exercice "
                                           "ORDER BY annee")]
        assert annees == [2024, 2025, 2026]
    finally:
        cx.close()


# ═══ Q-10 — une migration en échec ferme la porte ═════════════════════

def _rabaisser(chemin, version=2):
    cx = sqlite3.connect(chemin)
    cx.execute("UPDATE meta SET valeur=? WHERE cle='version_schema'",
               (str(version),))
    cx.commit()
    cx.close()


def test_q10_une_migration_echouee_bloque_lacces(client, monkeypatch):
    """L'exception était AVALÉE : la requête continuait sur un schéma à
    moitié mis à niveau, sans un mot. La garde doit désormais refuser."""
    cli, chemin = client
    _rabaisser(chemin)

    def _panne(*a, **k):
        raise RuntimeError("migration fictive impossible")

    monkeypatch.setattr(migrations, "migrer", _panne)
    monkeypatch.setattr(A.migrations, "migrer", _panne)
    rep = cli.get("/")
    assert rep.status_code == 409
    corps = rep.get_data(as_text=True)
    assert "migration fictive impossible" in corps


def test_q10_le_refus_garde_une_sortie(client, monkeypatch):
    """Un refus sans issue enfermerait l'utilisateur : la page 409 doit
    proposer le retour au dossier principal, seule action encore permise."""
    cli, chemin = client
    _rabaisser(chemin)
    monkeypatch.setattr(A.migrations, "migrer",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("migration fictive impossible")))
    corps = cli.get("/").get_data(as_text=True)
    assert "/dossiers/retour-principal" in corps


def test_q10_une_migration_reussie_ne_bloque_pas(client, monkeypatch):
    """Contre-épreuve : une base en retard qui se migre normalement doit
    s'ouvrir, et la mémoire d'échec rester vide."""
    cli, chemin = client
    _rabaisser(chemin)
    rep = cli.get("/")
    assert rep.status_code != 409, rep.get_data(as_text=True)[:400]
    assert A._MIGRATIONS_EN_ECHEC == {}
    cx = sqlite3.connect(chemin)
    try:
        assert init_db.version_base(cx) == init_db.VERSION_SCHEMA
    finally:
        cx.close()


def test_q10_lechec_est_reessayable(client, monkeypatch):
    """L'échec ne doit pas être définitif pour la session : le chemin est
    retiré des dossiers déjà migrés, pour qu'un redémarrage — ou la
    disparition de la cause — puisse réessayer."""
    cli, chemin = client
    _rabaisser(chemin)
    monkeypatch.setattr(A.migrations, "migrer",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("migration fictive impossible")))
    cli.get("/")
    assert chemin not in A._MIGRES


# ═══ Q-11 — pas d'exercice ouvert si la reprise est refusée ═══════════

def test_q11_louverture_avec_reprise_refusee_ne_cree_rien(client):
    """L'exercice 2027 était créé et validé, PUIS la reprise était tentée et
    refusée parce que 2026 n'est pas clos. Le message invitait à clôturer
    puis recommencer — mais 2027 existait déjà, vide et sans reprise."""
    cli, chemin = client
    rep = cli.post("/exercice/ouvrir", data={
        "annee": "2027", "date_debut": "2027-01-01",
        "date_fin": "2027-12-31", "reprise": "1"})
    assert "err=" in rep.headers["Location"]
    cx = sqlite3.connect(chemin)
    try:
        annees = [r[0] for r in cx.execute("SELECT annee FROM exercice "
                                           "ORDER BY annee")]
        assert annees == [2026], f"un exercice fantôme subsiste : {annees}"
    finally:
        cx.close()


def test_q11_louverture_sans_reprise_reste_possible(client):
    """Contre-épreuve : sans demande de reprise, l'ouverture d'un exercice
    suivant n'a aucune raison d'être refusée."""
    cli, chemin = client
    rep = cli.post("/exercice/ouvrir", data={
        "annee": "2027", "date_debut": "2027-01-01", "date_fin": "2027-12-31"})
    assert "err=" not in rep.headers["Location"], rep.headers["Location"]
    cx = sqlite3.connect(chemin)
    try:
        annees = [r[0] for r in cx.execute("SELECT annee FROM exercice "
                                           "ORDER BY annee")]
        assert annees == [2026, 2027]
    finally:
        cx.close()


# ═══ Q-12 — un incident géré se conserve aussi ════════════════════════

def test_q12_un_import_annule_laisse_une_trace_persistante(client, tmp_path,
                                                           monkeypatch):
    """Le journal était branché PARESSEUSEMENT, par le gestionnaire
    d'exception global — c'est-à-dire par les seules erreurs NON gérées. Un
    import proprement annulé à la septième ligne sur dix n'initialisait
    rien : sa trace partait sur la sortie d'erreur du processus et
    disparaissait à la fermeture du lanceur."""
    cli, chemin = client
    jeton = _preparer_import(cli, tmp_path)
    vrai_saisir = operations.saisir
    compteur = {"n": 0}

    def _panne(conn, **kw):
        compteur["n"] += 1
        if compteur["n"] == 7:
            raise ValueError("panne fictive à la septième ligne")
        return vrai_saisir(conn, **kw)

    monkeypatch.setattr(operations, "saisir", _panne)
    cli.post("/import/valider",
             data={"jeton": jeton, "ligne": [str(i) for i in range(10)]})
    journal = os.path.join(os.path.dirname(chemin), "logs", "erreurs.log")
    assert os.path.exists(journal), "aucun journal persistant n'a été créé"
    trace = open(journal, encoding="utf-8").read()
    assert "ligne 7" in trace, trace[:400]


def test_q12_limport_annule_nenregistre_rien(client, tmp_path, monkeypatch):
    """Rappel du tout-ou-rien : la trace ne remplace pas le rollback, elle
    s'y ajoute."""
    cli, chemin = client
    jeton = _preparer_import(cli, tmp_path)
    vrai_saisir = operations.saisir
    compteur = {"n": 0}

    def _panne(conn, **kw):
        compteur["n"] += 1
        if compteur["n"] == 7:
            raise ValueError("panne fictive à la septième ligne")
        return vrai_saisir(conn, **kw)

    monkeypatch.setattr(operations, "saisir", _panne)
    cli.post("/import/valider",
             data={"jeton": jeton, "ligne": [str(i) for i in range(10)]})
    cx = sqlite3.connect(chemin)
    try:
        assert cx.execute("SELECT COUNT(*) FROM operation").fetchone()[0] == 0
    finally:
        cx.close()


def test_q12_lannulation_nomme_le_rang_et_le_total(dossier):
    """Le message rendu à l'utilisateur doit situer l'incident : la
    septième ligne sur dix, et non « une erreur est survenue »."""
    conn, _ = dossier
    props = [{"type": "loyer", "montant": 800.0,
              "date_operation": f"2026-01-{j:02d}", "periode": "2026-01",
              "libelle": "Loyer fictif"} for j in range(1, 11)]
    props[6]["montant"] = float("nan")
    with pytest.raises(import_bancaire.ImportAnnule) as erreur:
        import_bancaire.enregistrer(conn, props, set(range(10)))
    assert erreur.value.rang == 7
    assert erreur.value.total == 10
    assert conn.execute("SELECT COUNT(*) FROM operation").fetchone()[0] == 0
