"""
RAGFlow 연결 및 지식베이스 테스트 스크립트
"""
import sys
from pathlib import Path

# src 디렉토리를 Python 경로에 추가
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from ragflow_sdk import RAGFlow
from config import RAGFLOW_API_KEY, RAGFLOW_BASE_URL
from logger import logger


def test_connection():
    """RAGFlow 연결 테스트"""
    logger.info("="*80)
    logger.info("RAGFlow 연결 테스트 시작")
    logger.info("="*80)
    
    try:
        # 설정 정보 출력
        logger.info(f"API URL: {RAGFLOW_BASE_URL}")
        logger.info(f"API KEY 설정 여부: {'예' if RAGFLOW_API_KEY else '아니오'}")
        if RAGFLOW_API_KEY:
            logger.info(f"API KEY 길이: {len(RAGFLOW_API_KEY)}")
            logger.info(f"API KEY 앞 10자: {RAGFLOW_API_KEY[:10]}...")
        
        # RAGFlow 클라이언트 생성
        logger.info("\n1. RAGFlow 클라이언트 초기화 중...")
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        logger.info("✓ 클라이언트 초기화 성공")
        
        # 지식베이스 목록 가져오기 (전체)
        logger.info("\n2. 전체 지식베이스 목록 조회 중...")
        all_datasets = rag.list_datasets()
        logger.info(f"✓ 총 {len(all_datasets) if all_datasets else 0}개 지식베이스 발견")
        
        if all_datasets:
            logger.info("\n지식베이스 목록:")
            for i, ds in enumerate(all_datasets[:10], 1):  # 최대 10개만 출력
                logger.info(f"  {i}. {ds.name if hasattr(ds, 'name') else 'Unknown'}")
                if hasattr(ds, 'id'):
                    logger.info(f"     - ID: {ds.id}")
                
                # 각 지식베이스 접근 테스트
                try:
                    docs = ds.list_documents()
                    logger.info(f"     - 문서 수: {len(docs) if docs else 0}")
                    logger.info(f"     - 소유권: 접근 가능 ✓")
                except Exception as e:
                    logger.warning(f"     - 소유권: 접근 불가 ✗ ({e})")
        
        # 특정 이름 검색 테스트
        logger.info("\n3. 특정 이름으로 검색 테스트...")
        test_names = ["KTX-EMU 매뉴얼", "2. KTX-EMU 외주수선설명서"]
        
        for name in test_names:
            logger.info(f"\n검색: '{name}'")
            datasets = rag.list_datasets(name=name)
            
            if datasets and len(datasets) > 0:
                logger.info(f"  - 발견됨: {len(datasets)}개")
                for ds in datasets:
                    logger.info(f"  - 이름: {ds.name if hasattr(ds, 'name') else 'Unknown'}")
                    
                    # 접근 테스트
                    try:
                        docs = ds.list_documents()
                        logger.info(f"  - 소유권: 접근 가능 ✓")
                    except Exception as e:
                        logger.warning(f"  - 소유권: 접근 불가 ✗")
                        logger.warning(f"  - 에러: {e}")
            else:
                logger.info(f"  - 발견되지 않음")
        
        # 새 지식베이스 생성 테스트
        logger.info("\n4. 새 지식베이스 생성 테스트...")
        test_kb_name = f"테스트_KB_{Path(__file__).name}"
        
        try:
            logger.info(f"생성 시도: '{test_kb_name}'")
            test_ds = rag.create_dataset(
                name=test_kb_name,
                description="연결 테스트용 임시 지식베이스"
            )
            logger.info(f"✓ 생성 성공: {test_ds.name if hasattr(test_ds, 'name') else 'Unknown'}")
            
            # 생성된 지식베이스 삭제
            try:
                test_ds.delete()
                logger.info("✓ 테스트 지식베이스 삭제 완료")
            except:
                logger.warning("테스트 지식베이스 삭제 실패 (수동 삭제 필요)")
        
        except Exception as e:
            logger.error(f"✗ 생성 실패: {e}")
        
        logger.info("\n" + "="*80)
        logger.info("테스트 완료")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())


def test_updated_code():
    """업데이트된 코드 확인"""
    logger.info("\n" + "="*80)
    logger.info("ragflow_client.py 업데이트 확인")
    logger.info("="*80)
    
    try:
        # ragflow_client.py 파일 읽기
        client_file = Path(__file__).parent / "src" / "ragflow_client.py"
        
        if not client_file.exists():
            logger.error(f"파일을 찾을 수 없습니다: {client_file}")
            return
        
        with open(client_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 수정된 코드 확인
        checks = [
            ("소유권 확인 로직", "_ = dataset.list_documents()"),
            ("접근 불가 경고", "지식베이스 '{name}'는 다른 사용자 소유입니다"),
            ("이름 중복 처리", "새 이름으로 재시도"),
            ("타임스탬프 추가", "timestamp = datetime.now().strftime"),
        ]
        
        logger.info("\n코드 업데이트 확인:")
        all_updated = True
        for check_name, check_text in checks:
            if check_text in content:
                logger.info(f"  ✓ {check_name}: 포함됨")
            else:
                logger.warning(f"  ✗ {check_name}: 누락됨")
                all_updated = False
        
        if all_updated:
            logger.info("\n✓ 모든 수정사항이 반영되었습니다.")
        else:
            logger.warning("\n✗ 일부 수정사항이 누락되었습니다. 파일을 다시 확인하세요.")
        
        # 파일 수정 시간 확인
        import os
        import time
        mtime = os.path.getmtime(client_file)
        mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
        logger.info(f"\n파일 수정 시간: {mtime_str}")
        
    except Exception as e:
        logger.error(f"코드 확인 실패: {e}")
    
    logger.info("="*80)


if __name__ == "__main__":
    # 1. 업데이트된 코드 확인
    test_updated_code()
    
    # 2. RAGFlow 연결 테스트
    test_connection()

