# 구현 노트

## 메타데이터 기능 구현

### 개요
RAGFlow Plus SDK를 사용하여 문서에 메타데이터를 설정하는 기능이 완전히 구현되었습니다.

### 구현 위치
`rag_batch/ragflow_client.py` 파일의 `set_document_metadata()` 메서드

### 구현 방법

#### 1. RAGFlow Plus API
- **엔드포인트**: `/api/v1/document/set_meta`
- **메서드**: POST
- **요청**: `{"doc_id": "...", "meta": "{\"key\": \"value\"}"}`
- **DB 필드**: `document.meta_fields` (JSONField)

#### 2. SDK 메서드
```python
# Document 객체의 update() 메서드 사용
doc.update({"meta_fields": metadata_dict})
```

#### 3. 배치 프로그램 통합
```python
# 1. 파일 업로드
uploaded_docs = dataset.upload_documents([doc_info])

# 2. 메타데이터 설정
doc = uploaded_docs[0]
doc.update({"meta_fields": {
    "구분": "설계",
    "자성보고": "K20",
    "관리번호": "002",
    "원본_파일": "document.pdf",
    "파일_형식": "pdf",
    "엑셀_행번호": "5",
    "하이퍼링크": "file:///path/to/document.pdf"
}})
```

### 메타데이터 구조

#### 자동 추가 필드
1. **엑셀 컬럼 데이터**: 헤더명을 키로 사용
   - 예: "구분", "자성보고", "관리번호", "제목", "WBS(4)", etc.

2. **시스템 필드**: 배치 프로그램에서 자동 추가
   - `원본_파일`: 원본 파일명
   - `파일_형식`: 파일 확장자 (txt, pdf, hwp 등)
   - `엑셀_행번호`: 엑셀의 행 번호
   - `하이퍼링크`: 원본 하이퍼링크 URL

### 사용 예시

#### 엑셀 데이터
| 구분 | 자성보고 | 관리번호 | 제목 | 작성일자 | 담당자 | 파일 |
|------|---------|---------|------|---------|--------|------|
| 설계 | K20 | 002 | 문서A | 2025-03-10 | 홍길동 | [링크] |

#### 생성된 메타데이터
```json
{
  "구분": "설계",
  "자성보고": "K20",
  "관리번호": "002",
  "제목": "문서A",
  "작성일자": "2025-03-10",
  "담당자": "홍길동",
  "원본_파일": "document.pdf",
  "파일_형식": "pdf",
  "엑셀_행번호": "5",
  "하이퍼링크": "file:///path/to/document.pdf"
}
```

### 확인 방법

#### 1. RAGFlow 웹 UI
```
지식베이스 → 문서 목록 → 문서 선택 → "메타데이터" 탭
```

#### 2. 배치 로그
```
2025-05-15 10:00:09 - INFO - 메타데이터 - document.pdf:
2025-05-15 10:00:09 - INFO -   구분: 설계
2025-05-15 10:00:09 - INFO -   자성보고: K20
2025-05-15 10:00:09 - INFO -   관리번호: 002
...
2025-05-15 10:00:10 - INFO - 메타데이터 설정 완료: document.pdf
```

#### 3. API 직접 호출
```python
from ragflow_sdk import RAGFlow

rag = RAGFlow(api_key="...", base_url="...")
dataset = rag.list_datasets(name="KTX-EMU 유지보수 매뉴얼")[0]
docs = dataset.list_documents()

for doc in docs:
    print(f"문서: {doc.name}")
    # doc 객체에 meta_fields 속성이 있는지 확인
    if hasattr(doc, 'meta_fields'):
        print(f"메타데이터: {doc.meta_fields}")
```

### 활용 방법

#### 1. 검색 필터링
RAGFlow의 검색 기능에서 메타데이터를 필터로 사용:
- "WBS(4) = K20-5인 문서만 검색"
- "작성일자 >= 2025-03-01인 문서만 검색"
- "담당자 = 홍길동인 문서만 검색"

#### 2. 문서 관리
- 작성자별 문서 분류
- 날짜별 문서 정렬
- 부서/프로젝트별 문서 그룹핑

#### 3. 추적 및 감사
- 원본 파일 위치 추적
- 업로드 시점 (엑셀 행번호로 추적)
- 파일 변환 이력

### 제한사항

1. **메타데이터 크기**
   - JSON 필드 크기 제한에 주의
   - 너무 많은 필드는 성능에 영향

2. **데이터 타입**
   - 모든 값은 문자열로 저장됨
   - 숫자, 날짜도 문자열로 변환됨

3. **특수 문자**
   - JSON에서 지원하는 문자만 사용
   - 이스케이프 처리 필요

### 오류 처리

#### 일반적인 오류
```python
try:
    doc.update({"meta_fields": metadata})
except Exception as e:
    logger.error(f"메타데이터 설정 실패: {e}")
    # 업로드는 성공, 메타데이터만 실패
    # 나중에 수동으로 설정 가능
```

#### 복구 방법
1. RAGFlow 웹 UI에서 수동 설정
2. API를 통해 재시도
3. 배치 프로그램 재실행 (중복 업로드 방지 필요)

### 테스트

#### 단위 테스트
```python
def test_metadata_setting():
    # 1. 문서 업로드
    docs = dataset.upload_documents([{"display_name": "test.txt", "blob": b"test"}])
    doc = docs[0]
    
    # 2. 메타데이터 설정
    metadata = {"key1": "value1", "key2": "value2"}
    doc.update({"meta_fields": metadata})
    
    # 3. 검증
    doc_list = dataset.list_documents(name="test.txt")
    assert doc_list[0].meta_fields == metadata
```

#### 통합 테스트
```bash
# 샘플 엑셀 파일로 전체 프로세스 테스트
cd rag_batch
python test_excel_read.py
python main.py --once --excel "../sample_excel/20250515_KTX-DATA_EMU.xlsx"

# 로그에서 메타데이터 설정 확인
grep "메타데이터 설정 완료" logs/batch_*.log
```

### 성능 고려사항

1. **배치 처리**
   - 현재는 파일당 1번 API 호출
   - 대량 처리 시 병렬 처리 고려

2. **재시도 로직**
   - 메타데이터 설정 실패 시 재시도
   - 백오프 전략 적용

3. **캐싱**
   - Document 객체 재사용
   - API 호출 최소화

### 참고 자료

- RAGFlow API 문서: `docs/api/README.md`
- RAGFlow SDK: `sdk/python/ragflow_sdk/modules/document.py`
- 배치 프로그램: `rag_batch/ragflow_client.py`
- 데이터베이스 모델: `api/db/db_models.py` (line 763)

