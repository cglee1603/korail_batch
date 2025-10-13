"""
RAGFlow API 연동 모듈
"""
from typing import Optional, List, Dict
from pathlib import Path
from ragflow_sdk import RAGFlow
from logger import logger
from config import RAGFLOW_API_KEY, RAGFLOW_BASE_URL


class RAGFlowClient:
    """RAGFlow API 클라이언트"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or RAGFLOW_API_KEY
        self.base_url = base_url or RAGFLOW_BASE_URL
        
        if not self.api_key:
            raise ValueError("RAGFlow API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
        
        self.rag = RAGFlow(api_key=self.api_key, base_url=self.base_url)
        logger.info(f"RAGFlow 클라이언트 초기화 완료 (URL: {self.base_url})")
    
    def get_or_create_dataset(
        self, 
        name: str, 
        description: str = "",
        permission: str = "me"
    ) -> Optional[object]:
        """
        지식베이스 삭제 후 재생성
        
        동일한 이름의 지식베이스가 존재하면 삭제하고 새로 생성합니다.
        
        Args:
            name: 지식베이스 이름
            description: 설명
            permission: 권한 설정 ("me": 나만, "team": 팀 공유)
        
        Returns:
            Dataset 객체 또는 None
        """
        # 1. 기존 지식베이스 검색 및 삭제
        try:
            datasets = self.rag.list_datasets(name=name)
            
            if datasets and len(datasets) > 0:
                logger.info(f"기존 지식베이스 발견: {name} (총 {len(datasets)}개)")
                
                # 모든 동일 이름 지식베이스 삭제 시도
                for idx, dataset in enumerate(datasets, 1):
                    try:
                        dataset_id = dataset.id if hasattr(dataset, 'id') else 'Unknown'
                        logger.info(f"기존 지식베이스 삭제 시도 [{idx}/{len(datasets)}]: {name} (ID: {dataset_id})")
                        dataset.delete()
                        logger.info(f"✓ 지식베이스 삭제 완료: {name}")
                    except Exception as delete_error:
                        error_msg = str(delete_error)
                        if "don't own" in error_msg.lower() or "permission" in error_msg.lower():
                            logger.error(f"✗ 삭제 권한 없음: {name} - 다른 사용자 소유")
                            logger.error(f"  다른 사용자가 소유한 '{name}' 지식베이스가 존재하여 생성할 수 없습니다.")
                            return None
                        else:
                            logger.error(f"✗ 지식베이스 삭제 실패: {delete_error}")
                            return None
        
        except Exception as list_error:
            error_msg = str(list_error)
            if "don't own" in error_msg.lower() or "permission" in error_msg.lower():
                logger.error(f"✗ 지식베이스 '{name}' 검색 실패 - 다른 사용자 소유")
                logger.error(f"  다른 사용자가 소유한 '{name}' 지식베이스가 존재하여 생성할 수 없습니다.")
                return None
            # 검색 결과 없음 또는 다른 에러 - 계속 진행
            logger.debug(f"지식베이스 검색 중 에러 (무시하고 계속): {list_error}")
        
        # 2. 새 지식베이스 생성
        try:
            logger.info(f"새 지식베이스 생성: {name}")
            dataset = self.rag.create_dataset(
                name=name,
                description=description,
                permission=permission
            )
            logger.info(f"✓ 지식베이스 생성 성공: {name}")
            return dataset
        
        except Exception as create_error:
            logger.error(f"✗ 지식베이스 생성 실패 ({name}): {create_error}")
            return None
    
    def upload_document(
        self, 
        dataset: object, 
        file_path: Path, 
        metadata: Dict[str, str] = None,
        display_name: str = None
    ) -> bool:
        """
        파일을 지식베이스에 업로드
        
        Args:
            dataset: Dataset 객체
            file_path: 업로드할 파일 경로
            metadata: 메타데이터
            display_name: 표시 이름
        
        Returns:
            성공 여부
        """
        try:
            if not file_path.exists():
                logger.error(f"파일이 존재하지 않습니다: {file_path}")
                return False
            
            # 파일 읽기
            with open(file_path, 'rb') as f:
                blob = f.read()
            
            # 파일명 설정
            if not display_name:
                display_name = file_path.name
            
            # 업로드할 문서 정보
            doc_info = {
                "display_name": display_name,
                "blob": blob
            }
            
            logger.info(f"파일 업로드 시작: {display_name}")
            uploaded_docs = dataset.upload_documents([doc_info])
            
            # 메타데이터 설정 (업로드 후)
            if metadata and uploaded_docs and len(uploaded_docs) > 0:
                doc = uploaded_docs[0]
                self.set_document_metadata(doc, metadata)
            
            logger.info(f"파일 업로드 완료: {display_name}")
            return True
        
        except Exception as e:
            logger.error(f"파일 업로드 실패 ({file_path}): {e}")
            return False
    
    def set_document_metadata(
        self, 
        doc: object, 
        metadata: Dict[str, str]
    ):
        """
        문서에 메타데이터 설정
        
        Args:
            doc: Document 객체
            metadata: 설정할 메타데이터 (dict)
        """
        try:
            doc_name = doc.name if hasattr(doc, 'name') else 'Unknown'
            logger.log_metadata(doc_name, metadata)
            
            # RAGFlow SDK의 Document.update() 메서드 사용
            # meta_fields는 dict 타입이어야 함
            doc.update({"meta_fields": metadata})
            
            logger.info(f"메타데이터 설정 완료: {doc_name}")
        
        except Exception as e:
            doc_name = doc.name if hasattr(doc, 'name') else 'Unknown'
            logger.error(f"메타데이터 설정 실패 ({doc_name}): {e}")
    
    def start_batch_parse(self, dataset: object) -> bool:
        """
        지식베이스의 모든 문서를 순차적으로 파싱
        
        각 문서를 파싱하고 완료될 때까지 기다린 후 다음 문서로 진행합니다.
        """
        import time
        
        try:
            logger.info(f"일괄 파싱 시작: {dataset.name}")
            
            # 모든 문서 목록 가져오기
            documents = dataset.list_documents()
            
            if not documents:
                logger.warning("파싱할 문서가 없습니다.")
                return True
            
            logger.info(f"총 {len(documents)}개 문서 파싱 예정")
            
            # 각 문서를 순차적으로 파싱
            success_count = 0
            failed_count = 0
            
            for idx, doc in enumerate(documents, 1):
                doc_name = doc.name if hasattr(doc, 'name') else 'Unknown'
                
                try:
                    logger.info(f"\n[{idx}/{len(documents)}] 문서 파싱 시작: {doc_name}")
                    
                    # 파싱 메서드 확인
                    if not hasattr(doc, 'parse'):
                        logger.warning(f"파싱 메서드를 찾을 수 없습니다: {doc_name}")
                        failed_count += 1
                        continue
                    
                    # 파싱 요청
                    doc.parse()
                    logger.info(f"  → 파싱 요청 완료, 상태 모니터링 시작...")
                    
                    # 파싱 완료 대기 (상태 모니터링)
                    if self._wait_for_parsing_complete(doc, doc_name):
                        success_count += 1
                        logger.info(f"  ✓ [{idx}/{len(documents)}] 파싱 완료: {doc_name}")
                    else:
                        failed_count += 1
                        logger.error(f"  ✗ [{idx}/{len(documents)}] 파싱 실패 또는 타임아웃: {doc_name}")
                
                except Exception as e:
                    failed_count += 1
                    logger.error(f"  ✗ [{idx}/{len(documents)}] 문서 파싱 중 에러 ({doc_name}): {e}")
                    continue
            
            # 최종 결과
            logger.info(f"\n{'='*60}")
            logger.info(f"일괄 파싱 완료")
            logger.info(f"  - 성공: {success_count}/{len(documents)}")
            logger.info(f"  - 실패: {failed_count}/{len(documents)}")
            logger.info(f"{'='*60}\n")
            
            return success_count > 0
        
        except Exception as e:
            logger.error(f"일괄 파싱 실패: {e}")
            return False
    
    def _wait_for_parsing_complete(
        self, 
        doc: object, 
        doc_name: str,
        max_wait_seconds: int = 300,
        check_interval: int = 3
    ) -> bool:
        """
        문서 파싱이 완료될 때까지 대기
        
        Args:
            doc: Document 객체
            doc_name: 문서 이름 (로깅용)
            max_wait_seconds: 최대 대기 시간 (초)
            check_interval: 상태 체크 간격 (초)
        
        Returns:
            파싱 성공 여부
        """
        import time
        
        elapsed_time = 0
        last_status = None
        
        while elapsed_time < max_wait_seconds:
            try:
                # 문서 정보 새로고침
                doc_info = doc.get()
                
                # 상태 확인 (다양한 필드명 시도)
                status = None
                for status_field in ['status', 'parsing_status', 'parse_status', 'progress']:
                    if hasattr(doc_info, status_field):
                        status = getattr(doc_info, status_field)
                        break
                
                # 상태 출력 (변경된 경우만)
                if status and status != last_status:
                    logger.info(f"    상태: {status} ({elapsed_time}초 경과)")
                    last_status = status
                
                # 완료 상태 확인
                if status:
                    status_lower = str(status).lower()
                    
                    # 성공 상태
                    if any(keyword in status_lower for keyword in ['done', 'success', 'completed', 'finish']):
                        logger.info(f"    파싱 완료 ({elapsed_time}초 소요)")
                        return True
                    
                    # 실패 상태
                    if any(keyword in status_lower for keyword in ['fail', 'error', 'cancel']):
                        logger.error(f"    파싱 실패 상태: {status}")
                        return False
                
                # 대기
                time.sleep(check_interval)
                elapsed_time += check_interval
            
            except Exception as e:
                logger.error(f"    상태 확인 중 에러: {e}")
                time.sleep(check_interval)
                elapsed_time += check_interval
        
        # 타임아웃
        logger.warning(f"    파싱 타임아웃 ({max_wait_seconds}초 초과)")
        return False
    
    def get_dataset_info(self, dataset: object) -> Dict:
        """지식베이스 정보 조회"""
        try:
            info = {
                'id': dataset.id if hasattr(dataset, 'id') else 'N/A',
                'name': dataset.name if hasattr(dataset, 'name') else 'N/A',
            }
            
            # 문서 수 조회
            try:
                docs = dataset.list_documents()
                info['document_count'] = len(docs) if docs else 0
            except:
                info['document_count'] = 'N/A'
            
            return info
        except Exception as e:
            logger.error(f"지식베이스 정보 조회 실패: {e}")
            return {}

