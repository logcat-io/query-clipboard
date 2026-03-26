from typing import List

from server.core.application.dto.purpose_dto import (
    CreatePurposeCommand,
    PurposeResult,
)
from server.core.application.usecase.purpose_usecase import PurposeUseCase
from server.core.domain.exception.domain_exception import InvalidPurposeException
from server.core.domain.model.purpose import Purpose
from server.core.domain.port.purpose_repository import PurposeRepository


class PurposeService(PurposeUseCase):
    def __init__(self, repository: PurposeRepository):
        self._repository = repository

    @staticmethod
    def _to_result(purpose: Purpose) -> PurposeResult:
        return PurposeResult.model_validate(purpose, from_attributes=True)

    async def get_all_purposes(self) -> List[PurposeResult]:
        purposes = await self._repository.find_all()
        return [self._to_result(p) for p in purposes]

    async def create_purpose(self, command: CreatePurposeCommand) -> PurposeResult:
        purpose = Purpose(name=command.name, sort_order=command.sort_order)
        purpose.validate()

        existing = await self._repository.find_by_name(command.name)
        if existing:
            raise InvalidPurposeException(f"이미 존재하는 용도입니다: {command.name}")

        saved = await self._repository.save(purpose)
        return self._to_result(saved)

    async def delete_purpose(self, purpose_id: int) -> None:
        existing = await self._repository.find_by_id(purpose_id)
        if existing is None:
            raise InvalidPurposeException("존재하지 않는 용도입니다")
        await self._repository.delete(purpose_id)
