from typing import List, Optional

from sqlmodel import select, delete, func, or_
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from server.core.domain.model.query import Query
from server.core.domain.port.query_repository import QueryRepository
from server.core.external.persistence.sqlalchemy_models import QueryTable


class MysqlQueryRepository(QueryRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    @staticmethod
    def _to_domain(model: QueryTable) -> Query:
        return Query.model_validate(model)

    async def find_all(self) -> List[Query]:
        async with self._session_factory() as session:
            stmt = select(QueryTable).order_by(QueryTable.created_at.desc())
            result = await session.exec(stmt)
            rows = result.all()
            return [self._to_domain(r) for r in rows]

    async def find_by_id(self, query_id: int) -> Optional[Query]:
        async with self._session_factory() as session:
            stmt = select(QueryTable).where(QueryTable.id == query_id)
            result = await session.exec(stmt)
            row = result.first()
            return self._to_domain(row) if row else None

    async def find_by_criteria(
        self, purpose_id: Optional[int] = None, search: Optional[str] = None
    ) -> List[Query]:
        async with self._session_factory() as session:
            stmt = select(QueryTable)

            if purpose_id:
                stmt = stmt.where(QueryTable.purpose_id == purpose_id)

            if search:
                search_pattern = f"%{search}%"
                stmt = stmt.where(
                    or_(
                        QueryTable.title.ilike(search_pattern),
                        QueryTable.description.ilike(search_pattern),
                        QueryTable.tags.ilike(search_pattern),
                        QueryTable.sql_text.ilike(search_pattern),
                    )
                )

            stmt = stmt.order_by(QueryTable.created_at.desc())
            result = await session.exec(stmt)
            rows = result.all()
            return [self._to_domain(r) for r in rows]

    async def save(self, query: Query) -> Query:
        async with self._session_factory() as session:
            model = QueryTable(
                title=query.title,
                description=query.description,
                purpose_id=query.purpose_id,
                tags=query.tags,
                sql_text=query.sql_text,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def update(self, query: Query) -> Query:
        async with self._session_factory() as session:
            stmt = select(QueryTable).where(QueryTable.id == query.id)
            result = await session.exec(stmt)
            model = result.first()
            if model is None:
                raise ValueError(f"Query not found: id={query.id}")

            model.title = query.title
            model.description = query.description
            model.purpose_id = query.purpose_id
            model.tags = query.tags
            model.sql_text = query.sql_text
            model.version = query.version
            model.updated_at = query.updated_at

            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def delete(self, query_id: int) -> None:
        async with self._session_factory() as session:
            stmt = delete(QueryTable).where(QueryTable.id == query_id)
            await session.exec(stmt)
            await session.commit()

    async def count(self) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(QueryTable)
            result = await session.exec(stmt)
            return result.one()
