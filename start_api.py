"""
RAGFlow Plus 배치 프로그램 API 서버 실행 스크립트
"""
import sys
from pathlib import Path

# src 디렉토리를 Python 경로에 추가
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    import uvicorn
    
    print("="*80)
    print("RAGFlow Plus Batch API 서버 시작")
    print("="*80)
    print("API 문서: http://localhost:8000/docs")
    print("API Redoc: http://localhost:8000/redoc")
    print("헬스 체크: http://localhost:8000/health")
    print("="*80)
    print()
    
    # API 서버 실행
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )

