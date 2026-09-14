# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Interface web de saisie — saisie par fait.
Lancer : python app.py   puis ouvrir http://localhost:5000
"""
from __future__ import annotations
import io
import json
import os
import sqlite3
import logging
import sys
from datetime import date

from flask import (Flask, g, has_app_context, redirect, render_template_string, request, send_file, url_for)
from markupsafe import escape

HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    # Executable autonome (PyInstaller) : le CODE vit dans le bundle, mais
    # les DONNEES de l'utilisateur (base, sauvegardes, certificat, journal)
    # doivent rester a cote de l'executable, la ou il les retrouvera apres
    # une mise a jour du logiciel. sys.executable est le seul chemin stable.
    HERE = os.path.dirname(os.path.abspath(sys.executable))
sys.path.insert(0, HERE)

# ── Amorçage du chemin d'import ───────────────────────────────────────────
#    Les modules métier vivent dans modules/ : sans ces lignes, « import
#    fiscal » échoue. Le paquet n'est pas installé par pip — c'est le prix
#    d'une distribution par simple décompression, et le lanceur ne peut pas
#    le faire à notre place. À poser AVANT le premier import métier.
_MODULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")
if _MODULES not in sys.path:
    sys.path.insert(0, _MODULES)

import controles
import fiscal
import init_db
import migrations
import operations
import pense_bete
import cession
import amortissement
import import_bancaire
import migration_fec
import re
import rejeu_fec
import uuid
import veille_fiscale
from pages import (ASSISTANT, PAGE_DOSSIER_ABSENT, PAGE_VERSION_TROP_RECENTE, PAGE_DEMARRAGE, PAGE_DON_SECTION, PAGE_QUITTANCES, PAGE_QUITTANCE_IMPRIMABLE, PAGE_IMPORT_SECTION, CSS, PAGE_ARCHIVES, PAGE_CLOTURE, PAGE_DOSSIERS, PAGE_EX_NOUVEAU, PAGE_IMMO, PAGE_LIASSE, PAGE_PENSE_BETE, PAGE_REGLEMENTATION, PAGE_SAISIE, PAGE_SANDBOX, PAGE_SAUVEGARDES_SECTION, PAGE_VEILLE)
import audit_cycle
import gabarits as gabarits_mod
import liasse as liasse_mod
import perennite
import quittances
import dossiers as dossiers_mod

def _lire_version() -> str:
    try:
        with open(os.path.join(HERE, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "?"


VERSION = _lire_version()

import parametres
import reprise

# COMPTA_DB / COMPTA_DB_BAC_A_SABLE : surcharge des chemins (tests hermétiques
# — sans elle, les tests du lanceur démarraient le serveur sur la base RÉELLE).
DB             = os.environ.get("COMPTA_DB",
                                os.path.join(HERE, "compta.db"))        # dossier RÉEL
BAC_A_SABLE_DB = os.environ.get("COMPTA_DB_BAC_A_SABLE",
                                os.path.join(HERE, "bac_a_sable.db"))   # dossier JETABLE

app = Flask(__name__)
# Plafond anti-abus : refuse un corps de requête > 2 Mo (413) avant même de
# le charger en mémoire. Une saisie comptable légitime pèse quelques Ko.
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


def _form_int(nom: str, defaut=None):
    """Lit un entier de formulaire SANS jamais lever : renvoie `defaut` si le
    champ est absent, vide ou non entier. Évite les erreurs 500 sur saisie
    malformée — la couche métier renverra un message clair si `defaut` est
    invalide en aval."""
    brut = (request.form.get(nom) or "").strip()
    try:
        return int(brut)
    except (TypeError, ValueError):
        return defaut


def _form_float(nom: str, defaut=None):
    """Idem pour un décimal. Accepte la virgule française (« 795,50 »)."""
    brut = (request.form.get(nom) or "").strip().replace(",", ".")
    try:
        return float(brut)
    except (TypeError, ValueError):
        return defaut


_MIGRES: set = set()


def _migrer_si_besoin() -> None:
    """Migre la base courante si son schéma est en retard. Une seule fois
    par chemin et par exécution : la vérification est une simple lecture,
    mais la migration prend une sauvegarde et ne doit pas se rejouer à
    chaque page."""
    try:
        chemin = _db_path()
    except FichierDossierAbsent:
        return                                   # traité par son gestionnaire
    if chemin in _MIGRES:
        return
    _MIGRES.add(chemin)
    try:
        c = sqlite3.connect(chemin)
        try:
            retard = init_db.version_base(c) < init_db.VERSION_SCHEMA
        finally:
            c.close()
        if retard:
            migrations.migrer(chemin)
    except Exception:                            # noqa: BLE001
        _MIGRES.discard(chemin)                  # réessayer au prochain accès


# Méthodes qui CHANGENT l'état. Une lecture forgée ne coûte rien ; une
# écriture forgée peut clôturer un exercice ou restaurer une sauvegarde.
_METHODES_ECRITURE = {"POST", "PUT", "PATCH", "DELETE"}


def _hote(url: str) -> str:
    """« http://localhost:5000/x » -> « http://localhost:5000 »."""
    from urllib.parse import urlsplit
    p = urlsplit(url or "")
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""


@app.before_request
def _garde_origine():
    """Refuse une écriture dont l'ORIGINE n'est pas le logiciel lui-même.

    Le modèle de menace reposait sur `host="127.0.0.1"` — « l'application
    n'est jamais exposée au réseau local ». C'est exact pour le réseau et
    SANS EFFET pour le navigateur : toute page ouverte dans le même
    navigateur pouvait poster ici. Reproduit avant correctif — un POST sans
    cookie, sans Referer et sans jeton clôturait l'exercice.

    Deux aggravations le rendaient pire qu'un CSRF ordinaire. `samesite=Lax`
    empêche l'envoi du cookie `dossier` sur une requête inter-site, si bien
    que `_dossier_actif()` retombait sur PRINCIPAL : une requête forgée
    visait TOUJOURS la comptabilité réelle, jamais le bac à sable. Et les
    routes concernées remplacent la base, clôturent, annulent, cèdent —
    aucune ne demande de connaître les données de l'utilisateur.

    Règle retenue : une origine PRÉSENTE et différente est refusée ; une
    origine ABSENTE est acceptée. Ce second choix est délibéré — curl, la
    ligne de commande et le client de test n'envoient aucun de ces
    en-têtes, et les exiger transformerait le contrôle en obstacle sans
    rien gagner : un navigateur, lui, envoie TOUJOURS `Origin` sur un POST
    inter-site (« null » si la politique de référent le masque), donc
    l'attaque par formulaire caché est bien couverte.
    """
    if request.method not in _METHODES_ECRITURE:
        return None
    attendu = _hote(request.base_url)
    for entete in ("Origin", "Referer"):
        valeur = request.headers.get(entete)
        if not valeur:
            continue
        if _hote(valeur) != attendu:
            app.logger.warning("Écriture refusée — %s %s depuis %s",
                               request.method, request.path, valeur)
            return (
                "Requête refusée : elle ne vient pas du logiciel.\n\n"
                f"Origine annoncée : {valeur}\n"
                f"Origine attendue : {attendu}\n\n"
                "Si vous lisiez cette page dans le logiciel, revenez à "
                "l'accueil et refaites l'action. Si vous ne comprenez pas "
                "ce message, ne refaites rien : une autre page de votre "
                "navigateur a peut-être tenté d'agir sur votre "
                "comptabilité.", 403, {"Content-Type": "text/plain; charset=utf-8"})
        return None                     # origine présente et conforme
    return None                         # aucune origine annoncée


@app.before_request
def _garde_version_schema():
    """Refus PÉDAGOGIQUE d'ouvrir une base plus récente que le logiciel
    (l'« impossible d'ouvrir une base de données plus récente » des
    logiciels classiques, transformé en message clair, sans toucher aux
    données)."""
    if request.path.startswith("/static"):
        return None
    # La sortie de secours doit rester joignable, sinon la page 409 est une
    # impasse : c'est elle qui repose le cookie sur le dossier principal.
    if request.path == "/dossiers/retour-principal":
        return None
    # MIGRATION À L'OUVERTURE. Elle ne tournait qu'au démarrage du serveur,
    # sur les dossiers alors connus — alors que `dossiers.creer` prévoit
    # explicitement d'ADOPTER une base préexistante, qui conserve donc son
    # schéma d'origine. Une base ancienne rattachée en cours de session
    # était ouverte telle quelle : le garde ne voyait rien (il ne refuse
    # qu'une base plus RÉCENTE), et les routes écrivaient dans un schéma
    # périmé — sans la copie de sûreté que la migration produit.
    _migrer_si_besoin()
    # LECTURE SEULE : marquer la version ici écrirait en base à CHAQUE
    # affichage de page (transaction d'écriture inutile, contention possible
    # avec une clôture en cours) et surtout ferait croire qu'un dossier est
    # à jour sans qu'aucun palier de migration n'ait tourné. Le marquage a
    # lieu à la création de la base (init_db.init) et à la fin d'une
    # migration (migrations.migrer) — là où il a un sens.
    conn = _conn()
    try:
        msg = init_db.verifier_version(conn)
    finally:
        conn.close()
    if msg:
        # Une ISSUE est indispensable : chaque lien de la barre de
        # navigation repasse par ce garde, et le cookie de dossier
        # vaut 180 jours. Sans elle, le logiciel devenait
        # inutilisable pour TOUS ses dossiers jusqu'à suppression
        # manuelle d'un cookie dans le navigateur.
        corps = render_template_string(PAGE_VERSION_TROP_RECENTE,
                                       msg=msg)
        try:
            return _base(corps, active="", annee=date.today().year,
                         annees=[]), 409
        except Exception:
            return msg, 409
    return None


def _journal_erreurs() -> None:
    """Journal d'erreurs PERSISTANT et ROTATIF (logs/erreurs.log, 512 Ko × 3).

    La console du lanceur est invisible (double-clic) ou perdue au
    redémarrage : sans fichier, un plancher chez un utilisateur distant est
    indiagnosticable. Rotation automatique — le disque ne peut pas se
    remplir. Le fichier reste sur la machine de l'utilisateur (aucun envoi
    réseau) : c'est lui qui choisit de le joindre à un message de support.
    """
    import logging.handlers
    d = os.path.join(os.path.dirname(_db_path()), "logs")
    os.makedirs(d, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(
        os.path.join(d, "erreurs.log"), maxBytes=512_000, backupCount=3,
        encoding="utf-8")
    h.setLevel(logging.ERROR)
    h.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)s  %(message)s"))
    h._journal_compta = True                     # marqueur d'idempotence
    app.logger.addHandler(h)


