"""
비동기 작업 상태 관리자 (In-Memory)
"""
import uuid
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List

from api.models import JobStatus


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
        job = self._storage.get(job_id)
        if job:
            job["status"] = JobStatus.COMPLETED
            job["completed_at"] = datetime.now().isoformat()
            job["stats"] = stats

    def fail_job(self, job_id: str, error_message: str):
        job = self._storage.get(job_id)
        if job:
            job["status"] = JobStatus.FAILED
            job["completed_at"] = datetime.now().isoformat()
            job["error_message"] = error_message

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
