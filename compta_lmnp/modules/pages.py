# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Gabarits HTML de l'interface web — la PRÉSENTATION, rien qu'elle.

Extraits d'app.py, qui mélangeait 1 300 lignes de HTML à la logique des
routes (52 % du fichier). Séparation stricte :
  - ce module : chaînes Jinja (gabarits de pages) et feuille de style —
    AUCUN import applicatif, aucune logique, rien d'exécutable ;
  - app.py : les routes, qui rendent ces gabarits avec leurs données.

Un gabarit se repère par sa page : PAGE_SAISIE, PAGE_IMMO, PAGE_CLOTURE,
PAGE_EX_NOUVEAU, PAGE_LIASSE, PAGE_REGLEMENTATION, PAGE_SANDBOX,
PAGE_ARCHIVES, PAGE_SAUVEGARDES_SECTION, PAGE_DOSSIERS, PAGE_PENSE_BETE,
PAGE_VEILLE — plus CSS (style global inline, distribution mono-fichier
oblige : pas de dossier static/).

L'échappement des données utilisateur est assuré par Jinja (autoescape) au
rendu, dans app.py — ces chaînes n'insèrent jamais rien elles-mêmes.
"""


CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; font-size: 14px;
       background: #f0f2f5; color: #1a1a1a; }

/* ── Header / nav ── */
/* Bleu marine ASM, avec le jaune de l'onglet actif : le bandeau porte les
   couleurs du club, et le contraste jaune sur marine est plus franc que
   le blanc sur bleu moyen d'avant. */
/* Bandeau VERROUILLÉ en haut de la fenêtre. Les pages longues — grand
   livre, liasse, contrôles — faisaient disparaître la navigation et le
   sélecteur d'exercice : changer d'onglet demandait de remonter. `sticky`
   plutôt que `fixed` : l'élément garde sa place dans le flux, donc aucune
   marge de compensation à régler sur `main`, et rien ne se glisse dessous
   au chargement.

   z-index 30 : au-dessus du contenu, mais SOUS les infobulles (40) et leur
   flèche (41) — une infobulle déclenchée dans la première ligne d'un
   tableau doit passer par-dessus le bandeau, pas dessous. */
header { background: #002b5c; color: #fff;
         display: flex; align-items: center; gap: 0; flex-wrap: wrap;
         position: sticky; top: 0; z-index: 30;
         box-shadow: 0 2px 6px rgba(0,0,0,.18); }
.brand { font-size: 16px; font-weight: 700; padding: 0 24px;
         letter-spacing: .4px; white-space: nowrap; }
nav { display: flex; flex: 1; }
nav a { display: block; padding: 14px 20px; color: rgba(255,255,255,.75);
        text-decoration: none; font-size: 13px; font-weight: 500;
        border-bottom: 3px solid transparent; transition: color .15s, border-color .15s; }
nav a:hover { color: #fff; }
/* Onglet courant : jaune sur fond assombri. L'ancien réglage — blanc sur
   bleu, souligné de bleu clair — ne se distinguait pas des autres onglets
   (retour d'usage). Le jaune tranche franchement sur le bleu du bandeau. */
nav a.active { color: #ffd54f; font-weight: 700;
        background: rgba(0,0,0,.22); border-bottom-color: #ffd54f;
        border-bottom-width: 3px; }
.header-right { margin-left: auto; padding: 0 16px;
                display: flex; align-items: center; gap: 8px; }
.header-right label { color: rgba(255,255,255,.6); font-size: 12px; }
.header-right select { background: #2d5080; color: #fff;
                       border: 1px solid #4a7ab5; border-radius: 4px;
                       padding: 4px 8px; font-size: 13px; cursor: pointer; }

/* ── Layout ── */
main { max-width: 960px; margin: 24px auto; padding: 0 16px; }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }

/* ── Cards ── */
/* `overflow: hidden` a été RETIRÉ d'ici. Il servait à ce que le bandeau
   coloré respecte les coins arrondis — mais il rognait aussi toute
   infobulle dépassant de la carte, c'est-à-dire la plupart de celles
   posées près d'un bord. Les coins sont désormais arrondis sur le bandeau
   lui-même, ce qui règle l'arrondi sans rien rogner. */
.card { background: #fff; border-radius: 8px;
        box-shadow: 0 1px 4px rgba(0,0,0,.12); margin-bottom: 24px; }

/* Bleu marine, avec le jaune de l'onglet actif : le bandeau porte les
   couleurs du club, et le contraste jaune sur marine est plus franc que
   le blanc sur bleu moyen d'avant.

   ATTENTION — ce commentaire était collé AU MILIEU du sélecteur, entre
   « .card- » et « header », ce qui le coupait en deux : `.card-header`
   ne recevait donc JAMAIS son `color: #fff`. Seules les variantes de
   couleur s'appliquaient, en posant un fond sans toucher au texte, qui
   héritait du noir du corps de page — titres noirs sur vert, ambre ou
   rouge foncé, illisibles. Un commentaire ne se place pas dans un
   sélecteur. */
.card-header { background: #002b5c; color: #fff; padding: 10px 20px;
               font-weight: 600; font-size: 12px;
               text-transform: uppercase; letter-spacing: .8px;
               border-radius: 8px 8px 0 0; }
/* Les variantes ne changent QUE le fond : la couleur du texte vient de la
   règle de base, et doit y rester — la redéclarer ici la ferait diverger. */
.card-header.green  { background: #1a6b3a; }
.card-header.amber  { background: #7a5200; }
.card-header.red    { background: #7a1c1c; }
.card-body { padding: 20px; }

/* ── Flash ── */
.flash { border-radius: 6px; padding: 10px 16px; margin-bottom: 20px; font-size: 13px; }
.flash-ok  { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
.flash-err { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
.flash-warn { background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }

/* ── Formulaires ── */
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.form-grid .full { grid-column: 1 / -1; }
.form-grid .w1   { grid-column: span 1; }
label.field { display: block; font-size: 12px; font-weight: 600;
              color: #555; margin-bottom: 4px; }
label.field .opt { font-weight: 400; color: #999; }
.rappel { border-left: 4px solid #ccc; border-radius: 6px; background: #fafbfc;
          padding: 12px 14px; margin: 10px 0; }
.rappel-important { border-left-color: #c0392b; background: #fdf3f2; }
.rappel-a_prevoir { border-left-color: #d68910; background: #fdf9f0; }
.rappel-info      { border-left-color: #2471a3; background: #f2f7fb; }
.rappel-fait      { border-left-color: #1a6b3a; background: #f4faf4; }
.rappel-titre  { font-weight: 600; margin-bottom: 4px; }
.rappel-detail { font-size: 13.5px; color: #444; line-height: 1.5; }

/* Infobulle d'aide au survol : petite pastille « ? » après le libellé, qui
   dévoile un exemple de format. Pur CSS, aucun JavaScript. */
.aide { position: relative; display: inline-flex; align-items: center;
        justify-content: center; width: 15px; height: 15px; margin-left: 5px;
        border-radius: 50%; background: #c7d0dd; color: #fff; font-size: 10px;
        font-weight: 700; cursor: help; vertical-align: middle; }
.aide::after {
        content: attr(data-aide); position: absolute; left: 50%; bottom: 150%;
        transform: translateX(-50%); min-width: 180px; max-width: 280px;
        background: #1e2b3d; color: #f3f5f8; font-size: 11.5px; font-weight: 400;
        line-height: 1.45; text-align: left; padding: 8px 10px; border-radius: 6px;
        box-shadow: 0 4px 14px rgba(0,0,0,.22); opacity: 0; visibility: hidden;
        transition: opacity .12s ease; z-index: 40; white-space: normal; }
.aide::before {
        content: ""; position: absolute; left: 50%; bottom: 150%;
        transform: translateX(-50%) translateY(6px); border: 5px solid transparent;
        border-top-color: #1e2b3d; opacity: 0; visibility: hidden;
        transition: opacity .12s ease; z-index: 41; }
.aide:hover::after, .aide:hover::before { opacity: 1; visibility: visible; }
/* Bords de fenêtre : l'infobulle est centrée sur sa pastille, donc coupée
   dès que celle-ci est à moins d'une demi-largeur du bord. Ces deux
   variantes l'ancrent du bon côté ; la classe est posée au survol par le
   script de mise en page. Sans JavaScript, rien ne les active et
   l'infobulle reste centrée — elle dépasse, elle ne disparaît pas. */
.aide.aide-gauche::after  { left: 0; transform: none; }
.aide.aide-droite::after  { left: auto; right: 0; transform: none; }
.flash-err { white-space: pre-line; }   /* messages multi-lignes lisibles */

/* ── L'assistante ─────────────────────────────────────────────────────
   Décorative et NON bloquante : les infobulles CSS fonctionnent sans
   elle (sans JavaScript, ou si elle est masquée). Elle ne s'invite
   jamais — elle paraît sur demande d'aide, ou pour commenter le message
   qui vient de s'afficher, puis s'efface. */
/* Les confirmations passent par data-confirmer plutôt que par un
   gestionnaire « onclick » écrit à la main. Deux d'entre elles — dont
   celle de la RESTAURATION, la plus destructrice — contenaient un saut de
   ligne réel et une apostrophe fermante : le gestionnaire ne compilait
   pas, valait donc null, et l'action s'exécutait SANS aucune boîte de
   dialogue. Les deux qui fonctionnaient étaient précisément celles
   écrites sans apostrophe. Avec un attribut, c'est Jinja qui échappe. */
#assistant { position: fixed; right: 18px; bottom: 18px; z-index: 60;
        display: none; align-items: flex-end; gap: 10px; pointer-events: none; }
#assistant.actif { display: flex; }
/* Pixel art : image-rendering: pixelated interdit au navigateur de lisser
   les bords à l'agrandissement — sans quoi le sprite devient flou et perd
   tout l'intérêt de la technique. */
#assistant .perso { width: 112px; height: 98px; flex: none;
        image-rendering: pixelated; image-rendering: crisp-edges;
        animation: flotte 3.4s steps(2, end) infinite; }
#assistant.salue .perso { animation: salue .5s steps(2, end) 3; }

/* — les trois états — */
#assistant .sur-info, #assistant .sur-valide,
#assistant .sur-anomalie { display: none; }
#assistant.info     .sur-info     { display: block; }
#assistant.valide   .sur-valide   { display: block; }
#assistant.anomalie .sur-anomalie { display: block;
        animation: alerte 1.1s steps(2, end) infinite; }
#assistant.anomalie .bulle { background: #5b1a13; }
#assistant.anomalie .bulle::after { border-left-color: #5b1a13; }
#assistant.valide .bulle { background: #123a25; }
#assistant.valide .bulle::after { border-left-color: #123a25; }

#assistant .bulle { pointer-events: auto; position: relative; max-width: 300px;
        background: #1e2b3d; color: #f3f5f8; font-size: 12px; line-height: 1.5;
        padding: 11px 30px 11px 13px; border-radius: 10px;
        box-shadow: 0 6px 20px rgba(0,0,0,.25); opacity: 0;
        transform: translateY(6px);
        transition: opacity .18s ease, transform .18s ease, background .2s ease; }
#assistant.parle .bulle { opacity: 1; transform: translateY(0); }
#assistant .bulle::after { content: ""; position: absolute; right: -6px;
        bottom: 16px; border: 6px solid transparent; border-left-color: #1e2b3d; }
#assistant .fermer { position: absolute; top: 4px; right: 6px; border: 0;
        background: none; color: #9fb0c7; font-size: 15px; line-height: 1;
        cursor: pointer; padding: 2px 4px; }
#assistant .fermer:hover { color: #fff; }
/* Animations par PALIERS (steps) et non en interpolation continue : un
   sprite qui glisse en sous-pixels trahit le pixel art. On le fait sauter
   d'un pixel entier, comme dans un jeu. */
@keyframes flotte { 0%,100% { transform: translateY(0); }
                    50% { transform: translateY(-4px); } }
@keyframes salue  { 0%,100% { transform: translateX(0); }
                    50% { transform: translateX(-3px); } }
@keyframes alerte { 0%,100% { opacity: 1; } 50% { opacity: .62; } }
/* Accessibilité : plus aucun mouvement si le système demande le calme. */
@media (prefers-reduced-motion: reduce) {
  #assistant .perso, #assistant.anomalie .sur-anomalie { animation: none; }
  #assistant .bulle { transition: none; }
}
@media (max-width: 700px) { #assistant { display: none !important; } }
input, select, textarea {
  width: 100%; border: 1px solid #d0d5dd; border-radius: 5px;
  padding: 7px 10px; font-size: 13px; color: #1a1a1a;
  background: #fff; transition: border-color .15s; }
input:focus, select:focus, textarea:focus {
  outline: none; border-color: #1e3a5f;
  box-shadow: 0 0 0 3px rgba(30,58,95,.1); }
textarea { resize: vertical; min-height: 52px; }
.hint { font-size: 11px; color: #888; margin-top: 3px; }

/* ── Buttons ── */
.btn { display: inline-block; border: none; border-radius: 6px;
       padding: 9px 22px; font-size: 13px; font-weight: 600;
       cursor: pointer; text-decoration: none; transition: background .15s; }
.btn-primary { background: #1e3a5f; color: #fff; }
.btn-primary:hover { background: #2d5080; }
.btn-danger  { background: #7a1c1c; color: #fff; }
.btn-danger:hover  { background: #a02020; }
.btn-success { background: #1a6b3a; color: #fff; }
.btn-success:hover { background: #228a4a; }
.btn-sm { padding: 5px 12px; font-size: 12px; }
.mt { margin-top: 16px; }

/* ── Tableaux ── */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th { background: #f0f2f5; padding: 8px 10px; text-align: left;
           font-size: 11px; font-weight: 700; color: #555;
           text-transform: uppercase; letter-spacing: .5px;
           border-bottom: 2px solid #d0d5dd; }
tbody tr:hover { background: #f7f8fa; }
td { padding: 8px 10px; border-bottom: 1px solid #eaecef; vertical-align: top; }
td.right { text-align: right; font-variant-numeric: tabular-nums;
           font-weight: 600; white-space: nowrap; }
td.green { color: #155724; }
td.red   { color: #721c24; }
td.muted { color: #999; font-size: 11px; }
.empty { color: #999; font-style: italic; padding: 20px; text-align: center; }

/* ── Badges ── */
.badge { display: inline-block; font-size: 10px; font-weight: 700;
         border-radius: 3px; padding: 2px 6px; vertical-align: middle; }
.badge-produit { background: #d4edda; color: #155724; }
.badge-charge  { background: #fff3cd; color: #856404; }
.badge-ok      { background: #d4edda; color: #155724; }
.badge-clos    { background: #d0d5dd; color: #444; }
.badge-warn    { background: #fff3cd; color: #856404; }
.badge-err     { background: #f8d7da; color: #721c24; }

/* ── Séparateur de section ── */
h2.section { font-size: 13px; font-weight: 700; color: #555;
             text-transform: uppercase; letter-spacing: .6px;
             margin: 24px 0 12px; border-bottom: 1px solid #d0d5dd;
             padding-bottom: 6px; }

/* ── Résumé fiscal ── */
.kpi-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.kpi { flex: 1; min-width: 120px; background: #f7f8fa; border-radius: 6px;
       padding: 12px 16px; }
.kpi .kpi-label { font-size: 11px; color: #666; margin-bottom: 4px;
                  text-transform: uppercase; letter-spacing: .4px; }
.kpi .kpi-val   { font-size: 20px; font-weight: 700; }
.kpi .kpi-val.pos { color: #155724; }
.kpi .kpi-val.neg { color: #721c24; }
"""


