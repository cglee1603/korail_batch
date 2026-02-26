"""
Filesystem 처리 API 라우터
- POST /filesystem/batch : Filesystem 배치 처리 (비동기)
"""
import traceback
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks

from api.models import (
    FilesystemBatchRequest,
    JobResponse,
    JobStatus,
)
from api.job_manager import JobManager
from logger import logger

router = APIRouter(prefix="/filesystem", tags=["Filesystem"])
job_manager = JobManager()


def _run_filesystem_batch(job_id: str, filesystem_path: str):
    """백그라운드 Filesystem 배치 작업"""
    from batch_processor import BatchProcessor

    job_manager.start_job(job_id)

    try:
        processor = BatchProcessor(
            data_source="filesystem",
            filesystem_path=filesystem_path,
        )
        processor.process()

        stats = {
            "filesystem_path": filesystem_path,
            "processor_stats": getattr(processor, "stats", {}),
        }
        job_manager.complete_job(job_id, stats)
        logger.info(f"[API Job {job_id}] Filesystem 배치 완료")
    except Exception as e:
        job_manager.fail_job(job_id, str(e))
        logger.error(f"[API Job {job_id}] Filesystem 배치 실패: {e}")
        logger.error(traceback.format_exc())


@router.post("/batch", response_model=JobResponse, summary="Filesystem 배치 처리 (비동기)")
async def filesystem_batch(request: FilesystemBatchRequest, background_tasks: BackgroundTasks):
    """
    지정된 디렉토리를 스캔하여 RAGFlow에 업로드하는 배치 작업을 비동기로 실행합니다.

    - **filesystem_path**: 스캔할 루트 디렉토리 경로

    반환된 `job_id`로 `/jobs/{job_id}`에서 진행 상황을 조회할 수 있습니다.
    """
    p = Path(request.filesystem_path)
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"경로를 찾을 수 없습니다: {request.filesystem_path}")
    if not p.is_dir():
        raise HTTPException(status_code=400, detail=f"디렉토리가 아닙니다: {request.filesystem_path}")

    job_id = job_manager.create_job(
        job_type="filesystem_batch",
        params=request.model_dump(),
    )
    background_tasks.add_task(_run_filesystem_batch, job_id, request.filesystem_path)

    logger.info(f"[API] Filesystem 배치 작업 생성: {job_id} (경로: {request.filesystem_path})")
    return JobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message="Filesystem 배치 작업이 큐에 추가되었습니다.",
        created_at=job_manager.get_job(job_id)["created_at"],
    )
