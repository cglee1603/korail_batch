# 폐쇄망 패키지 다운로드 빠른 가이드

**Python 3.11 | Windows & Linux 지원**

---

## 🚀 빠른 시작

### 🪟 Windows 환경

```powershell
# 1. 프로젝트 디렉토리로 이동
cd rag_batch

# 2. 자동 다운로드 스크립트 실행
.\scripts\download_packages_windows.ps1

# 3. 완료! (rag_batch_offline_windows.zip 생성됨)
```

### 🐧 Linux 환경

```bash
# 1. 프로젝트 디렉토리로 이동
cd rag_batch

# 2. 실행 권한 부여 (최초 1회)
chmod +x scripts/download_packages_linux.sh

# 3. 자동 다운로드 스크립트 실행
./scripts/download_packages_linux.sh

# 4. 완료! (rag_batch_offline_linux.tar.gz 생성됨)
```

---

## 📦 다운로드 내용

| 플랫폼 | 패키지 수 | 크기 | 특징 |
|--------|----------|-----|------|
| Windows | 35-55개 | 60-120 MB | pywin32, pyodbc 포함 |
| Linux | 30-50개 | 50-100 MB | psycopg2-binary 포함 |

### Windows 전용 패키지
- ✅ `pywin32` - 한글 프로그램 COM (HWP→PDF 변환)
- ✅ `python-magic-bin` - 파일 타입 감지
- ✅ `psycopg2` - PostgreSQL
- ✅ `pyodbc` - MSSQL

### Linux 전용 패키지
- ✅ `psycopg2-binary` - PostgreSQL (컴파일 불필요)

### 공통 패키지
- ✅ `requests` - HTTP 클라이언트
- ✅ `python-dotenv` - 환경 변수 관리
- ✅ `openpyxl` - Excel 처리
- ✅ `sqlalchemy` - 데이터베이스
- ✅ `schedule` - 스케줄링
- ✅ `pymysql` - MySQL

---

## 📂 생성되는 디렉토리 구조

### Windows
```
rag_batch_offline_windows/
├── packages/                 # Windows용 .whl 패키지들
│   ├── requests-*.whl
│   ├── pywin32-*-win_amd64.whl
│   ├── psycopg2-*-win_amd64.whl
│   └── ...
├── rag_batch/               # 프로젝트 소스
│   ├── src/
│   ├── scripts/
│   ├── docs/
│   ├── run.py
│   └── requirements.txt
└── requirements.txt
```

### Linux
```
rag_batch_offline_linux/
├── packages/                 # Linux용 .whl 패키지들
│   ├── requests-*.whl
│   ├── psycopg2_binary-*-manylinux*.whl
│   └── ...
├── rag_batch/               # 프로젝트 소스
│   ├── src/
│   ├── scripts/
│   ├── docs/
│   ├── run.py
│   └── requirements.txt
└── requirements.txt
```

---

## 🔧 수동 다운로드 (스크립트 없이)

### Windows

```powershell
# 디렉토리 생성
mkdir rag_batch_offline_windows
cd rag_batch_offline_windows
mkdir packages

# requirements.txt 복사
Copy-Item "..\rag_batch\requirements.txt" .

# 패키지 다운로드
py -3.11 -m pip download -r requirements.txt -d packages `
  --platform win_amd64 `
  --python-version 3.11 `
  --only-binary=:all:

# 프로젝트 파일 복사
Copy-Item -Path "..\rag_batch" -Destination ".\rag_batch" -Recurse
```

### Linux

```bash
# 디렉토리 생성
mkdir rag_batch_offline_linux
cd rag_batch_offline_linux
mkdir packages

# requirements.txt 복사
cp ../rag_batch/requirements.txt .

# 패키지 다운로드
python3.11 -m pip download -r requirements.txt -d packages \
  --platform manylinux2014_x86_64 \
  --python-version 3.11 \
  --only-binary=:all:

# 프로젝트 파일 복사
cp -r ../rag_batch ./rag_batch
```

---

## 📤 폐쇄망 전송

### Windows
1. `rag_batch_offline_windows.zip` 파일을 USB에 복사
2. 폐쇄망 PC로 이동
3. ZIP 파일 압축 해제

### Linux
1. `rag_batch_offline_linux.tar.gz` 파일을 USB에 복사
2. 폐쇄망 서버로 이동
3. `tar -xzf rag_batch_offline_linux.tar.gz`

---

## 💻 폐쇄망 설치

### Windows

```powershell
# 압축 해제한 디렉토리로 이동
cd rag_batch_offline_windows\rag_batch

# 가상환경 생성
py -3.11 -m venv venv

# 가상환경 활성화
.\venv\Scripts\Activate.ps1

# 오프라인 설치
python -m pip install --no-index --find-links=..\packages -r requirements.txt

# 설치 확인
pip list
```

### Linux

```bash
# 압축 해제한 디렉토리로 이동
cd rag_batch_offline_linux/rag_batch

# 가상환경 생성
python3.11 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# 오프라인 설치
python -m pip install --no-index --find-links=../packages -r requirements.txt

# 설치 확인
pip list
```

---

## ✅ 설치 확인

### Windows
```powershell
pip list | Select-String "requests|openpyxl|pywin32|sqlalchemy"

# 예상 출력:
# openpyxl       3.1.5
# pywin32        306
# requests       2.32.5
# SQLAlchemy     2.0.35
```

### Linux
```bash
pip list | grep -E "requests|openpyxl|psycopg2|sqlalchemy"

# 예상 출력:
# openpyxl           3.1.5
# psycopg2-binary    2.9.9
# requests           2.32.5
# SQLAlchemy         2.0.35
```

---

## 🐛 문제 해결

### Python 3.11이 없는 경우

**Windows:**
```powershell
# Python 3.11 확인
py -3.11 --version

# 없으면 다운로드: https://www.python.org/downloads/release/python-3119/
# python-3.11.9-amd64.exe 설치
```

**Linux:**
```bash
# Python 3.11 확인
python3.11 --version

# 없으면 설치
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv
```

### 패키지 다운로드 실패

```bash
# pip 업그레이드
python -m pip install --upgrade pip

# 다시 시도
```

### 플랫폼 불일치 오류

```
ERROR: xxx-win_amd64.whl is not a supported wheel on this platform
```

**원인:** Windows 패키지를 Linux에서 설치 시도 (또는 반대)  
**해결:** 올바른 플랫폼용 패키지 다운로드

---

## 📊 비교표

| 항목 | Windows | Linux |
|-----|---------|-------|
| Python 명령 | `py -3.11` | `python3.11` |
| 가상환경 활성화 | `.\venv\Scripts\Activate.ps1` | `source venv/bin/activate` |
| 압축 형식 | ZIP | tar.gz |
| HWP 변환 | 한글 프로그램 + LibreOffice | LibreOffice만 |
| 전용 패키지 | pywin32, pyodbc | psycopg2-binary |

---

## 📚 상세 문서

- **[OFFLINE_PLATFORM_GUIDE.md](OFFLINE_PLATFORM_GUIDE.md)** - 플랫폼별 상세 가이드
- **[OFFLINE_INSTALL_QUICK.md](OFFLINE_INSTALL_QUICK.md)** - 빠른 설치 가이드
- **[LIBRARY_CHECK_RESULT.md](LIBRARY_CHECK_RESULT.md)** - 라이브러리 점검 결과

---

## 🎯 요약

1. **다운로드:** 해당 플랫폼 스크립트 실행
   - Windows: `.\scripts\download_packages_windows.ps1`
   - Linux: `./scripts/download_packages_linux.sh`

2. **전송:** USB로 ZIP/tar.gz 파일 복사

3. **설치:** 폐쇄망에서 압축 해제 후
   ```bash
   python -m pip install --no-index --find-links=../packages -r requirements.txt
   ```

**작성일:** 2025-10-23  
**Python 버전:** 3.11

