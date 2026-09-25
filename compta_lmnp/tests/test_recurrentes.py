# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Charges récurrentes et moteur d'échéances.

Un test par règle et par refus. Scénarios sur le jeu de démonstration
anonymisé (2025 clôturé, 2026 ouvert) ou sur une base blanche avec un bien
fictif ; horloge injectée.

Lancer :  pytest -q tests/test_recurrentes.py
"""
import importlib
import os
import shutil
import sqlite3
import sys
from datetime import date

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import cession
import echeancier
import export_fec
import gabarits
import init_db
import migrations
import operations
import perennite
import recurrentes
import valider_fec

FEC_DEMO = os.path.join(HERE, "demo", "FEC_DEMO_2025.txt")
MI_MAI = date(2026, 5, 15)
ANNEE = (date(2026, 1, 1), date(2026, 12, 31))


@pytest.fixture()
def chemin(tmp_path):
    return str(tmp_path / "compta.db")


@pytest.fixture()
def conn(chemin):
    c = init_db.init_demo(chemin, FEC_DEMO, 2026)
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()


def _modele(conn, **kw):
    champs = dict(type="assurance", bien_id=1, montant=18.5,
                  periodicite="mensuelle", jour=31, date_debut="2026-01-31")
    champs.update(kw)
    return recurrentes.creer(conn, **champs)


def _grille(**kw):
    m = dict(date_debut="2026-01-31", periodicite="mensuelle", jour=31,
             date_fin=None, actif=1)
    m.update(kw)
    du = date.fromisoformat(m["date_debut"])
    au = kw.pop("_au", date(du.year + 2, 12, 31))
    return [d for d, motif in recurrentes.grille(m, du, au) if motif is None]


def _apercu(conn, du=ANNEE[0], au=ANNEE[1], auj=MI_MAI):
    return recurrentes.apercu(conn, du, au, aujourd_hui=auj)


def _generer(conn, retenues=None, auj=MI_MAI, du=ANNEE[0], au=ANNEE[1], **kw):
    if retenues is None:
        retenues = {x.cle for x in _apercu(conn, du, au, auj)
                    if x.cochee_par_defaut}
    return recurrentes.generer(conn, du, au, retenues, aujourd_hui=auj, **kw)


def _comptes(conn):
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("operation", "ecriture", "ligne", "echeance_generee",
                      "echeance_operation", "modele_recurrent")}


def _par_date(lignes):
    return {x.echeance.date: x for x in lignes}


# ── Règle 3 : calcul des dates ──────────────────────────────────────────

def test_mensuelle_au_31_depuis_le_31_janvier():
    assert _grille()[:5] == [date(2026, 1, 31), date(2026, 2, 28),
                             date(2026, 3, 31), date(2026, 4, 30),
                             date(2026, 5, 31)]


def test_dernier_jour_du_mois():
    assert _grille(jour=recurrentes.DERNIER_JOUR,
                   date_debut="2026-01-01")[:4] == [
        date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31),
        date(2026, 4, 30)]


def test_fevrier_bissextile_2028():
    d = _grille(date_debut="2028-01-31")
    assert d[1] == date(2028, 2, 29) and d[13] == date(2029, 2, 28)


def test_aucun_glissement_durable_vers_le_28():
    d = _grille(jour=30, date_debut="2026-01-30")
    assert d[1] == date(2026, 2, 28)
    assert all(x.day == 30 for x in d if x.month != 2)
    assert len(d) == 36                       # aucun débordement, aucun manque


def test_trimestrielle_depuis_le_31_janvier():
    assert _grille(periodicite="trimestrielle")[:4] == [
        date(2026, 1, 31), date(2026, 4, 30), date(2026, 7, 31),
        date(2026, 10, 31)]


def test_semestrielle():
    assert _grille(periodicite="semestrielle", jour=15,
                   date_debut="2026-03-15")[:3] == [
        date(2026, 3, 15), date(2026, 9, 15), date(2027, 3, 15)]


def test_annuelle_au_29_fevrier():
    assert _grille(periodicite="annuelle", jour=29, date_debut="2028-02-29",
                   _au=date(2032, 12, 31)) == [
        date(2028, 2, 29), date(2029, 2, 28), date(2030, 2, 28),
        date(2031, 2, 28), date(2032, 2, 29)]


def test_bornes_de_debut_et_de_fin_incluses():
    m = dict(date_debut="2026-01-15", periodicite="mensuelle", jour=15,
             date_fin="2026-04-15", actif=1)
    g = recurrentes.grille(m, date(2026, 1, 1), date(2026, 6, 30))
    assert [(d, motif is None) for d, motif in g] == [
        (date(2026, 1, 15), True), (date(2026, 2, 15), True),
        (date(2026, 3, 15), True), (date(2026, 4, 15), True),
        (date(2026, 5, 15), False), (date(2026, 6, 15), False)]
    assert "après la fin du modèle" in g[4][1]


def test_premier_mois_avant_le_debut_ecarte():
    m = dict(date_debut="2026-01-15", periodicite="mensuelle", jour=10,
             date_fin=None, actif=1)
    g = recurrentes.grille(m, date(2026, 1, 1), date(2026, 2, 28))
    assert g[0][0] == date(2026, 1, 10) and "avant le début" in g[0][1]
    assert g[1] == (date(2026, 2, 10), None)


# ── Règles 1 et 2 : modèle, liste blanche, refus ────────────────────────

def test_liste_blanche_ne_contient_que_des_charges_de_classe_6():
    for k in recurrentes.GABARITS_ADMIS:
        g = gabarits.GABARITS[k]
        assert g["nature"] == "charge" and g["compte"].startswith("6"), k


def test_creation_nominale(conn):
    n = _modele(conn, tiers="  Assureur fictif ", libelle="PNO")
    m = recurrentes.modele(conn, n)
    assert (m["type"], m["montant"], m["jour"], m["tiers"], m["libelle"],
            m["actif"]) == ("assurance", 18.5, 31, "Assureur fictif", "PNO", 1)


def _refus(conn, motif, **kw):
    avant = _comptes(conn)
    with pytest.raises(ValueError, match=motif):
        _modele(conn, **kw)
    assert _comptes(conn) == avant


@pytest.mark.parametrize("type_", ["loyer", "charges_locatives",
                                   "emprunt_capital_rembourse",
                                   "interets_emprunt", "petit_equipement",
                                   "frais_acquisition", "depot_garantie_restitue",
                                   "inconnu"])
def test_refus_gabarit_hors_liste_blanche(conn, type_):
    _refus(conn, "ne peut pas être récurrent", type=type_)


def test_refus_gabarit_personnalise(conn):
    gabarits.ajouter_personnalise(conn, cle="abonnement_x",
                                  libelle="Abonnement fictif",
                                  compte_num="628800", nature="charge")
    _refus(conn, "ne peut pas être récurrent", type="abonnement_x")


@pytest.mark.parametrize("montant", [0, -5, "nan", "abc", 0.001])
def test_refus_montant_nul_negatif_ou_invalide(conn, montant):
    _refus(conn, "Montant|strictement positif", montant=montant)


@pytest.mark.parametrize("jour", [32, -1, "abc"])
def test_refus_jour_invalide(conn, jour):
    _refus(conn, "Jour d'échéance invalide", jour=jour)


def test_jour_dernier_accepte_en_toutes_lettres(conn):
    n = _modele(conn, jour="dernier")
    assert recurrentes.modele(conn, n)["jour"] == recurrentes.DERNIER_JOUR


def test_refus_fin_avant_debut(conn):
    _refus(conn, "précède", date_fin="2026-01-01")


def test_refus_bien_inexistant(conn):
    _refus(conn, "Aucun bien", bien_id=99)


def test_refus_periodicite_inconnue(conn):
    _refus(conn, "Périodicité inconnue", periodicite="hebdomadaire")


def test_refus_libelle_multiligne(conn):
    _refus(conn, "saut de ligne", libelle="a\nb")


def test_refus_date_invalide(conn):
    _refus(conn, "Date de début invalide", date_debut="31/01/2026")


def test_creation_depuis_une_operation(conn):
    r = operations.saisir(conn, type="assurance", montant=21.3,
                          date_operation="2026-03-31", periode="2026-03",
                          tiers="Assureur fictif", libelle="PNO studio")
    n = recurrentes.depuis_operation(conn, r["operation_id"])
    m = recurrentes.modele(conn, n)
    assert (m["type"], m["bien_id"], m["montant"], m["libelle"], m["tiers"],
            m["jour"], m["date_debut"], m["periodicite"]) == (
        "assurance", 1, 21.3, "PNO studio", "Assureur fictif", 31,
        "2026-03-31", "mensuelle")


def test_depuis_une_operation_hors_liste_blanche_refuse(conn):
    r = operations.saisir(conn, type="loyer", montant=800,
                          date_operation="2026-03-05", periode="2026-03")
    with pytest.raises(ValueError, match="ne peut pas être récurrent"):
        recurrentes.depuis_operation(conn, r["operation_id"])


def test_depuis_une_operation_annulee_refuse(conn):
    r = operations.saisir(conn, type="assurance", montant=21.3,
                          date_operation="2026-03-31")
    operations.annuler(conn, r["operation_id"])
    with pytest.raises(ValueError, match="annulée"):
        recurrentes.depuis_operation(conn, r["operation_id"])


# ── Règles 4 à 6 : aperçu ───────────────────────────────────────────────

def test_apercu_n_ecrit_rien(conn):
    _modele(conn)
    avant = _comptes(conn)
    _apercu(conn)
    assert _comptes(conn) == avant and not conn.in_transaction


def test_apercu_echues_a_generer_futures_a_venir(conn):
    _modele(conn)
    lignes = _par_date(_apercu(conn, auj=date(2026, 4, 30)))
    assert lignes[date(2026, 4, 30)].statut == echeancier.A_GENERER  # ≤ aujourd'hui
    assert lignes[date(2026, 5, 31)].statut == echeancier.A_VENIR
    assert lignes[date(2026, 1, 31)].cochee_par_defaut


def test_echeance_d_un_exercice_cloture_ignoree(conn):
    _modele(conn, date_debut="2025-10-31")
    lignes = _par_date(_apercu(conn, du=date(2025, 1, 1)))
    assert lignes[date(2025, 11, 30)].statut == echeancier.IGNOREE
    assert lignes[date(2025, 11, 30)].motif == "exercice 2025 clôturé"


def test_echeance_d_un_exercice_inexistant_ignoree(conn):
    _modele(conn)
    lignes = _par_date(_apercu(conn, au=date(2027, 3, 31),
                               auj=date(2027, 4, 1)))
    assert lignes[date(2027, 1, 31)].motif == "exercice 2027 inexistant"


def test_echeance_posterieure_a_la_cession_ignoree(conn):
    _modele(conn)
    cession.assurer_schema(conn)
    conn.execute("UPDATE bien SET date_cession='2026-03-31' WHERE id=1")
    conn.commit()
    lignes = _par_date(_apercu(conn))
    assert lignes[date(2026, 3, 31)].statut == echeancier.A_GENERER
    assert lignes[date(2026, 4, 30)].statut == echeancier.IGNOREE
    assert "cession du bien" in lignes[date(2026, 4, 30)].motif


def test_modele_suspendu_ignore(conn):
    n = _modele(conn)
    recurrentes.activer(conn, n, False)
    lignes = _apercu(conn)
    assert {x.statut for x in lignes} == {echeancier.IGNOREE}
    assert {x.motif for x in lignes} == {"modèle suspendu"}


def test_date_hors_bornes_du_modele_ignoree(conn):
    _modele(conn, date_fin="2026-02-28")
    lignes = _par_date(_apercu(conn))
    assert lignes[date(2026, 2, 28)].statut == echeancier.A_GENERER
    assert "après la fin du modèle" in lignes[date(2026, 3, 31)].motif


def _exercice_court(tmp_path, debut, fin):
    """Exercice 2026 aux bornes données (aucun écran ne permet encore d'en
    créer : il est inséré directement)."""
    c = init_db.init(str(tmp_path / "court.db"), "blanc", annee_cible=2026)
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("INSERT INTO exploitant VALUES (1,'Exploitant fictif',"
              "'000000000','Adresse fictive')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total,"
              "date_acquisition) VALUES (1,1,'Bien fictif',100000,?)", (debut,))
    c.execute("UPDATE exercice SET date_debut=?, date_fin=? WHERE annee=2026",
              (debut, fin))
    c.commit()
    return c


def test_exercice_court_borne_de_debut(tmp_path):
    c = _exercice_court(tmp_path, "2026-06-15", "2026-12-31")
    try:
        _modele(c)
        lignes = _par_date(_apercu(c, auj=date(2026, 12, 31)))
        assert "hors de l'exercice 2026" in lignes[date(2026, 5, 31)].motif
        assert lignes[date(2026, 6, 30)].statut == echeancier.A_GENERER
        r = _generer(c, auj=date(2026, 12, 31))
        assert r["nb_operations"] == 7                   # juin → décembre
    finally:
        c.close()


def test_exercice_termine_avant_le_31_decembre_borne_de_fin(tmp_path):
    c = _exercice_court(tmp_path, "2026-01-01", "2026-09-30")
    try:
        _modele(c)
        lignes = _par_date(_apercu(c, auj=date(2026, 12, 31)))
        assert lignes[date(2026, 9, 30)].statut == echeancier.A_GENERER
        assert "hors de l'exercice 2026" in lignes[date(2026, 10, 31)].motif
        assert _generer(c, auj=date(2026, 12, 31))["nb_operations"] == 9
    finally:
        c.close()


# ── Règles 7 et 8 : idempotence, atomicité ──────────────────────────────

def test_generation_puis_rejeu_zero_creation(conn):
    _modele(conn)
    r = _generer(conn)
    assert r["nb_operations"] == 4                # janvier → avril
    avant = _comptes(conn)
    r2 = _generer(conn)
    assert r2["nb_operations"] == 0 and _comptes(conn) == avant
    # Même en retenant explicitement des échéances déjà générées.
    tout = {x.cle for x in _apercu(conn)}
    assert _generer(conn, retenues=tout)["nb_operations"] == 0
    assert _comptes(conn) == avant


def test_operations_generees_conformes(conn):
    n = _modele(conn, tiers="Assureur fictif")
    _generer(conn)
    ops = conn.execute(
        "SELECT o.date_operation, o.montant, o.type, o.periode, o.tiers, "
        "o.source, o.bien_id, e.journal_code, e.piece_ref "
        "FROM operation o JOIN ecriture e ON e.id=o.ecriture_id "
        "WHERE o.source='recurrent' ORDER BY o.date_operation").fetchall()
    assert ops[1] == ("2026-02-28", 18.5, "assurance", "2026-02",
                      "Assureur fictif", "recurrent", 1, "BQ",
                      "Relevé bancaire 02")
    liens = conn.execute("SELECT COUNT(*) FROM echeance_generee WHERE "
                         "source='recurrent' AND source_id=?", (n,)).fetchone()
    assert liens[0] == 4


def test_occurrence_annulee_non_regeneree(conn):
    _modele(conn)
    _generer(conn)
    oid = conn.execute("SELECT id FROM operation WHERE source='recurrent' "
                       "AND date_operation='2026-02-28'").fetchone()[0]
    operations.annuler(conn, oid)
    assert _generer(conn)["nb_operations"] == 0
    ligne = _par_date(_apercu(conn))[date(2026, 2, 28)]
    assert ligne.statut == echeancier.DEJA_GENEREE
    assert ligne.operations_liees[0]["annulee"] is True


def test_unicite_garantie_par_la_base(conn):
    _modele(conn)
    _generer(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO echeance_generee (source, source_id, "
                     "date_echeance, etat, genere_le) VALUES "
                     "('recurrent', 1, '2026-01-31', 'generee', 'x')")
    conn.rollback()


def test_apercu_perime_ne_genere_pas_deux_fois(conn):
    """Deux onglets ouverts sur le même aperçu : la seconde confirmation
    ne recrée rien, l'aperçu étant recalculé sous le verrou."""
    _modele(conn)
    retenues = {x.cle for x in _apercu(conn) if x.cochee_par_defaut}
    _generer(conn, retenues=retenues)
    r = _generer(conn, retenues=retenues)
    assert r["nb_operations"] == 0 and len(r["non_generees"]) == 4
    assert "n'étaient plus à générer" in recurrentes.message_generation(r)


