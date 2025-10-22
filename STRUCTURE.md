# 프로젝트 구조 설명

## 디렉토리 구조

```
rag_batch/
│
├── src/                             # 소스 코드 (핵심 로직)
│   ├── __init__.py                  # 패키지 초기화
│   ├── main.py                      # 메인 진입점 (CLI 파싱, 스케줄링)
│   ├── config.py                    # 설정 관리 (환경변수, 경로)
│   ├── logger.py                    # 로깅 시스템
│   ├── excel_processor.py           # 엑셀 파일 처리
│   ├── db_connector.py              # 🆕 데이터베이스 연결
│   ├── db_processor.py              # 🆕 DB 쿼리 결과 처리
│   ├── file_handler.py              # 파일 다운로드/변환
│   ├── ragflow_client.py            # RAGFlow API 클라이언트
│   └── batch_processor.py           # 배치 프로세스 조율
│
├── scripts/                         # 유틸리티 스크립트
│   ├── setup.py                     # 초기 설정 (디렉토리 생성, .env 설정)
│   ├── test_excel_read.py           # 엑셀 읽기 테스트
│   ├── copy_sample.py               # 샘플 파일 복사
│   ├── start.bat                    # Windows 시작 스크립트 (CMD)
│   └── start.ps1                    # Windows 시작 스크립트 (PowerShell)
│
├── docs/                            # 문서
│   ├── QUICK_START.md               # 빠른 시작 가이드
│   ├── EXAMPLES.md                  # 10가지 사용 예시
│   ├── TROUBLESHOOTING.md           # 21가지 문제 해결
│   ├── IMPLEMENTATION_NOTE.md       # 구현 상세 (메타데이터 등)
│   ├── CHANGELOG.md                 # 변경 이력
│   └── VERSION.txt                  # 버전 정보
│
├── data/                            # 데이터 디렉토리
│   ├── *.xlsx                       # 입력 엑셀 파일
│   ├── downloads/                   # 다운로드된 파일
│   └── temp/                        # 임시 파일
│
├── logs/                            # 로그 디렉토리
│   └── batch_YYYYMMDD.log           # 날짜별 로그 파일
│
├── run.py                           # 실행 진입점 (프로젝트 루트에서 실행)
├── requirements.txt                 # Python 의존성
├── env.example                      # 환경 설정 예시
├── .gitignore                       # Git 제외 목록
├── README.md                        # 프로젝트 문서 (메인)
└── STRUCTURE.md                     # 이 파일
```

## 모듈별 역할

### 핵심 모듈 (src/)

#### main.py
- **역할**: 프로그램의 진입점
- **기능**:
  - 명령행 인자 파싱 (--once, --excel, --schedule)
  - 스케줄링 설정 및 실행
  - BatchProcessor 호출
- **실행**: `python run.py`

#### config.py
- **역할**: 설정 관리
- **기능**:
  - 환경변수 로드 (.env)
  - 디렉토리 경로 설정
  - 파일 형식 정의
- **의존성**: python-dotenv

#### logger.py
- **역할**: 로깅 시스템
- **기능**:
  - 날짜별 로그 파일 생성
  - 콘솔 및 파일 출력
  - 특수 로그 메서드 (log_sheet_start, log_metadata 등)
- **출력**: `logs/batch_YYYYMMDD.log`

#### excel_processor.py
- **역할**: 엑셀 파일 처리
- **기능**:
  - 다중 시트 처리
  - 헤더 자동 감지
  - 하이퍼링크 추출
  - 숨김 행 제외
  - 메타데이터 추출
- **의존성**: openpyxl

#### db_connector.py (신규)
- **역할**: 데이터베이스 연결 및 쿼리 실행
- **기능**:
  - SQLAlchemy 기반 범용 DB 연결
  - PostgreSQL, MySQL, MSSQL, Oracle, SQLite 지원
  - SQL 파일 읽기 및 실행
  - 연결 문자열/개별 파라미터 지원
- **의존성**: sqlalchemy, psycopg2, pymysql, pyodbc

#### db_processor.py (신규)
- **역할**: DB 쿼리 결과를 RAGFlow 형식으로 변환
- **기능**:
  - SQL 파일 실행 및 결과 처리
  - 파일 경로 추출 (방식 A)
  - 텍스트 내용 파일 변환 (방식 B)
  - 메타데이터 추출 및 매핑
  - Excel 프로세서와 동일한 출력 형식
- **의존성**: db_connector

#### file_handler.py
- **역할**: 파일 다운로드 및 변환
- **기능**:
  - URL/로컬 파일 처리
  - 파일 형식 변환 (HWP→PDF, ZIP 압축 해제)
  - 임시 파일 관리
- **의존성**: requests, zipfile, shutil

#### ragflow_client.py
- **역할**: RAGFlow API 클라이언트
- **기능**:
  - 지식베이스 생성/조회
  - 파일 업로드
  - 메타데이터 설정 (✅ 완전 구현)
  - 일괄 파싱 시작
