"""
UI 업로드 방식 완전 모방 테스트
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


def test_ui_mimic_upload():
    """UI와 완전히 동일한 방식으로 업로드"""
    logger.info("="*80)
    logger.info("UI 업로드 방식 모방")
    logger.info("="*80)
    
    try:
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        
        # 테스트용 지식베이스 (UI에서 생성한 것 사용)
        logger.info(f"\n1. 기존 지식베이스 사용")
        
        # 이름으로 검색
        datasets = rag.list_datasets(name="KTX-EMU 매뉴얼")
        
        if not datasets:
            logger.error("지식베이스를 찾을 수 없습니다. UI에서 먼저 생성하세요.")
            return
        
        dataset = datasets[0]
        logger.info(f"✓ 지식베이스 찾음: {dataset.name}")
        logger.info(f"  Dataset ID: {dataset.id}")
        
        # 테스트 파일 생성
        test_file = Path("test_ui_mimic.txt")
        logger.info(f"\n2. 테스트 파일 생성")
        
        test_content = f"UI 모방 테스트\n시간: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        logger.info(f"✓ 테스트 파일 생성 완료")
        
        # SDK 방식으로 업로드 (UI가 사용하는 방식)
        logger.info(f"\n3. SDK로 파일 업로드...")
        
        with open(test_file, 'rb') as f:
            from io import BytesIO
            file_content = f.read()
            file_stream = BytesIO(file_content)
            file_stream.name = "test_ui_mimic.txt"
            file_stream.seek(0)
            
            doc_info = {
                "display_name": "test_ui_mimic.txt",
                "blob": file_stream
            }
            
            uploaded_docs = dataset.upload_documents([doc_info])
            file_stream.close()
        
        if uploaded_docs:
            doc = uploaded_docs[0]
            logger.info(f"✓ 업로드 성공")
            logger.info(f"  Document ID: {doc.id}")
            
            # 잠시 대기
            time.sleep(2)
            
            # 다운로드 테스트
            logger.info(f"\n4. 다운로드 테스트...")
            
            try:
                downloaded = doc.download()
                if downloaded:
                    logger.info(f"✅ 다운로드 성공! ({len(downloaded)} bytes)")
                    if downloaded.decode('utf-8') == test_content:
                        logger.info(f"✅ 파일 내용 일치!")
                else:
                    logger.error(f"✗ 다운로드 실패: 빈 응답")
            except Exception as e:
                logger.error(f"✗ 다운로드 실패: {e}")
        
        # 정리
        test_file.unlink()
        logger.info(f"\n✓ 테스트 완료")
    
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    test_ui_mimic_upload()

