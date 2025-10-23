# RAGFlow Plus 배치 프로그램

Excel 파일과 데이터베이스에서 자동으로 데이터를 추출하여 RAGFlow Plus 지식베이스에 문서를 업로드하고 인덱싱하는 배치 프로그램입니다.

## 🆕 주요 업데이트

- **✨ 데이터베이스 통합** - PostgreSQL, MySQL, MSSQL, Oracle, SQLite 지원
- **🔄 SQL 파일 기반 쿼리** - 동적 쿼리 수정 가능
- **📊 Excel + DB 혼합 사용** - 두 데이터 소스 동시 처리

## 📋 프로젝트 구조

```
rag_batch/
├── src/                         # 소스 코드
│   ├── __init__.py
│   ├── main.py                  # 메인 스크립트
│   ├── config.py                # 설정 관리
│   ├── logger.py                # 로깅 시스템
│   ├── excel_processor.py       # 엑셀 처리
│   ├── file_handler.py          # 파일 다운로드/변환
│   ├── ragflow_client.py        # RAGFlow API 연동
│   └── batch_processor.py       # 배치 프로세스 조율
│
├── scripts/                     # 유틸리티 스크립트
│   ├── setup.py                 # 초기 설정
│   ├── test_excel_read.py       # 엑셀 테스트
│   ├── copy_sample.py           # 샘플 복사
│   ├── start.bat                # Windows 시작 (CMD)
│   └── start.ps1                # Windows 시작 (PowerShell)
│
├── docs/                        # 문서
│   ├── QUICK_START.md           # 빠른 시작 가이드
│   ├── DATABASE_INTEGRATION.md  # 🆕 DB 통합 가이드
│   ├── DB_QUICK_START.md        # 🆕 DB 빠른 시작
│   ├── EXAMPLES.md              # 사용 예시 (10가지)
│   ├── TROUBLESHOOTING.md       # 문제 해결 (21가지)
│   ├── IMPLEMENTATION_NOTE.md   # 구현 노트
│   ├── CHANGELOG.md             # 변경 이력
│   └── VERSION.txt              # 버전 정보
│
├── data/                        # 데이터
│   ├── downloads/               # 다운로드 파일
│   └── temp/                    # 임시 파일
│
├── logs/                        # 로그 파일
│
├── run.py                       # 실행 진입점
├── requirements.txt             # Python 의존성
├── env.example                  # 환경 설정 예시
├── .gitignore                   # Git 제외 목록
└── README.md                    # 이 파일
```

## 🚀 빠른 시작

```powershell
# 1. 초기 설정
cd rag_batch
python scripts\setup.py

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경 설정 (.env 파일 편집)
# RAGFLOW_API_KEY 및 기타 설정 입력

# 4. 샘플 파일 복사 (테스트용)
python scripts\copy_sample.py

# 5. 배치 실행
python run.py --once
```

## 📚 상세 문서

### Excel 사용자
- **[빠른 시작](docs/QUICK_START.md)** - 처음 시작하는 분들을 위한 가이드
- **[전체 프로세스](PROCESS.md)** - 팀 공유, 문서 업로드/파싱 등 전체 프로세스 설명
- **[사용 예시](docs/EXAMPLES.md)** - 10가지 실제 사용 예시

### 데이터베이스 통합 (신규)
- **[DB 빠른 시작](docs/DB_QUICK_START.md)** - 🆕 5분 안에 DB 통합하기
- **[DB 통합 가이드](docs/DATABASE_INTEGRATION.md)** - 🆕 상세 DB 연동 문서

### 폐쇄망 설치
- **[플랫폼별 가이드](OFFLINE_PLATFORM_GUIDE.md)** - 🆕 Windows/Linux 환경별 설치 (권장)
- **[빠른 설치 가이드](OFFLINE_INSTALL_QUICK.md)** - Python 3.11 폐쇄망 설치 (간단)
- **[상세 설치 가이드](docs/OFFLINE_INSTALL.md)** - 오프라인 설치 전체 과정

### 일반
- **[문제 해결](docs/TROUBLESHOOTING.md)** - 21가지 문제 해결 방법
- **[구현 노트](docs/IMPLEMENTATION_NOTE.md)** - 메타데이터 등 상세 구현 정보
- **[변경 이력](docs/CHANGELOG.md)** - 버전별 변경 사항

## ✨ 주요 기능

### 데이터 소스
- ✅ **Excel 파일** - 하이퍼링크 기반 문서 수집
- ✅ **데이터베이스** - SQL 쿼리 기반 데이터 수집 🆕
  - PostgreSQL, MySQL, MSSQL, Oracle, SQLite 지원
  - SQL 파일로 쿼리 관리
  - 파일 경로 또는 텍스트 내용 처리
- ✅ **혼합 모드** - Excel + DB 동시 사용

### 엑셀 파일 처리
- ✅ 다중 시트 자동 처리
- ✅ 헤더 행 자동 감지
- ✅ 하이퍼링크 자동 추출 (파일 경로, URL)
- ✅ 숨김 행 자동 제외
- ✅ 메타데이터 자동 추출