def test_exception_au_milieu_du_lot_rien_n_est_cree(conn, monkeypatch):
    _modele(conn)
    avant = _comptes(conn)
    fec_avant = conn.execute("SELECT * FROM ligne ORDER BY id").fetchall()
    original, appels = operations.saisir, []

    def saisir_en_panne(*a, **k):
        appels.append(k["date_operation"])
        if len(appels) == 3:
            raise RuntimeError("panne simulée")
        return original(*a, **k)
    monkeypatch.setattr(operations, "saisir", saisir_en_panne)
    with pytest.raises(echeancier.LotAnnule) as exc:
        _generer(conn)
    assert "31/03/2026" in str(exc.value) and "panne simulée" in str(exc.value)
    assert "aucune opération n'a été créée" in str(exc.value)
    assert _comptes(conn) == avant
    assert conn.execute("SELECT * FROM ligne ORDER BY id").fetchall() == fec_avant
    assert not conn.in_transaction


# ── Règle 9 : indépendance des opérations générées ──────────────────────

def test_modifier_puis_supprimer_un_modele_laisse_les_operations(conn):
    n = _modele(conn)
    _generer(conn)
    ops = conn.execute("SELECT * FROM operation ORDER BY id").fetchall()
    lignes = conn.execute("SELECT * FROM ligne ORDER BY id").fetchall()
    recurrentes.modifier(conn, n, montant=25.0, libelle="Nouveau libellé")
    assert conn.execute("SELECT * FROM operation ORDER BY id").fetchall() == ops
    # Les prochaines échéances suivent le modèle modifié.
    futur = _par_date(_apercu(conn, auj=date(2026, 6, 30)))[date(2026, 5, 31)]
    assert futur.echeance.operations[0]["montant"] == 25.0
    r = recurrentes.supprimer(conn, n)
    assert r["operations_conservees"] == 4
    assert conn.execute("SELECT * FROM operation ORDER BY id").fetchall() == ops
    assert conn.execute("SELECT * FROM ligne ORDER BY id").fetchall() == lignes
    with pytest.raises(ValueError, match="Aucun modèle"):
        recurrentes.modele(conn, n)


