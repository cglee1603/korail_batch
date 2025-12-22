"""
RAGFlow Plus 배치 프로그램 REST API 서버
Excel 파일 경로를 받아 배치 처리를 실행하는 API를 제공합니다.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import uuid
from logger import logger
from batch_processor import BatchProcessor
from ragflow_client import RAGFlowClient

# FastAPI 앱 생성
app = FastAPI(
    title="RAGFlow Plus Batch API",
    description="Excel/DB 데이터를 RAGFlow 지식베이스에 업로드하는 배치 처리 API",
    version="1.0.0"
)

# 작업 상태 저장소 (메모리)
job_storage: Dict[str, Dict[str, Any]] = {}


class BatchRequest(BaseModel):
    """배치 처리 요청 모델"""
    excel_files: List[str] = Field(
        ..., 
        description="처리할 Excel 파일 경로 리스트 (절대 경로 또는 상대 경로)",
        min_items=1
    )
    data_source: Optional[str] = Field(
        default=None,
        description="데이터 소스 선택 (excel, db, both). None이면 config 기본값 사용"
    )
    
    @validator('data_source')
    def validate_data_source(cls, v):
        if v is not None and v not in ['excel', 'db', 'both']:
            raise ValueError('data_source는 excel, db, both 중 하나여야 합니다.')
        return v
    
    @validator('excel_files')
    def validate_excel_files(cls, files):
        """파일 경로 유효성 검사"""
        for file_path in files:
            path = Path(file_path)
            if not path.exists():
                raise ValueError(f"파일을 찾을 수 없습니다: {file_path}")
            if not path.is_file():
                raise ValueError(f"파일이 아닙니다: {file_path}")
            if path.suffix.lower() not in ['.xlsx', '.xls']:
                raise ValueError(f"Excel 파일이 아닙니다: {file_path}")
        return files


class BatchResponse(BaseModel):
    """배치 처리 응답 모델"""
    job_id: str = Field(..., description="작업 ID")
    status: str = Field(..., description="작업 상태 (queued, running, completed, failed)")
    message: str = Field(..., description="응답 메시지")
    excel_files: List[str] = Field(..., description="처리할 Excel 파일 경로 리스트")
    created_at: str = Field(..., description="작업 생성 시간")


class JobStatusResponse(BaseModel):
    """작업 상태 응답 모델"""
    job_id: str
    status: str
    excel_files: List[str]
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None


def run_batch_job(job_id: str, excel_files: List[str], data_source: Optional[str]):
    """백그라운드에서 배치 작업 실행"""
    try:
        # 작업 시작
        job_storage[job_id]['status'] = 'running'
        job_storage[job_id]['started_at'] = datetime.now().isoformat()
        
        logger.info(f"[API Job {job_id}] 배치 작업 시작")
        logger.info(f"[API Job {job_id}] 처리할 Excel 파일 수: {len(excel_files)}")
        
        # 통합 통계
        total_stats = {
            'total_files_processed': 0,
            'successful_files': 0,
            'failed_files': 0,
            'file_details': []
        }
        
        # 여러 Excel 파일 순차 처리
        for idx, excel_file in enumerate(excel_files, 1):
            logger.info(f"[API Job {job_id}] ({idx}/{len(excel_files)}) 처리 중: {excel_file}")
            
            file_start_time = datetime.now()
            
            try:
                # 각 파일에 대해 BatchProcessor 실행
                processor = BatchProcessor(excel_path=excel_file, data_source=data_source)
                processor.process()
                
                file_end_time = datetime.now()
                duration = (file_end_time - file_start_time).total_seconds()
                
                # 파일별 통계 수집
                total_stats['successful_files'] += 1
                total_stats['file_details'].append({
                    'file': excel_file,
                    'status': 'success',
                    'duration_seconds': duration,
                    'stats': processor.stats
                })
                
                logger.info(f"[API Job {job_id}] ({idx}/{len(excel_files)}) 완료: {excel_file} (소요시간: {duration:.1f}초)")
            
            except Exception as e:
                logger.error(f"[API Job {job_id}] ({idx}/{len(excel_files)}) 실패: {excel_file} - {e}")
                import traceback
                logger.error(traceback.format_exc())
                
                total_stats['failed_files'] += 1
                total_stats['file_details'].append({
                    'file': excel_file,
                    'status': 'failed',
                    'error': str(e)
                })
            
            total_stats['total_files_processed'] += 1
        
        # 작업 완료
        job_storage[job_id]['status'] = 'completed'
        job_storage[job_id]['completed_at'] = datetime.now().isoformat()
        job_storage[job_id]['stats'] = total_stats
        
        logger.info(f"[API Job {job_id}] 배치 작업 완료")
        logger.info(f"[API Job {job_id}] 성공: {total_stats['successful_files']}, 실패: {total_stats['failed_files']}")
    
    except Exception as e:
        # 작업 실패
        job_storage[job_id]['status'] = 'failed'
        job_storage[job_id]['completed_at'] = datetime.now().isoformat()
        job_storage[job_id]['error_message'] = str(e)
        
        logger.error(f"[API Job {job_id}] 배치 작업 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


@app.get("/")
async def root():
    """API 루트"""
    return {
        "service": "RAGFlow Plus Batch API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/batch/run", response_model=BatchResponse)
async def run_batch(request: BatchRequest, background_tasks: BackgroundTasks):
    """
    배치 작업 실행 (비동기)
    
    Excel 파일 경로 리스트를 받아 배치 처리를 백그라운드에서 실행합니다.
    작업 ID를 반환하며, /batch/status/{job_id}로 진행 상황을 확인할 수 있습니다.
    """
    try:
        # 작업 ID 생성
        job_id = str(uuid.uuid4())
        
        # 작업 정보 저장
        job_info = {
            'job_id': job_id,
            'status': 'queued',
            'excel_files': request.excel_files,
            'data_source': request.data_source,
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'error_message': None,
            'stats': None
        }
        job_storage[job_id] = job_info
        
        # 백그라운드 작업 추가
        background_tasks.add_task(
            run_batch_job, 
            job_id, 
            request.excel_files, 
            request.data_source
        )
        
        logger.info(f"[API] 새 배치 작업 생성: {job_id}")
        logger.info(f"[API] Excel 파일 수: {len(request.excel_files)}")
        
        return BatchResponse(
            job_id=job_id,
            status='queued',
            message='배치 작업이 큐에 추가되었습니다.',
            excel_files=request.excel_files,
            created_at=job_info['created_at']
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"배치 작업 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"배치 작업 생성 실패: {str(e)}")


@app.get("/batch/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    작업 상태 조회
    
    작업 ID로 배치 작업의 진행 상황을 조회합니다.
    """
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
    
    job_info = job_storage[job_id]
    
    return JobStatusResponse(
        job_id=job_info['job_id'],
        status=job_info['status'],
        excel_files=job_info['excel_files'],
        created_at=job_info['created_at'],
        started_at=job_info.get('started_at'),
        completed_at=job_info.get('completed_at'),
        error_message=job_info.get('error_message'),
        stats=job_info.get('stats')
    )


