"""
배치 프로그램 설정 관리 모듈
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 프로젝트 루트 디렉토리
ROOT_DIR = Path(__file__).parent

# RAGFlow 설정
RAGFLOW_API_KEY = os.getenv("RAGFLOW_API_KEY", "")
RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")

# 지식베이스 권한 설정
DATASET_PERMISSION = os.getenv("DATASET_PERMISSION", "me")  # "me" 또는 "team"
DATASET_LANGUAGE = os.getenv("DATASET_LANGUAGE", "Korean")

# 임베딩 모델 설정
# None으로 설정하여 tenant의 기본 임베딩 모델(tenant.embd_id) 자동 사용
# .env의 EMBEDDING_MODEL 설정은 무시됨 (서버측 tenant_llm 테이블 조회 문제 회피)
EMBEDDING_MODEL = None  # 항상 None 사용 - 서버가 tenant.embd_id 자동 적용

# ==================== Parser 설정 (GUI와 동일하게) ====================

# 청크 분할 방법
# - "naive": 일반 텍스트 분할 (기본값)
# - "qa": Q&A 형식
# - "manual": 수동 분할
# - "paper": 논문 형식
# - "book": 책 형식
# - "laws": 법률 문서
# - "presentation": 프레젠테이션
# - "knowledge_graph": 지식 그래프
CHUNK_METHOD = os.getenv("CHUNK_METHOD", "naive")

# Parser 설정 (GUI 기본값과 동일)
PARSER_CONFIG = {
    # 청크당 토큰 수 (기본: 128)
    "chunk_token_num": int(os.getenv("CHUNK_TOKEN_NUM", "128")),
    
    # 구분자 (기본: 줄바꿈, 문장 종결 기호)
    "delimiter": os.getenv("DELIMITER", "\\n!?;。；！？"),
    
    # 페이지 범위 (기본: 전체 페이지)
    "pages": [[1, 1000000]],
    
    # 레이아웃 인식 방법 (기본: MinerU)
    # - "DeepDOC": DeepDOC 모델 (구버전)
    # - "MinerU": MinerU 모델 (권장)
    "layout_recognize": os.getenv("LAYOUT_RECOGNIZE", "MinerU"),
    
    # Excel HTML 변환 사용 여부
    "html4excel": os.getenv("HTML4EXCEL", "false").lower() == "true",
    
    # Raptor 설정 (계층적 요약 - Recursive Abstractive Processing for Tree-Organized Retrieval)
    # ⚠️  Raptor는 처리 시간이 매우 길어질 수 있으므로 필요한 경우에만 활성화하세요
    "raptor": {
        "use_raptor": os.getenv("USE_RAPTOR", "false").lower() == "true",
        # 아래 설정들은 use_raptor=true일 때만 사용됨
        "prompt": os.getenv("RAPTOR_PROMPT", 
            "Please summarize the following paragraphs. Be careful with the numbers, do not make things up. Paragraphs as following:\n{cluster_content}\nThe above is the content you need to summarize."),
        "max_token": int(os.getenv("RAPTOR_MAX_TOKEN", "256")),
        "threshold": float(os.getenv("RAPTOR_THRESHOLD", "0.1")),
        "random_seed": int(os.getenv("RAPTOR_RANDOM_SEED", "0")),
        "max_cluster": int(os.getenv("RAPTOR_MAX_CLUSTER", "64"))
    }
}

# 환경변수로 전체 parser_config를 JSON으로 전달받을 수도 있음
# 예: PARSER_CONFIG='{"chunk_token_num": 256, "delimiter": "\\n"}'
import json
if os.getenv("PARSER_CONFIG"):
    try:
        custom_config = json.loads(os.getenv("PARSER_CONFIG"))
        PARSER_CONFIG.update(custom_config)
    except json.JSONDecodeError as e:
        print(f"[WARNING] PARSER_CONFIG 환경변수 파싱 실패: {e}")

# 파일 경로 설정
EXCEL_FILE_PATH = os.getenv("EXCEL_FILE_PATH", "./data/input.xlsx")
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./data/downloads"))
TEMP_DIR = Path(os.getenv("TEMP_DIR", "./data/temp"))
LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))

# 스케줄 설정
BATCH_SCHEDULE = os.getenv("BATCH_SCHEDULE", "10:00")

# 디렉토리 생성
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 파일 변환 설정
SUPPORTED_EXTENSIONS = {
    'txt': 'text',
    'pdf': 'pdf',
    'hwp': 'hwp',
    'zip': 'archive'
}

# 변환이 필요한 파일 형식
CONVERT_TO_PDF = ['hwp']
EXTRACT_ARCHIVE = ['zip']

# ==================== 데이터베이스 설정 ====================

# DB 연결 문자열
DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING", "")
# 예시:
# - PostgreSQL: postgresql://user:pass@localhost:5432/dbname
# - MySQL: mysql://user:pass@localhost:3306/dbname
# - MSSQL: mssql://user:pass@localhost:1433/dbname
# - Oracle: oracle://user:pass@localhost:1521/dbname

# SQL 파일 경로
DB_SQL_FILE_PATH = os.getenv("DB_SQL_FILE_PATH", "./data/query.sql")

# DB 내용을 텍스트 파일로 변환
DB_CONTENT_COLUMNS = os.getenv("DB_CONTENT_COLUMNS", "")  # 콤마로 구분 (예: "title,content,description")
if DB_CONTENT_COLUMNS:
    DB_CONTENT_COLUMNS = [col.strip() for col in DB_CONTENT_COLUMNS.split(',')]
else:
    DB_CONTENT_COLUMNS = []

# 메타데이터로 사용할 컬럼 (비어있으면 모든 컬럼 사용)
DB_METADATA_COLUMNS = os.getenv("DB_METADATA_COLUMNS", "")  # 콤마로 구분 (예: "category,author,created_at")
if DB_METADATA_COLUMNS:
    DB_METADATA_COLUMNS = [col.strip() for col in DB_METADATA_COLUMNS.split(',')]
else:
    DB_METADATA_COLUMNS = []

# 데이터 소스 선택
DATA_SOURCE = os.getenv("DATA_SOURCE", "excel")  # "excel", "db", "both"

# 내부 사용 (개별 파라미터 방식은 제거됨 - 연결 문자열만 사용)
DB_TYPE = ""
DB_HOST = ""
DB_PORT = ""
DB_NAME = ""
DB_USER = ""
DB_PASSWORD = ""
DB_DRIVER = ""
DB_FILE_PATH_COLUMN = ""  # 방식 B만 사용하므로 제거

