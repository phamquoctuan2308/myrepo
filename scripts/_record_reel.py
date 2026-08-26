"""Records the self-playing Orbit demo reel (Deliverables/orbit_demo_reel.html) as a real
silent video, in real time, by driving Chromium via Playwright and clicking Play. Ad hoc,
safe to delete after use.
"""
import os
import time

from playwright.sync_api import sync_playwright

REEL_PATH = os.path.abspath(os.path.join("Deliverables", "orbit_demo_reel.html"))
OUT_DIR = os.path.join("Deliverables", "evidence")
VIDEO_DIR = os.path.join(OUT_DIR, "_video_raw_reel")
os.makedirs(VIDEO_DIR, exist_ok=True)

DURATION_S = 178

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1120, "height": 900},
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1120, "height": 900},
    )
    page = context.new_page()
    page.goto(f"file:///{REEL_PATH}", wait_until="domcontentloaded")
    page.wait_for_selector("#playBtn", timeout=10000)
    time.sleep(0.3)
    page.click("#playBtn")
    print("playing, waiting", DURATION_S, "s ...")
    time.sleep(DURATION_S + 2)
    context.close()
    browser.close()

produced = [f for f in os.listdir(VIDEO_DIR) if f.endswith(".webm")]
produced.sort(key=lambda f: os.path.getmtime(os.path.join(VIDEO_DIR, f)))
src = os.path.join(VIDEO_DIR, produced[-1])
final = os.path.join(OUT_DIR, "orbit_reel_raw.webm")
if os.path.exists(final):
    os.remove(final)
os.replace(src, final)
print("VIDEO:", final)
