# 폐쇄망 설치 빠른 가이드 (Python 3.11)

RAGFlow Batch 프로그램을 폐쇄망(오프라인) 환경에서 설치하는 간단한 가이드입니다.

## 📋 목차
1. [패키지 다운로드 (인터넷 연결 필요)](#1-패키지-다운로드-인터넷-연결-필요)
2. [폐쇄망 설치 (오프라인)](#2-폐쇄망-설치-오프라인)
3. [문제 해결](#3-문제-해결)

---

## 1. 패키지 다운로드 (인터넷 연결 필요)

### 1.1 Python 3.11 버전 확인

```powershell
# Python 3.11 사용
py -3.11 --version
# 또는
python --version
```

출력: `Python 3.11.x` (3.11 버전이면 OK)

### 1.2 패키지 다운로드 (플랫폼별)

> **중요:** 폐쇄망에서 사용할 **운영체제에 맞는** 패키지를 다운로드하세요!

#### 🪟 Windows 환경용 패키지

```powershell
# 작업 디렉토리 생성
mkdir rag_batch_offline_windows
cd rag_batch_offline_windows
mkdir packages

# requirements.txt 복사
Copy-Item "..\rag_batch\requirements.txt" .

# Windows용 Python 3.11 패키지 다운로드
py -3.11 -m pip download -r requirements.txt -d packages --platform win_amd64 --python-version 3.11 --only-binary=:all:
```

**포함되는 Windows 전용 패키지:**
- `pywin32` (한글 프로그램 COM, HWP 변환용)
- `python-magic-bin` (파일 타입 감지)
- `psycopg2` (PostgreSQL, 바이너리)
- `pyodbc` (MSSQL)

**다운로드 크기:** 약 60-120 MB  
**패키지 수:** 약 35-55개

#### 🐧 Linux 환경용 패키지

```bash
# 작업 디렉토리 생성
mkdir rag_batch_offline_linux
cd rag_batch_offline_linux
mkdir packages

# requirements.txt 복사
cp ../rag_batch/requirements.txt .

# Linux용 Python 3.11 패키지 다운로드
python3.11 -m pip download -r requirements.txt -d packages \
  --platform manylinux2014_x86_64 \
  --python-version 3.11 \
  --only-binary=:all:
```

**포함되는 Linux 전용 패키지:**
- `psycopg2-binary` (PostgreSQL)
- Linux용 wheel 패키지들

**제외되는 패키지:**
- `pywin32` (Windows 전용)
- `python-magic-bin` (Windows 전용)
- `pyodbc` (Windows 전용)

**다운로드 크기:** 약 50-100 MB  
**패키지 수:** 약 30-50개

#### 🔄 두 플랫폼 모두 지원 (권장)

두 환경 모두에서 사용할 경우:

```bash
# 통합 디렉토리 생성
mkdir rag_batch_offline_multi
cd rag_batch_offline_multi
mkdir packages_windows packages_linux

# Windows용
python -m pip download -r requirements.txt -d packages_windows \
  --platform win_amd64 --python-version 3.11 --only-binary=:all:

# Linux용
python -m pip download -r requirements.txt -d packages_linux \
  --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all:
```

**다운로드 크기:** 약 100-200 MB (두 플랫폼 합산)

> **참고:** `--only-binary=:all:` 옵션은 바이너리 패키지만 다운로드하여 컴파일 불필요

### 1.3 프로젝트 파일 복사

```powershell
# 프로젝트 전체를 rag_batch_offline 디렉토리로 복사
Copy-Item -Path "C:\work\철도공사\ragplus\ragflow-plus\rag_batch\*" -Destination ".\rag_batch" -Recurse
```

### 1.4 압축 (전송용)

```powershell
# ZIP 파일 생성
Compress-Archive -Path ".\*" -DestinationPath "..\rag_batch_offline.zip"
```

**결과물:** `rag_batch_offline.zip` (약 100-150 MB)

---

## 2. 폐쇄망 설치 (오프라인)

### 2.1 파일 전송

- USB/보안USB로 `rag_batch_offline.zip` 파일을 폐쇄망 PC로 복사

### 2.2 압축 해제

```powershell
# 원하는 위치에 압축 해제
cd C:\
Expand-Archive -Path "C:\rag_batch_offline.zip" -DestinationPath "C:\"
cd C:\rag_batch_offline\rag_batch
```

### 2.3 가상환경 생성 및 활성화

```powershell
# Python 3.11로 가상환경 생성
py -3.11 -m venv venv

# 가상환경 활성화
.\venv\Scripts\Activate.ps1

# PowerShell 실행 정책 오류 시:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

프롬프트에 `(venv)` 표시되면 성공

### 2.4 오프라인 패키지 설치

```powershell
# 반드시 가상환경이 활성화된 상태에서 실행
python -m pip install --no-index --find-links=..\packages -r requirements.txt
```

**옵션 설명:**
- `--no-index`: 인터넷(PyPI) 사용 안 함
- `--find-links=..\packages`: 로컬 packages 디렉토리 사용

### 2.5 설치 확인

```powershell
pip list
```

주요 패키지가 설치되었는지 확인:
- requests
- openpyxl
- python-dotenv
- sqlalchemy
- psycopg2 (PostgreSQL 사용 시)
- pymysql (MySQL 사용 시)

### 2.6 환경 설정

```powershell
# .env 파일 생성
Copy-Item env.example .env

# .env 파일 편집 (메모장 등)
notepad .env
```

**필수 설정:**
```env
RAGFLOW_API_KEY=your_api_key_here
RAGFLOW_BASE_URL=http://your-server:9380

# 데이터 소스 선택
DATA_SOURCE=excel  # 또는 db, both

# Excel 사용 시
EXCEL_FILE_PATH=./data/input.xlsx

# DB 사용 시
DB_CONNECTION_STRING=postgresql://user:pass@host:5432/db
DB_SQL_FILE_PATH=./data/query.sql
```

### 2.7 디렉토리 생성

```powershell
mkdir data\downloads, data\temp, logs -Force
```

### 2.8 테스트 실행

```powershell
# 1회 실행 테스트
python run.py --once
```

---

## 3. 문제 해결

### 문제 1: Python 3.11이 없음

**증상:**
```
py -3.11 : Python 3.11을 찾을 수 없습니다
```

**해결:**
- Python 3.11 설치 필요
- 다운로드: https://www.python.org/downloads/release/python-3119/
- `python-3.11.9-amd64.exe` 다운로드 후 폐쇄망으로 전송

### 문제 2: 패키지 누락 오류

**증상:**
```
ERROR: Could not find a version that satisfies the requirement xxx
```

**해결:**
```powershell
# 인터넷 연결 환경에서 누락된 패키지 추가 다운로드
python -m pip download 패키지명 -d packages --python-version 3.11

# 예: psycopg2 누락 시
python -m pip download psycopg2 -d packages --python-version 3.11
```

### 문제 3: 가상환경이 활성화되지 않음

**증상:**
- `pip list` 실행 시 설치한 패키지가 보이지 않음

**해결:**
```powershell
# 가상환경 재활성화
.\venv\Scripts\Activate.ps1

# 프롬프트에 (venv) 표시 확인
```

### 문제 4: psycopg2 설치 오류 (PostgreSQL)

**증상:**
```
ERROR: Could not build wheels for psycopg2
```

**해결:**
- Windows에서는 `psycopg2-binary` 사용 권장
- requirements.txt에 이미 `psycopg2>=2.9.9; platform_system=="Windows"` 포함됨
- 다운로드 시 자동으로 바이너리 버전 다운로드됨

### 문제 5: DB 드라이버 충돌

**해결:**
- 사용하는 DB에 맞는 드라이버만 설치
- 필요없는 드라이버는 requirements.txt에서 주석 처리

```txt
# PostgreSQL만 사용
sqlalchemy>=2.0.0
psycopg2>=2.9.9; platform_system=="Windows"

# MySQL은 주석 처리
# pymysql>=1.1.0

# MSSQL은 주석 처리
# pyodbc>=5.0.0; platform_system=="Windows"
```

---

## 📝 체크리스트

### 인터넷 연결 환경
- [ ] Python 3.11 설치 확인
- [ ] `pip download` 실행
- [ ] packages 디렉토리에 .whl 파일 확인 (30-50개)
- [ ] 프로젝트 파일 복사
- [ ] ZIP 파일 생성

### 폐쇄망 환경
- [ ] ZIP 파일 전송
- [ ] 압축 해제
- [ ] Python 3.11 설치 확인
- [ ] 가상환경 생성 및 활성화
- [ ] 패키지 오프라인 설치
- [ ] .env 파일 설정
- [ ] 테스트 실행 성공

---

## 🔍 참고 사항

### 다운로드 패키지 크기
- 기본 패키지: ~50 MB
- DB 드라이버 포함: ~100 MB
- 프로젝트 소스: ~5 MB
- **총 크기: 약 100-150 MB**

### Python 3.11 버전
- Python 3.11.0 ~ 3.11.x 모두 호환
- 권장: Python 3.11.9 이상

### 데이터베이스 지원
- PostgreSQL (psycopg2)
- MySQL/MariaDB (pymysql)
- MSSQL (pyodbc)
- SQLite (기본 내장)
- Oracle (cx_oracle, 별도 설치 필요)

---

## 📚 추가 문서

- **상세 가이드:** [docs/OFFLINE_INSTALL.md](docs/OFFLINE_INSTALL.md)
- **DB 연동:** [docs/DATABASE_INTEGRATION.md](docs/DATABASE_INTEGRATION.md)
- **문제 해결:** [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

**작성일:** 2025-10-23  
**버전:** 1.1  
**Python 요구 버전:** 3.11.x

