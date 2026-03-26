import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from server.core.external.config.settings import settings
from server.core.external.persistence.sqlalchemy_models import QueryTable, PurposeTable
from server.core.external.persistence.query_repository import MysqlQueryRepository
from server.core.external.persistence.purpose_repository import MysqlPurposeRepository
from server.core.application.service.query_service import QueryService
from server.core.application.service.purpose_service import PurposeService
from server.main import create_app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def session_factory(test_engine):
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    yield factory
    async with test_engine.begin() as conn:
        await conn.execute(QueryTable.__table__.delete())
        await conn.execute(PurposeTable.__table__.delete())


@pytest_asyncio.fixture()
async def repository(session_factory):
    return MysqlQueryRepository(session_factory)


@pytest_asyncio.fixture()
async def purpose_repository(session_factory):
    return MysqlPurposeRepository(session_factory)


@pytest_asyncio.fixture()
async def service(repository, purpose_repository):
    return QueryService(repository, purpose_repository)


@pytest_asyncio.fixture()
async def purpose_service(purpose_repository):
    return PurposeService(purpose_repository)


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
