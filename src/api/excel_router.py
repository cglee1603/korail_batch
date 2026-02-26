"""
Excel 처리 API 라우터
- POST /excel/batch   : Excel 배치 처리 (비동기)
- POST /excel/export  : Excel 처리 결과 JSON 덤프 (동기)
"""
import json
import traceback
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks

from api.models import (
    ExcelBatchRequest,
    ExcelExportRequest,
    ExcelExportResponse,
    JobResponse,
    JobStatus,
)
from api.job_manager import JobManager
from logger import logger

router = APIRouter(prefix="/excel", tags=["Excel"])
job_manager = JobManager()


def _run_excel_batch(job_id: str, excel_files: List[str]):
    """백그라운드 Excel 배치 작업"""
    from batch_processor import BatchProcessor

    job_manager.start_job(job_id)

    total_stats = {
        "total_files_processed": 0,
        "successful_files": 0,
        "failed_files": 0,
        "file_details": [],
    }

    try:
        for idx, excel_file in enumerate(excel_files, 1):
            logger.info(f"[API Job {job_id}] ({idx}/{len(excel_files)}) 처리 중: {excel_file}")
            file_start = datetime.now()

            try:
                processor = BatchProcessor(excel_path=excel_file, data_source="excel")
                processor.process()

                duration = (datetime.now() - file_start).total_seconds()
                total_stats["successful_files"] += 1
                total_stats["file_details"].append({
                    "file": excel_file,
                    "status": "success",
                    "duration_seconds": round(duration, 1),
                    "stats": processor.stats,
                })
                logger.info(f"[API Job {job_id}] ({idx}/{len(excel_files)}) 완료 ({duration:.1f}초)")
            except Exception as e:
                logger.error(f"[API Job {job_id}] ({idx}/{len(excel_files)}) 실패: {e}")
                logger.error(traceback.format_exc())
                total_stats["failed_files"] += 1
                total_stats["file_details"].append({
                    "file": excel_file,
                    "status": "failed",
                    "error": str(e),
                })

            total_stats["total_files_processed"] += 1

        job_manager.complete_job(job_id, total_stats)
        logger.info(
            f"[API Job {job_id}] 배치 완료 - "
            f"성공: {total_stats['successful_files']}, 실패: {total_stats['failed_files']}"
        )
    except Exception as e:
        job_manager.fail_job(job_id, str(e))
        logger.error(f"[API Job {job_id}] 배치 실패: {e}")
        logger.error(traceback.format_exc())


@router.post("/batch", response_model=JobResponse, summary="Excel 배치 처리 (비동기)")
async def excel_batch(request: ExcelBatchRequest, background_tasks: BackgroundTasks):
    """
    Excel 파일 경로 리스트를 받아 배치 처리를 백그라운드에서 실행합니다.

    - **excel_files**: 처리할 Excel 파일 경로 리스트

    반환된 `job_id`로 `/jobs/{job_id}`에서 진행 상황을 조회할 수 있습니다.
    """
    for fp in request.excel_files:
        p = Path(fp)
        if not p.exists():
            raise HTTPException(status_code=400, detail=f"파일을 찾을 수 없습니다: {fp}")
        if not p.is_file():
            raise HTTPException(status_code=400, detail=f"파일이 아닙니다: {fp}")
        if p.suffix.lower() not in (".xlsx", ".xls"):
            raise HTTPException(status_code=400, detail=f"Excel 파일이 아닙니다: {fp}")

    job_id = job_manager.create_job(
        job_type="excel_batch",
        params=request.model_dump(),
    )
    background_tasks.add_task(_run_excel_batch, job_id, request.excel_files)

    logger.info(f"[API] Excel 배치 작업 생성: {job_id} (파일 수: {len(request.excel_files)})")
    return JobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message="Excel 배치 작업이 큐에 추가되었습니다.",
        created_at=job_manager.get_job(job_id)["created_at"],
    )


@router.post("/export", response_model=ExcelExportResponse, summary="Excel 처리 결과 JSON 덤프")
async def excel_export(request: ExcelExportRequest):
    """
    Excel 파일을 처리하여 시트별 JSON 결과를 지정 디렉토리에 저장합니다.

    - **excel_file**: 처리할 Excel 파일 경로
    - **export_outdir**: 출력 디렉토리 (기본: data/temp/export)
    - **early_stop**: 연속 무값 행 N개에서 시트 스캔 중지 (기본: 10)
    """
    from excel_processor import ExcelProcessor

    excel_path = request.excel_file
    if not Path(excel_path).exists():
        raise HTTPException(status_code=400, detail=f"파일을 찾을 수 없습니다: {excel_path}")

    outdir = Path(request.export_outdir) if request.export_outdir else Path("data/temp/export")
    early_stop = request.early_stop or 10

    proc = ExcelProcessor(excel_path)
    if not proc.load_workbook():
        raise HTTPException(status_code=500, detail="Excel 파일 로드 실패")

    sheets_processed = 0
    sheets_skipped = 0
    output_files: List[str] = []

    try:
        for sheet_name in proc.get_sheet_names():
            try:
                sheet = proc.workbook[sheet_name]
                if getattr(sheet, "sheet_state", None) in ("hidden", "veryHidden"):
                    sheets_skipped += 1
                    continue

                stype, items, headers = proc.process_sheet(sheet_name, early_stop_no_value=early_stop)
                data = {
                    "sheet_name": sheet_name,
                    "sheet_type": stype.value if hasattr(stype, "value") else str(stype),
                    "headers": headers,
                    "total_items": len(items),
                    "items": items,
                }
                outdir.mkdir(parents=True, exist_ok=True)
                safe = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in sheet_name).strip() or "sheet"
                out_file = outdir / f"{safe}.processed.json"
                with out_file.open("w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                output_files.append(str(out_file))
                sheets_processed += 1
            except Exception as e:
                logger.error(f"시트 '{sheet_name}' 처리 중 오류: {e}")
                logger.error(traceback.format_exc())
                sheets_skipped += 1
    finally:
        proc.close()

    return ExcelExportResponse(
        excel_file=excel_path,
        export_outdir=str(outdir),
        sheets_processed=sheets_processed,
        sheets_skipped=sheets_skipped,
        output_files=output_files,
    )
