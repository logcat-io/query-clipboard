# 사내 쿼리 모음집 - 구현 가이드

이 문서는 "사내 쿼리 모음집" 웹 애플리케이션의 전체 구현 과정을 단계별로 기록한 것입니다.
이 문서만으로 프로젝트를 처음부터 다시 구축할 수 있습니다.

---

## 1. 프로젝트 개요

### 1.1 목적
팀 내에서 자주 사용하는 SQL 쿼리를 한 곳에 모아두고,
필요할 때 검색하여 복사해 쓰는 내부 도구입니다.

### 1.2 기술 스택

| 영역 | 기술 |
|------|------|
| 백엔드 프레임워크 | Python FastAPI |
| 템플릿 엔진 | Jinja2 (서버사이드 렌더링) |
| 데이터베이스 | PostgreSQL 16 (Docker) |
| ORM | SQLAlchemy 2.0 (async) |
| DB 드라이버 | asyncpg |
| 프론트엔드 | 순수 HTML + CSS + 바닐라 JavaScript |
| 아키텍처 | 헥사고날 (포트-어댑터 패턴) |

### 1.3 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│                    External Layer                        │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  FastAPI  │  │  PostgreSQL  │  │  Jinja2 Templates │  │
│  │  Router   │  │  Adapter     │  │                   │  │
│  └─────┬─────┘  └──────┬───────┘  └───────────────────┘  │
│        │               │                                  │
│  ──────┼───────────────┼──────── Port Boundary ────────── │
│        │               │                                  │
│  ┌─────┴───────────────┴─────────────────────────────┐   │
│  │              Application Layer                     │   │
│  │  ┌─────────────┐  ┌────────┐  ┌───────────────┐   │   │
│  │  │ QueryService│  │  DTOs  │  │ QueryUseCase  │   │   │
│  │  │ (구현체)     │  │        │  │ (인터페이스)    │   │   │
│  │  └──────┬──────┘  └────────┘  └───────────────┘   │   │
│  │         │                                          │   │
│  │  ───────┼────────── Domain Boundary ────────────── │   │
│  │         │                                          │   │
│  │  ┌──────┴──────────────────────────────────────┐   │   │
│  │  │              Domain Layer                    │   │   │
│  │  │  ┌───────┐  ┌──────────────┐  ┌──────────┐  │   │   │
│  │  │  │ Query │  │ QueryRepo    │  │ Domain   │  │   │   │
│  │  │  │ Model │  │ Port (ABC)   │  │ Exceptions│ │   │   │
│  │  │  └───────┘  └──────────────┘  └──────────┘  │   │   │
│  │  │  프레임워크 의존성 ZERO                        │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

의존성 방향: External → Application → Domain
Domain은 아무것도 의존하지 않는다.
```

---

## 2. 사전 준비

### 2.1 필요한 도구
- Python 3.11 이상
- Docker Desktop
- pip (Python 패키지 관리자)

### 2.2 의존성 설치

`requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
jinja2==3.1.4
python-multipart==0.0.9
sqlalchemy[asyncio]==2.0.35
asyncpg==0.29.0
psycopg2-binary==2.9.9
```

테스트 의존성 (별도 설치):
```
pytest
pytest-asyncio
httpx
```

설치 명령:
```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx
```

---

## 3. 인프라 구성

### 3.1 Docker Compose로 PostgreSQL 실행

`docker-compose.yml`:
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

**설계 결정**: 포트를 `5433`으로 매핑한 이유는 로컬에 이미 PostgreSQL이 5432에서 실행 중일 수 있기 때문입니다.

실행:
```bash
docker compose up -d
```

확인:
```bash
docker compose exec db pg_isready -U root -d query_book
```

---

## 4. 프로젝트 디렉토리 구조

```
query-repository/
├── docker-compose.yml              # PostgreSQL 컨테이너 설정
├── requirements.txt                # Python 의존성
├── server/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 앱 진입점, DI 와이어링
│   ├── seed.py                     # 샘플 데이터 5개
│   ├── templates/
│   │   └── index.html              # Jinja2 템플릿 (HTML+CSS+JS)
│   └── core/
│       ├── __init__.py
│       ├── domain/                 # 도메인 계층 (프레임워크 의존성 ZERO)
│       │   ├── __init__.py
│       │   ├── model/
│       │   │   ├── __init__.py
│       │   │   └── query.py        # Query 엔티티
│       │   ├── port/
│       │   │   ├── __init__.py
│       │   │   └── query_repository.py  # 저장소 인터페이스 (ABC)
│       │   └── exception/
│       │       ├── __init__.py
│       │       └── domain_exception.py  # 도메인 예외
│       ├── application/            # 애플리케이션 계층
│       │   ├── __init__.py
│       │   ├── dto/
│       │   │   ├── __init__.py
│       │   │   └── query_dto.py    # Command, Result, Criteria
│       │   ├── usecase/
│       │   │   ├── __init__.py
│       │   │   └── query_usecase.py # 유스케이스 인터페이스
│       │   └── service/
│       │       ├── __init__.py
│       │       └── query_service.py # 유스케이스 구현체
│       └── external/               # 외부(인프라) 계층
│           ├── __init__.py
│           ├── config/
│           │   ├── __init__.py
│           │   └── database.py     # SQLAlchemy 엔진/세션 팩토리
│           ├── persistence/
│           │   ├── __init__.py
│           │   ├── sqlalchemy_models.py      # ORM 모델
│           │   └── postgres_query_repository.py # PostgreSQL 어댑터
│           └── api/
│               ├── __init__.py
│               └── query_router.py  # FastAPI 라우터
├── tests/
│   ├── conftest.py                 # 테스트 픽스처
│   ├── test_domain.py              # 도메인 테스트 (13개)
│   ├── test_application.py         # 애플리케이션 테스트 (11개)
│   └── test_api_integration.py     # 통합 테스트 (10개)
└── docs/
    └── implementation-guide.md     # 이 문서
