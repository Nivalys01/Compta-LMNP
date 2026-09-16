# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Gabarits de saisie : chaque type d'opération sait quel compte de résultat il
mouvemente, dans quel sens, et ses attributs métier (périodicité attendue,
seuil d'immobilisation, retraitement fiscal…). La contrepartie est TOUJOURS
le compte courant de l'exploitant 108000 (compta de caisse, conventions des offres payantes).

Deux sources, fusionnées par `tous(conn)` :
  1. GABARITS (code) — inventaire des articles constatés dans les exercices
     2023-2025 (FEC + liasses de référence) et des charges officiellement déductibles
     en LMNP au réel ;
  2. table `gabarit_personnalise` — extensible SANS toucher au code, pour
     accueillir une catégorie créée par une disposition future (menu
     « Réglementation »).

Attributs :
  nature       : 'produit' (108000 débité) ou 'charge' (108000 crédité)
  periodicite  : 'mensuel' | 'annuel' | 'variable' (contrôle de complétude)
  groupe       : rubrique du menu déroulant de saisie
  seuil_immo   : drapeau — le contrôle propose l’immobilisation au-delà de
                 la règle versionnée « seuil_immobilisation »
  requalifier  : le contrôle demande une requalification (fourre-tout)
  retraitement : 'reintegration' → montant réintégré fiscalement à la clôture
                 (ex. fonds travaux ALUR : provision, non déductible)
"""
from __future__ import annotations

import sqlite3

COMPTE_CONTREPARTIE = "108000"   # Exploitant

GABARITS = {
    # ── Produits ─────────────────────────────────────────────────────────────
    "loyer":                 {"compte": "708810", "nature": "produit", "periodicite": "mensuel",
                              "groupe": "Produits", "libelle": "Loyer hors charges locatives"},
    "charges_locatives":     {"compte": "708810", "nature": "produit", "periodicite": "mensuel",
                              "groupe": "Produits", "libelle": "Provision pour charges"},
    "forfait_charges":       {"compte": "708810", "nature": "produit", "periodicite": "mensuel",
                              "groupe": "Produits", "libelle": "Forfait pour charges"},
    "regularisation_charges":{"compte": "708810", "nature": "produit", "periodicite": "variable",
                              "groupe": "Produits", "libelle": "Régularisation de charges locatives"},
    # Régularisation en faveur du LOCATAIRE. Elle DÉBITE le compte de
    # produit, ce qui en diminue le solde : nature « charge » pour que
    # l'écriture parte dans le bon sens, compte inchangé pour que les
    # agrégats — qui raisonnent par CLASSE de compte — nettent d'eux-mêmes.
    # Sans cette nature, une restitution était impossible à saisir : les
    # montants sont strictement positifs partout, et c'est cette règle qui
    # protège des saisies inversées (signalé en revue du catalogue).
    "restitution_charges":   {"compte": "708810", "nature": "charge", "periodicite": "variable",
                              "groupe": "Produits", "libelle": "Restitution de charges au locataire"},
    "indemnite_assurance":   {"compte": "758000", "nature": "produit", "periodicite": "variable",
                              "groupe": "Produits", "libelle": "Indemnité d'assurance / produit divers"},
    "autres_produits":       {"compte": "708810", "nature": "produit", "periodicite": "variable",
                              "groupe": "Produits", "libelle": "Autres produits de location"},

    # ── Dépôts & emprunts (mouvements de BILAN, hors résultat) ──────────────
    #    Ces gabarits mouvementent des comptes de classe 1 : fiscal.py agrège
    #    le résultat par CLASSE (6 et 7), ils en sont donc exclus d'office.
    #    C'est tout l'objet du constat E-10 — sans ces comptes, un dépôt de
    #    garantie devenait un loyer imposable et un remboursement de capital
    #    une charge déductible.
    "depot_garantie_recu":   {"compte": "165000", "nature": "produit", "periodicite": "variable",
                              "groupe": "Dépôts & emprunts",
                              "libelle": "Dépôt de garantie reçu (dette — non imposable)"},
    "depot_garantie_restitue": {"compte": "165000", "nature": "charge", "periodicite": "variable",
                              "groupe": "Dépôts & emprunts",
                              "libelle": "Dépôt de garantie restitué (extinction de dette)"},
    "emprunt_recu":          {"compte": "164000", "nature": "produit", "periodicite": "variable",
                              "groupe": "Dépôts & emprunts",
                              "libelle": "Déblocage d'emprunt reçu (dette — non imposable)"},
    "emprunt_capital_rembourse": {"compte": "164000", "nature": "charge", "periodicite": "variable",
                              "groupe": "Dépôts & emprunts",
                              "libelle": "Remboursement d'emprunt — CAPITAL (non déductible)"},

    # ── Copropriété ─────────────────────────────────────────────────────────
    "charge_copro":          {"compte": "614100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Copropriété", "libelle": "Charges locatives et de copropriété"},
    "fonds_travaux_alur":    {"compte": "614100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Copropriété", "libelle": "Fonds travaux ALUR",
                              "retraitement": "reintegration"},

    # ── Abonnements & énergie ───────────────────────────────────────────────
    "telecom":               {"compte": "626210", "nature": "charge", "periodicite": "variable",
                              "groupe": "Abonnements & énergie", "libelle": "Internet / Télécoms"},
    "energie":               {"compte": "606100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Abonnements & énergie", "libelle": "Énergie (électricité, gaz)"},

    # ── Assurances ──────────────────────────────────────────────────────────
    "assurance":             {"compte": "616110", "nature": "charge", "periodicite": "variable",
                              "groupe": "Assurances", "libelle": "Assurance habitation PNO"},
    "assurance_emprunteur":  {"compte": "616110", "nature": "charge", "periodicite": "variable",
                              "groupe": "Assurances", "libelle": "Assurance emprunteur"},
    "assurance_gli":         {"compte": "616110", "nature": "charge", "periodicite": "variable",
                              "groupe": "Assurances", "libelle": "Garantie loyers impayés (GLI)"},

    # ── Entretien & équipement ──────────────────────────────────────────────
    "maintenance":           {"compte": "615200", "nature": "charge", "periodicite": "variable",
                              "groupe": "Entretien & équipement", "libelle": "Entretien et réparations"},
    "petit_equipement":      {"compte": "606320", "nature": "charge", "periodicite": "variable",
                              "groupe": "Entretien & équipement", "libelle": "Petit équipement",
                              "seuil_immo": True},  # → règle versionnée
    "electromenager":        {"compte": "606320", "nature": "charge", "periodicite": "variable",
                              "groupe": "Entretien & équipement", "libelle": "Électroménager",
                              "seuil_immo": True},  # → règle versionnée
    "autres_equipements":    {"compte": "606320", "nature": "charge", "periodicite": "variable",
                              "groupe": "Entretien & équipement", "libelle": "Autres équipements",
                              "seuil_immo": True},  # → règle versionnée
    "fournitures":           {"compte": "606400", "nature": "charge", "periodicite": "variable",
                              "groupe": "Entretien & équipement", "libelle": "Fournitures administratives"},

    # ── Emprunt & banque ────────────────────────────────────────────────────
    "interets_emprunt":      {"compte": "661100", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Emprunt & banque", "libelle": "Intérêts d'emprunt"},
    "frais_dossier_emprunt": {"compte": "627810", "nature": "charge", "periodicite": "variable",
                              "groupe": "Emprunt & banque", "libelle": "Frais de dossier / garantie emprunt"},
    "frais_bancaires":       {"compte": "627810", "nature": "charge", "periodicite": "variable",
                              "groupe": "Emprunt & banque", "libelle": "Frais de tenue de compte"},

    # ── Honoraires & gestion ────────────────────────────────────────────────
    "honoraires":            {"compte": "622610", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion", "libelle": "Frais de comptabilité"},
    "gestion_locative":      {"compte": "622800", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion", "libelle": "Frais de gestion locative / agence"},
    "honoraires_juridiques": {"compte": "622700", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion", "libelle": "Honoraires juridiques / actes / contentieux"},
    "frais_acquisition":     {"compte": "622700", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion",
                              "libelle": "Frais d'acquisition (option charges : notaire, mutation)"},
    "publicite_annonces":    {"compte": "623100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion", "libelle": "Annonces et publicité de location"},
    "cotisations_pro":       {"compte": "628100", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Honoraires & gestion", "libelle": "Cotisations professionnelles"},
    "frais_postaux":         {"compte": "626100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion", "libelle": "Frais postaux"},

    # ── Déplacements ────────────────────────────────────────────────────────
    "carburant":             {"compte": "606200", "nature": "charge", "periodicite": "variable",
                              "groupe": "Déplacements", "libelle": "Carburant (barème / réel)"},
    "peage_parking":         {"compte": "625100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Déplacements", "libelle": "Péage / parking"},
    "deplacements":          {"compte": "625100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Déplacements", "libelle": "Voyages et déplacements"},

    # ── Impôts & taxes ──────────────────────────────────────────────────────
    "cfe":                   {"compte": "635110", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Impôts & taxes", "libelle": "Cotisation Foncière des Entreprises (CFE)"},
    "taxe_fonciere":         {"compte": "635130", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Impôts & taxes", "libelle": "Taxe foncière (hors TEOM récupérable)"},
    "teom":                  {"compte": "635130", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Impôts & taxes", "libelle": "Taxe d'enlèvement des ordures ménagères (TEOM)"},
    "impot_local":           {"compte": "635130", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Impôts & taxes", "libelle": "Autres impôts locaux"},

    # ── Divers ──────────────────────────────────────────────────────────────
    "autres_charges":        {"compte": "628800", "nature": "charge", "periodicite": "variable",
                              "groupe": "Divers", "libelle": "Autres charges (à requalifier)",
                              "requalifier": True},

    # ── Attente ─────────────────────────────────────────────────────────────
    #    628800 est une charge IMMÉDIATEMENT DÉDUCTIBLE : y ranger une ligne
    #    non reconnue « signale » le doute sans rien empêcher. 472000 est un
    #    compte d'attente, et controles.py refuse BLOQUANTE une liasse dont
    #    le solde n'est pas apuré : le doute empêche alors de déclarer faux.
    "attente_encaissement":  {"compte": "472000", "nature": "produit", "periodicite": "variable",
                              "groupe": "Attente",
                              "libelle": "Encaissement à identifier (bloque la liasse)",
                              "requalifier": True},
    "attente_decaissement":  {"compte": "472000", "nature": "charge", "periodicite": "variable",
                              "groupe": "Attente",
                              "libelle": "Décaissement à identifier (bloque la liasse)",
                              "requalifier": True},
}

ORDRE_GROUPES = ["Produits", "Dépôts & emprunts", "Copropriété",
                 "Abonnements & énergie", "Assurances",
                 "Entretien & équipement", "Emprunt & banque", "Honoraires & gestion",
                 "Déplacements", "Impôts & taxes", "Divers", "Attente", "Personnalisé"]


# ── Gabarits personnalisés (table) ───────────────────────────────────────────

def assurer_table(conn: sqlite3.Connection) -> None:
    """Crée la table des gabarits personnalisés si elle manque.

    NE COMMITTE PAS quand une transaction est déjà ouverte. Elle committait
    inconditionnellement, et comme `gabarit()` — appelée à CHAQUE saisie —
    passe par `_personnalises()`, qui passe par ici, tout appelant travaillant
    en `commit=False` voyait sa transaction terminée en douce sous ses pieds.
    Observé sur la validation d'un import : la deuxième saisie committait la
    première, si bien qu'un `rollback` n'annulait plus que la dernière ligne
    — exactement l'inverse du tout-ou-rien recherché (constat D2-08).

    Le `CREATE TABLE IF NOT EXISTS` est transactionnel en SQLite : il peut
    voyager dans la transaction de l'appelant sans dommage.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS gabarit_personnalise ("
        "  cle          TEXT PRIMARY KEY,"
        "  libelle      TEXT NOT NULL,"
        "  compte_num   TEXT NOT NULL REFERENCES compte(numero),"
        "  nature       TEXT NOT NULL CHECK (nature IN ('produit','charge')),"
        "  periodicite  TEXT NOT NULL DEFAULT 'variable'"
        "               CHECK (periodicite IN ('mensuel','annuel','variable')),"
        "  retraitement TEXT,"
        "  actif        INTEGER NOT NULL DEFAULT 1)")
    if not conn.in_transaction:
        conn.commit()


