"""
RevisionDB 테스트 스크립트
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent))

def test_revision_db():
    """RevisionDB 초기화 및 기본 동작 테스트"""
    print("="*60)
    print("RevisionDB 테스트")
    print("="*60)
    
    try:
        # src 디렉토리를 Python path에 추가
        src_path = Path(__file__).parent / 'src'
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        
        from revision_db import RevisionDB
        
        # 1. DB 초기화
        print("\n1. DB 초기화 중...")
        db = RevisionDB(db_path="./data/test_revision.db")
        print("✅ DB 초기화 성공!")
        
        # 2. 문서 저장 테스트
        print("\n2. 문서 저장 테스트...")
        success = db.save_document(
            document_key="test_key_001",
            document_id="doc_12345",
            dataset_id="dataset_001",
            dataset_name="테스트 지식베이스",
            revision="A1",
            file_path="/path/to/file.pdf",
            file_name="test.pdf"
        )
        if success:
            print("✅ 문서 저장 성공!")
        else:
            print("❌ 문서 저장 실패!")
            return False
        
        # 3. 문서 조회 테스트
        print("\n3. 문서 조회 테스트...")
        doc = db.get_document("test_key_001", "dataset_001")
        if doc:
            print("✅ 문서 조회 성공!")
            print(f"   - document_key: {doc['document_key']}")
            print(f"   - document_id: {doc['document_id']}")
            print(f"   - revision: {doc['revision']}")
        else:
            print("❌ 문서 조회 실패!")
            return False
        
        # 4. 통계 조회 테스트
        print("\n4. 통계 조회 테스트...")
        stats = db.get_statistics()
        print(f"✅ 통계 조회 성공!")
        print(f"   - 총 문서 수: {stats['total_documents']}")
        print(f"   - 지식베이스 수: {len(stats['datasets'])}")
        
        # 5. 문서 업데이트 테스트
        print("\n5. 문서 업데이트 테스트 (revision A1 → B2)...")
        success = db.save_document(
            document_key="test_key_001",
            document_id="doc_67890",
            dataset_id="dataset_001",
            dataset_name="테스트 지식베이스",
            revision="B2",
            file_path="/path/to/file_v2.pdf",
            file_name="test_v2.pdf"
        )
        if success:
            doc = db.get_document("test_key_001", "dataset_001")
            print(f"✅ 문서 업데이트 성공!")
            print(f"   - 새 revision: {doc['revision']}")
            print(f"   - 새 document_id: {doc['document_id']}")
        else:
            print("❌ 문서 업데이트 실패!")
            return False
        
        # 6. 문서 삭제 테스트
        print("\n6. 문서 삭제 테스트...")
        success = db.delete_document("test_key_001", "dataset_001")
        if success:
            print("✅ 문서 삭제 성공!")
        else:
            print("❌ 문서 삭제 실패!")
            return False
        
        # 7. 삭제 확인
        doc = db.get_document("test_key_001", "dataset_001")
        if doc is None:
            print("✅ 삭제 확인: 문서가 존재하지 않음")
        else:
            print("❌ 삭제 확인 실패: 문서가 여전히 존재함")
            return False
        
        print("\n" + "="*60)
        print("✅ 모든 테스트 통과! RevisionDB가 정상 작동합니다.")
        print("="*60)
        
        # 테스트 DB 파일 삭제
        import os
        if os.path.exists("./data/test_revision.db"):
            os.remove("./data/test_revision.db")
            print("\n테스트 DB 파일 삭제 완료")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        print("\n상세 오류:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_revision_db()
    sys.exit(0 if success else 1)