def test_modification_refusee_laisse_le_modele_intact(conn):
    n = _modele(conn)
    avant = recurrentes.modele(conn, n)
    with pytest.raises(ValueError):
        recurrentes.modifier(conn, n, montant=-1)
    assert recurrentes.modele(conn, n) == avant


# ── Règle 10 : doublons probables, exclusion ────────────────────────────

def _deuxieme_bien(conn):
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total,"
                 "date_acquisition) VALUES (2,1,'Second bien fictif',90000,"
                 "'2025-01-01')")
    conn.commit()


def test_doublon_importe_signale_meme_sur_un_autre_bien(conn):
    """L'import rattache tout au bien n° 1 : le bien n'est pas comparé pour
    une opération importée."""
    _deuxieme_bien(conn)
    _modele(conn, bien_id=2)
    operations.saisir(conn, type="assurance", montant=18.5,
                      date_operation="2026-03-28", source="import")
    ligne = _par_date(_apercu(conn))[date(2026, 3, 31)]
    assert ligne.statut == echeancier.A_GENERER
    assert [d["date"] for d in ligne.doublons] == ["2026-03-28"]
    assert not ligne.cochee_par_defaut


def test_doublon_meme_compte_via_un_autre_gabarit(conn):
    """Même compte (616110), gabarit différent : c'est le compte qui compte."""
    _modele(conn)
    operations.saisir(conn, type="assurance_gli", montant=18.5,
                      date_operation="2026-04-27")
    assert _par_date(_apercu(conn))[date(2026, 4, 30)].doublons


