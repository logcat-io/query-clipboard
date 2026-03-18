```
사내 쿼리 모음집 웹 애플리케이션을 FastAPI로 구현해줘.

---

## 목적
팀 내에서 자주 쓰는 SQL 쿼리를 한 곳에 모아두고,
필요할 때 찾아서 복사해 쓰는 간단한 내부 도구.
로컬 머신에서 혼자 또는 소수 팀원이 사용.

---

## 기술 스택
- Python + FastAPI
- Jinja2 (서버사이드 렌더링, React/Vue 사용 금지)
- SQLite (외부 DB 없이 파일 하나로 관리)
- 순수 HTML + CSS + 바닐라 JS (프레임워크 없음)

---

## 파일 구조
query-book/
├── main.py
├── database.py
├── requirements.txt
└── templates/
    └── index.html

requirements.txt 내용:
fastapi
uvicorn
jinja2
python-multipart

---

## 데이터 모델 (SQLite 테이블: queries)
- id          INTEGER PRIMARY KEY AUTOINCREMENT
- title       TEXT NOT NULL          -- 쿼리 제목
- description TEXT                   -- 한 줄 설명
- purpose     TEXT NOT NULL          -- 조회 | 수정 | 삭제 | 집계 | 기타
- tags        TEXT DEFAULT ''        -- 쉼표 구분 문자열 (예: user,payment)
- sql_text    TEXT NOT NULL          -- 실제 SQL
- created_at  TEXT DEFAULT (datetime('now', 'localtime'))

최초 실행 시 샘플 데이터 5개 자동 삽입.

---

## 기능 요구사항

### 목록 화면 (GET /)
- 전체 쿼리 카드 목록 표시
- 용도 필터 버튼: 전체 / 조회 / 수정 / 삭제 / 집계 / 기타
- 검색창: 제목, 설명, 태그, SQL 내용 전체를 대상으로 검색
  - 검색은 입력 후 400ms 디바운스로 자동 폼 submit
- 카드 클릭 시 SQL 펼침/접힘 토글
- SQL 복사 버튼: 클릭 시 클립보드에 복사, "✓ 복사됨" 1.8초 표시
- 수정 버튼: /edit/{id} 로 이동
- 삭제 버튼: confirm 확인 후 POST /delete/{id}

### 쿼리 추가 (모달)
- 헤더의 "+ 쿼리 추가" 버튼 클릭 시 모달 오픈
- 필드: 제목(필수), 설명, 용도(select), 태그, SQL(textarea, 필수)
- POST /add 로 폼 제출 후 / 로 리다이렉트

### 쿼리 수정 (GET+POST /edit/{id})
- 기존 데이터 채워진 모달 자동 오픈
- POST /edit/{id} 로 저장 후 / 로 리다이렉트

### 쿼리 삭제 (POST /delete/{id})
- 삭제 후 / 로 리다이렉트

---

## UI/디자인 요구사항
- 다크 테마 (배경 #0f1117 계열)
- 폰트: IBM Plex Mono (코드), Pretendard (UI)
- 용도별 배지 색상:
  - 조회: 파랑 (#3b82f6)
  - 수정: 노랑 (#f59e0b)
  - 삭제: 빨강 (#ef4444)
  - 집계: 보라 (#a78bfa)
  - 기타: 회색 (#94a3b8)
- 헤더 sticky 고정
- 카드 hover 시 배경 미세하게 밝아짐
- SQL 영역은 monospace, 구문 강조 없이 단색으로 충분
- 모달 외부 클릭 시 닫힘
- 반응형 불필요 (데스크탑 전용)

---

## 실행 방법 (README 포함)
pip install fastapi uvicorn jinja2 python-multipart
uvicorn main:app --reload
# 브라우저에서 http://localhost:8000 접속

---

## 제약사항
- DB 직접 실행 기능 없음
- 사용자 인증 없음 (로컬 전용이므로)
- 페이지네이션 없음 (쿼리 수백 개 이하 전제)
- 외부 CSS 프레임워크(Bootstrap, Tailwind 등) 사용 금지
- JavaScript 프레임워크(React, Vue 등) 사용 금지
- 모든 스타일은 index.html 내 <style> 태그에 인라인 작성

---

위 명세를 기준으로 main.py, database.py, templates/index.html,
requirements.txt 전체 코드를 작성해줘.
```
