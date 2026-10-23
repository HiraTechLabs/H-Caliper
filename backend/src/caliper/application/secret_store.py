from typing import Protocol
from uuid import UUID


class SecretStoreError(Exception):
    """Base error for operations against the protected secret store."""


class SecretUnavailable(SecretStoreError):
    """A stored secret is missing or cannot be decrypted."""


class SecretStore(Protocol):
    def put(self, secret: bytes) -> UUID: ...

    def get(self, secret_id: UUID) -> bytes: ...

    def delete(self, secret_id: UUID) -> None: ...
