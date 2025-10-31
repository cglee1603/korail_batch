#!/usr/bin/env python3
"""
upload_document만 테스트하는 최소 코드
기존 지식베이스를 사용하여 파일 업로드만 테스트
"""

import os
import sys
from pathlib import Path

# 현재 디렉토리의 src 모듈 import
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ragflow_client import RAGFlowClient

def main():
    print("=" * 70)
    print("upload_document 단독 테스트")
    print("=" * 70)
    
    # 1. 환경 변수 확인
    base_url = os.getenv("RAGFLOW_BASE_URL", "http://localhost:5000")
    username = os.getenv("MANAGEMENT_USERNAME", "admin")
    password = os.getenv("MANAGEMENT_PASSWORD", "12345678")
    
    print(f"\n설정:")
    print(f"  Base URL: {base_url}")
    print(f"  Username: {username}")
    
    # 2. 클라이언트 생성
    try:
        client = RAGFlowClient(base_url=base_url, username=username, password=password)
        print(f"  ✅ 로그인 성공\n")
    except Exception as e:
        print(f"  ❌ 로그인 실패: {e}")
        return False
    
    # 3. 기존 지식베이스 사용 (새로 생성하지 않음!)
    print("[1] 기존 지식베이스 조회...")
    try:
        response = client._make_request('GET', '/api/v1/knowledgebases')
        if response.status_code == 200:
            result = response.json()
            kb_list = result.get('data', {}).get('list', [])
            
            if not kb_list:
                print("  ❌ 지식베이스가 없습니다. Management UI에서 먼저 생성하세요.")
                return False
            
            # 첫 번째 지식베이스 사용
            dataset = kb_list[0]
            kb_id = dataset['id']
            kb_name = dataset['name']
            print(f"  ✅ 지식베이스 발견: {kb_name}")
            print(f"     ID: {kb_id}\n")
        else:
            print(f"  ❌ 조회 실패 (HTTP {response.status_code})")
            return False
    except Exception as e:
        print(f"  ❌ 에러: {e}")
        return False
    
    # 4. 테스트 파일 생성
    test_file = Path(__file__).parent / "test_upload.txt"
    test_file.write_text("테스트 파일 내용입니다.\n이 파일은 업로드 테스트용입니다.", encoding='utf-8')
    print(f"[2] 테스트 파일 생성: {test_file.name}\n")
    
    # 5. upload_document 호출
    print("[3] upload_document 호출 (핵심 테스트!)")
    print("    " + "-" * 60)
    
    try:
        success = client.upload_document(
            dataset=dataset,
            file_path=test_file,
            display_name=test_file.name
        )
        
        print("    " + "-" * 60)
        
        if success:
            print("\n✅ 성공! 파일이 지식베이스에 추가되었습니다.")
            test_file.unlink()  # 테스트 파일 삭제
            return True
        else:
            print("\n❌ 실패! 위의 로그를 확인하세요.")
            test_file.unlink()  # 테스트 파일 삭제
            return False
            
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        if test_file.exists():
            test_file.unlink()
        return False

if __name__ == "__main__":
    try:
        success = main()
        print("\n" + "=" * 70)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n테스트 중단")
        sys.exit(1)

