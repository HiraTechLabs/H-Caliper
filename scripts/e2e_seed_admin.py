"""Seed an administrator for an isolated browser test using stdin only."""

import asyncio
import sys

from caliper.adapters.postgres.auth_repository import set_admin_password
from caliper.adapters.postgres.database import SessionLocal, engine
from caliper.application.auth import hash_password


async def main() -> None:
    password = sys.stdin.readline().rstrip("\r\n")
    if len(password) < 12:
        raise SystemExit("The temporary test password was not received.")
    async with SessionLocal() as session:
        await set_admin_password(session, hash_password(password))
        from caliper.adapters.postgres.auth_repository import authenticate

        if await authenticate(session, password) is None:
            raise SystemExit("Temporary administrator verification failed.")
    print("Temporary administrator seeded and verified.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
