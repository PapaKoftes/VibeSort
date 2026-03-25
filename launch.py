"""
launch.py — Vibesort launcher. Run with: python launch.py

First run (fully automatic, no user interaction):
  1. Install Python dependencies if missing
  2. Create .env from template if missing
  3. Generate a local CA + signed SSL cert (trusted by Chrome/Edge/Safari)
  4. Install the CA into the OS trust store (user-level, no admin required)
  5. Patch .env redirect URI to https://localhost:8501
  6. Write Streamlit config (suppress email prompt, dark theme)
  7. Launch Streamlit — browser opens with no security warning

Every subsequent run: skips steps 1-6, just launches.
"""

import os
import sys
import platform
import subprocess
import shutil

ROOT        = os.path.dirname(os.path.abspath(__file__))
CA_KEY      = os.path.join(ROOT, "ca.key")
CA_CERT     = os.path.join(ROOT, "ca.crt")
CERT        = os.path.join(ROOT, "cert.pem")
KEY         = os.path.join(ROOT, "key.pem")
CA_MARKER   = os.path.join(ROOT, ".ca_installed")   # exists once CA is trusted
ENV         = os.path.join(ROOT, ".env")
ENV_EXAMPLE = os.path.join(ROOT, ".env.example")
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")

REDIRECT_HTTPS = "https://localhost:8501"
SYSTEM = platform.system()   # "Windows" | "Darwin" | "Linux"


# ── Step 0: Dependencies ──────────────────────────────────────────────────────

def ensure_dependencies():
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("Installing dependencies (first run — takes ~1 min)...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS],
        )
        print("Dependencies installed.\n")


# ── Step 1: .env ──────────────────────────────────────────────────────────────

def ensure_env():
    if not os.path.exists(ENV):
        if os.path.exists(ENV_EXAMPLE):
            shutil.copy(ENV_EXAMPLE, ENV)
            print("Created .env — add your Spotify Client ID and Secret, then re-run.")
        else:
            with open(ENV, "w") as f:
                f.write("SPOTIFY_CLIENT_ID=\nSPOTIFY_CLIENT_SECRET=\n")
            print("Created .env — fill in your Spotify credentials, then re-run.")


# ── Step 2: CA + cert generation ─────────────────────────────────────────────

def _crypto_imports():
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime, ipaddress
        return x509, NameOID, ExtendedKeyUsageOID, hashes, serialization, rsa, datetime, ipaddress
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "cryptography"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        from cryptography import x509
        from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime, ipaddress
        return x509, NameOID, ExtendedKeyUsageOID, hashes, serialization, rsa, datetime, ipaddress


