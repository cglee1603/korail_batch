# 임베딩 모델 설정 관련 수정 사항

## 문제 원인

### 초기 상황
- `.env` 파일에서 `EMBEDDING_MODEL=bona/bge-m3-korean:latest` 또는 `qwen3-embedding:8b@Custom` 등을 설정
- API로 지식베이스 생성 시 이 값을 전달

### 발생한 문제
파싱 단계에서 다음 오류 발생:
```
LookupError: Model(qwen3-embedding:8b@Custom) not authorized
```

### 원인 분석

1. **데이터베이스 구조:**
   ```sql
   -- tenant 테이블
   embd_id: "qwen3-embedding:8b@Custom"  -- @ 기호 포함된 전체 문자열
   
   -- tenant_llm 테이블 (실제 모델 정보 저장)
   llm_factory: "Custom"
   llm_name: "qwen3-embedding:8b"  -- @ 없이 분리 저장
   ```

2. **서버 측 모델 조회 로직 (`llm_service.py`):**
   ```python
   # 1. llm_name에서 @Factory 분리 시도
   mdlnm, fid = split_model_name_and_factory(model_name)
   
   # 2. tenant_llm 테이블 조회
   model_config = TenantLLMService.get_api_key(tenant_id, mdlnm, fid)
   
   # 3. 조회 실패 시 LookupError 발생
   if not model_config:
       raise LookupError("Model({}) not authorized".format(mdlnm))
   ```

3. **문제 상황:**
   - API에서 명시적으로 `embedding_model`을 전달하면, 그 값이 지식베이스의 `embd_id`로 저장됨
   - 파싱 시 이 `embd_id` 값으로 `tenant_llm` 테이블 조회 시도
   - `@Custom` 접미사가 있는 전체 문자열로 조회하면 실패 가능

## 해결 방법

### 수정 사항

**`config.py` 수정:**
```python
# 기존 코드
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")

# 수정 후
EMBEDDING_MODEL = None  # 항상 None 사용 - 서버가 tenant.embd_id 자동 적용
```

**`batch_processor.py` 수정:**
```python
dataset = self.ragflow_client.get_or_create_dataset(
    name=dataset_name,
    description=dataset_description,
    permission=DATASET_PERMISSION,
    embedding_model=None  # 시스템 기본값 사용 (tenant.embd_id)
)
```

**`ragflow_client.py` 수정:**
```python
# embedding_model이 명시적으로 지정된 경우에만 전달
# None이면 서버에서 tenant.embd_id를 사용함
if embedding_model:
    create_payload["embedding_model"] = embedding_model
```

### 작동 원리

1. **API 요청 시 `embedding_model` 생략:**
   ```python
   POST /api/v1/datasets
   {
       "name": "KTX-EMU 매뉴얼",
       "permission": "team"
       // embedding_model 필드 없음
   }
   ```

2. **서버 측 자동 처리 (`dataset.py:142-143`):**
   ```python
   if not req.get("embedding_model"):
       req["embedding_model"] = t.embd_id  # tenant의 기본 모델 자동 사용
   ```

3. **결과:**
   - 지식베이스는 tenant 설정의 기본 임베딩 모델을 사용
   - RAGFlow UI에서 설정한 모델과 동일하게 작동
   - `@Factory` 형식 문제 없이 정상 조회 가능

## 장점

1. **UI와 일관성:**
   - RAGFlow UI에서 설정한 기본 모델을 자동으로 사용
   - 사용자가 별도로 모델을 지정할 필요 없음

2. **유지보수 용이:**
   - `.env` 파일에서 모델 설정 불필요
   - 서버 설정 변경 시 자동으로 반영

3. **오류 방지:**
   - `@Factory` 형식 문제 회피
   - 모델 이름 불일치로 인한 오류 방지

## 테스트 결과

### 이전 (오류 발생)
```
ERROR: Model(qwen3-embedding:8b@Custom) not authorized
```

### 이후 (정상 작동)
```
INFO: 새 지식베이스 생성: KTX-EMU 매뉴얼
INFO:   - 임베딩 모델: 시스템 기본값 (tenant 설정)
INFO: ✓ 지식베이스 생성 성공
```

## 주의 사항

- `.env`의 `EMBEDDING_MODEL` 설정은 **무시됨**
- 모델 변경이 필요한 경우 **RAGFlow UI**에서 tenant 기본 모델을 변경해야 함
- 특정 지식베이스에만 다른 모델을 사용하려면 서버 측 코드 수정 필요

## 관련 파일

- `rag_batch/src/config.py` - `EMBEDDING_MODEL = None` 설정
- `rag_batch/src/batch_processor.py` - `embedding_model=None` 전달
- `rag_batch/src/ragflow_client.py` - None 체크 로직
- `rag_batch/env.example` - 주석 업데이트

---

**수정 일시:** 2025-10-14  
**수정자:** AI Assistant  
**버전:** 1.0

