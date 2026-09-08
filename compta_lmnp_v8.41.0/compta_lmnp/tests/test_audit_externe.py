# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Audit externe — points corrigés ET points réfutés, figés en non-régression.

CORRIGÉS (l'auditeur avait raison) :
  1. prorata temporis au MOIS → en JOURS RÉELS (verrouillé par les tests
     de conformité à la liasse réelle, cf. tests/test_or_liasses_reelles.py) ;
  2. aucun index en base → 5 index (contrôles 31× plus rapides) ;
  3. registre dossiers.json réécrit en place → écriture atomique ;
  4. compte alphanumérique dans un FEC importé → plantage brut sur int().

RÉFUTÉS (vérification faite, le code était déjà correct) :
  5. « inserer() peut annuler la transaction de l'appelant » : le rollback
     de rejeu est gardé par debutee_ici — il n'a lieu que si c'est NOUS qui
     avons ouvert la transaction ;
  6. « la complétude des loyers rate un mois manquant s'il y a un doublon
     ailleurs » : le contrôle compare les ENSEMBLES de mois, un mois absent
     est toujours détecté.

Lancer :  pytest -q tests/test_audit_externe.py
"""
import json
import os
import sqlite3
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import controles
import dossiers as dossiers_mod
import ecritures
import fiscal
import init_db
import migrations
import operations
import rejeu_fec

FEC2025 = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init_demo(str(tmp_path / "a.db"), FEC2025, 2026)
    yield c
    c.close()


# === 2. Index de performance ==============================================

def test_index_crees_a_l_initialisation(conn):
    noms = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    for attendu in ("idx_ecriture_exercice", "idx_ligne_ecriture",
                    "idx_operation_exercice_type"):
        assert attendu in noms


def test_migration_ajoute_les_index_aux_bases_existantes(tmp_path):
    db = str(tmp_path / "vieille.db")
    c = init_db.init_demo(db, FEC2025, 2026)
    for n in ("idx_ecriture_exercice", "idx_ligne_ecriture",
              "idx_ligne_compte", "idx_operation_exercice_type",
              "idx_plan_amort_exercice"):
        c.execute(f"DROP INDEX IF EXISTS {n}")
    c.execute("DROP TABLE IF EXISTS meta")        # base d'avant le suivi de version
    c.commit()
    c.close()
    migrations.migrer(db)
    c = sqlite3.connect(db)
    noms = {r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    c.close()
    assert "idx_ecriture_exercice" in noms


# === 3. Registre atomique =================================================

def test_registre_ecrit_atomiquement(tmp_path):
    racine = str(tmp_path)
    dossiers_mod.creer(racine, "Deuxième dossier", 2026)
    registre = os.path.join(racine, "dossiers.json")
    assert json.load(open(registre, encoding="utf-8"))["dossiers"]
    # aucun fichier temporaire ne subsiste
    assert not os.path.exists(registre + ".tmp")


def test_registre_tronque_ne_perd_pas_le_dossier_principal(tmp_path):
    """Un registre corrompu (coupure d'une ancienne version) ne doit pas
    empêcher l'accès au dossier principal."""
    racine = str(tmp_path)
    open(os.path.join(racine, "dossiers.json"), "w").write('{"doss')
    liste = dossiers_mod.lister(racine, os.path.join(racine, "compta.db"))
    assert any(e["slug"] == dossiers_mod.PRINCIPAL for e in liste)


# === 4. Compte alphanumérique dans un FEC importé =========================

def test_compte_alphanumerique_refus_explicite(tmp_path, conn):
    fec = tmp_path / "bizarre.txt"
    import valider_fec
    entete = "\t".join(valider_fec.COLONNES)
    ligne = ["BQ", "Banque", "1", "20260301", "CLIENTS", "Clients divers",
             "", "", "P1", "20260301", "test", "100,00", "", "", "",
             "20260301", "", ""]
    ligne2 = list(ligne)
    ligne2[4], ligne2[11], ligne2[12] = "708810", "", "100,00"
    fec.write_text(entete + "\n" + "\t".join(ligne) + "\n"
                   + "\t".join(ligne2) + "\n", encoding="utf-8")
    conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, statut) "
                 "VALUES (2027,'2027-01-01','2027-12-31','ouvert')")
    conn.commit()
    with pytest.raises(ValueError, match="non numérique"):
        rejeu_fec.rejouer(conn, str(fec), 2026)


