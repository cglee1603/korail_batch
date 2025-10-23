#!/bin/bash
# Linux용 오프라인 패키지 다운로드 스크립트
# Python 3.11 환경

set -e

OUTPUT_DIR="${1:-rag_batch_offline_linux}"
PYTHON_VERSION="3.11"

echo "================================================================================"
echo " Linux용 패키지 다운로드"
echo "================================================================================"
echo ""

# 1. Python 버전 확인
echo "[1/6] Python 버전 확인..."
if command -v python${PYTHON_VERSION} &> /dev/null; then
    PYTHON_CMD="python${PYTHON_VERSION}"
    VERSION=$($PYTHON_CMD --version 2>&1)
    echo "  ✓ $VERSION"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    VERSION=$($PYTHON_CMD --version 2>&1)
    if [[ ! $VERSION =~ "3.11" ]]; then
        echo "  ✗ Python 3.11이 필요합니다. 현재: $VERSION"
        exit 1
    fi
    echo "  ✓ $VERSION"
else
    echo "  ✗ Python 3.11을 찾을 수 없습니다!"
    echo "  설치: sudo apt-get install python3.11"
    exit 1
fi

# 2. 스크립트 위치 및 프로젝트 루트 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo "  ✗ requirements.txt를 찾을 수 없습니다!"
    exit 1
fi

# 3. 출력 디렉토리 생성
echo ""
echo "[2/6] 출력 디렉토리 생성..."
OUTPUT_PATH="$(dirname "$PROJECT_ROOT")/$OUTPUT_DIR"

if [ -d "$OUTPUT_PATH" ]; then
    echo "  디렉토리가 이미 존재합니다: $OUTPUT_PATH"
    read -p "  삭제하고 새로 생성하시겠습니까? (y/n): " answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
        rm -rf "$OUTPUT_PATH"
        echo "  ✓ 기존 디렉토리 삭제"
    else
        exit 0
    fi
fi

mkdir -p "$OUTPUT_PATH/packages"
echo "  ✓ 디렉토리 생성: $OUTPUT_PATH"

# 4. requirements.txt 복사
echo ""
echo "[3/6] requirements.txt 복사..."
cp "$PROJECT_ROOT/requirements.txt" "$OUTPUT_PATH/"
echo "  ✓ requirements.txt 복사 완료"

# 5. Linux용 패키지 다운로드
echo ""
echo "[4/6] Linux용 패키지 다운로드 중..."
echo "  플랫폼: Linux (manylinux2014_x86_64)"
echo "  Python: $PYTHON_VERSION"
echo "  (시간이 소요될 수 있습니다...)"
echo ""

cd "$OUTPUT_PATH"

$PYTHON_CMD -m pip download \
    -r requirements.txt \
    -d packages \
    --platform manylinux2014_x86_64 \
    --python-version "$PYTHON_VERSION" \
    --only-binary=:all:

if [ $? -eq 0 ]; then
    echo ""
    echo "  ✓ 패키지 다운로드 완료"
else
    echo ""
    echo "  ✗ 패키지 다운로드 실패"
    exit 1
fi

cd - > /dev/null

# 6. 다운로드 확인
echo ""
echo "[5/6] 다운로드된 패키지 확인..."

PACKAGE_COUNT=$(find "$OUTPUT_PATH/packages" -name "*.whl" | wc -l)
TOTAL_SIZE=$(du -sh "$OUTPUT_PATH/packages" | cut -f1)

echo "  ✓ 패키지 수: $PACKAGE_COUNT 개"
echo "  ✓ 전체 크기: $TOTAL_SIZE"

# Linux 전용 패키지 확인
echo ""
echo "  Linux 전용 패키지:"

check_package() {
    local name=$1
    local pattern=$2
    local desc=$3
    
    if find "$OUTPUT_PATH/packages" -name "$pattern" | grep -q .; then
        echo "    ✓ $name - $desc"
    else
        echo "    ⚠ $name - 누락 (선택 패키지일 수 있음)"
    fi
}

check_package "psycopg2-binary" "psycopg2_binary-*-manylinux*.whl" "PostgreSQL 드라이버"
check_package "pymysql" "PyMySQL-*.whl" "MySQL 드라이버"

echo ""
echo "  제외된 Windows 전용 패키지:"
echo "    - pywin32 (Windows 전용)"
echo "    - python-magic-bin (Windows 전용)"
echo "    - pyodbc (Windows 전용)"

# 7. 프로젝트 파일 복사
echo ""
echo "[6/6] 프로젝트 파일 복사..."

ITEMS_TO_COPY=(
    "src"
    "scripts"
    "docs"
    "data"
    "run.py"
    "requirements.txt"
    "env.example"
    "README.md"
    "PROCESS.md"
    "OFFLINE_INSTALL_QUICK.md"
    "LIBRARY_CHECK_RESULT.md"
)

mkdir -p "$OUTPUT_PATH/rag_batch"

for item in "${ITEMS_TO_COPY[@]}"; do
    if [ -e "$PROJECT_ROOT/$item" ]; then
        cp -r "$PROJECT_ROOT/$item" "$OUTPUT_PATH/rag_batch/"
        echo "  ✓ $item"
    else
        echo "  ⚠ $item (없음)"
    fi
done

# 빈 디렉토리 생성
mkdir -p "$OUTPUT_PATH/rag_batch/logs"
echo "  ✓ logs (빈 디렉토리)"

# tar.gz 생성 여부 확인
echo ""
echo "================================================================================"
read -p "tar.gz 파일을 생성하시겠습니까? (y/n): " create_tar

if [ "$create_tar" = "y" ] || [ "$create_tar" = "Y" ]; then
    echo ""
    echo "tar.gz 파일 생성 중..."
    
    TAR_PATH="$OUTPUT_PATH.tar.gz"
    
    if [ -f "$TAR_PATH" ]; then
        rm -f "$TAR_PATH"
    fi
    
    cd "$(dirname "$OUTPUT_PATH")"
    tar -czf "$TAR_PATH" "$(basename "$OUTPUT_PATH")"
    cd - > /dev/null
    
    TAR_SIZE=$(du -sh "$TAR_PATH" | cut -f1)
    echo "  ✓ tar.gz 생성 완료"
    echo "  파일: $TAR_PATH"
    echo "  크기: $TAR_SIZE"
fi

# 완료
echo ""
echo "================================================================================"
echo " 다운로드 완료!"
echo "================================================================================"
echo ""
echo "📁 출력 위치: $OUTPUT_PATH"
echo "📦 패키지 수: $PACKAGE_COUNT 개"
echo "💾 전체 크기: $TOTAL_SIZE"
echo ""
echo "다음 단계 (폐쇄망 Linux PC에서):"
echo "  1. tar.gz 파일을 USB로 전송"
echo "  2. 압축 해제: tar -xzf $(basename "$OUTPUT_PATH").tar.gz"
echo "  3. 설치 명령:"
echo "     cd rag_batch"
echo "     python${PYTHON_VERSION} -m venv venv"
echo "     source venv/bin/activate"
echo "     python -m pip install --no-index --find-links=../packages -r requirements.txt"
echo ""

