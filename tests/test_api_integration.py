"""Integration tests with REAL PostgreSQL database."""
import os
import re

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import SQLModel

from server.core.external.persistence.sqlalchemy_models import QueryTable
from server.core.external.persistence.postgres_query_repository import PostgresQueryRepository
from server.core.application.service.query_service import QueryService
from server.core.external.api.query_router import create_query_router
from server.seed import SEED_QUERIES

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://root:root@localhost:5433/query_book",
)


@pytest_asyncio.fixture()
async def client():
    """Create a fresh app with its own engine for each test."""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI

    test_engine = create_async_engine(DATABASE_URL, echo=False)
    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Truncate to start fresh
    async with test_engine.begin() as conn:
        await conn.execute(text("DELETE FROM queries"))

    # Seed data
    repo = PostgresQueryRepository(test_session_factory)
    for query in SEED_QUERIES:
        await repo.save(query)

    # Build app
    service = QueryService(repo)
    router = create_query_router(service)

    @asynccontextmanager
    async def lifespan(app):
        yield

    app = FastAPI(title="test", lifespan=lifespan)
    app.include_router(router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        yield c

    # Cleanup
    async with test_engine.begin() as conn:
        await conn.execute(text("DELETE FROM queries"))
    await test_engine.dispose()


@pytest.mark.asyncio
class TestIndexPage:
    async def test_index_page_loads(self, client):
        """GET / returns 200 with HTML."""
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_index_contains_seed_data(self, client):
        """Seed queries appear on page."""
        response = await client.get("/")
        html = response.text
        assert "활성 사용자 조회" in html
        assert "주문 금액 집계" in html
        assert "탈퇴 사용자 삭제" in html


@pytest.mark.asyncio
class TestAddQuery:
    async def test_add_query(self, client):
        """POST /add creates a query, redirects to /."""
        response = await client.post(
            "/add",
            data={
                "title": "Integration Test Query",
                "description": "Test description",
                "purpose": "기타",
                "tags": "test,integration",
                "sql_text": "SELECT 'hello';",
            },
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    async def test_add_query_appears_in_list(self, client):
        """After adding, query appears on /."""
        await client.post(
            "/add",
            data={
                "title": "Unique Test Query 12345",
                "description": "desc",
                "purpose": "조회",
                "tags": "unique",
                "sql_text": "SELECT 12345;",
            },
        )
        response = await client.get("/")
        assert "Unique Test Query 12345" in response.text


@pytest.mark.asyncio
class TestEditQuery:
    async def test_edit_query_form(self, client):
        """GET /edit/{id} returns 200 with edit form."""
        await client.post(
            "/add",
            data={
                "title": "Edit Form Test",
                "description": "to be edited",
                "purpose": "조회",
                "tags": "edit",
                "sql_text": "SELECT 1;",
            },
        )
        index_resp = await client.get("/")
        match = re.search(r'href="/edit/(\d+)"', index_resp.text)
        assert match, "Could not find any edit link on the page"
        query_id = match.group(1)

        response = await client.get(f"/edit/{query_id}")
        assert response.status_code == 200
        assert "쿼리 수정" in response.text

    async def test_update_query(self, client):
        """POST /edit/{id} updates query, redirects."""
        await client.post(
            "/add",
            data={
                "title": "Before Update XYZ",
                "description": "old",
                "purpose": "조회",
                "tags": "old",
                "sql_text": "SELECT 'old';",
            },
        )
        index_resp = await client.get("/")
        match = re.search(r'href="/edit/(\d+)"', index_resp.text)
        assert match
        query_id = match.group(1)

        response = await client.post(
            f"/edit/{query_id}",
            data={
                "title": "After Update XYZ",
                "description": "new",
                "purpose": "수정",
                "tags": "new",
                "sql_text": "SELECT 'new';",
            },
        )
        assert response.status_code == 303

        index_resp = await client.get("/")
        assert "After Update XYZ" in index_resp.text


@pytest.mark.asyncio
class TestDeleteQuery:
    async def test_delete_query(self, client):
        """POST /delete/{id} removes query, redirects."""
        await client.post(
            "/add",
            data={
                "title": "Delete Me Please 999",
                "description": "to delete",
                "purpose": "삭제",
                "tags": "delete",
                "sql_text": "DELETE FROM test;",
            },
        )
        index_resp = await client.get("/")
        matches = re.findall(r'action="/delete/(\d+)"', index_resp.text)
        assert matches
        query_id = matches[-1]

        response = await client.post(f"/delete/{query_id}")
        assert response.status_code == 303

    async def test_delete_nonexistent(self, client):
        """POST /delete/99999 redirects without error."""
        response = await client.post("/delete/99999")
        assert response.status_code == 303


@pytest.mark.asyncio
class TestSearchAndFilter:
    async def test_search_by_text(self, client):
        """GET /?q=keyword returns matching results."""
        response = await client.get("/?q=활성 사용자")
        assert response.status_code == 200
        assert "활성 사용자 조회" in response.text

    async def test_filter_by_purpose(self, client):
        """GET /?purpose=조회 returns filtered results."""
        response = await client.get("/?purpose=조회")
        assert response.status_code == 200
        assert "활성 사용자 조회" in response.text
        assert "주문 금액 집계" not in response.text
