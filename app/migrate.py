"""Auto-migration: detect missing columns in SQLite and ALTER TABLE to add them.

Uses raw sqlite3 PRAGMA to avoid SQLAlchemy inspector caching issues.
Called during app startup after init_db().
"""

import logging
import sqlite3

from sqlalchemy import Column
from app.database import Base, DATABASE_URL

logger = logging.getLogger(__name__)

_TYPE_MAP = {
    "VARCHAR": "VARCHAR",
    "STRING": "VARCHAR",
    "TEXT": "TEXT",
    "INTEGER": "INTEGER",
    "DATETIME": "DATETIME",
    "JSON": "TEXT",
    "BOOLEAN": "BOOLEAN",
    "FLOAT": "FLOAT",
}


def _sql_type(col: Column) -> str:
    type_name = type(col.type).__name__.upper()
    return _TYPE_MAP.get(type_name, "TEXT")


def _default_clause(col: Column) -> str:
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
    """Compare ORM models with actual SQLite schema, add missing columns."""
    # Extract the file path from the SQLAlchemy URL (sqlite:///./path or sqlite:///path)
    db_path = DATABASE_URL.split("///", 1)[1]
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue

            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            existing_cols = {row[1] for row in cursor.fetchall()}

            for col in table.columns:
                if col.name in existing_cols:
                    continue

                sql_type = _sql_type(col)
                default = _default_clause(col)
                stmt = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {sql_type} {default}"
                logger.info("Auto-migrate: %s", stmt)
                conn.execute(stmt)
                conn.commit()
                logger.info("Added column %s.%s", table_name, col.name)
    finally:
        conn.close()
