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
from excel_processor import ExcelProcessor
from logger import logger
from config import EXCEL_FILE_PATH, BATCH_SCHEDULE,FILE_SYSTEM_PATH


def run_batch(excel_path: str = None, data_source: str = None, filesystem_path: str = None):
    """배치 작업 실행"""
    start_time = datetime.now()
    logger.info(f"\n배치 작업 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        processor = BatchProcessor(excel_path=excel_path, data_source=data_source, filesystem_path=filesystem_path)
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


def setup_schedule(excel_path: str = None, data_source: str = None, filesystem_path: str = None):
    """스케줄 설정"""
    schedule_config = parse_schedule_config(BATCH_SCHEDULE)
    
    if not schedule_config:
        logger.warning("스케줄이 설정되지 않았습니다. 1회만 실행합니다.")
        run_batch(excel_path, data_source, filesystem_path)
        return False
    
    schedule_type, value = schedule_config
    
    if schedule_type == 'time':
        # 특정 시간에 실행
        schedule.every().day.at(value).do(run_batch, excel_path=excel_path, data_source=data_source, filesystem_path=filesystem_path)
        logger.info(f"스케줄 설정 완료: 매일 {value}에 실행")
    
    elif schedule_type == 'multiple':
        # 여러 시간에 실행
        for time_str in value:
            schedule.every().day.at(time_str).do(run_batch, excel_path=excel_path, data_source=data_source, filesystem_path=filesystem_path)
        logger.info(f"스케줄 설정 완료: 매일 {', '.join(value)}에 실행")
    
    elif schedule_type == 'interval':
        # 주기적 실행
        schedule.every(value).seconds.do(run_batch, excel_path=excel_path, data_source=data_source, filesystem_path=filesystem_path)
        logger.info(f"스케줄 설정 완료: {value}초마다 실행")
    
    return True



def delete_knowledge(dataset_name: str, confirm: bool = False):
    """지식베이스 전량 삭제 (문서 + 파일)"""
    try:
        processor = BatchProcessor()
        
        result = processor.delete_knowledge_by_dataset_name(
            dataset_name=dataset_name,
            confirm=confirm
        )
        
        if result.get('success'):
            if result.get('total_documents', 0) == 0:
                logger.info("\n✓ 삭제할 항목이 없습니다.")
            elif confirm:
                logger.info("\n✓ 지식베이스 전량 삭제가 완료되었습니다.")
                logger.info(f"  - 문서: {result.get('deleted_documents', 0)}개 삭제")
                logger.info(f"  - 파일: {result.get('deleted_files', 0)}개 삭제")
                logger.info(f"  - DB: {result.get('db_deleted', 0)}개 항목 삭제")
                if result.get('failed_documents', 0) > 0 or result.get('failed_files', 0) > 0:
                    logger.warning(f"⚠️  일부 삭제 실패 - 문서: {result.get('failed_documents', 0)}개, 파일: {result.get('failed_files', 0)}개")
            else:
                logger.info(f"\n✓ 삭제 대상 항목:")
                logger.info(f"  - 지식베이스: {result.get('dataset_name')}")
                logger.info(f"  - 문서: {result.get('total_documents')}개")
                logger.info(f"  - 파일: {result.get('total_documents')}개")
                logger.info("\n실제로 삭제하려면 --confirm 옵션을 추가하세요:")
                logger.info(f'  python run.py --deleteKnowledge "{dataset_name}" --confirm')
        else:
            logger.error(f"\n✗ 삭제 실패: {result.get('message', '알 수 없는 오류')}")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"지식베이스 삭제 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


def delete_documents(dataset_name: str, confirm: bool = False):
    """지식베이스 문서 삭제"""
    try:
        processor = BatchProcessor()
        
        result = processor.delete_documents_by_dataset_name(
            dataset_name=dataset_name,
            confirm=confirm
        )
        
        if result.get('success'):
            if result.get('total_documents', 0) == 0:
                logger.info("\n✓ 삭제할 문서가 없습니다.")
            elif confirm:
                logger.info("\n✓ 문서 삭제가 완료되었습니다.")
                if result.get('ragflow_failed', 0) > 0:
                    logger.warning(f"⚠️  일부 문서 삭제 실패: {result.get('ragflow_failed')}개")
            else:
                logger.info(f"\n✓ 삭제 가능한 문서: {result.get('total_documents')}개")
                logger.info("\n실제로 삭제하려면 --confirm 옵션을 추가하세요:")
                logger.info(f'  python run.py --delete "{dataset_name}" --confirm')
        else:
            logger.error(f"\n✗ 삭제 실패: {result.get('message', '알 수 없는 오류')}")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"문서 삭제 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


def sync_dataset(dataset_name: str, fix: bool = False):
    """지식베이스와 DB 동기화"""
    try:
        processor = BatchProcessor()
        
        result = processor.sync_dataset_with_db(
            dataset_name=dataset_name,
            fix=fix
        )
        
        if result.get('success'):
            if not fix and (result.get('orphans') or result.get('ghosts')):
                logger.info("\n불일치 항목이 발견되었습니다. 자동 수정하려면 --fix 옵션을 사용하세요.")
                logger.info(f"  python run.py --sync \"{dataset_name}\" --fix")
        else:
            logger.error(f"\n✗ 동기화 검사 실패")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"동기화 작업 중 오류 발생: {e}")
        sys.exit(1)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='RAGFlow Plus 배치 프로그램 - Excel/DB에서 데이터를 추출하여 지식베이스에 업로드',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 배치 작업 1회 실행
  python run.py --once
  
  # 지식베이스 목록 조회
  python run.py --list
  
  # 문서 삭제 (확인만)
  python run.py --delete "지식베이스_이름"
  
  # 문서 삭제 (실제 삭제)
  python run.py --delete "지식베이스_이름" --confirm
  
  # 지식베이스 전량 삭제 - 문서와 파일 모두 삭제 (확인만)
  python run.py --deleteKnowledge "지식베이스_이름"
  
  # 지식베이스 전량 삭제 - 문서와 파일 모두 삭제 (실제 삭제)
  python run.py --deleteKnowledge "지식베이스_이름" --confirm

  # (검증) 처리 결과 덤프(JSON): 헤더/행을 전체 프로세스로 추출
  python run.py --export-processed --excel "data/20250515_KTX-DATA_EMU.xlsx" --export-outdir "data/temp/processed_dump" --early-stop 10 --once
        """
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
        default=None,
        help='데이터 소스 선택 (excel, db, filesystem 등 콤마로 구분 가능. 예: "excel,db")'
    )

    parser.add_argument(
        '--filesystem-path',
        dest='filesystem_path',
        type=str,
        default=None,
        help='파일시스템 모드용 입력 폴더 경로'
    )
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='1회만 실행하고 종료 (스케줄 무시)'
    )
    
    # === 검증용 익스포트 모드 ===
    parser.add_argument(
        '--export-processed',
        action='store_true',
        help='(검증) 처리 결과 덤프(JSON) 모드'
    )
    parser.add_argument(
        '--export-outdir',
        type=str,
        default=str(Path('data') / 'temp' / 'export'),
        help='익스포트 출력 디렉토리'
    )
    parser.add_argument(
        '--early-stop',
        type=int,
        default=10,
        help='연속 무값 행 N개에서 시트 스캔 중지 (processed 모드)'
    )
    
    parser.add_argument(
        '--schedule',
        type=str,
        default=None,
        help='실행 스케줄 설정 (예: "10:00" 또는 "300"초)'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='지식베이스 목록 조회'
    )
    
    parser.add_argument(
        '--check-and-parse',
        type=str,
        metavar='DATASET_NAME',
        help='문서 상태 확인 후 파싱 (Failed 제외) (예: --check-and-parse "시트1")'
    )
    
    parser.add_argument(
        '--cancel-parsing',
        type=str,
        metavar='DATASET_NAME',
        help='파싱 중(Running)인 문서 취소(삭제) (예: --cancel-parsing "시트1")'
    )
    
    parser.add_argument(
        '--delete',
        type=str,
        metavar='DATASET_NAME',
        help='지식베이스 문서 삭제 (예: --delete "시트1")'
    )
    
    parser.add_argument(
        '--deleteKnowledge',
        type=str,
        metavar='DATASET_NAME',
        help='지식베이스 전량 삭제 - 문서와 파일 모두 삭제 (예: --deleteKnowledge "시트1")'
    )
    
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='삭제 확인 (--delete 또는 --deleteKnowledge와 함께 사용)'
    )
    
    parser.add_argument(
        '--sync',
        type=str,
        metavar='DATASET_NAME',
        help='지식베이스와 DB 동기화 검사 (예: --sync "시트1")'
    )

    parser.add_argument(
        '--fix',
        action='store_true',
        help='동기화 불일치 자동 수정 (--sync와 함께 사용)'
    )
    
    args = parser.parse_args()

    # 공통 입력 경로/소스 우선 설정 (익스포트 모드에서도 사용)
    excel_path = args.excel or EXCEL_FILE_PATH
    data_source = args.source
    filesystem_path = args.filesystem_path or FILE_SYSTEM_PATH
    
    # === (우선) 검증용 익스포트 모드: 항상 1회 실행 후 종료 ===
    if args.export_processed:
        if not Path(excel_path).exists():
            logger.error(f"엑셀 파일을 찾을 수 없습니다: {excel_path}")
            sys.exit(1)
        proc = ExcelProcessor(excel_path)
        if not proc.load_workbook():
            sys.exit(1)
        outdir = Path(args.export_outdir)
        if args.export_processed:
            logger.info(f"[EXPORT-PROCESSED] {excel_path} → {outdir} (early-stop={args.early_stop})")
            for sheet_name in proc.get_sheet_names():
                try:
                    # 숨김 시트는 건너뛴다
                    sheet = proc.workbook[sheet_name]
                    if getattr(sheet, 'sheet_state', None) in ('hidden', 'veryHidden'):
                        logger.info(f"시트 '{sheet_name}'는 숨김 처리되어 건너뜁니다.")
                        continue

                    stype, items, headers = proc.process_sheet(sheet_name, early_stop_no_value=args.early_stop)
                    data = {
                        'sheet_name': sheet_name,
                        'sheet_type': stype.value if hasattr(stype, 'value') else str(stype),
                        'headers': headers,
                        'total_items': len(items),
                        'items': items,
                    }
                    outdir.mkdir(parents=True, exist_ok=True)
                    safe = ''.join(ch if ch not in '\\/:*?"<>|' else '_' for ch in sheet_name).strip() or 'sheet'
                    out_file = outdir / f"{safe}.processed.json"
                    with out_file.open('w', encoding='utf-8') as f:
                        import json
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    logger.info(f"시트 '{sheet_name}' 처리 결과 저장: {out_file}")
                except Exception as e:
                    logger.error(f"시트 '{sheet_name}' 처리 중 오류: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        proc.close()
        return

    # 1회만 실행
    if args.once:
        logger.info("1회 실행 모드")
        run_batch(excel_path, data_source, filesystem_path)
        return
    
    # 지식베이스 목록 조회
    if args.list:
        from ragflow_client import RAGFlowClient
        client = RAGFlowClient()
        datasets = client.list_datasets(page=1, page_size=100)
        logger.info(f"\n지식베이스 목록 (총 {len(datasets)}개):")
        for ds in datasets:
            logger.info(f"  - {ds.get('name')} (ID: {ds.get('id')})")
        return

    # 상태 확인 후 파싱 (Failed 제외)
    if args.check_and_parse:
        processor = BatchProcessor()
        processor.parse_non_failed_documents_by_dataset_name(args.check_and_parse)
        return

    # 파싱 취소
    if args.cancel_parsing:
        processor = BatchProcessor()
        processor.cancel_parsing_documents_by_dataset_name(args.cancel_parsing, args.confirm)
        return

    # 지식베이스 삭제
    if args.deleteKnowledge:
        delete_knowledge(args.deleteKnowledge, args.confirm)
        return

    # 문서 삭제
    if args.delete:
        delete_documents(args.delete, args.confirm)
        return

    # 동기화
    if args.sync:
        sync_dataset(args.sync, args.fix)
        return
    
    # 스케줄 실행
    logger.info("스케줄 모드로 시작")
    
    # 스케줄 설정
    has_schedule = setup_schedule(excel_path, data_source, filesystem_path)
    
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

