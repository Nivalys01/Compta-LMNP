# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""Lanceur exécutable : syntaxe, mode --verifier, présence à la racine."""
import os
import stat
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANCEUR = os.path.join(HERE, "Compta-LMNP-Linux-macOS.sh")


def test_lanceur_present_et_executable():
    assert os.path.exists(LANCEUR)
    assert os.stat(LANCEUR).st_mode & stat.S_IXUSR


def test_lanceur_syntaxe_bash():
    r = subprocess.run(["bash", "-n", LANCEUR], capture_output=True)
    assert r.returncode == 0, r.stderr.decode()


def test_lanceur_mode_verifier():
    """--verifier prépare l'environnement et sort en 0 sans lancer le serveur."""
    r = subprocess.run(["bash", LANCEUR, "--verifier"],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "opérationnel" in r.stdout


def test_lanceur_windows_present():
    """Le .bat Windows est livré à la racine, à côté du .sh."""
    bat = os.path.join(HERE, "Compta-LMNP-Windows.bat")
    assert os.path.exists(bat)
    contenu = open(bat, encoding="utf-8").read()
    # generer_certificat.py n'est plus appelé : HTTP est le défaut depuis la
    # v8.15.0 (un certificat auto-signé ne peut pas être validé, il ne
    # protège rien sur la boucle locale, et son seul effet était d'habituer
    # l'utilisateur à passer outre les avertissements du navigateur).
    for attendu in ("python.org", ".venv", "app.py", "http://localhost"):
        assert attendu in contenu


def test_generateur_certificat_python(tmp_path):
    """Générateur multiplateforme : PEM valides et chargeables par ssl."""
    import ssl
    pytest_mod = __import__("pytest")
    pytest_mod.importorskip("cryptography")
    import generer_certificat
    cert, cle = generer_certificat.generer(str(tmp_path))
    assert "BEGIN CERTIFICATE" in open(cert).read()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, cle)          # lève si invalide


def test_app_port_configurable(tmp_path):
    """COMPTA_PORT est respecté (repli automatique du lanceur)."""
    import subprocess
    import time
    import urllib.request
    import ssl
    import signal
    # COMPTA_DB : sans elle, ce test démarrait le serveur sur la base RÉELLE
    # du dépôt (et la créait à la racine si absente).
    env = dict(os.environ, COMPTA_PORT="5107",
               COMPTA_DB=str(tmp_path / "compta.db"),
               COMPTA_DB_BAC_A_SABLE=str(tmp_path / "bac_a_sable.db"))
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py")],
                         cwd=HERE, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        deadline = time.time() + 15
        code = None
        while time.time() < deadline:
            time.sleep(0.5)
            for proto in ("https", "http"):
                try:
                    code = urllib.request.urlopen(
                        f"{proto}://127.0.0.1:5107/saisie",
                        timeout=2, context=ctx).status
                    break
                except Exception:
                    continue
            if code:
                break
        assert code == 200
    finally:
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=5)


def test_avertissement_dev_server_contextualise(tmp_path):
    """Le warning Werkzeug (déploiements publics) est filtré et remplacé par
    une explication du contexte local mono-utilisateur."""
    import subprocess
    import time
    import urllib.request
    import signal
    env = dict(os.environ, COMPTA_PORT="5121",
               COMPTA_DB=str(tmp_path / "compta.db"),
               COMPTA_DB_BAC_A_SABLE=str(tmp_path / "bac_a_sable.db"))
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py")],
                         cwd=HERE, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            time.sleep(0.5)
            try:
                urllib.request.urlopen("http://127.0.0.1:5121/", timeout=2)
                break
            except Exception:
                continue
    finally:
        p.send_signal(signal.SIGTERM)
        try:
            sortie, _ = p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            sortie, _ = p.communicate()
    assert "This is a development server" not in sortie
    assert "Serveur local mono-utilisateur" in sortie
