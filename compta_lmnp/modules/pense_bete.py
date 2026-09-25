# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Pense-bête — ce que le logiciel ne fait PAS à votre place.

La comptabilité est automatisée ; mais déclarer, payer, informer le greffe
restent des gestes MANUELS de l'exploitant. Ce module croise le calendrier
et l'état du dossier pour rappeler, au bon moment, ce qu'il faut faire :

  - échéances calendaires récurrentes (déclaration de résultats, 2042C-PRO,
    CFE, taxe foncière) — dates indicatives : les dates exactes varient
    chaque année, toujours vérifier sur impots.gouv.fr ;
  - événements du dossier : exercice à clôturer/déclarer, bien acquis dans
    l'année (formalités de début/extension d'activité), seuils LMP,
    fonds travaux ALUR jamais saisi, sauvegardes.

Chaque rappel : {niveau: 'important'|'a_prevoir'|'info', titre, detail}.

S'y ajoute une CHECKLIST des oublis récurrents (`OUBLIS_FREQUENTS`), qui ne
dépend pas de l'état du dossier : ce sont les fautes que les loueurs
meublés au réel commettent le plus souvent, regroupées par moment de la
vie du dossier. Elle sert de relecture avant clôture — pas de conseil
personnalisé : chaque situation mérite d'être vérifiée, au besoin auprès
d'un professionnel.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date


