# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
L'installation est-elle d'un seul tenant ?

Défaut rencontré en usage réel (v8.53.0) : l'onglet Liasse tombait tout
entier sur « unsupported format string passed to Undefined.__format__ ».
Ni le gabarit ni le module de calcul n'étaient fautifs — le gabarit
demandait un champ que le module installé À CÔTÉ ne produisait pas encore.
Une installation MÉLANGÉE, où des fichiers de deux versions cohabitaient
parce qu'un paquet avait été décompressé par-dessus un autre sans tout
remplacer.

Rien ne le signalait. Le logiciel démarrait, servait ses pages, et le
défaut ne se manifestait qu'à l'écran le plus éloigné de sa cause.

## Deux cas, deux réponses — et surtout pas la même

**Un fichier MANQUE** : l'installation est incomplète, sans ambiguïté
possible. On refuse de servir, en nommant les fichiers absents. Continuer
reviendrait à écrire dans une comptabilité avec un logiciel dont on sait
qu'il est amputé.

**Un fichier DIFFÈRE** : impossible de distinguer une installation
périmée d'une modification volontaire — et la licence AGPL donne
explicitement le droit de modifier ce code. Refuser de démarrer
transformerait une liberté accordée par la licence en panne. On
AVERTIT donc, visiblement et à chaque page, en nommant les fichiers ; c'est
ce qui aurait donné le diagnostic en une seconde dans le cas ci-dessus.

## Quand le manifeste est absent

Dans l'arborescence de développement, il n'y en a pas : le manifeste est
produit à la construction du paquet. Son absence y est donc NORMALE, et
`tests/` permet de reconnaître ce cas sans se tromper.

Hors de là — chez un utilisateur — un manifeste absent est un manifeste
perdu, et la garde le dit au lieu de conclure au vert. Un contrôle qui
approuve faute de pouvoir travailler est pire que pas de contrôle.
"""
from __future__ import annotations

import hashlib
import json
import os

MANIFESTE = "MANIFESTE.json"

# Verdicts
OK = "ok"
NON_APPLICABLE = "non_applicable"      # arborescence de développement
ABSENT = "absent"                      # manifeste perdu chez l'utilisateur
INCOMPLETE = "incomplete"              # des fichiers manquent → refus
MODIFIEE = "modifiee"                  # des fichiers diffèrent → avertissement


def empreinte(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def construire_manifeste(version: str, fichiers: dict[str, bytes]) -> str:
    """Le manifeste, tel qu'il est déposé dans le paquet.

    `fichiers` porte les octets RÉELLEMENT livrés — pas ceux du disque :
    les documents Markdown sont réécrits à la construction (leurs liens
    relatifs changent entre le dépôt et le paquet), et un manifeste calculé
    sur la source annoncerait une différence à chaque démarrage.
    """
    return json.dumps(
        {"version": version,
         "fichiers": {chemin: empreinte(contenu)
                      for chemin, contenu in sorted(fichiers.items())}},
        ensure_ascii=False, indent=1, sort_keys=True)


def _est_arborescence_de_developpement(racine: str) -> bool:
    return os.path.isdir(os.path.join(racine, "tests"))


def verifier(racine: str) -> dict:
    """Confronte l'installation à son manifeste.

    Rend un dict : `statut`, `version`, `manquants`, `differents`.
    """
    resultat = {"statut": OK, "version": None,
                "manquants": [], "differents": []}
    chemin = os.path.join(racine, MANIFESTE)
    if not os.path.exists(chemin):
        resultat["statut"] = (NON_APPLICABLE
                              if _est_arborescence_de_developpement(racine)
                              else ABSENT)
        return resultat
    try:
        with open(chemin, encoding="utf-8") as f:
            manifeste = json.load(f)
        attendus = dict(manifeste["fichiers"])
        resultat["version"] = manifeste.get("version")
    except (OSError, ValueError, KeyError, TypeError):
        # Un manifeste illisible ne vaut pas un manifeste absent : il était
        # là, et on ne sait plus ce qu'il disait.
        resultat["statut"] = ABSENT
        return resultat

    for relatif, attendue in attendus.items():
        absolu = os.path.join(racine, relatif)
        if not os.path.exists(absolu):
            resultat["manquants"].append(relatif)
            continue
        try:
            with open(absolu, "rb") as f:
                obtenue = empreinte(f.read())
        except OSError:
            resultat["manquants"].append(relatif)
            continue
        if obtenue != attendue:
            resultat["differents"].append(relatif)

    if resultat["manquants"]:
        resultat["statut"] = INCOMPLETE
    elif resultat["differents"]:
        resultat["statut"] = MODIFIEE
    return resultat


def message(resultat: dict) -> str:
    """Ce que l'utilisateur doit lire — en clair, et avec quoi agir."""
    version = resultat.get("version") or "inconnue"
    if resultat["statut"] == INCOMPLETE:
        liste = "\n".join(f"  - {f}" for f in resultat["manquants"][:20])
        reste = len(resultat["manquants"]) - 20
        if reste > 0:
            liste += f"\n  … et {reste} autre(s)"
        return (
            f"INSTALLATION INCOMPLÈTE (version {version}).\n\n"
            f"{len(resultat['manquants'])} fichier(s) du logiciel manquent :\n"
            f"{liste}\n\n"
            "Le logiciel refuse de servir dans cet état : il vaut mieux "
            "s'arrêter ici que tenir une comptabilité avec un programme dont "
            "on sait qu'il est amputé.\n\n"
            "QUE FAIRE — décompressez À NOUVEAU le paquet complet de cette "
            "version, dans un dossier VIDE, puis recopiez-y votre "
            "compta.db, vos sauvegardes et vos archives. Vos données ne "
            "sont pas en cause et ne sont pas touchées.")
    if resultat["statut"] == ABSENT:
        return (
            "MANIFESTE D'INSTALLATION INTROUVABLE.\n\n"
            "Le fichier qui permet de vérifier que cette installation est "
            "complète a disparu. Le logiciel fonctionne, mais plus rien ne "
            "garantit que ses fichiers vont ensemble — et c'est précisément "
            "ce qui produit des erreurs incompréhensibles, très loin de leur "
            "cause.\n\n"
            "QUE FAIRE — redécompressez le paquet de votre version par-dessus "
            "cette installation.")
    if resultat["statut"] == MODIFIEE:
        liste = ", ".join(resultat["differents"][:8])
        reste = len(resultat["differents"]) - 8
        if reste > 0:
            liste += f" … (+{reste})"
        return (
            f"Installation modifiée par rapport à la version {version} : "
            f"{len(resultat['differents'])} fichier(s) diffèrent — {liste}. "
            "Si vous n'avez rien modifié volontairement, votre installation "
            "mélange probablement deux versions : redécompressez le paquet "
            "complet dans un dossier vide. C'est la cause la plus fréquente "
            "des erreurs qui n'ont aucun rapport apparent avec ce qu'on "
            "faisait.")
    return ""


