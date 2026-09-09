# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Import de relevé bancaire (CSV) avec pré-catégorisation par mots-clés.

Le relevé bancaire EST la source des mouvements réels : l'importer supprime
l'essentiel de la frappe. Chaque ligne est rapprochée d'un type d'opération ;
ce qui n'est pas reconnu tombe en 'autres_charges' (donc signalé à requalifier
par les contrôles — comportement prudent, pas silencieux).

Format CSV attendu (séparateur ;, tabulation ou ,) :
    date(JJ/MM/AAAA ou AAAA-MM-JJ);libelle;montant
EXACTEMENT trois colonnes. Montant signé : positif = encaissement, négatif
= décaissement ; les formes -120,50 / 120,50- / (120,50) / -120,50 EUR /
-1 234,50 € sont toutes acceptées.

Un export à colonnes débit et crédit séparées est REFUSÉ, pas deviné : il
était lu comme un montant positif et transformait toutes les charges en
recettes. Toute ligne dont le montant reste illisible est comptée et
restituée par analyser() — jamais ignorée en silence.
"""
from __future__ import annotations
import csv
import io
import re
import unicodedata
from datetime import date

import gabarits as _gabarits
import operations

# Mots-clés -> type de gabarit, pour les DÉCAISSEMENTS.
# Ordre = priorité (premier match gagne).
REGLES = [
    (("loyer", "rent"),                         "loyer"),
    (("pno", "assurance", "gmf", "maif", "matmut", "emprunteur"), "assurance"),
    (("syndic", "copro", "copropriete"),        "charge_copro"),
    (("orange", "free", "sfr", "bouygues", "internet", "box", "fibre"), "telecom"),
    (("chaudiere", "entretien", "reparation", "plomb", "depannage"), "maintenance"),
    # La CFE AVANT les impôts locaux. Dans l'autre ordre, la règle « cfe »
    # était inatteignable en pratique : les trois libellés réalistes d'un
    # avis de CFE — « DGFIP COTISATION FONCIERE DES ENTREPRISES »,
    # « TRESOR PUBLIC CFE 2026 », « CFE 2026 DGFIP » — contiennent tous
    # « dgfip » ou « tresor public », qui matchaient d'abord. Le plan
    # distingue pourtant 635110 (CET) de 635130 (autres impôts locaux), et
    # la liasse imprime une ligne « dont CFE » servie à zéro (constat E-08).
    (("cfe", "cotisation fonciere"),            "cfe"),
    (("taxe fonciere", "teom", "tresor public", "dgfip", "impot local"), "impot_local"),
    # « les acteurs payants actuels » occupait ce tableau : ce n'est pas un
    # oubli de relecture mais le produit d'un remplacement global — le nom du
    # prestataire comptable historique a été anonymisé partout dans le projet,
    # y compris là où il servait de MOT-CLÉ BANCAIRE légitime (une facture de
    # cabinet porte son nom sur le relevé). La clé est donc devenue inerte, et
    # sa place est rendue à des termes qui matchent vraiment (constat E-14).
    (("comptab", "expert comptable", "expertise comptable", "fiduciaire",
      "cabinet comptable"), "honoraires"),
    (("frais", "commission", "cotisation carte", "agios"), "frais_bancaires"),
    (("ikea", "electromenager", "darty", "boulanger", "mobilier"), "petit_equipement"),
]

# Mots-clés -> type, pour les ENCAISSEMENTS.
#
# Un encaissement n'était pas catégorisé du tout : `if montant > 0: return
# "loyer"` faisait de TOUT crédit un loyer imposable. Un dépôt de garantie,
# un apport, une indemnité d'assurance et une allocation logement — quatre
# natures, trois comptes — ressortaient identiques, et la recette annuelle
# était surévaluée de sommes qui, pour deux d'entre elles, ne sont pas des
# produits du tout (constat E-01).
REGLES_ENCAISSEMENT = [
    (("depot de garantie", "depot garantie", "caution", "dg locataire"),
     "depot_garantie_recu"),
    (("deblocage", "mise a disposition pret", "pret debloque"), "emprunt_recu"),
    (("sinistre", "indemnite", "indemnisation", "remboursement sinistre"),
     "indemnite_assurance"),
    (("regularisation charges", "regul charges"), "regularisation_charges"),
    (("provision charges", "charges locatives", "forfait charges"),
     "charges_locatives"),
    # CAF / APL versées en tiers payant : complément de loyer, imposable.
    (("loyer", "rent", "caf", "apl", "als", "msa"), "loyer"),
]

# Une mensualité de prêt MÊLE capital (non déductible) et intérêts
# (déductibles) : aucune proposition automatique ne peut être juste, elle
# demande une ventilation. On ne propose donc RIEN et la ligne part en
# attente, où elle bloque la liasse tant qu'elle n'est pas traitée.
VENTILATION_REQUISE = ("pret", "prets", "emprunt", "echeance", "mensualite",
                       "credit immo", "credit immobilier", "amortissement pret")

# Destination des lignes non identifiées, par sens du flux.
ATTENTE = {"produit": "attente_encaissement", "charge": "attente_decaissement"}


def _cle_libelle(s: str) -> str:
    """Clé de comparaison EXACTE d'un libellé, pour l'historique.

    Volontairement distincte de _norm() : la comparaison se fait côté SQL
    (`LOWER(TRIM(libelle))`), et SQLite ne replie pas les accents. Replier
    ici et pas là-bas rendrait l'historique introuvable pour tout libellé
    accentué — un défaut ajouté en corrigeant E-07.
    """
    return (s or "").strip().lower()


def _norm(s: str) -> str:
    """Normalise un libellé pour la RECHERCHE PAR MOTS-CLÉS : minuscules,
    puis repli des accents.

    Les clés de REGLES sont écrites sans accent (« taxe fonciere »,
    « chaudiere », « copropriete », « reparation ») alors que les libellés
    SEPA des banques en ligne les conservent. « PRELEVEMENT TAXE FONCIÈRE »
    tombait donc dans le fourre-tout quand « TAXE FONCIERE » était reconnu —
    et taxe foncière, entretien de chaudière et appels de copropriété sont
    l'essentiel des charges d'un dossier LMNP (constat E-07).
    """
    s = _cle_libelle(s)
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


def _contient(lib: str, cle: str) -> bool:
    """Vrai si `cle` apparaît au DÉBUT D'UN MOT de `lib`.

    `any(k in lib for k in cles)` cherchait une sous-chaîne, sans aucune
    frontière : « mobilier » matchait dans « IMMOBILIER », donc la mensualité
    d'un prêt immobilier devenait du petit équipement — 10 680 € de capital
    passés en charge sur l'année, le redressement le plus classique en LMNP
    au réel. « rent » matchait de même dans « PARENTS » (constat E-04).

    L'ancrage porte sur le DÉBUT du mot seulement, pas sur sa fin : les
    libellés bancaires fléchissent et tronquent les terminaisons — « comptab »
    doit continuer de reconnaître « COMPTABLE », « reparation » de reconnaître
    « REPARATIONS ». Un `\\b` des deux côtés les aurait tous fait tomber.
    """
    return re.search(rf"\b{re.escape(cle)}", lib) is not None


def _date_iso(s: str) -> str:
    """Convertit une date de relevé en AAAA-MM-JJ. Lève ValueError sinon.

    Aucune validation n'existait : `05/01/26` produisait « 26-01-05 » et une
    période « 26-01 », soit une date de l'an 26 rattachée à un exercice
    inexistant ; `31/13/2026` produisait un mois 13 ; `ab/cd/2026` laissait
    remonter une ValueError d'`int()` sans message exploitable, hors de
    `proposer` (constat E-11).

    Une année sur deux chiffres est REFUSÉE plutôt que devinée : choisir le
    siècle à la place de l'utilisateur, sur une pièce comptable, c'est
    prendre le risque de dater tout un exercice à côté sans que rien ne le
    signale. Le message dit quoi réexporter.
    """
    s = (s or "").strip()
    if "/" in s:                       # JJ/MM/AAAA
        parties = s.split("/")
        if len(parties) != 3:
            raise ValueError(f"date illisible : {s!r} (format attendu "
                             "JJ/MM/AAAA ou AAAA-MM-JJ)")
        j, m, a = (p.strip() for p in parties)
        if len(a) == 2:
            raise ValueError(
                f"année sur deux chiffres : {s!r}. Le siècle n'est pas "
                "devinable — réexportez le relevé avec des années sur "
                "quatre chiffres.")
        if not (j.isdigit() and m.isdigit() and a.isdigit()):
            raise ValueError(f"date illisible : {s!r} (format attendu "
                             "JJ/MM/AAAA ou AAAA-MM-JJ)")
        s = f"{int(a):04d}-{int(m):02d}-{int(j):02d}"
    try:
        date.fromisoformat(s)          # existence réelle : mois 13, 30/02…
    except ValueError:
        raise ValueError(f"date inexistante ou mal formée : {s!r}") from None
    return s


def _nature_attendue(montant: float) -> str:
    """'produit' pour un encaissement, 'charge' pour un décaissement."""
    return "produit" if montant > 0 else "charge"


def _coherent(type_op: str, montant: float, conn=None) -> bool:
    """Le type retenu va-t-il dans le sens du montant ?

    Rien en aval ne peut plus le vérifier : `proposer` enregistre
    `round(abs(montant), 2)` et le guichet impose des montants strictement
    positifs — l'information de signe est détruite. Un encaissement classé
    « assurance » devenait donc une charge déductible de 800 €, alors qu'il
    s'agissait d'une recette : 1 600 € d'écart sur le résultat pour 800 €
    encaissés (constat E-05).
    """
    g = _gabarits.tous(conn) if conn is not None else _gabarits.GABARITS
    fiche = g.get(type_op)
    if fiche is None:
        return False
    return fiche["nature"] == _nature_attendue(montant)


def _seuil_immobilisation(conn=None, annee: int | None = None) -> float:
    """Seuil au-delà duquel une dépense s'immobilise, pour l'exercice visé.

    C'est une RÈGLE FISCALE VERSIONNÉE (menu Réglementation), pas une
    constante : chaque exercice est lu à son millésime. 500 € par défaut,
    tolérance BOI-BIC-CHG-20-30-10.
    """
    if conn is None or annee is None:
        return 500.0
    try:
        import parametres
        return float(parametres.valeur(conn, "seuil_immobilisation", annee,
                                       defaut=500.0))
    except Exception:                     # noqa: BLE001 — le seuil ne doit
        return 500.0                      # jamais faire échouer un import


def categoriser(libelle: str, montant: float, conn=None,
                annee: int | None = None) -> str:
    """Renvoie le type de gabarit proposé pour une ligne de relevé.

    Priorité 1 : l'HISTORIQUE des saisies validées (un libellé déjà rencontré
    reprend son type — vos propres saisies sont le meilleur référentiel).
    Priorité 2 : les mots-clés, distincts selon le SENS du flux.
    Sinon : le compte d'attente 472000, qui BLOQUE la liasse tant que la
    ligne n'a pas été reclassée.

    Le type retenu est confronté au sens du montant avant d'être rendu : une
    nature de charge sur un encaissement (ou l'inverse) part en attente
    plutôt que d'être acceptée.
    """
    attente = ATTENTE[_nature_attendue(montant)]
    lib = _norm(libelle)

    if conn is not None:
        t = suggerer_depuis_historique(conn, libelle)
        if t:
            return t if _coherent(t, montant, conn) else attente

    # Une mensualité de prêt se ventile à la main : ne rien proposer.
    if any(_contient(lib, k) for k in VENTILATION_REQUISE):
        return attente

    regles = REGLES_ENCAISSEMENT if montant > 0 else REGLES
    for cles, type_op in regles:
        if any(_contient(lib, k) for k in cles):
            if not _coherent(type_op, montant, conn):
                return attente
            if _depasse_le_seuil(type_op, montant, conn, annee):
                return attente
            return type_op
    return attente


def _depasse_le_seuil(type_op: str, montant: float, conn=None,
                      annee: int | None = None) -> bool:
    """Un meuble ou un appareil au-delà du seuil n'est pas une charge.

    Le gabarit porte le drapeau `seuil_immo` et un contrôle signalait déjà
    le dépassement APRÈS coup ; l'import, lui, ne testait aucun montant et
    proposait « petit équipement » pour un achat de 1 850 €. Sur-déduction
    l'année de l'achat, aucun amortissement les suivantes, 2033-C amputé —
    c'est-à-dire la raison d'être du régime réel qui disparaît (E-09).

    Aucune proposition n'est faite au-delà du seuil : une immobilisation ne
    se saisit pas comme une opération, elle se crée dans la page
    Immobilisations, avec sa durée et son plan d'amortissement. La ligne
    part donc en attente, où elle bloque la liasse jusqu'à traitement.
    """
    g = _gabarits.tous(conn) if conn is not None else _gabarits.GABARITS
    if not g.get(type_op, {}).get("seuil_immo"):
        return False
    return abs(montant) > _seuil_immobilisation(conn, annee)


def _signature(libelle: str) -> str:
    """Libellé réduit à ses mots ALPHABÉTIQUES, accents repliés.

    « FACTURE CABINET DUPONT 2025 » et « FACTURE CABINET DUPONT 2026 »
    partagent la même signature : c'est ce qui permet à l'historique de
    reconnaître un libellé dont seule la référence ou la date varie —
    l'écrasante majorité des libellés bancaires.

    Volontairement conservateur : la signature garde l'ORDRE et la TOTALITÉ
    des mots. « VIR FACTURE CABINET DUPONT 2025 » ne matchera donc pas, un
    mot en tête suffisant à la distinguer. Une suggestion trop généreuse
    produirait des écritures fausses, ce qui est pire que pas de suggestion.
    """
    return " ".join(re.findall(r"[a-z]{2,}", _norm(libelle)))


def suggerer_depuis_historique(conn, libelle: str) -> str | None:
    """Type le plus fréquemment associé à ce libellé (normalisé) dans les
    opérations déjà saisies, tous exercices confondus. None si inconnu ou
    si l'historique ne pointe que vers un fourre-tout.

    « Fourre-tout » se lit sur le drapeau `requalifier` du gabarit, et non
    sur un nom de type écrit en dur : depuis la passe E, `autres_charges`
    n'est plus le seul — les deux comptes d'attente le portent aussi, et
    resuggérer une attente reconduirait indéfiniment le doute.
    """
    lib = _norm(libelle)
    if len(lib) < 4:
        return None
    sig = _signature(libelle)

    # Comparaison faite en PYTHON, pas en SQL. `LOWER()` de SQLite est
    # ASCII : « CHAUDIÈRE » y restait « CHAUDIèRE » quand Python rendait
    # « chaudière », et l'historique ne retrouvait AUCUN libellé accentué.
    # Le volume en jeu — les opérations saisies d'un dossier LMNP — ne
    # justifie pas de contourner cela par une extension SQLite.
    exacts: dict[str, int] = {}
    signatures: dict[str, int] = {}
    for type_op, libelle_hist in conn.execute(
            "SELECT type, libelle FROM operation "
            "WHERE source='saisie' AND libelle IS NOT NULL"):
        if _norm(libelle_hist) == lib:
            exacts[type_op] = exacts.get(type_op, 0) + 1
        if sig and _signature(libelle_hist) == sig:
            signatures[type_op] = signatures.get(type_op, 0) + 1

    candidats = exacts or signatures        # l'exact prime sur l'approchant
    if not candidats:
        return None
    type_op = max(candidats, key=candidats.get)
    fiche = _gabarits.tous(conn).get(type_op, {})
    return None if fiche.get("requalifier") else type_op


# Séparateurs de milliers (espace ordinaire, insécable, fine insécable) et
# marques de devise que les exports bancaires accolent au montant.
_PARASITES_MONTANT = (" ", "\xa0", " ", "€")


def _montant(brut: str) -> float:
    """Convertit un montant d'export bancaire en flottant SIGNÉ.

    Les banques françaises écrivent le même débit d'au moins cinq façons :
    -120,50 ; 120,50- (signe suffixe, hérité des mainframes) ; (120,50)
    (convention comptable anglo-saxonne) ; -120,50 EUR ; -1 234,50 €.
    Seule la première était lue ; les autres disparaissaient de l'import
    sans un mot, et l'utilisateur concluait que son relevé était vide.

    Lève ValueError si la chaîne reste illisible — à charge de l'appelant
    de COMPTER le rejet et de le restituer, jamais de l'avaler.
    """
    s = (brut or "").strip()
    for p in _PARASITES_MONTANT:
        s = s.replace(p, "")
    s = re.sub(r"(?i)eur", "", s).strip()   # « EUR » ne peut pas être un chiffre
    negatif = False
    if s.startswith("(") and s.endswith(")"):      # (120,50) = -120,50
        negatif, s = True, s[1:-1].strip()
    if s.endswith("-"):                            # 120,50-  = -120,50
        negatif, s = True, s[:-1].strip()
    if not s:
        raise ValueError("montant vide")
    valeur = float(s.replace(",", "."))
    return -abs(valeur) if negatif else valeur


def _delimiteur(texte: str) -> str:
    """Devine le séparateur de colonnes sur le début du fichier.

    Le point-virgule l'emporte à égalité : dans un export français la
    virgule est d'abord un séparateur DÉCIMAL (120,50), donc fréquente
    sans être le délimiteur. La tabulation est reconnue depuis la passe E
    — un export tabulé était auparavant lu comme une colonne unique, donc
    intégralement rejeté (constat E-03).
    """
    debut = texte[:2048]
    comptes = {c: debut.count(c) for c in (";", "\t", ",")}
    meilleur = max(comptes.values())
    if meilleur == 0:
        return ";"
    for c in (";", "\t", ","):             # ordre = priorité à égalité
        if comptes[c] == meilleur:
            return c
    return ";"


def analyser(csv_path: str, conn=None) -> dict:
    """Lit le relevé et rend compte de TOUT : ce qui est proposé, et ce qui
    ne l'est pas.

    Renvoie {"propositions": [...], "rejets": [...]}, chaque rejet portant
    son numéro de ligne, son contenu et la raison. Un import partiel qui se
    présente comme complet est le pire des résultats : le déclarant ne peut
    pas savoir que des charges manquent à l'appel.

    Robustesse (les exports bancaires réels sont sales) :
    - encodage : UTF-8 (avec ou sans BOM) puis repli cp1252 — les banques
      françaises exportent souvent en encodage Windows ;
    - un fichier binaire (PDF renommé…) est refusé avec un message clair ;
    - séparateur : point-virgule, tabulation ou virgule ;
    - montants : voir _montant() ;
    - libellés : tabulations et sauts de ligne remplacés par des espaces
      (interdits au guichet — un relevé bancaire peut en contenir).

    Refuse le FICHIER (et non la ligne) dès qu'une ligne de données ne porte
    pas exactement trois colonnes : un export « Date;Libellé;Débit;Crédit »
    se lisait auparavant sans erreur, la colonne débit étant prise pour un
    montant signé — toutes les charges devenaient des recettes (E-02).
    """
    with open(csv_path, "rb") as f:
        brut = f.read()
    texte = None
    for enc in ("utf-8-sig", "cp1252"):
        try:
            texte = brut.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if texte is None or "\x00" in texte:
        raise ValueError("Ce fichier n'est pas un relevé CSV lisible "
                         "(fichier binaire ? mauvais fichier ?). Exportez le "
                         "relevé au format CSV depuis votre banque.")

    delim = _delimiteur(texte)
    propositions: list[dict] = []
    rejets: list[dict] = []
    for n, r in enumerate(csv.reader(io.StringIO(texte), delimiter=delim), 1):
        if not r or all(not c.strip() for c in r):
            continue                          # ligne vide
        if _norm(r[0]) in ("date", "date operation"):
            continue                          # en-tête
        if len(r) != 3:
            raise ValueError(
                f"Ligne {n} : {len(r)} colonnes au lieu de 3. Ce module lit "
                "un relevé « date;libelle;montant », le montant étant signé "
                "(négatif pour un décaissement). Il ne sait pas lire un "
                "export à colonnes débit et crédit séparées : il prendrait "
                "chaque débit pour une recette, et toutes vos charges "
                "deviendraient des loyers. Réexportez le relevé en trois "
                "colonnes, ou supprimez les colonnes en trop avant l'import.")
        try:
            montant = _montant(r[2])
        except ValueError:
            rejets.append({"ligne": n, "contenu": delim.join(r).strip(),
                           "raison": f"montant illisible ({r[2].strip()!r})"})
            continue
        try:
            date_op = _date_iso(r[0])
        except ValueError as exc:
            rejets.append({"ligne": n, "contenu": delim.join(r).strip(),
                           "raison": str(exc)})
            continue
        date = date_op
        libelle = " ".join(r[1].split())       # tabs/newlines → espace simple
        annee = int(date[:4]) if date[:4].isdigit() else None
        type_op = categoriser(libelle, montant, conn, annee)
        mensuel = type_op in ("loyer", "charges_locatives")
        propositions.append({
            "date_operation": date,
            "libelle": libelle,
            "montant": round(abs(montant), 2),
            "type": type_op,
            "periode": date[:7] if mensuel else None,
        })
    return {"propositions": propositions, "rejets": rejets}


def proposer(csv_path: str, conn=None) -> list[dict]:
    """Propositions d'opérations (non insérées) issues du relevé.

    Ne dit RIEN des lignes rejetées : passer par analyser() partout où
    l'utilisateur doit les voir.
    """
    return analyser(csv_path, conn)["propositions"]


def importer(conn, csv_path: str, valider: bool = False) -> list[dict]:
    """Propose (et insère si valider=True) les opérations issues du relevé."""
    props = proposer(csv_path, conn)
    if valider:
        for p in props:
            operations.saisir(conn, source="import_bancaire", **p)
    return props
