# RAGFlow Batch 오프라인 설치 가이드

## 개요

폐쇄망 환경에서 RAGFlow Batch 프로그램을 설치하기 위한 가이드입니다.

**환경:**
- Python 3.11.9
- Windows 10 (PowerShell) 또는 Linux

---

## 📦 1단계: 인터넷 연결 환경에서 패키지 다운로드

### 1.1 다운로드용 디렉토리 생성

#### Windows PowerShell:
```powershell
# 작업 디렉토리 생성
New-Item -ItemType Directory -Path "C:\rag_batch_offline" -Force
cd C:\rag_batch_offline

# 패키지 저장 디렉토리 생성
New-Item -ItemType Directory -Path "packages" -Force
```

#### Linux/Mac:
```bash
# 작업 디렉토리 생성
mkdir -p ~/rag_batch_offline
cd ~/rag_batch_offline

# 패키지 저장 디렉토리 생성
mkdir -p packages
```

---

### 1.2 requirements.txt 준비

먼저 프로젝트의 `requirements.txt` 파일을 작업 디렉토리에 복사하거나 다음 내용으로 생성합니다:

**requirements.txt**
```txt
# RAGFlow SDK
ragflow-sdk>=0.5.0

# HTTP 클라이언트
requests>=2.31.0

# 환경 변수 관리
python-dotenv>=1.0.0

# Excel 처리
openpyxl>=3.1.0

# 파일 다운로드
urllib3>=2.0.0

# 파일 변환 (선택사항)
python-magic-bin>=0.4.14; platform_system=="Windows"

# 스케줄링
schedule>=1.2.0

# 로깅
colorlog>=6.7.0
```

---

### 1.3 모든 의존성 패키지 다운로드

#### Python 3.11.9 사용 확인:
```bash
python --version
# 출력: Python 3.11.9
```

다른 버전이면 Python 3.11.9을 먼저 설치하세요.

#### Windows PowerShell:
```powershell
cd C:\rag_batch_offline

# 방법 1: 의존성 포함하여 다운로드 (추천)
python -m pip download -r requirements.txt -d packages

# 방법 2: 특정 Python 버전 명시 (필요 시)
python -m pip download -r requirements.txt -d packages --python-version 3.11 --only-binary=:all:

# Windows 전용 패키지 추가 다운로드
python -m pip download python-magic-bin -d packages
```

#### Linux:
```bash
cd ~/rag_batch_offline

# 방법 1: 의존성 포함하여 다운로드 (추천)
python3.11 -m pip download -r requirements.txt -d packages

# 방법 2: 특정 Python 버전 및 플랫폼 명시 (필요 시)
python3.11 -m pip download -r requirements.txt -d packages --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all:
```

---

### 1.4 다운로드 확인

```bash
# Windows
dir packages

# Linux/Mac
ls -lh packages/
```

**예상 출력:**
```
ragflow_sdk-0.5.0-py3-none-any.whl
requests-2.31.0-py3-none-any.whl
python_dotenv-1.0.0-py3-none-any.whl
openpyxl-3.1.0-py3-none-any.whl
... (30~50개의 .whl 파일)
```

---

### 1.5 프로젝트 소스 코드 복사

```bash
# Windows
Copy-Item -Path "C:\work\철도공사\ragplus\ragflow-plus\rag_batch" -Destination "C:\rag_batch_offline\rag_batch" -Recurse

# Linux
cp -r /path/to/ragflow-plus/rag_batch ~/rag_batch_offline/
```

---

### 1.6 아카이브 생성 (전송용)

#### Windows:
```powershell
# ZIP 파일 생성
Compress-Archive -Path "C:\rag_batch_offline\*" -DestinationPath "C:\rag_batch_offline.zip"
```

#### Linux:
```bash
# tar.gz 파일 생성
cd ~
tar -czf rag_batch_offline.tar.gz rag_batch_offline/

# 또는 zip 사용
zip -r rag_batch_offline.zip rag_batch_offline/
```

