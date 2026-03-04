"""
DB 마이그레이션 API 라우터 (MySQL → PostgreSQL)

- POST /migration/run       : 마이그레이션 즉시 실행 (비동기)
- POST /migration/run-sync  : 마이그레이션 동기 실행
- GET  /migration/tables     : 대상 테이블 정보 조회
- POST /migration/cleanup    : 대상 테이블 데이터 전량 삭제
- GET  /migration/schedule   : 일배치 스케줄 상태 조회
- POST /migration/schedule/start : 일배치 스케줄 시작
- POST /migration/schedule/stop  : 일배치 스케줄 중지
"""
import traceback
import threading
from datetime import datetime
from typing import Optional

import schedule as schedule_lib

from fastapi import APIRouter, HTTPException, BackgroundTasks

from api.models import (
    MigrationRequest,
    MigrationResponse,
    MigrationScheduleStatus,
    MigrationInfoResponse,
    MigrationCleanupResponse,
    JobResponse,
    JobStatus,
)
from api.job_manager import JobManager
from logger import logger

router = APIRouter(prefix="/migration", tags=["Migration"])
job_manager = JobManager()

_schedule_thread: Optional[threading.Thread] = None
_schedule_stop_event = threading.Event()
_last_run_time: Optional[str] = None


def _build_migrator():
    """환경변수 기반으로 DBMigrator 인스턴스 생성"""
    from config import (
        MIGRATION_SOURCE_DB, MIGRATION_TARGET_DB, MIGRATION_BATCH_SIZE,
        MIGRATION_TEST_MODE, MIGRATION_TEST_LIMIT,
    )
    from db_migrator import DBMigrator

    if not MIGRATION_SOURCE_DB:
        raise ValueError("MIGRATION_SOURCE_DB 환경변수가 설정되지 않았습니다.")
    if not MIGRATION_TARGET_DB:
        raise ValueError("MIGRATION_TARGET_DB 환경변수가 설정되지 않았습니다.")

    return DBMigrator(
        source_conn_str=MIGRATION_SOURCE_DB,
        target_conn_str=MIGRATION_TARGET_DB,
        batch_size=MIGRATION_BATCH_SIZE,
        test_limit=MIGRATION_TEST_LIMIT if MIGRATION_TEST_MODE else 0,
    )


def _resolve_params(request: MigrationRequest) -> tuple:
    """요청 파라미터 + 환경변수 병합"""
    from config import MIGRATION_TABLES, MIGRATION_MODE, MIGRATION_MATERIAL_PARSE

    tables = request.tables or MIGRATION_TABLES
    mode = request.mode or MIGRATION_MODE
    material_config = (
        request.material_parse_config
        if request.material_parse_config is not None
        else MIGRATION_MATERIAL_PARSE
    )
    recreate = request.recreate_tables

    if not tables:
        raise ValueError(
            "마이그레이션 대상 테이블이 지정되지 않았습니다. "
            "요청 body의 tables 또는 환경변수 MIGRATION_TABLES를 설정하세요."
        )

    return tables, mode, material_config, recreate


def _resolve_env_params() -> tuple:
    """환경변수에서 기본 파라미터 로드"""
    from config import MIGRATION_TABLES, MIGRATION_MATERIAL_PARSE
    return MIGRATION_TABLES, MIGRATION_MATERIAL_PARSE


def _execute_migration(tables, mode, material_config, recreate_tables=False) -> dict:
    """마이그레이션 실행 (동기)"""
    from config import MIGRATION_EXCLUDE_COLUMNS_FILE
    global _last_run_time

    migrator = _build_migrator()
    try:
        result = migrator.run_migration(
            table_specs=tables,
            mode=mode,
            material_parse_config=material_config,
            recreate_tables=recreate_tables,
            exclude_columns_file=MIGRATION_EXCLUDE_COLUMNS_FILE,
        )
        _last_run_time = datetime.now().isoformat()
        return result
    finally:
        migrator.close()


