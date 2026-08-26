"""One-off script: drives the REAL running Orbit app (localhost:5173 / :8000) with a real
Chromium browser via Playwright and records a real .webm video of the session. Not part of the
test suite - ad hoc tooling for producing a genuine product demo recording, safe to delete after use.
"""
import json
import os
import time

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
OUT_DIR = os.path.join("Deliverables", "evidence")
VIDEO_DIR = os.path.join(OUT_DIR, "_video_raw")
os.makedirs(VIDEO_DIR, exist_ok=True)

with open(os.path.join(OUT_DIR, "_demo_setup.json"), encoding="utf-8") as f:
    setup = json.load(f)
an = setup["an"]

def pause(seconds):
    time.sleep(seconds)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1440, "height": 900},
    )
    page = context.new_page()
    log = []

    def step(label):
        log.append(label)
        print("STEP:", label)

    # 1. Login as An (real form, real JWT)
    step("Go to login page")
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    page.wait_for_selector('input[placeholder="you@company.com"]', timeout=15000)
    page.fill('input[placeholder="you@company.com"]', an["email"])
    page.fill('input[placeholder="Enter your password"]', an["password"])
    pause(0.6)
    step("Sign in")
    page.click('button:has-text("Sign in")')
    page.wait_for_url("**/chat", timeout=15000)
    pause(1.0)

    # 2. Open the An<->Quynh conversation (login already lands on /chat)
    step("Chat page loaded")
    page.wait_for_selector(".chat-item", timeout=15000)
    pause(0.5)
    step("Open conversation with Quynh")
    page.click('.chat-item:has-text("Quỳnh")')
    page.wait_for_selector(".composer-main input", timeout=15000)
    pause(0.8)

    # 3. Send a real message that should trip proactive detection
    step("Type and send a commitment message")
    msg_input = page.locator(".composer-main input")
    msg_input.click()
    msg_input.fill("")
    for ch in "Mai họp gấp với đối tác Kim Long lúc 9h sáng nhé":
        msg_input.press_sequentially(ch, delay=18)
    pause(0.4)
    page.click(".send-btn")
    pause(2.0)

    # 4. AI panel is a permanent column at this viewport width (>1200px) - no need to open it.
    step("Show AI panel / permission card")
    page.wait_for_selector(".permission-card", timeout=15000)
    pause(1.2)

    # 5. Quick action: Summarize (real LLM call)
    step("Click Summarize quick action")
    summarize_btn = page.get_by_role("button", name="Summarize")
    summarize_btn.click()
    try:
        page.wait_for_selector(".ai-panel >> text=Summary", timeout=45000)
        step("Summarize result rendered")
    except Exception:
        step("Summarize result did not render in time (continuing)")
    pause(2.0)

    # 6. Ask Orbit: request a reminder -> expect human-in-the-loop confirm
    step("Ask Orbit for a reminder")
    ask_box = page.locator('textarea[placeholder="Ask anything about this conversation..."]')
    ask_box.click()
    for ch in "Tạo nhắc nhở lúc 9h sáng mai cho cuộc họp với đối tác Kim Long, hỏi tôi xác nhận trước":
        ask_box.press_sequentially(ch, delay=12)
    pause(0.4)
    page.locator(".ask-footer button").click()

    confirmed = False
    try:
        page.wait_for_selector('button:has-text("Xác nhận")', timeout=45000)
        step("Confirm dialog appeared (human-in-the-loop)")
        pause(1.4)
        page.click('button:has-text("Xác nhận")')
        confirmed = True
        step("Clicked Xac nhan")
        page.wait_for_timeout(3000)
    except Exception:
        step("No confirm dialog observed in time (agent may have answered directly)")
    pause(1.5)

    # 7. Task Inbox - show real state (whatever proactive detection produced by now)
    step("Go to Task Inbox")
    page.goto(f"{BASE_URL}/tasks/inbox", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    pause(1.5)
    try:
        accept_btn = page.get_by_role("button", name="Accept").first
        if accept_btn.is_visible(timeout=2000):
            step("Accept a suggested task")
            accept_btn.click()
            page.wait_for_timeout(2000)
    except Exception:
        step("No suggested task to accept yet (proactive detection may still be running)")
    pause(1.5)

    # 8. Calendar page - real state (not connected, honest)
    step("Go to Calendar page")
    page.goto(f"{BASE_URL}/calendar", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    pause(2.0)

    step("Done")
    context.close()
    browser.close()

# Locate the produced video file and rename it clearly.
produced = [f for f in os.listdir(VIDEO_DIR) if f.endswith(".webm")]
final_path = None
if produced:
    produced.sort(key=lambda f: os.path.getmtime(os.path.join(VIDEO_DIR, f)))
    src = os.path.join(VIDEO_DIR, produced[-1])
    final_path = os.path.join(OUT_DIR, "orbit_real_demo.webm")
    if os.path.exists(final_path):
        os.remove(final_path)
    os.replace(src, final_path)

with open(os.path.join(OUT_DIR, "_demo_record_log.json"), "w", encoding="utf-8") as f:
    json.dump({"steps": log, "video": final_path}, f, ensure_ascii=False, indent=2)

print("VIDEO:", final_path)
print("LOG:", log)