---

## 💾 2단계: 폐쇄망으로 파일 전송

### 전송 방법 예시:

1. **USB 드라이브**: `rag_batch_offline.zip` 또는 `rag_batch_offline.tar.gz` 복사
2. **보안 USB**: 보안 USB에 복사 후 폐쇄망 PC로 이동
3. **내부 파일 공유**: 회사 내부 파일 서버를 통해 전송
4. **CD/DVD**: 아카이브를 굽기

---

## 🖥️ 3단계: 폐쇄망 환경에서 압축 해제

### Windows:
```powershell
# 작업 디렉토리로 이동
cd C:\

# 압축 해제
Expand-Archive -Path "C:\rag_batch_offline.zip" -DestinationPath "C:\"

# 디렉토리 이동
cd C:\rag_batch_offline
```

### Linux:
```bash
# 홈 디렉토리로 이동
cd ~

# 압축 해제
tar -xzf rag_batch_offline.tar.gz
# 또는
unzip rag_batch_offline.zip

# 디렉토리 이동
cd rag_batch_offline
```

---

## 🐍 4단계: Python 가상환경 생성

### Windows:
```powershell
cd C:\rag_batch_offline\rag_batch

# 가상환경 생성
python -m venv venv

# 가상환경 활성화
.\venv\Scripts\Activate.ps1

# PowerShell 실행 정책 오류 시:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Linux:
```bash
cd ~/rag_batch_offline/rag_batch

# 가상환경 생성
python3.11 -m venv venv

# 가상환경 활성화
source venv/bin/activate
```

**활성화 확인:**
```bash
# 프롬프트에 (venv) 표시됨
(venv) PS C:\rag_batch_offline\rag_batch>
(venv) [user@host rag_batch]$
```

---

## 📦 5단계: 오프라인 패키지 설치

### 5.1 pip 업그레이드 (선택사항)

다운로드한 패키지에 pip 업그레이드 파일이 있다면:

```bash
python -m pip install --upgrade --no-index --find-links=../packages pip
```

### 5.2 모든 패키지 설치

#### Windows:
```powershell
cd C:\rag_batch_offline\rag_batch

# 가상환경 활성화 확인
.\venv\Scripts\Activate.ps1

# 오프라인 설치
python -m pip install --no-index --find-links=..\packages -r requirements.txt
```

#### Linux:
```bash
cd ~/rag_batch_offline/rag_batch

# 가상환경 활성화 확인
source venv/bin/activate

# 오프라인 설치
python -m pip install --no-index --find-links=../packages -r requirements.txt
```

**설명:**
- `--no-index`: PyPI를 사용하지 않음 (인터넷 연결 불필요)
- `--find-links=../packages`: 로컬 패키지 디렉토리 사용
- `-r requirements.txt`: requirements.txt의 모든 패키지 설치

---

### 5.3 설치 확인

```bash
# 설치된 패키지 목록 확인
pip list

# 주요 패키지 확인
pip show ragflow-sdk
pip show requests
pip show openpyxl
```

**예상 출력:**
```
Package         Version
--------------- -------
ragflow-sdk     0.5.0
requests        2.31.0
python-dotenv   1.0.0
openpyxl        3.1.0
...
```

---

## ⚙️ 6단계: 환경 설정

### 6.1 .env 파일 생성

```bash
# env.example을 복사
cp env.example .env

# 또는 직접 생성
nano .env  # Linux
notepad .env  # Windows
```

### 6.2 .env 파일 편집

```bash
# RAGFlow 설정
RAGFLOW_API_KEY=your_api_key_here
RAGFLOW_BASE_URL=http://192.168.10.41

# 지식베이스 권한 설정
DATASET_PERMISSION=team
DATASET_LANGUAGE=Korean

# 임베딩 모델 설정
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5

