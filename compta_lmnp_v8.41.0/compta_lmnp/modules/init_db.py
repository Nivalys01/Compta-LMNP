# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Initialise la base. Deux modes :

  - "blanc" : produit prêt à l'emploi pour un NOUVEAU dossier. Référentiel
    générique seul (journaux + plan de comptes), un exercice ouvert, aucune
    donnée personnelle. C'est le mode livré au client.
  - "demo"  : référentiel + dossier d'exemple (FAURE) + reprise des à-nouveaux
    depuis un FEC de clôture. Sert au développement et à la démonstration.

Usage :
    python init_db.py                       # mode blanc, exercice courant
    python init_db.py --mode demo           # dossier d'exemple + reprise FEC 2025
    python init_db.py --mode blanc --annee 2026
"""
from __future__ import annotations
import argparse
import os
import sqlite3

import reprise

# Racine du PAQUET, pas du dossier de code : ce module vit dans
# modules/, alors que la base, les seeds, VERSION, reference/ et
# demo/ restent un cran au-dessus. Remonter ici évite de reprendre
# chaque os.path.join(HERE, ...) du fichier.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Dossier de référence (RÉEL) : présent en développement, JAMAIS livré.
FEC_REF_DEFAUT = os.path.join(HERE, "reference/FEC_REFERENCE_2025.txt")
SEED_REF = "seed_exemple.sql"

# Dossier de DÉMONSTRATION (fictif, dérivé du réel par outils_demo.py) :
# c'est lui qui part chez le client. Sans ce repli, la réinitialisation du
# bac à sable en mode démo échouait chez l'utilisateur : le seed livré
# réclamait un FEC volontairement exclu du paquet.
FEC_DEMO = os.path.join(HERE, "demo/FEC_DEMO_2025.txt")
SEED_DEMO = "seed_demo.sql"


def dossier_demonstration() -> tuple[str, str]:
    """(seed, FEC) à utiliser pour le mode démo : le dossier de référence
    s'il est là (développement), sinon le dossier anonymisé (client)."""
    if os.path.exists(FEC_REF_DEFAUT) and os.path.exists(
            os.path.join(HERE, SEED_REF)):
        return SEED_REF, FEC_REF_DEFAUT
    return SEED_DEMO, FEC_DEMO


def _exec(conn, nom_fichier):
    with open(os.path.join(HERE, nom_fichier), encoding="utf-8") as f:
        conn.executescript(f.read())


