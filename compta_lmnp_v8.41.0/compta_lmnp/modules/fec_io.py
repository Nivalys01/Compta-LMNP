# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Lecture des fichiers FEC — socle COMMUN aux trois consommateurs.

Avant cette refonte, trois lecteurs coexistaient (validateur, balance de
reprise, rejeu d'exercice), chacun ré-implémentant l'ouverture du fichier,
le découpage tabulaire et la conversion des montants à virgule. Trois
endroits où un même bug d'encodage ou de séparateur pouvait diverger.

Ce module ne fait QUE l'entrée-sortie :
  - `COLONNES` : les 18 colonnes de l'arrêté A-47 A-1, dans l'ordre —
    source unique (le validateur les réexporte pour compatibilité) ;
  - `lire_brut()` : tokenisation pure, sans filtre ni normalisation — le
    validateur garde ainsi tout son pouvoir de détection (lignes
    incomplètes, en-tête inexact…) ;
  - `lignes_nommees()` : les lignes exploitables, sous forme de dicts
    {colonne: valeur}, pour les consommateurs métier (rejeu) ;
  - `nombre()` : montant FEC (virgule décimale, champ vide = 0).

Les RÈGLES restent chez chaque consommateur : le validateur décide ce qui
est conforme, la reprise décide quelles lignes portent une balance, le
rejeu décide comment insérer. L'écriture (export_fec) reste volontairement
séparée : le validateur doit pouvoir contredire l'export, pas partager ses
défauts.
"""
from __future__ import annotations

import csv
import math
import re

COLONNES = [
    "JournalCode", "JournalLib", "EcritureNum", "EcritureDate",
    "CompteNum", "CompteLib", "CompAuxNum", "CompAuxLib",
    "PieceRef", "PieceDate", "EcritureLib", "Debit", "Credit",
    "EcritureLet", "DateLet", "ValidDate", "Montantdevise", "Idevise",
]


# Grammaire FERMÉE d'un montant FEC : des CHIFFRES, une virgule décimale,
# et un signe en tête OU SUFFIXÉ (« 800,00- »), forme admise par l'arrêté et
# produite par plusieurs logiciels de cabinet — elle était lue comme un
# « montant illisible ».
#
# Sa fermeture est tout son intérêt. `float()` accepte « NaN », « inf » et la
# notation scientifique « 1e309 » (qui VAUT inf) : ces valeurs traversaient
# ensuite tous les contrôles d'équilibre sans jamais les faire échouer, car
# nan ≠ nan et inf − inf = nan. Un fichier pouvait ainsi être déclaré
# équilibré alors que la somme n'était pas calculable. Un montant comptable
# est un nombre FINI écrit en chiffres ; rien d'autre n'est un montant.
_MONTANT = re.compile(r"""
    ^\s*
    (?P<prefixe>[+-])?\s*
    (?P<chiffres> \d+ (?:[.,]\d*)? | [.,]\d+ )
    \s*(?P<suffixe>[+-])?
    \s*$""", re.VERBOSE)


def analyser_montant(s: str) -> tuple[float | None, str | None]:
    """(valeur, message d'erreur) — parseur COMMUN au lecteur et au
    validateur, pour qu'ils ne puissent pas diverger sur ce qu'est un
    montant. Champ vide = 0. Aucune valeur non finie n'en sort jamais."""
    s = (s or "").strip()
    if not s:
        return 0.0, None
    m = _MONTANT.match(s)
    if not m:
        return None, f"montant illisible: {s!r}"
    if m["prefixe"] and m["suffixe"]:
        return None, f"montant portant deux signes: {s!r}"
    negatif = "-" in ((m["prefixe"] or "") + (m["suffixe"] or ""))
    valeur = float(m["chiffres"].replace(",", "."))
    if not math.isfinite(valeur):       # chaîne de chiffres démesurée
        return None, (f"montant hors des nombres représentables: {s!r}")
    return (-valeur if negatif else valeur), None


def nombre(s: str) -> float:
    """Montant FEC : virgule décimale, blanc = 0. Lève ValueError sur un
    contenu non numérique (chaque consommateur décide quoi en faire)."""
    valeur, erreur = analyser_montant(s)
    if erreur:
        raise ValueError(erreur)
    return valeur


ENCODAGES = ("utf-8-sig", "cp1252", "iso-8859-15")


def lire_texte(chemin: str) -> str:
    """Contenu du fichier, quel que soit son encodage.

    L'arrêté A47 A-1 autorise explicitement l'ISO-8859-15 en plus de
    l'UTF-8, et c'est ce que produisent plusieurs logiciels de cabinet.
    Le lecteur n'acceptait que l'UTF-8 strict : un FEC parfaitement
    conforme provoquait une `UnicodeDecodeError` brute — y compris dans le
    validateur, dont c'était précisément le rôle de le dire.

    `utf-8-sig` est essayé en premier : il lit l'UTF-8 ordinaire ET retire
    la marque d'ordre des octets qu'ajoutent Excel et plusieurs
    exporteurs. Sans ce retrait, le premier en-tête devenait
    « \ufeffJournalCode » et le rejeu s'arrêtait sur un `KeyError`
    incompréhensible.

    Entre les deux jeux LATINS, l'ordre d'essai ne peut pas trancher : ni
    l'un ni l'autre ne rejette d'octet dans la plage qui les sépare, si
    bien que le premier essayé gagnait toujours. Or l'octet 0xA4 vaut
    « € » en ISO-8859-15 et « ¤ » en CP1252 (où l'euro est 0x80) : tout
    FEC de cabinet en ISO-8859-15 voyait donc ses euros remplacés par le
    symbole monétaire générique, sans le moindre signal. On tranche sur
    l'INDICE plutôt que sur l'ordre : 0xA4 présent alors qu'aucun octet de
    la plage 0x80-0x9F — que l'ISO-8859-15 n'utilise pas et que CP1252
    réserve à ses caractères propres — ne figure dans le fichier désigne
    un fichier ISO-8859-15.
    """
    with open(chemin, "rb") as f:
        brut = f.read()
    try:
        return brut.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    if 0xA4 in brut and not any(0x80 <= o <= 0x9F for o in brut):
        return brut.decode("iso-8859-15")
    derniere = None
    for enc in ("cp1252", "iso-8859-15"):
        try:
            return brut.decode(enc)
        except UnicodeDecodeError as exc:
            derniere = exc
    raise ValueError(
        "Le fichier n'a pu être lu dans aucun encodage connu "
        "(UTF-8, Windows-1252, ISO-8859-15). Il est peut-être corrompu, "
        "ou ce n'est pas un fichier FEC."
    ) from derniere


def type_du_compte(numero: str) -> str:
    """Type PCG déduit du numéro, pour un compte absent du plan livré.

    Un FEC de cabinet contient presque toujours des comptes que le plan
    livré ne connaît pas (401 fournisseurs, 512 banque, 615 entretien…).
    Il faut donc pouvoir les créer à la volée — et la colonne `type` est
    NOT NULL, contrainte à une liste fermée.

    Les comptes d'amortissement et de dépréciation ont leur type propre :
    ce sont des comptes d'actif SOUSTRACTIF, et les ranger en passif
    fausserait le bilan.
    """
    numero = (numero or "").strip()
    if not numero:
        return "attente"
    if numero.startswith(("28", "29", "39", "49", "59")):
        return "amortissement"
    if numero.startswith("47"):
        return "attente"
    # La classe 4 — les comptes de TIERS — ne se déduit pas de son premier
    # chiffre : 401 fournisseurs est au passif, 411 clients à l'actif. Tout
    # ranger en passif contredisait le plan livré, qui déclare bien `411000`
    # en `actif` : un FEC de cabinet portant des auxiliaires (411DUPONT,
    # 4110000001) créait donc des créances typées comme des dettes.
    #
    # Seules les tranches SANS ambiguïté sont tranchées ici. 44 (État),
    # 45 (associés), 46 (divers) et 48 (régularisation) sont mixtes par
    # construction — c'est le SENS DU SOLDE qui décide, pas le numéro : elles
    # restent au repli, et le bilan LMNP les ignore de toute façon (la
    # comptabilité est tenue sans comptes de tiers, cf. constat E-22).
    #
    # Les tranches tranchées ont elles-mêmes leurs EXCEPTIONS, et le plan de
    # comptes les nomme une par une : ce sont les comptes qui portent le
    # solde INVERSE de leur tranche, créés exprès pour ne pas compenser une
    # créance avec une dette. Les ignorer rangeait un avoir fournisseur avec
    # les dettes et un trop-perçu de locataire avec les créances.
    _EXCEPTIONS = {
        "409": "actif",    # fournisseurs DÉBITEURS (avances, avoirs à recevoir)
        "419": "passif",   # clients CRÉDITEURS (trop-perçus, arrhes reçues)
        "425": "actif",    # personnel : avances et acomptes versés
        "4287": "actif",   # personnel : produits à recevoir
        "4387": "actif",   # organismes sociaux : produits à recevoir
    }
    for prefixe in ("4387", "4287", "425", "419", "409"):
        if numero.startswith(prefixe):
            return _EXCEPTIONS[prefixe]
    if numero.startswith(("40", "42", "43")):
        return "passif"                  # fournisseurs, personnel, organismes
    if numero.startswith("41"):
        return "actif"                   # clients, locataires : une CRÉANCE
    return {"1": "passif", "2": "actif", "3": "actif", "4": "passif",
            "5": "actif", "6": "charge", "7": "produit",
            "8": "attente"}.get(numero[0], "attente")


def assurer_comptes(conn, comptes) -> list[str]:
    """Crée les comptes absents du plan. Renvoie ceux qui ont été créés.

    Sans cela, la reprise d'un FEC externe échouait sur une
    `FOREIGN KEY constraint failed` brute — message qui ne dit rien à
    l'utilisateur et ne nomme même pas le compte en cause.
    """
    crees = []
    for numero, libelle in comptes:
        numero = (numero or "").strip()
        if not numero:
            continue
        if conn.execute("SELECT 1 FROM compte WHERE numero=?",
                        (numero,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO compte (numero, libelle, type, classe) "
            "VALUES (?,?,?,?)",
            (numero, (libelle or numero).strip()[:120],
             type_du_compte(numero), int(numero[0])))
        crees.append(numero)
    return crees


SEPARATEURS = ("\t", "|")


def separateur(premiere_ligne: str) -> str:
    """Le séparateur de champs du fichier.

    L'arrêté admet la TABULATION **ou** la barre verticale. Seule la
    tabulation était lue : un FEC à barres verticales — parfaitement
    conforme — était tokenisé en UNE seule colonne. Le validateur
    annonçait « reçu 1 » colonne au lieu de 18, et la reprise rendait
    « 0 écriture rejouée » comme un succès.
    """
    if "\t" in premiere_ligne:
        return "\t"
    return "|" if "|" in premiere_ligne else "\t"


def lire_brut(chemin: str) -> tuple[list[str], list[list[str]]]:
    """(en-tête, lignes) tels quels — tokenisation seule, au séparateur
    détecté sur l'en-tête. Aucune ligne n'est filtrée : les lignes vides ou
    incomplètes sont rendues telles quelles pour que le validateur puisse
    les signaler.

    QUOTE_NONE est essentiel. Le format FEC ne donne AUCUN rôle au
    guillemet : c'est un caractère de texte comme un autre dans un
    libellé. Or le lecteur CSV de Python le traite par défaut comme un
    délimiteur de champ — un seul guillemet non refermé dans un libellé
    faisait donc fusionner toutes les lignes jusqu'au suivant, et elles
    disparaissaient silencieusement de la balance. Sur un vrai FEC, une
    paire déséquilibrée peut escamoter des centaines d'écritures sans que
    rien ne le signale.
    """
    contenu = lire_texte(chemin)
    lignes_texte = contenu.splitlines()
    sep = separateur(lignes_texte[0] if lignes_texte else "")
    rows = list(csv.reader(lignes_texte, delimiter=sep,
                           quoting=csv.QUOTE_NONE))
    if not rows:
        return [], []
    return rows[0], rows[1:]


def lignes_nommees(chemin: str, *, strict: bool = True
                   ) -> list[dict[str, str]]:
    """Lignes exploitables, en dicts nommés d'après l'EN-TÊTE DU FICHIER —
    un FEC aux colonnes ordonnées différemment, ou portant des colonnes
    supplémentaires après les dix-huit réglementaires, reste lisible.

    `strict` (par défaut) REFUSE le fichier dès qu'une ligne ne peut pas
    être nommée, au lieu de l'écarter.

    C'était le défaut le plus grave de la chaîne d'import : une ligne qui
    n'atteignait pas le compte de colonnes disparaissait ici, en silence,
    et la reprise annonçait ensuite « n écritures rejouées » comme un
    succès. Un FEC dont on avait retiré deux colonnes vides en fin de ligne
    — ses montants tous présents — perdait donc des recettes entières, de
    façon parfaitement ÉQUILIBRÉE : aucun contrôle d'équilibre ne pouvait
    la rattraper en aval. Le validateur voit bien ces lignes, mais il n'est
    pas le garde de ce chemin : la reprise pouvait être lancée sans lui.

    Perdre des écritures sans le dire n'est pas une tolérance, c'est une
    perte de données. On lève donc, en nommant les lignes en cause.
    """
    entete, lignes = lire_brut(chemin)
    if not entete:
        if strict:
            raise ValueError(
                "Fichier FEC sans en-tête : la première ligne doit porter "
                "le nom des colonnes (JournalCode, JournalLib, …).")
        return []
    if strict:
        manquantes = [c for c in COLONNES if c not in entete]
        if manquantes:
            raise ValueError(
                "En-tête incomplet : colonne(s) réglementaire(s) absente(s) "
                f"— {', '.join(manquantes)}. Les dix-huit colonnes de "
                "l'arrêté A47 A-1 doivent toutes être présentes.")
    retenues, rejets = [], []
    for i, r in enumerate(lignes, start=2):     # ligne 1 = en-tête
        if not any(x.strip() for x in r):
            continue                            # ligne vide : sans objet
        if len(r) != len(entete):
            rejets.append(f"L.{i} ({len(r)} champs)")
            continue
        retenues.append(dict(zip(entete, r)))
    if rejets and strict:
        apercu = ", ".join(rejets[:5]) + ("…" if len(rejets) > 5 else "")
        raise ValueError(
            f"{len(rejets)} ligne(s) du fichier n'ont pas les "
            f"{len(entete)} colonnes annoncées par son en-tête : {apercu}. "
            "Ces lignes ne peuvent pas être lues, et les écarter en silence "
            "ferait disparaître des écritures d'une reprise annoncée "
            "réussie. Corrigez le fichier source, puis relancez.")
    return retenues