@app.get("/batch/jobs")
async def list_jobs():
    """
    모든 작업 목록 조회
    
    현재 메모리에 저장된 모든 배치 작업 목록을 반환합니다.
    """
    jobs = []
    for job_id, job_info in job_storage.items():
        jobs.append({
            'job_id': job_id,
            'status': job_info['status'],
            'excel_files_count': len(job_info['excel_files']),
            'created_at': job_info['created_at'],
            'completed_at': job_info.get('completed_at')
        })
    
    # 생성 시간 역순 정렬
    jobs.sort(key=lambda x: x['created_at'], reverse=True)
    
    return {
        'total_jobs': len(jobs),
        'jobs': jobs
    }


@app.delete("/batch/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    작업 삭제
    
    완료되거나 실패한 작업을 메모리에서 삭제합니다.
    실행 중인 작업은 삭제할 수 없습니다.
    """
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
    
    job_info = job_storage[job_id]
    
    if job_info['status'] in ['queued', 'running']:
        raise HTTPException(
            status_code=400, 
            detail=f"실행 중인 작업은 삭제할 수 없습니다. (상태: {job_info['status']})"
        )
    
    del job_storage[job_id]
    
    return {
        'message': f'작업이 삭제되었습니다: {job_id}',
        'job_id': job_id
    }


class BatchDeleteRequest(BaseModel):
    """일괄 문서 삭제 요청 모델"""
    kb_id: str = Field(..., description="지식베이스 ID")
    document_ids: List[str] = Field(
        ..., 
        description="삭제할 문서 ID 리스트",
        min_items=1
    )


class DeleteAllResponse(BaseModel):
    """모든 문서 삭제 응답 모델"""
    kb_id: str = Field(..., description="지식베이스 ID")
    kb_name: str = Field(..., description="지식베이스 이름")
    total_documents: int = Field(..., description="전체 문서 수")
    deleted_count: int = Field(..., description="삭제 성공 개수")
    failed_count: int = Field(..., description="삭제 실패 개수")
    failed_ids: List[str] = Field(..., description="삭제 실패한 문서 ID 리스트")



@app.delete("/knowledgebases/{kb_id}/documents/all", response_model=DeleteAllResponse)
async def delete_all_documents(kb_id: str):
    """
    특정 지식베이스의 모든 문서 일괄 삭제
    
    지정된 지식베이스에 있는 모든 문서를 삭제합니다.
    """
    try:
        logger.info(f"[API] 지식베이스 '{kb_id}'의 모든 문서 삭제 요청")
        
        # RAGFlow 클라이언트 생성
        client = RAGFlowClient()
        
        # 지식베이스 정보 조회
        dataset = {'id': kb_id}
        dataset_info = client.get_dataset_info(dataset)
        kb_name = dataset_info.get('name', 'Unknown')
        dataset['name'] = kb_name
        
        # 모든 문서 삭제
        result = client.delete_all_documents_in_dataset(dataset)
        
        if 'error' in result:
            raise HTTPException(
                status_code=500,
                detail=f"문서 삭제 실패: {result['error']}"
            )
        
        logger.info(
            f"[API] 지식베이스 '{kb_name}' 문서 삭제 완료: "
            f"성공 {result['deleted_count']}개, 실패 {result['failed_count']}개"
        )
        
        return DeleteAllResponse(
            kb_id=kb_id,
            kb_name=kb_name,
            total_documents=result['total_documents'],
            deleted_count=result['deleted_count'],
            failed_count=result['failed_count'],
            failed_ids=result['failed_ids']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] 문서 삭제 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"문서 삭제 중 오류가 발생했습니다: {str(e)}"
        )



if __name__ == "__main__":
    import uvicorn
    
    # 개발 모드 실행
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

