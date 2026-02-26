"""
파싱 제어 API 라우터
- POST /parsing/{name}/check-and-parse : 미파싱 문서 파싱
- POST /parsing/{name}/cancel          : 파싱 취소
- POST /parsing/{name}/reparse-all     : 전체 재파싱
- POST /parsing/{name}/throttle        : 동시성 제한 파싱 (비동기)
"""
import traceback
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks

from api.models import (
    ReparseAllRequest,
    ThrottleParseRequest,
    ParseResponse,
    JobResponse,
    JobStatus,
)
from api.job_manager import JobManager
from logger import logger

router = APIRouter(prefix="/parsing", tags=["Parsing"])
job_manager = JobManager()


@router.post(
    "/{dataset_name}/check-and-parse",
    response_model=ParseResponse,
    summary="미파싱 문서 파싱",
)
async def check_and_parse(dataset_name: str):
    """
    문서 상태를 확인하고 Failed가 아닌 미파싱 문서를 파싱합니다.

    CLI: `python run.py --check-and-parse "이름"`
    """
    from batch_processor import BatchProcessor

    try:
        processor = BatchProcessor()
        processor.parse_non_failed_documents_by_dataset_name(dataset_name)
        return ParseResponse(
            dataset_name=dataset_name,
            message="미파싱 문서 파싱이 완료되었습니다.",
        )
    except Exception as e:
        logger.error(f"[API] check-and-parse 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"파싱 실패: {str(e)}")


@router.post(
    "/{dataset_name}/cancel",
    response_model=ParseResponse,
    summary="파싱 취소",
)
async def cancel_parsing(dataset_name: str):
    """
    RUNNING 상태인 문서의 파싱을 취소합니다.

    CLI: `python run.py --cancel-parsing "이름"`
    """
    from batch_processor import BatchProcessor

    try:
        processor = BatchProcessor()
        processor.cancel_parsing_documents_by_dataset_name(dataset_name, confirm=True)
        return ParseResponse(
            dataset_name=dataset_name,
            message="파싱 취소가 완료되었습니다.",
        )
    except Exception as e:
        logger.error(f"[API] cancel-parsing 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"파싱 취소 실패: {str(e)}")


@router.post(
    "/{dataset_name}/reparse-all",
    response_model=ParseResponse,
    summary="전체 재파싱",
)
async def reparse_all(dataset_name: str, request: ReparseAllRequest):
    """
    지식베이스의 모든 문서를 재파싱(서버가 기존 청크/작업 정리 후 재큐잉)합니다.

    - **confirm**: True일 때만 실제 재파싱 수행
    - **cancel_running**: RUNNING 문서 포함 허용
    - **include_running**: RUNNING 문서도 대상에 포함
    - **exclude_failed**: FAIL 문서 제외

    CLI: `python run.py --reparse-all "이름" [--confirm] [--include-running] [--exclude-failed]`
    """
    from batch_processor import BatchProcessor

    try:
        processor = BatchProcessor()
        processor.reparse_all_documents_by_dataset_name(
            dataset_name=dataset_name,
            confirm=request.confirm,
            cancel_running=request.cancel_running,
            include_running=request.include_running,
            include_failed=not request.exclude_failed,
        )

        if request.confirm:
            message = "전체 재파싱이 시작되었습니다."
        else:
            message = "재파싱 대상 확인 완료. 실제 실행하려면 confirm=true로 요청하세요."

        return ParseResponse(
            dataset_name=dataset_name,
            message=message,
        )
    except Exception as e:
        logger.error(f"[API] reparse-all 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"재파싱 실패: {str(e)}")


def _run_throttle_parse(
    job_id: str,
    dataset_name: str,
    concurrency: Optional[int],
    check_interval: int,
    include_done: bool,
    include_failed: bool,
    max_hours: float,
):
    """백그라운드 동시성 제한 파싱 작업"""
    from batch_processor import BatchProcessor

    job_manager.start_job(job_id)

    try:
        processor = BatchProcessor()
        processor.throttle_parse_by_dataset_name(
            dataset_name=dataset_name,
            confirm=True,
            concurrency_limit=concurrency,
            include_done=include_done,
            include_failed=include_failed,
            check_interval=check_interval,
            max_hours=max_hours,
        )

        job_manager.complete_job(job_id, {"dataset_name": dataset_name})
        logger.info(f"[API Job {job_id}] throttle-parse 완료: {dataset_name}")
    except Exception as e:
        job_manager.fail_job(job_id, str(e))
        logger.error(f"[API Job {job_id}] throttle-parse 실패: {e}")
        logger.error(traceback.format_exc())


@router.post(
    "/{dataset_name}/throttle",
    response_model=JobResponse,
    summary="동시성 제한 파싱 (비동기)",
)
async def throttle_parse(
    dataset_name: str,
    request: ThrottleParseRequest,
    background_tasks: BackgroundTasks,
):
    """
    동시 파싱 수를 제한하면서 문서를 파싱합니다.
    장시간 작업이므로 비동기로 실행됩니다.

    - **confirm**: True일 때만 실제 파싱 수행
    - **concurrency**: 동시 파싱 수 (미지정 시 현재 RUNNING 수 사용)
    - **check_interval**: 상태 확인 간격 (초, 기본: 10)
    - **include_done**: DONE 문서도 재파싱 대상에 포함
    - **include_failed**: FAIL 문서도 재파싱 대상에 포함
    - **max_hours**: 최대 동작 시간 (기본: 2시간)

    CLI: `python run.py --throttle-parse "이름" --concurrency 5 --confirm`
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm=true 로 요청해야 실제 파싱이 수행됩니다.",
        )

    job_id = job_manager.create_job(
        job_type="throttle_parse",
        params={"dataset_name": dataset_name, **request.model_dump()},
    )

    background_tasks.add_task(
        _run_throttle_parse,
        job_id,
        dataset_name,
        request.concurrency,
        request.check_interval,
        request.include_done,
        request.include_failed,
        request.max_hours,
    )

    logger.info(f"[API] throttle-parse 작업 생성: {job_id} (대상: {dataset_name})")
    return JobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message=f"동시성 제한 파싱 작업이 큐에 추가되었습니다. (대상: {dataset_name})",
        created_at=job_manager.get_job(job_id)["created_at"],
    )
