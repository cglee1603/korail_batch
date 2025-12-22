# RAGFlow v21 마이그레이션 완료 요약

## ✅ 완료된 작업

### 1. `rag_batch/src/ragflow_client.py` 수정 완료

#### A. Dataset API 엔드포인트 변경
- ✅ **생성**: `/api/v1/knowledgebases` → `/datasets`
- ✅ **조회**: `/api/v1/knowledgebases` → `/datasets`
- ✅ **삭제**: `/api/v1/knowledgebases/{id}` → `/datasets/{id}`

#### B. Document 업로드 API 간소화 ⭐ (핵심 변경)
**기존 (2단계 프로세스)**:
```python
# Step 1: 파일 업로드
POST /api/v1/files/upload
# Step 2: 문서 추가
POST /api/v1/knowledgebases/{kb_id}/documents
```

**신규 v21 (1단계 프로세스)**:
```python
# 한 번의 요청으로 업로드 및 문서 생성
POST /datasets/{kb_id}/documents
- file: (multipart/form-data)
→ 응답: {'code': 0, 'data': [{'id': 'doc_id', ...}]}
```

#### C. 파싱 API 변경 및 document_ids 지원 ⭐
**기존**:
```python
POST /api/v1/knowledgebases/{kb_id}/batch_parse_sequential/start
# 전체 지식베이스 일괄 파싱
```

**신규 v21**:
```python
POST /datasets/{kb_id}/chunks
Body: {"document_ids": ["doc1", "doc2", ...]}
# 특정 문서들만 선택적 파싱
```

**새로운 메서드 시그니처**:
```python
def start_batch_parse(self, dataset: Dict, document_ids: List[str] = None) -> bool:
    # document_ids가 없으면 미파싱 문서 자동 조회
    if not document_ids:
        docs = self.get_documents_in_dataset(dataset)
        document_ids = [doc['id'] for doc in docs if doc.get('run') == 'UNSTART']
```

#### D. 문서 목록 조회 응답 구조 변경
**기존 응답 구조**:
```json
{
  "code": 0,
  "data": {
    "list": [...],
    "total": 10
  }
}
```

**v21 응답 구조**:
```json
{
  "code": 0,
  "data": {
    "docs": [...],
    "total": 10
  }
}
```

**변경된 코드**:
```python
# 기존
documents = data.get('list', [])

# v21
documents = data.get('docs', [])
```

#### E. 문서 삭제 API 변경
```python
# 기존
DELETE /api/v1/knowledgebases/documents/{document_id}

# v21 (dataset 컨텍스트 필요)
DELETE /datasets/{kb_id}/documents
Body: {"ids": ["doc1", "doc2", ...]}
```

#### F. 파싱 진행 상황 조회 변경
**기존**: Management API의 순차 파싱 진행 상황 엔드포인트 사용

**v21**: 문서 목록을 조회하여 각 문서의 `run` 상태를 집계
- `run` 상태: UNSTART=0, RUNNING=1, CANCEL=2, DONE=3, FAIL=4
- 상태 집계를 통해 진행률 계산

### 2. `rag_batch/src/batch_processor.py` 수정 완료

#### A. `process_item` 메서드 반환값 변경 ⭐
**기존**:
```python
def process_item(self, dataset, item) -> Optional[str]:
    # 단일 문서 ID 반환
    return document_id
```

**v21**:
```python
def process_item(self, dataset, item) -> List[str]:
    # 업로드된 모든 문서 ID 리스트 반환 (압축 파일 대응)
    uploaded_doc_ids = []
    for processed_path, file_type in processed_files:
        upload_result = self.ragflow_client.upload_document(...)
        if upload_result:
            doc_id = upload_result.get('document_id')
            uploaded_doc_ids.append(doc_id)
    return uploaded_doc_ids
```

**변경 이유**: 
- v21은 각 파일 업로드마다 즉시 문서 생성
- 압축 파일 해제 시 여러 문서 ID가 생성될 수 있음
- 파싱 시 정확한 문서 ID 리스트 필요

#### B. 문서 ID 수집 및 파싱 시 전달
**모든 시트 처리 메서드 변경**:

```python
# process_sheet_with_revision
uploaded_document_ids = []
for item in items:
    doc_ids = self.process_item(dataset, item)  # 리스트 반환
    if doc_ids:
        uploaded_document_ids.extend(doc_ids)

# 파싱 시작 (특정 문서 ID들만)
if uploaded_document_ids:
    parse_started = self.ragflow_client.start_batch_parse(
        dataset,
        document_ids=uploaded_document_ids  # v21: 업로드된 문서만
    )
```

**적용된 메서드들**:
- ✅ `process_sheet_with_revision()` - Revision 관리 시트
- ✅ `process_sheet_attachments()` - 첨부파일 시트
- ✅ `process_sheet_as_text()` - 이력관리/소프트웨어 시트

