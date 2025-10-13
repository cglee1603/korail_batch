"""
배치 프로그램 초기 설정 스크립트
필요한 디렉토리를 생성하고 환경 파일을 설정합니다.
"""
import os
from pathlib import Path


def setup_directories():
    """필요한 디렉토리 생성"""
    directories = [
        'data',
        'data/downloads',
        'data/temp',
        'logs'
    ]
    
    for dir_path in directories:
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)
        print(f"[OK] 디렉토리 생성: {dir_path}")


def setup_env_file():
    """환경 설정 파일 생성"""
    env_example = Path('env.example')
    env_file = Path('.env')
    
    if env_file.exists():
        print(f"[WARNING] .env 파일이 이미 존재합니다: {env_file}")
        response = input("덮어쓰시겠습니까? (y/N): ")
        if response.lower() != 'y':
            print("[OK] .env 파일 유지")
            return
    
    if env_example.exists():
        import shutil
        shutil.copy2(env_example, env_file)
        print(f"[OK] .env 파일 생성: {env_file}")
        print(f"  -> {env_file}을 편집하여 설정을 입력하세요")
    else:
        print(f"[WARNING] env.example 파일을 찾을 수 없습니다")


def main():
    """메인 함수"""
    print("="*60)
    print("RAGFlow Plus 배치 프로그램 초기 설정")
    print("="*60)
    print()
    
    # 디렉토리 생성
    print("[1] 디렉토리 구조 생성")
    setup_directories()
    print()
    
    # 환경 설정 파일 생성
    print("[2] 환경 설정 파일 생성")
    setup_env_file()
    print()
    
    print("="*60)
    print("초기 설정 완료!")
    print("="*60)
    print()
    print("다음 단계:")
    print("1. .env 파일을 편집하여 RAGFlow API 키와 설정을 입력하세요")
    print("2. 처리할 엑셀 파일을 data/ 디렉토리에 복사하세요")
    print("3. pip install -r requirements.txt 명령으로 의존성을 설치하세요")
    print("4. python main.py --once 명령으로 배치를 실행하세요")
    print()


if __name__ == "__main__":
    main()

