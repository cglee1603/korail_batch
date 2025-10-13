"""
MinIO 파일 저장 문제 해결 테스트
- 메타데이터 업데이트 제거 후 테스트
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


def test_minio_fix():
    """메타데이터 업데이트 없이 파일 업로드 테스트"""
    logger.info("="*80)
    logger.info("MinIO 저장 문제 해결 테스트")
    logger.info("="*80)
    logger.info("변경사항: doc.update() 메타데이터 업데이트 제거")
    
    try:
        # RAGFlow 클라이언트
        client = RAGFlowClient()
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        
        # 테스트용 지식베이스
        test_kb_name = f"MinIO_Fix_Test_{int(time.time())}"
        logger.info(f"\n1. 지식베이스 생성: {test_kb_name}")
        
        dataset = rag.create_dataset(
            name=test_kb_name,
            description="MinIO 저장 테스트",
            embedding_model="BAAI/bge-large-zh-v1.5"
        )
        logger.info(f"✓ 지식베이스 생성 완료 (ID: {dataset.id})")
        
        # 테스트 파일 생성
        test_file = Path("test_minio_fix.txt")
        logger.info(f"\n2. 테스트 파일 생성: {test_file}")
        
        test_content = f"""MinIO 저장 테스트 파일

이 파일은 메타데이터 업데이트 없이 업로드됩니다.

doc.update()를 호출하지 않으므로:
1. MinIO 파일 참조가 손상되지 않음
2. 다운로드 가능해야 함
3. 파싱이 정상 작동해야 함

생성 시간: {time.strftime("%Y-%m-%d %H:%M:%S")}

테스트 내용:
- 한글: 철도공사 KTX-EMU 매뉴얼
- 영문: RAGFlow Batch Processing System
- 숫자: 1234567890
- 특수문자: @#$%^&*()
"""
        
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        logger.info(f"✓ 테스트 파일 생성 완료 ({len(test_content)} bytes)")
        
        # 파일 업로드 (메타데이터 포함 - 하지만 업데이트는 안 함)
        logger.info(f"\n3. 파일 업로드 (메타데이터 업데이트 없이)...")
        
        test_metadata = {
            "원본_파일": "test_minio_fix.txt",
            "파일_형식": "text",
            "엑셀_행번호": "999",
            "하이퍼링크": "http://test.com/file"
        }
        
        success = client.upload_document(
            dataset=dataset,
            file_path=test_file,
            metadata=test_metadata,  # 전달은 하지만 적용은 안 됨
            display_name="minio_fix_test.txt"
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
        
        # ⭐ 핵심 테스트: 다운로드 시도
        logger.info(f"\n5. 다운로드 테스트 (MinIO 저장 확인)...")
        
        try:
            downloaded_content = doc.download()
            
            if downloaded_content:
                logger.info(f"✅ 다운로드 성공!")
                logger.info(f"   다운로드된 크기: {len(downloaded_content)} bytes")
                logger.info(f"   원본 크기: {len(test_content)} bytes")
                
                # 내용 비교
                downloaded_text = downloaded_content.decode('utf-8')
                if downloaded_text == test_content:
                    logger.info(f"✅ 파일 내용 일치! MinIO 저장 정상!")
                    logger.info(f"\n🎉 메타데이터 업데이트 제거로 MinIO 저장 문제 해결!")
                else:
                    logger.warning(f"⚠ 파일 내용 불일치")
            else:
                logger.error(f"✗ 다운로드 실패: 빈 응답")
        
        except Exception as download_error:
            logger.error(f"✗ 다운로드 실패: {download_error}")
            logger.error(f"   MinIO 저장에 여전히 문제가 있습니다!")
        
        # 파싱 테스트
        logger.info(f"\n6. 파싱 테스트...")
        
        try:
            client.start_batch_parse(dataset)
            logger.info(f"✓ 파싱 요청 완료")
            
            # 잠시 대기 후 상태 확인
            logger.info(f"   10초 대기 중...")
            time.sleep(10)
            
            documents_after = dataset.list_documents()
            if documents_after:
                doc_after = documents_after[0]
                logger.info(f"\n파싱 결과:")
                logger.info(f"   상태 (run): {doc_after.run}")
                logger.info(f"   진행률: {doc_after.progress}")
                
                if doc_after.run == "FAIL":
                    logger.error(f"✗ 파싱 실패!")
                    logger.error(f"   메시지: {doc_after.progress_msg}")
                elif doc_after.run == "DONE":
                    logger.info(f"✅ 파싱 완료!")
                    logger.info(f"   청크 수: {doc_after.chunk_count}")
                    logger.info(f"   토큰 수: {doc_after.token_count}")
                elif doc_after.run == "RUNNING":
                    logger.info(f"⏳ 파싱 진행 중...")
                    logger.info(f"   RAGFlow UI에서 최종 결과 확인하세요.")
        
        except Exception as parse_error:
            logger.error(f"✗ 파싱 요청 실패: {parse_error}")
        
        # 정리
        logger.info(f"\n7. 정리...")
        test_file.unlink()
        logger.info(f"✓ 테스트 파일 삭제")
        
        logger.info(f"\n{'='*80}")
        logger.info("테스트 완료")
        logger.info(f"{'='*80}")
        logger.info(f"\n✅ 성공 기준:")
        logger.info(f"   - 파일 다운로드 성공")
        logger.info(f"   - 파일 내용 일치")
        logger.info(f"   - 파싱 DONE 또는 RUNNING")
        logger.info(f"\n지식베이스 '{test_kb_name}'는 RAGFlow UI에서 확인 후 삭제하세요.")
    
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        if test_file.exists():
            test_file.unlink()


if __name__ == "__main__":
    test_minio_fix()