def test_pas_de_doublon_hors_fenetre_autre_montant_autre_bien(conn):
    _deuxieme_bien(conn)
    _modele(conn, bien_id=2)
    operations.saisir(conn, type="assurance", montant=18.5,
                      date_operation="2026-03-23", source="import")   # 8 jours
    operations.saisir(conn, type="assurance", montant=18.6,
                      date_operation="2026-03-30", source="import")
    operations.saisir(conn, type="assurance", montant=18.5,
                      date_operation="2026-03-30", bien_id=1)  # saisie, bien 1
    assert _par_date(_apercu(conn))[date(2026, 3, 31)].doublons == []


def test_doublon_annule_ignore(conn):
    _modele(conn)
    r = operations.saisir(conn, type="assurance", montant=18.5,
                          date_operation="2026-03-30")
    operations.annuler(conn, r["operation_id"])
    assert _par_date(_apercu(conn))[date(2026, 3, 31)].doublons == []


def test_ligne_exclue_non_generee(conn):
    _modele(conn)
    lignes = _apercu(conn)
    exclue = _par_date(lignes)[date(2026, 2, 28)].cle
    r = _generer(conn, retenues={x.cle for x in lignes
                                 if x.cochee_par_defaut} - {exclue})
    assert r["nb_operations"] == 3
    assert _par_date(_apercu(conn))[date(2026, 2, 28)].statut == \
        echeancier.A_GENERER                      # exclue cette fois seulement


