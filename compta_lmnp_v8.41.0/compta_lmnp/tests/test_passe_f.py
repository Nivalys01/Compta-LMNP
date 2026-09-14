# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Non-régression des constats de la passe F (chaîne de distribution).

Ces trois fichiers — construire_distribution.py, verifier_depot.py,
outils_demo.py — sont les gardiens qui empêchent la comptabilité réelle de
l'auteur de partir dans un paquet ou un dépôt public. Une défaillance ici
n'a pas de conséquence comptable : elle est irréversible d'une autre façon.

Le fil rouge des quatre constats critiques était qu'aucun ne produisait
d'erreur. Chacun se terminait par un message rassurant. Ces tests figent
l'exigence inverse : **aucun des trois ne doit pouvoir conclure
positivement sans avoir effectivement examiné quelque chose.**

Aucune donnée réelle n'apparaît ici : les scénarios utilisent une identité
fictive, ou lisent le dossier privé quand il est là.

Lancer :  pytest -q tests/test_passe_f.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import outils_demo  # noqa: E402
import verifier_depot  # noqa: E402

FICTIF = "MARTIN CAMILLE"


def _depot_jetable(avec_git=True, contenu=None):
    """Dépôt minimal, SANS dossier privé, avec un fichier à examiner."""
    box = tempfile.mkdtemp()
    paquet = os.path.join(box, "compta_lmnp")
    os.makedirs(paquet)
    shutil.copy(os.path.join(HERE, "verifier_depot.py"), paquet)
    open(os.path.join(box, "note.md"), "w", encoding="utf-8").write(
        contenu or f"{FICTIF} — 123456789\n")
    if avec_git:
        subprocess.run(["git", "init", "-q"], cwd=box, check=True)
    return box


# ═══ F-01 / F-02 — le contrôle ne conclut plus sans avoir cherché ═══════

def test_f01_sans_empreintes_le_verdict_est_bloquant():
    """Le dossier privé absent — un clone, un runner de CI, un `reference/`
    déplacé le temps d'un essai — et le contrôle concluait « aucune donnée
    personnelle » avec un code de sortie 0. Un garde-fou qui approuve quand
    il ne peut pas travailler est pire que pas de garde-fou."""
    box = _depot_jetable()
    try:
        r = subprocess.run([sys.executable,
                            os.path.join(box, "compta_lmnp", "verifier_depot.py")],
                           capture_output=True, text=True, cwd=box)
        assert r.returncode == 1, r.stdout
        assert "aucune empreinte chargée" in r.stdout
        assert "NE PAS PUBLIER" in r.stdout
    finally:
        shutil.rmtree(box)


def test_f02_sans_depot_git_le_verdict_est_bloquant():
    """git absent du PATH, dépôt non initialisé, commande en échec :
    `_fichiers_publies` rendait [] et l'échec d'outil devenait un « rien à
    signaler »."""
    box = _depot_jetable(avec_git=False)
    try:
        r = subprocess.run([sys.executable,
                            os.path.join(box, "compta_lmnp", "verifier_depot.py")],
                           capture_output=True, text=True, cwd=box)
        assert r.returncode == 1, r.stdout
        assert "aucun fichier listé" in r.stdout
    finally:
        shutil.rmtree(box)


def test_f02_le_mode_json_de_la_ci_echoue_aussi():
    """Le code de sortie était calculé sur les seules alertes : une CI verte
    sur un contrôle qui n'avait rien examiné."""
    box = _depot_jetable(avec_git=False)
    try:
        r = subprocess.run([sys.executable,
                            os.path.join(box, "compta_lmnp", "verifier_depot.py"),
                            "--json"], capture_output=True, text=True, cwd=box)
        assert r.returncode == 1, r.stdout
    finally:
        shutil.rmtree(box)