# === 5. RÉFUTÉ : inserer() n'annule pas la transaction de l'appelant ======

def test_inserer_ne_touche_pas_a_la_transaction_de_l_appelant(conn):
    """L'audit craignait qu'un rollback interne détruise le travail non
    validé de l'appelant. Le rollback est gardé : il n'a lieu que si
    inserer() a lui-même ouvert la transaction."""
    conn.execute("BEGIN")
    conn.execute("INSERT INTO compte (numero, libelle, type, classe) "
                 "VALUES ('999111','Compte témoin appelant','charge',6)")
    ecritures.inserer(conn, journal="OD", annee=2026, date="2026-05-05",
                      libelle="dans la transaction de l'appelant",
                      commit=False,
                      lignes=[("108000", 10, 0), ("708810", 0, 10)])
    # le travail de l'appelant est toujours là, la transaction toujours ouverte
    assert conn.in_transaction
    assert conn.execute("SELECT 1 FROM compte WHERE numero='999111'").fetchone()
    conn.commit()
    assert conn.execute("SELECT 1 FROM compte WHERE numero='999111'").fetchone()


# === 6. RÉFUTÉ : la complétude détecte bien un mois manquant ==============

def test_completude_detecte_mois_manquant_malgre_un_doublon(conn):
    """Deux loyers en mars, aucun en janvier : le mois manquant DOIT être
    signalé (le contrôle compare des ensembles de mois, pas un volume)."""
    for periode, jour in (("2026-03", "2026-03-05"), ("2026-03", "2026-03-25")):
        operations.saisir(conn, type="loyer", montant=795,
                          date_operation=jour, periode=periode, bien_id=1)
    for mois in range(2, 13):
        operations.saisir(conn, type="loyer", montant=795,
                          date_operation=f"2026-{mois:02d}-05",
                          periode=f"2026-{mois:02d}", bien_id=1)
    anomalies = controles.c_completude_loyers(conn, 2026)
    assert anomalies, "un janvier manquant doit être signalé"
    assert "2026-01" in anomalies[0].message


# === Second audit externe (v8.1.0) ========================================

def test_plus_aucun_alias_ouvrir_exercice():
    """L'alias _ouvrir_exercice dans audit_cycle (outillage) a été supprimé :
    l'ouverture d'exercice est une fonction de PRODUCTION, appelée
    directement depuis reprise."""
    import pathlib
    racine = pathlib.Path(HERE)
    fichiers = list(racine.glob("*.py")) + list((racine / "tests").glob("*.py"))
    coupables = [f.name for f in fichiers
                 if "_ouvrir_exercice" in f.read_text(encoding="utf-8")
                 and f.name != "test_audit_externe.py"]
    assert coupables == [], f"alias encore référencé dans {coupables}"


def test_montant_negatif_devient_une_observation(tmp_path):
    """Ni rejet (le format ne l'interdit pas, des FEC réels en contiennent),
    ni silence : une observation NON bloquante, comme le gradue l'outil
    DGFiP lui-même."""
    import valider_fec
    entete = "\t".join(valider_fec.COLONNES)

    def ligne(compte, debit, credit):
        return "\t".join(["AN", "A nouveaux", "1", "20260101", compte,
                          "Libellé", "", "", "NA", "20260101", "report",
                          debit, credit, "", "", "20260101", "", ""])

    fec = tmp_path / "negatifs.txt"
    fec.write_text(entete + "\n" + ligne("108000", "", "-100,00") + "\n"
                   + ligne("472000", "", "-100,00") + "\n"
                   + ligne("512000", "-200,00", "") + "\n", encoding="utf-8")
    rapport = valider_fec.valider(str(fec), comme_dict=True)
    assert rapport["erreurs"] == []                     # NON bloquant
    assert any("négatif" in o for o in rapport["observations"])
    assert valider_fec.observations(str(fec))           # accès direct


