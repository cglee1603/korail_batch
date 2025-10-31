"""
RevisionDB 관리 스크립트
테이블 삭제, 초기화, 정보 조회 등의 관리 작업을 수행합니다.

⚠️ 주의: 이 스크립트는 데이터를 삭제할 수 있습니다!
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from revision_db import RevisionDB


def show_menu():
    """메뉴 표시"""
    print("\n" + "="*60)
    print("RevisionDB 관리 메뉴")
    print("="*60)
    print("1. 테이블 정보 조회 (현재 상태)")
    print("2. 통계 조회 (문서 수)")
    print("3. 모든 문서 목록 조회")
    print("4. ⚠️  테이블 삭제 (DROP TABLE)")
    print("5. ⚠️  데이터베이스 초기화 (모든 데이터 삭제 + 재생성)")
    print("0. 종료")
    print("="*60)


def show_table_info(db: RevisionDB):
    """테이블 정보 표시"""
    print("\n📊 테이블 정보:")
    print("-"*60)
    
    info = db.get_table_info()
    
    if info.get('table_sql'):
        print("\n테이블 구조:")
        print(info['table_sql'])
    else:
        print("❌ 테이블이 존재하지 않습니다.")
        return
    
    if info.get('indexes'):
        print(f"\n인덱스 목록 ({len(info['indexes'])}개):")
        for idx in info['indexes']:
            print(f"  - {idx['name']}")
            if idx['sql']:
                print(f"    {idx['sql']}")
    else:
        print("\n인덱스가 없습니다.")


def show_statistics(db: RevisionDB):
    """통계 표시"""
    print("\n📈 통계:")
    print("-"*60)
    
    stats = db.get_statistics()
    print(f"총 문서 수: {stats.get('total_documents', 0)}")
    
    datasets = stats.get('datasets', [])
    if datasets:
        print(f"\n지식베이스별 문서 수:")
        for ds in datasets:
            print(f"  - {ds['name']}: {ds['count']}개")
    else:
        print("\n등록된 지식베이스가 없습니다.")


def show_all_documents(db: RevisionDB):
    """모든 문서 목록 표시"""
    print("\n📄 문서 목록:")
    print("-"*60)
    
    docs = db.get_all_documents()
    
    if not docs:
        print("등록된 문서가 없습니다.")
        return
    
    print(f"총 {len(docs)}개 문서:")
    for idx, doc in enumerate(docs, 1):
        print(f"\n{idx}. {doc['file_name']}")
        print(f"   - document_key: {doc['document_key']}")
        print(f"   - document_id: {doc['document_id']}")
        print(f"   - revision: {doc['revision']}")
        print(f"   - dataset: {doc['dataset_name']}")
        print(f"   - 수정일시: {doc['updated_at']}")


def drop_table_interactive(db: RevisionDB):
    """테이블 삭제 (대화형)"""
    print("\n⚠️  경고: 테이블 삭제")
    print("-"*60)
    print("이 작업은 documents 테이블을 완전히 삭제합니다.")
    print("모든 revision 이력이 손실됩니다!")
    print()
    
    confirm = input("정말로 삭제하시겠습니까? (yes 입력): ")
    
    if confirm.lower() != 'yes':
        print("❌ 취소되었습니다.")
        return
    
    print("\n테이블 삭제 중...")
    success = db.drop_table(confirm=True)
    
    if success:
        print("✅ 테이블이 삭제되었습니다.")
        print("⚠️  주의: 테이블을 다시 사용하려면 '5. 데이터베이스 초기화'를 실행하세요.")
    else:
        print("❌ 테이블 삭제에 실패했습니다.")


def reset_database_interactive(db: RevisionDB):
    """데이터베이스 초기화 (대화형)"""
    print("\n⚠️  경고: 데이터베이스 초기화")
    print("-"*60)
    print("이 작업은 모든 데이터를 삭제하고 깨끗한 상태로 초기화합니다.")
    print("모든 revision 이력이 손실됩니다!")
    print()
    
    confirm = input("정말로 초기화하시겠습니까? (yes 입력): ")
    
    if confirm.lower() != 'yes':
        print("❌ 취소되었습니다.")
        return
    
    print("\n데이터베이스 초기화 중...")
    success = db.reset_database(confirm=True)
    
    if success:
        print("✅ 데이터베이스가 초기화되었습니다.")
        print("   테이블이 새로 생성되었습니다.")
    else:
        print("❌ 데이터베이스 초기화에 실패했습니다.")


def main():
    """메인 함수"""
    print("="*60)
    print("RevisionDB 관리 도구")
    print("="*60)
    
    # DB 경로 설정
    db_path = "./data/revision_management.db"
    print(f"DB 경로: {db_path}")
    
    # DB 초기화 (파일이 없으면 생성)
    try:
        db = RevisionDB(db_path=db_path)
        print("✅ DB 연결 성공")
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return
    
    # 메뉴 루프
    while True:
        show_menu()
        
        try:
            choice = input("\n선택: ").strip()
            
            if choice == '0':
                print("\n종료합니다.")
                break
            
            elif choice == '1':
                show_table_info(db)
            
            elif choice == '2':
                show_statistics(db)
            
            elif choice == '3':
                show_all_documents(db)
            
            elif choice == '4':
                drop_table_interactive(db)
            
            elif choice == '5':
                reset_database_interactive(db)
            
            else:
                print("❌ 잘못된 선택입니다.")
        
        except KeyboardInterrupt:
            print("\n\n종료합니다.")
            break
        
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

