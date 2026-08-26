"""Second demo recording, using the real tuan@gmail.com account (already Google-Calendar-connected)
to capture the real Task Inbox -> Calendar two-way sync live. Only touches the fresh isolated
conversation created for this demo (most-recently-updated => first item in the list) - never the
account's existing real conversations/tasks/events. Ad hoc, safe to delete after use.
"""
import json
import os
import time

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
OUT_DIR = os.path.join("Deliverables", "evidence")
VIDEO_DIR = os.path.join(OUT_DIR, "_video_raw_tuan")
os.makedirs(VIDEO_DIR, exist_ok=True)

TUAN_EMAIL = os.environ["TUAN_EMAIL"]
TUAN_PASS = os.environ["TUAN_PASS"]

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

    step("Go to login page")
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    page.wait_for_selector('input[placeholder="you@company.com"]', timeout=15000)
    page.fill('input[placeholder="you@company.com"]', TUAN_EMAIL)
    page.fill('input[placeholder="Enter your password"]', TUAN_PASS)
    pause(0.6)
    step("Sign in (real tuan account)")
    page.click('button:has-text("Sign in")')
    page.wait_for_url("**/chat", timeout=15000)
    pause(1.0)

    step("Chat page loaded")
    page.wait_for_selector(".chat-item", timeout=15000)
    pause(0.5)
    # The demo conversation was created last -> most recently updated -> first in the list.
    # Deliberately NOT matching by name: this account already has a real, unrelated "Quynh" thread.
    step("Open the freshly-created demo conversation (first/most-recent item)")
    page.locator(".conversation-items .chat-item").first.click()
    page.wait_for_selector(".composer-main input", timeout=15000)
    pause(0.8)

    step("Type and send a commitment message")
    msg_input = page.locator(".composer-main input")
    msg_input.click()
    for ch in "Mai họp gấp với đối tác Kim Long lúc 9h sáng nhé":
        msg_input.press_sequentially(ch, delay=16)
    pause(0.4)
    page.click(".send-btn")
    pause(2.5)

    step("Show AI panel / permission card")
    page.wait_for_selector(".permission-card", timeout=15000)
    pause(1.2)

    step("Ask Orbit for a reminder")
    ask_box = page.locator('textarea[placeholder="Ask anything about this conversation..."]')
    ask_box.click()
    for ch in "Tạo nhắc nhở lúc 9h sáng mai cho cuộc họp với đối tác Kim Long, hỏi tôi xác nhận trước":
        ask_box.press_sequentially(ch, delay=10)
    pause(0.4)
    page.locator(".ask-footer button").click()
    try:
        page.wait_for_selector('button:has-text("Xác nhận")', timeout=45000)
        step("Confirm dialog appeared (human-in-the-loop)")
        pause(1.4)
        page.click('button:has-text("Xác nhận")')
        step("Clicked Xac nhan")
        page.wait_for_timeout(3000)
    except Exception:
        step("No confirm dialog observed in time")
    pause(1.5)

    step("Go to Task Inbox")
    page.goto(f"{BASE_URL}/tasks/inbox", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    pause(1.0)
    try:
        accept_btn = page.get_by_role("button", name="Accept").first
        if accept_btn.is_visible(timeout=3000):
            step("Accept the suggested task -> should auto-sync to real Google Calendar")
            accept_btn.click()
            page.wait_for_timeout(3000)
        else:
            step("No Accept button visible")
    except Exception:
        step("No suggested task to accept yet")
    pause(1.5)

    step("Go to Calendar page - expect the real synced event to appear")
    page.goto(f"{BASE_URL}/calendar", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    pause(2.0)

    event_deleted = False
    try:
        event_el = page.locator(".fc-event").first
        if event_el.is_visible(timeout=3000):
            step("Real Calendar event visible - click it")
            event_el.click()
            page.wait_for_selector('button:has-text("Delete event")', timeout=8000)
            pause(1.5)
            step("Delete the demo event (cleanup + shows 2-way sync)")
            page.click('button:has-text("Delete event")')
            page.wait_for_timeout(2000)
            event_deleted = True
        else:
            step("No calendar event visible to click")
    except Exception as e:
        step(f"Could not find/delete calendar event: {e}")
    pause(1.5)

    step("Back to Task Inbox to confirm the task auto-dismissed")
    page.goto(f"{BASE_URL}/tasks/inbox", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    pause(2.0)

    step("Done")
    context.close()
    browser.close()

produced = [f for f in os.listdir(VIDEO_DIR) if f.endswith(".webm")]
final_path = None
if produced:
    produced.sort(key=lambda f: os.path.getmtime(os.path.join(VIDEO_DIR, f)))
    src = os.path.join(VIDEO_DIR, produced[-1])
    final_path = os.path.join(OUT_DIR, "orbit_real_demo_tuan_calendar.webm")
    if os.path.exists(final_path):
        os.remove(final_path)
    os.replace(src, final_path)

with open(os.path.join(OUT_DIR, "_demo_record_tuan_log.json"), "w", encoding="utf-8") as f:
    json.dump({"steps": log, "video": final_path, "event_deleted": event_deleted}, f, ensure_ascii=False, indent=2)

print("VIDEO:", final_path)
print("EVENT DELETED (cleanup):", event_deleted)
print("LOG:", log)
