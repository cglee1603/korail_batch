"""
RAGFlow Plus 배치 프로그램 메인 스크립트
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime
import schedule
import time
from batch_processor import BatchProcessor
from logger import logger
from config import EXCEL_FILE_PATH, BATCH_SCHEDULE


def run_batch(excel_path: str = None, data_source: str = None):
    """배치 작업 실행"""
    start_time = datetime.now()
    logger.info(f"\n배치 작업 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        processor = BatchProcessor(excel_path=excel_path, data_source=data_source)
        processor.process()
    except Exception as e:
        logger.error(f"배치 작업 실행 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    end_time = datetime.now()
    duration = end_time - start_time
    logger.info(f"배치 작업 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"총 소요 시간: {duration}\n")


def parse_schedule_config(schedule_str: str):
    """
    스케줄 설정 파싱
    
    Examples:
        "10:00" -> 매일 10:00에 실행
        "300" -> 300초마다 실행
        "10:00,14:00,18:00" -> 매일 여러 시간에 실행
    """
    if not schedule_str:
        return None
    
    # 쉼표로 구분된 여러 시간
    if ',' in schedule_str:
        times = [t.strip() for t in schedule_str.split(',')]
        return ('multiple', times)
    
    # 시간 형식 (HH:MM)
    if ':' in schedule_str:
        return ('time', schedule_str)
    
    # 초 단위 간격
    try:
        seconds = int(schedule_str)
        return ('interval', seconds)
    except ValueError:
        logger.error(f"잘못된 스케줄 형식: {schedule_str}")
        return None


def setup_schedule(excel_path: str = None, data_source: str = None):
    """스케줄 설정"""
    schedule_config = parse_schedule_config(BATCH_SCHEDULE)
    
    if not schedule_config:
        logger.warning("스케줄이 설정되지 않았습니다. 1회만 실행합니다.")
        run_batch(excel_path, data_source)
        return False
    
    schedule_type, value = schedule_config
    
    if schedule_type == 'time':
        # 특정 시간에 실행
        schedule.every().day.at(value).do(run_batch, excel_path=excel_path, data_source=data_source)
        logger.info(f"스케줄 설정 완료: 매일 {value}에 실행")
    
    elif schedule_type == 'multiple':
        # 여러 시간에 실행
        for time_str in value:
            schedule.every().day.at(time_str).do(run_batch, excel_path=excel_path, data_source=data_source)
        logger.info(f"스케줄 설정 완료: 매일 {', '.join(value)}에 실행")
    
    elif schedule_type == 'interval':
        # 주기적 실행
        schedule.every(value).seconds.do(run_batch, excel_path=excel_path, data_source=data_source)
        logger.info(f"스케줄 설정 완료: {value}초마다 실행")
    
    return True


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='RAGFlow Plus 배치 프로그램 - Excel/DB에서 데이터를 추출하여 지식베이스에 업로드'
    )
    
    parser.add_argument(
        '--excel',
        type=str,
        default=None,
        help=f'처리할 엑셀 파일 경로 (기본값: {EXCEL_FILE_PATH})'
    )
    
    parser.add_argument(
        '--source',
        type=str,
        choices=['excel', 'db', 'both'],
        default=None,
        help='데이터 소스 선택 (excel: 엑셀만, db: DB만, both: 둘 다)'
    )
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='1회만 실행하고 종료 (스케줄 무시)'
    )
    
    parser.add_argument(
        '--schedule',
        type=str,
        default=None,
        help='실행 스케줄 설정 (예: "10:00" 또는 "300"초)'
    )
    
    args = parser.parse_args()
    
    # 엑셀 파일 경로
    excel_path = args.excel or EXCEL_FILE_PATH
    data_source = args.source
    
    # Excel 소스를 사용하는 경우 파일 존재 확인
    if not data_source or data_source in ['excel', 'both']:
        if not Path(excel_path).exists():
            logger.error(f"엑셀 파일을 찾을 수 없습니다: {excel_path}")
            logger.error("--excel 옵션으로 파일 경로를 지정하거나 .env 파일을 확인하세요.")
            logger.info("또는 --source db 옵션으로 DB만 사용할 수 있습니다.")
            sys.exit(1)
    
    # 1회만 실행
    if args.once:
        logger.info("1회 실행 모드")
        run_batch(excel_path, data_source)
        return
    
    # 스케줄 실행
    logger.info("스케줄 모드로 시작")
    
    # 스케줄 설정
    has_schedule = setup_schedule(excel_path, data_source)
    
    if not has_schedule:
        # 스케줄이 없으면 종료
        return
    
    # 스케줄 실행 루프
    logger.info("스케줄 대기 중... (Ctrl+C로 종료)")
    try:
        while True:
            schedule.run_pending()
            time.sleep(10)  # 10초마다 스케줄 체크
    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 종료되었습니다.")


if __name__ == "__main__":
    main()