ASSISTANT = """
<!-- ══════════════════════════════════════════════════════════════════════
     L'ASSISTANTE — un seul dessin, trois états.

     SVG EN LIGNE plutôt qu'une illustration : le logiciel se distribue en
     un dossier sans ressources externes, un dessin vectoriel reste net à
     toute taille, pèse quelques kilo-octets là où une image en pèse
     mille, et se recolorie par CSS — c'est ce qui permet trois états sans
     trois fichiers.

     ÉTATS (classe portée par #assistant) :
       .info      — elle explique ; tablette sombre, chiffres
       .valide    — sourire, pouce levé ; tablette verte, coche
       .anomalie  — sourcils froncés ; tablette rouge, triangle d'alerte
     ══════════════════════════════════════════════════════════════════ -->
<div id="assistant" class="info" aria-live="polite">
  <div class="bulle">
    <button class="fermer" type="button" title="Masquer l'assistante"
            aria-label="Masquer l'assistante">&times;</button>
    <span class="texte"></span>
  </div>
  <svg class="perso" viewBox="0 0 24 21" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges"
       role="img" aria-hidden="true">
    <g class="corps">
      <rect x="8" y="0" width="6" height="1" fill="#14121c"/>
      <rect x="6" y="1" width="2" height="1" fill="#14121c"/>
      <rect x="8" y="1" width="6" height="1" fill="#a8a6b8"/>
      <rect x="14" y="1" width="2" height="1" fill="#14121c"/>
      <rect x="4" y="2" width="2" height="1" fill="#14121c"/>
      <rect x="6" y="2" width="1" height="1" fill="#a8a6b8"/>
      <rect x="7" y="2" width="8" height="1" fill="#e8e6ef"/>
      <rect x="15" y="2" width="1" height="1" fill="#a8a6b8"/>
      <rect x="16" y="2" width="2" height="1" fill="#14121c"/>
      <rect x="2" y="3" width="2" height="1" fill="#14121c"/>
      <rect x="4" y="3" width="2" height="1" fill="#a8a6b8"/>
      <rect x="6" y="3" width="10" height="1" fill="#e8e6ef"/>
      <rect x="16" y="3" width="2" height="1" fill="#a8a6b8"/>
      <rect x="18" y="3" width="2" height="1" fill="#14121c"/>
      <rect x="2" y="4" width="1" height="3" fill="#14121c"/>
      <rect x="3" y="4" width="1" height="3" fill="#a8a6b8"/>
      <rect x="4" y="4" width="14" height="1" fill="#e8e6ef"/>
      <rect x="18" y="4" width="1" height="3" fill="#a8a6b8"/>
      <rect x="19" y="4" width="1" height="3" fill="#14121c"/>
      <rect x="4" y="5" width="1" height="2" fill="#e8e6ef"/>
      <rect x="5" y="5" width="12" height="1" fill="#2f8f5f"/>
      <rect x="17" y="5" width="1" height="2" fill="#e8e6ef"/>
      <rect x="5" y="6" width="12" height="1" fill="#57c98d"/>
      <rect x="2" y="7" width="2" height="1" fill="#14121c"/>
      <rect x="4" y="7" width="14" height="1" fill="#a8a6b8"/>
      <rect x="18" y="7" width="2" height="1" fill="#14121c"/>
      <rect x="4" y="8" width="1" height="2" fill="#14121c"/>
      <rect x="5" y="8" width="2" height="1" fill="#6e6c82"/>
      <rect x="7" y="8" width="2" height="1" fill="#8ad8ff"/>
      <rect x="9" y="8" width="4" height="1" fill="#6e6c82"/>
      <rect x="13" y="8" width="2" height="1" fill="#8ad8ff"/>
      <rect x="15" y="8" width="2" height="1" fill="#6e6c82"/>
      <rect x="17" y="8" width="1" height="2" fill="#14121c"/>
      <rect x="5" y="9" width="12" height="1" fill="#6e6c82"/>
      <rect x="21" y="9" width="3" height="1" fill="#14121c"/>
      <rect x="5" y="10" width="2" height="1" fill="#14121c"/>
      <rect x="7" y="10" width="8" height="1" fill="#6e6c82"/>
      <rect x="15" y="10" width="2" height="1" fill="#14121c"/>
      <rect x="20" y="10" width="1" height="3" fill="#14121c"/>
      <rect x="21" y="10" width="2" height="3" fill="#1e2b3d"/>
      <rect x="23" y="10" width="1" height="3" fill="#14121c"/>
      <rect x="7" y="11" width="2" height="1" fill="#14121c"/>
      <rect x="9" y="11" width="4" height="1" fill="#6e6c82"/>
      <rect x="13" y="11" width="2" height="1" fill="#14121c"/>
      <rect x="3" y="12" width="5" height="1" fill="#14121c"/>
      <rect x="8" y="12" width="6" height="1" fill="#f2c14e"/>
      <rect x="14" y="12" width="5" height="1" fill="#14121c"/>
      <rect x="2" y="13" width="1" height="3" fill="#14121c"/>
      <rect x="3" y="13" width="4" height="1" fill="#e8e6ef"/>
      <rect x="7" y="13" width="1" height="3" fill="#14121c"/>
      <rect x="8" y="13" width="6" height="1" fill="#3a6ea8"/>
      <rect x="14" y="13" width="1" height="3" fill="#14121c"/>
      <rect x="15" y="13" width="4" height="1" fill="#e8e6ef"/>
      <rect x="19" y="13" width="5" height="1" fill="#14121c"/>
      <rect x="3" y="14" width="1" height="2" fill="#e8e6ef"/>
      <rect x="4" y="14" width="2" height="2" fill="#a8a6b8"/>
      <rect x="6" y="14" width="1" height="2" fill="#e8e6ef"/>
      <rect x="8" y="14" width="2" height="2" fill="#3a6ea8"/>
      <rect x="10" y="14" width="2" height="2" fill="#f2c14e"/>
      <rect x="12" y="14" width="2" height="2" fill="#3a6ea8"/>
      <rect x="15" y="14" width="1" height="2" fill="#e8e6ef"/>
      <rect x="16" y="14" width="2" height="2" fill="#a8a6b8"/>
      <rect x="18" y="14" width="1" height="2" fill="#e8e6ef"/>
      <rect x="19" y="14" width="1" height="2" fill="#14121c"/>
      <rect x="2" y="16" width="6" height="1" fill="#14121c"/>
      <rect x="8" y="16" width="6" height="2" fill="#3a6ea8"/>
      <rect x="14" y="16" width="6" height="1" fill="#14121c"/>
      <rect x="6" y="17" width="1" height="2" fill="#14121c"/>
      <rect x="7" y="17" width="1" height="1" fill="#26507d"/>
      <rect x="14" y="17" width="1" height="1" fill="#26507d"/>
      <rect x="15" y="17" width="1" height="2" fill="#14121c"/>
      <rect x="7" y="18" width="2" height="1" fill="#26507d"/>
      <rect x="9" y="18" width="4" height="1" fill="#3a6ea8"/>
      <rect x="13" y="18" width="2" height="1" fill="#26507d"/>
      <rect x="6" y="19" width="2" height="1" fill="#14121c"/>
      <rect x="8" y="19" width="6" height="1" fill="#26507d"/>
      <rect x="14" y="19" width="2" height="1" fill="#14121c"/>
      <rect x="8" y="20" width="6" height="1" fill="#14121c"/>
    </g>
    <g class="sur-info">
      <rect x="21" y="10" width="2" height="1" fill="#8fb4e0"/>
      <rect x="21" y="11" width="1" height="1" fill="#f2c14e"/>
      <rect x="22" y="11" width="1" height="1" fill="#1e2b3d"/>
      <rect x="21" y="12" width="2" height="1" fill="#8fb4e0"/>
    </g>
    <g class="sur-valide">
      <rect x="7" y="8" width="2" height="1" fill="#57c98d"/>
      <rect x="13" y="8" width="2" height="1" fill="#57c98d"/>
      <rect x="21" y="10" width="1" height="1" fill="#0f3320"/>
      <rect x="22" y="10" width="1" height="1" fill="#57c98d"/>
      <rect x="21" y="11" width="1" height="2" fill="#57c98d"/>
      <rect x="22" y="11" width="1" height="2" fill="#0f3320"/>
    </g>
    <g class="sur-anomalie">
      <rect x="7" y="8" width="2" height="1" fill="#ff8a72"/>
      <rect x="13" y="8" width="2" height="1" fill="#ff8a72"/>
      <rect x="21" y="10" width="1" height="3" fill="#4a1410"/>
      <rect x="22" y="10" width="1" height="3" fill="#ff8a72"/>
    </g>
  </svg>
</div>
<script>
(function () {
  var boite = document.getElementById("assistant");
  if (!boite) return;
  if (document.cookie.indexOf("assistant=0") !== -1) return;
  var texte = boite.querySelector(".texte");
  var minuteur = null, premiere = true;

  function etat(nom) {
    boite.classList.remove("info", "valide", "anomalie");
    boite.classList.add(nom || "info");
  }
  function montrer(aide, nom) {
    clearTimeout(minuteur);
    etat(nom);
    texte.textContent = aide;
    boite.classList.add("actif");
    requestAnimationFrame(function () {
      boite.classList.add("parle");
      if (premiere) {
        premiere = false;
        boite.classList.add("salue");
        setTimeout(function () { boite.classList.remove("salue"); }, 1700);
      }
    });
  }
  function cacher(delai) {
    clearTimeout(minuteur);
    minuteur = setTimeout(function () {
      boite.classList.remove("parle");
      setTimeout(function () { boite.classList.remove("actif"); }, 250);
    }, delai === undefined ? 400 : delai);
  }

  // 1. Infobulles : elle EXPLIQUE. textContent, jamais innerHTML.
  document.querySelectorAll(".aide[data-aide]").forEach(function (a) {
    a.setAttribute("tabindex", "0");
    ["mouseenter", "focus"].forEach(function (ev) {
      a.addEventListener(ev, function () {
        montrer(a.dataset.aide, a.dataset.aideEtat || "info");
      });
    });
    ["mouseleave", "blur"].forEach(function (ev) {
      a.addEventListener(ev, function () { cacher(); });
    });
  });
  var bulle = boite.querySelector(".bulle");
  bulle.addEventListener("mouseenter", function () { clearTimeout(minuteur); });
  bulle.addEventListener("mouseleave", function () { cacher(); });
  boite.querySelector(".fermer").addEventListener("click", function () {
    boite.classList.remove("actif", "parle");
    document.cookie = "assistant=0; path=/; max-age=31536000";
  });

  // 2. Elle COMMENTE ce qui vient de se passer — c'est ce qui donne un
  //    sens aux trois visages. Le message existe déjà à l'écran : elle ne
  //    le remplace pas, elle l'incarne, puis s'efface d'elle-même.
  var err = document.querySelector(".flash-err");
  var avert = document.querySelector(".flash-warn");
  var ok = document.querySelector(".flash-ok");
  var reaction = err ? ["anomalie", err] : avert ? ["anomalie", avert]
               : ok ? ["valide", ok] : null;
  if (reaction) {
    var mot = (reaction[1].textContent || "").trim();
    if (mot.length > 240) { mot = mot.slice(0, 237) + "\u2026"; }
    setTimeout(function () { montrer(mot, reaction[0]); cacher(6500); }, 500);
  }
})();
</script>
"""

PAGE_DON_SECTION = """
<div class="card" style="border-left:4px solid #1a73e8;background:#f5f9ff">
  <div class="card-body" style="padding:12px 16px;display:flex;
       align-items:center;gap:14px;flex-wrap:wrap">
    <div style="flex:1;min-width:260px">
      <b>Ce logiciel est gratuit.</b>
      <span class="muted">S'il vous fait gagner du temps (ou des honoraires
      d'expert-comptable), vous pouvez soutenir son développement par un don
      — c'est entièrement facultatif et ça ne débloque rien : tout est déjà
      débloqué.</span>
    </div>
    <a href="https://www.paypal.me/sfaure01" target="_blank" rel="noopener"
       style="display:inline-block;background:#1a73e8;color:#fff;
       padding:8px 18px;border-radius:6px;text-decoration:none;
       font-weight:600">Faire un don (PayPal)</a>
    <span class="muted" style="font-size:.85em">Compte PayPal :
      sylvainfaure01@hotmail.fr</span>
  </div>
</div>
"""

PAGE_IMPORT_SECTION = """
<div class="card"><div class="card-body">
  <h2>Importer un relevé bancaire (CSV)
    <span style="background:#fff3cd;color:#7a5c00;border:1px solid #e6cf8b;
          border-radius:4px;padding:2px 8px;font-size:.7em;font-weight:600;
          vertical-align:middle">FONCTION EXPÉRIMENTALE</span></h2>
  <p style="background:#fff8e6;border-left:4px solid #e8b93e;padding:8px 12px">
  Cette fonction a été testée sur des relevés types, pas encore sur la
  diversité des exports réels des banques (chaque banque a son dialecte).
  <b>Vérifiez chaque proposition avant de valider</b> — rien n'est écrit
  sans votre accord, et une opération validée par erreur s'annule d'un clic
  (contre-passation). Vos retours sur des relevés réels sont bienvenus.</p>
  <p class="muted">Colonnes attendues : date ; libellé ; montant. Les exports
  des banques françaises sont acceptés tels quels (encodage Windows, montants
  « 1 234,56 »…). Chaque ligne devient une <b>proposition</b> que vous validez
  ou écartez — rien n'est écrit sans votre accord.</p>
  <form method="post" action="/import/proposer" enctype="multipart/form-data"
        style="display:flex;gap:10px;align-items:center">
    <input type="file" name="releve" accept=".csv,.txt" required>
    <button type="submit">Analyser le relevé</button>
  </form>
  {% if propositions %}
  <form method="post" action="/import/valider" style="margin-top:14px">
    <table>
      <thead><tr><th></th><th>Date</th><th>Libellé</th><th>Catégorie
        proposée</th><th style="text-align:right">Montant</th></tr></thead>
      <tbody>
      {% for p in propositions %}
        <tr>
          <td><input type="checkbox" name="ligne" value="{{ loop.index0 }}"
                     checked></td>
          <td>{{ p.date_operation }}</td>
          <td>{{ p.libelle }}</td>
          <td>{{ p.type }}</td>
          <td style="text-align:right">{{ '%.2f'|format(p.montant) }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
    <input type="hidden" name="jeton" value="{{ jeton }}">
    <p><button type="submit">Enregistrer les lignes cochées</button></p>
  </form>
  {% endif %}
</div></div>
"""