def _run_migration_background(job_id: str, tables, mode, material_config, recreate_tables=False):
    """백그라운드 마이그레이션 작업"""
    job_manager.start_job(job_id)
    try:
        result = _execute_migration(tables, mode, material_config, recreate_tables)
        job_manager.complete_job(job_id, result)
        logger.info(f"[Migration Job {job_id}] 완료: {result.get('status')}")
    except Exception as e:
        job_manager.fail_job(job_id, str(e))
        logger.error(f"[Migration Job {job_id}] 실패: {e}")
        logger.error(traceback.format_exc())


@router.post(
    "/run",
    response_model=JobResponse,
    summary="마이그레이션 비동기 실행",
)
async def migration_run_async(
    request: MigrationRequest,
    background_tasks: BackgroundTasks,
):
    """
    MySQL → PostgreSQL 마이그레이션을 백그라운드에서 실행합니다.

    - **tables**: 테이블 매핑 목록 (["source:target", ...])
    - **mode**: replace / append / upsert
    - **material_parse_config**: 자재 파싱 설정
      (소스테이블:파싱컬럼:키컬럼:대상테이블)

    반환된 `job_id`로 `/jobs/{job_id}`에서 진행 상황을 조회할 수 있습니다.
    """
    try:
        tables, mode, material_config, recreate = _resolve_params(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    job_id = job_manager.create_job(
        job_type="db_migration",
        params={
            "tables": tables,
            "mode": mode,
            "material_parse_config": material_config,
            "recreate_tables": recreate,
        },
    )
    background_tasks.add_task(
        _run_migration_background, job_id, tables, mode, material_config, recreate
    )

    logger.info(f"[API] 마이그레이션 작업 생성: {job_id} (테이블: {tables})")
    return JobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message="DB 마이그레이션 작업이 큐에 추가되었습니다.",
        created_at=job_manager.get_job(job_id)["created_at"],
    )


