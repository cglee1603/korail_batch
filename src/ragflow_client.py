"""
RAGFlow Management API 연동 모듈 (HTTP 직접 요청)
"""
from typing import Optional, List, Dict
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except ImportError:
    from requests.packages.urllib3.util.retry import Retry
from logger import logger
from config import MANAGEMENT_USERNAME, MANAGEMENT_PASSWORD, RAGFLOW_BASE_URL


class RAGFlowClient:
    """RAGFlow Management API 클라이언트"""
    
    def __init__(self, username: str = None, password: str = None, base_url: str = None):
        self.username = username or MANAGEMENT_USERNAME
        self.password = password or MANAGEMENT_PASSWORD
        self.base_url = (base_url or RAGFLOW_BASE_URL).rstrip('/')
        self.token = None
        self.headers = {}
        
        # 네트워크 연결을 위한 Session 생성 (Retry 및 Timeout 설정)
        self.session = self._create_session()
        
        if not self.username or not self.password:
            raise ValueError("Management 사용자명/비밀번호가 설정되지 않았습니다. .env 파일을 확인하세요.")
        
        # 로그인하여 JWT 토큰 획득
        self._login()
        
        logger.info(f"Management API 클라이언트 초기화 완료 (URL: {self.base_url})")
    
    def _create_session(self):
        """
        Retry 및 Timeout 설정이 적용된 Session 생성
        다른 서버 연결 시 발생하는 Max retries exceeded 에러 방지
        """
        session = requests.Session()
        
        # Retry 전략 설정
        # - total: 최대 재시도 횟수 (5번)
        # - backoff_factor: 재시도 간 대기 시간 증가율 (0.5초 -> 1초 -> 2초 ...)
        # - status_forcelist: 재시도할 HTTP 상태 코드
        # - allowed_methods: 재시도 허용 메서드
        retry_strategy = Retry(
            total=5,  # 최대 5번 재시도
            backoff_factor=0.5,  # 재시도 간 대기 시간 (0.5, 1, 2, 4, 8초)
            status_forcelist=[429, 500, 502, 503, 504],  # 재시도할 상태 코드
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        
        # HTTPAdapter에 Retry 전략 적용
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # 연결 풀 크기
            pool_maxsize=10       # 최대 연결 수
        )
        
        # HTTP와 HTTPS 모두에 적용
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _login(self):
        """Management API 로그인 - JWT 토큰 획득"""
        try:
            logger.info(f"로그인 시도: {self.base_url}/api/v1/auth/login")
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                json={
                    "username": self.username,
                    "password": self.password
                },
                timeout=30  # 30초 timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    self.token = result['data']['token']
                    self.headers = {
                        'Authorization': f'Bearer {self.token}',
                        'Content-Type': 'application/json'
                    }
                    logger.info(f"✓ Management API 로그인 성공 (사용자: {self.username})")
                else:
                    raise ValueError(f"로그인 실패: {result.get('message')}")
            else:
                raise ValueError(f"로그인 실패 (HTTP {response.status_code}): {response.text}")
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"✗ 서버 연결 실패: {self.base_url}")
            logger.error(f"  - RAGFlow 서버가 실행 중인지 확인하세요.")
            logger.error(f"  - 네트워크 연결 및 방화벽 설정을 확인하세요.")
            logger.error(f"  상세 오류: {e}")
            raise
        except requests.exceptions.Timeout as e:
            logger.error(f"✗ 연결 시간 초과: {self.base_url}")
            logger.error(f"  - 서버가 너무 느리게 응답하고 있습니다.")
            logger.error(f"  - 네트워크 상태를 확인하세요.")
            logger.error(f"  상세 오류: {e}")
            raise
        except requests.exceptions.RetryError as e:
            logger.error(f"✗ 최대 재시도 횟수 초과 (Max retries exceeded)")
            logger.error(f"  - 서버 주소: {self.base_url}")
            logger.error(f"  - 가능한 원인:")
            logger.error(f"    1. 잘못된 서버 주소")
            logger.error(f"    2. 네트워크 연결 불안정")
            logger.error(f"    3. 서버 과부하")
            logger.error(f"    4. 방화벽/프록시 차단")
            logger.error(f"  상세 오류: {e}")
            raise
        except Exception as e:
            logger.error(f"✗ Management API 로그인 실패: {e}")
            raise
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """HTTP 요청 헬퍼 (Retry 및 Timeout 포함)"""
        url = f"{self.base_url}{endpoint}"
        
        # headers 병합
        headers = kwargs.pop('headers', {})
        headers.update(self.headers)
        
        # 파일 업로드 시 Content-Type 제거 (requests가 자동으로 multipart/form-data 설정)
        if 'files' in kwargs and 'Content-Type' in headers:
            del headers['Content-Type']
            logger.debug("파일 업로드: Content-Type 헤더 제거 (multipart/form-data 자동 설정)")
        
        # timeout 기본값 설정 (지정되지 않은 경우)
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 30  # 기본 30초
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )
            return response
        except requests.exceptions.ConnectionError as e:
            logger.error(f"HTTP 요청 연결 실패: {method} {url}")
            logger.error(f"  - 서버 연결을 확인하세요.")
            logger.error(f"  상세: {e}")
            raise
        except requests.exceptions.Timeout as e:
            logger.error(f"HTTP 요청 시간 초과: {method} {url}")
            logger.error(f"  - Timeout: {kwargs.get('timeout')}초")
            logger.error(f"  상세: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP 요청 실패: {method} {url} - {e}")
            raise
    
    def get_or_create_dataset(
        self, 
        name: str, 
        description: str = "",
        permission: str = "me",
        embedding_model: str = None,
        chunk_method: str = "naive",
        parser_config: Dict = None,
        recreate: bool = False
    ) -> Optional[Dict]:
        """
        지식베이스 가져오기 또는 생성 (Management API 사용)
        
        Args:
            name: 지식베이스 이름
            description: 설명
            permission: 권한 설정 ("me": 나만, "team": 팀 공유)
            embedding_model: 임베딩 모델 (None이면 시스템 기본값)
            chunk_method: 청크 분할 방법 (기본: "naive")
            parser_config: Parser 설정 (GUI와 동일한 설정)
            recreate: True면 삭제 후 재생성, False면 기존 것 재사용 (기본: False)
        
        Returns:
            Dataset 딕셔너리 또는 None
        """
        # 1. 기존 지식베이스 검색
        try:
            response = self._make_request(
                'GET',
                '/api/v1/knowledgebases',  # datasets -> knowledgebases
                params={'name': name}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    # Management API는 data.list 형태로 반환
                    data = result.get('data', {})
                    datasets = data.get('list', []) if isinstance(data, dict) else data
                    
                    if datasets:
                        logger.info(f"기존 지식베이스 발견: {name} (총 {len(datasets)}개)")
                        
                        # recreate=False면 기존 것 재사용
                        if not recreate:
                            existing_dataset = datasets[0]
                            logger.info(f"✓ 기존 지식베이스 재사용: {name} (ID: {existing_dataset.get('id')})")
                            return existing_dataset
                        
                        # recreate=True면 모든 동일 이름 지식베이스 삭제
                        logger.info(f"기존 지식베이스 삭제 후 재생성 모드 (recreate=True)")
                        for idx, dataset in enumerate(datasets, 1):
                            dataset_id = dataset.get('id')
                            if not dataset_id:
                                continue
                            
                            try:
                                logger.info(f"기존 지식베이스 삭제 시도 [{idx}/{len(datasets)}]: {name} (ID: {dataset_id})")
                                del_response = self._make_request(
                                    'DELETE',
                                    f'/api/v1/knowledgebases/{dataset_id}'  # 개별 삭제 API
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
            logger.info(f"새 지식베이스 생성: {name}")
            logger.info(f"  - 임베딩 모델: {embedding_model if embedding_model else '시스템 기본값 (tenant 설정)'}")
            logger.info(f"  - 권한: {permission}")
            logger.info(f"  - 청크 방법: {chunk_method}")
            if parser_config:
                logger.info(f"  - Parser 설정: {parser_config}")
            
            create_payload = {
                "name": name,
                "permission": permission,
                "chunk_method": chunk_method
            }
            
            if description:
                create_payload["description"] = description
            
            # embedding_model이 명시적으로 지정된 경우에만 전달
            # None이면 서버에서 tenant.embd_id를 사용함
            if embedding_model:
                create_payload["embedding_model"] = embedding_model
            
            # parser_config가 있으면 전달 (GUI와 동일한 설정)
            if parser_config:
                create_payload["parser_config"] = parser_config
            
            response = self._make_request(
                'POST',
                '/api/v1/knowledgebases',  # datasets -> knowledgebases
                json=create_payload
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    dataset = result.get('data')
                    kb_id = dataset.get('id')
                    logger.info(f"✓ 지식베이스 생성 성공: {name} (ID: {kb_id})")
                    logger.debug(f"지식베이스 전체 정보: {dataset}")
                    return dataset
                else:
                    logger.error(f"✗ 지식베이스 생성 실패: {result.get('message')}")
                    return None
            else:
                logger.error(f"✗ 지식베이스 생성 실패 (HTTP {response.status_code})")
                logger.error(f"   응답 내용: {response.text}")
                return None
        
        except Exception as create_error:
            logger.error(f"✗ 지식베이스 생성 실패: {create_error}")
            return None
    
    def upload_document(
        self, 
        dataset: Dict, 
        file_path: Path, 
        metadata: Dict[str, str] = None,
        display_name: str = None,
        parser_config: Dict = None
    ) -> Optional[str]:
        """
        파일을 지식베이스에 업로드 (Management API 2단계 프로세스)
        1. 파일 업로드 -> 2. 지식베이스에 문서 추가
        
        Args:
            dataset: Dataset 딕셔너리
            file_path: 업로드할 파일 경로
            metadata: 메타데이터 (현재 미사용 - MinIO 참조 손상 방지)
            display_name: 표시 이름
            parser_config: Parser 설정 (업로드 후 문서에 적용)
        
        Returns:
            문서 ID (성공 시) 또는 None (실패 시)
        """
        try:
            if not file_path.exists():
                logger.error(f"파일이 존재하지 않습니다: {file_path}")
                return None
            
            kb_id = dataset.get('id')
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return None
            
            # 파일명 설정
            if not display_name:
                display_name = file_path.name
            
            file_size = file_path.stat().st_size
            logger.info(f"파일 업로드 시작: {display_name} ({file_size/1024/1024:.2f} MB)")
            
            # Step 1: 파일 업로드 (Management API)
            with open(file_path, 'rb') as f:
                files = {
                    'files': (display_name, f, 'application/octet-stream')
                }
                
                # _make_request가 자동으로 Content-Type을 제거하고 multipart/form-data로 설정
                upload_response = self._make_request(
                    'POST',
                    '/api/v1/files/upload',
                    files=files
                )
            
            if upload_response.status_code != 200:
                logger.error(f"✗ 파일 업로드 실패 (HTTP {upload_response.status_code}): {upload_response.text}")
                return None
            
            upload_result = upload_response.json()
            if upload_result.get('code') != 0:
                logger.error(f"✗ 파일 업로드 실패: {upload_result.get('message')}")
                return None
            
            # 업로드된 파일 ID 추출
            uploaded_files = upload_result.get('data', [])
            logger.debug(f"📦 upload_result 전체: {upload_result}")
            logger.debug(f"📦 uploaded_files (data 배열): {uploaded_files}")
            logger.debug(f"📦 uploaded_files 타입: {type(uploaded_files)}, 길이: {len(uploaded_files) if isinstance(uploaded_files, list) else 'N/A'}")
            
            if not uploaded_files:
                logger.error("✗ 업로드된 파일 정보를 찾을 수 없습니다.")
                return None
            
            # 단일 파일 업로드이므로 첫 번째(유일한) 파일 ID 사용
            first_file = uploaded_files[0]
            logger.debug(f"📦 첫 번째 파일 정보: {first_file}")
            logger.debug(f"📦 첫 번째 파일 타입: {type(first_file)}")
            logger.debug(f"📦 첫 번째 파일 keys: {first_file.keys() if isinstance(first_file, dict) else 'N/A'}")
            
            file_id = first_file.get('id') if isinstance(first_file, dict) else None
            logger.debug(f"📦 추출된 file_id: '{file_id}'")
            
            if not file_id:
                logger.error("✗ 파일 ID를 찾을 수 없습니다.")
                logger.error(f"   첫 번째 파일 전체 내용: {first_file}")
                return None
            
            logger.info(f"✓ 파일 업로드 완료: {display_name} (File ID: {file_id})")
            
            # Step 2: 지식베이스에 문서 추가
            logger.debug(f"지식베이스에 문서 추가 시도: KB ID={kb_id}, File ID={file_id}")
            logger.debug(f"요청 URL: {self.base_url}/api/v1/knowledgebases/{kb_id}/documents")
            logger.debug(f"요청 Body: {{'file_ids': ['{file_id}']}}")
            
            add_doc_response = self._make_request(
                'POST',
                f'/api/v1/knowledgebases/{kb_id}/documents',
                json={'file_ids': [file_id]}
            )
            
            logger.debug(f"문서 추가 응답 상태 코드: {add_doc_response.status_code}")
            
            if add_doc_response.status_code == 200 or add_doc_response.status_code == 201:
                add_result = add_doc_response.json()
                if add_result.get('code') == 0 or add_result.get('code') == 201:
                    logger.info(f"✓ 지식베이스에 문서 추가 성공: {display_name}")
                    
                    # 문서 ID 추출
                    # API 응답 형식: {'code': 0, 'data': [...]} 또는 {'code': 0, 'data': {'id': '...'}}
                    data = add_result.get('data', [])
                    document_id = None
                    
                    if isinstance(data, list) and data:
                        # 리스트인 경우 첫 번째 항목의 ID
                        first_doc = data[0]
                        document_id = first_doc.get('id') if isinstance(first_doc, dict) else None
                    elif isinstance(data, dict):
                        # 딕셔너리인 경우 직접 ID 추출
                        document_id = data.get('id')
                    
                    # file_id를 document_id로 사용 (문서 추가 응답에 ID가 없는 경우)
                    if not document_id:
                        document_id = file_id
                        logger.debug(f"문서 ID를 응답에서 찾을 수 없어 file_id 사용: {document_id}")
                    else:
                        logger.debug(f"문서 ID 추출 성공: {document_id}")
                    
                    # 메타데이터는 업로드 직후 업데이트하지 않음 (MinIO 참조 손상 방지)
                    if metadata:
                        logger.debug(f"메타데이터 (미적용): {metadata}")
                    
                    return document_id
                else:
                    logger.error(f"✗ 지식베이스에 문서 추가 실패: {add_result.get('message')}")
                    return None
            else:
                logger.error(f"✗ 지식베이스에 문서 추가 실패 (HTTP {add_doc_response.status_code})")
                logger.error(f"   KB ID: {kb_id}")
                logger.error(f"   File ID: {file_id}")
                logger.error(f"   URL: /api/v1/knowledgebases/{kb_id}/documents")
                logger.error(f"   응답 내용: {add_doc_response.text}")
                return None
        
        except Exception as e:
            logger.error(f"✗ 파일 업로드 실패 ({file_path.name}): {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def start_batch_parse(self, dataset: Dict) -> bool:
        """
        지식베이스의 모든 문서 일괄 파싱 (Management API 사용)
        Management API는 순차적 일괄 파싱을 지원하여 더 간단합니다.
        
        Args:
            dataset: Dataset 딕셔너리
        
        Returns:
            성공 여부
        """
        try:
            kb_id = dataset.get('id')
            kb_name = dataset.get('name', 'Unknown')
            
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return False
            
            logger.info(f"일괄 파싱 시작: {kb_name}")
            
            # Management API는 kb_id만으로 일괄 파싱 가능 (문서 목록 조회 불필요)
            parse_response = self._make_request(
                'POST',
                f'/api/v1/knowledgebases/{kb_id}/batch_parse_sequential/start'
            )
            
            if parse_response.status_code == 200:
                parse_result = parse_response.json()
                if parse_result.get('code') == 0:
                    logger.info(f"✓ 일괄 파싱 요청 완료")
                    logger.info(f"파싱은 백그라운드에서 순차적으로 진행됩니다.")
                    logger.info(f"Management UI에서 진행 상태를 확인하세요.")
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
    
    def get_parse_progress(self, dataset: Dict) -> Optional[Dict]:
        """
        지식베이스의 파싱 진행 상황 조회 (Management API 전용)
        
        Args:
            dataset: Dataset 딕셔너리
        
        Returns:
            진행 상황 딕셔너리 또는 None
        """
        try:
            kb_id = dataset.get('id')
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return None
            
            response = self._make_request(
                'GET',
                f'/api/v1/knowledgebases/{kb_id}/batch_parse_sequential/progress'
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    return result.get('data')
                else:
                    logger.warning(f"진행 상황 조회 실패: {result.get('message')}")
                    return None
            else:
                logger.warning(f"진행 상황 조회 실패 (HTTP {response.status_code})")
                return None
        
        except Exception as e:
            logger.warning(f"진행 상황 조회 중 에러: {e}")
            return None
    
    def get_documents_in_dataset(self, dataset: Dict, page: int = 1, page_size: int = 100) -> List[Dict]:
        """
        지식베이스의 문서 목록 조회 (Revision 관리용)
        
        Args:
            dataset: Dataset 딕셔너리
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지당 문서 수
        
        Returns:
            문서 목록 [{'id': 'xxx', 'name': 'yyy', 'metadata': {...}}, ...]
        """
        try:
            kb_id = dataset.get('id')
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return []
            
            logger.debug(f"지식베이스 '{dataset.get('name')}' 문서 목록 조회 중...")
            
            response = self._make_request(
                'GET',
                f'/api/v1/knowledgebases/{kb_id}/documents',
                params={
                    'page': page,
                    'page_size': page_size
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    data = result.get('data', {})
                    documents = data.get('list', []) if isinstance(data, dict) else []
                    logger.info(f"문서 목록 조회 완료: {len(documents)}개 문서")
                    return documents
                else:
                    logger.error(f"문서 목록 조회 실패: {result.get('message')}")
                    return []
            else:
                logger.error(f"문서 목록 조회 실패 (HTTP {response.status_code}): {response.text}")
                return []
        
        except Exception as e:
            logger.error(f"문서 목록 조회 중 오류: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def delete_document(self, dataset: Dict, document_id: str) -> bool:
        """
        지식베이스에서 문서 삭제
        
        Args:
            dataset: Dataset 딕셔너리
            document_id: 삭제할 문서 ID
        
        Returns:
            성공 여부
        """
        try:
            kb_id = dataset.get('id')
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return False
            
            logger.debug(f"문서 삭제 시도: KB ID={kb_id}, Doc ID={document_id}")
            
            response = self._make_request(
                'DELETE',
                f'/api/v1/knowledgebases/{kb_id}/documents/{document_id}'
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    logger.info(f"✓ 문서 삭제 완료: {document_id}")
                    return True
                else:
                    logger.error(f"✗ 문서 삭제 실패: {result.get('message')}")
                    return False
            else:
                logger.error(f"✗ 문서 삭제 실패 (HTTP {response.status_code}): {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"✗ 문서 삭제 중 오류: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def get_dataset_info(self, dataset: Dict) -> Dict:
        """지식베이스 정보 조회 (Management API 사용)"""
        try:
            kb_id = dataset.get('id')
            if not kb_id:
                return {'error': 'No knowledge base ID'}
            
            response = self._make_request(
                'GET',
                f'/api/v1/knowledgebases/{kb_id}/documents'
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    docs_data = result.get('data', {})
                    return {
                        'id': kb_id,
                        'name': dataset.get('name', 'N/A'),
                        'document_count': docs_data.get('total', 0)
                    }
            
            return {
                'id': kb_id,
                'name': dataset.get('name', 'N/A'),
                'document_count': 'N/A'
            }
        
        except Exception as e:
            logger.error(f"지식베이스 정보 조회 실패: {e}")
            return {}