#### C. 파싱 진행 상황 모니터링 업데이트
```python
def monitor_parse_progress(
    self, 
    dataset: Dict, 
    dataset_name: str, 
    document_ids: List[str] = None,  # v21: 모니터링 대상 문서 ID
    max_wait_minutes: int = 30
):
    # v21: 문서 ID 리스트로 진행 상황 조회
    progress = self.ragflow_client.get_parse_progress(
        dataset, 
        document_ids
    )
```

## 🔍 주요 변경 사항 요약

| 항목 | 기존 | v21 | 영향 |
|------|------|-----|------|
| **Document 업로드** | 2단계 프로세스 | 1단계로 간소화 | 코드 단순화, 성능 향상 |
| **파싱 API** | 전체 지식베이스 | 특정 문서 ID 지정 | 정확한 제어, 중복 파싱 방지 |
| **문서 목록 응답** | `data.list` | `data.docs` | 필드명 변경 |
| **process_item 반환값** | `Optional[str]` | `List[str]` | 압축 파일 다중 문서 지원 |
| **문서 삭제** | 단일 엔드포인트 | Dataset 컨텍스트 | 일관성 향상 |

## 📋 테스트 체크리스트

### 기본 기능 테스트
- [ ] Dataset 생성 테스트
- [ ] 단일 파일 업로드 및 파싱
- [ ] 압축 파일 업로드 및 파싱 (여러 문서 ID)
- [ ] 파싱 진행 상황 모니터링
- [ ] 문서 삭제

### Revision 관리 테스트
- [ ] 신규 문서 업로드
- [ ] 동일 revision 건너뛰기
- [ ] Revision 업데이트 (기존 문서 삭제 → 새 문서 업로드)
- [ ] RevisionDB 동기화 확인

### Excel 처리 테스트
- [ ] REV 관리 시트
- [ ] 작성버전 관리 시트
- [ ] 첨부파일 시트
- [ ] 이력관리 시트 (텍스트/Excel 업로드)
- [ ] 소프트웨어 시트

### 통합 테스트
- [ ] 대량 문서 업로드 (100개+)
- [ ] 여러 시트 동시 처리
- [ ] 파싱 타임아웃 시나리오
- [ ] 네트워크 오류 재시도

## 🚀 배포 가이드

### 1. 환경 설정 확인
`.env` 파일이 올바르게 설정되어 있는지 확인:
```bash
# RAGFlow 서버 주소 (v21)
RAGFLOW_BASE_URL=http://localhost:9380

# Management 인증 정보
MANAGEMENT_USERNAME=admin
MANAGEMENT_PASSWORD=your_password

# DB 연결 (RevisionDB)
REVISION_DB_CONNECTION_STRING=postgresql://...
```

### 2. 의존성 확인
```bash
cd rag_batch
pip install -r requirements.txt
```

### 3. 테스트 실행
```bash
# 소규모 테스트 (테스트 모드)
python run.py --once --source excel

# 전체 실행
python run.py --once
```

### 4. 로그 확인
```bash
# 최신 로그 확인
tail -f logs/batch_$(date +%Y%m%d).log
```

## ⚠️ 주의사항

### 1. 호환성
- ✅ RAGFlow v21.x와 호환
- ⚠️ RAGFlow v0.17.2 (Plus)와 **비호환** (API 변경)

### 2. RevisionDB 스키마
- 기존 스키마와 호환됨
- `file_id` 필드는 v21에서 `document_id`와 동일한 값 저장

### 3. 문서 ID 관리
- v21에서는 `document_id`만 사용
- `file_id`는 호환성을 위해 동일한 값으로 저장

### 4. 파싱 동작 변경
- 기존: 지식베이스 전체 문서 순차 파싱
- v21: 업로드된 문서만 선택적 파싱
- **장점**: 중복 파싱 방지, 정확한 제어

## 📚 참고 자료

- [마이그레이션 가이드](./MIGRATION_GUIDE_v21.md) - 상세 변경 사항
- [RAGFlow v21 API](../ragflow21v/api/apps/sdk/) - 신규 API 코드
- [기존 Management API](./src/ragflow_client.py) - 수정된 클라이언트

## 🎉 마이그레이션 완료!

RAGFlow v21 API로의 마이그레이션이 완료되었습니다. 주요 변경 사항:

1. ✅ **API 엔드포인트** 전환 완료
2. ✅ **Document 업로드** 간소화 (2단계 → 1단계)
3. ✅ **파싱 API** 개선 (특정 문서 선택)
4. ✅ **document_ids 추적** 로직 구현
5. ✅ **응답 구조** 변경 대응

코드는 이전 버전보다 더 간결하고 효율적이며, RAGFlow v21의 새로운 기능을 완전히 활용합니다.


