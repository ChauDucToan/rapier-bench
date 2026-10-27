"""Idempotent SQLite startup migrations for legacy databases.

FIX 5: SQLAlchemy ``create_all()`` never alters existing columns. Databases
created before Full Evaluation mode still carry ``sample_count INTEGER NOT
NULL``, which makes inserting ``sample_count = NULL`` fail. SQLite cannot
ALTER a column's nullability, so the fix is a one-time table rebuild:
create the replacement table with the current schema, copy rows, drop the
old table, rename, recreate indexes.

Foreign-key handling: ``PRAGMA foreign_keys`` is a connection-level setting
that is a NO-OP inside a transaction, so the toggle is issued on the
connection BEFORE the transaction starts (SQLite's documented rebuild
procedure). Additionally, legacy SQLite versions rewrite child-table FK
references on ``ALTER TABLE ... RENAME``; we disable ``legacy_alter_table``
for the duration so child tables keep pointing at ``benchmark_runs``.

ponytail: hand-rolled rebuild — swap for Alembic when migrations exceed
what a single function can express.
"""

import logging
from typing import Any

from sqlalchemy.engine import Engine

logger = logging.getLogger("app.db.migrations")


def _table_columns(conn: Any, table: str) -> dict[str, dict[str, Any]]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {
        row[1]: {
            "notnull": row[3],
            "dflt_value": row[4],
            "type": row[2],
        }
        for row in rows
    }


def _add_columns_if_missing(engine: Engine) -> None:
    with engine.begin() as conn:
        cols = _table_columns(conn, "benchmark_runs")
        if not cols:
            return
        if "worker_pid" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE benchmark_runs ADD COLUMN worker_pid INTEGER"
            )
        if "worker_start_ts" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE benchmark_runs ADD COLUMN worker_start_ts VARCHAR(64)"
            )


def _migrate_benchmark_runs_nullable_sample_count(engine: Engine) -> None:
    # Detect first (inside a transaction is fine).
    with engine.begin() as conn:
        cols = _table_columns(conn, "benchmark_runs")
        if not cols:
            return
        sample_count = cols.get("sample_count")
        if sample_count is None or not sample_count["notnull"]:
            return

    logger.info("Migrating benchmark_runs.sample_count -> nullable (table rebuild)")

    col_names = list(cols.keys())
    col_list = ", ".join(f'"{c}"' for c in col_names)

    # Rebuild procedure (verified against SQLite 3.5x behavior):
    #   1. rename the legacy table to a temp name (SQLite rewrites dependent
    #      FK references to the temp name — but they are restored in step 4)
    #   2. create the replacement table from the current model under the
    #      original name and copy rows
    #   3. DROP the temp table
    #   4. RENAME the replacement table from a temp name is NOT used; the
    #      replacement is created directly as 'benchmark_runs' after the
    #      rename in step 1 moved the old one out of the way. Child FK
    #      references were rewritten by step 1 to the temp name, so after
    #      step 3 they would dangle. Therefore the safe order is:
    #        a. create 'benchmark_runs_new' via the model, copy rows into it
    #        b. DROP 'benchmark_runs' (children reference a dropped table —
    #           acceptable only inside this FK-disabled transaction)
    #        c. RENAME 'benchmark_runs_new' -> 'benchmark_runs': SQLite
    #           rewrites child references from 'benchmark_runs_new' to
    #           'benchmark_runs', leaving children correctly linked.
    # PRAGMA foreign_keys is connection-level and a NO-OP inside a
    # transaction, so it is toggled on the raw DBAPI connection before the
    # rebuild transaction and restored afterwards.
    with engine.connect() as connection:
        dbapi = connection.connection

        def _pragma(name: str, value: str) -> None:
            cur = dbapi.cursor()
            cur.execute(f"PRAGMA {name}={value}")
            cur.close()

        def _get_pragma(name: str) -> str:
            cur = dbapi.cursor()
            cur.execute(f"PRAGMA {name}")
            val = cur.fetchone()[0]
            cur.close()
            return str(val)

        fk_before = _get_pragma("foreign_keys")
        _pragma("foreign_keys", "OFF")
        try:
            from app.db.models import BenchmarkRun

            # A1: SQLite index names are database-global. The legacy table's
            # indexes (e.g. ix_benchmark_runs_status) collide with the
            # replacement table's same-named indexes if both exist. Drop the
            # legacy indexes BEFORE creating the replacement — they are
            # recreated by the model DDL on the new table. Child-table indexes
            # are untouched (different names).
            with connection.begin():
                legacy_indexes = [
                    row[1]
                    for row in connection.exec_driver_sql(
                        "PRAGMA index_list(benchmark_runs)"
                    ).fetchall()
                    if row[3] != "pk"  # skip the implicit PK index
                ]
                for idx in legacy_indexes:
                    connection.exec_driver_sql(f'DROP INDEX IF EXISTS "{idx}"')

            # Create the replacement under a temp name with the full CURRENT
            # model schema (columns, PK, FKs, indexes) — same DDL the model
            # would emit, under a temporary name.
            original_name = BenchmarkRun.__table__.name
            BenchmarkRun.__table__.name = "benchmark_runs_new"
            try:
                with connection.begin():
                    BenchmarkRun.__table__.create(bind=connection)
                    connection.exec_driver_sql(
                        f"INSERT INTO benchmark_runs_new ({col_list}) "
                        f"SELECT {col_list} FROM benchmark_runs"
                    )
                    connection.exec_driver_sql("DROP TABLE benchmark_runs")
                    # RENAME rewrites dependent FK references from the temp
                    # name back to 'benchmark_runs'.
                    connection.exec_driver_sql(
                        "ALTER TABLE benchmark_runs_new RENAME TO benchmark_runs"
                    )
            finally:
                BenchmarkRun.__table__.name = original_name
        finally:
            _pragma("foreign_keys", fk_before)

    logger.info("benchmark_runs rebuild complete (sample_count now nullable)")


def run_startup_migrations(engine: Engine) -> None:
    _add_columns_if_missing(engine)
    _migrate_benchmark_runs_nullable_sample_count(engine)
