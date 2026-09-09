# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

import os
import sys

# Rend les modules de la racine (init_db, reprise) importables depuis tests/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
