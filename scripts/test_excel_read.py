"""
엑셀 파일 읽기 테스트 스크립트
첨부된 샘플 엑셀 파일로 테스트
"""
import sys
from pathlib import Path

# src 디렉토리를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from excel_processor import ExcelProcessor
from logger import logger


def test_excel_processing(excel_path: str):
    """엑셀 파일 처리 테스트"""
    logger.info("="*80)
    logger.info("엑셀 파일 읽기 테스트 시작")
    logger.info(f"파일: {excel_path}")
    logger.info("="*80)
    
    # 엑셀 프로세서 생성
    processor = ExcelProcessor(excel_path)
    
    # 모든 시트 처리
    all_results = processor.process_all_sheets()
    
    # 결과 출력
    logger.info("\n" + "="*80)
    logger.info("처리 결과 요약")
    logger.info("="*80)
    
    total_items = 0
    for sheet_name, items in all_results.items():
        logger.info(f"\n[시트: {sheet_name}]")
        logger.info(f"  항목 수: {len(items)}")
        
        for idx, item in enumerate(items, 1):
            logger.info(f"\n  항목 {idx}:")
            logger.info(f"    행번호: {item['row_number']}")
            logger.info(f"    하이퍼링크: {item['hyperlink']}")
            logger.info(f"    메타데이터:")
            for key, value in item['metadata'].items():
                logger.info(f"      {key}: {value}")
        
        total_items += len(items)
    
    logger.info("\n" + "="*80)
    logger.info(f"총 시트 수: {len(all_results)}")
    logger.info(f"총 항목 수: {total_items}")
    logger.info("="*80)
    
    # 워크북 닫기
    processor.close()


def main():
    """메인 함수"""
    # 샘플 엑셀 파일 경로
    sample_excel = Path("../sample_excel/20250515_KTX-DATA_EMU.xlsx")
    
    if not sample_excel.exists():
        logger.error(f"샘플 엑셀 파일을 찾을 수 없습니다: {sample_excel}")
        logger.error("경로를 확인하거나 다른 파일을 지정하세요.")
        sys.exit(1)
    
    # 테스트 실행
    test_excel_processing(str(sample_excel))


if __name__ == "__main__":
    main()

