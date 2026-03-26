from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from server.core.external.config.database import engine, async_session_factory
from server.core.external.persistence.query_repository import MysqlQueryRepository
from server.core.external.persistence.purpose_repository import MysqlPurposeRepository
from server.core.application.service.query_service import QueryService
from server.core.application.service.purpose_service import PurposeService
from server.core.external.api.query_router import create_query_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="사내 쿼리 모음집", lifespan=lifespan)

    purpose_repository = MysqlPurposeRepository(async_session_factory)
    query_repository = MysqlQueryRepository(async_session_factory)

    purpose_service = PurposeService(purpose_repository)
    query_service = QueryService(query_repository, purpose_repository)

    router = create_query_router(query_service, purpose_service)
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