def ajouter_personnalise(conn: sqlite3.Connection, *, cle: str, libelle: str,
                         compte_num: str, nature: str,
                         periodicite: str = "variable",
                         retraitement: str | None = None) -> None:
    """Nouvelle catégorie d'opération (disposition future) — sans toucher au code."""
    deja_en_transaction = conn.in_transaction
    assurer_table(conn)
    cle = cle.strip().lower().replace(" ", "_")
    if not cle:
        raise ValueError("Clé de gabarit vide.")
    if cle in GABARITS:
        raise ValueError(f"La clé {cle!r} existe déjà dans les gabarits standard.")
    ok = conn.execute("SELECT COUNT(*) FROM compte WHERE numero=?",
                      (compte_num,)).fetchone()[0]
    if not ok:
        raise ValueError(f"Compte {compte_num} absent du plan de comptes — "
                         "créez-le d'abord (menu Réglementation).")
    conn.execute(
        "INSERT INTO gabarit_personnalise (cle, libelle, compte_num, nature, "
        "periodicite, retraitement) VALUES (?,?,?,?,?,?)",
        (cle, libelle, compte_num, nature, periodicite, retraitement))
    # Ne committer QUE si l'appelant n'avait pas sa propre transaction —
    # même précaution que `assurer_table` et que les lecteurs de règles
    # (constat D2-08). Un `commit()` inconditionnel validait au passage tout
    # ce que l'appelant avait écrit sans le vouloir : un loyer de 800 €
    # saisi en `commit=False` survivait au rollback qui suivait, parce
    # qu'un gabarit avait été créé entre-temps sur la même connexion.
    if not deja_en_transaction:
        conn.commit()


