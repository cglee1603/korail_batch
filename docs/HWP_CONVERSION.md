# HWP 파일 변환 가이드

## 📋 개요

배치 프로그램은 HWP 파일을 자동으로 PDF로 변환하여 RAGFlow에 업로드합니다.

## 🔧 설치 및 설정

### Linux 환경 (권장)

#### 1. LibreOffice 설치

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y libreoffice libreoffice-writer

# CentOS/RHEL
sudo yum install -y libreoffice libreoffice-writer

# Alpine Linux (Docker)
apk add --no-cache libreoffice
```

#### 2. 한글 폰트 설치 (권장)

```bash
# Ubuntu/Debian
sudo apt-get install -y fonts-nanum fonts-nanum-coding fonts-nanum-extra

# 또는 직접 설치
wget https://github.com/naver/nanumfont/releases/download/VER2.6/NanumFont_TTF_ALL.zip
unzip NanumFont_TTF_ALL.zip -d /usr/share/fonts/truetype/nanum
fc-cache -f -v
```

#### 3. 설치 확인

```bash
# LibreOffice 버전 확인
soffice --version
# 또는
libreoffice --version

# 변환 테스트
soffice --headless --convert-to pdf test.hwp
```

### Windows 환경

#### 1. LibreOffice 설치

- **다운로드**: https://www.libreoffice.org/download/download/
- **버전**: LibreOffice 7.6 이상 권장
- **설치 옵션**: 기본값 사용

#### 2. 한글 지원 확인

- LibreOffice Writer 실행
- 도구 → 옵션 → 언어 설정 → 언어
- "한국어" 선택 및 설치

#### 3. PATH 설정 (선택사항)

```powershell
# 시스템 환경 변수에 추가
C:\Program Files\LibreOffice\program
```

### Docker 환경

```dockerfile
# Dockerfile에 추가
FROM python:3.11-slim

# LibreOffice 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        libreoffice-writer \
        fonts-nanum \
        fonts-nanum-coding && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 나머지 설정...
```

## 🚀 사용 방법

### 자동 변환 (배치 프로그램)

배치 프로그램 실행 시 HWP 파일을 자동으로 PDF로 변환합니다.

```bash
# 배치 실행
python run.py --once --excel "data/documents.xlsx"

# 로그에서 변환 과정 확인
tail -f logs/batch_*.log | grep "HWP"
```

### 로그 예시

```
2025-05-15 10:05:00 - INFO - HWP->PDF 변환 시작: document.hwp
2025-05-15 10:05:01 - INFO - LibreOffice 명령 실행: soffice --headless --convert-to pdf --outdir /tmp document.hwp
2025-05-15 10:05:05 - INFO - LibreOffice 변환 성공: document.pdf
2025-05-15 10:05:06 - INFO - 파일 업로드 시작: document.pdf
```

### 수동 변환 (테스트)

```bash
# 단일 파일 변환
soffice --headless --convert-to pdf document.hwp

# 출력 디렉토리 지정
soffice --headless --convert-to pdf --outdir output/ document.hwp

# 여러 파일 변환
soffice --headless --convert-to pdf *.hwp
```

## 🔍 문제 해결

### 1. LibreOffice를 찾을 수 없음

**증상:**
```
LibreOffice를 찾을 수 없습니다. 설치 필요
```

**해결:**
```bash
# Linux
which soffice
which libreoffice

# 설치되지 않은 경우
sudo apt-get install libreoffice

# Windows
# PATH에 LibreOffice 경로 추가
```

### 2. 변환 타임아웃

**증상:**
```
HWP 변환 타임아웃 (5분 초과)
```

**원인:**
- 파일이 너무 큼
- 복잡한 레이아웃
- 시스템 리소스 부족

**해결:**
- `file_handler.py`의 타임아웃 값 증가
- 파일 크기 확인
- 시스템 리소스 확인

### 3. 한글 깨짐

**증상:**
PDF에서 한글이 깨지거나 네모 박스로 표시됨

**해결:**
```bash
# 한글 폰트 설치
sudo apt-get install fonts-nanum fonts-nanum-coding

# 폰트 캐시 갱신
fc-cache -f -v