def test_f01_le_verdict_positif_dit_ce_qui_a_ete_examine():
    """« Aucune donnée personnelle » ne doit plus être une affirmation nue :
    le message porte le nombre de fichiers et d'empreintes."""
    r = verifier_depot.verifier()
    if not r["empreintes_cherchees"]:
        pytest.skip("dossier privé absent sur cette machine")
    assert r["fichiers_publies"] > 0
    assert not [a for a in r["alertes"] if a["gravite"] == "BLOQUANT"]


# ═══ F-09 / F-12 — ce que la recherche voit désormais ══════════════════

@pytest.mark.parametrize("variante", [
    "MARTIN CAMILLE",            # forme exacte
    "Martin Camille",            # casse différente
    "martin camille",
    "MARTIN  CAMILLE",           # espaces multiples
    "MARTIN\nCAMILLE",           # coupé sur deux lignes
    "MARTÍN CAMILLE",            # accent
    "  MARTIN   CAMILLE  ",
])
def test_f09_les_variantes_dun_nom_sont_detectees(variante):
    """La comparaison se faisait par sous-chaîne exacte. Un nom recopié dans
    une documentation ou un commentaire ne reprend presque jamais la casse
    du seed. Le dédoublonnage juste au-dessus comparait pourtant déjà en
    minuscules : l'intention était là, la comparaison ne l'appliquait pas."""
    assert verifier_depot.normaliser(FICTIF) in verifier_depot.normaliser(variante)


def test_f09_pas_de_faux_positif_sur_une_troncature():
    """Limite assumée : une troncature n'est pas détectée. La détecter
    demanderait un rapprochement approximatif, dont les faux positifs
    useraient le contrôle jusqu'à ce qu'on cesse de le lire."""
    assert verifier_depot.normaliser(FICTIF) not in verifier_depot.normaliser("MARTIN CAMIL")


def test_f12_un_fichier_cp1252_est_lu_sans_perdre_ses_accents(tmp_path):
    """`errors="ignore"` en utf-8 SUPPRIMAIT les accents : « MARTÍN »
    devenait « MARTN » et l'empreinte ne matchait plus. Or cp1252 est
    l'encodage d'export des banques françaises."""
    box = str(tmp_path / "depot")
    os.makedirs(box)
    subprocess.run(["git", "init", "-q"], cwd=box, check=True)
    with open(os.path.join(box, "releve.txt"), "wb") as f:
        f.write("Locataire : MARTÍN CAMILLE\n".encode("cp1252"))
    r = verifier_depot.verifier(box)
    if not r["empreintes_cherchees"]:
        pytest.skip("dossier privé absent sur cette machine")
    # L'empreinte réelle n'est pas dans ce fichier : on vérifie seulement
    # que le fichier a bien été LU, donc qu'il n'est pas signalé illisible.
    assert not [a for a in r["alertes"] if "illisible" in a["motif"]]


def test_f12_un_fichier_trop_gros_est_signale_pas_ignore(tmp_path):
    """Tout fichier de plus de 5 Mo était sauté sans un mot, et aucun motif
    de chemin ne couvre un .txt volumineux à la racine — or un export
    comptable dépasse facilement cette taille."""
    box = str(tmp_path / "depot")
    os.makedirs(box)
    subprocess.run(["git", "init", "-q"], cwd=box, check=True)
    with open(os.path.join(box, "export.txt"), "w", encoding="utf-8") as f:
        f.write("x" * 5_000_001)
    r = verifier_depot.verifier(box)
    motifs = [a["motif"] for a in r["alertes"] if a["fichier"] == "export.txt"]
    assert any("non examiné" in m for m in motifs), r["alertes"]


# ═══ F-03 / F-04 — le paquet est contrôlé sur son CONTENU ══════════════

