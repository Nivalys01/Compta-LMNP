# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Génération du certificat HTTPS local — version multiplateforme (Python pur).

Génère le certificat sans dépendre d'openssl : utilisé par le
lanceur Windows (Lancer-Compta-LMNP.bat) et en repli sur Linux si openssl est
absent. Nécessite le paquet `cryptography` (installé par les lanceurs).

Usage :  python generer_certificat.py [dossier_de_sortie]
Produit : certs/cert.pem (auto-signé, 10 ans, SAN localhost + 127.0.0.1)
          certs/key.pem  (RSA 2048, permissions 600 sous Linux/macOS)
"""
from __future__ import annotations

import datetime
import ipaddress
import os
import sys

def generer(dossier: str | None = None) -> tuple[str, str]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    ici = dossier or os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs")
    os.makedirs(ici, exist_ok=True)
    cert_path = os.path.join(ici, "cert.pem")
    key_path = os.path.join(ici, "key.pem")

    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nom = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Compta LMNP (usage local)"),
    ])
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nom)
        .issuer_name(nom)                          # auto-signé
        .public_key(cle.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(maintenant)
        .not_valid_after(maintenant + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(cle, hashes.SHA256())
    )

    with open(key_path, "wb") as f:
        f.write(cle.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()))
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    if os.name == "posix":
        os.chmod(key_path, 0o600)
    return cert_path, key_path


if __name__ == "__main__":
    try:
        cert, cle = generer(sys.argv[1] if len(sys.argv) > 1 else None)
    except ImportError:
        print("Paquet 'cryptography' manquant — installez-le dans le .venv :\n"
              "  .venv/bin/pip install cryptography   (Linux)\n"
              "  .venv\\Scripts\\pip install cryptography   (Windows)")
        sys.exit(1)
    print(f"Certificat créé : {cert} (valide 10 ans)")
    print(f"Clé privée      : {cle}")
    print("Relancez l'application puis ouvrez https://localhost:5000")