def test_ne_plus_proposer_puis_retablir(conn):
    _modele(conn)
    cle = _par_date(_apercu(conn))[date(2026, 2, 28)].cle
    r = _generer(conn, retenues=set(), ecarter={cle})
    assert r["ecartees"] == [cle] and r["nb_operations"] == 0
    assert _par_date(_apercu(conn))[date(2026, 2, 28)].statut == echeancier.ECARTEE
    assert _generer(conn, retenues={cle})["nb_operations"] == 0
    echeancier.retablir(conn, cle)
    assert _par_date(_apercu(conn))[date(2026, 2, 28)].statut == \
        echeancier.A_GENERER
    with pytest.raises(ValueError, match="pas écartée"):
        echeancier.retablir(conn, cle)


# ── Moteur générique : plusieurs opérations par échéance ────────────────

def _source_fictive(jours, **kw):
    """Ce que fera la fonction emprunts : une échéance, deux opérations."""
    return [echeancier.Echeance(
        source="essai", source_id=7, date=d, bien_id=1, libelle="Échéance",
        operations=[{"type": "assurance_emprunteur", "montant": 12.0},
                    {"type": "frais_bancaires", "montant": kw.get("frais", 3.0)}])
        for d in jours]


def test_moteur_deux_operations_par_echeance_idempotent(conn):
    ech = _source_fictive([date(2026, 1, 5), date(2026, 2, 5)])
    tout = {e.cle for e in ech}
    r = echeancier.generer(conn, ech, tout, aujourd_hui=MI_MAI)
    assert r["nb_operations"] == 4
    assert conn.execute("SELECT COUNT(*) FROM echeance_operation"
                        ).fetchone()[0] == 4
    avant = _comptes(conn)
    assert echeancier.generer(conn, ech, tout,
                              aujourd_hui=MI_MAI)["nb_operations"] == 0
    assert _comptes(conn) == avant


