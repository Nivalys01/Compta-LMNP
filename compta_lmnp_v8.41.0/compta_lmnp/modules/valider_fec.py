# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
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
    parfaitement conformes. Vérifié sur le FEC de référence 2025."""
    s = (s or "").strip()
    if s == "":
        return 0.0, None
    if "." in s:
        return None, "séparateur décimal '.' interdit (virgule attendue)"
    if " " in s or "\u202f" in s or "\xa0" in s:
        return None, "séparateur de milliers interdit"
    try:
        return float(s.replace(",", ".")), None
    except ValueError:
        return None, f"montant illisible: {s!r}"


def _date_valide(s: str) -> bool:
    if len(s) != 8 or not s.isdigit():
        return False
    a, m, j = int(s[:4]), int(s[4:6]), int(s[6:8])
    if not (1 <= m <= 12 and 1 <= j <= 31 and 1900 <= a <= 2100):
        return False
    return True


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

    # 1. En-tête exact (18 colonnes, bon ordre, bons noms).
    if entete != COLONNES:
        erreurs.append(f"En-tête non conforme. Attendu 18 colonnes A47 A-1, "
                       f"reçu {len(entete)}.")
        return {"conforme": False, "erreurs": erreurs} if comme_dict else erreurs

    par_ecriture = defaultdict(lambda: {"debit": 0.0, "credit": 0.0, "n": 0})
    nums = set()
    annees_ecriture: list[int] = []
    tot_d = tot_c = 0.0

    for i, r in enumerate(data, start=2):  # ligne 1 = en-tête
        # 2. Nombre de champs.
        if len(r) != 18:
            erreurs.append(f"L.{i}: {len(r)} champs au lieu de 18.")
            continue
        champ = dict(zip(COLONNES, r))

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

        # Agrégation par écriture.
        try:
            num = int(champ["EcritureNum"])
            nums.add(num)
            par_ecriture[num]["debit"] += d
            par_ecriture[num]["credit"] += c
            par_ecriture[num]["n"] += 1
        except ValueError:
            erreurs.append(f"L.{i}: EcritureNum '{champ['EcritureNum']}' non entier.")
        tot_d += d
        tot_c += c

    # 6. Équilibre par écriture + au moins 2 lignes par écriture.
    for num in sorted(par_ecriture):
        e = par_ecriture[num]
        if abs(e["debit"] - e["credit"]) > TOL:
            erreurs.append(f"Écriture {num} déséquilibrée: "
                           f"débit {e['debit']:.2f} ≠ crédit {e['credit']:.2f}.")
        if e["n"] < 2:
            erreurs.append(f"Écriture {num}: une seule ligne (partie double rompue).")

    # 7. Équilibre global.
    if abs(tot_d - tot_c) > TOL:
        erreurs.append(f"Déséquilibre global: débit {tot_d:.2f} ≠ crédit {tot_c:.2f}.")

    # 8. Continuité de la numérotation (1..N sans trou).
    if nums:
        attendu = set(range(min(nums), max(nums) + 1))
        manquants = sorted(attendu - nums)
        if manquants:
            erreurs.append(f"Numérotation non continue, EcritureNum manquant(s): {manquants}.")

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
    import sys
    for chemin in sys.argv[1:]:
        rapport = valider(chemin, comme_dict=True)
        errs, obs = rapport["erreurs"], rapport["observations"]
        if errs:
            print(f"✗ {chemin} — {len(errs)} erreur(s) bloquante(s)")
            for e in errs:
                print(f"    {e}")
        else:
            print(f"✓ {chemin} — conforme")
        for o in obs:
            print(f"  ⚠ observation : {o}")