# ── Checklist des oublis récurrents ─────────────────────────────────────────
# Synthèse de sources spécialisées et de la doctrine administrative,
# recoupée en juillet 2026. Volontairement formulée en POINTS DE VIGILANCE
# et non en affirmations fiscales : le but est de déclencher une
# vérification, pas de tenir lieu de conseil.
OUBLIS_FREQUENTS = [
    # --- Au démarrage -------------------------------------------------------
    {"moment": "Au démarrage de l'activité",
     "titre": "Frais d'acquisition passés par pertes et profits",
     "detail": "Frais de notaire, droits de mutation et commission "
               "d'agence sont fréquemment considérés comme un coût "
               "d'entrée définitivement perdu. Ils ne le sont pas : selon "
               "l'option retenue, ils se déduisent l'année d'acquisition "
               "ou s'incorporent au prix de revient pour être amortis. "
               "C'est l'oubli le plus coûteux de la première année, et il "
               "est difficile à rattraper ensuite."},
    {"moment": "Au démarrage de l'activité",
     "titre": "Immatriculation et numéro SIRET",
     "detail": "L'activité doit être déclarée pour obtenir un SIRET, et "
               "ce numéro doit être reporté sur la déclaration "
               "complémentaire de revenus. Un dossier sans SIRET reporté "
               "est une anomalie visible immédiatement par "
               "l'administration."},
    {"moment": "Au démarrage de l'activité",
     "titre": "Terrain amorti par erreur",
     "detail": "La quote-part de terrain n'est jamais amortissable. Si "
               "elle a été noyée dans la valeur du bâti, l'amortissement "
               "est surévalué chaque année — et l'erreur se répète "
               "jusqu'à la revente."},

    # --- Charges oubliées ---------------------------------------------------
    {"moment": "Charges souvent oubliées",
     "titre": "CFE — découverte plusieurs années trop tard",
     "detail": "La cotisation foncière des entreprises s'applique à la "
               "location meublée, sauf cas d'exonération, et n'est "
               "généralement pas due la première année. Beaucoup de "
               "bailleurs la découvrent avec un rappel : vérifiez votre "
               "espace professionnel dès la deuxième année."},
    {"moment": "Charges souvent oubliées",
     "titre": "Frais de déplacement : ne pas confondre les deux barèmes",
     "detail": "Les trajets réellement engagés pour l'activité (état des "
               "lieux, remise des clés, assemblée générale, visite de "
               "travaux) sont des charges, sur justificatif et pour un "
               "motif professionnel. Attention à une confusion "
               "fréquente : le barème KILOMÉTRIQUE (indemnités "
               "kilométriques) ne s'applique PAS aux BIC — il vise les "
               "traitements et salaires et les BNC. En BIC, c'est le "
               "barème CARBURANT qui existe, ouvert aux exploitants "
               "individuels au réel simplifié ayant opté pour la "
               "comptabilité super-simplifiée. Et ce barème ne couvre que "
               "le carburant : les dépenses qu'il ne couvre pas — péages, "
               "stationnement, assurance, entretien — se déduisent EN "
               "PLUS, pour leur montant réel et au prorata de l'usage "
               "professionnel.",
     "sources": ["BOI-BAREME-000003 (barème carburant)",
                 "CGI, art. 302 septies A ter A",
                 "BOI-BIC-CHG-40-20-40 (frais de déplacement du chef "
                 "d'entreprise)"]},
    {"moment": "Charges souvent oubliées",
     "titre": "Frais de comptabilité et d'outillage",
     "detail": "Honoraires d'expert-comptable, abonnement à un service de "
               "télétransmission, logiciel : ce sont des charges "
               "d'exploitation. Note utile depuis 2025 : la réduction "
               "d'impôt pour adhésion à un organisme de gestion agréé est "
               "supprimée, mais la déduction des frais, elle, demeure."},
    {"moment": "Erreurs de classement",
     "titre": "Caution mutuelle d'emprunt : ce n'est pas une charge",
     "detail": "Les frais de garantie d'un prêt se partagent en deux. La "
               "commission de caution est acquise à l'organisme : c'est "
               "une charge. Mais la part versée au FONDS MUTUEL DE "
               "GARANTIE est restituable en fin de prêt : c'est une "
               "CRÉANCE, pas une dépense — la déduire revient à déduire "
               "une somme qui vous sera rendue. Votre offre de prêt "
               "distingue les deux montants. Les frais d'hypothèque ou de "
               "privilège de prêteur de deniers, eux, ne se restituent "
               "pas : ce sont bien des charges.",
     "sources": ["CGI, art. 39-1 (charge = dépense engagée et définitive)",
                 "PCG, compte 275 « Dépôts et cautionnements versés »"]},
    {"moment": "Au démarrage de l'activité",
     "titre": "Frais d'acquisition : deux conditions à connaître",
     "detail": "L'option pour la déduction immédiate des frais "
               "d'acquisition (notaire, droits de mutation, commission "
               "d'agence) est GLOBALE et irrévocable : elle vaut pour "
               "TOUTES vos immobilisations, pas bien par bien, et vous ne "
               "pourrez pas en changer pour le suivant. Seconde condition, "
               "beaucoup moins connue : si le logement a été acquis AVANT "
               "d'être affecté à la location meublée — le cas le plus "
               "fréquent —, il entre au bilan pour sa valeur à la date "
               "d'affectation, et les frais payés à l'achat d'origine ne "
               "sont alors pas déductibles.",
     "sources": ["CGI, annexe III, art. 38 quinquies",
                 "PCG, art. 213-8"]},
    {"moment": "Charges souvent oubliées",
     "titre": "Assurances et frais bancaires du prêt",
     "detail": "Assurance propriétaire non occupant, assurance loyers "
               "impayés, assurance emprunteur, frais de dossier et de "
               "garantie : souvent oubliés parce qu'ils sont prélevés "
               "automatiquement et n'arrivent pas sous forme de facture."},

    # --- Erreurs de classement ---------------------------------------------
    {"moment": "Erreurs de classement",
     "titre": "Entretien ou amélioration ?",
     "detail": "Une réparation se déduit l'année où elle est engagée ; un "
               "aménagement qui crée un élément nouveau ou augmente la "
               "valeur du bien s'immobilise et s'amortit. C'est l'un des "
               "points les plus regardés en cas de contrôle, parce qu'il "
               "déplace de la charge immédiate vers de l'amortissement "
               "étalé."},
    {"moment": "Erreurs de classement",
     "titre": "Taxe d'habitation : déductible seulement si elle suit le bien",
     "detail": "La taxe d'habitation due parce que VOUS conservez la "
               "jouissance du logement — résidence secondaire, logement "
               "vacant que vous gardez meublé à votre usage — n'est pas "
               "une charge de l'activité : elle ne se déduit pas. Ne la "
               "saisissez que si elle se rattache réellement à "
               "l'exploitation.",
     "sources": ["CGI, art. 39-1 (charges engagées dans l'intérêt de "
                 "l'exploitation)"]},
    {"moment": "Erreurs de classement",
     "titre": "Indemnité d'assurance sur un bien détruit",
     "detail": "Une indemnité qui répare un dommage courant (dégât des "
               "eaux, perte de loyers) est un produit de l'exercice. Mais "
               "une indemnité versée pour la DESTRUCTION ou la disparition "
               "d'un bien immobilisé ne se traite pas comme un produit "
               "ordinaire : elle relève du régime des plus-values, comme "
               "une cession. La confondre avec une indemnité courante "
               "gonfle le résultat imposable à tort.",
     "sources": ["CGI, art. 39 duodecies",
                 "CGI, art. 39 quaterdecies 1 ter"]},
    {"moment": "Erreurs de classement",
     "titre": "Mobilier passé en charge d'un bloc",
     "detail": "Un équipement durable de valeur significative n'est pas "
               "une charge de l'année : il s'amortit sur sa durée "
               "d'usage. L'électroménager et le mobilier ont des durées "
               "plus courtes que le bâti — les traiter en charge gonfle "
               "artificiellement une année et appauvrit les suivantes."},
    {"moment": "Erreurs de classement",
     "titre": "Rattachement : trésorerie en cours d'année, régularisation "
              "à la clôture",
     "detail": "La quasi-totalité des LMNP relèvent du réel SIMPLIFIÉ et "
               "peuvent opter pour la comptabilité « super-simplifiée » — "
               "une case à cocher en tête de la déclaration 2031-SD. Au "
               "quotidien, on enregistre alors les ENCAISSEMENTS et les "
               "PAIEMENTS : c'est une comptabilité de trésorerie, et c'est "
               "ce que fait ce logiciel. Mais l'option ne dispense pas de "
               "tout : à la CLÔTURE, les créances et les dettes doivent "
               "être constatées — une facture de décembre payée en janvier "
               "revient à l'exercice de décembre. Une exception notable "
               "demeure en trésorerie pure : les frais généraux payés à "
               "échéances régulières dont la périodicité n'excède pas un "
               "an (assurance, abonnements). L'administration est explicite "
               "sur le principe : on ne peut pas se limiter à la "
               "trésorerie en faisant abstraction des créances et dettes "
               "de clôture.",
     "sources": ["CGI, art. 302 septies A ter A",
                 "Code de commerce, art. L. 123-25",
                 "BOI-BIC-DECLA-30-20-20"]},
    {"moment": "Erreurs de classement",
     "titre": "Charges récupérables : penser la SYMÉTRIE",
     "detail": "Les provisions encaissées auprès du locataire sont "
               "imposées en produits ; les charges correspondantes se "
               "déduisent. L'erreur n'est pas de déduire, c'est de "
               "déduire SANS avoir déclaré le produit en face — ou "
               "l'inverse. Vérifiez que les deux côtés figurent bien."},

    # --- Avant de déclarer --------------------------------------------------
    {"moment": "Avant de déclarer",
     "titre": "Ne pas déclarer une année sans loyer",
     "detail": "Même sans recette, les charges et les amortissements "
               "existent et peuvent créer un déficit reportable sur les "
               "bénéfices futurs de l'activité. Ne rien déposer, c'est "
               "renoncer à ce report."},
    {"moment": "Avant de déclarer",
     "titre": "Justificatifs : 6 ans au minimum, 10 ans pour les pièces "
              "comptables",
     "detail": "Deux délais à ne pas confondre. Le droit de REPRISE de "
               "l'administration est de 3 ans en matière d'impôt sur le "
               "revenu (jusqu'au 31 décembre de la 3e année suivant celle "
               "de l'imposition), porté à 10 ans en cas d'activité "
               "occulte. L'obligation de CONSERVATION, elle, est de 6 ans "
               "pour les documents sur lesquels l'administration peut "
               "exercer son droit de contrôle, et le Code de commerce "
               "impose 10 ans pour les livres et pièces comptables. En "
               "pratique : gardez 10 ans. Le logiciel archive vos FEC — il "
               "n'archive pas vos factures.",
     "sources": ["LPF, art. L. 169 (droit de reprise : 3 ans)",
                 "LPF, art. L. 102 B (conservation : 6 ans)",
                 "Code de commerce, art. L. 123-22 (10 ans)"]},
    {"moment": "Avant de déclarer",
     "titre": "Deux dépôts, deux espaces, deux dates",
     "detail": "La liasse (2031-SD et tableaux 2033) se dépose depuis "
               "l'espace PROFESSIONNEL d'impots.gouv.fr — « Votre espace "
               "professionnel » puis « Déclarer » — généralement au "
               "2e jour ouvré suivant le 1er mai, avec une tolérance de "
               "15 jours pour la voie dématérialisée. Le résultat est "
               "ensuite reporté sur la 2042-C-PRO, qui se dépose depuis "
               "l'espace PARTICULIER — « Votre espace particulier » puis "
               "« Déclarer mes revenus » — à une date qui varie selon le "
               "département (trois zones). Les deux espaces sont "
               "distincts et demandent chacun leur création. Le "
               "calendrier exact est publié chaque année sur "
               "impots.gouv.fr, rubrique « Professionnel > Déclarer > "
               "Résultats ». Un dépôt tardif déclenche une majoration.",
     "sources": ["impots.gouv.fr — espaces professionnel et particulier",
                 "CGI, art. 1728 (majorations pour dépôt tardif)"]},
    {"moment": "Avant de déclarer",
     "titre": "Amortissements et revente",
     "detail": "Une évolution introduite en 2025 modifie le traitement "
               "des amortissements pratiqués lors du calcul de la "
               "plus-value de revente. Cela ne change rien à la tenue "
               "courante, mais beaucoup en découvrent l'effet au moment "
               "de vendre : si une cession se profile, faites le point "
               "avant de signer."},
]


