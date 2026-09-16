# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Veille fiscale — le logiciel ne se met PAS à jour tout seul.

Les règles sont versionnées (parametres.py) : le moteur applique la valeur
en vigueur pour l'exercice traité. Mais personne n'avertit le logiciel
qu'une loi de finances a changé un seuil — c'est à l'exploitant de le
faire, et ce module l'y aide à l'ouverture de chaque exercice :

  1. il recense le CORPUS des textes qui régissent le LMNP, chacun rattaché
     au module du logiciel qu'il gouverne et, le cas échéant, à la règle
     versionnée correspondante ;
  2. il fabrique un PROMPT prêt à coller dans n'importe quelle IA
     conversationnelle disposant d'une recherche web, pour demander ce qui
     a changé depuis la dernière vérification ;
  3. il mémorise la date de la dernière veille (table meta) pour la
     rappeler quand elle vieillit.

⚠️ Ce module ne donne AUCUN conseil fiscal : il aide à poser les bonnes
questions. Toute évolution constatée doit être vérifiée sur les sources
officielles (Légifrance, BOFiP, impots.gouv.fr) et, en cas de doute,
auprès d'un expert-comptable. Une réponse d'IA n'est pas une source.
"""
from __future__ import annotations

import datetime
import sqlite3

# Date à laquelle ce corpus a été revu. Sert à dater le prompt par défaut
# et à signaler que le corpus lui-même mériterait une relecture.
CORPUS_REVU_LE = "2026-07-20"

# (référence, intitulé, ce que le texte gouverne DANS CE LOGICIEL, règle liée)
CORPUS = [
    # ── Qualification et champ du régime ────────────────────────────────
    ("Art. 155, IV du CGI",
     "Définition du loueur en meublé professionnel (LMP)",
     "Frontière LMNP / LMP : recettes supérieures à 23 000 € ET supérieures "
     "aux autres revenus professionnels du foyer. Détermine si ce logiciel "
     "est adapté à votre situation.",
     "seuil_lmp_recettes"),
    ("Art. 156, I-1° ter du CGI",
     "Déficits de location meublée non professionnelle",
     "Les déficits ne s'imputent QUE sur des bénéfices de location meublée "
     "non professionnelle, pendant 10 ans. Moteur des déficits (FIFO par "
     "millésime, expiration).",
     "duree_report_deficit_lmnp"),
    ("Art. 50-0 du CGI",
     "Régime micro-BIC",
     "Seuils et abattements du forfait. Ce logiciel tient une comptabilité "
     "au RÉEL : le micro n'est rappelé qu'à titre de comparaison.",
     "seuil_micro_bic_meuble"),
    ("BOI-BIC-CHAMP-40-10 et BOI-BIC-CHAMP-40-20",
     "Doctrine administrative — champ et régime de la location meublée",
     "Commentaires de l'administration sur la qualification LMP/LMNP et le "
     "régime applicable.", None),

    # ── Amortissements (cœur du moteur) ─────────────────────────────────
    ("Art. 39 C, II-2 du CGI",
     "Limitation de la déduction des amortissements",
     "LE calcul central du logiciel : l'amortissement déductible est plafonné "
     "au loyer acquis diminué des autres charges afférentes au bien ; "
     "l'excédent est reporté sans limite de durée (état de suivi SUIV39C).",
     None),
    ("BOI-BIC-AMT-20-40-10-20 et -10-30",
     "Doctrine — calcul de l'amortissement déductible et suivi des "
     "amortissements excédentaires",
     "Modalités de calcul du plafond et obligation de suivi annuel du stock "
     "reportable, y compris logement par logement en cas de pluralité de "
     "biens.", None),
    ("Art. 39-1 du CGI et règlement ANC n° 2014-03 (PCG)",
     "Charges déductibles ; amortissement par composants",
     "Décomposition des biens (gros œuvre, étanchéité, agencements, "
     "mobilier…), durées d'usage, terrain non amortissable.",
     "seuil_immobilisation"),

    # ── Sortie du bien ──────────────────────────────────────────────────
    ("Art. 150 U et suivants du CGI",
     "Plus-values immobilières des particuliers",
     "Régime applicable à la cession d'un bien LMNP : la plus-value est "
     "calculée et déclarée par le NOTAIRE (2048-IMM). Le logiciel neutralise "
     "donc la cession dans le résultat BIC.", None),
    ("Art. 150 VB du CGI, modifié par la loi de finances pour 2025 "
     "(loi n° 2025-127 du 14 février 2025)",
     "Réintégration des amortissements dans la plus-value",
     "Depuis 2025, le prix d'acquisition retenu pour la plus-value est "
     "diminué des amortissements déduits. Le suivi des amortissements tenu "
     "par le logiciel devient une pièce à fournir au notaire.", None),

    # ── Obligations déclaratives et comptables ──────────────────────────
    ("Art. 53 A et 302 septies A bis du CGI",
     "Déclaration de résultats (2031-SD) et régime réel simplifié "
     "(2033-A à 2033-G)",
     "Contenu et structure de la liasse produite par le logiciel.", None),
    ("Art. L. 47 A-I du LPF et arrêté A-47 A-1 du LPF",
     "Fichier des écritures comptables (FEC)",
     "Format exigé lors d'un contrôle : 18 colonnes, dates AAAAMMJJ, "
     "séquence des écritures. Gouverne l'export ET le validateur.", None),
    ("Art. 286 quater du CGI et art. L. 102 B du LPF",
     "Conservation des pièces et documents comptables",
     "Durée de conservation des justificatifs, du FEC et des archives "
     "produites par le logiciel.", None),

    ("BOI-BIC-CHG-40-20",
     "Fonds de travaux ALUR : charge non déductible",
     "La contribution au fonds de travaux est CAPITALISÉE : elle est "
     "réintégrée au résultat fiscal à la clôture. Le logiciel le fait "
     "automatiquement, et cette réintégration majore aussi le plafond "
     "d'amortissement déductible de l'article 39 C — une règle qui change "
     "donc réellement le résultat, et qui doit être revue comme les "
     "autres.", "retraitement_alur_auto"),

    # ── Fiscalité annexe ────────────────────────────────────────────────
    ("Art. 261 D, 4° du CGI",
     "Exonération de TVA de la location meublée",
     "Pourquoi le logiciel raisonne en TTC et ne gère pas de TVA "
     "(sauf para-hôtellerie, hors périmètre).", None),
    ("Art. 1447 et suivants du CGI",
     "Cotisation foncière des entreprises (CFE)",
     "Due par le loueur en meublé ; déclaration initiale 1447-C. Rappelée "
     "par le pense-bête, exclue du plafond 39 C par le moteur.", None),
    ("Loi n° 2024-1039 du 19 novembre 2024 (dite « loi Le Meur »)",
     "Meublés de tourisme",
     "Seuils et abattements du micro-BIC pour les meublés de tourisme, "
     "classement, obligations locales. Concerne la location saisonnière.",
     None),
]

# Points d'attention connus au moment de la revue du corpus — à confirmer.
ACTUALITE_CONNUE = [
    "Loi de finances pour 2025 : réintégration des amortissements dans le "
    "calcul de la plus-value de cession (art. 150 VB du CGI).",
    "Loi de finances pour 2026 (promulguée le 19 février 2026) : "
    "l'amortissement reste déductible sans plafonnement ; hausse annoncée "
    "des prélèvements sociaux sur les revenus BIC (17,2 % → 18,6 %) ; "
    "création d'un statut de bailleur privé ; règles particulières pour les "
    "non-résidents. À VÉRIFIER et à préciser lors de votre veille.",
    "Loi Le Meur (2024) : abattements et seuils du micro-BIC des meublés de "
    "tourisme non classés.",
]


def _table_meta(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS meta ("
                 "cle TEXT PRIMARY KEY, valeur TEXT NOT NULL)")


def derniere_veille(conn: sqlite3.Connection) -> str | None:
    """Date (AAAA-MM-JJ) de la dernière veille déclarée, ou None."""
    _table_meta(conn)
    row = conn.execute("SELECT valeur FROM meta WHERE cle='derniere_veille'"
                       ).fetchone()
    return row[0] if row else None


def enregistrer_veille(conn: sqlite3.Connection,
                       jour: str | None = None) -> str:
    """Mémorise qu'une veille vient d'être faite."""
    _table_meta(conn)
    jour = jour or datetime.date.today().isoformat()
    # Une veille se constate, elle ne se planifie pas : une date FUTURE
    # enregistrée par erreur — 2099 dans le cas reproduit — éteignait le
    # rappel pour des décennies, sans que rien ne signale l'incohérence.
    try:
        saisie = datetime.date.fromisoformat(jour)
    except ValueError:
        raise ValueError(f"Date de veille illisible : {jour!r} "
                         "(format attendu AAAA-MM-JJ).") from None
    if saisie > datetime.date.today():
        raise ValueError(
            f"Date de veille dans le futur : {jour}. Une veille s'enregistre "
            "le jour où elle est faite — une date future éteindrait le "
            "rappel jusque-là.")
    conn.execute("INSERT INTO meta (cle, valeur) VALUES ('derniere_veille', ?) "
                 "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
                 (jour,))
    conn.commit()
    return jour


def veille_a_refaire(conn: sqlite3.Connection,
                     aujourd_hui: datetime.date | None = None) -> bool:
    """Vrai si aucune veille n'a jamais été faite, ou si la dernière remonte
    à plus de 11 mois (une loi de finances par an, publiée fin décembre)."""
    auj = aujourd_hui or datetime.date.today()
    derniere = derniere_veille(conn)
    if not derniere:
        return True
    try:
        d = datetime.date.fromisoformat(derniere)
    except ValueError:
        return True
    # Une date postérieure à aujourd'hui ne prouve aucune veille faite :
    # l'écart en jours est alors négatif, et le test « plus de 334 jours »
    # concluait tranquillement que tout allait bien.
    if d > auj:
        return True
    return (auj - d).days > 334


def prompt_veille(annee_exercice: int, depuis: str | None = None) -> str:
    """
    Prompt prêt à coller dans une IA conversationnelle disposant d'une
    recherche web. Il est volontairement exigeant sur les SOURCES et sur la
    distinction adopté / en discussion : c'est là que les réponses d'IA
    dérapent le plus souvent en matière fiscale.
    """
    depuis = depuis or CORPUS_REVU_LE
    textes = "\n".join(f"- {ref} — {intitule}"
                       for ref, intitule, _effet, _regle in CORPUS)
    return f"""Tu es assisté d'une recherche web. Nous sommes le \
{datetime.date.today().isoformat()}.

