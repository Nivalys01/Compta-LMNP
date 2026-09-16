# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Non-régression des constats de la passe N (règles versionnées et veille).

Le logiciel applique les règles fiscales « telles qu'elles sont
enregistrées ». C'est un choix juste — une loi de finances par an peut
changer un seuil — mais il déplace la question : **que vaut une règle
enregistrée ?**

Les constats de cette passe répondent tous à cette question. Une durée de
report saisie à zéro faisait périmer un déficit l'année de sa naissance.
Une règle perdue revenait à sa valeur livrée sans qu'on puisse distinguer
ce retour d'une première installation. Un seuil devenu illisible faisait
proposer en charge ce que la règle disponible excluait. Et deux
consommateurs de la même règle — le contrôle métier et le pense-bête — ne
lisaient pas la même valeur.

Le principe retenu : **une règle a un domaine, une période, et une
histoire ; quand l'une des trois manque, il faut le dire plutôt que de
se rabattre en silence sur la valeur la plus commode.**

Aucune donnée réelle : exploitant fictif, bases blanches, règles fictives.

Lancer :  pytest -q tests/test_passe_n.py
"""
import datetime
import os
import sqlite3
import tempfile

import pytest

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import controles
import fiscal
import gabarits
import import_bancaire
import init_db
import operations
import parametres
import pense_bete
import veille_fiscale


@pytest.fixture
def base(tmp_path):
    conn = init_db.init_blanc(str(tmp_path / "fictif.db"), 2026)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Exploitant fictif','000000000','Adresse fictive')")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) "
                 "VALUES (1,1,'Bien fictif',12000)")
    conn.commit()
    yield conn
    conn.close()


def versions(conn, cle="seuil_immobilisation"):
    return conn.execute(
        "SELECT valeur, date_debut, date_fin FROM regle_fiscale WHERE cle=? "
        "ORDER BY date_debut", (cle,)).fetchall()


def codes(conn, annee=2026):
    return {a.code for a in controles.controler(conn, annee)}


# ═══ N-01 — une seule période ouverte à la fois ═══════════════════════

def test_n01_une_insertion_retroactive_ferme_sa_propre_periode(base):
    """Seule la clôture de la version PRÉCÉDENTE était faite. Saisir une
    règle rétroactive laissait donc deux périodes ouvertes en même temps,
    et l'historique se contredisait. Le tri par date décroissante sauvait
    le calcul — mais un historique contradictoire ne justifie rien devant
    un vérificateur, et il suffisait de clore la version la plus récente
    pour voir l'ancienne ressurgir."""
    parametres.definir(base, "seuil_immobilisation", 1000.0, "2026-07-01")
    parametres.definir(base, "seuil_immobilisation", 700.0, "2025-01-01")
    lignes = versions(base)
    assert lignes == [(500.0, "2000-01-01", "2024-12-31"),
                      (700.0, "2025-01-01", "2026-06-30"),
                      (1000.0, "2026-07-01", None)]
    assert sum(1 for _v, _d, fin in lignes if fin is None) == 1


def test_n01_les_valeurs_lues_restent_celles_du_millesime(base):
    parametres.definir(base, "seuil_immobilisation", 1000.0, "2026-07-01")
    parametres.definir(base, "seuil_immobilisation", 700.0, "2025-01-01")
    lire = lambda a: parametres.valeur(base, "seuil_immobilisation", a,  # noqa: E731
                                       defaut=500.0)
    assert lire(2024) == 500.0
    assert lire(2025) == 700.0
    assert lire(2027) == 1000.0


# ═══ N-02 — une règle a un domaine ═══════════════════════════════════

@pytest.mark.parametrize("cle,valeur", [
    ("seuil_immobilisation", -1),
    ("seuil_immobilisation", 0),
    ("seuil_immobilisation", 10_000_000),
    ("duree_report_deficit_lmnp", 0),
    ("duree_report_deficit_lmnp", 2.5),
    ("retraitement_alur_auto", 5),
    ("seuil_lmp_recettes", -100),
])
def test_n02_les_valeurs_hors_domaine_sont_refusees(base, cle, valeur):
    """Une durée de report à ZÉRO faisait expirer un déficit l'année même
    de sa naissance : 1 200 € purgés par le moteur, et un bénéfice de
    1 200 € laissé sans son imputation. Le caractère versionnable d'une
    règle ne dispense pas de valider son domaine."""
    with pytest.raises(ValueError):
        parametres.definir(base, cle, valeur, "2026-01-01")


@pytest.mark.parametrize("cle,valeur", [
    ("seuil_immobilisation", 1000.0),
    ("duree_report_deficit_lmnp", 6),
    ("retraitement_alur_auto", 0),
    ("seuil_lmp_recettes", 25000.0),
])
def test_n02_les_valeurs_plausibles_restent_admises(base, cle, valeur):
    """Contre-épreuve : le domaine borne l'absurde, pas le législateur."""
    parametres.definir(base, cle, valeur, "2026-01-01")
    assert parametres.valeur(base, cle, 2026) == float(valeur)


