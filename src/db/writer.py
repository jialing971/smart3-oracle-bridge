"""数据库写入（产线加固）

- 每客户端线程一个 DbSession，独立连接
- SQL 预编译缓存，避免重复拼串
- ping + 断线自动重连后重试一次
- schema/table/column 标识符校验，防配置误写导致 SQL 注入
"""
import re
from typing import Dict, List, Optional, Tuple

import oracledb

from src.config.models import AppConfig
from src.utils.logger import get_logger

log = get_logger(__name__)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]{0,127}$")


def _validate_ident(name: str, label: str) -> str:
    if not name or not _IDENT_RE.match(name):
        raise ValueError(f"非法 {label} 标识符: {name!r}")
    return name.upper()


def _build_insert_sql(cfg: AppConfig) -> Tuple[str, List[str]]:
    schema = _validate_ident(cfg.database.schema, "schema")
    table = _validate_ident(cfg.database.table, "table")
    if not cfg.field_mapping:
        raise ValueError("field_mapping 不能为空")

    col_keys = [m.column for m in cfg.field_mapping]
    col_sql = [_validate_ident(c, "column") for c in col_keys]
    placeholders = [f":{i + 1}" for i in range(len(col_sql))]
    sql = (
        f"INSERT INTO {schema}.{table} "
        f"({', '.join(col_sql)}) "
        f"VALUES ({', '.join(placeholders)})"
    )
    return sql, col_keys


class DbSession:
    """线程内数据库会话，负责连接生命周期与写入"""

    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg
        self._conn: Optional[oracledb.Connection] = None
        self._sql: Optional[str] = None
        self._columns: Optional[List[str]] = None

    def insert(self, record: Dict[str, str]) -> None:
        self._execute_insert(record, retry=True)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except oracledb.Error:
                pass
        self._conn = None
        self._sql = None
        self._columns = None

    def _execute_insert(self, record: Dict[str, str], *, retry: bool) -> None:
        try:
            conn = self._get_connection()
            assert self._sql is not None and self._columns is not None
            values = tuple(record.get(col, "") for col in self._columns)
            cursor = conn.cursor()
            try:
                cursor.execute(self._sql, values)
                conn.commit()
            finally:
                cursor.close()
            log.info("写入成功 barcode=%s", record.get("barcode", ""))
        except oracledb.Error as e:
            log.warning("数据库写入失败: %s", e)
            self.close()
            if retry:
                self._execute_insert(record, retry=False)
            else:
                raise

    def _get_connection(self) -> oracledb.Connection:
        if self._conn is None:
            self._connect()
            return self._conn  # type: ignore[return-value]

        try:
            self._conn.ping()
        except oracledb.Error:
            log.warning("数据库连接已失效，正在重连…")
            self.close()
            self._connect()
        return self._conn  # type: ignore[return-value]

    def _connect(self) -> None:
        db = self._cfg.database
        self._conn = oracledb.connect(user=db.user, password=db.password, dsn=db.dsn)
        self._sql, self._columns = _build_insert_sql(self._cfg)
        log.info("Oracle 连接已建立 (dsn=%s)", db.dsn)


def create_session(cfg: AppConfig) -> DbSession:
    return DbSession(cfg)
