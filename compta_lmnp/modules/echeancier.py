# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Moteur de génération d'échéances — aperçu, puis génération en lot.

Brique GÉNÉRIQUE : elle ne sait rien des charges récurrentes ni des
emprunts. Une SOURCE (aujourd'hui `recurrentes`, demain les emprunts) lui
remet des `Echeance` — une date, un bien, une ou plusieurs opérations à
saisir — et le moteur garantit le reste :

  - APERÇU sans écriture : un statut par échéance (à générer, déjà
    générée, écartée, à venir, ignorée avec motif) et les doublons
    probables avec des opérations déjà saisies ;
  - GÉNÉRATION ATOMIQUE : tout le lot en une transaction, par le guichet
    `operations.saisir` → `ecritures.inserer`. Une ligne en échec annule le
    lot, et le message dit laquelle ;
  - IDEMPOTENCE PAR LA BASE : chaque échéance générée est inscrite dans
    `echeance_generee`, unique par (source, identifiant, date). Rejouer ne
    crée rien ; une opération annulée par contre-passation existe toujours,
    son échéance n'est donc pas régénérée.

Seules les échéances ÉCHUES se génèrent : le logiciel suit la comptabilité
super-simplifiée (trésorerie en cours d'exercice, CGI art. 302 septies
A ter A) — une opération est un paiement EFFECTUÉ. Générer d'avance
inscrirait des charges qui n'ont pas été payées.

Génération à la demande uniquement : rien ici n'est appelé au démarrage ni
en tâche de fond.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

A_GENERER = "a_generer"
DEJA_GENEREE = "deja_generee"
ECARTEE = "ecartee"
A_VENIR = "a_venir"
IGNOREE = "ignoree"

LIBELLES_STATUT = {
    A_GENERER: "à générer", DEJA_GENEREE: "déjà générée",
    ECARTEE: "écartée", A_VENIR: "à venir", IGNOREE: "ignorée",
}

# Fenêtre de recherche des doublons probables : un prélèvement décalé par un
# week-end suivi d'un jour férié, plus le délai de traitement bancaire, sans
# jamais rapprocher deux mensualités (28 jours d'écart au moins).
FENETRE_DOUBLON_JOURS = 7


def _aujourd_hui() -> date:
    """Horloge du moteur — remplacée dans les tests (web et CLI compris)."""
    return date.today()


@dataclass
class Echeance:
    """Ce qu'une source demande de générer à une date."""
    source: str
    source_id: int
    date: date
    bien_id: int | None
    libelle: str
    # Chaque opération : {type, montant, libelle?, periode?, tiers?, piece_ref?}
    operations: list[dict]
    # Motif d'écart déjà connu de la source (modèle suspendu, hors bornes…).
    motif_source: str | None = None
    # Mises en garde propres à la source, affichées sans bloquer.
    alertes: list[str] = field(default_factory=list)

    @property
    def cle(self) -> str:
        return cle(self.source, self.source_id, self.date)


def cle(source: str, source_id: int, jour: date) -> str:
    return f"{source}:{source_id}:{jour.isoformat()}"


def lire_cle(valeur: str) -> tuple[str, int, date]:
    try:
        source, sid, jour = valeur.split(":")
        return source, int(sid), date.fromisoformat(jour)
    except (ValueError, AttributeError):
        raise ValueError(f"Référence d'échéance invalide : « {valeur} ».") from None


@dataclass
class Ligne:
    """Une échéance et son verdict."""
    echeance: Echeance
    statut: str
    motif: str | None = None
    operations_liees: list[dict] = field(default_factory=list)
    doublons: list[dict] = field(default_factory=list)

    @property
    def cle(self) -> str:
        return self.echeance.cle

    @property
    def cochee_par_defaut(self) -> bool:
        # Un doublon probable n'est pas bloqué, mais il n'est pas proposé
        # d'office : c'est à l'utilisateur de le retenir en connaissance
        # de cause.
        return self.statut == A_GENERER and not self.doublons


class LotAnnule(Exception):
    """Une échéance du lot a échoué : rien n'a été enregistré."""

    def __init__(self, echeance: Echeance, cause: Exception):
        self.echeance, self.cause = echeance, cause
        super().__init__(
            f"Génération annulée, aucune opération n'a été créée. L'échéance "
            f"du {echeance.date.strftime('%d/%m/%Y')} — {echeance.libelle} "
            f"({echeance.source} n° {echeance.source_id}) a échoué : {cause}")


# ── Schéma ───────────────────────────────────────────────────────────────

def assurer_schema(conn: sqlite3.Connection) -> None:
    """Tables de lien (palier de migration 10). Idempotent, sans commit :
    la DDL hors transaction est validée d'elle-même, et un commit ici
    validerait en silence la transaction d'un appelant."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS echeance_generee ("
        " id            INTEGER PRIMARY KEY,"
        " source        TEXT    NOT NULL,"
        " source_id     INTEGER NOT NULL,"
        " date_echeance TEXT    NOT NULL,"
        " etat          TEXT    NOT NULL CHECK (etat IN ('generee','ecartee')),"
        " genere_le     TEXT    NOT NULL,"
        " UNIQUE (source, source_id, date_echeance))")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS echeance_operation ("
        " echeance_id  INTEGER NOT NULL REFERENCES echeance_generee(id),"
        " operation_id INTEGER NOT NULL UNIQUE REFERENCES operation(id),"
        " PRIMARY KEY (echeance_id, operation_id))")


# ── Aperçu ───────────────────────────────────────────────────────────────

def _exercices(conn) -> dict[int, tuple[str, date, date]]:
    return {a: (s, date.fromisoformat(d), date.fromisoformat(f))
            for a, s, d, f in conn.execute(
                "SELECT annee, statut, date_debut, date_fin FROM exercice")}


def _cessions(conn) -> dict[int, date]:
    try:
        rows = conn.execute("SELECT id, date_cession FROM bien "
                            "WHERE date_cession IS NOT NULL AND date_cession<>''")
    except sqlite3.OperationalError:            # base sans colonne de cession
        return {}
    return {b: date.fromisoformat(d) for b, d in rows}


def _existantes(conn) -> dict[str, tuple[int, str]]:
    return {cle(s, i, date.fromisoformat(d)): (eid, etat)
            for eid, s, i, d, etat in conn.execute(
                "SELECT id, source, source_id, date_echeance, etat "
                "FROM echeance_generee")}


def _operations_liees(conn, echeance_id: int) -> list[dict]:
    return [{"id": o, "date": d, "type": t, "montant": m, "annulee": bool(a)}
            for o, d, t, m, a in conn.execute(
                "SELECT o.id, o.date_operation, o.type, o.montant, "
                "COALESCE(o.annulee,0) FROM echeance_operation eo "
                "JOIN operation o ON o.id = eo.operation_id "
                "WHERE eo.echeance_id=? ORDER BY o.id", (echeance_id,))]


def doublons_probables(conn, e: Echeance) -> list[dict]:
    """Opérations déjà saisies qui ressemblent à celles de l'échéance :
    même compte, même bien, même montant au centime, non annulées, à
    ± FENETRE_DOUBLON_JOURS jours.

    Le bien n'est PAS comparé pour une opération importée d'un relevé :
    l'import les rattache toutes au premier bien, et le doublon typique —
    la même charge déjà importée — serait sinon invisible sur tout autre
    bien.
    """
    import gabarits
    du = (e.date - timedelta(days=FENETRE_DOUBLON_JOURS)).isoformat()
    au = (e.date + timedelta(days=FENETRE_DOUBLON_JOURS)).isoformat()
    vus, out = set(), []
    for op in e.operations:
        # Catalogue du code d'abord : pas de relecture de la base à chaque
        # ligne d'aperçu (constat T-09) ; la base pour un gabarit personnalisé.
        g = gabarits.GABARITS.get(op["type"]) or gabarits.gabarit(op["type"], conn)
        compte = g["compte"]
        for oid, d, t, m, lib, src in conn.execute(
                "SELECT DISTINCT o.id, o.date_operation, o.type, o.montant, "
                "o.libelle, o.source FROM operation o "
                "JOIN ligne l ON l.ecriture_id = o.ecriture_id "
                "WHERE COALESCE(o.annulee,0)=0 AND l.compte_num=? "
                "AND ROUND(o.montant,2)=ROUND(?,2) "
                "AND (o.bien_id IS ? OR o.source='import') "
                "AND o.date_operation BETWEEN ? AND ? ORDER BY o.date_operation",
                (compte, op["montant"], e.bien_id, du, au)):
            if oid not in vus:
                vus.add(oid)
                out.append({"id": oid, "date": d, "type": t, "montant": m,
                            "libelle": lib, "source": src})
    return out


def apercu(conn: sqlite3.Connection, echeances: list[Echeance], *,
           aujourd_hui: date | None = None) -> list[Ligne]:
    """Statut de chaque échéance, sans rien écrire."""
    import operations
    assurer_schema(conn)
    operations.assurer_colonne_annulee(conn)
    auj = aujourd_hui or _aujourd_hui()
    exercices, cessions, existantes = (_exercices(conn), _cessions(conn),
                                       _existantes(conn))
    lignes = []
    for e in sorted(echeances, key=lambda x: (x.date, x.source, x.source_id)):
        deja = existantes.get(e.cle)
        if deja:
            lignes.append(Ligne(e, DEJA_GENEREE if deja[1] == "generee"
                                else ECARTEE,
                                operations_liees=_operations_liees(conn, deja[0])))
            continue
        motif = e.motif_source
        cession = cessions.get(e.bien_id)
        if motif is None and cession is not None and e.date > cession:
            motif = (f"postérieure à la cession du bien "
                     f"(le {cession.strftime('%d/%m/%Y')})")
        if motif:
            lignes.append(Ligne(e, IGNOREE, motif))
            continue
        if e.date > auj:
            lignes.append(Ligne(e, A_VENIR, "échéance non encore échue"))
            continue
        ex = exercices.get(e.date.year)
        if ex is None:
            motif = f"exercice {e.date.year} inexistant"
        elif ex[0] != "ouvert":
            motif = f"exercice {e.date.year} clôturé"
        elif not ex[1] <= e.date <= ex[2]:
            motif = (f"hors de l'exercice {e.date.year} (du "
                     f"{ex[1].strftime('%d/%m/%Y')} au "
                     f"{ex[2].strftime('%d/%m/%Y')})")
        if motif:
            lignes.append(Ligne(e, IGNOREE, motif))
            continue
        lignes.append(Ligne(e, A_GENERER, doublons=doublons_probables(conn, e)))
    return lignes


# ── Génération ───────────────────────────────────────────────────────────

def generer(conn: sqlite3.Connection, echeances: list[Echeance],
            retenues: set[str], *, ecarter: set[str] = frozenset(),
            aujourd_hui: date | None = None) -> dict:
    """Génère les échéances RETENUES encore « à générer », et consigne comme
    écartées celles de `ecarter`. Tout ou rien.

    L'aperçu est recalculé SOUS LE VERROU d'écriture : entre l'affichage et
    la confirmation, une autre génération a pu passer. Une échéance retenue
    qui n'est plus « à générer » n'est pas créée, et elle est rendue dans
    `non_generees` pour que l'appelant le dise.
    """
    import operations
    maintenant = datetime.now().isoformat(timespec="seconds")
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    creees, ecartees, non_generees = [], [], []
    try:
        lignes = apercu(conn, echeances, aujourd_hui=aujourd_hui)
        for ligne in lignes:
            e = ligne.echeance
            if ligne.cle in ecarter and ligne.statut == A_GENERER:
                conn.execute(
                    "INSERT INTO echeance_generee (source, source_id, "
                    "date_echeance, etat, genere_le) VALUES (?,?,?,'ecartee',?)",
                    (e.source, e.source_id, e.date.isoformat(), maintenant))
                ecartees.append(ligne.cle)
                continue
            if ligne.cle not in retenues:
                continue
            if ligne.statut != A_GENERER:
                non_generees.append(ligne)
                continue
            try:
                eid = conn.execute(
                    "INSERT INTO echeance_generee (source, source_id, "
                    "date_echeance, etat, genere_le) VALUES (?,?,?,'generee',?)",
                    (e.source, e.source_id, e.date.isoformat(),
                     maintenant)).lastrowid
                ops = []
                for op in e.operations:
                    r = operations.saisir(
                        conn, type=op["type"], montant=op["montant"],
                        date_operation=e.date.isoformat(),
                        periode=op.get("periode"), bien_id=e.bien_id,
                        tiers=op.get("tiers") or "", libelle=op.get("libelle"),
                        exercice=e.date.year, piece_ref=op.get("piece_ref"),
                        source=e.source, commit=False)
                    conn.execute("INSERT INTO echeance_operation "
                                 "(echeance_id, operation_id) VALUES (?,?)",
                                 (eid, r["operation_id"]))
                    ops.append(r["operation_id"])
            except Exception as exc:                 # noqa: BLE001
                raise LotAnnule(e, exc) from exc
            creees.append({"cle": ligne.cle, "operations": ops})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"creees": creees, "ecartees": ecartees,
            "non_generees": non_generees,
            "nb_operations": sum(len(c["operations"]) for c in creees)}


def retablir(conn: sqlite3.Connection, valeur_cle: str) -> None:
    """Annule l'écart d'une échéance : elle redevient proposable."""
    source, sid, jour = lire_cle(valeur_cle)
    assurer_schema(conn)
    n = conn.execute(
        "DELETE FROM echeance_generee WHERE source=? AND source_id=? "
        "AND date_echeance=? AND etat='ecartee'",
        (source, sid, jour.isoformat())).rowcount
    if not n:
        conn.rollback()
        raise ValueError("Cette échéance n'est pas écartée : rien à rétablir.")
    conn.commit()
