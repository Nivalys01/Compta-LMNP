#!/usr/bin/env python3
# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Assemble un dossier d'audit AUTOPORTANT, à confier à une IA tierce.

    python docs/audit/assembler.py R
    → docs/audit/paquets/passe-R-complet.md

Le document produit contient, dans l'ordre : les invariants, le prompt de la
passe, puis le CONTENU INTÉGRAL de chaque pièce à joindre. Un seul fichier à
téléverser, rien à rassembler à la main — et surtout rien à oublier.

Trois refus délibérés, tous appris ailleurs dans ce projet :

1. **La liste des pièces n'est pas dans ce script.** Elle est lue dans le
   tableau « Pièces à joindre » du prompt lui-même. Une liste recopiée ici
   aurait divergé du prompt à la première pièce ajoutée, et c'est le prompt
   que l'auditeur lit — le script aurait silencieusement joint autre chose
   que ce qui est annoncé (invariant n°5).

2. **Une pièce manquante fait ÉCHOUER l'assemblage**, elle n'est pas passée
   sous silence. Un dossier d'audit incomplet qui a l'air complet conduit
   l'auditeur à déduire au lieu de constater — c'est exactement la règle n°1
   des invariants, vue du côté de celui qui prépare les pièces.

3. **Le document est relu contre les empreintes du dossier réel avant
   d'exister.** Comme `construire_distribution.py`, ce script REFUSE de
   produire quoi que ce soit s'il ne peut pas charger ces empreintes : il ne
   tourne donc que sur le poste qui détient les données. Assembler un dossier
   destiné à un tiers sans pouvoir en contrôler le contenu reviendrait à
   affirmer sans avoir vérifié — et ici, le destinataire est une IA externe.
"""
from __future__ import annotations

import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
LOGICIEL = os.path.join(RACINE, "compta_lmnp")

# Coloration syntaxique du bloc, par extension. Un défaut sans conséquence :
# une extension inconnue donne un bloc sans langage, pas un assemblage raté.
LANGAGES = {".py": "python", ".md": "markdown", ".sh": "bash", ".bat": "bat",
            ".sql": "sql", ".yml": "yaml", ".toml": "toml", ".txt": "text",
            ".desktop": "ini"}


def pieces(source: str) -> list[str]:
    """Les chemins cités dans le tableau « Pièces à joindre » du prompt.

    Le tableau fait foi : c'est lui que l'auditeur lit.
    """
    dans_le_tableau = False
    trouves: list[str] = []
    for ligne in source.splitlines():
        if ligne.startswith("## Pièces à joindre"):
            dans_le_tableau = True
            continue
        if dans_le_tableau and ligne.startswith("## "):
            break                       # section suivante : le tableau est fini
        if not dans_le_tableau or not ligne.startswith("| `"):
            continue
        m = re.match(r"\|\s*`([^`]+)`", ligne)
        if m and not m.group(1).startswith("|"):
            trouves.append(m.group(1))
    return trouves


def cloture(contenu: str) -> str:
    """Une clôture de bloc plus longue que toute suite de ` du contenu.

    Les documents joints contiennent eux-mêmes des blocs de code : une
    clôture à trois accents graves refermerait le bloc au milieu du fichier,
    et tout ce qui suit basculerait hors du bloc sans que rien ne le signale.
    """
    plus_long = max((len(s) for s in re.findall(r"`+", contenu)), default=0)
    return "`" * max(4, plus_long + 1)


def assembler(lettre: str) -> str:
    chemins = [f for f in os.listdir(ICI) if f.startswith(f"{lettre}-")]
    if len(chemins) != 1:
        raise SystemExit(
            f"Passe « {lettre} » : {len(chemins)} fichier(s) trouvé(s) dans "
            f"{ICI} — il en faut exactement un.")
    with open(os.path.join(ICI, chemins[0]), encoding="utf-8") as f:
        prompt = f.read()
    with open(os.path.join(ICI, "00-INVARIANTS.md"), encoding="utf-8") as f:
        invariants = f.read()

    attendues = pieces(prompt)
    if not attendues:
        raise SystemExit(
            f"Aucune pièce lue dans le tableau de {chemins[0]}. Le tableau "
            "« Pièces à joindre » est absent ou d'un autre format : "
            "assembler un dossier sans pièces n'aurait aucun sens.")

    manquantes = [p for p in attendues
                  if not os.path.isfile(os.path.join(RACINE, p))]
    if manquantes:
        raise SystemExit(
            f"ASSEMBLAGE REFUSÉ — pièces introuvables : {manquantes}. "
            "Un dossier incomplet qui a l'air complet fait déduire l'auditeur "
            "au lieu de le faire constater.")

    morceaux = [
        f"# Dossier d'audit — passe {lettre}\n",
        "> Document **autoportant**, assemblé par `docs/audit/assembler.py`.",
        "> Il contient les invariants, le prompt de la passe, puis le contenu",
        f"> intégral des {len(attendues)} pièces à examiner. Rien d'autre n'est",
        "> nécessaire pour conduire la passe.",
        "",
        "> **Aucune donnée réelle n'y figure** : le contenu a été relu contre",
        "> les empreintes du dossier privé avant production. Les pièces jointes",
        "> sont celles d'un dépôt destiné à être public.",
        "",
        "---\n",
        invariants,
        "\n---\n",
        prompt,
        "\n---\n",
        f"# Les pièces ({len(attendues)})\n",
    ]
    for p in attendues:
        with open(os.path.join(RACINE, p), encoding="utf-8",
                  errors="replace") as fichier:
            contenu = fichier.read()
        f = cloture(contenu)
        langage = LANGAGES.get(os.path.splitext(p)[1], "")
        morceaux += [f"\n## `{p}`\n",
                     f"{f}{langage}", contenu.rstrip("\n"), f, ""]

    document = "\n".join(morceaux)

    # ── Garde anti-fuite : le destinataire est un tiers ──────────────────
    if LOGICIEL not in sys.path:
        sys.path.insert(0, LOGICIEL)
    import verifier_depot
    empreintes = verifier_depot.empreintes()
    if not empreintes:
        raise SystemExit(
            "ASSEMBLAGE REFUSÉ — aucune empreinte n'a pu être chargée "
            "(dossier privé absent ?). Le contenu du dossier d'audit n'a donc "
            "pas pu être contrôlé, et il est destiné à une IA tierce : le "
            "produire ici reviendrait à affirmer sans avoir vérifié.")
    norme = verifier_depot.normaliser(document)
    fuites = [quoi for quoi, valeur in empreintes
              if verifier_depot.normaliser(valeur) in norme]
    if fuites:
        raise SystemExit(f"FUITE BLOQUÉE — donnée personnelle dans le "
                         f"dossier assemblé : {sorted(set(fuites))}")

    dossier = os.path.join(ICI, "paquets")
    os.makedirs(dossier, exist_ok=True)
    cible = os.path.join(dossier, f"passe-{lettre}-complet.md")
    with open(cible, "w", encoding="utf-8") as f:
        f.write(document)
    print(f"✓ {os.path.relpath(cible, RACINE)} — {len(attendues)} pièces, "
          f"{len(document) // 1024} Ko, contrôlé contre "
          f"{len(empreintes)} empreinte(s) : aucune donnée personnelle.")
    return cible


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage : python docs/audit/assembler.py <lettre>")
    assembler(sys.argv[1].upper())
