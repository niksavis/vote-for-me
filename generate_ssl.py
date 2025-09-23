#!/usr/bin/env python3
"""
Generate self-signed SSL certificates for local HTTPS development

This script creates SSL certificates that are valid for:
- localhost (127.0.0.1)
- Your computer's hostname
- Your local network IP address

Usage:
    python generate_ssl.py

Requirements:
    pip install cryptography

The generated certificates will be saved to:
- ssl/cert.pem (certificate)
- ssl/key.pem (private key)

Note: These are self-signed certificates for development only.
Browsers will show a security warning that you can safely bypass
for local development.
"""

import socket
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timedelta, timezone
import ipaddress


def get_network_ip():
    """Get the local network IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_self_signed_cert():
    """Generate self-signed SSL certificate for local development"""

    # Create ssl directory if it doesn't exist
    ssl_dir = Path("ssl")
    ssl_dir.mkdir(exist_ok=True)

    cert_file = ssl_dir / "cert.pem"
    key_file = ssl_dir / "key.pem"

    # Check if certificates already exist
    if cert_file.exists() and key_file.exists():
        try:
            response = input("SSL certificates already exist. Regenerate? (y/N): ")
            if response.lower() != "y":
                print("Using existing certificates.")
                return
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            return

    print("🔐 Generating self-signed SSL certificate...")

    try:
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Get network information
        local_ip = get_network_ip()
        hostname = socket.gethostname()

        print(f"   🖥️  Hostname: {hostname}")
        print(f"   🌐 Local IP: {local_ip}")

        # Create certificate subject
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Local"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Development"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Vote For Me"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ]
        )

        # Create certificate with multiple SANs
        builder = x509.CertificateBuilder()
        builder = builder.subject_name(subject)
        builder = builder.issuer_name(subject)  # Self-signed
        builder = builder.public_key(private_key.public_key())
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.not_valid_before(datetime.now(timezone.utc))
        builder = builder.not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=365)
        )

        # Add Subject Alternative Names (SANs)
        san_list = [
            x509.DNSName("localhost"),
            x509.DNSName(hostname),
            x509.DNSName(f"{hostname}.local"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]

        # Add network IP if different from localhost
        if local_ip != "127.0.0.1":
            try:
                san_list.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
            except ValueError as e:
                print(f"   ⚠️  Could not add IP {local_ip} to certificate: {e}")

        builder = builder.add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        )

        # Sign the certificate
        certificate = builder.sign(private_key, hashes.SHA256())

        # Save private key
        with open(key_file, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Save certificate
        with open(cert_file, "wb") as f:
            f.write(certificate.public_bytes(serialization.Encoding.PEM))

    except Exception as e:
        print(f"❌ Error generating certificate: {e}")
        return

    print("✅ SSL certificate generated successfully!")
    print(f"   📄 Certificate: {cert_file}")
    print(f"   🔑 Private Key: {key_file}")
    print(f"   🌐 Valid for: localhost, {hostname}, {local_ip}")
    print(f"   📅 Valid until: {datetime.now(timezone.utc) + timedelta(days=365)}")
    print()
    print("⚠️  Note: This is a self-signed certificate for development only.")
    print(
        "   Browsers will show a security warning. Click 'Advanced' → 'Proceed to localhost'"
    )
    print()
    print("🚀 Now you can run the app with HTTPS support!")
    print("   python app.py")


if __name__ == "__main__":
    print("🔐 SSL Certificate Generator for Vote For Me")
    print("=" * 50)

    try:
        generate_self_signed_cert()
    except ImportError as e:
        if "cryptography" in str(e):
            print(
                "❌ Error: cryptography library is required for SSL certificate generation"
            )
            print("   Install with: pip install cryptography")
            print("   Or run from your virtual environment:")
            print("   .venv\\Scripts\\activate && pip install cryptography")
        else:
            print(f"❌ Import error: {e}")
    except KeyboardInterrupt:
        print("\n\n👋 Certificate generation cancelled by user.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print("   Please check your Python environment and try again.")