def _personnalises(conn: sqlite3.Connection) -> dict:
    assurer_table(conn)
    rows = conn.execute(
        "SELECT cle, libelle, compte_num, nature, periodicite, retraitement "
        "FROM gabarit_personnalise WHERE actif=1").fetchall()
    out = {}
    for cle, lib, compte, nature, per, retr in rows:
        g = {"compte": compte, "nature": nature, "periodicite": per,
             "groupe": "Personnalisé", "libelle": lib}
        if retr:
            g["retraitement"] = retr
        out[cle] = g
    return out


# ── API ──────────────────────────────────────────────────────────────────────

def tous(conn: sqlite3.Connection | None = None) -> dict:
    """Gabarits standard + personnalisés actifs (si une connexion est fournie)."""
    fusion = dict(GABARITS)
    if conn is not None:
        fusion.update(_personnalises(conn))
    return fusion


def gabarit(type_op: str, conn: sqlite3.Connection | None = None) -> dict:
    g = tous(conn)
    if type_op not in g:
        raise ValueError(f"Type d'opération inconnu : {type_op!r}. "
                         f"Connus : {', '.join(sorted(g))}")
    return g[type_op]


def grouper(g: dict) -> list[tuple[str, list]]:
    """Regroupe un catalogue DÉJÀ CHARGÉ. Fonction pure, sans connexion.

    `par_groupe(conn)` relisait le catalogue pour son propre compte, alors
    que son appelant venait de le charger : une page de saisie lisait ainsi
    trois fois la même table (constat T-09). La lecture et le regroupement
    sont désormais deux gestes distincts, et l'appelant choisit.
    """
    groupes: dict[str, list] = {}
    for cle, gab in g.items():
        groupes.setdefault(gab.get("groupe", "Divers"), []).append((cle, gab))
    ordre = ORDRE_GROUPES + [x for x in groupes if x not in ORDRE_GROUPES]
    return [(grp, sorted(groupes[grp], key=lambda kv: kv[1]["libelle"]))
            for grp in ordre if grp in groupes]


def par_groupe(conn: sqlite3.Connection | None = None) -> list[tuple[str, list]]:
    """[(groupe, [(cle, gabarit), …]), …] dans l'ordre d'affichage."""
    return grouper(tous(conn))
