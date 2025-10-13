"""
지식베이스 생성 테스트 - 다양한 이름 패턴 테스트
"""
import sys
from pathlib import Path

# src 디렉토리를 Python 경로에 추가
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from ragflow_sdk import RAGFlow
from config import RAGFLOW_API_KEY, RAGFLOW_BASE_URL
from logger import logger


def test_create_various_names():
    """다양한 이름으로 지식베이스 생성 테스트"""
    logger.info("="*80)
    logger.info("지식베이스 생성 테스트")
    logger.info("="*80)
    
    try:
        # RAGFlow 클라이언트 생성
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        logger.info(f"✓ RAGFlow 연결 성공")
        
        # 테스트할 이름들
        test_names = [
            ("영문만", "TEST_KB_001"),
            ("숫자만", "123456"),
            ("한글만", "테스트지식베이스"),
            ("한글+영문", "테스트TEST"),
            ("한글+숫자", "테스트123"),
            ("공백포함", "테스트 지식베이스"),
            ("특수문자-", "테스트-KB"),
            ("문제이름", "KTX-EMU 매뉴얼"),
        ]
        
        created_datasets = []
        
        for test_type, test_name in test_names:
            logger.info(f"\n{'='*60}")
            logger.info(f"테스트: {test_type} - '{test_name}'")
            logger.info(f"{'='*60}")
            
            try:
                # 1. 검색 테스트
                logger.info(f"1. 검색 시도...")
                try:
                    datasets = rag.list_datasets(name=test_name)
                    logger.info(f"   ✓ 검색 성공: {len(datasets) if datasets else 0}개 발견")
                    
                    if datasets and len(datasets) > 0:
                        logger.info(f"   이미 존재함. 생성 건너뛰기")
                        continue
                        
                except Exception as search_error:
                    logger.warning(f"   ✗ 검색 실패: {search_error}")
                
                # 2. 생성 테스트
                logger.info(f"2. 생성 시도...")
                try:
                    dataset = rag.create_dataset(
                        name=test_name,
                        description=f"테스트용 ({test_type})"
                    )
                    logger.info(f"   ✓ 생성 성공!")
                    logger.info(f"   - ID: {dataset.id if hasattr(dataset, 'id') else 'N/A'}")
                    logger.info(f"   - 이름: {dataset.name if hasattr(dataset, 'name') else 'N/A'}")
                    created_datasets.append(dataset)
                    
                except Exception as create_error:
                    logger.error(f"   ✗ 생성 실패: {create_error}")
                    
                    # 에러 메시지 상세 분석
                    error_msg = str(create_error)
                    logger.info(f"   에러 분석:")
                    logger.info(f"   - 'already exists' 포함: {'already exists' in error_msg.lower()}")
                    logger.info(f"   - 'duplicate' 포함: {'duplicate' in error_msg.lower()}")
                    logger.info(f"   - \"don't own\" 포함: {\"don't own\" in error_msg.lower()}")
                    logger.info(f"   - 'permission' 포함: {'permission' in error_msg.lower()}")
            
            except Exception as e:
                logger.error(f"테스트 실패: {e}")
        
        # 3. 생성된 지식베이스 정리
        logger.info(f"\n{'='*80}")
        logger.info(f"정리: 생성된 지식베이스 삭제")
        logger.info(f"{'='*80}")
        
        for dataset in created_datasets:
            try:
                name = dataset.name if hasattr(dataset, 'name') else 'Unknown'
                logger.info(f"삭제 시도: {name}")
                dataset.delete()
                logger.info(f"   ✓ 삭제 완료")
            except Exception as e:
                logger.warning(f"   ✗ 삭제 실패: {e}")
        
        logger.info(f"\n{'='*80}")
        logger.info("테스트 완료")
        logger.info(f"{'='*80}")
        
    except Exception as e:
        logger.error(f"전체 테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


def check_existing_kb():
    """RAGFlow에서 실제 지식베이스 목록 확인"""
    logger.info("\n" + "="*80)
    logger.info("RAGFlow 전체 지식베이스 목록 조회")
    logger.info("="*80)
    
    try:
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        
        # 전체 목록 (이름 필터 없음)
        logger.info("\n1. 전체 지식베이스 목록:")
        all_datasets = rag.list_datasets()
        
        if all_datasets:
            logger.info(f"총 {len(all_datasets)}개 지식베이스:")
            for i, ds in enumerate(all_datasets, 1):
                name = ds.name if hasattr(ds, 'name') else 'Unknown'
                ds_id = ds.id if hasattr(ds, 'id') else 'N/A'
                logger.info(f"{i}. '{name}' (ID: {ds_id})")
                
                # KTX 관련 이름 체크
                if 'KTX' in name.upper() or 'EMU' in name.upper():
                    logger.warning(f"   ⚠ KTX 관련 지식베이스 발견!")
        else:
            logger.info("지식베이스가 없습니다.")
        
        # 2. 문제의 이름으로 직접 검색
        logger.info("\n2. 'KTX-EMU 매뉴얼' 검색 테스트:")
        try:
            target_datasets = rag.list_datasets(name="KTX-EMU 매뉴얼")
            logger.info(f"검색 결과: {len(target_datasets) if target_datasets else 0}개")
        except Exception as e:
            logger.error(f"검색 실패: {e}")
        
        # 3. 유사 이름 검색
        similar_names = [
            "KTX-EMU",
            "KTX",
            "EMU",
            "매뉴얼"
        ]
        
        logger.info("\n3. 유사 이름 검색:")
        for name in similar_names:
            try:
                results = rag.list_datasets(name=name)
                if results and len(results) > 0:
                    logger.info(f"'{name}': {len(results)}개 발견")
                    for ds in results:
                        logger.info(f"  - {ds.name if hasattr(ds, 'name') else 'Unknown'}")
                else:
                    logger.info(f"'{name}': 없음")
            except Exception as e:
                logger.error(f"'{name}' 검색 실패: {e}")
        
    except Exception as e:
        logger.error(f"조회 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    # 1. 기존 지식베이스 확인
    check_existing_kb()
    
    # 2. 다양한 이름으로 생성 테스트
    test_create_various_names()

