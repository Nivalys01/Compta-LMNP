# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Audit « mise en production » (v8.9.0) — verdicts figés en non-régression.

Grille externe de 5 axes, passée au tamis du contexte AUTOPORTÉ (local,
mono-utilisateur, zéro réseau sortant). Appliqué :
  - journal d'erreurs persistant et ROTATIF (logs/erreurs.log, 512 Ko × 3),
    branché paresseusement au premier incident — la console du lanceur est
    invisible ou perdue, sans fichier un plantage distant est
    indiagnosticable ;
  - la page 500 masque toute trace ET oriente vers le fichier journal.
Déjà en place (verrouillé ici pour que ça le reste) :
  - liaison stricte 127.0.0.1, debug opt-in par variable d'environnement ;
  - sauvegarde automatique AVANT toute migration de schéma ;
  - export PDF en dépendance optionnelle (ImportError → message, pas de
    crash de l'application) ;
  - paquet client sans aucune base de données ni donnée de référence.
Réfutés (sans objet en autoporté, documentés dans l'échange) : healthcheck,
alerting, centralisation de logs, process manager, limites CPU/RAM,
timeouts d'API tierces, sessions/JWT/mots de passe (pas d'authentification
par conception, lié à l'écoute locale exclusive).

Lancer :  pytest -q tests/test_audit_production.py
"""
import importlib
import os
import re
import sys

import conftest
import zipfile

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import init_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    yield app_mod, app_mod.app.test_client(), str(tmp_path)
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


def test_erreur_500_masquee_mais_journalisee(client):
    app_mod, cl, dossier = client

    @app_mod.app.route("/_boom_audit")
    def _boom():
        raise RuntimeError("explosion contrôlée secret-interne-xyz")

    r = cl.get("/_boom_audit")
    t = r.get_data(as_text=True)
    assert r.status_code == 500
    # rien d'interne ne fuit vers l'utilisateur…
    assert "Traceback" not in t and "RuntimeError" not in t
    assert "secret-interne-xyz" not in t
    # …mais la page oriente vers le journal, qui contient tout
    assert "erreurs.log" in t
    log = os.path.join(dossier, "logs", "erreurs.log")
    assert os.path.exists(log)
    assert "secret-interne-xyz" in open(log, encoding="utf-8").read()


def test_journal_rotatif_et_idempotent(client):
    app_mod, cl, _dossier = client

    @app_mod.app.route("/_boom_audit2")
    def _boom2():
        raise RuntimeError("boum")

    for _ in range(3):
        cl.get("/_boom_audit2")
    handlers = [h for h in app_mod.app.logger.handlers
                if getattr(h, "_journal_compta", False)]
    assert len(handlers) == 1                     # jamais dupliqué
    assert handlers[0].maxBytes == 512_000        # rotation bornée
    assert handlers[0].backupCount == 3


def test_ecoute_locale_et_debug_opt_in():
    src = open(conftest.source("app.py"), encoding="utf-8").read()
    assert 'host="127.0.0.1"' in src              # jamais exposé au réseau
    assert re.search(r'debug = os\.environ\.get\("COMPTA_DEBUG"\) == "1"',
                     src)                          # debug jamais par défaut


def test_migration_sauvegarde_avant_de_toucher():
    src = open(conftest.source("migrations.py"), encoding="utf-8").read()
    corps = src.split("def migrer(")[1].split("def ")[0]
    assert "sauvegarder" in corps
    # la sauvegarde précède le premier palier
    assert corps.index("sauvegarder") < corps.index("PALIERS")


def test_pdf_est_une_dependance_optionnelle():
    src = open(conftest.source("app.py"), encoding="utf-8").read()
    assert "except ImportError" in src
    assert "reportlab" in src                      # message d'orientation
    # l'import est bien DIFFÉRÉ : jamais en tête de module
    entete = src[:src.index("def ")]
    assert "liasse_pdf" not in entete


def test_paquet_client_sans_donnees(tmp_path):
    conftest.exiger_dossier_prive()
    sys.path.insert(0, HERE)
    import construire_distribution as cd
    anciens = os.getcwd()
    os.chdir(HERE)
    try:
        chemin = cd.construire()
    finally:
        os.chdir(anciens)
    noms = zipfile.ZipFile(chemin).namelist()
    assert not any(n.endswith(".db") for n in noms)
    assert not any("reference/" in n for n in noms)
    assert not any("logs/" in n for n in noms)
    assert not any("certs/" in n for n in noms)


# === Lanceur Windows : lisible par cmd.exe ================================
# Constat de terrain (Windows 10, juillet 2026) : le .bat était écrit en
# UTF-8 avec des fins de ligne Unix. cmd.exe lit un fichier de commandes
# octet par octet ; le décalage lui faisait avaler le début des lignes
# (« echo » -> « ho » -> « o »), les variables n'étaient jamais affectées
# et l'installation échouait de façon incompréhensible.

def test_lanceur_bat_ascii_pur_et_crlf():
    chemin = os.path.join(HERE, "Compta-LMNP-Windows.bat")
    octets = open(chemin, "rb").read()
    non_ascii = [i for i, b in enumerate(octets) if b > 127]
    assert not non_ascii, (
        f"{len(non_ascii)} octet(s) non-ASCII dans le lanceur Windows : "
        "cmd.exe décale sa lecture et avale le début des lignes")
    lf_seuls = octets.count(b"\n") - octets.count(b"\r\n")
    assert lf_seuls == 0, (
        f"{lf_seuls} fin(s) de ligne Unix dans le lanceur Windows : "
        "un .bat doit être en CRLF")
    assert octets.count(b"\r\n") > 50          # le fichier est bien complet


def test_lanceur_bat_execute_python_avant_de_le_croire():
    """Windows 10 fournit un faux python.exe qui ouvre le Microsoft Store :
    tester la seule PRÉSENCE de la commande ne suffit pas."""
    src = open(os.path.join(HERE, "Compta-LMNP-Windows.bat"),
               encoding="ascii").read()
    assert "py -3 --version" in src
    assert "python --version" in src
    assert "where python" not in src           # l'ancien test, trompeur


def test_reportlab_non_bloquant_a_l_installation():
    """L'export PDF est optionnel : son échec d'installation ne doit pas
    empêcher le logiciel de fonctionner (versions récentes de Python sans
    roue disponible, notamment)."""
    src = open(os.path.join(HERE, "Compta-LMNP-Windows.bat"),
               encoding="ascii").read()
    avant = src.split("reportlab")[0]
    # Flask seul est essentiel : cryptography ne servait qu'à fabriquer le
    # certificat auto-signé, abandonné comme défaut en v8.15.0.
    assert "pip install --quiet flask" in avant
    assert "goto :echec_pip" not in src.split("reportlab", 1)[1].split(
        ":venv_ok")[0]                          # reportlab n'avorte rien


def test_chemins_utilisateur_a_cote_de_l_executable_si_gele():
    """Compatibilité PyInstaller : les données de l'utilisateur doivent
    vivre à côté du .exe, pas dans le bundle temporaire."""
    src = open(conftest.source("app.py"), encoding="utf-8").read()
    assert 'getattr(sys, "frozen", False)' in src
    assert "sys.executable" in src


# === HTTP local par défaut (v8.15.0) ======================================
# Retour d'usage Windows : « le navigateur indique toujours que la connexion
# localhost:5000 est non sécurisée, avec le https barré ». Ce n'était pas un
# défaut de configuration mais la nature d'un certificat AUTO-SIGNÉ : rien
# ne peut le valider. Or il ne protégeait rien — l'application n'écoute que
# sur la boucle locale — et son seul effet réel était d'entraîner
# l'utilisateur à passer outre les avertissements de son navigateur.

def test_https_nest_plus_le_defaut():
    src = open(conftest.source("app.py"), encoding="utf-8").read()
    bloc = src.split('if __name__ == "__main__":')[1]
    assert 'os.environ.get("COMPTA_HTTPS") == "1"' in bloc
    # le chemin par défaut ne doit PAS charger de certificat
    avant_opt_in = bloc.split('COMPTA_HTTPS')[0]
    assert "ssl_context" not in avant_opt_in


def test_le_message_explique_l_absence_de_cadenas():
    src = open(conftest.source("app.py"), encoding="utf-8").read()
    assert "contexte sécurisé" in src        # localhost EST un contexte sûr
    assert "traversent aucun réseau" in src


def test_lanceurs_distinguables_extensions_masquees():
    """Sous Windows les extensions sont masquées par défaut :
    « Lancer-Compta-LMNP.bat » et « .sh » s'affichaient sous un nom
    IDENTIQUE, côte à côte. Deux fichiers jumeaux, un seul qui marche."""
    fichiers = [f for f in os.listdir(HERE)
                if f.endswith((".bat", ".sh")) and "Compta" in f]
    souches = [os.path.splitext(f)[0] for f in fichiers]
    assert len(set(souches)) == len(souches), \
        f"noms identiques une fois l'extension masquée : {souches}"
    assert any("Windows" in s for s in souches)
    assert any("Linux" in s or "macOS" in s for s in souches)


def test_raccourci_bureau_cree_une_seule_fois():
    bat = open(os.path.join(HERE, "Compta-LMNP-Windows.bat"),
               encoding="ascii").read()
    assert "raccourci_bureau" in bat          # marqueur d'idempotence
    assert "CreateShortcut" in bat
    assert "Desktop" in bat
    # le marqueur est testé AVANT la création : pas de recréation forcée
    assert bat.index("raccourci_bureau") < bat.index("CreateShortcut")


# === Propriété intellectuelle (v8.16.0, préalable à toute publication) ====

def test_aucun_placeholder_de_titulaire():
    """66 fichiers portaient encore « <VOTRE NOM> » : une mention de
    copyright sans titulaire ne protège personne."""
    import glob
    restants = []
    for f in (glob.glob(os.path.join(HERE, "**/*.py"), recursive=True)
              + glob.glob(os.path.join(HERE, "*.md"))
              + [os.path.join(HERE, "LICENSE.txt")]):
        if ".venv" in f or os.sep + "dist" + os.sep in f:
            continue
        if os.path.basename(f) == "test_audit_production.py":
            continue          # ce fichier-ci doit citer le motif qu'il chasse
        try:
            if "VOTRE NOM" in open(f, encoding="utf-8").read():
                restants.append(os.path.basename(f))
        except (OSError, UnicodeDecodeError):
            continue
    assert not restants, f"placeholder de titulaire restant : {restants}"


def test_licence_coherente_avec_le_modele_gratuit():
    lic = open(os.path.join(HERE, "LICENSE.txt"), encoding="utf-8").read()
    assert "Sylvain FAURE" in lic
    assert "GRATUIT" in lic
    # l'ancienne licence parlait d'« acquéreur d'une licence » — modèle
    # commercial abandonné en v8.8.0
    assert "acquéreur" not in lic
    for section in ("ABSENCE DE GARANTIE", "DONS", "COMPOSANTS TIERS",
                    "droit français"):
        assert section in lic, section


def test_licence_livree_et_propriete_visible():
    src = open(conftest.source("construire_distribution.py"),
               encoding="utf-8").read()
    assert '"LICENSE.txt"' in src
    footer = open(conftest.source("app.py"), encoding="utf-8").read()
    assert "© 2026 Sylvain FAURE" in footer          # visible dans l'UI
    # Document d'accueil unique depuis la fusion de README.md et
    # LISEZ-MOI.md : la mention de propriété y reste en tête.
    accueil = open(os.path.join(HERE, "LISEZ-MOI.md"), encoding="utf-8").read()
    assert "tous droits réservés" in accueil


def test_import_csv_marque_experimental():
    p = open(conftest.source("pages.py"), encoding="utf-8").read()
    assert "FONCTION EXPÉRIMENTALE" in p
    section = p.split("FONCTION EXPÉRIMENTALE")[1][:800]
    assert "Vérifiez chaque proposition" in section
    assert "contre-passation" in section              # la sortie de secours


# === Préparation du dépôt public (v8.18.0) ================================
# Une fuite dans un dépôt public est IRRÉVERSIBLE : le fichier reste dans
# l'historique après suppression, et le dépôt est cloné et indexé en
# quelques minutes. Ces tests verrouillent ce qui a failli partir.

def test_gitignore_protege_le_dossier_reel():
    g = open(os.path.join(HERE, ".gitignore"), encoding="utf-8").read()
    for interdit in ("reference/", "seed_exemple.sql", "certs/", "*.db",
                     "logs/", "imports_tmp/"):
        assert interdit in g, interdit
    # La toute première version portait « !reference/*.txt », qui
    # DÉS-ignorait explicitement la comptabilité réelle.
    assert "!reference/*.txt" not in g
    # …mais le jeu de démonstration, lui, DOIT être publié
    assert "!demo/FEC_DEMO_" in g


def test_aucun_siren_reel_dans_les_sources():
    """Le SIREN de l'auteur était écrit en dur dans 31 fichiers (chemins
    du dossier de référence, exemples de docstrings)."""
    import glob
    import re
    siren_reel = None
    seed = os.path.join(HERE, "seed_exemple.sql")
    if os.path.exists(seed):
        m = re.search(r"'(\d{9})'", open(seed, encoding="utf-8").read())
        siren_reel = m.group(1) if m else None
    if not siren_reel:
        import pytest as _p
        _p.skip("dossier de référence absent")
    fautifs = []
    for f in (glob.glob(os.path.join(HERE, "**/*.py"), recursive=True)
              + glob.glob(os.path.join(HERE, "*.md"))):
        if ".venv" in f or os.sep + "dist" + os.sep in f:
            continue
        if siren_reel in open(f, encoding="utf-8", errors="ignore").read():
            fautifs.append(os.path.basename(f))
    assert not fautifs, f"SIREN réel présent dans : {fautifs}"


def test_outil_anonymisation_ne_contient_pas_ce_quil_masque():
    """Il portait en clair le nom et l'adresse à remplacer — publier cet
    outil revenait à publier exactement ce qu'il protège."""
    src = open(conftest.source("outils_demo.py"), encoding="utf-8").read()
    # La mention de copyright, elle, doit évidemment y figurer : on
    # inspecte le corps du fichier, pas son en-tête légal.
    corps = "\n".join(ligne for ligne in src.splitlines()
                       if "Copyright" not in ligne)
    seed = os.path.join(HERE, "seed_exemple.sql")
    if os.path.exists(seed):
        import re
        reel = open(seed, encoding="utf-8").read()
        m = re.search(r"INSERT INTO exploitant[^;]*?'([^']{4,})'", reel, re.S)
        if m:
            assert m.group(1) not in corps
        for adresse in re.findall(r"'(\d+\s+[Rr]ue[^']{4,})'", reel):
            assert adresse not in corps
    assert "INSERT INTO exploitant" in src      # il les LIT dans le seed


def test_controle_de_publication_disponible_et_strict():
    conftest.exiger_dossier_prive()
    import verifier_depot
    r = verifier_depot.verifier()
    assert r["fichiers_publies"] > 0
    assert not r["alertes"], r["alertes"]


# --- Un PDF n'est pas un fichier illisible --------------------------------
# Les preuves d'audit versionnées dans docs/ sont des PDF de texte. Le
# contrôle les rangeait parmi les formats opaques et rendait un
# AVERTISSEMENT pour chacun — le test ci-dessus échouait donc en
# permanence, et un contrôle qui échoue toujours finit par ne plus être lu.
# La solution de facilité, exempter docs/preuves_* par son chemin, aurait
# rouvert le trou que ce même contrôle documente : un PDF RÉEL déposé là
# serait passé sans être vu. Le PDF est donc LU.

def _pdf_de_test(chemin, texte=None, corps=True):
    """Petit PDF réel : avec du texte, ou muet (un simple rectangle) pour
    imiter un document scanné. `corps=False` ne pose que la ligne demandée,
    pour le cas du document presque vide."""
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(chemin))
    if texte is None:
        c.rect(100, 100, 200, 200, fill=1)
    else:
        c.drawString(72, 720, texte)
        if corps:
            for i, ligne in enumerate([
                    "Recettes de l'exercice (CA HT) : 12 000,00 EUR",
                    "Amortissements de l'exercice : 4 200,00 EUR",
                    "Resultat fiscal LMNP : 1 850,00 EUR",
                    "Document de travail — report champ a champ."]):
                c.drawString(72, 700 - 14 * i, ligne)
    c.save()
    return str(chemin)