def test_moteur_echec_sur_la_seconde_operation_annule_tout(conn):
    ech = _source_fictive([date(2026, 1, 5), date(2026, 2, 5)], frais=-1)
    avant = _comptes(conn)
    with pytest.raises(echeancier.LotAnnule, match="05/01/2026"):
        echeancier.generer(conn, ech, {e.cle for e in ech},
                           aujourd_hui=MI_MAI)
    assert _comptes(conn) == avant


def test_moteur_alertes_de_la_source_transmises(conn):
    ech = _source_fictive([date(2026, 1, 5)])
    ech[0].alertes.append("Mise en garde de la source")
    assert echeancier.apercu(conn, ech, aujourd_hui=MI_MAI)[0].echeance.alertes


# ── FEC, pérennité, migration ───────────────────────────────────────────

def test_fec_apres_generation_accepte_par_le_validateur(conn, tmp_path):
    _modele(conn)
    _modele(conn, type="charge_copro", montant=240, periodicite="trimestrielle")
    _generer(conn)
    fec = export_fec.exporter(conn, 2026, str(tmp_path / "fec.txt"))
    assert valider_fec.valider(fec) == []


def test_survie_a_une_sauvegarde_puis_restauration(chemin, conn):
    n = _modele(conn)
    _generer(conn)
    etat = (conn.execute("SELECT * FROM modele_recurrent").fetchall(),
            conn.execute("SELECT * FROM echeance_generee").fetchall(),
            conn.execute("SELECT * FROM echeance_operation").fetchall())
    conn.close()
    sauvegarde = perennite.sauvegarder(chemin, "manuel")
    c = sqlite3.connect(chemin)
    c.execute("PRAGMA foreign_keys = ON")
    recurrentes.supprimer(c, n)
    c.close()
    perennite.restaurer(chemin, sauvegarde)
    c = sqlite3.connect(chemin)
    try:
        assert (c.execute("SELECT * FROM modele_recurrent").fetchall(),
                c.execute("SELECT * FROM echeance_generee").fetchall(),
                c.execute("SELECT * FROM echeance_operation").fetchall()) == etat
    finally:
        c.close()


def test_migration_base_neuve(tmp_path):
    c = init_db.init(str(tmp_path / "neuve.db"), "blanc", annee_cible=2026)
    try:
        # Au moins le schéma 10 (les charges récurrentes) : les paliers
        # suivants s'ajoutent sans retirer ces tables.
        assert init_db.version_base(c) == init_db.VERSION_SCHEMA >= 10
        for t in ("modele_recurrent", "echeance_generee", "echeance_operation"):
            assert c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
    finally:
        c.close()


def _contenu(chemin, exclues):
    c = sqlite3.connect(chemin)
    try:
        tables = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            if r[0] not in exclues]
        return {t: c.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
                for t in tables}
    finally:
        c.close()


def test_migration_depuis_la_version_precedente_du_dossier_de_demo(tmp_path):
    chemin = str(tmp_path / "compta.db")
    init_db.init_demo(chemin, FEC_DEMO, 2026).close()
    nouvelles = {"modele_recurrent", "echeance_generee", "echeance_operation",
                 # paliers postérieurs au 10, appliqués par la même migration
                 "emprunt", "emprunt_ligne"}
    c = sqlite3.connect(chemin)
    for t in ("echeance_operation", "echeance_generee", "modele_recurrent",
              "emprunt_ligne", "emprunt"):
        c.execute(f"DROP TABLE {t}")
    c.execute("UPDATE meta SET valeur='9' WHERE cle='version_schema'")
    c.commit()
    c.close()
    avant = _contenu(chemin, nouvelles | {"meta"})

    r = migrations.migrer(chemin)
    assert (r["avant"], r["apres"]) == (9, init_db.VERSION_SCHEMA)
    assert r["sauvegarde"] and os.path.exists(r["sauvegarde"])
    assert _contenu(chemin, nouvelles | {"meta"}) == avant
    c = sqlite3.connect(chemin)
    try:
        for t in nouvelles:
            assert c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
    finally:
        c.close()
    assert migrations.migrer(chemin)["sauvegarde"] is None


