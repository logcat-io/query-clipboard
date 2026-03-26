from abc import ABC, abstractmethod
from typing import List

from server.core.application.dto.purpose_dto import (
    CreatePurposeCommand,
    PurposeResult,
)


class PurposeUseCase(ABC):
    @abstractmethod
    async def get_all_purposes(self) -> List[PurposeResult]:
        pass

    @abstractmethod
    async def create_purpose(self, command: CreatePurposeCommand) -> PurposeResult:
        pass

    @abstractmethod
    async def delete_purpose(self, purpose_id: int) -> None:
        pass
