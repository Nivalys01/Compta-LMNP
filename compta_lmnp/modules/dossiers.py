# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Multi-dossiers — J8.

Un DOSSIER = une comptabilité complète et indépendante (un fichier SQLite,
avec ses propres `sauvegardes/` et `archives/` à côté). Nécessaire dès qu'on
tient plusieurs activités LMNP distinctes — et indispensable pour livrer le
logiciel à d'autres loueurs.

Organisation sur disque (racine = dossier de l'application) :

    compta.db                    ← dossier « principal » (historique, inchangé)
    dossiers.json                ← registre : slug → nom, chemin relatif
    dossiers/
      <slug>/compta.db           ← un sous-dossier par comptabilité
      <slug>/sauvegardes/        ← J6 : sauvegardes propres au dossier
      <slug>/archives/           ← J6 : FEC archivés propres au dossier

Sécurité : le dossier actif est choisi par un cookie, donc par une valeur
QUE LE NAVIGATEUR PEUT FORGER. Le cookie ne sert JAMAIS à construire un
chemin : il est confronté au registre, et tout slug inconnu retombe sur le
dossier principal. Les slugs eux-mêmes sont restreints à [a-z0-9-].

Compatibilité : un `compta.db` existant à la racine reste le dossier
« principal » — aucune migration, aucun déplacement de données.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import threading
import unicodedata
from datetime import date

import init_db

REGISTRE = "dossiers.json"
SOUS_DOSSIER = "dossiers"
PRINCIPAL = "principal"
# Noms réservés par Windows : un dossier ainsi nommé est IMPOSSIBLE à créer
# (CON, PRN, AUX, NUL, COM1-9, LPT1-9), avec un message d'erreur système
# incompréhensible. On les refuse d'emblée, sur toutes les plateformes, pour
# qu'un dossier créé sous Linux reste transférable vers Windows.
_WINDOWS_RESERVES = {"con", "prn", "aux", "nul"} | \
    {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
RESERVES = {PRINCIPAL, "bac_a_sable", "bac-a-sable"} | _WINDOWS_RESERVES
_SLUG_VALIDE = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")


# ── Registre ─────────────────────────────────────────────────────────────────

def _chemin_registre(racine: str) -> str:
    return os.path.join(racine, REGISTRE)


class RegistreIllisible(Exception):
    """Le registre des dossiers existe mais ne peut pas être lu."""


def _charger(racine: str) -> list[dict]:
    chemin = _chemin_registre(racine)
    if not os.path.exists(chemin):
        return []                      # pas encore de registre : cas normal
    try:
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
        return list(data.get("dossiers", []))
    except (OSError, ValueError) as exc:
        # Un registre TRONQUÉ était traité comme un registre VIDE : tous
        # les dossiers secondaires disparaissaient de l'interface, la
        # session retombait sur le dossier principal, et les comptabilités
        # correspondantes restaient sur le disque sans que rien ne dise
        # où elles étaient passées. Pire : réenregistrer un dossier aurait
        # réécrit le registre par-dessus ce qu'il en restait.
        raise RegistreIllisible(
            f"Le registre des dossiers ({chemin}) est présent mais "
            f"illisible ({type(exc).__name__} : {exc}). Les dossiers "
            "secondaires ne peuvent pas être listés — leurs bases sont "
            "intactes sur le disque, mais le logiciel ne sait plus où. "
            "Restaurez ce fichier depuis une sauvegarde, ou renommez-le "
            "pour repartir d'un registre neuf.") from exc


def _enregistrer(racine: str, entrees: list[dict]) -> None:
    """Écriture ATOMIQUE du registre : fichier temporaire puis os.replace
    (opération atomique du système de fichiers). Sans cela, une coupure ou
    un plantage en pleine écriture laisserait un dossiers.json tronqué —
    donc tous les dossiers secondaires « disparus ». os.replace écrase
    l'ancien registre d'un seul geste : à tout instant, le fichier sur
    disque est soit l'ancien complet, soit le nouveau complet."""
    cible = _chemin_registre(racine)
    # Nom temporaire UNIQUE. `dossiers.json.tmp`, partagé, faisait que deux
    # écritures simultanées se marchaient dessus dans le fichier même censé
    # rendre l'opération sûre (constat T-05).
    temporaire = f"{cible}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(temporaire, "w", encoding="utf-8") as f:
            json.dump({"dossiers": entrees}, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporaire, cible)
    except BaseException:
        try:
            os.remove(temporaire)
        except OSError:
            pass
        raise


# ── Le registre se modifie d'un seul tenant ───────────────────────────────
#
# `os.replace` rend la PUBLICATION atomique, pas le cycle qui la précède.
# Renommer un dossier, c'est lire le registre, modifier une entrée, puis
# réécrire le tout : deux renommages simultanés lisaient la même version,
# et le second réécrivait par-dessus le premier. Les deux appels
# réussissaient, et l'une des deux modifications disparaissait sans un mot
# (constat T-05) — le pire des cas, puisque rien ne permet de le remarquer.
#
# La réponse n'est pas une écriture plus atomique : c'est de faire de la
# lecture ET de l'écriture UNE SEULE section critique.
_VERROU_REGISTRE = threading.RLock()


@contextlib.contextmanager
def _registre_exclusif(racine: str):
    """Charge le registre, laisse l'appelant le modifier, le réécrit.

    L'écriture n'a lieu QUE si le bloc s'achève normalement : une
    exception laisse le registre intact, ce qui est le comportement
    voulu pour une création refusée.

    **Portée : les fils d'exécution d'un processus.** Le serveur est local,
    mono-processus et lié à 127.0.0.1 ; deux instances lancées en parallèle
    sur le même dossier restent hors de portée de ce verrou. Le dire vaut
    mieux que le laisser croire.
    """
    with _VERROU_REGISTRE:
        entrees = _charger(racine)
        yield entrees
        _enregistrer(racine, entrees)


# ── Slugs ────────────────────────────────────────────────────────────────────

def slugifier(nom: str) -> str:
    """'Mon T2 à Nancy' → 'mon-t2-a-nancy'. ValueError si rien d'utilisable."""
    s = unicodedata.normalize("NFKD", nom or "")
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:50]
    if not s or not _SLUG_VALIDE.match(s):
        raise ValueError("Nom de dossier invalide : utilisez au moins une "
                         "lettre ou un chiffre.")
    if s in _WINDOWS_RESERVES:
        raise ValueError(
            f"« {nom} » correspond à un nom réservé par Windows ({s.upper()}) "
            "et ne peut pas servir de nom de dossier. Choisissez un autre "
            "nom, par exemple en ajoutant un mot.")
    return s


def slug_sur(slug: str) -> bool:
    """Vrai si le slug (ex. venu d'un cookie) est de forme sûre ET non réservé."""
    return bool(slug) and bool(_SLUG_VALIDE.match(slug)) and slug not in RESERVES


# ── Opérations ───────────────────────────────────────────────────────────────

def lister(racine: str, db_principal: str) -> list[dict]:
    """
    Tous les dossiers connus, « principal » en tête. Chaque entrée :
        {slug, nom, chemin (absolu), existe, taille}
    """
    out = [{"slug": PRINCIPAL, "nom": "Dossier principal",
            "chemin": os.path.abspath(db_principal)}]
    # Un registre illisible ne doit enfermer personne : le dossier
    # principal ne dépend pas de lui et reste accessible. Mais il ne doit
    # pas non plus passer pour un registre vide — `probleme_registre()`
    # rend le motif, que l'interface et les contrôles affichent.
    try:
        entrees = _charger(racine)
    except RegistreIllisible:
        entrees = []
    for e in entrees:
        out.append({"slug": e["slug"], "nom": e["nom"],
                    "chemin": os.path.join(racine, e["chemin"])})
    for e in out:
        e["existe"] = os.path.exists(e["chemin"])
        e["taille"] = os.path.getsize(e["chemin"]) if e["existe"] else 0
    return out


def probleme_registre(racine: str) -> str:
    """Motif d'illisibilité du registre, ou chaîne vide s'il se lit bien."""
    try:
        _charger(racine)
    except RegistreIllisible as exc:
        return str(exc)
    return ""


def chemin_db(racine: str, slug: str) -> str | None:
    """Chemin ABSOLU de la base du dossier `slug`, ou None si inconnu.
    Le chemin vient du registre, jamais du slug lui-même."""
    for e in _charger(racine):
        if e["slug"] == slug:
            return os.path.join(racine, e["chemin"])
    return None


def creer(racine: str, nom: str, annee_cible: int | None = None) -> dict:
    """
    Crée un dossier vierge (mode blanc) : sous-dossier + base initialisée +
    inscription au registre. ValueError si le nom est vide, réservé ou déjà
    utilisé.
    """
    nom = (nom or "").strip()
    slug = slugifier(nom)
    if slug in RESERVES:
        raise ValueError(f"Le nom « {nom} » est réservé par l'application.")
    with _registre_exclusif(racine) as entrees:
        if any(e["slug"] == slug for e in entrees):
            raise ValueError(f"Un dossier « {slug} » existe déjà — "
                             "choisissez un autre nom.")
        rel = os.path.join(SOUS_DOSSIER, slug, "compta.db")
        chemin = os.path.join(racine, rel)
        # GARDE-FOU perte de données : si une base existe déjà à cet
        # emplacement (registre perdu, copie partielle…), on ne la
        # réinitialise JAMAIS — on la RATTACHE au registre telle quelle.
        # Réinitialiser écraserait des écritures comptables sans avertir.
        adopte = os.path.exists(chemin)
        if not adopte:
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            init_db.init(chemin, "blanc",
                         annee_cible=annee_cible or date.today().year).close()
        entrees.append({"slug": slug, "nom": nom, "chemin": rel})
    return {"slug": slug, "nom": nom, "chemin": chemin, "adopte": adopte}


def renommer(racine: str, slug: str, nouveau_nom: str) -> None:
    """Change le nom d'affichage (le slug et le chemin restent stables :
    ils sont référencés par le cookie et par le disque)."""
    nouveau_nom = (nouveau_nom or "").strip()
    if not nouveau_nom:
        raise ValueError("Le nouveau nom est vide.")
    with _registre_exclusif(racine) as entrees:
        for e in entrees:
            if e["slug"] == slug:
                e["nom"] = nouveau_nom
                return
        raise ValueError(f"Dossier inconnu : {slug}")


def nom(racine: str, slug: str) -> str:
    if slug == PRINCIPAL:
        return "Dossier principal"
    for e in _charger(racine):
        if e["slug"] == slug:
            return e["nom"]
    return slug
