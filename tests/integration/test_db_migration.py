"""FIX 5 regression: legacy SQLite databases must upgrade to nullable
sample_count without data loss, and the migration must be idempotent."""

import sqlite3
from pathlib import Path

from app.db.migrations import run_startup_migrations
from sqlalchemy import create_engine, text

# Exact schema of benchmark_runs as of e05078e (sample_count NOT NULL,
# no worker identity columns).
LEGACY_DDL = """
CREATE TABLE benchmark_runs (
    id VARCHAR(36) NOT NULL,
    user_id INTEGER NOT NULL,
    model_id VARCHAR(64) NOT NULL,
    dataset_id VARCHAR(64) NOT NULL,
    protocol_id VARCHAR(64) NOT NULL,
    split VARCHAR(32),
    sample_size_mode VARCHAR(32),
    sample_count INTEGER NOT NULL,
    seed INTEGER,
    status VARCHAR(9),
    is_private BOOLEAN,
    cancel_requested BOOLEAN,
    progress_done INTEGER,
    progress_total INTEGER,
    error_text TEXT,
    sample_selection JSON,
    generation_config JSON,
    hardware_metadata JSON,
    created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
    started_at DATETIME,
    completed_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id),
    FOREIGN KEY(model_id) REFERENCES model_definitions (id),
    FOREIGN KEY(dataset_id) REFERENCES dataset_definitions (id),
    FOREIGN KEY(protocol_id) REFERENCES benchmark_protocols (id)
)
"""