def test_n02_un_deficit_reste_imputable_l_annee_suivante(base):
    """Ce que la durée nulle détruisait, vérifié de bout en bout."""
    fiscal.traiter_deficit(base, 2026, -1200.0)
    assert base.execute("SELECT COALESCE(SUM(solde),0) FROM deficit_lmnp"
                        ).fetchone()[0] == 1200.0
    base.execute("INSERT INTO exercice(annee,date_debut,date_fin,statut) "
                 "VALUES (2027,'2027-01-01','2027-12-31','ouvert')")
    base.commit()
    r = fiscal.traiter_deficit(base, 2027, 1200.0)
    assert r["impute_sur_benefice"] == 1200.0


# ═══ N-03 — deux lecteurs d'une règle disent la même chose ═══════════

def test_n03_le_pense_bete_lit_le_seuil_lmp_versionne(base):
    """La constante 23 000 écrite dans le pense-bête ignorait la valeur
    enregistrée : le rappel restait muet sur 20 000 € de recettes face à un
    seuil configuré à 15 000 €, alors que le contrôle métier, lui,
    signalait le franchissement."""
    parametres.definir(base, "seuil_lmp_recettes", 15000.0, "2026-01-01")
    for mois in range(1, 13):
        operations.saisir(base, type="loyer", montant=20000 / 12, bien_id=1,
                          date_operation=f"2026-{mois:02d}-10",
                          periode=f"2026-{mois:02d}")
    assert "SEUIL_LMP" in codes(base)                  # le contrôle métier
    rappels = pense_bete.rappels(base, datetime.date(2026, 9, 15))
    assert any("LMP" in r.get("titre", "") for r in rappels)


def test_n03_sous_le_seuil_aucun_des_deux_ne_previent(base):
    parametres.definir(base, "seuil_lmp_recettes", 30000.0, "2026-01-01")
    for mois in range(1, 13):
        operations.saisir(base, type="loyer", montant=20000 / 12, bien_id=1,
                          date_operation=f"2026-{mois:02d}-10",
                          periode=f"2026-{mois:02d}")
    assert "SEUIL_LMP" not in codes(base)
    rappels = pense_bete.rappels(base, datetime.date(2026, 9, 15))
    assert not any("LMP" in r.get("titre", "") for r in rappels)


# ═══ N-04 — une création de gabarit ne valide pas la transaction ═════

def test_n04_ajouter_un_gabarit_respecte_le_rollback(base):
    """Le `commit()` inconditionnel validait au passage tout ce que
    l'appelant avait écrit sans le vouloir : un loyer de 800 € saisi en
    `commit=False` survivait au rollback qui suivait, parce qu'un gabarit
    avait été créé entre-temps sur la même connexion."""
    operations.saisir(base, type="loyer", montant=800, bien_id=1,
                      date_operation="2026-03-10", periode="2026-03",
                      commit=False)
    gabarits.ajouter_personnalise(base, cle="fictif", libelle="Fictif",
                                  compte_num="606320", nature="charge")
    assert base.in_transaction
    base.rollback()
    assert base.execute("SELECT COUNT(*) FROM operation").fetchone()[0] == 0


def test_n04_hors_transaction_le_gabarit_est_bien_enregistre(base):
    """Contre-épreuve : l'appel autonome continue de persister."""
    gabarits.ajouter_personnalise(base, cle="fictif", libelle="Fictif",
                                  compte_num="606320", nature="charge")
    assert "fictif" in gabarits.tous(base)


# ═══ N-05 — une configuration perdue n'est pas une initialisation ════

def test_n05_une_regle_recreee_apres_perte_est_signalee(base):
    """Le logiciel ressème ses règles dès qu'une clé manque : bon
    comportement à la première ouverture, mauvais après une perte. Un seuil
    abaissé à 300 € revenait à 500 €, et l'avertissement sur une dépense de
    400 € disparaissait avec lui, sans que rien ne distingue cette perte
    d'une initialisation normale."""
    parametres.definir(base, "seuil_immobilisation", 300.0, "2026-01-01")
    base.execute("DELETE FROM regle_fiscale")
    base.commit()
    parametres.valeur(base, "seuil_immobilisation", 2026, defaut=500.0)
    assert parametres.regles_retablies(base)
    assert "REGLE_RETABLIE" in codes(base)


def test_n05_une_premiere_initialisation_ne_signale_rien(base):
    """Contre-épreuve indispensable : tout dossier neuf passe par là."""
    assert parametres.regles_retablies(base) == []
    assert "REGLE_RETABLIE" not in codes(base)


