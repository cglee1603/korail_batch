"""
로컬 파일시스템 처리 모듈
특정 폴더를 스캔하여 RAGFlow에 업로드하고 변경 사항을 감지
"""
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from logger import logger
from revision_db import RevisionDB
from ragflow_client import RAGFlowClient
from config import (
    DATASET_PERMISSION,
    CHUNK_METHOD,
    PARSER_CONFIG,
    AUTO_PARSE_AFTER_UPLOAD,
    MONITOR_PARSE_PROGRESS,
    PARSE_TIMEOUT_MINUTES
)

class FilesystemProcessor:
    """로컬 파일시스템 처리 클래스"""
    
    def __init__(self, root_path: str, revision_db: RevisionDB = None, file_handler=None):
        """
        Args:
            root_path: 스캔할 루트 디렉토리 경로
            revision_db: RevisionDB 인스턴스 (없으면 새로 생성)
            file_handler: 파일 처리 핸들러 (암복호화/변환용)
        """
        self.root_path = Path(root_path).resolve()
        if not self.root_path.exists():
            raise FileNotFoundError(f"경로를 찾을 수 없습니다: {root_path}")
            
        self.revision_db = revision_db if revision_db else RevisionDB()
        self.file_handler = file_handler  # FileHandler 주입
        self.ragflow_client = RAGFlowClient()
        
        self.stats = {
            'total_files': 0,
            'new_files': 0,
            'updated_files': 0,
            'skipped_files': 0,
            'failed_files': 0,
            'deleted_files': 0,
            'datasets_created': 0
        }

    def _calculate_file_hash(self, file_path: Path) -> str:
        """파일의 MD5 해시 계산"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _get_dataset_name(self, relative_path: Path) -> str:
        """
        상대 경로에서 Dataset 이름 추출
        규칙: 루트 바로 아래 폴더명을 Dataset 이름으로 사용
        예: 명칭도감/응급조치매뉴얼/aa.pdf -> 응급조치매뉴얼
        """
        parts = relative_path.parts
        if len(parts) > 0:
            return parts[0]
        return "Default"  # 루트 바로 아래 파일인 경우

    def _get_display_name(self, relative_path: Path) -> str:
        """
        상대 경로에서 표시용 파일명 생성
        규칙: 상위 폴더명을 파일명 앞에 붙임
        예: 명칭도감/응급조치매뉴얼/KTX응급조치매뉴얼/aa.pdf
            -> Dataset: 응급조치매뉴얼
            -> Relative: KTX응급조치매뉴얼/aa.pdf (Dataset 폴더 이후)
            -> Result: 응급조치매뉴얼_KTX응급조치매뉴얼_aa.pdf (전체 경로 반영)
        """
        # parts를 _로 연결
        return "_".join(relative_path.parts)

    def process(self):
        """파일시스템 스캔 및 처리 실행"""
        logger.info("="*80)
        logger.info(f"Filesystem 처리 시작: {self.root_path}")
        logger.info("="*80)

        try:
            # 1. 파일 목록 스캔 및 그룹화 (Dataset별)
            dataset_files: Dict[str, List[Path]] = {}
            
            for root, dirs, files in os.walk(self.root_path):
                # 숨김 폴더 제외
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    if file.startswith('.'):  # 숨김 파일 제외
                        continue
                        
                    file_path = Path(root) / file
                    try:
                        rel_path = file_path.relative_to(self.root_path)
                        dataset_name = self._get_dataset_name(rel_path)
                        if dataset_name not in dataset_files:
                            dataset_files[dataset_name] = []
                        dataset_files[dataset_name].append(file_path)
                    except ValueError:
                        logger.warning(f"경로 오류 (Skip): {file_path}")
                        continue

            # 2. Dataset별 처리
            for dataset_name, files in dataset_files.items():
                self._process_dataset(dataset_name, files)

            self._print_statistics()

        except Exception as e:
            logger.error(f"Filesystem 처리 중 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _process_dataset(self, dataset_name: str, files: List[Path]):
        """개별 Dataset 처리"""
        logger.info(f"\n[{dataset_name}] 처리 시작 ({len(files)}개 파일)")
        
        # 1. 지식베이스 생성/조회
        dataset_description = f"폴더 '{dataset_name}'에서 자동 생성된 지식베이스"
        dataset = self.ragflow_client.get_or_create_dataset(
            name=dataset_name,
            description=dataset_description,
            permission=DATASET_PERMISSION,
            embedding_model=None,
            chunk_method=CHUNK_METHOD,
            parser_config=PARSER_CONFIG
        )
        
        if not dataset:
            logger.error(f"[{dataset_name}] 지식베이스 생성 실패")
            return
            
        self.stats['datasets_created'] += 1
        dataset_id = dataset.get('id')
        
        # 2. DB에서 현재 Dataset의 모든 문서 미리 로드 (성능 및 정합성 향상)
        try:
            db_docs = self.revision_db.get_documents_by_dataset_name(dataset_name)
        except Exception as e:
            logger.warning(f"[{dataset_name}] DB 조회 실패 (신규로 간주): {e}")
            db_docs = []

        db_doc_map = {}  # document_key -> List[doc]
        for doc in db_docs:
            key = doc.get('document_key')
            if key:
                if key not in db_doc_map:
                    db_doc_map[key] = []
                db_doc_map[key].append(doc)
        
        if db_docs:
            logger.info(f"DB에서 기존 문서 {len(db_docs)}개 로드 완료")

        # 3. 파일 처리
        uploaded_doc_ids = []
        
        for file_path in files:
            try:
                self.stats['total_files'] += 1
                rel_path = file_path.relative_to(self.root_path)
                
                # document_key: 상대 경로 전체를 키로 사용 (불변)
                # Windows 경로 구분자(\)를 표준(/)으로 통일하여 DB 키로 사용
                document_key = str(rel_path).replace('\\', '/')
                
                # display_name: 경로 기반 이름 생성 (확장자 포함)
                display_name = self._get_display_name(rel_path)
                
                # 파일 해시 계산
                current_hash = self._calculate_file_hash(file_path)
                
                # DB 확인 (document_key로 조회)
                existing_docs = db_doc_map.get(document_key, [])
                
                if existing_docs:
                    # 변경 감지 (첫 번째 문서의 해시와 비교)
                    db_hash = existing_docs[0].get('file_hash')
                    
                    if db_hash == current_hash:
                        logger.info(f"  [Skip] 변경 없음: {display_name}")
                        self.stats['skipped_files'] += 1
                        continue
                    else:
                        logger.info(f"  [Update] 변경 감지: {display_name}")
                        # 기존 문서 모두 삭제 (RAGFlow)
                        # 압축 파일인 경우 하나의 key에 여러 문서가 매핑될 수 있음
                        for doc in existing_docs:
                            if doc.get('document_id'):
                                self.ragflow_client.delete_document(dataset, doc['document_id'])
                        
                        # DB에서도 삭제
                        self.revision_db.delete_document(document_key, dataset_id)
                else:
                    logger.info(f"  [New] 신규 파일: {display_name}")

                # 파일 변환 및 전처리
                processed_files = []
                if self.file_handler:
                    # 암복호화, PDF 변환 등 수행
                    processed_files = self.file_handler.process_file(file_path)
                else:
                    # FileHandler가 없는 경우 원본 파일 그대로 사용 (fallback)
                    ext = file_path.suffix.lower().lstrip('.')
                    processed_files = [(file_path, ext)]

                if not processed_files:
                    logger.error(f"  [Fail] 파일 처리 실패: {display_name}")
                    self.stats['failed_files'] += 1
                    continue

                # 압축 파일 여부 확인
                is_archive = file_path.suffix.lower() == '.zip' and len(processed_files) > 1
                archive_source = file_path.name if is_archive else None

                if is_archive:
                    logger.info(f"  [Archive] 압축 파일 내 {len(processed_files)}개 파일 추출됨")

                for processed_path, file_type in processed_files:
                    # 최종 파일명 생성
                    # display_name: 상위폴더_하위폴더_원본파일명.확장자
                    # file_path.name: 원본파일명.확장자
                    # processed_path.name: 처리된파일명.확장자 (예: 원본_part1.pdf)
                    
                    # 접두어 추출 (상위폴더_하위폴더_)
                    prefix = display_name[:-len(file_path.name)]
                    
                    # 최종 이름: 접두어 + 처리된 파일명
                    final_display_name = f"{prefix}{processed_path.name}" if prefix else processed_path.name

                    metadata = {
                        '원본경로': str(file_path),
                        '상대경로': str(rel_path),
                        '파일명': file_path.name,
                        '파일형식': file_type
                    }
                    
                    if is_archive:
                        metadata['압축파일'] = archive_source
                        metadata['압축파일_내_파일명'] = processed_path.name

                    upload_result = self.ragflow_client.upload_document(
                        dataset=dataset,
                        file_path=processed_path,
                        metadata=metadata,
                        display_name=final_display_name
                    )
                    
                    if upload_result:
                        doc_id = upload_result.get('document_id')
                        file_id = upload_result.get('file_id')
                        uploaded_doc_ids.append(doc_id)
                        
                        # Excel 파일인 경우 chunk_method를 "table"로 설정
                        if file_type in ['xlsx', 'xls', 'xlsm']:
                            self.ragflow_client.update_document_parser(
                                dataset_id=dataset_id,
                                document_id=doc_id,
                                chunk_method="table"
                            )
                        
                        # DB 저장/갱신
                        self.revision_db.save_document(
                            document_key=document_key,
                            document_id=doc_id,
                            dataset_id=dataset_id,
                            dataset_name=dataset_name,
                            file_path=str(processed_path),
                            file_name=final_display_name,
                            file_id=file_id,
                            file_hash=current_hash,
                            is_part_of_archive=is_archive,
                            archive_source=archive_source
                        )
                        
                        if existing_docs:
                            self.stats['updated_files'] += 1
                        else:
                            self.stats['new_files'] += 1
                    else:
                        logger.error(f"  [Fail] 업로드 실패: {final_display_name}")
                        self.stats['failed_files'] += 1
                
                # 처리 완료 후 임시 파일 정리
                if self.file_handler:
                    self.file_handler.cleanup_processed_files(processed_files)
                        
            except Exception as e:
                logger.error(f"파일 처리 중 오류 ({file_path}): {e}")
                self.stats['failed_files'] += 1
                import traceback
                logger.error(traceback.format_exc())

        # 일괄 파싱 시작
        if uploaded_doc_ids:
            if AUTO_PARSE_AFTER_UPLOAD:
                logger.info(f"[{dataset_name}] {len(uploaded_doc_ids)}개 문서 파싱 시작")
                parse_started = self.ragflow_client.start_batch_parse(
                    dataset,
                    document_ids=uploaded_doc_ids
                )
                
                if parse_started and MONITOR_PARSE_PROGRESS:
                    logger.info(f"[{dataset_name}] 파싱이 백그라운드에서 시작되었습니다.")
            else:
                logger.info(f"[{dataset_name}] {len(uploaded_doc_ids)}개 문서 업로드 완료 (자동 파싱 비활성화)")

    def _print_statistics(self):
        """통계 출력"""
        logger.info("="*80)
        logger.info("Filesystem 처리 통계")
        logger.info("-"*80)
        logger.info(f"총 파일 수: {self.stats['total_files']}")
        logger.info(f"신규 추가: {self.stats['new_files']}")
        logger.info(f"업데이트: {self.stats['updated_files']}")
        logger.info(f"건너뜀 (변경없음): {self.stats['skipped_files']}")
        logger.info(f"실패: {self.stats['failed_files']}")
        logger.info(f"생성된 Dataset: {self.stats['datasets_created']}")
        logger.info("="*80)