@router.post(
    "/run-sync",
    response_model=MigrationResponse,
    summary="마이그레이션 동기 실행",
)
async def migration_run_sync(request: MigrationRequest):
    """
    MySQL → PostgreSQL 마이그레이션을 동기적으로 실행하고 결과를 반환합니다.
    데이터 양이 적을 때 사용하세요.
    """
    try:
        tables, mode, material_config, recreate = _resolve_params(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = _execute_migration(tables, mode, material_config, recreate)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return MigrationResponse(**result)


# ==================== 테이블 정보 / 데이터 정리 ====================

@router.get(
    "/tables",
    response_model=MigrationInfoResponse,
    summary="마이그레이션 대상 테이블 정보 조회",
)
async def get_table_info():
    """
    PostgreSQL 대상 테이블의 존재 여부, 행 수, 컬럼 목록을 조회합니다.
    환경변수에 설정된 테이블을 기준으로 조회합니다.
    """
    tables, material_config = _resolve_env_params()
    if not tables:
        raise HTTPException(
            status_code=400,
            detail="MIGRATION_TABLES 환경변수가 설정되지 않았습니다.",
        )

    migrator = _build_migrator()
    try:
        return migrator.get_table_info(tables, material_config)
    finally:
        migrator.close()


@router.post(
    "/cleanup",
    response_model=MigrationCleanupResponse,
    summary="마이그레이션 데이터 전량 삭제 (TRUNCATE)",
)
async def cleanup_tables(confirm: bool = False):
    """
    PostgreSQL 대상 테이블의 데이터를 전량 삭제합니다.

    - **confirm**: True여야 실제 삭제 수행
    """
    if not confirm:
        return MigrationCleanupResponse(
            status="cancelled",
            tables=[{"message": "confirm=true로 호출해야 실제 삭제됩니다."}],
        )

    tables, material_config = _resolve_env_params()
    if not tables:
        raise HTTPException(
            status_code=400,
            detail="MIGRATION_TABLES 환경변수가 설정되지 않았습니다.",
        )

    migrator = _build_migrator()
    try:
        result = migrator.cleanup_tables(tables, material_config)
        logger.info(f"[API] 마이그레이션 데이터 정리 완료: {result['status']}")
        return MigrationCleanupResponse(**result)
    finally:
        migrator.close()


# ==================== 일배치 스케줄 관리 ====================

def _scheduled_migration_job():
    """스케줄러에 의해 호출되는 마이그레이션 작업"""
    from config import MIGRATION_TABLES, MIGRATION_MODE, MIGRATION_MATERIAL_PARSE

    logger.info("[Schedule] 일배치 마이그레이션 실행 시작")
    try:
        _execute_migration(
            tables=MIGRATION_TABLES,
            mode=MIGRATION_MODE,
            material_config=MIGRATION_MATERIAL_PARSE,
        )
    except Exception as e:
        logger.error(f"[Schedule] 일배치 마이그레이션 실패: {e}")
        logger.error(traceback.format_exc())


def _schedule_loop():
    """스케줄 실행 루프 (별도 스레드)"""
    logger.info("[Schedule] 마이그레이션 스케줄 루프 시작")
    while not _schedule_stop_event.is_set():
        schedule_lib.run_pending()
        _schedule_stop_event.wait(timeout=10)
    logger.info("[Schedule] 마이그레이션 스케줄 루프 종료")


@router.get(
    "/schedule",
    response_model=MigrationScheduleStatus,
    summary="일배치 스케줄 상태 조회",
)
async def get_schedule_status():
    """현재 일배치 마이그레이션 스케줄 상태를 조회합니다."""
    from config import MIGRATION_SCHEDULE

    is_running = _schedule_thread is not None and _schedule_thread.is_alive()

    next_run = None
    jobs = schedule_lib.get_jobs()
    migration_jobs = [
        j for j in jobs
        if j.job_func and 'scheduled_migration' in str(j.job_func)
    ]
    if migration_jobs:
        next_run_dt = migration_jobs[0].next_run
        if next_run_dt:
            next_run = next_run_dt.isoformat()

    return MigrationScheduleStatus(
        schedule_enabled=is_running,
        schedule_time=MIGRATION_SCHEDULE if MIGRATION_SCHEDULE else None,
        last_run=_last_run_time,
        next_run=next_run,
        message="일배치 스케줄 실행 중" if is_running else "일배치 스케줄 중지됨",
    )


@router.post("/schedule/start", summary="일배치 스케줄 시작")
async def start_schedule(schedule_time: Optional[str] = None):
    """
    일배치 마이그레이션 스케줄을 시작합니다.

    - **schedule_time**: 실행 시간 (HH:MM 형식, 미지정 시 환경변수 MIGRATION_SCHEDULE 사용)
    """
    global _schedule_thread

    from config import MIGRATION_SCHEDULE, MIGRATION_TABLES

    time_str = schedule_time or MIGRATION_SCHEDULE
    if not time_str:
        raise HTTPException(
            status_code=400,
            detail="스케줄 시간이 지정되지 않았습니다. "
                   "schedule_time 파라미터 또는 MIGRATION_SCHEDULE 환경변수를 설정하세요.",
        )

    if not MIGRATION_TABLES:
        raise HTTPException(
            status_code=400,
            detail="마이그레이션 대상 테이블이 설정되지 않았습니다. "
                   "MIGRATION_TABLES 환경변수를 설정하세요.",
        )

    if _schedule_thread and _schedule_thread.is_alive():
        raise HTTPException(status_code=400, detail="이미 스케줄이 실행 중입니다.")

    schedule_lib.every().day.at(time_str).do(
        _scheduled_migration_job
    ).tag('scheduled_migration')

    _schedule_stop_event.clear()
    _schedule_thread = threading.Thread(
        target=_schedule_loop, daemon=True, name="migration-schedule"
    )
    _schedule_thread.start()

    logger.info(f"[API] 마이그레이션 일배치 스케줄 시작: 매일 {time_str}")
    return {
        "message": f"일배치 스케줄이 시작되었습니다. 매일 {time_str}에 실행됩니다.",
        "schedule_time": time_str,
        "tables": MIGRATION_TABLES,
    }


@router.post("/schedule/stop", summary="일배치 스케줄 중지")
async def stop_schedule():
    """일배치 마이그레이션 스케줄을 중지합니다."""
    global _schedule_thread

    schedule_lib.clear('scheduled_migration')
    _schedule_stop_event.set()

    if _schedule_thread and _schedule_thread.is_alive():
        _schedule_thread.join(timeout=15)

    _schedule_thread = None

    logger.info("[API] 마이그레이션 일배치 스케줄 중지됨")
    return {"message": "일배치 스케줄이 중지되었습니다."}
