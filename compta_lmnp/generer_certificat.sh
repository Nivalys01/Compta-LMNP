#!/usr/bin/env bash
# Génère un certificat auto-signé pour servir l'application en HTTPS local.
# Aucune dépendance Python ajoutée : on utilise openssl (présent sur tout Linux).
#
# Usage :  ./generer_certificat.sh
# Puis :   python app.py     → https://localhost:5000
#
# Le navigateur affichera un avertissement à la première visite (certificat
# auto-signé, normal pour un usage local) : « Avancé → Continuer vers localhost ».
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p certs

openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 3650 \
  -keyout certs/key.pem -out certs/cert.pem \
  -subj "/CN=localhost/O=Compta LMNP (usage local)" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 certs/key.pem
echo
echo "Certificat créé : certs/cert.pem (valide 10 ans)"
echo "Clé privée      : certs/key.pem  (permissions 600)"
echo "Relancez :  python app.py   puis ouvrez https://localhost:5000"