def _paquet_jetable(tmp_path, seed_demo_contenu):
    """Copie du logiciel, avec un seed de démonstration piégé."""
    paquet = str(tmp_path / "compta_lmnp")
    os.makedirs(paquet)
    for f in os.listdir(HERE):
        src = os.path.join(HERE, f)
        if os.path.isfile(src):
            shutil.copy(src, paquet)
    for d in ("demo", "reference"):
        if os.path.isdir(os.path.join(HERE, d)):
            shutil.copytree(os.path.join(HERE, d), os.path.join(paquet, d))
    open(os.path.join(paquet, "seed_demo.sql"), "w", encoding="utf-8").write(
        seed_demo_contenu)
    return paquet


def test_f04_un_seed_de_demo_pollue_bloque_la_construction(tmp_path):
    """Le cas central pour lequel ces gardes existent, et celui qu'elles
    laissaient passer : `seed_demo.sql` est le seul fichier du paquet dérivé
    des données réelles, son nom est légitime, et personne ne relisait son
    contenu. La garde ne comparait que des noms tirés d'une liste écrite à
    la main — donc structurellement incapable de rien détecter."""
    reel = os.path.join(HERE, "seed_exemple.sql")
    if not os.path.exists(reel):
        pytest.skip("dossier privé absent sur cette machine")
    nom = re.search(r"INSERT INTO exploitant.*?'([^']+)'",
                    open(reel, encoding="utf-8").read(), re.S).group(1)
    paquet = _paquet_jetable(
        tmp_path, f"-- Seed DEMO\nINSERT INTO exploitant (nom) VALUES ('{nom}');\n")
    r = subprocess.run([sys.executable, "construire_distribution.py"],
                       capture_output=True, text=True, cwd=paquet)
    assert r.returncode != 0, r.stdout
    assert "FUITE BLOQUÉE" in (r.stdout + r.stderr)
    dist = os.path.join(paquet, "dist")
    assert not os.path.isdir(dist) or not os.listdir(dist), \
        "le zip fautif a été laissé sur le disque"


def test_f03_sans_empreintes_le_paquet_nest_pas_construit(tmp_path):
    """Refuser de conclure vaut aussi pour la construction : produire un
    paquet sans pouvoir en contrôler le contenu reviendrait à affirmer sans
    avoir vérifié."""
    paquet = _paquet_jetable(tmp_path, "-- Seed DEMO\n")
    for chemin in (os.path.join(paquet, "seed_exemple.sql"),
                   os.path.join(paquet, "reference")):
        if os.path.isdir(chemin):
            shutil.rmtree(chemin)
        elif os.path.exists(chemin):
            os.remove(chemin)
    r = subprocess.run([sys.executable, "construire_distribution.py"],
                       capture_output=True, text=True, cwd=paquet)
    assert r.returncode != 0, r.stdout
    assert "CONSTRUCTION REFUSÉE" in (r.stdout + r.stderr)


def test_f03_le_message_final_dit_contre_quoi_il_a_controle():
    """« aucune donnée personnelle » énonçait un fait que le programme
    n'établissait jamais."""
    src = open(os.path.join(HERE, "construire_distribution.py"),
               encoding="utf-8").read()
    assert "contenu contrôlé contre" in src
    assert "verifier_depot.empreintes()" in src


# ═══ F-05 à F-08, F-10 — l'anonymisation ═══════════════════════════════

def test_f05_sans_liste_de_termes_la_generation_est_refusee(monkeypatch):
    """`_termes_prives()` rendait [] en silence : la génération se
    poursuivait SANS UNE SEULE RÈGLE NOMINATIVE et le jeu publié conservait
    les noms de tiers intacts."""
    monkeypatch.setattr(outils_demo, "FICHIER_TERMES", "/inexistant.txt")
    with pytest.raises(SystemExit, match="GÉNÉRATION REFUSÉE"):
        outils_demo._exiger_les_prerequis()


def test_f05_sans_seed_prive_la_generation_est_refusee(monkeypatch):
    monkeypatch.setattr(outils_demo, "SEED_SOURCE", "/inexistant.sql")
    with pytest.raises(SystemExit, match="GÉNÉRATION REFUSÉE"):
        outils_demo._exiger_les_prerequis()


