# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Non-régression des constats de la passe O (sauvegardes et pérennité).

Le risque que cette passe met au jour tient en une phrase : **confondre une
copie créée avec une sauvegarde utilisable.** Une copie fidèle d'une base
abîmée est une copie abîmée ; un fichier de zéro octet porte le bon nom ;
un manifeste tronqué perd sa preuve sans rien dire ; un registre illisible
ressemble à un registre vide.

Le second fil est celui de l'APPARTENANCE et de l'HISTOIRE. Tous les
dossiers nomment leur base « compta.db » : le répertoire où traîne une
copie ne prouve pas de quel dossier elle vient. Et une restauration coupe
l'histoire comptable en deux — après elle, deux FEC du même exercice
peuvent coexister, tous deux intègres au sens de leur empreinte, sans que
rien ne dise lequel fait foi.

Ces tests figent l'exigence commune : **ce qui protège doit être vérifié
au moment où on le crée, pas le jour où l'on en a besoin.**

Aucune donnée réelle : exploitant fictif, bases blanches, loyers de 800 €.

Lancer :  pytest -q tests/test_passe_o.py
"""
import os
import shutil
import sqlite3
import tempfile

import pytest

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import dossiers as dossiers_mod
import fiscal
import init_db
import operations
import perennite


# ── Fabriques de pièces fictives ──────────────────────────────────────────

def _dossier(racine, nom="compta.db", annee=2026, loyer=800.0,
             exploitant="Exploitant fictif", siren="000000000",
             bien="Bien fictif"):
    chemin = os.path.join(racine, nom)
    conn = init_db.init_blanc(chemin, annee)
    conn.execute("INSERT INTO exploitant VALUES (1,?,?,'Adresse fictive')",
                 (exploitant, siren))
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) "
                 "VALUES (1,1,?,12000)", (bien,))
    conn.commit()
    operations.saisir(conn, type="loyer", montant=loyer, bien_id=1,
                      date_operation=f"{annee}-03-10", periode=f"{annee}-03")
    conn.close()
    return chemin


def corrompre(chemin):
    """Abîme le schéma d'une base, sans toucher à sa taille."""
    with open(chemin, "r+b") as f:
        f.seek(100)
        f.write(b"\x00" * 400)


def recettes(chemin):
    conn = sqlite3.connect(chemin)
    try:
        return round(conn.execute(
            "SELECT COALESCE(SUM(credit),0) FROM ligne "
            "WHERE compte_num='708810'").fetchone()[0], 2)
    finally:
        conn.close()


# ═══ O-01 — une copie n'est pas une sauvegarde tant qu'on ne l'a pas lue ═

def test_o01_une_copie_illisible_n_est_pas_retournee_comme_reussie(tmp_path):
    """L'API `backup` garantit une copie FIDÈLE, pas la validité de ce
    qu'elle copie : une base au schéma corrompu donnait une copie tout
    aussi corrompue, et `sauvegarder` retournait son chemin comme un
    succès. Le défaut n'apparaissait qu'au moment où l'on avait besoin de
    la copie — c'est-à-dire trop tard."""
    chemin = _dossier(str(tmp_path))
    corrompre(chemin)
    with pytest.raises(ValueError, match="inutilisable"):
        perennite.sauvegarder(chemin)


def test_o01_la_copie_inutilisable_est_retiree(tmp_path):
    """La laisser sur le disque la ferait figurer dans la liste des
    sauvegardes, où elle passerait pour une protection."""
    chemin = _dossier(str(tmp_path))
    corrompre(chemin)
    with pytest.raises(ValueError):
        perennite.sauvegarder(chemin)
    assert perennite.lister_sauvegardes(chemin) == []


def test_o01_une_sauvegarde_ordinaire_reste_possible(tmp_path):
    chemin = _dossier(str(tmp_path))
    copie = perennite.sauvegarder(chemin)
    assert copie and os.path.exists(copie)
    assert recettes(copie) == 800.0


# ═══ O-02 — le nom du jour ne prouve pas qu'une copie existe ════════════

def test_o02_une_copie_quotidienne_vide_est_refaite(tmp_path):
    """Un fichier de zéro octet — une coupure pendant la copie du matin —
    suffisait à dire « déjà fait aujourd'hui », et aucune sauvegarde
    utilisable n'était plus créée de la journée. Le fichier vide figurait
    même dans la liste, où il passait pour une protection."""
    chemin = _dossier(str(tmp_path))
    premiere = perennite.sauvegarde_quotidienne(chemin)
    open(premiere, "w").close()                    # vidée par une coupure
    assert perennite._copie_inutilisable(premiere)
    seconde = perennite.sauvegarde_quotidienne(chemin)
    # Une nouvelle tentative a bien eu lieu, et son résultat est relisible
    # (le nom peut être le même si les deux copies tombent dans la même
    # seconde : ce qui compte est qu'une copie EXPLOITABLE existe).
    assert seconde
    assert perennite._copie_inutilisable(seconde) == ""
    assert recettes(seconde) == 800.0


def test_o02_une_copie_quotidienne_saine_n_est_pas_refaite(tmp_path):
    """Contre-épreuve : le mécanisme reste bien quotidien."""
    chemin = _dossier(str(tmp_path))
    assert perennite.sauvegarde_quotidienne(chemin)
    assert perennite.sauvegarde_quotidienne(chemin) is None


# ═══ O-03 — la rotation n'efface pas la source d'une restauration ══════

def test_o03_la_source_survit_a_la_copie_de_surete(tmp_path):
    """La copie de sûreté prise juste avant la restauration déclenche une
    rotation, laquelle pouvait supprimer LE FICHIER que l'on s'apprêtait à
    lire. La base active était alors remplacée par du vide, avec un retour
    annoncé réussi."""
    chemin = _dossier(str(tmp_path))
    # La plus ancienne des sauvegardes ordinaires, au quota : c'est elle
    # que la rotation suivante éliminerait.
    source = perennite.sauvegarder(chemin, "test1", garder=2)
    perennite.sauvegarder(chemin, "test2", garder=2)
    assert os.path.exists(source)
    perennite.restaurer(chemin, source)
    assert os.path.exists(source), "la source a été supprimée en cours de route"
    assert recettes(chemin) == 800.0


def test_o03_une_source_disparue_n_ecrase_pas_la_base(tmp_path):
    """Garde de dernier recours : si la source s'évapore entre sa
    validation et sa lecture, la base courante reste intacte."""
    chemin = _dossier(str(tmp_path))
    source = perennite.sauvegarder(chemin)
    vraie_sauvegarde = perennite.sauvegarder

    def sauvegarde_qui_emporte_la_source(*a, **k):
        resultat = vraie_sauvegarde(*a, **k)
        os.remove(source)                  # ce que faisait la rotation
        return resultat

    perennite.sauvegarder = sauvegarde_qui_emporte_la_source
    try:
        with pytest.raises(ValueError, match="disparu"):
            perennite.restaurer(chemin, source)
    finally:
        perennite.sauvegarder = vraie_sauvegarde
    assert recettes(chemin) == 800.0


# ═══ O-04 — l'appartenance se lit dans la base, pas dans son chemin ════

def test_o04_la_copie_d_un_autre_dossier_est_refusee(tmp_path):
    """Le répertoire est un ACCIDENT DE RANGEMENT, pas une preuve
    d'appartenance : il suffisait d'y déposer la copie d'un autre dossier —
    tous nomment leur base « compta.db » — pour qu'elle soit acceptée, et
    une comptabilité en remplaçait une autre."""
    a = tmp_path / "A"
    b = tmp_path / "B"
    a.mkdir()
    b.mkdir()
    chemin_a = _dossier(str(a), loyer=1600.0)
    chemin_b = _dossier(str(b), loyer=900.0, exploitant="Autre exploitant",
                        siren="111111111", bien="Autre bien fictif")
    copie_b = perennite.sauvegarder(chemin_b)
    perennite.sauvegarder(chemin_a)                # crée le dossier de A
    intrus = os.path.join(perennite.dossier_sauvegardes(chemin_a),
                          os.path.basename(copie_b))
    shutil.copy(copie_b, intrus)
    with pytest.raises(ValueError, match="ne provient pas de ce dossier"):
        perennite.restaurer(chemin_a, intrus)
    assert recettes(chemin_a) == 1600.0


def test_o04_une_copie_du_meme_dossier_reste_restaurable(tmp_path):
    """Contre-épreuve : la vérification d'identité ne doit rien casser."""
    chemin = _dossier(str(tmp_path))
    copie = perennite.sauvegarder(chemin)
    perennite.restaurer(chemin, copie)
    assert recettes(chemin) == 800.0


