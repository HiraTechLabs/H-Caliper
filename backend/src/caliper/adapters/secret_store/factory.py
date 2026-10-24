import os
from pathlib import Path

from caliper.adapters.secret_store.fernet_store import FernetFileSecretStore


def configured_secret_store() -> FernetFileSecretStore:
    return FernetFileSecretStore(
        Path(os.environ.get("CALIPER_SECRET_DATA_DIR", "/var/lib/caliper/secret-data")),
        Path(os.environ.get("CALIPER_SECRET_KEYRING", "/var/lib/caliper/keyring/keyring.json")),
    )