PAGE_SAISIE = """
<div class="card">
  <div class="card-header">Nouvelle saisie</div>
  <div class="card-body">
    <form method="post" action="/saisir">
      <input type="hidden" name="annee" value="{{ annee }}">
      <div class="form-grid">

        <div class="full">
          <label class="field" for="type">Que souhaitez-vous saisir ?<span
            class="aide" data-aide="Choisissez la nature de l'opération : un loyer encaissé, une charge (assurance, énergie…), une acquisition à immobiliser. Le bon compte comptable est appliqué automatiquement.">?</span></label>
          <select id="type" name="type" required onchange="majPeriode(this.value)">
            <option value="" disabled selected>— choisir —</option>
            {% for groupe, items in choix_groupes %}
            <optgroup label="{{ groupe }}">
              {% for key, g in items %}
              <option value="{{ key }}" data-perio="{{ g['periodicite'] }}">{{ g['libelle'] }}</option>
              {% endfor %}
            </optgroup>
            {% endfor %}
          </select>
        </div>

        {% if biens|length > 1 %}
        <div class="full">
          <label class="field" for="bien_id">Bien concerné</label>
          <select id="bien_id" name="bien_id">
            {% for b in biens %}<option value="{{ b['id'] }}">{{ b['libelle'] }}</option>{% endfor %}
          </select>
        </div>
        {% else %}
        <input type="hidden" name="bien_id" value="{{ biens[0]['id'] if biens else 1 }}">
        {% endif %}

        <div>
          <label class="field" for="date_operation">Date de l'opération<span
            class="aide" data-aide="Jour de l'opération, au format AAAA-MM-JJ (ex. 2026-03-15). Elle doit tomber dans l'exercice ouvert, sinon la saisie est refusée.">?</span></label>
          <input type="date" id="date_operation" name="date_operation"
                 value="{{ today }}" required>
        </div>

        <div id="bloc-periode">
          <label class="field" for="periode">Période
            <span class="opt">(AAAA-MM, si mensuel)</span><span
            class="aide" data-aide="Mois concerné pour une charge ou un loyer récurrent, au format AAAA-MM (ex. 2026-03 pour mars 2026). Sert à repérer un loyer manquant sur l'année.">?</span></label>
          <input type="month" id="periode" name="periode" value="{{ today[:7] }}">
        </div>

        <div>
          <label class="field" for="montant">Montant TTC (€)<span
            class="aide" data-aide="Montant positif, en euros. La virgule et le point sont acceptés (ex. 795,50 ou 795.50). Pas de séparateur de milliers.">?</span></label>
          <input type="number" id="montant" name="montant"
                 step="0.01" min="0.01" placeholder="0,00" required>
        </div>

        <div>
          <label class="field" for="piece_ref">Pièce de l'écriture
            <span class="opt">(réf. justificatif)</span><span
            class="aide" data-aide="Référence du justificatif classé : quittance, facture, relevé… (ex. QUITTANCE-2026-03, FAC-042). Obligatoire — c'est le lien vers la pièce en cas de contrôle.">?</span></label>
          <input type="text" id="piece_ref" name="piece_ref"
                 placeholder="ex. QUITTANCE-2026-03, FAC-042">
        </div>

        <div>
          <label class="field" for="tiers">Tiers
            <span class="opt">(optionnel)</span><span
            class="aide" data-aide="Nom de la personne ou de l'entreprise concernée (ex. Locataire Dupont, EDF, Syndic Foncia). Facultatif, mais utile pour retrouver une opération.">?</span></label>
          <input type="text" id="tiers" name="tiers"
                 placeholder="ex. Locataire, EDF, Syndic…">
        </div>

        <div>
          <label class="field" for="libelle">Commentaire
            <span class="opt">(optionnel)</span><span
            class="aide" data-aide="Libellé personnalisé de l'écriture. Laissé vide, le libellé standard du gabarit est utilisé. Évitez les tabulations et retours à la ligne (interdits dans un FEC).">?</span></label>
          <input type="text" id="libelle" name="libelle"
                 placeholder="Remplace le libellé standard du gabarit">
        </div>

      </div>
      <button type="submit" class="btn btn-primary mt">Enregistrer</button>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header green" id="carte-appel">Appel de charges de copropriété — ventilation (formulaire distinct, ci-dessous)</div>
  <div class="card-body">
    <p class="muted" style="margin-bottom:12px">
      <strong>C'est ICI que se saisit un appel de charges du syndic</strong> —
      pas dans le formulaire de saisie simple ci-dessus. Un appel mélange
      plusieurs composantes fiscales : ventilez-le en une fois, les écritures
      sont rattachées à la même pièce.
      <strong>Charges courantes</strong> : déductibles en totalité — y compris
      la quote-part récupérable sur le locataire, puisque les provisions
      encaissées sont imposées en produits (traitement BIC symétrique).
      <strong>Fonds travaux ALUR</strong> : comptabilisé en charge mais
      réintégré fiscalement à la clôture (contribution capitalisée, non
      déductible). <strong>Travaux hors budget</strong> : en entretien ; pour
      de gros travaux (ravalement, toiture…), préférez une immobilisation.
    </p>
    <form method="post" action="/saisir-appel"
          style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr auto;gap:10px;align-items:end">
      <div><label class="field">Date de l'appel</label>
        <input type="date" name="date_operation" value="{{ today }}" required></div>
      <div><label class="field">Période</label>
        <input type="month" name="periode" value="{{ today[:7] }}"></div>
      <div><label class="field">Charges courantes (€)</label>
        <input type="number" step="0.01" min="0" name="charges_courantes"
               placeholder="déductibles"></div>
      <div><label class="field">Fonds travaux ALUR (€)</label>
        <input type="number" step="0.01" min="0" name="fonds_alur"
               placeholder="réintégré"></div>
      <div><label class="field">Travaux hors budget (€)</label>
        <input type="number" step="0.01" min="0" name="travaux"
               placeholder="entretien"></div>
      <button type="submit" class="btn btn-success">Ventiler l'appel</button>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header">Opérations {{ annee }}</div>
  <div class="card-body" style="padding:0">
    {% if ops %}
    <table>
      <thead>
        <tr>
          <th>N°</th><th>Date</th><th>Nature</th><th>Libellé</th>
          <th>Pièce</th><th>Tiers</th><th>Période</th>
          <th style="text-align:right">Montant TTC</th>
          <th style="text-align:center">Dupliquer</th>
          <th style="text-align:center">Annuler</th>
        </tr>
      </thead>
      <tbody>
        {% for op in ops %}
        {% set is_p = op['type'] in produit_types %}
        <tr>
          <td class="muted">BQ {{ op['ecriture_num'] }}</td>
          <td>{{ op['date_operation'][8:10] }}/{{ op['date_operation'][5:7] }}/{{ op['date_operation'][:4] }}</td>
          <td><span class="badge {{ 'badge-produit' if is_p else 'badge-charge' }}">
            {{ 'Recette' if is_p else 'Charge' }}</span></td>
          <td>{{ op['libelle'] or gabarits_lib.get(op['type'], op['type']) }}</td>
          <td>{{ op['piece_ref'] or '' }}</td>
          <td>{{ op['tiers'] or '' }}</td>
          <td>{{ op['periode'] or '' }}</td>
          <td class="right {{ 'green' if is_p else 'red' }}">
            {{ '%.2f'|format(op['montant'])|replace('.', ',') }} €</td>
          <td>
            {% if not op['annulee'] %}
            <form method="post" action="/operation/{{ op['id'] }}/dupliquer"
                  style="display:inline">
              <button type="submit" class="btn"
                      style="padding:2px 8px;font-size:12px"
                      title="Dupliquer cette opération au mois suivant
(même montant, même nature — date et période décalées d'un mois)">→ M+1</button>
            </form>
            {% endif %}
          </td>
          <td>
            {% if op['annulee'] %}
              <span class="badge badge-clos" title="Une écriture inverse a été passée : les montants se neutralisent. Rien n'a été supprimé.">annulée</span>
            {% else %}
            <form method="post" action="/operation/{{ op['id'] }}/annuler"
                  style="display:inline"
                  data-confirmer="Annuler cette opération ? Une écriture INVERSE sera passée à la même date (contre-passation). Rien n'est supprimé : la numérotation reste dense et la piste comptable complète.">
              <button type="submit" class="btn-secondaire"
                      style="padding:2px 8px;font-size:12px"
                      title="Annuler par contre-passation : une écriture inverse est passée à la même date. Rien n'est supprimé — c'est le geste comptable, pas une suppression.">Annuler</button>
            </form>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p class="empty">Aucune opération saisie pour {{ annee }}.</p>
    {% endif %}
  </div>
</div>

<script>
const perioMap = {{ perio | tojson }};
function majPeriode(type) {
  const bloc = document.getElementById('bloc-periode');
  bloc.style.display = (perioMap[type] === 'mensuel') ? '' : 'none';
}
majPeriode(document.getElementById('type').value);
</script>
"""


PAGE_IMMO = """
{% if not exploitant %}
<div class="card">
  <div class="card-header amber">Exploitant — configuration initiale
    <span class="aide" data-aide="Vous reprenez une comptabilite existante ? L'ordre compte : 1) cette identite ; 2) TOUTES les immobilisations, dans l'ordre d'acquisition, sur cette meme page ; 3) seulement ensuite, l'import des FEC anterieurs, onglet Nouvel exercice, du plus ancien au plus recent.">?</span></div>
  <div class="card-body">
    <p style="margin-bottom:16px;color:#555;font-size:13px">
      Aucun exploitant enregistré. Renseignez vos informations pour pouvoir créer un bien.
    </p>
    <p style="margin-bottom:16px;background:#f0f6fb;border-left:4px solid #1a73e8;padding:10px 14px;font-size:13px">
      <b>Vous importez une comptabilité existante ?</b> Dans cet ordre :
      cette identité → vos immobilisations, ci-dessous, dans l'ordre
      d'acquisition → puis seulement l'import des FEC, onglet
      <a href="/exercice/nouveau">Nouvel exercice</a>, du plus ancien au
      plus récent. L'import fait avant les immobilisations laisse un bilan
      que le tableau 2033-C contredit.
    </p>
    <form method="post" action="/immobilisations/exploitant">
      <input type="hidden" name="annee" value="{{ annee }}">
      <div class="form-grid">
        <div><label class="field">Nom / Raison sociale</label>
          <input name="nom" required placeholder="DUPONT JEAN"></div>
        <div><label class="field">SIREN</label>
          <input name="siren" required placeholder="123456789" maxlength="9"></div>
        <div class="full"><label class="field">Adresse</label>
          <input name="adresse" placeholder="1 rue de la Paix, 75001 Paris"></div>
      </div>
      <button type="submit" class="btn btn-primary mt">Enregistrer l'exploitant</button>
    </form>
  </div>
</div>
{% else %}

<!-- Biens & composants existants -->
{% if biens %}
{% for bien in biens %}
<div class="card">
  <div class="card-header">{{ bien['libelle'] }} — {{ bien['adresse'] or '' }}
    {% if bien['date_cession'] %}
      <span style="float:right;font-weight:400;color:#c0392b">Cédé le {{ bien['date_cession'] }}</span>
    {% else %}
      <details style="float:right;font-weight:400">
        <summary style="cursor:pointer">Céder ce bien…</summary>
        <form method="post" action="/immobilisations/bien/{{ bien['id'] }}/ceder"
              style="margin-top:8px;display:flex;gap:8px;align-items:center">
          <label class="field" style="margin:0">Date
            <span class="aide" data-aide="Date de l'acte de vente (AAAA-MM-JJ). Les composants sont amortis au prorata jusqu'à cette date, puis sortis du bilan.">?</span></label>
          <input type="date" name="date_cession" required>
          <label class="field" style="margin:0">Prix (€)
            <span class="aide" data-aide="Prix de cession de l'acte. La plus-value relève du régime des particuliers (déclarée par le notaire) : elle est neutralisée dans le résultat LMNP.">?</span></label>
          <input type="number" name="prix_cession" step="0.01" min="0" required style="width:120px">
          <!-- data-confirmer, pas un littéral JS : le texte y est un
               ATTRIBUT, donc apostrophes et sauts de ligne sans danger.
               C'est le mécanisme posé en passe D ; ces deux confirmations
               ne l'avaient pas reçu et contournaient le problème en
               RETIRANT les apostrophes du texte lu par l'utilisateur. -->
          <button type="submit" data-confirmer="Céder définitivement ce bien ? Les composants seront sortis du bilan.">Valider la cession</button>
        </form>
      </details>
    {% endif %}
  </div>
  <div class="card-body" style="padding:0">
    <table>
      <thead>
        <tr>
          <th>Réf.</th><th>Composant</th><th>Catégorie</th>
          <th style="text-align:right">Valeur brute</th>
          <th>Durée</th><th>Mise en service</th>
          <th>Compte</th><th>Amort.</th><th style="text-align:center">Durée</th>
          <th style="text-align:center">Corriger</th>
        </tr>
      </thead>
      <tbody>
        {% for c in composants if c['bien_id'] == bien['id'] %}
        <tr>
          <td class="muted">{{ c['code_immo'] or '—' }}</td>
          <td>{{ c['libelle'] }}</td>
          <td>{{ c['categorie'] or '—' }}</td>
          <td class="right">{{ '%.2f'|format(c['valeur_brute'])|replace('.', ',') }} €</td>
          <td>{{ (c['duree_annees']|string + ' ans') if c['duree_annees'] else '∞ (terrain)' }}</td>
          <td>{{ c['date_mise_service'] or '—' }}</td>
          <td class="muted">{{ c['compte_immo'] }}</td>
          <td><span class="badge {{ 'badge-ok' if c['amortissable'] else 'badge-clos' }}">
            {{ 'Oui' if c['amortissable'] else 'Non' }}</span></td>
          <td style="text-align:center">
            <form method="post" action="/immobilisations/composant/{{ c['id'] }}/duree"
                  style="margin:0;display:flex;gap:4px;justify-content:center">
              <input type="number" name="duree_annees" min="0" max="100"
                     value="{{ c['duree_annees'] or 0 }}" style="width:60px"
                     title="0 = non amortissable">
              <button type="submit" class="btn-secondaire">Corriger</button>
            </form>
          </td>
          <td style="text-align:center">
            <form method="post"
                  action="/immobilisations/composant/{{ c['id'] }}/supprimer"
                  style="margin:0">
              <button type="submit" class="btn-secondaire"
                      data-confirmer="Supprimer ce composant ? Son écriture d'acquisition sera contre-passée, et la ligne disparaîtra du plan d'amortissement. Vous pourrez la resaisir avec les bonnes valeurs.">Supprimer</button>
            </form>
          </td>
        </tr>
        {% else %}
        <tr><td colspan="10" class="empty">Aucun composant pour ce bien.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endfor %}
{% endif %}

<div class="row2">

  <!-- Nouveau bien -->
  <div class="card">
    <div class="card-header green">Ajouter un bien immobilier</div>
    <div class="card-body">
      <form method="post" action="/immobilisations/bien">
        <input type="hidden" name="annee" value="{{ annee }}">
        <div style="display:grid;gap:12px">
          <div><label class="field">Libellé du bien</label>
            <input name="libelle" required placeholder="Appartement 2P — Rue Gergovia"></div>
          <div><label class="field">Adresse <span class="opt">(optionnel)</span></label>
            <input name="adresse" placeholder="12 Rue Gergovia, 63000 Clermont-Ferrand"></div>
          <div><label class="field">Date d'acquisition</label>
            <input type="date" name="date_acquisition"></div>
          <div><label class="field">Prix total d'acquisition (€) <span class="opt">(optionnel)</span></label>
            <input type="number" name="prix_total" step="0.01" min="0" placeholder="117 000,00"></div>
          <div><label class="field">Quote-part terrain <span class="opt">(ex. 0.09)</span></label>
            <input type="number" name="quote_part_terrain" step="0.000001" min="0" max="1" placeholder="0.09">
            <p class="hint">Rapport terrain / prix total — sert au calcul de la décomposition.</p></div>
        </div>
        <button type="submit" class="btn btn-primary mt">Créer le bien</button>
      </form>
    </div>
  </div>

  {% for bien in biens %}{% if ventilations.get(bien['id']) %}
  <div class="card" style="border-left:4px solid #1a73e8;background:#f5f9ff">
    <div class="card-body">
      <h2 style="margin-top:0">Ventilation initiale — {{ bien['libelle'] }}</h2>
      <p>Avant d'ajouter des composants un par un, <b>répartissez le prix
      d'acquisition</b> ({{ '%.2f'|format(bien['prix_total'] or 0) }} €).
      C'est cette décomposition qui fait tout l'intérêt du régime réel :
      un bien saisi en bloc s'amortit à la vitesse du gros œuvre, et le
      mobilier — qui devrait s'amortir en quelques années — s'étale alors
      sur des décennies.</p>
      <p class="muted">Les parts pré-remplies sont des <b>ordres de grandeur
      usuels</b>, à ajuster : la répartition doit refléter la réalité du bien
      et les pièces de l'acquisition. Les durées suivent les usages admis par
      l'administration (BOI-ANNX-000115) et restent elles aussi indicatives.</p>
      <form method="post" action="/immobilisations/ventiler"
            id="form-vent-{{ bien['id'] }}">
        <input type="hidden" name="bien_id" value="{{ bien['id'] }}">
        <table id="tab-vent-{{ bien['id'] }}">
          <thead><tr><th>Poste</th><th style="text-align:right">Montant</th>
            <th style="text-align:right">Durée</th><th>À quoi ça correspond</th></tr></thead>
          <tbody>
          {% for l in ventilations[bien['id']] %}
            <tr data-cle="{{ l.cle }}">
              <td>{{ l.libelle }}
                {% if l.cle in dedoublables %}
                <button type="button" class="btn-secondaire ajout-poste"
                        data-cle="{{ l.cle }}" data-libelle="{{ l.libelle }}"
                        title="Ajouter une seconde ligne de ce poste, avec sa propre durée"
                        style="margin-left:6px;padding:0 7px">+</button>
                {% endif %}</td>
              <td style="text-align:right">
                <input type="number" step="0.01" min="0" style="width:120px"
                       class="vent-{{ bien['id'] }}"
                       name="montant_{{ l.cle }}" value="{{ '%.2f'|format(l.montant) }}"></td>
              <td style="text-align:right">
                <input type="number" min="0" max="100" style="width:70px"
                       name="duree_{{ l.cle }}" value="{{ l.duree }}"></td>
              <td class="muted" style="font-size:.9em">{{ l.note }}</td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
        <p class="muted" style="font-size:.9em">Le « + » d'un poste ajoute
        une ligne à ce poste. Un meublé n'a pas UNE durée de mobilier :
        l'électroménager se renouvelle en 5 ans, les lits en 10, une cuisine
        intégrée en 15. Séparez-les — c'est exactement ce que la
        décomposition apporte, et une ligne unique vous oblige sinon à une
        durée moyenne.</p>
        <p style="margin:10px 0">Total ventilé :
          <b id="tot-{{ bien['id'] }}">—</b>
          <span class="muted">/ prix d'acquisition
          {{ '%.2f'|format(bien['prix_total'] or 0) }} €</span>
          <span id="ec-{{ bien['id'] }}"></span></p>
        <p class="muted" style="font-size:.9em"><b>Frais d'acquisition</b>
        (notaire, droits de mutation, commission d'agence) : ils ne figurent
        pas ci-dessus car ils relèvent d'un choix — se déduire en charge
        l'année de l'acquisition, ou s'incorporer au prix de revient pour
        être amortis. Décidez avant de ventiler : l'option se retient une
        fois pour toutes.</p>
        <label><input type="checkbox" name="sans_ecriture" value="1">
          Ne pas générer les écritures d'acquisition (bien déjà porté par
          les à-nouveaux d'un exercice antérieur)</label>
        <p><button type="submit">Créer ces composants</button></p>
      </form>
      <script>
      (function(){
        var id = "{{ bien['id'] }}", prix = {{ bien['prix_total'] or 0 }};
        function maj(){
          var t = 0;
          document.querySelectorAll(".vent-" + id).forEach(function(i){
            t += parseFloat(i.value || 0); });
          t = Math.round(t * 100) / 100;
          document.getElementById("tot-" + id).textContent =
            t.toFixed(2) + " \u20ac";
          var e = document.getElementById("ec-" + id);
          if (!prix) { e.textContent = ""; return; }
          var ec = t - prix, pct = Math.abs(ec) / prix * 100;
          e.textContent = pct < 0.01 ? "  \u2713 le compte est juste"
            : "  \u00e9cart " + (ec > 0 ? "+" : "") + ec.toFixed(2)
              + " \u20ac (" + pct.toFixed(1) + " %)";
          e.style.color = pct > 5 ? "#c5221f" : (pct < 0.01 ? "#188038" : "#e8710a");
        }
        var form = document.getElementById("form-vent-" + id);
        form.addEventListener("input", function(e){
          if (e.target.classList.contains("vent-" + id)) maj(); });

        // Une ligne SUPPLÉMENTAIRE sur un poste dédoublable. Les champs
        // partent en listes parallèles (sup_cle / sup_libelle / sup_montant
        // / sup_duree) : c'est la forme que lit amortissement.postes_ventilation.
        function ajouter(cle, libelle){
          var corps = document.querySelector("#tab-vent-" + id + " tbody");
          var lignes = corps.querySelectorAll("tr[data-cle='" + cle + "']");
          var tr = document.createElement("tr");
          tr.setAttribute("data-cle", cle);
          var champ = function(n, v, attrs){
            return "<input name='" + n + "' value='" + v + "' " + attrs + ">"; };
          tr.innerHTML =
            "<td><input type='hidden' name='sup_cle' value='" + cle + "'>"
            + champ("sup_libelle", libelle + " (2)", "style='width:150px'")
            + "</td><td style='text-align:right'>"
            + champ("sup_montant", "", "type='number' step='0.01' min='0' "
                    + "style='width:120px' class='vent-" + id + "'")
            + "</td><td style='text-align:right'>"
            + champ("sup_duree", "", "type='number' min='0' max='100' "
                    + "style='width:70px'")
            + "</td><td class='muted' style='font-size:.9em'>"
            + "Ligne ajoutee : donnez-lui son libelle et sa propre duree. "
            + "<button type='button' class='btn-secondaire retirer-poste'>"
            + "Retirer</button></td>";
          lignes[lignes.length - 1].insertAdjacentElement("afterend", tr);
          maj();
        }
        form.addEventListener("click", function(e){
          if (e.target.classList.contains("ajout-poste")) {
            ajouter(e.target.dataset.cle, e.target.dataset.libelle);
          } else if (e.target.classList.contains("retirer-poste")) {
            e.target.closest("tr").remove();
            maj();
          }
        });
        maj();
      })();
      </script>
    </div>
  </div>
  {% endif %}{% endfor %}

  {% if amort_anterieurs %}
  <div class="card" style="border-left:4px solid #e8710a;background:#fff8f0">
    <div class="card-body">
      <h2 style="margin-top:0">Amortissements antérieurs non repris</h2>
      {% if amort_anterieurs > 0 %}
      <p>Vos composants sont amortis depuis leur mise en service, mais
      <b>{{ '%.2f'|format(amort_anterieurs) }} €</b> d'amortissements déjà
      courus avant cet exercice ne figurent pas dans les comptes. C'est le
      cas habituel d'un bien acquis il y a plusieurs années et saisi ici
      pour la première fois : l'écriture d'entrée porte la valeur brute,
      sans le cumul déjà pratiqué.</p>
      {% else %}
      <p>Les comptes d'amortissement portent
      <b>{{ '%.2f'|format(-amort_anterieurs) }} €</b> de PLUS que le plan
      d'amortissement n'en calcule à l'ouverture de cet exercice. Cela
      arrive quand les à-nouveaux viennent d'un cabinet qui appliquait
      d'autres durées que celles saisies ici, ou après avoir corrigé une
      durée, une valeur ou un composant.</p>
      <p class="muted"><b>Avant de reprendre, vérifiez la saisie.</b> Si le
      cabinet amortissait votre mobilier en 5 ans et que vous avez indiqué
      8 ans, c'est la durée qu'il faut aligner — pas le cumul qu'il faut
      réduire. La reprise ci-dessous met les comptes au niveau du plan :
      elle n'a de sens qu'une fois le plan juste.</p>
      {% endif %}
      <p class="muted">Tant que cet écart subsiste, le bilan et le tableau
      2033-C se contredisent — il réapparaîtra à chaque liasse, et la valeur
      nette comptable servant au calcul d'une future plus-value sera
      fausse.</p>
      <form method="post" action="/immobilisations/reprendre-amortissements"
            data-confirmer="Passer l'écriture de reprise ? Le résultat de l'exercice n'est pas modifié : seul le bilan est corrigé.">
        <input type="hidden" name="annee" value="{{ annee }}">
        <button type="submit">Reprendre les amortissements antérieurs</button>
      </form>
      <p class="hint">Écriture OD au 1er janvier, contrepartie compte de
      l'exploitant. Le résultat de l'exercice n'est pas affecté.</p>
    </div>
  </div>
  {% endif %}

  <!-- Nouveau composant -->
  <div class="card">
    <div class="card-header green">Ajouter un composant</div>
    <div class="card-body">
      {% if not biens %}
      <p class="empty">Créez d'abord un bien.</p>
      {% else %}
      <form method="post" action="/immobilisations/composant">
        <input type="hidden" name="annee" value="{{ annee }}">
        <div style="display:grid;gap:12px">
          <div><label class="field">Bien</label>
            <select name="bien_id">
              {% for b in biens %}<option value="{{ b['id'] }}">{{ b['libelle'] }}</option>{% endfor %}
            </select></div>
          <div><label class="field">Libellé du composant</label>
            <input name="libelle" required placeholder="Gros oeuvre, Cuisine équipée…"></div>
          <div><label class="field">Catégorie</label>
            <select name="categorie">
              <option>Terrain</option><option>Bâtiment</option>
              <option>Travaux</option><option>Mobilier</option><option>Autre</option>
            </select></div>
          <div><label class="field">Compte d'immobilisation</label>
            <select name="compte_immo" id="cpt_immo" onchange="majAmort(this.value)">
              {% for num, lib, amort in comptes_immo %}
              <option value="{{ num }}" data-amort="{{ amort or '' }}">{{ num }} — {{ lib }}</option>
              {% endfor %}
            </select></div>
          <div><label class="field">Valeur brute (€)</label>
            <input type="number" name="valeur_brute" step="0.01" min="0" required placeholder="58 500,00"></div>
          <div><label class="field">Durée d'amortissement (années)
            <span class="opt">(0 = non amortissable)</span>
            <span class="aide" data-aide="Durees usuelles admises par l'administration (BOI-ANNX-000115) : gros oeuvre / structure 40 a 60 ans ; facade et etancheite 20 a 30 ans ; installations generales et techniques (chauffage, electricite, plomberie) 15 a 25 ans ; agencements interieurs 10 a 15 ans ; mobilier 5 a 10 ans ; electromenager 5 a 7 ans ; terrain non amortissable. Ce tableau est indicatif : la duree doit refleter la duree reelle d'utilisation du composant.">?</span></label>
            <input type="number" name="duree_annees" min="0" max="99"
                   id="duree" placeholder="0" onchange="majAmortissable(this.value)"></div>
          <div><label class="field">Date de mise en service</label>
            <input type="date" name="date_mise_service"></div>
          <div><label class="field">Réf. pièce <span class="opt">(optionnel)</span></label>
            <input name="code_immo" placeholder="MODYDW"></div>
        </div>
        <div class="mt">
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
            <input type="checkbox" name="sans_ecriture" value="1">
            <span>Ne pas générer l'écriture d'acquisition
              <span class="opt">(reprise d'un historique déjà porté par les
              à-nouveaux)</span></span>
          </label>
        </div>
        <button type="submit" class="btn btn-primary mt">Ajouter le composant</button>
      </form>
      {% endif %}
    </div>
  </div>

</div>
{% endif %}

<script>
const amortMap = {{ amort | tojson }};
function majAmort(num) {
  // pas de champ visible pour compte_amort : géré côté serveur
}
function majAmortissable(v) {
  // futur : masquer/afficher selon durée
}
</script>
"""