def _depot_jetable(tmp_path, monkeypatch, empreinte="MARTIN"):
    """Dépôt git minimal + empreinte factice : un test n'a pas à manipuler
    la vraie identité de l'exploitant."""
    import subprocess
    import verifier_depot
    repo = tmp_path / "depot"
    (repo / "docs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    monkeypatch.setattr(verifier_depot, "_empreintes",
                        lambda: [("nom de l'exploitant", empreinte)])
    return repo


def test_un_pdf_de_texte_est_reellement_inspecte(tmp_path, monkeypatch):
    """Le cas qui motive tout : une liasse réelle déposée en PDF dans
    docs/. Le contrôle doit y trouver le nom, pas se contenter d'un
    « vérifiez à la main » que personne ne fait."""
    import verifier_depot
    repo = _depot_jetable(tmp_path, monkeypatch)
    _pdf_de_test(repo / "docs" / "bilan.pdf",
                 "Bilan 2026 — MARTIN Camille — exercice clos")

    r = verifier_depot.verifier(str(repo))

    fautifs = {a["fichier"]: a for a in r["alertes"]}
    assert "docs/bilan.pdf" in fautifs, r["alertes"]
    assert fautifs["docs/bilan.pdf"]["gravite"] == "BLOQUANT"
    assert "donnée réelle" in fautifs["docs/bilan.pdf"]["motif"]


