"""
파싱 실패 원인 진단 스크립트
"""
import sys
from pathlib import Path

# src 디렉토리를 Python 경로에 추가
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from ragflow_sdk import RAGFlow
from config import RAGFLOW_API_KEY, RAGFLOW_BASE_URL
from logger import logger
import time


def diagnose_all_datasets():
    """모든 지식베이스의 파싱 상태 진단"""
    logger.info("="*80)
    logger.info("파싱 상태 진단 시작")
    logger.info("="*80)
    
    try:
        # RAGFlow 연결
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        logger.info(f"✓ RAGFlow 연결 성공")
        
        # 모든 지식베이스 조회
        all_datasets = rag.list_datasets()
        
        if not all_datasets:
            logger.warning("지식베이스가 없습니다.")
            return
        
        logger.info(f"\n총 {len(all_datasets)}개 지식베이스 발견\n")
        
        # 각 지식베이스 진단
        for idx, dataset in enumerate(all_datasets, 1):
            dataset_name = dataset.name if hasattr(dataset, 'name') else 'Unknown'
            dataset_id = dataset.id if hasattr(dataset, 'id') else 'N/A'
            
            logger.info(f"{'='*80}")
            logger.info(f"[{idx}/{len(all_datasets)}] 지식베이스: {dataset_name}")
            logger.info(f"{'='*80}")
            logger.info(f"ID: {dataset_id}")
            
            try:
                # 문서 목록 조회
                documents = dataset.list_documents()
                
                if not documents:
                    logger.warning("문서가 없습니다.\n")
                    continue
                
                logger.info(f"문서 수: {len(documents)}\n")
                
                # 각 문서 상태 확인
                parsing_status = {
                    'pending': 0,
                    'parsing': 0,
                    'done': 0,
                    'failed': 0,
                    'unknown': 0
                }
                
                failed_docs = []
                
                for doc_idx, doc in enumerate(documents, 1):
                    doc_name = doc.name if hasattr(doc, 'name') else 'Unknown'
                    
                    logger.info(f"\n  [{doc_idx}/{len(documents)}] 문서: {doc_name}")
                    logger.info(f"  {'-'*70}")
                    
                    # 문서 상세 정보 조회
                    try:
                        doc_info = doc.get()
                        
                        # 기본 정보 출력
                        if hasattr(doc_info, 'id'):
                            logger.info(f"    ID: {doc_info.id}")
                        
                        if hasattr(doc_info, 'size'):
                            size_mb = doc_info.size / (1024 * 1024)
                            logger.info(f"    크기: {size_mb:.2f} MB")
                        
                        if hasattr(doc_info, 'type'):
                            logger.info(f"    타입: {doc_info.type}")
                        
                        # 파싱 상태 확인
                        status = None
                        status_field_name = None
                        
                        # 다양한 상태 필드명 시도
                        for field in ['status', 'parsing_status', 'parse_status', 'progress', 'run']:
                            if hasattr(doc_info, field):
                                status = getattr(doc_info, field)
                                status_field_name = field
                                break
                        
                        if status:
                            logger.info(f"    상태 ({status_field_name}): {status}")
                            
                            # 상태 분류
                            status_lower = str(status).lower()
                            if 'fail' in status_lower or 'error' in status_lower:
                                parsing_status['failed'] += 1
                                failed_docs.append(doc_name)
                                logger.error(f"    ⚠ 파싱 실패!")
                            elif 'done' in status_lower or 'success' in status_lower or 'completed' in status_lower:
                                parsing_status['done'] += 1
                                logger.info(f"    ✓ 파싱 완료")
                            elif 'pars' in status_lower or 'process' in status_lower:
                                parsing_status['parsing'] += 1
                                logger.info(f"    ⏳ 파싱 중...")
                            elif 'pend' in status_lower or 'wait' in status_lower:
                                parsing_status['pending'] += 1
                                logger.info(f"    ⏸ 대기 중...")
                            else:
                                parsing_status['unknown'] += 1
                                logger.warning(f"    ? 알 수 없는 상태")
                        else:
                            parsing_status['unknown'] += 1
                            logger.warning(f"    상태 정보 없음")
                        
                        # 청크 정보
                        if hasattr(doc_info, 'chunk_num'):
                            logger.info(f"    청크 수: {doc_info.chunk_num}")
                        
                        if hasattr(doc_info, 'token_num'):
                            logger.info(f"    토큰 수: {doc_info.token_num}")
                        
                        # 에러 메시지 확인
                        for error_field in ['error', 'error_message', 'message', 'reason']:
                            if hasattr(doc_info, error_field):
                                error_msg = getattr(doc_info, error_field)
                                if error_msg:
                                    logger.error(f"    에러 메시지: {error_msg}")
                        
                        # 생성/수정 시간
                        if hasattr(doc_info, 'created_at'):
                            logger.info(f"    생성 시간: {doc_info.created_at}")
                        
                        if hasattr(doc_info, 'updated_at'):
                            logger.info(f"    수정 시간: {doc_info.updated_at}")
                        
                        # 모든 속성 출력 (디버깅용)
                        logger.debug(f"    전체 속성: {dir(doc_info)}")
                    
                    except Exception as e:
                        logger.error(f"    문서 정보 조회 실패: {e}")
                        parsing_status['unknown'] += 1
                
                # 지식베이스별 요약
                logger.info(f"\n  {'='*70}")
                logger.info(f"  지식베이스 '{dataset_name}' 파싱 상태 요약:")
                logger.info(f"  {'-'*70}")
                logger.info(f"    ✓ 완료:     {parsing_status['done']:3d} 개")
                logger.info(f"    ⏳ 파싱 중:  {parsing_status['parsing']:3d} 개")
                logger.info(f"    ⏸ 대기 중:  {parsing_status['pending']:3d} 개")
                logger.info(f"    ✗ 실패:     {parsing_status['failed']:3d} 개")
                logger.info(f"    ? 알 수 없음: {parsing_status['unknown']:3d} 개")
                logger.info(f"  {'='*70}")
                
                # 실패한 문서 목록
                if failed_docs:
                    logger.error(f"\n  실패한 문서 목록:")
                    for failed_doc in failed_docs:
                        logger.error(f"    - {failed_doc}")
                
                logger.info("")
            
            except Exception as e:
                logger.error(f"지식베이스 '{dataset_name}' 진단 실패: {e}\n")
        
        logger.info("="*80)
        logger.info("진단 완료")
        logger.info("="*80)
    
    except Exception as e:
        logger.error(f"진단 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


def retry_failed_parsing(dataset_name: str = None):
    """실패한 파싱 재시도"""
    logger.info("="*80)
    logger.info("실패한 파싱 재시도")
    logger.info("="*80)
    
    try:
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        
        # 특정 지식베이스 또는 전체
        if dataset_name:
            datasets = [rag.get_dataset(dataset_name)]
        else:
            datasets = rag.list_datasets()
        
        retry_count = 0
        
        for dataset in datasets:
            ds_name = dataset.name if hasattr(dataset, 'name') else 'Unknown'
            logger.info(f"\n지식베이스: {ds_name}")
            
            try:
                documents = dataset.list_documents()
                
                for doc in documents:
                    doc_name = doc.name if hasattr(doc, 'name') else 'Unknown'
                    
                    try:
                        doc_info = doc.get()
                        
                        # 상태 확인
                        status = None
                        for field in ['status', 'parsing_status', 'parse_status']:
                            if hasattr(doc_info, field):
                                status = getattr(doc_info, field)
                                break
                        
                        # 실패 상태면 재시도
                        if status and ('fail' in str(status).lower() or 'error' in str(status).lower()):
                            logger.info(f"  재시도: {doc_name} (현재 상태: {status})")
                            doc.parse()
                            retry_count += 1
                            time.sleep(2)  # 요청 간 대기
                    
                    except Exception as e:
                        logger.error(f"  문서 '{doc_name}' 재시도 실패: {e}")
            
            except Exception as e:
                logger.error(f"지식베이스 '{ds_name}' 처리 실패: {e}")
        
        logger.info(f"\n총 {retry_count}개 문서 재시도 완료")
    
    except Exception as e:
        logger.error(f"재시도 실패: {e}")


def check_server_logs():
    """서버 로그 확인 안내"""
    logger.info("="*80)
    logger.info("RAGFlow 서버 로그 확인 방법")
    logger.info("="*80)
    logger.info("""
파싱 실패의 상세 원인은 RAGFlow 서버 로그에서 확인할 수 있습니다.

1. Docker 로그 확인:
   docker logs ragflow-server -f --tail=100

2. 파일 로그 확인:
   tail -f /path/to/ragflow/logs/*.log

3. 주요 확인 사항:
   - 파일 형식 지원 여부 (PDF, HWP 등)
   - 메모리 부족 에러
   - 파일 크기 제한
   - 권한 문제
   - Parsing worker 상태

4. Task consumer 상태:
   - pending: 대기 중인 작업 수
   - lag: 지연된 작업 수  
   - done: 완료된 작업 수
   - failed: 실패한 작업 수
   - current: 현재 처리 중인 작업
""")
    logger.info("="*80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='파싱 상태 진단 및 재시도')
    parser.add_argument('--retry', action='store_true', help='실패한 파싱 재시도')
    parser.add_argument('--dataset', type=str, help='특정 지식베이스만 처리')
    parser.add_argument('--logs', action='store_true', help='서버 로그 확인 방법 출력')
    
    args = parser.parse_args()
    
    if args.logs:
        check_server_logs()
    elif args.retry:
        retry_failed_parsing(args.dataset)
    else:
        diagnose_all_datasets()