def test_o04_un_dossier_vierge_ne_fait_conclure_a_rien(tmp_path):
    """Prudence volontaire : on ne refuse que sur une CONTRADICTION
    constatée, jamais sur une identité absente ou illisible."""
    chemin = os.path.join(str(tmp_path), "compta.db")
    init_db.init_blanc(chemin, 2026).close()
    assert perennite._identites_incompatibles(chemin, chemin) == ""


# ═══ O-05 — une preuve illisible est une anomalie ══════════════════════

def _dossier_archive(tmp_path):
    chemin = _dossier(str(tmp_path))
    conn = sqlite3.connect(chemin)
    try:
        fiscal.cloturer(conn, 2026, forcer=True)
        archive = perennite.archiver_fec(conn, 2026, chemin)
    finally:
        conn.close()
    return chemin, archive


def test_o05_une_ligne_de_manifeste_tronquee_est_signalee(tmp_path):
    """La ligne était SAUTÉE : la preuve portant sur cette archive cessait
    d'exister, sans un mot, et un consommateur cherchant les statuts
    différents de « ok » n'y voyait plus d'anomalie."""
    chemin, archive = _dossier_archive(tmp_path)
    with open(archive["manifeste"], "a", encoding="utf-8") as f:
        f.write("ligne;tronquee\n")
    statuts = [a["statut"] for a in perennite.verifier_archives(chemin)]
    assert "illisible" in statuts


def test_o05_un_manifeste_disparu_ne_rend_plus_une_liste_vide(tmp_path):
    """Son absence alors que des archives existent n'est pas « rien à
    vérifier » : c'est la disparition de ce qui permettait de vérifier."""
    chemin, archive = _dossier_archive(tmp_path)
    os.remove(archive["manifeste"])
    resultats = perennite.verifier_archives(chemin)
    assert resultats and all(a["statut"] == "sans_preuve" for a in resultats)


def test_o05_une_archive_hors_manifeste_est_signalee(tmp_path):
    chemin, archive = _dossier_archive(tmp_path)
    orpheline = os.path.join(os.path.dirname(archive["chemin"]),
                             "FEC2026-cloture-orpheline.txt")
    shutil.copy(archive["chemin"], orpheline)
    statuts = {a["fichier"]: a["statut"]
               for a in perennite.verifier_archives(chemin)}
    assert statuts[os.path.basename(orpheline)] == "sans_preuve"


def test_o05_des_archives_intactes_restent_ok(tmp_path):
    chemin, _archive = _dossier_archive(tmp_path)
    assert [a["statut"] for a in perennite.verifier_archives(chemin)] == ["ok"]


# ═══ O-06 — une preuve qui ne prouve plus rien n'est pas remise ════════

def test_o06_une_archive_alteree_n_est_plus_servie(tmp_path):
    """Le contrôle d'intégrité existait, mais le parcours de téléchargement
    ne l'appelait pas : une archive modifiée était servie en HTTP 200 comme
    n'importe quelle autre."""
    chemin, archive = _dossier_archive(tmp_path)
    with open(archive["chemin"], "a", encoding="utf-8") as f:
        f.write("ligne ajoutée après coup\n")
    refus = perennite.motif_archive_non_servable(chemin, archive["chemin"])
    assert refus and "empreinte" in refus


def test_o06_une_archive_intacte_reste_servie(tmp_path):
    chemin, archive = _dossier_archive(tmp_path)
    assert perennite.motif_archive_non_servable(chemin,
                                                archive["chemin"]) == ""


# ═══ O-08 — une sauvegarde d'une version future n'est pas installée ════

def test_o08_une_sauvegarde_trop_recente_est_refusee_avant_d_ecraser(tmp_path):
    """Elle était installée, puis le garde de version bloquait le dossier
    entier : la restauration s'annonçait réussie et rendait la comptabilité
    inaccessible dans la foulée."""
    chemin = _dossier(str(tmp_path))
    copie = perennite.sauvegarder(chemin)
    conn = sqlite3.connect(copie)
    conn.execute("UPDATE meta SET valeur='99' WHERE cle='version_schema'")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="plus récente"):
        perennite.restaurer(chemin, copie)
    assert recettes(chemin) == 800.0
    assert init_db.version_base(sqlite3.connect(chemin)) \
        == init_db.VERSION_SCHEMA


# ═══ O-09 — un registre illisible n'est pas un registre vide ═══════════

