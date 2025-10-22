"""
데이터베이스 연결 및 쿼리 실행 모듈
SQLAlchemy를 사용하여 다양한 DB 지원
"""
from typing import List, Dict, Optional
from pathlib import Path
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from logger import logger


class DBConnector:
    """범용 데이터베이스 연결 클래스"""
    
    # 지원하는 DB 드라이버
    SUPPORTED_DATABASES = {
        'postgresql': 'postgresql+psycopg2',
        'mysql': 'mysql+pymysql',
        'mssql': 'mssql+pyodbc',
        'oracle': 'oracle+cx_oracle',
        'sqlite': 'sqlite'
    }
    
    def __init__(self, connection_string: str = None, **kwargs):
        """
        DB 연결 초기화
        
        Args:
            connection_string: SQLAlchemy 연결 문자열
            **kwargs: 개별 연결 파라미터
                - db_type: 데이터베이스 타입 (postgresql, mysql, mssql, oracle, sqlite)
                - host: 호스트 주소
                - port: 포트 번호
                - database: 데이터베이스 이름
                - username: 사용자명
                - password: 비밀번호
                - driver: ODBC 드라이버 (MSSQL용)
        
        Examples:
            # 연결 문자열 사용
            connector = DBConnector("postgresql://user:pass@localhost:5432/dbname")
            
            # 개별 파라미터 사용
            connector = DBConnector(
                db_type='postgresql',
                host='localhost',
                port=5432,
                database='mydb',
                username='user',
                password='pass'
            )
        """
        self.engine: Optional[Engine] = None
        self.connection_string = connection_string
        
        if connection_string:
            self._connect_from_string(connection_string)
        elif kwargs:
            self._connect_from_params(**kwargs)
        else:
            logger.warning("DB 연결 정보가 제공되지 않았습니다.")
    
    def _connect_from_string(self, connection_string: str):
        """연결 문자열로 DB 연결"""
        try:
            logger.info(f"DB 연결 시도 (연결 문자열 사용)")
            # 비밀번호 마스킹
            safe_conn_str = self._mask_password(connection_string)
            logger.debug(f"연결 문자열: {safe_conn_str}")
            
            self.engine = create_engine(connection_string, echo=False)
            self._test_connection()
            logger.info("✓ DB 연결 성공")
        
        except Exception as e:
            logger.error(f"✗ DB 연결 실패: {e}")
            raise
    
    def _connect_from_params(
        self, 
        db_type: str,
        host: str = None,
        port: int = None,
        database: str = None,
        username: str = None,
        password: str = None,
        driver: str = None,
        **kwargs
    ):
        """개별 파라미터로 DB 연결"""
        try:
            logger.info(f"DB 연결 시도: {db_type}")
            
            # 데이터베이스 타입 확인
            if db_type.lower() not in self.SUPPORTED_DATABASES:
                raise ValueError(
                    f"지원하지 않는 DB 타입: {db_type}\n"
                    f"지원 목록: {', '.join(self.SUPPORTED_DATABASES.keys())}"
                )
            
            # 연결 문자열 생성
            connection_string = self._build_connection_string(
                db_type=db_type,
                host=host,
                port=port,
                database=database,
                username=username,
                password=password,
                driver=driver
            )
            
            self._connect_from_string(connection_string)
        
        except Exception as e:
            logger.error(f"✗ DB 연결 실패: {e}")
            raise
    
    def _build_connection_string(
        self,
        db_type: str,
        host: str = None,
        port: int = None,
        database: str = None,
        username: str = None,
        password: str = None,
        driver: str = None
    ) -> str:
        """연결 문자열 생성"""
        db_type_lower = db_type.lower()
        driver_prefix = self.SUPPORTED_DATABASES[db_type_lower]
        
        # SQLite는 특별 처리
        if db_type_lower == 'sqlite':
            return f"sqlite:///{database}"
        
        # MSSQL은 드라이버 지정 필요
        if db_type_lower == 'mssql':
            if not driver:
                driver = 'ODBC Driver 17 for SQL Server'
            driver_param = f"?driver={driver.replace(' ', '+')}"
            return f"{driver_prefix}://{username}:{password}@{host}:{port}/{database}{driver_param}"
        
        # 기타 DB
        return f"{driver_prefix}://{username}:{password}@{host}:{port}/{database}"
    
    def _mask_password(self, connection_string: str) -> str:
        """연결 문자열에서 비밀번호 마스킹"""
        try:
            if '://' in connection_string and '@' in connection_string:
                prefix, rest = connection_string.split('://', 1)
                if '@' in rest:
                    creds, server = rest.split('@', 1)
                    if ':' in creds:
                        user, _ = creds.split(':', 1)
                        return f"{prefix}://{user}:****@{server}"
            return connection_string
        except:
            return "***"
    
    def _test_connection(self):
        """연결 테스트"""
        if not self.engine:
            raise RuntimeError("DB 엔진이 초기화되지 않았습니다.")
        
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    
    def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        """
        SQL 쿼리 실행 및 결과 반환
        
        Args:
            query: SQL 쿼리문
            params: 쿼리 파라미터 (선택)
        
        Returns:
            결과 딕셔너리 리스트
        """
        if not self.engine:
            raise RuntimeError("DB가 연결되지 않았습니다.")
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                
                # 결과를 딕셔너리 리스트로 변환
                columns = result.keys()
                rows = []
                for row in result:
                    rows.append(dict(zip(columns, row)))
                
                logger.info(f"쿼리 실행 완료: {len(rows)}개 행 반환")
                return rows
        
        except Exception as e:
            logger.error(f"쿼리 실행 실패: {e}")
            logger.debug(f"쿼리: {query}")
            raise
    
    def execute_sql_file(self, sql_file_path: str, params: Dict = None) -> List[Dict]:
        """
        SQL 파일 읽어서 실행
        
        Args:
            sql_file_path: SQL 파일 경로
            params: 쿼리 파라미터 (선택)
        
        Returns:
            결과 딕셔너리 리스트
        """
        sql_path = Path(sql_file_path)
        
        if not sql_path.exists():
            raise FileNotFoundError(f"SQL 파일을 찾을 수 없습니다: {sql_file_path}")
        
        logger.info(f"SQL 파일 실행: {sql_path.name}")
        
        # UTF-8 인코딩으로 읽기 (BOM 제거)
        with open(sql_path, 'r', encoding='utf-8-sig') as f:
            query = f.read()
        
        if not query.strip():
            raise ValueError(f"SQL 파일이 비어있습니다: {sql_file_path}")
        
        return self.execute_query(query, params)
    
    def close(self):
        """DB 연결 종료"""
        if self.engine:
            self.engine.dispose()
            logger.info("DB 연결 종료")
    
    def __enter__(self):
        """컨텍스트 매니저 진입"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.close()

