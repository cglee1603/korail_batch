"""
RevisionDB 테이블 삭제/초기화 예제
필요할 때 주석을 해제하여 사용하세요.

⚠️ 주의: 모든 revision 이력이 삭제됩니다!
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from revision_db import RevisionDB


def example_drop_table():
    """예제 1: 테이블만 삭제 (수동 재생성 필요)"""
    print("="*60)
    print("예제 1: 테이블 삭제")
    print("="*60)
    
    db = RevisionDB()
    
    # ⚠️ 주석을 해제하여 실행
    # success = db.drop_table(confirm=True)
    # if success:
    #     print("✅ 테이블이 삭제되었습니다.")
    #     print("테이블을 다시 생성하려면 db._init_database()를 호출하세요.")
    # else:
    #     print("❌ 테이블 삭제 실패")
    
    print("⚠️  주석 처리되어 실행되지 않았습니다.")
    print("   실행하려면 코드에서 주석을 제거하세요.")


def example_reset_database():
    """예제 2: 데이터베이스 완전 초기화 (삭제 + 재생성)"""
    print("\n" + "="*60)
    print("예제 2: 데이터베이스 초기화")
    print("="*60)
    
    db = RevisionDB()
    
    # ⚠️ 주석을 해제하여 실행
    # success = db.reset_database(confirm=True)
    # if success:
    #     print("✅ 데이터베이스가 초기화되었습니다.")
    #     print("   모든 데이터가 삭제되고 깨끗한 테이블이 생성되었습니다.")
    # else:
    #     print("❌ 데이터베이스 초기화 실패")
    
    print("⚠️  주석 처리되어 실행되지 않았습니다.")
    print("   실행하려면 코드에서 주석을 제거하세요.")


def example_check_table_info():
    """예제 3: 테이블 정보 조회 (안전)"""
    print("\n" + "="*60)
    print("예제 3: 테이블 정보 조회")
    print("="*60)
    
    db = RevisionDB()
    
    # 테이블 정보 조회 (안전한 작업)
    info = db.get_table_info()
    
    if info.get('table_sql'):
        print("\n✅ 테이블이 존재합니다.")
        print("\n테이블 구조:")
        print(info['table_sql'])
        
        print(f"\n인덱스 ({len(info.get('indexes', []))}개):")
        for idx in info.get('indexes', []):
            print(f"  - {idx['name']}")
    else:
        print("\n❌ 테이블이 존재하지 않습니다.")
    
    # 통계 조회
    stats = db.get_statistics()
    print(f"\n총 문서 수: {stats.get('total_documents', 0)}")


def example_interactive():
    """예제 4: 대화형 삭제 (안전)"""
    print("\n" + "="*60)
    print("예제 4: 대화형 데이터베이스 초기화")
    print("="*60)
    
    db = RevisionDB()
    
    print("\n현재 데이터베이스를 초기화하시겠습니까?")
    print("⚠️  모든 revision 이력이 삭제됩니다!")
    
    answer = input("\n계속하려면 'yes'를 입력하세요 (다른 입력 시 취소): ")
    
    if answer.lower() == 'yes':
        # ⚠️ 주석을 해제하여 실행
        # success = db.reset_database(confirm=True)
        # if success:
        #     print("✅ 데이터베이스가 초기화되었습니다.")
        # else:
        #     print("❌ 초기화 실패")
        
        print("⚠️  주석 처리되어 실행되지 않았습니다.")
        print("   실행하려면 코드에서 주석을 제거하세요.")
    else:
        print("❌ 취소되었습니다.")


# ============================================================
# 직접 실행 예제 (주석 해제하여 사용)
# ============================================================

def quick_reset():
    """
    빠른 초기화 - 이 함수만 주석 해제하고 실행하면 됩니다.
    """
    # ⚠️ 아래 주석을 모두 해제하여 실행
    
    # from revision_db import RevisionDB
    # 
    # print("="*60)
    # print("⚠️  RevisionDB 초기화")
    # print("="*60)
    # print("\n모든 revision 이력이 삭제됩니다!")
    # 
    # confirm = input("\n정말로 초기화하시겠습니까? (yes 입력): ")
    # 
    # if confirm.lower() == 'yes':
    #     db = RevisionDB()
    #     success = db.reset_database(confirm=True)
    #     
    #     if success:
    #         print("\n✅ 초기화 완료!")
    #     else:
    #         print("\n❌ 초기화 실패!")
    # else:
    #     print("\n❌ 취소되었습니다.")
    
    print("⚠️  주석 처리되어 실행되지 않았습니다.")
    print("\n사용 방법:")
    print("1. 이 파일을 편집기로 열기")
    print("2. quick_reset() 함수 내부의 주석 제거")
    print("3. 파일 저장 후 다시 실행")


if __name__ == "__main__":
    print("\n🔧 RevisionDB 관리 예제 스크립트\n")
    
    # 안전한 예제 (항상 실행됨)
    example_check_table_info()
    
    # 위험한 예제 (주석 처리됨)
    print("\n" + "="*60)
    example_drop_table()
    example_reset_database()
    example_interactive()
    
    print("\n" + "="*60)
    print("빠른 초기화")
    print("="*60)
    quick_reset()
    
    print("\n" + "="*60)
    print("💡 관리 도구 사용:")
    print("   python scripts/manage_revision_db.py")
    print("="*60)

