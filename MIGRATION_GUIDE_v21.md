# RAGFlow v21 마이그레이션 가이드

## 개요
기존 RAGFlow Plus (v0.17.2 기반) 배치 프로그램을 RAGFlow v21로 업그레이드하기 위한 가이드입니다.

## 주요 변경 사항

### 1. API 엔드포인트 및 필드명 변경

#### Dataset(지식베이스) API
| 항목 | 기존 (Plus) | 신규 (v21) | 변경 내용 |
|------|-----------|-----------|----------|
| 필드: 임베딩 모델 | `embd_id` | `embedding_model` | API 요청/응답 시 필드명 변경 |
| 필드: 청킹 방법 | `parser_id` | `chunk_method` | API 요청/응답 시 필드명 변경 |
| 필드: 청크 수 | `chunk_num` | `chunk_count` | 응답 필드명 변경 |
| 필드: 문서 수 | `doc_num` | `document_count` | 응답 필드명 변경 |
| 필드: KB ID | `kb_id` | `dataset_id` | 일부 응답에서 필드명 통일 |

#### Document(문서) 업로드 프로세스
**기존 (2단계)**:
```python
# Step 1: 파일 업로드
POST /api/v1/files/upload
Response: {"data": [{"id": "file_id", ...}]}

# Step 2: 지식베이스에 문서 추가
POST /api/v1/knowledgebases/{kb_id}/documents
Body: {"file_ids": ["file_id"]}
```

**신규 v21 (1단계 - 간소화)**:
```python
# 파일 업로드 및 문서 생성을 한 번에 처리
POST /datasets/<dataset_id>/documents
Content-Type: multipart/form-data
Body:
  - file: (파일 데이터)
  - parent_path: (선택적)

Response: {
  "data": [{
    "id": "document_id",
    "name": "파일명",
    "chunk_count": 0,
    "dataset_id": "xxx",
    "run": "UNSTART",
    ...
  }]
}
```

#### 파싱 API
**기존**:
```python
POST /api/v1/knowledgebases/{kb_id}/batch_parse_sequential/start
# 전체 지식베이스의 모든 문서를 순차적으로 파싱
```

**신규 v21**:
```python
POST /datasets/<dataset_id>/chunks
Body: {"document_ids": ["doc1", "doc2", ...]}
# 특정 문서들만 선택적으로 파싱 시작
```

### 2. Validation 강화

ragflow21v는 Pydantic 기반 validation을 사용합니다:

```python
# CreateDatasetReq
class CreateDatasetReq(BaseModel):
    name: str  # Required
    avatar: Optional[str]
    description: Optional[str]
    embedding_model: Optional[str]
    permission: Optional[Literal['me', 'team']]
    chunk_method: Optional[str]
    parser_config: Optional[dict]
```

### 3. 응답 형식 변경

**Dataset 목록 조회**:
```python
# 기존
GET /api/v1/knowledgebases?page=1&size=100
Response: {
  "code": 0,
  "data": {
    "list": [...],
    "total": 10
  }
}

# 신규 v21
GET /datasets?page=1&page_size=30
Response: {
  "code": 0,
  "data": [...],  # 리스트 직접 반환
  "total": 10     # total은 별도 필드
}
```

## 수정 대상 파일

### 1. `src/ragflow_client.py` (핵심 수정)

**주요 수정 사항**:

#### A. Dataset 생성 API
```python
# 기존 코드
create_payload = {
    "name": name,
    "permission": permission,
    "chunk_method": chunk_method  # ← 이미 올바름
}
if embedding_model:
    create_payload["embedding_model"] = embedding_model  # ← 이미 올바름

response = self._make_request(
    'POST',
    '/api/v1/knowledgebases',  # ← 변경 필요
    json=create_payload
)

# 수정 후
response = self._make_request(
    'POST',
    '/datasets',  # v21 SDK 엔드포인트
    json=create_payload
)
```

