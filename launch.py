"""
launch.py — Vibesort launcher.

Run this instead of `streamlit run app.py`.

On first run:
  - Generates a self-signed SSL certificate (cert.pem / key.pem)
  - Patches .env to use https://localhost:8501 as redirect URI
  - Launches Streamlit over HTTPS automatically

Every subsequent run:
  - Skips cert generation (already exists)
  - Launches Streamlit with the same HTTPS flags

Usage:
  python launch.py
"""
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(ROOT, "cert.pem")
KEY  = os.path.join(ROOT, "key.pem")
ENV  = os.path.join(ROOT, ".env")
ENV_EXAMPLE = os.path.join(ROOT, ".env.example")
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")

REDIRECT_HTTPS = "https://localhost:8501"


# ── Step 0: Ensure dependencies are installed ─────────────────────────────────

def ensure_dependencies():
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("Installing dependencies (first run — takes ~1 min)...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS],
        )
        print("Dependencies installed.")


# ── Step 1: Ensure .env exists ────────────────────────────────────────────────

def ensure_env():
    if not os.path.exists(ENV):
        if os.path.exists(ENV_EXAMPLE):
            import shutil
            shutil.copy(ENV_EXAMPLE, ENV)
            print("Created .env from .env.example — fill in your Spotify credentials.")
        else:
            with open(ENV, "w") as f:
                f.write("SPOTIFY_CLIENT_ID=\nSPOTIFY_CLIENT_SECRET=\n")
            print("Created empty .env — fill in your Spotify credentials.")


# ── Step 2: Generate SSL cert if missing ─────────────────────────────────────

def ensure_certs():
    if os.path.exists(CERT) and os.path.exists(KEY):
        return  # Already done

    print("First launch: generating SSL certificate for local HTTPS...")

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        import ipaddress
    except ImportError:
        print("  Installing cryptography package...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "cryptography"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        import ipaddress

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
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
        .sign(key, hashes.SHA256())
    )

    with open(CERT, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(KEY, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))

    print("  SSL certificate created (cert.pem / key.pem) — valid 10 years.")


# ── Step 3: Patch .env redirect URI to HTTPS ─────────────────────────────────

def ensure_https_redirect():
    if not os.path.exists(ENV):
        return

    with open(ENV, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    patched = False
    already_https = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("SPOTIFY_REDIRECT_URI="):
            value = stripped.split("=", 1)[1].strip()
            if value == REDIRECT_HTTPS:
                already_https = True
                new_lines.append(line)
            else:
                new_lines.append(f"SPOTIFY_REDIRECT_URI={REDIRECT_HTTPS}\n")
                patched = True
        else:
            new_lines.append(line)

    # Add line if not present at all
    if not any(l.strip().startswith("SPOTIFY_REDIRECT_URI=") for l in lines):
        new_lines.append(f"SPOTIFY_REDIRECT_URI={REDIRECT_HTTPS}\n")
        patched = True

    if patched:
        with open(ENV, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"  .env updated: SPOTIFY_REDIRECT_URI → {REDIRECT_HTTPS}")
    elif not already_https:
        pass  # already correct


# ── Step 3b: Write Streamlit config (suppress email prompt + set theme) ───────

def ensure_streamlit_config():
    """
    Pre-create Streamlit's config and credentials files so it never
    prompts for an email address or usage stats on first run.
    Writes to both the project dir and the user home dir.
    """
    home_streamlit = os.path.join(os.path.expanduser("~"), ".streamlit")
    project_streamlit = os.path.join(ROOT, ".streamlit")

    config_content = (
        "[browser]\n"
        "gatherUsageStats = false\n"
        "\n"
        "[server]\n"
        "headless = false\n"
        "\n"
        "[theme]\n"
        'base = "dark"\n'
    )
    # credentials.toml with empty email — this is what silences the prompt
    credentials_content = '[general]\nemail = ""\n'

    for config_dir in (home_streamlit, project_streamlit):
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "config.toml")
        creds_path  = os.path.join(config_dir, "credentials.toml")
        if not os.path.exists(config_path):
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(config_content)
        if not os.path.exists(creds_path):
            with open(creds_path, "w", encoding="utf-8") as f:
                f.write(credentials_content)


# ── Step 4: Launch Streamlit ──────────────────────────────────────────────────

def launch():
    print("Starting Vibesort...")
    print(f"  Open: {REDIRECT_HTTPS}")
    print()

    cmd = [
        sys.executable, "-m", "streamlit", "run",
        os.path.join(ROOT, "app.py"),
        "--server.sslCertFile", CERT,
        "--server.sslKeyFile", KEY,
        "--browser.gatherUsageStats", "false",
    ]

    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    try:
        subprocess.run(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
    except KeyboardInterrupt:
        print("\nVibesort stopped.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ensure_dependencies()
    ensure_env()
    ensure_certs()
    ensure_https_redirect()
    ensure_streamlit_config()
    launch()
