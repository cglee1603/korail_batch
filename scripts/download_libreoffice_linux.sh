#!/bin/bash
# LibreOffice Linux 오프라인 설치 파일 다운로드 스크립트
# 인터넷 연결된 Linux PC에서 실행

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 다운로드 디렉토리
DOWNLOAD_DIR="./libreoffice_offline_linux"
mkdir -p "$DOWNLOAD_DIR"

echo "======================================================================"
echo "LibreOffice Linux 오프라인 설치 파일 다운로드"
echo "======================================================================"
echo ""

# 버전 설정
VERSION="24.8.4"
BUILD="1"

# 배포판 감지
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    DISTRO="unknown"
fi

echo "감지된 배포판: $DISTRO"
echo ""

# Ubuntu/Debian용 다운로드
download_deb() {
    echo "======================================================================"
    echo "Ubuntu/Debian용 패키지 다운로드"
    echo "======================================================================"
    echo ""
    
    DEB_DIR="$DOWNLOAD_DIR/deb"
    mkdir -p "$DEB_DIR"
    
    BASE_URL="https://download.documentfoundation.org/libreoffice/stable/$VERSION/deb/x86_64"
    
    # 메인 패키지
    MAIN_PKG="LibreOffice_${VERSION}_Linux_x86-64_deb.tar.gz"
    if [ ! -f "$DEB_DIR/$MAIN_PKG" ]; then
        echo -e "${CYAN}다운로드: $MAIN_PKG${NC}"
        wget -q --show-progress -O "$DEB_DIR/$MAIN_PKG" "$BASE_URL/$MAIN_PKG"
        echo -e "${GREEN}완료!${NC}"
    else
        echo -e "${YELLOW}이미 존재: $MAIN_PKG${NC}"
    fi
    
    # 한글 언어팩
    LANGPACK="LibreOffice_${VERSION}_Linux_x86-64_deb_langpack_ko.tar.gz"
    if [ ! -f "$DEB_DIR/$LANGPACK" ]; then
        echo -e "${CYAN}다운로드: $LANGPACK${NC}"
        wget -q --show-progress -O "$DEB_DIR/$LANGPACK" "$BASE_URL/$LANGPACK" || echo -e "${YELLOW}언어팩 다운로드 실패 (선택사항)${NC}"
    else
        echo -e "${YELLOW}이미 존재: $LANGPACK${NC}"
    fi
    
    # 설치 스크립트 생성
    cat > "$DEB_DIR/install.sh" << 'INSTALL_SCRIPT'
#!/bin/bash
# LibreOffice Ubuntu/Debian 오프라인 설치 스크립트

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "======================================================================"
echo "LibreOffice 오프라인 설치 (Ubuntu/Debian)"
echo "======================================================================"
echo ""

# 관리자 권한 확인
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}오류: 관리자 권한이 필요합니다.${NC}"
    echo "sudo ./install.sh 로 실행하세요."
    exit 1
fi

# 메인 패키지 압축 해제 및 설치
echo -e "${CYAN}[1/3] LibreOffice 메인 설치...${NC}"
tar -xzf LibreOffice_*_Linux_x86-64_deb.tar.gz
cd LibreOffice_*/DEBS
dpkg -i *.deb
cd ../..
echo -e "${GREEN}완료!${NC}"
echo ""

# 언어팩 설치 (파일이 있는 경우)
if ls LibreOffice_*_langpack_ko.tar.gz 1> /dev/null 2>&1; then
    echo -e "${CYAN}[2/3] 한글 언어팩 설치...${NC}"
    tar -xzf LibreOffice_*_langpack_ko.tar.gz
    cd LibreOffice_*/DEBS
    dpkg -i *.deb
    cd ../..
    echo -e "${GREEN}완료!${NC}"
else
    echo -e "${CYAN}[2/3] 한글 언어팩 건너뛰기 (파일 없음)${NC}"
fi
echo ""

# 한글 폰트 설치 (apt 사용 가능한 경우)
echo -e "${CYAN}[3/3] 한글 폰트 설치 시도...${NC}"
if command -v apt-get &> /dev/null; then
    apt-get install -y fonts-nanum fonts-nanum-coding 2>/dev/null || echo "폰트 설치 실패 (인터넷 필요)"
else
    echo "apt-get을 찾을 수 없습니다. 폰트 설치 건너뛰기"
fi
echo ""

echo "======================================================================"
echo -e "${GREEN}LibreOffice 설치 완료!${NC}"
echo "======================================================================"
echo ""
echo "설치 확인: soffice --version"
echo ""
INSTALL_SCRIPT
    
    chmod +x "$DEB_DIR/install.sh"
    
    echo ""
    echo -e "${GREEN}Ubuntu/Debian용 다운로드 완료: $DEB_DIR${NC}"
}

