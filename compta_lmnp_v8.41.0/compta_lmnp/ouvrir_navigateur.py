# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Attend que le serveur réponde, PUIS ouvre le navigateur.

    python ouvrir_navigateur.py https://localhost:5000 [délai_secondes]

Utilisé par le lanceur Windows (lancé en arrière-plan avant le serveur) :
ouvrir le navigateur immédiatement afficherait « site inaccessible », le
serveur n'écoutant pas encore.

Le certificat local étant auto-signé, la vérification TLS est désactivée
POUR CE TEST DE DISPONIBILITÉ uniquement (on interroge 127.0.0.1, pas
internet) — cela ne change rien à la sécurité du navigateur, qui affichera
son avertissement habituel.
"""
from __future__ import annotations

import ssl
import sys
import time
import urllib.request
import webbrowser
def attendre_puis_ouvrir(url: str, delai: float = 25.0) -> bool:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    fin = time.time() + delai
    while time.time() < fin:
        try:
            urllib.request.urlopen(url, timeout=2, context=ctx)
        except Exception:                      # noqa: BLE001 — serveur pas prêt
            time.sleep(0.5)
            continue
        webbrowser.open(url)
        return True
    return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage : python ouvrir_navigateur.py <url> [délai]")
        raise SystemExit(2)
    adresse = sys.argv[1]
    duree = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
    if not attendre_puis_ouvrir(adresse, duree):
        print(f"Le serveur n'a pas répondu — ouvrez vous-même : {adresse}")
        raise SystemExit(1)
