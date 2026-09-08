# Installation et mise à jour — Compta LMNP

Ce document couvre l'installation, le lancement et le dépannage.
Pour ce que fait le logiciel et comment il est construit, voir
[README.md](README.md).

---

## Installation (première fois)

### 1. Installer Python (une seule fois)

Le logiciel a besoin de **Python 3.10 ou plus récent**. Vérifiez d'abord
s'il est déjà là : ouvrez un terminal (ou l'invite de commandes) et tapez
`python3 --version` — si un numéro s'affiche, passez à l'étape 2.

| Système | Où le prendre |
|---|---|
| **Windows** | [python.org/downloads/windows](https://www.python.org/downloads/windows/) — prenez le « Windows installer (64-bit) ». **Cochez impérativement « Add python.exe to PATH »** sur le premier écran de l'installateur : sans cette case, le lanceur ne trouvera pas Python. |
| **macOS** | [python.org/downloads/macos](https://www.python.org/downloads/macos/), ou bien `xcode-select --install` dans le Terminal. |
| **Debian, Ubuntu, Mint** | `sudo apt install python3 python3-venv` |
| **Fedora, RHEL, Bazzite** | `sudo dnf install python3` |
| **Arch, Manjaro** | `sudo pacman -S python` |
| **openSUSE** | `sudo zypper install python3` |

> Si vous utilisez une version de Python **très récente** (sortie il y a
> moins de quelques mois) et que l'installation échoue, prenez la version
> précédente : certaines dépendances mettent du temps à s'y adapter.

### 2. Décompresser le logiciel

Décompressez le zip où vous voulez, par exemple `Documents/compta_lmnp`.
**Évitez un dossier synchronisé** (OneDrive, Google Drive, Dropbox) : une
synchronisation déclenchée pendant une écriture peut corrompre la base.

### 3. Lancer

| Système | Comment |
|---|---|
| **Windows** | Double-cliquez `Compta-LMNP-Windows.bat`. Un raccourci « Compta LMNP » est créé sur le Bureau au premier lancement. |
| **Linux** | Dans un terminal, **placez-vous d'abord dans le dossier**, puis lancez (voir ci-dessous). Le double-clic ouvre souvent le fichier dans un éditeur au lieu de l'exécuter. |
| **macOS** | Idem : `cd` dans le dossier, puis `bash Compta-LMNP-Linux-macOS.sh`. Ensuite, `bash Compta-LMNP-Linux-macOS.sh --raccourci` crée un « Compta LMNP.command » sur le Bureau, double-cliquable. |

**Linux et macOS — les deux commandes, dans l'ordre :**

```
cd ~/Documents/compta_lmnp          ← le dossier où vous avez décompressé
bash Compta-LMNP-Linux-macOS.sh
```

La première ligne est **indispensable** et souvent oubliée : sans elle, le
terminal cherche le fichier là où il se trouve (votre dossier personnel) et
répond « Aucun fichier ou dossier de ce nom ». Astuce : dans la plupart des
gestionnaires de fichiers, un clic droit dans le dossier propose « Ouvrir un
terminal ici » — le `cd` est alors déjà fait.

Le premier lancement dure **1 à 3 minutes** : le logiciel crée son
environnement local et télécharge Flask. Ne fermez pas la fenêtre. Les
lancements suivants sont immédiats.

L'application s'ouvre sur **http://localhost:5000**. Pas de cadenas dans
la barre d'adresse, et c'est normal : vos données ne quittent pas votre
ordinateur et ne traversent aucun réseau.

### 4. Premier démarrage

Une base **vierge** est créée à côté du logiciel (`compta.db`). Renseignez
l'exploitant (nom, SIREN, adresse d'activité) dans la page
Immobilisations, puis créez votre premier bien.

> **Pour découvrir le logiciel sans rien saisir** : la page *Dossiers*
> propose un **bac à sable** contenant une année de location complète et
> déjà clôturée — écritures, liasse, FEC. Vous pouvez tout y essayer sans
> aucun risque pour vos données.

### Options du lanceur

| Option | Effet |
|---|---|
| `--verifier` | contrôle l'environnement sans rien lancer |
| `--raccourci` | installe une entrée dans le menu (Linux) ou sur le Bureau (macOS) |
| `--https` | active HTTPS (certificat auto-signé : le navigateur affichera un avertissement — inutile en local) |

### Messages Windows au premier lancement (normaux)

- **SmartScreen** (« Windows a protégé votre ordinateur ») : le lanceur
  n'est pas signé numériquement. Cliquez « Informations complémentaires »
  puis « Exécuter quand même ».
- **Pare-feu** : autorisez l'accès « réseaux privés ». Le logiciel n'écoute
  que sur votre machine (127.0.0.1) — rien n'est accessible de l'extérieur
  ni envoyé sur internet.
- **Certificat du navigateur** : la connexion locale est chiffrée avec un
  certificat auto-signé ; acceptez l'avertissement (Avancé → Continuer).

## Mise à jour (installation existante)

Le code se remplace, **les données restent** :

1. Fermez le logiciel.
2. (Ceinture et bretelles) copiez le dossier `sauvegardes/` ailleurs.
3. Décompressez la nouvelle version PAR-DESSUS l'ancienne (remplacez les
   fichiers). Vos données ne sont pas dans le code : `compta.db`,
   `dossiers/`, `dossiers.json`, `sauvegardes/` et `archives/` ne sont pas
   touchés.
