# HTTP API 마이그레이션 가이드

## 변경 사항

### SDK → HTTP API 직접 호출로 전환

기존 `ragflow-sdk`를 사용하던 방식에서 RAGFlow HTTP API를 직접 호출하는 방식으로 변경했습니다.

### 변경 이유

1. **버킷 매핑 문제 해결**: SDK 업로드 시 파일 테이블의 `parent_id`가 잘못 저장되는 문제
2. **UI와 동일한 경로**: HTTP API는 UI와 동일한 서버 경로를 사용하여 일관성 보장
3. **투명성**: API 호출 과정이 명확하게 보임

## API 엔드포인트

### 1. 지식베이스 관리

#### 지식베이스 목록 조회
```http
GET /api/v1/datasets?name={name}
Authorization: Bearer {API_KEY}
```

#### 지식베이스 생성
```http
POST /api/v1/datasets
Authorization: Bearer {API_KEY}
Content-Type: application/json

{
  "name": "지식베이스명",
  "description": "설명",
  "permission": "me",
  "embedding_model": "BAAI/bge-large-zh-v1.5"
}
```

#### 지식베이스 삭제
```http
DELETE /api/v1/datasets
Authorization: Bearer {API_KEY}
Content-Type: application/json

{
  "ids": ["dataset_id"]
}
```

### 2. 문서 업로드

```http
POST /api/v1/datasets/{dataset_id}/documents
Authorization: Bearer {API_KEY}
Content-Type: multipart/form-data

file: (binary)
```

**응답 예시:**
```json
{
  "code": 0,
  "data": [
    {
      "id": "doc_id",
      "name": "filename.pdf",
      "dataset_id": "kb_id",
      "chunk_count": 0,
      "token_count": 0,
      "chunk_method": "naive",
      "run": "UNSTART"
    }
  ]
}
```

### 3. 문서 목록 조회

```http
GET /api/v1/datasets/{dataset_id}/documents
Authorization: Bearer {API_KEY}
```

**응답 예시:**
```json
{
  "code": 0,
  "data": {
    "total": 10,
    "docs": [
      {
        "id": "doc_id",
        "name": "filename.pdf",
        "dataset_id": "kb_id",
        "chunk_count": 749,
        "token_count": 125000,
        "chunk_method": "naive",
        "run": "DONE"
      }
    ]
  }
}
```

### 4. 일괄 파싱

```http
POST /api/v1/datasets/{dataset_id}/chunks
Authorization: Bearer {API_KEY}
Content-Type: application/json

{
  "document_ids": ["doc_id1", "doc_id2"]
}
```

## 코드 변경 사항

### RAGFlowClient 클래스

#### 이전 (SDK 사용)
```python
from ragflow_sdk import RAGFlow

class RAGFlowClient:
    def __init__(self):
        self.rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
    
    def upload_document(self, dataset, file_path):
        doc_info = {
            "display_name": file_path.name,
            "blob": BytesIO(file_content)
        }
        uploaded_docs = dataset.upload_documents([doc_info])
        return True
```

#### 이후 (HTTP API 직접 호출)
```python
import requests

class RAGFlowClient:
    def __init__(self):
        self.api_key = API_KEY
        self.base_url = BASE_URL
        self.headers = {'Authorization': f'Bearer {self.api_key}'}
    
    def upload_document(self, dataset, file_path):
        dataset_id = dataset.get('id')
        url = f"{self.base_url}/api/v1/datasets/{dataset_id}/documents"
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/octet-stream')}
            response = requests.post(url, headers=self.headers, files=files)
        
        return response.status_code == 200
```

## 주요 변경 포인트

### 1. 지식베이스 객체 → 딕셔너리

**이전:**
```python
dataset = self.rag.create_dataset(name="test")
dataset_id = dataset.id
```

**이후:**
```python
dataset = self.get_or_create_dataset(name="test")
dataset_id = dataset.get('id')
```

### 2. 문서 업로드

**이전:**
```python
doc_info = {
    "display_name": filename,
    "blob": BytesIO(content)
}
uploaded_docs = dataset.upload_documents([doc_info])
```