def test_un_pdf_de_texte_propre_ne_laisse_aucune_alerte(tmp_path, monkeypatch):
    """Contrepartie, et raison d'être du correctif : les preuves de docs/
    ne doivent plus produire d'avertissement perpétuel."""
    import verifier_depot
    repo = _depot_jetable(tmp_path, monkeypatch)
    _pdf_de_test(repo / "docs" / "preuve.pdf",
                 "Exploitant fictif — liasse de démonstration")

    assert verifier_depot.verifier(str(repo))["alertes"] == []


def test_un_pdf_sans_texte_reste_un_avertissement(tmp_path, monkeypatch):
    """« L'extraction n'a rien rendu » ne vaut pas « il n'y a rien dedans ».
    Un bilan photographié ou scanné ne donne aucun caractère : conclure au
    vert là-dessus serait le piège d'origine, déplacé d'un cran."""
    import verifier_depot
    repo = _depot_jetable(tmp_path, monkeypatch)
    _pdf_de_test(repo / "docs" / "scan.pdf")          # aucune chaîne de texte

    alertes = verifier_depot.verifier(str(repo))["alertes"]

    assert [a["fichier"] for a in alertes] == ["docs/scan.pdf"], alertes
    assert alertes[0]["gravite"] == "AVERTISSEMENT"
    assert "sans texte extractible" in alertes[0]["motif"]


