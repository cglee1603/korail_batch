"""
API 업로드 테스트 스크립트
"""
import sys
from pathlib import Path

# src 디렉토리를 Python 경로에 추가
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from ragflow_sdk import RAGFlow
from config import RAGFLOW_API_KEY, RAGFLOW_BASE_URL
from logger import logger
from ragflow_client import RAGFlowClient
import time


def test_upload():
    """API 업로드 테스트"""
    logger.info("="*80)
    logger.info("API 업로드 테스트")
    logger.info("="*80)
    
    try:
        # RAGFlow 클라이언트
        client = RAGFlowClient()
        
        # 테스트용 지식베이스 생성
        test_kb_name = "API_Upload_Test"
        logger.info(f"\n테스트 지식베이스 생성: {test_kb_name}")
        
        dataset = client.get_or_create_dataset(
            name=test_kb_name,
            description="API 업로드 테스트용 지식베이스"
        )
        
        if not dataset:
            logger.error("지식베이스 생성 실패")
            return
        
        logger.info(f"✓ 지식베이스 생성 완료: {dataset.name}")
        
        # 테스트 파일 생성
        test_file = Path("test_upload_sample.txt")
        logger.info(f"\n테스트 파일 생성: {test_file}")
        
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("="*50 + "\n")
            f.write("API 업로드 테스트 문서\n")
            f.write("="*50 + "\n\n")
            f.write("이 문서는 RAGFlow API 업로드 테스트를 위해 생성되었습니다.\n\n")
            f.write("테스트 내용:\n")
            f.write("1. BytesIO를 사용한 파일 업로드\n")
            f.write("2. MinIO 저장 확인\n")
            f.write("3. 파싱 자동 시작 확인\n\n")
            f.write("한글 테스트: 가나다라마바사아자차카타파하\n")
            f.write("영문 테스트: ABCDEFGHIJKLMNOPQRSTUVWXYZ\n")
            f.write("숫자 테스트: 0123456789\n")
        
        logger.info(f"✓ 테스트 파일 생성 완료")
        
        # 파일 업로드
        logger.info(f"\n파일 업로드 시작...")
        
        metadata = {
            "테스트_타입": "API_업로드",
            "생성_일시": time.strftime("%Y-%m-%d %H:%M:%S"),
            "목적": "MinIO 저장 확인"
        }
        
        success = client.upload_document(
            dataset=dataset,
            file_path=test_file,
            metadata=metadata,
            display_name="API_업로드_테스트.txt"
        )
        
        if success:
            logger.info(f"✓ 업로드 성공!")
            
            # 업로드된 문서 확인
            logger.info(f"\n업로드된 문서 확인...")
            time.sleep(2)  # 잠시 대기
            
            documents = dataset.list_documents()
            logger.info(f"문서 수: {len(documents)}")
            
            if documents:
                for doc in documents:
                    logger.info(f"\n문서 정보:")
                    logger.info(f"  - 이름: {doc.name}")
                    logger.info(f"  - ID: {doc.id}")
                    logger.info(f"  - 크기: {doc.size / 1024:.2f} KB")
                    logger.info(f"  - 타입: {doc.type}")
                    logger.info(f"  - 상태 (run): {doc.run}")
                    logger.info(f"  - 진행률: {doc.progress}")
                    
                    if doc.progress_msg:
                        logger.info(f"  - 메시지: {doc.progress_msg}")
                    
                    # 파싱 시작
                    if doc.run == "UNSTART" or doc.run == "0":
                        logger.info(f"\n파싱 시작...")
                        
                        # Dataset의 async_parse_documents 사용
                        client.start_batch_parse(dataset)
                        logger.info(f"✓ 파싱 요청 완료")
                        
                        # 잠시 대기 후 상태 확인
                        time.sleep(3)
                        
                        # 문서 목록 다시 조회
                        documents_after = dataset.list_documents()
                        if documents_after:
                            doc_after = documents_after[0]
                            logger.info(f"\n파싱 시작 후 상태:")
                            logger.info(f"  - 상태 (run): {doc_after.run}")
                            logger.info(f"  - 진행률: {doc_after.progress}")
                            if doc_after.progress_msg:
                                logger.info(f"  - 메시지: {doc_after.progress_msg}")
                    
                    elif doc.run == "2" or doc.run == "DONE":
                        logger.info(f"  ✓ 이미 파싱 완료됨")
                        logger.info(f"  - 청크 수: {doc.chunk_count}")
                        logger.info(f"  - 토큰 수: {doc.token_count}")
            
            logger.info(f"\n{'='*80}")
            logger.info("테스트 성공!")
            logger.info("="*80)
        else:
            logger.error(f"✗ 업로드 실패")
        
        # 정리
        logger.info(f"\n테스트 파일 삭제...")
        test_file.unlink()
        logger.info(f"✓ 정리 완료")
        
        logger.info(f"\n테스트 지식베이스는 RAGFlow UI에서 수동으로 삭제하세요: {test_kb_name}")
    
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    test_upload()

