import argparse
import asyncio
import getpass
import os
from pathlib import Path


def read_new_password() -> str:
    password = getpass.getpass("New administrator password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if not 12 <= len(password) <= 1024:
        raise SystemExit("Password must contain between 12 and 1024 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    return password


async def configure_admin(reset: bool) -> None:
    from caliper.adapters.postgres.auth_repository import admin_is_configured, set_admin_password
    from caliper.adapters.postgres.database import SessionLocal, engine
    from caliper.application.auth import hash_password

    async with SessionLocal() as session:
        configured = await admin_is_configured(session)
        if configured and not reset:
            raise SystemExit("Administrator is already configured. Use 'admin reset-password'.")
        if not configured and reset:
            raise SystemExit("Administrator is not configured. Use 'admin init'.")
        await set_admin_password(session, hash_password(read_new_password()))
    await engine.dispose()
    print("Administrator password saved; previous sessions revoked.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="caliper")
    commands = parser.add_subparsers(dest="resource", required=True)
    admin = commands.add_parser("admin")
    actions = admin.add_subparsers(dest="action", required=True)
    actions.add_parser("init")
    actions.add_parser("reset-password")
    secrets = commands.add_parser("secrets")
    secret_actions = secrets.add_subparsers(dest="action", required=True)
    secret_actions.add_parser("init-keyring")
    secret_actions.add_parser("rotate-key")
    args = parser.parse_args()
    if args.resource == "admin":
        asyncio.run(configure_admin(reset=args.action == "reset-password"))
        return

    from caliper.adapters.secret_store.fernet_store import FernetFileSecretStore

    store = FernetFileSecretStore(
        Path(os.environ.get("CALIPER_SECRET_DATA_DIR", "/var/lib/caliper/secret-data")),
        Path(os.environ.get("CALIPER_SECRET_KEYRING", "/var/lib/caliper/keyring/keyring.json")),
    )
    if args.action == "init-keyring":
        store.initialize_keyring()
        print("Secret keyring is initialized.")
    else:
        rotated = store.rotate_key()
        print(f"Key rotation completed for {rotated} secret records.")


if __name__ == "__main__":
    main()
