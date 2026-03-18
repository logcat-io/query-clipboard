from typing import List

from server.core.application.dto.query_dto import (
    CreateQueryCommand,
    UpdateQueryCommand,
    QueryResult,
    QuerySearchCriteria,
)
from server.core.application.usecase.query_usecase import QueryUseCase
from server.core.domain.exception.domain_exception import QueryNotFoundException
from server.core.domain.model.query import Query
from server.core.domain.port.query_repository import QueryRepository


class QueryService(QueryUseCase):
    def __init__(self, repository: QueryRepository):
        self._repository = repository

    @staticmethod
    def _to_result(query: Query) -> QueryResult:
        return QueryResult.model_validate(query, from_attributes=True)

    async def get_all_queries(self) -> List[QueryResult]:
        queries = await self._repository.find_all()
        return [self._to_result(q) for q in queries]

    async def get_query_by_id(self, query_id: int) -> QueryResult:
        query = await self._repository.find_by_id(query_id)
        if query is None:
            raise QueryNotFoundException(query_id)
        return self._to_result(query)

    async def search_queries(self, criteria: QuerySearchCriteria) -> List[QueryResult]:
        queries = await self._repository.find_by_criteria(
            purpose=criteria.purpose, search=criteria.search
        )
        return [self._to_result(q) for q in queries]

    async def create_query(self, command: CreateQueryCommand) -> QueryResult:
        query = Query(
            title=command.title,
            description=command.description,
            purpose=command.purpose,
            tags=command.tags,
            sql_text=command.sql_text,
        )
        query.validate()
        saved = await self._repository.save(query)
        return self._to_result(saved)

    async def update_query(
        self, query_id: int, command: UpdateQueryCommand
    ) -> QueryResult:
        existing = await self._repository.find_by_id(query_id)
        if existing is None:
            raise QueryNotFoundException(query_id)

        updated = existing.model_copy(update={
            "title": command.title,
            "description": command.description,
            "purpose": command.purpose,
            "tags": command.tags,
            "sql_text": command.sql_text,
        })
        updated.validate()

        result = await self._repository.update(updated)
        return self._to_result(result)

    async def delete_query(self, query_id: int) -> None:
        existing = await self._repository.find_by_id(query_id)
        if existing is None:
            raise QueryNotFoundException(query_id)
        await self._repository.delete(query_id)
