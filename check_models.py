"""
RAGFlow에서 사용 가능한 임베딩 모델 확인 스크립트
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


def check_available_models():
    """사용 가능한 임베딩 모델 확인"""
    logger.info("="*80)
    logger.info("RAGFlow 임베딩 모델 확인")
    logger.info("="*80)
    
    try:
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        logger.info(f"✓ RAGFlow 연결 성공: {RAGFLOW_BASE_URL}")
        
        # 테스트 1: 임베딩 모델 지정하지 않고 생성
        logger.info(f"\n테스트 1: 기본 임베딩 모델로 지식베이스 생성")
        test_name_1 = f"Model_Test_Default_{int(time.time())}"
        
        try:
            dataset_1 = rag.create_dataset(
                name=test_name_1,
                description="기본 모델 테스트"
                # embedding_model 파라미터 생략 - 시스템 기본값 사용
            )
            logger.info(f"✓ 지식베이스 생성 성공 (기본 모델)")
            logger.info(f"   ID: {dataset_1.id}")
            logger.info(f"   Name: {dataset_1.name}")
            
            # 생성된 데이터셋의 속성 확인
            logger.info(f"\n데이터셋 속성:")
            for attr in dir(dataset_1):
                if not attr.startswith('_') and not callable(getattr(dataset_1, attr)):
                    try:
                        value = getattr(dataset_1, attr)
                        if 'embed' in attr.lower() or 'model' in attr.lower():
                            logger.info(f"   {attr}: {value}")
                    except:
                        pass
            
            logger.info(f"\n✓ 기본 모델 사용 가능!")
            logger.info(f"   UI에서 '{test_name_1}' 지식베이스를 확인하여")
            logger.info(f"   어떤 임베딩 모델이 설정되었는지 확인하세요.")
        
        except Exception as e:
            logger.error(f"✗ 기본 모델 생성 실패: {e}")
        
        # 테스트 2: 다양한 모델 이름 시도
        logger.info(f"\n{'='*80}")
        logger.info(f"테스트 2: 다양한 모델 이름 시도")
        logger.info(f"{'='*80}")
        
        model_candidates = [
            "qwen3-embedding:8b",           # 원래 시도한 이름
            "qwen3-embedding",              # 버전 없이
            "BAAI/bge-large-zh-v1.5",       # 일반적인 다국어 모델
            "BAAI/bge-small-zh-v1.5",       # 작은 모델
            "text-embedding-ada-002",       # OpenAI 모델
            "embedding-001",                # 간단한 이름
        ]
        
        for model_name in model_candidates:
            test_name = f"Model_Test_{model_name.replace('/', '_').replace(':', '_')}_{int(time.time())}"
            logger.info(f"\n시도: {model_name}")
            
            try:
                dataset = rag.create_dataset(
                    name=test_name,
                    description=f"모델 테스트: {model_name}",
                    embedding_model=model_name
                )
                logger.info(f"   ✓ 성공! - {model_name}")
                logger.info(f"      Dataset ID: {dataset.id}")
                
                # 이 모델로 실제 파일 업로드 및 파싱 테스트
                logger.info(f"   파싱 테스트 시작...")
                
                # 간단한 테스트 파일 업로드
                from io import BytesIO
                test_content = f"테스트 파일 - 모델: {model_name}"
                file_stream = BytesIO(test_content.encode('utf-8'))
                file_stream.name = "test.txt"
                file_stream.seek(0)
                
                docs = dataset.upload_documents([{
                    "display_name": "test.txt",
                    "blob": file_stream
                }])
                file_stream.close()
                
                if docs and len(docs) > 0:
                    # 파싱 시도
                    dataset.async_parse_documents([docs[0].id])
                    time.sleep(3)
                    
                    # 상태 확인
                    docs_after = dataset.list_documents()
                    if docs_after and len(docs_after) > 0:
                        status = docs_after[0].run
                        if status == "FAIL":
                            logger.warning(f"   ⚠ 파싱 실패")
                            logger.warning(f"      메시지: {docs_after[0].progress_msg}")
                        elif status in ["RUNNING", "DONE"]:
                            logger.info(f"   ✓ 파싱 성공 또는 진행 중 (status: {status})")
                            logger.info(f"   ✅ 이 모델 사용 가능: {model_name}")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"   ✗ 실패 - {error_msg[:100]}")
        
        logger.info(f"\n{'='*80}")
        logger.info("테스트 완료")
        logger.info(f"{'='*80}")
        logger.info(f"\n다음 단계:")
        logger.info(f"1. RAGFlow UI에 접속")
        logger.info(f"2. 생성된 'Model_Test_*' 지식베이스들 확인")
        logger.info(f"3. 파싱이 성공한 지식베이스의 임베딩 모델 확인")
        logger.info(f"4. 해당 모델 이름을 .env의 EMBEDDING_MODEL에 설정")
        logger.info(f"5. 테스트 지식베이스들 삭제")
    
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    check_available_models()

