#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#   COMPTA LMNP — LANCEUR
#   Depuis un terminal :  bash <nom-de-ce-fichier>
#
#   Le lanceur s'occupe de tout :
#     1. vérifie Python 3 ;
#     2. crée un environnement local .venv et installe Flask (1er lancement) ;
#     3. démarre en HTTP local (HTTPS sur demande : --https) ;
#     4. démarre l'application et ouvre le navigateur.
#
#   Options :  --verifier    vérifie l'environnement sans rien lancer
#              --raccourci   installe une entrée dans le menu d'applications
#              --http        force le démarrage sans HTTPS
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

# Chemin ABSOLU résolu du script, calculé AVANT tout cd. Trois usages en
# dépendent, et chacun cassait avec un chemin relatif :
#   - le relancement dans un terminal (gnome-terminal et ptyxis sont
#     activés par D-Bus et NE conservent PAS le répertoire courant) ;
#   - le raccourci de menu, qui doit contenir un chemin absolu ;
#   - les messages d'aide, qui doivent donner une commande copiable.
# `readlink -f` est une extension GNU : BSD (donc macOS) ne l'a qu'à partir
# de la 12.3. Sur une version antérieure, la commande échoue — et comme
# c'est la PREMIÈRE instruction du script, `set -e` l'arrêtait net, avant
# le moindre message. On résout donc à la main, en POSIX pur.
_resoudre() {
    local p="$1" d
    while [ -L "$p" ]; do
        d="$(cd -P "$(dirname "$p")" && pwd)"
        p="$(readlink "$p")"
        case "$p" in /*) ;; *) p="$d/$p" ;; esac
    done
    printf '%s\n' "$(cd -P "$(dirname "$p")" && pwd)/$(basename "$p")"
}
MOI="$(_resoudre "$0")"
DOSSIER="$(dirname "$MOI")"

# macOS ou Linux ? Presque tout ce qui suit en dépend : ouverture du
# navigateur, terminal, notification, diagnostic de port, message
# d'installation de Python. Le fichier s'annonçait « Linux-macOS » alors
# qu'aucune de ces différences n'était traitée.
EST_MAC=0
[ "$(uname -s 2>/dev/null)" = "Darwin" ] && EST_MAC=1
NOM="$(basename "$MOI")"          # déduit, jamais écrit en dur : un
cd "$DOSSIER"                     # renommage ne peut plus le périmer

MODE="${1:-}"

# ── Double-clic depuis le gestionnaire de fichiers ? ─────────────────────────
# Sans terminal, l'utilisateur ne verrait rien : on se relance dans un
# émulateur de terminal. (Si le double-clic OUVRE ce fichier dans un éditeur
# au lieu de l'exécuter : clic droit → « Exécuter », ou installez le
# raccourci de menu avec :  bash <ce-fichier> --raccourci )
# Les modes qui ne font qu'afficher ou écrire un fichier n'ont pas besoin
# d'un terminal : les relancer dans une fenêtre était inutile, et cachait
# leur message de confirmation.
case "$MODE" in --verifier|--raccourci|--aide|-h|--help) SANS_FENETRE=1 ;;
                *) SANS_FENETRE=0 ;; esac
if [[ ! -t 1 && -z "${COMPTA_EN_TERMINAL:-}" && "$SANS_FENETRE" == "0" ]]; then
    export COMPTA_EN_TERMINAL=1
    # macOS : Terminal.app et iTerm sont des APPLICATIONS, pas des
    # commandes — `command -v` ne les trouve jamais. On passe par `open`.
    if [ "$EST_MAC" = "1" ]; then
        # Pas d'`exec` aveugle : si l'ouverture échoue, `exec` a déjà
        # remplacé le processus et le script meurt sans un mot. On teste,
        # et à défaut on continue vers le repli commun (journal + adresse).
        if [ -d "/Applications/iTerm.app" ] \
           && open -a iTerm "$MOI" >/dev/null 2>&1; then exit 0; fi
        if open -a Terminal "$MOI" >/dev/null 2>&1; then exit 0; fi
    fi

    # Ordre : les défauts des bureaux récents d'abord. ptyxis est le
    # terminal par défaut de Fedora 40+ et de Bazzite ; kgx/gnome-console
    # celui de GNOME ; konsole celui de KDE. Leur absence de cette liste
    # faisait échouer TOUT le relancement (constaté en usage réel).
    for term in ptyxis kgx gnome-console gnome-terminal konsole \
                io.elementary.terminal \
                x-terminal-emulator xfce4-terminal mate-terminal tilix \
                terminator alacritty kitty wezterm foot qterminal \
                lxterminal deepin-terminal urxvt xterm; do
        command -v "$term" >/dev/null 2>&1 || continue
        # Chemin ABSOLU : gnome-terminal et ptyxis passent par D-Bus et ne
        # transmettent pas le répertoire courant — un « bash ./script »
        # échouerait sans un mot.
        case "$term" in
            ptyxis)                   exec "$term" -- bash "$MOI" "$@" ;;
            gnome-terminal|tilix|kgx|gnome-console|io.elementary.terminal)
                                      exec "$term" -- bash "$MOI" "$@" ;;
            konsole|terminator|xfce4-terminal|mate-terminal|qterminal|\
            lxterminal|deepin-terminal)
                                      exec "$term" -e "bash '$MOI'" ;;
            alacritty|kitty|wezterm|foot|urxvt|xterm)
                                      exec "$term" -e bash "$MOI" "$@" ;;
        esac
    done
    # Aucun terminal graphique : NE PAS continuer en silence — c'est le
    # pire des cas, l'application démarre et l'utilisateur ne voit rien.
    # On prévient par tous les moyens disponibles, puis on continue.
    JOURNAL="${DOSSIER}/logs/demarrage.log"
    mkdir -p "${DOSSIER}/logs" 2>/dev/null || true
    {
        echo "[$(date '+%F %T')] Aucun terminal graphique trouvé."
        echo "  Compta LMNP démarre malgré tout : ouvrez http://localhost:5000"
        echo "  Pour voir les messages, lancez depuis un terminal :"
        echo "      bash \"$MOI\""
    } >> "$JOURNAL" 2>/dev/null || true
    if [ "$EST_MAC" = "1" ] && command -v osascript >/dev/null 2>&1; then
        osascript -e 'display notification "Ouvrez http://localhost:5000" with title "Compta LMNP"' >/dev/null 2>&1 || true
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send "Compta LMNP démarre" \
            "Ouvrez http://localhost:5000 dans votre navigateur." \
            >/dev/null 2>&1 || true
    elif command -v zenity >/dev/null 2>&1; then
        (zenity --info --title="Compta LMNP" \
            --text="L'application démarre.\n\nOuvrez http://localhost:5000" \
            >/dev/null 2>&1 &) || true
    fi
fi

BLEU='\033[1;34m'; VERT='\033[1;32m'; JAUNE='\033[1;33m'; ROUGE='\033[1;31m'; FIN='\033[0m'
ok()   { echo -e "  ${VERT}✓${FIN} $1"; }
info() { echo -e "  ${BLEU}·${FIN} $1"; }
warn() { echo -e "  ${JAUNE}⚠${FIN} $1"; }
err()  { echo -e "  ${ROUGE}✗${FIN} $1"; }

# ── Ouverture du navigateur : robuste et JAMAIS silencieuse ─────────────────
# xdg-open seul ne suffit pas : il est absent ou inopérant sur beaucoup de
# systèmes (distributions immuables, navigateurs en Flatpak, sessions
# minimales). On essaie plusieurs voies, et si AUCUNE ne marche on affiche
# l'adresse en grand — l'utilisateur ne doit jamais rester devant un écran
# qui ne fait rien.
ouvrir_navigateur() {
    local url="$1"

    # a) Préférence explicite de l'utilisateur
    if [[ -n "${BROWSER:-}" ]] && command -v "${BROWSER%% *}" >/dev/null 2>&1; then
        "$BROWSER" "$url" >/dev/null 2>&1 & sleep 1; return 0
    fi
    # a bis) macOS : `open` est l'ouvreur du système. xdg-open n'y existe
    #        pas — sans cette branche, on tombait directement sur le repli.
    if [ "$EST_MAC" = "1" ]; then
        open "$url" >/dev/null 2>&1 && { sleep 1; return 0; }
    fi
    # b) Ouvreurs génériques du bureau
    for cmd in xdg-open gio gnome-open kde-open5 kde-open; do
        if command -v "$cmd" >/dev/null 2>&1; then
            if [[ "$cmd" == "gio" ]]; then
                gio open "$url" >/dev/null 2>&1 && { sleep 1; return 0; }
            else
                "$cmd" "$url" >/dev/null 2>&1 && { sleep 1; return 0; }
            fi
        fi
    done
    # c) Module Python webbrowser (connaît la plupart des navigateurs)
    if "$PY" -m webbrowser -t "$url" >/dev/null 2>&1; then sleep 1; return 0; fi
    # d) Navigateurs installés en direct
    for nav in firefox chromium chromium-browser google-chrome google-chrome-stable \
               brave-browser vivaldi-stable microsoft-edge epiphany falkon \
               open; do
        if command -v "$nav" >/dev/null 2>&1; then
            "$nav" "$url" >/dev/null 2>&1 & sleep 1; return 0
        fi
    done
    # e) Navigateurs en Flatpak (fréquent sur Fedora Silverblue, Bazzite…)
    if command -v flatpak >/dev/null 2>&1; then
        for app in org.mozilla.firefox com.google.Chrome org.chromium.Chromium \
                   com.brave.Browser com.microsoft.Edge; do
            if flatpak info "$app" >/dev/null 2>&1; then
                flatpak run "$app" "$url" >/dev/null 2>&1 & sleep 1; return 0
            fi
        done
    fi
    return 1                                   # aucune voie n'a fonctionné
}

# L'adresse est TOUJOURS affichée, même quand l'ouverture semble réussir :
# xdg-open (comme python -m webbrowser) renvoie « succès » même lorsqu'il
# n'ouvre RIEN — aucune détection fiable n'est possible. L'utilisateur doit
# donc toujours avoir l'adresse sous les yeux ; l'ouverture est un bonus.
adresse_en_grand() {
    echo
    echo -e "${JAUNE}  ┌────────────────────────────────────────────────────┐${FIN}"
    echo -e "${JAUNE}  │  Si aucune page ne s'ouvre, collez cette adresse    │${FIN}"
    echo -e "${JAUNE}  │  dans votre navigateur :                            │${FIN}"
    echo -e "${JAUNE}  └────────────────────────────────────────────────────┘${FIN}"
    echo
    echo -e "        ${VERT}$1${FIN}"
    echo
    echo -e "  ${BLEU}·${FIN} Astuce : pour choisir le navigateur, lancez par exemple"
    echo -e "    ${BLEU}BROWSER=firefox bash \"$MOI\"${FIN}"
    echo
}

echo -e "${BLEU}══════════════════════════════════════════${FIN}"
echo -e "${BLEU}   Compta LMNP — démarrage${FIN}"
echo -e "${BLEU}══════════════════════════════════════════${FIN}"


# ── 1. Python 3 ──────────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
    if [ "$EST_MAC" = "1" ]; then
        err "Python 3 introuvable."
        info "Sur macOS, installez-le d'une de ces deux façons :"
        info "  · outils Apple :  xcode-select --install"
        info "  · ou le paquet officiel : https://www.python.org/downloads/"
    else
        err "Python 3 introuvable. Installez-le :"
        info "  · Debian/Ubuntu/Mint :  sudo apt install python3 python3-venv"
        info "  · Fedora/RHEL        :  sudo dnf install python3"
        info "  · Arch/Manjaro       :  sudo pacman -S python"
        info "  · openSUSE           :  sudo zypper install python3"
    fi
    read -rp "Appuyez sur Entrée pour fermer…"; exit 1
fi
ok "Python 3 : $(python3 --version 2>&1)"

# ── Option : installer un raccourci dans le menu d'applications ─────────────
if [[ "$MODE" == "--raccourci" ]]; then
    # macOS ignore les fichiers .desktop. Son équivalent natif est un
    # fichier « .command » : rendu exécutable, il se lance d'un
    # double-clic depuis le Finder et ouvre Terminal — exactement ce que
    # cherche l'utilisateur.
    if [ "$EST_MAC" = "1" ]; then
        CIBLE="${HOME}/Desktop/Compta LMNP.command"
        printf '#!/bin/sh\nexec bash "%s"\n' "$MOI" > "$CIBLE"
        chmod +x "$CIBLE"
        ok "Raccourci créé sur le Bureau : Compta LMNP.command"
        ok "Double-cliquez dessus pour lancer le logiciel."
        info "Au premier lancement, macOS peut demander une confirmation"
        info "(clic droit → Ouvrir) : c'est normal pour un fichier"
        info "téléchargé et non signé."
        exit 0
    fi
    DESK="${HOME}/.local/share/applications/compta-lmnp.desktop"
    mkdir -p "$(dirname "$DESK")"
    cat > "$DESK" <<EOF
[Desktop Entry]
Type=Application
Name=Compta LMNP
Comment=Comptabilité location meublée (LMNP réel)
Exec=bash "${MOI}"
Path=${DOSSIER}
Terminal=true
Categories=Office;Finance;
EOF
    chmod +x "$DESK"
    ok "Raccourci installé : ${DESK}"
    ok "« Compta LMNP » apparaît maintenant dans votre menu d'applications."
    exit 0
fi

# ── 2. Environnement local (.venv) + Flask ──────────────────────────────────
#
# Trois pièges appris en usage réel (Linux Mint, août 2026) :
#
#   1. Le SCRIPT ./.venv/bin/pip peut manquer alors que le MODULE pip est
#      présent — c'est le cas sur Debian et dérivés quand python3-venv est
#      installé sans le paquet pip. On appelle donc toujours « python -m
#      pip », jamais le script.
#   2. « python3 -m venv » peut échouer APRÈS avoir créé le dossier. Un
#      .venv incomplet subsiste alors, et un test « le dossier existe-t-il »
#      croit l'environnement prêt : le lancement suivant meurt sans un mot.
#      On teste donc que l'environnement FONCTIONNE, pas qu'il existe.
#   3. Sur Debian et dérivés, la création peut réussir SANS pip. ensurepip
#      permet de le rattraper sans réinstaller quoi que ce soit.
venv_operationnel() {
    [[ -x .venv/bin/python ]] && \
        ./.venv/bin/python -m pip --version >/dev/null 2>&1
}

if ! venv_operationnel; then
    if [[ -d .venv ]]; then
        warn "Environnement local incomplet ou abîmé — reconstruction."
        rm -rf .venv
    fi
    info "Premier lancement : création de l'environnement local (.venv)…"
    info "(1 à 3 minutes, ne fermez pas cette fenêtre)"
    if ! python3 -m venv .venv 2>/tmp/compta-venv.err; then
        err "Création de l'environnement impossible."
        [[ -s /tmp/compta-venv.err ]] && sed 's/^/      /' /tmp/compta-venv.err
        if [ "$EST_MAC" = "1" ]; then
            info "Vérifiez votre installation Python (python3 -m venv --help)."
        else
            info "Installez le paquet manquant, puis relancez :"
            info "  · Debian, Ubuntu, Mint :  sudo apt install python3-venv python3-pip"
            info "  · Fedora, RHEL, Bazzite:  sudo dnf install python3-virtualenv"
            info "  · Arch, Manjaro        :  sudo pacman -S python-pip"
        fi
        rm -rf .venv
        read -rp "Appuyez sur Entrée pour fermer…"; exit 1
    fi
    # La création a réussi — mais pip peut manquer malgré tout.
    if ! venv_operationnel; then
        info "pip absent de l'environnement — amorçage…"
        ./.venv/bin/python -m ensurepip --upgrade >/dev/null 2>&1 || true
    fi
    if ! venv_operationnel; then
        err "L'environnement a été créé, mais pip n'a pas pu y être installé."
        info "Sur Debian, Ubuntu et Mint, c'est le paquet python3-venv qui"
        info "fournit pip aux environnements virtuels :"
        info "  sudo apt install python3-venv python3-pip"
        info "Puis supprimez le dossier .venv et relancez ce fichier."
        read -rp "Appuyez sur Entrée pour fermer…"; exit 1
    fi
    ok "Environnement local créé."
else
    ok "Environnement local : .venv"
fi
PY=./.venv/bin/python

# « $PY -m pip » et non « ./.venv/bin/pip » : le module existe même quand le
# script d'appel manque.
if ! "$PY" -c "import flask" >/dev/null 2>&1; then
    info "Installation de Flask (une seule fois)…"
    "$PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
    # Le manifeste borne les versions au lieu de laisser pip prendre
    # n'importe quoi : deux installations d'une même version du logiciel
    # doivent donner le même environnement (constat T-06).
    if ! "$PY" -m pip install --quiet -r "$DOSSIER/requirements.txt"; then
        err "Installation de Flask impossible."
        info "Une connexion internet est nécessaire au premier lancement."
        info "Derrière un proxy d'entreprise, renseignez la variable"
        info "https_proxy avant de relancer."
        read -rp "Appuyez sur Entrée pour fermer…"; exit 1
    fi
fi
# reportlab ne sert qu'à l'export PDF : son absence ne doit RIEN bloquer.
if ! "$PY" -c "import reportlab" >/dev/null 2>&1; then
    "$PY" -m pip install --quiet -r "$DOSSIER/requirements.txt" >/dev/null 2>&1 \
        || warn "reportlab non installé — tout fonctionne sauf l'export PDF."
fi
# Un import qui réussit ne dit PAS que l'environnement est celui qu'attend
# CETTE version du logiciel : le lanceur passait outre, et un .venv vieilli
# survivait à toutes les mises à jour (constat T-06).
#
# On compare donc l'empreinte du manifeste à celle enregistrée lors de la
# dernière installation réussie. C'est déterministe, ça ne demande pas le
# réseau quand rien n'a changé, et ça se déclenche exactement quand le
# manifeste bouge — c'est-à-dire quand l'utilisateur met à jour le logiciel.
EMPREINTE_REQ="$DOSSIER/.venv/.compta-requirements"
ATTENDUE="$("$PY" - "$DOSSIER/requirements.txt" <<'EOF'
import sys
from hashlib import sha256
print(sha256(open(sys.argv[1], "rb").read()).hexdigest())
EOF
)"
if [ "$(cat "$EMPREINTE_REQ" 2>/dev/null || true)" != "$ATTENDUE" ]; then
    info "Mise à niveau des dépendances vers les versions attendues…"
    if "$PY" -m pip install --quiet --upgrade \
            -r "$DOSSIER/requirements.txt" >/dev/null 2>&1; then
        printf '%s' "$ATTENDUE" > "$EMPREINTE_REQ"
    else
        warn "Dépendances non mises à niveau (hors ligne ?) — le logiciel"
        warn "démarre avec l'environnement existant."
    fi
fi
ok "Flask : $("$PY" -c 'import importlib.metadata as m; print(m.version("flask"))')"

# ── 3. Protocole ─────────────────────────────────────────────────────────────
# HTTP par défaut depuis la v8.15.0. Un certificat AUTO-SIGNÉ ne peut pas
# être validé : le navigateur affiche un avertissement plein écran puis un
# cadenas barré, définitivement. Or il ne protège rien ici — l'application
# n'écoute que sur la boucle locale et les données ne traversent aucun
# réseau. Son seul effet était d'habituer l'utilisateur à passer outre les
# avertissements de sécurité. HTTPS reste disponible avec --https.
URL="http://localhost:5000"
export COMPTA_HTTPS=0
if [[ "$MODE" == "--https" ]]; then
    if [[ ! -f certs/cert.pem || ! -f certs/key.pem ]]; then
        info "Génération du certificat HTTPS local (une seule fois)…"
        "$PY" -c "import cryptography" 2>/dev/null || "$PY" -m pip install --quiet cryptography
        "$PY" generer_certificat.py >/dev/null 2>&1 \
            && ok "Certificat créé (valide 10 ans)." \
            || warn "HTTPS indisponible — démarrage en HTTP."
    fi
    if [[ -f certs/cert.pem && -f certs/key.pem ]]; then
        URL="https://localhost:5000"
        export COMPTA_HTTPS=1
        warn "HTTPS demandé : le navigateur signalera un certificat non "
        warn "vérifié (auto-signé). C'est attendu."
    fi
fi

# ── Mode vérification seule ──────────────────────────────────────────────────
if [[ "$MODE" == "--verifier" ]]; then
    ok "Environnement opérationnel — tout est prêt pour lancer l'application."
    exit 0
fi

# ── 4. Choix du port (diagnostic si 5000 occupé) ─────────────────────────────
PORT=5000
proto="${URL%%:*}"                                  # https ou http

port_occupe() {                                      # test de bind : portable
    ! "$PY" -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', $1)); s.close()" 2>/dev/null
}

serveur_repond() {                                   # 1 = URL à tester
    "$PY" - "$1" <<'PYEOF' >/dev/null 2>&1
import ssl, sys, urllib.request
ctx = ssl.create_default_context(); ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
urllib.request.urlopen(sys.argv[1], timeout=2, context=ctx)
PYEOF
}

if port_occupe "$PORT"; then
    if serveur_repond "${proto}://localhost:${PORT}"; then
        ok "L'application tourne déjà — ouverture du navigateur."
        ouvrir_navigateur "${proto}://localhost:${PORT}" \
            || adresse_en_grand "${proto}://localhost:${PORT}"
        exit 0
    fi
    warn "Le port ${PORT} est occupé par un processus qui NE RÉPOND PAS."
    # Est-ce un ancien lancement de CE logiciel (même dossier) ? → on le stoppe.
    pid=""
    if [ "$EST_MAC" = "1" ] && command -v lsof >/dev/null 2>&1; then
        # macOS n'a ni ss (iproute2) ni /proc : lsof est l'équivalent.
        pid="$(lsof -ti :"${PORT}" -sTCP:LISTEN 2>/dev/null | head -1 || true)"
    elif command -v ss >/dev/null 2>&1; then
        pid="$(ss -ltnp 2>/dev/null | grep ":${PORT} " | grep -oP 'pid=\K[0-9]+' | head -1 || true)"
    fi
    if [[ -z "${pid:-}" ]] && command -v pgrep >/dev/null 2>&1; then
        pid="$(pgrep -f "\.venv/bin/python app\.py" | head -1 || true)"
    fi
    # Le processus tourne-t-il depuis CE dossier ? /proc est propre à
    # Linux ; sur macOS on interroge lsof.
    cwd_pid=""
    if [ -n "${pid:-}" ]; then
        if [ "$EST_MAC" = "1" ]; then
            cwd_pid="$(lsof -a -d cwd -p "$pid" -Fn 2>/dev/null | sed -n 's/^n//p' | head -1 || true)"
        else
            cwd_pid="$(readlink -f "/proc/${pid}/cwd" 2>/dev/null || true)"
        fi
    fi
    if [[ -n "${pid:-}" ]] && [[ "$cwd_pid" == "$(pwd)" ]]; then
        info "Ancien lancement de Compta LMNP détecté (pid ${pid}) — arrêt…"
        kill "$pid" 2>/dev/null || true; sleep 1
        kill -9 "$pid" 2>/dev/null || true; sleep 1
        ok "Port ${PORT} libéré."
    else
        info "Processus étranger : recherche d'un port libre…"
        for p in 5001 5002 5003 5004 5005 5006 5007 5008 5009 5010; do
            if ! port_occupe "$p"; then PORT="$p"; break; fi
        done
        [[ "$PORT" == "5000" ]] && { err "Aucun port libre entre 5000 et 5010."; exit 1; }
        ok "Repli sur le port ${PORT}."
    fi
fi
URL="${proto}://localhost:${PORT}"

# ── 5. Démarrage, puis navigateur UNE FOIS LE SERVEUR PRÊT ───────────────────
echo
ok "Démarrage de Compta LMNP"
adresse_en_grand "${URL}"
info "Premier accès HTTPS : le navigateur affichera un avertissement"
info "(certificat auto-signé, normal en local) : « Avancé → Continuer »."
info "Pour arrêter l'application : Ctrl+C dans cette fenêtre."
echo
(
    # On n'ouvre le navigateur QUE lorsque le serveur répond réellement —
    # jamais sur un port mort.
    for _ in $(seq 1 30); do
        sleep 0.5
        if serveur_repond "$URL"; then
            adresse_en_grand "$URL"
            ouvrir_navigateur "$URL" || true
            exit 0
        fi
    done
    echo -e "  ${JAUNE}⚠${FIN} Le serveur n'a pas répondu après 15 s — lisez les messages ci-dessus."
    adresse_en_grand "$URL"
) &
exec env COMPTA_PORT="$PORT" "$PY" app.py
