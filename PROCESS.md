# RAGFlow Plus 배치 프로그램 - 전체 프로세스

## 📋 목차
1. [전체 흐름](#전체-흐름)
2. [팀 단위 지식베이스 생성](#팀-단위-지식베이스-생성)
3. [문서 업로드 및 파싱 프로세스](#문서-업로드-및-파싱-프로세스)
4. [상세 단계별 설명](#상세-단계별-설명)

---

## 전체 흐름

```
엑셀 파일
    ↓
[1] 시트별 데이터 추출
    ↓
[2] 지식베이스 생성/검색 (팀 권한 설정)
    ↓
[3] 하이퍼링크에서 파일 다운로드
    ↓
[4] 파일 형식 변환 (HWP→PDF, ZIP 압축해제)
    ↓
[5] RAGFlow에 파일 업로드
    ↓
[6] 메타데이터 설정
    ↓
[7] 일괄 파싱 시작 (자동 벡터화)
    ↓
완료: 검색 가능한 지식베이스
```

---

## 팀 단위 지식베이스 생성

### ✅ 지원 여부
**YES** - RAGFlow SDK의 `permission` 파라미터를 통해 팀 공유가 가능합니다.

### 권한 옵션

| 값 | 설명 | 사용 사례 |
|---|---|---|
| `"me"` | 나만 사용 (기본값) | 개인 테스트, 개발 |
| `"team"` | 팀 전체 공유 | 부서/팀 공동 사용 |

### 설정 방법

#### 1. `.env` 파일 설정

```bash
# 지식베이스 권한 설정
DATASET_PERMISSION=team    # 팀 공유로 설정
DATASET_LANGUAGE=Korean    # 한국어 설정
```

#### 2. 코드 동작

```python
# src/batch_processor.py
dataset = self.ragflow_client.get_or_create_dataset(
    name="KTX-EMU 매뉴얼",
    description="엑셀 시트에서 자동 생성",
    permission="team",      # 👈 팀 전체가 접근 가능
    language="Korean"       # 👈 한국어 문서
)
```

#### 3. 결과
- 생성된 지식베이스는 **같은 팀의 모든 구성원**이 접근 가능
- RAGFlow 웹 UI에서 다른 팀원들도 조회/검색 가능

---

## 문서 업로드 및 파싱 프로세스

### ✅ 구현 상태
**완벽하게 구현됨** - 업로드 후 자동으로 파싱이 시작됩니다.

### 프로세스 흐름

```python
# 1단계: 파일 업로드
uploaded = dataset.upload_documents([{
    "display_name": "매뉴얼.pdf",
    "blob": file_content
}])

# 2단계: 메타데이터 설정
doc.update({
    "meta_fields": {
        "년도": "2025",
        "제목": "KTX-EMU 매뉴얼",
        "버전": "v1.0"
    }
})

# 3단계: 파싱 시작 (자동)
for doc in documents:
    doc.parse()  # 👈 벡터화 및 인덱싱 시작
```

### 파싱 과정

```
문서 업로드
    ↓
[파싱 단계]
    ├─ 텍스트 추출 (PDF, HWP 등)
    ├─ 청크 분할 (적절한 크기로)
    ├─ 임베딩 생성 (벡터 변환)
    └─ 인덱스 저장
    ↓
검색 가능 상태
```

---

## 상세 단계별 설명

### 1️⃣ 엑셀 데이터 추출

**파일**: `src/excel_processor.py`

```python
class ExcelProcessor:
    def process_all_sheets(self):
        """
        모든 시트를 순회하며 처리
        - 헤더 자동 감지
        - 하이퍼링크 추출
        - 숨김 행 제외
        - 메타데이터 구성
        """
```

**출력**:
```python
{
    'KTX-EMU 매뉴얼': [
        {
            'hyperlink': 'file:///path/to/manual.pdf',
            'metadata': {
                '년도(1)': '2025',
                '제목(10)': 'KTX-EMU 매뉴얼',
                'REV.(11)': 'v1.0'
            },
            'row_number': 5,
            'sheet_name': 'KTX-EMU 매뉴얼'
        },
        ...
    ]
}
```

---

### 2️⃣ 지식베이스 생성/검색

**파일**: `src/ragflow_client.py`

```python
def get_or_create_dataset(name, description, permission, language):
    """
    지식베이스 가져오기 또는 생성
    
    동작:
    1. 기존 지식베이스 검색
       - 존재하고 접근 가능 → 재사용
       - 존재하지만 접근 불가 → 타임스탬프 추가하여 새로 생성
    2. 없으면 새로 생성
       - permission, language 설정
    """
```

**생성 파라미터**:
- `name`: 지식베이스 이름
- `description`: 설명
- `permission`: "me" 또는 "team"
- `language`: "Korean" (한국어 문서)
- `embedding_model`: "BAAI/bge-large-zh-v1.5" (기본값)
- `chunk_method`: "naive" (기본값)

---

### 3️⃣ 파일 다운로드/복사

**파일**: `src/file_handler.py`

```python
def get_file(hyperlink):
    """
    하이퍼링크에서 파일 가져오기
    
    지원 형식:
    - file:///C:/path/to/file.pdf  → 로컬 파일 복사
    - http://example.com/file.pdf  → HTTP 다운로드
    - \\server\share\file.pdf      → 네트워크 드라이브 복사
    """
```

---

### 4️⃣ 파일 형식 변환

**파일**: `src/file_handler.py`

```python
def process_file(file_path):
    """
    파일 형식 변환
    
    변환 규칙:
    - HWP → PDF 변환 (hwp2pdf)
    - ZIP → 압축 해제 후 개별 파일 처리
    - PDF, TXT → 그대로 사용
    
    반환:
    [
        (처리된파일경로1, 파일타입),
        (처리된파일경로2, 파일타입),
        ...
    ]
    """
```

**변환 예시**:
```
input.zip
    ├─ manual.pdf
    ├─ guide.hwp
    └─ notes.txt
    
↓ 처리 후

output/
    ├─ manual.pdf           (원본)
    ├─ guide_converted.pdf  (HWP → PDF 변환)
    └─ notes.txt            (원본)
```

---

### 5️⃣ RAGFlow 업로드

**파일**: `src/ragflow_client.py`

```python
def upload_document(dataset, file_path, metadata, display_name):
    """
    파일을 지식베이스에 업로드
    
    단계:
    1. 파일 읽기 (바이너리)
    2. RAGFlow API 호출
    3. 업로드 결과 확인
    """
    
    # 파일 내용 읽기
    with open(file_path, 'rb') as f:
        blob = f.read()
    
    # 업로드
    uploaded_docs = dataset.upload_documents([{
        "display_name": display_name,
        "blob": blob
    }])
    
    return uploaded_docs
```

---

### 6️⃣ 메타데이터 설정

**파일**: `src/ragflow_client.py`

```python
def set_document_metadata(doc, metadata):
    """
    업로드된 문서에 메타데이터 추가
    
    메타데이터 예시:
    {
        "년도(1)": "2025",
        "제목(10)": "KTX-EMU 매뉴얼",
        "REV.(11)": "v1.0",
        "원본_파일": "manual.pdf",
        "파일_형식": "pdf",
        "엑셀_행번호": "5",
        "하이퍼링크": "file:///path/to/manual.pdf"
    }
    """
    doc.update({"meta_fields": metadata})
```

**메타데이터 활용**:
- 검색 필터링
- 문서 분류
- 이력 추적
- 버전 관리

---

### 7️⃣ 일괄 파싱 시작

**파일**: `src/ragflow_client.py`

```python
def start_batch_parse(dataset):
    """
    지식베이스의 모든 문서 일괄 파싱
    
    동작:
    1. 지식베이스의 모든 문서 조회
    2. 각 문서에 대해 parse() 호출
    3. RAGFlow 백그라운드에서 처리
       - 텍스트 추출
       - 청크 분할
       - 임베딩 생성
       - 벡터 DB 저장
    """
    
    documents = dataset.list_documents()
    
    for doc in documents:
        doc.parse()  # 비동기 처리 시작
        logger.info(f"문서 파싱 요청: {doc.name}")
    
    # RAGFlow가 백그라운드에서 처리
```

**파싱 상태 확인**:
- RAGFlow 웹 UI → 지식베이스 → 문서 목록
- 상태: `Parsing`, `Completed`, `Failed` 등

---

## 실행 예시

### 로그 출력

```
2025-10-13 13:30:00 - INFO - 배치 프로세스 시작
2025-10-13 13:30:00 - INFO - 엑셀 파일: ./data/20250515_KTX-DATA_EMU.xlsx
2025-10-13 13:30:01 - INFO - 시트 처리 시작: KTX-EMU 매뉴얼
2025-10-13 13:30:01 - INFO - 새 지식베이스 생성: KTX-EMU 매뉴얼 (권한: team)
2025-10-13 13:30:02 - INFO - ✓ 지식베이스 생성 성공: KTX-EMU 매뉴얼
2025-10-13 13:30:02 - INFO - 파일 다운로드: file:///mnt/share/manual.pdf
2025-10-13 13:30:03 - INFO - 파일 업로드 시작: manual.pdf
2025-10-13 13:30:04 - INFO - 메타데이터 설정 완료: manual.pdf
2025-10-13 13:30:04 - INFO - 파일 업로드 완료: manual.pdf
2025-10-13 13:30:05 - INFO - 시트 'KTX-EMU 매뉴얼': 10개 파일 업로드 완료, 일괄 파싱 시작
2025-10-13 13:30:05 - INFO - 문서 파싱 요청: manual.pdf
2025-10-13 13:30:05 - INFO - 문서 파싱 요청: guide.pdf
...
2025-10-13 13:30:10 - INFO - 일괄 파싱 완료: 10/10 성공
2025-10-13 13:30:10 - INFO - 배치 처리 완료
```

---

## 문제 해결

### Q1: 지식베이스 생성 시 "You don't own" 에러

**원인**: 다른 사용자가 같은 이름으로 이미 생성함

**해결**: 자동으로 타임스탬프 추가
```
KTX-EMU 매뉴얼 → KTX-EMU 매뉴얼_20251013_133000
```

### Q2: 파싱이 시작되지 않음

**확인사항**:
1. RAGFlow 서버 상태 확인
2. 웹 UI에서 수동으로 파싱 시작 가능한지 확인
3. `doc.parse()` 메서드 존재 확인

### Q3: 팀원이 지식베이스를 볼 수 없음

**해결**:
1. `.env`에서 `DATASET_PERMISSION=team` 설정 확인
2. 같은 팀/조직에 속해 있는지 확인
3. RAGFlow 권한 설정 확인

---

## 성능 최적화

### 대용량 파일 처리
- 청크 크기: 기본값 사용 (최적화됨)
- 임베딩 모델: `BAAI/bge-large-zh-v1.5` (다국어 지원)

### 병렬 처리
- 현재: 순차 처리
- 개선 가능: `ThreadPoolExecutor`로 병렬 업로드

### 리소스 관리
- 임시 파일 자동 정리
- 메모리 효율적 파일 읽기 (스트리밍)

---

## 참고 자료

- RAGFlow 공식 문서: https://ragflow.io/docs
- RAGFlow SDK: `sdk/python/ragflow_sdk/`
- 프로젝트 구조: `STRUCTURE.md`

---

**마지막 업데이트**: 2025-10-13

