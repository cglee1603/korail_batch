# 문제 해결 가이드

## 설치 및 설정 문제

### 1. 의존성 설치 실패

**증상:**
```
ERROR: Could not find a version that satisfies the requirement ragflow-sdk>=0.8.0
```

**원인:** 
- Python 버전 호환성 문제
- 네트워크 연결 문제
- PyPI 서버 접근 문제

**해결:**
1. Python 버전 확인 (3.8 이상 필요)
   ```powershell
   python --version
   ```

2. pip 업그레이드
   ```powershell
   python -m pip install --upgrade pip
   ```

3. 개별 패키지 설치 시도
   ```powershell
   pip install openpyxl
   pip install ragflow-sdk
   pip install requests
   ```

4. 프록시 설정이 필요한 경우
   ```powershell
   pip install -r requirements.txt --proxy http://proxy.example.com:8080
   ```

---

### 2. 환경 변수 인코딩 문제

**증상:**
```
UnicodeEncodeError: 'cp949' codec can't encode character
```

**해결:**
1. PowerShell 코드 페이지 변경
   ```powershell
   chcp 65001
   ```

2. 환경 변수에 UTF-8 설정
   ```powershell
   $env:PYTHONIOENCODING="utf-8"
   ```

3. 또는 스크립트 실행 시 명시적 지정
   ```powershell
   $env:PYTHONIOENCODING="utf-8"; python main.py --once
   ```

---

## RAGFlow 연결 문제

### 3. API 키 오류

**증상:**
```
ValueError: RAGFlow API 키가 설정되지 않았습니다.
```

**해결:**
1. `.env` 파일 존재 확인
   ```powershell
   Test-Path .env
   ```

2. `.env` 파일 내용 확인
   ```powershell
   Get-Content .env
   ```

3. API 키 형식 확인
   - 올바른 형식: `ragflow-XXXXXXXXXXXXXXXXXXXX`
   - 공백이나 따옴표 제거

4. RAGFlow 웹 UI에서 새 키 발급

---

### 4. 연결 거부

**증상:**
```
ConnectionRefusedError: [WinError 10061] 대상 컴퓨터에서 연결을 거부했으므로 연결하지 못했습니다
```

**원인:**
- RAGFlow 서버가 실행되지 않음
- 잘못된 URL 또는 포트

**해결:**
1. RAGFlow 서버 상태 확인
   ```powershell
   # RAGFlow 프로젝트 루트에서
   python .\start_server.py
   ```

2. URL 및 포트 확인
   - 기본값: `http://localhost:9380`
   - `.env` 파일의 `RAGFLOW_BASE_URL` 확인

3. 방화벽 확인
   ```powershell
   Test-NetConnection -ComputerName localhost -Port 9380
   ```

---

### 5. 인증 오류

**증상:**
```
Authentication error: API key is invalid
```

**해결:**
1. API 키 재발급
   - RAGFlow 웹 UI → 설정 → API
   - 기존 키 삭제 후 새로 생성

2. `.env` 파일 업데이트

3. 서버 재시작 후 재시도

---

## 엑셀 파일 처리 문제

### 6. 엑셀 파일을 찾을 수 없음

**증상:**
```
엑셀 파일을 찾을 수 없습니다: ./data/input.xlsx
```

**해결:**
1. 파일 경로 확인
   ```powershell
   Test-Path "data\input.xlsx"
   ```

2. 절대 경로 사용
   ```powershell
   python main.py --once --excel "C:\full\path\to\file.xlsx"
   ```

3. `.env` 파일 수정
   ```env
   EXCEL_FILE_PATH=C:\full\path\to\file.xlsx
   ```

---

### 7. 엑셀 파일 읽기 오류

**증상:**
```
BadZipFile: File is not a zip file
```

**원인:**
- 손상된 엑셀 파일
- 잘못된 파일 형식

**해결:**
1. 파일 형식 확인 (.xlsx 여야 함, .xls는 지원 안 됨)

2. Excel에서 파일 다시 저장
   - 파일 → 다른 이름으로 저장
   - 형식: Excel 통합 문서 (*.xlsx)

3. 파일 복구 시도
   - Excel에서 열기
   - 파일 → 열기 → 찾아보기
   - 파일 선택 → 열기 옆 화살표 → "열기 및 복구"

