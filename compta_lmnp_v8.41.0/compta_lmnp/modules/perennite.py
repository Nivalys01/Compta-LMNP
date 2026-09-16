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
                garder: int = GARDER_DEFAUT, epargner=()) -> str | None:
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

    # UNE COPIE N'EST PAS UNE SAUVEGARDE tant qu'on n'a pas vérifié qu'elle
    # se relit. L'API `backup` garantit une copie fidèle, pas la validité
    # de ce qu'elle copie : une base dont le schéma a été corrompu donnait
    # une copie tout aussi corrompue, et `sauvegarder` retournait son
    # chemin comme un succès. Le défaut n'apparaissait qu'au moment où l'on
    # avait besoin de la copie — c'est-à-dire trop tard.
    probleme = _copie_inutilisable(cible)
    if probleme:
        # On retire la copie : la laisser sur le disque la ferait figurer
        # dans la liste des sauvegardes, où elle serait prise pour une
        # protection alors qu'elle n'en est pas une.
        try:
            os.remove(cible)
        except OSError:
            pass
        raise ValueError(
            f"Sauvegarde abandonnée : la copie produite est inutilisable "
            f"({probleme}). Le fichier a été retiré. La base d'origine est "
            "peut-être endommagée — vérifiez-la avant de continuer, et "
            "conservez les sauvegardes antérieures.")

    _rotation(dossier, stem, garder, epargner=epargner)
    return cible


def _copie_inutilisable(chemin: str) -> str:
    """Motif rendant une copie inexploitable, ou chaîne vide si elle l'est.

    On demande à la copie exactement ce qu'on lui demandera le jour d'une
    restauration : être une base SQLite saine, et porter les tables sans
    lesquelles elle ne restituerait rien.
    """
    try:
        if os.path.getsize(chemin) == 0:
            return "fichier vide"
        c = sqlite3.connect(chemin)
        try:
            verdict = c.execute("PRAGMA integrity_check").fetchone()[0]
            if verdict != "ok":
                return f"integrity_check : {verdict}"
            for table in ("ecriture", "ligne", "exercice"):
                c.execute(f"SELECT COUNT(*) FROM {table}")
        finally:
            c.close()
    except (OSError, sqlite3.DatabaseError) as exc:
        return f"{type(exc).__name__} : {exc}"
    return ""


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


def _version_trop_recente(chemin: str):
    """(version de la base, version connue) si la base vient d'une version
    postérieure du logiciel ; None sinon ou si l'information manque."""
    try:
        import init_db
        c = sqlite3.connect(chemin)
        try:
            version = init_db.version_base(c)
        finally:
            c.close()
        connue = init_db.VERSION_SCHEMA
    except Exception:                                # noqa: BLE001
        return None
    return (version, connue) if version and version > connue else None


def _identite(chemin: str) -> tuple | None:
    """(nom de l'exploitant, SIREN, libellés des biens) d'une base, ou None
    si cette identité n'est pas lisible."""
    try:
        c = sqlite3.connect(chemin)
        try:
            exp = c.execute("SELECT nom, siren FROM exploitant "
                            "ORDER BY id LIMIT 1").fetchone()
            biens = tuple(sorted(
                r[0] for r in c.execute("SELECT libelle FROM bien")))
        finally:
            c.close()
    except sqlite3.DatabaseError:
        return None
    return (None, None, biens) if exp is None else (exp[0], exp[1], biens)