@app.errorhandler(Exception)
def _erreur_globale(exc):
    """Filet de sécurité : aucune exception ne doit atteindre l'utilisateur
    sous forme de traceback. Les erreurs HTTP (404, 413…) gardent leur code ;
    toute autre devient une page 500 sobre, sans détail interne."""
    from werkzeug.exceptions import HTTPException
    if isinstance(exc, HTTPException):
        return exc
    # Branchement PARESSEUX du journal (au premier incident) : au chargement
    # du module, le chemin du dossier n'est pas encore connu.
    if not any(getattr(x, "_journal_compta", False)
               for x in app.logger.handlers):
        try:
            _journal_erreurs()
        except OSError:
            pass                       # disque plein / droits : la page 500
    app.logger.exception("Erreur non gérée")     # reste servie quoi qu'il arrive
    body = ('<div class="card"><div class="card-body">'
            '<h2>Une erreur interne est survenue</h2>'
            '<p>L\'opération n\'a pas pu aboutir. Vos données ne sont pas '
            'affectées. Réessayez ; si le problème persiste, le détail '
            'technique vient d\'être enregistré dans le fichier '
            '<code>logs/erreurs.log</code> (dossier du logiciel) : '
            'joignez-le à votre message de support.</p>'
            '<p><a href="/">Retour à l\'accueil</a></p></div></div>')
    try:
        return _base(body, active="", annee=0, annees=[]), 500
    except Exception:
        # même le repli minimal oriente vers le journal
        return ("Erreur interne. Détail enregistré dans logs/erreurs.log "
                "(dossier du logiciel).", 500)


def _en_bac_a_sable() -> bool:
    """Vrai si la session navigue dans le dossier bac à sable (cookie)."""
    try:
        return request.cookies.get("dossier") == "bac_a_sable"
    except RuntimeError:            # hors contexte requête
        return False


def _dossier_actif() -> str:
    """Slug du dossier actif (cookie « dossier »), validé contre le registre.
    Le cookie est une valeur forgeable par le navigateur : il n'est JAMAIS
    utilisé comme chemin — tout slug inconnu retombe sur le principal."""
    try:
        slug = request.cookies.get("dossier", "")
    except RuntimeError:                       # hors contexte de requête
        return dossiers_mod.PRINCIPAL
    if slug == "bac_a_sable":
        return slug
    if dossiers_mod.slug_sur(slug) and dossiers_mod.chemin_db(HERE, slug):
        return slug
    return dossiers_mod.PRINCIPAL


class FichierDossierAbsent(Exception):
    """La base d'un dossier du registre est introuvable à son emplacement."""

    def __init__(self, slug: str, chemin: str):
        self.slug, self.chemin = slug, chemin
        super().__init__(f"Base introuvable pour « {slug} » : {chemin}")


def _db_path() -> str:
    if _en_bac_a_sable():
        if not os.path.exists(BAC_A_SABLE_DB):
            init_db.init(BAC_A_SABLE_DB, "blanc",
                         annee_cible=date.today().year, ecraser=True).close()
        return BAC_A_SABLE_DB
    slug = _dossier_actif()
    if slug != dossiers_mod.PRINCIPAL:
        chemin = dossiers_mod.chemin_db(HERE, slug)
        if chemin:
            # Une base ABSENTE n'est pas une base à créer. Elle l'était :
            # le dossier était silencieusement remplacé par une base
            # vierge, et l'utilisateur voyait sa comptabilité disparaître
            # sans un mot. Or l'absence est le plus souvent TEMPORAIRE —
            # disque externe débranché, dossier synchronisé pas encore
            # redescendu, partage réseau non monté : créer une base à la
            # place masque le vrai fichier et fait diverger les deux.
            if not os.path.exists(chemin):
                raise FichierDossierAbsent(slug, chemin)
            return chemin
    return DB

# ── Catalogue menu déroulant (dynamique : gabarits standard + personnalisés) ─


def _catalogue(conn):
    """(choix_groupes, produit_types, libelles) pour la connexion courante."""
    g = gabarits_mod.tous(conn)
    return (gabarits_mod.par_groupe(conn),
            {k for k, v in g.items() if v["nature"] == "produit"},
            {k: v["libelle"] for k, v in g.items()})

# Comptes immobilisation disponibles (compte_immo → compte_amort ou None)
COMPTES_IMMO = [
    ("211550", "Terrain",                         None),
    ("213150", "Bâtiment",                        "281315"),
    ("218100", "Installation / agencement",       "281810"),
    ("218400", "Mobilier",                        "281840"),
]

# ── Helpers DB ───────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_db_path())
    c.execute("PRAGMA foreign_keys = ON")
    c.row_factory = sqlite3.Row
    # Filet de sécurité : la connexion est enregistrée dans le contexte de la
    # requête et fermée à coup sûr en fin de traitement, y compris si la
    # route lève avant son close() (21 routes reposaient sur un close()
    # placé hors finally — un rendu qui échoue laissait la connexion
    # ouverte, donc un verrou potentiel jusqu'au passage du ramasse-miettes).
    if has_app_context():
        if not hasattr(g, "_connexions"):
            g._connexions = []
        g._connexions.append(c)
    return c


@app.teardown_appcontext
def _fermer_connexions(_exc=None):
    """Ferme toute connexion restée ouverte à la fin de la requête."""
    for c in getattr(g, "_connexions", []):
        try:
            c.close()
        except Exception:                      # noqa: BLE001 — fermeture best effort
            pass