# ── Actualités réglementaires ───────────────────────────────────────────────
# Faits DATÉS et sourcés, distincts de la checklist intemporelle. Ils
# vieillissent : chacun porte sa date de vérification, et le module de
# veille fiscale sert précisément à les remettre en question.
VERIFIE_LE = "13 août 2026"

ACTUALITES = [
    {"titre": "Facturation électronique : une échéance vous concerne au "
              "1er septembre 2026",
     "resume": "Contrairement à une idée répandue, la réforme touche AUSSI "
               "les loueurs meublés dont les loyers sont exonérés de TVA.",
     "detail":
        "La ligne de partage n'est pas l'exonération, mais "
        "l'ASSUJETTISSEMENT. Vos loyers d'habitation sont exonérés de TVA "
        "(CGI art. 261 D), mais votre activité reste assujettie dès lors "
        "qu'elle est immatriculée et dispose d'un SIREN. La fiche "
        "officielle de la DGFiP est explicite : les bailleurs exonérés "
        "n'ont pas d'obligation d'ÉMISSION, mais « en réception, bien "
        "qu'exonérés, ils restent assujettis à la TVA et devront recevoir "
        "des factures électroniques, sous réserve de disposer également "
        "d'un numéro SIREN ».\n\n"
        "Ce que cela implique concrètement :\n"
        "• RÉCEPTION — au 1er septembre 2026, vous devez être en mesure de "
        "recevoir les factures de vos fournisseurs professionnels "
        "(artisans, assureur, syndic, comptable) au format électronique, "
        "via une plateforme agréée. Il suffit de choisir une plateforme et "
        "d'y référencer votre SIREN.\n"
        "• ÉMISSION — elle ne vous concerne PAS si vos loyers sont "
        "exonérés. Une quittance de loyer n'est pas une facture. "
        "L'obligation d'émission vise les loueurs redevables de la TVA "
        "(para-hôtellerie, résidences de services), au 1er septembre 2027 "
        "pour les petites et moyennes entreprises.\n\n"
        "La liste officielle des plateformes agréées est publiée sur "
        "impots.gouv.fr. Aucune n'est imposée : le choix vous appartient, "
        "et méfiez-vous des messages qui présentent une plateforme "
        "particulière comme obligatoire.",
     "sources": [
        "DGFiP — fiche « Facturation électronique : je suis un loueur en "
        "meublé » (version octobre 2025)",
        "CGI, art. 261 D (exonération de TVA des loyers d'habitation)",
        "CGI, art. 289 bis (e-invoicing) et 290 (e-reporting)",
        "Ordonnance n° 2021-1190 du 15 septembre 2021"]},
]

