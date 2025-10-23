# 플랫폼별 오프라인 설치 가이드

**대상:** Linux 또는 Windows 폐쇄망 환경  
**Python 버전:** 3.11

---

## 🎯 빠른 선택 가이드

| 폐쇄망 환경 | 다운로드 스크립트 | 패키지 크기 | 특징 |
|-----------|----------------|-----------|------|
| **Windows만** | `download_packages_windows.ps1` | ~60-120 MB | pywin32, pyodbc 포함 |
| **Linux만** | `download_packages_linux.sh` | ~50-100 MB | psycopg2-binary 포함 |
| **둘 다** | 두 스크립트 모두 실행 | ~100-200 MB | 별도 디렉토리 생성 |

---

## 🪟 Windows 환경

### 1단계: 패키지 다운로드 (인터넷 연결 환경)

#### 자동 다운로드 (권장)

```powershell
# 프로젝트 루트에서 실행
cd rag_batch
.\scripts\download_packages_windows.ps1
```

**스크립트가 자동으로:**
- Windows용 패키지 다운로드 (win_amd64)
- 프로젝트 파일 복사
- ZIP 파일 생성 (선택)

#### 수동 다운로드

```powershell
# 작업 디렉토리 생성
mkdir rag_batch_offline_windows
cd rag_batch_offline_windows
mkdir packages

# requirements.txt 복사
Copy-Item "..\rag_batch\requirements.txt" .

# Windows용 패키지 다운로드
py -3.11 -m pip download -r requirements.txt -d packages `
  --platform win_amd64 `
  --python-version 3.11 `
  --only-binary=:all:
```

### 2단계: 폐쇄망으로 전송

- USB/보안USB로 `rag_batch_offline_windows.zip` 복사

### 3단계: 폐쇄망 설치

```powershell
# 압축 해제
Expand-Archive -Path rag_batch_offline_windows.zip -DestinationPath C:\

# 설치
cd C:\rag_batch_offline_windows\rag_batch
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --no-index --find-links=..\packages -r requirements.txt
```

### Windows 전용 패키지

✅ **포함되는 패키지:**
- `pywin32>=306` - 한글 프로그램 COM (HWP→PDF 변환)
- `python-magic-bin>=0.4.14` - 파일 타입 감지
- `psycopg2>=2.9.9` - PostgreSQL 드라이버
- `pyodbc>=5.0.0` - MSSQL 드라이버

---

## 🐧 Linux 환경

### 1단계: 패키지 다운로드 (인터넷 연결 환경)

#### 자동 다운로드 (권장)

```bash
# 프로젝트 루트에서 실행
cd rag_batch
chmod +x scripts/download_packages_linux.sh
./scripts/download_packages_linux.sh
```

**스크립트가 자동으로:**
- Linux용 패키지 다운로드 (manylinux2014_x86_64)
- 프로젝트 파일 복사
- tar.gz 파일 생성 (선택)

#### 수동 다운로드

```bash
# 작업 디렉토리 생성
mkdir rag_batch_offline_linux
cd rag_batch_offline_linux
mkdir packages

# requirements.txt 복사
cp ../rag_batch/requirements.txt .

# Linux용 패키지 다운로드
python3.11 -m pip download -r requirements.txt -d packages \
  --platform manylinux2014_x86_64 \
  --python-version 3.11 \
  --only-binary=:all:
```

### 2단계: 폐쇄망으로 전송

- USB로 `rag_batch_offline_linux.tar.gz` 복사

### 3단계: 폐쇄망 설치

```bash
# 압축 해제
tar -xzf rag_batch_offline_linux.tar.gz
cd rag_batch_offline_linux/rag_batch

# 설치
python3.11 -m venv venv
source venv/bin/activate
python -m pip install --no-index --find-links=../packages -r requirements.txt
```

### Linux 전용 패키지

✅ **포함되는 패키지:**
- `psycopg2-binary>=2.9.9` - PostgreSQL 드라이버 (컴파일 불필요)
- `pymysql>=1.1.0` - MySQL 드라이버

❌ **제외되는 Windows 전용 패키지:**
- `pywin32` - Windows 전용
- `python-magic-bin` - Windows 전용
- `pyodbc` - Windows 전용

---

## 🔄 두 플랫폼 모두 지원

두 환경 모두에서 사용해야 하는 경우:

### 인터넷 연결 환경

```bash
# Windows용 다운로드
cd rag_batch
.\scripts\download_packages_windows.ps1

# Linux용 다운로드
./scripts/download_packages_linux.sh

# 또는 수동으로
mkdir rag_batch_offline_multi
cd rag_batch_offline_multi

