# 사내 쿼리 모음집

팀 내에서 자주 사용하는 SQL 쿼리를 한 곳에 모아두고, 검색/복사하여 사용하는 내부 도구입니다.

## 기술 스택

| 영역 | 기술 |
|------|------|
| 백엔드 | Python 3.12 + FastAPI |
| 템플릿 | Jinja2 (서버사이드 렌더링) |
| 데이터베이스 | PostgreSQL 16 (Docker) |
| ORM | SQLAlchemy 2.0 (async) |
| 프론트엔드 | 순수 HTML + CSS + 바닐라 JS |
| 패키지 관리 | uv |
| 아키텍처 | 헥사고날 (포트-어댑터 패턴) |

## 프로젝트 구조

```
query-repository/
├── pyproject.toml                  # 프로젝트 설정 및 의존성
├── docker-compose.yml              # PostgreSQL 컨테이너
├── server/
│   ├── main.py                     # FastAPI 앱 진입점
│   ├── seed.py                     # 샘플 데이터 (5개)
│   ├── templates/
│   │   └── index.html              # Jinja2 템플릿
│   └── core/
│       ├── domain/                 # 도메인 (프레임워크 의존성 ZERO)
│       │   ├── model/query.py      # Query 엔티티
│       │   ├── port/query_repository.py  # 저장소 인터페이스
│       │   └── exception/          # 도메인 예외
│       ├── application/            # 애플리케이션 계층
│       │   ├── dto/query_dto.py    # Command, Result, Criteria
│       │   ├── usecase/query_usecase.py  # 유스케이스 인터페이스
│       │   └── service/query_service.py  # 유스케이스 구현체
│       └── external/               # 인프라 계층
│           ├── config/database.py  # DB 설정
│           ├── persistence/        # PostgreSQL 어댑터
│           └── api/query_router.py # FastAPI 라우터
├── tests/
│   ├── test_domain.py              # 도메인 테스트 (13개)
│   ├── test_application.py         # 애플리케이션 테스트 (11개)
│   └── test_api_integration.py     # 통합 테스트 (10개)
└── docs/
    └── implementation-guide.md     # 상세 구현 가이드
```

## 빠른 시작

```bash
# 1. PostgreSQL 실행
docker compose up -d

# 2. 의존성 설치
uv sync --extra dev

# 3. 서버 실행
uv run uvicorn server.main:app --reload

# 4. 접속
# http://localhost:8000
```

최초 실행 시 `queries` 테이블이 자동 생성되고 샘플 데이터 5개가 삽입됩니다.

## 테스트

```bash
uv run python -m pytest tests/ -v
```

| 테스트 파일 | 대상 계층 | 테스트 수 | 인프라 의존 |
|-------------|-----------|-----------|-------------|
| test_domain.py | 도메인 | 13 | 없음 |
| test_application.py | 애플리케이션 | 11 | InMemoryRepository |
| test_api_integration.py | 전체 통합 | 10 | PostgreSQL |

## 주요 기능

- SQL 쿼리 CRUD (추가, 조회, 수정, 삭제)
- 용도별 필터링 (조회 / 수정 / 삭제 / 집계 / 기타)
- 제목, 설명, 태그, SQL 내용 통합 검색 (400ms 디바운스)
- SQL 클립보드 복사
- 다크 테마 UI

## 데이터베이스

PostgreSQL이 Docker로 실행됩니다.

| 항목 | 값 |
|------|-----|
| 호스트 | localhost |
| 포트 | 5433 |
| 사용자 | root |
| 비밀번호 | root |
| 데이터베이스 | query_book |

## 아키텍처

헥사고날 아키텍처를 따르며, 의존성 방향은 항상 안쪽을 향합니다.

```
External(FastAPI, PostgreSQL) → Application(Service, DTO) → Domain(Model, Port)
```

- **도메인 계층**: 순수 Python만 사용. FastAPI, SQLAlchemy 등 프레임워크를 일절 import하지 않음
- **애플리케이션 계층**: 유스케이스 오케스트레이션. 도메인 포트에만 의존
- **외부 계층**: 인프라 구현체. 도메인 포트를 구현하고 프레임워크를 사용

상세한 구현 과정은 [docs/implementation-guide.md](docs/implementation-guide.md)를 참고하세요.
