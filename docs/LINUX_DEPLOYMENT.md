# Linux 환경 배포 가이드

## 📋 개요

배치 프로그램을 Linux 서버에 배포하는 방법을 안내합니다.

## 🖥️ 시스템 요구사항

### 최소 사양
- **OS**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **Python**: 3.10, 3.11, 3.12
- **메모리**: 2GB 이상
- **디스크**: 10GB 이상 (문서 저장 공간)

### 권장 사양
- **메모리**: 4GB 이상
- **CPU**: 2코어 이상
- **디스크**: SSD 권장

## 🚀 설치 과정

### 1단계: 시스템 패키지 설치

#### Ubuntu/Debian
```bash
# 시스템 업데이트
sudo apt-get update
sudo apt-get upgrade -y

# Python 및 필수 패키지
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    libreoffice \
    libreoffice-writer \
    fonts-nanum \
    fonts-nanum-coding \
    git \
    curl \
    unzip

# LibreOffice 설치 확인
soffice --version
```

#### CentOS/RHEL
```bash
# EPEL 저장소 활성화
sudo yum install -y epel-release

# Python 및 필수 패키지
sudo yum install -y \
    python3.11 \
    python3-pip \
    libreoffice \
    libreoffice-writer \
    git \
    curl \
    unzip

# 한글 폰트 설치
sudo yum install -y google-noto-sans-cjk-fonts
```

### 2단계: 프로젝트 설정

```bash
# 작업 디렉토리 생성
sudo mkdir -p /opt/ragflow-batch
sudo chown $USER:$USER /opt/ragflow-batch
cd /opt/ragflow-batch

# 프로젝트 파일 복사 (Git 또는 직접)
# 방법 1: Git clone
git clone <repository-url> .

# 방법 2: 파일 직접 복사
# scp -r rag_batch/ user@server:/opt/ragflow-batch/

# 디렉토리 구조 확인
ls -la
```

### 3단계: Python 환경 설정

```bash
# 가상환경 생성 (Python 3.11)
python3.11 -m venv venv

# 또는 python3
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# pip 업그레이드
pip install --upgrade pip

# 의존성 설치
pip install -r requirements.txt

# 설치 확인
pip list | grep ragflow
```

### 4단계: 환경 설정

```bash
# .env 파일 생성
cp env.example .env

# .env 파일 편집
nano .env
# 또는
vi .env
```

**.env 파일 예시:**
```env
# RAGFlow 설정
RAGFLOW_API_KEY=ragflow-your-api-key-here
RAGFLOW_BASE_URL=http://localhost:9380

# 엑셀 파일 경로
EXCEL_FILE_PATH=./data/documents.xlsx

# 스케줄 (선택사항)
SCHEDULE_TIME=03:00
# 또는
SCHEDULE_INTERVAL=86400
```

### 5단계: 초기 설정 실행

```bash
# 가상환경 활성화 상태에서
python scripts/setup.py

# 샘플 엑셀 파일 복사 (테스트용)
python scripts/copy_sample.py
```

### 6단계: 테스트 실행

```bash
# 엑셀 파일 읽기 테스트
python scripts/test_excel_read.py

# 배치 1회 실행 테스트
python run.py --once --excel "data/documents.xlsx"

# 로그 확인
tail -f logs/batch_*.log
```

## 🔄 자동 실행 설정

### 방법 1: systemd 서비스 (권장)

#### 서비스 파일 생성
```bash
sudo nano /etc/systemd/system/ragflow-batch.service
```

```ini
[Unit]
Description=RAGFlow Batch Processing Service
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/opt/ragflow-batch
Environment="PATH=/opt/ragflow-batch/venv/bin"
ExecStart=/opt/ragflow-batch/venv/bin/python run.py --schedule daily --time 03:00
Restart=always
RestartSec=10

# 로그 설정
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ragflow-batch

[Install]
WantedBy=multi-user.target
```

#### 서비스 활성화
```bash
# 서비스 리로드
sudo systemctl daemon-reload

# 서비스 시작
sudo systemctl start ragflow-batch

# 부팅 시 자동 시작 설정
sudo systemctl enable ragflow-batch

# 상태 확인
sudo systemctl status ragflow-batch

# 로그 확인
sudo journalctl -u ragflow-batch -f
```

#### 서비스 관리
```bash
# 서비스 중지
sudo systemctl stop ragflow-batch

# 서비스 재시작
sudo systemctl restart ragflow-batch

# 서비스 비활성화
sudo systemctl disable ragflow-batch
```

### 방법 2: cron 작업

```bash
# crontab 편집
crontab -e

# 매일 새벽 3시 실행
0 3 * * * cd /opt/ragflow-batch && /opt/ragflow-batch/venv/bin/python run.py --once >> /opt/ragflow-batch/logs/cron.log 2>&1

# 4시간마다 실행
0 */4 * * * cd /opt/ragflow-batch && /opt/ragflow-batch/venv/bin/python run.py --once >> /opt/ragflow-batch/logs/cron.log 2>&1

# cron 작업 확인
crontab -l
```

### 방법 3: 백그라운드 실행 (개발용)

```bash
# nohup으로 백그라운드 실행
nohup python run.py --schedule daily --time 03:00 > logs/nohup.log 2>&1 &

# 프로세스 ID 확인
echo $!

# 또는
ps aux | grep run.py

# 종료
kill <PID>
```

## 📊 모니터링

### 로그 확인

```bash
# 실시간 로그 모니터링
tail -f logs/batch_$(date +%Y%m%d).log

# 최근 오류 확인
grep "ERROR" logs/batch_*.log

# 최근 변환 내역
grep "HWP->PDF" logs/batch_*.log

# 최근 업로드 내역
grep "파일 업로드" logs/batch_*.log
```

