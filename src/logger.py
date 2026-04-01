"""
로깅 시스템 모듈
"""
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from config import LOG_DIR, LOG_KEEP_DAYS


def cleanup_old_batch_logs() -> None:
    """보관일이 지난 batch_*.log 파일 정리 (장기 실행 프로세스에서도 주기적으로 호출 가능)"""
    if LOG_KEEP_DAYS <= 0:
        return

    now_ts = datetime.now().timestamp()
    retention_seconds = LOG_KEEP_DAYS * 24 * 60 * 60

    for log_file in LOG_DIR.glob("batch_*.log"):
        try:
            if not log_file.is_file():
                continue
            if (now_ts - log_file.stat().st_mtime) > retention_seconds:
                log_file.unlink(missing_ok=True)
        except Exception:
            pass


class DailyBatchFileHandler(logging.Handler):
    """날짜가 바뀌면 batch_YYYYMMDD.log로 전환 (서비스 장기 구동 시에도 일별 파일 분리)"""

    # logging.Handler는 3.2+ 에서 terminator 추가 — 구버전/환경 호환용 명시
    terminator = "\n"

    def __init__(self, log_dir: Path, encoding: str = "utf-8"):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.encoding = encoding
        self._stream = None
        self._current_day: Optional[str] = None

    def _ensure_stream(self) -> None:
        day = datetime.now().strftime("%Y%m%d")
        if day == self._current_day and self._stream is not None:
            return
        if self._current_day is not None and day != self._current_day:
            cleanup_old_batch_logs()
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        self._current_day = day
        path = self.log_dir / f"batch_{day}.log"
        self._stream = open(path, "a", encoding=self.encoding)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.acquire()
            try:
                self._ensure_stream()
                msg = self.format(record)
                self._stream.write(msg + self.terminator)
                self._stream.flush()
            finally:
                self.release()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        self.acquire()
        try:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        finally:
            self.release()
        super().close()


class BatchLogger:
    """배치 프로그램용 로거"""
    
    def __init__(self, name: str = "rag_batch"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        cleanup_old_batch_logs()

        # 로그 포맷 설정
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 파일 핸들러: 프로세스가 며칠 동안 떠 있어도 자정 기준으로 파일 전환
        file_handler = DailyBatchFileHandler(LOG_DIR, encoding="utf-8")
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

