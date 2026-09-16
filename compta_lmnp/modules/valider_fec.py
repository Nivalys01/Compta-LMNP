# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
# sans autorisation écrite de l'auteur.

"""
Jalon J3 — Validateur FEC indépendant.

Réplique les contrôles essentiels de l'outil Test Compta Demat de la DGFiP.
N'enforce QUE des règles vérifiées sur des FEC réels acceptés par l'administration
(notamment : PAS de contrôle de chronologie globale, que les logiciels du marché ne respectent pas).

API :
    erreurs = valider(chemin)        # liste de messages ; vide => fichier conforme
    valider(chemin, comme_dict=True) # rapport structuré
"""
from __future__ import annotations
import datetime
from collections import defaultdict

import fec_io

# Source unique des 18 colonnes : fec_io. Réexportées ici car le validateur
# est aussi utilisé en OUTIL AUTONOME (python valider_fec.py fichier.txt) et
# ses consommateurs historiques importent valider_fec.COLONNES.
COLONNES = fec_io.COLONNES
# Colonnes dont la valeur ne peut pas être vide (A47 A-1).
OBLIGATOIRES = ["JournalCode", "JournalLib", "EcritureNum", "EcritureDate",
                "CompteNum", "CompteLib", "PieceRef", "EcritureLib", "ValidDate"]
TOL = 0.005  # tolérance d'arrondi (demi-centime)


def _parse_montant(s: str):
    """Renvoie (valeur, erreur_format|None). Décimale virgule obligatoire.

    NB : les montants négatifs ne sont PAS rejetés. On pourrait croire qu'un
    montant FEC est toujours positif (le sens étant porté par la colonne
    Débit/Crédit), mais les FEC réels acceptés par l'administration en
    contiennent — notamment dans les à-nouveaux (contre-passations,
    répartitions). Les rejeter produirait des faux positifs sur des fichiers
    parfaitement conformes. Vérifié sur le FEC de référence 2025.

    La conversion elle-même est déléguée à `fec_io.analyser_montant` : le
    validateur et le lecteur doivent s'accorder sur ce qu'EST un montant.
    Le `float()` direct qui se trouvait ici acceptait « NaN », « inf » et
    « 1e309 » — des valeurs qui neutralisent ensuite toute comparaison
    d'équilibre (nan ≠ nan, inf − inf = nan). Le validateur prononçait alors
    « conforme, 0 erreur » sur un fichier dont il n'avait PAS pu calculer
    l'équilibre : le pire verdict possible, puisqu'il rassure.

    Les deux contrôles de FORME qui restent ici sont propres au validateur —
    le lecteur, lui, doit rester tolérant pour pouvoir montrer le fichier
    tel qu'il est."""
    s = (s or "").strip()
    if s == "":
        return 0.0, None
    if "." in s:
        return None, "séparateur décimal '.' interdit (virgule attendue)"
    if " " in s or "\u202f" in s or "\xa0" in s:
        return None, "séparateur de milliers interdit"
    return fec_io.analyser_montant(s)


def _date_valide(s: str) -> bool:
    """Date AAAAMMJJ réellement existante.

    Le contrôle bornait le jour à 31 sans regarder le calendrier : un
    30 février, un 31 avril ou un 29 février d'année non bissextile
    passaient pour des dates valides — sur EcritureDate, PieceDate,
    DateLet, ValidDate et jusque dans le nom de remise du fichier, où la
    date de clôture est censée être celle de l'exercice."""
    if len(s) != 8 or not s.isdigit():
        return False
    try:
        datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return False
    return 1900 <= int(s[:4]) <= 2100


def valider_nom_fichier(nom: str) -> str | None:
    """Vérifie la nomenclature DGFiP SirenFECAAAAMMJJ.txt (ex.
    FEC_REFERENCE_2025.txt). Renvoie un message d'anomalie, ou None si le
    nom est conforme. Contrôle distinct du contenu (c'est le NOM qui est
    imposé pour la remise à l'administration)."""
    import os
    import re
    base = os.path.basename(nom)
    m = re.fullmatch(r"(\d{9})FEC(\d{8})\.txt", base)
    if not m:
        return (f"Nom '{base}' non conforme : attendu SirenFECAAAAMMJJ.txt "
                "(9 chiffres SIREN + 'FEC' + date de clôture + .txt).")
    if not _date_valide(m.group(2)):
        return f"Nom '{base}' : date de clôture '{m.group(2)}' invalide."
    return None


def valider(chemin: str, comme_dict: bool = False):
    erreurs: list[str] = []
    # Observations = anomalies NON bloquantes, à documenter auprès du
    # vérificateur. L'outil DGFiP gradue lui aussi ses constats : anomalies
    # bloquantes (rejet) d'un côté, points à expliquer de l'autre. Le
    # validateur ne doit ni rejeter à tort un fichier réel, ni laisser
    # passer un signal en silence.
    observations: list[str] = []
    lignes_negatives: list[int] = []
    entete, data = fec_io.lire_brut(chemin)

    if not entete and not data:
        erreurs.append("Fichier vide.")
        return {"conforme": False, "erreurs": erreurs} if comme_dict else erreurs

    # 1. En-tête : les dix-huit colonnes A47 A-1, dans l'ordre, EN TÊTE.
    #    L'arrêté énumère les dix-huit PREMIÈRES informations, il ne fixe pas
    #    un maximum de colonnes : la notice DGFiP admet explicitement des
    #    colonnes supplémentaires à la suite (questions 5 à 7 de sa partie
    #    technique). L'égalité stricte rejetait donc en bloc, dès l'en-tête
    #    et sans lire une seule ligne, des fichiers de cabinet conformes.
    if entete[:len(COLONNES)] != COLONNES:
        erreurs.append(f"En-tête non conforme. Attendu 18 colonnes A47 A-1, "
                       f"reçu {len(entete)}.")
        return {"conforme": False, "erreurs": erreurs} if comme_dict else erreurs
    supplementaires = entete[len(COLONNES):]
    if supplementaires:
        observations.append(
            f"{len(supplementaires)} colonne(s) au-delà des dix-huit "
            f"réglementaires ({', '.join(supplementaires)}). Le format les "
            "admet à la suite des colonnes obligatoires ; elles sont à "
            "décrire dans la documentation technique remise avec le fichier.")

    par_ecriture = defaultdict(lambda: {"debit": 0.0, "credit": 0.0, "n": 0})
    # Numéros vus, GLOBALEMENT et PAR JOURNAL : les deux numérotations sont
    # admises (BOI-CF-IOR-60-40-20, §100) et la continuité ne peut être jugée
    # que dans le schéma effectivement employé.
    nums = set()
    nums_par_journal: dict[str, set] = defaultdict(set)
    journaux_non_numeriques: set = set()
    annees_ecriture: list[int] = []
    dates_validation: list[tuple[int, str]] = []
    tot_d = tot_c = 0.0

    for i, r in enumerate(data, start=2):  # ligne 1 = en-tête
        # 2. Nombre de champs : celui qu'annonce l'en-tête du fichier.
        if len(r) != len(entete):
            erreurs.append(f"L.{i}: {len(r)} champs au lieu de "
                           f"{len(entete)}.")
            continue
        champ = dict(zip(entete, r))

        # 3. Colonnes obligatoires non vides.
        for c in OBLIGATOIRES:
            if champ[c].strip() == "":
                erreurs.append(f"L.{i}: colonne obligatoire '{c}' vide.")

        # 4. Dates au format AAAAMMJJ.
        if champ["EcritureDate"] and not _date_valide(champ["EcritureDate"]):
            erreurs.append(f"L.{i}: EcritureDate '{champ['EcritureDate']}' invalide (AAAAMMJJ).")
        elif champ["EcritureDate"]:
            annees_ecriture.append(int(champ["EcritureDate"][:4]))
        if champ["ValidDate"] and not _date_valide(champ["ValidDate"]):
            erreurs.append(f"L.{i}: ValidDate '{champ['ValidDate']}' invalide (AAAAMMJJ).")
        for c in ("PieceDate", "DateLet"):
            if champ[c].strip() and not _date_valide(champ[c]):
                erreurs.append(f"L.{i}: {c} '{champ[c]}' invalide (AAAAMMJJ).")

        # 5. Montants : format + pas de débit ET crédit simultanés.
        d, ed = _parse_montant(champ["Debit"])
        c, ec = _parse_montant(champ["Credit"])
        if ed:
            erreurs.append(f"L.{i}: Debit — {ed}.")
            d = 0.0
        if ec:
            erreurs.append(f"L.{i}: Credit — {ec}.")
            c = 0.0
        if d > TOL and c > TOL:
            erreurs.append(f"L.{i}: débit ET crédit renseignés sur la même ligne.")

        if d < -TOL or c < -TOL:
            lignes_negatives.append(i)

        # 5 bis. CompteNum : le PCG impose au moins 3 caractères (classe +
        # sous-comptes). Un compte à 1-2 chiffres est structurellement invalide.
        cn = champ["CompteNum"].strip()
        if cn and len(cn) < 3:
            erreurs.append(f"L.{i}: CompteNum '{cn}' trop court "
                           "(3 caractères minimum, norme PCG).")
        # ... et ces trois caractères de tête sont des CHIFFRES : ce sont la
        # classe et les subdivisions du plan comptable, dont tout le
        # classement dépend. Seule la LONGUEUR était contrôlée : « 4AB »
        # passait pour un compte de tiers valide. Au-delà du troisième
        # caractère, les subdivisions alphanumériques d'auxiliaires restent
        # admises (411DUPONT).
        elif cn and not cn[:3].isdigit():
            erreurs.append(f"L.{i}: CompteNum '{cn}' — les trois premiers "
                           "caractères doivent être des chiffres (classe et "
                           "subdivisions du plan comptable).")

        # 5 ter. Lettrage cohérent : DateLet ne peut être renseignée sans
        # EcritureLet (une date de lettrage sans code de lettrage n'a pas de
        # sens — contrôle appliqué par Test Compta Demat).
        if champ["DateLet"].strip() and not champ["EcritureLet"].strip():
            erreurs.append(f"L.{i}: DateLet renseignée sans EcritureLet "
                           "(lettrage incohérent).")

        # 5 quater. Champs obligatoires par ligne (Test Compta Demat) :
        # JournalLib, CompteLib, PieceDate et ValidDate ne peuvent être vides.
        for col in ("JournalLib", "CompteLib", "PieceDate", "ValidDate"):
            if not champ[col].strip():
                erreurs.append(f"L.{i}: {col} vide (colonne obligatoire).")

        # 5 quinquies. Colonnes appariées : un compte auxiliaire renseigné
        # exige son libellé (et réciproquement) ; idem montant en devise et
        # code devise.
        if bool(champ["CompAuxNum"].strip()) != bool(champ["CompAuxLib"].strip()):
            erreurs.append(f"L.{i}: CompAuxNum et CompAuxLib doivent être "
                           "renseignés ensemble (ou vides ensemble).")
        if bool(champ["Montantdevise"].strip()) != bool(champ["Idevise"].strip()):
            erreurs.append(f"L.{i}: Montantdevise et Idevise doivent être "
                           "renseignés ensemble (ou vides ensemble).")
        # Montantdevise est un MONTANT : seule sa présence conjointe avec
        # Idevise était vérifiée, si bien que n'importe quel texte y passait
        # pour une contrevaleur.
        if champ["Montantdevise"].strip():
            _v, e_dev = _parse_montant(champ["Montantdevise"])
            if e_dev:
                erreurs.append(f"L.{i}: Montantdevise — {e_dev}.")

        # Agrégation par écriture — la clé est le couple (JOURNAL, numéro),
        # jamais le numéro seul. Beaucoup de logiciels numérotent PAR
        # JOURNAL : AC 1..n et BQ 1..n. Agréger sur le seul numéro
        # additionnait alors des écritures sans rapport, et leurs
        # déséquilibres se COMPENSAIENT — un débit isolé de 800 € dans AC/1
        # et un crédit isolé de 800 € dans BQ/1 donnaient « conforme, 0
        # erreur », alors qu'aucune des deux écritures ne tenait la partie
        # double. Le rejeu avait déjà été corrigé de ce défaut ; le
        # validateur, lui, l'avait gardé.
        journal = champ["JournalCode"].strip()
        numero = champ["EcritureNum"].strip()
        # EcritureNum est un champ ALPHANUMÉRIQUE de l'arrêté (VII-1) :
        # « BQ0001 » est un numéro d'écriture valide, et le refuser en bloc
        # rendait tout un FEC de cabinet non migrable. Seule la CONTINUITÉ
        # a besoin d'entiers : on note les journaux qu'elle ne peut pas
        # juger au lieu d'inventer une non-conformité.
        cle = (journal, numero)
        par_ecriture[cle]["debit"] += d
        par_ecriture[cle]["credit"] += c
        par_ecriture[cle]["n"] += 1
        try:
            n = int(numero)
            nums.add(n)
            nums_par_journal[journal].add(n)
        except ValueError:
            journaux_non_numeriques.add(journal)
        if champ["ValidDate"].strip():
            dates_validation.append((i, champ["ValidDate"].strip()))
        tot_d += d
        tot_c += c

    # 6. Équilibre par écriture + au moins 2 lignes par écriture.
    journaux = {j for j, _n in par_ecriture}

    def _nom(cle):
        journal, numero = cle
        return numero if len(journaux) <= 1 else f"{journal}/{numero}"

    for cle in sorted(par_ecriture):
        e = par_ecriture[cle]
        if abs(e["debit"] - e["credit"]) > TOL:
            erreurs.append(f"Écriture {_nom(cle)} déséquilibrée: "
                           f"débit {e['debit']:.2f} ≠ crédit {e['credit']:.2f}.")
        if e["n"] < 2:
            erreurs.append(f"Écriture {_nom(cle)}: une seule ligne "
                           "(partie double rompue).")

    # 7. Équilibre global.
    if abs(tot_d - tot_c) > TOL:
        erreurs.append(f"Déséquilibre global: débit {tot_d:.2f} ≠ crédit {tot_c:.2f}.")

    # 8. Continuité de la numérotation — GLOBALE **ou** PAR JOURNAL.
    #
    #    Les deux numérotations sont admises (BOI-CF-IOR-60-40-20, §100). Ne
    #    juger que la globale produisait des constats faux dans les deux
    #    sens : des séquences par journal parfaitement continues (AC 10-11,
    #    BQ 20-21) étaient déclarées trouées des numéros 12 à 19, tandis
    #    qu'un vrai trou dans AC (1 puis 3) était masqué par le numéro 2
    #    d'un AUTRE journal. Le fichier est donc jugé continu s'il l'est
    #    dans l'un des deux schémas.
    #
    #    Et c'est une OBSERVATION, pas une erreur bloquante : la notice
    #    DGFiP (question 14) admet des ruptures justifiées par la validation
    #    d'un brouillard. Un trou dans un fichier EXTERNE est un point à
    #    documenter, pas une non-conformité certaine. Les numéros que ce
    #    logiciel produit, eux, restent contrôlés strictement — à
    #    l'export (`export_fec.exporter`), où leur provenance est connue.
    def _trous(ensemble: set) -> list[int]:
        if not ensemble:
            return []
        return sorted(set(range(min(ensemble), max(ensemble) + 1)) - ensemble)

    if nums:
        trous_global = _trous(nums)
        trous_journal = {j: _trous(n) for j, n in nums_par_journal.items()
                         if j not in journaux_non_numeriques}
        trous_journal = {j: t for j, t in trous_journal.items() if t}
        # Quel schéma le fichier emploie-t-il ? Un même numéro présent dans
        # DEUX journaux ne laisse pas le choix : la numérotation est par
        # journal, et c'est par journal qu'il faut la juger — sinon un vrai
        # trou dans AC (1 puis 3) se trouve comblé, aux yeux du contrôle,
        # par le numéro 2 d'un journal sans rapport. À défaut d'un tel
        # indice, on accepte le fichier continu dans l'un OU l'autre schéma.
        vus = defaultdict(set)
        for journal, numeros in nums_par_journal.items():
            for n in numeros:
                vus[n].add(journal)
        par_journal_evident = any(len(j) > 1 for j in vus.values())
        a_signaler = (bool(trous_journal) if par_journal_evident
                      else bool(trous_global and trous_journal))
        if a_signaler:
            detail = "; ".join(f"{j} : {t}" for j, t in sorted(trous_journal.items()))
            observations.append(
                "Numérotation non continue — "
                + (f"par journal ({detail})." if par_journal_evident else
                   f"ni globalement (manquant(s) : {trous_global}), "
                   f"ni par journal ({detail}).")
                + " Une rupture peut s'expliquer (écritures validées depuis "
                "un brouillard, reprise partielle) : elle est à documenter "
                "auprès du vérificateur. Les FEC produits par ce logiciel "
                "n'en comportent pas.")

    # 9. Cohérence date/exercice : un FEC porte les écritures d'UN exercice.
    #    L'année de l'exercice est l'année majoritaire des EcritureDate ; toute
    #    écriture datée d'une autre année est signalée (miroir de la garde du
    #    guichet). Les à-nouveaux réels sont datés au 1er janvier de l'exercice,
    #    donc dans la bonne année — vérifié sur les FEC 2023-2025.
    if annees_ecriture:
        from collections import Counter
        exercice = Counter(annees_ecriture).most_common(1)[0][0]
        hors = sorted({a for a in annees_ecriture if a != exercice})
        if hors:
            erreurs.append(f"Écriture(s) datée(s) hors de l'exercice {exercice} "
                           f"(année(s) trouvée(s) : {', '.join(map(str, hors))}).")

    # 8 bis. Fichier sans aucune écriture.
    #        Un en-tête seul recevait « conforme, 0 erreur » — verdict exact
    #        sur la forme, et parfaitement trompeur : c'est exactement ce que
    #        produit un export qui a perdu toutes ses lignes en chemin. Un
    #        exercice réellement sans mouvement peut donner un tel fichier,
    #        d'où une observation et non une erreur ; mais il n'est plus
    #        possible de confondre « rien à dire » et « rien à lire ».
    if not par_ecriture:
        observations.append(
            "Ce fichier ne contient aucune écriture : seul l'en-tête a été "
            "lu. Un exercice sans mouvement peut le justifier ; vérifiez "
            "sinon que l'export a bien porté sur l'exercice voulu.")

    # 9 bis. Ordre de validation du fichier.
    #        Le fichier peut sortir avec des ValidDate DÉCROISSANTES quand la
    #        numérotation suit l'ordre de saisie et non l'ordre des dates :
    #        une écriture de mars validée avant celle de janvier. Rien ne
    #        l'interdit formellement — d'où une observation, pas une erreur —
    #        mais un fichier dont la chronologie recule est le premier motif
    #        de question d'un vérificateur.
    reculs = [i for (i, d), (_j, precedente)
              in zip(dates_validation[1:], dates_validation[:-1])
              if d < precedente]
    if reculs:
        apercu = ", ".join(str(n) for n in reculs[:5])
        suite = "…" if len(reculs) > 5 else ""
        observations.append(
            f"La date de validation recule {len(reculs)} fois dans le fichier "
            f"(lignes {apercu}{suite}). Le format ne l'interdit pas, mais un "
            "fichier remis se lit normalement dans l'ordre où les écritures "
            "ont été validées : à expliquer, ou à réexporter dans l'ordre.")

    if lignes_negatives:
        apercu = ", ".join(str(n) for n in lignes_negatives[:5])
        suite = "…" if len(lignes_negatives) > 5 else ""
        observations.append(
            f"{len(lignes_negatives)} ligne(s) comportent un montant négatif "
            f"(lignes {apercu}{suite}). Ce n'est pas une anomalie bloquante — "
            "le format ne l'interdit pas et des fichiers réels en contiennent, "
            "typiquement dans les à-nouveaux — mais le sens d'une écriture se "
            "porte normalement par la colonne (Débit OU Crédit) : à documenter "
            "auprès du vérificateur, ou à contre-passer dans la colonne "
            "opposée. Les FEC produits par ce logiciel n'en contiennent jamais "
            "(la base interdit les montants négatifs).")

    if comme_dict:
        return {"conforme": not erreurs, "nb_erreurs": len(erreurs),
                "erreurs": erreurs, "observations": observations}
    return erreurs


def observations(chemin: str) -> list[str]:
    """Anomalies NON bloquantes d'un FEC (à documenter, pas à corriger en
    urgence). `valider()` ne renvoie que les anomalies bloquantes."""
    return valider(chemin, comme_dict=True)["observations"]


if __name__ == "__main__":
    # Le code de retour EST le verdict, pour tout ce qui appelle ce
    # validateur autrement qu'en le lisant : script de sauvegarde, tâche
    # planifiée, chaîne d'intégration. Il valait 0 quoi qu'il arrive — une
    # automatisation pouvait donc archiver puis remettre un FEC déséquilibré
    # au motif que le contrôle « s'était bien passé ». Le message affiché
    # était pourtant explicite : c'est le CONTRAT DE COMMANDE qui manquait.
    #   0 = tous les fichiers conformes
    #   1 = au moins une erreur bloquante
    #   2 = au moins un fichier illisible (absent, corrompu, non FEC)
    import sys
    code = 0
    for chemin in sys.argv[1:]:
        try:
            rapport = valider(chemin, comme_dict=True)
        except (OSError, ValueError) as exc:
            print(f"✗ {chemin} — illisible : {exc}")
            code = max(code, 2)
            continue
        errs, obs = rapport["erreurs"], rapport["observations"]
        if errs:
            print(f"✗ {chemin} — {len(errs)} erreur(s) bloquante(s)")
            for e in errs:
                print(f"    {e}")
            code = max(code, 1)
        else:
            print(f"✓ {chemin} — conforme")
        for o in obs:
            print(f"  ⚠ observation : {o}")
    sys.exit(code)
