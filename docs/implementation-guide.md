# 사내 쿼리 모음집 - 구현 가이드

이 문서는 프로젝트의 전체 소스 코드와 설계 근거를 담고 있습니다.
이 문서만으로 프로젝트를 처음부터 다시 구축할 수 있습니다.

---

## 1. 프로젝트 개요

### 1.1 목적

팀 내에서 자주 사용하는 SQL 쿼리를 한 곳에 모아두고,
검색하여 복사해 쓰는 내부 도구.

### 1.2 기술 스택

| 영역 | 기술 | 선택 근거 |
|------|------|-----------|
| 백엔드 프레임워크 | FastAPI 0.115 | 비동기, 타입 힌트, Jinja2 통합 |
| 도메인 모델링 | Pydantic v2 BaseModel | 프레임워크 독립 + 데이터 검증 |
| ORM | SQLModel (table=True) | Pydantic + SQLAlchemy 통합, 보일러플레이트 감소 |
| 비동기 DB 드라이버 | asyncpg | PostgreSQL 네이티브, 최고 성능 |
| 템플릿 | Jinja2 SSR | SPA 불필요, 빌드 도구 불필요 |
| 프론트엔드 | 순수 HTML + CSS + 바닐라 JS | 프레임워크 사용 금지 (요구사항) |
| 패키지 관리 | uv | pip 대비 10~100배 빠른 의존성 해결 |
| 컨테이너 | Docker 멀티스테이지 빌드 | 이미지 크기 최소화, uv 캐시 활용 |
| CI/CD | GitHub Actions | 별도 인프라 불필요 |
| DB | PostgreSQL 16 (Docker) | 프로덕션 동일 DB, ilike 등 고급 기능 |
| 아키텍처 | 헥사고날 (포트-어댑터) | 도메인 독립성, 테스트 용이성 |

### 1.3 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     External Layer                           │
│   ┌───────────┐  ┌────────────────┐  ┌──────────────────┐   │
│   │  FastAPI   │  │  PostgreSQL    │  │ Jinja2 Templates │   │
│   │  Router    │  │  Adapter       │  │ (index.html)     │   │
│   │            │  │  (SQLModel)    │  │                  │   │
│   └─────┬──────┘  └──────┬─────────┘  └──────────────────┘   │
│         │                │                                    │
│   ──────┼────────────────┼───── Port Boundary ──────────────  │
│         │                │                                    │
│   ┌─────┴────────────────┴──────────────────────────────┐    │
│   │               Application Layer                      │    │
│   │   QueryService ─── QueryUseCase (ABC)                │    │
│   │   DTO: CreateQueryCommand, QueryResult, ...          │    │
│   │   모든 DTO는 Pydantic BaseModel                       │    │
│   │                                                      │    │
│   │   model_validate() / model_copy() 로 계층 간 변환     │    │
│   └─────────────────────┬────────────────────────────────┘    │
│                         │                                     │
│   ──────────────────────┼───── Domain Boundary ─────────────  │
│                         │                                     │
│   ┌─────────────────────┴────────────────────────────────┐    │
│   │                Domain Layer                           │    │
│   │   Query (Pydantic BaseModel + ClassVar + validate())  │    │
│   │   QueryRepository (ABC) ← 포트 인터페이스              │    │
│   │   DomainException 계층                                │    │
│   │                                                       │    │
│   │   허용: pydantic                                       │    │
│   │   금지: sqlmodel, sqlalchemy, fastapi, starlette       │    │
│   │   (AST 파싱 테스트로 자동 검증)                          │    │
│   └───────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘

의존성 방향: External → Application → Domain
Domain은 pydantic 외 아무것도 의존하지 않는다.
```

**Pydantic v2가 도메인에 허용되는 이유:**
Pydantic은 데이터 모델링 라이브러리로, HTTP나 DB 같은 인프라 관심사가 아닌
데이터 구조와 검증을 담당한다. `BaseModel`은 `dataclass`의 상위 호환이며,
`model_validate()`와 `model_copy()`로 계층 간 변환이 깔끔해진다.

**SQLModel이 도메인에 금지되는 이유:**
SQLModel은 내부적으로 SQLAlchemy를 import한다. 도메인에서 사용하면
ORM 의존성이 도메인에 침투하여 테스트 격리가 깨진다.

---

## 2. 사전 준비

### 2.1 필요한 도구

- Python 3.12+
- Docker Desktop
- uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### 2.2 의존성

`pyproject.toml`:
```toml
[project]
name = "query-repository"
version = "0.1.0"
description = "사내 쿼리 모음집 웹 애플리케이션"
requires-python = ">=3.12"
dependencies = [
    "fastapi==0.115.0",
    "uvicorn[standard]==0.30.6",
    "jinja2==3.1.4",
    "python-multipart==0.0.9",
    "sqlmodel>=0.0.22",
    "sqlalchemy[asyncio]>=2.0.35",
    "asyncpg==0.29.0",
    "psycopg2-binary==2.9.9",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

설치:
```bash
uv sync --extra dev
```

---

## 3. 인프라 구성

### 3.1 로컬 개발용 (`docker-compose.yml`)

PostgreSQL만 Docker로 실행. 앱은 로컬에서 직접 실행.

```yaml
version: '3.8'
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: root
      POSTGRES_PASSWORD: root
      POSTGRES_DB: query_book
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

포트가 `5433`인 이유: 로컬에 PostgreSQL이 이미 5432에서 실행 중일 수 있기 때문.

### 3.2 프로덕션용 (`docker-compose.prod.yml`)

App과 DB를 모두 Docker로 실행. DB healthcheck로 앱 시작 순서 보장.

```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    ports:
      - "80:8000"
    environment:
      DATABASE_URL: "postgresql+asyncpg://root:root@db:5432/query_book"
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: root
      POSTGRES_PASSWORD: root
      POSTGRES_DB: query_book
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U root -d query_book"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

프로덕션에서는 `DATABASE_URL`이 `db:5432`를 가리킨다 (Docker 내부 네트워크).

### 3.3 Dockerfile (멀티스테이지 빌드)

```dockerfile
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

COPY server/ server/

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/server /app/server

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**설계 결정:**
- builder 스테이지에서 uv로 의존성 설치 → 최종 이미지에는 uv 미포함
- `--frozen` 으로 lockfile 기반 재현 가능한 빌드
- `--no-dev` 으로 테스트 의존성 제외
- 최종 이미지는 python:3.12-slim + .venv + server/ 만 포함

---

## 4. 도메인 계층

### 4.1 도메인 모델

`server/core/domain/model/query.py`:
```python
from datetime import datetime
from typing import ClassVar, Optional

from pydantic import BaseModel, ConfigDict

from server.core.domain.exception.domain_exception import InvalidQueryException


class Query(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    title: str
    description: Optional[str] = None
    purpose: str  # 조회 | 수정 | 삭제 | 집계 | 기타
    tags: str = ""
    sql_text: str
    created_at: Optional[datetime] = None

    VALID_PURPOSES: ClassVar[tuple] = ("조회", "수정", "삭제", "집계", "기타")

    def validate(self) -> None:
        if not self.title or not self.title.strip():
            raise InvalidQueryException("제목은 필수입니다")
        if self.purpose not in self.VALID_PURPOSES:
            raise InvalidQueryException(f"유효하지 않은 용도: {self.purpose}")
        if not self.sql_text or not self.sql_text.strip():
            raise InvalidQueryException("SQL은 필수입니다")
```

**설계 결정:**
- `ConfigDict(from_attributes=True)`: SQLModel ORM 객체 → 도메인 변환에 `Query.model_validate(orm_obj)` 사용 가능
- `ClassVar[tuple]`: Pydantic이 필드로 인식하지 않도록 ClassVar 선언
- `validate()`: Pydantic 스키마 검증(타입)과 별도로 비즈니스 규칙 검증. Pydantic의 `@field_validator`를 사용하지 않은 이유는, 비즈니스 규칙 위반 시 `ValidationError`가 아닌 도메인 예외(`InvalidQueryException`)를 던지기 위함
- `model_copy(update={...})`: 서비스에서 엔티티 수정 시 불변 복사본 생성에 활용

### 4.2 도메인 예외

`server/core/domain/exception/domain_exception.py`:
```python
class DomainException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class QueryNotFoundException(DomainException):
    def __init__(self, query_id: int):
        super().__init__(f"쿼리를 찾을 수 없습니다: id={query_id}")
        self.query_id = query_id


class InvalidQueryException(DomainException):
    pass
```

### 4.3 저장소 포트

`server/core/domain/port/query_repository.py`:
```python
from abc import ABC, abstractmethod
from typing import List, Optional

from server.core.domain.model.query import Query


class QueryRepository(ABC):
    @abstractmethod
    async def find_all(self) -> List[Query]: pass

    @abstractmethod
    async def find_by_id(self, query_id: int) -> Optional[Query]: pass

    @abstractmethod
    async def find_by_criteria(
        self, purpose: Optional[str] = None, search: Optional[str] = None
    ) -> List[Query]: pass

    @abstractmethod
    async def save(self, query: Query) -> Query: pass

    @abstractmethod
    async def update(self, query: Query) -> Query: pass

    @abstractmethod
    async def delete(self, query_id: int) -> None: pass

    @abstractmethod
    async def count(self) -> int: pass
```

포트는 도메인 계층에 위치하며, 인프라 어댑터가 이 인터페이스를 구현한다.
이로써 도메인이 DB에 의존하는 것이 아니라, DB가 도메인에 의존하게 된다 (의존성 역전).

---

## 5. 애플리케이션 계층

### 5.1 DTO

`server/core/application/dto/query_dto.py`:
```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CreateQueryCommand(BaseModel):
    title: str
    description: Optional[str] = None
    purpose: str
    tags: str = ""
    sql_text: str


class UpdateQueryCommand(BaseModel):
    title: str
    description: Optional[str] = None
    purpose: str
    tags: str = ""
    sql_text: str


class QueryResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    purpose: str
    tags: str = ""
    sql_text: str
    created_at: datetime


class QuerySearchCriteria(BaseModel):
    purpose: Optional[str] = None
    search: Optional[str] = None
```

`QueryResult`에도 `from_attributes=True`를 설정하여
`QueryResult.model_validate(query_domain_obj)` 패턴으로 변환한다.

### 5.2 유스케이스 인터페이스

`server/core/application/usecase/query_usecase.py`:
```python
from abc import ABC, abstractmethod
from typing import List

from server.core.application.dto.query_dto import (
    CreateQueryCommand, UpdateQueryCommand, QueryResult, QuerySearchCriteria,
)


class QueryUseCase(ABC):
    @abstractmethod
    async def get_all_queries(self) -> List[QueryResult]: pass

    @abstractmethod
    async def get_query_by_id(self, query_id: int) -> QueryResult: pass

    @abstractmethod
    async def search_queries(self, criteria: QuerySearchCriteria) -> List[QueryResult]: pass

    @abstractmethod
    async def create_query(self, command: CreateQueryCommand) -> QueryResult: pass

    @abstractmethod
    async def update_query(self, query_id: int, command: UpdateQueryCommand) -> QueryResult: pass

    @abstractmethod
    async def delete_query(self, query_id: int) -> None: pass
```

### 5.3 서비스 구현

`server/core/application/service/query_service.py`:
```python
from typing import List

from server.core.application.dto.query_dto import (
    CreateQueryCommand, UpdateQueryCommand, QueryResult, QuerySearchCriteria,
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
```

**핵심 패턴:**
- `_to_result()`: `Query → QueryResult` 변환에 `model_validate()` 사용. 수동 필드 매핑 불필요
- `update_query()`: `existing.model_copy(update={...})`로 불변 업데이트. 기존 엔티티를 직접 수정하지 않음
- `validate()`: save/update 전 반드시 비즈니스 규칙 검증

---

## 6. 외부(인프라) 계층

### 6.1 데이터베이스 설정

`server/core/external/config/database.py`:
```python
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://root:root@localhost:5433/query_book",
)

engine = create_async_engine(DATABASE_URL, echo=False)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
```

`DATABASE_URL` 환경변수로 로컬/Docker/CI 환경 전환. `expire_on_commit=False`는 commit 후에도 ORM 속성 접근을 허용.

### 6.2 SQLModel ORM

`server/core/external/persistence/sqlalchemy_models.py`:
```python
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func


class QueryTable(SQLModel, table=True):
    __tablename__ = "queries"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    purpose: str
    tags: str = Field(default="")
    sql_text: str
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, default=func.now(), server_default=func.now()),
    )