PAGE_CLOTURE = """
<div class="card" style="border-left:4px solid #2e7d32;background:#f4faf4">
  <div class="card-body" style="padding:12px 16px">
    <b>Clôturer n'est pas irréversible :</b> une sauvegarde de votre dossier
    est prise automatiquement juste avant, et se restaure en un clic depuis
    la page <a href="/dossiers">Dossiers</a> (section Sauvegardes).
  </div>
</div>
{% for ex in exercices %}
<div class="card">
  <div class="card-header {{ 'red' if ex['statut']=='ouvert' else '' }}">
    Exercice {{ ex['annee'] }} —
    <span class="badge {{ 'badge-ok' if ex['statut']=='ouvert' else 'badge-clos' }}">
      {{ ex['statut'] }}</span>
  </div>
  <div class="card-body">

    {% if ex['statut'] == 'ouvert' %}

    <!-- KPI avant clôture -->
    <div class="kpi-row">
      <div class="kpi">
        <div class="kpi-label">Produits</div>
        <div class="kpi-val pos">{{ '%.2f'|format(ag[ex['annee']]['produits'])|replace('.',',') }} €</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Charges (hors DAA)</div>
        <div class="kpi-val neg">{{ '%.2f'|format(ag[ex['annee']]['charges_hors_daa'])|replace('.',',') }} €</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Résultat comptable provisoire<br><small style="color:#999;font-weight:400">(hors dotation non encore générée)</small></div>
        {% set rc = ag[ex['annee']]['resultat_comptable'] %}
        <div class="kpi-val {{ 'pos' if rc >= 0 else 'neg' }}">{{ '%.2f'|format(rc)|replace('.',',') }} €</div>
      </div>
    </div>

    <!-- Anomalies -->
    {% if anos[ex['annee']] %}
    <h2 class="section">Observations avant clôture</h2>
    <table>
      <thead><tr><th>Niveau</th><th>Code</th><th>Message</th></tr></thead>
      <tbody>
        {% for a in anos[ex['annee']] %}
        <tr>
          <td><span class="badge {{ 'badge-err' if a.niveau=='BLOQUANT' else 'badge-warn' if a.niveau=='AVERTISSEMENT' else '' }}">{{ a.niveau }}</span></td>
          <td class="muted">{{ a.code }}</td>
          <td>{{ a.message }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p style="color:#155724;font-size:13px;margin-bottom:16px">
      ✓ Aucune anomalie détectée — clôture possible.
    </p>
    {% endif %}

    {% set a_bloquantes = anos[ex['annee']] | selectattr('niveau','equalto','BLOQUANT') | list %}
    <form method="post" action="/cloturer" style="margin-top:16px">
      <input type="hidden" name="annee" value="{{ ex['annee'] }}">
      <label style="font-size:13px;display:flex;align-items:center;gap:8px;margin-bottom:12px">
        <input type="number" name="retraitements" step="0.01" value="0"
               style="width:120px"> €
        <span style="color:#555">Autres retraitements fiscaux
          <span style="color:#999;font-weight:400">— laissez 0 dans la
          quasi-totalité des cas</span>
          <span class="aide" data-aide="ATTENTION AU DOUBLE RETRAITEMENT. Le fonds de travaux ALUR est déjà réintégré AUTOMATIQUEMENT par le logiciel, à partir de vos écritures de ventilation d'appel de charges : le saisir ici le compterait DEUX FOIS et gonflerait votre résultat imposable. Cette case ne sert qu'à un retraitement que le logiciel ne connaît pas — un redressement demandé par votre comptable, par exemple. Un montant POSITIF augmente le résultat fiscal (réintégration), un montant négatif le diminue (déduction). En cas de doute, laissez 0 : la page Liasse vous montrera le détail des retraitements déjà appliqués.">?</span></span>
      </label>
      {% if a_bloquantes %}
      <label style="font-size:13px;display:flex;align-items:center;gap:8px;margin-bottom:12px">
        <input type="checkbox" name="forcer" value="1">
        Forcer la clôture malgré les anomalies bloquantes
      </label>
      {% endif %}
      <button type="submit" class="btn btn-danger">Clôturer l'exercice {{ ex['annee'] }}</button>
    </form>

    {% else %}
    <!-- Exercice déjà clos -->
    <div class="kpi-row">
      <div class="kpi">
        <div class="kpi-label">Résultat comptable</div>
        {% set rc = ex['resultat_comptable'] or 0 %}
        <div class="kpi-val {{ 'pos' if rc >= 0 else 'neg' }}">{{ '%.2f'|format(rc)|replace('.',',') }} €</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Résultat fiscal</div>
        {% set rf = ex['resultat_fiscal'] or 0 %}
        <div class="kpi-val {{ 'pos' if rf >= 0 else 'neg' }}">{{ '%.2f'|format(rf)|replace('.',',') }} €</div>
      </div>
    </div>
    <p style="color:#555;font-size:13px">Cet exercice est clôturé et ne peut plus être modifié.</p>
    <p style="color:#555;font-size:13px">Dépôts — {{ depots_resume(ex['annee']) }}
      (<a href="/liasse?annee={{ ex['annee'] }}#depots">noter un dépôt</a>)</p>
    {% endif %}

  </div>
</div>
{% endfor %}
"""


