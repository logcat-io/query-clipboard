"""Tests for the application service layer using an in-memory repository."""
from datetime import datetime
from typing import List, Optional

import pytest
import pytest_asyncio

from server.core.domain.model.query import Query
from server.core.domain.port.query_repository import QueryRepository
from server.core.domain.exception.domain_exception import (
    InvalidQueryException,
    QueryNotFoundException,
)
from server.core.application.dto.query_dto import (
    CreateQueryCommand,
    UpdateQueryCommand,
    QuerySearchCriteria,
    QueryResult,
)
from server.core.application.service.query_service import QueryService


class InMemoryQueryRepository(QueryRepository):
    """In-memory implementation of QueryRepository for testing the port-adapter pattern."""

    def __init__(self):
        self._store: dict[int, Query] = {}
        self._next_id: int = 1

    async def find_all(self) -> List[Query]:
        return sorted(
            self._store.values(),
            key=lambda q: q.created_at or datetime.min,
            reverse=True,
        )

    async def find_by_id(self, query_id: int) -> Optional[Query]:
        return self._store.get(query_id)

    async def find_by_criteria(
        self, purpose: Optional[str] = None, search: Optional[str] = None
    ) -> List[Query]:
        results = list(self._store.values())
        if purpose:
            results = [q for q in results if q.purpose == purpose]
        if search:
            search_lower = search.lower()
            results = [
                q
                for q in results
                if search_lower in (q.title or "").lower()
                or search_lower in (q.description or "").lower()
                or search_lower in (q.tags or "").lower()
                or search_lower in (q.sql_text or "").lower()
            ]
        return sorted(
            results,
            key=lambda q: q.created_at or datetime.min,
            reverse=True,
        )

    async def save(self, query: Query) -> Query:
        saved = query.model_copy(update={
            "id": self._next_id,
            "created_at": datetime.now(),
        })
        self._next_id += 1
        self._store[saved.id] = saved
        return saved

    async def update(self, query: Query) -> Query:
        if query.id not in self._store:
            raise ValueError(f"Query not found: id={query.id}")
        self._store[query.id] = query
        return query

    async def delete(self, query_id: int) -> None:
        self._store.pop(query_id, None)

    async def count(self) -> int:
        return len(self._store)


@pytest_asyncio.fixture()
async def in_memory_repo():
    return InMemoryQueryRepository()


@pytest_asyncio.fixture()
async def svc(in_memory_repo):
    return QueryService(in_memory_repo)


@pytest.mark.asyncio
class TestCreateQuery:
    async def test_create_query(self, svc):
        """Creates query via service, returns QueryResult."""
        cmd = CreateQueryCommand(
            title="Test Query",
            description="A description",
            purpose="조회",
            tags="test",
            sql_text="SELECT 1;",
        )
        result = await svc.create_query(cmd)
        assert isinstance(result, QueryResult)
        assert result.id is not None
        assert result.title == "Test Query"
        assert result.purpose == "조회"

    async def test_create_query_invalid(self, svc):
        """Raises InvalidQueryException for invalid data."""
        cmd = CreateQueryCommand(
            title="",
            description=None,
            purpose="조회",
            tags="",
            sql_text="SELECT 1;",
        )
        with pytest.raises(InvalidQueryException):
            await svc.create_query(cmd)


@pytest.mark.asyncio
class TestGetQueries:
    async def test_get_all_queries(self, svc):
        """Returns list of QueryResult."""
        cmd = CreateQueryCommand(
            title="Q1", description=None, purpose="조회", tags="", sql_text="SELECT 1;"
        )
        await svc.create_query(cmd)
        cmd2 = CreateQueryCommand(
            title="Q2", description=None, purpose="수정", tags="", sql_text="UPDATE t SET x=1;"
        )
        await svc.create_query(cmd2)

        results = await svc.get_all_queries()
        assert len(results) == 2
        assert all(isinstance(r, QueryResult) for r in results)

    async def test_get_query_by_id(self, svc):
        """Returns single QueryResult."""
        cmd = CreateQueryCommand(
            title="Find Me", description="desc", purpose="기타", tags="", sql_text="SELECT 1;"
        )
        created = await svc.create_query(cmd)

        result = await svc.get_query_by_id(created.id)
        assert result.title == "Find Me"
        assert result.id == created.id

    async def test_get_query_not_found(self, svc):
        """Raises QueryNotFoundException for missing ID."""
        with pytest.raises(QueryNotFoundException):
            await svc.get_query_by_id(99999)


@pytest.mark.asyncio
class TestUpdateQuery:
    async def test_update_query(self, svc):
        """Updates and returns QueryResult."""
        cmd = CreateQueryCommand(
            title="Original", description=None, purpose="조회", tags="", sql_text="SELECT 1;"
        )
        created = await svc.create_query(cmd)

        update_cmd = UpdateQueryCommand(
            title="Updated",
            description="new desc",
            purpose="수정",
            tags="updated",
            sql_text="UPDATE t SET x=1;",
        )
        result = await svc.update_query(created.id, update_cmd)
        assert result.title == "Updated"
        assert result.purpose == "수정"

    async def test_update_query_not_found(self, svc):
        """Raises QueryNotFoundException for missing ID."""
        update_cmd = UpdateQueryCommand(
            title="X", description=None, purpose="조회", tags="", sql_text="SELECT 1;"
        )
        with pytest.raises(QueryNotFoundException):
            await svc.update_query(99999, update_cmd)


@pytest.mark.asyncio
class TestDeleteQuery:
    async def test_delete_query(self, svc):
        """Deletes successfully."""
        cmd = CreateQueryCommand(
            title="To Delete", description=None, purpose="삭제", tags="", sql_text="DELETE FROM t;"
        )
        created = await svc.create_query(cmd)
        await svc.delete_query(created.id)

        with pytest.raises(QueryNotFoundException):
            await svc.get_query_by_id(created.id)

    async def test_delete_query_not_found(self, svc):
        """Raises QueryNotFoundException for missing ID."""
        with pytest.raises(QueryNotFoundException):
            await svc.delete_query(99999)


@pytest.mark.asyncio
class TestSearchQueries:
    async def test_search_queries_by_purpose(self, svc):
        """Filters by purpose."""
        await svc.create_query(
            CreateQueryCommand(title="A", description=None, purpose="조회", tags="", sql_text="SELECT 1;")
        )
        await svc.create_query(
            CreateQueryCommand(title="B", description=None, purpose="수정", tags="", sql_text="UPDATE t SET x=1;")
        )
        await svc.create_query(
            CreateQueryCommand(title="C", description=None, purpose="조회", tags="", sql_text="SELECT 2;")
        )

        criteria = QuerySearchCriteria(purpose="조회")
        results = await svc.search_queries(criteria)
        assert len(results) == 2
        assert all(r.purpose == "조회" for r in results)

    async def test_search_queries_by_text(self, svc):
        """Searches across fields (title, description, tags, sql_text)."""
        await svc.create_query(
            CreateQueryCommand(
                title="User Query",
                description="Find active users",
                purpose="조회",
                tags="user",
                sql_text="SELECT * FROM users;",
            )
        )
        await svc.create_query(
            CreateQueryCommand(
                title="Order Query",
                description="Aggregate orders",
                purpose="집계",
                tags="order",
                sql_text="SELECT SUM(amount) FROM orders;",
            )
        )

        criteria = QuerySearchCriteria(search="user")
        results = await svc.search_queries(criteria)
        assert len(results) >= 1
        assert any("User" in r.title for r in results)