def test_un_pdf_presque_muet_qui_porte_le_nom_reste_bloquant(tmp_path,
                                                            monkeypatch):
    """L'ordre des deux verdicts compte. Une page scannée dont l'extraction
    ne rend qu'une ligne — mais le nom en clair dedans — serait classée
    « à vérifier à la main » si la réserve se prononçait avant le tamis des
    empreintes. Un nom tient en moins de vingt signes."""
    import verifier_depot
    repo = _depot_jetable(tmp_path, monkeypatch)
    _pdf_de_test(repo / "docs" / "entete.pdf", "MARTIN Camille", corps=False)

    alertes = verifier_depot.verifier(str(repo))["alertes"]

    assert [a["gravite"] for a in alertes] == ["BLOQUANT"], alertes
    assert alertes[0]["fichier"] == "docs/entete.pdf"


def test_pdftotext_absent_ne_vaut_pas_pdf_propre(tmp_path, monkeypatch):
    """Sur une machine sans poppler — une CI, un autre poste — le contrôle
    doit DIRE qu'il n'a pas lu, et nommer ce qui lui manque."""
    import verifier_depot
    pdf = _pdf_de_test(tmp_path / "liasse.pdf", "MARTIN Camille")
    monkeypatch.setenv("PATH", str(tmp_path))         # plus de pdftotext

    texte, motif = verifier_depot.texte_du_pdf(pdf)

    assert texte is None
    assert "pdftotext" in motif and "poppler" in motif