# ═══ N-06 — une veille se constate, elle ne se planifie pas ══════════

def test_n06_une_date_de_veille_future_est_refusee(base):
    """Une date de 2099 enregistrée par erreur éteignait le rappel pour des
    décennies, sans que rien ne signale l'incohérence."""
    with pytest.raises(ValueError, match="futur"):
        veille_fiscale.enregistrer_veille(base, "2099-01-01")


def test_n06_une_date_future_deja_en_base_ne_vaut_pas_veille(base):
    """L'écart en jours devient négatif, et le test « plus de 334 jours »
    concluait tranquillement que tout allait bien."""
    veille_fiscale._table_meta(base)
    base.execute("INSERT OR REPLACE INTO meta(cle,valeur) "
                 "VALUES('derniere_veille','2099-01-01')")
    base.commit()
    assert veille_fiscale.veille_a_refaire(base, datetime.date(2029, 9, 15))


def test_n06_une_consultation_en_panne_est_annoncee(base, monkeypatch):
    """Le rappel était simplement abandonné : une consultation de veille en
    panne produisait la même sortie qu'une veille à jour."""
    def panne(*a, **k):
        raise sqlite3.OperationalError("panne fictive")

    monkeypatch.setattr(veille_fiscale, "veille_a_refaire", panne)
    rappels = pense_bete.rappels(base, datetime.date(2026, 9, 15))
    assert any("état inconnu" in r.get("titre", "") for r in rappels)


def test_n06_une_veille_recente_n_alerte_pas(base):
    veille_fiscale.enregistrer_veille(base, "2026-09-01")
    assert not veille_fiscale.veille_a_refaire(base,
                                               datetime.date(2026, 9, 15))


# ═══ N-07 — un garde-fou qui ne peut pas travailler ne laisse pas passer ═

def _interdire_regles(conn):
    def autoriseur(action, a1, a2, a3, a4):
        return (sqlite3.SQLITE_DENY if a1 == "regle_fiscale"
                else sqlite3.SQLITE_OK)
    conn.set_authorizer(autoriseur)


def test_n07_un_seuil_illisible_envoie_la_ligne_en_attente(base):
    """Une règle abaissée à 300 € et devenue illisible laissait proposer en
    charge un achat de 400 € que la règle disponible excluait, sans que la
    proposition dise un mot de son ignorance. Un repli silencieux vers la
    valeur la plus permissive est la pire réponse possible."""
    parametres.definir(base, "seuil_immobilisation", 300.0, "2026-01-01")
    assert import_bancaire.categoriser("mobilier fictif", -400.0, base,
                                       2026) == "attente_decaissement"
    _interdire_regles(base)
    try:
        assert import_bancaire.categoriser("mobilier fictif", -400.0, base,
                                           2026) == "attente_decaissement"
    finally:
        base.set_authorizer(None)


def test_n07_sous_le_seuil_la_proposition_reste_une_charge(base):
    """Contre-épreuve : l'import ne doit pas envoyer tout en attente."""
    assert import_bancaire.categoriser("mobilier fictif", -100.0, base,
                                       2026) == "petit_equipement"


# ═══ N-08 — chaque règle livrée est couverte par la veille ═══════════

def test_n08_toutes_les_regles_livrees_sont_au_corpus():
    """La revue guidée ne demandait pas de vérifier le traitement des fonds
    ALUR, alors qu'il réintègre des charges à la clôture ET majore le
    plafond d'amortissement déductible."""
    couvertes = {x[3] for x in veille_fiscale.CORPUS if x[3]}
    assert set(parametres.LIBELLES) <= couvertes


def test_n08_le_prompt_mentionne_l_alur():
    prompt = veille_fiscale.prompt_veille(2029)
    assert "ALUR" in prompt


# ═══ Ce qui tenait doit continuer de tenir ═════════════════════════

def test_les_valeurs_livrees_restent_celles_du_logiciel(base):
    assert parametres.valeur(base, "seuil_immobilisation", 2026) == 500.0
    assert parametres.valeur(base, "duree_report_deficit_lmnp", 2026) == 10
    assert parametres.valeur(base, "seuil_lmp_recettes", 2026) == 23000.0
    assert parametres.valeur(base, "retraitement_alur_auto", 2026) == 1


def test_un_millesime_non_couvert_retombe_sur_le_defaut(base):
    """Comportement documenté, conservé : une clé qui ne couvre pas
    l'exercice rend le défaut de l'appelant."""
    assert parametres.valeur(base, "cle_inexistante_fictive", 2026,
                             defaut=42.0) == 42.0


def test_dossier_temporaire_nettoye():
    """Garde-fou de la suite elle-même : ces tests n'écrivent que dans le
    tmp_path de pytest, jamais à côté des fichiers du projet."""
    assert not os.path.exists(os.path.join(tempfile.gettempdir(), "fictif.db"))
