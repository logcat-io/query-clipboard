from abc import ABC, abstractmethod
from typing import List, Optional

from server.core.domain.model.purpose import Purpose


class PurposeRepository(ABC):
    @abstractmethod
    async def find_all(self) -> List[Purpose]:
        pass

    @abstractmethod
    async def find_by_id(self, purpose_id: int) -> Optional[Purpose]:
        pass

    @abstractmethod
    async def find_by_name(self, name: str) -> Optional[Purpose]:
        pass

    @abstractmethod
    async def save(self, purpose: Purpose) -> Purpose:
        pass

    @abstractmethod
    async def delete(self, purpose_id: int) -> None:
        pass
