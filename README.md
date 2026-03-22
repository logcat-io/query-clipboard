# 사내 쿼리 모음집

팀 내에서 자주 사용하는 SQL 쿼리를 한 곳에 모아두고, 검색/복사하여 사용하는 내부 도구입니다.

## 기술 스택

| 영역 | 기술 |
|------|------|
| 백엔드 | Python 3.12 + FastAPI 0.115 |
| 데이터 모델링 | Pydantic v2 (도메인) + SQLModel (ORM) |
| 템플릿 | Jinja2 (서버사이드 렌더링) |
| 데이터베이스 | PostgreSQL 16 (Docker) |
| 비동기 드라이버 | asyncpg |
| 프론트엔드 | 순수 HTML + CSS + 바닐라 JS (SQL 구문 강조 포함) |
| 패키지 관리 | uv |
| 컨테이너 | Docker 멀티스테이지 빌드 |
| CI/CD | GitHub Actions |
| 아키텍처 | 헥사고날 (포트-어댑터 패턴) |

## 프로젝트 구조

```
query-repository/
├── pyproject.toml                    # 의존성 및 프로젝트 설정 (uv)
├── uv.lock                           # 잠금 파일
├── Dockerfile                        # 멀티스테이지 빌드 (uv + python:3.12-slim)
├── .dockerignore
├── docker-compose.yml                # 로컬 개발용 (PostgreSQL만)
├── docker-compose.prod.yml           # 프로덕션 (App + PostgreSQL)
├── .github/workflows/deploy.yml      # CI/CD (테스트 → EC2 배포)
│
├── server/
│   ├── main.py                       # FastAPI 앱 + 수동 DI 와이어링
│   ├── seed.py                       # 샘플 데이터 5개
│   ├── templates/
│   │   └── index.html                # Jinja2 (다크 테마 + SQL 구문 강조)
│   └── core/
│       ├── domain/                   # 도메인 (pydantic만 허용, 프레임워크 금지)
│       │   ├── model/query.py        # Query (Pydantic BaseModel)
│       │   ├── port/query_repository.py  # QueryRepository (ABC)
│       │   └── exception/            # DomainException 계층
│       ├── application/
│       │   ├── dto/query_dto.py      # Command, Result, Criteria (Pydantic)
│       │   ├── usecase/query_usecase.py  # QueryUseCase (ABC)
│       │   └── service/query_service.py  # QueryService 구현체
│       └── external/
│           ├── config/database.py    # SQLAlchemy async engine
│           ├── persistence/
│           │   ├── sqlalchemy_models.py      # QueryTable (SQLModel, table=True)
│           │   └── postgres_query_repository.py  # PostgreSQL 어댑터
│           └── api/query_router.py   # FastAPI 라우터
│
├── tests/                            # 3계층 테스트 (33개)
│   ├── conftest.py
│   ├── test_domain.py                # 도메인 순수 테스트 (13개)
│   ├── test_application.py           # InMemoryRepo 기반 서비스 테스트 (11개)
│   └── test_api_integration.py       # 실제 PostgreSQL 통합 테스트 (10개)
│
├── docs/
│   ├── implementation-guide.md       # 구현 가이드 (이 문서만으로 재구축 가능)
│   └── deployment-guide.md           # AWS 배포 가이드 (NAT Instance 기반)
│
└── reports/
    ├── essential.md                  # 아키텍처 원칙 명세
    └── what-todo.md                  # 기능 요구사항 원본
```

## 빠른 시작

```bash
# 1. PostgreSQL 실행
docker compose up -d

# 2. 의존성 설치
uv sync --extra dev

# 3. 서버 실행
uv run uvicorn server.main:app --reload

# 4. 접속 → http://localhost:8000
```

## 프로덕션 실행 (Docker Compose)

```bash
docker compose -f docker-compose.prod.yml up -d --build
# 접속 → http://localhost
```

## 테스트

```bash
uv run python -m pytest tests/ -v    # 33개 전체 테스트
```

| 테스트 파일 | 대상 | 수 | 인프라 |
|-------------|------|-----|--------|
| test_domain.py | 도메인 모델 + 예외 + 순수성 검증(AST) | 13 | 없음 |
| test_application.py | 서비스 로직 (InMemoryRepository) | 11 | 없음 |
| test_api_integration.py | HTTP 전체 사이클 | 10 | PostgreSQL |

## 주요 기능

- SQL 쿼리 CRUD (추가/조회/수정/삭제)
- 용도별 필터링 (조회/수정/삭제/집계/기타)
- 통합 검색 (제목, 설명, 태그, SQL 본문 / 400ms 디바운스)
- SQL 자동 포맷팅 + 구문 강조 (키워드, 함수, 문자열, 숫자)
- 원본 SQL 클립보드 복사
- 다크 테마 UI

## 아키텍처

```
┌──────────────────────────────────────────────────────────┐
│  External (FastAPI, SQLModel, Jinja2)                    │
│          │                                               │
│  ────────┼────────── Port Boundary ──────────────────    │
│          │                                               │
│  Application (QueryService, DTO)                         │
│          │                                               │
│  ────────┼────────── Domain Boundary ────────────────    │
│          │                                               │
│  Domain (Query:BaseModel, QueryRepository:ABC, Exception)│
│  pydantic만 허용 / sqlmodel,sqlalchemy,fastapi 금지      │
└──────────────────────────────────────────────────────────┘
의존성 방향: External → Application → Domain
```

상세 문서:
- [구현 가이드](docs/implementation-guide.md) - 소스코드 전체와 설계 근거
- [배포 가이드](docs/deployment-guide.md) - AWS EC2 + NAT Instance + GitHub Actions