# Échéances récurrentes de l'activité. Mois et jour seulement : l'année est
# calculée à l'affichage, pour que le tableau ne périme pas.
ECHEANCES = [
    {"quand": "2e jour ouvré après le 1er mai (+15 j en ligne)",
     "quoi": "Déclaration de résultats 2031-SD et tableaux 2033",
     "ou": "impots.gouv.fr — espace PROFESSIONNEL"},
    {"quand": "mai-juin, selon le département",
     "quoi": "Déclaration de revenus 2042-C-PRO (report du résultat)",
     "ou": "impots.gouv.fr — espace PARTICULIER"},
    {"quand": "1er septembre 2026",
     "quoi": "Être en mesure de RECEVOIR des factures électroniques",
     "ou": "plateforme agréée de votre choix (liste sur impots.gouv.fr)"},
    {"quand": "15 octobre (prélèvement : 20 octobre)",
     "quoi": "Taxe foncière",
     "ou": "impots.gouv.fr — espace particulier"},
    {"quand": "15 décembre",
     "quoi": "Cotisation foncière des entreprises (CFE)",
     "ou": "impots.gouv.fr — espace PROFESSIONNEL"},
    {"quand": "1er septembre 2027",
     "quoi": "Émission de factures électroniques — SEULEMENT si vous êtes "
             "redevable de la TVA (para-hôtellerie, résidences de services)",
     "ou": "votre plateforme agréée"},
]


