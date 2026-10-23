from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from caliper.adapters.postgres.connection import database_url_from_environment


def make_engine():
    return create_async_engine(database_url_from_environment(), pool_pre_ping=True)


engine = make_engine()
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
