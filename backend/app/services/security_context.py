"""Small helper to resolve repository credentials without leaking them."""

from __future__ import annotations

from typing import Optional

from app.core.security import decrypt_secret
from app.models.project import RepositoryConnection


def decrypt_repository_token(repo: RepositoryConnection) -> Optional[str]:
    if repo.auth_type == "none":
        return None
    return decrypt_secret(repo.secret_encrypted)
