import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.git.repository_sync import GitRepositorySyncAdapter
from caliper.adapters.postgres.repository_sync_repository import SqlRepositorySyncRepository
from caliper.adapters.secret_store.fernet_store import FernetFileSecretStore
from caliper.application.repository_sync import RepositorySync


def build_repository_sync(session: AsyncSession) -> RepositorySync:
    repository_root = Path(os.environ.get("CALIPER_REPOSITORY_ROOT", "/tmp/caliper-repositories"))
    local_root = Path(
        os.environ.get("CALIPER_LOCAL_REPOSITORY_ROOT", "/var/lib/caliper/local-repositories")
    )
    git = GitRepositorySyncAdapter(
        repository_root,
        local_root,
        allow_local_repositories=os.environ.get("CALIPER_ALLOW_LOCAL_REPOSITORIES", "false").lower()
        == "true",
        known_hosts_path=Path(
            os.environ.get("CALIPER_SSH_KNOWN_HOSTS", "/etc/caliper/ssh/known_hosts")
        ),
    )
    secrets = FernetFileSecretStore(
        Path(os.environ.get("CALIPER_SECRET_DATA_DIR", "/var/lib/caliper/secret-data")),
        Path(os.environ.get("CALIPER_SECRET_KEYRING", "/var/lib/caliper/keyring/keyring.json")),
    )
    return RepositorySync(SqlRepositorySyncRepository(session), secrets, git)
