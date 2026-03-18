import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from sqlmodel import SQLModel

from server.core.external.config.database import engine, async_session_factory
from server.core.external.persistence.postgres_query_repository import (
    PostgresQueryRepository,
)
from server.core.application.service.query_service import QueryService
from server.core.external.api.query_router import create_query_router
from server.seed import SEED_QUERIES

logger = logging.getLogger(__name__)


async def _init_db() -> None:
    """Create tables and seed data if the database is empty."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    repository = PostgresQueryRepository(async_session_factory)
    count = await repository.count()
    if count == 0:
        logger.info("Seeding database with sample queries...")
        for query in SEED_QUERIES:
            await repository.save(query)
        logger.info("Seeded %d queries.", len(SEED_QUERIES))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_db()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="사내 쿼리 모음집", lifespan=lifespan)

    # Wire dependencies
    repository = PostgresQueryRepository(async_session_factory)
    service = QueryService(repository)
    router = create_query_router(service)

    app.include_router(router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