# Windows용
mkdir packages_windows
python -m pip download -r ../rag_batch/requirements.txt -d packages_windows \
  --platform win_amd64 --python-version 3.11 --only-binary=:all:

# Linux용
mkdir packages_linux
python -m pip download -r ../rag_batch/requirements.txt -d packages_linux \
  --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all:
```

---

## 📊 플랫폼별 패키지 비교

| 패키지 | Windows | Linux | 용도 |
|--------|---------|-------|------|
| requests | ✅ | ✅ | HTTP 클라이언트 |
| python-dotenv | ✅ | ✅ | 환경 변수 |
| openpyxl | ✅ | ✅ | Excel 처리 |
| sqlalchemy | ✅ | ✅ | 데이터베이스 |
| schedule | ✅ | ✅ | 스케줄링 |
| **pywin32** | ✅ | ❌ | HWP 변환 (Windows) |
| **python-magic-bin** | ✅ | ❌ | 파일 타입 감지 (Windows) |
| **psycopg2** | ✅ | ❌ | PostgreSQL (Windows) |
| **psycopg2-binary** | ❌ | ✅ | PostgreSQL (Linux) |
| **pyodbc** | ✅ | ❌ | MSSQL (Windows) |
| pymysql | ✅ | ✅ | MySQL |

---

## 🔧 HWP 변환 차이점

### Windows
```
HWP 파일 → 1차: 한글 프로그램 COM (pywin32)
           ↓ 실패 시
           2차: LibreOffice
```

**필요 조건:**
- `pywin32>=306` 패키지 (자동 포함)
- 한글과컴퓨터 한글(HWP) 프로그램 (별도 설치)
- 또는 LibreOffice (대체)

### Linux
```
HWP 파일 → LibreOffice만 사용
```

**필요 조건:**
- LibreOffice 설치
  ```bash
  sudo apt-get install libreoffice libreoffice-writer
  sudo apt-get install fonts-nanum  # 한글 폰트
  ```

---

## 🐛 문제 해결

### Windows: pywin32 설치 오류

**증상:**
```
ERROR: Could not find a version that satisfies the requirement pywin32
```

**해결:**
```powershell
# 다운로드 재시도 (--no-binary 제거)
py -3.11 -m pip download pywin32 -d packages --python-version 3.11
```

### Linux: psycopg2-binary 누락

**증상:**
```
ERROR: Could not find psycopg2-binary
```

**해결:**
```bash
# 명시적으로 다운로드
python3.11 -m pip download psycopg2-binary -d packages \
  --platform manylinux2014_x86_64 --python-version 3.11
```

### 플랫폼 불일치

**증상:**
```
ERROR: xxx-win_amd64.whl is not a supported wheel on this platform
```

**원인:** Windows 패키지를 Linux에서 설치 시도 (또는 반대)

**해결:** 올바른 플랫폼용 패키지 다시 다운로드

---

## ✅ 설치 확인

### Windows

```powershell
# 가상환경 활성화
.\venv\Scripts\Activate.ps1

# 패키지 확인
pip list | Select-String "pywin32|psycopg2|requests|openpyxl"

# 출력 예시:
# openpyxl       3.1.5
# psycopg2       2.9.9
# pywin32        306
# requests       2.32.5
```

### Linux

```bash
# 가상환경 활성화
source venv/bin/activate

# 패키지 확인
pip list | grep -E "psycopg2|requests|openpyxl"

# 출력 예시:
# openpyxl           3.1.5
# psycopg2-binary    2.9.9
# requests           2.32.5
```

---

## 📚 관련 문서

- **[OFFLINE_INSTALL_QUICK.md](OFFLINE_INSTALL_QUICK.md)** - 빠른 설치 가이드
- **[docs/OFFLINE_INSTALL.md](docs/OFFLINE_INSTALL.md)** - 상세 설치 가이드
- **[LIBRARY_CHECK_RESULT.md](LIBRARY_CHECK_RESULT.md)** - 라이브러리 점검 결과
- **[docs/HWP_CONVERSION.md](docs/HWP_CONVERSION.md)** - HWP 변환 가이드

---

## 📞 요약

| 단계 | Windows | Linux |
|-----|---------|-------|
| 다운로드 | `download_packages_windows.ps1` | `download_packages_linux.sh` |
| 크기 | ~60-120 MB | ~50-100 MB |
| 전송 | ZIP 파일 | tar.gz 파일 |
| 설치 | `pip install --no-index --find-links=..\packages` | `pip install --no-index --find-links=../packages` |

**작성일:** 2025-10-23  
**Python 버전:** 3.11

