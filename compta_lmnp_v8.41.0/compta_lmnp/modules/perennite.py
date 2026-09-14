# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Pérennité du dossier comptable — J6.

Deux protections complémentaires :

1. SAUVEGARDES de la base (`sauvegardes/`) : copie horodatée de compta.db,
   réalisée via l'API backup de SQLite (cohérente même si une écriture est en
   cours — contrairement à un simple `cp`). Rotation automatique : seules les
   N copies les plus récentes sont conservées. Déclencheurs :
     - au démarrage de l'application (une fois par jour) ;
     - avant chaque clôture (l'opération la plus lourde de conséquences).

2. ARCHIVAGE des FEC (`archives/`) : à chaque clôture, le FEC de l'exercice
   est exporté et figé avec son empreinte SHA-256 dans `manifeste.csv`.
   C'est la piste d'audit : on peut prouver à tout moment qu'un FEC archivé
   n'a pas été modifié depuis sa production (`verifier_archives()`).

Aucune dépendance externe : sqlite3 + hashlib de la bibliothèque standard.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime

import export_fec

GARDER_DEFAUT = 30          # nombre de sauvegardes conservées (rotation)
MANIFESTE = "manifeste.csv"


# ── Sauvegardes de la base ───────────────────────────────────────────────────

def _sous_dossier(db_path: str, nom: str) -> str:
    """Répertoire annexe d'une base, PROPRE à cette base.

    Le nom du fichier entre dans le chemin. Sans cela, deux bases placées
    côte à côte — c'est le cas du dossier principal (`compta.db`) et du bac
    à sable (`bac_a_sable.db`) — partageaient leurs sauvegardes ET leurs
    archives. Conséquences observées : la page Archives du bac à sable
    servait les FEC de la comptabilité RÉELLE, et chaque réinitialisation
    du bac à sable déposait une copie dans les sauvegardes réelles, copie
    que la protection des motifs de sûreté empêchait ensuite d'effacer.

    Le dossier principal garde son emplacement historique, pour ne pas
    rendre invisibles les sauvegardes et archives déjà en place.
    """
    base = os.path.dirname(os.path.abspath(db_path))
    stem = os.path.splitext(os.path.basename(db_path))[0]
    if stem == "compta":
        return os.path.join(base, nom)
    return os.path.join(base, nom, stem)


def dossier_sauvegardes(db_path: str) -> str:
    return _sous_dossier(db_path, "sauvegardes")


def sauvegarder(db_path: str, motif: str = "manuel",
                garder: int = GARDER_DEFAUT) -> str | None:
    """
    Copie horodatée de la base → sauvegardes/<nom>-AAAAMMJJ-HHMMSS-<motif>.db
    Retourne le chemin créé, ou None si la base n'existe pas encore.
    """
    if not os.path.exists(db_path):
        return None
    dossier = dossier_sauvegardes(db_path)
    os.makedirs(dossier, exist_ok=True)
    stem = os.path.splitext(os.path.basename(db_path))[0]
    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
    motif_sain = "".join(c if c.isalnum() or c in "-_" else "-" for c in motif)
    cible = os.path.join(dossier, f"{stem}-{horodatage}-{motif_sain}.db")

    src = sqlite3.connect(db_path)
    try:
        dst = sqlite3.connect(cible)
        try:
            src.backup(dst)                    # copie cohérente (API SQLite)
        finally:
            dst.close()
    finally:
        src.close()

    _rotation(dossier, stem, garder)
    return cible


def _max_quittance(chemin: str) -> int:
    """Plus haut numéro de quittance d'une base, 0 si la table est absente."""
    if not os.path.exists(chemin):
        return 0
    try:
        c = sqlite3.connect(chemin)
        try:
            return c.execute(
                "SELECT COALESCE(MAX(numero), 0) FROM quittance").fetchone()[0]
        finally:
            c.close()
    except sqlite3.DatabaseError:
        return 0


def _avertir_quittances_perdues(db_path: str, sauvegarde: str) -> None:
    avant, apres = _max_quittance(db_path), _max_quittance(sauvegarde)
    if avant > apres:
        raise ValueError(
            f"Cette restauration ferait reculer la numérotation des "
            f"quittances : la base porte des quittances jusqu'au "
            f"n° {avant:05d}, la sauvegarde s'arrête au n° {apres:05d}.\n\n"
            f"{avant - apres} quittance(s) déjà émise(s) — et probablement "
            "remise(s) à vos locataires — disparaîtraient, et leurs numéros "
            "seraient réattribués à d'autres documents. Deux quittances "
            "porteraient alors le même numéro.\n\n"
            "Si vous voulez malgré tout restaurer, exportez d'abord la liste "
            "des quittances émises depuis la page Quittances.")


def restaurer(db_path: str, sauvegarde: str) -> str:
    """
    Restaure la base depuis une sauvegarde, avec deux garde-fous :
      1. la sauvegarde est vérifiée AVANT d'écraser quoi que ce soit
         (PRAGMA integrity_check) — on ne remplace jamais une base abîmée
         par une sauvegarde encore plus abîmée ;
      2. l'état courant est d'abord copié en « avant-restauration », pour
         que la restauration soit elle-même réversible.
    Retourne le chemin de la copie de sûreté créée avant restauration
    (ou une chaîne vide si la base n'existait pas).
    """
    if not os.path.exists(sauvegarde):
        raise ValueError(f"Sauvegarde introuvable : {sauvegarde}")
    # La sauvegarde doit appartenir AU DOSSIER que l'on restaure. Rien ne
    # le vérifiait, et tous les dossiers nomment leur base « compta.db » :
    # leurs sauvegardes sont donc strictement homonymes. Restaurer la
    # mauvaise remplaçait une comptabilité par une autre, en silence, les
    # deux contrôles d'intégrité passant sans broncher.
    attendu = os.path.realpath(dossier_sauvegardes(db_path))
    reel = os.path.realpath(os.path.dirname(sauvegarde))
    if reel != attendu:
        raise ValueError(
            "Cette sauvegarde n'appartient pas au dossier courant.\n"
            f"  attendue dans : {attendu}\n"
            f"  trouvée dans  : {reel}\n"
            "Tous les dossiers nomment leurs sauvegardes de la même façon : "
            "restaurer celle d'un autre dossier remplacerait cette "
            "comptabilité par une autre. Sélectionnez la sauvegarde depuis "
            "la page « Dossiers » du dossier concerné.")
    # Les quittances ont été REMISES À DES TIERS : une restauration qui
    # les efface libère leurs numéros, et la numérotation — que le logiciel
    # garantit continue et vérifiable — recommencerait à un rang déjà
    # utilisé. On avertit plutôt que de laisser deux documents porter le
    # même numéro chez deux locataires.
    _avertir_quittances_perdues(db_path, sauvegarde)

    # 1. Intégrité de la sauvegarde
    try:
        s = sqlite3.connect(sauvegarde)
        try:
            verdict = s.execute("PRAGMA integrity_check").fetchone()[0]
            n_ecr = s.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0]
        finally:
            s.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"Le fichier {os.path.basename(sauvegarde)} n'est pas "
                         f"une base valide : {exc}") from None
    if verdict != "ok":
        raise ValueError(f"La sauvegarde {os.path.basename(sauvegarde)} est "
                         f"corrompue (integrity_check : {verdict}) — "
                         "restauration refusée.")
    if n_ecr == 0:
        raise ValueError(f"La sauvegarde {os.path.basename(sauvegarde)} ne "
                         "contient aucune écriture — restauration refusée "
                         "(choisissez une autre sauvegarde).")
    # 2. Copie de sûreté de l'état courant (peut échouer si la base actuelle
    #    est trop corrompue pour être lue : on la met alors de côté telle
    #    quelle, sans la perdre).
    surete = ""
    if os.path.exists(db_path):
        try:
            surete = sauvegarder(db_path, "avant-restauration") or ""
        except sqlite3.DatabaseError:
            surete = db_path + ".corrompue-" + datetime.now().strftime("%Y%m%d-%H%M%S")
            os.replace(db_path, surete)
    # 3. Restauration par copie SQLite (cohérente), pas par copie de fichier
    src = sqlite3.connect(sauvegarde)
    try:
        dst = sqlite3.connect(db_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return surete


# Motifs de SÛRETÉ : ces sauvegardes précèdent une opération dangereuse et
# sont la seule chose qui permette d'y revenir. Les soumettre à la rotation
# ordinaire les faisait disparaître précisément dans le scénario où elles
# servent — une migration qui échoue chaque jour en reprend une, et la
# première, la seule antérieure à l'incident, sortait du quota en deux
# semaines.
MOTIFS_SURETE = ("avant-migration", "avant-restauration",
                 "avant-reinitialisation", "avant-cloture")


def _rotation(dossier: str, stem: str, garder: int) -> None:
    """Ne conserve que les `garder` sauvegardes ORDINAIRES les plus récentes.

    Les sauvegardes de sûreté sont hors quota : elles ne sont jamais
    effacées automatiquement.
    """
    fichiers = sorted(
        f for f in os.listdir(dossier)
        if f.startswith(stem + "-") and f.endswith(".db")
        and not any(m in f for m in MOTIFS_SURETE))
    for ancien in fichiers[:-garder] if garder > 0 else fichiers:
        os.remove(os.path.join(dossier, ancien))


def sauvegarde_quotidienne(db_path: str) -> str | None:
    """
    Sauvegarde « demarrage » au plus une fois par jour : si une sauvegarde
    de démarrage datée d'aujourd'hui existe déjà, ne fait rien.
    """
    if not os.path.exists(db_path):
        return None
    dossier = dossier_sauvegardes(db_path)
    stem = os.path.splitext(os.path.basename(db_path))[0]
    aujourd_hui = datetime.now().strftime("%Y%m%d")
    prefixe = f"{stem}-{aujourd_hui}-"
    if os.path.isdir(dossier):
        for f in os.listdir(dossier):
            if f.startswith(prefixe) and f.endswith("-demarrage.db"):
                return None                    # déjà fait aujourd'hui
    return sauvegarder(db_path, "demarrage")


def sauvegardes_quotidiennes(chemins: list[str]) -> list[str]:
    """Sauvegarde quotidienne de CHAQUE base fournie (J8 : le démarrage doit
    protéger tous les dossiers du registre, pas seulement le principal)."""
    faites = []
    for chemin in chemins:
        s = sauvegarde_quotidienne(chemin)
        if s:
            faites.append(s)
    return faites


def lister_sauvegardes(db_path: str) -> list[dict]:
    """Liste (récentes d'abord) : nom, chemin, taille, horodatage lisible."""
    dossier = dossier_sauvegardes(db_path)
    if not os.path.isdir(dossier):
        return []
    stem = os.path.splitext(os.path.basename(db_path))[0]
    out = []
    for f in sorted(os.listdir(dossier), reverse=True):
        if f.startswith(stem + "-") and f.endswith(".db"):
            chemin = os.path.join(dossier, f)
            out.append({"nom": f, "chemin": chemin,
                        "taille": os.path.getsize(chemin)})
    return out


# ── Archivage FEC + piste d'audit ────────────────────────────────────────────

def _sha256(chemin: str) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


def dossier_archives(db_path: str) -> str:
    return _sous_dossier(db_path, "archives")


def archiver_fec(conn: sqlite3.Connection, annee: int, db_path: str) -> dict:
    """
    Exporte le FEC de l'exercice dans archives/ (nom horodaté, jamais écrasé)
    et consigne son empreinte SHA-256 dans archives/manifeste.csv :

        horodatage;fichier;exercice;sha256

    Retourne {"chemin", "sha256", "manifeste"}.
    """
    dossier = dossier_archives(db_path)
    os.makedirs(dossier, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
    nom = f"FEC{annee}-cloture-{horodatage}.txt"
    chemin = os.path.join(dossier, nom)
    # Une archive n'est JAMAIS écrasée : en cas de collision d'horodatage
    # (deux clôtures dans la même seconde), on suffixe -2, -3, …
    n = 1
    while os.path.exists(chemin):
        n += 1
        nom = f"FEC{annee}-cloture-{horodatage}-{n}.txt"
        chemin = os.path.join(dossier, nom)
    export_fec.exporter(conn, annee, chemin)
    empreinte = _sha256(chemin)

    manifeste = os.path.join(dossier, MANIFESTE)
    nouveau = not os.path.exists(manifeste)
    with open(manifeste, "a", encoding="utf-8", newline="") as f:
        if nouveau:
            f.write("horodatage;fichier;exercice;sha256\n")
        f.write(f"{datetime.now().isoformat(timespec='seconds')};"
                f"{nom};{annee};{empreinte}\n")
    return {"chemin": chemin, "sha256": empreinte, "manifeste": manifeste}


def verifier_archives(db_path: str) -> list[dict]:
    """
    Recontrôle chaque FEC archivé contre son empreinte du manifeste.
    Retourne, par entrée : {"fichier", "exercice", "statut"} où statut vaut
    "ok", "modifie" (empreinte différente) ou "absent" (fichier disparu).
    """
    dossier = dossier_archives(db_path)
    manifeste = os.path.join(dossier, MANIFESTE)
    if not os.path.exists(manifeste):
        return []
    resultats = []
    with open(manifeste, encoding="utf-8") as f:
        next(f, None)                                     # entête
        for ligne in f:
            champs = ligne.rstrip("\n").split(";")
            if len(champs) != 4:
                continue
            _horo, nom, exercice, attendu = champs
            chemin = os.path.join(dossier, nom)
            if not os.path.exists(chemin):
                statut = "absent"
            elif _sha256(chemin) != attendu:
                statut = "modifie"
            else:
                statut = "ok"
            resultats.append({"fichier": nom, "exercice": int(exercice),
                              "statut": statut})
    return resultats
