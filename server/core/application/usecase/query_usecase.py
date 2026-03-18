from abc import ABC, abstractmethod
from typing import List

from server.core.application.dto.query_dto import (
    CreateQueryCommand,
    UpdateQueryCommand,
    QueryResult,
    QuerySearchCriteria,
)


class QueryUseCase(ABC):
    @abstractmethod
    async def get_all_queries(self) -> List[QueryResult]:
        pass

    @abstractmethod
    async def get_query_by_id(self, query_id: int) -> QueryResult:
        pass

    @abstractmethod
    async def search_queries(self, criteria: QuerySearchCriteria) -> List[QueryResult]:
        pass

    @abstractmethod
    async def create_query(self, command: CreateQueryCommand) -> QueryResult:
        pass

    @abstractmethod
    async def update_query(
        self, query_id: int, command: UpdateQueryCommand
    ) -> QueryResult:
        pass

    @abstractmethod
    async def delete_query(self, query_id: int) -> None:
        pass
