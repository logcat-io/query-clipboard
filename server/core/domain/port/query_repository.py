from abc import ABC, abstractmethod
from typing import List, Optional

from server.core.domain.model.query import Query


class QueryRepository(ABC):
    @abstractmethod
    async def find_all(self) -> List[Query]:
        pass

    @abstractmethod
    async def find_by_id(self, query_id: int) -> Optional[Query]:
        pass

    @abstractmethod
    async def find_by_criteria(
        self, purpose_id: Optional[int] = None, search: Optional[str] = None
    ) -> List[Query]:
        pass

    @abstractmethod
    async def save(self, query: Query) -> Query:
        pass

    @abstractmethod
    async def update(self, query: Query) -> Query:
        pass

    @abstractmethod
    async def delete(self, query_id: int) -> None:
        pass

    @abstractmethod
    async def count(self) -> int:
        pass
