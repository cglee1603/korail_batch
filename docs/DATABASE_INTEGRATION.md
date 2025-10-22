# 데이터베이스 통합 가이드

RAGFlow Plus 배치 프로그램에 데이터베이스 조회 기능을 통합하는 방법을 설명합니다.

## 목차

1. [개요](#개요)
2. [지원하는 데이터베이스](#지원하는-데이터베이스)
3. [설치](#설치)
4. [설정 방법](#설정-방법)
5. [데이터 처리 방식](#데이터-처리-방식)
6. [사용 예시](#사용-예시)
7. [문제 해결](#문제-해결)

---

## 개요

DB 통합 기능을 사용하면 다음과 같은 작업이 가능합니다:

- **데이터베이스에서 직접 데이터 조회** → RAGFlow에 업로드
- **SQL 파일 기반 쿼리 실행** (동적 쿼리 수정 가능)
- **Excel과 DB 혼합 사용** (both 모드)
- **3가지 데이터 처리 방식 지원**:
  - 방식 A: DB에 파일 경로 저장 → 파일 업로드
  - 방식 B: DB 내용을 텍스트로 변환 → 텍스트 업로드
  - 방식 C: 혼합 (A + B)

### 데이터 흐름

```
┌─────────────┐         ┌─────────────┐
│ Excel 파일  │         │  Database   │
└──────┬──────┘         └──────┬──────┘
       │                       │
       │                       │ SQL 쿼리 실행
       ↓                       ↓
┌─────────────────────────────────────┐
│      Batch Processor (통합)         │
├─────────────────────────────────────┤
│  • Excel Processor (기존)           │
│  • DB Processor (신규)               │
└──────────────┬──────────────────────┘
               ↓
       ┌───────────────┐
       │ File Handler  │
       └───────┬───────┘
               ↓
       ┌───────────────┐
       │ RAGFlow Client│
       └───────────────┘
```

---

## 지원하는 데이터베이스

| 데이터베이스 | 지원 여부 | 드라이버 | 설치 명령 |
|-----------|---------|---------|---------|
| PostgreSQL | ✅ | psycopg2 | `pip install psycopg2-binary` |
| MySQL/MariaDB | ✅ | pymysql | `pip install pymysql` |
| SQL Server (MSSQL) | ✅ | pyodbc | `pip install pyodbc` |
| Oracle | ✅ | cx_oracle | `pip install cx_oracle` |
| SQLite | ✅ | 기본 내장 | 추가 설치 불필요 |

---

## 설치

### 1. 기본 패키지 설치

```powershell
# SQLAlchemy (필수)
pip install sqlalchemy
```

### 2. 데이터베이스별 드라이버 설치

#### PostgreSQL
```powershell
pip install psycopg2-binary
```

#### MySQL/MariaDB
```powershell
pip install pymysql
```

#### SQL Server (MSSQL)
```powershell
# ODBC Driver 17 for SQL Server 설치 필요
# https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

pip install pyodbc
```

#### Oracle
```powershell
# Oracle Instant Client 설치 필요
# https://www.oracle.com/database/technologies/instant-client.html

pip install cx_oracle
```

#### SQLite
```
추가 설치 불필요 (Python 기본 내장)
```

### 3. 전체 패키지 설치 (권장)

```powershell
pip install -r requirements.txt
```

---

## 설정 방법

### 1. `.env` 파일 설정

`env.example`을 참고하여 `.env` 파일을 수정합니다.

#### 기본 설정
```env
# 데이터 소스 선택
DATA_SOURCE=db  # "excel", "db", "both" 중 선택

# SQL 파일 경로
DB_SQL_FILE_PATH=./data/query.sql
```

#### 방법 1: 연결 문자열 사용 (간편)
```env
# PostgreSQL
DB_CONNECTION_STRING=postgresql://user:password@localhost:5432/database_name

# MySQL
DB_CONNECTION_STRING=mysql://user:password@localhost:3306/database_name

# MSSQL
DB_CONNECTION_STRING=mssql://user:password@localhost:1433/database_name

# SQLite
DB_CONNECTION_STRING=sqlite:///./data/database.db
```

#### 방법 2: 개별 파라미터 사용 (상세 설정)
```env
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_username
DB_PASSWORD=your_password
```

### 2. SQL 쿼리 작성

`data/query.sql` 파일을 작성합니다.

#### 예시 1: 파일 경로 조회
```sql
SELECT 
    문서ID AS document_id,
    제목 AS title,
    파일경로 AS file_path,
    카테고리 AS category,
    작성일 AS created_at
FROM 
    문서관리
WHERE 
    삭제여부 = 'N'
ORDER BY 
    작성일 DESC;
```

#### 예시 2: 텍스트 내용 조회
```sql
SELECT 
    규정ID AS regulation_id,
    규정명 AS title,
    규정내용 AS content,
    부서 AS department
FROM 
    규정관리
WHERE 
    시행여부 = 'Y';
```

### 3. 데이터 처리 방식 설정

#### 방식 A: 파일 경로 사용
```env
DB_FILE_PATH_COLUMN=file_path
DB_CONTENT_COLUMNS=
```

#### 방식 B: 내용 변환
```env
DB_FILE_PATH_COLUMN=
DB_CONTENT_COLUMNS=title,content,description
```

#### 방식 C: 혼합
```env
DB_FILE_PATH_COLUMN=file_path
DB_CONTENT_COLUMNS=summary,notes
```

### 4. 메타데이터 설정 (선택)

```env
# 특정 컬럼만 메타데이터로 사용
DB_METADATA_COLUMNS=category,author,created_at

# 또는 비워두면 모든 컬럼 사용
DB_METADATA_COLUMNS=
```

---

## 데이터 처리 방식

### 방식 A: 파일 경로 사용

DB에 파일 경로가 저장되어 있는 경우 사용합니다.

**SQL 쿼리 예시:**
```sql
SELECT 
    매뉴얼ID AS manual_id,
    제목 AS title,
    파일경로 AS file_path,
    카테고리 AS category
FROM 매뉴얼관리;
```

**설정:**
```env
DB_FILE_PATH_COLUMN=file_path
```

**결과:**
- `file_path` 컬럼의 경로에서 파일을 가져옴
- 다른 컬럼들은 메타데이터로 저장

---

### 방식 B: 내용을 텍스트 파일로 변환

DB의 텍스트 데이터를 직접 파일로 만들어 업로드합니다.

**SQL 쿼리 예시:**
```sql
SELECT 
    규정ID AS regulation_id,
    규정명 AS title,
    규정내용 AS content
FROM 규정관리;
```

**설정:**
```env
DB_CONTENT_COLUMNS=title,content
```

**결과:**
- `title`과 `content` 컬럼을 텍스트 파일로 생성
- 파일 예시:
  ```
  ## title
  안전 운행 규정
  
  ## content
  1. 운행 전 점검사항...
  2. 안전 수칙...
  ```

---

### 방식 C: 혼합 (파일 + 텍스트)

파일 경로와 추가 텍스트를 모두 처리합니다.

**설정:**
```env
DB_FILE_PATH_COLUMN=file_path
DB_CONTENT_COLUMNS=summary,notes
```

**결과:**
- `file_path`가 있으면 파일 업로드
- `file_path`가 없으면 `summary`와 `notes`를 텍스트 파일로 생성

---

## 사용 예시

### 예시 1: PostgreSQL에서 문서 경로 조회

**1. 패키지 설치**
```powershell
pip install sqlalchemy psycopg2-binary
```

**2. `.env` 설정**
```env
DATA_SOURCE=db
DB_CONNECTION_STRING=postgresql://admin:pass123@192.168.1.100:5432/documents
DB_SQL_FILE_PATH=./data/query.sql
DB_FILE_PATH_COLUMN=document_path
DB_METADATA_COLUMNS=title,category,author,created_at
```

**3. `data/query.sql` 작성**
```sql
SELECT 
    doc_id,
    title,
    document_path,
    category,
    author,
    created_at
FROM documents
WHERE status = 'active'
ORDER BY created_at DESC
LIMIT 100;
```

**4. 실행**
```powershell
python run.py --once --source db
```

---

### 예시 2: MySQL에서 규정 내용 변환

**1. `.env` 설정**
```env
DATA_SOURCE=db
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=regulations
DB_USER=admin
DB_PASSWORD=admin123
DB_SQL_FILE_PATH=./data/query.sql
DB_FILE_PATH_COLUMN=
DB_CONTENT_COLUMNS=regulation_name,regulation_content
DB_METADATA_COLUMNS=department,effective_date
```

**2. `data/query.sql` 작성**
```sql
SELECT 
    regulation_name,
    regulation_content,
    department,
    effective_date
FROM regulations
WHERE status = 'active';
```

**3. 실행**
```powershell
python run.py --once --source db
```

---

### 예시 3: SQLite 테스트

**1. 테스트 DB 생성**
```powershell
sqlite3 data/test.db
```

```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    title TEXT,
    file_path TEXT,
    category TEXT
);

INSERT INTO documents VALUES 
(1, '매뉴얼 1', 'C:\docs\manual1.pdf', '기술'),
(2, '매뉴얼 2', 'C:\docs\manual2.hwp', '업무');
```

**2. `.env` 설정**
```env
DATA_SOURCE=db
DB_CONNECTION_STRING=sqlite:///./data/test.db
DB_SQL_FILE_PATH=./data/query.sql
DB_FILE_PATH_COLUMN=file_path
```

**3. `data/query.sql` 작성**
```sql
SELECT * FROM documents;
```

**4. 실행**
```powershell
python run.py --once --source db
```

---

### 예시 4: Excel + DB 혼합

**`.env` 설정**
```env
DATA_SOURCE=both
EXCEL_FILE_PATH=./data/input.xlsx
DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/db
DB_SQL_FILE_PATH=./data/query.sql
DB_FILE_PATH_COLUMN=file_path
```

**실행**
```powershell
python run.py --once --source both
```

**결과:**
- Excel 파일의 모든 시트 처리
- DB 쿼리 결과 처리
- 모두 RAGFlow에 업로드

---

## 명령행 옵션

```powershell
# DB만 사용
python run.py --once --source db

# Excel만 사용 (기본값)
python run.py --once --source excel

# 둘 다 사용
python run.py --once --source both

# 스케줄 실행
python run.py --source db
```

---

## 문제 해결

### 1. 연결 오류

**증상:**
```
✗ DB 연결 실패: could not connect to server
```

**해결:**
- DB 서버가 실행 중인지 확인
- 방화벽/포트 설정 확인
- 연결 정보 (호스트, 포트, 사용자명, 비밀번호) 재확인

---

### 2. 드라이버 오류

**증상:**
```
ModuleNotFoundError: No module named 'psycopg2'
```

**해결:**
```powershell
pip install psycopg2-binary
```

---

### 3. SQL 오류

**증상:**
```
✗ 쿼리 실행 실패: syntax error
```

**해결:**
- `data/query.sql` 파일의 SQL 문법 확인
- DB 타입별 문법 차이 확인 (예: LIMIT vs TOP)
- 테이블/컬럼명 확인

---

### 4. 인코딩 오류

**증상:**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte
```

**해결:**
- SQL 파일을 UTF-8로 저장
- BOM 없이 저장 (UTF-8 without BOM)

---

### 5. 컬럼 매핑 오류

**증상:**
```
파일 경로 또는 내용 컬럼 없음
```

**해결:**
- `.env`의 `DB_FILE_PATH_COLUMN` 설정 확인
- SQL 쿼리 결과의 컬럼명과 일치하는지 확인
- 또는 `DB_CONTENT_COLUMNS` 설정

---

## 고급 설정

### 쿼리 파라미터 사용

현재는 정적 SQL 파일만 지원하지만, 필요시 다음과 같이 확장 가능합니다:

```python
# src/db_processor.py 수정
params = {'start_date': '2024-01-01', 'end_date': '2024-12-31'}
rows = self.connector.execute_sql_file(self.sql_file_path, params)
```

```sql
-- data/query.sql
SELECT * FROM documents 
WHERE created_at BETWEEN :start_date AND :end_date;
```

---

## 보안 고려사항

1. **비밀번호 보호**: `.env` 파일을 `.gitignore`에 추가
2. **읽기 전용 계정**: DB 사용자에게 SELECT 권한만 부여
3. **SQL 인젝션 방지**: 파라미터 바인딩 사용
4. **연결 암호화**: SSL/TLS 연결 사용 권장

---

## 참고 자료

- [SQLAlchemy 공식 문서](https://docs.sqlalchemy.org/)
- [PostgreSQL psycopg2](https://www.psycopg.org/)
- [MySQL PyMySQL](https://pymysql.readthedocs.io/)
- [MSSQL pyodbc](https://github.com/mkleehammer/pyodbc)

---

## 문의

문제가 발생하면 다음 정보를 포함하여 문의해주세요:
- 사용 중인 DB 종류 및 버전
- `.env` 설정 (비밀번호 제외)
- 에러 메시지
- `logs/batch_YYYYMMDD.log` 파일 내용