### 파일 처리
- ✅ 로컬 파일 및 URL 지원
- ✅ 파일 형식별 자동 변환
  - TXT, PDF: 그대로 업로드
  - **HWP: PDF 변환 후 업로드** (LibreOffice 사용)
  - ZIP: 압축 해제 후 개별 파일 처리

### RAGFlow 연동
- ✅ 시트별 지식베이스 자동 생성
- ✅ **팀 단위 지식베이스 공유** (permission 설정)
- ✅ 파일 자동 업로드
- ✅ 메타데이터 자동 추가 (완전 구현)
- ✅ **일괄 파싱 자동 실행** (업로드 → 파싱 → 벡터화)

### 스케줄링
- ✅ 특정 시간 실행 (예: 매일 10:00)
- ✅ 주기적 실행 (예: 300초마다)
- ✅ 다중 시간대 실행 (예: 08:00, 12:00, 16:00)

## 💡 사용 방법

### Excel 사용
```powershell
# 기본 실행 (Excel 파일 처리)
python run.py --once

# 특정 파일 지정
python run.py --once --excel "C:\path\to\file.xlsx"

# 스케줄 실행
python run.py --schedule "10:00"
```

### 데이터베이스 사용 🆕
```powershell
# DB만 사용
python run.py --once --source db

# Excel + DB 혼합
python run.py --once --source both
```

**DB 설정 예시 (.env 파일):**
```env
DATA_SOURCE=db
DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/mydb
DB_SQL_FILE_PATH=./data/query.sql
DB_FILE_PATH_COLUMN=file_path
```

**더 자세한 내용:** [DB 빠른 시작](docs/DB_QUICK_START.md)

### Windows 시작 스크립트
```powershell
# PowerShell
.\scripts\start.ps1 --once

# CMD
scripts\start.bat --once
```

## ✅ 메타데이터 기능

엑셀의 각 행 데이터가 RAGFlow 문서의 메타데이터로 자동 추가됩니다:

```json
{
  "구분": "설계",
  "자성보고": "K20",
  "관리번호": "002",
  "제목": "KTX-이름 경정비",
  "원본_파일": "document.pdf",
  "파일_형식": "pdf",
  "엑셀_행번호": "5",
  "하이퍼링크": "file:///path/to/document.pdf"
}
```

**확인 방법:**
- RAGFlow 웹 UI → 지식베이스 → 문서 선택 → "메타데이터" 탭
- 검색 필터링에 활용 가능

## ⚙️ 시스템 요구사항

### HWP 파일 변환용 (필수)

**Linux:**
```bash
# LibreOffice 설치
sudo apt-get install -y libreoffice libreoffice-writer

# 한글 폰트 설치
sudo apt-get install -y fonts-nanum fonts-nanum-coding
```

**Windows:**
- LibreOffice 다운로드: https://www.libreoffice.org/download/
- 설치 후 PATH에 추가 (선택사항)

**확인:**
```bash
soffice --version
```

상세한 HWP 변환 설정은 [HWP_CONVERSION.md](docs/HWP_CONVERSION.md)를 참조하세요.

## 🔧 설정

### 환경 변수 (.env)

```env
# RAGFlow 설정
RAGFLOW_API_KEY=your_api_key_here
RAGFLOW_BASE_URL=http://localhost:9380

# 지식베이스 권한 설정
# "me" - 나만 사용 (기본값)
# "team" - 팀 전체 공유
DATASET_PERMISSION=me
DATASET_LANGUAGE=Korean

# 배치 설정
EXCEL_FILE_PATH=./data/input.xlsx
DOWNLOAD_DIR=./data/downloads
TEMP_DIR=./data/temp
LOG_DIR=./logs

# 스케줄 설정
BATCH_SCHEDULE=10:00
```

### 팀 단위 지식베이스 생성

`.env` 파일에서 `DATASET_PERMISSION=team`으로 설정하면:
- 생성된 지식베이스를 **팀 전체가 공유**
- RAGFlow 웹 UI에서 모든 팀원이 접근 가능
- 검색 및 대화 기능을 팀원들과 함께 사용

## 📝 로그

로그는 `logs/` 디렉토리에 날짜별로 저장됩니다:

```
logs/
├── batch_20250515.log
├── batch_20250516.log
└── ...
```

## 🐛 문제 해결

일반적인 문제와 해결 방법은 [문제 해결 가이드](docs/TROUBLESHOOTING.md)를 참조하세요.

### 빠른 해결책

**API 키 오류**
```
ValueError: RAGFlow API 키가 설정되지 않았습니다.
```
→ `.env` 파일의 `RAGFLOW_API_KEY` 확인

**연결 실패**
```
ConnectionRefusedError
```
→ RAGFlow 서버 실행 상태 확인 (`python .\start_server.py`)

**엑셀 파일 없음**
```
엑셀 파일을 찾을 수 없습니다
```
→ `--excel` 옵션으로 파일 경로 지정

## 🤝 기여

버그 리포트, 기능 요청, 개선 제안은 언제든 환영합니다.

## 📄 라이선스

MIT License

---

**개발 정보**
- 버전: 1.0.0
- 작성일: 2025-05-15
- Python 3.8 이상 필요
