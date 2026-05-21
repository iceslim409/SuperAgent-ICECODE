"""
ICECODE Browser Tool API — headless browser automation via Playwright.
Ported from Hermes browser_tool.
"""
from __future__ import annotations

import asyncio
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/browser", tags=["browser"])


async def _get_browser():
    """Lazy-load playwright browser."""
    from playwright.async_api import async_playwright
    return async_playwright


class NavigateRequest(BaseModel):
    url: str
    wait_for: str = "load"     # load | networkidle | domcontentloaded
    timeout: int = 15000
    extract: str = "text"      # text | html | links | screenshot | structured


class ClickRequest(BaseModel):
    url: str
    selector: str
    timeout: int = 10000


class FillRequest(BaseModel):
    url: str
    fields: dict   # {selector: value}
    submit_selector: Optional[str] = None


class ScrapRequest(BaseModel):
    url: str
    selectors: dict  # {name: css_selector}
    timeout: int = 15000


@router.post("/navigate")
async def browser_navigate(req: NavigateRequest):
    """Navigate to URL and extract content using headless Chromium."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page()
            page.set_default_timeout(req.timeout)

            await page.goto(req.url, wait_until=req.wait_for)
            title = await page.title()

            if req.extract == "text":
                content = await page.inner_text("body")
                content = content[:8000]
                result = {"url": req.url, "title": title, "text": content}

            elif req.extract == "html":
                content = await page.content()
                content = content[:8000]
                result = {"url": req.url, "title": title, "html": content}

            elif req.extract == "links":
                links = await page.eval_on_selector_all(
                    "a[href]",
                    "els => els.map(e => ({text: e.innerText.trim(), href: e.href})).slice(0,50)"
                )
                result = {"url": req.url, "title": title, "links": links}

            elif req.extract == "screenshot":
                screenshot = await page.screenshot(type="png")
                import base64
                result = {
                    "url": req.url, "title": title,
                    "screenshot_b64": base64.b64encode(screenshot).decode(),
                    "size": len(screenshot),
                }

            elif req.extract == "structured":
                # Extract main content, headings, and key data
                content = await page.evaluate("""() => {
                    const h = Array.from(document.querySelectorAll('h1,h2,h3')).slice(0,10).map(e=>e.innerText.trim());
                    const p = Array.from(document.querySelectorAll('p')).slice(0,20).map(e=>e.innerText.trim()).filter(t=>t.length>50);
                    const code = Array.from(document.querySelectorAll('code,pre')).slice(0,5).map(e=>e.innerText.trim());
                    return {headings: h, paragraphs: p.slice(0,10), code_blocks: code};
                }""")
                result = {"url": req.url, "title": title, **content}

            else:
                result = {"url": req.url, "title": title}

            await browser.close()
            return result

    except ImportError:
        raise HTTPException(503, "Playwright not installed. Run: playwright install chromium")
    except Exception as e:
        raise HTTPException(500, f"Browser error: {e}")


@router.post("/scrape")
async def browser_scrape(req: ScrapRequest):
    """Scrape specific CSS selectors from a page."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page()
            page.set_default_timeout(req.timeout)
            await page.goto(req.url, wait_until="load")

            result = {"url": req.url}
            for name, selector in req.selectors.items():
                try:
                    elements = await page.query_selector_all(selector)
                    texts = []
                    for el in elements[:20]:
                        text = await el.inner_text()
                        texts.append(text.strip())
                    result[name] = texts
                except Exception:
                    result[name] = []

            await browser.close()
            return result

    except ImportError:
        raise HTTPException(503, "Playwright not installed. Run: playwright install chromium")
    except Exception as e:
        raise HTTPException(500, f"Browser error: {e}")


@router.post("/fill-and-submit")
async def browser_fill(req: FillRequest):
    """Fill a form and optionally submit."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page()
            await page.goto(req.url, wait_until="load")

            for selector, value in req.fields.items():
                await page.fill(selector, str(value))

            if req.submit_selector:
                await page.click(req.submit_selector)
                await page.wait_for_load_state("load")

            title = await page.title()
            text = (await page.inner_text("body"))[:3000]
            await browser.close()
            return {"ok": True, "title": title, "result_text": text}

    except ImportError:
        raise HTTPException(503, "Playwright not installed. Run: playwright install chromium")
    except Exception as e:
        raise HTTPException(500, f"Browser error: {e}")


@router.get("/status")
async def browser_status():
    """Check if playwright is available and usable."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            version = browser.version
            await browser.close()
            return {"available": True, "chromium_version": version}
    except ImportError:
        return {"available": False, "error": "playwright not installed"}
    except Exception as e:
        return {"available": False, "error": str(e)}