@pytest.mark.parametrize("tuple_sql,attendu", [
    ("1, 'MARTIN', '123456789'", ["1", "'MARTIN'", "'123456789'"]),
    ("'a, b', 2", ["'a, b'", "2"]),           # virgule DANS une chaîne
    ("'l''ecole', NULL", ["'l''ecole'", "NULL"]),   # quote échappée SQL
])
def test_f07_les_valeurs_non_quotees_comptent_dans_lappariement(tuple_sql, attendu):
    """L'appariement était positionnel sur les seules valeurs QUOTÉES. Le
    seed déclare (id, nom, siren, adresse) et `id` n'est pas quoté : `nom`
    recevait donc la valeur de `id`, et l'identité traversait intacte."""
    assert outils_demo._decouper_valeurs(tuple_sql) == attendu


def test_f06_un_insert_de_forme_inattendue_fait_echouer(tmp_path, monkeypatch):
    """Le `if m:` sans `else` laissait l'identité RÉELLE traverser la
    fonction, et le fichier était écrit quand même."""
    faux = tmp_path / "seed.sql"
    faux.write_text("-- pas d'INSERT exploitant ici\nSELECT 1;\n", encoding="utf-8")
    monkeypatch.setattr(outils_demo, "SEED_SOURCE", str(faux))
    monkeypatch.setattr(outils_demo, "_exiger_les_prerequis", lambda: None)
    with pytest.raises(SystemExit, match="GÉNÉRATION REFUSÉE"):
        outils_demo.construire_seed_demo()


def test_f08_toutes_les_colonnes_textuelles_sont_anonymisees():
    """`CompAuxLib` était traitée mais pas `CompAuxNum`, son pendant
    immédiat : la paire l'était à moitié. Un nom de locataire se loge aussi
    bien dans le libellé d'un compte (« 411 DUPONT ») que d'un journal."""
    import fec_io
    couvertes = set(outils_demo.COLONNES_A_ANONYMISER)
    assert {"JournalLib", "CompteLib", "CompAuxNum", "CompAuxLib",
            "PieceRef", "EcritureLib"} <= couvertes
    assert couvertes <= set(fec_io.COLONNES), "colonne inconnue du format FEC"


def test_f10_un_fichier_genere_encore_pollue_est_supprime(tmp_path):
    """Les deux fonctions écrivaient puis rendaient un chemin, sans jamais
    relire leur sortie : toute défaillance des règles se soldait par un jeu
    publié silencieusement dégradé. Le fichier fautif est désormais
    SUPPRIMÉ — le réflexe que construire_distribution a déjà pour son zip."""
    if not verifier_depot.empreintes():
        pytest.skip("dossier privé absent sur cette machine")
    quoi, valeur = verifier_depot.empreintes()[0]
    piege = tmp_path / "sortie.sql"
    piege.write_text(f"-- {valeur}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="ANONYMISATION INCOMPLÈTE"):
        outils_demo._controler_apres_generation(str(piege))
    assert not piege.exists(), "le fichier fautif a été laissé sur le disque"


def test_f10_un_fichier_propre_passe(tmp_path):
    """Contrepartie : pas de faux positif."""
    if not verifier_depot.empreintes():
        pytest.skip("dossier privé absent sur cette machine")
    propre = tmp_path / "sortie.sql"
    propre.write_text(f"INSERT INTO exploitant VALUES ('{FICTIF}');\n",
                      encoding="utf-8")
    outils_demo._controler_apres_generation(str(propre))
    assert propre.exists()


# ═══ F-11 — plus rien d'identifiant en clair dans les fichiers suivis ═══

def test_f11_ni_patronyme_ni_nom_de_voie_en_clair():
    """L'outil d'anonymisation et un test anti-fuite nommaient en clair le
    patronyme et la rue de l'auteur — et la garde ne les voyait pas,
    puisqu'elle ne cherche que l'adresse entière. Le patronyme seul reste
    admis : il est la mention de paternité de dizaines de fichiers. Seul le
    nom de la VOIE est proscrit."""
    reel = os.path.join(HERE, "seed_exemple.sql")
    if not os.path.exists(reel):
        pytest.skip("dossier privé absent sur cette machine")
    adr = re.search(r"'\d+\s+[Rr]ue\s+([^,']+)", open(reel, encoding="utf-8").read())
    if not adr:
        pytest.skip("adresse non exploitable")
    voie = adr.group(1).strip().lower()

    racine = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                            capture_output=True, text=True)
    if racine.returncode != 0:
        pytest.skip("pas de dépôt git ici")
    racine = racine.stdout.strip()
    coupables = []
    for f in subprocess.run(["git", "ls-files"], cwd=racine,
                            capture_output=True, text=True).stdout.split("\n"):
        if not f or f.endswith("test_passe_f.py"):
            continue                      # ce fichier lit la voie, ne l'écrit pas
        try:
            contenu = open(os.path.join(racine, f), encoding="utf-8",
                           errors="ignore").read()
        except OSError:
            continue
        if voie in contenu.lower():
            coupables.append(f)
    assert not coupables, coupables


