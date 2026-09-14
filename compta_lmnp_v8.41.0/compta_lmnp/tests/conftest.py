# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

import os
import sys

# Rend le paquet importable depuis tests/ : la racine pour les points
# d'entrée et les outils (app, cli, verifier_depot…), et modules/ pour les
# modules métier, qui y ont été regroupés pour ne plus noyer LISEZ-MOI.md et
# les lanceurs sous trente-cinq fichiers Python.
_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RACINE)
sys.path.insert(0, os.path.join(_RACINE, "modules"))


def source(nom: str) -> str:
    """Chemin du FICHIER SOURCE d'un module, où qu'il vive.

    Les tests qui relisent le code — recherche d'une chaîne, d'un motif, d'un
    commentaire — le trouvaient par `os.path.join(HERE, "fiscal.py")`. Le
    regroupement des modules métier dans modules/ a cassé ces 56 appels d'un
    coup. Passer par ici les rend indifférents à l'emplacement : un module
    peut redéménager sans toucher un seul test.
    """
    direct = os.path.join(_RACINE, nom)
    return direct if os.path.exists(direct) else os.path.join(_RACINE, "modules", nom)


# ── Dossier de référence absent : le dépôt public reste testable ───────────
#
# Le jeu de données RÉEL (reference/) contient l'identité et la comptabilité
# de l'auteur : il n'est pas publié. Sur un clone public, deux réflexes
# opposés seraient également mauvais — laisser la suite échouer (le logiciel
# paraîtrait cassé) ou tout ignorer (il paraîtrait non testé).
#
# On fait donc la part des choses :
#   - la grande majorité des tests vérifient un COMPORTEMENT : on leur
#     substitue le jeu de démonstration anonymisé, et ils tournent ;
#   - seuls les tests de CALAGE, qui reproduisent à l'euro des liasses
#     réelles établies par un professionnel, sont ignorés : leur objet même
#     est cette comparaison, et elle ne peut pas être publique.

CALAGE_SUR_DOSSIER_REEL = {
    "test_or_liasses_reelles",          # le test en or : 3 exercices réels à l'euro
    "test_reprise_liasse",   # réconciliation du bilan d'ouverture
    "test_j0_j1",            # premiers calages (bilan, comptes, soldes)
    "test_j3",               # liasse calée sur les liasses réelles
    "test_j4_j5",            # reports et déficits réels
    "test_j9_release",       # contrôle du paquet sur le dossier réel
    "test_stress_web_fec",   # conformité des trois FEC réels
}


def pytest_collection_modifyitems(config, items):
    import os as _os

    import pytest as _pytest
    del config

    racine = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _os.path.isdir(_os.path.join(racine, "reference")):
        return                      # dossier présent : tout doit s'exécuter

    demo = _os.path.join(racine, "demo", "FEC_DEMO_2025.txt")
    marque = _pytest.mark.skip(
        reason="test de calage sur données réelles — jeu non publié "
               "(voir README, section « Tests »)")
    for item in items:
        module = getattr(item, "module", None)
        if module is None:
            continue
        nom = getattr(module, "__name__", "").rsplit(".", 1)[-1]
        if nom in CALAGE_SUR_DOSSIER_REEL:
            item.add_marker(marque)
            continue
        for attribut in ("FEC2025", "FEC_REF", "FEC_REEL", "FEC"):
            valeur = getattr(module, attribut, None)
            if isinstance(valeur, str) and "reference" in valeur:
                setattr(module, attribut, demo)


# ── Ne rien laisser traîner quand le dossier RÉEL est là (constat E-21) ────
#
# Sur la machine de développement, `dossier_demonstration()` fait pointer le
# mode démo sur `reference/` : la suite écrit donc la comptabilité RÉELLE
# dans les répertoires temporaires de pytest — FEC d'archive, FEC d'import,
# bases. Ces fichiers survivent à la session et pytest en conserve trois
# exécutions.
#
# Il n'y a pas d'exposition à un tiers local : pytest crée
# `/tmp/pytest-of-<user>/` en 0700. Mais ces copies échappent à TOUT ce que
# le projet a mis en place pour se protéger — .gitignore, verifier_depot,
# la garde du paquet — et une sauvegarde système les emporte sans obstacle.
#
# On efface donc l'arborescence temporaire en fin de session, mais SEULEMENT
# si la suite est passée : en cas d'échec, les fichiers sont la matière
# première du diagnostic et les supprimer rendrait l'échec inanalysable.
# Sur un clone public (pas de reference/), rien n'est touché : les données
# y sont anonymisées, et l'inspection reste possible.

def pytest_sessionfinish(session, exitstatus):
    import os as _os
    import shutil as _shutil

    racine = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if not _os.path.isdir(_os.path.join(racine, "reference")):
        return                          # jeu anonymisé : rien à protéger
    if exitstatus != 0:
        return                          # échec : on garde de quoi analyser
    fabrique = getattr(session.config, "_tmp_path_factory", None)
    base = getattr(fabrique, "_basetemp", None)
    if base:
        _shutil.rmtree(base, ignore_errors=True)


# ── Tests qui EXIGENT le dossier privé ────────────────────────────────────
#
# Depuis la passe F, construire_distribution et verifier_depot REFUSENT de
# conclure sans empreintes : c'est tout l'objet des constats F-01 et F-03,
# un garde-fou qui approuve quand il ne peut pas travailler étant pire que
# pas de garde-fou. Conséquence directe : sur un clone public — donc sur un
# runner d'intégration continue — ces deux outils échouent volontairement,
# et les tests qui les appellent avec eux.
#
# Ils sont donc IGNORÉS quand le dossier privé est absent, comme les tests
# de calage le sont déjà. Ce qu'ils vérifient n'a de sens que là où la
# frontière existe : sur le poste qui détient les données réelles.

def dossier_prive_present() -> bool:
    import os as _os
    racine = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    return (_os.path.isdir(_os.path.join(racine, "reference"))
            and _os.path.isfile(_os.path.join(racine, "seed_exemple.sql")))


def exiger_dossier_prive() -> None:
    """À appeler en tête d'un test qui ne peut pas s'exécuter sans lui."""
    import pytest as _pytest
    if not dossier_prive_present():
        _pytest.skip("exige le dossier privé (reference/ + seed_exemple.sql) : "
                     "les gardes de publication refusent de conclure sans "
                     "empreintes — voir passe F, constats F-01 et F-03")