```

**SQLModel과 도메인 Query의 관계:**
- `QueryTable`은 외부 계층에만 존재 (DB 테이블 매핑)
- `Query`는 도메인 계층에 존재 (비즈니스 엔티티)
- 어댑터가 `Query.model_validate(table_obj)`로 변환 (from_attributes=True 필요)

### 6.3 PostgreSQL 어댑터

`server/core/external/persistence/postgres_query_repository.py`:
```python
from typing import List, Optional

from sqlmodel import select
from sqlalchemy import delete as sa_delete, func, or_
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from server.core.domain.model.query import Query
from server.core.domain.port.query_repository import QueryRepository
from server.core.external.persistence.sqlalchemy_models import QueryTable


class PostgresQueryRepository(QueryRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    @staticmethod
    def _to_domain(model: QueryTable) -> Query:
        return Query.model_validate(model)

    async def find_all(self) -> List[Query]:
        async with self._session_factory() as session:
            stmt = select(QueryTable).order_by(QueryTable.created_at.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._to_domain(r) for r in rows]

    async def find_by_id(self, query_id: int) -> Optional[Query]:
        async with self._session_factory() as session:
            stmt = select(QueryTable).where(QueryTable.id == query_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return self._to_domain(row) if row else None

    async def find_by_criteria(
        self, purpose: Optional[str] = None, search: Optional[str] = None
    ) -> List[Query]:
        async with self._session_factory() as session:
            stmt = select(QueryTable)
            if purpose:
                stmt = stmt.where(QueryTable.purpose == purpose)
            if search:
                pattern = f"%{search}%"
                stmt = stmt.where(or_(
                    QueryTable.title.ilike(pattern),
                    QueryTable.description.ilike(pattern),
                    QueryTable.tags.ilike(pattern),
                    QueryTable.sql_text.ilike(pattern),
                ))
            stmt = stmt.order_by(QueryTable.created_at.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._to_domain(r) for r in rows]

    async def save(self, query: Query) -> Query:
        async with self._session_factory() as session:
            model = QueryTable(
                title=query.title, description=query.description,
                purpose=query.purpose, tags=query.tags, sql_text=query.sql_text,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def update(self, query: Query) -> Query:
        async with self._session_factory() as session:
            stmt = select(QueryTable).where(QueryTable.id == query.id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is None:
                raise ValueError(f"Query not found: id={query.id}")
            model.title = query.title
            model.description = query.description
            model.purpose = query.purpose
            model.tags = query.tags
            model.sql_text = query.sql_text
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def delete(self, query_id: int) -> None:
        async with self._session_factory() as session:
            stmt = sa_delete(QueryTable).where(QueryTable.id == query_id)
            await session.execute(stmt)
            await session.commit()

    async def count(self) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(QueryTable)
            result = await session.execute(stmt)
            return result.scalar_one()
```

**변환 흐름:**
```
save:   Query(도메인) → QueryTable(ORM) → DB INSERT → QueryTable → Query(도메인)
read:   DB SELECT → QueryTable(ORM) → Query.model_validate() → Query(도메인)
```

### 6.4 API 라우터

`server/core/external/api/query_router.py`:

| 메서드 | 경로 | 기능 | 성공 응답 |
|--------|------|------|-----------|
| GET | `/` | 목록 (필터/검색) | 200 HTML |
| POST | `/add` | 쿼리 추가 | 303 → `/` |
| GET | `/edit/{id}` | 수정 폼 | 200 HTML (모달 오픈) |
| POST | `/edit/{id}` | 쿼리 수정 | 303 → `/` |
| POST | `/delete/{id}` | 쿼리 삭제 | 303 → `/` |

검색 파라미터는 `q` (HTML form의 name과 일치). 라우터 내부에서 `QuerySearchCriteria(search=q)` 로 변환.

에러 처리:
- `InvalidQueryException` → 400 + 에러 메시지 포함 HTML
- `QueryNotFoundException` → 303 리다이렉트 (graceful)
- POST 성공 → 303 (PRG 패턴으로 중복 제출 방지)

---

## 7. 진입점

`server/main.py`:
```python
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from sqlmodel import SQLModel

from server.core.external.config.database import engine, async_session_factory
from server.core.external.persistence.postgres_query_repository import PostgresQueryRepository
from server.core.application.service.query_service import QueryService
from server.core.external.api.query_router import create_query_router
from server.seed import SEED_QUERIES

logger = logging.getLogger(__name__)


async def _init_db() -> None:
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
    repository = PostgresQueryRepository(async_session_factory)
    service = QueryService(repository)
    router = create_query_router(service)
    app.include_router(router)
    return app


app = create_app()
```

**DI 와이어링 (수동):**
```
async_session_factory
  └→ PostgresQueryRepository (어댑터)
       └→ QueryService (유스케이스 구현)
            └→ create_query_router (라우터)
                 └→ app.include_router()
```

DI 프레임워크 없이 `create_app()`에서 수동 조립.
프로젝트 규모에 DI 컨테이너는 과도하며, 명시적 와이어링이 디버깅에 유리.

---

## 8. 프론트엔드

### 8.1 구조

단일 `server/templates/index.html` 파일에 HTML + CSS(`<style>`) + JS(`<script>`) 모두 포함.

### 8.2 다크 테마 색상

| 요소 | 색상 |
|------|------|
| 배경 | `#0f1117` |
| 카드 | `#1a1d27` → hover `#222636` |
| 헤더 | `#161822` |
| 텍스트 | `#e2e8f0` / 보조 `#94a3b8` |
| 테두리 | `#2d3348` |

용도 배지: 조회(파랑), 수정(노랑), 삭제(빨강), 집계(보라), 기타(회색).

### 8.3 SQL 구문 강조

바닐라 JS로 구현. 외부 라이브러리 없음.

**처리 순서:**
1. `data-raw` 속성에서 원본 SQL 읽기
2. `formatSQL()`: 토크나이저 → 키워드별 줄바꿈 + 들여쓰기
3. `highlightSQL()`: 문자 단위 파싱 → 토큰 분류 → HTML span 래핑
4. `DOMContentLoaded` 이벤트에서 모든 `.sql-code` 요소에 적용

**토큰 색상:**

| 클래스 | 대상 | 색상 |
|--------|------|------|
| `.kw` | SQL 키워드 (SELECT, FROM, ...) | `#c792ea` 보라 |
| `.fn` | 함수 (COUNT, SUM, NOW, ...) | `#82aaff` 파랑 |
| `.str` | 문자열 리터럴 ('...') | `#c3e88d` 초록 |
| `.num` | 숫자 | `#f78c6c` 주황 |
| `.op` | 연산자 (=, <, >, *) | `#89ddff` 시안 |
| `.cmt` | 주석 (-- ...) | `#546e7a` 회색 |

**복사 기능:** `data-raw` 속성에서 원본(포맷팅 전) SQL을 가져와 클립보드에 복사.
사용자가 복사한 SQL은 항상 원본 형태.

### 8.4 주요 상호작용

- 검색: 400ms 디바운스 후 자동 form submit (GET)
- SQL 토글: 카드 클릭 → `.open` 클래스 토글
- 모달: 외부 클릭 / ESC 키로 닫힘
- 수정: `edit_query`가 있으면 모달 자동 오픈 (`.open` 클래스)
- 삭제: `confirm()` 대화상자 → hidden form POST

---

## 9. 테스트

### 9.1 테스트 전략

| 계층 | 파일 | 수 | 인프라 | 검증 대상 |
|------|------|-----|--------|-----------|
| 도메인 | test_domain.py | 13 | 없음 | 엔티티, 검증, 예외, 순수성(AST) |
| 애플리케이션 | test_application.py | 11 | InMemoryRepo | 서비스 로직, CRUD, 검색 |
| 통합 | test_api_integration.py | 10 | PostgreSQL | HTTP 전체 사이클 |

### 9.2 도메인 순수성 검증 (AST)

`test_domain.py::TestDomainPurity`에서 도메인 계층의 모든 `.py` 파일을
Python AST로 파싱하여 금지 모듈 import를 자동 검출:

```python
forbidden = {"fastapi", "sqlalchemy", "sqlmodel", "uvicorn", "starlette", "httpx"}
# pydantic은 허용
```

### 9.3 InMemoryQueryRepository

`test_application.py`에서 `QueryRepository` 포트의 인메모리 구현체를 작성.
이것이 포트-어댑터 패턴의 핵심 증명: 동일한 `QueryService`가 PostgreSQL 없이도 동작.

```python
class InMemoryQueryRepository(QueryRepository):
    def __init__(self):
        self._store: dict[int, Query] = {}
        self._next_id: int = 1

    async def save(self, query: Query) -> Query:
        saved = query.model_copy(update={"id": self._next_id, "created_at": datetime.now()})
        self._next_id += 1
        self._store[saved.id] = saved
        return saved
    # ... 나머지 메서드
```

`model_copy(update={...})`로 Pydantic 모델의 불변 복사본을 생성.

### 9.4 통합 테스트

각 테스트마다 독립 FastAPI 앱 + SQLAlchemy 엔진을 생성하고,
DB를 초기화(DELETE) → 시드 삽입 → 테스트 → 정리(DELETE) → 엔진 해제.

```bash
uv run python -m pytest tests/ -v    # 33 passed
```

---

## 10. CI/CD

`.github/workflows/deploy.yml`:

```
main 브랜치 push
  ├→ test job: PostgreSQL 서비스 컨테이너 + uv sync + pytest
  └→ deploy job (test 통과 후): SSH → git pull → docker compose build → up
```

---

## 11. 실행 방법

### 로컬 개발

```bash
docker compose up -d
uv sync --extra dev
uv run uvicorn server.main:app --reload
# http://localhost:8000
```

### 프로덕션 (Docker)

```bash
docker compose -f docker-compose.prod.yml up -d --build
# http://localhost
```

### 테스트

```bash
uv run python -m pytest tests/ -v
```

---

## 12. 아키텍처 의사결정 기록 (ADR)

### ADR-1: Pydantic v2 BaseModel을 도메인 모델로 채택

- **결정:** dataclass 대신 Pydantic v2 BaseModel 사용
- **근거:** `model_validate(orm_obj)`로 ORM↔도메인 변환이 1줄, `model_copy(update={})`로 불변 업데이트, `ConfigDict(from_attributes=True)`로 SQLModel 객체 직접 변환
- **트레이드오프:** 도메인에 pydantic 의존성 추가. 그러나 pydantic은 데이터 모델링 라이브러리이지 인프라 프레임워크가 아님

### ADR-2: SQLModel을 ORM으로 채택 (외부 계층만)

- **결정:** SQLAlchemy DeclarativeBase 대신 SQLModel 사용
- **근거:** Pydantic + SQLAlchemy 통합으로 ORM 모델 코드 50% 감소, 타입 힌트 기반 컬럼 정의
- **트레이드오프:** SQLModel은 내부적으로 sqlalchemy를 import하므로 도메인에서 사용 불가. 외부 계층(`QueryTable`)에서만 사용

### ADR-3: NAT Instance 기반 AWS 배포

- **결정:** NAT Gateway($32/월) 대신 NAT Instance(t3.nano, $3/월) 사용
- **근거:** 내부 도구이므로 고가용성 불필요. 비용 90% 절감
- **트레이드오프:** 단일 장애점, 수동 복구 필요. 내부 도구에는 허용 가능

### ADR-4: 바닐라 JS SQL 포맷터

- **결정:** sql-formatter CDN 대신 자체 구현
- **근거:** 요구사항의 "JS 프레임워크 금지" 원칙 준수, 외부 CDN 의존성 제거, 프로젝트 SQL은 단순하여 자체 구현으로 충분
- **트레이드오프:** 복잡한 SQL(서브쿼리 중첩 등)에서 포맷팅 품질이 전문 라이브러리 대비 낮을 수 있음

### ADR-5: uv 패키지 관리

- **결정:** pip/poetry 대신 uv 사용
- **근거:** 의존성 해결 10~100배 빠름, lockfile 기반 재현 가능한 빌드, Docker 멀티스테이지 빌드에서 `--frozen` 플래그로 캐시 최적화
- **트레이드오프:** 상대적으로 새로운 도구. 그러나 Astral 사에서 적극 유지보수 중

---

## 부록: 개발 과정에서 발견된 버그와 수정

| 버그 | 원인 | 수정 |
|------|------|------|
| 검색 동작 안 함 | 라우터가 `search` 파라미터를 기대, 폼은 `q`로 전송 | 라우터 파라미터명을 `q`로 변경 |
| 태그가 글자별로 나뉨 | `{% for tag in query.tags %}` → 문자열 순회 | `query.tags.split(',')` 으로 수정 |
| 수정 폼에 "None" 표시 | `{{ edit_query.description }}` → None 문자열 출력 | `{{ edit_query.description or '' }}` 로 수정 |
| 수정 시 기존 엔티티 변경 | 기존 Query 객체를 직접 수정 | `model_copy(update={...})`로 불변 복사본 생성 |