def test_f11_les_motifs_didentite_viennent_du_dossier_prive():
    """Ils doivent être LUS, pas écrits : c'est la règle que le projet
    s'était donnée et que ces deux fragments enfreignaient."""
    if not os.path.exists(os.path.join(HERE, "seed_exemple.sql")):
        pytest.skip("dossier privé absent sur cette machine")
    motifs = outils_demo._motifs_identite()
    assert motifs, "aucun motif d'identité dérivé du seed"
    src = open(os.path.join(HERE, "outils_demo.py"), encoding="utf-8").read()
    assert "_motifs_identite()" in src.split("REMPLACEMENTS_LIBELLE =")[1][:80]


# ═══ D2-01 — la garde d'origine (CSRF) ══════════════════════════════════
#
# Le modèle de menace reposait sur « 127.0.0.1, donc jamais exposé » : exact
# pour le réseau, sans effet pour le navigateur. Toute page ouverte dans le
# même navigateur pouvait poster ici — et `samesite=Lax` empêchant l'envoi
# du cookie sur une requête inter-site, `_dossier_actif()` retombait sur
# PRINCIPAL : la requête forgée visait TOUJOURS la comptabilité réelle.

@pytest.fixture
def client_web(tmp_path, monkeypatch):
    import sqlite3

    import init_db
    db = str(tmp_path / "compta.db")
    monkeypatch.setenv("COMPTA_DB", db)
    init_db.init(db, "blanc", annee_cible=2026).close()
    c = sqlite3.connect(db)
    c.execute("INSERT INTO exploitant (id,nom,siren) VALUES (1,'MARTIN Jean','000000000')")
    c.execute("INSERT INTO bien (id,exploitant_id,libelle) VALUES (1,1,'Logement')")
    c.commit(); c.close()
    import app as webapp
    webapp.app.config["TESTING"] = True
    # On DEMANDE au logiciel où il écrit, au lieu de le supposer : le module
    # est mis en cache par sys.modules, si bien qu'un test ultérieur dans la
    # même session réutilise le chemin résolu au premier import — la base
    # du test précédent, pas la sienne.
    with webapp.app.test_request_context("/"):
        reel = webapp._db_path()
    if not os.path.exists(reel):
        init_db.init(reel, "blanc", annee_cible=2026).close()
    c = sqlite3.connect(reel)
    c.execute("INSERT OR IGNORE INTO exploitant (id,nom,siren) "
              "VALUES (1,'MARTIN Jean','000000000')")
    c.execute("INSERT OR IGNORE INTO bien (id,exploitant_id,libelle) "
              "VALUES (1,1,'Logement')")
    c.execute("DELETE FROM operation")
    c.execute("UPDATE exercice SET statut='ouvert' WHERE annee=2026")
    c.commit(); c.close()
    return webapp.app.test_client(), reel


