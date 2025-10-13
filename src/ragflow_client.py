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
        permission: str = "me",
        embedding_model: str = None
    ) -> Optional[object]:
        """
        지식베이스 삭제 후 재생성
        
        동일한 이름의 지식베이스가 존재하면 삭제하고 새로 생성합니다.
        
        Args:
            name: 지식베이스 이름
            description: 설명
            permission: 권한 설정 ("me": 나만, "team": 팀 공유)
            embedding_model: 임베딩 모델 (None이면 시스템 기본값)
        
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
            else:
                logger.info(f"기존 지식베이스 없음: {name}")
        
        except Exception as list_error:
            # list_datasets() 호출 실패 - 일단 생성 시도
            logger.warning(f"지식베이스 검색 중 에러 발생 (생성 단계 진행): {list_error}")
            logger.debug(f"상세 에러: {type(list_error).__name__} - {str(list_error)}")
        
        # 2. 새 지식베이스 생성
        try:
            logger.info(f"새 지식베이스 생성: {name}")
            logger.info(f"  - 임베딩 모델: {embedding_model if embedding_model else '시스템 기본값'}")
            logger.info(f"  - 권한: {permission}")
            
            # embedding_model이 None이거나 빈 문자열이면 파라미터에서 제외
            create_params = {
                "name": name,
                "description": description,
                "permission": permission
            }
            
            if embedding_model:
                create_params["embedding_model"] = embedding_model
            
            dataset = self.rag.create_dataset(**create_params)
            logger.info(f"✓ 지식베이스 생성 성공: {name}")
            return dataset
        
        except Exception as create_error:
            error_msg = str(create_error)
            logger.error(f"✗ 지식베이스 생성 실패 ({name})")
            logger.error(f"  에러 타입: {type(create_error).__name__}")
            logger.error(f"  에러 메시지: {error_msg}")
            
            # 이름 중복이나 권한 문제인 경우 추가 안내
            if ("don't own" in error_msg.lower() or 
                "already exists" in error_msg.lower() or 
                "duplicate" in error_msg.lower() or
                "permission" in error_msg.lower()):
                logger.error(f"  → 동일한 이름의 지식베이스가 다른 사용자에게 있거나 이미 존재합니다.")
                logger.error(f"  → RAGFlow UI에서 '{name}' 지식베이스를 직접 확인하고 삭제해주세요.")
            
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
        from io import BytesIO
        
        try:
            if not file_path.exists():
                logger.error(f"파일이 존재하지 않습니다: {file_path}")
                return False
            
            # 파일명 설정
            if not display_name:
                display_name = file_path.name
            
            # 파일 읽기
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            file_size = len(file_content)
            logger.info(f"파일 업로드 시작: {display_name} ({file_size/1024/1024:.2f} MB)")
            
            # BytesIO 객체 생성
            file_stream = BytesIO(file_content)
            file_stream.name = display_name
            file_stream.seek(0)
            
            # 업로드할 문서 정보
            doc_info = {
                "display_name": display_name,
                "blob": file_stream
            }
            
            try:
                uploaded_docs = dataset.upload_documents([doc_info])
                
                if not uploaded_docs or len(uploaded_docs) == 0:
                    logger.error(f"업로드 응답에 문서가 없습니다: {display_name}")
                    return False
                
                logger.info(f"✓ 파일 업로드 성공: {display_name}")
                
                # 메타데이터 업데이트 제거 - MinIO 파일 참조 손상 방지
                if metadata:
                    logger.debug(f"메타데이터 (미적용): {metadata}")
                
                return True
            
            finally:
                file_stream.close()
        
        except Exception as e:
            logger.error(f"✗ 파일 업로드 실패 ({file_path.name}): {e}")
            import traceback
            logger.debug(traceback.format_exc())
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
        지식베이스의 모든 문서 일괄 파싱
        
        Dataset의 async_parse_documents() 메서드를 사용합니다.
        """
        try:
            logger.info(f"일괄 파싱 시작: {dataset.name}")
            
            # 모든 문서 목록 가져오기
            documents = dataset.list_documents()
            
            if not documents:
                logger.warning("파싱할 문서가 없습니다.")
                return True
            
            logger.info(f"총 {len(documents)}개 문서 파싱 예정")
            
            # 문서 ID 목록 수집
            document_ids = [doc.id for doc in documents if hasattr(doc, 'id')]
            
            if not document_ids:
                logger.error("문서 ID를 찾을 수 없습니다.")
                return False
            
            logger.info(f"문서 ID: {document_ids}")
            
            # 일괄 파싱 요청
            try:
                dataset.async_parse_documents(document_ids)
                logger.info(f"✓ 일괄 파싱 요청 완료")
                logger.info(f"파싱은 백그라운드에서 진행됩니다.")
                logger.info(f"RAGFlow UI에서 진행 상태를 확인하세요.")
                return True
            
            except Exception as e:
                logger.error(f"일괄 파싱 요청 실패: {e}")
                return False
        
        except Exception as e:
            logger.error(f"일괄 파싱 실패: {e}")
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

