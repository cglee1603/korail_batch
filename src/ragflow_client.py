"""
RAGFlow HTTP API 연동 모듈 (SDK 대신 직접 HTTP 요청)
"""
from typing import Optional, List, Dict
from pathlib import Path
import requests
from logger import logger
from config import RAGFLOW_API_KEY, RAGFLOW_BASE_URL


class RAGFlowClient:
    """RAGFlow HTTP API 클라이언트"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or RAGFLOW_API_KEY
        self.base_url = (base_url or RAGFLOW_BASE_URL).rstrip('/')
        
        if not self.api_key:
            raise ValueError("RAGFlow API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        
        logger.info(f"RAGFlow 클라이언트 초기화 완료 (URL: {self.base_url})")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """HTTP 요청 헬퍼"""
        url = f"{self.base_url}{endpoint}"
        
        # headers 병합
        headers = kwargs.pop('headers', {})
        headers.update(self.headers)
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP 요청 실패: {method} {url} - {e}")
            raise
    
    def get_or_create_dataset(
        self, 
        name: str, 
        description: str = "",
        permission: str = "me",
        embedding_model: str = None
    ) -> Optional[Dict]:
        """
        지식베이스 삭제 후 재생성 (HTTP API 사용)
        
        Args:
            name: 지식베이스 이름
            description: 설명
            permission: 권한 설정 ("me": 나만, "team": 팀 공유)
            embedding_model: 임베딩 모델 (None이면 시스템 기본값)
        
        Returns:
            Dataset 딕셔너리 또는 None
        """
        # 1. 기존 지식베이스 검색
        try:
            response = self._make_request(
                'GET',
                '/api/v1/datasets',
                params={'name': name}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    datasets = result.get('data', [])
                    
                    if datasets:
                        logger.info(f"기존 지식베이스 발견: {name} (총 {len(datasets)}개)")
                        
                        # 모든 동일 이름 지식베이스 삭제
                        for idx, dataset in enumerate(datasets, 1):
                            dataset_id = dataset.get('id')
                            if not dataset_id:
                                continue
                            
                            try:
                                logger.info(f"기존 지식베이스 삭제 시도 [{idx}/{len(datasets)}]: {name} (ID: {dataset_id})")
                                del_response = self._make_request(
                                    'DELETE',
                                    '/api/v1/datasets',
                                    json={'ids': [dataset_id]}
                                )
                                
                                if del_response.status_code == 200:
                                    logger.info(f"✓ 지식베이스 삭제 완료: {name}")
                                else:
                                    logger.error(f"✗ 지식베이스 삭제 실패: {del_response.text}")
                                    return None
                            except Exception as delete_error:
                                logger.error(f"✗ 지식베이스 삭제 실패: {delete_error}")
                                return None
                    else:
                        logger.info(f"기존 지식베이스 없음: {name}")
        
        except Exception as list_error:
            logger.warning(f"지식베이스 검색 중 에러 발생 (생성 단계 진행): {list_error}")
        
        # 2. 새 지식베이스 생성
        try:
            # 임베딩 모델 이름 정규화: @Factory 부분 제거
            # 예: "qwen3-embedding:8b@Custom" -> "qwen3-embedding:8b"
            normalized_embedding_model = None
            if embedding_model:
                if '@' in embedding_model:
                    # @ 앞부분만 사용 (모델명만 추출)
                    normalized_embedding_model = embedding_model.split('@')[0]
                    logger.info(f"임베딩 모델 형식 변환: {embedding_model} -> {normalized_embedding_model}")
                else:
                    normalized_embedding_model = embedding_model
            
            logger.info(f"새 지식베이스 생성: {name}")
            logger.info(f"  - 임베딩 모델: {normalized_embedding_model if normalized_embedding_model else '시스템 기본값'}")
            logger.info(f"  - 권한: {permission}")
            
            create_payload = {
                "name": name,
                "permission": permission
            }
            
            if description:
                create_payload["description"] = description
            
            if normalized_embedding_model:
                create_payload["embedding_model"] = normalized_embedding_model
            
            response = self._make_request(
                'POST',
                '/api/v1/datasets',
                json=create_payload
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    dataset = result.get('data')
                    logger.info(f"✓ 지식베이스 생성 성공: {name} (ID: {dataset.get('id')})")
                    return dataset
                else:
                    logger.error(f"✗ 지식베이스 생성 실패: {result.get('message')}")
                    return None
            else:
                logger.error(f"✗ 지식베이스 생성 실패 (HTTP {response.status_code}): {response.text}")
                return None
        
        except Exception as create_error:
            logger.error(f"✗ 지식베이스 생성 실패: {create_error}")
            return None
    
    def upload_document(
        self, 
        dataset: Dict, 
        file_path: Path, 
        metadata: Dict[str, str] = None,
        display_name: str = None
    ) -> bool:
        """
        파일을 지식베이스에 업로드 (HTTP API 직접 사용)
        
        Args:
            dataset: Dataset 딕셔너리
            file_path: 업로드할 파일 경로
            metadata: 메타데이터 (현재 미사용 - MinIO 참조 손상 방지)
            display_name: 표시 이름
        
        Returns:
            성공 여부
        """
        try:
            if not file_path.exists():
                logger.error(f"파일이 존재하지 않습니다: {file_path}")
                return False
            
            dataset_id = dataset.get('id')
            if not dataset_id:
                logger.error("Dataset ID를 찾을 수 없습니다.")
                return False
            
            # 파일명 설정
            if not display_name:
                display_name = file_path.name
            
            file_size = file_path.stat().st_size
            logger.info(f"파일 업로드 시작: {display_name} ({file_size/1024/1024:.2f} MB)")
            
            # HTTP multipart/form-data 업로드
            with open(file_path, 'rb') as f:
                files = {
                    'file': (display_name, f, 'application/octet-stream')
                }
                
                response = self._make_request(
                    'POST',
                    f'/api/v1/datasets/{dataset_id}/documents',
                    files=files
                )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    logger.info(f"✓ 파일 업로드 성공: {display_name}")
                    
                    # 메타데이터는 업로드 직후 업데이트하지 않음 (MinIO 참조 손상 방지)
                    if metadata:
                        logger.debug(f"메타데이터 (미적용): {metadata}")
                    
                    return True
                else:
                    logger.error(f"✗ 파일 업로드 실패: {result.get('message')}")
                    return False
            else:
                logger.error(f"✗ 파일 업로드 실패 (HTTP {response.status_code}): {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"✗ 파일 업로드 실패 ({file_path.name}): {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def start_batch_parse(self, dataset: Dict) -> bool:
        """
        지식베이스의 모든 문서 일괄 파싱 (HTTP API 사용)
        
        Args:
            dataset: Dataset 딕셔너리
        
        Returns:
            성공 여부
        """
        try:
            dataset_id = dataset.get('id')
            dataset_name = dataset.get('name', 'Unknown')
            
            if not dataset_id:
                logger.error("Dataset ID를 찾을 수 없습니다.")
                return False
            
            logger.info(f"일괄 파싱 시작: {dataset_name}")
            
            # 1. 문서 목록 가져오기
            response = self._make_request(
                'GET',
                f'/api/v1/datasets/{dataset_id}/documents'
            )
            
            if response.status_code != 200:
                logger.error(f"문서 목록 조회 실패 (HTTP {response.status_code}): {response.text}")
                return False
            
            result = response.json()
            if result.get('code') != 0:
                logger.error(f"문서 목록 조회 실패: {result.get('message')}")
                return False
            
            docs_data = result.get('data', {})
            documents = docs_data.get('docs', [])
            
            if not documents:
                logger.warning("파싱할 문서가 없습니다.")
                return True
            
            logger.info(f"총 {len(documents)}개 문서 파싱 예정")
            
            # 2. 문서 ID 목록 수집
            document_ids = [doc.get('id') for doc in documents if doc.get('id')]
            
            if not document_ids:
                logger.error("문서 ID를 찾을 수 없습니다.")
                return False
            
            logger.info(f"문서 ID: {document_ids[:5]}{'...' if len(document_ids) > 5 else ''}")
            
            # 3. 일괄 파싱 요청
            parse_response = self._make_request(
                'POST',
                f'/api/v1/datasets/{dataset_id}/chunks',
                json={'document_ids': document_ids}
            )
            
            if parse_response.status_code == 200:
                parse_result = parse_response.json()
                if parse_result.get('code') == 0:
                    logger.info(f"✓ 일괄 파싱 요청 완료")
                    logger.info(f"파싱은 백그라운드에서 진행됩니다.")
                    logger.info(f"RAGFlow UI에서 진행 상태를 확인하세요.")
                    return True
                else:
                    logger.error(f"일괄 파싱 요청 실패: {parse_result.get('message')}")
                    return False
            else:
                logger.error(f"일괄 파싱 요청 실패 (HTTP {parse_response.status_code}): {parse_response.text}")
                return False
        
        except Exception as e:
            logger.error(f"일괄 파싱 실패: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def get_dataset_info(self, dataset: Dict) -> Dict:
        """지식베이스 정보 조회 (HTTP API 사용)"""
        try:
            dataset_id = dataset.get('id')
            if not dataset_id:
                return {'error': 'No dataset ID'}
            
            response = self._make_request(
                'GET',
                f'/api/v1/datasets/{dataset_id}/documents'
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    docs_data = result.get('data', {})
                    return {
                        'id': dataset_id,
                        'name': dataset.get('name', 'N/A'),
                        'document_count': docs_data.get('total', 0)
                    }
            
            return {
                'id': dataset_id,
                'name': dataset.get('name', 'N/A'),
                'document_count': 'N/A'
            }
        
        except Exception as e:
            logger.error(f"지식베이스 정보 조회 실패: {e}")
            return {}
