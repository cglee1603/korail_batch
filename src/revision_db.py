"""
Revision 관리 데이터베이스 모듈
문서 ID, document_key, revision을 PostgreSQL에 저장하여 관리
"""
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from typing import Any, Optional, Dict, List
from datetime import datetime
from logger import logger
import os
from urllib.parse import urlparse, parse_qs, unquote


class RevisionDB:
    """Revision 관리용 PostgreSQL 데이터베이스"""
    
    def __init__(self, connection_string: str = None):
        """
        Args:
            connection_string: PostgreSQL 연결 문자열
                예: postgresql://user:password@localhost:5432/ragflow_revision
        """
        if connection_string is None:
            # config.py에서 가져오기
            from config import REVISION_DB_CONNECTION_STRING
            connection_string = REVISION_DB_CONNECTION_STRING
        
        self.connection_string = connection_string
        self._parse_connection_string()
        self._init_connection_pool()
        self._init_database()
    
    def _parse_connection_string(self):
        """연결 문자열 파싱"""
        try:
            parsed = urlparse(self.connection_string)
            query_params = parse_qs(parsed.query) if parsed.query else {}

            self.db_config = {
                'host': parsed.hostname,
                'port': parsed.port or 5432,
                'database': parsed.path[1:] if parsed.path else 'ragflow_revision',
                # 사용자/비밀번호는 퍼센트 인코딩 해제하여 원문으로 전달
                'user': unquote(parsed.username) if parsed.username is not None else None,
                'password': unquote(parsed.password) if parsed.password is not None else None
            }

            # 연결 문자열의 ?options= 값 반영 (예: options=-csearch_path%3Dschema)
            if 'options' in query_params and query_params['options']:
                self.db_config['options'] = query_params['options'][0]

            # 환경변수로 스키마 지정 시 search_path 설정 (연결문자열 옵션보다 낮은 우선순위)
            # 예: REVISION_DB_SCHEMA=my_schema
            schema = os.getenv("REVISION_DB_SCHEMA")
            if schema and 'options' not in self.db_config:
                # psycopg2 옵션 문자열: '-c search_path=my_schema'
                self.db_config['options'] = f"-c search_path={schema}"

            # 타겟 스키마명 보관 (환경변수 우선, 없으면 options에서 search_path의 첫 번째 스키마 추출)
            self.schema_name = None
            if schema:
                self.schema_name = schema
            else:
                options = self.db_config.get('options') or ""
                key = "search_path="
                idx = options.find(key)
                if idx != -1:
                    rest = options[idx + len(key):].strip()
                    # 공백/세미콜론 전까지
                    for sep in [' ', ';']:
                        pos = rest.find(sep)
                        if pos != -1:
                            rest = rest[:pos]
                            break
                    # 첫 번째 스키마만 사용
                    first_schema = (rest.strip().strip('"').split(',')[0]).strip()
                    if first_schema:
                        self.schema_name = first_schema
        except Exception as e:
            logger.error(f"연결 문자열 파싱 실패: {e}")
            raise
    
    def _init_connection_pool(self):
        """연결 풀 초기화"""
        try:
            self.connection_pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                **self.db_config
            )
            logger.info(f"PostgreSQL 연결 풀 초기화 완료: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
        except Exception as e:
            logger.error(f"PostgreSQL 연결 풀 초기화 실패: {e}")
            raise
    
    def _get_connection(self):
        """연결 풀에서 연결 가져오기"""
        return self.connection_pool.getconn()
    
    def _put_connection(self, conn):
        """연결을 풀에 반환"""
        self.connection_pool.putconn(conn)
    
    def _init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        conn = None
        try:
            conn = self._get_connection()
            # DDL 실행을 위해 autocommit 모드 설정
            conn.autocommit = True
            cursor = conn.cursor()
            
            def qualified(table_name: str):
                if getattr(self, 'schema_name', None):
                    return sql.SQL('.').join([sql.Identifier(self.schema_name), sql.Identifier(table_name)])
                return sql.Identifier(table_name)

            # 문서 관리 테이블
            cursor.execute(
                sql.SQL("""
                    CREATE TABLE IF NOT EXISTS {} (
                        id SERIAL PRIMARY KEY,
                        document_key TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        file_id TEXT,
                        dataset_id TEXT NOT NULL,
                        dataset_name TEXT NOT NULL,
                        revision TEXT,
                        file_path TEXT,
                        file_name TEXT,
                        file_hash TEXT,
                        is_part_of_archive BOOLEAN DEFAULT FALSE,
                        archive_source TEXT,
                        created_at TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP NOT NULL,
                        UNIQUE(document_key, dataset_id, file_name)
                    )
                """).format(qualified('documents'))
            )
            
            # 다운로드 캐시 테이블
            cursor.execute(
                sql.SQL("""
                    CREATE TABLE IF NOT EXISTS {} (
                        id SERIAL PRIMARY KEY,
                        url TEXT NOT NULL UNIQUE,
                        file_path TEXT NOT NULL,
                        file_size BIGINT,
                        downloaded_at TIMESTAMP NOT NULL,
                        last_accessed TIMESTAMP NOT NULL
                    )
                """).format(qualified('download_cache'))
            )
            
            # 처리된 URL 테이블 (Revision 관리 안하는 시트용)
            cursor.execute(
                sql.SQL("""
                    CREATE TABLE IF NOT EXISTS {} (
                        id SERIAL PRIMARY KEY,
                        url TEXT NOT NULL UNIQUE,
                        processed_at TIMESTAMP NOT NULL
                    )
                """).format(qualified('processed_urls'))
            )
            
            # 인덱스 생성
            cursor.execute(
                sql.SQL("""
                    CREATE INDEX IF NOT EXISTS idx_document_key 
                    ON {}(document_key)
                """).format(qualified('documents'))
            )
            
            cursor.execute(
                sql.SQL("""
                    CREATE INDEX IF NOT EXISTS idx_dataset_id 
                    ON {}(dataset_id)
                """).format(qualified('documents'))
            )
            
            cursor.execute(
                sql.SQL("""
                    CREATE INDEX IF NOT EXISTS idx_document_id 
                    ON {}(document_id)
                """).format(qualified('documents'))
            )
            
            cursor.execute(
                sql.SQL("""
                    CREATE INDEX IF NOT EXISTS idx_download_url 
                    ON {}(url)
                """).format(qualified('download_cache'))
            )
            
            cursor.execute(
                sql.SQL("""
                    CREATE INDEX IF NOT EXISTS idx_processed_url 
                    ON {}(url)
                """).format(qualified('processed_urls'))
            )
            
            # 기존 테이블에 file_id 컬럼 추가 (마이그레이션)
            try:
                cursor.execute(
                    sql.SQL("""
                        ALTER TABLE {} 
                        ADD COLUMN IF NOT EXISTS file_id TEXT
                    """).format(qualified('documents'))
                )
                logger.debug("file_id 컬럼 추가/확인 완료")
            except Exception as e:
                logger.debug(f"file_id 컬럼 추가 시도 중 오류 (이미 존재할 수 있음): {e}")

            # 기존 테이블에 file_hash 컬럼 추가 (마이그레이션)
            try:
                cursor.execute(
                    sql.SQL("""
                        ALTER TABLE {} 
                        ADD COLUMN IF NOT EXISTS file_hash TEXT
                    """).format(qualified('documents'))
                )
                logger.debug("file_hash 컬럼 추가/확인 완료")
            except Exception as e:
                logger.debug(f"file_hash 컬럼 추가 시도 중 오류 (이미 존재할 수 있음): {e}")
            
            logger.info(f"Revision DB 초기화 완료: {self.db_config['database']}")
        
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Revision DB 초기화 실패: {e}")
            raise
        finally:
            if conn:
                try:
                    conn.autocommit = False
                except:
                    pass
                cursor.close()
                self._put_connection(conn)
    
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
        
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 테이블 삭제
            if getattr(self, 'schema_name', None):
                cursor.execute(
                    sql.SQL("DROP TABLE IF EXISTS {}").format(
                        sql.SQL('.').join([sql.Identifier(self.schema_name), sql.Identifier('documents')])
                    )
                )
            else:
                cursor.execute("DROP TABLE IF EXISTS documents")
            
            conn.commit()
            
            logger.warning(f"⚠️ documents 테이블이 삭제되었습니다: {self.db_config['database']}")
            return True
        
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"테이블 삭제 실패: {e}")
            return False
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
     
    def get_document(self, document_key: str, dataset_id: str, file_name: str = None) -> Optional[Dict]:
        """
        문서 조회
        
        Args:
            document_key: 문서 고유 키
            dataset_id: 지식베이스 ID
            file_name: 파일명 (None이면 첫 번째 매칭 반환)
        
        Returns:
            문서 정보 딕셔너리 또는 None
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if file_name:
                cursor.execute("""
                    SELECT * FROM documents 
                    WHERE document_key = %s AND dataset_id = %s AND file_name = %s
                """, (document_key, dataset_id, file_name))
            else:
                cursor.execute("""
                    SELECT * FROM documents 
                    WHERE document_key = %s AND dataset_id = %s
                    ORDER BY created_at ASC
                    LIMIT 1
                """, (document_key, dataset_id))
            
            row = cursor.fetchone()
            
            if row:
                return dict[Any, Any](row)
            return None
        
        except Exception as e:
            logger.error(f"문서 조회 실패 (key: {document_key}): {e}")
            return None
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
    
    def get_documents_by_key(self, document_key: str, dataset_id: str) -> List[Dict]:
        """
        동일한 document_key를 가진 모든 문서 조회 (압축 파일 등)
        
        Args:
            document_key: 문서 고유 키
            dataset_id: 지식베이스 ID
        
        Returns:
            문서 목록
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM documents 
                WHERE document_key = %s AND dataset_id = %s
                ORDER BY created_at ASC
            """, (document_key, dataset_id))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"문서 목록 조회 실패 (key: {document_key}): {e}")
            return []
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
    
    def save_document(
        self,
        document_key: str,
        document_id: str,
        dataset_id: str,
        dataset_name: str,
        revision: str = None,
        file_path: str = None,
        file_name: str = None,
        file_id: str = None,
        file_hash: str = None,
        is_part_of_archive: bool = False,
        archive_source: str = None
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
            file_id: RAGFlow 파일 ID (업로드된 파일 삭제용)
            file_hash: 파일 해시 (변경 감지용)
            is_part_of_archive: 압축 파일의 일부인지 여부
            archive_source: 원본 압축 파일명
        
        Returns:
            성공 여부
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now()
            
            # 기존 문서 확인 (file_name까지 포함)
            existing = self.get_document(document_key, dataset_id, file_name)
            
            if existing:
                # 업데이트
                cursor.execute("""
                    UPDATE documents 
                    SET document_id = %s,
                        file_id = %s,
                        revision = %s,
                        file_path = %s,
                        file_hash = %s,
                        is_part_of_archive = %s,
                        archive_source = %s,
                        updated_at = %s
                    WHERE document_key = %s AND dataset_id = %s AND file_name = %s
                """, (document_id, file_id, revision, file_path, file_hash, is_part_of_archive, archive_source, 
                      now, document_key, dataset_id, file_name))
                logger.debug(f"문서 업데이트: {document_key}/{file_name} → {document_id}")
            else:
                # 신규 삽입
                cursor.execute("""
                    INSERT INTO documents 
                    (document_key, document_id, file_id, dataset_id, dataset_name, revision, 
                     file_path, file_name, file_hash, is_part_of_archive, archive_source, 
                     created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (document_key, document_id, file_id, dataset_id, dataset_name, revision,
                      file_path, file_name, file_hash, is_part_of_archive, archive_source, now, now))
                logger.debug(f"문서 저장: {document_key}/{file_name} → {document_id}")
            
            conn.commit()
            return True
        
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"문서 저장 실패 (key: {document_key}, file: {file_name}): {e}")
            return False
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
    
    def delete_document(self, document_key: str, dataset_id: str, file_name: str = None) -> int:
        """
        문서 삭제
        
        Args:
            document_key: 문서 고유 키
            dataset_id: 지식베이스 ID
            file_name: 파일명 (None이면 해당 키의 모든 파일 삭제)
        
        Returns:
            삭제된 문서 수
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if file_name:
                cursor.execute("""
                    DELETE FROM documents 
                    WHERE document_key = %s AND dataset_id = %s AND file_name = %s
                """, (document_key, dataset_id, file_name))
            else:
                cursor.execute("""
                    DELETE FROM documents 
                    WHERE document_key = %s AND dataset_id = %s
                """, (document_key, dataset_id))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                if file_name:
                    logger.debug(f"문서 삭제: {document_key}/{file_name}")
                else:
                    logger.debug(f"문서 삭제: {document_key} ({deleted_count}개 파일)")
                return deleted_count
            return 0
        
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"문서 삭제 실패 (key: {document_key}): {e}")
            return 0
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
    
    def get_all_documents(self, dataset_id: str = None) -> List[Dict]:
        """
        모든 문서 조회 (선택적으로 dataset_id 필터링)
        
        Args:
            dataset_id: 지식베이스 ID (None이면 전체)
        
        Returns:
            문서 목록
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if dataset_id:
                cursor.execute("""
                    SELECT * FROM documents 
                    WHERE dataset_id = %s
                    ORDER BY updated_at DESC
                """, (dataset_id,))
            else:
                cursor.execute("""
                    SELECT * FROM documents 
                    ORDER BY updated_at DESC
                """)
            
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"문서 목록 조회 실패: {e}")
            return []
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
    
    def get_documents_by_dataset_name(self, dataset_name: str) -> List[Dict]:
        """
        dataset_name으로 모든 문서 조회
        
        Args:
            dataset_name: 지식베이스 이름
        
        Returns:
            문서 목록 [{'document_id': 'xxx', 'file_name': 'yyy', ...}, ...]
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM documents 
                WHERE dataset_name = %s
                ORDER BY updated_at DESC
            """, (dataset_name,))
            
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"dataset_name으로 문서 조회 실패 ({dataset_name}): {e}")
            return []
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
    
    def clear_dataset(self, dataset_id: str) -> int:
        """
        특정 지식베이스의 모든 문서 삭제
        
        Args:
            dataset_id: 지식베이스 ID
        
        Returns:
            삭제된 문서 수
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM documents 
                WHERE dataset_id = %s
            """, (dataset_id,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"지식베이스 문서 삭제: {dataset_id} ({deleted_count}개)")
            return deleted_count
        
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"지식베이스 문서 삭제 실패: {e}")
            return 0
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
    
    def get_statistics(self) -> Dict:
        """
        데이터베이스 통계
        
        Returns:
            통계 정보
        """
        conn = None
        try:
            conn = self._get_connection()
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
            
            # 다운로드 캐시 통계
            try:
                cursor.execute("SELECT COUNT(*) FROM download_cache")
                cached_downloads = cursor.fetchone()[0]
            except:
                cached_downloads = 0
            
            return {
                'total_documents': total_docs,
                'datasets': [{'name': ds[0], 'count': ds[1]} for ds in datasets],
                'cached_downloads': cached_downloads
            }
        
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return {'total_documents': 0, 'datasets': [], 'cached_downloads': 0}
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
    
    # ==================== 다운로드 캐시 관리 ====================
    
    def get_cached_download(self, url: str) -> Optional[Dict]:
        """
        다운로드 캐시 조회
        
        Args:
            url: 다운로드 URL
        
        Returns:
            캐시 정보 딕셔너리 또는 None
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM download_cache 
                WHERE url = %s
            """, (url,))
            
            row = cursor.fetchone()
            
            if row:
                # 마지막 접근 시간 업데이트
                now = datetime.now()
                cursor.execute("""
                    UPDATE download_cache 
                    SET last_accessed = %s
                    WHERE url = %s
                """, (now, url))
                conn.commit()
                
                return dict(row)
            return None
        
        except Exception as e:
            logger.debug(f"다운로드 캐시 조회 실패: {e}")
            return None
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
    
    def save_download_cache(
        self,
        url: str,
        file_path: str,
        file_size: int = None
    ) -> bool:
        """
        다운로드 캐시 저장
        
        Args:
            url: 다운로드 URL
            file_path: 저장된 파일 경로
            file_size: 파일 크기 (bytes)
        
        Returns:
            성공 여부
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now()
            
            # 기존 캐시 확인
            cursor.execute("""
                SELECT id FROM download_cache WHERE url = %s
            """, (url,))
            
            existing = cursor.fetchone()
            
            if existing:
                # 업데이트
                cursor.execute("""
                    UPDATE download_cache 
                    SET file_path = %s,
                        file_size = %s,
                        downloaded_at = %s,
                        last_accessed = %s
                    WHERE url = %s
                """, (file_path, file_size, now, now, url))
                logger.debug(f"다운로드 캐시 업데이트: {url}")
            else:
                # 신규 삽입
                cursor.execute("""
                    INSERT INTO download_cache 
                    (url, file_path, file_size, downloaded_at, last_accessed)
                    VALUES (%s, %s, %s, %s, %s)
                """, (url, file_path, file_size, now, now))
                logger.debug(f"다운로드 캐시 저장: {url}")
            
            conn.commit()
            return True
        
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"다운로드 캐시 저장 실패: {e}")
            return False
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
    
    def clear_download_cache(self, older_than_days: int = None) -> int:
        """
        다운로드 캐시 정리
        
        Args:
            older_than_days: 지정된 일수보다 오래된 캐시만 삭제 (None이면 전체 삭제)
        
        Returns:
            삭제된 캐시 수
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if older_than_days:
                cursor.execute("""
                    DELETE FROM download_cache 
                    WHERE last_accessed < NOW() - INTERVAL '%s days'
                """, (older_than_days,))
            else:
                cursor.execute("DELETE FROM download_cache")
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"다운로드 캐시 정리: {deleted_count}개 삭제")
            return deleted_count
        
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"다운로드 캐시 정리 실패: {e}")
            return 0
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)

    # ==================== 처리된 URL 관리 (Revision 관리 안함용) ====================

    def is_url_processed(self, url: str) -> bool:
        """
        URL 처리 여부 확인
        
        Args:
            url: 확인 할 URL
            
        Returns:
            이미 처리되었으면 True
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT 1 FROM processed_urls WHERE url = %s", (url,))
            return cursor.fetchone() is not None
        
        except Exception as e:
            logger.error(f"URL 처리 여부 확인 실패: {e}")
            return False
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)

    def add_processed_url(self, url: str) -> bool:
        """
        처리된 URL 추가
        
        Args:
            url: 추가할 URL
            
        Returns:
            성공 여부
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO processed_urls (url, processed_at)
                VALUES (%s, %s)
                ON CONFLICT (url) DO NOTHING
            """, (url, datetime.now()))
            
            conn.commit()
            return True
        
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"URL 추가 실패: {e}")
            return False
        finally:
            if conn:
                cursor.close()
                self._put_connection(conn)
    
    def close(self):
        """연결 풀 종료"""
        if hasattr(self, 'connection_pool') and self.connection_pool:
            self.connection_pool.closeall()
            logger.info("PostgreSQL 연결 풀 종료")
