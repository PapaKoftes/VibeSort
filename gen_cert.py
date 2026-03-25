"""
gen_cert.py — Generate a self-signed SSL cert for running Vibesort over HTTPS.

Run once:  python gen_cert.py
Then run:  streamlit run app.py --server.sslCertFile cert.pem --server.sslKeyFile key.pem

In Spotify dashboard, use:  https://localhost:8501
In .env, set:               SPOTIFY_REDIRECT_URI=https://localhost:8501
"""
import subprocess, sys

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import datetime, ipaddress
except ImportError:
    print("Installing cryptography...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography"])
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import datetime, ipaddress

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
])

cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
    .add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]),
        critical=False,
    )
    .sign(key, hashes.SHA256())
)

with open("cert.pem", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

with open("key.pem", "wb") as f:
    f.write(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))

print("Done. cert.pem and key.pem created.")
print()
print("Next steps:")
print("  1. In your .env file, set:  SPOTIFY_REDIRECT_URI=https://localhost:8501")
print("  2. In Spotify dashboard, add redirect URI:  https://localhost:8501")
print("  3. Run Vibesort with:")
print("     streamlit run app.py --server.sslCertFile cert.pem --server.sslKeyFile key.pem")
print()
print("Your browser will warn about the self-signed cert — click 'Advanced' then 'Proceed'.")
