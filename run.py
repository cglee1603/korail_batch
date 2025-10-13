"""
RAGFlow Plus 배치 프로그램 실행 스크립트
프로젝트 루트에서 실행하는 메인 진입점
"""
import sys
from pathlib import Path

# src 디렉토리를 Python 경로에 추가
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# 메인 모듈 실행
from main import main

if __name__ == "__main__":
    main()

