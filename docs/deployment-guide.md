# AWS 배포 가이드

개발자 소수가 사용하는 내부 도구를 **최소 비용**으로 AWS에 배포하는 가이드입니다.

---

## 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [비용 분석](#2-비용-분석)
3. [사전 준비](#3-사전-준비)
4. [1단계: VPC 네트워크 구성](#4-1단계-vpc-네트워크-구성)
5. [2단계: NAT Instance 구성](#5-2단계-nat-instance-구성)
6. [3단계: 애플리케이션 EC2 구성](#6-3단계-애플리케이션-ec2-구성)
7. [4단계: 서버 설정 및 배포](#7-4단계-서버-설정-및-배포)
8. [5단계: GitHub Actions CI/CD](#8-5단계-github-actions-cicd)
9. [6단계: 도메인 및 HTTPS (선택)](#9-6단계-도메인-및-https-선택)
10. [운영 가이드](#10-운영-가이드)
11. [트러블슈팅](#11-트러블슈팅)

---

## 1. 아키텍처 개요

```
                    ┌─────────────────────────────────────────────┐
                    │                    VPC                       │
                    │              10.0.0.0/16                     │
                    │                                             │
  Internet          │   Public Subnet (10.0.1.0/24)               │
     │              │   ┌─────────────────────────────────┐       │
     │              │   │                                 │       │
     ├──── IGW ─────┤   │  NAT Instance (t3.nano)        │       │
     │              │   │  - Elastic IP                   │       │
     │              │   │  - iptables NAT                 │       │
     │              │   │                                 │       │
     │              │   └──────────┬──────────────────────┘       │
     │              │              │                               │
     │              │   Private Subnet (10.0.2.0/24)              │
     │              │   ┌──────────┴──────────────────────┐       │
     │              │   │                                 │       │
     │              │   │  App EC2 (t3.micro / t4g.micro) │       │
     │              │   │  ┌───────────┐ ┌─────────────┐  │       │
     │              │   │  │  FastAPI   │ │ PostgreSQL  │  │       │
     │              │   │  │  (Docker)  │ │ (Docker)    │  │       │
     │              │   │  └───────────┘ └─────────────┘  │       │
     │              │   │    docker-compose.prod.yml       │       │
     │              │   └─────────────────────────────────┘       │
     │              │                                             │
     │              └─────────────────────────────────────────────┘
     │
  개발자 브라우저
  (SSH 터널 또는 포트포워딩으로 접속)
```

### 왜 이 구조인가

| 결정 | 이유 |
|------|------|
| NAT Instance (t3.nano) | NAT Gateway($32/월) 대신 t3.nano($3/월)로 비용 90% 절감 |
| Private Subnet에 App 배치 | DB가 외부에 직접 노출되지 않도록 보안 확보 |
| 단일 EC2에 Docker Compose | RDS($15+/월) 없이 PostgreSQL을 같은 인스턴스에서 실행 |
| GitHub Actions SSH 배포 | 별도 CI/CD 인프라 불필요 |
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

### 프리 티어 이후 - 월 예상: ~$11

| 리소스 | 월 비용 |
|--------|---------|
| App EC2 (t3.micro) | ~$7.6 |
| NAT Instance (t3.nano) | ~$3.0 |
| EBS 16GB | ~$1.0 |
| **합계** | **~$11.6/월** |

### ARM (Graviton) 전환 시 - 월 예상: ~$9

| 리소스 | 월 비용 |
|--------|---------|
| App EC2 (t4g.micro) | ~$6.0 |
| NAT Instance (t4g.nano) | ~$2.4 |
| EBS 16GB | ~$1.0 |
| **합계** | **~$9.4/월** |

### 비교: NAT Gateway 사용 시

| | NAT Instance | NAT Gateway |
|---|---|---|
| 월 비용 | ~$3 | ~$32 + 전송비 |
| 가용성 | 단일 인스턴스 (수동 복구) | AWS 관리형 HA |
| 대역폭 | 인스턴스 타입에 의존 | 최대 45Gbps |
| **적합 대상** | **내부 도구, 소규모** | 프로덕션, 대규모 |

내부 개발자 도구이므로 NAT Instance가 적합합니다.

---

## 3. 사전 준비

### 3.1 필요한 도구

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

### 3.2 SSH 키 페어 생성

```bash
# AWS에서 키 페어 생성
aws ec2 create-key-pair \
  --key-name query-book-key \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/query-book-key.pem

chmod 400 ~/.ssh/query-book-key.pem
```

### 3.3 GitHub Repository Secrets 설정

GitHub 리포지토리 > Settings > Secrets and variables > Actions에서:

| Secret 이름 | 값 |
|-------------|-----|
| `EC2_HOST` | NAT Instance의 Elastic IP |
| `EC2_SSH_KEY` | `~/.ssh/query-book-key.pem`의 내용 |

---

## 4. 1단계: VPC 네트워크 구성

### 4.1 VPC 생성

```bash
# VPC 생성
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=query-book-vpc}]' \
  --query 'Vpc.VpcId' --output text)

echo "VPC_ID=$VPC_ID"

# DNS 호스트네임 활성화
aws ec2 modify-vpc-attribute \
  --vpc-id $VPC_ID \
  --enable-dns-hostnames '{"Value":true}'
```

### 4.2 서브넷 생성

```bash
# Public Subnet (NAT Instance용)
PUBLIC_SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.1.0/24 \
  --availability-zone ap-northeast-2a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=query-book-public}]' \
  --query 'Subnet.SubnetId' --output text)

echo "PUBLIC_SUBNET_ID=$PUBLIC_SUBNET_ID"

# Private Subnet (App EC2용)
PRIVATE_SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.2.0/24 \
  --availability-zone ap-northeast-2a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=query-book-private}]' \
  --query 'Subnet.SubnetId' --output text)

echo "PRIVATE_SUBNET_ID=$PRIVATE_SUBNET_ID"
```

### 4.3 Internet Gateway

```bash
# IGW 생성 및 VPC에 연결
IGW_ID=$(aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=query-book-igw}]' \
  --query 'InternetGateway.InternetGatewayId' --output text)

aws ec2 attach-internet-gateway \
  --internet-gateway-id $IGW_ID \
  --vpc-id $VPC_ID

echo "IGW_ID=$IGW_ID"
```

### 4.4 라우팅 테이블

```bash
# Public 라우팅 테이블 (IGW로 나감)
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

# Private 라우팅 테이블 (NAT Instance로 나감 - NAT 생성 후 업데이트)
PRIVATE_RT_ID=$(aws ec2 create-route-table \
  --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=query-book-private-rt}]' \
  --query 'RouteTable.RouteTableId' --output text)

aws ec2 associate-route-table \
  --route-table-id $PRIVATE_RT_ID \
  --subnet-id $PRIVATE_SUBNET_ID

echo "PUBLIC_RT_ID=$PUBLIC_RT_ID"
echo "PRIVATE_RT_ID=$PRIVATE_RT_ID"
```

---

## 5. 2단계: NAT Instance 구성

### 5.1 보안 그룹

```bash
# NAT Instance 보안 그룹
NAT_SG_ID=$(aws ec2 create-security-group \
  --group-name query-book-nat-sg \
  --description "NAT Instance SG" \
  --vpc-id $VPC_ID \
  --query 'GroupId' --output text)

# SSH 접속 (본인 IP만)
MY_IP=$(curl -s https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress \
  --group-id $NAT_SG_ID \
  --protocol tcp --port 22 \
  --cidr "${MY_IP}/32"

# Private Subnet에서 오는 모든 트래픽 허용
aws ec2 authorize-security-group-ingress \
  --group-id $NAT_SG_ID \
  --protocol -1 \
  --cidr 10.0.2.0/24

# 외부 접근용 HTTP (포트 포워딩으로 App에 접근)
aws ec2 authorize-security-group-ingress \
  --group-id $NAT_SG_ID \
  --protocol tcp --port 80 \
  --cidr "${MY_IP}/32"

echo "NAT_SG_ID=$NAT_SG_ID"
```

### 5.2 NAT Instance 시작

```bash
# Amazon Linux 2023 AMI 조회 (ap-northeast-2)
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" \
            "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

echo "AMI_ID=$AMI_ID"

# NAT Instance 시작
NAT_INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t3.nano \
  --key-name query-book-key \
  --subnet-id $PUBLIC_SUBNET_ID \
  --security-group-ids $NAT_SG_ID \
  --associate-public-ip-address \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=query-book-nat}]' \
  --query 'Instances[0].InstanceId' --output text)

echo "NAT_INSTANCE_ID=$NAT_INSTANCE_ID"

# 인스턴스 시작 대기
aws ec2 wait instance-running --instance-ids $NAT_INSTANCE_ID
```

### 5.3 Source/Dest Check 비활성화 (NAT 필수)

```bash
aws ec2 modify-instance-attribute \
  --instance-id $NAT_INSTANCE_ID \
  --no-source-dest-check
```

### 5.4 Elastic IP 할당

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

echo "NAT_PUBLIC_IP=$NAT_PUBLIC_IP"
```

### 5.5 NAT Instance에 iptables 설정

```bash
ssh -i ~/.ssh/query-book-key.pem ec2-user@$NAT_PUBLIC_IP << 'EOF'
# IP 포워딩 활성화
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward = 1" | sudo tee /etc/sysctl.d/nat.conf

# iptables NAT 규칙
sudo iptables -t nat -A POSTROUTING -o ens5 -s 10.0.2.0/24 -j MASQUERADE

# 포트 포워딩: NAT의 80 → App EC2의 80
# (App EC2 생성 후 IP 확인 후 설정)

# iptables 규칙 영구 저장
sudo dnf install -y iptables-services
sudo systemctl enable iptables
sudo service iptables save
EOF
```

### 5.6 Private 라우팅 테이블에 NAT 경로 추가

```bash
aws ec2 create-route \
  --route-table-id $PRIVATE_RT_ID \
  --destination-cidr-block 0.0.0.0/0 \
  --instance-id $NAT_INSTANCE_ID
```

---

## 6. 3단계: 애플리케이션 EC2 구성

### 6.1 보안 그룹

```bash
APP_SG_ID=$(aws ec2 create-security-group \
  --group-name query-book-app-sg \
  --description "App Instance SG" \
  --vpc-id $VPC_ID \
  --query 'GroupId' --output text)

# NAT Instance에서의 SSH
aws ec2 authorize-security-group-ingress \
  --group-id $APP_SG_ID \
  --protocol tcp --port 22 \
  --source-group $NAT_SG_ID

# NAT Instance에서의 HTTP
aws ec2 authorize-security-group-ingress \
  --group-id $APP_SG_ID \
  --protocol tcp --port 80 \
  --source-group $NAT_SG_ID

echo "APP_SG_ID=$APP_SG_ID"
```

### 6.2 App EC2 시작

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

echo "APP_INSTANCE_ID=$APP_INSTANCE_ID"
echo "APP_PRIVATE_IP=$APP_PRIVATE_IP"
```

### 6.3 NAT Instance에 포트 포워딩 추가

```bash
# NAT의 80번 포트 → App EC2의 80번 포트로 포워딩
ssh -i ~/.ssh/query-book-key.pem ec2-user@$NAT_PUBLIC_IP << EOF
sudo iptables -t nat -A PREROUTING -i ens5 -p tcp --dport 80 -j DNAT --to-destination ${APP_PRIVATE_IP}:80
sudo iptables -A FORWARD -p tcp -d ${APP_PRIVATE_IP} --dport 80 -j ACCEPT
sudo service iptables save
EOF
```

---

## 7. 4단계: 서버 설정 및 배포

### 7.1 NAT Instance를 통해 App EC2 접속

```bash
# SSH ProxyJump (로컬 → NAT → App)
ssh -i ~/.ssh/query-book-key.pem \
  -o ProxyCommand="ssh -i ~/.ssh/query-book-key.pem -W %h:%p ec2-user@$NAT_PUBLIC_IP" \
  ec2-user@$APP_PRIVATE_IP
```

**편의를 위해 `~/.ssh/config` 설정:**

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

이후 `ssh query-app`으로 바로 접속 가능.

### 7.2 App EC2 초기 설정

```bash
ssh query-app << 'SETUP'
# Docker 설치
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user

# Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Docker Compose V2 plugin
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo ln -sf /usr/local/bin/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose

echo "Docker: $(docker --version)"
echo "Docker Compose: $(docker compose version)"
SETUP
```

### 7.3 프로젝트 배포

```bash
ssh query-app << 'DEPLOY'
# 새 세션에서 docker 그룹 적용
newgrp docker << 'INNER'

# GitHub에서 코드 클론
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

### 7.4 배포 확인

```bash
# 로컬에서 NAT Instance의 Elastic IP로 접속
curl http://$NAT_PUBLIC_IP
# 또는 브라우저에서 http://<NAT_PUBLIC_IP>
```

---

## 8. 5단계: GitHub Actions CI/CD

### 8.1 워크플로우 파일

`.github/workflows/deploy.yml`이 이미 프로젝트에 포함되어 있습니다.

동작 흐름:
```
main 브랜치 push
  → GitHub Actions에서 테스트 실행 (PostgreSQL 서비스 컨테이너)
  → 테스트 통과 시 SSH로 EC2 접속
  → git pull → docker compose build → docker compose up
```

### 8.2 GitHub Secrets 등록

GitHub 리포지토리에서 Settings > Secrets and variables > Actions:

```
EC2_HOST     = <NAT_PUBLIC_IP>
EC2_SSH_KEY  = <~/.ssh/query-book-key.pem 내용 전체>
```

### 8.3 NAT Instance에 SSH 접근 허용 (GitHub Actions)

GitHub Actions의 IP 범위는 동적이므로, deploy job에서만 일시적으로 열거나
NAT Instance의 SSH를 0.0.0.0/0으로 열어야 합니다.

**방법 A: 고정 SG 규칙 (간단, 내부 도구용)**

```bash
# GitHub Actions IP 범위를 열기 (내부 도구이므로 허용 가능)
aws ec2 authorize-security-group-ingress \
  --group-id $NAT_SG_ID \
  --protocol tcp --port 22 \
  --cidr 0.0.0.0/0
```

**방법 B: deploy job에서 동적으로 IP 추가/제거 (더 안전)**

워크플로우에서 deploy job을 다음과 같이 수정:

```yaml
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Get runner IP
        id: ip
        run: echo "ip=$(curl -s https://checkip.amazonaws.com)" >> $GITHUB_OUTPUT

      - name: Open SSH
        run: |
          aws ec2 authorize-security-group-ingress \
            --group-id ${{ secrets.NAT_SG_ID }} \
            --protocol tcp --port 22 \
            --cidr "${{ steps.ip.outputs.ip }}/32"
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: ap-northeast-2

      - name: Deploy
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

      - name: Close SSH
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

### 8.4 SSH ProxyJump를 통한 배포

GitHub Actions에서 NAT를 거쳐 App EC2에 배포하려면:

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

이 경우 추가 Secret:
- `APP_PRIVATE_IP`: App EC2의 Private IP

---

## 9. 6단계: 도메인 및 HTTPS (선택)

내부 도구이므로 HTTPS가 필수는 아니지만, 필요 시:

### 방법 1: SSH 터널 (무료, 가장 간단)

```bash
# 로컬 8080 → NAT → App:80 터널
ssh -L 8080:$APP_PRIVATE_IP:80 query-nat

# 브라우저에서 http://localhost:8080 접속
```

### 방법 2: Caddy 리버스 프록시 (무료 Let's Encrypt)

NAT Instance에 Caddy를 설치하면 자동 HTTPS 인증서 발급:

```bash
ssh query-nat << 'EOF'
# Caddy 설치
sudo dnf install -y caddy

# Caddyfile 설정
sudo tee /etc/caddy/Caddyfile << 'CADDY'
query.yourdomain.com {
    reverse_proxy <APP_PRIVATE_IP>:80
}
CADDY

sudo systemctl enable caddy
sudo systemctl start caddy
EOF
```

**전제 조건**: 도메인의 DNS A 레코드가 NAT의 Elastic IP를 가리켜야 함.
이 경우 NAT SG에 443 포트도 열어야 합니다.

---

## 10. 운영 가이드

### 10.1 로그 확인

```bash
ssh query-app << 'EOF'
cd ~/query-repository
docker compose -f docker-compose.prod.yml logs -f --tail 50 app
docker compose -f docker-compose.prod.yml logs -f --tail 50 db
EOF
```

### 10.2 수동 배포

```bash
ssh query-app << 'EOF'
cd ~/query-repository
git pull origin main
docker compose -f docker-compose.prod.yml build --no-cache app
docker compose -f docker-compose.prod.yml up -d app
docker image prune -f
EOF
```

### 10.3 DB 백업

```bash
ssh query-app << 'EOF'
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U root query_book > ~/backup_$(date +%Y%m%d).sql
EOF

# 로컬로 다운로드
scp query-app:~/backup_*.sql ./backups/
```

### 10.4 DB 복원

```bash
scp ./backups/backup_20260318.sql query-app:~/

ssh query-app << 'EOF'
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U root query_book < ~/backup_20260318.sql
EOF
```

### 10.5 서비스 재시작

```bash
ssh query-app << 'EOF'
cd ~/query-repository
docker compose -f docker-compose.prod.yml restart
EOF
```

### 10.6 디스크 공간 관리

```bash
ssh query-app << 'EOF'
# Docker 미사용 리소스 정리
docker system prune -af --volumes

# 디스크 사용량 확인
df -h
EOF
```

### 10.7 NAT Instance 상태 확인

NAT Instance가 중지되면 App EC2는 외부 통신(docker pull 등)이 불가합니다.

```bash
# NAT Instance 상태 확인
aws ec2 describe-instance-status \
  --instance-ids $NAT_INSTANCE_ID \
  --query 'InstanceStatuses[0].InstanceState.Name' --output text
```

---

## 11. 트러블슈팅

### App EC2에서 인터넷이 안 되는 경우

```bash
# 1. NAT Instance가 실행 중인지 확인
aws ec2 describe-instances \
  --instance-ids $NAT_INSTANCE_ID \
  --query 'Reservations[0].Instances[0].State.Name'

# 2. Source/Dest Check가 비활성화되었는지 확인
aws ec2 describe-instance-attribute \
  --instance-id $NAT_INSTANCE_ID \
  --attribute sourceDestCheck

# 3. NAT Instance에서 IP 포워딩 확인
ssh query-nat "cat /proc/sys/net/ipv4/ip_forward"
# 출력: 1

# 4. iptables 규칙 확인
ssh query-nat "sudo iptables -t nat -L -n -v"

# 5. Private 라우팅 테이블에 NAT 경로 확인
aws ec2 describe-route-tables \
  --route-table-ids $PRIVATE_RT_ID \
  --query 'RouteTables[0].Routes'
```

### Docker Compose가 실행되지 않는 경우

```bash
ssh query-app << 'EOF'
cd ~/query-repository

# 컨테이너 상태 확인
docker compose -f docker-compose.prod.yml ps -a

# 에러 로그 확인
docker compose -f docker-compose.prod.yml logs --tail 100

# DB healthcheck 상태 확인
docker inspect query-repository-db-1 --format='{{.State.Health.Status}}'
EOF
```

### NAT Instance 재부팅 후 iptables 복구

```bash
ssh query-nat << 'EOF'
# iptables 규칙이 사라졌을 때
sudo sysctl -w net.ipv4.ip_forward=1
sudo service iptables restart

# 확인
sudo iptables -t nat -L -n
EOF
```

### GitHub Actions 배포 실패

1. **SSH 연결 실패**: NAT SG에서 GitHub Actions IP가 허용되었는지 확인
2. **git pull 실패**: App EC2에서 GitHub에 접근 가능한지 확인 (NAT 동작 여부)
3. **docker build 실패**: 디스크 공간 확인 (`df -h`)

---

## 부록: 전체 리소스 정리 (삭제 시)

프로젝트를 종료할 때 비용이 발생하지 않도록 모든 리소스를 삭제:

```bash
# 1. EC2 인스턴스 종료
aws ec2 terminate-instances --instance-ids $APP_INSTANCE_ID $NAT_INSTANCE_ID
aws ec2 wait instance-terminated --instance-ids $APP_INSTANCE_ID $NAT_INSTANCE_ID

# 2. Elastic IP 해제
aws ec2 release-address --allocation-id $EIP_ALLOC

# 3. 보안 그룹 삭제
aws ec2 delete-security-group --group-id $APP_SG_ID
aws ec2 delete-security-group --group-id $NAT_SG_ID

# 4. 서브넷 삭제
aws ec2 delete-subnet --subnet-id $PUBLIC_SUBNET_ID
aws ec2 delete-subnet --subnet-id $PRIVATE_SUBNET_ID

# 5. 라우팅 테이블 삭제
aws ec2 delete-route-table --route-table-id $PUBLIC_RT_ID
aws ec2 delete-route-table --route-table-id $PRIVATE_RT_ID

# 6. IGW 분리 및 삭제
aws ec2 detach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID
aws ec2 delete-internet-gateway --internet-gateway-id $IGW_ID

# 7. VPC 삭제
aws ec2 delete-vpc --vpc-id $VPC_ID

# 8. 키 페어 삭제 (선택)
aws ec2 delete-key-pair --key-name query-book-key
```
