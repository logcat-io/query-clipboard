# 배포 가이드

AWS EC2 (Amazon Linux 2023, ARM/Graviton) + RDS MySQL + Secrets Manager 구성 배포 가이드입니다.

---

## 1. 인프라 구성

```
┌─────────────────── VPC ───────────────────┐
│                                           │
│  ┌─── Public Subnet ──┐                  │
│  │                     │                  │
│  │  EC2 (t4g.micro)    │                  │
│  │  ┌───────────────┐  │                  │
│  │  │ App (Docker)   │  │                  │
│  │  │ FastAPI :8000  │──┼──┐              │
│  │  └───────────────┘  │  │              │
│  └─────────────────────┘  │              │
│                            │              │
│  ┌─── Private Subnet ─────┼───────────┐  │
│  │                         ▼           │  │
│  │  RDS MySQL 8.0 (db.t4g.micro)      │  │
│  │  :3306                              │  │
│  └─────────────────────────────────────┘  │
│                                           │
│  Secrets Manager                          │
│  └─ dev-env      │
└───────────────────────────────────────────┘
```

| 구성 요소 | 사양 |
|-----------|------|
| EC2 | t4g.micro (ARM, 2 vCPU, 1GB) / Amazon Linux 2023 |
| RDS | db.t4g.micro / MySQL 8.0 / gp3 20GB |
| Secrets Manager | DB 접속 정보 관리 |
| 보안 그룹 | EC2 → RDS (3306) 허용 |

---

## 2. AWS 리소스 생성

### 2.1 RDS MySQL 생성

AWS 콘솔 → RDS → 데이터베이스 생성:

| 항목 | 설정 |
|------|------|
| 엔진 | MySQL 8.0 |
| 템플릿 | 프리 티어 |
| 인스턴스 | db.t4g.micro |
| 스토리지 | gp3, 20GB |
| DB 이름 | query_repository |
| 마스터 사용자 | admin |
| 퍼블릭 액세스 | 아니요 |
| VPC | EC2와 동일한 VPC |
| 서브넷 | Private Subnet |

### 2.2 보안 그룹 설정

**EC2 보안 그룹:**

| 유형 | 포트 | 소스 |
|------|------|------|
| SSH | 22 | 내 IP |
| HTTP | 80 | 0.0.0.0/0 |
| HTTPS | 443 | 0.0.0.0/0 |

**RDS 보안 그룹:**

| 유형 | 포트 | 소스 |
|------|------|------|
| MySQL/Aurora | 3306 | EC2 보안 그룹 |

### 2.3 Secrets Manager 생성

AWS 콘솔 → Secrets Manager → 새 보안 암호 저장:

- **보안 암호 유형**: RDS 데이터베이스에 대한 자격 증명
- **사용자 이름**: admin
- **암호**: (RDS 생성 시 설정한 비밀번호)
- **데이터베이스**: 생성한 RDS 인스턴스 선택
- **보안 암호 이름**: `dev-env`

저장된 시크릿 JSON 형식:
```json
{
  "host": "query-repository-db.xxxx.ap-northeast-2.rds.amazonaws.com",
  "port": 3306,
  "username": "admin",
  "password": "xxxxxx",
  "dbname": "query_repository"
}
```

### 2.4 EC2 IAM 역할

EC2 인스턴스에 Secrets Manager 접근 권한이 필요합니다.

IAM → 역할 생성:
- **신뢰 엔터티**: EC2
- **정책**: 인라인 정책 추가

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-2:<ACCOUNT_ID>:secret:dev-env-*"
    }
  ]
}
```

EC2 인스턴스에 이 IAM 역할을 연결합니다.

---

## 3. EC2 서버 설정

### 3.1 SSH 접속

```bash
ssh -i ~/.ssh/query-repository-key ec2-user@<EC2_PUBLIC_IP>
```

### 3.2 Docker 설치

```bash
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user

# Docker Compose 플러그인
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 재접속
exit
ssh -i ~/.ssh/query-repository-key ec2-user@<EC2_PUBLIC_IP>
docker --version && docker compose version
```

### 3.3 프로젝트 클론

```bash
git clone https://github.com/<OWNER>/query-repository.git ~/query-repository
cd ~/query-repository
```

---

## 4. 환경 변수 설정

EC2에서 `.env` 파일을 생성합니다. Secrets Manager를 사용하므로 DB 접속 정보는 직접 입력하지 않습니다.

```bash
cat > ~/query-repository/.env << 'EOF'
AWS_SECRET_NAME=dev-env
AWS_REGION=ap-northeast-2
EOF

