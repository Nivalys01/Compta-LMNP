# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Fabrication du jeu de DÉMONSTRATION anonymisé (outil de développement).

Pourquoi ce fichier existe
--------------------------
Le mode « démo » du logiciel s'appuyait sur un dossier RÉEL : nom, SIREN,
adresse et FEC de l'auteur. Deux conséquences fâcheuses, découvertes en
usage :
  1. le paquet client embarquait `seed_exemple.sql`, donc une identité
     réelle — alors que le fichier lui-même portait la mention « NE JAMAIS
     LIVRER » ;
  2. le FEC dont ce seed a besoin, lui, était (à juste titre) exclu du
     paquet : la réinitialisation du bac à sable en mode démo échouait
     chez le client, faute de trouver le fichier.

Ce script dérive du dossier réel un dossier de démonstration : montants
multipliés par un COEFFICIENT, identité et libellés remplacés. Un débutant
dispose ainsi d'un dossier complet et cohérent pour explorer le logiciel,
sans qu'aucune donnée personnelle ne quitte la machine de l'auteur.

Ce que l'anonymisation préserve — et pourquoi
---------------------------------------------
  - l'ÉQUILIBRE de chaque écriture (débit = crédit), au centime : un
    arrondi naïf après multiplication déséquilibre les écritures et le FEC
    devient non conforme. L'écart d'arrondi est reporté sur la ligne la
    plus élevée de l'écriture ;
  - la STRUCTURE : mêmes journaux, mêmes comptes, mêmes dates, même
    numérotation — le dossier de démonstration exerce donc les mêmes
    chemins de code que le dossier réel ;
  - la COHÉRENCE entre le FEC et les composants du seed : tous deux sont
    multipliés par le même coefficient, sinon le contrôle des
    amortissements antérieurs se déclencherait sur le dossier de démo.

Lancer (développement uniquement) :
    python outils_demo.py