def _annees(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute("SELECT annee FROM exercice ORDER BY annee DESC").fetchall()
    return [r[0] for r in rows] or [date.today().year]


def _dossier_configure() -> bool:
    """Un exploitant est-il enregistré ? C'est le seul vrai marqueur d'un
    dossier prêt à l'emploi : sans lui, ni bien ni saisie ne sont
    possibles."""
    try:
        c = sqlite3.connect(_db_path())
        n = c.execute("SELECT COUNT(*) FROM exploitant").fetchone()[0]
        c.close()
        return n > 0
    except sqlite3.Error:
        return True          # en cas de doute, ne pas perturber la navigation


def _annees_ouvertes(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        "SELECT annee FROM exercice WHERE statut='ouvert' ORDER BY annee DESC"
    ).fetchall()
    return [r[0] for r in rows]


def _annee_courante(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT annee FROM exercice WHERE statut='ouvert' ORDER BY annee DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else date.today().year


def _annee_param(conn: sqlite3.Connection) -> int:
    a = request.args.get("annee", type=int)
    if a is None:
        a = request.form.get("annee", type=int)
    return a or _annee_courante(conn)


# ── Base HTML (mise en page partagée) ────────────────────────────────────────


def _base(content: str, *, active: str, annee: int, annees: list[int],
          flash_ok: str = "", flash_err: str = "", flash_warn: str = "") -> str:
    # Ordre des onglets. Au PREMIER lancement — aucun exploitant enregistré —
    # « Démarrer » passe en tête : un dossier vierge n'a rien à saisir, et
    # l'utilisateur cherchait par où commencer (retour d'usage).
    nav_items = [
        ("saisie",          "Saisie"),
        ("immobilisations", "Immobilisations"),
        ("cloture",         "Clôture"),
        ("liasse",          "Liasse"),
        ("quittances",      "Quittances"),
        ("pense_bete",      "Pense-bête"),
        ("veille",          "Veille fiscale"),
        ("archives",        "Archives FEC"),
        ("reglementation",  "Réglementation"),
        ("exercice_nouveau","Nouvel exercice"),
        ("dossiers",        "Dossiers"),
        ("bac_a_sable",     "Bac à sable"),
    ]
    if not _dossier_configure():
        nav_items = [("dossiers", "▶ Démarrer")] + [
            x for x in nav_items if x[0] != "dossiers"]
    def _href(k: str) -> str:
        if k == "pense_bete":
            return "/pense-bete"
        if k == "veille":
            return "/veille"
        if k == "archives":
            return "/archives"
        if k == "exercice_nouveau":
            return "/exercice/nouveau"
        if k == "bac_a_sable":
            return "/bac-a-sable"
        return f"/{k}"
    nav_html = "".join(
        f'<a href="{_href(k)}?annee={annee}"'
        f' class="{"active" if k == active else ""}">{label}</a>'
        for k, label in nav_items
    )
    bandeau_sandbox = ""
    if _en_bac_a_sable():
        bandeau_sandbox = (
            '<div style="background:#7a4a00;color:#ffe8b8;text-align:center;'
            'padding:8px 16px;font-weight:600;letter-spacing:.3px">'
            '🧪 BAC À SABLE — dossier d\'essai jetable, la comptabilité réelle '
            'n\'est pas modifiée. '
            '<form method="post" action="/bac-a-sable/quitter" style="display:inline">'
            '<button type="submit" style="margin-left:12px;background:#ffe8b8;'
            'color:#7a4a00;border:0;padding:4px 12px;border-radius:4px;'
            'font-weight:700;cursor:pointer">Revenir au dossier réel</button>'
            '</form></div>')
    # escape() : les messages arrivent par la query string (?ok= / ?err= /
    # ?warn=) — sans échappement : XSS réfléchie, et messages légitimes
    # contenant & < > cassés.
    flashes = ""
    if flash_ok:
        flashes += f'<div class="flash flash-ok">{escape(flash_ok)}</div>'
    if flash_err:
        flashes += f'<div class="flash flash-err">{escape(flash_err)}</div>'
    if flash_warn:
        flashes += f'<div class="flash flash-warn">{escape(flash_warn)}</div>'

    annee_opts = "".join(
        f'<option value="{a}" {"selected" if a == annee else ""}>{a}</option>'
        for a in annees
    )
    nom_dossier = ("🧪 bac à sable" if _en_bac_a_sable()
                   else escape(dossiers_mod.nom(HERE, _dossier_actif())))
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Compta LMNP</title>
  <style>{CSS}</style>
</head>
<body>
{bandeau_sandbox}
<header>
  <div class="brand">Compta LMNP</div>
  <nav>{nav_html}</nav>
  <div class="header-right">
    <label>Dossier</label>
    <a href="/dossiers" style="margin-right:14px;font-weight:700;
       text-decoration:none;color:#ffd54f">{nom_dossier}</a>
    <label>Exercice</label>
    <form method="get" style="display:inline">
      <select name="annee" onchange="this.form.submit()">{annee_opts}</select>
    </form>
  </div>
</header>
<main>
  {flashes}
  {content}
</main>
<footer style="max-width:1080px;margin:24px auto 16px;padding:0 24px;
        color:#8a93a3;font-size:12px;text-align:right">
  Compta LMNP v{VERSION} — © 2026 Sylvain FAURE, tous droits réservés.
  Logiciel gratuit (voir LICENSE.txt) · fourni sans garantie : les états
  produits sont à faire valider avant tout dépôt.
</footer>
<script>
// Confirmation unique pour tout ce qui porte data-confirmer. Écrire le
// gestionnaire a la main dans chaque gabarit avait produit deux
// confirmations qui ne s'affichaient jamais : leur litteral JavaScript
// contenait un saut de ligne et une apostrophe non echappes, le
// gestionnaire ne compilait pas, et l'operation partait sans un mot.
document.addEventListener("click", function (ev) {{
  var el = ev.target.closest("[data-confirmer]");
  if (!el) return;
  if (!window.confirm(el.getAttribute("data-confirmer"))) {{
    ev.preventDefault();
    ev.stopPropagation();
  }}
}}, true);
// Infobulles d'aide : recentrage quand elles toucheraient un bord.
// Elles sont posees en CSS pur, centrees sur leur pastille — donc coupees
// des que la pastille est a moins d'une demi-largeur du bord de la
// fenetre. Ce script ne fait que POSER une classe : sans JavaScript,
// l'infobulle reste centree et lisible comme avant, elle depasse
// simplement. Amelioration progressive, jamais un prerequis.
document.addEventListener("mouseover", function (ev) {{
  var a = ev.target.closest(".aide");
  if (!a || !a.hasAttribute("data-aide")) return;
  a.classList.remove("aide-gauche", "aide-droite");
  var r = a.getBoundingClientRect();
  var demi = 140;                       // moitie de la largeur maximale
  if (r.left + r.width / 2 - demi < 8) a.classList.add("aide-gauche");
  else if (r.left + r.width / 2 + demi > window.innerWidth - 8)
    a.classList.add("aide-droite");
}}, true);
document.addEventListener("submit", function (ev) {{
  var f = ev.target.closest("form[data-confirmer]");
  if (f && !window.confirm(f.getAttribute("data-confirmer"))) {{
    ev.preventDefault();
  }}
}}, true);
</script>
{ASSISTANT}
</body>
</html>"""


# ── Page Saisie ──────────────────────────────────────────────────────────────



@app.route("/")
def root():
    conn = _conn()
    a = _annee_courante(conn)
    conn.close()
    return redirect(url_for("saisie", annee=a))


@app.route("/saisie")
def saisie():
    conn = _conn()
    operations.assurer_colonne_annulee(conn)
    annee  = _annee_param(conn)
    annees = _annees(conn)
    biens  = conn.execute("SELECT id, libelle FROM bien ORDER BY id").fetchall()
    ops    = conn.execute(
        "SELECT o.id, o.date_operation, o.type, o.montant, o.tiers, o.periode, "
        "       o.libelle, e.piece_ref, e.ecriture_num, "
        "       COALESCE(o.annulee,0) AS annulee "
        "FROM operation o LEFT JOIN ecriture e ON e.id=o.ecriture_id "
        "WHERE o.exercice_annee=? ORDER BY o.date_operation DESC, o.id DESC LIMIT 100",
        (annee,),
    ).fetchall()
    choix_groupes, produit_types, libs = _catalogue(conn)
    perio = {k: g["periodicite"] for k, g in gabarits_mod.tous(conn).items()}
    conn.close()
    body = render_template_string(PAGE_DON_SECTION) \
        + render_template_string(PAGE_SAISIE,
        annee=annee, today=date.today().isoformat(),
        choix_groupes=choix_groupes, biens=biens, ops=ops,
        produit_types=produit_types, gabarits_lib=libs,
        perio_json=json.dumps(perio),
    ) + render_template_string(PAGE_IMPORT_SECTION,
        propositions=None, jeton="")
    return _base(body, active="saisie", annee=annee, annees=annees,
                 flash_ok=request.args.get("ok",""),
                 flash_err=request.args.get("err",""))


@app.route("/operation/<int:operation_id>/dupliquer", methods=["POST"])
def operation_dupliquer(operation_id: int):
    conn = _conn()
    annee = _annee_param(conn)
    try:
        r = operations.dupliquer(conn, operation_id)
        op = conn.execute("SELECT type, montant, date_operation FROM operation "
                          "WHERE id=?", (r["operation_id"],)).fetchone()
        conn.close()
        ok = (f"Opération dupliquée au mois suivant : {op[0]} "
              f"{op[1]:.2f} € le {op[2][8:10]}/{op[2][5:7]}/{op[2][:4]} "
              f"(BQ n°{r['ecriture_num']}).")
        return redirect(url_for("saisie", annee=int(op[2][:4]), ok=ok))
    except Exception as exc:
        conn.close()
        return redirect(url_for("saisie", annee=annee, err=str(exc)))


@app.route("/immobilisations/reprendre-amortissements", methods=["POST"])
def immo_reprendre_amortissements():
    """Passe le « à-nouveau » d'amortissement d'un bien déjà amorti à son
    entrée dans le logiciel. Constaté en usage réel : sans lui, le bilan et
    le tableau 2033-C divergent définitivement."""
    conn = _conn()
    annee = _annee_param(conn)
    try:
        r = operations.reprendre_amortissements_anterieurs(conn, annee)
        comptes = ", ".join(f"{c} : {m:.2f} €"
                            for c, m in sorted(r["par_compte"].items()))
        return redirect(url_for("immobilisations", annee=annee,
            ok=f"Amortissements antérieurs repris pour {r['total']:.2f} € "
               f"({comptes}) — écriture OD n°{r['ecriture_num']} au "
               f"1er janvier. Le résultat de l'exercice est inchangé."))
    except Exception as exc:
        return redirect(url_for("immobilisations", annee=annee, err=str(exc)))
    finally:
        conn.close()


@app.route("/saisir-appel", methods=["POST"])
def saisir_appel():
    conn = _conn()
    annee = _annee_param(conn)
    try:
        def _f(champ):
            v = request.form.get(champ, "").strip()
            return float(v) if v else 0.0
        res = operations.saisir_appel_charges(
            conn,
            date_operation=request.form["date_operation"],
            periode=(request.form.get("periode") or None),
            charges_courantes=_f("charges_courantes"),
            fonds_alur=_f("fonds_alur"),
            travaux=_f("travaux"),
            bien_id=_form_int("bien_id", 1),
            exercice=annee,
        )
        conn.close()
        ok = (f"Appel de charges ventilé ({res['piece_ref']}) : "
              f"{len(res['operations'])} écriture(s), total {res['total']:.2f} €.")
        return redirect(url_for("saisie", annee=annee, ok=ok))
    except Exception as exc:
        conn.close()
        return redirect(url_for("saisie", annee=annee, err=str(exc)))


@app.route("/saisir", methods=["POST"])
def saisir_op():
    conn = _conn()
    try:
        annee = _annee_param(conn)
        type_op = (request.form.get("type") or "").strip()
        date_op = (request.form.get("date_operation") or "").strip()
        montant = _form_float("montant")
        if not type_op or not date_op:
            raise ValueError("Type et date d'opération sont obligatoires.")
        if montant is None:
            raise ValueError("Montant invalide ou manquant.")
        r = operations.saisir(
            conn,
            type         = type_op,
            montant      = montant,
            date_operation = date_op,
            periode      = request.form.get("periode") or None,
            piece_ref    = request.form.get("piece_ref") or None,
            tiers        = request.form.get("tiers", ""),
            libelle      = request.form.get("libelle") or None,
            bien_id      = _form_int("bien_id", 1),
            exercice     = annee,
        )
        # tous(conn) et non tous() : sans connexion, les gabarits personnalisés
        # du dossier courant (bac à sable compris) seraient ignorés.
        lib = gabarits_mod.tous(conn).get(type_op, {}) \
                                     .get("libelle", type_op)
        ok  = f"Opération enregistrée : {lib} — {r['montant']:.2f} € (BQ n°{r['ecriture_num']})"
        return redirect(url_for("saisie", annee=annee, ok=ok))
    except Exception as exc:
        annee = request.form.get("annee", type=int) or date.today().year
        return redirect(url_for("saisie", annee=annee,
                                err=f"Saisie refusée — {exc}"))
    finally:
        conn.close()


# ── Page Immobilisations ─────────────────────────────────────────────────────



@app.route("/immobilisations")
def immobilisations():
    conn   = _conn()
    cession.assurer_schema(conn)          # colonnes/comptes de cession à la volée
    conn.commit()
    annee  = _annee_param(conn)
    annees = _annees(conn)
    exp    = conn.execute("SELECT * FROM exploitant LIMIT 1").fetchone()
    biens  = conn.execute("SELECT * FROM bien ORDER BY id").fetchall()
    compos = conn.execute("SELECT * FROM composant ORDER BY bien_id, id").fetchall()
    manque_amort = operations.amortissements_anterieurs_manquants(conn, annee)["total"]
    conn.close()

    amort_map = {num: amort for num, _, amort in COMPTES_IMMO}
    body = render_template_string(PAGE_IMMO,
        amort_anterieurs=manque_amort,
        ventilations={b["id"]: amortissement.ventilation_proposee(
            b["prix_total"] or 0.0, b["quote_part_terrain"])
            for b in biens
            if not any(c["bien_id"] == b["id"] for c in compos)},
        annee=annee, exploitant=exp, biens=biens, composants=compos,
        comptes_immo=COMPTES_IMMO,
        amort_json=json.dumps(amort_map),
    )
    return _base(body, active="immobilisations", annee=annee, annees=annees,
                 flash_ok=request.args.get("ok",""),
                 flash_err=request.args.get("err",""))


@app.route("/immobilisations/exploitant", methods=["POST"])
def creer_exploitant():
    """Enregistre l'exploitant.

    Accessible depuis la page Immobilisations ET depuis la configuration
    initiale d'un dossier neuf : c'est là qu'un débutant la cherche, et
    l'y trouver évite de commencer par une page d'immobilisations vide
    (retour d'usage). Le paramètre `retour` dit où revenir.
    """
    conn  = _conn()
    annee = _annee_param(conn)
    retour = request.form.get("retour") or "immobilisations"
    try:
        conn.execute(
            "INSERT INTO exploitant (nom, siren, adresse) VALUES (?,?,?)",
            (request.form["nom"], request.form["siren"], request.form.get("adresse",""))
        )
        conn.commit()
        ouverts = _annees_ouvertes(conn)
        ok = (f"Dossier configuré au nom de « {request.form['nom']} ». "
              f"L'exercice {ouverts[0]} est déjà OUVERT : vous pouvez "
              "saisir immédiatement." if ouverts else
              f"Exploitant « {request.form['nom']} » enregistré.")
    except Exception as exc:
        conn.close()
        return redirect(url_for(retour, annee=annee, err=str(exc)))
    conn.close()
    cible = "saisie" if retour == "saisie" else retour
    return redirect(url_for(cible, annee=annee, ok=ok))


@app.route("/immobilisations/bien", methods=["POST"])
def creer_bien():
    conn  = _conn()
    annee = _annee_param(conn)
    try:
        exp = conn.execute("SELECT id FROM exploitant LIMIT 1").fetchone()
        if not exp:
            raise ValueError("Créez d'abord un exploitant.")
        prix  = request.form.get("prix_total") or None
        qpt   = request.form.get("quote_part_terrain") or None
        dacq  = request.form.get("date_acquisition") or None
        conn.execute(
            "INSERT INTO bien (exploitant_id, libelle, adresse, date_acquisition, "
            "prix_total, quote_part_terrain) VALUES (?,?,?,?,?,?)",
            (exp[0], request.form["libelle"], request.form.get("adresse",""),
             dacq, float(prix) if prix else None, float(qpt) if qpt else None)
        )
        conn.commit()
        ok = f"Bien « {request.form['libelle']} » créé."
    except Exception as exc:
        conn.close()
        return redirect(url_for("immobilisations", annee=annee, err=str(exc)))
    conn.close()
    return redirect(url_for("immobilisations", annee=annee, ok=ok))


@app.route("/immobilisations/composant", methods=["POST"])
def creer_composant():
    conn  = _conn()
    annee = _annee_param(conn)
    try:
        bien_id  = _form_int("bien_id")
        if bien_id is None:
            raise ValueError("Bien non sélectionné.")
        duree_s  = request.form.get("duree_annees","").strip()
        duree    = int(duree_s) if duree_s and duree_s != "0" else None
        amortissable = 1 if duree else 0

        cpt_immo = request.form["compte_immo"]
        # Résolution automatique du compte d'amortissement depuis le compte
        # d'immobilisation.
        amort_map = {num: amort for num, _, amort in COMPTES_IMMO}
        cpt_amort = amort_map.get(cpt_immo) if amortissable else None
        # Un compte SANS contrepartie d'amortissement (le terrain) ne peut
        # pas porter de durée : le composant était accepté, puis la clôture
        # échouait sur « NOT NULL constraint failed: ligne.compte_num » —
        # message incompréhensible, et blocage total (constat d'usage).
        if amortissable and not cpt_amort:
            libelle_cpt = next((lib for num, lib, _ in COMPTES_IMMO
                                if num == cpt_immo), cpt_immo)
            raise ValueError(
                f"« {libelle_cpt} » n'est pas amortissable : laissez la "
                "durée à 0. Le terrain ne se déprécie pas — c'est d'ailleurs "
                "pour cela qu'il faut isoler sa quote-part du reste du prix. "
                "Si vous vouliez amortir du bâti, choisissez « Bâtiment ».")

        dms = request.form.get("date_mise_service") or None
        conn.execute(
            "INSERT INTO composant (bien_id, code_immo, libelle, categorie, valeur_brute, "
            "duree_annees, date_mise_service, compte_immo, compte_amort, amortissable) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (bien_id, request.form.get("code_immo") or None, request.form["libelle"],
             request.form.get("categorie",""), float(request.form["valeur_brute"]),
             duree, dms, cpt_immo, cpt_amort, amortissable)
        )
        conn.commit()
        ok = f"Composant « {request.form['libelle']} » ajouté."
        # Alerte de cohérence AU MOMENT DE L'AJOUT : c'est là qu'elle sert,
        # pendant que l'utilisateur a le montant en tête.
        b = conn.execute("SELECT libelle, prix_total FROM bien WHERE id=?",
                         (bien_id,)).fetchone()
        if b and b["prix_total"]:
            total = conn.execute(
                "SELECT COALESCE(SUM(valeur_brute),0) FROM composant "
                "WHERE bien_id=?", (bien_id,)).fetchone()[0]
            depassement = round(total - b["prix_total"], 2)
            if depassement > 0.05 * b["prix_total"]:
                ok += (f" ⚠ La somme des composants ({total:.2f} €) dépasse "
                       f"désormais de {depassement:.2f} € "
                       f"({depassement / b['prix_total'] * 100:.1f} %) le "
                       f"prix d'acquisition ({b['prix_total']:.2f} €). "
                       "Normal si vous immobilisez des travaux postérieurs ; "
                       "à vérifier s'il s'agit de la ventilation initiale.")

        # Écriture d'acquisition (débit 2xx / crédit 108000) sur l'exercice
        # ouvert — sinon le composant n'existe qu'en référentiel et le bilan
        # (2033-A) comme le FEC seraient faux. Désactivable pour une reprise
        # d'historique déjà portée par les à-nouveaux.
        if request.form.get("sans_ecriture") != "1":
            ouverts = _annees_ouvertes(conn)
            if not ouverts:
                raise ValueError("Aucun exercice ouvert pour comptabiliser "
                                 "l'écriture d'acquisition.")
            cible = min(ouverts)
            date_op = dms if dms and int(dms[:4]) == cible else f"{cible}-01-01"
            res = operations.saisir_acquisition(
                conn, compte_immo=cpt_immo,
                montant=float(request.form["valeur_brute"]),
                date_operation=date_op, libelle=request.form["libelle"],
                exercice=cible)
            ok += (f" Écriture d'acquisition n°{res['ecriture_num']} "
                   f"générée sur {cible}.")
    except Exception as exc:
        conn.close()
        return redirect(url_for("immobilisations", annee=annee, err=str(exc)))
    conn.close()
    return redirect(url_for("immobilisations", annee=annee, ok=ok))


@app.route("/immobilisations/ventiler", methods=["POST"])
def immo_ventiler():
    """
    Ventile le prix d'acquisition d'un bien en composants, en une fois.

    Ajouté après un constat d'usage : on pouvait empiler des composants
    sans qu'aucun lien ne soit fait avec le prix payé. Or c'est la
    ventilation qui donne au réel tout son intérêt — un bien saisi en bloc
    s'amortit sur la durée du gros œuvre, et le mobilier, qui devrait
    s'amortir en quelques années, s'étale sur des décennies.
    """
    conn = _conn()
    annee = _annee_param(conn)
    try:
        bien_id = _form_int("bien_id")
        bien = conn.execute("SELECT * FROM bien WHERE id=?",
                            (bien_id,)).fetchone()
        if bien is None:
            raise ValueError("Bien introuvable.")
        if conn.execute("SELECT COUNT(*) FROM composant WHERE bien_id=?",
                        (bien_id,)).fetchone()[0]:
            raise ValueError(
                "Ce bien a déjà des composants : la ventilation initiale ne "
                "s'utilise qu'une fois. Ajoutez les composants manquants "
                "un par un ci-dessous.")
        dms = request.form.get("date_mise_service") or bien["date_acquisition"]
        cree, total = 0, 0.0
        for ligne in amortissement.VENTILATION_INDICATIVE:
            brut = request.form.get(f"montant_{ligne['cle']}", "").strip()
            try:
                montant = float(brut.replace(",", ".").replace(" ", "")) if brut else 0.0
            except ValueError:
                raise ValueError(
                    f"« {ligne['libelle']} » : « {brut} » n'est pas un "
                    "montant. Attendu un nombre en euros (ex. 52000 ou "
                    "52000,50), ou une case vide pour ignorer ce poste."
                ) from None
            if montant > 1e12:
                raise ValueError(
                    f"« {ligne['libelle']} » : montant hors de proportion "
                    f"({montant:,.0f} €). Vérifiez la saisie.".replace(",", " "))
            if montant <= 0:
                continue          # poste laissé vide : simplement ignoré
            duree_s = request.form.get(f"duree_{ligne['cle']}", "").strip()
            duree = int(duree_s) if duree_s and duree_s != "0" else None
            amort_map = {num: am for num, _, am in COMPTES_IMMO}
            cpt_amort = amort_map.get(ligne["compte_immo"]) if duree else None
            if duree and not cpt_amort:
                raise ValueError(f"« {ligne['libelle']} » ne s'amortit pas : "
                                 "laissez sa durée à 0.")
            conn.execute(
                "INSERT INTO composant (bien_id, libelle, categorie, "
                "valeur_brute, duree_annees, date_mise_service, compte_immo, "
                "compte_amort, amortissable) VALUES (?,?,?,?,?,?,?,?,?)",
                (bien_id, ligne["libelle"], ligne["categorie"], montant,
                 duree, dms, ligne["compte_immo"], cpt_amort,
                 1 if duree else 0))
            ouverts = _annees_ouvertes(conn)
            if request.form.get("sans_ecriture") != "1" and ouverts:
                cible = min(ouverts)
                date_op = (dms if dms and int(dms[:4]) == cible
                           else f"{cible}-01-01")
                operations.saisir_acquisition(
                    conn, compte_immo=ligne["compte_immo"], montant=montant,
                    date_operation=date_op, libelle=ligne["libelle"],
                    exercice=cible, commit=False)
            cree += 1
            total = round(total + montant, 2)
        if not cree:
            raise ValueError("Aucun montant saisi : renseignez au moins un "
                             "poste.")
        conn.commit()
        prix = bien["prix_total"] or 0.0
        alerte = ""
        if prix and abs(total - prix) > 0.05 * prix:
            alerte = (f" Attention : le total ventilé ({total:.2f} €) "
                      f"s'écarte de plus de 5 % du prix d'acquisition "
                      f"({prix:.2f} €) — vérifiez la répartition.")
        return redirect(url_for("immobilisations", annee=annee,
            ok=f"{cree} composant(s) créé(s) pour {total:.2f} €.{alerte}"))
    except Exception as exc:
        conn.rollback()
        return redirect(url_for("immobilisations", annee=annee, err=str(exc)))
    finally:
        conn.close()


@app.route("/immobilisations/composant/<int:composant_id>/duree",
           methods=["POST"])
def composant_duree(composant_id):
    """
    Corrige la durée d'amortissement d'un composant.

    Ajouté après un blocage réel : un composant créé avec une durée sur un
    compte non amortissable (terrain) faisait échouer toute clôture, et
    RIEN dans l'interface ne permettait de le corriger — les composants
    étaient créables, jamais modifiables. Un logiciel qui laisse commettre
    une erreur doit laisser la défaire.
    """
    conn = _conn()
    annee = _annee_param(conn)
    try:
        c = conn.execute("SELECT libelle, compte_immo FROM composant "
                         "WHERE id=?", (composant_id,)).fetchone()
        if c is None:
            raise ValueError("Composant introuvable.")
        brut = request.form.get("duree_annees", "").strip()
        duree = int(brut) if brut and brut != "0" else None
        amortissable = 1 if duree else 0
        amort_map = {num: amort for num, _, amort in COMPTES_IMMO}
        cpt_amort = amort_map.get(c["compte_immo"]) if amortissable else None
        if amortissable and not cpt_amort:
            raise ValueError(
                f"Le compte {c['compte_immo']} ne s'amortit pas : seule la "
                "durée 0 est acceptée pour ce composant.")
        conn.execute("UPDATE composant SET duree_annees=?, amortissable=?, "
                     "compte_amort=? WHERE id=?",
                     (duree, amortissable, cpt_amort, composant_id))
        conn.commit()
        msg = (f"Composant « {c['libelle']} » : durée portée à "
               f"{duree} ans." if duree else
               f"Composant « {c['libelle']} » : durée retirée, il n'est "
               "plus amorti.")
        return redirect(url_for("immobilisations", annee=annee, ok=msg))
    except Exception as exc:
        return redirect(url_for("immobilisations", annee=annee, err=str(exc)))
    finally:
        conn.close()


@app.route("/pense-bete/notes", methods=["POST"])
def pense_bete_notes():
    """Bloc-notes personnel de l'utilisateur.

    Conservé dans la table `meta` du dossier plutôt que dans un fichier à
    part : il suit ainsi les sauvegardes, les restaurations et les
    changements de dossier sans mécanique supplémentaire — et ne quitte
    jamais la machine.
    """
    conn = _conn()
    try:
        pense_bete.ecrire_notes(conn, request.form.get("notes", ""))
        return redirect(url_for("pense_bete_page", ok="Notes enregistrées."))
    except Exception as exc:
        return redirect(url_for("pense_bete_page", err=str(exc)))
    finally:
        conn.close()


@app.route("/dossiers/retour-principal", methods=["POST"])
def dossiers_retour_principal():
    """Sortie de secours : repose le cookie sur le dossier principal.

    Joignable même quand le garde de version bloque tout le reste — sans
    elle, ouvrir un dossier produit par une version plus récente rendait le
    logiciel inutilisable jusqu'à suppression manuelle d'un cookie.
    """
    resp = redirect(url_for("dossiers_page",
                            ok="Retour au dossier principal."))
    resp.set_cookie("dossier", dossiers_mod.PRINCIPAL,
                    max_age=180*24*3600, samesite="Lax")
    return resp


@app.errorhandler(FichierDossierAbsent)
def _dossier_absent(exc):
    """La base d'un dossier est introuvable — sans la remplacer.

    Le comportement d'origine créait une base vierge à sa place : la
    comptabilité paraissait perdue, et le vrai fichier — souvent
    simplement pas encore disponible — se trouvait masqué.
    """
    corps = render_template_string(PAGE_DOSSIER_ABSENT,
                                   slug=exc.slug, chemin=exc.chemin)
    try:
        return _base(corps, active="", annee=date.today().year,
                     annees=[]), 409
    except Exception:                            # noqa: BLE001
        return str(exc), 409


# ── Quittances de loyer ──────────────────────────────────────────────────────
@app.route("/quittances")
def quittances_page():
    conn = _conn()
    try:
        annee = _annee_param(conn)
        biens = conn.execute("SELECT id, libelle FROM bien ORDER BY id").fetchall()
        toutes = quittances.lister(conn)
        an_filtre = (request.args.get("an") or "").strip()
        affichees = ([q for q in toutes
                      if q["periode"].startswith(an_filtre + "-")]
                     if an_filtre else toutes)
        annees_q = sorted({q["periode"][:4] for q in toutes}, reverse=True)
        body = render_template_string(
            PAGE_QUITTANCES,
            locataires=quittances.locataires(conn),
            quittances=affichees, annees_quittances=annees_q,
            an_filtre=an_filtre, biens=biens)
        return _base(body, active="quittances", annee=annee,
                     annees=_annees(conn),
                     flash_ok=request.args.get("ok", ""),
                     flash_err=request.args.get("err", ""))
    finally:
        conn.close()


@app.route("/quittances/locataire", methods=["POST"])
def quittances_locataire():
    conn = _conn()
    try:
        nom = request.form.get("nom", "")
        quittances.ajouter_locataire(
            conn, bien_id=_form_int("bien_id"), nom=nom,
            date_entree=request.form.get("date_entree", ""),
            date_sortie=request.form.get("date_sortie") or None,
            loyer_mensuel=_form_float("loyer_mensuel", None),
            charges_mensuelles=_form_float("charges_mensuelles", 0) or 0)
        return redirect(url_for("quittances_page",
                                ok=f"Locataire « {nom} » enregistré."))
    except Exception as exc:
        return redirect(url_for("quittances_page", err=str(exc)))
    finally:
        conn.close()


@app.route("/quittances/emettre", methods=["POST"])
def quittances_emettre():
    conn = _conn()
    try:
        r = quittances.emettre(
            conn, locataire_id=_form_int("locataire_id"),
            periode=request.form.get("periode", ""),
            loyer=_form_float("loyer", None),
            charges=_form_float("charges", None),
            date_paiement=request.form.get("date_paiement") or None)
        return redirect(url_for("quittances_page",
            ok=f"Quittance n° {r['numero']:05d} émise pour {r['locataire']} "
               f"({r['periode']}) : {r['total']:.2f} €."))
    except Exception as exc:
        return redirect(url_for("quittances_page", err=str(exc)))
    finally:
        conn.close()


@app.route("/quittance/<int:quittance_id>")
def quittance_imprimable(quittance_id):
    """Quittance prête à imprimer, dans une page nue.

    Volontairement en HTML plutôt qu'en PDF : elle s'imprime depuis le
    navigateur (ou s'enregistre en PDF par la même boîte de dialogue),
    sans dépendre de reportlab — qui reste optionnel.
    """
    conn = _conn()
    try:
        return render_template_string(PAGE_QUITTANCE_IMPRIMABLE,
                                      q=quittances.detail(conn, quittance_id))
    except ValueError as exc:
        return redirect(url_for("quittances_page", err=str(exc)))
    finally:
        conn.close()


# ── Page Clôture ─────────────────────────────────────────────────────────────



@app.route("/cloture")
def cloture():
    conn   = _conn()
    annee  = _annee_param(conn)
    annees = _annees(conn)
    exercices = conn.execute(
        "SELECT * FROM exercice ORDER BY annee DESC"
    ).fetchall()

    ag_map   = {}
    anos_map = {}
    for ex in exercices:
        a = ex["annee"]
        try:
            ag_map[a] = fiscal.agregats(conn, a)
        except Exception:
            ag_map[a] = {"produits": 0, "charges_hors_daa": 0,
                         "dotation": 0, "resultat_comptable": 0, "plafond_39c": 0}
        try:
            anos_map[a] = controles.controler(conn, a) if ex["statut"] == "ouvert" else []
        except Exception:
            anos_map[a] = []
    conn.close()

    body = render_template_string(PAGE_CLOTURE,
        annee=annee, exercices=exercices, ag=ag_map, anos=anos_map)
    return _base(body, active="cloture", annee=annee, annees=annees,
                 flash_ok=request.args.get("ok",""),
                 flash_err=request.args.get("err",""),
                 flash_warn=request.args.get("warn",""))


@app.route("/cloturer", methods=["POST"])
def cloturer():
    annee = _form_int("annee")
    if annee is None:
        return redirect(url_for("cloture", err="Année de clôture invalide."))
    forcer = request.form.get("forcer") == "1"
    retr   = _form_float("retraitements", 0.0) or 0.0
    conn   = _conn()
    try:
        anos   = controles.controler(conn, annee)
        bloq   = controles.bloquants(anos)
        if bloq and not forcer:
            warn = (f"{len(bloq)} anomalie(s) bloquante(s) — cochez « Forcer » pour clôturer quand même.")
            conn.close()
            return redirect(url_for("cloture", annee=annee, warn=warn))

        # J6 — pérennité : sauvegarde AVANT l'opération la plus lourde de
        # conséquences, archivage FEC + empreinte SHA-256 APRÈS (piste
        # d'audit). Sans objet dans le bac à sable (dossier jetable).
        if not _en_bac_a_sable():
            perennite.sauvegarder(_db_path(), "avant-cloture")
        res = fiscal.cloturer(conn, annee, autres_retraitements=retr)
        info_archive = ""
        if not _en_bac_a_sable():
            arch = perennite.archiver_fec(conn, annee, _db_path())
            info_archive = (" | FEC archivé : "
                            f"{os.path.basename(arch['chemin'])}")
        conn.close()
        ag = res["agregats"]
        ok = (f"Exercice {annee} clôturé. "
              f"Résultat comptable : {ag['resultat_comptable']:.2f} € | "
              f"Résultat fiscal : {res['resultat_fiscal']:.2f} € | "
              f"Dotation : {ag['dotation']:.2f} €" + info_archive)
        return redirect(url_for("cloture", annee=annee, ok=ok))
    except Exception as exc:
        conn.close()
        return redirect(url_for("cloture", annee=annee, err=str(exc)))


# ── Page Nouvel exercice ─────────────────────────────────────────────────────



@app.route("/exercice/nouveau")
def exercice_nouveau():
    return _page_exercice_nouveau(None)


def _page_exercice_nouveau(conn_ouverte, analyse=None):
    """Rend la page. `analyse` porte le résultat d'une analyse
    multi-FEC, qui doit s'afficher SANS redirection — sinon le
    résultat serait perdu."""
    del conn_ouverte
    conn   = _conn()
    annee  = _annee_param(conn)
    annees = _annees(conn)
    exercices = conn.execute(
        "SELECT * FROM exercice ORDER BY annee DESC"
    ).fetchall()
    annee_suggere = (max(e["annee"] for e in exercices) + 1) if exercices else date.today().year
    prev_ouvert   = next(
        (e["annee"] for e in exercices if e["statut"] == "ouvert"), None
    )
    reprise_possible = any(
        e["annee"] == annee_suggere - 1 and e["statut"] == "clos" for e in exercices
    )
    conn.close()

    conn2 = _conn()
    veille_due = veille_fiscale.veille_a_refaire(conn2)
    derniere = veille_fiscale.derniere_veille(conn2)
    conn2.close()
    body = render_template_string(PAGE_EX_NOUVEAU,
        annee=annee, exercices=exercices,
        annee_suggere=annee_suggere, prev_ouvert=prev_ouvert,
        reprise_possible=reprise_possible, analyse=analyse,
        veille_due=veille_due, derniere_veille=derniere)
    return _base(body, active="exercice_nouveau", annee=annee, annees=annees,
                 flash_ok=request.args.get("ok",""),
                 flash_err=request.args.get("err",""))


@app.route("/exercice/ouvrir", methods=["POST"])
def exercice_ouvrir():
    conn = _conn()
    try:
        a    = _form_int("annee")
        if a is None:
            raise ValueError("Année d'exercice invalide.")
        deb  = request.form.get("date_debut", "")
        fin  = request.form.get("date_fin", "")
        exis = conn.execute("SELECT annee FROM exercice WHERE annee=?", (a,)).fetchone()
        if exis:
            raise ValueError(f"L'exercice {a} existe déjà.")
        conn.execute(
            "INSERT INTO exercice (annee, date_debut, date_fin, statut) VALUES (?,?,?,'ouvert')",
            (a, deb, fin)
        )
        conn.commit()

        msg = f"Exercice {a} ouvert ({deb} → {fin})."
        if veille_fiscale.veille_a_refaire(conn):
            msg += (" Pensez à votre veille fiscale avant de saisir : "
                    "voir le menu « Veille fiscale ».")
        if request.form.get("reprise") == "1":
            info = reprise.construire_an_interne(conn, a)
            d, c_ = reprise.controle_equilibre(conn, a)
            if abs(d - c_) > 0.005:
                raise ValueError("À-nouveaux déséquilibrés — reprise annulée.")
            msg += (f" À-nouveaux repris depuis {info['annee_source']} : "
                    f"{info['nb_comptes']} comptes, résultat reporté "
                    f"{info['resultat_reporte']:.2f} € (affecté au compte exploitant).")
        conn.close()
        return redirect(url_for("exercice_nouveau", annee=a, ok=msg))
    except Exception as exc:
        conn.close()
        return redirect(url_for("exercice_nouveau", err=str(exc)))


# ── Page Liasse fiscale ──────────────────────────────────────────────────────



def _eur(x) -> str:
    if x is None:
        return "—"
    return f"{x:,.2f} €".replace(",", " ").replace(".", ",")


@app.route("/liasse")
def liasse_page():
    conn   = _conn()
    annee  = _annee_param(conn)
    annees = _annees(conn)
    try:
        L = liasse_mod.generer(conn, annee)
        conn.close()
        body = render_template_string(PAGE_LIASSE, L=L, eur=_eur)
        return _base(body, active="liasse", annee=annee, annees=annees,
                     flash_ok=request.args.get("ok",""),
                     flash_err=request.args.get("err",""))
    except Exception as exc:
        conn.close()
        body = ('<div class="card"><div class="card-body">'
                f'Liasse indisponible : {escape(str(exc))}</div></div>')
        return _base(body, active="liasse", annee=annee, annees=annees,
                     flash_err=str(exc))


@app.route("/liasse.pdf")
def liasse_pdf_route():
    """J7 — export PDF de la liasse (ReportLab)."""
    conn  = _conn()
    annee = _annee_param(conn)
    try:
        import liasse_pdf                       # import différé : dépendance optionnelle
    except ImportError:
        conn.close()
        return redirect(url_for("liasse_page", annee=annee,
                                err="Export PDF indisponible : le module reportlab "
                                    "n'est pas installé (relancez le lanceur, ou "
                                    "« pip install reportlab » dans le .venv)."))
    try:
        L = liasse_mod.generer(conn, annee)
        conn.close()
        buffer = io.BytesIO()
        liasse_pdf.generer_pdf(L, buffer)
        buffer.seek(0)
        suffixe = "" if not L["provisoire"] else "-provisoire"
        return send_file(buffer, mimetype="application/pdf",
                         as_attachment=True,
                         download_name=f"liasse-lmnp-{annee}{suffixe}.pdf")
    except Exception as exc:
        conn.close()
        return redirect(url_for("liasse_page", annee=annee, err=str(exc)))


# ── Page Réglementation (règles versionnées + gabarits personnalisés) ────────



@app.route("/reglementation")
def reglementation():
    conn   = _conn()
    annee  = _annee_param(conn)
    annees = _annees(conn)
    regles = parametres.historique(conn)
    gabarits_mod.assurer_table(conn)
    conn.row_factory = sqlite3.Row
    persos = conn.execute("SELECT * FROM gabarit_personnalise WHERE actif=1 "
                          "ORDER BY libelle").fetchall()
    comptes = conn.execute("SELECT numero, libelle FROM compte "
                           "WHERE type IN ('charge','produit') ORDER BY numero").fetchall()
    conn.close()
    body = render_template_string(PAGE_REGLEMENTATION,
        regles=[type("R", (), dict(r,
                    impact_module=parametres.impact(r["cle"])[0],
                    impact_effet=parametres.impact(r["cle"])[1]))
                for r in regles],
        libelles_regles=sorted(parametres.LIBELLES.items(), key=lambda kv: kv[1]),
        persos=persos, comptes=comptes)
    return _base(body, active="reglementation", annee=annee, annees=annees,
                 flash_ok=request.args.get("ok",""),
                 flash_err=request.args.get("err",""))


@app.route("/reglementation/regle", methods=["POST"])
def reglementation_regle():
    conn = _conn()
    try:
        parametres.definir(conn, request.form["cle"],
                           float(request.form["valeur"]),
                           request.form["date_debut"],
                           reference=request.form.get("reference", ""),
                           commentaire=request.form.get("commentaire", ""))
        conn.close()
        return redirect(url_for("reglementation",
            ok=f"Nouvelle version de « {parametres.LIBELLES.get(request.form['cle'], request.form['cle'])} » "
               f"applicable à compter du {request.form['date_debut']}."))
    except Exception as exc:
        conn.close()
        return redirect(url_for("reglementation", err=str(exc)))


@app.route("/reglementation/gabarit", methods=["POST"])
def reglementation_gabarit():
    conn = _conn()
    try:
        lib = request.form["libelle"].strip()
        gabarits_mod.ajouter_personnalise(
            conn, cle=lib, libelle=lib,
            compte_num=request.form["compte_num"],
            nature=request.form["nature"],
            periodicite=request.form.get("periodicite", "variable"),
            retraitement="reintegration"
                if request.form.get("reintegration") == "1" else None)
        conn.close()
        return redirect(url_for("reglementation",
            ok=f"Catégorie « {lib} » ajoutée — disponible dans la saisie."))
    except Exception as exc:
        conn.close()
        return redirect(url_for("reglementation", err=str(exc)))


@app.route("/reglementation/compte", methods=["POST"])
def reglementation_compte():
    conn = _conn()
    try:
        num = request.form["numero"].strip()
        if len(num) != 6 or not num.isdigit():
            raise ValueError("Numéro de compte : 6 chiffres attendus.")
        conn.execute("INSERT INTO compte (numero, libelle, type, classe) "
                     "VALUES (?,?,?,?)",
                     (num, request.form["libelle"].strip(),
                      request.form["type"], int(num[0])))
        conn.commit()
        conn.close()
        return redirect(url_for("reglementation",
                                ok=f"Compte {num} créé."))
    except Exception as exc:
        conn.close()
        return redirect(url_for("reglementation", err=str(exc)))


# ── Page Bac à sable ─────────────────────────────────────────────────────────



# ── Page Dossiers (J8 : plusieurs comptabilités indépendantes) ──────────────





@app.route("/archives")
def archives_page():
    """Archives FEC du dossier COURANT.

    Elles étaient servies depuis le répertoire du dossier principal, y
    compris en bac à sable : la page proposait alors au téléchargement les
    FEC de la comptabilité réelle, sous un bandeau affirmant que celle-ci
    n'était pas touchée. Les répertoires sont désormais cloisonnés.
    """
    """Les FEC archivés à chaque clôture : c'est LE fichier que
    l'administration réclame lors d'un contrôle (art. L. 47 A-I du LPF).
    Ils existaient sur le disque mais rien ne permettait de les retrouver
    depuis l'interface."""
    conn = _conn()
    annee = _annee_param(conn)
    annees = _annees(conn)
    conn.close()
    dossier = perennite.dossier_archives(_db_path())
    fichiers = []
    if os.path.isdir(dossier):
        empreintes = {}
        manifeste = os.path.join(dossier, "manifeste.csv")
        if os.path.exists(manifeste):
            with open(manifeste, encoding="utf-8") as f:
                for ligne in f:
                    parts = [p.strip() for p in ligne.split(";")]
                    if len(parts) >= 2:
                        empreintes[os.path.basename(parts[0])] = parts[-1]
        for nom in sorted(os.listdir(dossier), reverse=True):
            if nom.lower().endswith(".txt"):
                chemin = os.path.join(dossier, nom)
                fichiers.append({"nom": nom,
                                 "ko": max(1, os.path.getsize(chemin) // 1024),
                                 "sha": (empreintes.get(nom) or "")[:16]})
    body = render_template_string(PAGE_ARCHIVES, fichiers=fichiers,
                                  dossier=dossier)
    return _base(body, active="archives", annee=annee, annees=annees,
                 flash_err=request.args.get("err", ""))


@app.route("/archives/<nom>")
def archive_telecharger(nom):
    """Téléchargement d'un FEC archivé. Le nom est réduit à son basename :
    aucun chemin relatif ne peut sortir du dossier d'archives."""
    dossier = perennite.dossier_archives(_db_path())
    chemin = os.path.join(dossier, os.path.basename(nom))
    if not os.path.isfile(chemin) or not chemin.lower().endswith(".txt"):
        return redirect(url_for("archives_page", err="Archive introuvable."))
    return send_file(chemin, as_attachment=True,
                     download_name=os.path.basename(chemin),
                     mimetype="text/plain")


@app.route("/sauvegardes/restaurer", methods=["POST"])
def sauvegardes_restaurer():
    if _en_bac_a_sable():
        return redirect(url_for("dossiers_page",
                                err="Pas de restauration en bac à sable."))
    conn = _conn()
    annee = _annee_param(conn)
    conn.close()                          # aucune connexion pendant la copie
    nom = os.path.basename((request.form.get("nom") or "").strip())
    chemin = os.path.join(perennite.dossier_sauvegardes(_db_path()), nom)
    try:
        perennite.restaurer(_db_path(), chemin)
        return redirect(url_for("dossiers_page", annee=annee,
                                ok=f"Dossier restauré depuis {nom}. L'état "
                                   "précédent est conservé en « avant-"
                                   "restauration »."))
    except Exception as exc:
        return redirect(url_for("dossiers_page", annee=annee,
                                err=f"Restauration refusée — {exc}"))


@app.route("/dossiers")
def dossiers_page():
    conn   = _conn()
    annee  = _annee_param(conn)
    annees = _annees(conn)
    conn.close()
    liste = dossiers_mod.lister(HERE, DB)
    sauvegardes = [] if _en_bac_a_sable() else [
        dict(sv, taille_ko=os.path.getsize(sv["chemin"]) // 1024)
        for sv in perennite.lister_sauvegardes(_db_path())]
    # Dossier vierge : la configuration initiale passe DEVANT la gestion
    # des dossiers. Un débutant ne cherche pas à gérer des dossiers, il
    # cherche par où commencer.
    tete = ("" if _dossier_configure()
            else render_template_string(PAGE_DEMARRAGE))
    body = tete + render_template_string(PAGE_DOSSIERS, liste=liste,
                                  actif=_dossier_actif()) + \
           render_template_string(PAGE_SAUVEGARDES_SECTION,
                                  sauvegardes=sauvegardes)
    return _base(body, active="dossiers", annee=annee, annees=annees,
                 flash_ok=request.args.get("ok", ""),
                 flash_err=request.args.get("err", ""))


@app.route("/dossiers/creer", methods=["POST"])
def dossiers_creer():
    try:
        d = dossiers_mod.creer(HERE, request.form.get("nom", ""))
    except ValueError as exc:
        return redirect(url_for("dossiers_page", err=str(exc)))
    msg = (f"Dossier existant « {d['nom']} » retrouvé sur le disque et "
           "rattaché au registre (données conservées)."
           if d.get("adopte") else f"Dossier « {d['nom']} » créé et ouvert.")
    resp = redirect(url_for("dossiers_page", ok=msg))
    resp.set_cookie("dossier", d["slug"], max_age=180*24*3600, samesite="Lax")
    resp.delete_cookie("dossier_retour")     # mémo bac à sable devenu caduc
    return resp


@app.route("/dossiers/ouvrir", methods=["POST"])
def dossiers_ouvrir():
    slug = request.form.get("slug", "")
    if slug == dossiers_mod.PRINCIPAL:
        resp = redirect(url_for("dossiers_page", ok="Dossier principal ouvert."))
        resp.delete_cookie("dossier")
        return resp
    if not (dossiers_mod.slug_sur(slug) and dossiers_mod.chemin_db(HERE, slug)):
        return redirect(url_for("dossiers_page", err="Dossier inconnu."))
    resp = redirect(url_for("dossiers_page",
                            ok=f"Dossier « {dossiers_mod.nom(HERE, slug)} » ouvert."))
    resp.set_cookie("dossier", slug, max_age=180*24*3600, samesite="Lax")
    resp.delete_cookie("dossier_retour")     # mémo bac à sable devenu caduc
    return resp


@app.route("/dossiers/renommer", methods=["POST"])
def dossiers_renommer():
    try:
        dossiers_mod.renommer(HERE, request.form.get("slug", ""),
                              request.form.get("nom", ""))
    except ValueError as exc:
        return redirect(url_for("dossiers_page", err=str(exc)))
    return redirect(url_for("dossiers_page", ok="Dossier renommé."))


@app.route("/bac-a-sable")
def bac_a_sable():
    conn   = _conn()
    annee  = _annee_param(conn)
    annees = _annees(conn)
    conn.close()
    body = render_template_string(PAGE_SANDBOX, actif=_en_bac_a_sable(),
                                  rapport=request.args.get("rapport"))
    return _base(body, active="bac_a_sable", annee=annee, annees=annees,
                 flash_ok=request.args.get("ok",""),
                 flash_err=request.args.get("err",""))


@app.route("/bac-a-sable/activer", methods=["POST"])
def bac_a_sable_activer():
    if not os.path.exists(BAC_A_SABLE_DB):
        init_db.init(BAC_A_SABLE_DB, "blanc",
                     annee_cible=date.today().year, ecraser=True).close()
    resp = redirect(url_for("bac_a_sable",
                            ok="Bac à sable activé — vous travaillez sur le dossier d'essai."))
    # Mémorise le dossier de travail pour y REVENIR en quittant le bac à sable.
    # Même durée que les autres dossiers. À 8 h, le cookie expirait tout
    # seul — souvent d'un jour à l'autre — et l'utilisateur se retrouvait
    # dans le dossier PRINCIPAL en croyant être encore dans le bac à
    # sable : une page de propositions d'import laissée ouverte la veille
    # écrivait alors dans la comptabilité réelle.
    resp.set_cookie("dossier_retour", _dossier_actif(),
                    max_age=180*24*3600, samesite="Lax")
    resp.set_cookie("dossier", "bac_a_sable",
                    max_age=180*24*3600, samesite="Lax")
    return resp


@app.route("/bac-a-sable/quitter", methods=["POST"])
def bac_a_sable_quitter():
    resp = redirect(url_for("bac_a_sable",
                            ok="Retour au dossier réel."))
    retour = request.cookies.get("dossier_retour", "")
    if dossiers_mod.slug_sur(retour) and dossiers_mod.chemin_db(HERE, retour):
        resp.set_cookie("dossier", retour, max_age=180*24*3600, samesite="Lax")
    else:
        resp.delete_cookie("dossier")
    resp.delete_cookie("dossier_retour")
    return resp


@app.route("/bac-a-sable/reset", methods=["POST"])
def bac_a_sable_reset():
    mode = request.form.get("mode", "blanc")
    try:
        init_db.init(BAC_A_SABLE_DB, mode,
                     annee_cible=date.today().year, ecraser=True).close()
        ok = (f"Bac à sable réinitialisé en mode {mode} "
              f"({'dossier vierge' if mode == 'blanc' else 'dossier d’exemple'}).")
        return redirect(url_for("bac_a_sable", ok=ok))
    except Exception as exc:
        return redirect(url_for("bac_a_sable", err=str(exc)))


@app.route("/bac-a-sable/audit", methods=["POST"])
def bac_a_sable_audit():
    r = audit_cycle.executer()          # base jetable dédiée, jamais la réelle
    return redirect(url_for("bac_a_sable", rapport=r.texte(),
                            ok="Audit conforme ✓" if r.succes
                               else f"{len(r.echecs)} vérification(s) en échec ✗"))


# ── Démarrage (HTTPS local si certificat présent) ────────────────────────────

CERT_DIR  = os.path.join(HERE, "certs")
CERT_FILE = os.path.join(CERT_DIR, "cert.pem")
KEY_FILE  = os.path.join(CERT_DIR, "key.pem")





@app.route("/pense-bete")
def pense_bete_page():
    conn = _conn()
    try:
        annee = _annee_param(conn)
        rappels = pense_bete.rappels(conn, db_path=_db_path())
        body = render_template_string(
            PAGE_PENSE_BETE, rappels=rappels,
            oublis=pense_bete.oublis_frequents(),
            actualites=pense_bete.actualites(),
            notes=pense_bete.lire_notes(conn),
            badge={"important": "🔴", "a_prevoir": "🟠", "info": "🔵"})
        return _base(body, active="pense_bete", annee=annee,
                     annees=_annees(conn))
    finally:
        conn.close()




@app.route("/immobilisations/bien/<int:bien_id>/ceder", methods=["POST"])
def bien_ceder(bien_id):
    conn = _conn()
    try:
        annee = _annee_param(conn)
        r = cession.ceder_bien(
            conn, bien_id,
            date_cession=(request.form.get("date_cession") or "").strip(),
            prix_cession=_form_float("prix_cession", -1))
        ok = (f"Cession de {r['bien']} enregistrée : dotation complémentaire "
              f"{r['dotation_complementaire']:.2f} €, VNC sortie "
              f"{r['vnc_sortie']:.2f} €, prix {r['prix_cession']:.2f} € "
              f"({'plus' if r['pv_comptable'] >= 0 else 'moins'}-value comptable "
              f"{abs(r['pv_comptable']):.2f} €, neutralisée fiscalement — "
              "voir le Pense-bête pour les démarches).")
        return redirect(url_for("immobilisations", annee=annee, ok=ok))
    except Exception as exc:
        return redirect(url_for("immobilisations",
                                annee=request.form.get("annee", type=int)
                                or date.today().year,
                                err=f"Cession refusée — {exc}"))
    finally:
        conn.close()






@app.route("/veille")
def veille_page():
    conn = _conn()
    try:
        annee = _annee_param(conn)
        v = veille_fiscale.resume(conn, annee)
        body = render_template_string(PAGE_VEILLE, v=v)
        return _base(body, active="veille", annee=annee, annees=_annees(conn),
                     flash_ok=request.args.get("ok", ""))
    finally:
        conn.close()


@app.route("/veille/faite", methods=["POST"])
def veille_faite():
    conn = _conn()
    try:
        annee = _annee_param(conn)
        jour = veille_fiscale.enregistrer_veille(conn)
        return redirect(url_for("veille_page", annee=annee,
                                ok=f"Veille enregistrée au {jour}. Si une "
                                   "règle a changé, mettez-la à jour dans le "
                                   "menu « Réglementation » (les règles sont "
                                   "datées : l'historique est conservé)."))
    finally:
        conn.close()


@app.route("/operation/<int:operation_id>/annuler", methods=["POST"])
def operation_annuler(operation_id):
    """Annulation par contre-passation : écriture inverse, jamais de
    suppression — la numérotation du FEC reste dense, la piste complète."""
    conn = _conn()
    try:
        r = operations.annuler(conn, operation_id)
        ok = (f"Opération {operation_id} annulée par contre-passation "
              f"(écriture {r['ecriture_annulation']}). Les montants se "
              "neutralisent dans tous les calculs ; rien n'est supprimé.")
        return redirect(url_for("saisie", ok=ok))
    except Exception as exc:
        return redirect(url_for("saisie", err=str(exc)))
    finally:
        conn.close()


def _dossier_imports() -> str:
    """Répertoire des fichiers reçus, PROPRE au dossier courant.

    Il dérivait du répertoire parent de la base, que le dossier principal
    et le bac à sable partagent : un import préparé en bac à sable, puis
    validé après une bascule ou l'expiration du cookie, écrivait ses
    opérations dans la comptabilité RÉELLE. Le jeton passait tous les
    contrôles, le fichier existait — rien ne pouvait le détecter.
    """
    base = os.path.dirname(os.path.abspath(_db_path()))
    stem = os.path.splitext(os.path.basename(_db_path()))[0]
    chemin = (os.path.join(base, "imports_tmp") if stem == "compta"
              else os.path.join(base, "imports_tmp", stem))
    os.makedirs(chemin, exist_ok=True)
    return chemin


@app.route("/import/proposer", methods=["POST"])
def import_proposer():
    """Étape 1 : analyse du relevé, PROPOSITIONS seulement — rien n'est
    écrit sans validation explicite (étape 2)."""
    f = request.files.get("releve")
    if f is None or not f.filename:
        return redirect(url_for("saisie", err="Choisissez un fichier de "
                                              "relevé (CSV)."))
    conn = _conn()
    try:
        jeton = uuid.uuid4().hex
        chemin = os.path.join(_dossier_imports(), jeton + ".csv")
        f.save(chemin)
        analyse = import_bancaire.analyser(chemin, conn)
        props, rejets = analyse["propositions"], analyse["rejets"]
        if not props:
            os.remove(chemin)
            detail = ""
            if rejets:
                # Un relevé entièrement dans un format de montant non lu
                # produisait « aucune ligne exploitable » : l'utilisateur
                # croyait son fichier vide. Il doit voir la vraie raison.
                ex = rejets[0]
                detail = (f" {len(rejets)} ligne(s) rejetée(s), la première "
                          f"en ligne {ex['ligne']} : {ex['raison']}.")
            return redirect(url_for("saisie", err="Aucune ligne exploitable "
                                                  "dans ce relevé." + detail))
        annee = _annee_param(conn)
        annees = _annees(conn)
        biens = conn.execute("SELECT id, libelle FROM bien ORDER BY id").fetchall()
        choix_groupes, produit_types, libs = _catalogue(conn)
        perio = {k: g["periodicite"] for k, g in gabarits_mod.tous(conn).items()}
        ops = []
        body = render_template_string(PAGE_SAISIE,
            annee=annee, today=date.today().isoformat(),
            choix_groupes=choix_groupes, biens=biens, ops=ops,
            produit_types=produit_types, gabarits_lib=libs,
            perio_json=json.dumps(perio),
        ) + render_template_string(PAGE_IMPORT_SECTION,
            propositions=props, jeton=jeton)
        avertissement = ("" if not rejets else
                         f" {len(rejets)} ligne(s) du relevé n'ont PAS pu "
                         f"être lues (première : ligne {rejets[0]['ligne']}, "
                         f"{rejets[0]['raison']}) — vérifiez-les à la main.")
        return _base(body, active="saisie", annee=annee, annees=annees,
                     flash_ok=f"{len(props)} proposition(s) — cochez et "
                              "validez ci-dessous." + avertissement)
    except ValueError as exc:
        return redirect(url_for("saisie", err=str(exc)))
    finally:
        conn.close()


@app.route("/import/valider", methods=["POST"])
def import_valider():
    """Étape 2 : insertion des lignes COCHÉES uniquement."""
    jeton = request.form.get("jeton", "")
    chemin = os.path.join(_dossier_imports(), os.path.basename(jeton) + ".csv")
    if not re.fullmatch(r"[0-9a-f]{32}", jeton) or not os.path.exists(chemin):
        return redirect(url_for("saisie", err="Session d'import expirée — "
                                              "relancez l'analyse."))
    retenues = {int(i) for i in request.form.getlist("ligne")}
    conn = _conn()
    try:
        props = import_bancaire.proposer(chemin, conn)
        faites, ecartees = 0, 0
        for i, p in enumerate(props):
            if i not in retenues:
                ecartees += 1
                continue
            operations.saisir(conn, type=p["type"], montant=p["montant"],
                              date_operation=p["date_operation"],
                              periode=p.get("periode"),
                              libelle=p.get("libelle"), source="import")
            faites += 1
        os.remove(chemin)
        return redirect(url_for("saisie",
            ok=f"Import terminé : {faites} opération(s) enregistrée(s), "
               f"{ecartees} écartée(s)."))
    except Exception as exc:
        return redirect(url_for("saisie", err=f"Import interrompu : {exc}"))
    finally:
        conn.close()


@app.route("/exercice/analyser-fec", methods=["POST"])
def exercice_analyser_fec():
    """Analyse PLUSIEURS FEC sans rien écrire.

    Deux temps volontairement séparés : une migration est irréversible en
    pratique (on ne défait pas trois exercices d'un clic), et l'utilisateur
    doit voir ce que le logiciel a compris — l'ordre déduit, les jonctions,
    les dotations — AVANT de s'engager.
    """
    fichiers = [f for f in request.files.getlist("fecs") if f and f.filename]
    if not fichiers:
        return redirect(url_for("exercice_nouveau",
                                err="Sélectionnez au moins un fichier FEC."))
    conn = _conn()
    try:
        jeton = uuid.uuid4().hex
        dossier = os.path.join(_dossier_imports(), jeton)
        os.makedirs(dossier, exist_ok=True)
        chemins = []
        for n, f in enumerate(fichiers):
            c = os.path.join(dossier, f"{n:02d}.txt")
            f.save(c)
            chemins.append(c)
        ordre = migration_fec.ordonner(chemins)
        for x, f in zip(ordre, [None] * len(ordre)):
            del f
        noms = {c: f.filename for c, f in zip(chemins, fichiers)}
        for x in ordre:
            x["nom"] = noms.get(x["chemin"], "")
            x["dotations"] = migration_fec.dotations_du_fec(x["chemin"])
        deja = {r[0] for r in conn.execute("SELECT annee FROM exercice")}
        for x in ordre:
            if x["annee"] and x["annee"] in deja:
                x["erreurs"].append(
                    f"l'exercice {x['annee']} existe déjà dans ce dossier : "
                    "il ne sera pas repris.")
        obs = (migration_fec.controler_jonctions(ordre)
               + migration_fec.controler_amortissements(conn, ordre))
        reprenables = sum(1 for x in ordre if x["annee"] and not x["erreurs"])
        analyse = {"fichiers": ordre, "observations": obs,
                   "jeton": jeton, "reprenables": reprenables}
        return _page_exercice_nouveau(None, analyse=analyse)
    except Exception as exc:
        return redirect(url_for("exercice_nouveau", err=str(exc)))
    finally:
        conn.close()


@app.route("/exercice/reprendre-fec-multi", methods=["POST"])
def exercice_reprendre_fec_multi():
    """Rejoue les exercices analysés, DU PLUS ANCIEN AU PLUS RÉCENT.

    L'ordre est imposé par les données : rejouer 2025 avant 2023
    produirait des à-nouveaux absurdes, et l'utilisateur n'a aucune raison
    de connaître cette contrainte.
    """
    jeton = request.form.get("jeton", "")
    if not re.fullmatch(r"[0-9a-f]{32}", jeton):
        return redirect(url_for("exercice_nouveau",
                                err="Session d'analyse expirée — recommencez."))
    dossier = os.path.join(_dossier_imports(), jeton)
    if not os.path.isdir(dossier):
        return redirect(url_for("exercice_nouveau",
                                err="Session d'analyse expirée — recommencez."))
    conn = _conn()
    try:
        chemins = [os.path.join(dossier, n) for n in sorted(os.listdir(dossier))]
        ordre = migration_fec.ordonner(chemins)
        deja = {r[0] for r in conn.execute("SELECT annee FROM exercice")}
        faits, ignores = [], []
        for x in ordre:
            a = x["annee"]
            if not a or a in deja:
                ignores.append(str(a or "?"))
                continue
            conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, "
                         "statut) VALUES (?,?,?,'ouvert')",
                         (a, f"{a}-01-01", f"{a}-12-31"))
            res = rejeu_fec.rejouer(conn, x["chemin"], a)
            faits.append(f"{a} ({res['ecritures']} écritures)")
            deja.add(a)
        conn.commit()
        if not faits:
            raise ValueError("Aucun exercice repris : tous étaient déjà "
                             "présents ou illisibles.")
        msg = ("Exercices repris du plus ancien au plus récent : "
               + ", ".join(faits) + ".")
        if ignores:
            msg += f" Ignorés : {', '.join(ignores)}."
        msg += (" Vérifiez la balance de chaque exercice, puis clôturez-les "
                "dans l'ordre.")
        return redirect(url_for("exercice_nouveau", ok=msg))
    except Exception as exc:
        conn.rollback()
        return redirect(url_for("exercice_nouveau",
                                err=f"Reprise interrompue : {exc}"))
    finally:
        conn.close()
        import shutil
        shutil.rmtree(dossier, ignore_errors=True)


@app.route("/exercice/reprendre-fec", methods=["POST"])
def exercice_reprendre_fec():
    """Reprise d'un exercice complet depuis son FEC (migration depuis un
    prestataire de comptabilité LMNP) :
    exercice créé puis fichier rejoué écriture par écriture."""
    f = request.files.get("fec")
    a = _form_int("annee")
    if f is None or not f.filename or a is None:
        return redirect(url_for("exercice_nouveau",
                                err="Année et fichier FEC requis."))
    conn = _conn()
    chemin = os.path.join(_dossier_imports(), uuid.uuid4().hex + ".txt")
    try:
        f.save(chemin)
        if conn.execute("SELECT 1 FROM exercice WHERE annee=?", (a,)).fetchone():
            raise ValueError(f"L'exercice {a} existe déjà : la reprise crée "
                             "l'exercice, elle ne complète pas un exercice "
                             "existant.")
        conn.execute("INSERT INTO exercice (annee, date_debut, date_fin, "
                     "statut) VALUES (?,?,?,'ouvert')",
                     (a, f"{a}-01-01", f"{a}-12-31"))
        res = rejeu_fec.rejouer(conn, chemin, a)
        conn.commit()
        ok = (f"Exercice {a} repris depuis le FEC : {res['ecritures']} "
              f"écritures rejouées, {len(res['comptes_crees'])} compte(s) "
              f"créé(s) depuis le fichier"
              + (f", {res['normalisees']} ligne(s) à montant négatif "
                 f"normalisée(s) par équivalence comptable" if res.get("normalisees") else "")
              + ". Vérifiez la balance puis clôturez normalement.")
        return redirect(url_for("exercice_nouveau", annee=a, ok=ok))
    except Exception as exc:
        conn.rollback()
        return redirect(url_for("exercice_nouveau", err=f"Reprise refusée : {exc}"))
    finally:
        conn.close()
        if os.path.exists(chemin):
            os.remove(chemin)


if __name__ == "__main__":
    if not os.path.exists(DB):
        print("Base absente — initialisation en mode blanc…")
        init_db.init(DB, "blanc", annee_cible=date.today().year).close()
        print(f"Base créée : {DB}")

    tous = [e["chemin"] for e in dossiers_mod.lister(HERE, DB) if e["existe"]]
    import migrations
    for r in migrations.migrer_tous(tous):
        if r.get("erreur"):
            print(f"⚠ Migration impossible ({r['chemin']}): {r['erreur']}")
        elif r["apres"] > r["avant"]:
            print(f"✓ Dossier mis à jour (schéma {r['avant']} → {r['apres']}) "
                  f"— copie de sûreté : {r['sauvegarde']}")
    for sauvegarde in perennite.sauvegardes_quotidiennes(tous):
        print(f"✓ Sauvegarde quotidienne : {sauvegarde}")

    debug = os.environ.get("COMPTA_DEBUG") == "1"     # jamais en debug par défaut
    port = int(os.environ.get("COMPTA_PORT", "5000")) # port de repli si 5000 occupé

    # L'avertissement « development server » de Flask vise les déploiements
    # PUBLICS sur internet (montée en charge, durcissement). Il ne s'applique
    # pas à un logiciel local mono-utilisateur lié à 127.0.0.1 : on le filtre
    # et on affiche à la place une explication exacte du contexte.

    class _FiltreAvertissementDev(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            return ("development server" not in msg
                    and "production WSGI server" not in msg)

    logging.getLogger("werkzeug").addFilter(_FiltreAvertissementDev())
    print("ℹ Serveur local mono-utilisateur : l'application n'écoute que sur "
          "127.0.0.1 (votre machine), n'est jamais exposée au réseau, et le "
          "mode debug est désactivé. L'avertissement « development server » "
          "de Flask, qui vise les sites publics sur internet, ne s'applique "
          "pas à cet usage.")
    # HTTP par défaut sur la boucle locale — décision assumée, revue en
    # v8.15.0 après retour d'usage. Un certificat AUTO-SIGNÉ ne peut pas
    # être validé par le navigateur : il affiche un avertissement plein
    # écran au premier accès, puis un cadenas barré à chaque lancement,
    # définitivement. Ce n'est pas un défaut de configuration, c'est la
    # nature d'un certificat que personne n'a signé.
    #
    # Or il ne protège rien ici : l'application n'écoute que sur 127.0.0.1,
    # les données ne quittent jamais la machine et ne traversent aucun
    # réseau. Le seul effet réel du HTTPS local est donc d'habituer
    # l'utilisateur à passer outre les avertissements de sécurité de son
    # navigateur — exactement le réflexe qu'il ne faut pas installer.
    #
    # Les navigateurs traitent d'ailleurs http://localhost comme un
    # CONTEXTE SÉCURISÉ, au même titre que HTTPS : aucune fonctionnalité
    # web n'est perdue. HTTPS reste disponible sur demande explicite
    # (COMPTA_HTTPS=1), pour qui expose l'application autrement.
    ssl_ctx = None
    if os.environ.get("COMPTA_HTTPS") == "1":
        if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
            ssl_ctx = (CERT_FILE, KEY_FILE)
            print(f"HTTPS actif → https://localhost:{port}")
            print("  Le navigateur signalera un certificat non vérifié : "
                  "c'est normal pour un certificat auto-signé.")
        else:
            print("⚠ COMPTA_HTTPS=1 mais aucun certificat "
                  "(certs/cert.pem, certs/key.pem) — démarrage en HTTP.")
    if ssl_ctx is None:
        print(f"→ http://localhost:{port}")
        print("  Pas de cadenas dans la barre d'adresse, et c'est normal : "
              "vos données ne quittent pas votre ordinateur, elles ne "
              "traversent aucun réseau. Les navigateurs considèrent "
              "d'ailleurs localhost comme un contexte sécurisé.")

    # 127.0.0.1 : l'application n'est jamais exposée au réseau local.
    app.run(host="127.0.0.1", port=port, debug=debug, ssl_context=ssl_ctx)