def test_un_pdf_illisible_redevient_un_avertissement(tmp_path, monkeypatch):
    """Et cet échec d'extraction, quelle qu'en soit la cause, remonte bien
    jusqu'au verdict : il n'est pas avalé par la branche qui le lit."""
    import verifier_depot
    repo = _depot_jetable(tmp_path, monkeypatch)
    (repo / "docs" / "chiffre.pdf").write_bytes(b"%PDF-1.4 abime")

    alertes = verifier_depot.verifier(str(repo))["alertes"]

    assert [a["gravite"] for a in alertes] == ["AVERTISSEMENT"], alertes
    assert alertes[0]["fichier"] == "docs/chiffre.pdf"
    assert "non inspecté" in alertes[0]["motif"]


def test_les_preuves_pdf_de_ce_depot_sont_lisibles():
    """Garde-fou sur le dépôt réel : si l'extraction cessait de fonctionner,
    le contrôle redeviendrait vert-par-avertissement sans que rien ne le
    signale, et ce dossier est précisément celui où l'on dépose des sorties
    fraîchement produites."""
    import glob
    import verifier_depot
    racine = verifier_depot.racine_depot()
    preuves = sorted(glob.glob(os.path.join(racine, "docs", "preuves_*",
                                            "*.pdf")))
    if not preuves:
        import pytest as _p
        _p.skip("aucune preuve PDF dans ce dépôt")
    muets = [os.path.basename(f) for f in preuves
             if verifier_depot.texte_du_pdf(f)[0] is None]
    assert not muets, f"PDF non inspectables : {muets}"