PAGE_EX_NOUVEAU = """
<div class="card"><div class="card-body">
  <h2>Reprendre PLUSIEURS exercices depuis leurs FEC</h2>
  <p>Sélectionnez tous les fichiers d'un coup — l'ordre n'a pas
  d'importance, il est déduit des dates contenues dans chaque fichier.
  <b>Trois exercices valent bien mieux qu'un</b> : ils permettent des
  contrôles qu'un fichier isolé rend impossibles.</p>
  <ul class="muted" style="margin:6px 0 12px 18px">
    <li><b>Jonction des bilans</b> — le solde de clôture de chaque année
      doit se retrouver à l'ouverture de la suivante. Un écart signale une
      écriture ajoutée après coup, ou un fichier qui n'est pas la version
      définitive : c'est le défaut de migration le plus fréquent, et le
      plus silencieux.</li>
    <li><b>Amortissements</b> — avec plusieurs années de dotations
      réelles, le logiciel confronte son propre plan à celui de votre
      ancien prestataire. Un écart durable fausserait toutes vos liasses
      à venir.</li>
    <li><b>Continuité</b> — année manquante, exercice en double.</li>
  </ul>
  <form method="post" action="/exercice/analyser-fec"
        enctype="multipart/form-data"
        style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <input type="file" name="fecs" accept=".txt,.tsv" multiple required>
    <button type="submit">Analyser avant de reprendre</button>
  </form>
  <p class="hint">Rien n'est écrit à cette étape : l'analyse vous montre ce
  qu'elle a compris et ce qu'elle a trouvé, et vous décidez ensuite.</p>
</div></div>

{% if analyse %}
<div class="card"><div class="card-body">
  <h2 style="margin-top:0">Analyse des fichiers</h2>
  <table>
    <thead><tr><th>Exercice</th><th>Fichier</th><th class="num">Dotations</th>
      <th>Observations</th></tr></thead>
    <tbody>
    {% for f in analyse.fichiers %}
      <tr><td><b>{{ f.annee or '?' }}</b></td>
        <td class="muted">{{ f.nom }}</td>
        <td class="num">{{ '%.2f'|format(f.dotations) }} €</td>
        <td>{% if f.erreurs %}<span style="color:#c5221f">{{ f.erreurs|join(' ') }}</span>
            {% else %}<span class="badge badge-ok">lisible</span>{% endif %}</td></tr>
    {% endfor %}
    </tbody>
  </table>

  {% for o in analyse.observations %}
  <p style="margin:8px 0;padding:8px 12px;border-left:4px solid
     {{ '#188038' if o.type == 'ok' else '#c5221f' if o.type == 'ecart' else '#e8710a' }};
     background:{{ '#f2faf5' if o.type == 'ok' else '#fdf3f2' if o.type == 'ecart' else '#fff8ee' }}">
     {{ o.message }}</p>
  {% endfor %}

  {% if analyse.reprenables %}
  <form method="post" action="/exercice/reprendre-fec-multi">
    <input type="hidden" name="jeton" value="{{ analyse.jeton }}">
    <p><button type="submit">Reprendre {{ analyse.reprenables }} exercice(s),
      du plus ancien au plus récent</button></p>
  </form>
  {% else %}
  <p class="muted">Aucun exercice reprenable : corrigez les fichiers
  signalés ci-dessus.</p>
  {% endif %}
</div></div>
{% endif %}

<div class="card"><div class="card-body">
  <h2>Reprendre un seul exercice</h2>
  <p class="muted">Vous arrivez d'un autre logiciel ou d'un prestataire
  (prestataire de comptabilité LMNP) ? Téléversez le FEC d'un exercice :
  il est rejoué écriture par
  écriture, à numérotation identique, dans un exercice créé pour l'occasion.
  Les journaux et comptes absents du plan sont créés depuis le fichier.</p>
  <form method="post" action="/exercice/reprendre-fec"
        enctype="multipart/form-data"
        style="display:flex;gap:10px;align-items:center">
    <label class="field" style="margin:0">Année</label>
    <input type="number" name="annee" min="2000" max="2099" required
           style="width:90px">
    <input type="file" name="fec" accept=".txt,.tsv" required>
    <button type="submit">Reprendre cet exercice</button>
  </form>
</div></div>

{% if veille_due %}
<div class="card" style="border-left:4px solid #d68910;background:#fdf9f0">
  <div class="card-body">
    <h2 style="margin-top:0">Avant d'ouvrir un exercice : votre veille fiscale</h2>
    <p>Ce logiciel applique les règles <b>telles qu'elles y sont enregistrées</b> :
    il ne se met pas à jour tout seul. Une loi de finances par an peut changer
    un seuil, une durée de report ou le traitement d'une cession.
    {% if derniere_veille %}Dernière veille déclarée : {{ derniere_veille }}.
    {% else %}Aucune veille n'a encore été déclarée.{% endif %}</p>
    <p><a href="/veille"><b>Ouvrir la page Veille fiscale</b></a> — corpus des
    textes qui régissent le LMNP et question type à poser à une IA.</p>
  </div>
</div>
{% endif %}
<!-- Liste des exercices existants -->
<div class="card">
  <div class="card-header">Exercices enregistrés</div>
  <div class="card-body" style="padding:0">
    {% if exercices %}
    <table>
      <thead>
        <tr><th>Année</th><th>Début</th><th>Fin</th><th>Statut</th>
            <th style="text-align:right">Résultat comptable</th>
            <th style="text-align:right">Résultat fiscal</th></tr>
      </thead>
      <tbody>
        {% for ex in exercices %}
        <tr>
          <td><strong>{{ ex['annee'] }}</strong></td>
          <td>{{ ex['date_debut'] }}</td>
          <td>{{ ex['date_fin'] }}</td>
          <td><span class="badge {{ 'badge-ok' if ex['statut']=='ouvert' else 'badge-clos' }}">
            {{ ex['statut'] }}</span></td>
          {% if ex['resultat_comptable'] is not none %}
            {% set rc = ex['resultat_comptable'] %}
            <td class="right {{ 'green' if rc >= 0 else 'red' }}">{{ '%.2f'|format(rc)|replace('.',',') }} €</td>
          {% else %}<td class="muted right">—</td>{% endif %}
          {% if ex['resultat_fiscal'] is not none %}
            {% set rf = ex['resultat_fiscal'] %}
            <td class="right {{ 'green' if rf >= 0 else 'red' }}">{{ '%.2f'|format(rf)|replace('.',',') }} €</td>
          {% else %}<td class="muted right">—</td>{% endif %}
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p class="empty">Aucun exercice enregistré.</p>
    {% endif %}
  </div>
</div>

<!-- Formulaire -->
<div class="card" style="max-width:480px">
  <div class="card-header green">Ouvrir un nouvel exercice</div>
  <div class="card-body">
    {% if prev_ouvert %}
    <div class="flash flash-warn" style="margin-bottom:16px">
      L'exercice {{ prev_ouvert }} est encore ouvert. Pensez à le clôturer avant d'utiliser le nouvel exercice.
    </div>
    {% endif %}
    <form method="post" action="/exercice/ouvrir">
      <div style="display:grid;gap:14px">
        <div>
          <label class="field">Année</label>
          <input type="number" name="annee" value="{{ annee_suggere }}"
                 min="2000" max="2099" required>
        </div>
        <div>
          <label class="field">Date de début</label>
          <input type="date" name="date_debut" value="{{ annee_suggere }}-01-01" required>
        </div>
        <div>
          <label class="field">Date de fin</label>
          <input type="date" name="date_fin" value="{{ annee_suggere }}-12-31" required>
        </div>
        <div>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
            <input type="checkbox" name="reprise" value="1"
                   {{ 'checked' if reprise_possible else 'disabled' }}>
            <span>Reprendre les à-nouveaux de l'exercice précédent
              {% if reprise_possible %}
                <span class="muted">(bilan de clôture {{ annee_suggere - 1 }} +
                affectation du résultat, générés automatiquement)</span>
              {% else %}
                <span class="muted">(indisponible : l'exercice précédent est
                absent ou non clôturé)</span>
              {% endif %}
            </span>
          </label>
        </div>
      </div>
      <button type="submit" class="btn btn-success mt">Ouvrir l'exercice</button>
    </form>
  </div>
</div>
"""


PAGE_LIASSE = """
<style>
.liasse table { width:100%; border-collapse:collapse; font-size:13px }
.liasse th, .liasse td { padding:6px 10px; border-bottom:1px solid #e4e7ec }
.liasse th { text-align:left; background:#f7f8fa; font-weight:600 }
.liasse td.num, .liasse th.num { text-align:right; font-variant-numeric:tabular-nums }
.liasse .case { color:#8a93a3; font-size:11px; margin-left:6px }
.liasse .tot td { font-weight:700; border-top:2px solid #1e3a5f }
@media print {
  header, .no-print, .flash { display:none !important }
  body { background:#fff } main { max-width:none; padding:0 }
  .card { box-shadow:none; border:1px solid #ccc; page-break-inside:avoid }
}
</style>

<div class="liasse">
<div class="no-print" style="text-align:right;margin-bottom:12px">
  <a class="btn" href="/liasse.pdf?annee={{ L.annee }}"
     style="text-decoration:none">&#128196; Télécharger la liasse en PDF</a>
</div>
{% if L.provisoire %}
<div class="flash flash-warn">Exercice {{ L.annee }} non clôturé — chiffres
<strong>provisoires</strong> (la dotation aux amortissements et la mécanique
39 C / déficits ne sont figées qu'à la clôture).</div>
{% endif %}

<div class="card">
  <div class="card-header">Liasse fiscale — Année fiscale {{ L.annee }}
    <button class="btn no-print" style="float:right"
            onclick="window.print()">Imprimer / PDF</button>
  </div>
  <div class="card-body">
    {% if L.exploitant %}
    <p><strong>{{ L.exploitant.nom }}</strong>
       {% if L.exploitant.adresse %}— {{ L.exploitant.adresse }}{% endif %}
       {% if L.exploitant.siren %}— SIREN {{ L.exploitant.siren }}{% endif %}
       — Location Meublée (LMNP, réel simplifié)</p>
    {% endif %}
    <table style="margin-top:10px">
      <tr><th>Chiffre d'affaires HT</th><th>Résultat fiscal</th>
          <th>Déficit LMNP de l'exercice</th><th>Revenu imposable</th></tr>
      <tr><td class="num">{{ eur(L.page_garde.ca_ht) }}</td>
          <td class="num">{{ eur(L.page_garde.resultat_fiscal) }}</td>
          <td class="num">{{ eur(L.page_garde.deficit_lmnp) }}</td>
          <td class="num">{{ eur(L.page_garde.revenu_imposable) }}</td></tr>
    </table>
    <table style="margin-top:14px">
      <tr><th colspan="3">Restant à imputer sur les exercices suivants</th></tr>
      <tr><th>Amort. reportés art. 39 C</th><th>Déficits LMNP</th><th>Total</th></tr>
      <tr><td class="num">{{ eur(L.page_garde.restant_39c) }}</td>
          <td class="num">{{ eur(L.page_garde.restant_deficits) }}</td>
          <td class="num"><strong>{{ eur(L.page_garde.restant_total) }}</strong></td></tr>
    </table>
  </div>
</div>

<div class="card">
  <div class="card-header {{ 'green' if L.conforme else 'red' }}">
    Contrôles de cohérence de la liasse —
    {{ 'CONFORME ✓' if L.conforme else 'ANOMALIES ✗' }}</div>
  <div class="card-body" style="padding:0"><table>
    {% for c in L.controles %}
    <tr><td style="width:60px">{{ '✓' if c.ok else '✗' }}</td>
        <td>{{ c.nom }}</td><td class="num muted">{{ c.detail }}</td></tr>
    {% endfor %}
  </table></div>
</div>

<div class="card">
  <div class="card-header">N° 2031-SD — Récapitulation & BIC non professionnels</div>
  <div class="card-body" style="padding:0"><table>
    <tr><td>1. Résultat fiscal <span class="case">(liasse, hors LMNP non pro.)</span></td>
        <td class="num">{{ eur(L.f2031.resultat_fiscal_1) }}</td></tr>
    <tr><td>7a. BIC non professionnels — BÉNÉFICE
        <span class="case">2031 bis, cadre I « Autres locations meublées non prof. »</span></td>
        <td class="num">{{ eur(L.f2031.bic_non_pro_7a_benefice) if
            L.f2031.bic_non_pro_7a_benefice is not none else '—' }}</td></tr>
    <tr><td>7b. BIC non professionnels — DÉFICIT</td>
        <td class="num">{{ eur(L.f2031.bic_non_pro_7b_deficit) if
            L.f2031.bic_non_pro_7b_deficit is not none else '—' }}</td></tr>
  </table></div>
</div>

<div class="card">
  <div class="card-header">N° 2033-A — Bilan simplifié</div>
  <div class="card-body" style="padding:0"><table>
    <tr><th>ACTIF</th><th class="num">Brut</th>
        <th class="num">Amort.</th><th class="num">Net</th></tr>
    <tr><td>Immobilisations corporelles <span class="case">028 / 030</span></td>
        <td class="num">{{ eur(L.f2033a.immo_corporelles_brut_028) }}</td>
        <td class="num">{{ eur(L.f2033a.amortissements_030) }}</td>
        <td class="num">{{ eur(L.f2033a.immo_corporelles_net) }}</td></tr>
    <tr class="tot"><td>Total général <span class="case">110 / 112</span></td>
        <td class="num">{{ eur(L.f2033a.total_actif_110) }}</td>
        <td class="num">{{ eur(L.f2033a.amortissements_030) }}</td>
        <td class="num">{{ eur(L.f2033a.immo_corporelles_net) }}</td></tr>
    <tr><th colspan="3">PASSIF</th><th></th></tr>
    <tr><td colspan="3">Capital individuel <span class="case">120</span></td>
        <td class="num">{{ eur(L.f2033a.capital_individuel_120) }}</td></tr>
    <tr><td colspan="3">Résultat de l'exercice <span class="case">136</span></td>
        <td class="num">{{ eur(L.f2033a.resultat_exercice_136) }}</td></tr>
    <tr class="tot"><td colspan="3">Total général <span class="case">142 / 180</span></td>
        <td class="num">{{ eur(L.f2033a.total_passif_180) }}</td></tr>
  </table></div>
</div>

{% if L.projection_cloture and L.projection_cloture.dotation_previsionnelle %}
<div class="card" style="border-left:4px solid #1a73e8;background:#f5f9ff">
  <div class="card-body">
    <h2 style="margin-top:0">Projection — si l'exercice était clôturé aujourd'hui</h2>
    <p class="muted">Les tableaux ci-dessous ne portent que les écritures
    enregistrées. La dotation aux amortissements de l'exercice n'est
    comptabilisée qu'à la clôture : ces chiffres-là l'anticipent d'après le
    plan d'amortissement. C'est aussi pourquoi le tableau 2033-C peut
    afficher une dotation que la 2033-B ne voit pas encore.</p>
    <table>
      <tr><td>Dotation aux amortissements de l'exercice</td>
          <td class="num">{{ eur(L.projection_cloture.dotation_previsionnelle) }}</td></tr>
      <tr><td>Résultat comptable projeté</td>
          <td class="num">{{ eur(L.projection_cloture.resultat_comptable_projete) }}</td></tr>
      <tr><td>Amortissements reportés (art. 39 C) projetés</td>
          <td class="num">{{ eur(L.projection_cloture.report_39c_projete) }}</td></tr>
      <tr><td><b>Résultat fiscal projeté</b></td>
          <td class="num"><b>{{ eur(L.projection_cloture.resultat_fiscal_projete) }}</b></td></tr>
    </table>
  </div>
</div>
{% endif %}

<div class="card">
  <div class="card-header">N° 2033-B — Compte de résultat simplifié & résultat fiscal</div>
  <div class="card-body" style="padding:0"><table>
    <tr><td>Production vendue — services <span class="case">218</span></td>
        <td class="num">{{ eur(L.f2033b.produits_218) }}</td></tr>
    <tr><td>Total des produits d'exploitation <span class="case">232</span></td>
        <td class="num">{{ eur(L.f2033b.total_produits_232) }}</td></tr>
    <tr><td>Autres charges externes <span class="case">242</span></td>
        <td class="num">{{ eur(L.f2033b.charges_externes_242) }}</td></tr>
    <tr><td>Impôts, taxes et versements assimilés <span class="case">244
        (dont CFE {{ eur(L.f2033b.dont_cfe_243) }} — 243)</span></td>
        <td class="num">{{ eur(L.f2033b.impots_244) }}</td></tr>
    <tr><td>Dotations aux amortissements <span class="case">254</span></td>
        <td class="num">{{ eur(L.f2033b.dotations_254) }}</td></tr>
    <tr><td>Total des charges d'exploitation <span class="case">264</span></td>
        <td class="num">{{ eur(L.f2033b.total_charges_264) }}</td></tr>
    <tr><td>Charges financières (intérêts d'emprunt) <span class="case">294</span></td>
        <td class="num">{{ eur(L.f2033b.charges_financieres_294) }}</td></tr>
    <tr class="tot"><td>Bénéfice ou perte (résultat comptable)
        <span class="case">270 / 310 / 312-314</span></td>
        <td class="num">{{ eur(L.f2033b.benefice_ou_perte_310) }}</td></tr>
    <tr><td>Réintégrations — amortissements excédentaires (art. 39 C)
        <span class="case">318</span></td>
        <td class="num">{{ eur(L.f2033b.reintegration_amort_318) }}</td></tr>
    <tr><td>Réintégrations — divers <span class="case">330</span>
        {% for lib, m in L.f2033b.reintegrations_detail %}
          <div class="case">· {{ lib }} : {{ eur(m) }}</div>{% endfor %}</td>
        <td class="num">{{ eur(L.f2033b.reintegration_divers_330) }}</td></tr>
    <tr><td>Déductions <span class="case">350</span>
        {% for lib, m in L.f2033b.deductions_detail %}
          <div class="case">· {{ lib }} : {{ eur(m) }}</div>{% endfor %}</td>
        <td class="num">{{ eur(L.f2033b.deductions_350) }}</td></tr>
    <tr class="tot"><td>Résultat fiscal après imputation
        <span class="case">352 / 370 — le résultat LMNP non professionnel est
        déclaré au cadre I de la 2031 bis</span></td>
        <td class="num">{{ eur(L.f2033b.resultat_fiscal_370) }}</td></tr>
  </table></div>
</div>

<div class="card">
  <div class="card-header">N° 2033-C — Immobilisations & amortissements</div>
  <div class="card-body" style="padding:0"><table>
    <tr><th>Rubrique</th><th class="num">Brut début</th>
        <th class="num">Augment.</th><th class="num">Dimin.</th>
        <th class="num">Brut fin</th>
        <th class="num">Amort. début</th><th class="num">Dotation</th>
        <th class="num">Amort. dimin.</th>
        <th class="num">Amort. fin</th></tr>
    {% for r in L.f2033c.rubriques %}
    <tr><td>{{ r.libelle }} <span class="case">{{ r.case_immo }} /
        {{ r.case_amort }}</span></td>
        <td class="num">{{ eur(r.brut_debut) }}</td>
        <td class="num">{{ eur(r.augmentations) }}</td>
        <td class="num">{{ eur(r.diminutions) }}</td>
        <td class="num">{{ eur(r.brut_fin) }}</td>
        <td class="num">{{ eur(r.amort_debut) }}</td>
        <td class="num">{{ eur(r.dotation) }}</td>
        <td class="num">{{ eur(r.amort_diminutions) }}</td>
        <td class="num">{{ eur(r.amort_fin) }}</td></tr>
    {% endfor %}
    <tr class="tot"><td>TOTAL <span class="case">490-496 / 570-576</span></td>
        <td class="num">{{ eur(L.f2033c.totaux.brut_debut) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.augmentations) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.diminutions) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.brut_fin) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.amort_debut) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.dotation) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.amort_diminutions) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.amort_fin) }}</td></tr>
  </table>
  <table style="margin-top:6px">
    <tr><th>Détail par composant</th><th class="num">Valeur brute</th>
        <th class="num">Durée</th><th class="num">Dotation</th>
        <th class="num">Cumul fin</th><th class="num">VNC fin</th></tr>
    {% for d in L.f2033c.detail_composants %}
    <tr><td>{{ d.libelle }}</td>
        <td class="num">{{ eur(d.valeur_brute) }}</td>
        <td class="num">{{ d.duree or '—' }}</td>
        <td class="num">{{ eur(d.dotation) }}</td>
        <td class="num">{{ eur(d.cumul_fin) }}</td>
        <td class="num">{{ eur(d.vnc_fin) }}</td></tr>
    {% endfor %}
  </table></div>
</div>

<div class="card">
  <div class="card-header">Suivi des reports — art. 39 C (SUIV39C) & déficits LMNP</div>
  <div class="card-body" style="padding:0"><table>
    <tr><th>Article 39 C</th><th class="num">Stock ouverture</th>
        <th class="num">Report de l'année</th>
        <th class="num">Utilisation</th><th class="num">Stock clôture</th></tr>
    <tr><td>Amortissements dont la déduction est écartée</td>
        <td class="num">{{ eur(L.reports.suivi_39c.stock_ouverture) }}</td>
        <td class="num">{{ eur(L.reports.suivi_39c.report_annee) }}</td>
        <td class="num">{{ eur(L.reports.suivi_39c.utilisation_annee) }}</td>
        <td class="num">{{ eur(L.reports.suivi_39c.stock_cloture) }}</td></tr>
    {% if L.reports.sortie_39c %}
    <tr><td colspan="4" style="color:#c5221f">dont <b>perdu à la cession
      d'un bien</b>
      <span class="aide" data-aide-etat="anomalie" data-aide="Les amortissements reportés au titre de l'article 39 C restent rattachés au bien qui les a produits. Quand ce bien sort du patrimoine, le stock qui lui restait ne peut plus être imputé : il est définitivement perdu. Ce montant n'a donc PAS été déduit de votre résultat — c'est lui qui explique la baisse du stock.">?</span></td>
      <td class="num" style="color:#c5221f">−{{ eur(L.reports.sortie_39c) }}</td></tr>
    {% endif %}
  </table>
  <table style="margin-top:6px">
    <tr><th>Déficits LMNP — millésime</th><th class="num">Montant initial</th>
        <th class="num">Solde restant</th><th class="num">Péremption</th></tr>
    {% for d in L.reports.deficits %}
    <tr><td>{{ d.annee_origine }}</td>
        <td class="num">{{ eur(d.montant_initial) }}</td>
        <td class="num">{{ eur(d.solde) }}</td>
        <td class="num">{{ d.annee_expiration }}{% if d.perime %} <b style="color:#c5221f">— périmé</b>{% endif %}</td></tr>
    {% else %}
    <tr><td colspan="4" class="muted">Aucun déficit LMNP en report.</td></tr>
    {% endfor %}
    <tr class="tot"><td>Total déficits reportables</td><td></td>
        <td class="num">{{ eur(L.reports.total_deficits) }}</td><td></td></tr>
  </table></div>
</div>

<div class="card">
  <div class="card-header green">Aide au report — déclaration 2042C-PRO</div>
  <div class="card-body" style="padding:0"><table>
    <tr><th>Case</th><th>Intitulé</th><th class="num">Montant (arrondi €)</th></tr>
    {% if L.aide_2042c.case_5NA %}
    <tr><td><strong>5NA</strong></td><td>Revenus imposables — régime réel</td>
        <td class="num">{{ L.aide_2042c.case_5NA }}</td></tr>{% endif %}
    {% if L.aide_2042c.case_5NY %}
    <tr><td><strong>5NY</strong></td><td>Déficit de l'exercice — cas général</td>
        <td class="num">{{ L.aide_2042c.case_5NY }}</td></tr>{% endif %}
    {% for c in L.aide_2042c.cases_deficits_anterieurs %}
    <tr><td><strong>{{ c.case }}</strong></td>
        <td>Déficit antérieur non encore déduit — millésime {{ c.annee_origine }}</td>
        <td class="num">{{ c.montant }}</td></tr>
    {% endfor %}
  </table>
  <p class="muted" style="padding:10px 12px">{{ L.aide_2042c.note }}</p></div>
</div>

{# Suivi des dépôts : purement déclaratif, hors de l'impression. #}
{% set D = depots_etat(L.annee) %}
<div class="card no-print" id="depots">
  <div class="card-header">Dépôt des déclarations — exercice {{ D.annee }}</div>
  <div class="card-body">
    <p class="muted">Notez ici le dépôt de chaque déclaration, avec la
    référence de l'accusé de réception. Rien n'est transmis : c'est un
    aide-mémoire. Les chiffres calculés au moment de l'enregistrement sont
    conservés, pour vous signaler s'ils changent ensuite.</p>
    {% for a in D.anomalies %}
    <div class="{{ 'flash flash-warn' if a.niveau == 'AVERTISSEMENT' else 'rappel rappel-info' }}">{{ a.message }}</div>
    {% endfor %}
    {% for t in D.types %}
    <h4 style="margin:14px 0 6px">{{ t.libelle }}</h4>
    {% if t.depots %}
    <table>
      <tr><th>Nature</th><th>Date de dépôt</th><th>Référence de l'accusé</th><th>Note</th><th></th></tr>
      {% for d in t.depots %}
      <tr><td>{{ d.nature }}</td><td>{{ d.date_depot }}</td>
          <td>{{ d.reference or '—' }}</td><td>{{ d.note or '' }}</td>
          <td style="text-align:center">
            <form method="post" action="/depots/{{ d.id }}/supprimer" style="margin:0">
              <input type="hidden" name="annee" value="{{ D.annee }}">
              <button type="submit" class="btn-secondaire"
                      data-confirmer="Supprimer ce dépôt ? La ligne sera effacée. Pour corriger une date ou une référence, supprimez puis ressaisissez.">Supprimer</button>
            </form></td></tr>
      {% endfor %}
    </table>
    {% else %}
    <p class="muted">Aucun dépôt enregistré.</p>
    {% endif %}
    {% endfor %}
    {% if D.clos %}
    <form method="post" action="/depots/enregistrer" style="margin-top:16px">
      <input type="hidden" name="annee" value="{{ D.annee }}">
      <div class="form-grid">
        <div><label class="field">Déclaration</label>
          <select name="type" required>
            {% for t in D.types %}<option value="{{ t.code }}">{{ t.libelle }}</option>{% endfor %}
          </select></div>
        <div><label class="field">Nature</label>
          <select name="nature" required>
            <option value="initiale">Initiale</option>
            <option value="rectificative">Rectificative</option>
          </select></div>
        <div><label class="field">Date de dépôt</label>
          <input type="date" name="date_depot" max="{{ D.aujourd_hui }}" required></div>
        <div><label class="field">Référence de l'accusé <span class="opt">(facultatif)</span></label>
          <input type="text" name="reference" maxlength="64"></div>
        <div><label class="field">Note <span class="opt">(facultatif)</span></label>
          <input type="text" name="note" maxlength="200"></div>
      </div>
      <p><button type="submit">Enregistrer le dépôt</button></p>
    </form>
    {% else %}
    <p class="muted">Un dépôt s'enregistre une fois l'exercice clôturé.</p>
    {% endif %}
  </div>
</div>

<div class="card no-print">
  <div class="card-header amber">Télétransmettre cette liasse (obligation légale)</div>
  <div class="card-body">
    <p style="margin-bottom:10px"><strong>Ce logiciel ne télétransmet pas
    (encore) lui-même</strong> : il produit la liasse complète, case par case,
    que vous transmettez ensuite par l'une des deux voies légales. Le dépôt
    papier n'est plus admis (art. 1649 quater B quater CGI — pénalité 0,2 %,
    minimum 60 €).</p>
    <p style="margin-bottom:10px"><strong>1. EFI — saisie en ligne, gratuit
    (recommandé au réel simplifié).</strong> Espace <em>professionnel</em> sur
    impots.gouv.fr → adhérer une fois au service « Déclarer › Résultats » →
    recopier les cases 2031 / 2033-A / B / C ci-dessus (formulaire
    pré-renseigné, totaux automatiques). Délai : 2ᵉ jour ouvré suivant le
    1ᵉʳ mai + 15 jours de tolérance télédéclaration.</p>
    <p style="margin-bottom:10px"><strong>2. EDI-TDFC — via un partenaire
    habilité DGFiP.</strong> La voie qu'empruntent les prestataires de
    comptabilité LMNP (le « N° Interchange » figure sur les liasses qu'ils
    produisent) : expert-comptable ou portail de saisie en ligne à bas coût
    (liste officielle sur impots.gouv.fr).</p>
    <p style="margin-bottom:6px"><strong>Sources officielles :</strong></p>
    <ul style="margin:0 0 10px 20px;line-height:1.7">
      <li><a href="https://bofip.impots.gouv.fr/bofip/7690-PGP.html/identifiant=BOI-BIC-DECLA-30-60-20-20190605"
        target="_blank">BOFiP BOI-BIC-DECLA-30-60-20</a> — présentation de
        l'EFI : déclaration de résultat BIC/RSI en ligne, gratuite, depuis
        l'espace professionnel ;</li>
      <li><a href="https://www.impots.gouv.fr/professionnel/teleprocedures-efi-ou-edi"
        target="_blank">impots.gouv.fr — Téléprocédures EFI ou EDI</a> —
        création de l'espace, adhésion au service « Déclarer le résultat »
        (2031 au RSI) ;</li>
      <li><a href="https://www.impots.gouv.fr/professionnel/obligations-de-teleprocedures-0"
        target="_blank">impots.gouv.fr — Obligations de téléprocédures</a> —
        tableau des obligations et solutions TDFC avec saisie en ligne ;</li>
      <li><a href="https://entreprendre.service-public.gouv.fr/vosdroits/F23543"
        target="_blank">Service-Public F23543</a> — les deux modes EFI/EDI ;</li>
      <li><a href="https://entreprendre.service-public.gouv.fr/vosdroits/R14668"
        target="_blank">Service-Public R14668</a> — liste des démarches EFI,
        dont la « déclaration de résultats des entrepreneurs individuels BIC
        au régime simplifié (formulaire 2031) ».</li>
    </ul>
    <p>N'oubliez pas ensuite le report sur la <strong>2042C-PRO</strong> du
    foyer — dans votre espace <em>particulier</em>, cases pré-calculées
    ci-dessus.</p>
  </div>
</div>

<p class="muted no-print" style="margin:8px 0 24px">
⚠️ Liasse générée automatiquement sur les modèles disponibles à la date de
version du logiciel — peut ne pas correspondre aux derniers modèles en date.
À faire valider par un expert-comptable avant tout dépôt (télétransmission
EDI-TDFC non incluse).</p>
</div>
"""