chmod 600 .env
```

> `AWS_SECRET_NAME`이 설정되면 앱 시작 시 Secrets Manager에서 DB 접속 정보를 자동으로 가져옵니다.
> 로컬 개발 시에는 `AWS_SECRET_NAME`을 설정하지 않고 `DB_HOST`, `DB_PASSWORD` 등을 직접 지정합니다.

---

## 5. 배포

### 5.1 빌드 및 실행

```bash
cd ~/query-repository

docker compose -f docker-compose.prod.yml up -d --build

# 상태 확인
docker compose -f docker-compose.prod.yml ps

# 로그 확인
docker compose -f docker-compose.prod.yml logs -f app
```

### 5.2 DB 마이그레이션

```bash
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

### 5.3 동작 확인

```bash
curl http://localhost
```

---

## 6. HTTPS 설정 (Caddy)

도메인이 있는 경우 Caddy로 자동 HTTPS를 설정합니다.

### 6.1 Caddyfile 생성

```bash
cat > ~/query-repository/Caddyfile << 'EOF'
your-domain.com {
    reverse_proxy app:8000
}
EOF
```

### 6.2 docker-compose.prod.yml 수정

```yaml
services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - app

  app:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    expose:
      - "8000"
    env_file:
      - .env

volumes:
  caddy_data:
  caddy_config:
```

---

## 7. GitHub Actions CI/CD

### 7.1 GitHub Secrets 등록

리포지토리 Settings → Secrets and variables → Actions:

| Secret | 값 |
|--------|-----|
| `EC2_HOST` | EC2 퍼블릭 IP 또는 도메인 |
| `EC2_SSH_KEY` | SSH 프라이빗 키 내용 |

### 7.2 배포 흐름

```
git push origin main
  → test (pytest + MySQL 서비스 컨테이너)
    → deploy (SSH → git pull → docker compose build → up → alembic upgrade)
```

---

## 8. 운영

### 로그

```bash
# 앱 로그
docker compose -f docker-compose.prod.yml logs -f app

# 최근 100줄
docker compose -f docker-compose.prod.yml logs --tail=100 app
```

### 재시작

```bash
docker compose -f docker-compose.prod.yml restart app
```

### 수동 배포

```bash
cd ~/query-repository
git pull origin main
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
docker image prune -f
```

### DB 백업 / 복원

RDS 자동 백업을 활용하거나, 수동으로 덤프합니다:

```bash
# EC2에서 RDS로 직접 접속 (mysql 클라이언트 필요)
sudo dnf install -y mariadb105

# 백업
mysqldump -h <RDS_ENDPOINT> -u admin -p query_repository > backup_$(date +%Y%m%d).sql

# 복원
mysql -h <RDS_ENDPOINT> -u admin -p query_repository < backup_20260323.sql
```

### 디스크 정리

```bash
docker system prune -af
df -h
```

---

## 9. 트러블슈팅

### Secrets Manager 접근 실패

```
Failed to load secret 'dev-env': ...
```

- EC2 인스턴스에 IAM 역할이 연결되어 있는지 확인
- IAM 정책의 Resource ARN이 올바른지 확인
- 리전(`AWS_REGION`)이 시크릿이 생성된 리전과 일치하는지 확인

### RDS 연결 실패

```bash
# EC2에서 RDS 연결 테스트
mysql -h <RDS_ENDPOINT> -u admin -p

# 보안 그룹 확인: RDS 보안 그룹에 EC2 보안 그룹이 인바운드 허용되어 있는지
# VPC 확인: EC2와 RDS가 같은 VPC에 있는지
```

### 마이그레이션 오류

```bash
docker compose -f docker-compose.prod.yml exec app alembic current
docker compose -f docker-compose.prod.yml exec app alembic history
```

---

## 10. 비용 예상

| 항목 | 월 비용 (서울 리전) |
|------|---------------------|
| EC2 t4g.micro | ~$6.1 |
| RDS db.t4g.micro (프리 티어 이후) | ~$11.5 |
| gp3 스토리지 (20GB) | ~$1.6 |
| Secrets Manager (1개 시크릿) | ~$0.4 |
| **합계** | **~$19.6/월** |

> EC2 t4g.micro, RDS db.t4g.micro 모두 프리 티어 대상입니다 (각 월 750시간).
> 프리 티어 기간 중에는 약 $0.4/월 (Secrets Manager만) 수준입니다.

---

## 환경별 설정 요약

| 환경 | DB | 인증 정보 관리 | .env 설정 |
|------|-----|--------------|-----------|
| 로컬 개발 | Docker MySQL (3307) | `.env` 직접 지정 | `DB_HOST=localhost` `DB_PORT=3307` `DB_PASSWORD=root` |
| 운영 (EC2) | RDS MySQL | Secrets Manager | `AWS_SECRET_NAME=dev-env` |
| CI (GitHub Actions) | 서비스 컨테이너 MySQL | 환경 변수 직접 지정 | workflow에서 `DB_*` 환경 변수 설정 |
