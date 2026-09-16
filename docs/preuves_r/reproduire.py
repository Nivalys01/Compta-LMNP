"""Preuves de la passe R ; aucune lecture des dossiers comptables privés.

Depuis la racine : .venv/bin/python docs/preuves_r/reproduire.py
Construire auparavant le ZIP avec python build_client.py.
Le téléchargement FSF, facultatif, est attendu dans /tmp/audit_r_agpl.txt.
"""
from pathlib import Path
import collections
import hashlib
import importlib.metadata as metadata
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
os.chdir(ROOT)
version = (ROOT / 'compta_lmnp/VERSION').read_text().strip()
archive = ROOT / f'compta_lmnp/dist/compta_lmnp_client_v{version}.zip'
result = {'version': version, 'head': subprocess.check_output(
    ['git', 'rev-parse', 'HEAD'], text=True).strip()}
license_bytes = (ROOT / 'LICENSE').read_bytes()
result['licence'] = {'octets': len(license_bytes), 'sha256': hashlib.sha256(license_bytes).hexdigest()}
canonical = Path('/tmp/audit_r_agpl.txt')
if canonical.exists():
    canon = canonical.read_bytes()
    result['licence'].update(canon_octets=len(canon),
        canon_sha256=hashlib.sha256(canon).hexdigest(), identique=license_bytes == canon,
        identique_apres_http_https=license_bytes.replace(b'http://', b'https://') == canon)
with zipfile.ZipFile(archive) as z:
    names = z.namelist()
    result['zip'] = {'nombre': len(names), 'extensions': dict(collections.Counter(Path(n).suffix for n in names)),
        'licence_identique': z.read('compta_lmnp/LICENSE.txt') == license_bytes,
        'clause_13': b'13. Remote Network Interaction' in z.read('compta_lmnp/LICENSE.txt'),
        'restes_autorisation': [n for n in names if n.endswith('.py') and b'sans autorisation' in z.read(n)]}
    (OUT / 'zip.txt').write_text('\n'.join(names) + '\n')
    result['liens_locaux_absents'] = []
    for dest in re.findall(r'\]\(([^)]+)\)', z.read('compta_lmnp/LISEZ-MOI.md').decode()):
        if dest.startswith('../'):
            target = posixpath.normpath(posixpath.join('compta_lmnp', dest))
            if target not in names:
                result['liens_locaux_absents'].append(dest)
    with tempfile.TemporaryDirectory(prefix='audit-r-') as tmp:
        z.extractall(tmp)
        package = Path(tmp) / 'compta_lmnp'
        os.environ['COMPTA_DB'] = str(package / 'fictif.db')
        os.environ['COMPTA_DB_BAC_A_SABLE'] = str(package / 'fictif-bac.db')
        sys.path.insert(0, str(package))
        import app
        app.init_db.init(str(package / 'fictif.db'), 'blanc').close()
        with app.app.test_client() as client:
            response = client.get('/', follow_redirects=True)
            html = response.get_data(as_text=True)
        result['interface'] = {'http': response.status_code,
            'source_lien_present': bool(re.findall(r'href="([^"]+)"[^>]*>code source</a>', html)),
            'source_lien_versionne': bool(re.search(r'href="[^"]+/(tree|releases|archive)/[^\"]+"[^>]*>code source</a>', html)),
            'version_visible': f'v{version}' in html}
        sys.path.append(str(ROOT / 'compta_lmnp'))
        import outils_sprite
        import pages
        result['sprite_genere_present'] = outils_sprite.svg_complet() in pages.ASSISTANT
        from reportlab.pdfgen.canvas import Canvas
        pdf = Path(tmp) / 'fictif.pdf'
        c = Canvas(str(pdf)); c.drawString(50, 700, 'Document fictif audit R sans aucune donnee personnelle.'); c.save()
        import verifier_depot
        text, reserve = verifier_depot.texte_du_pdf(str(pdf))
        result['poppler_execution'] = {'texte': text.strip() if text else None, 'reserve': reserve}

packages = {}
for name in sorted({d.metadata['Name'] for d in metadata.distributions()}, key=str.lower):
    d = metadata.distribution(name)
    files = [f for f in d.files or [] if '.dist-info/' in str(f) and
             any(x in str(f).lower() for x in ['license', 'copying'])]
    packages[name] = {'version': d.version,
        'licence_expression': d.metadata.get('License-Expression'),
        'classifiers_licence': [c for c in d.metadata.get_all('Classifier', []) if 'License' in c],
        'requires': d.requires or [],
        'licences': [{'fichier': str(f), 'sha256': hashlib.sha256(d.locate_file(f).read_bytes()).hexdigest()}
                     for f in files if d.locate_file(f).is_file()]}
(OUT / 'paquets.json').write_text(json.dumps(packages, ensure_ascii=False, indent=2) + '\n')

tracked = subprocess.check_output(['git', 'ls-files', '-z'], text=True).split('\0')
inventory = []
for file in tracked:
    p = Path(file)
    if not p.is_file() or 'reference/' in file or p.name == 'seed_exemple.sql':
        continue
    data = p.read_bytes()
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        inventory.append({'fichier': file, 'spdx': False, 'mention_licence': 'binaire à examiner séparément'})
        continue
    inventory.append({'fichier': file, 'spdx': 'SPDX-License-Identifier:' in text,
                      'mention_licence': bool(re.search(r'AGPL|Affero|licen[cs]e', text, re.I))})
(OUT / 'indications_licence.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n')
result['inventaire'] = {'fichiers': len(inventory), 'sans_spdx': sum(not f['spdx'] for f in inventory),
                       'sans_spdx_ni_mention': sum(not f['spdx'] and f['mention_licence'] is False for f in inventory)}
rows = subprocess.check_output(['git', 'log', '--all', '--format=%H%x00%an%x00%ae%x00%B%x00END'], text=True)
identities = {}; commits = []
for row in rows.split('\0END'):
    fields = row.strip().split('\0', 3)
    if len(fields) != 4:
        continue
    sha, name, email, body = fields
    key = (name, email)
    identities.setdefault(key, f'identite-{len(identities)+1}')
    commits.append({'commit': sha, 'identite': identities[key],
                    'signed_off_by': bool(re.search(r'^Signed-off-by:', body, re.M | re.I))})
(OUT / 'historique_pseudonymise.json').write_text(json.dumps(commits, indent=2) + '\n')
result['git'] = {'commits': len(commits), 'identites': len(identities),
                 'signed_off_by': sum(c['signed_off_by'] for c in commits),
                 'tags': subprocess.check_output(['git', 'tag'], text=True).splitlines()}
(OUT / 'resultats.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