def _identites_incompatibles(db_path: str, sauvegarde: str) -> str:
    """Motif d'incompatibilité entre deux bases, ou chaîne vide.

    Prudence volontaire : une identité illisible, absente des deux côtés,
    ou un dossier encore vierge ne font conclure à RIEN. On ne refuse que
    sur une contradiction constatée.
    """
    ici, la_bas = _identite(db_path), _identite(sauvegarde)
    if ici is None or la_bas is None:
        return ""
    nom_ici, siren_ici, biens_ici = ici
    nom_la, siren_la, biens_la = la_bas
    if siren_ici and siren_la and siren_ici != siren_la:
        return f"SIREN {siren_la} au lieu de {siren_ici}"
    if nom_ici and nom_la and nom_ici != nom_la:
        return f"exploitant « {nom_la} » au lieu de « {nom_ici} »"
    if biens_ici and biens_la and not (set(biens_ici) & set(biens_la)):
        return (f"aucun bien commun ({', '.join(biens_la)} au lieu de "
                f"{', '.join(biens_ici)})")
    return ""


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
    if reel == attendu:
        # …mais le répertoire est un ACCIDENT DE RANGEMENT, pas une preuve
        # d'appartenance : il suffisait d'y déposer la copie d'un autre
        # dossier pour qu'elle soit acceptée, et une comptabilité en
        # remplaçait une autre. Ce qui identifie un dossier est ce qu'il
        # contient — son exploitant et ses biens.
        ecart = _identites_incompatibles(db_path, sauvegarde)
        if ecart:
            raise ValueError(
                "Cette sauvegarde ne provient pas de ce dossier : " + ecart
                + ". Elle a sans doute été déposée ici par erreur. La "
                  "restaurer remplacerait cette comptabilité par une autre.")
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
    # Une sauvegarde produite par une version PLUS RÉCENTE du logiciel était
    # installée, puis le garde de version bloquait le dossier entier : la
    # restauration s'annonçait réussie et rendait la comptabilité
    # inaccessible dans la foulée. On vérifie avant d'écraser.
    trop_recente = _version_trop_recente(sauvegarde)
    if trop_recente:
        raise ValueError(
            f"La sauvegarde {os.path.basename(sauvegarde)} a été produite par "
            f"une version plus récente du logiciel (schéma {trop_recente[0]}, "
            f"celui-ci en connaît {trop_recente[1]}). La restaurer rendrait "
            "ce dossier inaccessible : mettez d'abord le logiciel à jour.")
    # 2. Copie de sûreté de l'état courant (peut échouer si la base actuelle
    #    est trop corrompue pour être lue : on la met alors de côté telle
    #    quelle, sans la perdre).
    surete = ""
    if os.path.exists(db_path):
        try:
            # `epargner` : la copie de sûreté déclenche une rotation, qui
            # pouvait supprimer LA SAUVEGARDE QUE L'ON S'APPRÊTE À LIRE —
            # la base active était alors remplacée par du vide, avec un
            # retour annoncé réussi.
            surete = sauvegarder(db_path, "avant-restauration",
                                 epargner=(sauvegarde,)) or ""
        # `ValueError` : depuis que `sauvegarder` vérifie sa copie, une base
        # courante trop abîmée pour produire une copie relisible ressort
        # par là. C'est exactement le cas que cette branche traite — on met
        # la base de côté telle quelle plutôt que de la perdre.
        except (sqlite3.DatabaseError, ValueError):
            surete = db_path + ".corrompue-" + datetime.now().strftime("%Y%m%d-%H%M%S")
            os.replace(db_path, surete)
    # 2 bis. La restauration COUPE L'HISTOIRE du dossier en deux. Les FEC
    #        archivés avant elle décrivent un état que la base ne porte
    #        plus : deux archives du même exercice peuvent coexister, toutes
    #        deux intègres au sens de leur empreinte, et rien ne disait
    #        laquelle fait foi. L'utilisateur devait reconstruire ce
    #        contexte hors du logiciel. On inscrit donc la coupure dans le
    #        manifeste, à sa date, entre les deux séries.
    _marquer_restauration(db_path, sauvegarde)

    # 3. Restauration par copie SQLite (cohérente), pas par copie de fichier.
    #    La source est revérifiée : entre sa validation et ici, la copie de
    #    sûreté et sa rotation sont passées.
    if not os.path.exists(sauvegarde):
        raise ValueError(
            f"La sauvegarde {os.path.basename(sauvegarde)} a disparu avant "
            "d'avoir pu être lue — restauration abandonnée, la base courante "
            "est intacte" + (f" (copie de sûreté : {surete})" if surete else ""))
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


def _rotation(dossier: str, stem: str, garder: int, epargner=()) -> None:
    """Ne conserve que les `garder` sauvegardes ORDINAIRES les plus récentes.

    Les sauvegardes de sûreté (MOTIFS_SURETE) sont hors quota : elles ne
    sont jamais effacées automatiquement. `epargner` protège en outre des
    fichiers nommément — voir `restaurer`, qui y met sa propre source.
    """
    protege = {os.path.realpath(p) for p in epargner}
    fichiers = sorted(
        f for f in os.listdir(dossier)
        if f.startswith(stem + "-") and f.endswith(".db")
        and not any(m in f for m in MOTIFS_SURETE)
        and os.path.realpath(os.path.join(dossier, f)) not in protege)
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
                # La décision se prenait sur le SEUL NOM du fichier. Un
                # fichier de zéro octet — une coupure pendant la copie du
                # matin — suffisait donc à dire « déjà fait aujourd'hui »,
                # et aucune sauvegarde utilisable n'était plus créée de la
                # journée. Le fichier vide figurait même dans la liste des
                # sauvegardes, où il passait pour une protection.
                if not _copie_inutilisable(os.path.join(dossier, f)):
                    return None                # déjà fait, et exploitable
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


MARQUE_RESTAURATION = "-- RESTAURATION"


def _marquer_restauration(db_path: str, sauvegarde: str) -> None:
    """Inscrit la coupure d'histoire dans le manifeste des archives."""
    dossier = dossier_archives(db_path)
    manifeste = os.path.join(dossier, MANIFESTE)
    if not os.path.exists(manifeste):
        return                       # aucune archive : rien à départager
    with open(manifeste, "a", encoding="utf-8", newline="") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')};"
                f"{MARQUE_RESTAURATION};0;"
                f"dossier restauré depuis {os.path.basename(sauvegarde)} — "
                "les archives ci-dessus décrivent l'état ANTÉRIEUR\n")


