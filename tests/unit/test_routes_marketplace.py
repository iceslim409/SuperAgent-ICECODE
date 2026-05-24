"""Tests for /api/marketplace routes."""
import base64
import json
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


def _encode(skill: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(skill).encode()).decode()


class TestListSkills:
    def test_returns_200(self, client):
        r = client.get("/api/marketplace/skills")
        assert r.status_code == 200

    def test_returns_list(self, client):
        data = client.get("/api/marketplace/skills").json()
        assert isinstance(data, list)

    def test_has_featured_skills(self, client):
        data = client.get("/api/marketplace/skills").json()
        assert len(data) > 0

    def test_code_reviewer_present(self, client):
        data = client.get("/api/marketplace/skills").json()
        names = [s.get("name") for s in data]
        assert "Code Reviewer" in names

    def test_search_filters(self, client):
        data = client.get("/api/marketplace/skills?search=code").json()
        assert all("code" in s.get("name", "").lower() or
                   "code" in s.get("description", "").lower() or
                   any("code" in t for t in s.get("tags", []))
                   for s in data)


class TestPublishSkill:
    def test_returns_200(self, client):
        skill = {"name": "TestSkill", "description": "A test skill", "tools": []}
        with patch("icecode_server.routes.marketplace._MARKET_DIR") as mock_dir:
            mock_path = MagicMock()
            mock_dir.__truediv__ = MagicMock(return_value=mock_path)
            r = client.post("/api/marketplace/publish", json={"skill": skill})
        assert r.status_code == 200

    def test_returns_code(self, client):
        skill = {"name": "TestSkill", "description": "d", "tools": []}
        with patch("icecode_server.routes.marketplace._MARKET_DIR") as mock_dir:
            mock_path = MagicMock()
            mock_dir.__truediv__ = MagicMock(return_value=mock_path)
            data = client.post("/api/marketplace/publish", json={"skill": skill}).json()
        assert "code" in data

    def test_missing_name_returns_400(self, client):
        r = client.post("/api/marketplace/publish", json={"skill": {"description": "no name"}})
        assert r.status_code == 400


class TestImportSkill:
    def test_import_valid_code(self, client):
        skill = {"name": "Imported", "id": "imported", "tools": []}
        code = _encode(skill)
        with patch("icecode_server.routes.marketplace._MARKET_DIR") as mock_dir:
            mock_path = MagicMock()
            mock_dir.__truediv__ = MagicMock(return_value=mock_path)
            r = client.post("/api/marketplace/import", json={"code": code})
        assert r.status_code == 200

    def test_import_returns_skill(self, client):
        skill = {"name": "Imported2", "id": "imported2", "tools": []}
        code = _encode(skill)
        with patch("icecode_server.routes.marketplace._MARKET_DIR") as mock_dir:
            mock_path = MagicMock()
            mock_dir.__truediv__ = MagicMock(return_value=mock_path)
            data = client.post("/api/marketplace/import", json={"code": code}).json()
        # Response may be the skill directly or wrapped in {"ok": True, "skill": {...}}
        skill_data = data.get("skill", data)
        assert skill_data.get("name") == "Imported2"

    def test_import_invalid_code_400(self, client):
        r = client.post("/api/marketplace/import", json={"code": "not_valid_base64!!!"})
        assert r.status_code == 400


class TestDeleteSkill:
    def test_delete_nonexistent_404(self, client):
        with patch("icecode_server.routes.marketplace._MARKET_DIR") as mock_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_dir.__truediv__ = MagicMock(return_value=mock_path)
            r = client.delete("/api/marketplace/skills/ghost_skill")
        assert r.status_code == 404