PAGE_REGLEMENTATION = """
<div class="card">
  <div class="card-header">⚖️ Règles fiscales versionnées</div>
  <div class="card-body">
    <p style="margin-bottom:12px">Aucun seuil ni durée n'est figé dans le code :
    chaque règle est <strong>datée</strong>. Quand une loi de finances change une
    valeur, enregistrez la nouvelle version avec sa <strong>date d'effet</strong> —
    les exercices passés restent calculés avec les règles de leur millésime.</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <tr style="background:#f7f8fa"><th style="text-align:left;padding:6px 10px">Règle</th>
          <th style="text-align:right;padding:6px 10px">Valeur</th>
          <th style="padding:6px 10px">En vigueur</th>
          <th style="text-align:left;padding:6px 10px">Ce que la règle change</th>
          <th style="text-align:left;padding:6px 10px">Référence légale</th></tr>
      {% for r in regles %}
      <tr style="border-bottom:1px solid #e4e7ec{{ ';color:#8a93a3' if r.date_fin else '' }}">
        <td style="padding:6px 10px">{{ r.libelle }}
            <span class="opt">({{ r.cle }})</span></td>
        <td style="padding:6px 10px;text-align:right">{{ '%g'|format(r.valeur) }}</td>
        <td style="padding:6px 10px;white-space:nowrap">{{ r.date_debut }} →
            {{ r.date_fin or 'en vigueur' }}</td>
        <td style="padding:6px 10px"><strong>{{ r.impact_module }}</strong>
            <div class="opt">{{ r.impact_effet }}</div></td>
        <td style="padding:6px 10px">{{ r.reference }}
            {% if r.commentaire %}<div class="opt">{{ r.commentaire }}</div>{% endif %}</td>
      </tr>
      {% endfor %}
    </table>

    <form method="post" action="/reglementation/regle" class="mt"
          style="display:grid;grid-template-columns:2fr 1fr 1fr 2fr auto;gap:10px;align-items:end">
      <div><label class="field">Règle</label>
        <select name="cle" required>
          {% for cle, lib in libelles_regles %}
          <option value="{{ cle }}">{{ lib }}</option>{% endfor %}
        </select></div>
      <div><label class="field">Nouvelle valeur</label>
        <input type="number" step="any" name="valeur" required></div>
      <div><label class="field">Date d'effet</label>
        <input type="date" name="date_debut" required></div>
      <div><label class="field">Référence légale <span class="opt">(LF, art. CGI, BOFiP)</span></label>
        <input name="reference" placeholder="ex. LF 2027, art. 12"></div>
      <button class="btn btn-success">Enregistrer la version</button>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header">Catégories d'opérations personnalisées</div>
  <div class="card-body">
    <p style="margin-bottom:12px">Une disposition future crée une nouvelle
    charge ou un nouveau produit ? Ajoutez la catégorie ici : elle apparaît
    immédiatement dans la liste déroulante de saisie, avec son compte, sa
    périodicité, et si besoin une <strong>réintégration fiscale automatique</strong>
    à la clôture.</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <tr style="background:#f7f8fa"><th style="text-align:left;padding:6px 10px">Libellé</th>
          <th style="padding:6px 10px">Clé</th><th style="padding:6px 10px">Compte</th>
          <th style="padding:6px 10px">Nature</th><th style="padding:6px 10px">Périodicité</th>
          <th style="padding:6px 10px">Retraitement</th></tr>
      {% for g in persos %}
      <tr style="border-bottom:1px solid #e4e7ec">
        <td style="padding:6px 10px">{{ g.libelle }}</td>
        <td style="padding:6px 10px">{{ g.cle }}</td>
        <td style="padding:6px 10px">{{ g.compte_num }}</td>
        <td style="padding:6px 10px">{{ g.nature }}</td>
        <td style="padding:6px 10px">{{ g.periodicite }}</td>
        <td style="padding:6px 10px">{{ 'réintégration' if g.retraitement else '—' }}</td>
      </tr>
      {% else %}
      <tr><td colspan="6" class="muted" style="padding:6px 10px">Aucune catégorie
          personnalisée — les 37 gabarits standard couvrent l'existant.</td></tr>
      {% endfor %}
    </table>

    <form method="post" action="/reglementation/gabarit" class="mt"
          style="display:grid;grid-template-columns:2fr 1.5fr 1fr 1fr auto auto;gap:10px;align-items:end">
      <div><label class="field">Libellé</label>
        <input name="libelle" required placeholder="ex. Éco-contribution meublés 2028"></div>
      <div><label class="field">Compte</label>
        <select name="compte_num" required>
          {% for num, lib in comptes %}
          <option value="{{ num }}">{{ num }} — {{ lib }}</option>{% endfor %}
        </select></div>
      <div><label class="field">Nature</label>
        <select name="nature"><option value="charge">Charge</option>
          <option value="produit">Produit</option></select></div>
      <div><label class="field">Périodicité</label>
        <select name="periodicite"><option value="variable">Variable</option>
          <option value="mensuel">Mensuelle</option>
          <option value="annuel">Annuelle</option></select></div>
      <label style="display:flex;align-items:center;gap:6px;white-space:nowrap">
        <input type="checkbox" name="reintegration" value="1"> Réintégration fiscale</label>
      <button class="btn btn-success">Ajouter</button>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header">Plan de comptes — ajouter un compte</div>
  <div class="card-body">
    <form method="post" action="/reglementation/compte"
          style="display:grid;grid-template-columns:1fr 2fr 1fr auto;gap:10px;align-items:end">
      <div><label class="field">Numéro (6 chiffres)</label>
        <input name="numero" required pattern="[1-7][0-9]{5}" placeholder="637800"></div>
      <div><label class="field">Libellé</label>
        <input name="libelle" required placeholder="Nouvelle taxe secteur locatif"></div>
      <div><label class="field">Type</label>
        <select name="type"><option value="charge">Charge</option>
          <option value="produit">Produit</option><option value="actif">Actif</option>
          <option value="passif">Passif</option>
          <option value="amortissement">Amortissement</option></select></div>
      <button class="btn">Créer le compte</button>
    </form>
    <p class="muted mt">Le compte devient utilisable par les gabarits
    personnalisés et l'export FEC. Les comptes existants ne sont jamais modifiés.</p>
  </div>
</div>
"""


