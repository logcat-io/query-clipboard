# 사내 쿼리 모음집

팀 내에서 자주 사용하는 SQL 쿼리를 용도별로 분류하고, 검색/복사하여 사용하는 내부 도구입니다.

## 기술 스택

| 영역 | 기술 |
|------|------|
| 백엔드 | Python 3.12 + FastAPI |
| 템플릿 | Jinja2 (서버사이드 렌더링) |
| 데이터베이스 | MySQL 8.0 |
| ORM | SQLModel + SQLAlchemy 2.0 (async) |
| DB 마이그레이션 | Alembic |
| 프론트엔드 | 순수 HTML + CSS + 바닐라 JS |
| 패키지 관리 | uv |
| 아키텍처 | 헥사고날 (포트-어댑터 패턴) |

## 프로젝트 구조

```
query-repository/
├── pyproject.toml
├── docker-compose.yml              # MySQL 컨테이너 (개발)
├── docker-compose.prod.yml         # 운영 (앱 + MySQL)
├── alembic/                        # DB 마이그레이션
├── server/
│   ├── main.py                     # FastAPI 앱 진입점
│   ├── templates/
│   │   └── index.html              # Jinja2 템플릿
│   └── core/
│       ├── domain/                 # 도메인 (프레임워크 의존성 ZERO)
│       │   ├── model/              # Query, Purpose 엔티티
│       │   ├── port/               # Repository 인터페이스
│       │   └── exception/          # 도메인 예외
│       ├── application/            # 애플리케이션 계층
│       │   ├── dto/                # Command, Result, Criteria
│       │   ├── usecase/            # 유스케이스 인터페이스
│       │   └── service/            # 유스케이스 구현체
│       └── external/               # 인프라 계층
│           ├── config/             # DB 설정, 환경 변수
│           ├── persistence/        # MySQL 어댑터
│           └── api/                # FastAPI 라우터
└── tests/
    ├── test_domain.py
    ├── test_application.py
    └── test_api_integration.py
```

## 빠른 시작

```bash
# 1. MySQL 실행 (Docker)
docker compose up -d

# 2. 의존성 설치
uv sync --extra dev

# 3. DB 마이그레이션
uv run alembic upgrade head

# 4. 서버 실행
uv run uvicorn server.main:app --reload

# 5. 접속: http://localhost:8000
```

## 환경 변수

`.env` 파일로 DB 접속 정보를 관리합니다.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| DB_HOST | localhost | MySQL 호스트 |
| DB_PORT | 3307 | MySQL 포트 |
| DB_USER | root | MySQL 사용자 |
| DB_PASSWORD | root | MySQL 비밀번호 |
| DB_NAME | query_repository | 데이터베이스 이름 |

## 테스트

```bash
uv run python -m pytest tests/ -v
```

## 아키텍처

헥사고날 아키텍처를 따르며, 의존성 방향은 항상 안쪽을 향합니다.

```
External(FastAPI, MySQL) → Application(Service, DTO) → Domain(Model, Port)
```

- **도메인 계층**: 순수 Python + SQLModel(데이터 모델). 프레임워크 import 없음
- **애플리케이션 계층**: 유스케이스 오케스트레이션. 도메인 포트에만 의존
- **외부 계층**: 인프라 구현체. 도메인 포트를 구현하고 프레임워크를 사용
