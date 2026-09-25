# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Suivi des dépôts de déclaration (liasse 2031/2033, 2042-C-PRO).

Un test par règle et par refus. Scénarios sur le jeu de démonstration
anonymisé : exercice 2026 clôturé, dépôts datés au printemps 2027 par une
horloge injectée.

Lancer :  pytest -q tests/test_suivi_depot.py
"""
import hashlib
import importlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import date

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import controles
import depots
import export_fec
import fiscal
import init_db
import liasse
import migrations
import operations
import pense_bete
import perennite
import reprise

FEC_DEMO = os.path.join(HERE, "demo", "FEC_DEMO_2025.txt")
PRINTEMPS = date(2027, 5, 20)


def _dossier(chemin, *, clore=True):
    """Dossier de démonstration, 2026 clôturé (forcé : la démo porte une
    anomalie bloquante sans rapport avec les dépôts)."""
    c = init_db.init_demo(chemin, FEC_DEMO, 2026)
    c.execute("PRAGMA foreign_keys = ON")
    if clore:
        fiscal.cloturer(c, 2026, forcer=True)
    return c


@pytest.fixture()
def chemin(tmp_path):
    return str(tmp_path / "compta.db")


@pytest.fixture()
def conn(chemin):
    c = _dossier(chemin)
    yield c
    c.close()


def _depot(conn, type_="liasse_2031", nature="initiale", jour="2027-05-12",
           **kw):
    return depots.enregistrer(conn, annee=2026, type=type_, nature=nature,
                              date_depot=jour, aujourd_hui=PRINTEMPS, **kw)


def _nb(conn):
    return conn.execute("SELECT COUNT(*) FROM depot_declaration").fetchone()[0]


def _refus(conn, motif, **kw):
    """Le refus porte le message attendu et ne laisse aucune trace."""
    avant = conn.execute("SELECT * FROM depot_declaration ORDER BY id").fetchall()
    with pytest.raises(ValueError, match=motif):
        _depot(conn, **kw)
    assert conn.execute("SELECT * FROM depot_declaration ORDER BY id"
                        ).fetchall() == avant
    assert not conn.in_transaction


# ── Règles 1 et 2 : deux suivis, contenu, ordre ──────────────────────────

def test_depot_nominal_de_la_liasse(conn):
    n = _depot(conn, reference="ACC-2027-0001", note="télétransmise")
    d = depots.lister(conn, 2026)
    assert [x["id"] for x in d["liasse_2031"]] == [n]
    assert d["2042_c_pro"] == []
    ligne = d["liasse_2031"][0]
    assert (ligne["nature"], ligne["date_depot"], ligne["reference"],
            ligne["note"]) == ("initiale", "2027-05-12", "ACC-2027-0001",
                               "télétransmise")


def test_depot_nominal_de_la_2042_apres_la_liasse(conn):
    _depot(conn)
    _depot(conn, type_="2042_c_pro", jour="2027-05-20")
    d = depots.lister(conn, 2026)
    assert len(d["liasse_2031"]) == 1 and len(d["2042_c_pro"]) == 1
    assert depots.initiales(conn, 2026) == {"liasse_2031": "2027-05-12",
                                            "2042_c_pro": "2027-05-20"}


def test_instantane_lu_dans_la_liasse(conn):
    _depot(conn)
    _depot(conn, type_="2042_c_pro")
    d = depots.lister(conn, 2026)
    b = liasse.resultat_2033b(conn, 2026)
    assert d["liasse_2031"][0]["chiffres"] == {
        "resultat_fiscal": round(b["resultat_fiscal_lmnp"], 2),
        "resultat_fiscal_cloture": conn.execute(
            "SELECT resultat_fiscal FROM exercice WHERE annee=2026"
        ).fetchone()[0]}
    aide = liasse.aide_2042c(conn, 2026)
    attendu = {"5NA": aide["case_5NA"], "5NY": aide["case_5NY"]}
    attendu.update({c["case"]: c["montant"]
                    for c in aide["cases_deficits_anterieurs"]})
    assert d["2042_c_pro"][0]["chiffres"] == attendu


def test_rectificative_apres_initiale_ordre_chronologique(conn):
    _depot(conn, jour="2027-05-12")
    _depot(conn, nature="rectificative", jour="2027-05-19")
    _depot(conn, nature="rectificative", jour="2027-05-15")
    liste = depots.lister(conn, 2026)["liasse_2031"]
    assert [x["date_depot"] for x in liste] == ["2027-05-12", "2027-05-15",
                                               "2027-05-19"]
    assert [x["nature"] for x in liste] == ["initiale", "rectificative",
                                           "rectificative"]


def test_rectificative_le_jour_de_l_initiale_acceptee(conn):
    _depot(conn, jour="2027-05-12")
    _depot(conn, nature="rectificative", jour="2027-05-12")
    assert _nb(conn) == 2


# ── Règle 3 : refus ─────────────────────────────────────────────────────

def test_refus_date_future(conn):
    _refus(conn, "futur", jour="2027-05-21")


def test_refus_date_egale_a_la_fin_d_exercice(conn):
    _refus(conn, "antérieure ou égale", jour="2026-12-31")


def test_refus_date_anterieure_a_la_fin_d_exercice(conn):
    _refus(conn, "antérieure ou égale", jour="2026-06-30")


def test_refus_exercice_ouvert(chemin):
    c = _dossier(chemin, clore=False)
    try:
        with pytest.raises(ValueError, match="pas clôturé"):
            _depot(c)
        assert _nb(c) == 0
    finally:
        c.close()


def test_refus_exercice_inexistant(conn):
    with pytest.raises(ValueError, match="n'existe pas"):
        depots.enregistrer(conn, annee=2030, type="liasse", nature="initiale",
                           date_depot="2031-05-01",
                           aujourd_hui=date(2031, 6, 1))
    assert _nb(conn) == 0


def test_refus_date_mal_formee(conn):
    _refus(conn, "format attendu", jour="12/05/2027")


def test_refus_rectificative_sans_initiale(conn):
    _refus(conn, "aucune déclaration initiale", nature="rectificative")


def test_refus_rectificative_anterieure_a_l_initiale(conn):
    _depot(conn, jour="2027-05-12")
    _refus(conn, "avant l'initiale", nature="rectificative",
           jour="2027-05-11")


def test_refus_double_initiale(conn):
    _depot(conn)
    _refus(conn, "déjà enregistrée", jour="2027-05-13")


def test_double_initiale_bloquee_par_la_base(conn):
    """L'index partiel tient même si la vérification applicative est
    contournée (deux enregistrements concurrents)."""
    _depot(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO depot_declaration (exercice_annee, type, nature, "
            "date_depot, chiffres_json, enregistre_le) VALUES "
            "(2026, 'liasse_2031', 'initiale', '2027-05-13', '{}', 'x')")
    conn.rollback()


def test_la_2042_a_sa_propre_initiale(conn):
    """Une initiale de liasse n'empêche pas l'initiale de 2042 (et
    réciproquement) : deux suivis distincts."""
    _depot(conn)
    _depot(conn, type_="2042_c_pro")
    assert _nb(conn) == 2


def test_refus_reference_avec_tabulation(conn):
    _refus(conn, "tabulation", reference="ACC\t123")


def test_refus_reference_avec_saut_de_ligne(conn):
    _refus(conn, "saut de ligne", reference="ACC\n123")


def test_refus_reference_trop_longue(conn):
    _refus(conn, "trop longue", reference="X" * 65)


def test_reference_de_64_caracteres_acceptee(conn):
    _depot(conn, reference="X" * 64)
    assert depots.lister(conn, 2026)["liasse_2031"][0]["reference"] == "X" * 64


def test_espaces_de_bord_retires(conn):
    _depot(conn, reference="   ACC-1  ", note="  ok ")
    ligne = depots.lister(conn, 2026)["liasse_2031"][0]
    assert (ligne["reference"], ligne["note"]) == ("ACC-1", "ok")


def test_reference_blanche_devient_vide(conn):
    _depot(conn, reference="   ")
    assert depots.lister(conn, 2026)["liasse_2031"][0]["reference"] is None


def test_refus_note_trop_longue_ou_multiligne(conn):
    _refus(conn, "trop longue", note="n" * 201)
    _refus(conn, "saut de ligne", note="a\r\nb")


def test_refus_type_et_nature_inconnus(conn):
    _refus(conn, "Type de déclaration inconnu", type_="2044")
    _refus(conn, "Nature inconnue", nature="complementaire")


# ── Règle 5 : suppression ───────────────────────────────────────────────

def test_suppression(conn):
    n = _depot(conn)
    r = depots.supprimer(conn, n)
    assert r["annee"] == 2026 and _nb(conn) == 0
    # La ligne entière est partie : une nouvelle initiale est acceptée.
    _depot(conn, jour="2027-05-14")


def test_suppression_d_une_initiale_avec_rectificative_refusee(conn):
    n = _depot(conn)
    _depot(conn, nature="rectificative", jour="2027-05-15")
    with pytest.raises(ValueError, match="supprimez-les d'abord"):
        depots.supprimer(conn, n)
    assert _nb(conn) == 2


def test_suppression_d_un_depot_inexistant(conn):
    with pytest.raises(ValueError, match="Aucun dépôt"):
        depots.supprimer(conn, 999)


# ── Règle 6 : exercice clôturé sans dépôt (INFO) ────────────────────────

def _codes(conn, annee=2026):
    return [(a.niveau, a.code) for a in depots.controler(conn, annee)]


def test_info_exercice_clos_sans_depot(conn):
    assert _codes(conn) == [("INFO", "DEPOT_ABSENT")] * 2
    _depot(conn)
    assert _codes(conn) == [("INFO", "DEPOT_ABSENT")]
    _depot(conn, type_="2042_c_pro")
    assert _codes(conn) == []


def test_pas_d_info_sur_un_exercice_ouvert(chemin):
    c = _dossier(chemin, clore=False)
    try:
        assert _codes(c) == []
    finally:
        c.close()


def test_aucune_date_limite_codee(conn, monkeypatch):
    """Le contrôle ne dépend pas du calendrier : même verdict en janvier
    qu'en décembre, et aucune échéance annoncée."""
    verdicts = []
    for jour in (date(2027, 1, 2), date(2027, 5, 20), date(2027, 12, 30)):
        monkeypatch.setattr(depots, "_aujourd_hui", lambda j=jour: j)
        verdicts.append([(a.code, a.message)
                         for a in depots.controler(conn, 2026)])
    assert verdicts[0] == verdicts[1] == verdicts[2]
    for _, message in verdicts[0]:
        assert "2027" not in message and "limite" not in message


