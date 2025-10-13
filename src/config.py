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