PAGE_SANDBOX = """
<div class="card" style="max-width:760px">
  <div class="card-header">🧪 Bac à sable — dossier d'essai jetable</div>
  <div class="card-body">
    <p style="margin-bottom:14px">
      Le bac à sable est un <strong>dossier comptable séparé</strong>
      (<code>bac_a_sable.db</code>), totalement isolé de votre comptabilité
      réelle. Vous pouvez y dérouler <strong>tout le processus</strong> :
      ouvrir un exercice du 1<sup>er</sup> janvier au 31 décembre, saisir
      librement, créer des immobilisations, lancer les contrôles, clôturer,
      exporter le FEC — puis tout effacer d'un clic.
    </p>

    {% if actif %}
      <div class="flash flash-warn" style="margin-bottom:14px">
        Vous êtes actuellement <strong>dans le bac à sable</strong>. Tous les
        menus (Saisie, Immobilisations, Clôture, Nouvel exercice) opèrent sur
        le dossier d'essai.
      </div>
      <form method="post" action="/bac-a-sable/quitter" style="display:inline">
        <button class="btn">← Revenir au dossier réel</button>
      </form>
    {% else %}
      <form method="post" action="/bac-a-sable/activer" style="display:inline">
        <button class="btn btn-success">Entrer dans le bac à sable →</button>
      </form>
    {% endif %}
  </div>
</div>

<div class="card" style="max-width:760px">
  <div class="card-header">Réinitialiser le dossier d'essai</div>
  <div class="card-body">
    <p style="margin-bottom:14px" class="muted">
      La réinitialisation efface <em>uniquement</em> <code>bac_a_sable.db</code> ;
      la comptabilité réelle n'est jamais touchée.
    </p>
    <form method="post" action="/bac-a-sable/reset" style="display:inline">
      <input type="hidden" name="mode" value="blanc">
      <button class="btn">Réinitialiser — dossier vierge (mode blanc)</button>
    </form>
    <form method="post" action="/bac-a-sable/reset" style="display:inline;margin-left:8px">
      <input type="hidden" name="mode" value="demo">
      <button class="btn">Réinitialiser — dossier d'exemple (mode démo)</button>
    </form>
  </div>
</div>

<div class="card" style="max-width:760px">
  <div class="card-header green">Audit automatique du cycle complet</div>
  <div class="card-body">
    <p style="margin-bottom:14px">
      Rejoue l'intégralité du processus sur une base jetable et vérifie chaque
      étape : ouverture, saisie 12 mois, immobilisations, contrôles
      (y compris détection d'anomalies injectées), clôture, limitation 39 C,
      déficits LMNP pluri-exercices, export et validation FEC.
    </p>
    <form method="post" action="/bac-a-sable/audit">
      <button class="btn btn-success">Lancer l'audit complet</button>
    </form>
    {% if rapport %}
    <pre style="margin-top:16px;background:#1a1a1a;color:#d8e8d8;padding:16px;
                border-radius:6px;overflow-x:auto;font-size:12.5px;
                line-height:1.55">{{ rapport }}</pre>
    {% endif %}
  </div>
</div>
"""


PAGE_ARCHIVES = """
<div class="card"><div class="card-body">
  <h2>Fichiers des écritures comptables (FEC) archivés</h2>
  <p class="muted">Un FEC est produit et horodaté à <b>chaque clôture</b>, avec
  son empreinte SHA-256 au manifeste. C'est le fichier que l'administration
  demande en cas de contrôle (art. L. 47 A-I du LPF) : conservez-en une copie
  hors de cet ordinateur.</p>
  {% if not fichiers %}
    <p>Aucune archive pour l'instant : le premier FEC sera produit à votre
    prochaine clôture.</p>
  {% else %}
  <table>
    <thead><tr><th>Fichier</th><th>Taille</th><th>Empreinte SHA-256</th>
      <th></th></tr></thead>
    <tbody>
    {% for f in fichiers %}
      <tr><td>{{ f.nom }}</td><td class="muted">{{ f.ko }} Ko</td>
        <td class="muted" style="font-family:monospace">{{ f.sha }}…</td>
        <td style="text-align:right">
          <a href="/archives/{{ f.nom }}">Télécharger</a></td></tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}
  <p class="opt">Dossier : {{ dossier }}</p>
</div></div>
"""


PAGE_SAUVEGARDES_SECTION = """
<div class="card"><div class="card-body">
  <h2>Sauvegardes du dossier actif</h2>
  <p class="muted">Une sauvegarde automatique est faite chaque jour au
  lancement, plus une avant chaque clôture. <b>Restaurer</b> remet le dossier
  dans l'état de la sauvegarde choisie — l'état actuel est lui-même
  sauvegardé d'abord (« avant-restauration ») : l'opération est réversible.
  C'est le geste à faire après une clôture lancée par erreur ou une série de
  saisies malheureuses.</p>
  {% if not sauvegardes %}
    <p>Aucune sauvegarde pour l'instant : elles apparaîtront au prochain
    lancement du logiciel.</p>
  {% else %}
  <table>
    <thead><tr><th>Sauvegarde</th><th>Taille</th><th></th></tr></thead>
    <tbody>
    {% for s in sauvegardes[:15] %}
      <tr>
        <td>{{ s['nom'] }}</td>
        <td class="muted">{{ s['taille_ko'] }} Ko</td>
        <td style="text-align:right">
          <form method="post" action="/sauvegardes/restaurer" style="margin:0">
            <input type="hidden" name="nom" value="{{ s['nom'] }}">
            <button type="submit" class="btn-secondaire"
              data-confirmer="Restaurer « {{ s['nom'] }} » ? Le dossier reviendra à cet état. L'état actuel sera d'abord mis de côté (avant-restauration).">Restaurer</button>
          </form>
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}
</div></div>
"""


PAGE_VERSION_TROP_RECENTE = """
<div class="card"><div class="card-body">
  <h2>Dossier plus récent que le logiciel</h2>
  <p>{{ msg }}</p>
  <!-- Une issue est INDISPENSABLE ici : chaque lien de la barre de
       navigation repasse par le garde qui a produit cette page, et le
       cookie de dossier vaut 180 jours. Sans ce bouton, le logiciel
       devenait inutilisable — pour TOUS ses dossiers — jusqu'à ce que
       l'utilisateur sache supprimer un cookie dans son navigateur. -->
  <form method="post" action="/dossiers/retour-principal">
    <button type="submit">Revenir au dossier principal</button>
  </form>
  <p class="muted" style="margin-top:14px">Pour rouvrir ce dossier,
  installez la version du logiciel qui l'a produit.</p>
</div></div>
"""

PAGE_DOSSIER_ABSENT = """
<div class="card"><div class="card-body">
  <h2>Fichier du dossier introuvable</h2>
  <p>Le dossier « <b>{{ slug }}</b> » est enregistré, mais son fichier est
  introuvable :</p>
  <p><code>{{ chemin }}</code></p>
  <p><b>Rien n'a été créé ni modifié.</b> Cette situation est le plus
  souvent temporaire : disque externe débranché, dossier synchronisé pas
  encore redescendu, partage réseau non monté. Rebranchez le support, puis
  rechargez la page.</p>
  <p class="muted">Le logiciel créait auparavant une base vierge à cette
  place : la comptabilité paraissait perdue, et le vrai fichier se
  trouvait masqué.</p>
  <form method="post" action="/dossiers/retour-principal">
    <button type="submit">Revenir au dossier principal</button>
  </form>
</div></div>
"""

PAGE_QUITTANCES = """
<div class="card">
  <div class="card-header">Locataires</div>
  <div class="card-body">
    {% if locataires %}
    <table>
      <thead><tr><th>Nom</th><th>Logement</th><th>Entrée</th><th>Sortie</th>
        <th class="num">Loyer</th><th class="num">Charges</th></tr></thead>
      <tbody>
      {% for l in locataires %}
        <tr><td><b>{{ l.nom }}</b></td><td>{{ l.bien }}</td>
          <td>{{ l.date_entree }}</td>
          <td>{{ l.date_sortie or '—' }}
            {% if not l.date_sortie %}<span class="badge badge-ok">en cours</span>{% endif %}</td>
          <td class="num">{{ '%.2f'|format(l.loyer_mensuel or 0) }} €</td>
          <td class="num">{{ '%.2f'|format(l.charges_mensuelles or 0) }} €</td></tr>
      {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p class="muted">Aucun locataire enregistré.</p>
    {% endif %}

    <h2 style="font-size:1em;margin:18px 0 8px">Ajouter un locataire</h2>
    <form method="post" action="/quittances/locataire">
      <div class="grid3">
        <div><label class="field">Nom et prénom</label>
          <input name="nom" required placeholder="DUPONT Jean"></div>
        <div><label class="field">Logement</label>
          <select name="bien_id" required>
            {% for b in biens %}<option value="{{ b['id'] }}">{{ b['libelle'] }}</option>{% endfor %}
          </select></div>
        <div><label class="field">Date d'entrée</label>
          <input type="date" name="date_entree" required></div>
        <div><label class="field">Date de sortie <span class="opt">(vide si en cours)</span></label>
          <input type="date" name="date_sortie"></div>
        <div><label class="field">Loyer mensuel hors charges (€)</label>
          <input type="number" step="0.01" name="loyer_mensuel"></div>
        <div><label class="field">Provision de charges (€)</label>
          <input type="number" step="0.01" name="charges_mensuelles" value="0"></div>
      </div>
      <p><button type="submit">Ajouter</button></p>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header">Émettre une quittance</div>
  <div class="card-body">
    <p class="muted">Les montants sont lus dans vos ÉCRITURES : la quittance
    reflète la comptabilité, elle ne la double pas. Laissez les champs vides
    pour reprendre le loyer encaissé sur la période ; renseignez-les pour
    forcer un montant.</p>
    {% if locataires %}
    <form method="post" action="/quittances/emettre">
      <div class="grid3">
        <div><label class="field">Locataire</label>
          <select name="locataire_id" required>
            {% for l in locataires %}<option value="{{ l.id }}">{{ l.nom }} — {{ l.bien }}</option>{% endfor %}
          </select></div>
        <div><label class="field">Période (mois)</label>
          <input type="month" name="periode" required></div>
        <div><label class="field">Date de paiement <span class="opt">(facultatif)</span></label>
          <input type="date" name="date_paiement"></div>
        <div><label class="field">Loyer (€) <span class="opt">(vide = depuis les écritures)</span></label>
          <input type="number" step="0.01" name="loyer"></div>
        <div><label class="field">Charges (€) <span class="opt">(vide = depuis les écritures)</span></label>
          <input type="number" step="0.01" name="charges"></div>
      </div>
      <p><button type="submit">Émettre la quittance</button></p>
    </form>
    {% else %}
    <p class="muted">Enregistrez d'abord un locataire.</p>
    {% endif %}
  </div>
</div>

<div class="card">
  <div class="card-header">Quittances émises</div>
  <div class="card-body">
    <form method="get" style="margin-bottom:12px">
      <label class="field" style="display:inline">Année</label>
      <select name="an" onchange="this.form.submit()">
        <option value="">toutes</option>
        {% for a in annees_quittances %}
        <option value="{{ a }}" {{ 'selected' if a|string == an_filtre else '' }}>{{ a }}</option>
        {% endfor %}
      </select>
      <span class="muted" style="margin-left:10px">Toutes les quittances
      restent consultables et réimprimables, sans limite d'ancienneté.</span>
    </form>
    {% if quittances %}
    <table>
      <thead><tr><th>N°</th><th>Locataire</th><th>Logement</th><th>Période</th>
        <th class="num">Loyer</th><th class="num">Charges</th>
        <th class="num">Total</th><th>Émise le</th><th></th></tr></thead>
      <tbody>
      {% for q in quittances %}
        <tr><td><b>{{ '%05d'|format(q.numero) }}</b></td>
          <td>{{ q.locataire }}</td><td class="muted">{{ q.bien }}</td>
          <td>{{ q.periode }}</td>
          <td class="num">{{ '%.2f'|format(q.loyer) }} €</td>
          <td class="num">{{ '%.2f'|format(q.charges) }} €</td>
          <td class="num"><b>{{ '%.2f'|format(q.loyer + q.charges) }} €</b></td>
          <td>{{ q.date_emission }}</td>
          <td><a class="btn" href="/quittance/{{ q.id }}" target="_blank">Imprimer</a></td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
    <p class="muted" style="font-size:.88em">La numérotation est continue et
    sans trou, dans une série UNIQUE partagée par tous vos logements —
    c'est ce qui la rend vérifiable. Elle suit l'ordre d'ÉMISSION, comme
    une numérotation de factures : une quittance établie aujourd'hui pour
    un mois ancien reçoit donc le numéro suivant, et non un numéro
    intercalé.</p>
    {% else %}
    <p class="muted">Aucune quittance émise.</p>
    {% endif %}
  </div>
</div>

"""

