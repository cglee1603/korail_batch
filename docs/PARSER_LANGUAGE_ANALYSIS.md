# Batch vs GUI 파싱 결과 차이 원인 분석

## 📋 문제 상황
동일한 문서를 배치(rag_batch)로 처리하는 것과 GUI에서 처리하는 것의 결과가 다름

## 🔍 원인 분석

### 1. **MinerU 언어 설정 하드코딩 발견**

#### 위치: `management/server/services/knowledgebases/document_parser.py`

**PDF 파싱 (412번째 줄):**
```python
# 언어 및 파싱 방법 설정 (기본값 사용)
lang = "korean"  # 한국어 기본값, 필요에 따라 변경
chunk_method = "auto"  # 자동 감지, 필요에 따라 "txt" 또는 "ocr"로 변경 가능
```

**이미지 파싱 (505번째 줄):**
```python
# 언어 설정 (기본값)
lang = "korean"  # 필요에 따라 변경
```

### 2. **parser_config에 언어 설정 없음**

현재 RAGFlow의 `parser_config`에서 지원하는 설정:
- `chunk_token_num` - 청크 토큰 수
- `delimiter` - 구분자
- `raptor` - Raptor 설정
- `graphrag` - Graph RAG 설정
- `layout_recognize` - 레이아웃 인식 방법
- `task_page_size` - 작업 페이지 크기
- `pages` - 처리할 페이지 범위
- `html4excel` - Excel HTML 처리
- `auto_keywords` - 자동 키워드 추출
- `auto_questions` - 자동 질문 생성
- `tag_kb_ids` - 태그 KB ID
- `topn_tags` - 상위 N개 태그
- `filename_embd_weight` - 파일명 임베딩 가중치

**❌ 언어(language) 설정이 없음!**

### 3. **Batch와 GUI의 처리 흐름**

#### Batch 처리 (`rag_batch/src/ragflow_client.py`):
1. HTTP API로 파일 업로드
2. HTTP API로 파싱 요청 (`/api/v1/datasets/{dataset_id}/chunks`)
3. 서버의 `document_parser.py`에서 파싱 수행 → **언어 하드코딩("korean")** 적용

#### GUI 처리:
1. 웹 인터페이스에서 파일 업로드
2. 서버의 `document_parser.py`에서 파싱 수행 → **언어 하드코딩("korean")** 적용

### 4. **실제 차이 원인 추정**

두 경로 모두 동일한 `document_parser.py`를 사용하므로 언어 설정은 동일합니다.
그러나 다음과 같은 차이가 있을 수 있습니다:

1. **Parser Config 차이**: 
   - GUI에서는 지식베이스 생성 시 설정한 `parser_config`가 적용됨
   - Batch에서는 `parser_config`를 전달하지 않음 (기본값 사용)
   
2. **Embedding Model 차이**:
   - GUI: 지식베이스 생성 시 선택한 임베딩 모델 사용
   - Batch: `tenant.embd_id`(시스템 기본값) 사용
   
3. **청크 처리 방법 차이**:
   - GUI: 지식베이스의 `chunk_method` 설정 적용
   - Batch: 기본 `chunk_method` 사용

## 🔧 MinerU 한국어 지원 여부

### MinerU 지원 언어

MinerU(Magic-PDF)는 다음 언어를 지원합니다:
- `chinese` - 중국어 (간체/번체)
- `english` - 영어
- `korean` - **한국어** ✅
- `japanese` - 일본어
- 기타 다국어 OCR 지원

### OCR 모델 정보

`docker/magic-pdf.json` 설정 파일에서 확인:
- **Layout Model**: `doclayout_yolo`
- **Table Model**: `rapid_table` + `slanet_plus`
- **Formula Model**: `yolo_v8_mfd` + `unimernet_small`

이 모델들은 다국어를 지원하지만, **OCR 품질은 언어와 폰트에 따라 달라질 수 있습니다.**

## ✅ 해결 방안

### 1. **Batch에서 parser_config 전달 추가**

`rag_batch/src/ragflow_client.py`의 `get_or_create_dataset` 함수 수정:
```python
def get_or_create_dataset(
    self, 
    name: str, 
    description: str = "",
    permission: str = "me",
    embedding_model: str = None,
    chunk_method: str = "naive",  # 추가
    parser_config: Dict = None     # 추가
) -> Optional[Dict]:
```

### 2. **언어 설정을 parser_config에 추가 (향후 개선)**

RAGFlow 코어 수정이 필요:
1. `api/utils/api_utils.py`의 `valid_parser_config`에 `language` 추가
2. `document_parser.py`에서 하드코딩 대신 `parser_config['language']` 사용

```python
# document_parser.py 수정 예시
lang = doc_info.get("parser_config", {}).get("language", "korean")
```

### 3. **임시 해결책: Batch와 GUI 설정 일치시키기**

현재로서는 GUI에서 사용하는 지식베이스 설정과 동일한 설정을 Batch에서도 사용하도록 수정:

1. GUI에서 사용하는 `chunk_method` 확인
2. `rag_batch/src/config.py`에 해당 설정 추가
3. 파일 업로드 시 동일한 설정 전달

## 📝 결론

1. **언어 설정은 두 경로 모두 "korean"으로 하드코딩되어 있어 동일함**
2. **차이의 주요 원인은 parser_config 설정의 차이**
3. **MinerU는 한국어를 지원하지만, OCR 품질은 문서 품질에 따라 달라질 수 있음**
4. **해결을 위해서는 Batch에서도 GUI와 동일한 parser_config를 전달해야 함**

## 🔗 관련 파일

- `management/server/services/knowledgebases/document_parser.py` - 실제 파싱 로직
- `api/utils/api_utils.py` - parser_config 검증 및 기본값 설정
- `api/db/db_models.py` - parser_config 데이터 모델
- `rag_batch/src/ragflow_client.py` - Batch 처리 클라이언트
- `docker/magic-pdf.json` - MinerU 설정 파일