"""
from __future__ import annotations

import os
import re

import fec_io

HERE = os.path.dirname(os.path.abspath(__file__))

COEFFICIENT = 0.78

FEC_SOURCE = os.path.join(HERE, "reference", "FEC_REFERENCE_2025.txt")
FEC_DEMO = os.path.join(HERE, "demo", "FEC_DEMO_2025.txt")
SEED_SOURCE = os.path.join(HERE, "seed_exemple.sql")
SEED_DEMO = os.path.join(HERE, "seed_demo.sql")

# Identité fictive. SIREN volontairement invalide au regard de la clé de
# Luhn : personne ne peut le confondre avec une entreprise existante.
DEMO_NOM = "MARTIN CAMILLE"
DEMO_SIREN = "000000000"
DEMO_ADRESSE = "14 Rue Gergovia, 63000 Clermont-Ferrand"
DEMO_BIEN = "Appartement de demonstration"

# Libellés d'écriture : on remplace ce qui identifie (fournisseurs, numéros
# de facture, noms de locataires) et on garde ce qui instruit (la nature de
# l'opération, que le débutant doit pouvoir reconnaître).
REMPLACEMENTS_LIBELLE = [
    (re.compile(r"(?i)\bfaure\b\s*\w*"), "MARTIN"),
    (re.compile(r"(?i)berteaux"), "Gergovia"),
    (re.compile(r"(?i)\b(ikea|mda|leroy\s*merlin|april|castorama|but|conforama)\b"),
     "Fournisseur"),
    # Nom du prestataire comptable historique : il figurait dans les
    # libellés d'écriture du FEC source, donc dans le jeu de démonstration
    # PUBLIÉ. Nommer un tiers dans un dépôt public n'apporte rien et
    # l'expose autant que nous.
    (re.compile(r"(?i)\bfacture\s+les acteurs payants actuels[^)]*"), "facture du cabinet"),
    (re.compile(r"(?i)\bn[°o]\s*\d+"), "n°000"),
    (re.compile(r"\b\d{6,}\b"), "000000"),
]

# Références de pièce : mêmes règles, plus les codes internes du prestataire.
# Termes supplémentaires à retirer, LUS dans le dossier privé — noms de
# tiers (prestataire comptable historique), fournisseurs, toute mention
# nominative repérée dans les libellés du FEC source. Les inscrire ici
# reviendrait à publier ce que l'outil sert à masquer.
FICHIER_TERMES = os.path.join(HERE, "reference", "termes_a_anonymiser.txt")


def _termes_prives() -> list[tuple[re.Pattern, str]]:
    if not os.path.exists(FICHIER_TERMES):
        return []
    regles = []
    for ligne in open(FICHIER_TERMES, encoding="utf-8"):
        terme = ligne.strip()
        if terme and not terme.startswith("#"):
            regles.append((re.compile(rf"(?i)\b{re.escape(terme)}\b[^)\t]*",
                                      ), "cabinet comptable"))
    return regles


REMPLACEMENTS_LIBELLE += _termes_prives()

REMPLACEMENTS_PIECE = REMPLACEMENTS_LIBELLE + [
    (re.compile(r"\b[A-Z]{6}\b"), "PIECE0"),
]


def _anonymiser(texte: str, regles) -> str:
    for motif, remplacement in regles:
        texte = motif.sub(remplacement, texte)
    return texte.strip()


def _mettre_a_l_echelle(lignes: list[list[str]], i_debit: int,
                        i_credit: int, i_num: int) -> list[list[str]]:
    """Multiplie les montants, puis REÉQUILIBRE chaque écriture.

    L'arrondi indépendant de chaque ligne casse l'égalité débit = crédit
    (0,005 € suffit). On corrige l'écart résiduel sur la ligne au montant
    le plus élevé de l'écriture : c'est celle où un centime se remarque le
    moins, et cela garantit un FEC conforme par construction.
    """
    for ligne in lignes:
        for i in (i_debit, i_credit):
            brut = (ligne[i] or "").strip().replace(",", ".")
            if brut:
                ligne[i] = f"{round(float(brut) * COEFFICIENT, 2):.2f}".replace(".", ",")

    groupes: dict[str, list[list[str]]] = {}
    for ligne in lignes:
        groupes.setdefault(ligne[i_num], []).append(ligne)

    for ecriture in groupes.values():
        debit = sum(fec_io.nombre(x[i_debit]) for x in ecriture)
        credit = sum(fec_io.nombre(x[i_credit]) for x in ecriture)
        ecart = round(debit - credit, 2)
        if ecart == 0:
            continue
        # Correction du côté EXCÉDENTAIRE, sur sa ligne la plus élevée.
        col = i_debit if ecart > 0 else i_credit
        cible = max(ecriture, key=lambda x: fec_io.nombre(x[col]))
        corrige = round(fec_io.nombre(cible[col]) - abs(ecart), 2)
        cible[col] = f"{corrige:.2f}".replace(".", ",")
    return lignes


COMPTE_ATTENTE = "472000"


def _resorber_compte_attente(lignes: list[list[str]], idx: dict) -> None:
    """Ramène le compte d'ATTENTE à zéro.

    Le dossier source l'utilise comme compte de passage : ses lignes se
    neutralisent exactement. Après mise à l'échelle, chacune est arrondie
    pour son propre compte et il subsiste un centime — que la reconstruction
    des à-nouveaux ÉCARTE (elle ignore les soldes ≤ 1 ct), d'où un
    déséquilibre d'un centime comblé par un compte d'attente… non soldé, et
    un contrôle BLOQUANT sur un dossier de démonstration tout neuf.

    On absorbe donc le résidu sur une ligne d'attente, en compensant dans la
    MÊME écriture pour préserver l'équilibre.
    """
    solde = round(sum(fec_io.nombre(x[idx["Debit"]])
                      - fec_io.nombre(x[idx["Credit"]])
                      for x in lignes
                      if x[idx["CompteNum"]] == COMPTE_ATTENTE), 2)
    if solde == 0:
        return
    col = idx["Debit"] if solde > 0 else idx["Credit"]
    # La ligne porteuse doit avoir de quoi être RÉDUITE du côté visé :
    # choisir une ligne à zéro dans cette colonne produirait un montant
    # négatif — non conforme, et refusé par le validateur.
    candidates = [x for x in lignes if x[idx["CompteNum"]] == COMPTE_ATTENTE
                  and fec_io.nombre(x[col]) >= abs(solde)]
    if not candidates:
        return
    porteuse = max(candidates, key=lambda x: fec_io.nombre(x[col]))
    nouvelle = round(fec_io.nombre(porteuse[col]) - abs(solde), 2)
    porteuse[col] = f"{nouvelle:.2f}".replace(".", ",")

    # Compensation dans la même écriture, sur sa plus grosse ligne.
    # …sur une ligne d'un AUTRE compte : compenser sur une seconde ligne
    # d'attente annulerait exactement la correction qu'on vient de faire.
    meme = [x for x in lignes
            if x[idx["EcritureNum"]] == porteuse[idx["EcritureNum"]]
            and x is not porteuse
            and x[idx["CompteNum"]] != COMPTE_ATTENTE]
    if not meme:
        return
    autre_col = idx["Credit"] if col == idx["Debit"] else idx["Debit"]
    cible = max(meme, key=lambda x: fec_io.nombre(x[autre_col]))
    ajuste = round(fec_io.nombre(cible[autre_col]) - abs(solde), 2)
    cible[autre_col] = f"{ajuste:.2f}".replace(".", ",")


def construire_fec_demo() -> str:
    entete, lignes = fec_io.lire_brut(FEC_SOURCE)
    idx = {c: i for i, c in enumerate(entete)}
    lignes = [x for x in lignes if len(x) >= len(fec_io.COLONNES)]

    lignes = _mettre_a_l_echelle(lignes, idx["Debit"], idx["Credit"],
                                 idx["EcritureNum"])
    _resorber_compte_attente(lignes, idx)
    for x in lignes:
        x[idx["EcritureLib"]] = _anonymiser(x[idx["EcritureLib"]],
                                            REMPLACEMENTS_LIBELLE)
        x[idx["PieceRef"]] = _anonymiser(x[idx["PieceRef"]],
                                         REMPLACEMENTS_PIECE)
        x[idx["CompAuxLib"]] = _anonymiser(x[idx["CompAuxLib"]],
                                           REMPLACEMENTS_LIBELLE)

    os.makedirs(os.path.dirname(FEC_DEMO), exist_ok=True)
    with open(FEC_DEMO, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(entete) + "\r\n")
        for x in lignes:
            f.write("\t".join(x) + "\r\n")
    return FEC_DEMO


def construire_seed_demo() -> str:
    src = open(SEED_SOURCE, encoding="utf-8").read()

    # 1. Identité — LUE dans le seed, jamais écrite ici. Ce fichier est
    #    publié : y inscrire en clair le nom et l'adresse à masquer
    #    reviendrait à publier exactement ce qu'il sert à protéger
    #    (détecté par verifier_depot.py avant la première publication).
    m = re.search(r"INSERT INTO exploitant[^;]*?VALUES\s*\(([^;]*?)\);",
                  src, re.S)
    if m:
        valeurs = re.findall(r"'((?:[^']|'')*)'", m.group(1))
        remplacements = [DEMO_NOM, DEMO_SIREN, DEMO_ADRESSE]
        for ancienne, nouvelle in zip(valeurs, remplacements):
            if len(ancienne) >= 4:
                src = src.replace(f"'{ancienne}'", f"'{nouvelle}'")
    # Le libellé du bien reprend souvent l'adresse : on le neutralise aussi.
    src = re.sub(r"'Appartement[^']*'", f"'{DEMO_BIEN}'", src)
    # NE PAS reformuler cette chaîne. Ce n'est PAS de la prose : c'est le
    # motif qui neutralise le nom du prestataire comptable dans le seed
    # PRIVÉ, où il subsiste sous cette forme. La prose du dépôt a été
    # reformulée en « les logiciels du marché » ; ces deux motifs-ci
    # (ligne 73 et celle-ci) doivent continuer de matcher le seed et le FEC
    # source, sans quoi l'anonymisation du jeu de démonstration PUBLIÉ
    # échoue en silence.
    src = src.replace("les acteurs payants actuels", "prestataire")

    # 2. Codes de pièce du prestataire (6 majuscules entre quotes).
    #    NUMÉROTÉS : la colonne composant.code_immo est UNIQUE au schéma,
    #    un code identique pour tous ferait échouer l'insertion du seed.
    compteur = iter(range(1, 1000))
    src = re.sub(r"'[A-Z]{6}'", lambda _m: f"'DEMO{next(compteur):02d}'", src)

    # 3. Montants : même coefficient que le FEC, sinon les composants et les
    #    à-nouveaux divergeraient et le contrôle des amortissements
    #    antérieurs se déclencherait sur le dossier de démonstration.
    def _echelle(m: re.Match) -> str:
        return f"{round(float(m.group(0)) * COEFFICIENT, 2)}"

    lignes = []
    for ligne in src.splitlines():
        if re.search(r"\b\d+\.\d{1,2}\b", ligne) and "quote_part" not in ligne:
            # on ne touche ni aux durées (entiers) ni aux dates
            ligne = re.sub(r"(?<![\d.'])\d{2,}\.\d{1,2}(?![\d'])", _echelle, ligne)
        lignes.append(ligne)
    src = "\n".join(lignes)

    # 4. ACCORD avec le FEC : la somme des composants d'un compte doit
    #    égaler, au centime, le solde de ce compte dans le FEC de démo.
    #    Sans cela, le tableau 2033-C et le bilan divergent de quelques
    #    centimes et le contrôle de cohérence de la liasse échoue sur un
    #    dossier neuf — exactement ce qu'un débutant ne doit pas voir.
    src = _accorder_composants_au_fec(src)

    entete = (
        "-- ====================================================================\n"
        "-- Seed DÉMONSTRATION — dossier FICTIF, généré par outils_demo.py.\n"
        "--\n"
        f"-- Dérivé d'un dossier réel : montants x {COEFFICIENT}, identité et\n"
        "-- libellés remplacés. AUCUNE donnée personnelle. C'est CE fichier qui\n"
        "-- est livré au client (seed_exemple.sql, lui, ne quitte jamais le\n"
        "-- poste de développement).\n"
        "--\n"
        "-- Ne pas modifier à la main : régénérer avec `python outils_demo.py`.\n"
        "-- ====================================================================\n"
    )
    corps = src.split("\n", 5)[-1] if src.startswith("--") else src
    open(SEED_DEMO, "w", encoding="utf-8").write(entete + corps)
    return SEED_DEMO


def _accorder_composants_au_fec(src: str) -> str:
    """Ajuste les valeurs brutes pour que leur somme par compte colle au FEC."""
    import reprise
    soldes = reprise.lire_balance_fec(FEC_DEMO)

    # Les colonnes du seed sont ALIGNÉES : plusieurs espaces séparent les
    # champs. Exiger une espace unique ne reconnaissait qu'un composant sur
    # cinq — et l'écart calculé devenait absurde.
    motif = re.compile(
        r"\((\d+),\s*'([^']*)',\s*'((?:[^']|'')*)',\s*'([^']*)',"
        r"\s*([\d.]+),\s*(NULL|\d+),\s*'([^']*)',\s*'(\d+)'")
    trouvees = list(motif.finditer(src))
    par_compte: dict[str, list] = {}
    for m in trouvees:
        par_compte.setdefault(m.group(8), []).append(m)

    remplacements: dict[str, str] = {}
    for compte, groupe in par_compte.items():
        attendu = round(soldes.get(compte, 0.0), 2)
        total = round(sum(float(m.group(5)) for m in groupe), 2)
        ecart = round(attendu - total, 2)
        if ecart == 0:
            continue
        cible = max(groupe, key=lambda m: float(m.group(5)))
        remplacements[cible.group(0)] = cible.group(0).replace(
            cible.group(5), f"{round(float(cible.group(5)) + ecart, 2)}", 1)
    for avant, apres in remplacements.items():
        src = src.replace(avant, apres, 1)
    return src


def main() -> None:
    if not os.path.exists(FEC_SOURCE):
        raise SystemExit("Dossier de référence absent : cet outil ne sert "
                         "qu'en développement.")
    print("FEC de démonstration :", construire_fec_demo())
    print("Seed de démonstration :", construire_seed_demo())


if __name__ == "__main__":
    main()