```

### 계층별 역할

| 계층 | 역할 | 의존 대상 |
|------|------|-----------|
| domain | 비즈니스 엔티티, 규칙, 인터페이스 정의 | 없음 (순수 Python) |
| application | 유스케이스 오케스트레이션, DTO 변환 | domain |
| external | 인프라 구현 (DB, HTTP, 설정) | application, domain |

---

## 5. 도메인 계층 구현

### 5.1 도메인 모델 (Query)

**파일**: `server/core/domain/model/query.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from server.core.domain.exception.domain_exception import InvalidQueryException


@dataclass
class Query:
    id: Optional[int]
    title: str
    description: Optional[str]
    purpose: str  # 조회 | 수정 | 삭제 | 집계 | 기타
    tags: str
    sql_text: str
    created_at: Optional[datetime] = field(default=None)

    VALID_PURPOSES = ("조회", "수정", "삭제", "집계", "기타")

    def validate(self) -> None:
        if not self.title or not self.title.strip():
            raise InvalidQueryException("제목은 필수입니다")
        if self.purpose not in self.VALID_PURPOSES:
            raise InvalidQueryException(f"유효하지 않은 용도: {self.purpose}")
        if not self.sql_text or not self.sql_text.strip():
            raise InvalidQueryException("SQL은 필수입니다")
