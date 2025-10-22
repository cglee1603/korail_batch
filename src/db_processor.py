"""
데이터베이스 쿼리 결과 처리 모듈
ExcelProcessor와 동일한 형식으로 데이터 변환
"""
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import json
from db_connector import DBConnector
from logger import logger
from config import (
    DB_SQL_FILE_PATH, 
    DB_CONTENT_COLUMNS,
    DB_METADATA_COLUMNS,
    TEMP_DIR
)


class DBProcessor:
    """데이터베이스 결과를 RAGFlow 형식으로 처리"""
    
    def __init__(self, connector: DBConnector, sql_file_path: str = None):
        """
        Args:
            connector: DBConnector 인스턴스
            sql_file_path: SQL 파일 경로 (기본값은 config에서 가져옴)
        """
        self.connector = connector
        self.sql_file_path = sql_file_path or DB_SQL_FILE_PATH
        self.stats = {
            'total_rows': 0,
            'content_conversions': 0,
            'skipped': 0
        }
    
    def process(self, query_name: str = "default") -> Dict[str, List[Dict]]:
        """
        SQL 파일 실행 및 결과 처리
        
        Args:
            query_name: 쿼리 이름 (지식베이스 이름으로 사용)
        
        Returns:
            Excel Processor와 동일한 형식의 딕셔너리
            {
                'query_name': [
                    {
                        'hyperlink': '파일경로 또는 생성된 파일경로',
                        'metadata': {...},
                        'row_number': 1
                    },
                    ...
                ]
            }
        """
        logger.info("="*80)
        logger.info("DB 쿼리 처리 시작")
        logger.info(f"SQL 파일: {self.sql_file_path}")
        logger.info("="*80)
        
        try:
            # SQL 파일 실행
            rows = self.connector.execute_sql_file(self.sql_file_path)
            self.stats['total_rows'] = len(rows)
            
            if not rows:
                logger.warning("쿼리 결과가 비어있습니다.")
                return {}
            
            logger.info(f"쿼리 결과: {len(rows)}개 행")
            
            # 컬럼 분석
            self._analyze_columns(rows[0])
            
            # 결과를 Excel 형식으로 변환
            items = []
            for idx, row in enumerate(rows, start=1):
                item = self._process_row(row, idx)
                if item:
                    items.append(item)
            
            logger.info(f"처리 완료: {len(items)}개 항목")
            self._print_statistics()
            
            return {query_name: items}
        
        except Exception as e:
            logger.error(f"DB 쿼리 처리 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}
    
    def _analyze_columns(self, sample_row: Dict):
        """컬럼 분석 및 로그 출력"""
        columns = list(sample_row.keys())
        logger.info(f"검색된 컬럼 ({len(columns)}개): {', '.join(columns)}")
        
        # 내용 컬럼 확인
        if DB_CONTENT_COLUMNS:
            found_content_cols = [col for col in DB_CONTENT_COLUMNS if col in columns]
            if found_content_cols:
                logger.info(f"✓ 내용 컬럼 발견: {', '.join(found_content_cols)}")
        else:
            logger.warning("DB_CONTENT_COLUMNS가 설정되지 않았습니다. 모든 컬럼을 JSON으로 변환합니다.")
        
        # 메타데이터 컬럼
        metadata_cols = self._get_metadata_columns(columns)
        logger.info(f"✓ 메타데이터 컬럼: {', '.join(metadata_cols) if metadata_cols else '(전체)'}")
    
    def _process_row(self, row: Dict, row_number: int) -> Optional[Dict]:
        """
        개별 행 처리 (방식 B: DB 내용을 텍스트 파일로 변환)
        
        Returns:
            {
                'hyperlink': '생성된 텍스트 파일 경로',
                'metadata': {...},
                'row_number': 1
            }
        """
        try:
            # 내용 컬럼이 설정된 경우 - 텍스트 파일 생성
            if DB_CONTENT_COLUMNS:
                content = self._build_content(row)
                if content:
                    file_path = self._create_text_file(row, content, row_number)
                    self.stats['content_conversions'] += 1
                    return {
                        'hyperlink': str(file_path),
                        'metadata': self._extract_metadata(row),
                        'row_number': row_number
                    }
            
            # 내용 컬럼이 없으면 모든 컬럼을 JSON으로 변환 (폴백)
            logger.debug(f"{row_number}행: DB_CONTENT_COLUMNS 미설정, JSON 변환")
            file_path = self._create_json_file(row, row_number)
            self.stats['content_conversions'] += 1
            return {
                'hyperlink': str(file_path),
                'metadata': self._extract_metadata(row),
                'row_number': row_number
            }
        
        except Exception as e:
            logger.error(f"{row_number}행 처리 실패: {e}")
            self.stats['skipped'] += 1
            return None
    
    def _extract_metadata(self, row: Dict) -> Dict[str, str]:
        """메타데이터 추출"""
        metadata = {}
        
        # 특정 메타데이터 컬럼이 설정된 경우
        if DB_METADATA_COLUMNS:
            for col in DB_METADATA_COLUMNS:
                if col in row and row[col] is not None:
                    # datetime 객체는 문자열로 변환
                    value = row[col]
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    metadata[col] = str(value)
        else:
            # 모든 컬럼을 메타데이터로 사용 (내용 컬럼 제외)
            for key, value in row.items():
                # 내용 컬럼은 메타데이터에서 제외
                if DB_CONTENT_COLUMNS and key in DB_CONTENT_COLUMNS:
                    continue
                if value is not None:
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    metadata[key] = str(value)
        
        # DB 소스 표시
        metadata['데이터_소스'] = 'Database'
        
        return metadata
    
    def _get_metadata_columns(self, all_columns: List[str]) -> List[str]:
        """메타데이터로 사용할 컬럼 목록 반환"""
        if DB_METADATA_COLUMNS:
            return [col for col in DB_METADATA_COLUMNS if col in all_columns]
        else:
            # 내용 컬럼 제외한 모든 컬럼
            exclude = set()
            if DB_CONTENT_COLUMNS:
                exclude.update(DB_CONTENT_COLUMNS)
            return [col for col in all_columns if col not in exclude]
    
    def _build_content(self, row: Dict) -> Optional[str]:
        """내용 컬럼들을 하나의 텍스트로 결합"""
        if not DB_CONTENT_COLUMNS:
            return None
        
        content_parts = []
        for col in DB_CONTENT_COLUMNS:
            if col in row and row[col]:
                value = row[col]
                content_parts.append(f"## {col}\n{value}")
        
        return "\n\n".join(content_parts) if content_parts else None
    
    def _create_text_file(self, row: Dict, content: str, row_number: int) -> Path:
        """DB 내용을 텍스트 파일로 생성"""
        # 파일명 생성 (첫 번째 컬럼 값 사용 또는 행 번호)
        first_col = list(row.keys())[0]
        first_value = str(row[first_col])[:50]  # 최대 50자
        
        # 파일명에 사용 불가능한 문자 제거
        safe_filename = "".join(c for c in first_value if c.isalnum() or c in (' ', '-', '_'))
        safe_filename = safe_filename.strip() or f"row_{row_number}"
        
        # 파일 생성
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"db_{safe_filename}_{timestamp}.txt"
        file_path = TEMP_DIR / filename
        
        # UTF-8로 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.debug(f"텍스트 파일 생성: {filename}")
        return file_path
    
    def _create_json_file(self, row: Dict, row_number: int) -> Path:
        """DB 행을 JSON 파일로 생성"""
        # datetime 객체 변환
        serializable_row = {}
        for key, value in row.items():
            if isinstance(value, datetime):
                serializable_row[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            elif value is None:
                serializable_row[key] = ""
            else:
                serializable_row[key] = str(value)
        
        # 파일 생성
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"db_row_{row_number}_{timestamp}.json"
        file_path = TEMP_DIR / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_row, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"JSON 파일 생성: {filename}")
        return file_path
    
    def _print_statistics(self):
        """처리 통계 출력"""
        logger.info("-"*80)
        logger.info("DB 처리 통계")
        logger.info(f"  총 행 수: {self.stats['total_rows']}")
        logger.info(f"  텍스트 변환: {self.stats['content_conversions']}")
        logger.info(f"  건너뜀: {self.stats['skipped']}")
        logger.info("-"*80)