def test_aucun_tiers_nomme_dans_le_depot():
    """Nommer un prestataire tiers dans un dépôt public n'apporte rien et
    l'expose autant que nous. Les termes à proscrire sont listés dans le
    dossier privé — ce test le lit s'il est là, et ne bloque pas sinon."""
    import glob
    liste = os.path.join(HERE, "reference", "termes_a_anonymiser.txt")
    if not os.path.exists(liste):
        import pytest as _p
        _p.skip("liste des termes absente (dossier privé)")
    termes = [x.strip() for x in open(liste, encoding="utf-8")
              if x.strip() and not x.strip().startswith("#")]
    fautifs = []
    for f in (glob.glob(os.path.join(HERE, "**/*.py"), recursive=True)
              + glob.glob(os.path.join(HERE, "*.md"))
              + glob.glob(os.path.join(HERE, "*.sql"))
              + glob.glob(os.path.join(HERE, "demo/*.txt"))):
        if ".venv" in f or os.sep + "dist" + os.sep in f:
            continue
        contenu = open(f, encoding="utf-8", errors="ignore").read().lower()
        for terme in termes:
            if terme.lower() in contenu:
                fautifs.append((os.path.basename(f), terme))
    assert not fautifs, f"tiers nommé dans : {fautifs}"


def test_un_seul_lanceur_shell_dans_le_paquet(tmp_path):
    """Constat d'usage Linux : le paquet contenait DEUX fichiers .sh — le
    lanceur et un générateur de certificat — affichés côte à côte. Sur un
    bureau Linux, double-cliquer un .sh l'ouvre dans un éditeur : ouvrir
    l'un pour l'autre ne produit donc aucun message d'erreur, juste du code
    à l'écran et rien qui démarre."""
    conftest.exiger_dossier_prive()
    import zipfile
    import construire_distribution as cd
    anciens = os.getcwd()
    os.chdir(HERE)
    try:
        chemin = cd.construire()
    finally:
        os.chdir(anciens)
    del tmp_path
    with zipfile.ZipFile(chemin) as z:
        noms = z.namelist()
        shells = [n for n in noms if n.endswith(".sh")]
        assert len(shells) == 1, f"plusieurs .sh livrés : {shells}"
        assert "Compta-LMNP-Linux-macOS" in shells[0]
        # …et il doit être exécutable à l'arrivée
        info = z.getinfo(shells[0])
        assert (info.external_attr >> 16) & 0o111, \
            "le lanceur perd son droit d'exécution dans l'archive"
        assert any(n.endswith(".desktop") for n in noms)