# ── Règle 4 : réouverture puis reclôture ────────────────────────────────

def _scenario_reouverture(chemin, modifier):
    """Réouverture telle qu'elle existe : restauration de la sauvegarde
    d'avant clôture, puis reclôture."""
    c = _dossier(chemin, clore=False)
    c.close()
    sauvegarde = perennite.sauvegarder(chemin, "avant-cloture")
    c = sqlite3.connect(chemin)
    c.execute("PRAGMA foreign_keys = ON")
    fiscal.cloturer(c, 2026, forcer=True)
    _depot(c, reference="ACC-1")
    _depot(c, type_="2042_c_pro")
    assert _codes(c) == []
    c.close()
    perennite.restaurer(chemin, sauvegarde)
    c = sqlite3.connect(chemin)
    c.execute("PRAGMA foreign_keys = ON")
    # Rouvert : dépôts reportés, comparaison suspendue.
    assert c.execute("SELECT statut FROM exercice WHERE annee=2026"
                     ).fetchone()[0] == "ouvert"
    assert _nb(c) == 2
    assert {code for _, code in _codes(c)} == {"DEPOT_EXERCICE_ROUVERT"}
    if modifier:
        operations.saisir(c, type="loyer", montant=60000.0,
                          date_operation="2026-11-05", periode="2026-11")
    fiscal.cloturer(c, 2026, forcer=True)
    return c


