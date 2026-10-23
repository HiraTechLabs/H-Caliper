import json
import os
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from caliper.application.secret_store import SecretUnavailable


class FernetFileSecretStore:
    """Encrypted files plus a separately persisted, rotatable keyring."""

    def __init__(self, data_dir: Path, keyring_path: Path):
        self.data_dir = data_dir
        self.keyring_path = keyring_path
        self.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.data_dir.chmod(0o700)
        self.keyring_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.keyring_path.parent.chmod(0o700)

    def initialize_keyring(self) -> None:
        if self.keyring_path.exists():
            self._cipher()
            return
        if any(self.data_dir.glob("*.secret")):
            raise SecretUnavailable("Secret keyring is missing while encrypted secrets exist")
        key = Fernet.generate_key()
        self._write_keyring([key.decode("ascii")])

    def _cipher(self) -> MultiFernet:
        try:
            keyring = json.loads(self.keyring_path.read_text(encoding="utf-8"))
            keys = keyring["keys"]
            if not keys or not all(isinstance(key, str) for key in keys):
                raise ValueError("Invalid keyring")
            fernets = [Fernet(key.encode("ascii")) for key in keys]
            return MultiFernet(fernets)
        except (OSError, ValueError, KeyError, TypeError, UnicodeError) as error:
            raise SecretUnavailable("Secret keyring is unavailable or invalid") from error

    def put(self, secret: bytes) -> UUID:
        if not secret or len(secret) > 1024 * 1024:
            raise ValueError("Secret must contain between 1 byte and 1 MiB")
        secret_id = uuid4()
        encrypted = self._cipher().encrypt(secret)
        self._atomic_write(self._path(secret_id), encrypted)
        return secret_id

    def get(self, secret_id: UUID) -> bytes:
        try:
            token = self._path(secret_id).read_bytes()
            return self._cipher().decrypt(token)
        except FileNotFoundError as error:
            raise SecretUnavailable("Stored secret is unavailable") from error
        except InvalidToken as error:
            raise SecretUnavailable("Stored secret cannot be decrypted") from error

    def delete(self, secret_id: UUID) -> None:
        try:
            path = self._path(secret_id)
            path.unlink(missing_ok=True)
            self._sync_directory(self.data_dir)
        except OSError as error:
            raise SecretUnavailable("Stored secret could not be destroyed") from error

    def rotate_key(self) -> int:
        old_keys = self._key_strings()
        new_key = Fernet.generate_key()
        new_cipher = MultiFernet(
            [Fernet(new_key), *(Fernet(key.encode("ascii")) for key in old_keys)]
        )
        self._write_keyring([new_key.decode("ascii"), *old_keys])

        rotated = 0
        for path in self.data_dir.glob("*.secret"):
            try:
                token = path.read_bytes()
                self._atomic_write(path, new_cipher.rotate(token))
                rotated += 1
            except (OSError, InvalidToken) as error:
                raise SecretUnavailable(
                    "Key rotation stopped; current and previous keys were retained"
                ) from error
        self._write_keyring([new_key.decode("ascii")])
        return rotated

    def _key_strings(self) -> list[str]:
        try:
            return json.loads(self.keyring_path.read_text(encoding="utf-8"))["keys"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise SecretUnavailable("Secret keyring is unavailable or invalid") from error

    def _path(self, secret_id: UUID) -> Path:
        return self.data_dir / f"{secret_id.hex}.secret"

    def _write_keyring(self, keys: list[str]) -> None:
        payload = json.dumps({"keys": keys}, separators=(",", ":")).encode("utf-8")
        self._atomic_write(self.keyring_path, payload)
        self.keyring_path.chmod(0o600)
        self._sync_directory(self.keyring_path.parent)

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        fd, temp_name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as temp_file:
                temp_file.write(payload)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
            FernetFileSecretStore._sync_directory(path.parent)
        finally:
            Path(temp_name).unlink(missing_ok=True)

    @staticmethod
    def _sync_directory(directory: Path) -> None:
        if os.name != "nt":
            fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