# 설치된 폰트 확인
fc-list | grep -i nanum
```

### 4. 변환 실패 시 동작

배치 프로그램은 변환 실패 시 원본 HWP 파일을 그대로 업로드합니다.

```
WARNING - HWP->PDF 변환 실패: document.hwp
WARNING - 원본 HWP 파일을 그대로 사용: document.hwp
```

RAGFlow가 HWP를 지원하지 않으면 파싱 오류가 발생할 수 있습니다.

## 🎯 고급 설정

### 변환 품질 설정

`file_handler.py`에서 LibreOffice 명령에 옵션 추가:

```python
cmd = [
    soffice_cmd,
    '--headless',
    '--convert-to', 'pdf:writer_pdf_Export',
    '--outdir', str(output_dir),
    str(hwp_path)
]
```

### PDF 옵션 설정

```python
# 고품질 PDF
'--convert-to', 'pdf:writer_pdf_Export:{"Quality":100}'

# 압축된 PDF
'--convert-to', 'pdf:writer_pdf_Export:{"Quality":75,"ReduceImageResolution":true}'
```

### 배치 변환

여러 파일을 한 번에 변환:

```python
def batch_convert_hwp(self, hwp_files: List[Path]) -> List[Path]:
    """여러 HWP 파일을 일괄 변환"""
    converted = []
    for hwp_file in hwp_files:
        pdf_file = self.convert_hwp_to_pdf(hwp_file)
        if pdf_file:
            converted.append(pdf_file)
    return converted
```

## 📊 성능 최적화

### 1. 병렬 처리

```python
from concurrent.futures import ThreadPoolExecutor

def convert_multiple_hwp(self, hwp_paths: List[Path], max_workers: int = 4):
    """병렬로 여러 HWP 파일 변환"""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(self.convert_hwp_to_pdf, hwp_paths))
    return results
```

### 2. 캐싱

```python
def convert_hwp_to_pdf_cached(self, hwp_path: Path) -> Optional[Path]:
    """변환 결과 캐싱"""
    pdf_path = hwp_path.with_suffix('.pdf')
    
    # 이미 변환된 파일이 있고 최신이면 재사용
    if pdf_path.exists():
        if pdf_path.stat().st_mtime > hwp_path.stat().st_mtime:
            logger.info(f"캐시된 PDF 사용: {pdf_path}")
            return pdf_path
    
    return self.convert_hwp_to_pdf(hwp_path)
```

## 🐳 Docker 배포 예시

```dockerfile
FROM python:3.11-slim

# 시스템 패키지 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        libreoffice-writer \
        fonts-nanum \
        fonts-liberation && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 작업 디렉토리
WORKDIR /app

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드
COPY . .

# 실행
CMD ["python", "run.py"]
```

## 📝 대안 솔루션

### 1. unoconv (LibreOffice 기반)

```bash
# 설치
pip install unoconv

# 사용
unoconv -f pdf document.hwp
```

### 2. hwp5tools (Python 라이브러리)

```bash
# 설치 (Linux만)
pip install hwp5

# 사용
hwp5proc --to=pdf document.hwp
```

**제한사항**: 복잡한 레이아웃 지원 제한적

### 3. 클라우드 변환 서비스

- CloudConvert API
- Zamzar API
- ConvertAPI

**장점**: 서버 설치 불필요  
**단점**: 비용, 파일 업로드 필요, 개인정보 보호 이슈

## 🔒 보안 고려사항

1. **파일 크기 제한**: 너무 큰 파일은 변환 시간이 오래 걸림
2. **타임아웃 설정**: 무한 대기 방지
3. **임시 파일 정리**: 변환 후 임시 파일 삭제
4. **권한 제한**: LibreOffice를 제한된 권한으로 실행

## ✅ 체크리스트

- [ ] LibreOffice 설치 확인
- [ ] 한글 폰트 설치 확인
- [ ] 테스트 변환 성공
- [ ] 배치 프로그램에서 변환 동작 확인
- [ ] 로그에서 변환 과정 확인
- [ ] 변환된 PDF 품질 확인
- [ ] RAGFlow에서 PDF 파싱 확인

## 📞 지원

변환 관련 문제가 있으면:
1. 로그 파일 확인 (`logs/batch_*.log`)
2. LibreOffice 버전 확인
3. 한글 폰트 설치 확인
4. 수동 변환 테스트

