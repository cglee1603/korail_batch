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
    AUTO_PARSE_AFTER_UPLOAD,
    MONITOR_PARSE_PROGRESS,
    PARSE_TIMEOUT_MINUTES,
    ENABLE_REVISION_MANAGEMENT,
    SKIP_SAME_REVISION,
    DELETE_BEFORE_UPLOAD,
    PURGE_BEFORE_HISTORY_SOFTWARE,
    HISTORY_SHEET_UPLOAD_FORMAT,
    TEMP_DIR
)


class BatchProcessor:
    """배치 처리 메인 클래스"""
    
    def __init__(self, excel_path: str = None, data_source: str = None, filesystem_path: str = None):
        """
        Args:
            excel_path: 엑셀 파일 경로
            data_source: 데이터 소스 ("excel", "db", "filesystem", "both" 등 콤마 구분)
            filesystem_path: 파일시스템 루트 경로 (filesystem 모드용)
        """
        self.excel_path = excel_path or EXCEL_FILE_PATH
        
        # 데이터 소스 파싱 (콤마로 구분된 값 지원)
        raw_source = data_source or DATA_SOURCE
        self.data_sources = [s.strip().lower() for s in raw_source.split(',')]
        
        self.data_source = raw_source  # 로깅용 원본 문자열
        self.filesystem_path = filesystem_path

        # 프로세서 초기화
        self.excel_processor = None
        self.db_processor = None
        self.filesystem_processor = None
        
        # Excel 소스
        if 'excel' in self.data_sources:
            self.excel_processor = ExcelProcessor(self.excel_path)
        
        # Revision 관리 DB 먼저 초기화 (FileHandler에서 사용)
        self.revision_db = RevisionDB()
        
        # 다운로드 캐시 자동 정리 (설정된 경우)
        from config import AUTO_CLEAN_DOWNLOAD_CACHE, DOWNLOAD_CACHE_KEEP_DAYS
        if AUTO_CLEAN_DOWNLOAD_CACHE:
            logger.info(f"다운로드 캐시 자동 정리 시작 (보관 기간: {DOWNLOAD_CACHE_KEEP_DAYS}일)")
            if DOWNLOAD_CACHE_KEEP_DAYS > 0:
                deleted = self.revision_db.clear_mt_download_cache(older_than_days=DOWNLOAD_CACHE_KEEP_DAYS, delete_files=True)
                logger.info(f"✓ {DOWNLOAD_CACHE_KEEP_DAYS}일 이상된 캐시 정리 완료: {deleted}개")
            else:
                deleted = self.revision_db.clear_mt_download_cache(older_than_days=None, delete_files=True)
                logger.info(f"✓ 전체 캐시 정리 완료: {deleted}개")
        
        # 암복호화 핸들러 초기화
        from crypto_handler import CryptoHandler
        self.crypto_handler = CryptoHandler()
        
        # FileHandler 초기화 (다운로드 캐시 + 암복호화)
        self.file_handler = FileHandler(
            revision_db=self.revision_db,
            crypto_handler=self.crypto_handler
        )

        # FilesystemProcessor 초기화 (FileHandler 생성 후)
        if 'filesystem' in self.data_sources and self.filesystem_path:
            from filesystem_processor import FilesystemProcessor
            self.filesystem_processor = FilesystemProcessor(
                root_path=self.filesystem_path,
                revision_db=self.revision_db,
                file_handler=self.file_handler
            )
        
        # DB 소스
        if 'db' in self.data_sources:
            self._init_db_processor()
        
        self.ragflow_client = RAGFlowClient()
        
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
            if 'db' in self.data_sources:
                self.data_sources.remove('db')
        except Exception as e:
            logger.error(f"DB 프로세서 초기화 실패: {e}")
            if 'db' in self.data_sources:
                self.data_sources.remove('db')
    
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
        if 'excel' in self.data_sources:
            logger.info(f"엑셀 파일: {self.excel_path}")
        if 'filesystem' in self.data_sources and self.filesystem_path:
            logger.info(f"파일시스템 경로: {self.filesystem_path}")
        logger.info(f"Revision 관리: {'활성화' if ENABLE_REVISION_MANAGEMENT else '비활성화'}")
        logger.info("="*80)
        
        try:
            # 데이터 수집
            all_data = {}
            
            # 1. Excel 데이터 추출
            if 'excel' in self.data_sources and self.excel_processor:
                logger.info("\n[Excel 데이터 처리]")
                sheet_data = self.excel_processor.process_all_sheets()
                all_data.update(sheet_data)
                self.stats['total_sheets'] += len(sheet_data)
            
            # 2. DB 데이터 추출
            if 'db' in self.data_sources and self.db_processor:
                logger.info("\n[DB 데이터 처리]")
                db_data = self.db_processor.process(query_name="DB_Query")
                # DB 데이터는 기존 형식이므로 변환
                for sheet_name, items in db_data.items():
                    all_data[sheet_name] = (SheetType.ATTACHMENT, items, [])
                self.stats['total_sheets'] += len(db_data)

            # 3. Filesystem 처리 (독립적으로 실행)
            if 'filesystem' in self.data_sources and self.filesystem_processor:
                logger.info("\n[Filesystem 데이터 처리]")
                self.filesystem_processor.process()
                # 통계 병합
                fs_stats = self.filesystem_processor.stats
                self.stats['datasets_created'] += fs_stats['datasets_created']
                self.stats['total_files'] += fs_stats['total_files']
                self.stats['new_documents'] += fs_stats['new_files']
                self.stats['updated_documents'] += fs_stats['updated_files']
                self.stats['skipped_documents'] += fs_stats['skipped_files']
                self.stats['failed_uploads'] += fs_stats['failed_files']
            
            if not all_data and 'filesystem' not in self.data_sources:
                logger.error("처리할 데이터가 없습니다.")
                return
            
            # 4. 시트 타입별로 처리 (Excel/DB 데이터)
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
            
            # 5. 임시 파일 정리
            self.file_handler.cleanup_temp()
            
            # 6. 복호화된 파일 정리
            if self.crypto_handler and self.crypto_handler.enabled:
                self.crypto_handler.cleanup_decrypted_files()
            
            # 7. 통계 출력
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
            existing_docs_map = {}  # document_key -> List[{doc_id, revision, name}]
            dataset_id = dataset.get('id')
            
            if ENABLE_REVISION_MANAGEMENT:
                logger.info(f"[{sheet_name}] RevisionDB에서 기존 문서 목록 조회 중...")
                db_docs = self.revision_db.get_all_documents(dataset_id=dataset_id)
                
                # 문서를 document_key로 그룹화 (하나의 키가 여러 파일을 가질 수 있음)
                for doc in db_docs:
                    doc_key = doc.get('document_key')
                    if doc_key:
                        if doc_key not in existing_docs_map:
                            existing_docs_map[doc_key] = []
                        
                        existing_docs_map[doc_key].append({
                            'doc_id': doc.get('document_id'),
                            'revision': doc.get('revision'),
                            'name': doc.get('file_name'),
                            'is_archive': doc.get('is_part_of_archive', False)
                        })
                
                total_files = sum(len(files) for files in existing_docs_map.values())
                logger.info(f"[{sheet_name}] RevisionDB에서 기존 문서 {len(existing_docs_map)}개 (총 {total_files}개 파일) 발견")
            
            # 각 항목 처리 (업로드된 문서 ID 수집)
            uploaded_document_ids = []  # v21: 파싱할 문서 ID 리스트
            
            for item in items:
                document_key = item.get('document_key')
                new_revision = item.get('revision')
                
                if not document_key:
                    logger.warning(f"행 {item.get('row_number')}: document_key가 없습니다. 건너뜁니다.")
                    continue
                
                # Revision 비교 및 처리
                if ENABLE_REVISION_MANAGEMENT and document_key in existing_docs_map:
                    existing_files = existing_docs_map[document_key]  # List[{doc_id, revision, name}] 혹은 Dict
                    # 리스트/딕셔너리 모두 안전하게 처리
                    files_list = existing_files if isinstance(existing_files, list) else ([existing_files] if isinstance(existing_files, dict) else [])
                    old_revision = files_list[0].get('revision') if files_list else None
                    file_count = len(files_list)
                    
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
                            
                            # 기존 문서들 삭제 (압축 파일인 경우 여러 개)
                            if DELETE_BEFORE_UPLOAD:
                                logger.info(f"    기존 파일 {file_count}개 삭제 중...")
                                deleted_count = 0
                                failed_count = 0
                                
                                for file_info in files_list:
                                    doc_id = file_info.get('doc_id')
                                    file_name = file_info.get('name')
                                    
                                    if self.ragflow_client.delete_document(dataset, doc_id):
                                        deleted_count += 1
                                        logger.debug(f"      ✓ RAGFlow 삭제: {file_name}")
                                    else:
                                        failed_count += 1
                                        logger.warning(f"      ✗ RAGFlow 삭제 실패: {file_name}")
                                
                                # RevisionDB에서도 해당 키의 모든 파일 삭제
                                db_deleted = self.revision_db.delete_document(document_key, dataset_id)
                                
                                self.stats['deleted_documents'] += deleted_count
                                self.stats['failed_deletions'] += failed_count
                                
                                if deleted_count > 0:
                                    logger.info(f"    ✓ 기존 파일 삭제 완료: {deleted_count}개 (실패: {failed_count}개)")
                                
                                if failed_count == file_count:
                                    logger.error(f"    ✗ 모든 기존 파일 삭제 실패 - 건너뜀")
                                    continue
                    else:
                        logger.debug(f"  [{document_key}] Revision 정보 불완전 - 업데이트 진행")
                    
                    # 파일 업로드 (v21: 문서 ID 리스트 반환)
                    doc_ids = self.process_item(dataset, item)
                    if doc_ids:
                        uploaded_document_ids.extend(doc_ids)
                        self.stats['updated_documents'] += 1
                        logger.info(f"    ✓ 문서 업데이트 완료 ({len(doc_ids)}개 파일)")
                
                else:
                    # 신규 문서
                    logger.info(f"  [{document_key}] 신규 문서 (revision: {new_revision})")
                    doc_ids = self.process_item(dataset, item)
                    if doc_ids:
                        uploaded_document_ids.extend(doc_ids)
                        self.stats['new_documents'] += 1
                        logger.info(f"    ✓ 신규 문서 업로드 완료 ({len(doc_ids)}개 파일)")
            
            # v21: 업로드된 문서 ID들만 파싱
            if uploaded_document_ids:
                if AUTO_PARSE_AFTER_UPLOAD:
                    logger.info(f"[{sheet_name}] {len(uploaded_document_ids)}개 문서 업로드 완료, 파싱 시작")
                    parse_started = self.ragflow_client.start_batch_parse(
                        dataset,
                        document_ids=uploaded_document_ids
                    )
                    
                    if parse_started and monitor_progress and MONITOR_PARSE_PROGRESS:
                        self.monitor_parse_progress(dataset, sheet_name, uploaded_document_ids, max_wait_minutes=PARSE_TIMEOUT_MINUTES)
                    elif parse_started:
                        logger.info(f"[{sheet_name}] 파싱이 백그라운드에서 진행됩니다.")
                else:
                    logger.info(f"[{sheet_name}] {len(uploaded_document_ids)}개 문서 업로드 완료 (자동 파싱 비활성화)")
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
            
            # 각 항목 처리 (v21: 문서 ID 수집)
            uploaded_document_ids = []
            for item in items:
                doc_ids = self.process_item(dataset, item, check_processed_urls=True)
                if doc_ids:
                    uploaded_document_ids.extend(doc_ids)
            
            # v21: 업로드된 문서 ID들만 파싱
            if uploaded_document_ids:
                if AUTO_PARSE_AFTER_UPLOAD:
                    logger.info(f"[{sheet_name}] {len(uploaded_document_ids)}개 문서 업로드 완료, 파싱 시작")
                    parse_started = self.ragflow_client.start_batch_parse(
                        dataset,
                        document_ids=uploaded_document_ids
                    )
                    
                    if parse_started and monitor_progress and MONITOR_PARSE_PROGRESS:
                        self.monitor_parse_progress(dataset, sheet_name, uploaded_document_ids, max_wait_minutes=PARSE_TIMEOUT_MINUTES)
                    elif parse_started:
                        logger.info(f"[{sheet_name}] 파싱이 백그라운드에서 진행됩니다.")
                else:
                    logger.info(f"[{sheet_name}] {len(uploaded_document_ids)}개 문서 업로드 완료 (자동 파싱 비활성화)")
            
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
            
            # 업로드 전 전량 삭제(문서+연결 파일) - 히스토리/소프트웨어 시트 전용 퍼지
            if PURGE_BEFORE_HISTORY_SOFTWARE:
                try:
                    logger.info(f"[{sheet_name}] 업로드 전 데이터셋 전량 삭제(문서+파일) 수행")
                    purge_result = self.ragflow_client.delete_all_documents_and_files_in_dataset(dataset)
                    logger.info(
                        f"[{sheet_name}] 퍼지 결과 - 문서: {purge_result.get('deleted_documents', 0)} 삭제 "
                        f"(실패 {purge_result.get('failed_documents', 0)}) | "
                        f"파일: {purge_result.get('deleted_files', 0)} 삭제 "
                        f"(실패 {purge_result.get('failed_files', 0)})"
                    )
                except Exception as e:
                    logger.error(f"[{sheet_name}] 퍼지 중 오류: {e}")
                
            # v21: 업로드된 문서 ID 추적
            uploaded_document_ids = []
            
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
                
                upload_result = self.ragflow_client.upload_document(
                    dataset=dataset,
                    file_path=excel_file_path,
                    metadata=metadata,
                    display_name=f"{sheet_name}.xlsx"
                )
                
                if upload_result:
                    doc_id = upload_result.get('document_id')
                    uploaded_document_ids.append(doc_id)
                    self.stats['successful_uploads'] += 1
                    logger.info(f"[{sheet_name}] Excel 파일 업로드 완료")
                else:
                    self.stats['failed_uploads'] += 1
                    logger.error(f"[{sheet_name}] Excel 파일 업로드 실패")
            
            else:  # upload_format == "text" - PDF로 변환하여 업로드
                # 텍스트로 변환 후 PDF로 변환 (여러 청크 가능)
                logger.info(f"[{sheet_name}] 텍스트로 변환 중...")
                # PDF 변환 시 Row 단위 페이지 제어를 위해 리스트 형태로 반환받음
                text_chunks = self.excel_processor.convert_sheet_to_text_chunks(
                    sheet_name,
                    return_rows_as_list=True
                )
                
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
                    
                    upload_result = self.ragflow_client.upload_document(
                        dataset=dataset,
                        file_path=pdf_file_path,
                        metadata=metadata,
                        display_name=display_name
                    )
                    
                    if upload_result:
                        doc_id = upload_result.get('document_id')
                        uploaded_document_ids.append(doc_id)
                        self.stats['successful_uploads'] += 1
                        logger.info(f"[{sheet_name}] 청크 {chunk_idx}/{len(text_chunks)} PDF 업로드 완료")
                    else:
                        self.stats['failed_uploads'] += 1
                        logger.error(f"[{sheet_name}] 청크 {chunk_idx}/{len(text_chunks)} PDF 업로드 실패")
            
            # v21: 업로드된 문서 ID들만 파싱
            if uploaded_document_ids:
                if AUTO_PARSE_AFTER_UPLOAD:
                    logger.info(f"[{sheet_name}] {len(uploaded_document_ids)}개 파일 업로드 완료, 파싱 시작")
                    parse_started = self.ragflow_client.start_batch_parse(
                        dataset,
                        document_ids=uploaded_document_ids
                    )
                    
                    if parse_started and monitor_progress and MONITOR_PARSE_PROGRESS:
                        self.monitor_parse_progress(dataset, sheet_name, uploaded_document_ids, max_wait_minutes=PARSE_TIMEOUT_MINUTES)
                    elif parse_started:
                        logger.info(f"[{sheet_name}] 파싱이 백그라운드에서 진행됩니다.")
                else:
                    logger.info(f"[{sheet_name}] {len(uploaded_document_ids)}개 파일 업로드 완료 (자동 파싱 비활성화)")
            
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
                chunk_method=CHUNK_METHOD,  # GUI와 동일한 파싱 방법
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
                if AUTO_PARSE_AFTER_UPLOAD:
                    logger.info(f"시트 '{sheet_name}': {uploaded_count}개 파일 업로드 완료, 일괄 파싱 시작")
                    parse_started = self.ragflow_client.start_batch_parse(dataset)
                    
                    # 진행 상황 모니터링 (옵션)
                    if parse_started and monitor_progress:
                        self.monitor_parse_progress(dataset, sheet_name, max_wait_minutes=PARSE_TIMEOUT_MINUTES)
                    elif parse_started:
                        logger.info(f"시트 '{sheet_name}': 파싱이 백그라운드에서 진행됩니다. Management UI에서 확인하세요.")
                else:
                    logger.info(f"시트 '{sheet_name}': {uploaded_count}개 파일 업로드 완료 (자동 파싱 비활성화)")
            
            logger.log_sheet_end(sheet_name, uploaded_count)
        
        except Exception as e:
            logger.error(f"시트 '{sheet_name}' 처리 중 오류: {e}")
    
    def process_item(self, dataset: object, item: Dict, check_processed_urls: bool = False) -> List[str]:
        """
        개별 항목 처리 (파일 다운로드, 변환, 업로드)
        
        Args:
            dataset: Dataset 객체
            item: {'hyperlink': '...', 'metadata': {...}, 'document_key': '...', 'revision': '...', ...}
            check_processed_urls: 이미 처리된 URL인지 확인할지 여부 (Revision 관리 안하는 시트용)
        
        Returns:
            업로드된 문서 ID 리스트 (성공 시) 또는 빈 리스트 (실패 시)
        """
        hyperlinks = []
        # hyperlinks 배열 우선, 없으면 단일 hyperlink 사용
        if isinstance(item.get('hyperlinks'), list) and item.get('hyperlinks'):
            hyperlinks = [h for h in item.get('hyperlinks') if isinstance(h, str) and h.strip()]
        elif item.get('hyperlink'):
            hyperlinks = [item.get('hyperlink')]
        metadata = item.get('metadata', {})
        row_number = item.get('row_number')
        document_key = item.get('document_key')
        revision = item.get('revision')
        
        if not hyperlinks:
            logger.warning(f"{row_number}행: 하이퍼링크가 없습니다.")
            return []
        
        all_uploaded_doc_ids: List[str] = []
        for hyperlink in hyperlinks:
            # 처리된 URL 확인 (Revision 관리 안하는 시트용)
            if check_processed_urls and self.revision_db.is_url_processed(hyperlink):
                logger.info(f"{row_number}행: 이미 처리된 URL이므로 스킵합니다 - {hyperlink}")
                continue

            self.stats['total_files'] += 1
            try:
                # 1. 파일 가져오기 (다운로드 또는 복사)
                file_path = self.file_handler.get_file(hyperlink)
                
                if not file_path:
                    logger.error(f"{row_number}행: 파일 가져오기 실패 - {hyperlink}")
                    self.stats['failed_uploads'] += 1
                    continue
                
                # 2. 파일 처리 (형식 변환)
                processed_files = self.file_handler.process_file(file_path)
                
                if not processed_files:
                    logger.error(f"{row_number}행: 파일 처리 실패 - {file_path.name}")
                    self.stats['failed_uploads'] += 1
                    continue
                
                # 3. 처리된 파일들을 RAGFlow에 업로드
                # 압축 파일 여부 확인 (ZIP 파일이고 여러 파일이 추출된 경우)
                is_archive = file_path.suffix.lower() == '.zip' and len(processed_files) > 1
                archive_source = file_path.name if is_archive else None
                
                if is_archive:
                    logger.info(f"압축 파일 감지: {file_path.name} ({len(processed_files)}개 파일 추출됨)")
                
                for processed_path, file_type in processed_files:
                    # 메타데이터에 원본 정보 추가
                    enhanced_metadata = metadata.copy()
                    enhanced_metadata['원본_파일'] = file_path.name
                    enhanced_metadata['파일_형식'] = file_type
                    enhanced_metadata['엑셀_행번호'] = str(row_number)
                    enhanced_metadata['하이퍼링크'] = hyperlink
                    
                    # 압축 파일 정보 추가
                    if is_archive:
                        enhanced_metadata['압축파일'] = archive_source
                        enhanced_metadata['압축파일_내_파일명'] = processed_path.name
                    
                    # Revision 관리 정보 추가
                    if document_key:
                        enhanced_metadata['document_key'] = document_key
                    if revision:
                        enhanced_metadata['revision'] = revision
                    
                    # 업로드 (document_id 및 file_id 반환)
                    upload_result = self.ragflow_client.upload_document(
                        dataset=dataset,
                        file_path=processed_path,
                        metadata=enhanced_metadata,
                        display_name=processed_path.name
                    )
                    
                    if upload_result:
                        doc_id = upload_result.get('document_id')
                        file_id = upload_result.get('file_id')

                        # Excel 파일인 경우 chunk_method를 "table"로 설정
                        if file_type in ['xlsx', 'xls', 'xlsm']:
                            self.ragflow_client.update_document_parser(
                                dataset_id=dataset.get('id'),
                                document_id=doc_id,
                                chunk_method="table"
                            )

                        # 메타데이터 업데이트 (업로드 후 별도 호출)
                        # 중요: 사용자 요구사항에 따라 엑셀의 row별 헤더:값(metadata)만 전달한다.
                        self.ragflow_client.update_document(dataset.get('id'), doc_id, metadata)

                        all_uploaded_doc_ids.append(doc_id)
                        self.stats['successful_uploads'] += 1
                        logger.log_file_process(
                            processed_path.name, 
                            "업로드 성공",
                            f"형식: {file_type}, 행: {row_number}, 문서ID: {doc_id}, 파일ID: {file_id}"
                        )
                        
                        # RevisionDB에 저장 (revision 관리가 활성화된 경우)
                        if ENABLE_REVISION_MANAGEMENT and document_key:
                            dataset_id = dataset.get('id')
                            dataset_name = dataset.get('name')
                            
                            # DB 저장 시도
                            db_success = self.revision_db.save_document(
                                document_key=document_key,
                                document_id=doc_id,
                                file_id=file_id,
                                dataset_id=dataset_id,
                                dataset_name=dataset_name,
                                revision=revision,
                                file_path=str(processed_path),
                                file_name=processed_path.name,
                                is_part_of_archive=is_archive,
                                archive_source=archive_source
                            )
                            
                            if db_success:
                                if is_archive:
                                    logger.debug(f"RevisionDB에 저장 (압축 파일): {document_key}/{processed_path.name} → {doc_id} (파일ID: {file_id})")
                                else:
                                    logger.debug(f"RevisionDB에 저장: {document_key} → {doc_id} (파일ID: {file_id})")
                            else:
                                # DB 저장 실패 시 RAGFlow 업로드 롤백 (삭제)
                                logger.error(f"RevisionDB 저장 실패! 데이터 정합성을 위해 RAGFlow 업로드를 롤백(삭제)합니다: {processed_path.name}")
                                try:
                                    self.ragflow_client.delete_document(dataset, doc_id)
                                    logger.info(f"  ✓ 롤백 성공: 문서 삭제됨 ({doc_id})")
                                except Exception as e:
                                    logger.error(f"  ✗ 롤백 실패: 문서를 수동으로 삭제해야 합니다 ({doc_id}): {e}")
                                
                                # 업로드 실패로 처리 및 통계 수정
                                if doc_id in all_uploaded_doc_ids:
                                    all_uploaded_doc_ids.remove(doc_id)
                                self.stats['successful_uploads'] -= 1
                                self.stats['failed_uploads'] += 1
                                continue  # 다음 파일 처리
                        
                        # 처리된 URL 저장 (Revision 관리 안하는 시트용)
                        if check_processed_urls:
                            self.revision_db.add_processed_url(hyperlink)

                    else:
                        self.stats['failed_uploads'] += 1
                        logger.log_file_process(
                            processed_path.name, 
                            "업로드 실패",
                            f"형식: {file_type}, 행: {row_number}"
                        )
            except Exception as e:
                logger.error(f"{row_number}행 처리 중 오류: {e}")
                self.stats['failed_uploads'] += 1
                continue
        
        return all_uploaded_doc_ids
    
    def monitor_parse_progress(self, dataset: Dict, dataset_name: str, document_ids: List[str] = None, max_wait_minutes: int = 30):
        """
        파싱 진행 상황 모니터링 (RAGFlow v21)
        
        Args:
            dataset: Dataset 딕셔너리
            dataset_name: 데이터셋 이름 (로그용)
            document_ids: 모니터링할 문서 ID 리스트
            max_wait_minutes: 최대 대기 시간 (분, 기본: 30분)
        """
        logger.info(f"[{dataset_name}] 📊 파싱 진행 상황 모니터링 시작...")
        if document_ids:
            logger.info(f"[{dataset_name}] 모니터링 대상: {len(document_ids)}개 문서")
        logger.info(f"[{dataset_name}] 최대 대기 시간: {max_wait_minutes}분")
        
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60
        check_interval = 10  # 10초마다 확인
        last_status = None
        
        while True:
            try:
                # v21: 문서 ID 리스트로 진행 상황 조회
                progress = self.ragflow_client.get_parse_progress(dataset, document_ids)
                
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
    
    def delete_knowledge_by_dataset_name(self, dataset_name: str, confirm: bool = False) -> Dict:
        """
        dataset_name으로 RAGFlow 지식베이스의 모든 문서와 파일을 삭제
        
        Args:
            dataset_name: 지식베이스 이름
            confirm: True로 설정해야만 실행됨 (실수 방지)
        
        Returns:
            삭제 결과 딕셔너리
        """
        logger.info("="*80)
        logger.info(f"지식베이스 '{dataset_name}' 전량 삭제(문서+파일) 조회")
        logger.info("="*80)
        
        try:
            # 1. 지식베이스 조회
            logger.info(f"지식베이스 '{dataset_name}' 조회 중...")
            dataset = self.ragflow_client.get_dataset_by_name(dataset_name)
            
            if not dataset:
                logger.error(f"지식베이스 '{dataset_name}'을 찾을 수 없습니다.")
                return {
                    'success': False,
                    'message': f"지식베이스 '{dataset_name}'을 찾을 수 없습니다."
                }
            
            dataset_id = dataset.get('id')
            logger.info(f"✓ 지식베이스 발견 (dataset_id: {dataset_id})")
            
            # 2. 문서 목록 조회
            logger.info("문서 목록 조회 중...")
            all_documents = []
            page = 1
            page_size = 100
            while True:
                documents = self.ragflow_client.get_documents_in_dataset(dataset, page=page, page_size=page_size)
                if not documents:
                    break
                all_documents.extend(documents)
                if len(documents) < page_size:
                    break
                page += 1
            
            total_docs = len(all_documents)
            logger.info(f"✓ {total_docs}개 문서 발견")
            
            if not confirm:
                # 확인 모드: 삭제할 항목만 보여줌
                logger.info("\n삭제 대상 항목:")
                logger.info(f"  - 지식베이스: {dataset_name} (ID: {dataset_id})")
                logger.info(f"  - 문서 수: {total_docs}개")
                logger.info(f"  - 연결된 파일: {total_docs}개 (문서당 1개)")
                
                return {
                    'success': True,
                    'total_documents': total_docs,
                    'dataset_id': dataset_id,
                    'dataset_name': dataset_name
                }
            
            # 3. 실제 삭제 수행
            logger.info("\n="*80)
            logger.info(f"지식베이스 '{dataset_name}' 전량 삭제 시작")
            logger.info("="*80)
            
            purge_result = self.ragflow_client.delete_all_documents_and_files_in_dataset(dataset)
            
            deleted_docs = purge_result.get('deleted_documents', 0)
            failed_docs = purge_result.get('failed_documents', 0)
            deleted_files = purge_result.get('deleted_files', 0)
            failed_files = purge_result.get('failed_files', 0)
            
            logger.info(f"\n삭제 결과:")
            logger.info(f"  - 문서: {deleted_docs}개 삭제 (실패: {failed_docs}개)")
            logger.info(f"  - 파일: {deleted_files}개 삭제 (실패: {failed_files}개)")
            
            # 4. RevisionDB에서도 해당 dataset의 모든 항목 삭제
            logger.info(f"\nRevisionDB에서 '{dataset_name}' 항목 삭제 중...")
            db_documents = self.revision_db.get_documents_by_dataset_name(dataset_name)
            db_deleted = 0
            
            if db_documents:
                for doc in db_documents:
                    document_key = doc.get('document_key')
                    file_name = doc.get('file_name', 'Unknown')
                    deleted_count = self.revision_db.delete_document(
                        document_key=document_key,
                        dataset_id=dataset_id,
                        file_name=file_name
                    )
                    if deleted_count > 0:
                        db_deleted += deleted_count
                
                logger.info(f"✓ RevisionDB에서 {db_deleted}개 항목 삭제")
            else:
                logger.info("RevisionDB에 삭제할 항목이 없습니다.")
            
            return {
                'success': True,
                'dataset_name': dataset_name,
                'dataset_id': dataset_id,
                'total_documents': total_docs,
                'deleted_documents': deleted_docs,
                'failed_documents': failed_docs,
                'deleted_files': deleted_files,
                'failed_files': failed_files,
                'db_deleted': db_deleted
            }
            
        except Exception as e:
            logger.error(f"지식베이스 삭제 중 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': str(e)
            }
    
    def delete_documents_by_dataset_name(self, dataset_name: str, confirm: bool = False) -> Dict:
        """
        dataset_name으로 RAGFlow와 RevisionDB에서 모든 문서 삭제
        
        Args:
            dataset_name: 지식베이스 이름
            confirm: True로 설정해야만 실행됨 (실수 방지)
        
        Returns:
            삭제 결과 딕셔너리
        """
        if not confirm:
            logger.warning("⚠️ 삭제를 실행하려면 confirm=True를 전달해야 합니다.")
            return {
                'success': False,
                'message': 'confirm=True 필요'
            }
        
        logger.info("="*80)
        logger.info(f"지식베이스 '{dataset_name}' 문서 삭제 시작")
        logger.info("="*80)
        
        try:
            # 1. RevisionDB에서 문서 조회
            logger.info(f"[1/2] RevisionDB에서 '{dataset_name}' 문서 조회 중...")
            documents = self.revision_db.get_documents_by_dataset_name(dataset_name)
            
            if not documents:
                logger.warning(f"'{dataset_name}'에 해당하는 문서가 없습니다.")
                return {
                    'success': True,
                    'total_documents': 0,
                    'ragflow_deleted': 0,
                    'ragflow_failed': 0,
                    'db_deleted': 0
                }
            
            total_docs = len(documents)
            dataset_id = documents[0].get('dataset_id')
            logger.info(f"✓ {total_docs}개 문서 발견 (dataset_id: {dataset_id})")
            
            # 2. RAGFlow 및 DB에서 순차 삭제 (성공 시에만 DB 삭제)
            logger.info(f"\n[2/2] RAGFlow 및 DB에서 문서 삭제 중...")
            ragflow_deleted = 0
            ragflow_failed = 0
            db_deleted = 0
            failed_items = []
            
            # dataset 정보 구성
            dataset = {
                'id': dataset_id,
                'name': dataset_name
            }
            
            for idx, doc in enumerate(documents, 1):
                doc_id = doc.get('document_id')
                file_id = doc.get('file_id')
                document_key = doc.get('document_key')
                file_name = doc.get('file_name', 'Unknown')
                
                logger.info(f"  [{idx}/{total_docs}] 처리 중: {file_name} (문서ID: {doc_id}, 파일ID: {file_id})")
                
                deletion_success = True
                failure_reason = None
                
                # Step 1: RAGFlow knowledgebase에서 문서 삭제
                if self.ragflow_client.delete_document(dataset, doc_id):
                    logger.debug(f"    ✓ RAGFlow 문서 삭제 성공")
                    ragflow_deleted += 1
                else:
                    deletion_success = False
                    failure_reason = 'RAGFlow 문서 삭제 실패'
                    logger.warning(f"    ✗ RAGFlow 문서 삭제 실패")
                
                # Step 2: RAGFlow에서 업로드된 파일 삭제 (문서 삭제 성공 시에만)
                if deletion_success and file_id:
                    if self.ragflow_client.delete_uploaded_file(file_id):
                        logger.debug(f"    ✓ RAGFlow 파일 삭제 성공")
                    else:
                        deletion_success = False
                        failure_reason = 'RAGFlow 파일 삭제 실패 (문서는 삭제됨)'
                        logger.warning(f"    ✗ RAGFlow 파일 삭제 실패")
                elif deletion_success and not file_id:
                    logger.debug(f"    ⚠ file_id가 없어 파일 삭제 생략")
                
                # Step 3: 모두 성공 시에만 DB에서 삭제
                if deletion_success:
                    deleted_count = self.revision_db.delete_document(
                        document_key=document_key,
                        dataset_id=dataset_id,
                        file_name=file_name
                    )
                    
                    if deleted_count > 0:
                        db_deleted += deleted_count
                        logger.debug(f"    ✓ DB에서 삭제 완료")
                    else:
                        logger.warning(f"    ⚠ DB 삭제 실패 (RAGFlow는 삭제됨)")
                else:
                    ragflow_failed += 1
                    failed_items.append({
                        'document_id': doc_id,
                        'file_id': file_id,
                        'file_name': file_name,
                        'reason': failure_reason
                    })
                    logger.warning(f"    ✗ 삭제 실패: {failure_reason} - DB는 유지됨")
            
            logger.info(f"✓ 삭제 완료: RAGFlow {ragflow_deleted}개, DB {db_deleted}개, 실패 {ragflow_failed}개")
            
            # 결과 요약
            logger.info("\n" + "="*80)
            logger.info("삭제 작업 완료")
            logger.info("-"*80)
            logger.info(f"지식베이스: {dataset_name}")
            logger.info(f"총 문서 수: {total_docs}")
            logger.info(f"RAGFlow 삭제: {ragflow_deleted}개 (실패: {ragflow_failed}개)")
            logger.info(f"RevisionDB 삭제: {db_deleted}개")
            
            if failed_items:
                logger.warning(f"\n실패한 문서 목록:")
                for item in failed_items[:10]:  # 최대 10개만 표시
                    file_id_info = f", 파일ID: {item['file_id']}" if item.get('file_id') else ""
                    logger.warning(f"  - {item['file_name']} (문서ID: {item['document_id']}{file_id_info}) - {item['reason']}")
                if len(failed_items) > 10:
                    logger.warning(f"  ... 외 {len(failed_items) - 10}개")
            
            logger.info("="*80)
            
            return {
                'success': True,
                'dataset_name': dataset_name,
                'dataset_id': dataset_id,
                'total_documents': total_docs,
                'ragflow_deleted': ragflow_deleted,
                'ragflow_failed': ragflow_failed,
                'db_deleted': db_deleted,
                'failed_items': failed_items
            }
        
        except Exception as e:
            logger.error(f"문서 삭제 중 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': str(e)
            }
    
    def parse_non_failed_documents_by_dataset_name(self, dataset_name: str, monitor_progress: bool = True):
        """
        지식베이스 내 문서 상태를 확인하고, Failed('4')가 아닌 문서들을 파싱
        (이미 완료('3')되거나 실행 중('1')인 문서는 제외하고 UNSTART('0'), CANCEL('2') 등 대상)
        
        Args:
            dataset_name: 지식베이스 이름
            monitor_progress: 파싱 진행 상황 모니터링 여부
        """
        logger.info("="*80)
        logger.info(f"지식베이스 '{dataset_name}' 상태 기반 파싱 (Non-Failed)")
        logger.info("="*80)
        
        try:
            # 1. 지식베이스 조회
            dataset = self.ragflow_client.get_dataset_by_name(dataset_name)
            if not dataset:
                logger.error(f"지식베이스 '{dataset_name}'을 찾을 수 없습니다.")
                return
            
            logger.info(f"문서 목록 조회 중... (Dataset ID: {dataset.get('id')})")
            
            # 2. 문서 목록 조회
            all_documents = []
            page = 1
            while True:
                docs = self.ragflow_client.get_documents_in_dataset(dataset, page=page, page_size=100)
                if not docs:
                    break
                all_documents.extend(docs)
                if len(docs) < 100:
                    break
                page += 1
            
            if not all_documents:
                logger.warning("문서가 없습니다.")
                return

            logger.info(f"총 {len(all_documents)}개 문서 검사 시작")

            # 3. 상태 필터링
            # run status: '0': UNSTART, '1': RUNNING, '2': CANCEL, '3': DONE, '4': FAIL
            target_ids = []
            skipped_counts = {'RUNNING': 0, 'DONE': 0, 'FAIL': 0}
            
            for doc in all_documents:
                run_status = str(doc.get('run', '0'))
                doc_id = doc.get('id')
                doc_name = doc.get('name', 'Unknown')
                
                if run_status == '4':  # FAIL
                    skipped_counts['FAIL'] += 1
                    logger.debug(f"  [Skip] Failed 상태: {doc_name}")
                elif run_status == '3':  # DONE
                    skipped_counts['DONE'] += 1
                elif run_status == '1':  # RUNNING
                    skipped_counts['RUNNING'] += 1
                else:
                    # '0' (UNSTART), '2' (CANCEL) 등
                    target_ids.append(doc_id)
                    logger.debug(f"  [Target] 파싱 대상 추가 (Status: {run_status}): {doc_name}")

            logger.info("-" * 40)
            logger.info(f"상태 검사 결과:")
            logger.info(f"  - 파싱 대상 (UNSTART/CANCEL): {len(target_ids)}개")
            logger.info(f"  - 건너뜀 (완료): {skipped_counts['DONE']}개")
            logger.info(f"  - 건너뜀 (실행중): {skipped_counts['RUNNING']}개")
            logger.info(f"  - 건너뜀 (실패 - 제외됨): {skipped_counts['FAIL']}개")
            
            if not target_ids:
                logger.info("파싱할 대상 문서가 없습니다.")
                return

            # 4. 파싱 요청
            logger.info(f"\n{len(target_ids)}개 문서 파싱 시작...")
            parse_started = self.ragflow_client.start_batch_parse(
                dataset,
                document_ids=target_ids
            )
            
            if parse_started and monitor_progress and MONITOR_PARSE_PROGRESS:
                self.monitor_parse_progress(dataset, dataset_name, target_ids, max_wait_minutes=PARSE_TIMEOUT_MINUTES)
            elif parse_started:
                logger.info(f"[{dataset_name}] 파싱이 백그라운드에서 진행됩니다.")

        except Exception as e:
            logger.error(f"작업 중 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def cancel_parsing_documents_by_dataset_name(self, dataset_name: str, confirm: bool = False):
        """
        특정 데이터셋의 파싱 중인(RUNNING) 문서를 파싱 취소
        
        Args:
            dataset_name: 지식베이스 이름
            confirm: 실제 실행 여부 확인 플래그
        """
        logger.info("="*80)
        logger.info(f"지식베이스 '{dataset_name}' 파싱 취소 (Running 상태 문서)")
        logger.info("="*80)
        
        try:
            # 1. 지식베이스 조회
            dataset = self.ragflow_client.get_dataset_by_name(dataset_name)
            if not dataset:
                logger.error(f"지식베이스 '{dataset_name}'을 찾을 수 없습니다.")
                return
            
            logger.info(f"문서 목록 조회 중... (Dataset ID: {dataset.get('id')})")
            
            # 2. 문서 목록 조회
            all_documents = []
            page = 1
            while True:
                docs = self.ragflow_client.get_documents_in_dataset(dataset, page=page, page_size=100)
                if not docs:
                    break
                all_documents.extend(docs)
                if len(docs) < 100:
                    break
                page += 1
            
            if not all_documents:
                logger.warning("문서가 없습니다.")
                return

            # 3. RUNNING 상태 문서 필터링
            running_ids = []
            
            for doc in all_documents:
                # run status: '1': RUNNING
                run_status = str(doc.get('run', '0'))
                doc_id = doc.get('id')
                doc_name = doc.get('name', 'Unknown')
                
                if run_status == '1':  # RUNNING
                    running_ids.append(doc_id)
                    logger.debug(f"  [Running] 파싱 취소 대상: {doc_name}")
            
            logger.info("-" * 40)
            logger.info(f"검사 결과:")
            logger.info(f"  - 파싱 중(Running) 문서: {len(running_ids)}개")
            
            if not running_ids:
                logger.info("파싱 중인 문서가 없습니다.")
                return
            
            if not confirm:
                logger.info("\n실제로 파싱을 취소하려면 --confirm 옵션을 사용하세요.")
                logger.info(f"  예: python run.py --cancel-parsing \"{dataset_name}\" --confirm")
                return

            # 4. 파싱 취소 요청
            logger.info(f"\n{len(running_ids)}개 문서 파싱 취소 요청 중...")
            if self.ragflow_client.stop_batch_parse(dataset, running_ids):
                logger.info("✓ 파싱 취소 요청이 성공적으로 전송되었습니다.")
            else:
                logger.error("✗ 파싱 취소 요청 실패")

        except Exception as e:
            logger.error(f"작업 중 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def get_running_document_count(self, dataset) -> tuple:
        """
        특정 데이터셋에서 현재 파싱 중(RUNNING)인 문서 수와 전체 상태 정보를 반환
        
        Args:
            dataset: 데이터셋 딕셔너리
            
        Returns:
            (running_count, status_counts) 튜플
            - running_count: RUNNING 상태 문서 수
            - status_counts: 상태별 문서 수 딕셔너리
        """
        try:
            all_documents = []
            page = 1
            while True:
                docs = self.ragflow_client.get_documents_in_dataset(dataset, page=page, page_size=100)
                if not docs:
                    break
                all_documents.extend(docs)
                if len(docs) < 100:
                    break
                page += 1
            
            status_counts = {'UNSTART': 0, 'RUNNING': 0, 'CANCEL': 0, 'DONE': 0, 'FAIL': 0, 'TOTAL': len(all_documents)}
            
            for doc in all_documents:
                run_status = str(doc.get('run', '0'))
                if run_status == '0':
                    status_counts['UNSTART'] += 1
                elif run_status == '1':
                    status_counts['RUNNING'] += 1
                elif run_status == '2':
                    status_counts['CANCEL'] += 1
                elif run_status == '3':
                    status_counts['DONE'] += 1
                elif run_status == '4':
                    status_counts['FAIL'] += 1
            
            return status_counts['RUNNING'], status_counts
            
        except Exception as e:
            logger.error(f"RUNNING 문서 수 조회 실패: {e}")
            return 0, {}

    def throttle_parse_by_dataset_name(
        self,
        dataset_name: str,
        confirm: bool = False,
        concurrency_limit: int = None,
        include_done: bool = False,
        include_failed: bool = False,
        check_interval: int = 10,
        max_hours: float = 2.0
    ):
        """
        동시 파싱 수를 제한하면서 전체 문서 파싱 수행
        
        현재 RUNNING 상태의 문서 수를 기준으로 동시 파싱 수를 제한하여
        서버 부하를 조절하면서 전체 문서를 파싱합니다.
        
        Args:
            dataset_name: 지식베이스 이름 (특수값 "ALL"이면 모든 데이터셋)
            confirm: True여야 실제 실행
            concurrency_limit: 동시 파싱 수 제한 (None이면 현재 RUNNING 수 사용)
            include_done: DONE 상태 문서 포함 여부 (재파싱)
            include_failed: FAIL 상태 문서 포함 여부
            check_interval: 상태 확인 간격 (초)
            max_hours: 최대 동작 시간 (시간 단위, 기본: 2시간)
        """
        # "ALL" 옵션 처리 - 모든 데이터셋 대상
        if dataset_name.upper() == "ALL":
            logger.info("=" * 80)
            logger.info("모든 지식베이스 동시성 제한 파싱 (Throttled Parse ALL)")
            logger.info("=" * 80)
            
            # 전체 데이터셋 목록 조회
            all_datasets = self.ragflow_client.list_datasets(page=1, page_size=1000)
            if not all_datasets:
                logger.warning("지식베이스가 없습니다.")
                return
            
            logger.info(f"총 {len(all_datasets)}개 지식베이스 발견:")
            for ds in all_datasets:
                logger.info(f"  - {ds.get('name')} (ID: {ds.get('id')})")
            
            if not confirm:
                logger.info("\n" + "=" * 80)
                logger.info("실제로 파싱을 실행하려면 --confirm 옵션을 추가하세요.")
                logger.info('  예: python run.py --throttle-parse "ALL" --confirm')
                logger.info(f"\n예상 동작:")
                logger.info(f"  - 대상: 모든 지식베이스 ({len(all_datasets)}개)")
                logger.info(f"  - 동시 파싱 수: {concurrency_limit or '자동 감지'}개")
                logger.info(f"  - 확인 간격: {check_interval}초")
                logger.info(f"  - 최대 동작 시간: {max_hours}시간")
                logger.info("=" * 80)
                return
            
            # 각 데이터셋에 대해 순차적으로 파싱 실행
            logger.info("\n" + "=" * 80)
            logger.info("모든 지식베이스 파싱 시작")
            logger.info("=" * 80)
            # ALL: API 목록 역순으로 데이터셋별 파싱 (고정)
            for idx, dataset in enumerate(reversed(all_datasets), 1):
                ds_name = dataset.get('name')
                logger.info(f"\n[{idx}/{len(all_datasets)}] 처리 중: {ds_name}")
                logger.info("-" * 60)
                
                try:
                    # 개별 데이터셋 파싱 (재귀 호출)
                    self.throttle_parse_by_dataset_name(
                        dataset_name=ds_name,
                        confirm=True,  # 이미 확인했으므로 True
                        concurrency_limit=concurrency_limit,
                        include_done=include_done,
                        include_failed=include_failed,
                        check_interval=check_interval,
                        max_hours=max_hours
                    )
                except Exception as e:
                    logger.error(f"지식베이스 '{ds_name}' 파싱 중 오류: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    logger.info("다음 지식베이스로 계속...")
            
            logger.info("\n" + "=" * 80)
            logger.info("모든 지식베이스 파싱 완료")
            logger.info("=" * 80)
            return
        
        # 기존 로직: 특정 데이터셋 파싱
        logger.info("=" * 80)
        logger.info(f"지식베이스 '{dataset_name}' 동시성 제한 파싱 (Throttled Parse)")
        logger.info("=" * 80)
        
        try:
            # 1. 지식베이스 조회
            dataset = self.ragflow_client.get_dataset_by_name(dataset_name)
            if not dataset:
                logger.error(f"지식베이스 '{dataset_name}'을 찾을 수 없습니다.")
                return
            
            dataset_id = dataset.get('id')
            logger.info(f"Dataset ID: {dataset_id}")
            
            # 2. 현재 상태 조회
            running_count, status_counts = self.get_running_document_count(dataset)
            
            logger.info("-" * 40)
            logger.info("현재 문서 상태:")
            logger.info(f"  - 총 문서: {status_counts.get('TOTAL', 0)}개")
            logger.info(f"  - UNSTART: {status_counts.get('UNSTART', 0)}개")
            logger.info(f"  - RUNNING: {status_counts.get('RUNNING', 0)}개")
            logger.info(f"  - CANCEL: {status_counts.get('CANCEL', 0)}개")
            logger.info(f"  - DONE: {status_counts.get('DONE', 0)}개")
            logger.info(f"  - FAIL: {status_counts.get('FAIL', 0)}개")
            
            # 3. 동시성 제한 설정
            if concurrency_limit is None:
                if running_count > 0:
                    concurrency_limit = running_count
                    logger.info(f"\n✓ 동시성 제한: 현재 RUNNING 수 기준 → {concurrency_limit}개")
                else:
                    concurrency_limit = 5  # 기본값
                    logger.info(f"\n⚠ 현재 RUNNING 문서가 없어 기본값 사용: {concurrency_limit}개")
            else:
                logger.info(f"\n✓ 동시성 제한: 사용자 지정 → {concurrency_limit}개")
            
            # 4. 파싱 대상 문서 수집
            all_documents = []
            page = 1
            while True:
                docs = self.ragflow_client.get_documents_in_dataset(dataset, page=page, page_size=100)
                if not docs:
                    break
                all_documents.extend(docs)
                if len(docs) < 100:
                    break
                page += 1
            
            # 파싱 대상: UNSTART, CANCEL, (옵션) DONE, (옵션) FAIL
            pending_ids = []
            for doc in all_documents:
                run_status = str(doc.get('run', '0'))
                doc_id = doc.get('id')
                
                if run_status in ['0', '2']:  # UNSTART, CANCEL
                    pending_ids.append(doc_id)
                elif run_status == '3' and include_done:  # DONE (재파싱)
                    pending_ids.append(doc_id)
                elif run_status == '4' and include_failed:  # FAIL
                    pending_ids.append(doc_id)
            
            total_pending = len(pending_ids)
            logger.info(f"파싱 대기 문서: {total_pending}개")
            logger.info(f"  - 옵션: include_done={include_done}, include_failed={include_failed}")
            
            if total_pending == 0:
                logger.info("파싱할 문서가 없습니다.")
                return
            
            if not confirm:
                logger.info("\n" + "-" * 40)
                logger.info("실제로 파싱을 실행하려면 --confirm 옵션을 추가하세요.")
                logger.info(f'  예: python run.py --throttle-parse "{dataset_name}" --confirm')
                logger.info(f"\n예상 동작:")
                logger.info(f"  - 동시 파싱 수: {concurrency_limit}개 유지")
                logger.info(f"  - 파싱 대상: {total_pending}개")
                logger.info(f"  - 확인 간격: {check_interval}초")
                logger.info(f"  - 최대 동작 시간: {max_hours}시간")
                return
            
            # 5. 동시성 제한 파싱 실행
            logger.info("\n" + "=" * 80)
            logger.info("동시성 제한 파싱 시작")
            logger.info(f"최대 동작 시간: {max_hours}시간")
            logger.info("=" * 80)
            
            start_time = time.time()
            max_wait_seconds = max_hours * 3600  # 시간 -> 초
            
            submitted_ids = set()  # 이미 파싱 요청한 문서
            completed_ids = set()  # 완료된 문서
            
            # 전체 문서 목록은 이미 위에서 조회했으므로 all_documents 사용
            # pending_ids도 이미 계산됨
            logger.info(f"✓ 전체 문서 목록 캐시 완료: {len(all_documents)}개 (매 반복마다 재조회하지 않음)")
            
            while len(completed_ids) < total_pending:
                # 제출했지만 아직 완료되지 않은 문서 ID들
                in_progress_ids = list(submitted_ids - completed_ids)
                
                # 제출한 문서들의 현재 상태만 개별 조회 (전체 목록 조회 대신)
                our_running = 0
                if in_progress_ids:
                    # 진행 중인 문서들의 상태만 조회
                    in_progress_docs = self.ragflow_client.get_documents_by_ids(dataset, in_progress_ids)
                    
                    for doc in in_progress_docs:
                        doc_id = doc.get('id')
                        run_status = str(doc.get('run', '0'))
                        
                        if run_status in ['3', '4']:  # DONE or FAIL
                            completed_ids.add(doc_id)
                        elif run_status == '1':  # RUNNING
                            our_running += 1
                
                # 추가 가능한 슬롯 계산
                available_slots = concurrency_limit - our_running
                
                # 아직 제출하지 않은 문서 중 추가
                if available_slots > 0:
                    to_submit = []
                    for doc_id in pending_ids:
                        if doc_id not in submitted_ids and len(to_submit) < available_slots:
                            to_submit.append(doc_id)
                    
                    if to_submit:
                        logger.info(f"[{len(completed_ids)}/{total_pending}] "
                                   f"RUNNING: {our_running} → 추가 요청: {len(to_submit)}개")
                        
                        # 파싱 요청
                        if self.ragflow_client.start_batch_parse(dataset, document_ids=to_submit):
                            for doc_id in to_submit:
                                submitted_ids.add(doc_id)
                        else:
                            logger.warning("파싱 요청 실패, 재시도 예정...")
                else:
                    # 진행 상황 로그
                    if len(completed_ids) % 10 == 0 or our_running > 0:
                        logger.info(f"[{len(completed_ids)}/{total_pending}] "
                                   f"RUNNING: {our_running}/{concurrency_limit}")
                
                # 타임아웃 체크
                elapsed = time.time() - start_time
                if elapsed > max_wait_seconds:
                    logger.warning(f"⏱️ 최대 동작 시간 초과 ({max_hours}시간)")
                    logger.info(f"진행 상황: {len(completed_ids)}/{total_pending} 완료")
                    break
                
                # 모든 문서가 제출되고 완료되면 종료
                if len(submitted_ids) >= total_pending and len(completed_ids) >= len(submitted_ids):
                    break
                
                # 대기
                time.sleep(check_interval)
            
            # 최종 상태 확인
            _, final_status = self.get_running_document_count(dataset)
            
            elapsed_time = time.time() - start_time
            elapsed_minutes = elapsed_time / 60
            
            logger.info("\n" + "=" * 80)
            logger.info("파싱 완료")
            logger.info("-" * 40)
            logger.info(f"소요 시간: {elapsed_minutes:.1f}분")
            logger.info(f"완료된 문서: {len(completed_ids)}/{total_pending}개")
            logger.info(f"최종 상태:")
            logger.info(f"  - DONE: {final_status.get('DONE', 0)}개")
            logger.info(f"  - FAIL: {final_status.get('FAIL', 0)}개")
            logger.info(f"  - RUNNING: {final_status.get('RUNNING', 0)}개")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"동시성 제한 파싱 중 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def reparse_all_documents_by_dataset_name(
        self,
        dataset_name: str,
        confirm: bool = False,
        cancel_running: bool = False,
        include_running: bool = False,
        include_failed: bool = True,
        monitor_progress: bool = True,
        page_size: int = 100
    ):
        """
        특정 지식베이스의 "모든 문서"를 재파싱합니다.
        
        기본 동작:
        - 문서 목록을 전부 조회
        - RUNNING 문서는 기본적으로 제외 (include_running=False)
        - confirm=True일 때만 재파싱을 시작 (서버가 기존 청크/작업을 정리하고 재큐잉함)
        
        Args:
            dataset_name: 지식베이스 이름
            confirm: True여야 실제 실행 (재파싱 시 서버가 기존 청크/작업을 정리하므로 안전장치)
            cancel_running: (호환 유지) True면 RUNNING 문서도 대상으로 포함하도록 허용
            include_running: True면 RUNNING 문서도 "재파싱 대상"으로 포함 (cancel_running과 함께 쓰는 것을 권장)
            include_failed: True면 FAIL 문서도 포함
            monitor_progress: 진행 모니터링 여부
            page_size: 문서 목록 페이지 크기
        """
        logger.info("=" * 80)
        logger.info(f"지식베이스 '{dataset_name}' 전체 문서 재파싱")
        logger.info("=" * 80)
        
        try:
            dataset = self.ragflow_client.get_dataset_by_name(dataset_name)
            if not dataset:
                logger.error(f"지식베이스 '{dataset_name}'을 찾을 수 없습니다.")
                return
            
            # 1) 문서 목록 전체 수집
            all_documents = []
            page = 1
            while True:
                docs = self.ragflow_client.get_documents_in_dataset(dataset, page=page, page_size=page_size)
                if not docs:
                    break
                all_documents.extend(docs)
                if len(docs) < page_size:
                    break
                page += 1
            
            if not all_documents:
                logger.warning("문서가 없습니다.")
                return
            
            # 2) 대상 문서 선정
            # run status: '0': UNSTART, '1': RUNNING, '2': CANCEL, '3': DONE, '4': FAIL
            target_ids = []
            doc_run_map = {}
            counts = {'TOTAL': len(all_documents), 'RUNNING': 0, 'DONE': 0, 'UNSTART': 0, 'CANCEL': 0, 'FAIL': 0, 'UNKNOWN': 0}
            
            for doc in all_documents:
                run_status = str(doc.get('run', '0'))
                doc_id = doc.get('id')
                if not doc_id:
                    continue
                doc_run_map[doc_id] = run_status
                
                if run_status == '1':
                    counts['RUNNING'] += 1
                    if include_running:
                        target_ids.append(doc_id)
                elif run_status == '3':
                    counts['DONE'] += 1
                    target_ids.append(doc_id)
                elif run_status == '4':
                    counts['FAIL'] += 1
                    if include_failed:
                        target_ids.append(doc_id)
                elif run_status == '2':
                    counts['CANCEL'] += 1
                    target_ids.append(doc_id)
                elif run_status == '0':
                    counts['UNSTART'] += 1
                    target_ids.append(doc_id)
                else:
                    counts['UNKNOWN'] += 1
                    target_ids.append(doc_id)
            
            # 중복 제거 (방어)
            target_ids = list(dict.fromkeys(target_ids))
            
            logger.info("-" * 40)
            logger.info("문서 상태 요약:")
            logger.info(f"  - 총 문서: {counts['TOTAL']}개")
            logger.info(f"  - UNSTART: {counts['UNSTART']}개")
            logger.info(f"  - CANCEL: {counts['CANCEL']}개")
            logger.info(f"  - DONE: {counts['DONE']}개")
            logger.info(f"  - FAIL: {counts['FAIL']}개 (include_failed={include_failed})")
            logger.info(f"  - RUNNING: {counts['RUNNING']}개 (include_running={include_running})")
            if counts['UNKNOWN'] > 0:
                logger.info(f"  - UNKNOWN: {counts['UNKNOWN']}개")
            logger.info(f"재파싱 대상 문서: {len(target_ids)}개")
            
            if not target_ids:
                logger.info("재파싱할 대상 문서가 없습니다.")
                return
            
            if not confirm:
                logger.info("\n실제로 재파싱을 실행하려면 --confirm 옵션을 추가하세요.")
                logger.info(f'  예: python run.py --reparse-all "{dataset_name}" --confirm')
                logger.info("주의: --confirm 실행 시 대상 문서의 기존 청크가 삭제(리셋)됩니다.")
                return
            
            # 3) RUNNING 문서 처리 정책
            if counts['RUNNING'] > 0 and include_running and not cancel_running:
                logger.warning("RUNNING 문서를 포함하려면 --cancel-running 옵션을 함께 사용하세요. (안전)")
                logger.warning("현재 설정에서는 RUNNING 문서를 대상에서 제외합니다.")
                # 대상에서 RUNNING 문서를 제거
                running_ids = {d.get('id') for d in all_documents if str(d.get('run', '0')) == '1'}
                target_ids = [i for i in target_ids if i not in running_ids]
            
            # 4) 재파싱 시작
            # 참고: RAGFlow v21 API(POST /datasets/{id}/chunks)는 내부에서 기존 chunk/index/task를 정리하고 재큐잉한다.
            logger.info("\n재파싱 시작...")
            parse_started = self.ragflow_client.start_batch_parse(dataset, document_ids=target_ids)
            if not parse_started:
                logger.error("재파싱 요청 실패")
                return
            
            if monitor_progress and MONITOR_PARSE_PROGRESS:
                self.monitor_parse_progress(dataset, dataset_name, target_ids, max_wait_minutes=PARSE_TIMEOUT_MINUTES)
            else:
                logger.info(f"[{dataset_name}] 재파싱이 백그라운드에서 진행됩니다.")
        
        except Exception as e:
            logger.error(f"전체 재파싱 중 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())

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
        
        logger.info("-"*80)
        
        # 다운로드 캐시 통계
        try:
            db_stats = self.revision_db.get_statistics()
            cached_downloads = db_stats.get('cached_downloads', 0)
            if cached_downloads > 0:
                logger.info(f"다운로드 캐시: {cached_downloads}개 URL 캐시됨")
                logger.info("-"*80)
        except Exception as e:
            logger.debug(f"다운로드 캐시 통계 조회 실패: {e}")
        
        logger.info("="*80)

    def sync_dataset_with_db(self, dataset_name: str, fix: bool = False) -> Dict:
        """
        RAGFlow Dataset과 RevisionDB 간의 데이터 정합성 검사 및 동기화
        
        Args:
            dataset_name: 데이터셋 이름
            fix: True이면 불일치 항목 자동 수정 (RAGFlow에서 고아 문서 삭제)
            
        Returns:
            검사 결과 (orphans, ghosts 등)
        """
        logger.info("="*80)
        logger.info(f"데이터 정합성 검사 (Sync Check): {dataset_name}")
        logger.info("="*80)
        
        result = {
            'success': False,
            'ragflow_count': 0,
            'db_count': 0,
            'orphans': [],  # RAGFlow에만 있음 (삭제 대상)
            'ghosts': [],   # DB에만 있음 (DB에서 삭제 대상)
            'fixed_count': 0
        }
        
        try:
            # 1. RAGFlow 데이터 조회
            dataset = self.ragflow_client.get_dataset_by_name(dataset_name)
            if not dataset:
                logger.error(f"지식베이스 '{dataset_name}'을 찾을 수 없습니다.")
                return result
                
            dataset_id = dataset.get('id')
            logger.info(f"RAGFlow 문서 목록 조회 중... (Dataset ID: {dataset_id})")
            
            ragflow_docs = []
            page = 1
            while True:
                docs = self.ragflow_client.get_documents_in_dataset(dataset, page=page, page_size=100)
                if not docs:
                    break
                ragflow_docs.extend(docs)
                if len(docs) < 100:
                    break
                page += 1
            
            result['ragflow_count'] = len(ragflow_docs)
            ragflow_map = {d['id']: d for d in ragflow_docs}
            logger.info(f"✓ RAGFlow 문서: {len(ragflow_docs)}개")
            
            # 2. RevisionDB 데이터 조회
            logger.info("RevisionDB 문서 목록 조회 중...")
            db_docs = self.revision_db.get_documents_by_dataset_name(dataset_name)
            result['db_count'] = len(db_docs)
            db_map = {d['document_id']: d for d in db_docs}
            logger.info(f"✓ RevisionDB 문서: {len(db_docs)}개")
            
            # 3. 불일치 분석
            # Orphans: RAGFlow에는 있는데 DB에는 없는 것 (삭제해야 함)
            for doc_id, doc in ragflow_map.items():
                if doc_id not in db_map:
                    result['orphans'].append({
                        'id': doc_id,
                        'name': doc.get('name')
                    })
            
            # Ghosts: DB에는 있는데 RAGFlow에는 없는 것 (DB에서 삭제해야 함)
            for doc_id, doc in db_map.items():
                if doc_id not in ragflow_map:
                    result['ghosts'].append({
                        'id': doc_id,
                        'key': doc.get('document_key'),
                        'name': doc.get('file_name')
                    })
            
            logger.info("-" * 40)
            logger.info(f"분석 결과:")
            logger.info(f"  - 정상 매칭: {len(ragflow_docs) - len(result['orphans'])}개")
            logger.info(f"  - 고아 문서 (RAGFlow Only): {len(result['orphans'])}개 {'(삭제 필요)' if result['orphans'] else ''}")
            logger.info(f"  - 유령 문서 (DB Only): {len(result['ghosts'])}개 {'(DB 정리 필요)' if result['ghosts'] else ''}")
            
            # 4. 수정 (Fix)
            if fix and (result['orphans'] or result['ghosts']):
                logger.info("-" * 40)
                logger.info("자동 복구(Fix) 시작...")
                
                # 고아 문서 삭제 (RAGFlow에서 삭제)
                for item in result['orphans']:
                    doc_id = item['id']
                    doc_name = item['name']
                    if self.ragflow_client.delete_document(dataset, doc_id):
                        logger.info(f"  ✓ 고아 문서 삭제됨: {doc_name} ({doc_id})")
                        result['fixed_count'] += 1
                    else:
                        logger.error(f"  ✗ 고아 문서 삭제 실패: {doc_name}")
                
                # 유령 문서 삭제 (DB에서 삭제)
                for item in result['ghosts']:
                    doc_id = item['id']
                    doc_key = item['key']
                    # 유령 문서는 이미 RAGFlow에 없으므로 안전하게 삭제 가능
                    self.revision_db.delete_document(doc_key, dataset_id, item['name'])
                    logger.info(f"  ✓ DB 유령 레코드 삭제됨: {item['name']} ({doc_key})")
                    result['fixed_count'] += 1
                
                logger.info("복구 완료")
            
            result['success'] = True
            return result
            
        except Exception as e:
            logger.error(f"동기화 검사 중 오류: {e}")
            return result


