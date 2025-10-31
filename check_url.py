#!/usr/bin/env python3
"""
실제 호출되는 URL 확인 스크립트
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ragflow_client import RAGFlowClient

def main():
    base_url = os.getenv("RAGFLOW_BASE_URL", "http://localhost:5000")
    username = os.getenv("MANAGEMENT_USERNAME", "admin")
    password = os.getenv("MANAGEMENT_PASSWORD", "12345678")
    
    print("=" * 70)
    print("URL 확인 테스트")
    print("=" * 70)
    
    # 1. 로그인
    try:
        client = RAGFlowClient(base_url=base_url, username=username, password=password)
        print(f"\n✅ 로그인 성공")
        print(f"Base URL: {client.base_url}")
    except Exception as e:
        print(f"\n❌ 로그인 실패: {e}")
        return
    
    # 2. 지식베이스 조회
    print("\n" + "=" * 70)
    print("지식베이스 조회")
    print("=" * 70)
    
    try:
        response = client._make_request('GET', '/api/v1/knowledgebases')
        if response.status_code == 200:
            result = response.json()
            kb_list = result.get('data', {}).get('list', [])
            
            if not kb_list:
                print("❌ 지식베이스 없음")
                return
            
            kb = kb_list[0]
            kb_id = kb['id']
            kb_name = kb['name']
            
            print(f"✅ 지식베이스: {kb_name}")
            print(f"   ID: {kb_id}")
            print(f"   ID 길이: {len(kb_id)}")
            print(f"   ID에 슬래시 포함: {'/' in kb_id}")
            print(f"   ID에 공백 포함: {' ' in kb_id}")
            
            # 3. 실제 URL 구성 확인
            print("\n" + "=" * 70)
            print("문서 추가 URL 확인")
            print("=" * 70)
            
            endpoint = f'/api/v1/knowledgebases/{kb_id}/documents'
            full_url = f"{client.base_url}{endpoint}"
            
            print(f"Endpoint: {endpoint}")
            print(f"Full URL: {full_url}")
            print(f"URL 길이: {len(full_url)}")
            
            # 4. 테스트용 file_id (더미)
            test_file_id = "test-file-id-12345"
            
            print(f"\n요청 정보:")
            print(f"  Method: POST")
            print(f"  URL: {full_url}")
            print(f"  Body: {{'file_ids': ['{test_file_id}']}}")
            
            # 5. 실제 호출 (에러 확인용)
            print("\n" + "=" * 70)
            print("실제 API 호출 (더미 file_id)")
            print("=" * 70)
            
            test_response = client._make_request(
                'POST',
                f'/api/v1/knowledgebases/{kb_id}/documents',
                json={'file_ids': [test_file_id]}
            )
            
            print(f"\n응답 상태 코드: {test_response.status_code}")
            print(f"응답 내용: {test_response.text[:200]}")
            
            if test_response.status_code == 404:
                print("\n" + "=" * 70)
                print("❌ 404 오류 발생!")
                print("=" * 70)
                print("\n원인 분석:")
                print(f"1. URL: {full_url}")
                print(f"2. kb_id: {kb_id}")
                print(f"3. kb_id 타입: {type(kb_id)}")
                print(f"\n확인 사항:")
                print("□ Management API 서버가 실행 중인가?")
                print("□ 서버가 http://localhost:5000 에서 실행 중인가?")
                print("□ Blueprint가 등록되었나?")
                print(f"\nManagement API 서버에서 다음 명령으로 확인:")
                print(f"  curl -X GET {client.base_url}/api/v1/knowledgebases/{kb_id}")
                
        else:
            print(f"❌ 지식베이스 조회 실패: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 에러: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()


