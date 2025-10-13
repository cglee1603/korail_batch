"""
Content-Type을 명시하여 파일 업로드 테스트
"""
import sys
from pathlib import Path
import mimetypes

# src 디렉토리를 Python 경로에 추가
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from ragflow_sdk import RAGFlow
from config import RAGFLOW_API_KEY, RAGFLOW_BASE_URL
from logger import logger
import time
from io import BytesIO


def upload_with_content_type(dataset, file_path: Path, display_name: str = None):
    """Content-Type을 명시하여 파일 업로드"""
    
    if not display_name:
        display_name = file_path.name
    
    # Content-Type 추측
    content_type, _ = mimetypes.guess_type(file_path.name)
    if not content_type:
        content_type = 'application/octet-stream'
    
    logger.info(f"파일: {display_name}")
    logger.info(f"  Content-Type: {content_type}")
    
    # 파일 읽기
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    logger.info(f"  파일 크기: {len(file_content)/1024/1024:.2f} MB")
    
    # BytesIO 생성
    file_stream = BytesIO(file_content)
    file_stream.name = display_name
    file_stream.seek(0)
    
    # RAGFlow API 직접 호출 (Content-Type 명시)
    url = f"/datasets/{dataset.id}/documents"
    
    # Content-Type을 포함한 파일 튜플
    files = [("file", (display_name, file_stream, content_type))]
    
    try:
        res = dataset.post(path=url, json=None, files=files)
        res_json = res.json()
        
        if res_json.get("code") == 0:
            logger.info(f"✓ 업로드 성공")
            return res_json.get("data", [])
        else:
            logger.error(f"✗ 업로드 실패: {res_json.get('message')}")
            return None
    
    finally:
        file_stream.close()


def test_upload_comparison():
    """UI 업로드 vs API 업로드(Content-Type 명시) 비교"""
    logger.info("="*80)
    logger.info("Content-Type 명시 업로드 테스트")
    logger.info("="*80)
    
    try:
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        
        # 테스트용 지식베이스
        test_kb_name = f"ContentType_Test_{int(time.time())}"
        logger.info(f"\n1. 지식베이스 생성: {test_kb_name}")
        
        dataset = rag.create_dataset(
            name=test_kb_name,
            description="Content-Type 테스트",
            embedding_model="BAAI/bge-large-zh-v1.5"
        )
        logger.info(f"✓ 지식베이스 생성 완료")
        
        # 테스트 파일 생성
        test_file = Path("test_contenttype.pdf")
        logger.info(f"\n2. 테스트 PDF 파일 생성")
        
        # 최소한의 PDF 파일 생성 (실제 PDF 헤더)
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Content-Type Test) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000317 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF
"""
        
        with open(test_file, 'wb') as f:
            f.write(pdf_content)
        
        logger.info(f"✓ PDF 파일 생성 완료 ({len(pdf_content)} bytes)")
        
        # Content-Type 명시하여 업로드
        logger.info(f"\n3. Content-Type 명시하여 업로드...")
        
        uploaded_docs = upload_with_content_type(dataset, test_file, "contenttype_test.pdf")
        
        if not uploaded_docs:
            logger.error("업로드 실패")
            test_file.unlink()
            return
        
        # 업로드된 문서 확인
        time.sleep(2)
        logger.info(f"\n4. 업로드된 문서 확인...")
        
        documents = dataset.list_documents()
        if documents:
            doc = documents[0]
            logger.info(f"  문서 ID: {doc.id}")
            logger.info(f"  문서 이름: {doc.name}")
            logger.info(f"  파일 크기: {doc.size} bytes")
            logger.info(f"  타입: {doc.type}")
            
            # 다운로드 테스트
            logger.info(f"\n5. 다운로드 테스트...")
            try:
                downloaded = doc.download()
                if downloaded:
                    logger.info(f"✓ 다운로드 성공 ({len(downloaded)} bytes)")
                    if downloaded == pdf_content:
                        logger.info(f"✓ 파일 내용 일치!")
                else:
                    logger.error(f"✗ 다운로드 실패")
            except Exception as e:
                logger.error(f"✗ 다운로드 오류: {e}")
            
            # 파싱 시도
            logger.info(f"\n6. 파싱 시작...")
            dataset.async_parse_documents([doc.id])
            logger.info(f"✓ 파싱 요청 완료")
            
            time.sleep(5)
            
            # 파싱 결과 확인
            documents_after = dataset.list_documents()
            if documents_after:
                doc_after = documents_after[0]
                logger.info(f"\n파싱 결과:")
                logger.info(f"  상태 (run): {doc_after.run}")
                logger.info(f"  진행률: {doc_after.progress}")
                logger.info(f"  메시지: {doc_after.progress_msg}")
                
                if doc_after.run == "DONE":
                    logger.info(f"✅ 파싱 성공!")
                elif doc_after.run == "FAIL":
                    logger.error(f"✗ 파싱 실패")
                elif doc_after.run == "RUNNING":
                    logger.info(f"⏳ 파싱 진행 중")
        
        # 정리
        test_file.unlink()
        logger.info(f"\n✓ 테스트 완료")
        logger.info(f"\n지식베이스 '{test_kb_name}'는 RAGFlow UI에서 확인 후 삭제하세요.")
    
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    test_upload_comparison()