def test_o09_un_registre_tronque_est_signale(tmp_path):
    """Un registre TRONQUÉ était traité comme un registre VIDE : tous les
    dossiers secondaires disparaissaient de l'interface, la session
    retombait sur le principal, et les comptabilités correspondantes
    restaient sur le disque sans que rien ne dise où elles étaient
    passées."""
    racine = str(tmp_path)
    chemin = _dossier(racine)
    with open(os.path.join(racine, "dossiers.json"), "w") as f:
        f.write('{"doss')
    assert dossiers_mod.probleme_registre(racine)
    # …mais l'utilisateur n'est pas enfermé : le principal reste joignable.
    liste = dossiers_mod.lister(racine, chemin)
    assert any(e["slug"] == dossiers_mod.PRINCIPAL for e in liste)


def test_o09_on_ne_reecrit_pas_par_dessus_un_registre_abime(tmp_path):
    """Enregistrer un dossier réécrirait le registre par-dessus ce qu'il en
    reste, détruisant les entrées encore récupérables."""
    racine = str(tmp_path)
    _dossier(racine)
    with open(os.path.join(racine, "dossiers.json"), "w") as f:
        f.write('{"doss')
    with pytest.raises(dossiers_mod.RegistreIllisible):
        dossiers_mod._charger(racine)


def test_o09_un_registre_sain_ne_signale_rien(tmp_path):
    racine = str(tmp_path)
    _dossier(racine)
    assert dossiers_mod.probleme_registre(racine) == ""


def test_o09_l_absence_de_registre_reste_normale(tmp_path):
    """Un dossier neuf n'a pas encore de registre : ce n'est pas une
    anomalie."""
    assert dossiers_mod.probleme_registre(str(tmp_path)) == ""


# ═══ O-10 — une restauration coupe l'histoire comptable en deux ═══════

def test_o10_les_archives_sont_rattachees_a_leur_histoire(tmp_path):
    """Deux FEC du même exercice peuvent coexister après une restauration,
    tous deux intègres au sens de leur empreinte, et rien ne disait lequel
    fait foi : l'utilisateur devait reconstruire ce contexte hors du
    logiciel."""
    chemin, _archive = _dossier_archive(tmp_path)
    copie = perennite.sauvegarder(chemin)
    perennite.restaurer(chemin, copie)
    conn = sqlite3.connect(chemin)
    try:
        perennite.archiver_fec(conn, 2026, chemin)
    finally:
        conn.close()
    histoires = perennite.archives_par_histoire(chemin)
    assert len(histoires) == 2
    assert histoires[0]["courante"] is True
    assert histoires[1]["courante"] is False
    assert "restauré" in histoires[1]["rupture"]
    assert len(histoires[0]["archives"]) == 1


def test_o10_le_repere_n_est_pas_compte_comme_une_archive(tmp_path):
    """Le marqueur de rupture vit dans le manifeste : il ne doit pas
    apparaître comme un fichier manquant."""
    chemin, _archive = _dossier_archive(tmp_path)
    copie = perennite.sauvegarder(chemin)
    perennite.restaurer(chemin, copie)
    statuts = [a["statut"] for a in perennite.verifier_archives(chemin)]
    assert statuts == ["ok"]


def test_o10_sans_restauration_il_n_y_a_qu_une_histoire(tmp_path):
    chemin, _archive = _dossier_archive(tmp_path)
    histoires = perennite.archives_par_histoire(chemin)
    assert len(histoires) == 1 and histoires[0]["courante"] is True


# ═══ Ce qui tenait doit continuer de tenir ═══════════════════════════

def test_les_sauvegardes_de_surete_restent_hors_quota(tmp_path):
    chemin = _dossier(str(tmp_path))
    surete = perennite.sauvegarder(chemin, "avant-cloture", garder=1)
    for i in range(3):
        perennite.sauvegarder(chemin, f"ordinaire{i}", garder=1)
    assert os.path.exists(surete)


def test_une_sauvegarde_vide_reste_refusee_a_la_restauration(tmp_path):
    """Garde antérieure : une copie sans écriture ne remplace rien."""
    chemin = _dossier(str(tmp_path))
    copie = perennite.sauvegarder(chemin)
    conn = sqlite3.connect(copie)
    conn.execute("DELETE FROM ligne")
    conn.execute("DELETE FROM ecriture")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="aucune écriture"):
        perennite.restaurer(chemin, copie)
    assert recettes(chemin) == 800.0


def test_dossier_temporaire_nettoye():
    """Garde-fou de la suite elle-même : ces tests n'écrivent que dans le
    tmp_path de pytest, jamais à côté des fichiers du projet."""
    assert not os.path.exists(os.path.join(tempfile.gettempdir(),
                                           "compta.db"))