def _make_legacy_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE users (id INTEGER NOT NULL PRIMARY KEY, username VARCHAR(64), email VARCHAR(255), password_hash VARCHAR(255), created_at DATETIME DEFAULT (CURRENT_TIMESTAMP));
        CREATE TABLE model_definitions (id VARCHAR(64) NOT NULL PRIMARY KEY, name VARCHAR(128), hf_id VARCHAR(255), revision VARCHAR(64), parameters INTEGER, context_length INTEGER, torch_dtype VARCHAR(32), vram_weight_gb FLOAT, trust_remote_code BOOLEAN, license VARCHAR(64));
        CREATE TABLE dataset_definitions (id VARCHAR(64) NOT NULL PRIMARY KEY, name VARCHAR(128), hf_id VARCHAR(255), domain VARCHAR(64), task_type VARCHAR(64), default_split VARCHAR(32), evaluator_key VARCHAR(64));
        CREATE TABLE benchmark_protocols (id VARCHAR(64) NOT NULL PRIMARY KEY, dataset_id VARCHAR(64), name VARCHAR(128), version VARCHAR(32), prompt_template TEXT, expected_answer_format VARCHAR(64), FOREIGN KEY(dataset_id) REFERENCES dataset_definitions (id));
        """
    )
    con.executescript(LEGACY_DDL)
    con.execute(
        "INSERT INTO users (id, username, email, password_hash) VALUES (1, 'legacy', 'legacy@test.com', 'x')"
    )
    con.execute(
        "INSERT INTO model_definitions (id, name, hf_id, revision, parameters, context_length, torch_dtype, vram_weight_gb, trust_remote_code, license) "
        "VALUES ('m1', 'Model One', 'org/m1', 'rev1', 1000, 4096, 'bfloat16', 1.0, 0, 'mit')"
    )
    con.execute(
        "INSERT INTO dataset_definitions (id, name, hf_id, domain, task_type, default_split, evaluator_key) "
        "VALUES ('sciq', 'SciQ', 'allenai/sciq', 'education', 'multiple_choice', 'test', 'sciq_evaluator')"
    )
    con.execute(
        "INSERT INTO benchmark_protocols (id, dataset_id, name, version, prompt_template, expected_answer_format) "
        "VALUES ('sciq_evidence_grounded', 'sciq', 'Evidence', '1.0.0', '{text}', 'letter')"
    )
    con.execute(
        "INSERT INTO benchmark_runs (id, user_id, model_id, dataset_id, protocol_id, split, sample_size_mode, sample_count, seed, status, is_private, cancel_requested, progress_done, progress_total, created_at) "
        "VALUES ('legacy-run-1', 1, 'm1', 'sciq', 'sciq_evidence_grounded', 'test', 'smoke', 10, 42, 'completed', 0, 0, 10, 10, CURRENT_TIMESTAMP)"
    )
    # Dependent rows referencing benchmark_runs (FK survival must be tested).
    con.execute(
        "CREATE TABLE benchmark_metrics (id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "run_id VARCHAR(36) NOT NULL, metric_name VARCHAR(64), metric_value FLOAT, "
        "FOREIGN KEY(run_id) REFERENCES benchmark_runs (id) ON DELETE CASCADE)"
    )
    con.execute(
        "CREATE TABLE artifacts (id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "run_id VARCHAR(36) NOT NULL, artifact_type VARCHAR(64), relative_path VARCHAR(255), "
        "file_size_bytes INTEGER, created_at DATETIME, "
        "FOREIGN KEY(run_id) REFERENCES benchmark_runs (id) ON DELETE CASCADE)"
    )
    con.execute(
        "INSERT INTO benchmark_metrics (run_id, metric_name, metric_value) VALUES ('legacy-run-1', 'accuracy', 0.9)"
    )
    con.execute(
        "INSERT INTO artifacts (run_id, artifact_type, relative_path, file_size_bytes, created_at) VALUES ('legacy-run-1', 'predictions', 'legacy-run-1/predictions.jsonl', 100, CURRENT_TIMESTAMP)"
    )
    con.commit()
    con.close()


def _apply_app_startup(path: str):
    """Simulate app startup: create_all + run_startup_migrations."""
    import app.db.models  # noqa: F401 — register all tables
    from app.db.base import Base

    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    run_startup_migrations(engine)
    return engine


def test_legacy_db_upgrade_preserves_data_and_allows_null(tmp_path: Path):
    db = str(tmp_path / "legacy.db")
    _make_legacy_db(db)

    # Pre-check: legacy constraint reproduces the defect.
    con = sqlite3.connect(db)
    with pytest_raises_not_null():
        con.execute(
            "INSERT INTO benchmark_runs (id, user_id, model_id, dataset_id, protocol_id, sample_count) "
            "VALUES ('x', 1, 'm1', 'sciq', 'sciq_evidence_grounded', NULL)"
        )
    con.close()

    engine = _apply_app_startup(db)
    try:
        # Legacy row preserved with original values.
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT id, user_id, model_id, sample_count FROM benchmark_runs WHERE id='legacy-run-1'")
            ).fetchone()
            assert row is not None
            assert row[0] == "legacy-run-1"
            assert row[1] == 1
            assert row[2] == "m1"
            assert row[3] == 10

        # Full-mode insert with sample_count NULL now works.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO benchmark_runs (id, user_id, model_id, dataset_id, protocol_id, split, sample_size_mode, sample_count, seed, status, is_private, cancel_requested, progress_done, progress_total, created_at) "
                    "VALUES ('full-run-1', 1, 'm1', 'sciq', 'sciq_evidence_grounded', 'test', 'full', NULL, 42, 'queued', 1, 0, 0, 0, CURRENT_TIMESTAMP)"
                )
            )
        with engine.begin() as conn:
            got = conn.execute(
                text("SELECT sample_count FROM benchmark_runs WHERE id='full-run-1'")
            ).scalar()
            assert got is None
    finally:
        engine.dispose()


def test_migration_is_idempotent(tmp_path: Path):
    db = str(tmp_path / "legacy2.db")
    _make_legacy_db(db)

    engine1 = _apply_app_startup(db)
    engine1.dispose()
    # Second startup must be a no-op and keep data.
    engine2 = _apply_app_startup(db)
    try:
        with engine2.begin() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM benchmark_runs")).scalar()
            assert count == 1
            row = conn.execute(
                text("SELECT sample_count FROM benchmark_runs WHERE id='legacy-run-1'")
            ).scalar()
            assert row == 10
    finally:
        engine2.dispose()


def test_fresh_db_unaffected(tmp_path: Path):
    db = str(tmp_path / "fresh.db")
    engine = _apply_app_startup(db)
    try:
        with engine.begin() as conn:
            cols = conn.exec_driver_sql("PRAGMA table_info(benchmark_runs)").fetchall()
            names = {c[1] for c in cols}
            assert "worker_pid" in names
            assert "worker_start_ts" in names
            # Fresh create_all already nullable.
            sc = next(c for c in cols if c[1] == "sample_count")
            assert sc[3] == 0  # notnull = 0
    finally:
        engine.dispose()


def test_foreign_keys_preserved_after_rebuild(tmp_path: Path):
    db = str(tmp_path / "legacy3.db")
    _make_legacy_db(db)
    engine = _apply_app_startup(db)
    try:
        with engine.begin() as conn:
            fks = conn.exec_driver_sql("PRAGMA foreign_key_list(benchmark_runs)").fetchall()
            # (id, seq, table, from, to, on_update, on_delete, match)
            targets = {fk[2] for fk in fks}
            assert "users" in targets
            assert "model_definitions" in targets
            assert "dataset_definitions" in targets
            assert "benchmark_protocols" in targets
    finally:
        engine.dispose()


def test_dependent_rows_survive_rebuild_and_stay_linked(tmp_path: Path):
    """Child rows (metrics, artifacts) must survive the rebuild of the
    parent table and still reference the rebuilt benchmark_runs."""
    db = str(tmp_path / "legacy4.db")
    _make_legacy_db(db)
    engine = _apply_app_startup(db)
    try:
        with engine.begin() as conn:
            # Dependent rows still exist and link to the rebuilt parent.
            m = conn.execute(
                text("SELECT COUNT(*) FROM benchmark_metrics WHERE run_id='legacy-run-1'")
            ).scalar()
            assert m == 1
            a = conn.execute(
                text("SELECT COUNT(*) FROM artifacts WHERE run_id='legacy-run-1'")
            ).scalar()
            assert a == 1
            # FK enforcement on the rebuilt relationship works: inserting a
            # child row with a bogus run_id must fail. Run on a separate
            # connection so the failing statement cannot abort this
            # transaction.
            import sqlite3

            probe = sqlite3.connect(db)
            try:
                probe.execute("PRAGMA foreign_keys=ON")
                probe.execute(
                    "INSERT INTO benchmark_metrics (run_id, metric_name, metric_value) "
                    "VALUES ('nonexistent-run', 'x', 1.0)"
                )
                raise AssertionError("FK constraint not enforced after rebuild")
            except sqlite3.IntegrityError:
                pass
            finally:
                probe.close()
    finally:
        engine.dispose()


class pytest_raises_not_null:
    """Tiny context manager: assert sqlite3.IntegrityError NOT NULL."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        assert exc_type is not None, "expected NOT NULL constraint failure"
        assert "NOT NULL" in str(exc), f"unexpected error: {exc}"
        return True
