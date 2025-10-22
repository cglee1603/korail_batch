# DB 통합 기능 요약

## ✅ 구현 완료 항목

### 1. 핵심 모듈
- ✅ `src/db_connector.py` - SQLAlchemy 기반 범용 DB 연결
- ✅ `src/db_processor.py` - SQL 결과를 RAGFlow 형식으로 변환
- ✅ `src/batch_processor.py` - DB 처리 통합
- ✅ `src/main.py` - CLI 옵션 추가 (`--source`)
- ✅ `src/config.py` - DB 설정 추가

### 2. 지원 데이터베이스
- ✅ PostgreSQL (psycopg2)
- ✅ MySQL/MariaDB (pymysql)
- ✅ SQL Server (pyodbc)
- ✅ Oracle (cx_oracle)
- ✅ SQLite (기본 내장)

### 3. 데이터 처리 방식
- ✅ **방식 A**: DB에 파일 경로 저장 → 파일 업로드
- ✅ **방식 B**: DB 내용을 텍스트로 변환 → 텍스트 업로드
- ✅ **방식 C**: 혼합 (A + B)

### 4. 설정 및 문서
- ✅ `requirements.txt` - DB 드라이버 추가
- ✅ `env.example` - DB 설정 예시 추가
- ✅ `data/query.sql` - SQL 예시 파일
- ✅ `docs/DATABASE_INTEGRATION.md` - 상세 가이드
- ✅ `docs/DB_QUICK_START.md` - 빠른 시작
- ✅ `README.md` - 메인 문서 업데이트
- ✅ `STRUCTURE.md` - 구조 문서 업데이트

---

## 🚀 사용 방법

### 기본 사용
```powershell
# 1. DB 드라이버 설치
pip install sqlalchemy psycopg2-binary

# 2. .env 설정
DATA_SOURCE=db
DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/mydb
DB_SQL_FILE_PATH=./data/query.sql
DB_FILE_PATH_COLUMN=file_path

# 3. SQL 쿼리 작성 (data/query.sql)
SELECT id, title, file_path, category FROM documents;

# 4. 실행
python run.py --once --source db
```

### Excel + DB 혼합
```powershell
python run.py --once --source both
```

---

## 📊 데이터 흐름

```
┌─────────────┐         ┌─────────────┐
│ Excel 파일  │         │  Database   │
└──────┬──────┘         └──────┬──────┘
       │                       │
       │                       │ SQL 쿼리
       ↓                       ↓
┌─────────────────────────────────────┐
│    Batch Processor (통합)           │
├─────────────────────────────────────┤
│  • Excel Processor                  │
│  • DB Connector → DB Processor      │
└──────────────┬──────────────────────┘
               ↓
       ┌───────────────┐
       │ File Handler  │  파일 처리
       └───────┬───────┘
               ↓
       ┌───────────────┐
       │ RAGFlow Client│  업로드
       └───────────────┘
```

---

## 🎯 주요 특징

### 유연한 연결 방식
- 연결 문자열 (간편)
- 개별 파라미터 (상세 설정)

### SQL 파일 기반
- 쿼리를 외부 파일로 관리
- 재시작 없이 쿼리 수정 가능

### 3가지 데이터 처리
- 파일 경로 → 파일 업로드
- 텍스트 내용 → 파일 생성 후 업로드
- 혼합 처리

### 자동 메타데이터
- 모든 컬럼을 메타데이터로 자동 변환
- 선택적 컬럼 필터링 지원

---

## 📁 주요 파일

### 소스 코드
- `src/db_connector.py` (323줄) - DB 연결 및 쿼리 실행
- `src/db_processor.py` (208줄) - 결과 처리 및 변환
- `src/batch_processor.py` (수정) - DB 통합
- `src/config.py` (수정) - DB 설정

### 문서
- `docs/DATABASE_INTEGRATION.md` - 상세 가이드 (400줄+)
- `docs/DB_QUICK_START.md` - 빠른 시작 (300줄+)
- `data/query.sql` - SQL 예시

### 설정
- `env.example` - DB 설정 예시
- `requirements.txt` - DB 드라이버

---

## 🔍 예시 시나리오

### 시나리오 1: 문서 관리 시스템
```sql
-- DB에 파일 경로가 있는 경우
SELECT 
    doc_id,
    title,
    file_path,
    category,
    created_at
FROM documents
WHERE status = 'active';
```

**설정:**
```env
DB_FILE_PATH_COLUMN=file_path
```

---

### 시나리오 2: 규정/정책 시스템
```sql
-- DB에 텍스트 내용이 있는 경우
SELECT 
    regulation_id,
    regulation_name AS title,
    regulation_content AS content,
    department
FROM regulations
WHERE effective = 1;
```

**설정:**
```env
DB_CONTENT_COLUMNS=title,content
```

---

### 시나리오 3: 하이브리드
```sql
-- 파일 경로와 요약 정보 모두
SELECT 
    manual_id,
    title,
    file_path,
    summary,
    category
FROM manuals;
```

**설정:**
```env
DB_FILE_PATH_COLUMN=file_path
DB_CONTENT_COLUMNS=summary
```

---

## ⚙️ 설정 옵션

### 필수 설정
```env
DATA_SOURCE=db              # "excel", "db", "both"
DB_CONNECTION_STRING=...    # 또는 개별 파라미터
DB_SQL_FILE_PATH=./data/query.sql
```

### 데이터 처리 방식
```env
# 방식 A: 파일 경로 사용
DB_FILE_PATH_COLUMN=file_path

# 방식 B: 내용 변환
DB_CONTENT_COLUMNS=title,content

# 메타데이터 (선택)
DB_METADATA_COLUMNS=category,author,date
```

---

## 🧪 테스트

### SQLite로 빠른 테스트
```powershell
# 1. 테스트 DB 생성
sqlite3 data/test.db
CREATE TABLE docs (id INT, title TEXT, file_path TEXT);
INSERT INTO docs VALUES (1, 'Test', 'C:\test.pdf');

# 2. 설정
DATA_SOURCE=db
DB_CONNECTION_STRING=sqlite:///./data/test.db

# 3. 실행
python run.py --once --source db
```

---

## 📚 참고 문서

- [DB 빠른 시작](./DB_QUICK_START.md) - 5분 안에 시작하기
- [DB 통합 가이드](./DATABASE_INTEGRATION.md) - 상세 설명
- [EXAMPLES.md](./EXAMPLES.md) - 사용 예시
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - 문제 해결

---

## 🎉 완료!

이제 RAGFlow Plus 배치 프로그램에서 데이터베이스를 사용할 수 있습니다!

