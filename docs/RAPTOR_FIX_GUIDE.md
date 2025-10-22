# Raptor KeyError 해결 가이드

## 🐛 문제 상황

API를 통해 문서를 업로드하고 파싱할 때 다음과 같은 오류 발생:

```python
KeyError: 'prompt'
File "/ragflow/rag/svr/task_executor.py", line 413, in run_raptor
    row["parser_config"]["raptor"]["prompt"],
```

### 에러 로그 분석
```json
"parser_config": {
    "chunk_token_num": 128,
    "delimiter": "\\\\n!?;。；！？",
    "pages": [[1, 1000000]],
    "layout_recognize": "MinerU",
    "html4excel": false,
    "raptor": {"use_raptor": true}  // ❌ prompt, max_token 등이 없음!
}
```

## 🔍 원인

Raptor를 활성화(`use_raptor: true`)했지만 **필수 설정값들이 누락**되었습니다:

### Raptor 필수 설정 (task_executor.py:409-418)
```python
raptor = Raptor(
    row["parser_config"]["raptor"].get("max_cluster", 64),  # 선택 (기본값 있음)
    chat_mdl,
    embd_mdl,
    row["parser_config"]["raptor"]["prompt"],      # ❌ 필수 - 누락 시 KeyError
    row["parser_config"]["raptor"]["max_token"],   # ❌ 필수 - 누락 시 KeyError
    row["parser_config"]["raptor"]["threshold"]    # ❌ 필수 - 누락 시 KeyError
)
chunks = await raptor(chunks, 
    row["parser_config"]["raptor"]["random_seed"],  # ❌ 필수 - 누락 시 KeyError
    callback)
```

## ✅ 해결 방법

### 방법 1: Raptor 비활성화 (권장)

대부분의 경우 Raptor는 필요하지 않습니다. `.env` 파일에서:

```bash
# Raptor 비활성화 (기본값)
USE_RAPTOR=false
```

**Raptor를 사용하지 말아야 하는 이유:**
- 처리 시간이 매우 길어짐 (수십 배)
- LLM 호출이 대량으로 발생 (비용 증가)
- 일반적인 문서 검색에는 과도한 처리
- 소규모 문서에는 효과가 제한적

### 방법 2: Raptor 완전한 설정 (고급 사용자)

정말로 Raptor가 필요한 경우 `.env` 파일에 다음 추가:

```bash
# Raptor 활성화
USE_RAPTOR=true

# 필수 설정들
RAPTOR_PROMPT=Please summarize the following paragraphs. Be careful with the numbers, do not make things up. Paragraphs as following:\n{cluster_content}\nThe above is the content you need to summarize.
RAPTOR_MAX_TOKEN=256
RAPTOR_THRESHOLD=0.1
RAPTOR_RANDOM_SEED=0
RAPTOR_MAX_CLUSTER=64
```

## 📋 GUI vs Batch 차이점

### GUI에서 Raptor 활성화 시
- 웹 인터페이스가 자동으로 기본값 설정
- `max_token`: 256
- `threshold`: 0.1  
- `random_seed`: 0 또는 랜덤 생성
- `prompt`: 다국어 기본 프롬프트

### Batch에서 (수정 전)
- `use_raptor: true`만 전달
- 나머지 필수 값들이 없어서 KeyError 발생

### Batch에서 (수정 후)
- `config.py`에서 모든 필수 값을 GUI와 동일하게 설정
- `.env`에서 커스터마이징 가능

## 🔧 수정된 파일

### 1. `rag_batch/src/config.py`
```python
PARSER_CONFIG = {
    # ... 기타 설정 ...
    
    "raptor": {
        "use_raptor": os.getenv("USE_RAPTOR", "false").lower() == "true",
        "prompt": os.getenv("RAPTOR_PROMPT", 
            "Please summarize the following paragraphs..."),
        "max_token": int(os.getenv("RAPTOR_MAX_TOKEN", "256")),
        "threshold": float(os.getenv("RAPTOR_THRESHOLD", "0.1")),
        "random_seed": int(os.getenv("RAPTOR_RANDOM_SEED", "0")),
        "max_cluster": int(os.getenv("RAPTOR_MAX_CLUSTER", "64"))
    }
}
```

### 2. `rag_batch/env.example`
모든 Raptor 설정 예시 추가

## ✨ Raptor란?

**RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval)**

- 문서를 계층적으로 요약하여 트리 구조 생성
- 각 계층에서 클러스터링 수행
- LLM을 사용하여 각 클러스터 요약
- 검색 시 여러 추상화 레벨에서 정보 검색

**장점:**
- 긴 문서에서 고수준 개념 검색에 유리
- 문서 전체의 맥락 파악 가능

**단점:**
- 처리 시간이 매우 길어짐
- LLM 호출 비용 증가
- 짧은 문서나 단순 검색에는 과도함

## 📝 테스트 방법

### 1. Raptor 비활성화 테스트
```bash
# .env 파일
USE_RAPTOR=false

# 실행
python run.py
```

✅ **예상 결과:** 문서가 정상적으로 파싱되고 KeyError 없음

### 2. Raptor 활성화 테스트 (선택)
```bash
# .env 파일
USE_RAPTOR=true
RAPTOR_MAX_TOKEN=256
RAPTOR_THRESHOLD=0.1
RAPTOR_RANDOM_SEED=0

# 실행 (⚠️  시간이 오래 걸림)
python run.py
```

✅ **예상 결과:** 
- 문서 파싱 완료 후 추가로 Raptor 처리 진행
- 로그에 "task_type": "raptor" 확인
- 처리 시간이 수십 배 증가

## 🎯 권장 사항

1. **기본적으로 `USE_RAPTOR=false` 사용** (99%의 경우 충분)
2. 정말 필요한 경우에만 활성화:
   - 수백 페이지 이상의 긴 문서
   - 고수준 개념 검색이 중요한 경우
   - LLM 호출 비용과 시간을 감당할 수 있는 경우
3. 소규모 테스트로 효과 확인 후 전체 적용

## 🔗 관련 자료

- [RAPTOR 논문](https://huggingface.co/papers/2401.18059)
- `rag/raptor.py` - Raptor 구현 코드
- `rag/svr/task_executor.py:409-418` - Raptor 호출 코드
- `web/src/components/parse-configuration/index.tsx` - GUI Raptor 설정

