import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.database import Base


@pytest_asyncio.fixture
async def session():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("integration test requires isolated TEST_DATABASE_URL")
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()
