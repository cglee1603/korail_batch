"""
DB 마이그레이션 모듈 (MySQL → PostgreSQL)

두 테이블을 마이그레이션하고, 특정 컬럼(matnr)을 파싱하여
정규화된 자재 사용 테이블(mt_material_usage)을 생성합니다.

데이터 흐름:
  [MySQL] eai_mt_zspmt_aibot_equip_error_monit
      ├─ (matnr 제외) ──→ [PG] mt_zspmt_aibot_equip_error_monit
      └─ order_no + matnr 파싱 ──→ [PG] mt_material_usage

  [MySQL] eai_mt_zspmt_aibot_material_master
      └─ 전체 ──→ [PG] mt_zspmt_aibot_material_master
"""
import json
import os
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    create_engine, text, inspect,
    MetaData, Table, Column,
    String, Integer, BigInteger, SmallInteger, Float,
    Numeric, Text, Boolean, DateTime, Date, Time, LargeBinary,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from logger import logger


MYSQL_TO_SA_TYPE = {
    'tinyint':    SmallInteger,
    'smallint':   SmallInteger,
    'mediumint':  Integer,
    'int':        Integer,
    'integer':    Integer,
    'bigint':     BigInteger,
    'float':      Float,
    'double':     Float,
    'decimal':    Numeric,
    'numeric':    Numeric,
    'varchar':    String,
    'char':       String,
    'text':       Text,
    'tinytext':   Text,
    'mediumtext': Text,
    'longtext':   Text,
    'blob':       LargeBinary,
    'tinyblob':   LargeBinary,
    'mediumblob': LargeBinary,
    'longblob':   LargeBinary,
    'datetime':   DateTime,
    'timestamp':  DateTime,
    'date':       Date,
    'time':       Time,
    'boolean':    Boolean,
    'bool':       Boolean,
    'json':       JSONB,
    'enum':       String,
    'set':        Text,
}