def test_reouverture_avec_chiffres_modifies_alerte_chiffree(chemin):
    c = _scenario_reouverture(chemin, modifier=True)
    try:
        anos = depots.controler(c, 2026)
        assert {(a.niveau, a.code) for a in anos} == {
            ("AVERTISSEMENT", "DEPOT_ECART")}
        assert len(anos) == 2              # la liasse ET la 2042 ont bougé
        liasse_msg = next(a.message for a in anos if "2031" in a.message)
        declare = depots.lister(c, 2026)["liasse_2031"][0]["chiffres"]
        actuel = depots.chiffres_actuels(c, 2026, "liasse_2031")
        ecart = actuel["resultat_fiscal"] - declare["resultat_fiscal"]
        assert abs(ecart) > 1
        assert depots._fmt(ecart) in liasse_msg
        assert "rectificative peut être nécessaire" in liasse_msg
    finally:
        c.close()


def test_reouverture_sans_changement_aucune_alerte(chemin):
    c = _scenario_reouverture(chemin, modifier=False)
    try:
        assert _codes(c) == []
    finally:
        c.close()


def test_instantane_indisponible_est_dit(conn, monkeypatch):
    """Garde-fou qui ne peut pas travailler : il le dit."""
    def panne(*a, **k):
        raise RuntimeError("lecture impossible")
    monkeypatch.setattr(depots, "chiffres_actuels", panne)
    _depot(conn)
    monkeypatch.undo()
    assert ("INFO", "DEPOT_NON_COMPARABLE") in _codes(conn)


