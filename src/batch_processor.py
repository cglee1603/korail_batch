"""
배치 프로세서 - 전체 프로세스 조율
"""
import time
from pathlib import Path
from typing import Dict, List, Optional
from excel_processor import ExcelProcessor, SheetType
from file_handler import FileHandler
from ragflow_client import RAGFlowClient  # HTTP API 클라이언트
from revision_db import RevisionDB  # Revision 관리 DB
from logger import logger
from config import (
    EXCEL_FILE_PATH, 
    DATASET_PERMISSION, 
    EMBEDDING_MODEL,
    DATA_SOURCE,
    DB_CONNECTION_STRING,
    CHUNK_METHOD,
    PARSER_CONFIG,
    MONITOR_PARSE_PROGRESS,
    PARSE_TIMEOUT_MINUTES,
    ENABLE_REVISION_MANAGEMENT,
    SKIP_SAME_REVISION,
    DELETE_BEFORE_UPLOAD,
    HISTORY_SHEET_UPLOAD_FORMAT,
    TEMP_DIR
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
        self.revision_db = RevisionDB()  # Revision 관리 DB
        
        self.stats = {
            'total_sheets': 0,
            'skipped_sheets': 0,  # 목차 등
            'revision_sheets': 0,  # REV/작성버전 관리
            'attachment_sheets': 0,  # 첨부파일
            'history_sheets': 0,  # 이력관리+소프트웨어
            
            'new_documents': 0,  # 신규 문서
            'updated_documents': 0,  # 업데이트된 문서
            'skipped_documents': 0,  # 동일 revision
            'deleted_documents': 0,  # 삭제된 문서
            'failed_deletions': 0,  # 삭제 실패
            
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
            # FileHandler를 전달하여 DB 데이터를 PDF로 변환
            self.db_processor = DBProcessor(connector, file_handler=self.file_handler)
            logger.info(f"DB 프로세서 초기화 완료 (PDF 변환 지원)")
        
        except ImportError as e:
            logger.error(f"DB 모듈 import 실패: {e}")
            logger.error("필요한 패키지를 설치하세요: pip install sqlalchemy psycopg2-binary pymysql")
            self.data_source = 'excel'
        except Exception as e:
            logger.error(f"DB 프로세서 초기화 실패: {e}")
            self.data_source = 'excel'
    
    def is_revision_newer(self, old_rev: str, new_rev: str) -> bool:
        """
        두 revision을 비교하여 새 버전인지 판단
        
        Args:
            old_rev: 기존 revision
            new_rev: 새 revision
        
        Returns:
            True if new_rev가 old_rev보다 최신
            
        Note:
            - REV 형식: A, A1, C1, D4 (알파벳 + 숫자)
            - 작성버전 형식: R1, R0, R16 (R + 숫자)
            - 점 버전: 1.0, 2.0, 1.1.0
        """
        if old_rev == new_rev:
            return False
        
        import re
        
        try:
            # 1. 작성버전 형식: R + 숫자 (예: R1, R0, R16)
            if old_rev.upper().startswith('R') and new_rev.upper().startswith('R'):
                try:
                    old_num = int(old_rev[1:])
                    new_num = int(new_rev[1:])
                    result = new_num > old_num
                    logger.debug(f"작성버전 비교: {old_rev}({old_num}) vs {new_rev}({new_num}) → {'최신' if result else '동일/이전'}")
                    return result
                except ValueError:
                    pass
            
            # 2. REV 형식: 알파벳 + 숫자 (예: A, A1, C1, D4)
            # 패턴: 알파벳(대문자) + 선택적 숫자
            rev_pattern = re.compile(r'^([A-Z]+)(\d*)$', re.IGNORECASE)
            old_match = rev_pattern.match(old_rev)
            new_match = rev_pattern.match(new_rev)
            
            if old_match and new_match:
                old_letter = old_match.group(1).upper()
                old_number = int(old_match.group(2)) if old_match.group(2) else 0
                new_letter = new_match.group(1).upper()
                new_number = int(new_match.group(2)) if new_match.group(2) else 0
                
                # 알파벳 먼저 비교
                if new_letter > old_letter:
                    logger.debug(f"REV 비교: {old_rev}({old_letter}{old_number}) vs {new_rev}({new_letter}{new_number}) → 최신 (알파벳)")
                    return True
                elif new_letter < old_letter:
                    logger.debug(f"REV 비교: {old_rev}({old_letter}{old_number}) vs {new_rev}({new_letter}{new_number}) → 이전 (알파벳)")
                    return False
                else:
                    # 알파벳이 같으면 숫자 비교
                    result = new_number > old_number
                    logger.debug(f"REV 비교: {old_rev}({old_letter}{old_number}) vs {new_rev}({new_letter}{new_number}) → {'최신' if result else '동일/이전'} (숫자)")
                    return result
            
            # 3. 점 버전 형식 비교 (1.0, 2.0, 1.1.0)
            if '.' in old_rev or '.' in new_rev:
                old_parts = old_rev.split('.')
                new_parts = new_rev.split('.')
                
                # 숫자로 변환 가능한 경우
                try:
                    for i in range(max(len(old_parts), len(new_parts))):
                        old_num = int(old_parts[i]) if i < len(old_parts) else 0
                        new_num = int(new_parts[i]) if i < len(new_parts) else 0
                        
                        if new_num > old_num:
                            return True
                        elif new_num < old_num:
                            return False
                    
                    # 모두 같으면 False
                    return False
                
                except (ValueError, IndexError):
                    # 숫자 변환 실패
                    pass
            
            # 4. 순수 숫자 비교
            try:
                return float(new_rev) > float(old_rev)
            except ValueError:
                pass
            
            # 5. 문자열 사전식 비교 (폴백)
            logger.debug(f"Revision 비교 (사전식): {old_rev} vs {new_rev}")
            return new_rev > old_rev
        
        except Exception as e:
            logger.warning(f"Revision 비교 실패 (old: {old_rev}, new: {new_rev}): {e}")
            # 비교 실패 시 업데이트로 간주
            return True
    
    def process(self):
        """배치 프로세스 실행"""
        logger.info("="*80)
        logger.info("배치 프로세스 시작")
        logger.info(f"데이터 소스: {self.data_source.upper()}")
        if self.data_source in ['excel', 'both']:
            logger.info(f"엑셀 파일: {self.excel_path}")
        logger.info(f"Revision 관리: {'활성화' if ENABLE_REVISION_MANAGEMENT else '비활성화'}")
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
                # DB 데이터는 기존 형식이므로 변환
                for sheet_name, items in db_data.items():
                    all_data[sheet_name] = (SheetType.ATTACHMENT, items, [])
                self.stats['total_sheets'] += len(db_data)
            
            if not all_data:
                logger.error("처리할 데이터가 없습니다.")
                return
            
            # 3. 시트 타입별로 처리
            for sheet_name, (sheet_type, items, headers) in all_data.items():
                logger.info(f"\n{'='*60}")
                logger.info(f"시트 처리 시작: {sheet_name} (타입: {sheet_type.value})")
                logger.info(f"{'='*60}")
                
                # 시트 타입별 분기 처리
                if sheet_type == SheetType.TOC:
                    # 목차 시트 - 건너뛰기
                    logger.info(f"[{sheet_name}] 목차 시트입니다. 처리를 건너뜁니다.")
                    self.stats['skipped_sheets'] += 1
                
                elif sheet_type in [SheetType.REV_MANAGED, SheetType.VERSION_MANAGED]:
                    # REV/작성버전 관리 시트
                    self.stats['revision_sheets'] += 1
                    self.process_sheet_with_revision(sheet_name, sheet_type, items, headers)
                
                elif sheet_type == SheetType.ATTACHMENT:
                    # 첨부파일 시트 (기존 방식)
                    self.stats['attachment_sheets'] += 1
                    self.process_sheet_attachments(sheet_name, items)
                
                elif sheet_type in [SheetType.HISTORY, SheetType.SOFTWARE]:
                    # 이력관리/소프트웨어 형상기록 시트
                    self.stats['history_sheets'] += 1
                    self.process_sheet_as_text(sheet_name, sheet_type)
                
                elif sheet_type == SheetType.UNKNOWN:
                    # 미분류 시트 - 첨부파일로 처리
                    logger.warning(f"[{sheet_name}] 미분류 시트입니다. 첨부파일 방식으로 처리합니다.")
                    self.stats['attachment_sheets'] += 1
                    self.process_sheet_attachments(sheet_name, items)
            
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
    
    def process_sheet_with_revision(
        self, 
        sheet_name: str, 
        sheet_type: SheetType,
        items: List[Dict], 
        headers: List[str],
        monitor_progress: bool = True
    ):
        """
        Revision 관리 시트 처리 (REV/작성버전)
        
        Args:
            sheet_name: 시트 이름
            sheet_type: 시트 타입
            items: 항목 목록 (document_key, revision 포함)
            headers: 헤더 리스트
            monitor_progress: 파싱 진행 상황 모니터링 여부
        """
        if not items:
            logger.warning(f"시트 '{sheet_name}'에 처리할 항목이 없습니다.")
            return
        
        logger.info(f"[{sheet_name}] Revision 관리 시트 처리 시작 (항목 수: {len(items)})")
        
        try:
            # 지식베이스 생성
            dataset_name = f"{sheet_name}"
            dataset_description = f"엑셀 시트 '{sheet_name}'에서 자동 생성된 지식베이스 (Revision 관리)"
            
            dataset = self.ragflow_client.get_or_create_dataset(
                name=dataset_name,
                description=dataset_description,
                permission=DATASET_PERMISSION,
                embedding_model=None,
                chunk_method=CHUNK_METHOD,
                parser_config=PARSER_CONFIG
            )
            
            if not dataset:
                logger.error(f"지식베이스 생성 실패: {sheet_name}")
                return
            
            self.stats['datasets_created'] += 1
            
            # Revision 관리가 활성화된 경우: RevisionDB에서 기존 문서 목록 조회
            existing_docs_map = {}  # document_key -> {doc_id, revision, ...}
            dataset_id = dataset.get('id')
            
            if ENABLE_REVISION_MANAGEMENT:
                logger.info(f"[{sheet_name}] RevisionDB에서 기존 문서 목록 조회 중...")
                db_docs = self.revision_db.get_all_documents(dataset_id=dataset_id)
                
                # 문서를 document_key로 매핑
                for doc in db_docs:
                    doc_key = doc.get('document_key')
                    if doc_key:
                        existing_docs_map[doc_key] = {
                            'doc_id': doc.get('document_id'),
                            'revision': doc.get('revision'),
                            'name': doc.get('file_name')
                        }
                
                logger.info(f"[{sheet_name}] RevisionDB에서 기존 문서 {len(existing_docs_map)}개 발견")
            
            # 각 항목 처리
            uploaded_count = 0
            for item in items:
                document_key = item.get('document_key')
                new_revision = item.get('revision')
                
                if not document_key:
                    logger.warning(f"행 {item.get('row_number')}: document_key가 없습니다. 건너뜁니다.")
                    continue
                
                # Revision 비교 및 처리
                if ENABLE_REVISION_MANAGEMENT and document_key in existing_docs_map:
                    existing_info = existing_docs_map[document_key]
                    old_revision = existing_info.get('revision')
                    
                    # Revision 비교
                    if old_revision and new_revision:
                        if old_revision == new_revision:
                            # 동일 버전 - 건너뛰기
                            if SKIP_SAME_REVISION:
                                logger.info(f"  [{document_key}] 동일 revision ({new_revision}) - 건너뜀")
                                self.stats['skipped_documents'] += 1
                                continue
                        elif not self.is_revision_newer(old_revision, new_revision):
                            # 이전 버전 - 건너뛰기
                            logger.info(f"  [{document_key}] 이전 revision ({new_revision} <= {old_revision}) - 건너뜀")
                            self.stats['skipped_documents'] += 1
                            continue
                        else:
                            # 업데이트 필요
                            logger.info(f"  [{document_key}] Revision 업데이트: {old_revision} → {new_revision}")
                            
                            # 기존 문서 삭제
                            if DELETE_BEFORE_UPLOAD:
                                doc_id = existing_info.get('doc_id')
                                if self.ragflow_client.delete_document(dataset, doc_id):
                                    self.stats['deleted_documents'] += 1
                                    logger.info(f"    ✓ RAGFlow에서 기존 문서 삭제 완료")
                                    # RevisionDB에서도 삭제
                                    self.revision_db.delete_document(document_key, dataset_id)
                                    logger.debug(f"    ✓ RevisionDB에서도 삭제 완료")
                                else:
                                    self.stats['failed_deletions'] += 1
                                    logger.error(f"    ✗ 기존 문서 삭제 실패 - 건너뜀")
                                    continue
                    else:
                        logger.debug(f"  [{document_key}] Revision 정보 불완전 - 업데이트 진행")
                    
                    # 파일 업로드
                    if self.process_item(dataset, item):
                        uploaded_count += 1
                        self.stats['updated_documents'] += 1
                        logger.info(f"    ✓ 문서 업데이트 완료")
                
                else:
                    # 신규 문서
                    logger.info(f"  [{document_key}] 신규 문서 (revision: {new_revision})")
                    if self.process_item(dataset, item):
                        uploaded_count += 1
                        self.stats['new_documents'] += 1
                        logger.info(f"    ✓ 신규 문서 업로드 완료")
            
            # 일괄 파싱 시작
            if uploaded_count > 0:
                logger.info(f"[{sheet_name}] {uploaded_count}개 파일 업로드 완료, 일괄 파싱 시작")
                parse_started = self.ragflow_client.start_batch_parse(dataset)
                
                if parse_started and monitor_progress and MONITOR_PARSE_PROGRESS:
                    self.monitor_parse_progress(dataset, sheet_name, max_wait_minutes=PARSE_TIMEOUT_MINUTES)
                elif parse_started:
                    logger.info(f"[{sheet_name}] 파싱이 백그라운드에서 진행됩니다.")
            else:
                logger.info(f"[{sheet_name}] 업로드된 파일이 없습니다.")
            
            logger.info(f"[{sheet_name}] Revision 관리 시트 처리 완료")
        
        except Exception as e:
            logger.error(f"시트 '{sheet_name}' 처리 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def process_sheet_attachments(self, sheet_name: str, items: List[Dict], monitor_progress: bool = False):
        """
        첨부파일 시트 처리 (기존 방식 - Revision 관리 없음)
        
        Args:
            sheet_name: 시트 이름
            items: 하이퍼링크와 메타데이터 목록
            monitor_progress: 파싱 진행 상황 모니터링 여부
        """
        if not items:
            logger.warning(f"시트 '{sheet_name}'에 처리할 항목이 없습니다.")
            return
        
        logger.info(f"[{sheet_name}] 첨부파일 시트 처리 시작 (항목 수: {len(items)})")
        
        try:
            # 지식베이스 생성
            dataset_name = f"{sheet_name}"
            dataset_description = f"엑셀 시트 '{sheet_name}'에서 자동 생성된 지식베이스"
            
            dataset = self.ragflow_client.get_or_create_dataset(
                name=dataset_name,
                description=dataset_description,
                permission=DATASET_PERMISSION,
                embedding_model=None,
                chunk_method=CHUNK_METHOD,
                parser_config=PARSER_CONFIG
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
                logger.info(f"[{sheet_name}] {uploaded_count}개 파일 업로드 완료, 일괄 파싱 시작")
                parse_started = self.ragflow_client.start_batch_parse(dataset)
                
                if parse_started and monitor_progress and MONITOR_PARSE_PROGRESS:
                    self.monitor_parse_progress(dataset, sheet_name, max_wait_minutes=PARSE_TIMEOUT_MINUTES)
                elif parse_started:
                    logger.info(f"[{sheet_name}] 파싱이 백그라운드에서 진행됩니다.")
            
            logger.info(f"[{sheet_name}] 첨부파일 시트 처리 완료")
        
        except Exception as e:
            logger.error(f"시트 '{sheet_name}' 처리 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def process_sheet_as_text(self, sheet_name: str, sheet_type: SheetType, monitor_progress: bool = False):
        """
        이력관리/소프트웨어 형상기록 시트를 텍스트 또는 Excel로 변환하여 업로드
        
        Args:
            sheet_name: 시트 이름
            sheet_type: 시트 타입 (HISTORY 또는 SOFTWARE)
            monitor_progress: 파싱 진행 상황 모니터링 여부
        """
        upload_format = HISTORY_SHEET_UPLOAD_FORMAT
        logger.info(f"[{sheet_name}] 시트 처리 시작 (형식: {upload_format.upper()})")
        
        try:
            # 지식베이스 생성
            dataset_name = f"{sheet_name}"
            dataset_description = f"엑셀 시트 '{sheet_name}' ({sheet_type.value})"
            
            dataset = self.ragflow_client.get_or_create_dataset(
                name=dataset_name,
                description=dataset_description,
                permission=DATASET_PERMISSION,
                embedding_model=None,
                chunk_method=CHUNK_METHOD,
                parser_config=PARSER_CONFIG
            )
            
            if not dataset:
                logger.error(f"지식베이스 생성 실패: {sheet_name}")
                return
            
            self.stats['datasets_created'] += 1
            uploaded_count = 0
            
            if upload_format == "excel":
                # Excel 파일로 추출하여 업로드
                logger.info(f"[{sheet_name}] Excel 파일로 추출 중...")
                excel_file_path = self.excel_processor.extract_sheet_as_excel(sheet_name, TEMP_DIR)
                
                if not excel_file_path:
                    logger.error(f"[{sheet_name}] Excel 추출 실패")
                    return
                
                # Excel 파일 업로드
                metadata = {
                    '시트명': sheet_name,
                    '타입': sheet_type.value,
                    '파일형식': 'excel'
                }
                
                success = self.ragflow_client.upload_document(
                    dataset=dataset,
                    file_path=excel_file_path,
                    metadata=metadata,
                    display_name=f"{sheet_name}.xlsx"
                )
                
                if success:
                    uploaded_count += 1
                    self.stats['successful_uploads'] += 1
                    logger.info(f"[{sheet_name}] Excel 파일 업로드 완료")
                else:
                    self.stats['failed_uploads'] += 1
                    logger.error(f"[{sheet_name}] Excel 파일 업로드 실패")
            
            else:  # upload_format == "text" - PDF로 변환하여 업로드
                # 텍스트로 변환 후 PDF로 변환 (여러 청크 가능)
                logger.info(f"[{sheet_name}] 텍스트로 변환 중...")
                text_chunks = self.excel_processor.convert_sheet_to_text_chunks(sheet_name)
                
                if not text_chunks:
                    logger.warning(f"[{sheet_name}] 변환된 텍스트가 비어있습니다.")
                    return
                
                logger.info(f"[{sheet_name}] {len(text_chunks)}개 청크 생성됨")
                
                # 각 청크를 PDF로 변환하여 업로드
                for chunk_idx, chunk_content in enumerate(text_chunks, 1):
                    # 파일명: 청크가 1개면 번호 없이, 여러 개면 번호 붙임
                    if len(text_chunks) == 1:
                        filename = f"{sheet_name}_{sheet_type.value}"
                        display_name = f"{sheet_name}_{sheet_type.value}.pdf"
                    else:
                        filename = f"{sheet_name}_{sheet_type.value}_part{chunk_idx}"
                        display_name = f"{sheet_name}_{sheet_type.value}_part{chunk_idx}.pdf"
                    
                    # 텍스트를 PDF로 변환
                    pdf_file_path = self.file_handler.convert_text_to_pdf(chunk_content, filename)
                    
                    if not pdf_file_path:
                        logger.error(f"[{sheet_name}] 청크 {chunk_idx} PDF 변환 실패")
                        self.stats['failed_uploads'] += 1
                        continue
                    
                    # PDF 파일 업로드
                    metadata = {
                        '시트명': sheet_name,
                        '타입': sheet_type.value,
                        '파일형식': 'pdf',
                        '청크_번호': str(chunk_idx) if len(text_chunks) > 1 else '1',
                        '총_청크_수': str(len(text_chunks))
                    }
                    
                    success = self.ragflow_client.upload_document(
                        dataset=dataset,
                        file_path=pdf_file_path,
                        metadata=metadata,
                        display_name=display_name
                    )
                    
                    if success:
                        uploaded_count += 1
                        self.stats['successful_uploads'] += 1
                        logger.info(f"[{sheet_name}] 청크 {chunk_idx}/{len(text_chunks)} PDF 업로드 완료")
                    else:
                        self.stats['failed_uploads'] += 1
                        logger.error(f"[{sheet_name}] 청크 {chunk_idx}/{len(text_chunks)} PDF 업로드 실패")
            
            # 일괄 파싱 시작
            if uploaded_count > 0:
                logger.info(f"[{sheet_name}] {uploaded_count}개 파일 업로드 완료, 일괄 파싱 시작")
                parse_started = self.ragflow_client.start_batch_parse(dataset)
                
                if parse_started and monitor_progress and MONITOR_PARSE_PROGRESS:
                    self.monitor_parse_progress(dataset, sheet_name, max_wait_minutes=PARSE_TIMEOUT_MINUTES)
                elif parse_started:
                    logger.info(f"[{sheet_name}] 파싱이 백그라운드에서 진행됩니다.")
            
            logger.info(f"[{sheet_name}] 시트 처리 완료")
        
        except Exception as e:
            logger.error(f"시트 '{sheet_name}' 처리 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def process_sheet(self, sheet_name: str, items: List[Dict], monitor_progress: bool = False):
        """
        시트 단위 처리
        
        Args:
            sheet_name: 시트 이름
            items: 하이퍼링크와 메타데이터 목록
            monitor_progress: 파싱 진행 상황 모니터링 여부 (기본: False)
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
                parse_started = self.ragflow_client.start_batch_parse(dataset)
                
                # 진행 상황 모니터링 (옵션)
                if parse_started and monitor_progress:
                    self.monitor_parse_progress(dataset, sheet_name, max_wait_minutes=PARSE_TIMEOUT_MINUTES)
                elif parse_started:
                    logger.info(f"시트 '{sheet_name}': 파싱이 백그라운드에서 진행됩니다. Management UI에서 확인하세요.")
            
            logger.log_sheet_end(sheet_name, uploaded_count)
        
        except Exception as e:
            logger.error(f"시트 '{sheet_name}' 처리 중 오류: {e}")
    
    def process_item(self, dataset: object, item: Dict) -> Optional[str]:
        """
        개별 항목 처리 (파일 다운로드, 변환, 업로드)
        
        Args:
            dataset: Dataset 객체
            item: {'hyperlink': '...', 'metadata': {...}, 'document_key': '...', 'revision': '...', ...}
        
        Returns:
            문서 ID (성공 시) 또는 None (실패 시)
        """
        hyperlink = item.get('hyperlink')
        metadata = item.get('metadata', {})
        row_number = item.get('row_number')
        document_key = item.get('document_key')
        revision = item.get('revision')
        
        if not hyperlink:
            logger.warning(f"{row_number}행: 하이퍼링크가 없습니다.")
            return None
        
        self.stats['total_files'] += 1
        
        try:
            # 1. 파일 가져오기 (다운로드 또는 복사)
            file_path = self.file_handler.get_file(hyperlink)
            
            if not file_path:
                logger.error(f"{row_number}행: 파일 가져오기 실패 - {hyperlink}")
                self.stats['failed_uploads'] += 1
                return None
            
            # 2. 파일 처리 (형식 변환)
            processed_files = self.file_handler.process_file(file_path)
            
            if not processed_files:
                logger.error(f"{row_number}행: 파일 처리 실패 - {file_path.name}")
                self.stats['failed_uploads'] += 1
                return None
            
            # 3. 처리된 파일들을 RAGFlow에 업로드
            document_id = None
            for processed_path, file_type in processed_files:
                # 메타데이터에 원본 정보 추가
                enhanced_metadata = metadata.copy()
                enhanced_metadata['원본_파일'] = file_path.name
                enhanced_metadata['파일_형식'] = file_type
                enhanced_metadata['엑셀_행번호'] = str(row_number)
                enhanced_metadata['하이퍼링크'] = hyperlink
                
                # Revision 관리 정보 추가
                if document_key:
                    enhanced_metadata['document_key'] = document_key
                if revision:
                    enhanced_metadata['revision'] = revision
                
                # 업로드 (document_id 반환)
                doc_id = self.ragflow_client.upload_document(
                    dataset=dataset,
                    file_path=processed_path,
                    metadata=enhanced_metadata,
                    display_name=processed_path.name
                )
                
                if doc_id:
                    document_id = doc_id  # 첫 번째 성공한 문서 ID 사용
                    self.stats['successful_uploads'] += 1
                    logger.log_file_process(
                        processed_path.name, 
                        "업로드 성공",
                        f"형식: {file_type}, 행: {row_number}, 문서ID: {doc_id}"
                    )
                    
                    # RevisionDB에 저장 (revision 관리가 활성화된 경우)
                    if ENABLE_REVISION_MANAGEMENT and document_key:
                        dataset_id = dataset.get('id')
                        dataset_name = dataset.get('name')
                        self.revision_db.save_document(
                            document_key=document_key,
                            document_id=doc_id,
                            dataset_id=dataset_id,
                            dataset_name=dataset_name,
                            revision=revision,
                            file_path=str(processed_path),
                            file_name=processed_path.name
                        )
                        logger.debug(f"RevisionDB에 저장: {document_key} → {doc_id}")
                else:
                    self.stats['failed_uploads'] += 1
                    logger.log_file_process(
                        processed_path.name, 
                        "업로드 실패",
                        f"형식: {file_type}, 행: {row_number}"
                    )
            
            return document_id
        
        except Exception as e:
            logger.error(f"{row_number}행 처리 중 오류: {e}")
            self.stats['failed_uploads'] += 1
            return None
    
    def monitor_parse_progress(self, dataset: Dict, dataset_name: str, max_wait_minutes: int = 30):
        """
        파싱 진행 상황 모니터링 (Management API 전용)
        
        Args:
            dataset: Dataset 딕셔너리
            dataset_name: 데이터셋 이름 (로그용)
            max_wait_minutes: 최대 대기 시간 (분, 기본: 30분)
        """
        logger.info(f"[{dataset_name}] 📊 파싱 진행 상황 모니터링 시작...")
        logger.info(f"[{dataset_name}] 최대 대기 시간: {max_wait_minutes}분")
        
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60
        check_interval = 10  # 10초마다 확인
        last_status = None
        
        while True:
            try:
                # 진행 상황 조회
                progress = self.ragflow_client.get_parse_progress(dataset)
                
                if progress:
                    status = progress.get('status', 'unknown')
                    current = progress.get('current_document_index', 0)
                    total = progress.get('total_documents', 0)
                    current_doc = progress.get('current_document_name', 'N/A')
                    
                    # 상태 변경 시에만 로그 출력 (중복 방지)
                    if status != last_status or current != getattr(self, '_last_current', -1):
                        if total > 0:
                            progress_percent = (current / total) * 100
                            logger.info(
                                f"[{dataset_name}] 📄 진행: {current}/{total} ({progress_percent:.1f}%) "
                                f"| 상태: {status} | 현재: {current_doc}"
                            )
                        else:
                            logger.info(f"[{dataset_name}] 상태: {status}")
                        
                        last_status = status
                        self._last_current = current
                    
                    # 완료 체크
                    if status == 'completed' or (total > 0 and current >= total):
                        logger.info(f"[{dataset_name}] ✓ 파싱 완료!")
                        logger.info(f"[{dataset_name}] 총 {total}개 문서 파싱 완료")
                        break
                    
                    elif status == 'error':
                        error_msg = progress.get('error_message', '알 수 없는 오류')
                        logger.error(f"[{dataset_name}] ✗ 파싱 중 오류 발생: {error_msg}")
                        break
                    
                    elif status == 'idle' and current == 0:
                        logger.warning(f"[{dataset_name}] ⚠️ 파싱이 시작되지 않았습니다.")
                else:
                    logger.debug(f"[{dataset_name}] 진행 상황 정보 없음 (백그라운드 작업 대기 중...)")
                
                # 타임아웃 체크
                elapsed = time.time() - start_time
                if elapsed > max_wait_seconds:
                    logger.warning(f"[{dataset_name}] ⏱️ 파싱 대기 시간 초과 ({max_wait_minutes}분)")
                    logger.info(f"[{dataset_name}] 파싱은 계속 진행 중입니다. Management UI에서 확인하세요.")
                    break
                
                # 대기
                time.sleep(check_interval)
            
            except Exception as e:
                logger.error(f"[{dataset_name}] 진행 상황 모니터링 중 오류: {e}")
                logger.info(f"[{dataset_name}] Management UI에서 진행 상황을 확인하세요.")
                break
        
        # 최종 상태 확인
        try:
            final_progress = self.ragflow_client.get_parse_progress(dataset)
            if final_progress:
                final_status = final_progress.get('status', 'unknown')
                logger.info(f"[{dataset_name}] 최종 상태: {final_status}")
        except:
            pass
    
    def print_statistics(self):
        """처리 통계 출력"""
        logger.info("="*80)
        logger.info("배치 처리 통계")
        logger.info("-"*80)
        
        # 시트 통계
        logger.info(f"총 시트 수: {self.stats['total_sheets']}")
        logger.info(f"  - 건너뛴 시트 (목차): {self.stats['skipped_sheets']}")
        logger.info(f"  - Revision 관리 시트: {self.stats['revision_sheets']}")
        logger.info(f"  - 첨부파일 시트: {self.stats['attachment_sheets']}")
        logger.info(f"  - 이력관리/소프트웨어 시트: {self.stats['history_sheets']}")
        logger.info(f"생성된 지식베이스 수: {self.stats['datasets_created']}")
        
        logger.info("-"*80)
        
        # Revision 관리 통계
        if self.stats['revision_sheets'] > 0:
            logger.info(f"Revision 관리 문서:")
            logger.info(f"  - 신규 문서: {self.stats['new_documents']}")
            logger.info(f"  - 업데이트 문서: {self.stats['updated_documents']}")
            logger.info(f"  - 건너뛴 문서 (동일 revision): {self.stats['skipped_documents']}")
            logger.info(f"  - 삭제된 문서: {self.stats['deleted_documents']}")
            if self.stats['failed_deletions'] > 0:
                logger.info(f"  - 삭제 실패: {self.stats['failed_deletions']}")
            logger.info("-"*80)
        
        # 파일 업로드 통계
        logger.info(f"총 파일 수: {self.stats['total_files']}")
        logger.info(f"업로드 성공: {self.stats['successful_uploads']}")
        logger.info(f"업로드 실패: {self.stats['failed_uploads']}")
        
        if self.stats['total_files'] > 0:
            success_rate = (self.stats['successful_uploads'] / self.stats['total_files']) * 100
            logger.info(f"업로드 성공률: {success_rate:.1f}%")
        
        logger.info("="*80)