def ensure_certs():
    if os.path.exists(CERT) and os.path.exists(KEY) and os.path.exists(CA_CERT):
        return

    print("First launch: generating trusted local SSL certificate...")
    x509, NameOID, ExtendedKeyUsageOID, hashes, serialization, rsa, datetime, ipaddress = _crypto_imports()

    now = datetime.datetime.now(datetime.timezone.utc)

    # ── Generate CA key + cert ────────────────────────────────────────────────
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME,         "Vibesort Local CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME,   "Vibesort"),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_cert_sign=True, crl_sign=True,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    # ── Generate server key + cert signed by CA ───────────────────────────────
    srv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    srv_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    srv_cert = (
        x509.CertificateBuilder()
        .subject_name(srv_name)
        .issuer_name(ca_name)
        .public_key(srv_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    # ── Write files ───────────────────────────────────────────────────────────
    with open(CA_KEY,  "wb") as f:
        f.write(ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
    with open(CA_CERT, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    with open(CERT, "wb") as f:
        f.write(srv_cert.public_bytes(serialization.Encoding.PEM))
    with open(KEY, "wb") as f:
        f.write(srv_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))

    print("  Certificate generated.")


# ── Step 3: Install CA into OS trust store ────────────────────────────────────

def ensure_ca_trusted():
    if os.path.exists(CA_MARKER):
        return  # Already installed this CA

    if not os.path.exists(CA_CERT):
        return

    print("  Installing local CA into system trust store...")
    ok = False

    if SYSTEM == "Windows":
        # certutil -addstore -user ROOT — no admin needed (user cert store)
        result = subprocess.run(
            ["certutil", "-addstore", "-user", "ROOT", CA_CERT],
            capture_output=True,
        )
        ok = result.returncode == 0

    elif SYSTEM == "Darwin":
        # Add to user login keychain — no sudo needed
        result = subprocess.run(
            [
                "security", "add-trusted-cert",
                "-d", "-r", "trustRoot",
                "-k", os.path.expanduser("~/Library/Keychains/login.keychain-db"),
                CA_CERT,
            ],
            capture_output=True,
        )
        ok = result.returncode == 0
        if not ok:
            # Older macOS uses .keychain not .keychain-db
            result = subprocess.run(
                [
                    "security", "add-trusted-cert",
                    "-d", "-r", "trustRoot",
                    "-k", os.path.expanduser("~/Library/Keychains/login.keychain"),
                    CA_CERT,
                ],
                capture_output=True,
            )
            ok = result.returncode == 0

    elif SYSTEM == "Linux":
        # Try NSS database (used by Chrome/Chromium/Firefox)
        nss_db = os.path.expanduser("~/.pki/nssdb")
        if not os.path.exists(nss_db):
            subprocess.run(
                ["mkdir", "-p", nss_db], capture_output=True
            )
            subprocess.run(
                ["certutil", "-d", f"sql:{nss_db}", "-N", "--empty-password"],
                capture_output=True,
            )
        result = subprocess.run(
            [
                "certutil", "-d", f"sql:{nss_db}",
                "-A", "-n", "Vibesort Local CA",
                "-t", "CT,,",
                "-i", CA_CERT,
            ],
            capture_output=True,
        )
        ok = result.returncode == 0

    if ok:
        # Write marker so we don't reinstall on every launch
        with open(CA_MARKER, "w") as f:
            f.write("installed\n")
        print("  CA trusted — browser will not show security warnings.\n")
    else:
        print("  CA install skipped (click Advanced → Proceed if browser warns).\n")


# ── Step 4: Patch .env ────────────────────────────────────────────────────────

def ensure_https_redirect():
    if not os.path.exists(ENV):
        return
    with open(ENV, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines, patched = [], False
    has_key = False
    for line in lines:
        if line.strip().startswith("SPOTIFY_REDIRECT_URI="):
            has_key = True
            if line.strip() != f"SPOTIFY_REDIRECT_URI={REDIRECT_HTTPS}":
                line = f"SPOTIFY_REDIRECT_URI={REDIRECT_HTTPS}\n"
                patched = True
        new_lines.append(line)
    if not has_key:
        new_lines.append(f"SPOTIFY_REDIRECT_URI={REDIRECT_HTTPS}\n")
        patched = True
    if patched:
        with open(ENV, "w", encoding="utf-8") as f:
            f.writelines(new_lines)


# ── Step 5: Streamlit config ──────────────────────────────────────────────────

def ensure_streamlit_config():
    config_content = (
        "[browser]\ngatherUsageStats = false\n\n"
        "[server]\nheadless = false\n\n"
        '[theme]\nbase = "dark"\n'
    )
    credentials_content = '[general]\nemail = ""\n'

    for config_dir in (
        os.path.join(os.path.expanduser("~"), ".streamlit"),
        os.path.join(ROOT, ".streamlit"),
    ):
        os.makedirs(config_dir, exist_ok=True)
        for fname, content in (
            ("config.toml",      config_content),
            ("credentials.toml", credentials_content),
        ):
            path = os.path.join(config_dir, fname)
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)


# ── Step 6: Launch ────────────────────────────────────────────────────────────

def launch():
    print(f"Starting Vibesort at {REDIRECT_HTTPS}")
    print()
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    try:
        subprocess.run(
            [
                sys.executable, "-m", "streamlit", "run",
                os.path.join(ROOT, "app.py"),
                "--server.sslCertFile", CERT,
                "--server.sslKeyFile",  KEY,
                "--browser.gatherUsageStats", "false",
            ],
            cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
        )
    except KeyboardInterrupt:
        print("\nVibesort stopped.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ensure_dependencies()
    ensure_env()
    ensure_certs()
    ensure_ca_trusted()
    ensure_https_redirect()
    ensure_streamlit_config()
    launch()
