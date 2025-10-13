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
                    
                    # 문서 정보는 doc 객체 자체에 있음 (get() 호출 불필요)
                    try:
                        # 기본 정보 출력
                        if hasattr(doc, 'id'):
                            logger.info(f"    ID: {doc.id}")
                        
                        if hasattr(doc, 'size'):
                            size_mb = doc.size / (1024 * 1024)
                            logger.info(f"    크기: {size_mb:.2f} MB")
                        
                        if hasattr(doc, 'type'):
                            logger.info(f"    타입: {doc.type}")
                        
                        # 파싱 상태 확인 (여러 필드 체크)
                        # run: "0" (대기), "1" (처리 중), "2" (완료), "3" (실패)
                        # status: "1" (정상), "0" (삭제됨)
                        # progress: 0.0 ~ 1.0
                        
                        run_status = getattr(doc, 'run', None)
                        status = getattr(doc, 'status', None)
                        progress = getattr(doc, 'progress', None)
                        progress_msg = getattr(doc, 'progress_msg', '')
                        
                        logger.info(f"    run: {run_status}")
                        logger.info(f"    status: {status}")
                        logger.info(f"    progress: {progress}")
                        if progress_msg:
                            logger.info(f"    progress_msg: {progress_msg}")
                        
                        # 파싱 상태 분류
                        if run_status == "3":  # 실패
                            parsing_status['failed'] += 1
                            failed_docs.append(doc_name)
                            logger.error(f"    ⚠ 파싱 실패!")
                        elif run_status == "2":  # 완료
                            parsing_status['done'] += 1
                            logger.info(f"    ✓ 파싱 완료")
                        elif run_status == "1":  # 처리 중
                            parsing_status['parsing'] += 1
                            logger.info(f"    ⏳ 파싱 중... ({progress*100:.1f}%)")
                        elif run_status == "0":  # 대기
                            parsing_status['pending'] += 1
                            logger.info(f"    ⏸ 파싱 대기 중...")
                        else:
                            parsing_status['unknown'] += 1
                            logger.warning(f"    ? 알 수 없는 상태 (run={run_status})")
                        
                        # 청크 정보
                        if hasattr(doc, 'chunk_count'):
                            logger.info(f"    청크 수: {doc.chunk_count}")
                        
                        if hasattr(doc, 'token_count'):
                            logger.info(f"    토큰 수: {doc.token_count}")
                        
                        # 처리 시간 정보
                        if hasattr(doc, 'process_begin_at') and doc.process_begin_at:
                            logger.info(f"    처리 시작: {doc.process_begin_at}")
                        
                        if hasattr(doc, 'process_duration') and doc.process_duration:
                            logger.info(f"    처리 시간: {doc.process_duration:.2f}초")
                        
                        # 생성 정보
                        if hasattr(doc, 'created_by'):
                            logger.info(f"    생성자: {doc.created_by}")
                    
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
                
                # 파싱이 필요한 문서 ID 수집
                doc_ids_to_parse = []
                
                for doc in documents:
                    doc_name = doc.name if hasattr(doc, 'name') else 'Unknown'
                    run_status = getattr(doc, 'run', None)
                    
                    # UNSTART, 실패(3), 대기(0) 상태면 파싱 필요
                    if run_status in ["UNSTART", "3", "0"]:
                        logger.info(f"  파싱 필요: {doc_name} (run={run_status})")
                        doc_ids_to_parse.append(doc.id)
                
                # 일괄 파싱 요청
                if doc_ids_to_parse:
                    logger.info(f"\n{len(doc_ids_to_parse)}개 문서 일괄 파싱 시작...")
                    dataset.async_parse_documents(doc_ids_to_parse)
                    logger.info(f"✓ 파싱 요청 완료")
                    retry_count += len(doc_ids_to_parse)
                else:
                    logger.info(f"  파싱이 필요한 문서가 없습니다.")
            
            except Exception as e:
                logger.error(f"지식베이스 '{ds_name}' 처리 실패: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        logger.info(f"\n총 {retry_count}개 문서 파싱 요청 완료")
    
    except Exception as e:
        logger.error(f"재시도 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


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