def test_notice_explique_le_double_clic_linux():
    t = open(os.path.join(HERE, "LISEZ-MOI.md"), encoding="utf-8").read()
    assert "double-clic ne lance rien" in t
    # la forme la plus robuste doit être donnée en PREMIER : elle survit à
    # la perte du droit d'exécution à la décompression
    assert "bash Compta-LMNP-Linux-macOS.sh" in t
    assert t.index("bash Compta-LMNP-Linux-macOS.sh") < t.index("chmod +x")


# === Lanceur Linux (v8.24.0) ==============================================
# « Rien ne se lance » signalé deux fois de suite. Quatre causes, dont la
# plus embarrassante : le lanceur donnait LUI-MÊME le mauvais nom de
# fichier, et le raccourci qu'il installait pointait vers un fichier
# inexistant depuis le renommage de la v8.15.0.

def _lanceur():
    return open(os.path.join(HERE, "Compta-LMNP-Linux-macOS.sh"),
                encoding="utf-8").read()


def test_lanceur_ne_cite_aucun_nom_de_fichier_perime():
    """Un nom écrit en dur devient faux au premier renommage. Le script
    déduit le sien de $0 : il ne peut plus se tromper."""
    src = _lanceur()
    import re
    for cite in re.findall(r"[A-Za-z0-9_\-]+\.sh", src):
        if cite.startswith("$") or cite == "generer_certificat.sh":
            continue
        chemin = os.path.join(HERE, cite)
        assert os.path.exists(chemin), (
            f"le lanceur cite « {cite} », qui n'existe pas")
    assert 'NOM="$(basename "$MOI")"' in src


def test_lanceur_connait_les_terminaux_des_bureaux_recents():
    """ptyxis est le terminal par défaut de Fedora 40+ et de Bazzite ;
    son absence de la liste faisait échouer TOUT le relancement, et le
    script continuait en silence — l'application démarrait sans que rien
    n'apparaisse à l'écran."""
    src = _lanceur()
    for terminal in ("ptyxis", "kgx", "gnome-console", "konsole",
                     "gnome-terminal", "alacritty", "kitty", "foot"):
        assert terminal in src, terminal
    # ptyxis doit être cherché AVANT les anciens : c'est le défaut actuel
    assert src.index("ptyxis") < src.index("xterm")


def test_lanceur_se_relance_avec_un_chemin_absolu():
    """gnome-terminal et ptyxis passent par D-Bus et ne transmettent pas le
    répertoire courant : « bash ./script » échouait sans un mot."""
    src = _lanceur()
    # Résolution portable depuis la v8.25.0 : readlink -f est une
    # extension GNU, absente de BSD avant macOS 12.3.
    assert 'MOI="$(_resoudre "$0")"' in src
    bloc = src.split("for term in")[1].split("done")[0]
    assert 'bash "$MOI"' in bloc or "bash '$MOI'" in bloc
    assert 'bash "$0"' not in bloc          # jamais le chemin d'invocation


def test_lanceur_ne_disparait_jamais_en_silence():
    """Le pire des cas : l'application démarre et l'utilisateur ne voit
    rien. À défaut de terminal, on écrit un journal et on notifie."""
    src = _lanceur()
    # « Aucun terminal graphique » figure deux fois (commentaire puis
    # message) : on prend ce qui suit la DERNIÈRE occurrence.
    bloc = src.split("Aucun terminal graphique")[-1][:1200]
    assert "logs/demarrage.log" in src
    assert "notify-send" in bloc or "zenity" in bloc
    assert "localhost:5000" in bloc          # l'adresse, toujours donnée


