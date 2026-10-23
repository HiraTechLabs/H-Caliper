from pathlib import Path
from uuid import UUID

import pytest

from caliper.adapters.secret_store.fernet_store import FernetFileSecretStore
from caliper.application.secret_store import SecretUnavailable


def make_store(tmp_path: Path) -> FernetFileSecretStore:
    store = FernetFileSecretStore(tmp_path / "vault", tmp_path / "keys" / "keyring.json")
    store.initialize_keyring()
    return store


def test_secret_is_encrypted_durable_and_destroyed(tmp_path: Path):
    secret = b"private-test-token-never-returned-by-api"
    store = make_store(tmp_path)
    secret_id = store.put(secret)
    encrypted_path = tmp_path / "vault" / f"{secret_id.hex}.secret"
    assert secret not in encrypted_path.read_bytes()

    restarted = FernetFileSecretStore(tmp_path / "vault", tmp_path / "keys" / "keyring.json")
    assert restarted.get(secret_id) == secret
    restarted.delete(secret_id)
    with pytest.raises(SecretUnavailable):
        restarted.get(secret_id)


def test_key_rotation_keeps_secrets_readable_and_rewrites_ciphertext(tmp_path: Path):
    store = make_store(tmp_path)
    secret_id = store.put(b"rotate-me")
    record = tmp_path / "vault" / f"{secret_id.hex}.secret"
    previous_ciphertext = record.read_bytes()

    assert store.rotate_key() == 1
    assert record.read_bytes() != previous_ciphertext
    assert (
        FernetFileSecretStore(tmp_path / "vault", tmp_path / "keys" / "keyring.json").get(secret_id)
        == b"rotate-me"
    )


def test_missing_keyring_with_ciphertext_fails_closed(tmp_path: Path):
    store = make_store(tmp_path)
    store.put(b"must-not-be-lost")
    (tmp_path / "keys" / "keyring.json").unlink()
    with pytest.raises(SecretUnavailable):
        store.initialize_keyring()


def test_invalid_secret_identifier_cannot_select_arbitrary_files(tmp_path: Path):
    store = make_store(tmp_path)
    with pytest.raises(SecretUnavailable):
        store.get(UUID(int=0))
