"""Generate animated GIF demo of ICECODE for the README."""
import time, io
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw, ImageFont

BASE = "http://127.0.0.1:13210"
OUT  = Path(__file__).parents[1] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1280, 800

PAGES = [
    ("dashboard",  None,          "Dashboard — live stats & system health",           4000),
    ("chat",       "chat",        "Chat — real-time streaming with any LLM",           4000),
    ("swarm",      "swarm",       "Swarm — multi-agent pipeline orchestration",        4000),
    ("knowledge",  "knowledge",   "Knowledge — local RAG, 100% offline",              4000),
    ("optimizer",  "optimizer",   "Cost Optimizer — semantic cache + smart routing",  4000),
    ("debug",      "debug",       "Auto-Debug — full project health in one click",    4000),
    ("benchmark",  "benchmark",   "Benchmark — compare LLMs side-by-side",            4000),
]

def label(img, text):
    img = img.copy()
    d = ImageDraw.Draw(img)
    bh = 46
    d.rectangle([(0, H-bh),(W, H)], fill=(12,12,18))
    d.rectangle([(14, H-bh+9),(116, H-9)], fill=(255,204,0))
    try:
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        fr = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    except:
        fb = fr = ImageFont.load_default()
    d.text((20, H-bh+15), "ICECODE", fill=(0,0,0), font=fb)
    d.text((126, H-bh+16), text, fill=(210,210,210), font=fr)
    return img

def main():
    frames = []
    ARGS = ['--no-sandbox','--disable-dev-shm-usage','--disable-gpu',
            '--single-process','--no-zygote']

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=ARGS)
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(BASE, wait_until="commit", timeout=20000)
        time.sleep(4)  # wait for dashboard API calls to complete

        for slug, page_id, lbl, ms in PAGES:
            print(f"  📸 {lbl}")
            if page_id:
                try:
                    pg.evaluate(f"() => showPage('{page_id}')")
                    time.sleep(2.5)  # wait for page data to load
                except:
                    pass
            else:
                time.sleep(2.5)

            raw = pg.screenshot()
            img = Image.open(io.BytesIO(raw)).convert("RGB").resize((W,H), Image.LANCZOS)
            img = label(img, lbl)
            img.save(OUT / f"{slug}.png")
            frames.append((img, ms))
        b.close()

    print(f"\n🎬 Building GIF ({len(frames)} frames)…")
    TW, TH = 960, 600
    imgs = [f[0].resize((TW,TH), Image.LANCZOS) for f in frames]
    durs = [f[1] for f in frames]

    gif = OUT / "demo.gif"
    imgs[0].save(gif, save_all=True, append_images=imgs[1:],
                 duration=durs, loop=0, optimize=True)
    print(f"✓ {gif}  ({gif.stat().st_size/1024/1024:.1f} MB)")

if __name__ == "__main__":
    main()