#### B. Document 업로드 API (⚠️ 중요한 변경)
```python
# 기존 코드 (2단계)
def upload_document(self, dataset, file_path, metadata=None, display_name=None):
    # Step 1: 파일 업로드
    upload_response = self._make_request(
        'POST',
        '/api/v1/files/upload',
        files=files
    )
    file_id = upload_result['data'][0]['id']
    
    # Step 2: 문서 추가
    add_doc_response = self._make_request(
        'POST',
        f'/api/v1/knowledgebases/{kb_id}/documents',
        json={'file_ids': [file_id]}
    )

# 수정 후 (1단계로 간소화)
def upload_document(self, dataset, file_path, metadata=None, display_name=None):
    kb_id = dataset.get('id')
    
    with open(file_path, 'rb') as f:
        files = {
            'file': (display_name or file_path.name, f, 'application/octet-stream')
        }
        
        # 한 번의 요청으로 업로드 및 문서 생성
        response = self._make_request(
            'POST',
            f'/datasets/{kb_id}/documents',
            files=files
        )
    
    if response.status_code == 200:
        result = response.json()
        if result.get('code') == 0:
            # 응답 데이터는 리스트 형태
            docs = result.get('data', [])
            if docs:
                doc = docs[0]
                # 필드명 변환: chunk_count, dataset_id
                return {
                    'document_id': doc.get('id'),
                    'file_id': doc.get('id')  # v21에서는 document_id만 사용
                }
```

#### C. 파싱 API
```python
# 기존 코드
def start_batch_parse(self, dataset):
    kb_id = dataset.get('id')
    response = self._make_request(
        'POST',
        f'/api/v1/knowledgebases/{kb_id}/batch_parse_sequential/start'
    )

# 수정 후
def start_batch_parse(self, dataset, document_ids=None):
    """
    문서 파싱 시작
    
    Args:
        dataset: Dataset 딕셔너리
        document_ids: 파싱할 문서 ID 리스트 (None이면 업로드된 모든 문서)
    """
    kb_id = dataset.get('id')
    
    # document_ids가 없으면 최근 업로드된 문서 목록 조회
    if not document_ids:
        # 미파싱 문서 조회 로직 필요
        docs = self.get_documents_in_dataset(dataset, page=1, page_size=100)
        # run="UNSTART"인 문서만 필터링
        document_ids = [
            doc['id'] for doc in docs 
            if doc.get('run') == 'UNSTART' or doc.get('run') == '0'
        ]
    
    if not document_ids:
        logger.warning("파싱할 문서가 없습니다.")
        return False
    
    response = self._make_request(
        'POST',
        f'/datasets/{kb_id}/chunks',
        json={'document_ids': document_ids}
    )
    
    return response.status_code == 200
```

#### D. 문서 목록 조회 API
```python
# 기존 코드
def get_documents_in_dataset(self, dataset, page=1, page_size=100):
    response = self._make_request(
        'GET',
        f'/api/v1/knowledgebases/{kb_id}/documents',
        params={'page': page, 'page_size': page_size}
    )

# 수정 후
def get_documents_in_dataset(self, dataset, page=1, page_size=100):
    kb_id = dataset.get('id')
    
    response = self._make_request(
        'GET',
        f'/datasets/{kb_id}/documents',
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
            data = result.get('data', {})
            # v21 응답 구조: {"total": N, "docs": [...]}
            documents = data.get('docs', [])
            return documents
```

### 2. `src/batch_processor.py`

**수정 사항**:

#### A. process_item 메서드
```python
# document_id 추적을 위한 수정
def process_item(self, dataset, item):
    # ... 기존 파일 처리 로직 ...
    
    # 업로드된 문서 ID들을 추적
    uploaded_doc_ids = []
    
    for processed_path, file_type in processed_files:
        upload_result = self.ragflow_client.upload_document(
            dataset=dataset,
            file_path=processed_path,
            metadata=enhanced_metadata,
            display_name=processed_path.name
        )
        
        if upload_result:
            doc_id = upload_result.get('document_id')
            uploaded_doc_ids.append(doc_id)
            # ... RevisionDB 저장 ...
    
    return uploaded_doc_ids  # 리스트 반환
```

#### B. process_sheet_with_revision 메서드
```python
def process_sheet_with_revision(self, sheet_name, sheet_type, items, headers, monitor_progress=True):
    # ... 기존 로직 ...
    
    # 업로드된 문서 ID들 수집
    uploaded_document_ids = []
    
    for item in items:
        doc_ids = self.process_item(dataset, item)  # 리스트 반환
        if doc_ids:
            uploaded_document_ids.extend(doc_ids)
    
    # 일괄 파싱 시작 (특정 문서 ID들만)
    if uploaded_document_ids:
        logger.info(f"[{sheet_name}] {len(uploaded_document_ids)}개 문서 파싱 시작")
        parse_started = self.ragflow_client.start_batch_parse(
            dataset,
            document_ids=uploaded_document_ids
        )
```

### 3. `src/config.py`

**변경 불필요** - MANAGEMENT_USERNAME/PASSWORD 방식은 v21에서도 지원됨

## 마이그레이션 체크리스트

- [ ] `ragflow_client.py` 수정
  - [ ] Dataset 생성 엔드포인트: `/datasets`
  - [ ] Document 업로드 간소화 (1단계 프로세스)
  - [ ] 파싱 API: `/datasets/{id}/chunks` + `document_ids`
  - [ ] 문서 목록 조회 응답 구조 변경
  - [ ] 필드명 변환 (embedding_model, chunk_method, chunk_count 등)

- [ ] `batch_processor.py` 수정
  - [ ] process_item: 문서 ID 리스트 반환
  - [ ] 업로드된 문서 ID 추적
  - [ ] start_batch_parse 호출 시 document_ids 전달

- [ ] 테스트
  - [ ] Dataset 생성 테스트
  - [ ] Document 업로드 테스트
  - [ ] 파싱 시작 테스트
  - [ ] Revision 관리 테스트
  - [ ] Excel 처리 종단 간 테스트

## 호환성 주의사항

### 1. Management API vs SDK API
- RAGFlow v21에서 Management API (`/api/v1/...`)는 여전히 존재하지만, SDK 스타일 엔드포인트 (`/datasets`, `/documents`)를 사용하는 것을 권장
- Management API는 주로 관리자 패널용

### 2. 인증 방식
- 기존: JWT 토큰 (username/password 로그인)
- v21: 동일하게 지원됨 (token_required 데코레이터)

### 3. 파싱 진행 상황 모니터링
- 기존: `/batch_parse_sequential/progress` 엔드포인트
- v21: 문서별 `run` 상태 확인 (`UNSTART`, `RUNNING`, `DONE`, `FAIL`)

```python
# v21 진행 상황 확인 방법
def monitor_parse_progress(self, dataset, document_ids):
    while True:
        docs = self.get_documents_in_dataset(dataset)
        target_docs = [d for d in docs if d['id'] in document_ids]
        
        # 상태 집계
        status_counts = {}
        for doc in target_docs:
            status = doc.get('run', 'UNKNOWN')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # 완료 체크
        if status_counts.get('DONE', 0) + status_counts.get('FAIL', 0) == len(target_docs):
            break
        
        time.sleep(10)
```

## 테스트 계획

1. **단위 테스트**
   - Dataset CRUD 테스트
   - Document 업로드 테스트
   - 파싱 시작/상태 확인 테스트

2. **통합 테스트**
   - Excel 파일 전체 처리 플로우
   - Revision 관리 시나리오
   - 압축 파일 처리

3. **성능 테스트**
   - 대량 문서 업로드 (100개+)
   - 동시 파싱 처리

## 참고 자료

- RAGFlow v21 API 문서: `/datasets` SDK endpoints
- 기존 코드: `ragflow17v/ragflow/api/apps/sdk/`
- 신규 코드: `ragflow21v/api/apps/sdk/`


