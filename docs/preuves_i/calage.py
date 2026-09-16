"""Calage privé : exécution des assertions existantes, sans publier de données.

pytest absent : seul son import et les décorateurs sont retirés de l'AST.
Les corps de la fixture et des tests restent intacts. Ce lanceur n'est pas pytest.
"""
import ast
import contextlib
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / 'compta_lmnp'
TEST = SRC / 'tests/test_or_liasses_reelles.py'
sys.path[:0] = [str(SRC / 'modules'), str(SRC)]
result = {'mode': 'assertions existantes executees directement, sans pytest',
          'source_sha256': hashlib.sha256(TEST.read_bytes()).hexdigest(),
          'reussites': 0, 'exercices_verifies': 0,
          'valeurs_privees_conservees': False}
try:
    with tempfile.TemporaryDirectory(prefix='audit-i-calage-') as tmp:
        class Factory:
            def mktemp(self, name):
                path = Path(tmp) / name
                path.mkdir()
                return path
        tree = ast.parse(TEST.read_text())
        tree.body = [n for n in tree.body if not (
            isinstance(n, ast.Import) and any(a.name == 'pytest' for a in n.names))]
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                node.decorator_list = []
        ns = {'__file__': str(TEST), '__name__': 'audit_calage_prive'}
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exec(compile(tree, str(TEST), 'exec'), ns)
            if not all(Path(p).is_file() for p in ns['FEC'].values()):
                raise FileNotFoundError()
            data = ns['resultats'](Factory())
            for year in sorted(ns['FEC']):
                ns['test_annee_reproduite_a_l_euro'](data, year)
                result['reussites'] += 1
                result['exercices_verifies'] += 1
            for name in ('test_reports_finaux_au_31_12_2025',
                         'test_imputation_2023_sur_deficit_2021'):
                ns[name](data)
                result['reussites'] += 1
    result['code_sortie'] = 0
except Exception as exc:
    result['code_sortie'] = 1
    result['type_erreur'] = type(exc).__name__  # jamais le message ni les valeurs
(HERE / 'calage.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
sys.exit(result['code_sortie'])
