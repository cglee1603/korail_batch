"""
Revision 관리 데이터베이스 모듈
문서 ID, document_key, revision을 SQLite에 저장하여 관리
"""
import sqlite3
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from logger import logger


class RevisionDB:
    """Revision 관리용 SQLite 데이터베이스"""
    
    def __init__(self, db_path: str = "./data/revision_management.db"):
        """
        Args:
            db_path: SQLite DB 파일 경로
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 문서 관리 테이블
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
            
            # 인덱스 생성
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_key 
                ON documents(document_key)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_dataset_id 
                ON documents(dataset_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_id 
                ON documents(document_id)
            """)
            
            conn.commit()
            conn.close()
            logger.info(f"Revision DB 초기화 완료: {self.db_path}")
        
        except Exception as e:
            logger.error(f"Revision DB 초기화 실패: {e}")
            raise
    
    # ==================== 테이블 관리 함수 (주의해서 사용) ====================
    
    def drop_table(self, confirm: bool = False) -> bool:
        """
        ⚠️ 위험: documents 테이블 삭제 (모든 데이터 손실)
        
        테이블을 잘못 생성했거나 스키마를 변경해야 할 때만 사용하세요.
        삭제 후 자동으로 재생성되지 않으므로 수동으로 _init_database()를 호출해야 합니다.
        
        Args:
            confirm: True로 설정해야만 실행됨 (실수 방지)
        
        Returns:
            성공 여부
        
        Example:
            # 주석을 해제하고 사용
            # db = RevisionDB()
            # db.drop_table(confirm=True)
            # db._init_database()  # 테이블 재생성
        """
        if not confirm:
            logger.warning("⚠️ drop_table(): confirm=True를 전달해야 실행됩니다.")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 테이블 삭제
            cursor.execute("DROP TABLE IF EXISTS documents")
            
            conn.commit()
            conn.close()
            
            logger.warning(f"⚠️ documents 테이블이 삭제되었습니다: {self.db_path}")
            return True
        
        except Exception as e:
            logger.error(f"테이블 삭제 실패: {e}")
            return False
    
    def get_document(self, document_key: str, dataset_id: str) -> Optional[Dict]:
        """
        문서 조회
        
        Args:
            document_key: 문서 고유 키
            dataset_id: 지식베이스 ID
        
        Returns:
            문서 정보 딕셔너리 또는 None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM documents 
                WHERE document_key = ? AND dataset_id = ?
            """, (document_key, dataset_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
        
        except Exception as e:
            logger.error(f"문서 조회 실패 (key: {document_key}): {e}")
            return None
    
    def save_document(
        self,
        document_key: str,
        document_id: str,
        dataset_id: str,
        dataset_name: str,
        revision: str = None,
        file_path: str = None,
        file_name: str = None
    ) -> bool:
        """
        문서 저장 또는 업데이트
        
        Args:
            document_key: 문서 고유 키
            document_id: RAGFlow 문서 ID
            dataset_id: 지식베이스 ID
            dataset_name: 지식베이스 이름
            revision: revision 값
            file_path: 파일 경로
            file_name: 파일 이름
        
        Returns:
            성공 여부
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # 기존 문서 확인
            existing = self.get_document(document_key, dataset_id)
            
            if existing:
                # 업데이트
                cursor.execute("""
                    UPDATE documents 
                    SET document_id = ?,
                        revision = ?,
                        file_path = ?,
                        file_name = ?,
                        updated_at = ?
                    WHERE document_key = ? AND dataset_id = ?
                """, (document_id, revision, file_path, file_name, now, document_key, dataset_id))
                logger.debug(f"문서 업데이트: {document_key} → {document_id} (revision: {revision})")
            else:
                # 신규 삽입
                cursor.execute("""
                    INSERT INTO documents 
                    (document_key, document_id, dataset_id, dataset_name, revision, 
                     file_path, file_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (document_key, document_id, dataset_id, dataset_name, revision,
                      file_path, file_name, now, now))
                logger.debug(f"문서 저장: {document_key} → {document_id} (revision: {revision})")
            
            conn.commit()
            conn.close()
            return True
        
        except Exception as e:
            logger.error(f"문서 저장 실패 (key: {document_key}): {e}")
            return False
    
    def delete_document(self, document_key: str, dataset_id: str) -> bool:
        """
        문서 삭제
        
        Args:
            document_key: 문서 고유 키
            dataset_id: 지식베이스 ID
        
        Returns:
            성공 여부
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM documents 
                WHERE document_key = ? AND dataset_id = ?
            """, (document_key, dataset_id))
            
            conn.commit()
            deleted_count = cursor.rowcount
            conn.close()
            
            if deleted_count > 0:
                logger.debug(f"문서 삭제: {document_key} (dataset: {dataset_id})")
                return True
            return False
        
        except Exception as e:
            logger.error(f"문서 삭제 실패 (key: {document_key}): {e}")
            return False
    
    def get_all_documents(self, dataset_id: str = None) -> List[Dict]:
        """
        모든 문서 조회 (선택적으로 dataset_id 필터링)
        
        Args:
            dataset_id: 지식베이스 ID (None이면 전체)
        
        Returns:
            문서 목록
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if dataset_id:
                cursor.execute("""
                    SELECT * FROM documents 
                    WHERE dataset_id = ?
                    ORDER BY updated_at DESC
                """, (dataset_id,))
            else:
                cursor.execute("""
                    SELECT * FROM documents 
                    ORDER BY updated_at DESC
                """)
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"문서 목록 조회 실패: {e}")
            return []
    
    def clear_dataset(self, dataset_id: str) -> int:
        """
        특정 지식베이스의 모든 문서 삭제
        
        Args:
            dataset_id: 지식베이스 ID
        
        Returns:
            삭제된 문서 수
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM documents 
                WHERE dataset_id = ?
            """, (dataset_id,))
            
            conn.commit()
            deleted_count = cursor.rowcount
            conn.close()
            
            logger.info(f"지식베이스 문서 삭제: {dataset_id} ({deleted_count}개)")
            return deleted_count
        
        except Exception as e:
            logger.error(f"지식베이스 문서 삭제 실패: {e}")
            return 0
    
    def get_statistics(self) -> Dict:
        """
        데이터베이스 통계
        
        Returns:
            통계 정보
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 총 문서 수
            cursor.execute("SELECT COUNT(*) FROM documents")
            total_docs = cursor.fetchone()[0]
            
            # 지식베이스별 문서 수
            cursor.execute("""
                SELECT dataset_name, COUNT(*) as count 
                FROM documents 
                GROUP BY dataset_name 
                ORDER BY count DESC
            """)
            datasets = cursor.fetchall()
            
            conn.close()
            
            return {
                'total_documents': total_docs,
                'datasets': [{'name': ds[0], 'count': ds[1]} for ds in datasets]
            }
        
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return {'total_documents': 0, 'datasets': []}