# 배치 설정
EXCEL_FILE_PATH=./data/input.xlsx
DOWNLOAD_DIR=./data/downloads
TEMP_DIR=./data/temp
LOG_DIR=./logs

# 스케줄 설정
BATCH_SCHEDULE=10:00
```

---

### 6.3 디렉토리 생성

```bash
# Windows
New-Item -ItemType Directory -Path "data\downloads" -Force
New-Item -ItemType Directory -Path "data\temp" -Force
New-Item -ItemType Directory -Path "logs" -Force

# Linux
mkdir -p data/downloads
mkdir -p data/temp
mkdir -p logs
```

---

### 6.4 Excel 파일 준비

```bash
# data 디렉토리에 Excel 파일 복사
# Windows
Copy-Item "path\to\your\excel.xlsx" "data\input.xlsx"

# Linux
cp /path/to/your/excel.xlsx data/input.xlsx
```

---

## ✅ 7단계: 테스트 실행

### 7.1 연결 테스트

```bash
# 가상환경 활성화 확인
# Windows: .\venv\Scripts\Activate.ps1
# Linux: source venv/bin/activate

# RAGFlow 연결 테스트
python -c "from ragflow_sdk import RAGFlow; from src.config import RAGFLOW_API_KEY, RAGFLOW_BASE_URL; rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL); print('연결 성공:', rag.list_datasets())"
```

### 7.2 배치 프로세스 1회 실행

```bash
python run.py --once
```

### 7.3 로그 확인

```bash
# Windows
type logs\batch_YYYYMMDD.log

# Linux
tail -f logs/batch_YYYYMMDD.log
```

---

## 🔧 문제 해결

### 문제 1: ModuleNotFoundError

**증상:**
```
ModuleNotFoundError: No module named 'ragflow_sdk'
```

**해결:**
```bash
# 가상환경 활성화 확인
# Windows
.\venv\Scripts\Activate.ps1

# Linux
source venv/bin/activate

# 패키지 재설치
python -m pip install --no-index --find-links=../packages -r requirements.txt
```

---

### 문제 2: 특정 패키지 버전 충돌

**해결:**
```bash
# 특정 패키지만 재설치
python -m pip install --no-index --find-links=../packages --force-reinstall ragflow-sdk
```

---

### 문제 3: Python 버전 불일치

**증상:**
```
ERROR: Package 'xxx' requires a different Python: 3.9.0 not in '>=3.11'
```

**해결:**
```bash
# Python 버전 확인
python --version

# Python 3.11.9가 아니면, 올바른 Python 사용
# Windows
py -3.11 -m venv venv

# Linux
python3.11 -m venv venv
```

---

### 문제 4: 패키지 다운로드 누락

**해결:**

인터넷 연결 환경에서 누락된 패키지만 추가 다운로드:

```bash
# 특정 패키지 다운로드
python -m pip download package_name -d packages --python-version 3.11

# 예시
python -m pip download certifi -d packages --python-version 3.11
```

---

## 📋 체크리스트

### 인터넷 연결 환경:
- [ ] Python 3.11.9 설치 확인
- [ ] requirements.txt 준비
- [ ] 모든 패키지 다운로드 (packages/ 디렉토리)
- [ ] 프로젝트 소스 복사 (rag_batch/ 디렉토리)
- [ ] 아카이브 생성 (zip 또는 tar.gz)

### 폐쇄망 환경:
- [ ] 아카이브 전송 및 압축 해제
- [ ] Python 3.11.9 설치 확인
- [ ] 가상환경 생성 및 활성화
- [ ] 패키지 오프라인 설치
- [ ] .env 파일 설정
- [ ] 디렉토리 생성 (data, logs)
- [ ] Excel 파일 준비
- [ ] 연결 테스트
- [ ] 배치 1회 실행 테스트

---

## 📚 추가 리소스

### Python 3.11.9 다운로드 (오프라인용)

**인터넷 연결 환경에서:**

1. **Windows**: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
2. **Linux**: https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tar.xz

Python 설치 파일도 함께 전송하여 폐쇄망에서 설치하세요.

---

### 전체 패키지 크기 추정

- 패키지 파일: 약 50~100 MB
- 프로젝트 소스: 약 1~5 MB
- **총 크기: 약 100~150 MB**

---

## 🎯 빠른 시작 스크립트

### Windows 전용 설치 스크립트 (install.ps1)

```powershell
# rag_batch_offline/install.ps1

