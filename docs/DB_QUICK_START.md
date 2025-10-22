# DB 통합 빠른 시작 가이드

5분 안에 데이터베이스 통합 기능을 시작하는 방법입니다.

## 🚀 빠른 설정 (3단계)

### 1단계: 패키지 설치

사용할 데이터베이스에 맞는 드라이버를 설치합니다:

```powershell
# PostgreSQL
pip install sqlalchemy psycopg2-binary

# MySQL
pip install sqlalchemy pymysql

# MSSQL
pip install sqlalchemy pyodbc

# SQLite (추가 설치 불필요)
pip install sqlalchemy
```

---

### 2단계: .env 파일 설정

`.env` 파일을 열고 다음 설정을 추가합니다:

#### PostgreSQL 예시
```env
DATA_SOURCE=db
DB_CONNECTION_STRING=postgresql://user:password@localhost:5432/mydb
DB_SQL_FILE_PATH=./data/query.sql
DB_FILE_PATH_COLUMN=file_path
```

#### MySQL 예시
```env
DATA_SOURCE=db
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=mydb
DB_USER=root
DB_PASSWORD=password
DB_SQL_FILE_PATH=./data/query.sql
DB_FILE_PATH_COLUMN=file_path
```

#### SQLite 예시 (테스트용)
```env
DATA_SOURCE=db
DB_CONNECTION_STRING=sqlite:///./data/test.db
DB_SQL_FILE_PATH=./data/query.sql
DB_FILE_PATH_COLUMN=file_path
```

---

### 3단계: SQL 쿼리 작성

`data/query.sql` 파일을 생성하고 쿼리를 작성합니다:

#### 방식 A: 파일 경로 조회
```sql
SELECT 
    id,
    title,
    file_path,
    category,
    created_at
FROM 
    documents
WHERE 
    status = 'active'
ORDER BY 
    created_at DESC;
```

#### 방식 B: 텍스트 내용 변환
```sql
SELECT 
    id,
    title AS title,
    content AS content,
    category
FROM 
    articles
WHERE 
    published = 1;
```

**방식 B를 사용하는 경우 `.env`에 추가:**
```env
DB_FILE_PATH_COLUMN=
DB_CONTENT_COLUMNS=title,content
```

---

### 4단계: 실행

```powershell
python run.py --once --source db
```

---

## 📋 3가지 사용 시나리오

### 시나리오 1: DB에만 파일 경로가 있을 때

**DB 테이블 구조:**
```
documents
- id
- title
- file_path  (예: "Z:\docs\manual.pdf")
- category
```

**설정:**
```env
DB_FILE_PATH_COLUMN=file_path
DB_CONTENT_COLUMNS=
```

**결과:** 
- `file_path`의 파일을 RAGFlow에 업로드
- `title`, `category`는 메타데이터로 저장

---

### 시나리오 2: DB에 텍스트 내용이 있을 때

**DB 테이블 구조:**
```
regulations
- id
- regulation_name
- regulation_content  (텍스트 내용)
- department
```

**설정:**
```env
DB_FILE_PATH_COLUMN=
DB_CONTENT_COLUMNS=regulation_name,regulation_content
```

**결과:**
- `regulation_name`과 `regulation_content`를 텍스트 파일로 변환
- 생성된 파일을 RAGFlow에 업로드

---

### 시나리오 3: Excel + DB 함께 사용

**설정:**
```env
DATA_SOURCE=both
EXCEL_FILE_PATH=./data/input.xlsx
DB_CONNECTION_STRING=postgresql://user:pass@localhost/db
DB_SQL_FILE_PATH=./data/query.sql
DB_FILE_PATH_COLUMN=file_path
```

**실행:**
```powershell
python run.py --once --source both
```

**결과:**
- Excel의 모든 시트 처리
- DB 쿼리 결과 처리
- 모두 RAGFlow에 업로드

---

## 🧪 SQLite로 테스트하기

SQLite를 사용하면 설치 없이 바로 테스트할 수 있습니다.

### 1. 테스트 DB 생성

```powershell
# PowerShell에서 실행
sqlite3 data/test.db
```

SQLite 프롬프트에서:
```sql
CREATE TABLE test_docs (
    id INTEGER PRIMARY KEY,
    title TEXT,
    file_path TEXT,
    category TEXT
);

INSERT INTO test_docs VALUES 
(1, '샘플 문서 1', 'C:\docs\sample1.pdf', '기술문서'),
(2, '샘플 문서 2', 'C:\docs\sample2.hwp', '업무매뉴얼');

.quit
```

### 2. .env 설정

```env
DATA_SOURCE=db
DB_CONNECTION_STRING=sqlite:///./data/test.db
DB_SQL_FILE_PATH=./data/query.sql
DB_FILE_PATH_COLUMN=file_path
```

### 3. SQL 쿼리 작성

`data/query.sql`:
```sql
SELECT * FROM test_docs;
```

### 4. 실행

```powershell
python run.py --once --source db
```

---

## 🔍 실행 결과 확인

실행 후 로그에서 다음 정보를 확인할 수 있습니다:

```
================================================================================
배치 프로세스 시작
데이터 소스: DB
================================================================================

[DB 데이터 처리]
DB 연결 시도 (연결 문자열 사용)
✓ DB 연결 성공
SQL 파일 실행: query.sql
쿼리 실행 완료: 10개 행 반환
검색된 컬럼 (4개): id, title, file_path, category
✓ 파일 경로 컬럼 발견: file_path

처리 완료: 10개 항목
--------------------------------------------------------------------------------
DB 처리 통계
  총 행 수: 10
  파일 경로: 10
  내용 변환: 0
  건너뜀: 0
--------------------------------------------------------------------------------
```

---

## 🆘 문제 해결

### 연결 실패

```
✗ DB 연결 실패: could not connect to server
```

**체크리스트:**
- [ ] DB 서버가 실행 중인가?
- [ ] 연결 정보 (호스트, 포트, 사용자명, 비밀번호)가 정확한가?
- [ ] 방화벽이 포트를 차단하지 않는가?

---

### 드라이버 오류

```
ModuleNotFoundError: No module named 'psycopg2'
```

**해결:**
```powershell
pip install psycopg2-binary
```

---

### 컬럼을 찾을 수 없음

```
파일 경로 또는 내용 컬럼 없음
```

**해결:**
1. SQL 쿼리 결과 확인
2. `.env`의 `DB_FILE_PATH_COLUMN` 설정 확인
3. 컬럼명이 정확히 일치하는지 확인

---

## 📚 더 알아보기

- 📖 [전체 DATABASE_INTEGRATION.md](./DATABASE_INTEGRATION.md) - 상세 가이드
- 📖 [EXAMPLES.md](./EXAMPLES.md) - 다양한 사용 예시
- 📖 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - 문제 해결

---

## ✅ 체크리스트

DB 통합 기능을 사용하기 전에 확인하세요:

- [ ] 데이터베이스 드라이버 설치 완료
- [ ] `.env` 파일에 DB 연결 정보 설정
- [ ] `data/query.sql` 파일 작성
- [ ] `DB_FILE_PATH_COLUMN` 또는 `DB_CONTENT_COLUMNS` 설정
- [ ] RAGFlow API 키 설정
- [ ] 테스트 실행 성공

모두 완료했다면 실제 DB로 실행해보세요! 🎉

