"""
비동기 작업 상태 관리자 (In-Memory)

작업이 완료(completed) 또는 실패(failed)되면 즉시 메모리에서 자동 삭제됩니다.
결과 정보는 삭제 전에 로그로 기록됩니다.
"""
import uuid
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List

from api.models import JobStatus

logger = logging.getLogger(__name__)


class JobManager:
    """비동기 작업 상태를 메모리에서 관리"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._storage: Dict[str, Dict[str, Any]] = {}
            return cls._instance

    def create_job(self, job_type: str, params: Dict[str, Any]) -> str:
        """새 작업 생성 후 job_id 반환"""
        job_id = str(uuid.uuid4())
        self._storage[job_id] = {
            "job_id": job_id,
            "job_type": job_type,
            "status": JobStatus.QUEUED,
            "params": params,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "error_message": None,
            "stats": None,
        }
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._storage.get(job_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        jobs = list(self._storage.values())
        jobs.sort(key=lambda x: x["created_at"], reverse=True)
        return jobs

    def start_job(self, job_id: str):
        job = self._storage.get(job_id)
        if job:
            job["status"] = JobStatus.RUNNING
            job["started_at"] = datetime.now().isoformat()

    def complete_job(self, job_id: str, stats: Optional[Dict[str, Any]] = None):
        """작업 완료 처리 후 즉시 메모리에서 삭제"""
        job = self._storage.get(job_id)
        if job:
            completed_at = datetime.now().isoformat()
            logger.info(
                f"[Job {job_id}] 완료 → 자동 삭제 | "
                f"type={job['job_type']}, "
                f"created={job['created_at']}, "
                f"completed={completed_at}, "
                f"stats={stats}"
            )
            del self._storage[job_id]

    def fail_job(self, job_id: str, error_message: str):
        """작업 실패 처리 후 즉시 메모리에서 삭제"""
        job = self._storage.get(job_id)
        if job:
            completed_at = datetime.now().isoformat()
            logger.warning(
                f"[Job {job_id}] 실패 → 자동 삭제 | "
                f"type={job['job_type']}, "
                f"created={job['created_at']}, "
                f"failed={completed_at}, "
                f"error={error_message}"
            )
            del self._storage[job_id]

    def delete_job(self, job_id: str) -> bool:
        if job_id in self._storage:
            job = self._storage[job_id]
            if job["status"] in (JobStatus.QUEUED, JobStatus.RUNNING):
                return False
            del self._storage[job_id]
            return True
        return False

    def is_deletable(self, job_id: str) -> bool:
        job = self._storage.get(job_id)
        if not job:
            return False
        return job["status"] not in (JobStatus.QUEUED, JobStatus.RUNNING)