def test_chiffres_actuels_illisibles_est_dit(conn, monkeypatch):
    _depot(conn)

    def panne(*a, **k):
        raise RuntimeError("lecture impossible")
    monkeypatch.setattr(depots, "chiffres_actuels", panne)
    assert ("AVERTISSEMENT", "DEPOT_COMPARAISON_IMPOSSIBLE") in _codes(conn)


# ── Fonction purement déclarative ───────────────────────────────────────

def _empreintes(conn, tmp_path, etape):
    fec = export_fec.exporter(conn, 2026, str(tmp_path / f"fec-{etape}.txt"))
    with open(fec, "rb") as f:
        h_fec = hashlib.sha256(f.read()).hexdigest()
    L = json.dumps(liasse.generer(conn, 2026), sort_keys=True, default=str)
    ctl = [(a.niveau, a.code, a.message)
           for a in controles.controler(conn, 2026)]
    ecr = conn.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0]
    return h_fec, L, ctl, ecr


def test_fec_liasse_et_controles_identiques(conn, tmp_path):
    avant = _empreintes(conn, tmp_path, "avant")
    n = _depot(conn)
    _depot(conn, type_="2042_c_pro")
    pendant = _empreintes(conn, tmp_path, "pendant")
    depots.supprimer(conn, n)
    apres = _empreintes(conn, tmp_path, "apres")
    assert avant == pendant == apres


# ── Pense-bête ─────────────────────────────────────────────────────────

def _rappel(conn):
    return [r for r in pense_bete.rappels(conn, PRINTEMPS)
            if "2026" in r["titre"] and "clar" in r["titre"]]


def test_pense_bete_etape_faite_quand_les_deux_depots_sont_notes(conn):
    r = _rappel(conn)
    assert [(x["niveau"], x["titre"]) for x in r] == [
        ("important", "Déclarer les résultats 2026")]
    _depot(conn)
    r = _rappel(conn)
    assert r[0]["niveau"] == "important"
    assert "Déjà fait : Liasse 2031 / 2033" in r[0]["detail"]
    _depot(conn, type_="2042_c_pro", jour="2027-05-18")
    r = _rappel(conn)
    assert [(x["niveau"], x["titre"]) for x in r] == [
        ("fait", "Résultats 2026 déclarés ✓")]
    assert "2027-05-12" in r[0]["detail"] and "2027-05-18" in r[0]["detail"]


# ── Sauvegarde, restauration, cloisonnement, migration ──────────────────

def test_survie_a_une_sauvegarde_puis_restauration(chemin):
    c = _dossier(chemin)
    _depot(c, reference="ACC-9")
    c.close()
    sauvegarde = perennite.sauvegarder(chemin, "manuel")
    c = sqlite3.connect(chemin)
    c.execute("DELETE FROM depot_declaration")
    c.commit()
    c.close()
    # La base courante fait foi pour les dépôts : la suppression tient.
    perennite.restaurer(chemin, sauvegarde)
    c = sqlite3.connect(chemin)
    assert _nb(c) == 0
    c.close()
    # Et la sauvegarde, elle, a bien emporté le dépôt.
    s = sqlite3.connect(sauvegarde)
    assert s.execute("SELECT reference FROM depot_declaration"
                     ).fetchall() == [("ACC-9",)]
    s.close()


def test_restauration_reporte_les_depots_posterieurs(chemin):
    c = _dossier(chemin)
    c.close()
    sauvegarde = perennite.sauvegarder(chemin, "manuel")
    c = sqlite3.connect(chemin)
    _depot(c, reference="ACC-APRES")
    c.close()
    perennite.restaurer(chemin, sauvegarde)
    c = sqlite3.connect(chemin)
    assert c.execute("SELECT reference FROM depot_declaration"
                     ).fetchall() == [("ACC-APRES",)]
    c.close()


def _dossier_avec_depot_2027(chemin):
    """Sauvegarde prise quand 2027 n'existait pas, puis dépôt sur 2027."""
    c = _dossier(chemin)
    c.close()
    sauvegarde = perennite.sauvegarder(chemin, "manuel")
    c = sqlite3.connect(chemin)
    c.execute("PRAGMA foreign_keys = ON")
    reprise.ouvrir_exercice(c, 2027)
    operations.saisir(c, type="loyer", montant=700.0,
                      date_operation="2027-03-05", periode="2027-03")
    fiscal.cloturer(c, 2027, forcer=True)
    depots.enregistrer(c, annee=2027, type="liasse", nature="initiale",
                       date_depot="2028-05-10", reference="ACC-2027",
                       aujourd_hui=date(2028, 6, 1))
    _depot(c)
    c.close()
    return sauvegarde


def _empreinte(chemin):
    with open(chemin, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_restauration_refusee_si_l_exercice_du_depot_manque(chemin):
    sauvegarde = _dossier_avec_depot_2027(chemin)
    avant = _empreinte(chemin)
    copies = set(os.listdir(perennite.dossier_sauvegardes(chemin)))
    with pytest.raises(ValueError) as exc:
        perennite.restaurer(chemin, sauvegarde)
    msg = str(exc.value)
    assert "1 dépôt(s)" in msg and "2027" in msg and "ACC-2027" in msg
    # La voie de sortie est donnée, et l'absence de passage en force expliquée.
    assert "supprimez ces dépôts depuis la page Liasse" in msg
    assert "pas de bouton « restaurer quand même »" in msg
    # Base courante intacte, et rien n'a été entrepris.
    assert _empreinte(chemin) == avant
    assert set(os.listdir(perennite.dossier_sauvegardes(chemin))) == copies
    c = sqlite3.connect(chemin)
    assert _nb(c) == 2
    assert c.execute("SELECT statut FROM exercice WHERE annee=2027"
                     ).fetchone()[0] == "clos"
    c.close()


def test_restauration_forcee_ne_perd_que_les_orphelins(chemin):
    sauvegarde = _dossier_avec_depot_2027(chemin)
    perennite.restaurer(chemin, sauvegarde, perdre_depots=True)
    c = sqlite3.connect(chemin)
    assert c.execute("SELECT exercice_annee FROM depot_declaration"
                     ).fetchall() == [(2026,)]
    c.close()


def test_cloisonnement_du_bac_a_sable(tmp_path, monkeypatch):
    principal = str(tmp_path / "compta.db")
    bac = str(tmp_path / "bac.db")
    _dossier(principal).close()
    shutil.copy(principal, bac)
    client, _ = _client(tmp_path, monkeypatch, principal, bac)
    client.set_cookie("dossier", "bac_a_sable")
    r = client.post("/depots/enregistrer", data={
        "annee": "2026", "type": "liasse_2031", "nature": "initiale",
        "date_depot": "2027-05-12"})
    assert "ok=" in r.headers["Location"]
    for chemin_db, attendu in ((bac, 1), (principal, 0)):
        c = sqlite3.connect(chemin_db)
        assert _nb(c) == attendu, chemin_db
        c.close()


def test_migration_base_neuve(tmp_path):
    c = init_db.init(str(tmp_path / "neuve.db"), "blanc", annee_cible=2026)
    try:
        assert init_db.version_base(c) == init_db.VERSION_SCHEMA == 9
        assert c.execute("SELECT COUNT(*) FROM depot_declaration"
                         ).fetchone()[0] == 0
    finally:
        c.close()


def _contenu(chemin):
    """Toutes les tables sauf meta et la nouvelle, ligne à ligne."""
    c = sqlite3.connect(chemin)
    try:
        tables = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT "
            "IN ('meta', 'depot_declaration') ORDER BY name")]
        return {t: c.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
                for t in tables}
    finally:
        c.close()


