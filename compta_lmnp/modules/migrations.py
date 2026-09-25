# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Migrations versionnées — mise à jour d'une installation SANS toucher aux
données.

Principe (J9) : le code se remplace, les données restent. À chaque
démarrage, chaque dossier est comparé à la version de schéma du logiciel
(init_db.VERSION_SCHEMA, tracée dans la table meta depuis v7.9) :

  - base au niveau      → rien à faire ;
  - base plus ancienne  → SAUVEGARDE « avant-migration » d'abord, puis
    application des paliers manquants (idempotents), puis marquage ;
  - base plus récente   → on ne touche à RIEN (la garde web affiche le
    message pédagogique « mettez à jour le logiciel »).

Les paliers réutilisent les fonctions d'infrastructure existantes (déjà
idempotentes : CREATE TABLE IF NOT EXISTS, ALTER sous try/except) — une
seule source de vérité, pas de SQL dupliqué.
"""
from __future__ import annotations

import sqlite3

import init_db
import perennite


def _palier_2(conn: sqlite3.Connection) -> None:
    """v2 — multi-biens : ventilation du stock 39 C par bien."""
    import fiscal
    fiscal._table_39c_bien(conn)
    try:
        conn.execute("ALTER TABLE suivi_39c_bien ADD COLUMN "
                     "sortie_bien REAL NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass


def _palier_3(conn: sqlite3.Connection) -> None:
    """v3 — cession d'un bien : colonnes de sortie et comptes 675/775."""
    import cession
    cession.assurer_schema(conn)


def _palier_4(conn: sqlite3.Connection) -> None:
    """v4 — index de performance (aucun n'existait auparavant)."""
    init_db.creer_index(conn)


def _palier_5(conn: sqlite3.Connection) -> None:
    """v5 — annulation d'opération par contre-passation (colonne annulee)."""
    import operations
    operations.assurer_colonne_annulee(conn)


def _palier_6(conn: sqlite3.Connection) -> None:
    """v6 — quittances de loyer (tables locataire et quittance)."""
    import quittances
    quittances.assurer_schema(conn)


def _palier_7(conn: sqlite3.Connection) -> None:
    """v7 — comptes absents du plan livré (passe E, constat E-10).

    Un dossier créé avant cette version n'a ni dette financière, ni compte
    de dépôt de garantie : les gabarits qui les visent échoueraient sur la
    clé étrangère `compte(numero)` au moment de la saisie, c'est-à-dire
    chez l'utilisateur et pas ici. Les comptes sont donc créés sur les
    bases existantes, à l'identique du seed livré.

    INSERT OR IGNORE : le palier est rejouable, et il ne touche pas un
    compte que l'utilisateur aurait créé lui-même sous le même numéro.
    """
    conn.executemany(
        "INSERT OR IGNORE INTO compte (numero, libelle, type, classe) "
        "VALUES (?,?,?,?)",
        [("164000", "Emprunts auprès des établissements de crédit", "passif", 1),
         ("165000", "Dépôts et cautionnements reçus", "passif", 1),
         ("401000", "Fournisseurs", "passif", 4),
         ("411000", "Locataires", "actif", 4),
         ("758000", "Produits divers de gestion courante", "produit", 7)])


def _palier_8(conn: sqlite3.Connection) -> None:
    """v8 — le justificatif de loyer conserve son identité (passe P).

    Ajoute à `quittance` le type de document (reçu partiel / quittance) et
    les champs figés à l'émission : nom du locataire, adresse du logement,
    identité du bailleur, montant dû. Sans eux, un document déjà remis
    était reconstruit par jointure sur le référentiel COURANT — corriger un
    nom réécrivait rétroactivement tous les justificatifs de ce locataire,
    sous leurs numéros d'origine.

    `assurer_schema` est idempotent et connaît les colonnes à ajouter.
    """
    import quittances
    quittances.assurer_schema(conn)


def _palier_9(conn: sqlite3.Connection) -> None:
    """v9 — suivi des dépôts de déclaration (table depot_declaration).

    Aucune donnée existante n'est touchée : la table naît vide.
    """
    import depots
    depots.assurer_schema(conn)


def _palier_10(conn: sqlite3.Connection) -> None:
    """v10 — charges récurrentes : modèles et tables du moteur d'échéances.

    Aucune donnée existante n'est touchée : les tables naissent vides.
    """
    import recurrentes
    recurrentes.assurer_schema(conn)


PALIERS = {2: _palier_2, 3: _palier_3, 4: _palier_4, 5: _palier_5,
           6: _palier_6, 7: _palier_7, 8: _palier_8, 9: _palier_9,
           10: _palier_10}

# Garde-fou de développement. La boucle de `migrer` ignorait silencieusement
# un palier absent, puis marquait la base au niveau du logiciel : une base
# à laquelle il manque une table se déclarait à jour, n'était plus jamais
# examinée, et l'erreur ne se manifestait qu'à la première requête sur le
# schéma manquant — à une date arbitraire, sans lien apparent avec la mise
# à jour. Cette assertion fait échouer la suite de tests dès qu'on relève
# VERSION_SCHEMA sans écrire le palier correspondant.
assert set(PALIERS) == set(range(2, init_db.VERSION_SCHEMA + 1)), (
    f"Paliers de migration incomplets : {sorted(PALIERS)} pour un schéma "
    f"en version {init_db.VERSION_SCHEMA}. Ajoutez le palier manquant — "
    "sans lui, la base serait marquée à jour sans l'être.")


def migrer(db_path: str) -> dict:
    """Met une base au niveau du logiciel. Retourne
    {"avant": v, "apres": v, "sauvegarde": chemin|None}."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        avant = init_db.version_base(conn)
        if avant >= init_db.VERSION_SCHEMA:
            return {"avant": avant, "apres": avant, "sauvegarde": None}
        sauvegarde = perennite.sauvegarder(db_path, "avant-migration")
        for palier in range(max(avant, 1) + 1, init_db.VERSION_SCHEMA + 1):
            fn = PALIERS.get(palier)
            if fn:
                fn(conn)
        init_db.marquer_version(conn)
        conn.commit()
        return {"avant": avant, "apres": init_db.VERSION_SCHEMA,
                "sauvegarde": sauvegarde}
    finally:
        conn.close()


def migrer_tous(chemins: list[str]) -> list[dict]:
    """Migre tous les dossiers du registre (appelé au démarrage). Une base
    qui échoue n'empêche pas les autres — l'erreur est rapportée."""
    resultats = []
    for chemin in chemins:
        try:
            r = migrer(chemin)
            r["chemin"] = chemin
            resultats.append(r)
        except Exception as exc:            # noqa: BLE001 — rapport démarrage
            resultats.append({"chemin": chemin, "erreur": str(exc)})
    return resultats