class DBMigrator:
    """MySQL → PostgreSQL 데이터 마이그레이션"""

    def __init__(
        self,
        source_conn_str: str,
        target_conn_str: str,
        batch_size: int = 1000,
        test_limit: int = 0,
    ):
        self.source_engine: Engine = create_engine(source_conn_str, echo=False)
        self.target_engine: Engine = create_engine(target_conn_str, echo=False)
        self.batch_size = batch_size
        self.test_limit = test_limit
        self.stats: Dict[str, Any] = {}
        if self.test_limit > 0:
            logger.info(f"[테스트 모드] 테이블당 최대 {self.test_limit}행만 추출")

    # ==================== 연결 / 유틸리티 ====================

    def _test_connections(self):
        with self.source_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("소스 DB(MySQL) 연결 성공")

        with self.target_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("대상 DB(PostgreSQL) 연결 성공")

    @staticmethod
    def parse_table_mapping(table_spec: str) -> Tuple[str, str]:
        """'source:target' 또는 'table' 형식을 (source, target) 튜플로 변환"""
        if ':' in table_spec:
            src, tgt = table_spec.split(':', 1)
            return src.strip(), tgt.strip()
        name = table_spec.strip()
        return name, name

    @staticmethod
    def load_exclude_columns(file_path: str) -> Dict[str, List[str]]:
        """
        제외 컬럼 설정 파일 로드

        Args:
            file_path: JSON 파일 경로
                형식: { "소스테이블명": ["컬럼1", "컬럼2"], ... }

        Returns:
            테이블명 → 제외 컬럼 리스트 딕셔너리
        """
        if not file_path or not os.path.isfile(file_path):
            logger.debug(f"제외 컬럼 파일 없음 또는 미지정: {file_path}")
            return {}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"제외 컬럼 파일 로드 실패: {file_path} ({e})")
            return {}

        result: Dict[str, List[str]] = {}
        for table_name, columns in data.items():
            if table_name.startswith('_'):
                continue
            if isinstance(columns, list) and columns:
                result[table_name] = [str(c) for c in columns]

        if result:
            logger.info(
                f"제외 컬럼 로드: {file_path} "
                f"({sum(len(v) for v in result.values())}개 컬럼, "
                f"{len(result)}개 테이블)"
            )
        return result

    @staticmethod
    def parse_material_config(config_str: str) -> Optional[Dict[str, str]]:
        """
        자재 파싱 설정 문자열을 딕셔너리로 변환

        형식: '소스테이블:파싱컬럼:키컬럼:대상테이블'
        반환: {'source_table', 'parse_column', 'key_column', 'target_table'}
        """
        if not config_str or not config_str.strip():
            return None
        parts = config_str.strip().split(':')
        if len(parts) != 4:
            logger.warning(
                f"자재 파싱 설정 형식 오류: '{config_str}' "
                f"(올바른 형식: 소스테이블:파싱컬럼:키컬럼:대상테이블)"
            )
            return None
        return {
            'source_table': parts[0].strip(),
            'parse_column': parts[1].strip(),
            'key_column': parts[2].strip(),
            'target_table': parts[3].strip(),
        }

    def _serialize_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        return value

    def _transform_rows(self, rows: List[Dict]) -> List[Dict]:
        return [
            {k: self._serialize_value(v) for k, v in row.items()}
            for row in rows
        ]

    # ==================== 소스 스키마 분석 ====================

    def _get_source_columns(self, table_name: str) -> List[Dict]:
        insp = inspect(self.source_engine)
        columns = insp.get_columns(table_name)
        pk_cols = insp.get_pk_constraint(table_name).get('constrained_columns', [])
        for col in columns:
            col['is_pk'] = col['name'] in pk_cols
        return columns

    def _resolve_sa_type(self, col_info: Dict) -> Any:
        sa_type = col_info.get('type')
        type_name = type(sa_type).__name__.lower() if sa_type else 'text'

        for mysql_type, sa_cls in MYSQL_TO_SA_TYPE.items():
            if mysql_type in type_name:
                if sa_cls is String and hasattr(sa_type, 'length') and sa_type.length:
                    return sa_cls(sa_type.length)
                if sa_cls is Numeric and hasattr(sa_type, 'precision'):
                    return sa_cls(
                        precision=getattr(sa_type, 'precision', None),
                        scale=getattr(sa_type, 'scale', None),
                    )
                return sa_cls()

        return Text()

    # ==================== 대상 테이블 관리 ====================

    def _drop_target_table(self, target_table: str):
        """대상 테이블 삭제 (존재하면)"""
        insp = inspect(self.target_engine)
        if not insp.has_table(target_table):
            logger.debug(f"삭제 대상 테이블 없음: {target_table}")
            return
        with self.target_engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {target_table} CASCADE"))
        logger.info(f"대상 테이블 삭제: {target_table}")

    def _ensure_target_table(
        self,
        target_table: str,
        source_columns: List[Dict],
        exclude_columns: Optional[List[str]] = None,
        recreate: bool = False,
    ):
        """대상 DB에 테이블 생성 (recreate=True면 DROP 후 재생성)"""
        insp = inspect(self.target_engine)

        if insp.has_table(target_table):
            if recreate:
                self._drop_target_table(target_table)
            else:
                logger.info(f"대상 테이블 이미 존재: {target_table}")
                return

        exclude = set(c.lower() for c in (exclude_columns or []))
        metadata = MetaData()
        cols = []
        for col_info in source_columns:
            if col_info['name'].lower() in exclude:
                continue
            sa_type = self._resolve_sa_type(col_info)
            cols.append(Column(
                col_info['name'],
                sa_type,
                primary_key=col_info.get('is_pk', False),
                nullable=col_info.get('nullable', True),
            ))

        Table(target_table, metadata, *cols)
        metadata.create_all(self.target_engine)
        action = "재생성" if recreate else "생성"
        logger.info(f"대상 테이블 {action}: {target_table} ({len(cols)}개 컬럼)")

    def _ensure_material_usage_table(self, table_name: str, recreate: bool = False):
        """mt_material_usage 테이블 생성"""
        if recreate:
            self._drop_target_table(table_name)

        with self.target_engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id SERIAL PRIMARY KEY,
                    order_no TEXT NOT NULL,
                    matnr TEXT,
                    menge TEXT,
                    meins TEXT,
                    insertdate TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_order_no
                ON {table_name}(order_no)
            """))
        action = "재생성" if recreate else "확인/생성"
        logger.info(f"자재 사용 테이블 {action} 완료: {table_name}")

    # ==================== Extract ====================

    def _extract(
        self,
        table_name: str,
        exclude_columns: Optional[List[str]] = None,
    ) -> List[Dict]:
        """소스 테이블에서 데이터 추출 (exclude_columns 지정 시 해당 컬럼 제외)"""
        if exclude_columns:
            exclude_set = set(c.lower() for c in exclude_columns)
            all_cols = self._get_source_columns(table_name)
            select_cols = [
                c['name'] for c in all_cols
                if c['name'].lower() not in exclude_set
            ]
            col_str = ', '.join(select_cols)
            sql = f"SELECT {col_str} FROM {table_name}"
        else:
            sql = f"SELECT * FROM {table_name}"

        if self.test_limit > 0:
            sql += f" LIMIT {self.test_limit}"

        with self.source_engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result]

        if self.test_limit > 0:
            logger.info(f"[Extract][테스트] {table_name}: {len(rows)}행 추출 (LIMIT {self.test_limit})")
        else:
            logger.info(f"[Extract] {table_name}: {len(rows)}행 추출")
        return rows

    # ==================== Load ====================

    def _batch_insert(self, conn, table_name: str, rows: List[Dict]):
        if not rows:
            return
        all_cols = list(rows[0].keys())
        col_list = ', '.join(all_cols)
        param_list = ', '.join(f":{c}" for c in all_cols)
        insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({param_list})"

        total = len(rows)
        for i in range(0, total, self.batch_size):
            batch = rows[i:i + self.batch_size]
            conn.execute(text(insert_sql), batch)
            logger.debug(f"[Insert] {table_name}: {min(i + self.batch_size, total)}/{total}")

    def _load_replace(self, table_name: str, rows: List[Dict]):
        with self.target_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table_name}"))
            self._batch_insert(conn, table_name, rows)
        logger.info(f"[Load] {table_name}: TRUNCATE + INSERT {len(rows)}행")

    def _load_append(self, table_name: str, rows: List[Dict]):
        with self.target_engine.begin() as conn:
            self._batch_insert(conn, table_name, rows)
        logger.info(f"[Load] {table_name}: APPEND {len(rows)}행")

    def _load_upsert(self, table_name: str, rows: List[Dict], pk_columns: List[str]):
        if not rows:
            return
        if not pk_columns:
            logger.warning(f"[Load] {table_name}: PK 없음 → replace 모드로 전환")
            self._load_replace(table_name, rows)
            return

        all_cols = list(rows[0].keys())
        update_cols = [c for c in all_cols if c not in pk_columns]

        col_list = ', '.join(all_cols)
        param_list = ', '.join(f":{c}" for c in all_cols)
        conflict_cols = ', '.join(pk_columns)

        if update_cols:
            update_set = ', '.join(f"{c} = EXCLUDED.{c}" for c in update_cols)
            upsert_sql = (
                f"INSERT INTO {table_name} ({col_list}) VALUES ({param_list}) "
                f"ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_set}"
            )
        else:
            upsert_sql = (
                f"INSERT INTO {table_name} ({col_list}) VALUES ({param_list}) "
                f"ON CONFLICT ({conflict_cols}) DO NOTHING"
            )

        with self.target_engine.begin() as conn:
            for i in range(0, len(rows), self.batch_size):
                batch = rows[i:i + self.batch_size]
                conn.execute(text(upsert_sql), batch)

        logger.info(f"[Load] {table_name}: UPSERT {len(rows)}행")

    def _load_rows(self, table_name: str, rows: List[Dict], mode: str, pk_columns: List[str]):
        """모드에 따라 적재 방식 분기"""
        if mode == 'replace':
            self._load_replace(table_name, rows)
        elif mode == 'append':
            self._load_append(table_name, rows)
        elif mode == 'upsert':
            self._load_upsert(table_name, rows, pk_columns)
        else:
            raise ValueError(f"지원하지 않는 적재 모드: {mode}")

    # ==================== 테이블 마이그레이션 ====================

    def migrate_table(
        self,
        source_table: str,
        target_table: str,
        mode: str = "replace",
        exclude_columns: Optional[List[str]] = None,
        recreate: bool = False,
    ) -> Dict[str, Any]:
        """
        단일 테이블 마이그레이션

        Args:
            source_table: MySQL 소스 테이블명
            target_table: PostgreSQL 대상 테이블명
            mode: "replace" | "append" | "upsert"
            exclude_columns: 대상 테이블에서 제외할 컬럼 목록
            recreate: True면 대상 테이블 DROP 후 재생성
        """
        start = datetime.now()
        result = {
            'source_table': source_table,
            'target_table': target_table,
            'mode': mode,
            'source_rows': 0,
            'target_rows': 0,
            'excluded_columns': exclude_columns or [],
            'recreated': recreate,
            'status': 'pending',
        }

        try:
            source_columns = self._get_source_columns(source_table)
            pk_columns = [c['name'] for c in source_columns if c.get('is_pk')]

            self._ensure_target_table(
                target_table, source_columns, exclude_columns, recreate=recreate,
            )

            rows = self._extract(source_table, exclude_columns=exclude_columns)
            result['source_rows'] = len(rows)
            rows = self._transform_rows(rows)

            if exclude_columns:
                exclude_set = set(c.lower() for c in exclude_columns)
                pk_columns = [c for c in pk_columns if c.lower() not in exclude_set]

            self._load_rows(target_table, rows, mode, pk_columns)

            with self.target_engine.connect() as conn:
                result['target_rows'] = conn.execute(
                    text(f"SELECT COUNT(*) FROM {target_table}")
                ).scalar()

            result['status'] = 'success'
            result['duration_seconds'] = round((datetime.now() - start).total_seconds(), 2)
            logger.info(
                f"[Migrate] {source_table} → {target_table}: "
                f"{result['source_rows']}행 → {result['target_rows']}행 "
                f"({result['duration_seconds']}초)"
            )

        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            result['duration_seconds'] = round((datetime.now() - start).total_seconds(), 2)
            logger.error(f"[Migrate] {source_table} → {target_table} 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return result

    # ==================== matnr 파싱 → mt_material_usage ====================

    @staticmethod
    def parse_matnr(matnr_value: str) -> List[Dict[str, str]]:
        """
        matnr 컬럼 값을 파싱하여 (matnr, menge, meins) 리스트 반환

        형식: '자재,수량,단위/자재,수량,단위/...'
        예: '100001234,10,EA/100005678,5,KG'
        → [{'matnr':'100001234','menge':'10','meins':'EA'},
           {'matnr':'100005678','menge':'5','meins':'KG'}]
        """
        if not matnr_value or not str(matnr_value).strip():
            return []

        parsed = []
        groups = str(matnr_value).split('/')
        for group in groups:
            group = group.strip()
            if not group:
                continue
            parts = group.split(',')
            entry = {
                'matnr': parts[0].strip() if len(parts) >= 1 else '',
                'menge': parts[1].strip() if len(parts) >= 2 else '',
                'meins': parts[2].strip() if len(parts) >= 3 else '',
            }
            if entry['matnr']:
                parsed.append(entry)

        return parsed

    def parse_and_load_material_usage(
        self,
        source_table: str,
        parse_column: str,
        key_column: str,
        target_table: str,
        mode: str = "replace",
        recreate: bool = False,
    ) -> Dict[str, Any]:
        """
        소스 테이블에서 matnr 컬럼을 파싱하여 정규화된 자재 사용 테이블에 적재

        Args:
            source_table: 소스(MySQL) 테이블명
            parse_column: 파싱 대상 컬럼명 (예: matnr)
            key_column: 키 컬럼명 (예: order_no)
            target_table: 대상(PostgreSQL) 자재 사용 테이블명
            mode: 적재 모드
            recreate: True면 대상 테이블 DROP 후 재생성
        """
        start = datetime.now()
        result = {
            'source_table': source_table,
            'parse_column': parse_column,
            'key_column': key_column,
            'target_table': target_table,
            'source_rows': 0,
            'parsed_rows': 0,
            'skipped_rows': 0,
            'status': 'pending',
        }

        try:
            self._ensure_material_usage_table(target_table, recreate=recreate)

            with self.source_engine.connect() as conn:
                sql = f"SELECT {key_column}, {parse_column} FROM {source_table}"
                if self.test_limit > 0:
                    sql += f" LIMIT {self.test_limit}"
                rows = conn.execute(text(sql)).fetchall()

            result['source_rows'] = len(rows)
            if self.test_limit > 0:
                logger.info(f"[Material][테스트] {source_table}에서 {len(rows)}행 추출 (LIMIT {self.test_limit})")
            else:
                logger.info(f"[Material] {source_table}에서 {len(rows)}행 추출")

            material_rows = []
            for row in rows:
                key_value = str(row[0]) if row[0] is not None else ''
                matnr_value = row[1]

                parsed = self.parse_matnr(matnr_value)
                if not parsed:
                    result['skipped_rows'] += 1
                    continue

                for entry in parsed:
                    material_rows.append({
                        'order_no': key_value,
                        'matnr': entry['matnr'],
                        'menge': entry['menge'],
                        'meins': entry['meins'],
                    })

            result['parsed_rows'] = len(material_rows)
            logger.info(
                f"[Material] {result['source_rows']}행에서 "
                f"{result['parsed_rows']}개 자재 행 파싱 "
                f"(건너뜀: {result['skipped_rows']})"
            )

            if material_rows:
                if mode == 'replace':
                    with self.target_engine.begin() as conn:
                        conn.execute(text(f"TRUNCATE TABLE {target_table}"))
                        self._batch_insert(conn, target_table, material_rows)
                else:
                    with self.target_engine.begin() as conn:
                        self._batch_insert(conn, target_table, material_rows)

            result['status'] = 'success'
            result['duration_seconds'] = round((datetime.now() - start).total_seconds(), 2)
            logger.info(
                f"[Material] {target_table}: {result['parsed_rows']}행 적재 완료 "
                f"({result['duration_seconds']}초)"
            )

        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            result['duration_seconds'] = round((datetime.now() - start).total_seconds(), 2)
            logger.error(f"[Material] {target_table} 적재 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return result

    # ==================== 전체 파이프라인 ====================

    def cleanup_tables(self, table_specs: List[str], material_parse_config: str = "") -> Dict[str, Any]:
        """
        마이그레이션 대상 테이블의 데이터 전량 삭제 (TRUNCATE)

        Returns:
            테이블별 정리 결과
        """
        result = {'tables': [], 'material_usage': None, 'status': 'success'}

        for spec in table_specs:
            _, target_table = self.parse_table_mapping(spec)
            try:
                insp = inspect(self.target_engine)
                if not insp.has_table(target_table):
                    result['tables'].append({
                        'table': target_table, 'status': 'skipped', 'reason': '테이블 없음'
                    })
                    continue
                with self.target_engine.begin() as conn:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {target_table}")).scalar()
                    conn.execute(text(f"TRUNCATE TABLE {target_table}"))
                result['tables'].append({
                    'table': target_table, 'status': 'truncated', 'deleted_rows': count
                })
                logger.info(f"[Cleanup] {target_table}: {count}행 삭제")
            except Exception as e:
                result['tables'].append({
                    'table': target_table, 'status': 'failed', 'error': str(e)
                })
                result['status'] = 'partial_failure'

        mat_cfg = self.parse_material_config(material_parse_config)
        if mat_cfg:
            target_table = mat_cfg['target_table']
            try:
                insp = inspect(self.target_engine)
                if insp.has_table(target_table):
                    with self.target_engine.begin() as conn:
                        count = conn.execute(text(f"SELECT COUNT(*) FROM {target_table}")).scalar()
                        conn.execute(text(f"TRUNCATE TABLE {target_table}"))
                    result['material_usage'] = {
                        'table': target_table, 'status': 'truncated', 'deleted_rows': count
                    }
                    logger.info(f"[Cleanup] {target_table}: {count}행 삭제")
                else:
                    result['material_usage'] = {
                        'table': target_table, 'status': 'skipped', 'reason': '테이블 없음'
                    }
            except Exception as e:
                result['material_usage'] = {
                    'table': target_table, 'status': 'failed', 'error': str(e)
                }
                result['status'] = 'partial_failure'

        return result

    def get_table_info(self, table_specs: List[str], material_parse_config: str = "") -> Dict[str, Any]:
        """
        마이그레이션 대상 테이블 상태 정보 조회

        Returns:
            테이블별 존재 여부, 행 수, 컬럼 목록
        """
        result = {'tables': [], 'material_usage': None}

        for spec in table_specs:
            _, target_table = self.parse_table_mapping(spec)
            try:
                insp = inspect(self.target_engine)
                if not insp.has_table(target_table):
                    result['tables'].append({
                        'table': target_table, 'exists': False
                    })
                    continue
                with self.target_engine.connect() as conn:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {target_table}")).scalar()
                columns = [c['name'] for c in insp.get_columns(target_table)]
                result['tables'].append({
                    'table': target_table, 'exists': True,
                    'row_count': count, 'columns': columns,
                })
            except Exception as e:
                result['tables'].append({
                    'table': target_table, 'exists': None, 'error': str(e)
                })

        mat_cfg = self.parse_material_config(material_parse_config)
        if mat_cfg:
            target_table = mat_cfg['target_table']
            try:
                insp = inspect(self.target_engine)
                if insp.has_table(target_table):
                    with self.target_engine.connect() as conn:
                        count = conn.execute(text(f"SELECT COUNT(*) FROM {target_table}")).scalar()
                    columns = [c['name'] for c in insp.get_columns(target_table)]
                    result['material_usage'] = {
                        'table': target_table, 'exists': True,
                        'row_count': count, 'columns': columns,
                    }
                else:
                    result['material_usage'] = {
                        'table': target_table, 'exists': False
                    }
            except Exception as e:
                result['material_usage'] = {
                    'table': target_table, 'exists': None, 'error': str(e)
                }

        return result

    def run_migration(
        self,
        table_specs: List[str],
        mode: str = "replace",
        material_parse_config: str = "",
        recreate_tables: bool = False,
        exclude_columns_file: str = "",
    ) -> Dict[str, Any]:
        """
        전체 마이그레이션 파이프라인

        Args:
            table_specs: 테이블 매핑 목록 (["source:target", ...])
            mode: 적재 모드 ("replace" | "append" | "upsert")
            material_parse_config: 자재 파싱 설정
                ("소스테이블:파싱컬럼:키컬럼:대상테이블")
            recreate_tables: True면 대상 테이블 DROP 후 재생성 (스키마 변경 반영)
            exclude_columns_file: 제외 컬럼 JSON 파일 경로
        """
        start = datetime.now()
        overall = {
            'started_at': start.isoformat(),
            'tables': [],
            'material_usage': None,
            'status': 'running',
        }

        mat_cfg = self.parse_material_config(material_parse_config)

        exclude_map: Dict[str, List[str]] = self.load_exclude_columns(exclude_columns_file)

        if mat_cfg:
            src = mat_cfg['source_table']
            parse_col = mat_cfg['parse_column']
            if src in exclude_map:
                if parse_col not in exclude_map[src]:
                    exclude_map[src].append(parse_col)
            else:
                exclude_map[src] = [parse_col]

        logger.info("=" * 80)
        logger.info("DB 마이그레이션 시작 (MySQL → PostgreSQL)")
        logger.info(f"테이블 매핑: {table_specs}")
        logger.info(f"적재 모드: {mode}")
        if recreate_tables:
            logger.info("테이블 재생성 모드: ON (DROP → CREATE)")
        if exclude_map:
            for tbl, cols in exclude_map.items():
                logger.info(f"제외 컬럼: {tbl} → {cols}")
        if mat_cfg:
            logger.info(
                f"자재 파싱: {mat_cfg['source_table']}.{mat_cfg['parse_column']} "
                f"(키: {mat_cfg['key_column']}) → {mat_cfg['target_table']}"
            )
        logger.info("=" * 80)

        try:
            self._test_connections()

            for spec in table_specs:
                source_table, target_table = self.parse_table_mapping(spec)
                exclude_cols = exclude_map.get(source_table)

                table_result = self.migrate_table(
                    source_table=source_table,
                    target_table=target_table,
                    mode=mode,
                    exclude_columns=exclude_cols,
                    recreate=recreate_tables,
                )
                overall['tables'].append(table_result)

            if mat_cfg:
                material_result = self.parse_and_load_material_usage(
                    source_table=mat_cfg['source_table'],
                    parse_column=mat_cfg['parse_column'],
                    key_column=mat_cfg['key_column'],
                    target_table=mat_cfg['target_table'],
                    mode=mode,
                    recreate=recreate_tables,
                )
                overall['material_usage'] = material_result

            failed = [t for t in overall['tables'] if t['status'] == 'failed']
            mat_failed = (
                overall.get('material_usage', {}).get('status') == 'failed'
                if overall.get('material_usage') else False
            )
            if failed or mat_failed:
                overall['status'] = 'partial_failure'
            else:
                overall['status'] = 'success'

        except Exception as e:
            overall['status'] = 'failed'
            overall['error'] = str(e)
            logger.error(f"마이그레이션 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())

        overall['completed_at'] = datetime.now().isoformat()
        overall['duration_seconds'] = round(
            (datetime.now() - start).total_seconds(), 2
        )

        logger.info("=" * 80)
        logger.info(f"DB 마이그레이션 완료: {overall['status']} ({overall['duration_seconds']}초)")
        for t in overall['tables']:
            icon = "✓" if t['status'] == 'success' else "✗"
            logger.info(
                f"  {icon} {t['source_table']} → {t['target_table']}: "
                f"{t['source_rows']}행 → {t.get('target_rows', '?')}행"
            )
        if overall.get('material_usage'):
            m = overall['material_usage']
            icon = "✓" if m['status'] == 'success' else "✗"
            logger.info(
                f"  {icon} 자재 파싱: {m['source_table']}.{m['parse_column']} "
                f"→ {m['target_table']} ({m['parsed_rows']}행)"
            )
        logger.info("=" * 80)

        self.stats = overall
        return overall

    # ==================== 정리 ====================

    def close(self):
        if self.source_engine:
            self.source_engine.dispose()
        if self.target_engine:
            self.target_engine.dispose()
        logger.info("마이그레이션 DB 연결 종료")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