---

### 8. 하이퍼링크 추출 실패

**증상:**
```
시트 'Sheet1'에 처리할 항목이 없습니다.
```

**원인:**
- 하이퍼링크가 없는 시트
- 잘못된 하이퍼링크 형식

**해결:**
1. 테스트 스크립트 실행
   ```powershell
   python test_excel_read.py
   ```

2. 하이퍼링크 확인
   - Excel에서 셀 우클릭 → "하이퍼링크 편집"
   - 링크 주소 확인

3. 하이퍼링크 형식 예시
   - 파일: `file:///C:/path/to/file.pdf`
   - URL: `http://example.com/document.pdf`
   - 네트워크 경로: `\\server\share\file.pdf`

---

### 9. 숨김 행 처리 문제

**증상:**
처리되지 말아야 할 행이 처리됨

**원인:**
- 행이 실제로 숨겨지지 않음
- 필터만 적용된 상태

**해결:**
1. Excel에서 숨김 확인
   - 행 번호가 연속적이지 않으면 숨김 상태

2. 숨김 행 설정
   - 행 선택 → 우클릭 → "숨기기"

3. 필터가 아닌 숨김 사용

---

## 파일 처리 문제

### 10. 파일 다운로드 실패

**증상:**
```
ERROR - 파일 다운로드 실패 (http://example.com/file.pdf): 404 Not Found
```

**해결:**
1. URL 확인
   - 브라우저에서 URL 열어보기
   - 경로 오타 확인

2. 네트워크 연결 확인

3. 로컬 파일 경로 사용 시
   - 절대 경로 사용
   - 경로 구분자: `/` 또는 `\\`

---

### 11. HWP 파일 변환 문제

#### 11-1. LibreOffice를 찾을 수 없음

**증상:**
```
ERROR - LibreOffice를 찾을 수 없습니다. 설치 필요
```

**해결:**

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y libreoffice libreoffice-writer

# CentOS/RHEL
sudo yum install -y libreoffice libreoffice-writer

# 설치 확인
soffice --version
```

**Windows:**
1. LibreOffice 다운로드: https://www.libreoffice.org/download/
2. 설치 (기본 옵션)
3. 설치 확인
   ```powershell
   & "C:\Program Files\LibreOffice\program\soffice.exe" --version
   ```

---

#### 11-2. HWP 변환 타임아웃

**증상:**
```
ERROR - HWP 변환 타임아웃 (5분 초과)
```

**원인:**
- 파일 크기가 매우 큼
- 복잡한 레이아웃
- 시스템 리소스 부족

**해결:**
1. `src/file_handler.py` 수정 - 타임아웃 증가
   ```python
   # 300초 → 600초 (10분)
   timeout=600
   ```

2. 파일 크기 확인
   ```bash
   ls -lh document.hwp
   ```

3. 수동 변환 테스트
   ```bash
   soffice --headless --convert-to pdf document.hwp
   ```

---

#### 11-3. 한글 폰트 깨짐

**증상:**
변환된 PDF에서 한글이 깨지거나 □로 표시됨

**해결:**
```bash
# Ubuntu/Debian
sudo apt-get install -y fonts-nanum fonts-nanum-coding fonts-nanum-extra

# 폰트 캐시 갱신
fc-cache -f -v

