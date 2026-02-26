"""
지식베이스 관리 API 라우터
- GET    /knowledgebases                    : 목록 조회
- DELETE /knowledgebases/{name}/documents   : 문서 삭제
- DELETE /knowledgebases/{name}             : 전량 삭제 (문서 + 파일)
- POST   /knowledgebases/{name}/sync        : DB 동기화
"""
import traceback

from fastapi import APIRouter, HTTPException, Query

from api.models import (
    KnowledgebaseItem,
    KnowledgebaseListResponse,
    DeleteDocumentsResponse,
    DeleteKnowledgeResponse,
    SyncRequest,
    SyncResponse,
)
from logger import logger

router = APIRouter(prefix="/knowledgebases", tags=["Knowledgebases"])


@router.get("", response_model=KnowledgebaseListResponse, summary="지식베이스 목록 조회")
async def list_knowledgebases():
    """
    모든 지식베이스 목록을 조회합니다.
    CLI: `python run.py --list`
    """
    from ragflow_client import RAGFlowClient

    try:
        client = RAGFlowClient()
        datasets = client.list_datasets(page=1, page_size=100)
        items = [
            KnowledgebaseItem(
                id=ds.get("id", ""),
                name=ds.get("name", ""),
                document_count=ds.get("document_count"),
                chunk_count=ds.get("chunk_num"),
            )
            for ds in datasets
        ]
        return KnowledgebaseListResponse(total=len(items), knowledgebases=items)
    except Exception as e:
        logger.error(f"[API] 지식베이스 목록 조회 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"지식베이스 목록 조회 실패: {str(e)}")


@router.delete(
    "/{dataset_name}/documents",
    response_model=DeleteDocumentsResponse,
    summary="지식베이스 문서 삭제",
)
async def delete_documents(
    dataset_name: str,
    confirm: bool = Query(
        default=False,
        description="True일 때만 실제 삭제 수행. False이면 삭제 대상 미리보기만 반환",
    ),
):
    """
    지식베이스의 모든 문서를 삭제합니다.

    - **confirm=false**: 삭제 대상 문서 수만 확인 (미리보기)
    - **confirm=true**: 실제 삭제 수행

    CLI: `python run.py --delete "이름" [--confirm]`
    """
    from batch_processor import BatchProcessor

    try:
        processor = BatchProcessor()
        result = processor.delete_documents_by_dataset_name(
            dataset_name=dataset_name,
            confirm=confirm,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "알 수 없는 오류"),
            )

        total = result.get("total_documents", 0)

        if not confirm:
            message = f"삭제 가능한 문서: {total}개. 실제 삭제하려면 confirm=true로 요청하세요."
        elif total == 0:
            message = "삭제할 문서가 없습니다."
        else:
            failed = result.get("ragflow_failed", 0)
            message = f"문서 삭제 완료. 실패: {failed}개" if failed else "문서 삭제가 완료되었습니다."

        return DeleteDocumentsResponse(
            dataset_name=dataset_name,
            confirm=confirm,
            total_documents=total,
            deleted_count=result.get("ragflow_deleted", 0),
            failed_count=result.get("ragflow_failed", 0),
            message=message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] 문서 삭제 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"문서 삭제 중 오류: {str(e)}")


@router.delete(
    "/{dataset_name}",
    response_model=DeleteKnowledgeResponse,
    summary="지식베이스 전량 삭제 (문서 + 파일)",
)
async def delete_knowledge(
    dataset_name: str,
    confirm: bool = Query(
        default=False,
        description="True일 때만 실제 삭제 수행. False이면 삭제 대상 미리보기만 반환",
    ),
):
    """
    지식베이스의 모든 문서와 파일을 삭제합니다.

    - **confirm=false**: 삭제 대상 미리보기
    - **confirm=true**: 실제 삭제 수행

    CLI: `python run.py --deleteKnowledge "이름" [--confirm]`
    """
    from batch_processor import BatchProcessor

    try:
        processor = BatchProcessor()
        result = processor.delete_knowledge_by_dataset_name(
            dataset_name=dataset_name,
            confirm=confirm,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "알 수 없는 오류"),
            )

        total = result.get("total_documents", 0)

        if not confirm:
            message = (
                f"삭제 대상 - 문서: {total}개, 파일: {total}개. "
                f"실제 삭제하려면 confirm=true로 요청하세요."
            )
        elif total == 0:
            message = "삭제할 항목이 없습니다."
        else:
            message = "지식베이스 전량 삭제가 완료되었습니다."

        return DeleteKnowledgeResponse(
            dataset_name=dataset_name,
            confirm=confirm,
            total_documents=total,
            deleted_documents=result.get("deleted_documents", 0),
            deleted_files=result.get("deleted_files", 0),
            db_deleted=result.get("db_deleted", 0),
            failed_documents=result.get("failed_documents", 0),
            failed_files=result.get("failed_files", 0),
            message=message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] 지식베이스 삭제 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"지식베이스 삭제 중 오류: {str(e)}")


@router.post(
    "/{dataset_name}/sync",
    response_model=SyncResponse,
    summary="지식베이스-DB 동기화",
)
async def sync_knowledgebase(dataset_name: str, request: SyncRequest):
    """
    지식베이스와 DB의 동기화 상태를 검사하고, 선택적으로 불일치를 수정합니다.

    - **fix=false**: 불일치 항목 확인만
    - **fix=true**: 자동 수정 수행

    CLI: `python run.py --sync "이름" [--fix]`
    """
    from batch_processor import BatchProcessor

    try:
        processor = BatchProcessor()
        result = processor.sync_dataset_with_db(
            dataset_name=dataset_name,
            fix=request.fix,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail="동기화 검사 실패",
            )

        orphans = result.get("orphans", [])
        ghosts = result.get("ghosts", [])

        if request.fix:
            message = "동기화 수정이 완료되었습니다."
        elif orphans or ghosts:
            message = (
                f"불일치 발견 - orphans: {len(orphans)}개, ghosts: {len(ghosts)}개. "
                f"자동 수정하려면 fix=true로 요청하세요."
            )
        else:
            message = "동기화 상태가 정상입니다."

        return SyncResponse(
            dataset_name=dataset_name,
            fix=request.fix,
            orphans=orphans,
            ghosts=ghosts,
            fixed=request.fix and bool(orphans or ghosts),
            message=message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] 동기화 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"동기화 중 오류: {str(e)}")
