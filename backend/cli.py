"""Local migrations, first administrator bootstrap and HTTPS launcher."""

import argparse
from datetime import UTC, datetime, timedelta
from getpass import getpass
from ipaddress import ip_address
import os
from pathlib import Path
import secrets

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import select
import uvicorn

from backend.api.schemas import NewAccount
from backend.data.backups import backup, restore, start_daily_backup
from backend.data.database import ROOT, check_disposable, database
from backend.data.migrate import migrate
from backend.data.privileges import PROFILES, grant_local_runtime
from backend.data.store import Store
from backend.services.accounts import insert
from backend.services.security import audit, password_hash
from backend.worker_process import worker_process

LOCAL = ROOT / ".ates"
LOCAL_URL = f"sqlite:///{(LOCAL / 'ates.sqlite3').as_posix()}"


def tls_pair(directory):
    directory.mkdir(parents=True, exist_ok=True)
    cert = directory / "local-cert.pem"
    key = directory / "local-key.pem"
    now = datetime.now(UTC)
    if cert.is_file() and key.is_file():
        prior = x509.load_pem_x509_certificate(cert.read_bytes())
        if prior.not_valid_after_utc > now:
            return cert, key

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(subject).public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName("localhost"), x509.IPAddress(ip_address("127.0.0.1")),
        ]), critical=False)
        .sign(private_key, hashes.SHA256())
    )
    descriptor = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption()))
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return cert, key


def bootstrap(url, username, name, email, password):
    check_disposable(url)
    store = Store(url)
    try:
        with store.transaction() as connection:
            users = store["users"]
            if connection.scalar(select(users.c.user_id).where(users.c.role == "Administrator").limit(1)):
                raise SystemExit("An Administrator already exists. Use account administration to create another.")
            account = NewAccount(username=username, full_name=name, email=email, password=password,
                                 role="Administrator")
            values = account.model_dump(include={"username", "full_name", "email", "role"})
            row = insert(connection, users, {**values, "password_hash": password_hash(password)})
            audit(connection, store, row["user_id"], "account_bootstrapped", entity_id=row["user_id"])
    finally:
        store.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    backup_command = commands.add_parser("backup")
    backup_command.add_argument("--directory", type=Path, default=LOCAL / "backups")
    restore_command = commands.add_parser("restore")
    restore_command.add_argument("source", type=Path)
    grants = commands.add_parser("grant-local-runtime")
    grants.add_argument("--role", required=True)
    grants.add_argument("--profile", choices=list(PROFILES), required=True)
    admin = commands.add_parser("bootstrap")
    admin.add_argument("--username", default="admin")
    admin.add_argument("--name", default="ATES Administrator")
    admin.add_argument("--email", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8443)
    serve.add_argument("--prepared", action="store_true", help="Start against a previously migrated database.")
    serve.add_argument("--tls-dir", type=Path, default=LOCAL / "tls")
    serve.add_argument("--api-only", action="store_true", help="Run the solver worker separately.")
    args = parser.parse_args()
    LOCAL.mkdir(exist_ok=True)
    url = os.environ.setdefault("ATES_DATABASE_URL", LOCAL_URL)
    if args.command in {"backup", "restore"}:
        if args.command == "backup":
            print(backup(os.environ.get("ATES_MIGRATION_DATABASE_URL", url), args.directory))
        else:
            restore(url, args.source)
            print("Restored the disposable database.")
        return
    if args.command != "serve" or not args.prepared:
        migration_url = os.environ.get("ATES_MIGRATION_DATABASE_URL", url)
        check_disposable(migration_url)
        if args.command != "migrate" and migration_url != url:
            check_disposable(url)
            if database_target(migration_url) != database_target(url):
                raise SystemExit("Runtime and migration URLs must target the same disposable database.")
        engine = database(migration_url)
        try:
            migrate(engine)
            if args.command == "grant-local-runtime":
                grant_local_runtime(engine, args.role, args.profile)
        finally:
            engine.dispose()

    if args.command == "bootstrap":
        password = os.getenv("ATES_BOOTSTRAP_PASSWORD") or getpass("Administrator password (at least 8 characters): ")
        if not 8 <= len(password) <= 1024:
            raise SystemExit("Enter a password of 8 to 1024 characters.")
        bootstrap(url, args.username, args.name, args.email, password)
        print("Administrator created.")
    if args.command == "serve":
        worker_url = os.getenv("ATES_WORKER_DATABASE_URL", url)
        if not args.prepared:
            os.environ.setdefault("ATES_JWT_SECRET", secrets.token_urlsafe(48))
            if not args.api_only:
                check_disposable(worker_url)
                if database_target(worker_url) != database_target(url):
                    raise SystemExit("The server and worker must target the same disposable database.")
        cert, key = tls_pair(args.tls_dir)
        daily = None
        if directory := os.getenv("ATES_BACKUP_DIRECTORY"):
            backup_url = os.environ.get("ATES_MIGRATION_DATABASE_URL", url)
            check_disposable(backup_url)
            if database_target(backup_url) != database_target(url):
                raise SystemExit("The daily backup must target the same disposable database.")
            daily = start_daily_backup(backup_url, directory)
        try:
            with worker_process(worker_url, enabled=not args.api_only):
                uvicorn.run("backend.api.app:create_app", factory=True, host="127.0.0.1", port=args.port,
                            ssl_certfile=str(cert), ssl_keyfile=str(key))
        finally:
            if daily:
                daily.set()


def database_target(url):
    from sqlalchemy import make_url

    target = make_url(url)
    return target.get_backend_name(), target.host, target.port, target.database


if __name__ == "__main__":
    main()

