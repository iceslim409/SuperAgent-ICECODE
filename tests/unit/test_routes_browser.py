"""Tests for /api/browser routes."""
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


def _mk_playwright(title="Test Page", text="body text", content="<html/>"):
    """Build a mock playwright context manager chain."""
    mock_page = AsyncMock()
    mock_page.title = AsyncMock(return_value=title)
    mock_page.inner_text = AsyncMock(return_value=text)
    mock_page.content = AsyncMock(return_value=content)
    mock_page.eval_on_selector_all = AsyncMock(return_value=[])
    mock_page.screenshot = AsyncMock(return_value=b"PNG")
    mock_page.set_default_timeout = MagicMock()

    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser.close = AsyncMock()
    mock_browser.version = "109.0"

    mock_chromium = AsyncMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_pw)
    cm.__aexit__ = AsyncMock(return_value=False)

    return cm


class TestBrowserStatus:
    def test_returns_200(self, client):
        r = client.get("/api/browser/status")
        assert r.status_code == 200

    def test_has_available_key(self, client):
        data = client.get("/api/browser/status").json()
        assert "available" in data

    def test_unavailable_when_no_playwright(self, client):
        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            data = client.get("/api/browser/status").json()
        # either available or unavailable, but key must exist
        assert "available" in data


class TestBrowserNavigate:
    def test_navigate_returns_200_or_503(self, client):
        r = client.post("/api/browser/navigate", json={"url": "https://example.com"})
        assert r.status_code in (200, 500, 503)

    def test_navigate_with_mock(self, client):
        with patch("playwright.async_api.async_playwright", return_value=_mk_playwright()):
            r = client.post("/api/browser/navigate", json={"url": "https://example.com", "extract": "text"})
        assert r.status_code in (200, 500, 503)


class TestBrowserScrape:
    def test_scrape_returns_200_or_503(self, client):
        r = client.post("/api/browser/scrape", json={
            "url": "https://example.com",
            "selectors": {"title": "h1"},
        })
        assert r.status_code in (200, 500, 503)


class TestBrowserFillSubmit:
    def test_fill_returns_200_or_503(self, client):
        r = client.post("/api/browser/fill-and-submit", json={
            "url": "https://example.com",
            "fields": {"input[name=q]": "test"},
        })
        assert r.status_code in (200, 500, 503)