# ── Branchement sur l'application ─────────────────────────────────────────
#
# La garde vit ici plutôt que dans app.py, pour la même raison que les
# gardes HTTP : elle ne dépend ni de la base, ni du dossier actif, ni des
# routes — et le point d'entrée est au plafond que lui impose sa garde
# anti-monolithe.

# Racine de l'INSTALLATION : le dossier qui contient app.py et modules/.
# Déduite de ce fichier, jamais d'une variable que les tests déplacent pour
# désigner l'emplacement des DONNÉES. Ce sont deux choses différentes, et
# les confondre ferait vérifier l'intégrité d'un répertoire temporaire.
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ETAT: dict | None = None
_JOURNAL = None


def etat(racine: str | None = None) -> dict:
    """Le verdict, calculé UNE fois par exécution.

    Relire et hacher l'arborescence à chaque requête coûterait cher pour
    une réponse qui ne change pas : les fichiers du logiciel ne bougent pas
    pendant qu'il tourne. Un redémarrage suffit à reprendre la mesure —
    c'est justement ce qu'on demande à l'utilisateur après réinstallation.
    """
    global _ETAT
    if _ETAT is None:
        _ETAT = verifier(racine or RACINE)
        if _ETAT["statut"] not in (OK, NON_APPLICABLE) and _JOURNAL:
            _JOURNAL("Intégrité de l'installation — %s",
                     message(_ETAT).replace("\n", " ")[:300])
    return _ETAT


def banniere() -> str:
    """Bandeau HTML pour les cas qui n'empêchent pas de travailler.

    Un fichier qui DIFFÈRE peut être une modification volontaire : la
    licence AGPL donne ce droit, et refuser de démarrer le transformerait
    en panne. On avertit donc, mais à chaque page — c'est ce qui aurait
    donné le diagnostic en une seconde le jour où deux versions
    cohabitaient dans la même installation.
    """
    resultat = etat()
    if resultat["statut"] not in (MODIFIEE, ABSENT):
        return ""
    from markupsafe import escape
    return ('<div style="background:#7a4a00;color:#ffe8b8;text-align:center;'
            'padding:8px 16px;font-weight:600">⚠ '
            f'{escape(message(resultat).splitlines()[0])} '
            '<span style="font-weight:400">Détail dans le journal '
            '(logs/erreurs.log).</span></div>')


def enregistrer(app, journal=None) -> None:
    """Branche le refus des installations INCOMPLÈTES.

    Les autres cas ne passent pas par là : ils n'empêchent pas de
    travailler, et c'est `banniere()` qui les porte.
    """
    global _JOURNAL
    _JOURNAL = journal

    @app.before_request
    def _garde_integrite():                      # noqa: ANN202
        if etat()["statut"] == INCOMPLETE:
            return (message(etat()), 409,
                    {"Content-Type": "text/plain; charset=utf-8"})
        return None


def exiger_installation_complete(sortie=None) -> None:
    """À appeler AVANT les imports métier, et c'est tout l'enjeu.

    Le refus en cours de requête ne sert que si l'application a pu
    démarrer. Or un MODULE manquant la fait échouer à l'import — le
    lanceur affiche alors un `ModuleNotFoundError` nu, qui nomme certes le
    module mais ne dit ni pourquoi il manque, ni quoi faire. La garde
    n'avait jamais la parole : reproduit en retirant `modules/liasse.py`
    d'une installation.

    Elle parle donc avant, sur la console — que le lanceur garde ouverte
    précisément pour ça — puis arrête le programme. Un logiciel de
    comptabilité amputé ne doit pas s'ouvrir sur une base réelle.
    """
    import sys
    resultat = etat()
    if resultat["statut"] != INCOMPLETE:
        return
    flux = sortie or sys.stderr
    print("\n" + "=" * 70, file=flux)
    print(message(resultat), file=flux)
    print("=" * 70 + "\n", file=flux)
    raise SystemExit(1)
