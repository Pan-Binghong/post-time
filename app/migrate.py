"""自动迁移：检测 ORM 模型与数据库 Schema 的差异，补充缺失的列。

使用 SQLAlchemy inspect() 实现，兼容 SQLite 和 PostgreSQL。
在应用启动时（init_db 之后）调用。
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from app.database import Base, engine

logger = logging.getLogger(__name__)


def _sql_type(col) -> str:
    """将 SQLAlchemy 列类型编译为当前方言的 SQL 类型字符串。"""
    return col.type.compile(dialect=engine.dialect)


def _default_clause(col) -> str:
    if col.default is not None:
        arg = col.default.arg
        if callable(arg):
            return "DEFAULT NULL"
        if isinstance(arg, str):
            return f"DEFAULT '{arg}'"
        if isinstance(arg, (int, float)):
            return f"DEFAULT {arg}"
    if col.nullable is not False:
        return "DEFAULT NULL"
    type_name = type(col.type).__name__.upper()
    if type_name in ("INTEGER", "FLOAT", "BOOLEAN"):
        return "DEFAULT 0"
    return "DEFAULT ''"


def auto_migrate():
    """对比 ORM 模型与数据库实际 Schema，补充缺失的列。"""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue

        existing_cols = {col["name"] for col in inspector.get_columns(table_name)}

        for col in table.columns:
            if col.name in existing_cols:
                continue

            sql_type = _sql_type(col)
            default = _default_clause(col)
            stmt = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {sql_type} {default}"
            try:
                with engine.connect() as conn:
                    conn.execute(text(stmt))
                    conn.commit()
                logger.info("Auto-migrate: 新增列 %s.%s", table_name, col.name)
            except OperationalError as e:
                logger.warning("Auto-migrate 失败 %s.%s: %s", table_name, col.name, e)
