"""Unit tests for ICECODE server database layer."""
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "test.db"


class TestDBInit:
    def test_init_creates_file(self, tmp_db):
        from icecode_server.db import init_db
        conn = init_db(tmp_db)
        assert tmp_db.exists()
        conn.close()

    def test_init_creates_all_tables(self, tmp_db):
        from icecode_server.db import init_db
        conn = init_db(tmp_db)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "sessions" in tables
        assert "messages" in tables
        assert "usage_stats" in tables
        assert "kanban_tasks" in tables
        assert "schema_version" in tables
        conn.close()

    def test_init_idempotent(self, tmp_db):
        """Calling init_db twice should not raise errors."""
        from icecode_server.db import init_db
        conn1 = init_db(tmp_db)
        conn1.close()
        conn2 = init_db(tmp_db)
        conn2.close()

    def test_schema_version_recorded(self, tmp_db):
        from icecode_server.db import init_db, SCHEMA_VERSION
        conn = init_db(tmp_db)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        assert row is not None
        assert row[0] == SCHEMA_VERSION
        conn.close()

    def test_wal_mode(self, tmp_db):
        from icecode_server.db import init_db
        conn = init_db(tmp_db)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode in ("wal", "delete")  # delete is WAL fallback on NFS
        conn.close()


class TestUsageStats:
    def test_record_usage(self, tmp_db):
        from icecode_server.db import init_db, record_usage, get_usage_summary
        init_db(tmp_db)
        # patch connection to use tmp db
        import icecode_server.db as db_mod
        original = db_mod._conn
        db_mod._conn = init_db(tmp_db)

        record_usage("s1", "gpt-4o", "openai", 100, 50, 0.002)
        record_usage("s1", "gpt-4o", "openai", 200, 80, 0.004)
        summary = get_usage_summary()

        assert summary["total_tokens"] == 430
        assert summary["total_prompt"] == 300
        assert summary["total_completion"] == 130
        assert "gpt-4o" in summary["by_model"]
        assert summary["by_model"]["gpt-4o"]["prompt"] == 300

        db_mod._conn = original

    def test_usage_summary_empty(self, tmp_db):
        from icecode_server.db import init_db, get_usage_summary
        import icecode_server.db as db_mod
        original = db_mod._conn
        db_mod._conn = init_db(tmp_db)

        summary = get_usage_summary()
        assert summary["total_tokens"] == 0
        assert summary["by_model"] == {}

        db_mod._conn = original


class TestSessionInsert:
    def test_insert_and_query_session(self, tmp_db):
        from icecode_server.db import init_db
        from datetime import datetime, timezone
        conn = init_db(tmp_db)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO sessions (id, title, model, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("sess-1", "Test Session", "qwen2.5:7b", now, now)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sessions WHERE id='sess-1'").fetchone()
        assert row["title"] == "Test Session"
        assert row["model"] == "qwen2.5:7b"
        conn.close()
