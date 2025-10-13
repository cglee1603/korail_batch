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
        language: str = "Korean"
    ) -> Optional[object]:
        """
        지식베이스 가져오기 또는 생성
        
        Args:
            name: 지식베이스 이름
            description: 설명
            permission: 권한 설정 ("me": 나만, "team": 팀 공유)
            language: 언어 설정 (기본값: "Korean")
        
        Returns:
            Dataset 객체 또는 None
        """
        from datetime import datetime
        
        # 기존 지식베이스 검색 시도
        try:
            datasets = self.rag.list_datasets(name=name)
            
            if datasets and len(datasets) > 0:
                # 첫 번째 데이터셋 접근 시도 (소유권 확인)
                try:
                    dataset = datasets[0]
                    # 소유권 확인을 위해 문서 목록 조회 시도
                    _ = dataset.list_documents()
                    logger.info(f"기존 지식베이스 사용: {name}")
                    return dataset
                except Exception as access_error:
                    # 접근 권한 없음 - 다른 사용자 소유
                    error_msg = str(access_error)
                    if "don't own" in error_msg.lower() or "permission" in error_msg.lower():
                        logger.warning(f"지식베이스 '{name}'는 다른 사용자 소유입니다. 새로 생성합니다.")
                    else:
                        raise access_error
        
        except Exception as list_error:
            # list_datasets() 호출 자체가 실패 (다른 사용자 소유로 검색 불가)
            error_msg = str(list_error)
            if "don't own" in error_msg.lower() or "permission" in error_msg.lower():
                logger.warning(f"지식베이스 '{name}'는 이미 존재하지만 다른 사용자 소유입니다.")
                logger.info(f"타임스탬프를 추가하여 새 지식베이스를 생성합니다.")
                
                # 타임스탬프 추가하여 새 이름 생성
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_name = f"{name}_{timestamp}"
                
                try:
                    logger.info(f"새 지식베이스 생성: {new_name}")
                    dataset = self.rag.create_dataset(
                        name=new_name,
                        description=f"{description} (자동 생성: {timestamp})",
                        permission=permission,
                        language=language
                    )
                    logger.info(f"✓ 지식베이스 생성 성공: {new_name}")
                    return dataset
                except Exception as create_error:
                    logger.error(f"지식베이스 생성 실패 ({new_name}): {create_error}")
                    return None
            else:
                # 다른 종류의 에러
                logger.error(f"지식베이스 검색 실패 ({name}): {list_error}")
                return None
        
        # 새 지식베이스 생성 (검색 결과 없음)
        try:
            logger.info(f"새 지식베이스 생성: {name}")
            dataset = self.rag.create_dataset(
                name=name,
                description=description,
                permission=permission,
                language=language
            )
            logger.info(f"✓ 지식베이스 생성 성공: {name}")
            return dataset
        
        except Exception as create_error:
            create_error_msg = str(create_error)
            
            # "You don't own" 에러 또는 이름 중복 에러
            if ("don't own" in create_error_msg.lower() or 
                "already exists" in create_error_msg.lower() or 
                "duplicate" in create_error_msg.lower()):
                
                # 타임스탬프 추가하여 재시도
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_name = f"{name}_{timestamp}"
                logger.warning(f"지식베이스 '{name}' 생성 실패 (이미 존재하거나 권한 없음)")
                logger.info(f"새 이름으로 재시도: {new_name}")
                
                try:
                    dataset = self.rag.create_dataset(
                        name=new_name,
                        description=f"{description} (자동 생성: {timestamp})",
                        permission=permission,
                        language=language
                    )
                    logger.info(f"✓ 지식베이스 생성 성공: {new_name}")
                    return dataset
                except Exception as retry_error:
                    logger.error(f"지식베이스 재생성 실패 ({new_name}): {retry_error}")
                    return None
            else:
                logger.error(f"지식베이스 생성 실패 ({name}): {create_error}")
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
        지식베이스의 모든 문서 일괄 파싱 시작
        
        Note:
            RAGFlow SDK에 일괄 파싱 메서드가 있는지 확인 필요
            없다면 개별 문서별로 파싱 요청
        """
        try:
            logger.info(f"일괄 파싱 시작: {dataset.name}")
            
            # 모든 문서 목록 가져오기
            documents = dataset.list_documents()
            
            if not documents:
                logger.warning("파싱할 문서가 없습니다.")
                return True
            
            # 각 문서 파싱
            success_count = 0
            for doc in documents:
                try:
                    # SDK에 parse 메서드가 있는지 확인
                    if hasattr(doc, 'parse'):
                        doc.parse()
                        success_count += 1
                        logger.info(f"문서 파싱 요청: {doc.name}")
                    else:
                        logger.warning(f"파싱 메서드를 찾을 수 없습니다: {doc.name}")
                except Exception as e:
                    logger.error(f"문서 파싱 실패 ({doc.name}): {e}")
            
            logger.info(f"일괄 파싱 완료: {success_count}/{len(documents)} 성공")
            return success_count > 0
        
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

