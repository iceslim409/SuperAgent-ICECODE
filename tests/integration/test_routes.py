"""Integration tests for ICECODE API routes — chat, gateway, cron, kanban, settings, agents."""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "core"))
sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "server"))


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from icecode_server.main import app
    return TestClient(app)


class TestStatusRoutes:
    def test_status(self, client):
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert "systems" in data
        assert data["systems"]["agent"] == "ready"

    def test_metrics(self, client):
        r = client.get("/api/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "uptime_seconds" in data
        assert "routes_registered" in data
        assert data["routes_registered"] > 0


class TestChatRoutes:
    def test_list_sessions(self, client):
        r = client.get("/api/chat/sessions")
        assert r.status_code == 200

    def test_get_nonexistent_session(self, client):
        r = client.get("/api/chat/sessions/definitely_not_real_xyz")
        assert r.status_code == 404

    def test_chat_memories(self, client):
        r = client.get("/api/chat/memories")
        assert r.status_code == 200


class TestGatewayRoutes:
    def test_list_channels(self, client):
        r = client.get("/api/channels/")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_channel_platforms(self, client):
        r = client.get("/api/channels/platforms")
        assert r.status_code == 200

    def test_gateway_status(self, client):
        r = client.get("/api/gateway/status")
        assert r.status_code == 200


class TestCronRoutes:
    def test_list_jobs(self, client):
        r = client.get("/api/cron/")
        assert r.status_code == 200

    def test_create_job(self, client):
        r = client.post("/api/cron/", json={
            "name": "test_ci_job",
            "schedule": "0 * * * *",
            "task_type": "echo",
            "task_payload": {"cmd": "echo test"},
        })
        assert r.status_code in (200, 201, 422)


class TestKanbanRoutes:
    def test_list_boards(self, client):
        r = client.get("/api/kanban/boards")
        assert r.status_code == 200

    def test_list_tasks(self, client):
        r = client.get("/api/kanban/tasks")
        assert r.status_code == 200

    def test_kanban_stats(self, client):
        r = client.get("/api/kanban/stats")
        assert r.status_code == 200


class TestSettingsRoutes:
    def test_get_settings(self, client):
        r = client.get("/api/settings/")
        assert r.status_code == 200

    def test_get_models(self, client):
        r = client.get("/api/models/")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))


class TestAgentsRoutes:
    def test_list_agents(self, client):
        r = client.get("/api/agents/")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_auto_models(self, client):
        r = client.get("/api/agents/auto-models")
        assert r.status_code == 200


class TestGoalsRoutes:
    def test_list_goals(self, client):
        r = client.get("/api/goals/")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_active_prompt(self, client):
        r = client.get("/api/goals/active-prompt")
        assert r.status_code == 200

    def test_create_goal(self, client):
        r = client.post("/api/goals/", json={"title": "CI test goal", "description": "automated"})
        assert r.status_code in (200, 201, 422)


class TestSkillsRoutes:
    def test_list_skills(self, client):
        r = client.get("/api/skills/")
        assert r.status_code == 200

    def test_skills_stats(self, client):
        r = client.get("/api/skills/stats")
        assert r.status_code == 200

    def test_discover_skills(self, client):
        r = client.post("/api/skills/discover", json={})
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True


class TestSwarmRoutes:
    def test_list_templates(self, client):
        r = client.get("/api/swarm/templates")
        assert r.status_code == 200
        data = r.json()
        assert "templates" in data
        ids = [t["id"] for t in data["templates"]]
        assert "research_write" in ids

    def test_template_detail(self, client):
        r = client.get("/api/swarm/templates/brainstorm")
        assert r.status_code == 200
        assert r.json()["mode"] == "parallel"

    def test_nonexistent_template(self, client):
        r = client.get("/api/swarm/templates/does_not_exist")
        assert r.status_code == 404


class TestKnowledgeRoutes:
    def test_stats(self, client):
        r = client.get("/api/knowledge/stats")
        assert r.status_code == 200
        assert "rag_available" in r.json()

    def test_sources(self, client):
        r = client.get("/api/knowledge/sources")
        assert r.status_code == 200
        assert "sources" in r.json()


class TestOpenCodeCompatRoutes:
    """OpenCode-compatible API layer (TypeScript SDK integration)."""

    def test_list_sessions(self, client):
        r = client.get("/session")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_session(self, client):
        r = client.post("/session", json={})
        assert r.status_code in (200, 201)
        data = r.json()
        assert "id" in data

    def test_list_providers(self, client):
        r = client.get("/provider")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_config(self, client):
        r = client.get("/config")
        assert r.status_code == 200

    def test_get_current_project(self, client):
        r = client.get("/project/current")
        assert r.status_code == 200
        data = r.json()
        assert "directory" in data


class TestMCPRoutes:
    def test_list_servers_empty(self, client):
        r = client.get("/api/mcp/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_add_server(self, client):
        r = client.post("/api/mcp/", json={
            "name": "test-fs",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
            "env": {},
        })
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "test-fs"
        assert data["transport"] == "stdio"
        assert "id" in data
        assert data["status"] == "disconnected"
        return data["id"]

    def test_connect_server(self, client):
        # stdio transport without a real command returns ok:False — just verify status 200
        r = client.post("/api/mcp/", json={"name": "conn-test", "transport": "stdio", "command": "echo"})
        sid = r.json()["id"]
        r2 = client.post(f"/api/mcp/{sid}/connect", json={})
        assert r2.status_code == 200
        assert "ok" in r2.json()
        client.delete(f"/api/mcp/{sid}")

    def test_delete_server(self, client):
        r = client.post("/api/mcp/", json={"name": "del-test", "transport": "stdio"})
        sid = r.json()["id"]
        r2 = client.delete(f"/api/mcp/{sid}")
        assert r2.status_code == 200
        assert r2.json()["ok"] is True
        servers = client.get("/api/mcp/").json()
        assert not any(s["id"] == sid for s in servers)

    def test_add_sse_server(self, client):
        r = client.post("/api/mcp/", json={
            "name": "sse-server",
            "transport": "sse",
            "url": "http://localhost:8080/mcp",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["transport"] == "sse"
        client.delete(f"/api/mcp/{data['id']}")
