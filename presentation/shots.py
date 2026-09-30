"""Capture real screenshots of the running prototype for the deck (API on :8010, web on :3000).

Uses the installed Microsoft Edge. Staff pages log in with the demo curator account from
data/demo_users.local.txt (gitignored); credentials are never printed.
"""
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "shots"
CREDS = HERE.parent / "data" / "demo_users.local.txt"
WEB = "http://localhost:3000"

PUBLIC = {
    "search_glacier": "/search?q=Dakshin+Gangotri+glacier+movement",
    "page_viewer": "/page/167/10",
    "expedition_isea9": "/expeditions/ISEA-9",
    "coverage": "/coverage",
    "ask_refusal": None,  # filled by interaction below
}
STAFF = {"review_answer": "/staff/review/1", "review_lesson": "/staff/review/2"}


def main() -> None:
    creds = dict(re.findall(r"username=(\S+) password=(\S+)", CREDS.read_text(encoding="utf-8")))
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        for name, path in PUBLIC.items():
            if path is None:
                continue
            page.goto(WEB + path, wait_until="networkidle", timeout=120_000)
            page.screenshot(path=str(OUT / f"{name}.png"))
            print("saved", name)

        page.goto(WEB + "/ask", wait_until="networkidle")
        page.fill("#question", "How fast do Mars rovers drive?")
        page.click("button:has-text('Ask')")
        page.wait_for_selector("text=No NCPOR source found", timeout=120_000)
        page.screenshot(path=str(OUT / "ask_refusal.png"))
        print("saved ask_refusal")

        page.goto(WEB + "/staff", wait_until="networkidle")
        page.fill("#username", "curator")
        page.fill("#password", creds["curator"])
        page.click("button:has-text('Sign in')")
        page.wait_for_selector("text=Staff overview", timeout=60_000)
        for name, path in STAFF.items():
            page.goto(WEB + path, wait_until="networkidle")
            page.wait_for_selector("text=Decision", timeout=60_000)
            page.screenshot(path=str(OUT / f"{name}.png"))
            print("saved", name)
        browser.close()


if __name__ == "__main__":
    main()