CONTEXTE
Je tiens moi-même la comptabilité d'une activité de location meublée non
professionnelle (LMNP) au régime réel simplifié, en France. Je prépare
l'exercice {annee_exercice}. Je dois savoir ce qui a changé dans la
réglementation depuis le {depuis}.

TEXTES QUI RÉGISSENT MON RÉGIME (corpus de référence)
{textes}

CE QUE JE TE DEMANDE
1. Pour CHACUN de ces textes, indique s'il a été modifié, complété ou
   commenté depuis le {depuis} (loi de finances, loi de financement de la
   sécurité sociale, autre loi, décret, arrêté, mise à jour BOFiP,
   jurisprudence significative).
2. Signale aussi tout texte NOUVEAU qui concernerait la location meublée
   non professionnelle et qui ne figurerait pas dans ma liste.
3. Pour chaque évolution, précise :
   - la référence exacte (loi/décret/BOFiP + date + numéro d'article) ;
   - la date d'entrée en vigueur et les exercices concernés ;
   - en une phrase, ce qui change concrètement ;
   - l'impact sur : (a) le calcul des amortissements déductibles
     (art. 39 C), (b) le report et l'expiration des déficits, (c) les
     seuils (LMP, micro-BIC, immobilisation), (d) la plus-value de
     cession, (e) les obligations déclaratives (liasse, FEC).
4. Dis-moi où en est la réforme de la FACTURATION ÉLECTRONIQUE pour les
   loueurs meublés : calendrier effectif (obligation de réception, puis
   d'émission), report éventuel, et ce qui change pour un bailleur dont
   les loyers sont exonérés de TVA mais qui reste assujetti.
5. Dis-moi si les MODÈLES DÉCLARATIFS eux-mêmes ont changé : millésime en
   vigueur des formulaires 2031-SD, 2033-A à 2033-G et 2042-C-PRO,
   création ou suppression de cases, renumérotation, nouvelles rubriques
   obligatoires. Un logiciel qui produit une liasse sur un modèle périmé
   sort des chiffres justes dans des cases fausses : je dois le savoir
   même quand la règle de fond, elle, n'a pas bougé.
6. Distingue CLAIREMENT ce qui est DÉFINITIVEMENT ADOPTÉ et en vigueur de
   ce qui n'est qu'un projet, un amendement déposé ou une proposition en
   discussion. Ne présente jamais un projet comme du droit positif.
7. Termine par une liste des VALEURS CHIFFRÉES en vigueur pour
   {annee_exercice} : seuil LMP, seuils et abattements micro-BIC, durée de
   report des déficits, seuil d'immobilisation, taux des prélèvements
   sociaux sur les BIC.

EXIGENCES DE FIABILITÉ
- Cite tes sources avec des liens vers Légifrance, le BOFiP
  (bofip.impots.gouv.fr) ou impots.gouv.fr ; les articles de blogs ne font
  pas foi.
- Si tu n'es pas certain d'un point, dis-le explicitement plutôt que de
  formuler une réponse plausible.
- N'invente aucun numéro d'article ni aucune date.
- Termine par la liste des points qui, selon toi, méritent l'avis d'un
  expert-comptable."""


def resume(conn: sqlite3.Connection, annee: int) -> dict:
    """Tout ce dont la page de veille a besoin."""
    return {"corpus": CORPUS, "actualite": ACTUALITE_CONNUE,
            "corpus_revu_le": CORPUS_REVU_LE,
            "derniere_veille": derniere_veille(conn),
            "a_refaire": veille_a_refaire(conn),
            "prompt": prompt_veille(annee, derniere_veille(conn))}
