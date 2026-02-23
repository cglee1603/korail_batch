"""
RAGFlow HTTP API 연동 모듈
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
from config import RAGFLOW_API_KEY, RAGFLOW_BASE_URL, DB_CONNECTION_STRING
from db_connector import DBConnector


class RAGFlowClient:
    """RAGFlow HTTP API 클라이언트"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or RAGFLOW_API_KEY
        self.base_url = (base_url or RAGFLOW_BASE_URL).rstrip('/')
        
        if not self.api_key:
            raise ValueError("RAGFlow API Key가 설정되지 않았습니다. .env 파일에 RAGFLOW_API_KEY를 설정하세요.")
        
        # API Key 기반 인증 헤더 설정
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # 네트워크 연결을 위한 Session 생성 (Retry 및 Timeout 설정)
        self.session = self._create_session()
        
        # DB 연결 초기화 (file2document 테이블 조회용)
        self.db_connector = None
        if DB_CONNECTION_STRING:
            try:
                self.db_connector = DBConnector(connection_string=DB_CONNECTION_STRING)
                logger.info("✓ RAGFlow DB 연결 초기화 완료 (file2document 테이블 조회용)")
            except Exception as e:
                logger.warning(f"⚠️ DB 연결 실패 (file_id 조회 불가): {e}")
        else:
            logger.warning("⚠️ DB_CONNECTION_STRING이 설정되지 않음 (file_id 조회 불가)")
        
        logger.info(f"RAGFlow API 클라이언트 초기화 완료 (URL: {self.base_url})")
    
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
    
    def list_datasets(
        self,
        page: int = 1,
        page_size: int = 100,
        keywords: str = None,
        orderby: str = "create_time",
        desc: bool = True
    ) -> List[Dict]:
        """
        지식베이스 목록 조회
        
        Args:
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지당 항목 수
            keywords: 검색 키워드 (지식베이스 이름 검색)
            orderby: 정렬 기준 (create_time, update_time, name 등)
            desc: 내림차순 정렬 여부 (True: 내림차순, False: 오름차순)
        
        Returns:
            지식베이스 목록
        """
        try:
            params = {
                'page': page,
                'page_size': page_size,
                'orderby': orderby,
                'desc': desc
            }
            
            if keywords:
                params['keywords'] = keywords
            
            response = self._make_request(
                'GET',
                '/api/v1/datasets',
                params=params
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    data = result.get('data', [])
                    # data가 리스트면 그대로 사용, 딕셔너리면 'list' 키 찾기
                    if isinstance(data, list):
                        datasets = data
                    elif isinstance(data, dict):
                        datasets = data.get('list', [])
                    else:
                        datasets = []
                    logger.debug(f"지식베이스 목록 조회 완료: {len(datasets)}개")
                    return datasets
                else:
                    logger.error(f"지식베이스 목록 조회 실패: {result.get('message')}")
                    return []
            else:
                logger.error(f"지식베이스 목록 조회 실패 (HTTP {response.status_code}): {response.text}")
                return []
        
        except Exception as e:
            logger.error(f"지식베이스 목록 조회 중 오류: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def get_dataset(self, dataset_id: str) -> Optional[Dict]:
        """
        지식베이스 ID로 조회
        
        Args:
            dataset_id: 지식베이스 ID
        
        Returns:
            지식베이스 딕셔너리 또는 None
        """
        try:
            logger.debug(f"지식베이스 조회: ID={dataset_id}")
            
            response = self._make_request(
                'GET',
                f'/api/v1/datasets/{dataset_id}'
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    dataset = result.get('data')
                    logger.info(f"✓ 지식베이스 조회 성공: {dataset.get('name')} (ID: {dataset_id})")
                    return dataset
                else:
                    logger.error(f"✗ 지식베이스 조회 실패: {result.get('message')}")
                    return None
            elif response.status_code == 404:
                logger.warning(f"지식베이스를 찾을 수 없습니다: ID={dataset_id}")
                return None
            else:
                logger.error(f"✗ 지식베이스 조회 실패 (HTTP {response.status_code}): {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"지식베이스 조회 중 오류: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def get_dataset_by_name(self, name: str, exact_match: bool = True) -> Optional[Dict]:
        """
        지식베이스 이름으로 조회
        
        Args:
            name: 지식베이스 이름
            exact_match: True면 정확히 일치하는 것만, False면 부분 일치도 허용
        
        Returns:
            지식베이스 딕셔너리 또는 None (여러 개 있으면 첫 번째 반환)
        """
        try:
            logger.debug(f"지식베이스 이름으로 조회: {name} (정확 일치: {exact_match})")
            
            # 이름으로 검색
            datasets = self.list_datasets(keywords=name, page_size=100)
            
            if not datasets:
                logger.warning(f"지식베이스를 찾을 수 없습니다: {name}")
                return None
            
            # 정확히 일치하는 것 찾기
            if exact_match:
                for dataset in datasets:
                    if dataset.get('name') == name:
                        logger.info(f"✓ 지식베이스 발견: {name} (ID: {dataset.get('id')})")
                        return dataset
                
                logger.warning(f"정확히 일치하는 지식베이스를 찾을 수 없습니다: {name}")
                logger.info(f"부분 일치하는 지식베이스 {len(datasets)}개 발견")
                return None
            else:
                # 부분 일치 허용 - 첫 번째 반환
                dataset = datasets[0]
                logger.info(f"✓ 지식베이스 발견: {dataset.get('name')} (ID: {dataset.get('id')})")
                return dataset
        
        except Exception as e:
            logger.error(f"지식베이스 이름 조회 중 오류: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
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
        지식베이스 가져오기 또는 생성
        
        Args:
            name: 지식베이스 이름
            description: 설명
            permission: 권한 설정 ("me": 나만, "team": 팀 공유)
            embedding_model: 임베딩 모델 (None이면 시스템 기본값)
            chunk_method: 파싱 방법 (기본: "naive")
            parser_config: Parser 설정 (GUI와 동일한 설정)
            recreate: True면 삭제 후 재생성, False면 기존 것 재사용 (기본: False)
        
        Returns:
            Dataset 딕셔너리 또는 None
        """
        # 1. 기존 지식베이스 검색 (이름으로 부분 일치 검색)
        try:
            datasets = self.list_datasets(keywords=name, page_size=100)
            
            # 정확히 일치하는 것만 필터링
            exact_matches = [ds for ds in datasets if ds.get('name') == name]
            
            if exact_matches:
                logger.info(f"기존 지식베이스 발견: {name} (총 {len(exact_matches)}개)")
                
                # recreate=False면 기존 것 재사용
                if not recreate:
                    existing_dataset = exact_matches[0]
                    logger.info(f"✓ 기존 지식베이스 재사용: {name} (ID: {existing_dataset.get('id')})")
                    return existing_dataset
                
                # recreate=True면 모든 동일 이름 지식베이스 삭제
                logger.info(f"기존 지식베이스 삭제 후 재생성 모드 (recreate=True)")
                for idx, dataset in enumerate(exact_matches, 1):
                    dataset_id = dataset.get('id')
                    if not dataset_id:
                        continue
                    
                    try:
                        logger.info(f"기존 지식베이스 삭제 시도 [{idx}/{len(exact_matches)}]: {name} (ID: {dataset_id})")
                        del_response = self._make_request(
                            'DELETE',
                            f'/api/v1/datasets',
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
            logger.info(f"새 지식베이스 생성: {name}")
            logger.info(f"  - 임베딩 모델: {embedding_model if embedding_model else '시스템 기본값 (tenant 설정)'}")
            logger.info(f"  - 권한: {permission}")
            logger.info(f"  - 파싱 방법: {chunk_method}")
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
                '/api/v1/datasets',
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
    ) -> Optional[Dict]:
        """
        파일을 지식베이스에 업로드
        파일 업로드와 문서 생성이 한 번의 요청으로 처리됨
        
        Args:
            dataset: Dataset 딕셔너리
            file_path: 업로드할 파일 경로
            metadata: 메타데이터 (현재 지원 안 됨 -> update_document로 별도 처리 권장)
            display_name: 표시 이름
            parser_config: Parser 설정 (현재 dataset 단위 설정 사용)
        
        Returns:
            {'document_id': str, 'file_id': str} (성공 시) 또는 None (실패 시)
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
            
            # v21: 한 번의 요청으로 파일 업로드 및 문서 생성
            with open(file_path, 'rb') as f:
                files = {
                    'file': (display_name, f, 'application/octet-stream')
                }
                
                # _make_request가 자동으로 Content-Type을 제거하고 multipart/form-data로 설정
                response = self._make_request(
                    'POST',
                    f'/api/v1/datasets/{kb_id}/documents',
                    files=files
                )
            
            if response.status_code != 200:
                logger.error(f"✗ 파일 업로드 실패 (HTTP {response.status_code}): {response.text}")
                return None
            
            result = response.json()
            if result.get('code') != 0:
                logger.error(f"✗ 파일 업로드 실패: {result.get('message')}")
                return None
            
            # 응답 구조: {'code': 0, 'data': [{'id': 'doc_id', 'name': '...', 'run': 'UNSTART', ...}]}
            documents = result.get('data', [])
            
            if not documents or not isinstance(documents, list):
                logger.error("✗ 업로드된 문서 정보를 찾을 수 없습니다.")
                logger.error(f"   응답 데이터: {result.get('data')}")
                return None
            
            # 첫 번째 문서 정보 추출
            doc = documents[0]
            document_id = doc.get('id')
            
            if not document_id:
                logger.error("✗ 문서 ID를 찾을 수 없습니다.")
                logger.error(f"   문서 정보: {doc}")
                return None
            
            logger.info(f"✓ 파일 업로드 완료: {display_name} (Document ID: {document_id})")
            
            # document_id만 사용 (별도의 file_id 개념 없음)
            # 하지만 호환성을 위해 동일한 ID 반환
            return {
                'document_id': document_id,
                'file_id': document_id  # document_id와 동일
            }
        
        except Exception as e:
            logger.error(f"✗ 파일 업로드 실패 ({file_path.name}): {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def update_document(self, dataset_id: str, document_id: str, metadata: Dict) -> bool:
        """
        문서 정보(메타데이터) 업데이트
        
        Args:
            dataset_id: 지식베이스 ID
            document_id: 문서 ID
            metadata: 업데이트할 메타데이터 (meta_fields)
            
        Returns:
            성공 여부
        """
        try:
            logger.debug(f"문서 메타데이터 업데이트 시도: KB={dataset_id}, Doc={document_id}")
            
            # API: PUT /api/v1/datasets/{dataset_id}/documents/{document_id}
            endpoint = f'/api/v1/datasets/{dataset_id}/documents/{document_id}'
            
            payload = {
                "meta_fields": metadata
            }
            
            response = self._make_request(
                'PUT',
                endpoint,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    logger.info(f"✓ 메타데이터 업데이트 완료: {document_id}")
                    return True
                else:
                    logger.error(f"✗ 메타데이터 업데이트 실패: {result.get('message')}")
                    return False
            else:
                logger.error(f"✗ 메타데이터 업데이트 실패 (HTTP {response.status_code}): {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"문서 업데이트 중 오류: {e}")
            return False

    def update_document_parser(self, dataset_id: str, document_id: str, chunk_method: str = "table") -> bool:
        """
        문서의 파서(chunk_method) 업데이트
        
        Args:
            dataset_id: 지식베이스 ID
            document_id: 문서 ID
            chunk_method: 파싱 방법 (기본: "table")
            
        Returns:
            성공 여부
        """
        try:
            logger.debug(f"문서 파서 업데이트 시도: KB={dataset_id}, Doc={document_id}, Method={chunk_method}")
            
            # API: PUT /api/v1/datasets/{dataset_id}/documents/{document_id}
            endpoint = f'/api/v1/datasets/{dataset_id}/documents/{document_id}'
            
            payload = {
                "chunk_method": chunk_method
            }
            
            response = self._make_request(
                'PUT',
                endpoint,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    logger.info(f"✓ 문서 파서 업데이트 완료: {document_id} → {chunk_method}")
                    return True
                else:
                    logger.error(f"✗ 문서 파서 업데이트 실패: {result.get('message')}")
                    return False
            else:
                logger.error(f"✗ 문서 파서 업데이트 실패 (HTTP {response.status_code}): {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"문서 파서 업데이트 중 오류: {e}")
            return False

    def start_batch_parse(self, dataset: Dict, document_ids: List[str] = None) -> bool:
        """
        지식베이스의 문서 파싱 시작
        
        Args:
            dataset: Dataset 딕셔너리
            document_ids: 파싱할 문서 ID 리스트 (None이면 미파싱 문서 자동 조회)
        
        Returns:
            성공 여부
        """
        try:
            kb_id = dataset.get('id')
            kb_name = dataset.get('name', 'Unknown')
            
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return False
            
            # document_ids가 없으면 미파싱 문서 자동 조회
            if not document_ids:
                logger.info(f"파싱할 문서 ID 목록이 없습니다. 미파싱 문서 조회 중...")
                docs = self.get_documents_in_dataset(dataset, page=1, page_size=1000)
                
                # run="UNSTART"인 문서만 필터링
                document_ids = [
                    doc['id'] for doc in docs 
                    if doc.get('run') in ['UNSTART', '0']
                ]
                
                if not document_ids:
                    logger.warning(f"파싱할 문서가 없습니다 (모든 문서가 이미 파싱됨).")
                    return False
                
                logger.info(f"미파싱 문서 {len(document_ids)}개 발견")
            
            logger.info(f"파싱 시작: {kb_name} ({len(document_ids)}개 문서)")
            
            # 특정 문서 ID들만 파싱
            parse_response = self._make_request(
                'POST',
                f'/api/v1/datasets/{kb_id}/chunks',
                json={'document_ids': document_ids}
            )
            
            if parse_response.status_code == 200:
                parse_result = parse_response.json()
                if parse_result.get('code') == 0:
                    logger.info(f"✓ 파싱 요청 완료 ({len(document_ids)}개 문서)")
                    logger.info(f"파싱은 백그라운드에서 진행됩니다.")
                    return True
                else:
                    logger.error(f"파싱 요청 실패: {parse_result.get('message')}")
                    return False
            else:
                logger.error(f"파싱 요청 실패 (HTTP {parse_response.status_code}): {parse_response.text}")
                return False
        
        except Exception as e:
            logger.error(f"파싱 실패: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def stop_batch_parse(self, dataset: Dict, document_ids: List[str]) -> bool:
        """
        지식베이스의 문서 파싱 중지
        
        Args:
            dataset: Dataset 딕셔너리
            document_ids: 파싱 중지할 문서 ID 리스트
        
        Returns:
            성공 여부
        """
        try:
            kb_id = dataset.get('id')
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return False
            
            if not document_ids:
                logger.warning("파싱 중지할 문서 ID 목록이 없습니다.")
                return False
                
            logger.info(f"파싱 중지 요청: {len(document_ids)}개 문서")
            
            # DELETE /api/v1/datasets/{kb_id}/chunks
            response = self._make_request(
                'DELETE',
                f'/api/v1/datasets/{kb_id}/chunks',
                json={'document_ids': document_ids}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    logger.info(f"✓ 파싱 중지 요청 완료")
                    return True
                else:
                    logger.error(f"파싱 중지 실패: {result.get('message')}")
                    return False
            else:
                logger.error(f"파싱 중지 실패 (HTTP {response.status_code}): {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"파싱 중지 중 오류: {e}")
            return False

    def get_parse_progress(self, dataset: Dict, document_ids: List[str] = None) -> Optional[Dict]:
        """
        지식베이스의 파싱 진행 상황 조회
        문서별 run 상태를 조회하여 진행 상황 계산
        
        Args:
            dataset: Dataset 딕셔너리
            document_ids: 확인할 문서 ID 리스트 (None이면 전체 문서)
        
        Returns:
            진행 상황 딕셔너리 {'status': str, 'current': int, 'total': int, ...} 또는 None
        """
        try:
            kb_id = dataset.get('id')
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return None
            
            # 문서 목록 조회
            docs = self.get_documents_in_dataset(dataset, page=1, page_size=1000)
            
            if not docs:
                return None
            
            # 특정 문서만 필터링
            if document_ids:
                docs = [d for d in docs if d.get('id') in document_ids]
            
            if not docs:
                return None
            
            # 상태 집계 (run: UNSTART=0, RUNNING=1, CANCEL=2, DONE=3, FAIL=4)
            status_counts = {
                'UNSTART': 0,
                'RUNNING': 0,
                'CANCEL': 0,
                'DONE': 0,
                'FAIL': 0
            }
            
            for doc in docs:
                run_status = doc.get('run', 'UNSTART')
                # 숫자 -> 텍스트 변환
                status_map = {
                    '0': 'UNSTART',
                    '1': 'RUNNING',
                    '2': 'CANCEL',
                    '3': 'DONE',
                    '4': 'FAIL'
                }
                run_status = status_map.get(str(run_status), run_status)
                
                if run_status in status_counts:
                    status_counts[run_status] += 1
            
            total = len(docs)
            completed = status_counts['DONE'] + status_counts['FAIL']
            running = status_counts['RUNNING']
            
            # 전체 상태 결정
            if completed == total:
                overall_status = 'completed'
            elif running > 0:
                overall_status = 'running'
            else:
                overall_status = 'idle'
            
            return {
                'status': overall_status,
                'total_documents': total,
                'current_document_index': completed,
                'status_counts': status_counts
            }
        
        except Exception as e:
            logger.warning(f"진행 상황 조회 중 에러: {e}")
            return None
    
    def get_documents_in_dataset(self, dataset: Dict, page: int = 1, page_size: int = 100) -> List[Dict]:
        """
        지식베이스의 문서 목록 조회
        
        Args:
            dataset: Dataset 딕셔너리
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지당 문서 수
        
        Returns:
            문서 목록 [{'id': 'xxx', 'name': 'yyy', 'run': 'DONE', ...}, ...]
        """
        try:
            kb_id = dataset.get('id')
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return []
            
            logger.debug(f"지식베이스 '{dataset.get('name')}' 문서 목록 조회 중...")
            
            response = self._make_request(
                'GET',
                f'/api/v1/datasets/{kb_id}/documents',
                params={
                    'page': page,
                    'page_size': page_size,
                    'orderby': 'create_time',
                    'desc': True
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    # 응답 구조: {'code': 0, 'data': {'total': N, 'docs': [...]}} 또는 {'code': 0, 'data': [...]}
                    data = result.get('data', [])
                    # data가 리스트면 그대로 사용, 딕셔너리면 'docs' 키 찾기
                    if isinstance(data, list):
                        documents = data
                    elif isinstance(data, dict):
                        documents = data.get('docs', [])
                    else:
                        documents = []
                    logger.info(f"문서 목록 조회 완료: {len(documents)}개 문서")
                    
                    # 디버깅: 첫 번째 문서의 구조 출력
                    if documents and len(documents) > 0:
                        logger.debug(f"첫 번째 문서 구조 샘플: {documents[0]}")
                    
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
    
    def get_document_by_id(self, dataset: Dict, document_id: str) -> Optional[Dict]:
        """
        특정 문서 ID로 문서 정보 조회
        
        Args:
            dataset: Dataset 딕셔너리
            document_id: 조회할 문서 ID
        
        Returns:
            문서 정보 딕셔너리 또는 None
        """
        try:
            kb_id = dataset.get('id')
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return None
            
            response = self._make_request(
                'GET',
                f'/api/v1/datasets/{kb_id}/documents',
                params={
                    'id': document_id,
                    'page': 1,
                    'page_size': 1
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    data = result.get('data', [])
                    if isinstance(data, list):
                        documents = data
                    elif isinstance(data, dict):
                        documents = data.get('docs', [])
                    else:
                        documents = []
                    
                    if documents:
                        return documents[0]
                    else:
                        logger.debug(f"문서를 찾을 수 없습니다: {document_id}")
                        return None
            
            return None
        
        except Exception as e:
            logger.debug(f"문서 조회 중 오류: {e}")
            return None
    
    def get_documents_by_ids(self, dataset: Dict, document_ids: List[str]) -> List[Dict]:
        """
        여러 문서 ID로 문서 정보 일괄 조회
        
        Args:
            dataset: Dataset 딕셔너리
            document_ids: 조회할 문서 ID 리스트
        
        Returns:
            문서 정보 리스트
        """
        documents = []
        for doc_id in document_ids:
            doc = self.get_document_by_id(dataset, doc_id)
            if doc:
                documents.append(doc)
        return documents
    
    def delete_document(self, dataset: Dict, document_id: str) -> bool:
        """
        지식베이스에서 문서 삭제
        
        Args:
            dataset: Dataset 딕셔너리 (참고용, document_id가 전역적으로 유니크하므로 필수는 아님)
            document_id: 삭제할 문서 ID
        
        Returns:
            성공 여부
        
        Note:
            Document ID는 전체 시스템에서 유니크하므로 kb_id 없이 삭제 가능
        """
        try:
            logger.debug(f"문서 삭제 시도: Doc ID={document_id}")
            
            # Document ID는 전역적으로 유니크하므로 kb_id 불필요
            # document 삭제는 dataset 내에서 수행
            kb_id = dataset.get('id')
            response = self._make_request(
                'DELETE',
                f'/api/v1/datasets/{kb_id}/documents',
                json={'ids': [document_id]}
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
        """지식베이스 정보 조회"""
        try:
            kb_id = dataset.get('id')
            if not kb_id:
                return {'error': 'No knowledge base ID'}
            
            response = self._make_request(
                'GET',
                f'/api/v1/datasets/{kb_id}/documents'
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    data = result.get('data', {})
                    # data가 딕셔너리면 total 가져오기, 리스트면 len 사용
                    if isinstance(data, dict):
                        doc_count = data.get('total', 0)
                    elif isinstance(data, list):
                        doc_count = len(data)
                    else:
                        doc_count = 0
                    return {
                        'id': kb_id,
                        'name': dataset.get('name', 'N/A'),
                        'document_count': doc_count
                    }
            
            return {
                'id': kb_id,
                'name': dataset.get('name', 'N/A'),
                'document_count': 'N/A'
            }
        
        except Exception as e:
            logger.error(f"지식베이스 정보 조회 실패: {e}")
            return {}
    
    def delete_all_documents_in_dataset(self, dataset: Dict) -> Dict:
        """
        지식베이스의 모든 문서 일괄 삭제
        
        Args:
            dataset: Dataset 딕셔너리
        
        Returns:
            삭제 결과 딕셔너리 {
                'total_documents': int,
                'deleted_count': int,
                'failed_count': int,
                'failed_ids': List[str]
            }
        """
        try:
            kb_id = dataset.get('id')
            kb_name = dataset.get('name', 'Unknown')
            
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return {
                    'total_documents': 0,
                    'deleted_count': 0,
                    'failed_count': 0,
                    'failed_ids': [],
                    'error': '지식베이스 ID 없음'
                }
            
            logger.info(f"지식베이스 '{kb_name}'의 모든 문서 삭제 시작")
            
            # 모든 문서 목록 조회 (페이지네이션 처리)
            all_documents = []
            page = 1
            page_size = 100
            
            while True:
                documents = self.get_documents_in_dataset(dataset, page=page, page_size=page_size)
                if not documents:
                    break
                
                all_documents.extend(documents)
                
                # 마지막 페이지인 경우 종료
                if len(documents) < page_size:
                    break
                
                page += 1
            
            total_documents = len(all_documents)
            logger.info(f"삭제할 문서 총 {total_documents}개 발견")
            
            if total_documents == 0:
                logger.info("삭제할 문서가 없습니다.")
                return {
                    'total_documents': 0,
                    'deleted_count': 0,
                    'failed_count': 0,
                    'failed_ids': []
                }
            
            # 모든 문서 삭제
            deleted_count = 0
            failed_count = 0
            failed_ids = []
            
            for idx, doc in enumerate(all_documents, 1):
                doc_id = doc.get('id')
                doc_name = doc.get('name', 'Unknown')
                
                if not doc_id:
                    logger.warning(f"문서 ID가 없습니다: {doc_name}")
                    failed_count += 1
                    continue
                
                logger.info(f"[{idx}/{total_documents}] 문서 삭제 중: {doc_name} (ID: {doc_id})")
                
                if self.delete_document(dataset, doc_id):
                    deleted_count += 1
                else:
                    failed_count += 1
                    failed_ids.append(doc_id)
            
            logger.info(f"문서 일괄 삭제 완료: 성공 {deleted_count}개, 실패 {failed_count}개")
            
            return {
                'total_documents': total_documents,
                'deleted_count': deleted_count,
                'failed_count': failed_count,
                'failed_ids': failed_ids
            }
        
        except Exception as e:
            logger.error(f"문서 일괄 삭제 중 오류: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return {
                'total_documents': 0,
                'deleted_count': 0,
                'failed_count': 0,
                'failed_ids': [],
                'error': str(e)
            }
    
    def _get_file_ids_from_db(self, document_id: str) -> List[str]:
        """
        DB에서 file2document 테이블을 직접 조회하여 file_id 목록 가져오기
        
        Args:
            document_id: 문서 ID
        
        Returns:
            file_id 목록
        """
        if not self.db_connector:
            logger.debug(f"DB 연결이 없어 file_id를 조회할 수 없습니다 (document_id={document_id})")
            return []
        
        try:
            query = """
                SELECT file_id 
                FROM file2document 
                WHERE document_id = :document_id
            """
            results = self.db_connector.execute_query(query, {'document_id': document_id})
            
            file_ids = [row['file_id'] for row in results if row.get('file_id')]
            
            if file_ids:
                logger.debug(f"✓ DB에서 file_id 조회 성공: document_id={document_id}, file_ids={file_ids}")
            else:
                logger.debug(f"⚠️ DB에서 file_id를 찾지 못함: document_id={document_id}")
            
            return file_ids
        
        except Exception as e:
            logger.warning(f"✗ DB에서 file_id 조회 중 오류 (document_id={document_id}): {e}")
            return []
    
    def _extract_file_ids_from_document(self, document: Dict) -> List[str]:
        """
        문서 객체에서 업로드된 파일 ID 목록을 추출
        
        Note:
            document 객체에는 file_id가 없으므로, DB에서 file2document 테이블을 조회합니다.
        """
        file_ids: List[str] = []
        
        try:
            # document_id 추출
            doc_id = document.get('id')
            if not doc_id:
                logger.warning("문서 객체에 id가 없습니다")
                return []
            
            # DB에서 file_id 조회
            file_ids = self._get_file_ids_from_db(doc_id)
            
            # DB 조회가 실패한 경우, 기존 방식으로 시도 (하위 호환성)
            if not file_ids and isinstance(document, dict):
                # 단일 키
                if 'file_id' in document and isinstance(document.get('file_id'), str):
                    file_ids.append(document['file_id'])
                
                # 배열 키
                for key in ['fileIds', 'file_ids']:
                    value = document.get(key)
                    if isinstance(value, list):
                        for v in value:
                            if isinstance(v, str):
                                file_ids.append(v)
                
                # 객체 리스트
                files_value = document.get('files')
                if isinstance(files_value, list):
                    for f in files_value:
                        if isinstance(f, dict):
                            fid = f.get('id')
                            if isinstance(fid, str):
                                file_ids.append(fid)
                        elif isinstance(f, str):
                            file_ids.append(f)
        
        except Exception as e:
            logger.warning(f"file_id 추출 중 오류: {e}")
        
        # 중복 제거
        return list(dict.fromkeys(file_ids))
    
    def delete_all_documents_and_files_in_dataset(self, dataset: Dict) -> Dict:
        """
        지식베이스의 모든 문서를 삭제하고, 연결된 업로드 파일도 함께 삭제
        """
        try:
            kb_id = dataset.get('id')
            kb_name = dataset.get('name', 'Unknown')
            if not kb_id:
                logger.error("지식베이스 ID를 찾을 수 없습니다.")
                return {
                    'total_documents': 0,
                    'deleted_documents': 0,
                    'failed_documents': 0,
                    'deleted_files': 0,
                    'failed_files': 0,
                    'failed_document_ids': [],
                    'failed_file_ids': [],
                    'error': '지식베이스 ID 없음'
                }
            
            logger.info(f"지식베이스 '{kb_name}' 전량 삭제(문서+파일) 시작")
            
            # 문서 목록 수집
            all_documents = []
            page = 1
            page_size = 100
            while True:
                documents = self.get_documents_in_dataset(dataset, page=page, page_size=page_size)
                if not documents:
                    break
                all_documents.extend(documents)
                if len(documents) < page_size:
                    break
                page += 1
            
            total_documents = len(all_documents)
            logger.info(f"삭제 대상 문서: {total_documents}개")
            
            if total_documents == 0:
                return {
                    'total_documents': 0,
                    'deleted_documents': 0,
                    'failed_documents': 0,
                    'deleted_files': 0,
                    'failed_files': 0,
                    'failed_document_ids': [],
                    'failed_file_ids': []
                }
            
            deleted_documents = 0
            failed_documents = 0
            failed_document_ids: List[str] = []
            
            deleted_files = 0
            failed_files = 0
            failed_file_ids: List[str] = []
            
            for idx, doc in enumerate(all_documents, 1):
                doc_id = doc.get('id')
                doc_name = doc.get('name', 'Unknown')
                file_ids = self._extract_file_ids_from_document(doc)
                
                if not doc_id:
                    logger.warning(f"문서 ID가 없습니다: {doc_name}")
                    failed_documents += 1
                    continue
                
                logger.info(f"[{idx}/{total_documents}] 문서 삭제: {doc_name} (ID: {doc_id})")
                if self.delete_document(dataset, doc_id):
                    deleted_documents += 1
                else:
                    failed_documents += 1
                    failed_document_ids.append(doc_id)
                    # 문서 삭제 실패 시 파일 삭제는 건너뜀
                    continue
                
                # 문서 삭제 시 연결된 파일도 자동으로 삭제됩니다
                # (최신 API에서는 별도로 파일을 삭제할 필요 없음)
                if file_ids:
                    logger.debug(f"문서에 연결된 파일 {len(file_ids)}개는 자동 삭제됨: {file_ids}")
                    deleted_files += len(file_ids)
            
            logger.info(f"전량 삭제 완료 - 문서: 성공 {deleted_documents}, 실패 {failed_documents} | 파일: 성공 {deleted_files}, 실패 {failed_files}")
            return {
                'total_documents': total_documents,
                'deleted_documents': deleted_documents,
                'failed_documents': failed_documents,
                'deleted_files': deleted_files,
                'failed_files': failed_files,
                'failed_document_ids': failed_document_ids,
                'failed_file_ids': failed_file_ids
            }
        
        except Exception as e:
            logger.error(f"문서/파일 전량 삭제 중 오류: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return {
                'total_documents': 0,
                'deleted_documents': 0,
                'failed_documents': 0,
                'deleted_files': 0,
                'failed_files': 0,
                'failed_document_ids': [],
                'failed_file_ids': [],
                'error': str(e)
            }
