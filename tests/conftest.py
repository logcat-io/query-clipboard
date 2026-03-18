import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import SQLModel

from server.core.external.persistence.sqlalchemy_models import QueryTable
from server.core.external.persistence.postgres_query_repository import PostgresQueryRepository
from server.core.application.service.query_service import QueryService
from server.main import create_app

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://root:root@localhost:5433/query_book",
)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def session_factory(test_engine):
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    # Truncate queries table after each test
    async with test_engine.begin() as conn:
        await conn.execute(QueryTable.__table__.delete())


@pytest_asyncio.fixture()
async def repository(session_factory):
    return PostgresQueryRepository(session_factory)


@pytest_asyncio.fixture()
async def service(repository):
    return QueryService(repository)


@pytest_asyncio.fixture()
async def app():
    application = create_app()
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture()
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        yield c
