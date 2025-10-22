# LibreOffice 폐쇄망(Offline) 설치 가이드

## 📋 목차

1. [Windows 폐쇄망 설치](#windows-폐쇄망-설치)
2. [Linux 폐쇄망 설치](#linux-폐쇄망-설치)
3. [Docker 환경 설치](#docker-환경-설치)
4. [한글 폰트 추가 설치](#한글-폰트-추가-설치)

---

## 🪟 Windows 폐쇄망 설치

### 준비 단계 (인터넷 가능한 PC)

#### 방법 1: 자동 다운로드 (권장)

```powershell
# PowerShell 스크립트 실행
cd rag_batch/scripts
.\download_libreoffice_windows.ps1

# 결과: libreoffice_offline_windows 폴더 생성
```

#### 방법 2: 수동 다운로드

1. **브라우저에서 다운로드:**
   - https://www.libreoffice.org/download/download/
   - "Download Version" 클릭 → "Main Installer" 선택
   - 파일: `LibreOffice_24.8.4_Win_x64.msi` (약 320MB)

2. **한글 언어팩 (선택사항):**
   - 같은 페이지에서 "Translated User Interface" 클릭
   - 언어: Korean 선택
   - 파일: `LibreOffice_24.8.4_Win_x64_langpack_ko.msi`

3. **폴더 구조:**
   ```
   libreoffice_offline_windows/
   ├── LibreOffice_24.8.4_Win_x64.msi
   ├── LibreOffice_24.8.4_Win_x64_langpack_ko.msi
   └── install.bat
   ```

### 설치 단계 (폐쇄망 PC)

#### 방법 1: 배치 파일 실행 (권장)

```batch
REM 관리자 권한으로 실행
install.bat
```

#### 방법 2: 수동 설치

```powershell
# 메인 설치
msiexec /i LibreOffice_24.8.4_Win_x64.msi /qb ALLUSERS=1

# 한글 언어팩 설치 (선택)
msiexec /i LibreOffice_24.8.4_Win_x64_langpack_ko.msi /qb ALLUSERS=1
```

### 설치 확인

```powershell
# 설치 경로 확인
Test-Path "C:\Program Files\LibreOffice\program\soffice.exe"

# 버전 확인
& "C:\Program Files\LibreOffice\program\soffice.exe" --version

# PATH 확인 (선택사항)
$env:Path += ";C:\Program Files\LibreOffice\program"
soffice --version
```

---

## 🐧 Linux 폐쇄망 설치

### 준비 단계 (인터넷 가능한 PC)

#### 방법 1: 자동 다운로드 (권장)

```bash
# 스크립트 실행
cd rag_batch/scripts
chmod +x download_libreoffice_linux.sh
./download_libreoffice_linux.sh

# 결과: libreoffice_offline_linux 폴더 생성
#   ├── deb/  (Ubuntu/Debian용)
#   └── rpm/  (CentOS/RHEL용)
```

#### 방법 2: 수동 다운로드

**Ubuntu/Debian:**
```bash
# 메인 패키지
wget https://download.documentfoundation.org/libreoffice/stable/24.8.4/deb/x86_64/LibreOffice_24.8.4_Linux_x86-64_deb.tar.gz

# 한글 언어팩 (선택)
wget https://download.documentfoundation.org/libreoffice/stable/24.8.4/deb/x86_64/LibreOffice_24.8.4_Linux_x86-64_deb_langpack_ko.tar.gz
```

**CentOS/RHEL:**
```bash
# 메인 패키지
wget https://download.documentfoundation.org/libreoffice/stable/24.8.4/rpm/x86_64/LibreOffice_24.8.4_Linux_x86-64_rpm.tar.gz

# 한글 언어팩 (선택)
wget https://download.documentfoundation.org/libreoffice/stable/24.8.4/rpm/x86_64/LibreOffice_24.8.4_Linux_x86-64_rpm_langpack_ko.tar.gz
```

### 설치 단계 (폐쇄망 Linux)

#### Ubuntu/Debian

```bash
# 1. 압축 해제
tar -xzf LibreOffice_24.8.4_Linux_x86-64_deb.tar.gz
cd LibreOffice_*/DEBS

# 2. 패키지 설치
sudo dpkg -i *.deb

# 3. 의존성 문제 해결 (필요시)
sudo apt-get install -f

# 4. 한글 언어팩 설치 (선택)
cd ../../
tar -xzf LibreOffice_24.8.4_Linux_x86-64_deb_langpack_ko.tar.gz
cd LibreOffice_*/DEBS
sudo dpkg -i *.deb

# 5. 설치 확인
soffice --version
which soffice
```

#### CentOS/RHEL/Rocky Linux

```bash
# 1. 압축 해제
tar -xzf LibreOffice_24.8.4_Linux_x86-64_rpm.tar.gz
cd LibreOffice_*/RPMS

# 2. 패키지 설치 (yum)
sudo yum localinstall -y *.rpm

# 또는 (dnf - CentOS 8+)
sudo dnf install -y *.rpm

# 3. 한글 언어팩 설치 (선택)
cd ../../
tar -xzf LibreOffice_24.8.4_Linux_x86-64_rpm_langpack_ko.tar.gz
cd LibreOffice_*/RPMS
sudo yum localinstall -y *.rpm

# 4. 설치 확인
soffice --version
which soffice
```

---

## 🐳 Docker 환경 설치

### Dockerfile (폐쇄망용)

```dockerfile
FROM python:3.11-slim

# 1. 오프라인 패키지를 이미지에 복사
COPY libreoffice_offline_linux/deb/*.tar.gz /tmp/

# 2. 압축 해제 및 설치
RUN cd /tmp && \
    tar -xzf LibreOffice_*_Linux_x86-64_deb.tar.gz && \
    cd LibreOffice_*/DEBS && \
    apt-get update && \
    dpkg -i *.deb && \
    apt-get install -f -y && \
    rm -rf /tmp/* /var/lib/apt/lists/*

# 3. 설치 확인
RUN soffice --version

# 4. 작업 디렉토리
WORKDIR /app

# 5. Python 패키지 (오프라인 whl 파일 사용)
COPY requirements.txt .
COPY wheels/*.whl /tmp/wheels/
RUN pip install --no-index --find-links=/tmp/wheels -r requirements.txt

CMD ["python", "run.py"]
```

### 빌드 방법

```bash
# Docker 이미지 빌드
docker build -t ragflow-batch-offline .

# 실행
docker run -v ./data:/app/data ragflow-batch-offline
```

---

## 🎨 한글 폰트 추가 설치

### Windows

```powershell
# 나눔폰트 다운로드 (인터넷 PC)
# https://hangeul.naver.com/font
# 폰트 파일을 C:\Windows\Fonts에 복사
```

### Ubuntu/Debian

```bash
# 나눔폰트 패키지 (인터넷 연결 시)
sudo apt-get install fonts-nanum fonts-nanum-coding fonts-nanum-extra

# 오프라인 설치:
# 1. 인터넷 PC에서 패키지 다운로드
apt-get download fonts-nanum fonts-nanum-coding fonts-nanum-extra

# 2. 폐쇄망 PC로 전달 후 설치
sudo dpkg -i fonts-nanum*.deb

# 3. 폰트 캐시 갱신
fc-cache -f -v
```

### CentOS/RHEL

```bash
# Google Noto 폰트 (인터넷 연결 시)
sudo yum install google-noto-sans-cjk-fonts

# 오프라인 설치:
# 1. 인터넷 PC에서 RPM 다운로드
yumdownloader google-noto-sans-cjk-fonts

# 2. 폐쇄망 PC로 전달 후 설치
sudo rpm -ivh google-noto-sans-cjk-fonts*.rpm

# 3. 폰트 캐시 갱신
fc-cache -f -v
```

### 폰트 설치 확인

```bash
# Linux에서 설치된 한글 폰트 확인
fc-list :lang=ko

# LibreOffice에서 사용 가능한 폰트 확인
soffice --headless --convert-to pdf --help
```

---

## 🧪 설치 테스트

### Windows

```powershell
# 버전 확인
soffice --version

# HWP → PDF 변환 테스트
soffice --headless --convert-to pdf --outdir C:\temp test.hwp
```

### Linux

```bash
# 버전 확인
soffice --version

# HWP → PDF 변환 테스트
soffice --headless --convert-to pdf --outdir /tmp test.hwp

# 프로세스 확인
ps aux | grep soffice
```

---

## 📊 파일 크기 참고

| 파일 | 크기 | 설명 |
|------|------|------|
| LibreOffice Windows (msi) | ~320MB | 메인 설치 파일 |
| LibreOffice Linux (DEB) | ~240MB | 압축된 패키지 |
| LibreOffice Linux (RPM) | ~240MB | 압축된 패키지 |
| 한글 언어팩 | ~3MB | 선택사항 |
| 한글 도움말 | ~10MB | 선택사항 |
| 나눔폰트 | ~10MB | 한글 표시용 |

**총 용량 (권장):**
- Windows: ~350MB
- Linux: ~260MB
- Docker: ~270MB (베이스 이미지 제외)

---

## ⚠️ 주의사항

1. **버전 확인:**
   - 이 가이드는 LibreOffice 24.8.4 기준입니다.
   - 최신 버전: https://www.libreoffice.org/download/download/

2. **의존성:**
   - Linux에서 의존성 패키지가 없으면 설치 실패 가능
   - 필요시 의존성도 함께 다운로드: `apt-get download $(apt-cache depends libreoffice-writer | grep Depends | awk '{print $2}')`

3. **디스크 공간:**
   - Windows: 최소 1GB 여유 공간
   - Linux: 최소 800MB 여유 공간

4. **Java (선택사항):**
   - LibreOffice Base 사용 시 Java 필요
   - HWP → PDF 변환에는 불필요

---

## 🔧 문제 해결

### "command not found: soffice"

```bash
# PATH 추가
export PATH=$PATH:/usr/bin:/opt/libreoffice*/program

# 또는 절대 경로 사용
/opt/libreoffice7.6/program/soffice --version
```

### "dpkg: dependency problems"

```bash
# 의존성 자동 설치
sudo apt-get install -f
```

### "This application failed to start"

```bash
# 라이브러리 확인
ldd /usr/bin/soffice

# 누락된 라이브러리 확인 후 설치
```

---

## 📚 참고 링크

- LibreOffice 공식: https://www.libreoffice.org/
- 다운로드 미러: https://download.documentfoundation.org/libreoffice/stable/
- 문서: https://documentation.libreoffice.org/

---

**작성일:** 2025-10-15  
**버전:** 1.0  
**테스트 환경:** Windows 10, Ubuntu 22.04, CentOS 8

