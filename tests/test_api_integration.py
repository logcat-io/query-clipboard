"""Integration tests with REAL MySQL database."""
import re

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel, text
from sqlmodel.ext.asyncio.session import AsyncSession

from server.core.external.config.settings import settings
from server.core.external.persistence.query_repository import MysqlQueryRepository
from server.core.external.persistence.purpose_repository import MysqlPurposeRepository
from server.core.application.service.query_service import QueryService
from server.core.application.service.purpose_service import PurposeService
from server.core.application.dto.query_dto import CreateQueryCommand
from server.core.application.dto.purpose_dto import CreatePurposeCommand
from server.core.external.api.query_router import create_query_router


@pytest_asyncio.fixture()
async def client():
    from contextlib import asynccontextmanager
    from fastapi import FastAPI

    test_engine = create_async_engine(settings.database_url, echo=False)
    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with test_session_factory() as session:
        await session.exec(text("DELETE FROM queries"))
        await session.exec(text("DELETE FROM purposes"))
        await session.commit()

    purpose_repo = MysqlPurposeRepository(test_session_factory)
    purpose_service = PurposeService(purpose_repo)

    purposes = {}
    for i, name in enumerate(["alpha", "beta", "gamma"]):
        p = await purpose_service.create_purpose(
            CreatePurposeCommand(name=name, sort_order=i)
        )
        purposes[name] = p.id

    query_repo = MysqlQueryRepository(test_session_factory)
    query_service = QueryService(query_repo, purpose_repo)

    for cmd in [
        CreateQueryCommand(
            title="Active Users", description="List active users",
            purpose_id=purposes["alpha"], tags="user,active",
            sql_text="SELECT * FROM users WHERE is_active = true;",
        ),
        CreateQueryCommand(
            title="Order Summary", description="Daily order totals",
            purpose_id=purposes["beta"], tags="order,payment",
            sql_text="SELECT DATE(order_date), SUM(amount) FROM orders GROUP BY 1;",
        ),
        CreateQueryCommand(
            title="Cleanup Old Data", description="Remove stale records",
            purpose_id=purposes["gamma"], tags="cleanup",
            sql_text="DELETE FROM logs WHERE created_at < NOW() - INTERVAL 90 DAY;",
        ),
    ]:
        await query_service.create_query(cmd)

    router = create_query_router(query_service, purpose_service)

    @asynccontextmanager
    async def lifespan(app):
        yield

    app = FastAPI(title="test", lifespan=lifespan)
    app.include_router(router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        yield c

    async with test_session_factory() as session:
        await session.exec(text("DELETE FROM queries"))
        await session.exec(text("DELETE FROM purposes"))
        await session.commit()
    await test_engine.dispose()


@pytest.mark.asyncio
class TestIndexPage:
    async def test_index_page_loads(self, client):
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_index_contains_seed_data(self, client):
        html = (await client.get("/")).text
        assert "Active Users" in html
        assert "Order Summary" in html
        assert "Cleanup Old Data" in html


@pytest.mark.asyncio
class TestAddQuery:
    async def test_add_query(self, client):
        # Get a purpose_id from the page
        html = (await client.get("/")).text
        match = re.search(r'purpose_id=(\d+)', html)
        assert match
        pid = match.group(1)

        response = await client.post(
            "/add",
            data={
                "title": "Integration Test Query",
                "description": "Test",
                "purpose_id": pid,
                "tags": "test",
                "sql_text": "SELECT 'hello';",
            },
        )
        assert response.status_code == 303

    async def test_add_query_appears_in_list(self, client):
        html = (await client.get("/")).text
        pid = re.search(r'purpose_id=(\d+)', html).group(1)

        await client.post("/add", data={
            "title": "Unique Test Query 12345",
            "purpose_id": pid, "sql_text": "SELECT 12345;",
        })
        response = await client.get("/")
        assert "Unique Test Query 12345" in response.text


@pytest.mark.asyncio
class TestEditQuery:
    async def test_edit_query_form(self, client):
        index_resp = await client.get("/")
        match = re.search(r'href="/edit/(\d+)', index_resp.text)
        assert match
        response = await client.get(f"/edit/{match.group(1)}")
        assert response.status_code == 200

    async def test_update_query(self, client):
        html = (await client.get("/")).text
        qid = re.search(r'href="/edit/(\d+)', html).group(1)
        pid = re.search(r'purpose_id=(\d+)', html).group(1)

        response = await client.post(f"/edit/{qid}", data={
            "title": "After Update XYZ", "description": "new",
            "purpose_id": pid, "tags": "new", "sql_text": "SELECT 'new';",
        })
        assert response.status_code == 303
        assert "After Update XYZ" in (await client.get("/")).text


@pytest.mark.asyncio
class TestDeleteQuery:
    async def test_delete_query(self, client):
        html = (await client.get("/")).text
        matches = re.findall(r'action="/delete/(\d+)"', html)
        assert matches
        response = await client.post(f"/delete/{matches[-1]}")
        assert response.status_code == 303

    async def test_delete_nonexistent(self, client):
        response = await client.post("/delete/99999")
        assert response.status_code == 303


@pytest.mark.asyncio
class TestSearchAndFilter:
    async def test_search_by_text(self, client):
        response = await client.get("/?q=Active Users")
        assert response.status_code == 200
        assert "Active Users" in response.text

    async def test_filter_by_purpose(self, client):
        html = (await client.get("/")).text
        pid = re.search(r'purpose_id=(\d+)', html).group(1)

        response = await client.get(f"/?purpose_id={pid}")
        assert response.status_code == 200


@pytest.mark.asyncio
class TestPurposeManagement:
    async def test_add_purpose(self, client):
        response = await client.post(
            "/purposes/add", data={"name": "delta", "sort_order": "10"},
        )
        assert response.status_code == 303
        assert "delta" in (await client.get("/")).text

    async def test_add_duplicate_purpose(self, client):
        response = await client.post(
            "/purposes/add", data={"name": "alpha", "sort_order": "0"},
        )
        assert response.status_code == 303