```

**설계 결정**:
- `dataclass`를 사용하여 프레임워크 없이 순수 Python 엔티티를 정의
- `validate()` 메서드를 엔티티에 배치하여 도메인 규칙을 도메인 내부에서 관리
- `VALID_PURPOSES`를 클래스 레벨 상수로 정의하여 유효한 용도를 도메인에서 통제
- `tags`는 쉼표 구분 문자열로 관리 (단순성 우선)

### 5.2 도메인 예외

**파일**: `server/core/domain/exception/domain_exception.py`

```python
class DomainException(Exception):
    """Base exception for domain layer."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class QueryNotFoundException(DomainException):
    """Raised when a query is not found."""

    def __init__(self, query_id: int):
        super().__init__(f"쿼리를 찾을 수 없습니다: id={query_id}")
        self.query_id = query_id


class InvalidQueryException(DomainException):
    """Raised when a query fails validation."""
    pass
```

**설계 결정**:
- `DomainException` 기반 클래스로 도메인 예외 계층 구성
- `message` 속성으로 에러 메시지 접근 가능
- `QueryNotFoundException`에 `query_id` 속성 포함하여 디버깅 용이

### 5.3 저장소 포트 (인터페이스)

**파일**: `server/core/domain/port/query_repository.py`

```python
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
        self, purpose: Optional[str] = None, search: Optional[str] = None
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
```

**설계 결정**:
- ABC(Abstract Base Class)로 인터페이스 정의
- 도메인 계층에 위치하여, 도메인이 인프라에 의존하지 않고 인프라가 도메인의 인터페이스를 구현하는 구조
- 모든 메서드가 `async`로 정의되어 비동기 어댑터를 지원
- `find_by_criteria`로 검색/필터링 기능을 포트 레벨에서 정의

### 5.4 설계 원칙: 프레임워크 독립성

도메인 계층의 모든 파일은 다음 모듈을 **절대 import하지 않습니다**:
- `fastapi`, `starlette`
- `sqlalchemy`
- `uvicorn`
- `pydantic`
- `httpx`

이는 테스트 코드(`test_domain.py`)에서 AST 파싱으로 자동 검증됩니다.

---

## 6. 애플리케이션 계층 구현

### 6.1 DTO (Data Transfer Object)

**파일**: `server/core/application/dto/query_dto.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CreateQueryCommand:
    title: str
    description: Optional[str]
    purpose: str
    tags: str
    sql_text: str


@dataclass
class UpdateQueryCommand:
    title: str
    description: Optional[str]
    purpose: str
    tags: str
    sql_text: str


@dataclass
class QueryResult:
    id: int
    title: str
    description: Optional[str]
    purpose: str
    tags: str
    sql_text: str
    created_at: datetime


@dataclass
class QuerySearchCriteria:
    purpose: Optional[str] = None
    search: Optional[str] = None
```

**설계 결정**:
- Command 패턴: `CreateQueryCommand`, `UpdateQueryCommand`로 쓰기 작업의 입력을 명시적으로 표현
- `QueryResult`: 읽기 전용 응답 DTO. 도메인 엔티티를 직접 외부에 노출하지 않음
- `QuerySearchCriteria`: 검색 조건을 객체로 캡슐화하여 파라미터 확장에 유연

### 6.2 유스케이스 인터페이스

**파일**: `server/core/application/usecase/query_usecase.py`

```python
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
```

**설계 결정**:
- API 라우터는 `QueryUseCase` 인터페이스에만 의존하여, 구현체 교체가 자유로움
- DTO를 통해 입출력을 정의하여 계층 간 계약이 명확

### 6.3 서비스 구현

**파일**: `server/core/application/service/query_service.py`

```python
from typing import List

from server.core.application.dto.query_dto import (
    CreateQueryCommand,
    UpdateQueryCommand,
    QueryResult,
    QuerySearchCriteria,
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
        return QueryResult(
            id=query.id,
            title=query.title,
            description=query.description,
            purpose=query.purpose,
            tags=query.tags,
            sql_text=query.sql_text,
            created_at=query.created_at,
        )

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
            id=None,
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

        existing.title = command.title
        existing.description = command.description
        existing.purpose = command.purpose
        existing.tags = command.tags
        existing.sql_text = command.sql_text
        existing.validate()

        updated = await self._repository.update(existing)
        return self._to_result(updated)

    async def delete_query(self, query_id: int) -> None:
        existing = await self._repository.find_by_id(query_id)
        if existing is None:
            raise QueryNotFoundException(query_id)
        await self._repository.delete(query_id)
```

**유효성 검증 흐름**:
1. Command DTO를 받아 도메인 엔티티 `Query`로 변환
2. `query.validate()` 호출 — 도메인 규칙 검증
3. 검증 통과 시 저장소 포트를 통해 영속화
4. 결과를 `QueryResult` DTO로 변환하여 반환

**의존성 방향**:
- `QueryService` → `QueryRepository` (포트, 인터페이스)
- `QueryService` → `Query` (도메인 모델)
- 절대로 SQLAlchemy나 FastAPI를 import하지 않음

---

## 7. 외부(인프라) 계층 구현

### 7.1 데이터베이스 설정

**파일**: `server/core/external/config/database.py`

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

**설계 결정**:
- 환경 변수 `DATABASE_URL`로 오버라이드 가능 (테스트/배포 환경 분리)
- `expire_on_commit=False`로 커밋 후에도 객체 속성 접근 가능
- `asyncpg` 드라이버로 비동기 DB 접근

### 7.2 ORM 모델

**파일**: `server/core/external/persistence/sqlalchemy_models.py`

```python
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class QueryModel(Base):
    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    purpose = Column(String, nullable=False)
    tags = Column(String, default="")
    sql_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now(), server_default=func.now())
```

**설계 결정**:
- ORM 모델은 `external` 계층에 위치 — 도메인 모델과 분리
- `server_default=func.now()`로 DB 레벨에서도 기본값 보장
- 도메인 `Query`와 ORM `QueryModel`은 별개 객체 — 어댑터에서 변환

### 7.3 PostgreSQL 어댑터

**파일**: `server/core/external/persistence/postgres_query_repository.py`

```python
from typing import List, Optional

from sqlalchemy import select, delete as sa_delete, func, or_
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from server.core.domain.model.query import Query
from server.core.domain.port.query_repository import QueryRepository
from server.core.external.persistence.sqlalchemy_models import QueryModel


class PostgresQueryRepository(QueryRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    @staticmethod
    def _to_domain(model: QueryModel) -> Query:
        return Query(
            id=model.id,
            title=model.title,
            description=model.description,
            purpose=model.purpose,
            tags=model.tags or "",
            sql_text=model.sql_text,
            created_at=model.created_at,
        )

    @staticmethod
    def _to_model(query: Query) -> QueryModel:
        return QueryModel(
            id=query.id,
            title=query.title,
            description=query.description,
            purpose=query.purpose,
            tags=query.tags,
            sql_text=query.sql_text,
            created_at=query.created_at,
        )

    async def find_all(self) -> List[Query]:
        async with self._session_factory() as session:
            stmt = select(QueryModel).order_by(QueryModel.created_at.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._to_domain(r) for r in rows]

    async def find_by_id(self, query_id: int) -> Optional[Query]:
        async with self._session_factory() as session:
            stmt = select(QueryModel).where(QueryModel.id == query_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return self._to_domain(row) if row else None

    async def find_by_criteria(
        self, purpose: Optional[str] = None, search: Optional[str] = None
    ) -> List[Query]:
        async with self._session_factory() as session:
            stmt = select(QueryModel)

            if purpose:
                stmt = stmt.where(QueryModel.purpose == purpose)

            if search:
                search_pattern = f"%{search}%"
                stmt = stmt.where(
                    or_(
                        QueryModel.title.ilike(search_pattern),
                        QueryModel.description.ilike(search_pattern),
                        QueryModel.tags.ilike(search_pattern),
                        QueryModel.sql_text.ilike(search_pattern),
                    )
                )

            stmt = stmt.order_by(QueryModel.created_at.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._to_domain(r) for r in rows]

    async def save(self, query: Query) -> Query:
        async with self._session_factory() as session:
            model = QueryModel(
                title=query.title,
                description=query.description,
                purpose=query.purpose,
                tags=query.tags,
                sql_text=query.sql_text,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_domain(model)

    async def update(self, query: Query) -> Query:
        async with self._session_factory() as session:
            stmt = select(QueryModel).where(QueryModel.id == query.id)
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
            stmt = sa_delete(QueryModel).where(QueryModel.id == query_id)
            await session.execute(stmt)
            await session.commit()

    async def count(self) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(QueryModel)
            result = await session.execute(stmt)
            return result.scalar_one()
```

**핵심 설계**:
- `_to_domain()`: ORM 모델 → 도메인 엔티티 변환
- `_to_model()`: 도메인 엔티티 → ORM 모델 변환 (양방향 변환)
- 각 메서드에서 세션을 새로 생성하여 트랜잭션 격리
- `find_by_criteria`에서 `ilike`로 대소문자 무관 검색

### 7.4 API 라우터

**파일**: `server/core/external/api/query_router.py`

```python
import os
from typing import Optional

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from server.core.application.dto.query_dto import (
    CreateQueryCommand,
    UpdateQueryCommand,
    QuerySearchCriteria,
)
from server.core.application.usecase.query_usecase import QueryUseCase
from server.core.domain.exception.domain_exception import (
    QueryNotFoundException,
    InvalidQueryException,
)

PURPOSES = ["조회", "수정", "삭제", "집계", "기타"]

templates_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "templates")
templates = Jinja2Templates(directory=os.path.abspath(templates_dir))


def create_query_router(use_case: QueryUseCase) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def index(
        request: Request,
        purpose: Optional[str] = None,
        q: Optional[str] = None,
    ):
        criteria = QuerySearchCriteria(
            purpose=purpose if purpose else None,
            search=q if q else None,
        )

        if criteria.purpose or criteria.search:
            queries = await use_case.search_queries(criteria)
        else:
            queries = await use_case.get_all_queries()

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "queries": queries,
                "purposes": PURPOSES,
                "current_purpose": purpose or "",
                "search_query": q or "",
                "edit_query": None,
            },
        )

    @router.post("/add")
    async def add_query(
        request: Request,
        title: str = Form(...),
        description: Optional[str] = Form(None),
        purpose: str = Form(...),
        tags: str = Form(""),
        sql_text: str = Form(...),
    ):
        try:
            command = CreateQueryCommand(
                title=title,
                description=description if description else None,
                purpose=purpose,
                tags=tags,
                sql_text=sql_text,
            )
            await use_case.create_query(command)
            return RedirectResponse(url="/", status_code=303)
        except InvalidQueryException as e:
            queries = await use_case.get_all_queries()
            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "queries": queries,
                    "purposes": PURPOSES,
                    "current_purpose": "",
                    "search_query": "",
                    "edit_query": None,
                    "error": e.message,
                },
                status_code=400,
            )

    @router.get("/edit/{query_id}")
    async def edit_query_form(
        request: Request,
        query_id: int,
        purpose: Optional[str] = None,
        q: Optional[str] = None,
    ):
        try:
            edit_query = await use_case.get_query_by_id(query_id)

            criteria = QuerySearchCriteria(
                purpose=purpose if purpose else None,
                search=q if q else None,
            )
            if criteria.purpose or criteria.search:
                queries = await use_case.search_queries(criteria)
            else:
                queries = await use_case.get_all_queries()

            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "queries": queries,
                    "purposes": PURPOSES,
                    "current_purpose": purpose or "",
                    "search_query": q or "",
                    "edit_query": edit_query,
                },
            )
        except QueryNotFoundException:
            return RedirectResponse(url="/", status_code=303)

    @router.post("/edit/{query_id}")
    async def update_query(
        request: Request,
        query_id: int,
        title: str = Form(...),
        description: Optional[str] = Form(None),
        purpose: str = Form(...),
        tags: str = Form(""),
        sql_text: str = Form(...),
    ):
        try:
            command = UpdateQueryCommand(
                title=title,
                description=description if description else None,
                purpose=purpose,
                tags=tags,
                sql_text=sql_text,
            )
            await use_case.update_query(query_id, command)
            return RedirectResponse(url="/", status_code=303)
        except QueryNotFoundException:
            return RedirectResponse(url="/", status_code=303)
        except InvalidQueryException as e:
            queries = await use_case.get_all_queries()
            edit_query = None
            try:
                edit_query = await use_case.get_query_by_id(query_id)
            except QueryNotFoundException:
                pass
            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "queries": queries,
                    "purposes": PURPOSES,
                    "current_purpose": "",
                    "search_query": "",
                    "edit_query": edit_query,
                    "error": e.message,
                },
                status_code=400,
            )

    @router.post("/delete/{query_id}")
    async def delete_query(query_id: int):
        try:
            await use_case.delete_query(query_id)
        except QueryNotFoundException:
            pass
        return RedirectResponse(url="/", status_code=303)

    return router
```

**엔드포인트 정리**:

| 메서드 | 경로 | 기능 | 성공 응답 |
|--------|------|------|-----------|
| GET | `/` | 목록 조회 (필터/검색) | 200 + HTML |
| POST | `/add` | 쿼리 추가 | 303 → `/` |
| GET | `/edit/{id}` | 수정 폼 표시 | 200 + HTML (모달 오픈) |
| POST | `/edit/{id}` | 쿼리 수정 | 303 → `/` |
| POST | `/delete/{id}` | 쿼리 삭제 | 303 → `/` |

**에러 처리 전략**:
- `InvalidQueryException` → 400 응답 + 에러 메시지 포함 렌더링
- `QueryNotFoundException` → 303 리다이렉트 (사용자에게 graceful한 경험)
- POST 성공 시 항상 303 (POST-Redirect-GET 패턴으로 중복 제출 방지)

---

## 8. 프론트엔드 (Jinja2 템플릿)

### 8.1 전체 구조

**파일**: `server/templates/index.html`

단일 HTML 파일에 모든 CSS와 JavaScript를 포함합니다.

```
index.html
├── <head>
│   ├── Pretendard 폰트 CDN
│   ├── IBM Plex Mono 폰트 (Google Fonts)
│   └── <style> (전체 CSS)
├── <body>
│   ├── <header> (스티키 헤더)
│   ├── .container
│   │   ├── .filter-bar (필터 버튼 + 검색)
│   │   ├── .query-card (쿼리 카드 목록) × N
│   │   └── .empty-state (비어있을 때)
│   ├── #addModal (추가 모달)
│   ├── #editModal (수정 모달, edit_query가 있을 때만)
│   └── <script> (전체 JavaScript)
```

### 8.2 UI 컴포넌트별 설명

#### 헤더
- sticky 고정 (top: 0, z-index: 100)
- 좌측: "쿼리 모음집" 타이틀
- 우측: "+ 쿼리 추가" 버튼

#### 필터바
- 용도별 필터 버튼: `전체` / `조회` / `수정` / `삭제` / `집계` / `기타`
- 각 버튼은 `<a>` 태그로 `/?purpose=조회` 형태의 링크
- 검색어가 있을 때 필터 링크에 `&q=검색어` 보존
- 현재 선택된 필터에 `.active` 클래스 적용

#### 검색
- `<form>` 태그로 GET 요청
- hidden input으로 현재 `purpose` 유지
- `oninput` 이벤트에 400ms 디바운스 적용 후 자동 submit

#### 쿼리 카드
- 카드 클릭 → SQL 섹션 토글 (display: none ↔ block)
- 용도 배지: CSS 클래스 `.purpose-조회`, `.purpose-수정` 등으로 색상 분리
- 태그: `query.tags.split(',')` 으로 분리하여 pill 형태로 표시
- 수정 버튼: `<a href="/edit/{{ query.id }}">`
- 삭제 버튼: hidden form + confirm 대화상자

#### 모달
- `.modal-overlay`: 전체 화면 반투명 오버레이
- `.modal-box`: 중앙 정렬 폼 박스
- 외부 클릭 또는 ESC 키로 닫힘
- edit_query가 존재하면 수정 모달이 자동으로 열림 (`.open` 클래스)

### 8.3 JavaScript 기능

```javascript
// 1. 검색 디바운스 (400ms)
let searchTimeout;
function debounceSearch(input) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(function() {
        document.getElementById('searchForm').submit();
    }, 400);
}

// 2. SQL 토글
function toggleSQL(sectionId) {
    var section = document.getElementById(sectionId);
    section.classList.toggle('open');
}

// 3. 클립보드 복사
async function copySQL(btn, sqlText) {
    await navigator.clipboard.writeText(sqlText);
    btn.textContent = '✓ 복사됨';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = '복사'; btn.classList.remove('copied'); }, 1800);
}

// 4. 모달 열기/닫기
function openModal(modalId) { document.getElementById(modalId).classList.add('open'); }
function closeModal(modalId) { document.getElementById(modalId).classList.remove('open'); }

// 5. 삭제 확인
function confirmDelete(queryId) {
    if (confirm('정말 삭제하시겠습니까?')) {
        document.getElementById('deleteForm-' + queryId).submit();
    }
}
```

### 8.4 스타일링

#### 색상 체계 (다크 테마)
| 요소 | 색상 |
|------|------|
| 배경 | `#0f1117` |
| 카드 배경 | `#1a1d27` |
| 카드 hover | `#222636` |
| 헤더 배경 | `#161822` |
| 텍스트 기본 | `#e2e8f0` |
| 텍스트 보조 | `#94a3b8` |
| 테두리 | `#2d3348` |

#### 용도별 배지 색상
| 용도 | 배경 | 글자 |
|------|------|------|
| 조회 | `rgba(59,130,246,0.15)` | `#3b82f6` |
| 수정 | `rgba(245,158,11,0.15)` | `#f59e0b` |
| 삭제 | `rgba(239,68,68,0.15)` | `#ef4444` |
| 집계 | `rgba(167,139,250,0.15)` | `#a78bfa` |
| 기타 | `rgba(148,163,184,0.15)` | `#94a3b8` |

#### 폰트
- UI: Pretendard (CDN)
- 코드/SQL: IBM Plex Mono (Google Fonts)

---

## 9. 애플리케이션 진입점

### 9.1 main.py

**파일**: `server/main.py`

```python
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from server.core.external.config.database import engine, async_session_factory
from server.core.external.persistence.sqlalchemy_models import Base
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
        await conn.run_sync(Base.metadata.create_all)

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

    # Wire dependencies (수동 DI)
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
```

**DI 와이어링 흐름**:
1. `PostgresQueryRepository(async_session_factory)` — 어댑터 생성
2. `QueryService(repository)` — 서비스에 포트(인터페이스) 주입
3. `create_query_router(service)` — 라우터에 유스케이스 주입
4. `app.include_router(router)` — FastAPI에 라우터 등록

### 9.2 시드 데이터

**파일**: `server/seed.py`

```python
from server.core.domain.model.query import Query

SEED_QUERIES = [
    Query(
        id=None,
        title="활성 사용자 조회",
        description="현재 활성 상태인 사용자 목록을 최신순으로 조회합니다.",
        purpose="조회",
        tags="user,active",
        sql_text="SELECT * FROM users WHERE is_active = true ORDER BY created_at DESC;",
    ),
    Query(
        id=None,
        title="주문 금액 집계",
        description="일별 주문 금액 합계를 집계합니다.",
        purpose="집계",
        tags="order,payment",
        sql_text="SELECT DATE(order_date) AS dt, SUM(amount) AS total FROM orders GROUP BY DATE(order_date) ORDER BY dt DESC;",
    ),
    Query(
        id=None,
        title="탈퇴 사용자 삭제",
        description="90일 이상 경과한 탈퇴 사용자 데이터를 삭제합니다.",
        purpose="삭제",
        tags="user,cleanup",
        sql_text="DELETE FROM users WHERE status = 'withdrawn' AND updated_at < NOW() - INTERVAL '90 days';",
    ),
    Query(
        id=None,
        title="상품 가격 수정",
        description="전자제품 카테고리의 오래된 상품 가격을 10% 인상합니다.",
        purpose="수정",
        tags="product,price",
        sql_text="UPDATE products SET price = price * 1.1 WHERE category = 'electronics' AND updated_at < '2024-01-01';",
    ),
    Query(
        id=None,
        title="월별 매출 리포트",
        description="월별 판매 건수와 매출액을 집계하는 리포트 쿼리입니다.",
        purpose="집계",
        tags="sales,report",
        sql_text="SELECT TO_CHAR(sale_date, 'YYYY-MM') AS month, COUNT(*) AS cnt, SUM(total) AS revenue FROM sales GROUP BY TO_CHAR(sale_date, 'YYYY-MM') ORDER BY month DESC;",
    ),
]
```

---

## 10. 테스트

### 10.1 테스트 전략

3계층 테스트로 각 계층을 독립적으로 검증합니다:

| 계층 | 테스트 파일 | 테스트 수 | 인프라 의존 |
|------|-------------|-----------|-------------|
| 도메인 | test_domain.py | 13개 | 없음 (순수 Python) |
| 애플리케이션 | test_application.py | 11개 | InMemoryRepository (Mock) |
| 통합 | test_api_integration.py | 10개 | 실제 PostgreSQL |

### 10.2 테스트 픽스처

**파일**: `tests/conftest.py`

```python
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from server.core.external.persistence.sqlalchemy_models import Base, QueryModel
from server.core.external.persistence.postgres_query_repository import PostgresQueryRepository
from server.core.application.service.query_service import QueryService
from server.main import create_app

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://root:root@localhost:5433/query_book",
)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def session_factory(test_engine):
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    async with test_engine.begin() as conn:
        await conn.execute(QueryModel.__table__.delete())


@pytest_asyncio.fixture()
async def repository(session_factory):
    return PostgresQueryRepository(session_factory)


@pytest_asyncio.fixture()
async def service(repository):
    return QueryService(repository)


@pytest_asyncio.fixture()
async def app():
    application = create_app()
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture()
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        yield c
```

### 10.3 도메인 테스트

**파일**: `tests/test_domain.py`

주요 테스트:
- **엔티티 생성**: 모든 필드가 올바르게 설정되는지 확인
- **유효성 검증**: 빈 제목, 잘못된 용도, 빈 SQL에 대해 `InvalidQueryException` 발생
- **예외 계층**: `InvalidQueryException`과 `QueryNotFoundException`이 `DomainException`의 하위 클래스인지 확인
- **도메인 순수성**: AST 파싱으로 도메인 계층 파일에 프레임워크 import가 없는지 자동 검증

### 10.4 애플리케이션 테스트

**파일**: `tests/test_application.py`

`InMemoryQueryRepository`를 구현하여 도메인 포트-어댑터 패턴이 실제로 작동하는지 검증합니다.
이 테스트는 PostgreSQL 없이 순수하게 비즈니스 로직만 검증합니다.

InMemoryQueryRepository 구현:
```python
class InMemoryQueryRepository(QueryRepository):
    def __init__(self):
        self._store: dict[int, Query] = {}
        self._next_id: int = 1

    async def find_all(self) -> List[Query]:
        return sorted(self._store.values(), key=lambda q: q.created_at or datetime.min, reverse=True)

    async def find_by_id(self, query_id: int) -> Optional[Query]:
        return self._store.get(query_id)

    async def find_by_criteria(self, purpose=None, search=None) -> List[Query]:
        results = list(self._store.values())
        if purpose:
            results = [q for q in results if q.purpose == purpose]
        if search:
            search_lower = search.lower()
            results = [q for q in results if search_lower in (q.title or "").lower()
                       or search_lower in (q.description or "").lower()
                       or search_lower in (q.tags or "").lower()
                       or search_lower in (q.sql_text or "").lower()]
        return sorted(results, key=lambda q: q.created_at or datetime.min, reverse=True)

    async def save(self, query: Query) -> Query:
        query.id = self._next_id
        query.created_at = datetime.now()
        self._next_id += 1
        self._store[query.id] = query
        return query

    async def update(self, query: Query) -> Query:
        self._store[query.id] = query
        return query

    async def delete(self, query_id: int) -> None:
        self._store.pop(query_id, None)

    async def count(self) -> int:
        return len(self._store)
```

### 10.5 통합 테스트

**파일**: `tests/test_api_integration.py`

실제 PostgreSQL 데이터베이스에 대해 전체 HTTP 요청-응답 사이클을 검증합니다.
각 테스트마다 DB를 초기화하고 시드 데이터를 삽입합니다.

### 10.6 테스트 실행 방법

```bash
# PostgreSQL Docker 컨테이너가 실행 중이어야 합니다
docker compose up -d

# 전체 테스트 실행
python -m pytest tests/ -v

# 계층별 실행
python -m pytest tests/test_domain.py -v          # 도메인만
python -m pytest tests/test_application.py -v      # 애플리케이션만
python -m pytest tests/test_api_integration.py -v  # 통합만
```

---

## 11. 실행 방법

### 단계별 가이드

```bash
# 1. 프로젝트 디렉토리로 이동
cd query-repository

# 2. Docker로 PostgreSQL 실행
docker compose up -d

# 3. Python 의존성 설치
pip install -r requirements.txt

# 4. 테스트 실행 (선택사항)
pip install pytest pytest-asyncio httpx
python -m pytest tests/ -v

# 5. 서버 실행
python -m server.main
# 또는
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

# 6. 브라우저에서 접속
# http://localhost:8000
```

최초 실행 시 자동으로:
1. `queries` 테이블 생성
2. 샘플 데이터 5개 삽입

---

## 12. 아키텍처 의사결정 기록 (ADR)

### ADR-1: 왜 헥사고날 아키텍처인가

**결정**: 포트-어댑터 기반 헥사고날 아키텍처 채택

**근거**:
- 도메인 로직이 인프라(DB, HTTP)에 의존하지 않아 단위 테스트가 용이
- 데이터베이스 변경(예: PostgreSQL → MongoDB) 시 어댑터만 교체하면 됨
- 비즈니스 규칙이 컨트롤러나 ORM에 분산되지 않고 도메인 계층에 집중

**트레이드오프**:
- 파일/클래스 수가 증가 (이 규모에서는 오버엔지니어링으로 보일 수 있음)
- 도메인↔ORM 변환 코드 필요

### ADR-2: 왜 PostgreSQL인가

**결정**: SQLite 대신 PostgreSQL 사용 (Docker 배포)

**근거**:
- 프로덕션 환경과 동일한 DB를 개발 단계에서 사용
- `ilike` 등 PostgreSQL 특화 기능 활용 가능
- 동시 접속 처리 능력 (SQLite는 단일 쓰기 잠금)

**트레이드오프**:
- Docker 의존성 추가
- 로컬 설치 복잡도 증가

### ADR-3: 왜 Jinja2 SSR인가

**결정**: React/Vue 대신 Jinja2 서버사이드 렌더링

**근거**:
- 요구사항 명시: JavaScript 프레임워크 사용 금지
- 단순한 CRUD 도구에 SPA는 과도한 복잡도
- 빌드 도구 불필요, 즉시 배포 가능
- SEO 불필요 (내부 도구)

### ADR-4: 의존성 방향 규칙

```
외부(External) → 애플리케이션(Application) → 도메인(Domain)
```

- 도메인은 순수 Python만 사용 (dataclass, ABC, typing)
- 애플리케이션은 도메인의 포트를 사용하되 구현체를 모름
- 외부 계층만 FastAPI, SQLAlchemy 등 프레임워크를 import
- 이 규칙은 `test_domain.py`의 AST 검증 테스트로 자동화

### ADR-5: 수동 DI (Dependency Injection)

**결정**: DI 프레임워크 없이 `main.py`에서 수동 와이어링

**근거**:
- 프로젝트 규모에 DI 컨테이너는 과도
- 의존성 그래프가 단순 (Repository → Service → Router)
- 명시적 와이어링으로 디버깅 용이

---

## 부록: 발견된 버그와 수정 내역

개발 과정에서 다음 버그가 발견되어 수정되었습니다:

1. **검색 파라미터 불일치**: 라우터가 `search` 파라미터를 기대했으나 템플릿 폼이 `q`로 전송 → 라우터 파라미터명을 `q`로 변경

2. **태그 문자열 반복 오류**: `query.tags`는 쉼표 구분 문자열인데 `{% for tag in query.tags %}`로 문자별 순회 발생 → `query.tags.split(',')` 으로 수정

3. **수정 폼 태그 표시 오류**: `edit_query.tags | join(', ')`가 문자열에 적용되어 문자 사이에 쉼표 삽입 → `edit_query.tags`로 직접 출력하도록 수정
