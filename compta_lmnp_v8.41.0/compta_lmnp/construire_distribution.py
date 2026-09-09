# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Construit le paquet de DISTRIBUTION (à remettre à un tiers) :

    python construire_distribution.py   →  dist/compta_lmnp_client_vX.Y.Z.zip

Contenu : le code de production, les lanceurs et la documentation.
JAMAIS : les tests, le dossier reference/ (FEC réels = données personnelles,
SIREN et adresse de l'exploitant), ni aucune base .db, sauvegarde, archive
ou registre de dossiers. Une GARDE vérifie le zip après construction et
échoue s'il contient le moindre fichier interdit — la fuite de données
personnelles est bloquante, pas simplement évitée.
"""
from __future__ import annotations

import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

MODULES_PROD = [
    "app.py", "cli.py", "init_db.py", "migrations.py",
    "schema.sql", "seed_referentiel.sql", "seed_demo.sql",
    "demo/FEC_DEMO_2025.txt",
    "ecritures.py", "operations.py", "gabarits.py", "import_bancaire.py",
    "amortissement.py", "cession.py", "fiscal.py", "parametres.py",
    "controles.py", "audit_cycle.py", "reprise.py", "rejeu_fec.py",
    "export_fec.py", "valider_fec.py", "liasse.py", "liasse_pdf.py",
    "perennite.py", "dossiers.py", "pense_bete.py", "veille_fiscale.py",
    "fec_io.py", "migration_fec.py", "pages.py", "quittances.py", "construire_exe.py",
    "verifier_depot.py",
]
DOCS = ["LICENSE.txt", "README.md", "CHANGELOG.md", "ARCHITECTURE.md", "LISEZ-MOI.md",
        "VERSION"]
# Un SEUL fichier .sh est livré. Le générateur de certificat existait en
# double (.sh et .py) et s'affichait juste à côté du lanceur : sur un
# bureau Linux, l'utilisateur ouvrait l'un pour l'autre (constaté en
# usage). Le générateur Python fait le même travail, sur toutes les
# plateformes, et ne ressemble pas à un lanceur.
LANCEURS = ["Compta-LMNP-Linux-macOS.sh", "Compta-LMNP-Windows.bat",
            "Compta-LMNP.desktop",
            "generer_certificat.py", "ouvrir_navigateur.py"]

# Fichiers locaux référencés par les lanceurs : le paquet DOIT les contenir,
# sinon l'installation neuve échoue chez le client (défaut trouvé en v8.0.0 :
# les générateurs de certificat manquaient, HTTPS tombait en panne).
REFERENCES_LANCEURS = re.compile(
    r"\b([A-Za-z0-9_\-]+\.(?:py|sh|sql))\b")

# Motifs interdits dans le paquet (données personnelles ou de travail).
INTERDITS = [
    re.compile(r"\.db$"), re.compile(r"^reference/"),
    # Le dossier de référence porte une identité RÉELLE. Il était livré
    # (constat v8.13.0) alors que le fichier lui-même portait la mention
    # « NE JAMAIS LIVRER » : c'est désormais impossible.
    re.compile(r"^seed_exemple\.sql$"),
    re.compile(r"^\d{9}FEC\d{8}\.txt$"), re.compile(r"^tests/"),
    re.compile(r"^dossiers(/|\.json$)"), re.compile(r"^sauvegardes/"),
    re.compile(r"^archives/"), re.compile(r"__pycache__"),
]


def construire() -> str:
    version = open(os.path.join(HERE, "VERSION"), encoding="utf-8").read().strip()
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    cible = os.path.join(HERE, "dist", f"compta_lmnp_client_v{version}.zip")

    fichiers = MODULES_PROD + DOCS + LANCEURS
    manquants = [f for f in fichiers
                 if not os.path.exists(os.path.join(HERE, f))]
    if manquants:
        raise SystemExit(f"Fichiers manquants : {manquants}")

    # ── Garde Windows : un .bat DOIT etre en ASCII pur et en CRLF ────────
    #    cmd.exe lit un fichier de commandes octet par octet ; un caractere
    #    accentue (UTF-8, donc multi-octets) ou une fin de ligne Unix
    #    decale sa lecture et il avale le debut des lignes suivantes —
    #    « echo » devient « ho » puis « o », les variables ne sont jamais
    #    affectees, et le lanceur echoue de facon incomprehensible.
    #    Constate en conditions reelles sur Windows 10 (juillet 2026).
    for lanceur in LANCEURS:
        if not lanceur.lower().endswith(".bat"):
            continue
        octets = open(os.path.join(HERE, lanceur), "rb").read()
        non_ascii = [i for i, b in enumerate(octets) if b > 127]
        lf_seuls = octets.count(b"\n") - octets.count(b"\r\n")
        if non_ascii or lf_seuls:
            raise SystemExit(
                f"LANCEUR WINDOWS ILLISIBLE — {lanceur} : "
                f"{len(non_ascii)} octet(s) non-ASCII, {lf_seuls} fin(s) de "
                "ligne Unix. cmd.exe ne peut pas interpreter ce fichier : "
                "reecrivez-le en ASCII pur avec des fins de ligne CRLF.")

    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED) as z:
        for f in fichiers:
            z.write(os.path.join(HERE, f), arcname=f"compta_lmnp/{f}")

    # ── Garde anti-fuite n°1 : aucun NOM interdit ───────────────────────
    with zipfile.ZipFile(cible) as z:
        noms = [n.split("compta_lmnp/", 1)[-1] for n in z.namelist()]
    fuites = [n for n in noms for motif in INTERDITS if motif.search(n)]
    if fuites:
        os.remove(cible)
        raise SystemExit(f"FUITE BLOQUÉE — fichiers interdits : {fuites}")

    # ── Garde anti-fuite n°2 : aucun CONTENU personnel ───────────────────
    #
    #    La garde ci-dessus compare des noms à une liste écrite à la main —
    #    or les fichiers du zip SONT cette liste. Elle vérifiait donc qu'une
    #    liste rédigée par l'auteur ne contenait pas ce qu'il n'y avait pas
    #    mis : structurellement incapable de rien détecter (constat F-03).
    #
    #    Le cas qu'elle laissait passer est précisément celui pour lequel
    #    elle existe : seed_demo.sql et le FEC de démonstration sont les
    #    seuls fichiers du paquet DÉRIVÉS des données réelles, leur nom est
    #    légitime, et personne ne relisait leur contenu (constat F-04).
    #
    #    Les empreintes viennent de verifier_depot, qui les lit dans le
    #    dossier privé : une seule définition de ce qui est sensible.
    #    HERE explicitement dans sys.path : ce script est aussi lancé par
    #    build_client.py via runpy, qui n'ajoute PAS le dossier du script
    #    aux chemins d'import. Sans cela la garde échouerait à l'import —
    #    donc bloquerait la construction, mais pour une mauvaise raison.
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import verifier_depot
    liste = verifier_depot.empreintes()
    if not liste:
        os.remove(cible)
        raise SystemExit(
            "CONSTRUCTION REFUSÉE — aucune empreinte n'a pu être chargée "
            "(dossier privé absent ?). Le contenu du paquet n'a donc pas pu "
            "être contrôlé : produire un paquet dans ces conditions "
            "reviendrait à affirmer sans avoir vérifié.")
    cherchees = [(quoi, verifier_depot.normaliser(v)) for quoi, v in liste]
    fuites_contenu = []
    with zipfile.ZipFile(cible) as z:
        for entree in z.namelist():
            brut = z.read(entree)
            texte = None
            for enc in ("utf-8", "cp1252"):
                try:
                    texte = brut.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if texte is None:
                continue
            norme = verifier_depot.normaliser(texte)
            for quoi, valeur in cherchees:
                if valeur and valeur in norme:
                    fuites_contenu.append(f"{entree} ({quoi})")
    if fuites_contenu:
        os.remove(cible)
        raise SystemExit("FUITE BLOQUÉE — donnée personnelle dans le "
                         f"contenu : {sorted(set(fuites_contenu))}")

    # ── Garde anti-oubli : tout fichier local invoqué par un lanceur doit
    #    être dans le paquet (sinon panne à l'installation chez le client).
    embarques = set(noms)
    manquants_lanceurs = set()
    for lanceur in LANCEURS:
        texte = open(os.path.join(HERE, lanceur), encoding="utf-8",
                     errors="ignore").read()
        for ref in REFERENCES_LANCEURS.findall(texte):
            if os.path.exists(os.path.join(HERE, ref)) and ref not in embarques:
                manquants_lanceurs.add(ref)
    if manquants_lanceurs:
        os.remove(cible)
        raise SystemExit("PAQUET INCOMPLET — fichiers utilisés par les "
                         f"lanceurs mais absents : {sorted(manquants_lanceurs)}")

    taille = os.path.getsize(cible) // 1024
    print(f"✓ Paquet client : {cible} ({taille} Ko, {len(fichiers)} fichiers, "
          f"contenu contrôlé contre {len(liste)} empreinte(s) du dossier "
          "réel : aucune donnée personnelle)")
    return cible


if __name__ == "__main__":
    sys.exit(0 if construire() else 1)
