"""
파일 업로드 → MinIO 저장 → 다운로드 프로세스 테스트
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


def test_file_storage_process():
    """파일 업로드 → 저장 → 다운로드 전체 프로세스 테스트"""
    logger.info("="*80)
    logger.info("파일 저장 프로세스 테스트")
    logger.info("="*80)
    
    try:
        # RAGFlow 클라이언트
        client = RAGFlowClient()
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        
        # 테스트용 지식베이스
        test_kb_name = "Storage_Test"
        logger.info(f"\n1. 지식베이스 생성/확인: {test_kb_name}")
        
        # 기존 지식베이스 확인
        try:
            existing_datasets = rag.list_datasets(name=test_kb_name)
            if existing_datasets and len(existing_datasets) > 0:
                dataset = existing_datasets[0]
                logger.info(f"✓ 기존 지식베이스 사용")
            else:
                # 새로 생성
                dataset = rag.create_dataset(
                    name=test_kb_name,
                    description="파일 저장 테스트",
                    embedding_model="qwen3-embedding:8b"  # UI와 동일한 모델
                )
                logger.info(f"✓ 지식베이스 생성 완료")
        except Exception as e:
            error_msg = str(e)
            if "don't own" in error_msg.lower():
                # 다른 사용자 소유 - 새 이름으로 생성
                test_kb_name = f"Storage_Test_{int(time.time())}"
                logger.warning(f"기존 지식베이스는 다른 사용자 소유. 새 이름 사용: {test_kb_name}")
                dataset = rag.create_dataset(
                    name=test_kb_name,
                    description="파일 저장 테스트",
                    embedding_model="qwen3-embedding:8b"
                )
                logger.info(f"✓ 지식베이스 생성 완료")
            else:
                raise
        
        logger.info(f"   Dataset ID: {dataset.id}")
        
        # 테스트 파일 생성
        test_file = Path("test_storage.txt")
        logger.info(f"\n2. 테스트 파일 생성: {test_file}")
        
        test_content = """이것은 MinIO 저장 테스트 파일입니다.

이 파일이 제대로 업로드되면:
1. RAGFlow 서버가 파일을 받음
2. MinIO에 파일 저장
3. 데이터베이스에 메타데이터 저장
4. 파싱 시 MinIO에서 파일 읽기

한글 테스트: 가나다라마바사아자차카타파하
영문 테스트: The quick brown fox jumps over the lazy dog
숫자 테스트: 0123456789

저장 시간: """ + time.strftime("%Y-%m-%d %H:%M:%S")
        
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        logger.info(f"✓ 테스트 파일 생성 완료 ({len(test_content)} bytes)")
        
        # 파일 업로드
        logger.info(f"\n3. 파일 업로드 시작...")
        
        success = client.upload_document(
            dataset=dataset,
            file_path=test_file,
            display_name="storage_test.txt"
        )
        
        if not success:
            logger.error("✗ 업로드 실패")
            test_file.unlink()
            return
        
        logger.info(f"✓ 업로드 성공")
        
        # 업로드된 문서 확인
        time.sleep(2)
        logger.info(f"\n4. 업로드된 문서 확인...")
        
        documents = dataset.list_documents()
        logger.info(f"   문서 수: {len(documents)}")
        
        if not documents:
            logger.error("✗ 문서를 찾을 수 없습니다")
            test_file.unlink()
            return
        
        doc = documents[0]
        logger.info(f"   문서 ID: {doc.id}")
        logger.info(f"   문서 이름: {doc.name}")
        logger.info(f"   파일 크기: {doc.size} bytes")
        logger.info(f"   저장 위치 (location): {getattr(doc, 'location', 'N/A')}")
        
        # MinIO 저장 확인을 위한 파일 다운로드 시도
        logger.info(f"\n5. 파일 다운로드 시도 (MinIO 저장 확인)...")
        
        try:
            # Document.download() 메서드 사용
            downloaded_content = doc.download()
            
            if downloaded_content:
                logger.info(f"✓ 다운로드 성공!")
                logger.info(f"   다운로드된 크기: {len(downloaded_content)} bytes")
                logger.info(f"   원본 크기: {len(test_content)} bytes")
                
                # 내용 비교
                try:
                    downloaded_text = downloaded_content.decode('utf-8')
                    if downloaded_text == test_content:
                        logger.info(f"✓ 파일 내용 일치! MinIO 저장 정상")
                    else:
                        logger.warning(f"⚠ 파일 내용 불일치")
                        logger.info(f"   원본 앞 100자: {test_content[:100]}")
                        logger.info(f"   다운로드 앞 100자: {downloaded_text[:100]}")
                except:
                    logger.info(f"   (바이너리 파일 - 내용 비교 건너뜀)")
            else:
                logger.error(f"✗ 다운로드 실패: 빈 응답")
        
        except Exception as download_error:
            logger.error(f"✗ 다운로드 실패: {download_error}")
            logger.error(f"   이것은 MinIO에 파일이 저장되지 않았음을 의미합니다!")
            
            # 상세 에러 정보
            import traceback
            logger.debug(traceback.format_exc())
        
        # 파싱 시도
        logger.info(f"\n6. 파싱 시작 (MinIO 읽기 테스트)...")
        
        try:
            client.start_batch_parse(dataset)
            logger.info(f"✓ 파싱 요청 완료")
            
            # 잠시 대기 후 상태 확인
            time.sleep(3)
            
            documents_after = dataset.list_documents()
            if documents_after:
                doc_after = documents_after[0]
                logger.info(f"\n파싱 후 상태:")
                logger.info(f"   run: {doc_after.run}")
                logger.info(f"   progress: {doc_after.progress}")
                logger.info(f"   progress_msg: {doc_after.progress_msg}")
                
                if doc_after.run == "FAIL":
                    logger.error(f"✗ 파싱 실패!")
                    if "버킷" in str(doc_after.progress_msg) or "bucket" in str(doc_after.progress_msg).lower():
                        logger.error(f"   → MinIO 저장 문제로 파싱 실패")
                elif doc_after.run in ["RUNNING", "DONE"]:
                    logger.info(f"✓ 파싱 진행 중 또는 완료")
        
        except Exception as parse_error:
            logger.error(f"✗ 파싱 요청 실패: {parse_error}")
        
        # 정리
        logger.info(f"\n7. 정리...")
        test_file.unlink()
        logger.info(f"✓ 테스트 파일 삭제")
        
        logger.info(f"\n{'='*80}")
        logger.info("테스트 완료")
        logger.info(f"{'='*80}")
        logger.info(f"\n요약:")
        logger.info(f"- 지식베이스: {test_kb_name}")
        logger.info(f"- 업로드: {'성공' if success else '실패'}")
        logger.info(f"- MinIO 저장: 다운로드 테스트 결과 확인")
        logger.info(f"\n지식베이스 '{test_kb_name}'는 RAGFlow UI에서 수동 삭제하세요.")
    
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    test_file_storage_process()