def init(db_path: str, mode: str = "blanc", *,
         fec_path: str | None = None, annee_cible: int | None = None,
         ecraser: bool = False) -> sqlite3.Connection:
    """Crée la base selon le mode. Renvoie la connexion ouverte."""
    if mode not in ("blanc", "demo"):
        raise ValueError(f"Mode inconnu : {mode!r} (attendu 'blanc' ou 'demo').")
    # L'année par défaut suit l'horloge : une valeur figée dans la
    # signature créait, l'année suivante, un dossier dont l'exercice ouvert
    # appartenait au passé.
    if annee_cible is None:
        import datetime as _dt
        annee_cible = _dt.date.today().year
    # Validée AVANT toute destruction : le mode démo insère l'exercice 2025
    # en dur, et un `--annee 2025` provoquait une violation d'unicité APRÈS
    # avoir supprimé la base.
    if mode == "demo" and int(annee_cible) <= 2025:
        raise ValueError(
            f"Le mode démonstration réserve l'exercice 2025 à son "
            f"historique : choisissez une année postérieure "
            f"(reçu : {annee_cible}).")
    if os.path.exists(db_path):
        # Une base existante n'est JAMAIS supprimée sans filet. Le
        # comportement d'origine effaçait le fichier sans un mot — et
        # `main()` visait par défaut la base du dossier principal, si bien
        # qu'un simple « python init_db.py », donné en tête du mode
        # d'emploi, détruisait la comptabilité de l'utilisateur. La base
        # neuve étant cohérente, rien ne distinguait la destruction d'un
        # bug d'affichage.
        if not ecraser:
            raise FileExistsError(
                f"Une base existe déjà à cet emplacement : {db_path}\n"
                "Elle n'a PAS été touchée. Pour créer un dossier, passez "
                "par la page « Dossiers » du logiciel. Pour réinitialiser "
                "malgré tout, relancez avec --ecraser : une sauvegarde sera "
                "prise avant destruction.")
        try:
            import perennite
            sv = perennite.sauvegarder(db_path, motif="avant-reinitialisation")
            print(f"Sauvegarde prise avant réinitialisation : "
                  f"{sv['chemin'] if isinstance(sv, dict) else sv}")
        except Exception as exc:                       # noqa: BLE001
            raise RuntimeError(
                f"Réinitialisation refusée : la sauvegarde préalable a "
                f"échoué ({exc}). Rien n'a été supprimé.") from exc
        # Les fichiers annexes du moteur doivent partir avec la base : un
        # journal résiduel se rattacherait à la base neuve et y rejouerait
        # des pages qui ne lui appartiennent pas.
        for suffixe in ("", "-journal", "-wal", "-shm"):
            annexe = db_path + suffixe
            if os.path.exists(annexe):
                os.remove(annexe)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    _exec(conn, "schema.sql")
    _exec(conn, "seed_referentiel.sql")        # générique, toujours
    creer_index(conn)                          # index de performance
    marquer_version(conn)                      # base neuve = schéma courant

    if mode == "blanc":
        # Dossier neuf : juste un exercice ouvert, prêt pour la saisie.
        conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, statut) "
                     "VALUES (?, ?, ?, 'ouvert')",
                     (annee_cible, f"{annee_cible}-01-01", f"{annee_cible}-12-31"))
        conn.commit()
        return conn

    # mode == "demo" : un dossier COMPLET, pas une coquille.
    #
    # L'exercice précédent était créé « clos » mais VIDE : le débutant qui
    # basculait dessus ne voyait rien, et le bac à sable ne montrait donc
    # jamais à quoi ressemble une année de location tenue de bout en bout.
    # On y rejoue désormais le FEC : loyers mois par mois, appels de
    # charges, taxes, dotation aux amortissements, clôture. Il y a ainsi un
    # exercice PASSÉ à inspecter (grand livre, liasse, export FEC) et un
    # exercice OUVERT pour s'exercer sans rien risquer.
    conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, statut) "
                 "VALUES (2025, '2025-01-01', '2025-12-31', 'ouvert')")
    conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, statut) "
                 "VALUES (?, ?, ?, 'ouvert')",
                 (annee_cible, f"{annee_cible}-01-01", f"{annee_cible}-12-31"))
    conn.commit()
    seed, fec_defaut = dossier_demonstration()
    _exec(conn, seed)
    conn.commit()

    # On teste l'EXISTENCE, pas seulement la présence d'une chaîne. Le
    # paramètre en ligne de commande vaut par défaut le chemin du dossier
    # de référence, absent du paquet client : « fec_path or fec_defaut »
    # retenait donc toujours un fichier inexistant, et le repli sur le jeu
    # anonymisé — dont c'était toute la raison d'être — n'était jamais
    # atteint.
    fec = fec_path if (fec_path and os.path.exists(fec_path)) else fec_defaut
    # 1. L'exercice précédent, écriture par écriture, à numérotation
    #    identique — l'exercice doit être OUVERT pour l'accueillir, il est
    #    refermé juste après.
    import rejeu_fec
    try:
        rejeu_fec.rejouer(conn, fec, 2025)
    except Exception:
        # Un dossier de démonstration ne doit jamais empêcher le logiciel
        # de démarrer : en cas d'échec, on retombe sur l'ancien
        # comportement (exercice précédent vide mais cohérent).
        conn.rollback()
    conn.execute("UPDATE exercice SET statut='clos', resultat_comptable=-949.37 "
                 "WHERE annee=2025")
    conn.commit()

    # 2. Les OPÉRATIONS de l'exercice précédent, reconstituées depuis ses
    #    écritures : le rejeu d'un FEC produit des écritures comptables,
    #    pas des opérations de saisie. Sans cette étape, la page Saisie de
    #    l'exercice passé restait vide — or c'est le premier écran que
    #    regarde un débutant, et c'est là qu'il doit voir à quoi ressemble
    #    une année de location tenue de bout en bout.
    _reconstituer_operations(conn, 2025)

    # 3. Les à-nouveaux de l'exercice courant, depuis le même FEC.
    reprise.construire_an(conn, fec, annee_cible)
    return conn


def _reconstituer_operations(conn: sqlite3.Connection, annee: int) -> None:
    """Rattache une opération de saisie à chaque écriture d'exploitation.

    Le rapprochement se fait par le COMPTE : chaque gabarit en désigne un,
    ce qui donne une correspondance déterministe, sans deviner. Les
    écritures qui ne correspondent à aucune saisie utilisateur — à-nouveaux,
    dotation aux amortissements, acquisitions — n'en reçoivent aucune :
    c'est exact, elles ne sont pas saisies mais générées.
    """
    import gabarits as _g
    catalogue = _g.tous(conn)
    # Plusieurs gabarits partagent un même compte (un loyer et un « autre
    # produit » vont tous deux au 708810). Deux niveaux de rapprochement :
    #   1. le LIBELLÉ de l'écriture, qui reprend celui du gabarit d'origine
    #      — c'est l'indice le plus sûr ;
    #   2. à défaut le compte, en retenant le PREMIER gabarit du catalogue
    #      (l'usage courant précède les cas particuliers), et non le
    #      dernier comme le faisait une simple affectation de dictionnaire.
    # Seuls les gabarits de RÉSULTAT (classes 6 et 7) reconstituent une
    # opération de démonstration. Depuis la passe E, des gabarits visent des
    # comptes de BILAN — dépôt de garantie, capital d'emprunt, compte
    # d'attente 472000. Sans ce filtre, la ligne 472000 des à-nouveaux de la
    # démo devenait une « opération » de démonstration, rattachée à une
    # écriture dont elle ne représentait qu'une fraction du montant.
    comptes_resultat = {n for (n,) in conn.execute(
        "SELECT numero FROM compte WHERE classe IN (6, 7)")}
    catalogue_resultat = {t: g for t, g in catalogue.items()
                          if g["compte"] in comptes_resultat}
    par_libelle = {g["libelle"].strip().lower(): (t, g["nature"])
                   for t, g in catalogue_resultat.items()}
    par_compte: dict[str, tuple[str, str]] = {}
    for t, g in catalogue_resultat.items():
        par_compte.setdefault(g["compte"], (t, g["nature"]))
    bien = conn.execute("SELECT id FROM bien ORDER BY id LIMIT 1").fetchone()
    bien_id = bien[0] if bien else None
    faites = 0
    for eid, num, date, lib, piece in conn.execute(
            "SELECT id, ecriture_num, ecriture_date, libelle, piece_ref "
            "FROM ecriture WHERE exercice_annee=? AND journal_code<>'AN' "
            "ORDER BY ecriture_num", (annee,)):
        del num
        cle_lib = (lib or "").strip().lower()
        for compte, debit, credit in conn.execute(
                "SELECT compte_num, debit, credit FROM ligne "
                "WHERE ecriture_id=?", (eid,)):
            trouve = par_libelle.get(cle_lib) or par_compte.get(compte)
            if trouve and trouve[0] not in catalogue:
                trouve = None
            if not trouve:
                continue
            if catalogue[trouve[0]]["compte"] != compte:
                trouve = par_compte.get(compte)   # le libellé mentait
                if not trouve:
                    continue
            type_op, nature = trouve
            montant = round(credit - debit if nature == "produit"
                            else debit - credit, 2)
            if montant <= 0:                 # contre-passation, sortie…
                continue
            conn.execute(
                "INSERT INTO operation (exercice_annee, type, montant, "
                "date_operation, periode, bien_id, libelle, ecriture_id, "
                "source) VALUES (?,?,?,?,?,?,?,?, 'demo')",
                (annee, type_op, montant, date, date[:7], bien_id,
                 lib or piece, eid))
            faites += 1
            break                            # une opération par écriture
    conn.commit()


# Raccourcis lisibles -------------------------------------------------------

def init_blanc(db_path: str, annee_cible: int | None = None) -> sqlite3.Connection:
    return init(db_path, "blanc", annee_cible=annee_cible)


def init_demo(db_path: str, fec_path: str | None = None,
              annee_cible: int = 2026) -> sqlite3.Connection:
    return init(db_path, "demo", fec_path=fec_path, annee_cible=annee_cible)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["blanc", "demo"], default="blanc")
    p.add_argument("--db", default=os.path.join(HERE, "compta.db"))
    p.add_argument("--fec", default=None)
    p.add_argument("--ecraser", action="store_true",
                   help="réinitialise une base existante "
                        "(sauvegarde prise au préalable)")
    p.add_argument("--annee", type=int, default=2026)
    args = p.parse_args()

    conn = init(args.db, args.mode, fec_path=args.fec,
                annee_cible=args.annee, ecraser=args.ecraser)
    nb_comptes = conn.execute("SELECT COUNT(*) FROM compte").fetchone()[0]
    nb_compo = conn.execute("SELECT COUNT(*) FROM composant").fetchone()[0]
    print(f"Base initialisée : {args.db}  (mode {args.mode})")
    print(f"Comptes : {nb_comptes}  |  Composants : {nb_compo}  "
          f"|  Exercice ouvert : {args.annee}")

    if args.mode == "demo":
        d, c = reprise.controle_equilibre(conn, args.annee)
        print(f"À-nouveaux {args.annee} : Débit {d:.2f} | Crédit {c:.2f} | "
              f"{'ÉQUILIBRÉ ✓' if abs(d - c) < 0.005 else 'DÉSÉQUILIBRÉ ✗'}")
    else:
        print("Dossier vierge : crée ton exploitant, ton bien et tes composants, "
              "puis saisis tes opérations.")
    conn.close()


if __name__ == "__main__":
    main()


# ── Version de schéma ────────────────────────────────────────────────────
# Incrémentée à chaque évolution de structure (nouvelle table/colonne).
# La garde évite l'irritant classique des logiciels comptables : ouvrir une
# base créée par une version PLUS RÉCENTE du logiciel (données invisibles ou
# comportements faux), sans message compréhensible.
VERSION_SCHEMA = 7        # …5: annulation d'opération, 6: quittances,
                          # 7: comptes 164/165/401/411/758 (passe E, E-10)

# Index de performance. Aucun n'existait : SQLite n'indexe pas les clés
# étrangères automatiquement, et tous les calculs (agrégats, contrôles,
# export FEC) filtrent sur l'exercice puis joignent ligne→écriture. Créés
# à l'initialisation ET par la migration (palier 4) pour les bases
# existantes. IF NOT EXISTS : rejouables sans risque.
INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_ecriture_exercice "
    "ON ecriture(exercice_annee)",
    "CREATE INDEX IF NOT EXISTS idx_ligne_ecriture ON ligne(ecriture_id)",
    "CREATE INDEX IF NOT EXISTS idx_ligne_compte ON ligne(compte_num)",
    "CREATE INDEX IF NOT EXISTS idx_operation_exercice_type "
    "ON operation(exercice_annee, type)",
    "CREATE INDEX IF NOT EXISTS idx_plan_amort_exercice "
    "ON plan_amortissement(exercice_annee)",
)


def creer_index(conn) -> None:
    for requete in INDEX:
        conn.execute(requete)
    conn.commit()


def marquer_version(conn) -> None:
    """Crée la table meta si besoin et élève la version au niveau du
    logiciel (jamais d'abaissement)."""
    conn.execute("CREATE TABLE IF NOT EXISTS meta ("
                 "cle TEXT PRIMARY KEY, valeur TEXT NOT NULL)")
    conn.execute("INSERT INTO meta (cle, valeur) VALUES ('version_schema', ?) "
                 "ON CONFLICT(cle) DO UPDATE SET valeur = MAX(CAST(valeur AS "
                 "INTEGER), CAST(excluded.valeur AS INTEGER))",
                 (str(VERSION_SCHEMA),))
    conn.commit()


def version_base(conn) -> int:
    try:
        v = conn.execute("SELECT valeur FROM meta WHERE cle='version_schema'"
                         ).fetchone()
        return int(v[0]) if v else 0
    except Exception:
        return 0


def verifier_version(conn) -> str | None:
    """None si tout va bien ; sinon message pour l'utilisateur (base créée
    par une version plus récente du logiciel)."""
    v = version_base(conn)
    if v > VERSION_SCHEMA:
        return (f"Ce dossier a été créé ou mis à jour par une version plus "
                f"récente du logiciel (schéma {v}, ce logiciel gère jusqu'au "
                f"schéma {VERSION_SCHEMA}). Pour éviter toute perte ou "
                "erreur, mettez à jour le logiciel avant de continuer — "
                "aucune donnée n'a été modifiée.")
    return None
