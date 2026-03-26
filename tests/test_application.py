"""Tests for the application service layer using in-memory repositories."""
from datetime import datetime, timezone
from typing import List, Optional

import pytest
import pytest_asyncio

from server.core.domain.model.query import Query
from server.core.domain.model.purpose import Purpose
from server.core.domain.port.query_repository import QueryRepository
from server.core.domain.port.purpose_repository import PurposeRepository
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
        self, purpose_id: Optional[int] = None, search: Optional[str] = None
    ) -> List[Query]:
        results = list(self._store.values())
        if purpose_id:
            results = [q for q in results if q.purpose_id == purpose_id]
        if search:
            search_lower = search.lower()
            results = [
                q for q in results
                if search_lower in (q.title or "").lower()
                or search_lower in (q.description or "").lower()
                or search_lower in (q.tags or "").lower()
                or search_lower in (q.sql_text or "").lower()
            ]
        return sorted(results, key=lambda q: q.created_at or datetime.min, reverse=True)

    async def save(self, query: Query) -> Query:
        saved = query.model_copy(update={
            "id": self._next_id,
            "created_at": datetime.now(timezone.utc),
            "version": 1,
        })
        self._next_id += 1
        self._store[saved.id] = saved
        return saved

    async def update(self, query: Query) -> Query:
        if query.id not in self._store:
            raise ValueError(f"Query not found: id={query.id}")
        updated = query.model_copy(update={
            "updated_at": query.updated_at or datetime.now(timezone.utc),
        })
        self._store[query.id] = updated
        return updated

    async def delete(self, query_id: int) -> None:
        self._store.pop(query_id, None)

    async def count(self) -> int:
        return len(self._store)


class InMemoryPurposeRepository(PurposeRepository):

    def __init__(self):
        self._store: dict[int, Purpose] = {}
        self._next_id: int = 1

    async def find_all(self) -> List[Purpose]:
        return sorted(self._store.values(), key=lambda p: p.sort_order)

    async def find_by_id(self, purpose_id: int) -> Optional[Purpose]:
        return self._store.get(purpose_id)

    async def find_by_name(self, name: str) -> Optional[Purpose]:
        for p in self._store.values():
            if p.name == name:
                return p
        return None

    async def save(self, purpose: Purpose) -> Purpose:
        saved = purpose.model_copy(update={"id": self._next_id})
        self._next_id += 1
        self._store[saved.id] = saved
        return saved

    async def delete(self, purpose_id: int) -> None:
        self._store.pop(purpose_id, None)


@pytest_asyncio.fixture()
async def in_memory_purpose_repo():
    repo = InMemoryPurposeRepository()
    for i, name in enumerate(["alpha", "beta", "gamma"]):
        await repo.save(Purpose(name=name, sort_order=i))
    return repo


@pytest_asyncio.fixture()
async def in_memory_repo():
    return InMemoryQueryRepository()


@pytest_asyncio.fixture()
async def svc(in_memory_repo, in_memory_purpose_repo):
    return QueryService(in_memory_repo, in_memory_purpose_repo)


@pytest.mark.asyncio
class TestCreateQuery:
    async def test_create_query(self, svc):
        result = await svc.create_query(
            CreateQueryCommand(title="Test", purpose_id=1, sql_text="SELECT 1;")
        )
        assert isinstance(result, QueryResult)
        assert result.purpose_id == 1
        assert result.purpose_name == "alpha"

    async def test_create_query_invalid_title(self, svc):
        with pytest.raises(InvalidQueryException):
            await svc.create_query(
                CreateQueryCommand(title="", purpose_id=1, sql_text="SELECT 1;")
            )

    async def test_create_query_invalid_purpose(self, svc):
        with pytest.raises(InvalidQueryException, match="존재하지 않는 용도"):
            await svc.create_query(
                CreateQueryCommand(title="Test", purpose_id=999, sql_text="SELECT 1;")
            )


@pytest.mark.asyncio
class TestGetQueries:
    async def test_get_all_queries(self, svc):
        await svc.create_query(CreateQueryCommand(title="Q1", purpose_id=1, sql_text="SELECT 1;"))
        await svc.create_query(CreateQueryCommand(title="Q2", purpose_id=2, sql_text="SELECT 2;"))
        results = await svc.get_all_queries()
        assert len(results) == 2

    async def test_get_query_by_id(self, svc):
        created = await svc.create_query(
            CreateQueryCommand(title="Find Me", purpose_id=3, sql_text="SELECT 1;")
        )
        result = await svc.get_query_by_id(created.id)
        assert result.title == "Find Me"
        assert result.purpose_name == "gamma"

    async def test_get_query_not_found(self, svc):
        with pytest.raises(QueryNotFoundException):
            await svc.get_query_by_id(99999)


@pytest.mark.asyncio
class TestUpdateQuery:
    async def test_update_query(self, svc):
        created = await svc.create_query(
            CreateQueryCommand(title="Original", purpose_id=1, sql_text="SELECT 1;")
        )
        result = await svc.update_query(created.id, UpdateQueryCommand(
            title="Updated", purpose_id=2, sql_text="SELECT 2;",
        ))
        assert result.title == "Updated"
        assert result.purpose_id == 2
        assert result.purpose_name == "beta"

    async def test_update_query_not_found(self, svc):
        with pytest.raises(QueryNotFoundException):
            await svc.update_query(99999, UpdateQueryCommand(
                title="X", purpose_id=1, sql_text="SELECT 1;",
            ))


@pytest.mark.asyncio
class TestDeleteQuery:
    async def test_delete_query(self, svc):
        created = await svc.create_query(
            CreateQueryCommand(title="To Delete", purpose_id=1, sql_text="DELETE FROM t;")
        )
        await svc.delete_query(created.id)
        with pytest.raises(QueryNotFoundException):
            await svc.get_query_by_id(created.id)

    async def test_delete_query_not_found(self, svc):
        with pytest.raises(QueryNotFoundException):
            await svc.delete_query(99999)


@pytest.mark.asyncio
class TestSearchQueries:
    async def test_search_queries_by_purpose(self, svc):
        await svc.create_query(CreateQueryCommand(title="A", purpose_id=1, sql_text="SELECT 1;"))
        await svc.create_query(CreateQueryCommand(title="B", purpose_id=2, sql_text="SELECT 2;"))
        await svc.create_query(CreateQueryCommand(title="C", purpose_id=1, sql_text="SELECT 3;"))

        results = await svc.search_queries(QuerySearchCriteria(purpose_id=1))
        assert len(results) == 2
        assert all(r.purpose_id == 1 for r in results)

    async def test_search_queries_by_text(self, svc):
        await svc.create_query(CreateQueryCommand(
            title="User Query", description="Find users",
            purpose_id=1, tags="user", sql_text="SELECT * FROM users;",
        ))
        await svc.create_query(CreateQueryCommand(
            title="Order Query", description="Orders",
            purpose_id=2, tags="order", sql_text="SELECT * FROM orders;",
        ))
        results = await svc.search_queries(QuerySearchCriteria(search="user"))
        assert len(results) >= 1
        assert any("User" in r.title for r in results)