**이후:**
```python
with open(file_path, 'rb') as f:
    files = {'file': (filename, f, 'application/octet-stream')}
    response = requests.post(url, headers=headers, files=files)
```

### 3. 일괄 파싱

**이전:**
```python
documents = dataset.list_documents()
document_ids = [doc.id for doc in documents]
dataset.async_parse_documents(document_ids)
```

**이후:**
```python
# 문서 목록 조회
response = requests.get(f"{base_url}/api/v1/datasets/{dataset_id}/documents")
documents = response.json()['data']['docs']
document_ids = [doc['id'] for doc in documents]

# 파싱 요청
requests.post(
    f"{base_url}/api/v1/datasets/{dataset_id}/chunks",
    json={'document_ids': document_ids}
)
```

## 의존성 변경

### requirements.txt

**제거:**
```
ragflow-sdk>=0.5.0
```

**유지 (이미 있음):**
```
requests>=2.31.0
urllib3>=2.0.0
certifi>=2023.7.22
```

## 테스트 방법

### 1. 패키지 재설치
```powershell
cd rag_batch
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 단일 파일 테스트
```powershell
python -c "from src.ragflow_client import RAGFlowClient; c = RAGFlowClient(); print('OK')"
```

### 3. 업로드 테스트
```python
from pathlib import Path
from src.ragflow_client import RAGFlowClient

client = RAGFlowClient()
dataset = client.get_or_create_dataset("테스트KB")
success = client.upload_document(dataset, Path("test.pdf"))
print(f"업로드 결과: {success}")
```

## 버킷 매핑 확인

### 올바른 흐름

1. **업로드 시**: `STORAGE_IMPL.put(kb.id, location, blob)`
   - 버킷 = `kb.id` (지식베이스 ID)
   - 오브젝트 = `location` (파일명)

2. **다운로드/파싱 시**: `File2DocumentService.get_storage_address(doc_id)`
   - 반환값 = `(kb_id, location)`
   - 버킷 = `kb_id`

3. **파일 테이블 저장**:
   - `parent_id` = KB 폴더 ID (파일 트리용)
   - 실제 스토리지 주소는 `document.kb_id` + `document.location` 사용

### 확인 방법

#### MinIO 버킷 확인
```sql
-- 업로드된 문서의 KB ID
SELECT DISTINCT kb_id FROM document WHERE name LIKE '%test%';
```

MinIO UI에서 해당 KB ID를 버킷명으로 검색하면 파일이 있어야 함.

#### 다운로드 테스트
```python
# RAGFlow UI에서 문서 다운로드 버튼 클릭 → 정상 다운로드 확인
```

#### 파싱 테스트
```python
# RAGFlow UI에서 파싱 시작 → 진행률 상승 확인 (에러 없음)
```

## 참고 문서

- [RAGFlow HTTP API Reference](https://ragflow.io/docs/dev/http_api_reference)
- [RAGFlow Python SDK (비교용)](https://github.com/infiniflow/ragflow/tree/main/sdk)

## 문제 해결

### API 호출 실패
```python
# 로그 확인
tail -f rag_batch/logs/batch_*.log

# API 키 확인
echo $RAGFLOW_API_KEY

# 서버 상태 확인
curl -H "Authorization: Bearer $RAGFLOW_API_KEY" \
  http://localhost:9380/api/v1/datasets
```

### 버킷 불일치
```sql
-- 문서와 실제 스토리지 비교
SELECT d.id, d.name, d.kb_id, d.location 
FROM document d 
WHERE d.name = 'problem_file.pdf';

-- MinIO에서 {kb_id}/{location} 경로 확인
```

## 마이그레이션 체크리스트

- [x] `ragflow_client.py` HTTP API로 재작성
- [x] `requirements.txt`에서 `ragflow-sdk` 제거 (주석 처리)
- [x] `requests` 라이브러리 사용
- [ ] 기존 환경에서 `pip install -r requirements.txt` 재실행
- [ ] 테스트 파일로 업로드 → 다운로드 → 파싱 검증
- [ ] MinIO 버킷과 DB의 `kb_id` 일치 확인

