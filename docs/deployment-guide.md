# AWS 배포 가이드

개발자 소수가 사용하는 내부 도구를 **최소 비용**으로 AWS에 배포하는 가이드입니다.

---

## 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [비용 분석](#2-비용-분석)
3. [프로젝트 배포 파일 설명](#3-프로젝트-배포-파일-설명)
4. [사전 준비](#4-사전-준비)
5. [1단계: VPC 네트워크 구성](#5-1단계-vpc-네트워크-구성)
6. [2단계: NAT Instance 구성](#6-2단계-nat-instance-구성)
7. [3단계: 애플리케이션 EC2 구성](#7-3단계-애플리케이션-ec2-구성)
8. [4단계: 서버 설정 및 배포](#8-4단계-서버-설정-및-배포)
9. [5단계: GitHub Actions CI/CD](#9-5단계-github-actions-cicd)
10. [6단계: 도메인 및 HTTPS (선택)](#10-6단계-도메인-및-https-선택)
11. [운영 가이드](#11-운영-가이드)
12. [트러블슈팅](#12-트러블슈팅)
13. [리소스 정리 (삭제)](#13-리소스-정리-삭제)

---

## 1. 아키텍처 개요

```
                         Internet
                            │
                            │
               ┌────────────┴────────────────────────────────────┐
               │            IGW                VPC 10.0.0.0/16   │
               │            │                                    │
               │   ┌────────┴──────────────────────────┐         │
               │   │   Public Subnet  10.0.1.0/24      │         │
               │   │                                    │         │
               │   │   ┌──────────────────────────┐     │         │
               │   │   │  NAT Instance  (t3.nano) │     │         │
               │   │   │  - Elastic IP            │     │         │
               │   │   │  - iptables MASQUERADE   │     │         │
               │   │   │  - iptables DNAT :80     │     │         │
               │   │   └────────────┬─────────────┘     │         │
               │   └────────────────┼───────────────────┘         │
               │                    │                              │
               │   ┌────────────────┴───────────────────┐         │
               │   │   Private Subnet  10.0.2.0/24      │         │
               │   │                                     │         │
               │   │   ┌───────────────────────────┐     │         │
               │   │   │  App EC2  (t3.micro)      │     │         │
               │   │   │                           │     │         │
               │   │   │  docker-compose.prod.yml  │     │         │
               │   │   │  ┌─────────┐ ┌─────────┐  │     │         │
               │   │   │  │ FastAPI │ │PostgreSQL│  │     │         │
               │   │   │  │  :8000  │ │  :5432   │  │     │         │
               │   │   │  └─────────┘ └─────────┘  │     │         │
               │   │   └───────────────────────────┘     │         │
               │   └─────────────────────────────────────┘         │
               └───────────────────────────────────────────────────┘

  개발자 브라우저 → http://<NAT_EIP>:80 → iptables DNAT → App:80 → FastAPI:8000
  GitHub Actions → SSH → NAT (ProxyJump) → App EC2 → git pull + docker compose up
```

### 왜 이 구조인가

| 결정 | 이유 |
|------|------|
| NAT Instance (t3.nano) | NAT Gateway($32/월) 대신 $3/월로 비용 90% 절감 |
| Private Subnet에 App 배치 | DB 포트가 외부에 직접 노출되지 않음 |
| 단일 EC2에 Docker Compose | RDS($15+/월) 없이 PostgreSQL을 같은 인스턴스에서 실행 |
| 멀티스테이지 Docker 빌드 (uv) | 이미지 크기 최소화, lockfile 기반 재현 가능한 빌드 |
| GitHub Actions SSH 배포 | 별도 CI/CD 인프라 불필요, PostgreSQL 서비스 컨테이너로 테스트 |
| t3.micro (프리 티어) | 12개월 무료, 이후에도 $7.6/월 |

---

## 2. 비용 분석

### 프리 티어 기간 (12개월) - 월 예상: ~$3.5

| 리소스 | 스펙 | 월 비용 |
|--------|------|---------|
| App EC2 | t3.micro (프리 티어) | $0 |
| NAT Instance | t3.nano | ~$3.0 |
| Elastic IP | NAT Instance에 연결 | $0 (연결 상태) |
| EBS (App) | 8GB gp3 | $0 (프리 티어) |
| EBS (NAT) | 8GB gp3 | ~$0.5 |
| 데이터 전송 | 최소 (내부 도구) | ~$0 |
| **합계** | | **~$3.5/월** |

### 프리 티어 이후 - 월 예상: ~$11.6

| 리소스 | 월 비용 |
|--------|---------|
| App EC2 (t3.micro) | ~$7.6 |
| NAT Instance (t3.nano) | ~$3.0 |
| EBS 16GB (2대) | ~$1.0 |
| **합계** | **~$11.6/월** |

### ARM (Graviton) 전환 시 - 월 예상: ~$9.4

| 리소스 | 월 비용 |
|--------|---------|
| App EC2 (t4g.micro) | ~$6.0 |
| NAT Instance (t4g.nano) | ~$2.4 |
| EBS 16GB | ~$1.0 |
| **합계** | **~$9.4/월** |

Graviton 전환 시 Dockerfile의 베이스 이미지를 `python:3.12-slim`에서 ARM 호환으로 변경. `python:3.12-slim`은 이미 multi-arch이므로 코드 변경 없이 t4g 인스턴스에서 빌드 가능.

### 비교: NAT Gateway 사용 시

| | NAT Instance | NAT Gateway |
|---|---|---|
| 월 비용 | ~$3 | ~$32 + 전송비 |
| 가용성 | 단일 인스턴스 (수동 복구) | AWS 관리형 HA |
| 대역폭 | 인스턴스 타입에 의존 | 최대 45Gbps |
| **적합 대상** | **내부 도구, 소규모** | 프로덕션, 대규모 |

내부 개발자 도구이므로 NAT Instance가 적합합니다.

---

## 3. 프로젝트 배포 파일 설명

프로젝트에 이미 포함된 배포 관련 파일들:

```
query-repository/
├── Dockerfile                        # App 컨테이너 빌드
├── .dockerignore                     # Docker 빌드 컨텍스트 제외 목록
├── docker-compose.yml                # 로컬 개발용 (PostgreSQL만)
├── docker-compose.prod.yml           # 프로덕션 (App + PostgreSQL)
└── .github/workflows/deploy.yml      # CI/CD (테스트 → EC2 배포)
```

### 3.1 Dockerfile

멀티스테이지 빌드로 최종 이미지에 uv를 포함하지 않음.

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

**빌드 흐름:**
1. builder: uv 복사 → 의존성만 먼저 설치 (캐시 레이어) → 소스 복사
2. final: python:3.12-slim + .venv + server/ 만 포함
3. `--frozen`: lockfile 기반 재현 가능한 빌드
4. `--no-dev`: pytest, httpx 등 테스트 의존성 제외

### 3.2 .dockerignore

```
.venv
.git
.github
.pytest_cache
__pycache__
*.pyc
tests/
docs/
reports/
.dockerignore
*.md
```

### 3.3 docker-compose.prod.yml

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

**핵심:**
- `depends_on: condition: service_healthy` → DB가 ready 상태일 때만 App 시작
- `DATABASE_URL`이 `db:5432`를 가리킴 (Docker 내부 네트워크, 로컬의 5433이 아님)
- `postgres:16-alpine`으로 프로덕션 이미지 크기 최소화
- `restart: unless-stopped`로 서버 재부팅 시 자동 복구

### 3.4 GitHub Actions 워크플로우

`.github/workflows/deploy.yml`:

```yaml
name: Deploy to EC2

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: root
          POSTGRES_PASSWORD: root
          POSTGRES_DB: query_book
        ports:
          - 5433:5432
        options: >-
          --health-cmd "pg_isready -U root -d query_book"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Run tests
        env:
          DATABASE_URL: "postgresql+asyncpg://root:root@localhost:5433/query_book"
        run: uv run python -m pytest tests/ -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to EC2
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ec2-user
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd ~/query-repository
            git pull origin main
            docker compose -f docker-compose.prod.yml build --no-cache
            docker compose -f docker-compose.prod.yml up -d
            docker image prune -f
```

**동작 흐름:**
```
main 브랜치 push
  ├→ test: PostgreSQL 서비스 컨테이너 + uv 설치 + 33개 테스트 실행
  └→ deploy (test 통과 후): SSH → git pull → docker compose build → up → image prune
```

---

## 4. 사전 준비

### 4.1 필요한 도구

```bash
# AWS CLI 설치
brew install awscli

# AWS 계정 설정
aws configure
# AWS Access Key ID: <your-key>
# AWS Secret Access Key: <your-secret>
# Default region: ap-northeast-2
# Default output format: json
```

### 4.2 SSH 키 페어 생성

```bash
aws ec2 create-key-pair \
  --key-name query-book-key \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/query-book-key.pem

chmod 400 ~/.ssh/query-book-key.pem
```

### 4.3 변수 파일 준비

배포 과정에서 여러 리소스 ID를 참조합니다. 편의를 위해 `~/.query-book-env`에 저장:

```bash
touch ~/.query-book-env
# 각 단계에서 생성되는 ID를 여기에 기록
# 예: echo "VPC_ID=vpc-xxx" >> ~/.query-book-env
```

---

## 5. 1단계: VPC 네트워크 구성

### 5.1 VPC 생성

```bash
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=query-book-vpc}]' \
  --query 'Vpc.VpcId' --output text)

aws ec2 modify-vpc-attribute \
  --vpc-id $VPC_ID \
  --enable-dns-hostnames '{"Value":true}'

echo "VPC_ID=$VPC_ID" | tee -a ~/.query-book-env
```

### 5.2 서브넷 생성

```bash
# Public Subnet (NAT Instance용)
PUBLIC_SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.1.0/24 \
  --availability-zone ap-northeast-2a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=query-book-public}]' \
  --query 'Subnet.SubnetId' --output text)

echo "PUBLIC_SUBNET_ID=$PUBLIC_SUBNET_ID" | tee -a ~/.query-book-env

# Private Subnet (App EC2용)
PRIVATE_SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.2.0/24 \
  --availability-zone ap-northeast-2a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=query-book-private}]' \
  --query 'Subnet.SubnetId' --output text)

echo "PRIVATE_SUBNET_ID=$PRIVATE_SUBNET_ID" | tee -a ~/.query-book-env
```

### 5.3 Internet Gateway

```bash
IGW_ID=$(aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=query-book-igw}]' \
  --query 'InternetGateway.InternetGatewayId' --output text)

aws ec2 attach-internet-gateway \
  --internet-gateway-id $IGW_ID \
  --vpc-id $VPC_ID

echo "IGW_ID=$IGW_ID" | tee -a ~/.query-book-env
```

### 5.4 라우팅 테이블

```bash
# Public 라우팅 테이블 (0.0.0.0/0 → IGW)
PUBLIC_RT_ID=$(aws ec2 create-route-table \
  --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=query-book-public-rt}]' \
  --query 'RouteTable.RouteTableId' --output text)

aws ec2 create-route \
  --route-table-id $PUBLIC_RT_ID \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id $IGW_ID

aws ec2 associate-route-table \
  --route-table-id $PUBLIC_RT_ID \
  --subnet-id $PUBLIC_SUBNET_ID

# Private 라우팅 테이블 (NAT 생성 후 경로 추가)
PRIVATE_RT_ID=$(aws ec2 create-route-table \
  --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=query-book-private-rt}]' \
  --query 'RouteTable.RouteTableId' --output text)

aws ec2 associate-route-table \
  --route-table-id $PRIVATE_RT_ID \
  --subnet-id $PRIVATE_SUBNET_ID

echo "PUBLIC_RT_ID=$PUBLIC_RT_ID" | tee -a ~/.query-book-env
echo "PRIVATE_RT_ID=$PRIVATE_RT_ID" | tee -a ~/.query-book-env
```

---

## 6. 2단계: NAT Instance 구성

### 6.1 보안 그룹

```bash
NAT_SG_ID=$(aws ec2 create-security-group \
  --group-name query-book-nat-sg \
  --description "NAT Instance SG" \
  --vpc-id $VPC_ID \
  --query 'GroupId' --output text)

MY_IP=$(curl -s https://checkip.amazonaws.com)

# SSH (본인 IP만)
aws ec2 authorize-security-group-ingress \
  --group-id $NAT_SG_ID \
  --protocol tcp --port 22 \
  --cidr "${MY_IP}/32"

# Private Subnet에서 오는 모든 트래픽 허용 (NAT 대상)
aws ec2 authorize-security-group-ingress \
  --group-id $NAT_SG_ID \
  --protocol -1 \
  --cidr 10.0.2.0/24

# HTTP (본인 IP → 포트 포워딩으로 App에 접근)
aws ec2 authorize-security-group-ingress \
  --group-id $NAT_SG_ID \
  --protocol tcp --port 80 \
  --cidr "${MY_IP}/32"

echo "NAT_SG_ID=$NAT_SG_ID" | tee -a ~/.query-book-env
```

### 6.2 NAT Instance 시작

```bash
# Amazon Linux 2023 최신 AMI 조회
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" \
            "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

NAT_INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t3.nano \
  --key-name query-book-key \
  --subnet-id $PUBLIC_SUBNET_ID \
  --security-group-ids $NAT_SG_ID \
  --associate-public-ip-address \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=query-book-nat}]' \
  --query 'Instances[0].InstanceId' --output text)

aws ec2 wait instance-running --instance-ids $NAT_INSTANCE_ID

echo "NAT_INSTANCE_ID=$NAT_INSTANCE_ID" | tee -a ~/.query-book-env
```

### 6.3 Source/Dest Check 비활성화

NAT 동작에 필수. 이 설정이 없으면 인스턴스가 자신의 IP가 아닌 패킷을 드롭함.

```bash
aws ec2 modify-instance-attribute \
  --instance-id $NAT_INSTANCE_ID \
  --no-source-dest-check
```

### 6.4 Elastic IP 할당

```bash
EIP_ALLOC=$(aws ec2 allocate-address \
  --domain vpc \
  --tag-specifications 'ResourceType=elastic-ip,Tags=[{Key=Name,Value=query-book-nat-eip}]' \
  --query 'AllocationId' --output text)

aws ec2 associate-address \
  --instance-id $NAT_INSTANCE_ID \
  --allocation-id $EIP_ALLOC

NAT_PUBLIC_IP=$(aws ec2 describe-addresses \
  --allocation-ids $EIP_ALLOC \
  --query 'Addresses[0].PublicIp' --output text)

echo "EIP_ALLOC=$EIP_ALLOC" | tee -a ~/.query-book-env
echo "NAT_PUBLIC_IP=$NAT_PUBLIC_IP" | tee -a ~/.query-book-env
```

### 6.5 NAT Instance iptables 설정

```bash
ssh -i ~/.ssh/query-book-key.pem ec2-user@$NAT_PUBLIC_IP << 'EOF'
# IP 포워딩 활성화 (즉시 + 영구)
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward = 1" | sudo tee /etc/sysctl.d/nat.conf

# NAT: Private Subnet → 인터넷
sudo iptables -t nat -A POSTROUTING -o ens5 -s 10.0.2.0/24 -j MASQUERADE

# iptables 규칙 영구 저장
sudo dnf install -y iptables-services
sudo systemctl enable iptables
sudo service iptables save
EOF
```

### 6.6 Private 라우팅 테이블에 NAT 경로 추가

```bash
aws ec2 create-route \
  --route-table-id $PRIVATE_RT_ID \
  --destination-cidr-block 0.0.0.0/0 \
  --instance-id $NAT_INSTANCE_ID
```

---

## 7. 3단계: 애플리케이션 EC2 구성

### 7.1 보안 그룹

```bash
APP_SG_ID=$(aws ec2 create-security-group \
  --group-name query-book-app-sg \
  --description "App Instance SG" \
  --vpc-id $VPC_ID \
  --query 'GroupId' --output text)

# NAT Instance에서의 SSH + HTTP만 허용
aws ec2 authorize-security-group-ingress \
  --group-id $APP_SG_ID \
  --protocol tcp --port 22 \
  --source-group $NAT_SG_ID

aws ec2 authorize-security-group-ingress \
  --group-id $APP_SG_ID \
  --protocol tcp --port 80 \
  --source-group $NAT_SG_ID

echo "APP_SG_ID=$APP_SG_ID" | tee -a ~/.query-book-env
```

### 7.2 App EC2 시작

```bash
APP_INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t3.micro \
  --key-name query-book-key \
  --subnet-id $PRIVATE_SUBNET_ID \
  --security-group-ids $APP_SG_ID \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=query-book-app}]' \
  --query 'Instances[0].InstanceId' --output text)

aws ec2 wait instance-running --instance-ids $APP_INSTANCE_ID

APP_PRIVATE_IP=$(aws ec2 describe-instances \
  --instance-ids $APP_INSTANCE_ID \
  --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)

echo "APP_INSTANCE_ID=$APP_INSTANCE_ID" | tee -a ~/.query-book-env
echo "APP_PRIVATE_IP=$APP_PRIVATE_IP" | tee -a ~/.query-book-env
```

### 7.3 NAT Instance에 포트 포워딩 추가

```bash
ssh -i ~/.ssh/query-book-key.pem ec2-user@$NAT_PUBLIC_IP << EOF
# 외부:80 → App:80 포트 포워딩
sudo iptables -t nat -A PREROUTING -i ens5 -p tcp --dport 80 -j DNAT --to-destination ${APP_PRIVATE_IP}:80
sudo iptables -A FORWARD -p tcp -d ${APP_PRIVATE_IP} --dport 80 -j ACCEPT
sudo service iptables save
EOF
```

---

## 8. 4단계: 서버 설정 및 배포

### 8.1 SSH 설정 (~/.ssh/config)

```
Host query-nat
    HostName <NAT_PUBLIC_IP>
    User ec2-user
    IdentityFile ~/.ssh/query-book-key.pem

Host query-app
    HostName <APP_PRIVATE_IP>
    User ec2-user
    IdentityFile ~/.ssh/query-book-key.pem
    ProxyJump query-nat
```

이후 `ssh query-app`으로 NAT를 경유하여 App에 바로 접속 가능.

### 8.2 App EC2 초기 설정

```bash
ssh query-app << 'SETUP'
# 시스템 업데이트 + Docker + Git 설치
sudo dnf update -y
sudo dnf install -y docker git

# Docker 서비스 활성화
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user

# Docker Compose V2 플러그인 설치
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 확인
echo "Docker: $(docker --version)"
echo "Docker Compose: $(docker compose version)"
SETUP
```

### 8.3 최초 배포

```bash
ssh query-app << 'DEPLOY'
# docker 그룹 적용을 위한 새 쉘
newgrp docker << 'INNER'

cd ~
git clone https://github.com/<your-username>/query-repository.git
cd query-repository

# 프로덕션 실행
docker compose -f docker-compose.prod.yml up -d --build

# 상태 확인
docker compose -f docker-compose.prod.yml ps
INNER
DEPLOY
```

### 8.4 배포 확인

```bash
# 로컬에서 NAT의 Elastic IP로 접속
curl -s -o /dev/null -w "%{http_code}" http://$NAT_PUBLIC_IP
# 200이면 성공

# 브라우저에서 http://<NAT_PUBLIC_IP> 접속
```

---

## 9. 5단계: GitHub Actions CI/CD

### 9.1 GitHub Secrets 등록

GitHub 리포지토리 > Settings > Secrets and variables > Actions:

| Secret 이름 | 값 | 용도 |
|-------------|-----|------|
| `EC2_HOST` | NAT Instance의 Elastic IP | SSH 접속 대상 |
| `EC2_SSH_KEY` | `~/.ssh/query-book-key.pem` 내용 전체 | SSH 인증 |

### 9.2 NAT Instance SSH 접근 허용

GitHub Actions의 러너 IP는 동적이므로 두 가지 방법 중 선택:

**방법 A: SSH 22번 포트를 전체 개방 (간단, 내부 도구용)**

```bash
aws ec2 authorize-security-group-ingress \
  --group-id $NAT_SG_ID \
  --protocol tcp --port 22 \
  --cidr 0.0.0.0/0
```

**방법 B: 워크플로우에서 동적 IP 추가/제거 (더 안전)**

추가 Secrets 필요:

| Secret | 값 |
|--------|-----|
| `AWS_ACCESS_KEY_ID` | IAM Access Key |
| `AWS_SECRET_ACCESS_KEY` | IAM Secret Key |
| `NAT_SG_ID` | NAT 보안 그룹 ID |

deploy job을 다음으로 교체:

```yaml
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Get runner IP
        id: ip
        run: echo "ip=$(curl -s https://checkip.amazonaws.com)" >> $GITHUB_OUTPUT

      - name: Open SSH port
        run: |
          aws ec2 authorize-security-group-ingress \
            --group-id ${{ secrets.NAT_SG_ID }} \
            --protocol tcp --port 22 \
            --cidr "${{ steps.ip.outputs.ip }}/32"
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: ap-northeast-2

      - name: Deploy to EC2
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ec2-user
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd ~/query-repository
            git pull origin main
            docker compose -f docker-compose.prod.yml build --no-cache
            docker compose -f docker-compose.prod.yml up -d
            docker image prune -f

      - name: Close SSH port
        if: always()
        run: |
          aws ec2 revoke-security-group-ingress \
            --group-id ${{ secrets.NAT_SG_ID }} \
            --protocol tcp --port 22 \
            --cidr "${{ steps.ip.outputs.ip }}/32"
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: ap-northeast-2
```

### 9.3 ProxyJump를 통한 Private Subnet 직접 배포

NAT가 아닌 App EC2에 직접 배포하려면:

추가 Secret: `APP_PRIVATE_IP`

```yaml
      - name: Deploy via NAT
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.APP_PRIVATE_IP }}
          username: ec2-user
          key: ${{ secrets.EC2_SSH_KEY }}
          proxy_host: ${{ secrets.EC2_HOST }}
          proxy_username: ec2-user
          proxy_key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd ~/query-repository
            git pull origin main
            docker compose -f docker-compose.prod.yml build --no-cache
            docker compose -f docker-compose.prod.yml up -d
            docker image prune -f
```

---

## 10. 6단계: 도메인 및 HTTPS (선택)

내부 도구이므로 HTTPS가 필수는 아니지만, 필요 시:

### 방법 1: SSH 터널 (무료, 가장 간단)

```bash
# 로컬 8080 → NAT → App:80 터널
ssh -L 8080:$APP_PRIVATE_IP:80 query-nat

# 브라우저에서 http://localhost:8080 접속
```

### 방법 2: Caddy 리버스 프록시 (무료 Let's Encrypt)

NAT Instance에 Caddy를 설치하면 자동 HTTPS:

```bash
ssh query-nat << 'EOF'
sudo dnf install -y caddy

sudo tee /etc/caddy/Caddyfile << 'CADDY'
query.yourdomain.com {
    reverse_proxy <APP_PRIVATE_IP>:80
}
CADDY

sudo systemctl enable caddy
sudo systemctl start caddy
EOF
```

**전제:** 도메인 DNS A 레코드가 NAT의 Elastic IP를 가리켜야 함.
NAT SG에 443 포트도 열어야 함:

```bash
aws ec2 authorize-security-group-ingress \
  --group-id $NAT_SG_ID \
  --protocol tcp --port 443 \
  --cidr 0.0.0.0/0
```

---

## 11. 운영 가이드

### 11.1 로그 확인

```bash
# App 로그 (FastAPI)
ssh query-app "cd ~/query-repository && docker compose -f docker-compose.prod.yml logs -f --tail 50 app"

# DB 로그
ssh query-app "cd ~/query-repository && docker compose -f docker-compose.prod.yml logs -f --tail 50 db"
```

### 11.2 수동 배포

```bash
ssh query-app << 'EOF'
cd ~/query-repository
git pull origin main
docker compose -f docker-compose.prod.yml build --no-cache app
docker compose -f docker-compose.prod.yml up -d app
docker image prune -f
EOF
```

### 11.3 DB 백업

```bash
# 서버에서 백업 생성
ssh query-app "cd ~/query-repository && docker compose -f docker-compose.prod.yml exec db pg_dump -U root query_book > ~/backup_\$(date +%Y%m%d).sql"

# 로컬로 다운로드
scp query-app:~/backup_*.sql ./backups/
```

### 11.4 DB 복원

```bash
scp ./backups/backup_20260322.sql query-app:~/

ssh query-app << 'EOF'
cd ~/query-repository
docker compose -f docker-compose.prod.yml exec -T db psql -U root query_book < ~/backup_20260322.sql
EOF
```

### 11.5 서비스 재시작

```bash
ssh query-app "cd ~/query-repository && docker compose -f docker-compose.prod.yml restart"
```

### 11.6 디스크 공간 관리

```bash
ssh query-app << 'EOF'
docker system prune -af --volumes
df -h
EOF
```

### 11.7 NAT Instance 상태 확인

NAT Instance가 중지되면 App EC2에서 외부 통신 불가 (docker pull, git pull 등).

```bash
aws ec2 describe-instance-status \
  --instance-ids $NAT_INSTANCE_ID \
  --query 'InstanceStatuses[0].InstanceState.Name' --output text
```

### 11.8 컨테이너 상태 확인

```bash
ssh query-app << 'EOF'
cd ~/query-repository
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml exec db pg_isready -U root -d query_book
EOF
```

---

## 12. 트러블슈팅

### App EC2에서 인터넷이 안 되는 경우

원인 진단 순서:

```bash
# 1. NAT Instance 실행 상태
aws ec2 describe-instances \
  --instance-ids $NAT_INSTANCE_ID \
  --query 'Reservations[0].Instances[0].State.Name'

# 2. Source/Dest Check 비활성화 여부
aws ec2 describe-instance-attribute \
  --instance-id $NAT_INSTANCE_ID \
  --attribute sourceDestCheck
# 결과: "Value": false 여야 함

# 3. IP 포워딩 활성화 여부
ssh query-nat "cat /proc/sys/net/ipv4/ip_forward"
# 결과: 1

# 4. iptables NAT 규칙 존재 여부
ssh query-nat "sudo iptables -t nat -L -n -v"
# MASQUERADE 규칙이 있어야 함

# 5. Private 라우팅 테이블에 NAT 경로
aws ec2 describe-route-tables \
  --route-table-ids $PRIVATE_RT_ID \
  --query 'RouteTables[0].Routes'
# 0.0.0.0/0 → NAT Instance ID 경로가 있어야 함
```

### Docker Compose 실행 안 됨

```bash
ssh query-app << 'EOF'
cd ~/query-repository

# 전체 상태
docker compose -f docker-compose.prod.yml ps -a

# 에러 로그
docker compose -f docker-compose.prod.yml logs --tail 100

# DB healthcheck
docker inspect query-repository-db-1 --format='{{.State.Health.Status}}'
# 결과: healthy

# App 컨테이너 직접 접속
docker compose -f docker-compose.prod.yml exec app python -c "print('OK')"
EOF
```

### NAT Instance 재부팅 후 iptables 복구

iptables-services가 설치되어 있으면 자동 복구되지만, 안 될 경우:

```bash
ssh query-nat << 'EOF'
sudo sysctl -w net.ipv4.ip_forward=1
sudo service iptables restart
sudo iptables -t nat -L -n
EOF
```

### GitHub Actions 배포 실패

| 증상 | 원인 | 해결 |
|------|------|------|
| SSH 연결 타임아웃 | NAT SG에 러너 IP 미허용 | 방법 A(전체 개방) 또는 방법 B(동적 IP) 적용 |
| git pull 실패 | App EC2에서 GitHub 접근 불가 | NAT Instance 동작 확인 |
| docker build 실패 | 디스크 부족 | `docker system prune -af` |
| docker compose up 실패 | 이전 컨테이너 충돌 | `docker compose -f docker-compose.prod.yml down && up -d` |

### 포트 포워딩이 동작하지 않는 경우

```bash
# NAT Instance에서 확인
ssh query-nat << 'EOF'
# PREROUTING 규칙 확인 (DNAT)
sudo iptables -t nat -L PREROUTING -n -v

# FORWARD 규칙 확인
sudo iptables -L FORWARD -n -v

# App EC2 연결 테스트
curl -s -o /dev/null -w "%{http_code}" http://<APP_PRIVATE_IP>:80
EOF
```

---

## 13. 리소스 정리 (삭제)

프로젝트를 종료할 때 비용이 발생하지 않도록 **역순으로** 모든 리소스를 삭제:

```bash
# 환경 변수 로드
source ~/.query-book-env

# 1. EC2 인스턴스 종료
aws ec2 terminate-instances --instance-ids $APP_INSTANCE_ID $NAT_INSTANCE_ID
aws ec2 wait instance-terminated --instance-ids $APP_INSTANCE_ID $NAT_INSTANCE_ID

# 2. Elastic IP 해제
aws ec2 release-address --allocation-id $EIP_ALLOC

# 3. 보안 그룹 삭제 (인스턴스 종료 후 가능)
aws ec2 delete-security-group --group-id $APP_SG_ID
aws ec2 delete-security-group --group-id $NAT_SG_ID

# 4. 서브넷 삭제
aws ec2 delete-subnet --subnet-id $PUBLIC_SUBNET_ID
aws ec2 delete-subnet --subnet-id $PRIVATE_SUBNET_ID

# 5. 라우팅 테이블 삭제 (연결 해제 후)
# 연결된 서브넷이 삭제되었으므로 바로 삭제 가능
aws ec2 delete-route-table --route-table-id $PUBLIC_RT_ID
aws ec2 delete-route-table --route-table-id $PRIVATE_RT_ID

# 6. IGW 분리 및 삭제
aws ec2 detach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID
aws ec2 delete-internet-gateway --internet-gateway-id $IGW_ID

# 7. VPC 삭제
aws ec2 delete-vpc --vpc-id $VPC_ID

# 8. 키 페어 삭제 (선택)
aws ec2 delete-key-pair --key-name query-book-key
rm ~/.ssh/query-book-key.pem

# 9. 환경 변수 파일 삭제
rm ~/.query-book-env

echo "모든 리소스가 삭제되었습니다."
```

**주의:** Elastic IP를 인스턴스 종료 전에 해제하면 과금됩니다 (미연결 EIP 시간당 $0.005). 반드시 인스턴스 종료 후 해제하세요.
