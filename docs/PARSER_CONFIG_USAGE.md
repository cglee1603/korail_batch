# Parser 설정 사용 가이드

## 📖 개요

이 문서는 RAGFlow Batch에서 GUI와 동일한 Parser 설정을 사용하는 방법을 설명합니다.

## 🎯 설정 목적

동일한 문서를 Batch와 GUI에서 처리할 때 **동일한 결과**를 얻기 위해 Parser 설정을 일치시킵니다.

## ⚙️ 설정 항목

### 1. 청크 분할 방법 (CHUNK_METHOD)

문서를 어떤 방식으로 청크(조각)로 나눌지 결정합니다.

```bash
# 기본값: naive (일반 텍스트 분할)
CHUNK_METHOD=naive
```

**사용 가능한 값:**
- `naive`: 일반 텍스트 분할 (기본값, 대부분의 경우 권장)
- `qa`: Q&A 형식 문서
- `manual`: 수동 분할
- `paper`: 학술 논문
- `book`: 책
- `laws`: 법률 문서
- `presentation`: 프레젠테이션
- `knowledge_graph`: 지식 그래프

### 2. 청크당 토큰 수 (CHUNK_TOKEN_NUM)

각 청크의 크기를 토큰 단위로 지정합니다.

```bash
# 기본값: 128 (권장: 128-512)
CHUNK_TOKEN_NUM=128
```

**설정 가이드:**
- **128**: 정밀한 검색, 빠른 처리 (기본값)
- **256**: 균형잡힌 설정
- **512**: 더 많은 문맥, 검색 정확도는 낮을 수 있음
- **1024+**: 긴 문맥이 필요한 특수한 경우

### 3. 구분자 (DELIMITER)

텍스트를 나눌 때 사용할 구분 문자들입니다.

```bash
# 기본값: 줄바꿈과 문장 종결 기호
DELIMITER=\\n!?;。；！？
```

**구분자 설명:**
- `\n`: 줄바꿈
- `!`, `?`: 영어 문장 종결
- `;`: 세미콜론
- `。`, `；`, `！`, `？`: 한중일 문장 종결

### 4. 레이아웃 인식 방법 (LAYOUT_RECOGNIZE)

문서의 레이아웃을 인식하는 방법을 선택합니다.

```bash
# 기본값: MinerU (권장)
LAYOUT_RECOGNIZE=MinerU
```

**사용 가능한 값:**
- `MinerU`: 최신 모델, 한국어 지원 우수 (권장)
- `DeepDOC`: 구버전 모델

### 5. Excel HTML 변환 (HTML4EXCEL)

Excel 파일을 HTML로 변환할지 여부입니다.

```bash
# 기본값: false
HTML4EXCEL=false
```

### 6. Raptor 설정 (USE_RAPTOR)

계층적 요약을 사용할지 여부입니다.

```bash
# 기본값: false (대부분의 경우 권장)
USE_RAPTOR=false
```

⚠️  **주의:** Raptor는 처리 시간이 매우 길고 LLM 호출이 많이 발생합니다.
자세한 내용은 [RAPTOR_FIX_GUIDE.md](./RAPTOR_FIX_GUIDE.md)를 참조하세요.

## 📝 설정 예시

### 예시 1: 기본 설정 (권장)

```bash
# .env 파일
CHUNK_METHOD=naive
CHUNK_TOKEN_NUM=128
DELIMITER=\\n!?;。；！？
LAYOUT_RECOGNIZE=MinerU
HTML4EXCEL=false
USE_RAPTOR=false
```

### 예시 2: 법률 문서용

```bash
CHUNK_METHOD=laws
CHUNK_TOKEN_NUM=256
DELIMITER=\\n!?;。；！？
LAYOUT_RECOGNIZE=MinerU
HTML4EXCEL=false
USE_RAPTOR=false
```

### 예시 3: 학술 논문용

```bash
CHUNK_METHOD=paper
CHUNK_TOKEN_NUM=512
DELIMITER=\\n!?;。；！？
LAYOUT_RECOGNIZE=MinerU
HTML4EXCEL=false
USE_RAPTOR=false
```

### 예시 4: Excel 문서 처리

```bash
CHUNK_METHOD=naive
CHUNK_TOKEN_NUM=128
DELIMITER=\\n!?;。；！？
LAYOUT_RECOGNIZE=MinerU
HTML4EXCEL=true  # Excel을 HTML로 변환
USE_RAPTOR=false
```

## 🔧 고급 설정

### JSON 방식으로 직접 설정

환경변수로 전체 설정을 JSON 형태로 전달할 수 있습니다:

```bash
PARSER_CONFIG='{"chunk_token_num": 256, "delimiter": "\\n", "layout_recognize": "MinerU", "raptor": {"use_raptor": false}}'
```

⚠️  **주의:** `PARSER_CONFIG`를 사용하면 개별 환경변수보다 우선 적용됩니다.

## 📊 GUI와 설정 일치시키기

### 1. GUI에서 현재 설정 확인

1. RAGFlow 웹 인터페이스 접속
2. 지식베이스 생성/수정 페이지로 이동
3. Parser 설정 섹션에서 현재 사용 중인 값 확인

### 2. Batch 설정 업데이트

GUI에서 확인한 값을 `.env` 파일에 동일하게 설정:

```bash
# GUI 설정
# - Chunk Method: naive
# - Chunk Size: 256 tokens
# - Layout: MinerU
# - Raptor: Off

# Batch .env 파일
CHUNK_METHOD=naive
CHUNK_TOKEN_NUM=256
LAYOUT_RECOGNIZE=MinerU
USE_RAPTOR=false
```

### 3. 테스트

```bash
# 동일한 파일로 테스트
python run.py
```

## 🐛 문제 해결

### KeyError: 'prompt' 오류

Raptor를 활성화했지만 필수 설정이 누락된 경우입니다.

**해결 방법:**
1. `USE_RAPTOR=false`로 설정 (권장)
2. 또는 [RAPTOR_FIX_GUIDE.md](./RAPTOR_FIX_GUIDE.md) 참조

### 파싱 결과가 GUI와 다름

**확인 사항:**
1. 모든 Parser 설정이 GUI와 동일한지 확인
2. 임베딩 모델이 동일한지 확인 (시스템 기본값 사용)
3. 파일 버전이 동일한지 확인

## 📚 추가 자료

- [PARSER_LANGUAGE_ANALYSIS.md](./PARSER_LANGUAGE_ANALYSIS.md) - 파서 언어 분석
- [RAPTOR_FIX_GUIDE.md](./RAPTOR_FIX_GUIDE.md) - Raptor 오류 해결
- [README.md](../README.md) - 전체 가이드
- [DATABASE_INTEGRATION.md](./DATABASE_INTEGRATION.md) - DB 연동 가이드

