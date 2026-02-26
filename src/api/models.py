"""
API 요청/응답 Pydantic 모델 정의
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


# ==================== 공통 ====================

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobResponse(BaseModel):
    """비동기 작업 생성 응답"""
    job_id: str = Field(..., description="작업 ID")
    status: JobStatus = Field(..., description="작업 상태")
    message: str = Field(..., description="응답 메시지")
    created_at: str = Field(..., description="작업 생성 시간")


class JobStatusResponse(BaseModel):
    """작업 상태 조회 응답"""
    job_id: str
    status: JobStatus
    job_type: str = Field(..., description="작업 유형 (excel_batch, filesystem_batch, ...)")
    params: Dict[str, Any] = Field(default_factory=dict, description="작업 파라미터")
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None


class JobListItem(BaseModel):
    """작업 목록 항목"""
    job_id: str
    status: JobStatus
    job_type: str
    created_at: str
    completed_at: Optional[str] = None


class JobListResponse(BaseModel):
    """작업 목록 응답"""
    total_jobs: int
    jobs: List[JobListItem]


# ==================== Excel ====================

class ExcelBatchRequest(BaseModel):
    """Excel 배치 처리 요청"""
    excel_files: List[str] = Field(
        ...,
        description="처리할 Excel 파일 경로 리스트 (절대 경로 또는 상대 경로)",
        min_length=1
    )


class ExcelExportRequest(BaseModel):
    """Excel 처리 결과 JSON 덤프 요청"""
    excel_file: str = Field(..., description="처리할 Excel 파일 경로")
    export_outdir: Optional[str] = Field(
        default=None,
        description="익스포트 출력 디렉토리 (기본: data/temp/export)"
    )
    early_stop: Optional[int] = Field(
        default=10,
        description="연속 무값 행 N개에서 시트 스캔 중지 (기본: 10)",
        ge=1
    )


class ExcelExportResponse(BaseModel):
    """Excel 익스포트 응답"""
    excel_file: str
    export_outdir: str
    sheets_processed: int
    sheets_skipped: int
    output_files: List[str]


# ==================== Filesystem ====================

class FilesystemBatchRequest(BaseModel):
    """Filesystem 배치 처리 요청"""
    filesystem_path: str = Field(..., description="스캔할 파일시스템 루트 디렉토리 경로")


# ==================== 지식베이스 ====================

class KnowledgebaseItem(BaseModel):
    """지식베이스 항목"""
    id: str
    name: str
    document_count: Optional[int] = None
    chunk_count: Optional[int] = None


class KnowledgebaseListResponse(BaseModel):
    """지식베이스 목록 응답"""
    total: int
    knowledgebases: List[KnowledgebaseItem]


class DeleteDocumentsResponse(BaseModel):
    """문서 삭제 응답"""
    dataset_name: str
    confirm: bool
    total_documents: int
    deleted_count: int = 0
    failed_count: int = 0
    message: str


class DeleteKnowledgeResponse(BaseModel):
    """지식베이스 전량 삭제 응답"""
    dataset_name: str
    confirm: bool
    total_documents: int = 0
    deleted_documents: int = 0
    deleted_files: int = 0
    db_deleted: int = 0
    failed_documents: int = 0
    failed_files: int = 0
    message: str


class SyncRequest(BaseModel):
    """동기화 요청"""
    fix: bool = Field(
        default=False,
        description="True일 때 불일치 항목 자동 수정"
    )


class SyncResponse(BaseModel):
    """동기화 응답"""
    dataset_name: str
    fix: bool
    orphans: Optional[List[Dict[str, Any]]] = None
    ghosts: Optional[List[Dict[str, Any]]] = None
    fixed: bool = False
    message: str


# ==================== 파싱 제어 ====================

class ReparseAllRequest(BaseModel):
    """전체 재파싱 요청"""
    confirm: bool = Field(default=False, description="True일 때만 실제 재파싱 수행")
    cancel_running: bool = Field(default=False, description="RUNNING 문서 포함 허용 플래그")
    include_running: bool = Field(default=False, description="RUNNING 문서도 대상으로 포함")
    exclude_failed: bool = Field(default=False, description="FAIL 문서를 제외")


class ThrottleParseRequest(BaseModel):
    """동시성 제한 파싱 요청"""
    confirm: bool = Field(default=False, description="True일 때만 실제 파싱 수행")
    concurrency: Optional[int] = Field(
        default=None,
        description="동시 파싱 수 (미지정시 현재 RUNNING 수 사용)",
        ge=1
    )
    check_interval: int = Field(
        default=10,
        description="상태 확인 간격 (초)",
        ge=1
    )
    include_done: bool = Field(default=False, description="DONE 문서도 재파싱 대상에 포함")
    include_failed: bool = Field(default=False, description="FAIL 문서도 재파싱 대상에 포함")
    max_hours: float = Field(
        default=2.0,
        description="최대 동작 시간 (시간 단위)",
        gt=0
    )


class ParseResponse(BaseModel):
    """파싱 작업 응답 (동기)"""
    dataset_name: str
    message: str
    details: Optional[Dict[str, Any]] = None
