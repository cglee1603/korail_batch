"""
배치 프로세서 - 전체 프로세스 조율
"""
from pathlib import Path
from typing import Dict, List, Optional
from excel_processor import ExcelProcessor
from file_handler import FileHandler
from ragflow_client import RAGFlowClient  # HTTP API 클라이언트
from logger import logger
from config import (
    EXCEL_FILE_PATH, 
    DATASET_PERMISSION, 
    EMBEDDING_MODEL,
    DATA_SOURCE,
    DB_CONNECTION_STRING,
    CHUNK_METHOD,
    PARSER_CONFIG
)


class BatchProcessor:
    """배치 처리 메인 클래스"""
    
    def __init__(self, excel_path: str = None, data_source: str = None):
        """
        Args:
            excel_path: 엑셀 파일 경로
            data_source: 데이터 소스 ("excel", "db", "both")
        """
        self.excel_path = excel_path or EXCEL_FILE_PATH
        self.data_source = data_source or DATA_SOURCE
        
        # 프로세서 초기화
        self.excel_processor = None
        self.db_processor = None
        
        # Excel 소스
        if self.data_source in ['excel', 'both']:
            self.excel_processor = ExcelProcessor(self.excel_path)
        
        # DB 소스
        if self.data_source in ['db', 'both']:
            self._init_db_processor()
        
        self.file_handler = FileHandler()
        self.ragflow_client = RAGFlowClient()
        
        self.stats = {
            'total_sheets': 0,
            'total_files': 0,
            'successful_uploads': 0,
            'failed_uploads': 0,
            'datasets_created': 0
        }
    
    def _init_db_processor(self):
        """DB 프로세서 초기화"""
        try:
            from db_connector import DBConnector
            from db_processor import DBProcessor
            
            # DB 연결 문자열 확인
            if not DB_CONNECTION_STRING:
                logger.warning("DB 연결 문자열이 설정되지 않았습니다. DB 처리를 건너뜁니다.")
                self.data_source = 'excel'  # 강제로 Excel만 처리
                return
            
            connector = DBConnector(connection_string=DB_CONNECTION_STRING)
            self.db_processor = DBProcessor(connector)
            logger.info(f"DB 프로세서 초기화 완료")
        
        except ImportError as e:
            logger.error(f"DB 모듈 import 실패: {e}")
            logger.error("필요한 패키지를 설치하세요: pip install sqlalchemy psycopg2-binary pymysql")
            self.data_source = 'excel'
        except Exception as e:
            logger.error(f"DB 프로세서 초기화 실패: {e}")
            self.data_source = 'excel'
    
    def process(self):
        """배치 프로세스 실행"""
        logger.info("="*80)
        logger.info("배치 프로세스 시작")
        logger.info(f"데이터 소스: {self.data_source.upper()}")
        if self.data_source in ['excel', 'both']:
            logger.info(f"엑셀 파일: {self.excel_path}")
        logger.info("="*80)
        
        try:
            # 데이터 수집
            all_data = {}
            
            # 1. Excel 데이터 추출
            if self.data_source in ['excel', 'both'] and self.excel_processor:
                logger.info("\n[Excel 데이터 처리]")
                sheet_data = self.excel_processor.process_all_sheets()
                all_data.update(sheet_data)
                self.stats['total_sheets'] += len(sheet_data)
            
            # 2. DB 데이터 추출
            if self.data_source in ['db', 'both'] and self.db_processor:
                logger.info("\n[DB 데이터 처리]")
                db_data = self.db_processor.process(query_name="DB_Query")
                all_data.update(db_data)
                self.stats['total_sheets'] += len(db_data)
            
            if not all_data:
                logger.error("처리할 데이터가 없습니다.")
                return
            
            # 3. 시트/쿼리별로 처리
            for dataset_name, items in all_data.items():
                self.process_sheet(dataset_name, items)
            
            # 4. 임시 파일 정리
            self.file_handler.cleanup_temp()
            
            # 5. 통계 출력
            self.print_statistics()
        
        except Exception as e:
            logger.error(f"배치 프로세스 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        finally:
            # 리소스 정리
            if self.excel_processor:
                self.excel_processor.close()
            if self.db_processor and self.db_processor.connector:
                self.db_processor.connector.close()
            
            logger.info("="*80)
            logger.info("배치 프로세스 종료")
            logger.info("="*80)
    
    def process_sheet(self, sheet_name: str, items: List[Dict]):
        """
        시트 단위 처리
        
        Args:
            sheet_name: 시트 이름
            items: 하이퍼링크와 메타데이터 목록
        """
        if not items:
            logger.warning(f"시트 '{sheet_name}'에 처리할 항목이 없습니다.")
            return
        
        logger.log_sheet_start(sheet_name)
        
        try:
            # 시트별 지식베이스 생성
            dataset_name = f"{sheet_name}"
            dataset_description = f"엑셀 시트 '{sheet_name}'에서 자동 생성된 지식베이스"
            
            dataset = self.ragflow_client.get_or_create_dataset(
                name=dataset_name,
                description=dataset_description,
                permission=DATASET_PERMISSION,
                embedding_model=None,  # 시스템 기본값 사용 (tenant.embd_id)
                chunk_method=CHUNK_METHOD,  # GUI와 동일한 청크 방법
                parser_config=PARSER_CONFIG  # GUI와 동일한 파서 설정
            )
            
            if not dataset:
                logger.error(f"지식베이스 생성 실패: {sheet_name}")
                return
            
            self.stats['datasets_created'] += 1
            
            # 각 항목 처리
            uploaded_count = 0
            for item in items:
                if self.process_item(dataset, item):
                    uploaded_count += 1
            
            # 일괄 파싱 시작
            if uploaded_count > 0:
                logger.info(f"시트 '{sheet_name}': {uploaded_count}개 파일 업로드 완료, 일괄 파싱 시작")
                self.ragflow_client.start_batch_parse(dataset)
            
            logger.log_sheet_end(sheet_name, uploaded_count)
        
        except Exception as e:
            logger.error(f"시트 '{sheet_name}' 처리 중 오류: {e}")
    
    def process_item(self, dataset: object, item: Dict) -> bool:
        """
        개별 항목 처리 (파일 다운로드, 변환, 업로드)
        
        Args:
            dataset: Dataset 객체
            item: {'hyperlink': '...', 'metadata': {...}, ...}
        
        Returns:
            성공 여부
        """
        hyperlink = item.get('hyperlink')
        metadata = item.get('metadata', {})
        row_number = item.get('row_number')
        
        if not hyperlink:
            logger.warning(f"{row_number}행: 하이퍼링크가 없습니다.")
            return False
        
        self.stats['total_files'] += 1
        
        try:
            # 1. 파일 가져오기 (다운로드 또는 복사)
            file_path = self.file_handler.get_file(hyperlink)
            
            if not file_path:
                logger.error(f"{row_number}행: 파일 가져오기 실패 - {hyperlink}")
                self.stats['failed_uploads'] += 1
                return False
            
            # 2. 파일 처리 (형식 변환)
            processed_files = self.file_handler.process_file(file_path)
            
            if not processed_files:
                logger.error(f"{row_number}행: 파일 처리 실패 - {file_path.name}")
                self.stats['failed_uploads'] += 1
                return False
            
            # 3. 처리된 파일들을 RAGFlow에 업로드
            upload_success = False
            for processed_path, file_type in processed_files:
                # 메타데이터에 원본 정보 추가
                enhanced_metadata = metadata.copy()
                enhanced_metadata['원본_파일'] = file_path.name
                enhanced_metadata['파일_형식'] = file_type
                enhanced_metadata['엑셀_행번호'] = str(row_number)
                enhanced_metadata['하이퍼링크'] = hyperlink
                
                # 업로드
                success = self.ragflow_client.upload_document(
                    dataset=dataset,
                    file_path=processed_path,
                    metadata=enhanced_metadata,
                    display_name=processed_path.name
                )
                
                if success:
                    upload_success = True
                    self.stats['successful_uploads'] += 1
                    logger.log_file_process(
                        processed_path.name, 
                        "업로드 성공",
                        f"형식: {file_type}, 행: {row_number}"
                    )
                else:
                    self.stats['failed_uploads'] += 1
                    logger.log_file_process(
                        processed_path.name, 
                        "업로드 실패",
                        f"형식: {file_type}, 행: {row_number}"
                    )
            
            return upload_success
        
        except Exception as e:
            logger.error(f"{row_number}행 처리 중 오류: {e}")
            self.stats['failed_uploads'] += 1
            return False
    
    def print_statistics(self):
        """처리 통계 출력"""
        logger.info("="*80)
        logger.info("배치 처리 통계")
        logger.info("-"*80)
        logger.info(f"처리된 시트 수: {self.stats['total_sheets']}")
        logger.info(f"생성된 지식베이스 수: {self.stats['datasets_created']}")
        logger.info(f"총 파일 수: {self.stats['total_files']}")
        logger.info(f"업로드 성공: {self.stats['successful_uploads']}")
        logger.info(f"업로드 실패: {self.stats['failed_uploads']}")
        
        if self.stats['total_files'] > 0:
            success_rate = (self.stats['successful_uploads'] / self.stats['total_files']) * 100
            logger.info(f"성공률: {success_rate:.1f}%")
        
        logger.info("="*80)

