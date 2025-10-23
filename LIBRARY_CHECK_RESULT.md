# Requirements.txt 라이브러리 점검 결과

**점검일:** 2025-10-23  
**Python 버전:** 3.11

## ✅ 실제 사용되는 라이브러리

### 1. 직접 import되는 외부 라이브러리

| 라이브러리 | 사용 파일 | requirements.txt | 상태 |
|-----------|----------|------------------|------|
| `requests` | ragflow_client.py, file_handler.py | ✓ `requests>=2.31.0` | ✅ 포함됨 |
| `python-dotenv` | config.py | ✓ `python-dotenv>=1.0.0` | ✅ 포함됨 |
| `openpyxl` | excel_processor.py | ✓ `openpyxl>=3.1.0` | ✅ 포함됨 |
| `sqlalchemy` | db_connector.py | ✓ `sqlalchemy>=2.0.0` | ✅ 포함됨 |
| `schedule` | main.py | ✓ `schedule>=1.2.0` | ✅ 포함됨 |
| `pywin32` | file_handler.py (HWP 변환) | ✓ `pywin32>=306` | ✅ 포함됨 (Windows만) |

### 2. 데이터베이스 드라이버 (조건부 사용)

| 드라이버 | 데이터베이스 | requirements.txt | 상태 |
|---------|-------------|------------------|------|
| `psycopg2` | PostgreSQL | ✓ (조건부) | ✅ 포함됨 |
| `pymysql` | MySQL/MariaDB | ✓ | ✅ 포함됨 |
| `pyodbc` | MSSQL | ✓ (조건부) | ✅ 포함됨 |

## ⚠️ 직접 사용되지 않는 라이브러리

다음 라이브러리들은 소스 코드에서 직접 import되지 않지만, requirements.txt에 포함되어 있습니다:

| 라이브러리 | requirements.txt | 비고 |
|-----------|------------------|------|
| `colorlog` | ✓ `colorlog>=6.7.0` | logger.py는 표준 logging만 사용 |
| `chardet` | ✓ `chardet>=5.2.0` | 직접 사용 안 함 (requests의 의존성) |
| `python-magic-bin` | ✓ (Windows만) | 직접 사용 안 함 |
| `python-dateutil` | ✓ `python-dateutil>=2.8.2` | datetime은 표준 라이브러리 |
| `urllib3` | ✓ `urllib3>=2.0.0` | 직접 사용 안 함 (requests의 의존성) |
| `certifi` | ✓ `certifi>=2023.7.22` | 직접 사용 안 함 (requests의 의존성) |
| `et-xmlfile` | ✓ `et-xmlfile>=1.1.0` | openpyxl의 의존성 |

## 🔍 분석 결과

### 필수 라이브러리 (반드시 필요)

```txt
# HTTP 클라이언트
requests>=2.31.0

# 환경 변수 관리
python-dotenv>=1.0.0

# Excel 처리
openpyxl>=3.1.0

# 스케줄링
schedule>=1.2.0

# 데이터베이스 (SQLAlchemy)
sqlalchemy>=2.0.0
```

### DB 드라이버 (사용하는 DB에 따라 선택)

```txt
# PostgreSQL
psycopg2>=2.9.9; platform_system=="Windows"
psycopg2-binary>=2.9.9; platform_system!="Windows"

# MySQL/MariaDB
pymysql>=1.1.0

# MSSQL (Windows)
pyodbc>=5.0.0; platform_system=="Windows"
```

### 의존성 라이브러리 (자동 설치됨)

다음 라이브러리들은 명시하지 않아도 다른 패키지 설치 시 자동으로 설치됩니다:

- `urllib3` - requests의 의존성
- `certifi` - requests의 의존성
- `chardet` - requests의 의존성 (또는 charset-normalizer)
- `et-xmlfile` - openpyxl의 의존성

### 불필요한 라이브러리 (제거 가능)

```txt
# 사용되지 않음
colorlog>=6.7.0
python-magic-bin>=0.4.14
python-dateutil>=2.8.2
```

## 📝 권장사항

### 1. 최소 requirements.txt (필수만)

```txt
# RAGFlow Batch 필수 패키지
# Python 3.11+

# HTTP 클라이언트
requests>=2.31.0

# 환경 변수 관리
python-dotenv>=1.0.0

# Excel 처리
openpyxl>=3.1.0

# 스케줄링
schedule>=1.2.0

# 데이터베이스
sqlalchemy>=2.0.0

# PostgreSQL (선택)
psycopg2>=2.9.9; platform_system=="Windows"
psycopg2-binary>=2.9.9; platform_system!="Windows"

# MySQL (선택)
pymysql>=1.1.0

# MSSQL (선택, Windows만)
pyodbc>=5.0.0; platform_system=="Windows"
```

### 2. 현재 requirements.txt 유지

현재 requirements.txt를 그대로 유지해도 문제없습니다:
- 불필요한 라이브러리가 일부 있지만 용량이 크지 않음
- 의존성 라이브러리를 명시하면 버전 호환성 문제 예방
- 향후 기능 추가 시 사용할 수 있음

### 3. 폐쇄망 설치 시 고려사항

```powershell
# 모든 의존성 포함하여 다운로드 (권장)
python -m pip download -r requirements.txt -d packages

# 다운로드되는 패키지 수: 약 30-50개
# 총 크기: 약 50-100 MB
```

## ✅ 결론

**현재 requirements.txt는 정상입니다.**

1. ✅ 모든 필수 라이브러리 포함
2. ✅ DB 드라이버 정상 포함
3. ⚠️ 일부 불필요한 라이브러리 포함 (colorlog, python-magic-bin 등)
   - 하지만 제거하지 않아도 문제없음
4. ✅ 의존성 라이브러리 명시 (버전 호환성 보장)

**권장 조치:** 현재 상태 유지 또는 위의 "최소 requirements.txt" 사용

## 🔧 Python 3.11 호환성

모든 라이브러리는 Python 3.11과 호환됩니다:

| 라이브러리 | Python 3.11 지원 |
|-----------|-----------------|
| requests | ✅ |
| python-dotenv | ✅ |
| openpyxl | ✅ |
| schedule | ✅ |
| sqlalchemy | ✅ (2.0+) |
| psycopg2 | ✅ |
| pymysql | ✅ |
| pyodbc | ✅ |

---

**점검 방법:**
```powershell
# 실제 import 확인
grep -r "^import \|^from " src/

# 설치 테스트
py -3.11 -m pip install -r requirements.txt

# 실행 테스트
py -3.11 run.py --once
```