def test_fec_produit_par_le_logiciel_sans_negatif_ni_observation(tmp_path):
    """Notre propre export ne peut PAS contenir de négatif : la base les
    interdit (CHECK debit >= 0 AND credit >= 0)."""
    import export_fec
    import fiscal
    import valider_fec
    db = str(tmp_path / "x.db")
    c = init_db.init_demo(db, FEC2025, 2026)
    operations.saisir(c, type="loyer", montant=795, bien_id=1,
                      date_operation="2026-03-05")
    fiscal.cloturer(c, 2026)
    fec = str(tmp_path / "sortie.txt")
    export_fec.exporter(c, 2026, fec)
    c.close()
    rapport = valider_fec.valider(fec, comme_dict=True)
    assert rapport["erreurs"] == []
    assert rapport["observations"] == []


def test_base_refuse_structurellement_un_montant_negatif(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO ligne (ecriture_id, compte_num, debit, credit)"
                     " SELECT id, '108000', -50, 0 FROM ecriture LIMIT 1")


# === Second audit externe, points 3 à 5 ====================================

def test_alur_reintegre_automatiquement_sans_saisie_manuelle(conn):
    """RÉFUTATION du point 4 : la règle retraitement_alur_auto est livrée à 1
    (active). Ce test couvre le chemin AUTOMATIQUE, que le test en or ne
    vérifiait pas (il passe les retraitements à la main)."""
    import parametres
    assert parametres.valeur(conn, "retraitement_alur_auto", 2026,
                             defaut=None) == 1
    operations.saisir(conn, type="loyer", montant=10000, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    operations.saisir(conn, type="fonds_travaux_alur", montant=61,
                      date_operation="2026-04-10", bien_id=1)
    r = fiscal.cloturer(conn, 2026)                # AUCUN autres_retraitements
    s = r["suivi_39c"]
    sans_retraitement = round(r["agregats"]["resultat_comptable"]
                              + s["report_annee"] - s["utilisation_annee"], 2)
    assert r["resultat_fiscal"] == pytest.approx(sans_retraitement + 61, abs=0.01)


def test_alur_desactivable_par_regle_datee(conn):
    """La règle reste une RÈGLE : à 0, la réintégration cesse."""
    import parametres
    parametres.definir(conn, "retraitement_alur_auto", 0, "2026-01-01",
                       reference="test", commentaire="désactivation")
    operations.saisir(conn, type="loyer", montant=10000, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    operations.saisir(conn, type="fonds_travaux_alur", montant=61,
                      date_operation="2026-04-10", bien_id=1)
    r = fiscal.cloturer(conn, 2026)
    s = r["suivi_39c"]
    sans = round(r["agregats"]["resultat_comptable"] + s["report_annee"]
                 - s["utilisation_annee"], 2)
    assert r["resultat_fiscal"] == pytest.approx(sans, abs=0.01)


def test_chaque_regle_livree_declare_son_impact():
    """Point 4 retenu : une règle versionnée n'est utile que si l'utilisateur
    sait ce qu'elle change."""
    import parametres
    for cle, *_ in parametres.REGLES_DEFAUT:
        module, effet = parametres.impact(cle)
        assert module != "Non documenté", f"impact non déclaré pour {cle}"
        assert len(effet) > 30


def test_seuil_immobilisation_avertit_sans_changer_le_compte(conn):
    """L'audit relevait une confusion possible : ce seuil n'est qu'un
    AVERTISSEMENT, il ne requalifie jamais la dépense."""
    import parametres
    r = operations.saisir(conn, type="maintenance", montant=600,
                          date_operation="2026-05-05", bien_id=1)
    compte = conn.execute(
        "SELECT compte_num FROM ligne WHERE ecriture_id=? AND compte_num "
        "LIKE '6%'", (r["ecriture_id"],)).fetchone()
    assert compte, "la dépense reste sur un compte de CHARGE"
    assert parametres.impact("seuil_immobilisation")[0] == "Contrôle de saisie"


def test_composant_cede_exclu_de_l_exercice_de_cession(conn):
    """Point 3 : la comparaison de dates (désormais lexicographique, sans
    CAST) doit garder exactement la même sémantique."""
    import amortissement
    import cession
    actifs_avant = len(amortissement.dotations_exercice(conn, 2026))
    cession.ceder_bien(conn, 1, "2026-07-10", 150000)
    # exercice de la cession : plus aucune dotation de clôture
    assert amortissement.dotations_exercice(conn, 2026) == []
    # exercice ANTÉRIEUR : les dotations restent dues
    assert len(amortissement.dotations_exercice(conn, 2025)) == actifs_avant