def _compter_operations(db):
    import sqlite3
    c = sqlite3.connect(db)
    n = c.execute("SELECT COUNT(*) FROM operation").fetchone()[0]
    c.close()
    return n


SAISIE = {"type": "loyer", "montant": "795.50",
          "date_operation": "2026-03-05", "bien_id": "1"}


def test_d201_une_ecriture_dorigine_etrangere_est_refusee(client_web):
    """Le scénario reproduit avant correctif : un formulaire caché sur une
    page quelconque postait ici, et l'exercice se clôturait."""
    cl, db = client_web
    r = cl.post("/saisir", data=SAISIE,
                headers={"Origin": "http://evil.example"})
    assert r.status_code == 403, r.status_code
    assert _compter_operations(db) == 0, "l'écriture est passée malgré tout"


def test_d201_le_referer_etranger_est_refuse_aussi(client_web):
    """Certains navigateurs n'envoient que le Referer : les deux en-têtes
    sont contrôlés."""
    cl, db = client_web
    r = cl.post("/saisir", data=SAISIE,
                headers={"Referer": "http://evil.example/piege.html"})
    assert r.status_code == 403
    assert _compter_operations(db) == 0


def test_d201_origin_null_est_refuse(client_web):
    """Une politique de référent restrictive fait envoyer « null » plutôt
    que d'omettre l'en-tête : ce n'est pas l'origine attendue."""
    cl, db = client_web
    r = cl.post("/saisir", data=SAISIE, headers={"Origin": "null"})
    assert r.status_code == 403
    assert _compter_operations(db) == 0


def test_d201_la_cloture_forgee_est_refusee(client_web):
    """La route la plus lourde de conséquences : irréversible, et elle ne
    demande de connaître aucune donnée de l'utilisateur."""
    import sqlite3
    cl, db = client_web
    r = cl.post("/cloturer", data={"annee": "2026", "forcer": "1"},
                headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    c = sqlite3.connect(db)
    statut, = c.execute("SELECT statut FROM exercice WHERE annee=2026").fetchone()
    c.close()
    assert statut == "ouvert", "l'exercice a été clôturé par une requête forgée"


def test_d201_une_ecriture_du_logiciel_passe(client_web):
    """Contrepartie indispensable : l'usage normal ne doit pas être gêné.
    Le navigateur annonce l'origine du logiciel lui-même."""
    cl, db = client_web
    r = cl.post("/saisir", data=SAISIE,
                headers={"Origin": "http://localhost"},
                base_url="http://localhost")
    assert r.status_code in (200, 302), r.status_code
    assert _compter_operations(db) == 1


def test_d201_sans_entete_dorigine_la_requete_passe(client_web):
    """Choix DÉLIBÉRÉ, figé ici pour qu'il ne passe pas pour un oubli :
    curl, la ligne de commande et le client de test n'envoient ni Origin ni
    Referer, et les exiger transformerait le contrôle en obstacle sans rien
    gagner — un navigateur envoie TOUJOURS Origin sur un POST inter-site."""
    cl, db = client_web
    r = cl.post("/saisir", data=SAISIE)
    assert r.status_code in (200, 302)
    assert _compter_operations(db) == 1


def test_d201_les_lectures_ne_sont_pas_genees(client_web):
    """La garde ne porte que sur les méthodes qui CHANGENT l'état : une
    lecture forgée ne coûte rien, et refuser les GET casserait la
    navigation depuis un signet."""
    cl, _ = client_web
    r = cl.get("/saisie", headers={"Referer": "http://evil.example"},
               follow_redirects=True)
    assert r.status_code == 200
