from datetime import datetime, timezone
from typing import List

from server.core.application.dto.query_dto import (
    CreateQueryCommand,
    UpdateQueryCommand,
    QueryResult,
    QuerySearchCriteria,
)
from server.core.application.usecase.query_usecase import QueryUseCase
from server.core.domain.exception.domain_exception import (
    QueryNotFoundException,
    InvalidQueryException,
)
from server.core.domain.model.query import Query
from server.core.domain.port.query_repository import QueryRepository
from server.core.domain.port.purpose_repository import PurposeRepository


class QueryService(QueryUseCase):
    def __init__(self, repository: QueryRepository, purpose_repository: PurposeRepository):
        self._repository = repository
        self._purpose_repository = purpose_repository

    async def _to_result(self, query: Query) -> QueryResult:
        purpose = await self._purpose_repository.find_by_id(query.purpose_id)
        purpose_name = purpose.name if purpose else ""
        return QueryResult(
            id=query.id,
            title=query.title,
            description=query.description,
            purpose_id=query.purpose_id,
            purpose_name=purpose_name,
            tags=query.tags,
            sql_text=query.sql_text,
            version=query.version,
            created_at=query.created_at,
            updated_at=query.updated_at,
        )

    async def _validate_purpose_exists(self, purpose_id: int) -> None:
        purpose = await self._purpose_repository.find_by_id(purpose_id)
        if purpose is None:
            raise InvalidQueryException(f"존재하지 않는 용도입니다: id={purpose_id}")

    async def get_all_queries(self) -> List[QueryResult]:
        queries = await self._repository.find_all()
        return [await self._to_result(q) for q in queries]

    async def get_query_by_id(self, query_id: int) -> QueryResult:
        query = await self._repository.find_by_id(query_id)
        if query is None:
            raise QueryNotFoundException(query_id)
        return await self._to_result(query)

    async def search_queries(self, criteria: QuerySearchCriteria) -> List[QueryResult]:
        queries = await self._repository.find_by_criteria(
            purpose_id=criteria.purpose_id, search=criteria.search
        )
        return [await self._to_result(q) for q in queries]

    async def create_query(self, command: CreateQueryCommand) -> QueryResult:
        await self._validate_purpose_exists(command.purpose_id)
        query = Query(
            title=command.title,
            description=command.description,
            purpose_id=command.purpose_id,
            tags=command.tags,
            sql_text=command.sql_text,
        )
        query.validate()
        saved = await self._repository.save(query)
        return await self._to_result(saved)

    async def update_query(
        self, query_id: int, command: UpdateQueryCommand
    ) -> QueryResult:
        existing = await self._repository.find_by_id(query_id)
        if existing is None:
            raise QueryNotFoundException(query_id)

        await self._validate_purpose_exists(command.purpose_id)

        updated = existing.model_copy(update={
            "title": command.title,
            "description": command.description,
            "purpose_id": command.purpose_id,
            "tags": command.tags,
            "sql_text": command.sql_text,
            "version": existing.version + 1,
            "updated_at": datetime.now(timezone.utc),
        })
        updated.validate()

        result = await self._repository.update(updated)
        return await self._to_result(result)

    async def delete_query(self, query_id: int) -> None:
        existing = await self._repository.find_by_id(query_id)
        if existing is None:
            raise QueryNotFoundException(query_id)
        await self._repository.delete(query_id)