def test_migration_depuis_la_version_precedente_du_dossier_de_demo(tmp_path):
    """Copie du dossier de démonstration ramenée au schéma 8 : ce que la
    version précédente du logiciel produisait (le palier 9 n'ajoute qu'une
    table)."""
    chemin = str(tmp_path / "compta.db")
    _dossier(chemin).close()
    c = sqlite3.connect(chemin)
    c.execute("DROP TABLE depot_declaration")
    c.execute("UPDATE meta SET valeur='8' WHERE cle='version_schema'")
    c.commit()
    c.close()
    avant = _contenu(chemin)

    r = migrations.migrer(chemin)
    assert (r["avant"], r["apres"]) == (8, 9)
    assert r["sauvegarde"] and os.path.exists(r["sauvegarde"])
    assert _contenu(chemin) == avant
    c = sqlite3.connect(chemin)
    try:
        assert init_db.version_base(c) == 9
        assert _nb(c) == 0
        assert c.execute("SELECT 1 FROM sqlite_master WHERE name="
                         "'ux_depot_initiale'").fetchone()
    finally:
        c.close()
    assert migrations.migrer(chemin)["sauvegarde"] is None     # rejouable


# ── Interface web ───────────────────────────────────────────────────────

def _client(tmp_path, monkeypatch, principal, bac=None):
    monkeypatch.setenv("COMPTA_DB", principal)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", bac or str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    monkeypatch.setattr(depots, "_aujourd_hui", lambda: PRINTEMPS)
    return app_mod.app.test_client(), app_mod


@pytest.fixture()
def web(tmp_path, monkeypatch):
    principal = str(tmp_path / "compta.db")
    _dossier(principal).close()
    client, app_mod = _client(tmp_path, monkeypatch, principal)
    yield client, principal
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def _poster(client, **champs):
    data = {"annee": "2026", "type": "liasse_2031", "nature": "initiale",
            "date_depot": "2027-05-12"}
    data.update(champs)
    return client.post("/depots/enregistrer", data=data)


def test_web_enregistrer_puis_afficher(web):
    client, principal = web
    r = _poster(client, reference="ACC-WEB")
    assert r.status_code == 302 and "ok=" in r.headers["Location"]
    assert r.headers["Location"].endswith("#depots")
    page = client.get("/liasse?annee=2026").get_data(as_text=True)
    assert 'id="depots"' in page and "ACC-WEB" in page
    assert "data-confirmer=\"Supprimer ce dépôt" in page
    cloture = client.get("/cloture").get_data(as_text=True)
    assert "2031/2033 : déposée le 2027-05-12" in cloture


