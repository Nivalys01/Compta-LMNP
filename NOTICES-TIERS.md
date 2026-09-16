# Composants tiers

Compta LMNP est distribué sous licence **AGPL-3.0-or-later**. Il s'appuie sur
les composants ci-dessous, dont les licences s'appliquent **à ces composants
uniquement**. Toutes sont permissives (BSD, MIT, PSF) et donc compatibles avec
une œuvre sous AGPL : leurs termes sont respectés dès lors que le copyright et
le texte de licence accompagnent toute redistribution.

| Composant | Rôle | Licence |
|---|---|---|
| Python | interpréteur | PSF License |
| Flask | serveur web local | BSD-3-Clause |
| Werkzeug | couche WSGI (dépendance de Flask) | BSD-3-Clause |
| Jinja2 | gabarits (dépendance de Flask) | BSD-3-Clause |
| MarkupSafe | échappement HTML | BSD-3-Clause |
| itsdangerous | signature de sessions (dépendance de Flask) | BSD-3-Clause |
| click | ligne de commande (dépendance de Flask) | BSD-3-Clause |
| blinker | signaux (dépendance de Flask) | MIT |
| reportlab | export PDF de la liasse — **facultatif** | BSD-3-Clause |

Aucun composant sous licence à réciprocité (GPL ou assimilée) n'est utilisé.

## Ce que le projet redistribue — et ce qu'il ne redistribue pas

Cette distinction commande les obligations, et elle a déjà été manquée une
fois :

- **Le paquet client** (`dist/compta_lmnp_client_vX.Y.Z.zip`) et le dépôt
  **ne contiennent aucun composant tiers**. Les lanceurs `.bat` / `.sh`
  installent Flask et reportlab depuis PyPI **sur la machine de
  l'utilisateur**, au premier démarrage. Il n'y a donc pas de redistribution,
  et les obligations BSD/MIT ne sont pas déclenchées.
- **Un exécutable PyInstaller**, lui, embarquerait Flask et reportlab dans le
  binaire : ce serait une redistribution **binaire**, et la BSD-3-Clause
  exigerait alors que le copyright et le texte de licence de chaque composant
  accompagnent le livrable. `construire_exe.py` ne le faisait pas — il
  n'embarquait ni licence, ni notices. C'est l'une des raisons pour lesquelles
  la construction d'exécutable a été **retirée du périmètre** (elle était par
  ailleurs cassée : ni seeds SQL embarqués, ni gestion de `sys._MEIPASS`).

**Si l'exécutable est un jour remis en service**, il faudra livrer à côté du
binaire : le fichier `LICENSE` (AGPL du logiciel), ce fichier, et le texte
complet de chaque licence tierce — la BSD-3 exige la reproduction du texte,
pas un simple renvoi vers le projet d'origine.

## Textes complets

Les textes ne sont pas recopiés ici tant qu'il n'y a pas de redistribution
binaire. Ils sont disponibles auprès de chaque projet, et dans les
métadonnées des paquets installés :

```bash
python -m pip show -f flask reportlab      # emplacement des fichiers de licence
```

| Projet | Source |
|---|---|
| Python | <https://docs.python.org/3/license.html> |
| Flask, Werkzeug, Jinja2, MarkupSafe, itsdangerous, click | <https://github.com/pallets> |
| blinker | <https://github.com/pallets-eco/blinker> |
| reportlab | <https://www.reportlab.com/software/opensource/> |
