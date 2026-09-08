# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""Qualité statique : le dépôt doit rester propre au sens de ruff
(imports morts, variables inutilisées, style) — configuration pyproject.toml."""
import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_ruff_sans_erreur():
    if shutil.which("ruff") is None:
        pytest.skip("ruff non installé (pip install ruff)")
    r = subprocess.run(["ruff", "check", "."], cwd=HERE,
                       capture_output=True, text=True)
    assert r.returncode == 0, "\n" + r.stdout + r.stderr


def test_insertion_ecritures_centralisee():
    """Aucune insertion SQL brute dans la table ecriture hors du module
    central ecritures.py (invariant d'architecture)."""
    for f in os.listdir(HERE):
        if not f.endswith(".py") or f == "ecritures.py":
            continue
        src = open(os.path.join(HERE, f), encoding="utf-8").read()
        assert "INSERT INTO ecriture" not in src, f