# ── Interface web ───────────────────────────────────────────────────────

def _client(tmp_path, monkeypatch, principal, bac=None):
    monkeypatch.setenv("COMPTA_DB", principal)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", bac or str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    monkeypatch.setattr(echeancier, "_aujourd_hui", lambda: MI_MAI)
    return app_mod.app.test_client(), app_mod


@pytest.fixture()
def web(tmp_path, monkeypatch):
    principal = str(tmp_path / "compta.db")
    init_db.init_demo(principal, FEC_DEMO, 2026).close()
    client, app_mod = _client(tmp_path, monkeypatch, principal)
    yield client, principal
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def _db(chemin):
    c = sqlite3.connect(chemin)
    c.execute("PRAGMA foreign_keys = ON")
    return c


def _form_modele(**kw):
    d = {"annee": "2026", "type": "assurance", "bien_id": "1",
         "montant": "18.50", "periodicite": "mensuelle", "jour": "31",
         "date_debut": "2026-01-31", "date_fin": "", "libelle": "",
         "tiers": ""}
    d.update(kw)
    return d


def test_web_creer_modele_puis_page(web):
    client, principal = web
    r = client.post("/recurrentes/modele", data=_form_modele())
    assert "ok=" in r.headers["Location"]
    page = client.get("/recurrentes?annee=2026").get_data(as_text=True)
    assert "Assurance habitation PNO" in page
    assert page.count('name="retenir"') == 4           # janvier → avril
    assert "data-confirmer=\"Générer les opérations" in page
    assert "data-confirmer=\"Supprimer ce modèle" in page
    import html
    assert "régularisation de fin d'année" in html.unescape(page)  # aide TF/CFE


def test_web_refus_avec_message(web):
    client, principal = web
    r = client.post("/recurrentes/modele", data=_form_modele(type="loyer"))
    assert "err=" in r.headers["Location"]
    c = _db(principal)
    assert c.execute("SELECT COUNT(*) FROM modele_recurrent").fetchone()[0] == 0
    c.close()


def test_web_generer_puis_rejeu(web):
    client, principal = web
    client.post("/recurrentes/modele", data=_form_modele())
    c = _db(principal)
    cles = [x.cle for x in _apercu(c)]
    c.close()
    data = {"annee": "2026", "du": "2026-01-01", "au": "2026-12-31",
            "retenir": cles[:2]}
    r = client.post("/recurrentes/generer", data=data)
    assert "ok=" in r.headers["Location"]
    client.post("/recurrentes/generer", data=data)
    c = _db(principal)
    assert c.execute("SELECT COUNT(*) FROM operation WHERE source='recurrent'"
                     ).fetchone()[0] == 2
    c.close()


def test_web_modifier_suspendre_supprimer(web):
    client, principal = web
    client.post("/recurrentes/modele", data=_form_modele())
    client.post("/recurrentes/modele", data=_form_modele(id="1", montant="20"))
    client.post("/recurrentes/1/etat", data={"annee": "2026", "actif": "0"})
    c = _db(principal)
    assert c.execute("SELECT montant, actif FROM modele_recurrent").fetchone() \
        == (20.0, 0)
    c.close()
    r = client.post("/recurrentes/1/supprimer", data={"annee": "2026"})
    assert "ok=" in r.headers["Location"]
    c = _db(principal)
    assert c.execute("SELECT COUNT(*) FROM modele_recurrent").fetchone()[0] == 0
    c.close()


def test_web_depuis_operation_et_bouton_de_la_saisie(web):
    client, principal = web
    c = _db(principal)
    r = operations.saisir(c, type="assurance", montant=21.3,
                          date_operation="2026-03-31")
    loyer = operations.saisir(c, type="loyer", montant=800,
                              date_operation="2026-03-05")
    c.close()
    page = client.get("/saisie?annee=2026").get_data(as_text=True)
    assert f'/recurrentes/depuis-operation/{r["operation_id"]}' in page
    assert f'/recurrentes/depuis-operation/{loyer["operation_id"]}' not in page
    assert "Charges récurrentes" in page
    rep = client.post(f"/recurrentes/depuis-operation/{r['operation_id']}",
                      data={"annee": "2026"})
    assert "modele=1" in rep.headers["Location"]


