"""
파일 업로드 후 응답 확인 - MinIO 경로 추적
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
import requests


def test_upload_response():
    """업로드 후 응답 상세 확인"""
    logger.info("="*80)
    logger.info("업로드 응답 상세 분석")
    logger.info("="*80)
    
    try:
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        
        # 테스트용 지식베이스
        test_kb_name = f"Upload_Response_Test_{int(time.time())}"
        logger.info(f"\n1. 지식베이스 생성: {test_kb_name}")
        
        dataset = rag.create_dataset(
            name=test_kb_name,
            description="업로드 응답 테스트",
            embedding_model="BAAI/bge-large-zh-v1.5"
        )
        logger.info(f"✓ 지식베이스 생성 완료")
        logger.info(f"  Dataset ID: {dataset.id}")
        
        # 테스트 파일 생성
        test_file = Path("test_response.txt")
        logger.info(f"\n2. 테스트 파일 생성")
        
        test_content = f"업로드 응답 테스트\n시간: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        logger.info(f"✓ 테스트 파일 생성 완료")
        
        # 파일 업로드 (requests로 직접)
        logger.info(f"\n3. 파일 업로드 (응답 상세 확인)...")
        
        url = f"{RAGFLOW_BASE_URL}/api/v1/datasets/{dataset.id}/documents"
        headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}"}
        
        with open(test_file, 'rb') as file_obj:
            files = {"file": ("test_response.txt", file_obj)}
            response = requests.post(url, headers=headers, files=files, timeout=60)
        
        logger.info(f"  HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"\n✓ 업로드 성공!")
            logger.info(f"\n응답 JSON (전체):")
            import json
            logger.info(json.dumps(result, indent=2, ensure_ascii=False))
            
            # 문서 데이터 추출
            if result.get("code") == 0 and result.get("data"):
                docs = result.get("data", [])
                if docs:
                    doc_data = docs[0]
                    logger.info(f"\n문서 정보:")
                    logger.info(f"  ID: {doc_data.get('id')}")
                    logger.info(f"  Name: {doc_data.get('name')}")
                    logger.info(f"  Size: {doc_data.get('size')}")
                    logger.info(f"  Type: {doc_data.get('type')}")
                    logger.info(f"  KB ID: {doc_data.get('kb_id')}")
                    
                    # 중요: 저장 경로 관련 정보
                    for key in ['location', 'path', 'storage_path', 'minio_path', 
                               'bucket', 'bucket_id', 'object_name']:
                        if key in doc_data:
                            logger.info(f"  {key}: {doc_data.get(key)}")
                    
                    # 모든 필드 출력
                    logger.info(f"\n모든 필드:")
                    for key, value in doc_data.items():
                        logger.info(f"  {key}: {value}")
        else:
            logger.error(f"✗ 업로드 실패")
            logger.error(f"  응답: {response.text[:500]}")
        
        # SDK로 문서 조회 후 비교
        time.sleep(2)
        logger.info(f"\n4. SDK로 문서 조회...")
        
        documents = dataset.list_documents()
        if documents:
            doc = documents[0]
            logger.info(f"\nSDK Document 객체:")
            logger.info(f"  ID: {doc.id}")
            logger.info(f"  Name: {doc.name}")
            logger.info(f"  Dataset ID: {doc.dataset_id if hasattr(doc, 'dataset_id') else 'N/A'}")
            
            # 모든 속성 확인
            logger.info(f"\nSDK Document 모든 속성:")
            for attr in dir(doc):
                if not attr.startswith('_') and not callable(getattr(doc, attr)):
                    try:
                        value = getattr(doc, attr)
                        logger.info(f"  {attr}: {value}")
                    except:
                        pass
        
        # MinIO 확인 안내
        logger.info(f"\n{'='*80}")
        logger.info("MinIO 웹 UI 확인:")
        logger.info(f"{'='*80}")
        logger.info(f"1. http://192.168.10.41:9001 접속")
        logger.info(f"2. ragflow → f3f2b739bd0c425c9e8a74e7400900f7 폴더 확인")
        logger.info(f"3. Dataset ID로 시작하는 폴더 찾기: {dataset.id}")
        logger.info(f"4. 또는 다른 ID 폴더에 test_response.txt 파일 검색")
        logger.info(f"5. 실제 저장된 버킷 ID를 확인하세요!")
        
        # 정리
        test_file.unlink()
        logger.info(f"\n✓ 테스트 완료")
        logger.info(f"지식베이스 '{test_kb_name}'는 RAGFlow UI에서 확인 후 삭제하세요.")
    
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    test_upload_response()

