"""
로깅 시스템 모듈
"""
import logging
from pathlib import Path
from datetime import datetime
from config import LOG_DIR


class BatchLogger:
    """배치 프로그램용 로거"""
    
    def __init__(self, name: str = "rag_batch"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # 로그 포맷 설정
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 파일 핸들러 (일별 로그 파일)
        log_file = LOG_DIR / f"batch_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        
        # 핸들러 추가
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def info(self, message: str):
        """정보 로그"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """경고 로그"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """에러 로그"""
        self.logger.error(message)
    
    def debug(self, message: str):
        """디버그 로그"""
        self.logger.debug(message)
    
    def log_sheet_start(self, sheet_name: str):
        """시트 처리 시작 로그"""
        self.info(f"{'='*60}")
        self.info(f"시트 처리 시작: {sheet_name}")
        self.info(f"{'='*60}")
    
    def log_sheet_end(self, sheet_name: str, file_count: int):
        """시트 처리 완료 로그"""
        self.info(f"시트 처리 완료: {sheet_name} (파일 수: {file_count})")
        self.info(f"{'='*60}\n")
    
    def log_file_process(self, filename: str, status: str, detail: str = ""):
        """파일 처리 로그"""
        msg = f"파일: {filename} - {status}"
        if detail:
            msg += f" ({detail})"
        self.info(msg)
    
    def log_metadata(self, filename: str, metadata: dict):
        """메타데이터 로그"""
        self.info(f"메타데이터 - {filename}:")
        for key, value in metadata.items():
            self.info(f"  {key}: {value}")


# 전역 로거 인스턴스
logger = BatchLogger()

