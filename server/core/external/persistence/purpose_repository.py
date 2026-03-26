from typing import List, Optional

from sqlmodel import select, delete
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from server.core.domain.model.purpose import Purpose
from server.core.domain.port.purpose_repository import PurposeRepository
from server.core.external.persistence.sqlalchemy_models import PurposeTable


class MysqlPurposeRepository(PurposeRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    @staticmethod
    def _to_domain(model: PurposeTable) -> Purpose:
        return Purpose.model_validate(model)

    async def find_all(self) -> List[Purpose]:
        async with self._session_factory() as session:
            stmt = select(PurposeTable).order_by(PurposeTable.sort_order)
            result = await session.exec(stmt)
            rows = result.all()
            return [self._to_domain(r) for r in rows]

    async def find_by_id(self, purpose_id: int) -> Optional[Purpose]:
        async with self._session_factory() as session:
            stmt = select(PurposeTable).where(PurposeTable.id == purpose_id)
            result = await session.exec(stmt)
            row = result.first()
            return self._to_domain(row) if row else None

    async def find_by_name(self, name: str) -> Optional[Purpose]:
        async with self._session_factory() as session:
            stmt = select(PurposeTable).where(PurposeTable.name == name)
            result = await session.exec(stmt)
            row = result.first()
            return self._to_domain(row) if row else None

    async def save(self, purpose: Purpose) -> Purpose:
        async with self._session_factory() as session:
            model = PurposeTable(name=purpose.name, sort_order=purpose.sort_order)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def delete(self, purpose_id: int) -> None:
        async with self._session_factory() as session:
            stmt = delete(PurposeTable).where(PurposeTable.id == purpose_id)
            await session.exec(stmt)
            await session.commit()