- **의존성**: ragflow-sdk

#### batch_processor.py
- **역할**: 전체 프로세스 조율
- **기능**:
  - Excel/DB → 파일 → RAGFlow 전체 플로우 관리
  - 데이터 소스 선택 (excel, db, both)
  - 시트/쿼리별 처리
  - 통계 수집 및 출력
- **의존성**: 위 모든 모듈

### 유틸리티 스크립트 (scripts/)

#### setup.py
- **역할**: 초기 설정 자동화
- **실행**: `python scripts/setup.py`
- **기능**:
  - 필요한 디렉토리 생성 (data, logs 등)
  - .env 파일 생성

#### test_excel_read.py
- **역할**: 엑셀 파일 테스트
- **실행**: `python scripts/test_excel_read.py`
- **기능**:
  - 엑셀 파일 읽기 테스트
  - 하이퍼링크 및 메타데이터 확인

#### copy_sample.py
- **역할**: 샘플 파일 복사
- **실행**: `python scripts/copy_sample.py`
- **기능**:
  - `../sample_excel/` → `data/` 복사

#### start.bat / start.ps1
- **역할**: Windows 시작 스크립트
- **실행**: `.\scripts\start.bat` 또는 `.\scripts\start.ps1`
- **기능**:
  - 프로젝트 루트로 이동
  - 가상환경 활성화
  - run.py 실행

### 실행 진입점

#### run.py
- **위치**: 프로젝트 루트
- **역할**: Python 경로 설정 및 main.py 실행
- **이유**: src/ 디렉토리를 sys.path에 추가하여 임포트 가능하게 함

## 실행 방법

### 1. 직접 실행
```powershell
python run.py --once
```

### 2. 스크립트 사용
```powershell
.\scripts\start.ps1 --once
```

### 3. 모듈로 실행 (개발 모드)
```powershell
python -m src.main --once
```

## 데이터 흐름

### Excel 모드
```
1. run.py
   ↓
2. src/main.py (인자 파싱, 스케줄링)
   ↓
3. src/batch_processor.py (전체 조율)
   ↓
4. src/excel_processor.py (엑셀 읽기)
   ↓
5. src/file_handler.py (파일 다운로드/변환)
   ↓
6. src/ragflow_client.py (RAGFlow 업로드)
   ↓
7. src/logger.py (로그 기록)
```

### DB 모드 (신규)
```
1. run.py
   ↓
2. src/main.py (--source db)
   ↓
3. src/batch_processor.py (전체 조율)
   ↓
4. src/db_connector.py (DB 연결)
   ↓
5. src/db_processor.py (쿼리 실행 및 결과 변환)
   ↓
6. src/file_handler.py (파일 처리)
   ↓
7. src/ragflow_client.py (RAGFlow 업로드)
   ↓
8. src/logger.py (로그 기록)
```

### 혼합 모드 (Both)
```
Excel 처리 + DB 처리 → 통합 업로드
```

## 설정 파일

### .env
```env
RAGFLOW_API_KEY=your_api_key_here
RAGFLOW_BASE_URL=http://localhost:9380
EXCEL_FILE_PATH=./data/input.xlsx
DOWNLOAD_DIR=./data/downloads
TEMP_DIR=./data/temp
LOG_DIR=./logs
BATCH_SCHEDULE=10:00
```

### requirements.txt
```
# 기본 패키지
openpyxl>=3.1.2
requests>=2.31.0
python-dotenv>=1.0.0
schedule>=1.2.0
colorlog>=6.7.0

# DB 연동 (선택)
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.9  # PostgreSQL
pymysql>=1.1.0          # MySQL
pyodbc>=5.0.0           # MSSQL
```

## 확장 방법

### 새로운 파일 형식 지원
`src/file_handler.py`의 `process_file()` 메서드 수정

### 새로운 데이터 소스 지원
- Excel: `src/excel_processor.py` 참고
- DB: `src/db_processor.py` 참고하여 새로운 프로세서 작성
- 반드시 동일한 출력 형식 유지: `{'hyperlink': ..., 'metadata': ..., 'row_number': ...}`

### 새로운 데이터베이스 지원
- `src/db_connector.py`의 `SUPPORTED_DATABASES`에 추가
- SQLAlchemy 연결 문자열 형식 확인

### 새로운 출력 대상 지원
`src/ragflow_client.py` 참고하여 새로운 클라이언트 작성

## 테스트

```powershell
# 엑셀 읽기 테스트
python scripts\test_excel_read.py

# 샘플 파일로 전체 테스트
python run.py --once --excel "data/20250515_KTX-DATA_EMU.xlsx"
```

## 배포

1. 필요한 파일만 복사
   - `src/`, `scripts/`, `docs/`, `data/`, `logs/`
   - `run.py`, `requirements.txt`, `env.example`, `.gitignore`, `README.md`

2. `.env` 파일 설정

3. 의존성 설치
   ```powershell
   pip install -r requirements.txt
   ```

4. 실행
   ```powershell
   python run.py --once
   ```

