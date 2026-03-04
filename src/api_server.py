"""
RAGFlow Plus 배치 프로그램 REST API 서버

Excel/Filesystem 데이터를 RAGFlow 지식베이스에 업로드하는 배치 처리 API를 제공합니다.
Database 처리는 batch(CLI)로만 수행합니다.
"""
import time
from datetime import datetime

from fastapi import FastAPI, HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request

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
from api.migration_router import router as migration_router
from logger import logger

app = FastAPI(
    title="RAGFlow Plus Batch API",
    description=(
        "Excel/Filesystem 데이터를 RAGFlow 지식베이스에 업로드하는 배치 처리 API.\n\n"
        "**Excel**: 엑셀 파일을 파싱하여 지식베이스에 등록\n"
        "**Filesystem**: 지정 폴더를 스캔하여 지식베이스에 등록\n"
        "**Migration**: MySQL → PostgreSQL 데이터 마이그레이션 (일배치 스케줄 지원)\n"
        "**Database**: batch(CLI) 전용 (`python run.py --source db`)\n\n"
        "비동기 작업은 `/jobs/{job_id}`로 상태를 조회합니다."
    ),
    version="2.0.0",
)

job_manager = JobManager()


class RequestLoggingMiddleware:
    """순수 ASGI 미들웨어 - 모든 HTTP 요청/응답을 로깅"""

    SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self.SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        request = Request(scope)
        method = request.method
        query = str(request.query_params) if request.query_params else ""
        client_ip = request.client.host if request.client else "unknown"

        recv = receive
        body_text = ""

        if method in ("POST", "PUT", "PATCH"):
            body_chunks = []
            while True:
                message = await receive()
                body_chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break

            body_bytes = b"".join(body_chunks)
            if body_bytes:
                body_text = body_bytes.decode("utf-8", errors="replace")

            replayed = False

            async def receive_replay():
                nonlocal replayed
                if not replayed:
                    replayed = True
                    return {"type": "http.request", "body": body_bytes, "more_body": False}
                return {"type": "http.disconnect"}

            recv = receive_replay

        log_parts = [f"[Request] {method} {path}", f"client={client_ip}"]
        if query:
            log_parts.append(f"query={query}")
        if body_text:
            log_parts.append(f"body={body_text}")
        logger.info(" | ".join(log_parts))

        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, recv, send_wrapper)

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"[Response] {method} {path} | status={status_code} | {elapsed_ms:.1f}ms")


app.add_middleware(RequestLoggingMiddleware)

# 라우터 등록
app.include_router(excel_router)
app.include_router(filesystem_router)
app.include_router(knowledgebase_router)
app.include_router(parsing_router)
app.include_router(migration_router)


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