4. Relancez. Au démarrage, chaque dossier est automatiquement mis au
   niveau (migrations versionnées) **après une copie de sûreté
   « avant-migration »** — visible dans la page Dossiers, section
   Sauvegardes, restaurable en un clic.

Ne JAMAIS ouvrir un dossier avec une version plus ancienne que celle qui
l'a mis à jour : le logiciel le refuse de lui-même avec un message clair
(aucune donnée modifiée) — installez simplement la dernière version.

## Où sont mes données ?

Tout est local, dans le dossier du logiciel : `compta.db` (dossier
principal), `dossiers/<nom>/compta.db` (autres dossiers), `sauvegardes/`
(une par jour + avant chaque clôture/migration/restauration), `archives/`
(FEC de chaque clôture, empreinte SHA-256 au manifeste). Pour un
déménagement complet : copier tout le dossier du logiciel suffit.


## Variante : exécutable autonome (sans installer Python)

Un exécutable Windows peut être fabriqué avec PyInstaller — l'utilisateur
n'a alors plus rien à installer. Le script `construire_exe.py` s'en charge,
mais il doit être lancé **sur une machine Windows** : PyInstaller ne
fabrique pas d'exécutable Windows depuis Linux ou macOS.

```
py -3 -m pip install pyinstaller
py -3 construire_exe.py
```

Ce que cela règle : plus de Python à installer, plus d'attente au premier
lancement. Ce que cela ne règle **pas** : SmartScreen. Un exécutable non
signé déclenche « Windows a protégé votre ordinateur » — davantage qu'un
fichier de commandes. La seule parade est une signature de code, dont le
certificat est payant et à renouveler ; ce n'est pas envisageable pour un
logiciel gratuit. Le message se contourne par « Informations
complémentaires » puis « Exécuter quand même ».

Le dossier produit doit être copié **en entier** (pas seulement le .exe).
La base, le certificat, les sauvegardes et le journal d'erreurs se créent
à côté de l'exécutable et survivent aux mises à jour du logiciel.


## Linux : pourquoi un double-clic ne lance rien

Sur la plupart des bureaux Linux (GNOME, KDE…), **double-cliquer sur un
fichier `.sh` l'ouvre dans un éditeur de texte au lieu de l'exécuter**.
C'est un choix de sécurité du système, pas un défaut du logiciel : vous
voyez alors le code s'afficher, et rien ne démarre.

Trois façons de lancer, de la plus sûre à la plus pratique :

**1. Par le terminal (fonctionne toujours)**
```
cd /chemin/vers/compta_lmnp
bash Compta-LMNP-Linux-macOS.sh
```
Si rien n'apparaît alors que vous avez double-cliqué, regardez
`logs/demarrage.log` : le logiciel y écrit pourquoi il n'a pas pu ouvrir de
fenêtre, et la commande exacte à taper. **L'application a probablement
démarré quand même** — essayez `http://localhost:5000` dans votre
navigateur avant toute chose.
La forme `bash <fichier>` est la plus robuste : elle fonctionne même si le
droit d'exécution a été perdu à la décompression, ce qui arrive avec
certains gestionnaires d'archives.

**2. En rendant le fichier exécutable, une fois pour toutes**
```
chmod +x Compta-LMNP-Linux-macOS.sh
./Compta-LMNP-Linux-macOS.sh
```
Certains gestionnaires de fichiers proposent ensuite « Exécuter » ou
« Lancer dans un terminal » au clic droit.

**3. Par le raccourci fourni**
Le fichier `Compta-LMNP.desktop` sert de lanceur graphique. Selon le
bureau, il faut d'abord l'autoriser : clic droit → *Autoriser le
lancement* (GNOME), ou lui donner le droit d'exécution. Vous pouvez le
copier sur votre bureau ou dans `~/.local/share/applications/` pour le
retrouver dans le menu des applications.

> **Un seul fichier `.sh` est livré** — celui qui porte le nom du logiciel.
> S'il y en avait deux, ce serait une erreur d'empaquetage.
