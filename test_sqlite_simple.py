"""
간단한 SQLite 테스트 - RevisionDB와 동일한 SQL 구문 테스트
"""
import sqlite3
import os
from pathlib import Path

def test_sqlite_syntax():
    """RevisionDB와 동일한 SQL 구문 테스트"""
    print("="*60)
    print("SQLite SQL 구문 테스트")
    print("="*60)
    
    db_path = "./data/test_simple.db"
    
    # 데이터 디렉토리 생성
    Path("./data").mkdir(parents=True, exist_ok=True)
    
    try:
        # 1. 데이터베이스 연결
        print("\n1. 데이터베이스 연결...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("✅ 연결 성공!")
        
        # 2. 테이블 생성 (RevisionDB와 동일한 구문)
        print("\n2. 테이블 생성 (CREATE TABLE IF NOT EXISTS)...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_key TEXT NOT NULL,
                document_id TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                dataset_name TEXT NOT NULL,
                revision TEXT,
                file_path TEXT,
                file_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(document_key, dataset_id)
            )
        """)
        print("✅ 테이블 생성 성공!")
        
        # 3. 인덱스 생성 (RevisionDB와 동일한 구문)
        print("\n3. 인덱스 생성 (CREATE INDEX IF NOT EXISTS)...")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_key 
            ON documents(document_key)
        """)
        print("✅ idx_document_key 생성 성공!")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dataset_id 
            ON documents(dataset_id)
        """)
        print("✅ idx_dataset_id 생성 성공!")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_id 
            ON documents(document_id)
        """)
        print("✅ idx_document_id 생성 성공!")
        
        conn.commit()
        
        # 4. 데이터 삽입 테스트
        print("\n4. 데이터 삽입 테스트...")
        from datetime import datetime
        now = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO documents 
            (document_key, document_id, dataset_id, dataset_name, revision, 
             file_path, file_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("test_key_001", "doc_12345", "dataset_001", "테스트 지식베이스", "A1",
              "/path/to/file.pdf", "test.pdf", now, now))
        conn.commit()
        print("✅ 데이터 삽입 성공!")
        
        # 5. 데이터 조회 테스트
        print("\n5. 데이터 조회 테스트...")
        cursor.execute("""
            SELECT * FROM documents 
            WHERE document_key = ? AND dataset_id = ?
        """, ("test_key_001", "dataset_001"))
        row = cursor.fetchone()
        
        if row:
            print("✅ 데이터 조회 성공!")
            print(f"   - ID: {row[0]}")
            print(f"   - document_key: {row[1]}")
            print(f"   - document_id: {row[2]}")
            print(f"   - revision: {row[5]}")
        else:
            print("❌ 데이터 조회 실패!")
            return False
        
        # 6. 테이블 정보 확인
        print("\n6. 테이블 정보 확인...")
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='documents'")
        table_sql = cursor.fetchone()[0]
        print(f"테이블 구조:\n{table_sql}")
        
        # 7. 인덱스 정보 확인
        print("\n7. 인덱스 목록 확인...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='documents'")
        indexes = cursor.fetchall()
        for idx in indexes:
            print(f"   - {idx[0]}")
        
        conn.close()
        
        print("\n" + "="*60)
        print("✅ 모든 SQL 구문이 정상 작동합니다!")
        print("   RevisionDB에 문제가 없습니다.")
        print("="*60)
        
        # 테스트 DB 파일 삭제
        if os.path.exists(db_path):
            os.remove(db_path)
            print("\n테스트 DB 파일 삭제 완료")
        
        return True
        
    except sqlite3.Error as e:
        print(f"\n❌ SQLite 오류 발생: {e}")
        print(f"   오류 타입: {type(e).__name__}")
        
        # 오류가 'EXISTX' 관련인지 확인
        error_msg = str(e).lower()
        if 'existx' in error_msg or 'exist' in error_msg:
            print("\n⚠️  'EXISTX' 또는 'EXISTS' 관련 오류입니다!")
            print("   - 오타를 확인하세요: 'IF NOT EXISTX' → 'IF NOT EXISTS'")
            print("   - SQL 구문을 다시 확인하세요.")
        
        return False
        
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    import sys
    success = test_sqlite_syntax()
    sys.exit(0 if success else 1)