def actualites() -> dict:
    """Actualités datées + échéances. Séparées de la checklist : les unes
    périment, l'autre non."""
    # Clé « faits » et non « items » : en gabarit Jinja, « actualites.items »
    # résout la MÉTHODE items() du dictionnaire, pas la clé — l'affichage
    # échouait sur « builtin_function_or_method is not iterable ».
    return {"verifie_le": VERIFIE_LE, "faits": ACTUALITES,
            "echeances": ECHEANCES}


# ── Bloc-notes personnel ────────────────────────────────────────────────────
# Conservé dans la table `meta` du dossier : il suit donc les sauvegardes,
# les restaurations et les changements de dossier, sans schéma supplémentaire.
CLE_NOTES = "notes_personnelles"


def lire_notes(conn) -> str:
    r = conn.execute("SELECT valeur FROM meta WHERE cle=?",
                     (CLE_NOTES,)).fetchone()
    return (r[0] if r else "") or ""


def ecrire_notes(conn, texte: str) -> None:
    conn.execute(
        "INSERT INTO meta (cle, valeur) VALUES (?,?) "
        "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
        (CLE_NOTES, (texte or "").strip()))
    conn.commit()


def oublis_frequents() -> list[dict]:
    """Checklist statique, groupée par moment de la vie du dossier."""
    groupes: dict[str, list[dict]] = {}
    for o in OUBLIS_FREQUENTS:
        groupes.setdefault(o["moment"], []).append(o)
    return [{"moment": m, "points": pts} for m, pts in groupes.items()]