# 설치 확인
fc-list | grep -i nanum
```

---

#### 11-4. HWP 변환 실패 - 원본 업로드

**증상:**
```
WARNING - HWP->PDF 변환 실패: document.hwp
WARNING - 원본 HWP 파일을 그대로 사용: document.hwp
```

**동작:**
변환 실패 시 원본 HWP 파일을 그대로 업로드 시도

**문제:**
RAGFlow가 HWP를 지원하지 않으면 파싱 실패

**해결:**
1. 수동 변환 후 재업로드
   ```bash
   soffice --headless --convert-to pdf document.hwp
   ```

2. LibreOffice 재설치

3. 다른 변환 도구 사용
   - unoconv: `pip install unoconv`
   - hwp5tools: `pip install hwp5` (Linux만)

**상세 가이드:** [HWP_CONVERSION.md](HWP_CONVERSION.md)

---

### 12. ZIP 파일 압축 해제 오류

**증상:**
```
ERROR - ZIP 압축 해제 실패: Bad CRC-32
```

**원인:**
- 손상된 ZIP 파일
- 암호화된 ZIP 파일

**해결:**
1. ZIP 파일 무결성 검사

2. 암호 보호 해제

3. 다시 압축

---

## 업로드 및 파싱 문제

### 13. 파일 업로드 실패

**증상:**
```
ERROR - 파일 업로드 실패 (document.pdf): 500 Internal Server Error
```

**해결:**
1. RAGFlow 서버 로그 확인

2. 파일 크기 확인
   - 너무 큰 파일은 분할

3. 파일 형식 확인
   - RAGFlow가 지원하는 형식인지 확인

4. 디스크 공간 확인

---

### 14. 파싱이 시작되지 않음

**증상:**
문서가 업로드되었지만 파싱되지 않음

**해결:**
1. RAGFlow 웹 UI에서 수동 파싱 시도

2. 파서 설정 확인

3. `ragflow_client.py`의 `start_batch_parse` 메서드 디버깅

---

### 15. 메타데이터가 보이지 않음

**증상:**
파일은 업로드되었지만 메타데이터가 보이지 않음

**해결:**
1. RAGFlow 웹 UI에서 확인
   - 지식베이스 → 문서 선택 → "메타데이터" 탭

2. 로그에서 메타데이터 설정 확인
   ```
   INFO - 메타데이터 설정 완료: document.pdf
   ```

3. API 오류 확인
   - 로그에서 "메타데이터 설정 실패" 메시지 검색

4. RAGFlow 서버 버전 확인
   - 메타데이터 기능은 최신 버전에서 지원됨

---

## 성능 문제

### 16. 처리 속도가 느림

**해결:**
1. 동시 업로드 수 증가
   - `batch_processor.py`에서 멀티스레딩 추가

2. 파일 크기 확인
   - 큰 파일은 사전 압축

3. 네트워크 속도 확인

---

### 17. 메모리 부족

**증상:**
```
MemoryError: Unable to allocate array
```

**해결:**
1. 대용량 파일 처리 시 스트리밍 사용

2. 임시 파일 정기적 정리
   ```python
   file_handler.cleanup_temp()
   ```

3. Python 메모리 제한 증가

---

## 로그 문제

### 18. 로그 파일이 생성되지 않음

**해결:**
1. `logs/` 디렉토리 존재 확인
   ```powershell
   mkdir logs
   ```

2. 쓰기 권한 확인

3. `logger.py` 디버깅

---

### 19. 로그 인코딩 문제

**증상:**
로그에 한글이 깨짐

**해결:**
`logger.py`의 파일 핸들러 수정:
```python
file_handler = logging.FileHandler(log_file, encoding='utf-8')
```

---

## 기타 문제

### 20. 스케줄이 실행되지 않음

**증상:**
스케줄 설정했지만 실행되지 않음

**해결:**
1. 스케줄 형식 확인
   - 시간: "HH:MM" (예: "10:00")
   - 초: 숫자만 (예: "300")

2. 프로그램이 계속 실행 중인지 확인

3. 로그 확인

---

### 21. 프로그램이 예기치 않게 종료됨

**해결:**
1. 전체 로그 확인
   ```powershell
   Get-Content logs\batch_*.log | Select-String "ERROR"
   ```

2. 예외 처리 추가

3. Python 버전 확인

---

## 도움 요청

위 방법으로 해결되지 않는 경우:

1. **로그 파일 확인**
   - `logs/batch_YYYYMMDD.log`

2. **이슈 리포트 작성**
   - 발생한 오류 메시지
   - 사용 환경 (OS, Python 버전)
   - 재현 단계
   - 로그 파일 첨부

3. **디버그 모드 실행**
   ```python
   # logger.py에서 로그 레벨 변경
   self.logger.setLevel(logging.DEBUG)
   ```

4. **테스트 실행**
   ```powershell
   # 엑셀 읽기 테스트
   python test_excel_read.py
   
   # 단순 설정 테스트
   python -c "from config import *; print(RAGFLOW_API_KEY)"
   ```

