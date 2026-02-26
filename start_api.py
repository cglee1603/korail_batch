"""
RAGFlow Plus 배치 프로그램 API 서버 실행 스크립트
"""
import os
import sys
from pathlib import Path

# src 디렉토리를 Python 경로에 추가
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    print("=" * 80)
    print("RAGFlow Plus Batch API 서버 v2.0")
    print("=" * 80)
    print(f"API 문서 : http://{host}:{port}/docs")
    print(f"API Redoc: http://{host}:{port}/redoc")
    print(f"헬스 체크: http://{host}:{port}/health")
    print("=" * 80)
    print()
    print("[엔드포인트]")
    print("  Excel      : POST /excel/batch, POST /excel/export")
    print("  Filesystem : POST /filesystem/batch")
    print("  지식베이스 : GET /knowledgebases, DELETE /knowledgebases/{name}/documents, ...")
    print("  파싱       : POST /parsing/{name}/check-and-parse, /cancel, /reparse-all, /throttle")
    print("  작업 관리  : GET /jobs, GET /jobs/{id}, DELETE /jobs/{id}")
    print("  Database   : batch(CLI) 전용 → python run.py --source db")
    print("=" * 80)
    print()

    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )

