"""
RAGFlow Plus Batch API 테스트 스크립트

폐쇄망 반입 후 API 서버가 정상 동작하는지 확인하기 위한 테스트 코드입니다.
requests 라이브러리만 사용하므로 별도 테스트 프레임워크 설치가 필요 없습니다.

사용법:
    1) API 서버 실행:  python start_api.py
    2) 테스트 실행:    python src/api/test_api.py
    3) 개별 테스트:    python src/api/test_api.py --test health
    4) 서버 주소 변경: python src/api/test_api.py --base-url http://192.168.0.10:8000

테스트 목록:
    health       - 헬스 체크 (의존성 없음)
    root         - 서비스 정보 (의존성 없음)
    jobs         - 작업 관리 CRUD (의존성 없음)
    kb_list      - 지식베이스 목록 (RAGFlow 연결 필요)
    kb_delete    - 문서 삭제 미리보기 (RAGFlow 연결 필요, --kb-name 필요)
    kb_sync      - DB 동기화 확인 (RAGFlow + DB 연결 필요, --kb-name 필요)
    excel_export - Excel 익스포트 (Excel 파일 필요, --excel-file 필요)
    excel_batch  - Excel 배치 (Excel 파일 + RAGFlow 필요, --excel-file 필요)
    fs_batch     - Filesystem 배치 (디렉토리 + RAGFlow 필요, --fs-path 필요)
    parse        - 파싱 제어 (RAGFlow 연결 필요, --kb-name 필요)
    all          - 전체 테스트 (기본)
"""
import sys
import time
import json
import argparse
import requests


# ==================== 테스트 유틸리티 ====================

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {title}{Colors.END}")
    print(f"{'='*60}")


def print_result(name: str, passed: bool, detail: str = ""):
    status = f"{Colors.GREEN}PASS{Colors.END}" if passed else f"{Colors.RED}FAIL{Colors.END}"
    print(f"  [{status}] {name}")
    if detail:
        print(f"         {detail}")


def print_skip(name: str, reason: str):
    print(f"  [{Colors.YELLOW}SKIP{Colors.END}] {name}")
    print(f"         {reason}")


def safe_request(method: str, url: str, **kwargs):
    """안전한 HTTP 요청 (연결 실패 시 None 반환)"""
    try:
        resp = getattr(requests, method)(url, timeout=30, **kwargs)
        return resp
    except requests.ConnectionError:
        return None
    except Exception as e:
        print(f"         요청 오류: {e}")
        return None


# ==================== 개별 테스트 ====================

class APITester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.results = {"pass": 0, "fail": 0, "skip": 0}
        self._created_job_id = None

    def _record(self, passed: bool):
        self.results["pass" if passed else "fail"] += 1

    def _skip(self):
        self.results["skip"] += 1

    # ---------- Common ----------

    def test_health(self):
        print_header("Health Check")

        resp = safe_request("get", f"{self.base_url}/health")
        if resp is None:
            print_result("GET /health", False, "서버 연결 실패. API 서버가 실행 중인지 확인하세요.")
            self._record(False)
            return False

        ok = resp.status_code == 200 and resp.json().get("status") == "healthy"
        print_result("GET /health", ok, f"status={resp.status_code}, body={resp.json()}")
        self._record(ok)
        return ok

    def test_root(self):
        print_header("Root / Service Info")

        resp = safe_request("get", f"{self.base_url}/")
        if resp is None:
            print_result("GET /", False, "서버 연결 실패")
            self._record(False)
            return False

        body = resp.json()
        ok = resp.status_code == 200 and body.get("service") == "RAGFlow Plus Batch API"
        print_result("GET /", ok, f"version={body.get('version')}, status={body.get('status')}")
        self._record(ok)
        return ok

    # ---------- Jobs ----------

    def test_jobs(self):
        print_header("Jobs 관리 (CRUD)")

        # 1) 빈 목록 조회
        resp = safe_request("get", f"{self.base_url}/jobs")
        if resp is None:
            print_result("GET /jobs", False, "서버 연결 실패")
            self._record(False)
            return False

        ok = resp.status_code == 200 and "total_jobs" in resp.json()
        print_result("GET /jobs (목록 조회)", ok, f"total_jobs={resp.json().get('total_jobs')}")
        self._record(ok)

        # 2) 존재하지 않는 job 조회 → 404
        resp = safe_request("get", f"{self.base_url}/jobs/non-existent-id")
        ok = resp is not None and resp.status_code == 404
        print_result("GET /jobs/invalid-id (404 확인)", ok, f"status={resp.status_code if resp else 'N/A'}")
        self._record(ok)

        # 3) 존재하지 않는 job 삭제 → 404
        resp = safe_request("delete", f"{self.base_url}/jobs/non-existent-id")
        ok = resp is not None and resp.status_code == 404
        print_result("DELETE /jobs/invalid-id (404 확인)", ok, f"status={resp.status_code if resp else 'N/A'}")
        self._record(ok)

        return True

    # ---------- Knowledgebase ----------

    def test_kb_list(self):
        print_header("지식베이스 목록 조회")

        resp = safe_request("get", f"{self.base_url}/knowledgebases")
        if resp is None:
            print_result("GET /knowledgebases", False, "서버 연결 실패")
            self._record(False)
            return False

        if resp.status_code == 500:
            print_result("GET /knowledgebases", False, f"RAGFlow 연결 실패: {resp.json().get('detail', '')}")
            self._record(False)
            return False

        body = resp.json()
        ok = resp.status_code == 200 and "knowledgebases" in body
        detail = f"total={body.get('total', 0)}"
        if body.get("knowledgebases"):
            names = [kb["name"] for kb in body["knowledgebases"][:5]]
            detail += f", 상위5: {names}"
        print_result("GET /knowledgebases", ok, detail)
        self._record(ok)
        return ok

    def test_kb_delete_preview(self, kb_name: str):
        print_header(f"문서 삭제 미리보기 (kb={kb_name})")

        # confirm=false → 미리보기만
        resp = safe_request("delete", f"{self.base_url}/knowledgebases/{kb_name}/documents?confirm=false")
        if resp is None:
            print_result("DELETE .../documents?confirm=false", False, "서버 연결 실패")
            self._record(False)
            return False

        if resp.status_code == 500:
            print_result("DELETE .../documents?confirm=false", False, f"오류: {resp.json().get('detail', '')}")
            self._record(False)
            return False

        body = resp.json()
        ok = resp.status_code == 200 and body.get("confirm") is False
        print_result(
            "DELETE .../documents?confirm=false (미리보기)",
            ok,
            f"total_documents={body.get('total_documents')}, message={body.get('message', '')[:60]}",
        )
        self._record(ok)
        return ok

    def test_kb_sync(self, kb_name: str):
        print_header(f"지식베이스-DB 동기화 확인 (kb={kb_name})")

        resp = safe_request("post", f"{self.base_url}/knowledgebases/{kb_name}/sync", json={"fix": False})
        if resp is None:
            print_result("POST .../sync", False, "서버 연결 실패")
            self._record(False)
            return False

        if resp.status_code == 500:
            print_result("POST .../sync", False, f"오류: {resp.json().get('detail', '')}")
            self._record(False)
            return False

        body = resp.json()
        ok = resp.status_code == 200 and "message" in body
        print_result(
            "POST .../sync (fix=false, 확인만)",
            ok,
            f"message={body.get('message', '')[:60]}",
        )
        self._record(ok)
        return ok

    # ---------- Excel ----------

    def test_excel_export(self, excel_file: str):
        print_header(f"Excel Export (file={excel_file})")

        resp = safe_request("post", f"{self.base_url}/excel/export", json={
            "excel_file": excel_file,
            "export_outdir": "data/temp/test_export",
            "early_stop": 5,
        })
        if resp is None:
            print_result("POST /excel/export", False, "서버 연결 실패")
            self._record(False)
            return False

        if resp.status_code == 400:
            print_result("POST /excel/export", False, f"파일 오류: {resp.json().get('detail', '')}")
            self._record(False)
            return False

        if resp.status_code == 500:
            print_result("POST /excel/export", False, f"서버 오류: {resp.json().get('detail', '')}")
            self._record(False)
            return False

        body = resp.json()
        ok = resp.status_code == 200 and body.get("sheets_processed", 0) >= 0
        print_result(
            "POST /excel/export",
            ok,
            f"sheets_processed={body.get('sheets_processed')}, "
            f"sheets_skipped={body.get('sheets_skipped')}, "
            f"output_files={len(body.get('output_files', []))}개",
        )
        self._record(ok)
        return ok

    def test_excel_batch(self, excel_file: str):
        print_header(f"Excel Batch (file={excel_file})")

        # 1) 배치 작업 생성
        resp = safe_request("post", f"{self.base_url}/excel/batch", json={
            "excel_files": [excel_file],
        })
        if resp is None:
            print_result("POST /excel/batch", False, "서버 연결 실패")
            self._record(False)
            return False

        if resp.status_code == 400:
            print_result("POST /excel/batch", False, f"파일 오류: {resp.json().get('detail', '')}")
            self._record(False)
            return False

        body = resp.json()
        ok = resp.status_code == 200 and body.get("status") == "queued"
        job_id = body.get("job_id", "")
        print_result("POST /excel/batch (작업 생성)", ok, f"job_id={job_id}, status={body.get('status')}")
        self._record(ok)

        if not ok:
            return False

        # 2) 작업 상태 폴링 (최대 60초)
        print(f"\n  ⏳ 작업 완료 대기 중 (최대 60초)...")
        final_status = self._poll_job(job_id, timeout=60)
        ok = final_status in ("completed", "failed")
        print_result(
            f"GET /jobs/{job_id[:8]}... (최종 상태)",
            ok,
            f"status={final_status}",
        )
        self._record(ok)

        self._created_job_id = job_id
        return ok

    def test_excel_batch_validation(self):
        print_header("Excel Batch 유효성 검사")

        # 존재하지 않는 파일 → 400
        resp = safe_request("post", f"{self.base_url}/excel/batch", json={
            "excel_files": ["non_existent_file.xlsx"],
        })
        if resp is None:
            print_result("POST /excel/batch (invalid file)", False, "서버 연결 실패")
            self._record(False)
            return False

        ok = resp.status_code == 400
        print_result("POST /excel/batch (존재하지 않는 파일 → 400)", ok, f"status={resp.status_code}")
        self._record(ok)

        # 빈 리스트 → 422
        resp = safe_request("post", f"{self.base_url}/excel/batch", json={
            "excel_files": [],
        })
        ok = resp is not None and resp.status_code == 422
        print_result("POST /excel/batch (빈 리스트 → 422)", ok, f"status={resp.status_code if resp else 'N/A'}")
        self._record(ok)

        return True

    # ---------- Filesystem ----------

    def test_fs_batch(self, fs_path: str):
        print_header(f"Filesystem Batch (path={fs_path})")

        resp = safe_request("post", f"{self.base_url}/filesystem/batch", json={
            "filesystem_path": fs_path,
        })
        if resp is None:
            print_result("POST /filesystem/batch", False, "서버 연결 실패")
            self._record(False)
            return False

        if resp.status_code == 400:
            print_result("POST /filesystem/batch", False, f"경로 오류: {resp.json().get('detail', '')}")
            self._record(False)
            return False

        body = resp.json()
        ok = resp.status_code == 200 and body.get("status") == "queued"
        job_id = body.get("job_id", "")
        print_result("POST /filesystem/batch (작업 생성)", ok, f"job_id={job_id}, status={body.get('status')}")
        self._record(ok)

        if not ok:
            return False

        print(f"\n  ⏳ 작업 완료 대기 중 (최대 120초)...")
        final_status = self._poll_job(job_id, timeout=120)
        ok = final_status in ("completed", "failed")
        print_result(f"GET /jobs/{job_id[:8]}... (최종 상태)", ok, f"status={final_status}")
        self._record(ok)

        return ok

    def test_fs_batch_validation(self):
        print_header("Filesystem Batch 유효성 검사")

        resp = safe_request("post", f"{self.base_url}/filesystem/batch", json={
            "filesystem_path": "/non/existent/path",
        })
        if resp is None:
            print_result("POST /filesystem/batch (invalid path)", False, "서버 연결 실패")
            self._record(False)
            return False

        ok = resp.status_code == 400
        print_result("POST /filesystem/batch (존재하지 않는 경로 → 400)", ok, f"status={resp.status_code}")
        self._record(ok)

        return True

    # ---------- Parsing ----------

    def test_parse_check(self, kb_name: str):
        print_header(f"파싱 제어 테스트 (kb={kb_name})")

        # check-and-parse
        resp = safe_request("post", f"{self.base_url}/parsing/{kb_name}/check-and-parse")
        if resp is None:
            print_result("POST .../check-and-parse", False, "서버 연결 실패")
            self._record(False)
            return False

        if resp.status_code == 500:
            detail = resp.json().get("detail", "")
            print_result("POST .../check-and-parse", False, f"오류: {detail[:80]}")
            self._record(False)
            return False

        body = resp.json()
        ok = resp.status_code == 200 and "message" in body
        print_result("POST .../check-and-parse", ok, f"message={body.get('message', '')[:60]}")
        self._record(ok)

        # reparse-all (confirm=false, 미리보기만)
        resp = safe_request("post", f"{self.base_url}/parsing/{kb_name}/reparse-all", json={
            "confirm": False,
        })
        if resp is not None and resp.status_code == 200:
            body = resp.json()
            ok = body.get("message", "").find("confirm=true") != -1 or "확인" in body.get("message", "")
            print_result("POST .../reparse-all (confirm=false)", ok, f"message={body.get('message', '')[:60]}")
        else:
            ok = False
            print_result("POST .../reparse-all (confirm=false)", False, f"status={resp.status_code if resp else 'N/A'}")
        self._record(ok)

        # throttle (confirm=false → 400)
        resp = safe_request("post", f"{self.base_url}/parsing/{kb_name}/throttle", json={
            "confirm": False,
        })
        ok = resp is not None and resp.status_code == 400
        print_result("POST .../throttle (confirm=false → 400)", ok, f"status={resp.status_code if resp else 'N/A'}")
        self._record(ok)

        return True

    # ---------- 유틸 ----------

    def _poll_job(self, job_id: str, timeout: int = 60) -> str:
        """작업 상태 폴링. 최종 상태 반환."""
        start = time.time()
        interval = 2
        while time.time() - start < timeout:
            resp = safe_request("get", f"{self.base_url}/jobs/{job_id}")
            if resp and resp.status_code == 200:
                status = resp.json().get("status", "")
                if status in ("completed", "failed"):
                    return status
            time.sleep(interval)
            interval = min(interval * 1.5, 10)
        return "timeout"

    # ---------- 전체 실행 ----------

    def run_all(self, excel_file: str = None, fs_path: str = None, kb_name: str = None):
        """전체 테스트 실행"""

        # 서버 연결 확인
        server_ok = self.test_health()
        if not server_ok:
            print(f"\n{Colors.RED}서버 연결 실패. 테스트를 중단합니다.{Colors.END}")
            print(f"서버 실행: python start_api.py")
            return

        self.test_root()
        self.test_jobs()
        self.test_excel_batch_validation()
        self.test_fs_batch_validation()

        # RAGFlow 연결 필요 테스트
        self.test_kb_list()

        if kb_name:
            self.test_kb_delete_preview(kb_name)
            self.test_kb_sync(kb_name)
            self.test_parse_check(kb_name)
        else:
            print_header("지식베이스 연동 테스트 (SKIP)")
            for name in ["문서 삭제 미리보기", "DB 동기화", "파싱 제어"]:
                print_skip(name, "--kb-name 미지정. 예: --kb-name \"지식베이스_이름\"")
                self._skip()

        if excel_file:
            self.test_excel_export(excel_file)
            self.test_excel_batch(excel_file)
        else:
            print_header("Excel 테스트 (SKIP)")
            for name in ["Excel Export", "Excel Batch"]:
                print_skip(name, "--excel-file 미지정. 예: --excel-file \"data/input.xlsx\"")
                self._skip()

        if fs_path:
            self.test_fs_batch(fs_path)
        else:
            print_header("Filesystem 테스트 (SKIP)")
            print_skip("Filesystem Batch", "--fs-path 미지정. 예: --fs-path \"data/filesystem\"")
            self._skip()

    def print_summary(self):
        """테스트 결과 요약"""
        total = self.results["pass"] + self.results["fail"] + self.results["skip"]
        print(f"\n{'='*60}")
        print(f"{Colors.BOLD}  테스트 결과 요약{Colors.END}")
        print(f"{'='*60}")
        print(f"  총 테스트: {total}")
        print(f"  {Colors.GREEN}PASS: {self.results['pass']}{Colors.END}")
        print(f"  {Colors.RED}FAIL: {self.results['fail']}{Colors.END}")
        print(f"  {Colors.YELLOW}SKIP: {self.results['skip']}{Colors.END}")
        print(f"{'='*60}")

        if self.results["fail"] == 0:
            print(f"\n  {Colors.GREEN}{Colors.BOLD}모든 테스트 통과!{Colors.END}\n")
        else:
            print(f"\n  {Colors.RED}{Colors.BOLD}실패한 테스트가 있습니다.{Colors.END}\n")


# ==================== CLI 진입점 ====================

def main():
    parser = argparse.ArgumentParser(
        description="RAGFlow Plus Batch API 테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 기본 테스트 (서버 연결 + 유효성 검사)
  python src/api/test_api.py

  # 특정 테스트만 실행
  python src/api/test_api.py --test health
  python src/api/test_api.py --test jobs

  # 지식베이스 연동 테스트
  python src/api/test_api.py --test kb_list
  python src/api/test_api.py --test kb_delete --kb-name "테스트_KB"

  # Excel 테스트
  python src/api/test_api.py --test excel_export --excel-file "data/input.xlsx"
  python src/api/test_api.py --test excel_batch --excel-file "data/input.xlsx"

  # Filesystem 테스트
  python src/api/test_api.py --test fs_batch --fs-path "data/filesystem"

  # 전체 테스트 (모든 옵션 지정)
  python src/api/test_api.py --excel-file "data/input.xlsx" --fs-path "data/filesystem" --kb-name "테스트_KB"

  # 서버 주소 변경
  python src/api/test_api.py --base-url http://192.168.0.10:9000
        """,
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="API 서버 URL (기본: http://localhost:8000)")
    parser.add_argument("--test", default="all", help="실행할 테스트 (health, root, jobs, kb_list, kb_delete, kb_sync, excel_export, excel_batch, fs_batch, parse, all)")
    parser.add_argument("--excel-file", default=None, help="테스트용 Excel 파일 경로")
    parser.add_argument("--fs-path", default=None, help="테스트용 Filesystem 디렉토리 경로")
    parser.add_argument("--kb-name", default=None, help="테스트용 지식베이스 이름")

    args = parser.parse_args()
    tester = APITester(args.base_url)

    print(f"\n{Colors.BOLD}RAGFlow Plus Batch API 테스트{Colors.END}")
    print(f"서버: {args.base_url}")

    test_name = args.test.lower()

    if test_name == "all":
        tester.run_all(
            excel_file=args.excel_file,
            fs_path=args.fs_path,
            kb_name=args.kb_name,
        )
    elif test_name == "health":
        tester.test_health()
    elif test_name == "root":
        tester.test_root()
    elif test_name == "jobs":
        tester.test_jobs()
    elif test_name == "kb_list":
        tester.test_kb_list()
    elif test_name == "kb_delete":
        if not args.kb_name:
            print(f"{Colors.RED}--kb-name 옵션이 필요합니다.{Colors.END}")
            sys.exit(1)
        tester.test_kb_delete_preview(args.kb_name)
    elif test_name == "kb_sync":
        if not args.kb_name:
            print(f"{Colors.RED}--kb-name 옵션이 필요합니다.{Colors.END}")
            sys.exit(1)
        tester.test_kb_sync(args.kb_name)
    elif test_name == "excel_export":
        if not args.excel_file:
            print(f"{Colors.RED}--excel-file 옵션이 필요합니다.{Colors.END}")
            sys.exit(1)
        tester.test_excel_export(args.excel_file)
    elif test_name == "excel_batch":
        if not args.excel_file:
            print(f"{Colors.RED}--excel-file 옵션이 필요합니다.{Colors.END}")
            sys.exit(1)
        tester.test_excel_batch(args.excel_file)
    elif test_name == "fs_batch":
        if not args.fs_path:
            print(f"{Colors.RED}--fs-path 옵션이 필요합니다.{Colors.END}")
            sys.exit(1)
        tester.test_fs_batch(args.fs_path)
    elif test_name == "parse":
        if not args.kb_name:
            print(f"{Colors.RED}--kb-name 옵션이 필요합니다.{Colors.END}")
            sys.exit(1)
        tester.test_parse_check(args.kb_name)
    else:
        print(f"{Colors.RED}알 수 없는 테스트: {test_name}{Colors.END}")
        parser.print_help()
        sys.exit(1)

    tester.print_summary()

    sys.exit(0 if tester.results["fail"] == 0 else 1)


if __name__ == "__main__":
    main()
