# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Insertion d'écritures en partie double — point de passage UNIQUE.

Toutes les créations d'écritures (saisie, acquisitions, à-nouveaux,
affectation du résultat, injections des audits) passent par `inserer()`, qui
garantit les invariants du FEC A47 A-1 :

  - numérotation séquentielle par exercice (sauf numéro imposé) ;
  - PieceDate et ValidDate alignées sur la date d'écriture ;
  - équilibre débit/crédit vérifié AVANT insertion (rejet au centime),
    désactivable uniquement pour les injections d'anomalies volontaires
    des audits (verifier_equilibre=False).
"""
from __future__ import annotations

import math
import sqlite3

TOL = 0.005

# Caractères interdits dans tout champ texte : ils casseraient la structure
# du FEC (fichier tabulé, une écriture-ligne par ligne physique). Un libellé
# collé depuis un tableur ou un mail peut en contenir sans qu'on le voie.
_CARS_INTERDITS = ("\t", "\n", "\r")


def _sans_cars_interdits(valeur: str, ou: str) -> None:
    for car in _CARS_INTERDITS:
        if car in (valeur or ""):
            nom = {"\t": "une tabulation", "\n": "un saut de ligne",
                   "\r": "un retour chariot"}[car]
            raise ValueError(f"{ou} contient {nom} — caractère interdit "
                             "dans un FEC (il en casserait la structure). "
                             "Retirez-le (souvent un copier-coller depuis un "
                             "tableur ou un e-mail).")


def _verifier_conformite_fec(conn: sqlite3.Connection, *, journal: str,
                             date: str, annee: int, libelle: str,
                             piece_ref: str,
                             lignes: list) -> None:
    """
    Conformité par construction : rejette AVANT insertion toute écriture qui
    rendrait le FEC non conforme (art. A47 A-1). Chaque règle ici a son miroir
    dans valider_fec.py — le guichet garantit ce que le validateur exige, pour
    qu'un FEC produit par le logiciel soit conforme par construction et non
    par vérification a posteriori.
    """
    # 1. Colonnes obligatoires non vides (EcritureLib, PieceRef, JournalCode).
    #    Un champ réduit à des espaces est vide au sens DGFiP.
    if not (libelle or "").strip():
        raise ValueError("Le libellé de l'écriture est obligatoire "
                         "(colonne EcritureLib du FEC).")
    if not (piece_ref or "").strip():
        raise ValueError("La référence de pièce est obligatoire "
                         "(colonne PieceRef du FEC).")
    if not (journal or "").strip():
        raise ValueError("Le code journal est obligatoire.")

    # 2. Date d'écriture : format AAAA-MM-JJ réel ET dans l'exercice déclaré.
    try:
        an, mois, jour = (date or "").split("-")
        annee_date = int(an)
        import datetime
        datetime.date(annee_date, int(mois), int(jour))
    except (ValueError, AttributeError):
        raise ValueError(f"Date d'écriture invalide : {date!r} "
                         "(format attendu AAAA-MM-JJ).") from None
    if annee_date != annee:
        raise ValueError(f"La date d'écriture ({date}) est hors de l'exercice "
                         f"{annee} : une écriture doit être datée dans son "
                         "propre exercice (cohérence FEC).")

    # 3. Partie double : au moins deux lignes (une seule romprait la partie
    #    double, contrôle DGFiP « écriture à une seule ligne »).
    if len(lignes) < 2:
        raise ValueError("Une écriture comptable doit comporter au moins deux "
                         "lignes (partie double).")

    # 4. Aucun caractère de structure dans les champs texte libres.
    _sans_cars_interdits(libelle, "Le libellé de l'écriture")
    _sans_cars_interdits(piece_ref, "La référence de pièce")
    for lg in lignes:
        lib_ligne = lg[3] if len(lg) > 3 else ""
        _sans_cars_interdits(lib_ligne, f"Le libellé de la ligne {lg[0]}")


def prochain_num(conn: sqlite3.Connection, annee: int) -> int:
    return conn.execute(
        "SELECT COALESCE(MAX(ecriture_num),0)+1 FROM ecriture WHERE exercice_annee=?",
        (annee,)).fetchone()[0]


def inserer(conn: sqlite3.Connection, *, journal: str, date: str, annee: int,
            libelle: str, lignes: list[tuple[str, float, float]],
            piece_ref: str = "NA", num: int | None = None,
            verifier_equilibre: bool = True, verifier_conformite: bool = True,
            commit: bool = True) -> dict:
    """
    Insère une écriture et ses lignes [(compte, débit, crédit[, libellé]), …]
    — le libellé de ligne, optionnel, remplace celui de l'écriture.
    Renvoie {'ecriture_id', 'ecriture_num'}.
    """
    lignes = [(lg[0], lg[1], lg[2], lg[3] if len(lg) > 3 else libelle)
              for lg in lignes]
    if not lignes:
        raise ValueError("Écriture sans ligne.")
    for cpt, d, c, _l in lignes:
        # NaN/inf traversent les comparaisons d'équilibre (nan > TOL est faux)
        # et corrompraient le FEC : rejet inconditionnel, même pour les
        # injections d'anomalies volontaires (verifier_equilibre=False).
        if not (math.isfinite(d) and math.isfinite(c)):
            raise ValueError(f"Montant non fini sur le compte {cpt} : "
                             f"débit {d!r} / crédit {c!r}.")
    total_d = round(sum(d for _, d, _c, _l in lignes), 2)
    total_c = round(sum(c for _, _d, c, _l in lignes), 2)
    if verifier_equilibre and abs(total_d - total_c) > TOL:
        raise ValueError(f"Écriture déséquilibrée : débit {total_d:.2f} € / "
                         f"crédit {total_c:.2f} €.")

    # Conformité FEC par construction : toute écriture acceptée ici produit un
    # FEC conforme (règles miroir de valider_fec.py). verifier_conformite est
    # désactivable UNIQUEMENT pour les injections d'anomalies volontaires des
    # tests d'audit (comme verifier_equilibre).
    if verifier_conformite:
        _verifier_conformite_fec(conn, journal=journal, date=date, annee=annee,
                                 libelle=libelle, piece_ref=piece_ref,
                                 lignes=lignes)

    # Un exercice CLOS est scellé : son résultat est figé et son FEC archivé.
    # Rien ne détecterait une écriture ajoutée après coup (les contrôles
    # tournent AVANT clôture) — rejet dur, sans exception ni contournement.
    ex = conn.execute("SELECT statut FROM exercice WHERE annee=?",
                      (annee,)).fetchone()
    if ex is None:
        raise ValueError(f"Exercice {annee} inconnu — ouvrez-le d'abord "
                         "(menu « Nouvel exercice »).")
    if ex[0] == "clos":
        raise ValueError(f"L'exercice {annee} est clos : aucune écriture ne "
                         "peut plus y être ajoutée.")

    num_auto = num is None
    cur = conn.cursor()
    # SAVEPOINT : si l'insertion des lignes échoue (compte inconnu, montant
    # négatif rejeté par la base…), l'en-tête déjà inséré est annulé avec
    # elles. Sans cela, un commit ultérieur sans rapport figerait une
    # écriture SANS LIGNE — un trou dans la numérotation séquentielle du FEC.
    # ATTENTION (piège SQLite) : le RELEASE d'un savepoint le plus externe
    # vaut COMMIT s'il n'existe pas de transaction englobante — ce qui
    # briserait le contrat commit=False (l'appelant, ex. la clôture, compte
    # sur un commit UNIQUE final pour être atomique face à une coupure).
    # On ouvre donc explicitement la transaction avant le savepoint.
    if not conn.in_transaction:
        # IMMEDIATE (et non deferred) : une transaction qui LIT (prochain_num)
        # puis ÉCRIT part en « database is locked » IMMÉDIAT si un autre
        # écrivain s'est intercalé — l'upgrade de verrou n'attend jamais
        # (détection d'interblocage SQLite, le busy_timeout ne s'applique
        # pas). BEGIN IMMEDIATE prend le verrou d'écriture d'emblée : les
        # écrivains simultanés se sérialisent en attendant leur tour.
        cur.execute("BEGIN IMMEDIATE")
        debutee_ici = True
    else:
        debutee_ici = False
    # Rejeu borné : deux saisies simultanées (deux onglets, deux instances)
    # peuvent calculer le même numéro d'écriture ; la contrainte UNIQUE en
    # rejette une. Quand le numéro était AUTO-attribué, on recalcule et on
    # réessaie (5 tentatives) — jamais quand l'appelant l'a imposé.
    # Piège d'isolation SQLite : notre transaction lit un INSTANTANÉ — sans
    # rollback, prochain_num() relirait le même numéro et re-collisionnerait
    # à l'infini. En mode autonome (transaction ouverte ici, commit=True),
    # on repart donc d'une transaction fraîche entre deux tentatives.
    for tentative in range(5):
        if num_auto:
            num = prochain_num(conn, annee)
        cur.execute("SAVEPOINT ecr_inserer")
        try:
            cur.execute(
                "INSERT INTO ecriture (journal_code, ecriture_num, ecriture_date, "
                "exercice_annee, piece_ref, piece_date, libelle, valid_date) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (journal, num, date, annee, piece_ref, date, libelle, date))
            eid = cur.lastrowid
            cur.executemany(
                "INSERT INTO ligne (ecriture_id, compte_num, libelle, debit, credit) "
                "VALUES (?,?,?,?,?)",
                [(eid, compte, lib_ligne, round(d, 2), round(c, 2))
                 for compte, d, c, lib_ligne in lignes])
        except sqlite3.IntegrityError as exc:
            cur.execute("ROLLBACK TO SAVEPOINT ecr_inserer")
            cur.execute("RELEASE SAVEPOINT ecr_inserer")
            collision = "ecriture_num" in str(exc)
            if num_auto and collision and tentative < 4:
                if debutee_ici and commit:
                    conn.rollback()          # instantané rafraîchi
                    cur.execute("BEGIN IMMEDIATE")
                continue                      # numéro pris entre-temps : rejeu
            raise
        except Exception:
            cur.execute("ROLLBACK TO SAVEPOINT ecr_inserer")
            cur.execute("RELEASE SAVEPOINT ecr_inserer")
            raise
        cur.execute("RELEASE SAVEPOINT ecr_inserer")
        break
    if commit:
        conn.commit()
    return {"ecriture_id": eid, "ecriture_num": num}
