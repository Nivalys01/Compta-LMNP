# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Construction d'un exécutable Windows autonome (sans Python à installer).

À LANCER SUR WINDOWS, depuis le dossier du logiciel :

    py -3 -m pip install pyinstaller
    py -3 construire_exe.py

PyInstaller ne fait PAS de compilation croisée : un .exe Windows ne peut
être fabriqué que sur Windows. Ce script n'a donc rien à faire sur Linux
ou macOS, et refuse de s'y exécuter.

Choix retenu : --onedir (un dossier), PAS --onefile. Un exécutable
« fichier unique » se décompresse intégralement dans %TEMP% à CHAQUE
lancement — plusieurs secondes sur une machine ancienne, et un antivirus
qui s'affole devant ce comportement. Le dossier démarre vite et ne
surprend personne.

Ce que le .exe change et ne change pas :
  - change : plus besoin d'installer Python ni d'attendre le premier
    lancement (venv + pip) ;
  - ne change pas : SmartScreen. Un exécutable non signé déclenche
    « Windows a protégé votre ordinateur » — davantage qu'un .bat. Seule
    une signature de code (certificat payant, renouvelable) l'évite.
    Voir NOTICE_LISEZ-MOI.md.
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Fichiers de données à embarquer DANS le bundle (le code en a besoin).
# Les données de l'UTILISATEUR (compta.db, sauvegardes, certs, logs) n'y
# sont pas : elles se créent à côté de l'exécutable, au premier lancement.
DONNEES = ["schema.sql"]

# Modules importés dynamiquement (au premier incident, à la demande…) que
# l'analyse statique de PyInstaller ne peut pas voir.
IMPORTS_CACHES = [
    "logging.handlers",       # journal d'erreurs rotatif, branché à chaud
    "sqlite3",
    "reportlab.pdfgen",       # export PDF (optionnel mais embarqué s'il est là)
    "reportlab.lib.pagesizes",
]


def construire() -> int:
    if not sys.platform.startswith("win"):
        print("Ce script doit être lancé SUR WINDOWS : PyInstaller ne "
              "fabrique pas d'exécutable Windows depuis un autre système.")
        return 1

    version = open(os.path.join(HERE, "VERSION"), encoding="utf-8").read().strip()

    cmd = [sys.executable, "-m", "PyInstaller",
           "--noconfirm", "--clean",
           "--onedir",
           "--name", f"ComptaLMNP-{version}",
           "--console",            # la fenêtre affiche les messages et les
                                   # erreurs : indispensable pour le support
           ]
    for f in DONNEES:
        if os.path.exists(os.path.join(HERE, f)):
            cmd += ["--add-data", f"{f}{os.pathsep}."]
    for m in IMPORTS_CACHES:
        cmd += ["--hidden-import", m]
    cmd.append(os.path.join(HERE, "app.py"))

    print("Commande :", " ".join(cmd), "\n")
    code = subprocess.call(cmd)
    if code != 0:
        return code

    dossier = os.path.join(HERE, "dist", f"ComptaLMNP-{version}")
    print(f"""
Exécutable construit : {dossier}

À faire ensuite :
  1. Copiez TOUT le dossier (pas seulement le .exe) sur la machine cible.
  2. Lancez ComptaLMNP-{version}.exe : la base, le certificat et les
     sauvegardes se créeront à côté de l'exécutable.
  3. Au premier lancement, Windows affichera « Windows a protégé votre
     ordinateur » : Informations complémentaires -> Exécuter quand même.
     C'est le comportement normal d'un exécutable non signé.
  4. Testez la restauration d'une sauvegarde AVANT de distribuer : c'est
     le scénario que le passage à l'exécutable est le plus susceptible
     de casser (chemins).
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(construire())