def test_web_refus_avec_message(web):
    client, principal = web
    r = _poster(client, date_depot="2027-06-01")          # futur
    assert "err=" in r.headers["Location"]
    c = sqlite3.connect(principal)
    assert _nb(c) == 0
    c.close()


def test_web_supprimer(web):
    client, principal = web
    _poster(client)
    c = sqlite3.connect(principal)
    n = c.execute("SELECT id FROM depot_declaration").fetchone()[0]
    c.close()
    r = client.post(f"/depots/{n}/supprimer", data={"annee": "2026"})
    assert "ok=" in r.headers["Location"]
    c = sqlite3.connect(principal)
    assert _nb(c) == 0
    c.close()


def test_web_origine_etrangere_refusee(web):
    client, principal = web
    r = client.post(
        "/depots/enregistrer",
        data={"annee": "2026", "type": "liasse_2031", "nature": "initiale",
              "date_depot": "2027-05-12"},
        headers={"Origin": "https://exemple.invalid"})
    assert r.status_code == 403
    c = sqlite3.connect(principal)
    assert _nb(c) == 0
    c.close()


def test_web_pense_bete_affiche_l_etape_faite(web, monkeypatch):
    client, _ = web
    monkeypatch.setattr(pense_bete, "rappels", lambda *a, **k: [
        {"niveau": "fait", "titre": "Résultats 2026 déclarés ✓",
         "detail": "Liasse déposée le 2027-05-12."}])
    page = client.get("/pense-bete").get_data(as_text=True)
    assert 'class="rappel rappel-fait"' in page
    assert "✅ Résultats 2026 déclarés ✓" in page


# ── Ligne de commande ───────────────────────────────────────────────────

def _cli(monkeypatch, chemin, *args):
    import cli
    monkeypatch.setattr(cli, "DB", chemin)
    monkeypatch.setattr(depots, "_aujourd_hui", lambda: PRINTEMPS)
    monkeypatch.setattr(sys, "argv", ["cli.py", *args])
    cli.main()


def test_cli_ajouter_lister_supprimer(chemin, monkeypatch, capsys):
    _dossier(chemin).close()
    _cli(monkeypatch, chemin, "depot", "ajouter", "--annee", "2026",
         "--type", "liasse", "--nature", "initiale", "--date", "2027-05-12",
         "--reference", "ACC-CLI")
    sortie = capsys.readouterr().out
    assert f"Dossier : {chemin}" in sortie and "enregistré" in sortie
    _cli(monkeypatch, chemin, "depot", "lister", "--annee", "2026")
    sortie = capsys.readouterr().out
    assert "ACC-CLI" in sortie and "DEPOT_ABSENT" in sortie
    c = sqlite3.connect(chemin)
    n = c.execute("SELECT id FROM depot_declaration").fetchone()[0]
    c.close()
    _cli(monkeypatch, chemin, "depot", "supprimer", "--id", str(n), "--oui")
    assert "Dépôt supprimé" in capsys.readouterr().out
    c = sqlite3.connect(chemin)
    assert _nb(c) == 0
    c.close()


def test_cli_refus_code_de_retour(chemin, monkeypatch, capsys):
    _dossier(chemin).close()
    with pytest.raises(SystemExit) as exc:
        _cli(monkeypatch, chemin, "depot", "ajouter", "--annee", "2026",
             "--type", "2042", "--nature", "rectificative",
             "--date", "2027-05-12")
    assert "aucune déclaration initiale" in str(exc.value.code)


def test_cli_supprimer_sans_confirmation_abandonne(chemin, monkeypatch, capsys):
    c = _dossier(chemin)
    n = _depot(c)
    c.close()
    monkeypatch.setattr("builtins.input", lambda _: "n")
    _cli(monkeypatch, chemin, "depot", "supprimer", "--id", str(n))
    assert "rien n'a été supprimé" in capsys.readouterr().out
    c = sqlite3.connect(chemin)
    assert _nb(c) == 1
    c.close()