Write-Host "RAGFlow Batch 오프라인 설치 시작..." -ForegroundColor Green

# 1. 가상환경 생성
Write-Host "`n1. 가상환경 생성 중..." -ForegroundColor Yellow
cd rag_batch
python -m venv venv

# 2. 가상환경 활성화
Write-Host "`n2. 가상환경 활성화..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# 3. 패키지 설치
Write-Host "`n3. 패키지 설치 중..." -ForegroundColor Yellow
python -m pip install --no-index --find-links=..\packages -r requirements.txt

# 4. 디렉토리 생성
Write-Host "`n4. 디렉토리 생성..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "data\downloads" -Force | Out-Null
New-Item -ItemType Directory -Path "data\temp" -Force | Out-Null
New-Item -ItemType Directory -Path "logs" -Force | Out-Null

# 5. .env 파일 생성
Write-Host "`n5. .env 파일 생성..." -ForegroundColor Yellow
if (!(Test-Path ".env")) {
    Copy-Item "env.example" ".env"
    Write-Host ".env 파일을 생성했습니다. 설정을 편집하세요." -ForegroundColor Cyan
}

Write-Host "`n설치 완료!" -ForegroundColor Green
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "1. .env 파일 편집 (notepad .env)" -ForegroundColor White
Write-Host "2. Excel 파일을 data/input.xlsx로 복사" -ForegroundColor White
Write-Host "3. 테스트 실행: python run.py --once" -ForegroundColor White
```

### Linux 전용 설치 스크립트 (install.sh)

```bash
#!/bin/bash
# rag_batch_offline/install.sh

echo "RAGFlow Batch 오프라인 설치 시작..."

# 1. 가상환경 생성
echo -e "\n1. 가상환경 생성 중..."
cd rag_batch
python3.11 -m venv venv

# 2. 가상환경 활성화
echo -e "\n2. 가상환경 활성화..."
source venv/bin/activate

# 3. 패키지 설치
echo -e "\n3. 패키지 설치 중..."
python -m pip install --no-index --find-links=../packages -r requirements.txt

# 4. 디렉토리 생성
echo -e "\n4. 디렉토리 생성..."
mkdir -p data/downloads
mkdir -p data/temp
mkdir -p logs

# 5. .env 파일 생성
echo -e "\n5. .env 파일 생성..."
if [ ! -f .env ]; then
    cp env.example .env
    echo ".env 파일을 생성했습니다. 설정을 편집하세요."
fi

echo -e "\n설치 완료!"
echo "다음 단계:"
echo "1. .env 파일 편집 (nano .env)"
echo "2. Excel 파일을 data/input.xlsx로 복사"
echo "3. 테스트 실행: python run.py --once"
```

**사용 방법:**

```bash
# Windows
cd C:\rag_batch_offline
.\install.ps1

# Linux
cd ~/rag_batch_offline
chmod +x install.sh
./install.sh
```

---

## 📞 지원

설치 중 문제가 발생하면 로그 파일과 오류 메시지를 확인하세요.

**일반적인 확인 사항:**
1. Python 버전이 3.11.9인지 확인
2. 가상환경이 활성화되어 있는지 확인
3. packages 디렉토리에 모든 .whl 파일이 있는지 확인
4. .env 파일 설정이 올바른지 확인

---

**작성일:** 2025-10-13  
**버전:** 1.0  
**Python 버전:** 3.11.9

