"""
RAGFlow Plus 배치 프로그램 REST API 서버

Excel/Filesystem 데이터를 RAGFlow 지식베이스에 업로드하는 배치 처리 API를 제공합니다.
Database 처리는 batch(CLI)로만 수행합니다.
"""
from datetime import datetime

from fastapi import FastAPI, HTTPException

from api.models import (
    JobStatusResponse,
    JobListItem,
    JobListResponse,
)
from api.job_manager import JobManager
from api.excel_router import router as excel_router
from api.filesystem_router import router as filesystem_router
from api.knowledgebase_router import router as knowledgebase_router
from api.parsing_router import router as parsing_router

app = FastAPI(
    title="RAGFlow Plus Batch API",
    description=(
        "Excel/Filesystem 데이터를 RAGFlow 지식베이스에 업로드하는 배치 처리 API.\n\n"
        "**Excel**: 엑셀 파일을 파싱하여 지식베이스에 등록\n"
        "**Filesystem**: 지정 폴더를 스캔하여 지식베이스에 등록\n"
        "**Database**: batch(CLI) 전용 (`python run.py --source db`)\n\n"
        "비동기 작업은 `/jobs/{job_id}`로 상태를 조회합니다."
    ),
    version="2.0.0",
)

job_manager = JobManager()

# 라우터 등록
app.include_router(excel_router)
app.include_router(filesystem_router)
app.include_router(knowledgebase_router)
app.include_router(parsing_router)


# ==================== 공통 엔드포인트 ====================

@app.get("/", tags=["Common"])
async def root():
    """API 서비스 정보"""
    return {
        "service": "RAGFlow Plus Batch API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["Common"])
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }


# ==================== 작업 관리 엔드포인트 ====================

@app.get("/jobs", response_model=JobListResponse, tags=["Jobs"], summary="작업 목록 조회")
async def list_jobs():
    """현재 메모리에 저장된 모든 비동기 작업 목록을 반환합니다."""
    all_jobs = job_manager.list_jobs()
    items = [
        JobListItem(
            job_id=j["job_id"],
            status=j["status"],
            job_type=j["job_type"],
            created_at=j["created_at"],
            completed_at=j.get("completed_at"),
        )
        for j in all_jobs
    ]
    return JobListResponse(total_jobs=len(items), jobs=items)


@app.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    tags=["Jobs"],
    summary="작업 상태 조회",
)
async def get_job_status(job_id: str):
    """작업 ID로 비동기 작업의 진행 상황을 조회합니다."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")

    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        job_type=job["job_type"],
        params=job["params"],
        created_at=job["created_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        error_message=job.get("error_message"),
        stats=job.get("stats"),
    )


@app.delete("/jobs/{job_id}", tags=["Jobs"], summary="작업 삭제")
async def delete_job(job_id: str):
    """
    완료되거나 실패한 작업을 메모리에서 삭제합니다.
    실행 중(queued/running)인 작업은 삭제할 수 없습니다.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")

    if not job_manager.is_deletable(job_id):
        raise HTTPException(
            status_code=400,
            detail=f"실행 중인 작업은 삭제할 수 없습니다. (상태: {job['status'].value})",
        )

    job_manager.delete_job(job_id)
    return {"message": f"작업이 삭제되었습니다: {job_id}", "job_id": job_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
