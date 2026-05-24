"""Unit tests for icecode_server.routes.skills

Tests skill listing, stats, CRUD, toggle, and curator operations.
Patches file I/O so tests are hermetic and fast.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).parents[2]
for _p in ("packages/core", "packages/server", "packages/tools"):
    sys.path.insert(0, str(ROOT / _p))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_SAMPLE_SKILLS = [
    {"id": "web_search", "name": "Web Search", "description": "Search the web", "enabled": True, "builtin": True, "tools": ["web_search"]},
    {"id": "code_review", "name": "Code Review", "description": "Review code", "enabled": False, "builtin": True, "tools": ["read_file"]},
    {"id": "my_custom", "name": "My Custom", "description": "Custom skill", "enabled": True, "builtin": False, "tools": []},
]

_SAMPLE_CURATOR = {
    "pinned": ["web_search"],
    "archived": [],
    "usage_counts": {"web_search": 42, "code_review": 5},
}


@pytest.fixture()
def mock_skills():
    with patch(
        "icecode_server.routes.skills._build_skill_list",
        return_value=_SAMPLE_SKILLS,
    ):
        yield


@pytest.fixture()
def mock_overrides():
    store = {}
    with patch(
        "icecode_server.routes.skills._load_overrides",
        return_value=dict(store),
    ), patch(
        "icecode_server.routes.skills._save_overrides",
        side_effect=lambda d: store.update(d),
    ) as mock_save:
        yield mock_save


@pytest.fixture()
def mock_curator():
    store = dict(_SAMPLE_CURATOR)
    with patch(
        "icecode_server.routes.skills._load_curator",
        return_value=dict(store),
    ), patch(
        "icecode_server.routes.skills._save_curator",
        side_effect=lambda d: store.update(d),
    ) as mock_save:
        yield mock_save


# ---------------------------------------------------------------------------
# GET /api/skills/
# ---------------------------------------------------------------------------

class TestListSkills:
    def test_list_returns_200(self, client):
        resp = client.get("/api/skills/")
        assert resp.status_code == 200

    def test_list_returns_list(self, client):
        data = client.get("/api/skills/").json()
        assert isinstance(data, list)

    def test_list_with_mock_returns_sample(self, client, mock_skills):
        data = client.get("/api/skills/").json()
        assert len(data) == 3

    def test_each_skill_has_id(self, client, mock_skills):
        data = client.get("/api/skills/").json()
        for s in data:
            assert "id" in s

    def test_each_skill_has_enabled_flag(self, client, mock_skills):
        data = client.get("/api/skills/").json()
        for s in data:
            assert "enabled" in s
            assert isinstance(s["enabled"], bool)


# ---------------------------------------------------------------------------
# GET /api/skills/stats
# ---------------------------------------------------------------------------

class TestSkillStats:
    def test_stats_returns_200(self, client):
        resp = client.get("/api/skills/stats")
        assert resp.status_code == 200

    def test_stats_has_counts(self, client, mock_skills):
        data = client.get("/api/skills/stats").json()
        assert "total" in data
        assert "enabled" in data
        assert "builtin" in data
        assert "custom" in data

    def test_stats_total_matches_list(self, client, mock_skills):
        stats = client.get("/api/skills/stats").json()
        skills = client.get("/api/skills/").json()
        assert stats["total"] == len(skills)

    def test_stats_enabled_count_correct(self, client, mock_skills):
        stats = client.get("/api/skills/stats").json()
        skills = client.get("/api/skills/").json()
        enabled_count = sum(1 for s in skills if s.get("enabled"))
        assert stats["enabled"] == enabled_count

    def test_stats_builtin_custom_sum_to_total(self, client, mock_skills):
        data = client.get("/api/skills/stats").json()
        assert data["builtin"] + data["custom"] == data["total"]


# ---------------------------------------------------------------------------
# PUT /api/skills/{id}/toggle
# ---------------------------------------------------------------------------

class TestToggleSkill:
    def test_toggle_disable_returns_ok(self, client, mock_skills, mock_overrides):
        resp = client.put("/api/skills/web_search/toggle", json={"enabled": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["skill_id"] == "web_search"
        assert data["enabled"] is False

    def test_toggle_enable_returns_ok(self, client, mock_skills, mock_overrides):
        resp = client.put("/api/skills/code_review/toggle", json={"enabled": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True

    def test_toggle_calls_save(self, client, mock_skills, mock_overrides):
        client.put("/api/skills/web_search/toggle", json={"enabled": False})
        mock_overrides.assert_called()


# ---------------------------------------------------------------------------
# POST /api/skills/discover
# ---------------------------------------------------------------------------

class TestDiscoverSkills:
    def test_discover_returns_200(self, client):
        resp = client.post("/api/skills/discover")
        assert resp.status_code == 200

    def test_discover_has_count(self, client, mock_skills):
        data = client.post("/api/skills/discover").json()
        assert "count" in data
        assert data["count"] == 3

    def test_discover_has_ok(self, client, mock_skills):
        data = client.post("/api/skills/discover").json()
        assert data.get("ok") is True


# ---------------------------------------------------------------------------
# POST /api/skills/ (create custom skill)
# ---------------------------------------------------------------------------

class TestCreateSkill:
    def test_create_returns_200(self, client, tmp_path):
        with patch("icecode.config.settings.ICECodeSettings") as mock_cfg:
            mock_cfg.return_value.home_dir = tmp_path
            resp = client.post("/api/skills/", json={
                "name": "My Test Skill",
                "description": "Does something useful",
                "tools": ["read_file", "web_search"],
            })
        assert resp.status_code == 200

    def test_create_returns_id(self, client, tmp_path):
        with patch("icecode.config.settings.ICECodeSettings") as mock_cfg:
            mock_cfg.return_value.home_dir = tmp_path
            resp = client.post("/api/skills/", json={"name": "Alpha Skill"})
        data = resp.json()
        assert "id" in data
        assert data["id"] == "alpha_skill"

    def test_create_missing_name_returns_400(self, client):
        resp = client.post("/api/skills/", json={"description": "no name"})
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Curator endpoints
# ---------------------------------------------------------------------------

class TestCuratorStatus:
    def test_status_returns_200(self, client):
        resp = client.get("/api/skills/curator/status")
        assert resp.status_code == 200

    def test_status_has_pinned_and_archived(self, client, mock_skills, mock_curator):
        data = client.get("/api/skills/curator/status").json()
        assert "pinned" in data
        assert "archived" in data
        assert isinstance(data["pinned"], list)
        assert isinstance(data["archived"], list)

    def test_status_pinned_contains_expected(self, client, mock_skills, mock_curator):
        data = client.get("/api/skills/curator/status").json()
        assert "web_search" in data["pinned"]


class TestCuratorPin:
    def test_pin_skill_returns_ok(self, client, mock_skills, mock_curator):
        resp = client.post("/api/skills/curator/pin/code_review")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_pin_saves_curator(self, client, mock_skills, mock_curator):
        client.post("/api/skills/curator/pin/new_skill")
        mock_curator.assert_called()

    def test_unpin_skill_returns_ok(self, client, mock_skills, mock_curator):
        resp = client.post("/api/skills/curator/unpin/web_search")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestCuratorArchive:
    def test_archive_returns_ok(self, client, mock_skills, mock_overrides, mock_curator):
        resp = client.post("/api/skills/curator/archive/code_review")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_restore_returns_ok(self, client, mock_skills, mock_overrides, mock_curator):
        resp = client.post("/api/skills/curator/restore/code_review")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestCuratorRun:
    def test_curator_run_returns_200(self, client, mock_skills, mock_curator):
        resp = client.post("/api/skills/curator/run")
        assert resp.status_code == 200

    def test_curator_run_has_suggestions_key(self, client, mock_skills, mock_curator):
        data = client.post("/api/skills/curator/run").json()
        assert "suggestions" in data or "report" in data or "ok" in data


# ---------------------------------------------------------------------------
# Library endpoints
# ---------------------------------------------------------------------------

class TestSkillLibrary:
    def test_library_returns_200(self, client):
        resp = client.get("/api/skills/library")
        assert resp.status_code == 200

    def test_library_categories_returns_200(self, client):
        resp = client.get("/api/skills/library/categories")
        assert resp.status_code == 200

    def test_library_is_list_or_dict(self, client):
        data = client.get("/api/skills/library").json()
        assert isinstance(data, (list, dict))
