"""
Filesystem 처리 API 라우터
- POST /filesystem/batch : Filesystem 배치 처리 (비동기)
- DELETE /filesystem/files : 로컬 파일 삭제
"""
import traceback
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks

from api.models import (
    FilesystemBatchRequest,
    FileDeleteRequest,
    FileDeleteResponse,
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


@router.post("/delete-file", response_model=FileDeleteResponse, summary="로컬 파일 삭제 + RAGFlow 동기화")
async def delete_local_file(request: FileDeleteRequest):
    """
    로컬 서버의 파일을 삭제하고, RAGFlow Dataset에서도 해당 문서를 삭제합니다.

    - **file_path**: 삭제할 파일의 절대 경로 (JSON body)
    """
    file_path = request.file_path
    target = Path(file_path)

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {file_path}")

    if not target.is_file():
        raise HTTPException(status_code=400, detail=f"파일이 아닙니다 (디렉토리일 수 있음): {file_path}")

    resolved_path = str(target.resolve())

    # RAGFlow 동기화를 위해 삭제 전 mt_documents에서 문서 정보 사전 조회
    linked_docs = []
    try:
        from revision_db import RevisionDB
        db = RevisionDB()
        linked_docs = db.get_documents_by_file_path(resolved_path)
    except Exception as e:
        logger.warning(f"[API] 문서 사전 조회 실패: {e}")

    try:
        target.unlink()
        logger.info(f"[API] 파일 삭제 완료: {file_path}")

        ragflow_deleted = 0

        try:
            if not db:
                from revision_db import RevisionDB
                db = RevisionDB()

            # mt_file_list 노드 삭제
            deleted_nodes = db.delete_file_structure_node_by_path(resolved_path)
            if deleted_nodes > 0:
                logger.info(f"[API] DB 파일 구조 노드 삭제: {file_path} ({deleted_nodes}건)")

            # RAGFlow 동기화: mt_documents에서 찾은 문서를 RAGFlow에서도 삭제
            if linked_docs:
                ragflow_deleted = _sync_delete_ragflow_documents(db, linked_docs)

        except Exception as db_err:
            logger.warning(f"[API] DB/RAGFlow 동기화 실패 (파일은 삭제됨): {db_err}")
            logger.warning(traceback.format_exc())

        message = "파일이 성공적으로 삭제되었습니다."
        if ragflow_deleted > 0:
            message += f" (RAGFlow 문서 {ragflow_deleted}건 동기 삭제)"

        return FileDeleteResponse(
            file_path=file_path,
            deleted=True,
            message=message,
            ragflow_deleted=ragflow_deleted,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"파일 삭제 권한이 없습니다: {file_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 삭제 실패: {str(e)}")


def _sync_delete_ragflow_documents(db, docs: list) -> int:
    """
    mt_documents에서 조회된 문서들을 RAGFlow에서 삭제하고 DB 레코드도 정리합니다.

    Args:
        db: RevisionDB 인스턴스
        docs: mt_documents에서 file_path로 조회된 문서 목록
              각 문서에 document_id, dataset_id, dataset_name, document_key 포함

    Returns:
        RAGFlow에서 삭제된 문서 수
    """
    from ragflow_client import RAGFlowClient

    ragflow_client = RAGFlowClient()
    dataset_cache = {}
    deleted_count = 0

    for doc in docs:
        doc_id = doc.get('document_id')
        dataset_id = doc.get('dataset_id')
        dataset_name = doc.get('dataset_name')
        document_key = doc.get('document_key')
        file_name = doc.get('file_name', 'Unknown')

        if not doc_id or not dataset_id:
            continue

        # dataset 객체 캐싱 (같은 dataset 반복 조회 방지)
        if dataset_id not in dataset_cache:
            dataset = ragflow_client.get_dataset(dataset_id)
            dataset_cache[dataset_id] = dataset

        dataset = dataset_cache[dataset_id]
        if not dataset:
            logger.warning(f"[API] RAGFlow Dataset 조회 실패: {dataset_name} ({dataset_id})")
            continue

        if ragflow_client.delete_document(dataset, doc_id):
            logger.info(f"[API] RAGFlow 문서 삭제: {file_name} (doc_id: {doc_id})")
            deleted_count += 1
        else:
            logger.error(f"[API] RAGFlow 문서 삭제 실패: {file_name} (doc_id: {doc_id})")

        # mt_documents 레코드 삭제
        if document_key and dataset_id:
            db.delete_document(document_key, dataset_id, file_name=file_name)

    return deleted_count