def archives_par_histoire(db_path: str) -> list[dict]:
    """Archives regroupées par HISTOIRE comptable, la plus récente d'abord.

    Chaque restauration ouvre une histoire nouvelle : les archives qui la
    précèdent restent des documents valides, mais elles ne décrivent plus
    la comptabilité en cours. Les présenter côte à côte sans le dire
    laissait deux FEC du même exercice se contredire en silence.
    """
    dossier = dossier_archives(db_path)
    manifeste = os.path.join(dossier, MANIFESTE)
    if not os.path.exists(manifeste):
        return []
    histoires: list[dict] = [{"courante": True, "rupture": "", "archives": []}]
    with open(manifeste, encoding="utf-8") as f:
        next(f, None)
        for ligne in f:
            champs = ligne.rstrip("\n").split(";")
            if len(champs) != 4:
                continue
            horo, nom, _ex, detail = champs
            if nom == MARQUE_RESTAURATION:
                histoires.insert(0, {"courante": True, "rupture": "",
                                     "archives": []})
                histoires[1]["courante"] = False
                histoires[1]["rupture"] = f"{horo} — {detail}"
                continue
            histoires[0]["archives"].append({"fichier": nom,
                                             "horodatage": horo})
    # `insert(0, …)` a déjà placé les histoires de la plus récente à la
    # plus ancienne : la première est celle en cours.
    return [h for h in histoires if h["archives"] or h["rupture"]]


def motif_archive_non_servable(db_path: str, chemin: str) -> str:
    """Motif refusant de remettre cette archive, ou chaîne vide.

    Le contrôle d'intégrité existait, mais le parcours de téléchargement ne
    l'appelait pas : une archive modifiée était servie comme n'importe
    quelle autre, sans le moindre signal. Une preuve qui ne prouve plus
    rien ne doit pas être remise comme si elle prouvait encore.
    """
    nom = os.path.basename(chemin)
    statuts = {a["fichier"]: a["statut"] for a in verifier_archives(db_path)}
    statut = statuts.get(nom)
    if not statut or statut == "ok":
        return ""
    motif = {
        "modifie": "son contenu ne correspond plus à l'empreinte enregistrée "
                   "lors de son archivage",
        "absent": "le fichier a disparu du dossier d'archives",
        "sans_preuve": "aucune empreinte n'a été conservée pour elle",
    }.get(statut, f"statut « {statut} »")
    return (f"Téléchargement refusé : {nom} — {motif}. Ce fichier ne peut "
            "plus servir de preuve. Réexportez le FEC de l'exercice "
            "concerné, ou restaurez une sauvegarde antérieure.")


def verifier_archives(db_path: str) -> list[dict]:
    """
    Recontrôle chaque FEC archivé contre son empreinte du manifeste.
    Retourne, par entrée : {"fichier", "exercice", "statut"} où statut vaut
    "ok", "modifie" (empreinte différente) ou "absent" (fichier disparu).
    """
    dossier = dossier_archives(db_path)
    manifeste = os.path.join(dossier, MANIFESTE)
    # Le manifeste EST la preuve : son absence alors que des archives
    # existent n'est pas « rien à vérifier », c'est la disparition de ce
    # qui permettait de vérifier. La fonction rendait une liste vide, et
    # tout consommateur cherchant un statut différent de « ok » n'y voyait
    # aucune anomalie.
    archives = ([f for f in sorted(os.listdir(dossier))
                 if f.startswith("FEC") and f.endswith(".txt")]
                if os.path.isdir(dossier) else [])
    if not os.path.exists(manifeste):
        if not archives:
            return []
        return [{"fichier": nom, "exercice": 0, "statut": "sans_preuve"}
                for nom in archives]
    resultats = []
    vus = set()
    with open(manifeste, encoding="utf-8") as f:
        next(f, None)                                     # entête
        for numero, ligne in enumerate(f, start=2):
            champs = ligne.rstrip("\n").split(";")
            # Une ligne tronquée était simplement SAUTÉE : la preuve
            # portant sur cette archive cessait d'exister, sans un mot.
            if len(champs) != 4:
                if ligne.strip():
                    resultats.append({"fichier": f"manifeste ligne {numero}",
                                      "exercice": 0, "statut": "illisible"})
                continue
            _horo, nom, exercice, attendu = champs
            if nom == MARQUE_RESTAURATION:
                continue             # repère d'histoire, pas une archive
            vus.add(nom)
            chemin = os.path.join(dossier, nom)
            if not os.path.exists(chemin):
                statut = "absent"
            elif _sha256(chemin) != attendu:
                statut = "modifie"
            else:
                statut = "ok"
            try:
                millesime = int(exercice)
            except ValueError:
                millesime = 0
                statut = "illisible"
            resultats.append({"fichier": nom, "exercice": millesime,
                              "statut": statut})
    # Une archive présente sur le disque mais absente du manifeste n'a plus
    # de preuve d'intégrité : elle doit se voir, elle aussi.
    resultats += [{"fichier": nom, "exercice": 0, "statut": "sans_preuve"}
                  for nom in archives if nom not in vus]
    return resultats