PAGE_QUITTANCE_IMPRIMABLE = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Quittance n° {{ '%05d'|format(q.numero) }}</title>
<style>
  body { font-family: Georgia, serif; max-width: 17cm; margin: 2cm auto;
         color: #1a1a1a; line-height: 1.55; }
  h1 { font-size: 1.35em; margin: 0 0 4px; }
  .num { color: #555; margin-bottom: 26px; }
  .parties { display: flex; justify-content: space-between; gap: 30px;
             margin-bottom: 26px; }
  .bloc { font-size: .95em; }
  .bloc b { display: block; margin-bottom: 3px; }
  table { width: 100%; border-collapse: collapse; margin: 18px 0; }
  td, th { padding: 7px 10px; border-bottom: 1px solid #ddd; }
  th { text-align: left; background: #f4f4f6; }
  .droite { text-align: right; }
  .total td { font-weight: bold; border-top: 2px solid #333; border-bottom: 0; }
  .mentions { font-size: .82em; color: #555; margin-top: 30px;
              border-top: 1px solid #ddd; padding-top: 12px; }
  @media print { body { margin: 1.2cm; } .noprint { display: none; } }
</style></head><body>
<p class="noprint" style="text-align:right">
  <button onclick="window.print()">Imprimer</button></p>

{% if q.ecart_ecritures %}
<p class="noprint" style="background:#fdf3f2;border-left:4px solid #c5221f;
   padding:10px 14px;font-size:.9em">
  <b>Cette quittance ne correspond plus à vos écritures.</b><br>
  {{ q.ecart_ecritures.message }}</p>
{% endif %}

<h1>{{ q.titre_document or 'Quittance de loyer' }}</h1>
<p class="num">N° {{ '%05d'|format(q.numero) }} — {{ q.periode_lettres }}</p>

{% if q.type_document == 'recu' %}
<p style="background:#fff8ee;border-left:4px solid #e8710a;padding:10px 14px">
  <b>Paiement partiel.</b> Ce document n'est pas une quittance : il atteste
  d'un versement reçu, sans solder la période.
  {% if q.reste_du and q.reste_du > 0 %}Reste dû au titre de
  {{ q.periode_lettres }} : <b>{{ '%.2f'|format(q.reste_du) }} €</b>.{% endif %}
  Une quittance sera établie lorsque la période sera intégralement réglée
  (article 21 de la loi du 6 juillet 1989).</p>
{% endif %}

{% if q.referentiel_modifie %}
<p class="noprint" style="background:#fff8ee;border-left:4px solid #e8710a;
   padding:10px 14px;font-size:.9em">
  Depuis l'émission de ce document, {{ q.referentiel_modifie|join(' et ') }}
  a changé dans le dossier. Ce qui est imprimé ci-dessous est l'identité
  <b>figée à l'émission</b> — celle du document réellement remis.</p>
{% endif %}

<div class="parties">
  <div class="bloc"><b>Bailleur</b>
    {{ q.bailleur.nom }}<br>{{ q.bailleur.adresse or '' }}</div>
  <div class="bloc"><b>Locataire</b>
    {{ q.locataire }}<br>{{ q.bien_adresse or q.bien }}</div>
</div>

<p>Je soussigné(e) <b>{{ q.bailleur.nom }}</b>, bailleur du logement situé
<b>{{ q.bien_adresse or q.bien }}</b>, déclare avoir reçu de
<b>{{ q.locataire }}</b> la somme de
<b>{{ '%.2f'|format(q.total) }} €</b>, au titre du loyer et des charges de
la période de <b>{{ q.periode_lettres }}</b>,
{% if q.type_document == 'recu' %}à valoir sur les sommes dues pour cette
période, sans que ce versement en constitue quittance.
{% else %}et lui en donne quittance,{% endif %}
sous réserve de tous mes droits.</p>

{% if not q.bien_adresse %}
<p class="noprint" style="background:#fff8ee;border-left:4px solid #e8710a;
   padding:10px 14px;font-size:.9em">
  <b>Adresse du logement absente.</b> Le libellé interne
  « {{ q.bien }} » est imprimé à sa place : renseignez l'adresse postale du
  bien dans la page Immobilisations avant de remettre ce document.</p>
{% endif %}

<table>
  <tr><th>Désignation</th><th class="droite">Montant</th></tr>
  <tr><td>Loyer hors charges</td>
      <td class="droite">{{ '%.2f'|format(q.loyer) }} €</td></tr>
  <tr><td>Provision pour charges</td>
      <td class="droite">{{ '%.2f'|format(q.charges) }} €</td></tr>
  <tr class="total"><td>Total réglé</td>
      <td class="droite">{{ '%.2f'|format(q.total) }} €</td></tr>
</table>

<p>{% if q.date_paiement %}Paiement reçu le {{ q.date_paiement }}.{% endif %}
Fait le {{ q.date_emission }}.</p>

<p style="margin-top:38px">Signature du bailleur :</p>

<p class="mentions">
  La présente quittance annule tous les reçus qui auraient pu être établis
  précédemment pour la même période. Elle distingue le loyer des charges,
  conformément à l'article 21 de la loi n° 89-462 du 6 juillet 1989, qui
  impose au bailleur de la transmettre gratuitement au locataire qui en
  fait la demande.
</p>
</body></html>
"""

PAGE_DEMARRAGE = """
<div class="card" style="border-left:5px solid #ffd54f;background:#fffdf3">
  <div class="card-body">
    <h2 style="margin-top:0">Bienvenue — configurons votre dossier
      <span class="aide" data-aide="Vous reprenez une comptabilite existante ? L'ordre compte : 1) enregistrez l'identite ci-dessous ; 2) saisissez TOUTES les immobilisations, dans l'ordre d'acquisition, page Immobilisations ; 3) seulement ensuite, importez vos FEC anterieurs depuis l'onglet Nouvel exercice, du plus ancien au plus recent. Un FEC importe avant les immobilisations laisse un bilan que le tableau 2033-C contredit.">?</span></h2>
    <p>Ce dossier est vierge. Une seule chose est nécessaire pour commencer :
    l'identité sous laquelle vous déclarez.</p>

    <form method="post" action="/immobilisations/exploitant">
      <input type="hidden" name="retour" value="saisie">
      <div class="grid3">
        <div><label class="field">Nom de l'exploitant
          <span class="aide" data-aide="Le nom sous lequel l'activité est déclarée. Pour un particulier, vos nom et prénom ; pour une société, sa dénomination. Il apparaît sur la liasse fiscale.">?</span></label>
          <input name="nom" required placeholder="NOM Prénom"></div>
        <div><label class="field">SIREN
          <span class="aide" data-aide="Les 9 chiffres attribués lors de la déclaration d'activité auprès du guichet unique de l'INPI. Il figure sur votre avis de situation SIRENE et sur vos avis de CFE.">?</span></label>
          <input name="siren" required pattern="[0-9]{9}"
                 title="9 chiffres" placeholder="123456789"></div>
        <div><label class="field">Adresse d'activité
          <span class="aide" data-aide="L'adresse déclarée pour l'activité de location meublée. Souvent celle du bien loué, ou votre domicile selon ce que vous avez déclaré.">?</span></label>
          <input name="adresse" placeholder="12 rue Exemple, 63000 Clermont-Ferrand"></div>
      </div>
      <p><button type="submit">Enregistrer et commencer</button></p>
    </form>

    <div style="background:#f0f6fb;border-left:4px solid #1a73e8;
                padding:10px 14px;margin-top:6px">
      <b>L'exercice est déjà ouvert.</b> Vous n'avez rien à créer : un
      exercice a été ouvert automatiquement à la création du dossier, et
      vous pourrez saisir dès l'étape suivante. L'onglet
      <i>Nouvel exercice</i> ne sert qu'à l'ANNÉE SUIVANTE, une fois la
      précédente clôturée — ou à reprendre un historique depuis un FEC.
    </div>

    <p class="muted" style="margin-top:14px">Ensuite : créez votre bien dans
    <i>Immobilisations</i> et ventilez son prix d'acquisition, puis saisissez
    vos loyers et vos charges. Pour voir le logiciel à l'œuvre sans rien
    risquer, le <a href="/bac-a-sable">bac à sable</a> contient une année
    complète déjà tenue.</p>
  </div>
</div>

<div class="card">
  <div class="card-header amber">Reprendre une comptabilité existante —
    l'ordre des trois étapes</div>
  <div class="card-body">
    <p>Vous venez d'un autre logiciel ou d'un prestataire, et vous voulez
    importer vos FEC ? <b>Ne commencez pas par l'import.</b> Rien ne
    l'interdit, mais l'import seul reconstitue les ÉCRITURES sans le plan
    d'amortissement qui les explique : le bilan porterait des immobilisations
    que le tableau 2033-C ne saurait pas dérouler, et l'écart ne se résorbe
    pas tout seul.</p>
    <ol style="line-height:1.8;padding-left:20px">
      <li><b>Votre identité</b> — nom, SIREN, adresse, dans le cadre
        ci-dessus. C'est fait en une minute.</li>
      <li><b>Vos immobilisations</b>, page
        <a href="/immobilisations">Immobilisations</a> :
        créez chaque bien, puis ventilez son prix d'acquisition en
        composants (terrain, gros œuvre, agencements, mobilier…).
        <b>Dans l'ordre d'acquisition</b>, du plus ancien au plus récent.
        Une valeur ou une durée mal saisie se corrige ou se supprime tant
        que l'exercice n'est pas clôturé — ne restez pas bloqué dessus.</li>
      <li><b>Vos FEC antérieurs</b>, onglet
        <a href="/exercice/nouveau">Nouvel exercice</a> — l'import s'y
        trouve, et nulle part ailleurs. Rejouez-les
        <b>du plus ancien au plus récent</b>, un exercice à la fois.</li>
    </ol>
    <p class="muted">Ensuite seulement, page Immobilisations, le bouton
    « Reprendre les amortissements antérieurs » aligne les comptes 28 sur
    le plan : c'est l'étape qui réconcilie le bilan et le 2033-C, et elle
    suppose que le plan soit juste — donc que les deux étapes précédentes
    soient faites.</p>
  </div>
</div>

"""

PAGE_DOSSIERS = """
<div class="card">
  <div class="card-header">📁 Dossiers comptables</div>
  <div class="card-body">
    <p style="margin-bottom:12px">Chaque dossier est une <strong>comptabilité
    indépendante</strong> (sa base, ses sauvegardes, ses archives FEC). Le
    dossier actif est indiqué dans l'en-tête ; il reste actif jusqu'à ce que
    vous en ouvriez un autre.</p>
    <table>
      <thead><tr><th>Nom</th><th>Emplacement</th>
        <th style="text-align:right">Taille</th><th></th><th></th></tr></thead>
      <tbody>
      {% for d in liste %}
      <tr>
        <td><strong>{{ d.nom }}</strong>
          {% if d.slug == actif %}<span class="badge badge-ok">actif</span>{% endif %}
          {% if not d.existe %}<span class="badge badge-clos">base absente</span>{% endif %}
        </td>
        <td class="muted" style="font-size:12px">{{ d.chemin }}</td>
        <td style="text-align:right">{{ '%.1f'|format(d.taille / 1024) }} Ko</td>
        <td>
          {% if d.slug != actif %}
          <form method="post" action="/dossiers/ouvrir" style="display:inline">
            <input type="hidden" name="slug" value="{{ d.slug }}">
            <button type="submit" class="btn">Ouvrir</button>
          </form>
          {% endif %}
        </td>
        <td>
          {% if d.slug != 'principal' %}
          <form method="post" action="/dossiers/renommer"
                style="display:flex;gap:6px">
            <input type="hidden" name="slug" value="{{ d.slug }}">
            <input type="text" name="nom" value="{{ d.nom }}" style="width:160px">
            <button type="submit" class="btn">Renommer</button>
          </form>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<div class="card" style="max-width:480px">
  <div class="card-header green">Créer un nouveau dossier</div>
  <div class="card-body">
    <form method="post" action="/dossiers/creer">
      <label class="field">Nom du dossier</label>
      <input type="text" name="nom" placeholder="ex. Studio Nancy" required
             maxlength="60">
      <p class="muted" style="font-size:12px;margin-top:6px">Le dossier est
      créé vierge (plan de comptes et journaux installés, aucune écriture).
      Pour repartir d'une clôture existante, utilisez ensuite « Nouvel
      exercice » avec reprise d'un FEC.</p>
      <button type="submit" class="btn btn-success mt">Créer le dossier</button>
    </form>
  </div>
</div>
"""


PAGE_PENSE_BETE = """
<div class="card"><div class="card-body">
  <h2>Pense-bête — à faire manuellement</h2>
  <p class="muted">Le logiciel tient la comptabilité ; déclarer, payer et
  informer les administrations restent des gestes manuels. Rappels croisant
  le calendrier et l'état de ce dossier — dates indicatives, à vérifier sur
  impots.gouv.fr.</p>
  {% if not rappels %}
    <p>✅ Rien de particulier à signaler en ce moment.</p>
  {% endif %}
  {% for r in rappels %}
    <div class="rappel rappel-{{ r['niveau'] }}">
      <div class="rappel-titre">{{ badge[r['niveau']] }} {{ r['titre'] }}</div>
      <div class="rappel-detail">{{ r['detail'] }}</div>
    </div>
  {% endfor %}
</div></div>

<div class="card">
  <div class="card-header">Actualités réglementaires</div>
  <div class="card-body">
    <p class="muted">Faits datés, vérifiés le {{ actualites.verifie_le }}.
    Contrairement à la relecture ci-dessous, ils périment : la page
    <a href="/veille">Veille fiscale</a> sert à les remettre en question.</p>

    {% for a in actualites.faits %}
    <div style="border-left:4px solid #1a73e8;background:#f5f9ff;
                padding:12px 16px;margin-bottom:14px">
      <h2 style="margin:0 0 6px;font-size:1.02em">{{ a.titre }}</h2>
      <p style="margin:0 0 8px"><b>{{ a.resume }}</b></p>
      <p class="muted" style="white-space:pre-line;margin:0">{{ a.detail }}</p>
      {% if a.sources %}
      <p class="muted" style="font-size:.86em;margin:10px 0 0">
        <b>Sources :</b> {{ a.sources|join(' · ') }}</p>
      {% endif %}
    </div>
    {% endfor %}

    <h2 style="font-size:1em;margin:18px 0 8px">Échéances à connaître</h2>
    <table>
      <thead><tr><th>Quand</th><th>Quoi</th><th>Où</th></tr></thead>
      <tbody>
      {% for e in actualites.echeances %}
        <tr><td>{{ e.quand }}</td><td>{{ e.quoi }}</td>
            <td class="muted">{{ e.ou }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
    <p class="muted" style="font-size:.86em">Les dates de dépôt sont
    publiées chaque année par l'administration et varient selon le
    département : vérifiez le calendrier de l'année en cours.</p>
  </div>
</div>

<div class="card">
  <div class="card-header">Mes notes personnelles</div>
  <div class="card-body">
    <p class="muted">Cet espace est à vous : notez ici ce que votre veille
    vous apprend, les questions à poser, les points à vérifier l'an
    prochain. Le contenu est conservé dans votre dossier — il suit vos
    sauvegardes et vos restaurations, et ne quitte jamais votre
    ordinateur.</p>
    <form method="post" action="/pense-bete/notes">
      <textarea name="notes" rows="12" style="width:100%;font-family:inherit;
                font-size:.95em;line-height:1.5"
                placeholder="Ex. : 13/08 — vérifié la plateforme agréée pour la réception des factures, inscription faite.&#10;Question au comptable : les frais de notaire de 2021 sont-ils bien reportés ?">{{ notes }}</textarea>
      <p><button type="submit">Enregistrer mes notes</button>
         <span class="muted" style="margin-left:10px">Dernier
         enregistrement conservé dans le dossier courant.</span></p>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header">Les oublis les plus fréquents — relecture avant clôture</div>
  <div class="card-body">
    <p class="muted">Ces points ne dépendent pas de votre dossier : ce sont
    les fautes que commettent le plus souvent les loueurs meublés au réel.
    Ils servent de relecture, pas de conseil personnalisé — en cas de doute
    sur l'un d'eux, la question mérite d'être posée à un professionnel.</p>
    {% for groupe in oublis %}
    <h2 style="font-size:1em;margin:18px 0 8px">{{ groupe.moment }}</h2>
    {% for p in groupe.points %}
    <details style="margin-bottom:6px">
      <summary style="cursor:pointer;font-weight:600">{{ p.titre }}</summary>
      <p class="muted" style="margin:6px 0 0 16px">{{ p.detail }}</p>
      {% if p.sources %}
      <p class="muted" style="margin:6px 0 0 16px;font-size:.86em">
        <b>Sources :</b> {{ p.sources|join(' · ') }}</p>
      {% endif %}
    </details>
    {% endfor %}
    {% endfor %}
  </div>
</div>
"""


PAGE_VEILLE = """
<div class="card"><div class="card-body">
  <h2>Veille fiscale — ce logiciel ne se met pas à jour tout seul</h2>
  <p class="muted">Les règles de calcul sont <b>datées</b> : le moteur applique
  celle qui était en vigueur pour l'exercice traité. Mais personne ne prévient
  le logiciel qu'une loi de finances a changé un seuil — c'est à vous de le
  vérifier, idéalement à chaque ouverture d'exercice.</p>
  <p>
    {% if v.derniere_veille %}Dernière veille déclarée : <b>{{ v.derniere_veille }}</b>.
    {% else %}<b>Aucune veille déclarée à ce jour.</b>{% endif %}
    {% if v.a_refaire %}<span style="color:#c0392b"> — il est temps d'en refaire une.</span>{% endif %}
  </p>
  <form method="post" action="/veille/faite" style="margin:0">
    <button type="submit">J'ai fait ma veille aujourd'hui</button>
  </form>
</div></div>

<div class="card"><div class="card-body">
  <h2>Question type à poser à une IA</h2>
  <p class="muted">Copiez ce texte dans n'importe quelle IA conversationnelle
  disposant d'une recherche web. Il est volontairement exigeant sur les sources
  et sur la distinction entre ce qui est adopté et ce qui n'est qu'un projet.
  <b>Une réponse d'IA n'est pas une source</b> : vérifiez toujours sur
  Légifrance, le BOFiP ou impots.gouv.fr, et demandez l'avis d'un
  expert-comptable en cas de doute.</p>
  <textarea id="prompt" rows="16" style="width:100%;font-family:ui-monospace,
    Menlo,Consolas,monospace;font-size:12.5px">{{ v.prompt }}</textarea>
  <p><button type="button" onclick="copierPrompt()">Copier la question</button>
     <span id="copie_ok" class="muted"></span></p>
</div></div>

<div class="card"><div class="card-body">
  <h2>Points d'attention connus</h2>
  <p class="muted">Relevés lors de la revue du corpus ({{ v.corpus_revu_le }}) —
  à confirmer lors de votre veille.</p>
  <ul>{% for a in v.actualite %}<li>{{ a }}</li>{% endfor %}</ul>
</div></div>

<div class="card"><div class="card-body" style="padding:0">
  <div style="padding:16px 16px 0"><h2>Les textes qui régissent le LMNP</h2>
  <p class="muted">Chaque texte est rattaché à ce qu'il gouverne dans ce
  logiciel.</p></div>
  <table>
    <thead><tr><th>Référence</th><th>Objet</th>
      <th>Ce qu'il gouverne ici</th><th>Règle liée</th></tr></thead>
    <tbody>
    {% for ref, intitule, effet, regle in v.corpus %}
      <tr>
        <td style="white-space:nowrap"><b>{{ ref }}</b></td>
        <td>{{ intitule }}</td>
        <td class="opt">{{ effet }}</td>
        <td class="muted">{{ regle or '—' }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div></div>

<script>
function copierPrompt() {
  var z = document.getElementById('prompt');
  z.select(); z.setSelectionRange(0, 999999);
  var ok = function () {
    document.getElementById('copie_ok').textContent = ' ✓ copié';
  };
  if (navigator.clipboard) {
    navigator.clipboard.writeText(z.value).then(ok, function () {
      document.execCommand('copy'); ok();
    });
  } else { document.execCommand('copy'); ok(); }
}
</script>
"""