def test_raccourci_desktop_est_valide():
    d = open(os.path.join(HERE, "Compta-LMNP.desktop"), encoding="utf-8").read()
    # « Path=. » est invalide : la spécification exige un chemin absolu.
    for ligne in d.splitlines():
        if ligne.startswith("Path="):
            assert ligne[5:].startswith("/"), ligne
    # %k peut être une URI « file:// » : le préfixe doit être retiré, sinon
    # cd échoue sans un mot.
    assert "${p#file://}" in d
    assert "Compta-LMNP-Linux-macOS.sh" in d


def test_raccourci_genere_pointe_vers_un_chemin_absolu():
    src = _lanceur()
    bloc = src.split("--raccourci")[-1]
    assert 'Exec=bash "${MOI}"' in bloc
    assert "Path=${DOSSIER}" in bloc


def test_jeu_de_regles_du_linter_est_declare():
    """Sans « select », le jeu appliqué suit la version de ruff installée :
    une release du linter faisait passer le projet de propre à 234 erreurs
    sans qu'une ligne de code ait bougé. Sur un dépôt public, c'est une CI
    rouge un matin, sans raison."""
    t = open(os.path.join(HERE, "pyproject.toml"), encoding="utf-8").read()
    assert "select = [" in t
    dev = os.path.join(HERE, "requirements-dev.txt")
    assert os.path.exists(dev)
    contenu = open(dev, encoding="utf-8").read()
    assert "ruff==" in contenu and "pytest==" in contenu


# === Environnement local robuste (v8.29.0) ================================
# Signalé sur Linux Mint XFCE : « ./.venv/bin/pip: Aucun fichier ou dossier
# de ce nom », puis plus rien. Sur Debian et dérivés, le SCRIPT pip peut
# manquer alors que le MODULE pip est présent — et « python3 -m venv » peut
# échouer APRÈS avoir créé le dossier, laissant un .venv incomplet qu'un
# simple test de présence croit prêt.

def test_lanceur_nappelle_jamais_le_script_pip():
    """« python -m pip » fonctionne là où « ./.venv/bin/pip » n'existe pas."""
    src = _lanceur()
    for ligne in src.splitlines():
        nu = ligne.strip()
        if nu.startswith("#"):
            continue
        assert "./.venv/bin/pip " not in nu, ligne
        assert "/bin/pip install" not in nu, ligne
    assert '"$PY" -m pip install' in src


def test_lanceur_verifie_que_le_venv_fonctionne():
    """Et non qu'il existe : un dossier incomplet trompait le test."""
    src = _lanceur()
    assert "venv_operationnel()" in src
    assert "-m pip --version" in src
    assert "rm -rf .venv" in src          # reconstruction si abîmé
    assert "ensurepip" in src             # rattrapage si pip manque
    assert "[[ ! -d .venv ]]" not in src  # l'ancien test, trompeur


def test_message_dinstallation_cite_le_bon_paquet():
    src = _lanceur()
    assert "python3-venv python3-pip" in src
    assert "Mint" in src


def test_reportlab_ne_bloque_pas_le_lancement():
    """L'export PDF est optionnel : son échec ne doit rien empêcher."""
    src = _lanceur()
    bloc = src.split("reportlab")[1][:400]
    assert "warn" in bloc or "|| warn" in src.split("import reportlab")[1][:300]
    assert "exit 1" not in bloc


def test_lanceur_windows_verifie_aussi_le_fonctionnement():
    bat = open(os.path.join(HERE, "Compta-LMNP-Windows.bat"),
               encoding="ascii").read()
    assert "-m pip --version" in bat
    assert "ensurepip" in bat
    assert "rmdir /s /q" in bat
    # …et reste lisible par cmd.exe
    octets = open(os.path.join(HERE, "Compta-LMNP-Windows.bat"), "rb").read()
    assert not [x for x in octets if x > 127]
    assert octets.count(b"\n") - octets.count(b"\r\n") == 0