### 시스템 리소스 모니터링

```bash
# CPU 및 메모리 사용량
top
# 또는
htop

# 디스크 사용량
df -h

# 프로세스별 리소스
ps aux | grep python
```

### 로그 로테이션

```bash
# logrotate 설정 파일 생성
sudo nano /etc/logrotate.d/ragflow-batch
```

```
/opt/ragflow-batch/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 644 your-username your-username
}
```

## 🔒 보안 설정

### 1. 파일 권한 설정

```bash
# 소유자만 읽기/쓰기
chmod 600 .env

# 스크립트 실행 권한
chmod +x run.py
chmod +x scripts/*.py

# 로그 디렉토리 권한
chmod 755 logs/
```

### 2. 방화벽 설정

```bash
# RAGFlow 서버가 같은 서버에 있는 경우
# 외부 접근 차단
sudo ufw deny 9380/tcp

# SSH 허용 (필요한 경우)
sudo ufw allow 22/tcp

# 방화벽 활성화
sudo ufw enable

# 상태 확인
sudo ufw status
```

### 3. SELinux 설정 (CentOS/RHEL)

```bash
# SELinux 상태 확인
getenforce

# 필요시 permissive 모드
sudo setenforce 0

# 영구 설정
sudo nano /etc/selinux/config
# SELINUX=permissive
```

## 🐳 Docker 배포 (선택사항)

### Dockerfile

```dockerfile
FROM python:3.11-slim

# 시스템 패키지 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        libreoffice-writer \
        fonts-nanum \
        fonts-nanum-coding \
        fonts-liberation \
        curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 작업 디렉토리
WORKDIR /app

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 초기 설정
RUN mkdir -p data/downloads data/temp logs

# 환경 변수
ENV PYTHONUNBUFFERED=1
ENV RAGFLOW_BASE_URL=http://ragflow:9380

# 볼륨
VOLUME ["/app/data", "/app/logs"]

# 실행
CMD ["python", "run.py", "--schedule", "daily", "--time", "03:00"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  ragflow-batch:
    build: .
    container_name: ragflow-batch
    environment:
      - RAGFLOW_API_KEY=${RAGFLOW_API_KEY}
      - RAGFLOW_BASE_URL=http://ragflow:9380
      - EXCEL_FILE_PATH=/app/data/documents.xlsx
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    depends_on:
      - ragflow
    networks:
      - ragflow-network

  ragflow:
    image: infiniflow/ragflow:latest
    container_name: ragflow
    ports:
      - "9380:9380"
    volumes:
      - ragflow-data:/ragflow/data
    restart: unless-stopped
    networks:
      - ragflow-network

networks:
  ragflow-network:
    driver: bridge

volumes:
  ragflow-data:
```

### Docker 실행

```bash
# 이미지 빌드
docker build -t ragflow-batch .

# 컨테이너 실행
docker run -d \
  --name ragflow-batch \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e RAGFLOW_API_KEY=your-api-key \
  ragflow-batch

# 또는 docker-compose 사용
docker-compose up -d

# 로그 확인
docker logs -f ragflow-batch

# 컨테이너 접속
docker exec -it ragflow-batch bash
```

## 🔧 문제 해결

### 권한 오류

```bash
# 오류: Permission denied
sudo chown -R $USER:$USER /opt/ragflow-batch
chmod -R 755 /opt/ragflow-batch
```

### LibreOffice 오류

```bash
# 오류: soffice command not found
which soffice
# 없으면 재설치
sudo apt-get install --reinstall libreoffice
```

### Python 버전 오류

```bash
# Python 버전 확인
python3 --version

# 여러 버전 설치 시
python3.11 --version
python3.12 --version

# 가상환경 재생성
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📝 유지보수

### 업데이트

```bash
# 코드 업데이트 (Git)
cd /opt/ragflow-batch
git pull origin main

# 가상환경 활성화
source venv/bin/activate

# 의존성 업데이트
pip install -r requirements.txt --upgrade

# 서비스 재시작
sudo systemctl restart ragflow-batch
```

### 백업

```bash
# 백업 스크립트
#!/bin/bash
BACKUP_DIR=/backup/ragflow-batch
DATE=$(date +%Y%m%d)

# 백업 디렉토리 생성
mkdir -p $BACKUP_DIR

# 데이터 백업
tar -czf $BACKUP_DIR/data-$DATE.tar.gz data/
tar -czf $BACKUP_DIR/logs-$DATE.tar.gz logs/

# .env 백업
cp .env $BACKUP_DIR/.env-$DATE

# 30일 이상 된 백업 삭제
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

### 정리

```bash
# 임시 파일 정리
rm -rf data/downloads/*
rm -rf data/temp/*

# 오래된 로그 정리 (30일 이상)
find logs/ -name "batch_*.log" -mtime +30 -delete

# 디스크 사용량 확인
du -sh data/ logs/
```

## ✅ 체크리스트

배포 전 확인:
- [ ] Python 3.10+ 설치 확인
- [ ] LibreOffice 설치 및 동작 확인
- [ ] 한글 폰트 설치 확인
- [ ] .env 파일 설정 완료
- [ ] 테스트 실행 성공
- [ ] 로그 파일 생성 확인
- [ ] systemd 서비스 등록 (또는 cron)
- [ ] 방화벽 설정 (필요시)
- [ ] 백업 설정
- [ ] 모니터링 설정

## 📞 지원

문제 발생 시:
1. 로그 파일 확인: `tail -f logs/batch_*.log`
2. 서비스 상태 확인: `systemctl status ragflow-batch`
3. 시스템 리소스 확인: `htop`, `df -h`
4. LibreOffice 테스트: `soffice --headless --convert-to pdf test.hwp`

