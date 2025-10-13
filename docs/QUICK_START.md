# 빠른 시작 가이드

## 1단계: 초기 설정

```powershell
cd rag_batch
python setup.py
```

## 2단계: 의존성 설치

```powershell
pip install -r requirements.txt
```

## 3단계: 환경 설정

`.env` 파일을 편집하여 RAGFlow 설정을 입력합니다.

```env
RAGFLOW_API_KEY=your_api_key_here
RAGFLOW_BASE_URL=http://localhost:9380
EXCEL_FILE_PATH=./data/20250515_KTX-DATA_EMU.xlsx
```

### RAGFlow API 키 발급 방법

1. RAGFlow 웹 인터페이스에 로그인
2. 설정 → API 메뉴로 이동
3. "API KEY 생성" 버튼 클릭
4. 생성된 키를 복사하여 `.env` 파일에 입력

## 4단계: 샘플 파일 복사 (선택사항)

```powershell
python copy_sample.py
```

이 명령은 `../sample_excel/20250515_KTX-DATA_EMU.xlsx` 파일을 `data/` 폴더로 복사합니다.

## 5단계: 엑셀 파일 테스트

배치 실행 전에 엑셀 파일이 올바르게 읽히는지 테스트합니다.

```powershell
python test_excel_read.py
```

이 명령은 엑셀 파일을 읽어 다음 정보를 출력합니다:
- 시트 목록
- 각 시트의 헤더
- 하이퍼링크가 포함된 항목
- 메타데이터

## 6단계: 배치 실행

### 1회 실행 (테스트용)

```powershell
python main.py --once
```

### 특정 엑셀 파일 지정

```powershell
python main.py --once --excel "C:\path\to\your\file.xlsx"
```

### 스케줄 실행

```powershell
# .env 파일의 BATCH_SCHEDULE 설정 사용
python main.py

# 또는 명령행에서 스케줄 지정
python main.py --schedule "10:00"  # 매일 10시
python main.py --schedule "300"     # 300초(5분)마다
```

## 로그 확인

처리 결과는 `logs/` 디렉토리에 날짜별로 저장됩니다.

```powershell
# 오늘 로그 확인
Get-Content logs\batch_$(Get-Date -Format 'yyyyMMdd').log
```

## 문제 해결

### API 키 오류

```
ValueError: RAGFlow API 키가 설정되지 않았습니다.
```

**해결**: `.env` 파일에서 `RAGFLOW_API_KEY` 값을 확인하세요.

### 엑셀 파일 없음

```
엑셀 파일을 찾을 수 없습니다: ./data/input.xlsx
```

**해결**: 
1. `.env` 파일의 `EXCEL_FILE_PATH` 경로를 확인
2. 또는 `--excel` 옵션으로 파일 경로 지정

### 연결 오류

```
Connection refused
```

**해결**: 
1. RAGFlow 서버가 실행 중인지 확인
2. `.env` 파일의 `RAGFLOW_BASE_URL` 확인

## 다음 단계

1. 실제 사용할 엑셀 파일을 `data/` 폴더에 복사
2. `.env` 파일의 `EXCEL_FILE_PATH` 수정
3. 스케줄 설정 (`.env`의 `BATCH_SCHEDULE`)
4. 배치 프로그램을 백그라운드 서비스로 등록 (선택사항)

## 추가 정보

상세한 사용법은 [README.md](README.md)를 참조하세요.