def _ca(conn: sqlite3.Connection, annee: int) -> float:
    return conn.execute(
        "SELECT COALESCE(SUM(l.credit-l.debit),0) FROM ligne l "
        "JOIN ecriture e ON e.id=l.ecriture_id "
        "JOIN compte c ON c.numero=l.compte_num "
        "WHERE e.exercice_annee=? AND c.classe=7", (annee,)).fetchone()[0]


def rappels(conn: sqlite3.Connection, aujourd_hui: date | None = None,
            db_path: str | None = None) -> list[dict]:
    auj = aujourd_hui or date.today()
    N = auj.year
    out: list[dict] = []

    def add(niveau, titre, detail):
        out.append({"niveau": niveau, "titre": titre, "detail": detail})

    import operations as _ops
    _ops.assurer_colonne_annulee(conn)
    exercices = dict(conn.execute("SELECT annee, statut FROM exercice"))

    # ── Cycle déclaratif de l'exercice précédent ─────────────────────────
    prec = N - 1
    if exercices.get(prec) == "ouvert":
        if auj.month >= 5:
            add("important", f"Clôturer l'exercice {prec}",
                f"L'exercice {prec} est toujours ouvert alors que la période "
                "déclarative est engagée (télétransmission de la liasse "
                "généralement mi-mai). Passez les dernières écritures, lancez "
                "les contrôles puis la clôture — sans elle, pas de liasse "
                "définitive à déclarer.")
        elif auj.month >= 2:
            add("a_prevoir", f"Préparer la clôture de l'exercice {prec}",
                "Rassemblez les dernières pièces (relevés de décembre, "
                "quittances, factures) et saisissez le fonds travaux ALUR "
                "de l'année le cas échéant, avant de clôturer.")
    if exercices.get(prec) == "clos" and 2 <= auj.month <= 6:
        # Les dépôts notés dans la page Liasse cochent l'étape : un rappel
        # « important » qui persiste après le dépôt apprend à l'ignorer.
        import depots
        faits = depots.initiales(conn, prec)
        if len(faits) == len(depots.TYPES):
            add("fait", f"Résultats {prec} déclarés ✓",
                f"Liasse déposée le {faits['liasse_2031']}, 2042-C-PRO "
                f"déposée le {faits['2042_c_pro']}. Conservez les accusés "
                "de réception avec les pièces de l'exercice.")
        else:
            add("important", f"Déclarer les résultats {prec}",
                "La clôture ne déclare RIEN : télétransmettez la liasse "
                f"(2031 + 2033) au titre de {prec} — via votre "
                "expert-comptable/EDI ou votre espace impots.gouv.fr — "
                "généralement pour mi-mai, puis reportez le résultat sur la "
                "2042C-PRO de votre déclaration de revenus (aide dédiée dans "
                "l'onglet Liasse). Vérifiez les dates exactes de l'année sur "
                "impots.gouv.fr."
                + "".join(f" Déjà fait : {depots.TYPES[t]}, déposée le {d}."
                          for t, d in sorted(faits.items())))

    # ── Échéances calendaires ────────────────────────────────────────────
    if auj.month in (10, 11):
        add("a_prevoir", "Taxe foncière puis CFE",
            "La taxe foncière se paie généralement mi-octobre, l'avis de "
            "CFE arrive en novembre sur votre espace professionnel "
            "impots.gouv.fr (aucun avis papier n'est envoyé) pour un "
            "paiement au 15 décembre. Pensez à saisir ces paiements ici "
            "(gabarits Taxe foncière et CFE).")
    if auj.month == 12:
        add("important", "Payer la CFE avant le 15 décembre",
            "Le paiement se fait en ligne sur votre espace professionnel "
            "impots.gouv.fr. Saisissez ensuite l'opération (gabarit CFE — "
            "exclue à juste titre du plafond 39 C par le logiciel).")

    # ── Événements : biens ───────────────────────────────────────────────
    for bid, lib, acq in conn.execute(
            "SELECT id, libelle, date_acquisition FROM bien "
            "WHERE date_acquisition IS NOT NULL"):
        try:
            annee_acq = int(str(acq)[:4])
        except (ValueError, TypeError):
            continue
        if annee_acq == N:
            add("important", f"Formalités pour « {lib} » (acquis en {N})",
                "Un nouveau bien mis en location meublée doit être déclaré "
                "dans les 15 jours du début d'activité via le guichet unique "
                "de l'INPI (début ou extension d'activité — l'équivalent de "
                "l'ancien P0i/P2P2i) ; déposez aussi la déclaration initiale "
                "de CFE (1447-C) avant le 31 décembre. Si ce bien devient "
                "celui qui rapporte le plus, l'adresse d'activité (page "
                "Immobilisations) doit être mise à jour en conséquence.")

    # ── Événements : cession d'un bien dans l'année ──────────────────────
    try:
        cessions = conn.execute(
            "SELECT libelle, date_cession FROM bien WHERE date_cession IS NOT "
            "NULL AND date_cession >= ? AND date_cession < ?",
            (f"{N}-01-01", f"{N + 1}-01-01")).fetchall()
    except sqlite3.OperationalError:
        cessions = []
    for lib, dc in cessions:
        add("important", f"Cession de « {lib} » ({dc}) — démarches",
            "La plus-value relève du régime des PARTICULIERS : calculée et "
            "déclarée par le notaire (2048-IMM) lors de la vente — depuis "
            "2025, les amortissements déduits sont réintégrés dans son "
            "calcul. Le stock 39 C attaché au bien est définitivement perdu "
            "(ligne G' de l'état SUIV39C, suivi automatiquement). Si c'était "
            "votre DERNIER bien loué : déclarez la cessation d'activité au "
            "guichet INPI dans les 30 jours et déposez la liasse de "
            "cessation dans les 60 jours ; sinon, mettez à jour l'adresse "
            "d'activité si nécessaire.")

    # ── Seuils LMP ───────────────────────────────────────────────────────
    for annee, statut in sorted(exercices.items()):
        if statut != "ouvert" or annee > N:
            continue
        ca = _ca(conn, annee)
        # Le seuil est une RÈGLE VERSIONNÉE, comme pour le contrôle métier :
        # la constante écrite ici ignorait la valeur enregistrée, et le
        # rappel restait muet sur 20 000 € de recettes face à un seuil
        # configuré à 15 000 €. Les deux consommateurs de la même règle
        # doivent répondre la même chose.
        try:
            import parametres as _param
            seuil_lmp = float(_param.valeur(conn, "seuil_lmp_recettes",
                                            annee, defaut=23000.0))
        except Exception:                            # noqa: BLE001
            seuil_lmp = 23000.0
        if ca > seuil_lmp:
            add("important", f"CA {annee} : {ca:,.0f} € — seuil LMP franchi ?",
                f"Au-delà de {seuil_lmp:,.0f} € de recettes, le statut LMP "
                "s'applique "
                "si elles excèdent AUSSI les autres revenus d'activité du "
                "foyer — avec affiliation sociale (SSI) possible dès "
                "23 000 € selon le mode de location. Vérifiez votre "
                "situation (le logiciel est conçu pour le LMNP).")

    # ── Fonds travaux ALUR jamais saisi (copropriété probable) ───────────
    annee_ouverte = max((a for a, s in exercices.items() if s == "ouvert"),
                        default=None)
    if annee_ouverte:
        copro = conn.execute(
            "SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 "
            "AND exercice_annee=? AND type='charge_copro'", (annee_ouverte,)).fetchone()[0]
        alur = conn.execute(
            "SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 "
            "AND exercice_annee=? AND type='fonds_travaux_alur'", (annee_ouverte,)).fetchone()[0]
        if copro and not alur:
            add("a_prevoir", "Fonds travaux ALUR non saisi cette année",
                "Des charges de copropriété sont saisies mais aucun fonds "
                "travaux ALUR : si vos appels de fonds en contiennent un "
                "(relevé du syndic), saisissez-le via son gabarit dédié — "
                "il n'est pas déductible et le logiciel le réintègre "
                "automatiquement à la clôture.")

    # ── Veille fiscale ───────────────────────────────────────────────────
    try:
        import veille_fiscale
        if veille_fiscale.veille_a_refaire(conn, auj):
            derniere = veille_fiscale.derniere_veille(conn)
            add("a_prevoir", "Veille fiscale à faire",
                ("Aucune veille n'a encore été déclarée." if not derniere
                 else f"Dernière veille : {derniere}.")
                + " Une loi de finances par an peut modifier un seuil, la "
                "durée de report des déficits ou le traitement d'une "
                "cession — ce logiciel applique les règles telles qu'elles y "
                "sont enregistrées. Le menu « Veille fiscale » fournit le "
                "corpus des textes et une question type à poser à une IA.")
    except Exception as exc:               # noqa: BLE001
        # Le rappel était simplement abandonné : une consultation de veille
        # en panne produisait donc la même sortie qu'une veille à jour. Ne
        # pas pouvoir vérifier n'est pas avoir vérifié — on le dit.
        add("a_prevoir", "Veille fiscale : état inconnu",
            f"La date de dernière veille n'a pas pu être lue ({exc}). Le "
            "logiciel ne peut donc pas dire si les règles enregistrées ont "
            "été revues récemment — vérifiez-le depuis le menu « Veille "
            "fiscale ».")

    # ── Sauvegardes ──────────────────────────────────────────────────────
    if db_path:
        dossier = os.path.join(os.path.dirname(os.path.abspath(db_path)),
                               "sauvegardes")
        recentes = []
        if os.path.isdir(dossier):
            seuil = auj.toordinal() - 35
            recentes = [f for f in os.listdir(dossier)
                        if os.path.isfile(os.path.join(dossier, f)) and
                        date.fromtimestamp(os.path.getmtime(
                            os.path.join(dossier, f))).toordinal() >= seuil]
        if not recentes:
            add("info", "Aucune sauvegarde récente détectée",
                "Les sauvegardes automatiques se font au lancement du "
                "logiciel (une par jour) : lancez-le régulièrement, et "
                "copiez de temps en temps le dossier « sauvegardes » sur "
                "un support externe. Une restauration se teste AVANT d'en "
                "avoir besoin.")

    # ── Oublis récurrents DÉTECTABLES dans le dossier ──────────────────────
    # La checklist ci-dessous est générique ; ces deux rappels-ci, eux,
    # regardent réellement ce qui a été saisi. C'est toute la différence
    # entre un mémo et une alerte utile.
    biens = conn.execute("SELECT COUNT(*) FROM bien").fetchone()[0]
    if biens:
        frais = conn.execute(
            "SELECT COUNT(*) FROM composant WHERE libelle LIKE '%notaire%' "
            "OR libelle LIKE '%acquisition%' OR libelle LIKE '%agence%' "
            "OR categorie LIKE '%frais%'").fetchone()[0]
        if not frais:
            add("info", "Frais d'acquisition : rien d'enregistré",
                "Aucun composant ne correspond à des frais de notaire, "
                "droits de mutation ou commission d'agence. C'est l'oubli "
                "le plus coûteux de la première année : selon l'option "
                "retenue, ces frais se déduisent l'année de l'acquisition "
                "ou s'amortissent avec le bien. S'ils ont déjà été traités "
                "ailleurs, ignorez ce rappel.")
        mobilier = conn.execute(
            "SELECT COUNT(*) FROM composant WHERE compte_immo LIKE '2184%'"
        ).fetchone()[0]
        if not mobilier:
            add("info", "Aucun mobilier immobilisé",
                "La location meublée suppose un mobilier suffisant, qui "
                "s'amortit sur une durée plus courte que le bâti. Aucun "
                "composant de mobilier ou d'électroménager n'est "
                "enregistré : soit il a été passé en charge (à vérifier), "
                "soit il reste à saisir dans la page Immobilisations.")

    ordre = {"important": 0, "a_prevoir": 1, "info": 2, "fait": 3}
    out.sort(key=lambda r: ordre[r["niveau"]])
    return out