def test_web_ecarter_puis_retablir(web):
    client, principal = web
    client.post("/recurrentes/modele", data=_form_modele())
    cle = "recurrent:1:2026-02-28"
    client.post("/recurrentes/generer", data={
        "annee": "2026", "du": "2026-01-01", "au": "2026-12-31",
        "ecarter": [cle]})
    page = client.get("/recurrentes?annee=2026").get_data(as_text=True)
    assert "écartée" in page and "Rétablir" in page
    r = client.post("/recurrentes/retablir", data={"annee": "2026", "cle": cle})
    assert "ok=" in r.headers["Location"]


def test_web_origine_etrangere_refusee(web):
    client, principal = web
    r = client.post("/recurrentes/modele", data=_form_modele(),
                    headers={"Origin": "https://exemple.invalid"})
    assert r.status_code == 403
    c = _db(principal)
    assert c.execute("SELECT COUNT(*) FROM modele_recurrent").fetchone()[0] == 0
    c.close()


def test_cloisonnement_du_bac_a_sable(tmp_path, monkeypatch):
    principal, bac = str(tmp_path / "compta.db"), str(tmp_path / "bac.db")
    init_db.init_demo(principal, FEC_DEMO, 2026).close()
    shutil.copy(principal, bac)
    client, _ = _client(tmp_path, monkeypatch, principal, bac)
    client.set_cookie("dossier", "bac_a_sable")
    client.post("/recurrentes/modele", data=_form_modele())
    client.post("/recurrentes/generer", data={
        "annee": "2026", "du": "2026-01-01", "au": "2026-12-31",
        "retenir": ["recurrent:1:2026-01-31"]})
    for chemin_db, attendu in ((bac, 1), (principal, 0)):
        c = sqlite3.connect(chemin_db)
        assert c.execute("SELECT COUNT(*) FROM modele_recurrent"
                         ).fetchone()[0] == attendu, chemin_db
        assert c.execute("SELECT COUNT(*) FROM operation WHERE "
                         "source='recurrent'").fetchone()[0] == attendu
        c.close()


# ── Ligne de commande ───────────────────────────────────────────────────

def _cli(monkeypatch, chemin, *args):
    import cli
    monkeypatch.setattr(cli, "DB", chemin)
    monkeypatch.setattr(echeancier, "_aujourd_hui", lambda: MI_MAI)
    monkeypatch.setattr(sys, "argv", ["cli.py", *args])
    cli.main()


def test_cli_cycle_complet(chemin, monkeypatch, capsys):
    init_db.init_demo(chemin, FEC_DEMO, 2026).close()
    _cli(monkeypatch, chemin, "recurrent", "ajouter", "--type", "taxe_fonciere",
         "--bien", "1", "--montant", "80", "--periodicite", "mensuelle",
         "--jour", "15", "--debut", "2026-01-15")
    sortie = capsys.readouterr().out
    assert f"Dossier : {chemin}" in sortie and "Modèle n° 1 créé" in sortie
    assert "régularisation de fin d'année" in sortie
    _cli(monkeypatch, chemin, "recurrent", "lister")
    assert "80.00 € mensuelle" in capsys.readouterr().out
    _cli(monkeypatch, chemin, "recurrent", "apercu")
    assert "recurrent:1:2026-05-15" in capsys.readouterr().out
    _cli(monkeypatch, chemin, "recurrent", "generer", "--oui",
         "--exclure", "recurrent:1:2026-02-15")
    assert "4 opération(s) générée(s)" in capsys.readouterr().out
    _cli(monkeypatch, chemin, "recurrent", "suspendre", "--id", "1")
    _cli(monkeypatch, chemin, "recurrent", "supprimer", "--id", "1", "--oui")
    assert "4 opération(s) déjà générée(s) conservée(s)" in capsys.readouterr().out


def test_cli_refus_code_de_retour(chemin, monkeypatch):
    init_db.init_demo(chemin, FEC_DEMO, 2026).close()
    with pytest.raises(SystemExit) as exc:
        _cli(monkeypatch, chemin, "recurrent", "ajouter", "--type", "loyer",
             "--bien", "1", "--montant", "800", "--periodicite", "mensuelle",
             "--jour", "5", "--debut", "2026-01-05")
    assert "ne peut pas être récurrent" in str(exc.value.code)


def test_cli_generer_sans_confirmation_abandonne(chemin, monkeypatch, capsys):
    c = init_db.init_demo(chemin, FEC_DEMO, 2026)
    _modele(c)
    c.close()
    monkeypatch.setattr("builtins.input", lambda _: "n")
    _cli(monkeypatch, chemin, "recurrent", "generer")
    assert "rien n'a été généré" in capsys.readouterr().out
    c = sqlite3.connect(chemin)
    assert c.execute("SELECT COUNT(*) FROM operation WHERE source='recurrent'"
                     ).fetchone()[0] == 0
    c.close()