# CentOS/RHEL용 다운로드
download_rpm() {
    echo "======================================================================"
    echo "CentOS/RHEL용 패키지 다운로드"
    echo "======================================================================"
    echo ""
    
    RPM_DIR="$DOWNLOAD_DIR/rpm"
    mkdir -p "$RPM_DIR"
    
    BASE_URL="https://download.documentfoundation.org/libreoffice/stable/$VERSION/rpm/x86_64"
    
    # 메인 패키지
    MAIN_PKG="LibreOffice_${VERSION}_Linux_x86-64_rpm.tar.gz"
    if [ ! -f "$RPM_DIR/$MAIN_PKG" ]; then
        echo -e "${CYAN}다운로드: $MAIN_PKG${NC}"
        wget -q --show-progress -O "$RPM_DIR/$MAIN_PKG" "$BASE_URL/$MAIN_PKG"
        echo -e "${GREEN}완료!${NC}"
    else
        echo -e "${YELLOW}이미 존재: $MAIN_PKG${NC}"
    fi
    
    # 한글 언어팩
    LANGPACK="LibreOffice_${VERSION}_Linux_x86-64_rpm_langpack_ko.tar.gz"
    if [ ! -f "$RPM_DIR/$LANGPACK" ]; then
        echo -e "${CYAN}다운로드: $LANGPACK${NC}"
        wget -q --show-progress -O "$RPM_DIR/$LANGPACK" "$BASE_URL/$LANGPACK" || echo -e "${YELLOW}언어팩 다운로드 실패 (선택사항)${NC}"
    else
        echo -e "${YELLOW}이미 존재: $LANGPACK${NC}"
    fi
    
    # 설치 스크립트 생성
    cat > "$RPM_DIR/install.sh" << 'INSTALL_SCRIPT'
#!/bin/bash
# LibreOffice CentOS/RHEL 오프라인 설치 스크립트

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "======================================================================"
echo "LibreOffice 오프라인 설치 (CentOS/RHEL)"
echo "======================================================================"
echo ""

# 관리자 권한 확인
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}오류: 관리자 권한이 필요합니다.${NC}"
    echo "sudo ./install.sh 로 실행하세요."
    exit 1
fi

# 메인 패키지 압축 해제 및 설치
echo -e "${CYAN}[1/3] LibreOffice 메인 설치...${NC}"
tar -xzf LibreOffice_*_Linux_x86-64_rpm.tar.gz
cd LibreOffice_*/RPMS
yum localinstall -y *.rpm || dnf install -y *.rpm
cd ../..
echo -e "${GREEN}완료!${NC}"
echo ""

# 언어팩 설치 (파일이 있는 경우)
if ls LibreOffice_*_langpack_ko.tar.gz 1> /dev/null 2>&1; then
    echo -e "${CYAN}[2/3] 한글 언어팩 설치...${NC}"
    tar -xzf LibreOffice_*_langpack_ko.tar.gz
    cd LibreOffice_*/RPMS
    yum localinstall -y *.rpm || dnf install -y *.rpm
    cd ../..
    echo -e "${GREEN}완료!${NC}"
else
    echo -e "${CYAN}[2/3] 한글 언어팩 건너뛰기 (파일 없음)${NC}"
fi
echo ""

# 한글 폰트 설치 (yum/dnf 사용 가능한 경우)
echo -e "${CYAN}[3/3] 한글 폰트 설치 시도...${NC}"
if command -v yum &> /dev/null; then
    yum install -y google-noto-sans-cjk-fonts 2>/dev/null || echo "폰트 설치 실패 (인터넷 필요)"
elif command -v dnf &> /dev/null; then
    dnf install -y google-noto-sans-cjk-fonts 2>/dev/null || echo "폰트 설치 실패 (인터넷 필요)"
fi
echo ""

echo "======================================================================"
echo -e "${GREEN}LibreOffice 설치 완료!${NC}"
echo "======================================================================"
echo ""
echo "설치 확인: soffice --version"
echo ""
INSTALL_SCRIPT
    
    chmod +x "$RPM_DIR/install.sh"
    
    echo ""
    echo -e "${GREEN}CentOS/RHEL용 다운로드 완료: $RPM_DIR${NC}"
}

# 배포판에 따라 다운로드
case "$DISTRO" in
    ubuntu|debian)
        download_deb
        ;;
    centos|rhel|rocky|almalinux)
        download_rpm
        ;;
    *)
        echo -e "${YELLOW}알 수 없는 배포판입니다. 양쪽 모두 다운로드합니다.${NC}"
        download_deb
        download_rpm
        ;;
esac

echo ""
echo "======================================================================"
echo -e "${GREEN}다운로드 완료!${NC}"
echo "======================================================================"
echo ""
echo "다운로드된 파일: $DOWNLOAD_DIR"
echo ""
echo "오프라인 PC로 전달 방법:"
echo "  1. '$DOWNLOAD_DIR' 폴더를 USB/SCP로 전달"
echo "  2. 오프라인 PC에서 해당 배포판 폴더로 이동"
echo "  3. sudo ./install.sh 실행"
echo ""
echo "파일 경로: $(readlink -f $DOWNLOAD_DIR)"
echo ""

