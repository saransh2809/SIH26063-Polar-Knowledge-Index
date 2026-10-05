# -*- coding: utf-8 -*-
"""~4-minute demo video for the Polar Knowledge Index (SIH 2026, PS 26063), 16:9, 1920x1080.

Follows the template: 1 Problem & Core Challenge · 2 Why It's a Game-Changer · 3 Core Innovation ·
4 Prototype Walkthrough · 5 Long-Term Impact. Narration is the team's short script (neural voice,
edge-tts). The prototype is recorded live with Playwright: for each sentence the camera zooms and
spotlights the element being described. Motion-graphics scenes come from motion.html.

Needs: API on :8010 (pointed at the demo database copy, see prep_demo_db.py) and web on :3000.
Usage: python build_video.py [tts|build|assemble|all] [scene ...]
"""
import asyncio
import json
import re
import subprocess
import sys
import time
import urllib.request
import wave
from pathlib import Path

import edge_tts
import imageio_ffmpeg
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUDIO, CLIPS, RAW = HERE / "audio", HERE / "clips", HERE / "raw"
for d in (AUDIO, CLIPS, RAW):
    d.mkdir(exist_ok=True)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VOICE, RATE = "en-IN-PrabhatNeural", "+15%"
WEB, API = "http://localhost:3000", "http://localhost:8010"
APP_VIEW = (1440, 810)      # app pages: content fills more of the frame
MOTION_VIEW = (1600, 900)   # motion.html is laid out for 1600x900; both upscaled to 1920x1080
OW, OH, FPS = 1920, 1080, 30
LEAD, GAP, TAIL = 0.45, 0.4, 0.7
MOTION = (HERE / "motion.html").as_uri()
DSPACE = "http://14.139.119.23:8080/dspace/handle/123456789/326"

SEC = {1: "01 · Problem & Core Challenge", 2: "02 · Why It's a Game-Changer", 3: "03 · Core Innovation",
       4: "04 · Prototype Walkthrough", 5: "05 · Long-Term Impact"}

# Each scene: kind (motion|app|card), url, section, sents = [(caption, narration)], actions = per-sentence coroutines.
SCENES = {
    "title": dict(kind="motion", url=MOTION + "?scene=title", lead=0.9, sents=[
        ("", "Namaste. We are Team Anarch, and this is the Polar Knowledge Index: every expedition, every page, every claim cited.")]),
    "card1": dict(kind="card", n="01", t="Problem & Core Challenge", s="Forty years of polar science, locked away"),
    "problem": dict(kind="motion", url=MOTION + "?scene=problem", sents=[
        ("", "N C P O R has over forty years of Indian polar science: reports, datasets, news and videos."),
        ("", "But it sits in six separate systems that do not talk to each other."),
        ("", "Old reports are scans no one can search, and nothing turns them into lessons or outreach.")]),
    "card2": dict(kind="card", n="02", t="Why It's a Game-Changer", s="Zero new data entry · every answer cited to a page"),
    "game": dict(kind="app", section=2, url=DSPACE, external=True, sents=[
        ("NCPOR's DSpace today: scanned PDFs, no links", "The Polar Knowledge Index does not ask N C P O R to type anything new."),
        ("Same report in our index · linked to its expedition", "It harvests what N C P O R already publishes, reads it, and links every item to its expedition, station, topic and year."),
        ("Answers only from these pages · the page is the proof", "And it answers only from those pages, with the page as proof.")]),
    "card3": dict(kind="card", n="03", t="Core Innovation", s="Harvest · Read · Link · Answer"),
    "innovation": dict(kind="app", section=3, url=WEB + "/expeditions/ISEA-9", steps=True, sents=[
        ("Harvest · OAI-PMH, 1 request/second, originals stay on DSpace", "Harvest: N C P O R's reports come straight from DSpace through the standard O A I P M H protocol, plus the news feed, leaving originals where they are."),
        ("Read · text layer or OCR · printed page + page image", "Read: it uses the P D F's text layer, or O C R when there is none, and keeps the printed page and its image."),
        ("Link · NCPOR's catalogue = confirmed · inferred = unconfirmed", "Link: each item is tied to its expedition, station, topic and year; anything inferred waits for a curator."),
        ("Answer · grounded drafts · every sentence checked", "Answer: hybrid search, A I drafts only from the retrieved pages, a fact-checker colours every sentence, and a named reviewer approves.")]),
    "card4": dict(kind="card", n="04", t="Prototype Walkthrough", s="Live on NCPOR's real archive"),
    "walk": dict(kind="app", section=4, url=WEB + "/search", staff=True, sents=[
        ("A student's question", "A student asks: has India measured how the Dakshin Gangotri glacier is moving?", 1.2),
        ("9th Expedition paper · printed page 248", "Search finds the Ninth Expedition paper on the glacier's secular movement, printed page two forty-eight,"),
        ("Original scan beside its text", "and opens the original scan beside its text."),
        ("Cited answer · 9th, 11th, 26th, 30th Expedition reports", "The cited answer draws on the ninth, eleventh, twenty-sixth and thirtieth Expedition reports:"),
        ("4 of 4 sentences supported", "the snout has been monitored since nineteen eighty-three, and it receded eighty-one centimetres in twenty eleven. All four sentences are supported."),
        ("Off-archive question → refused", "Ask: how fast do Mars rovers drive? And it refuses: no N C P O R source found.", 1.0),
        ("Lesson draft · red = not in the sources", "Now a Class eleven lesson. The checker flags one line red: glaciers are large bodies of ice that move slowly. True, but not in the sources."),
        ("Reviewer deletes it, approves under their name, publishes", "The reviewer deletes it, approves under their own name, and publishes.", 2.5),
        ("Hindi version · checked, approved, published", "Then the Hindi version: drafted, checked, approved and published.", 3.0),
        ("Append-only audit log", "Every step lands in an audit log that cannot be edited."),
        ("Coverage view · what is missing", "Finally, coverage: the seventh and eighth expedition reports are listed but unpublished, and twelve later expeditions are known only from news.")]),
    "card5": dict(kind="card", n="05", t="Long-Term Impact", s="Stats · who benefits · vision"),
    "stats": dict(kind="motion", url=MOTION + "?scene=stats", sents=[
        ("", "Results: thirty-two expedition reports, seven hundred and sixty-five papers and eight hundred and thirty-seven news posts, with zero new data entry."),
        ("", "Over three thousand two hundred scanned pages read, with ninety percent O C R confidence where text was missing."),
        ("", "Accuracy is measured, not claimed, on a hand-verified test set of seventy-five questions."),
        ("", "Honest limits: ten of thirty reports so far, and a human always has the last word.")]),
    "impact": dict(kind="motion", url=MOTION + "?scene=impact", sents=[
        ("", "Teachers get Indian polar lessons, students get trusted answers, and outreach gets drafts in minutes."),
        ("", "It runs on a laptop, with open-source tools and free A I tiers."),
        ("", "Next: the full archive, N C P O R's own curators, and approved stories for the Polar and Ocean Museum.")]),
    "end": dict(kind="motion", url=MOTION + "?scene=end", tail=1.6, sents=[
        ("", "Polar Knowledge Index. Every expedition, every page, every claim cited. Thank you.")]),
}
ORDER = list(SCENES)
CARD_SECONDS = 2.2


# ------------------------------------------------------------------ audio
def ff_duration(path):
    r = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


async def tts_scene(name):
    sc = SCENES[name]
    sc["dur"] = []
    for i, sent in enumerate(sc.get("sents", [])):
        text = sent[1]
        mp3, wav, txt = AUDIO / f"{name}_{i}.mp3", AUDIO / f"{name}_{i}.wav", AUDIO / f"{name}_{i}.txt"
        key = f"{VOICE}|{RATE}|{text}"  # re-voice when the text, voice or speed changes
        if not wav.exists() or not txt.exists() or txt.read_text(encoding="utf-8") != key:
            for attempt in range(5):
                try:
                    await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(mp3))
                    break
                except Exception as e:  # transient network errors
                    print("tts retry", name, i, e)
                    await asyncio.sleep(3)
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "24000", "-ac", "1",
                            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", str(wav)], check=True)
            txt.write_text(key, encoding="utf-8")
        sc["dur"].append(ff_duration(wav))


def scene_timing(name):
    sc = SCENES[name]
    if sc["kind"] == "card":
        return [], CARD_SECONDS
    starts, t = [], sc.get("lead", LEAD)
    for i, d in enumerate(sc["dur"]):
        starts.append(t)
        sent = sc["sents"][i]
        t += d + GAP + (sent[2] if len(sent) > 2 else 0.0)
    return starts, t - GAP + sc.get("tail", TAIL)


def write_scene_wav(name):
    starts, total = scene_timing(name)
    rate = 24000
    frames = bytearray(b"\x00\x00" * int(total * rate))
    for i, s in enumerate(starts):
        with wave.open(str(AUDIO / f"{name}_{i}.wav")) as w:
            data = w.readframes(w.getnframes())
        off = int(s * rate) * 2
        frames[off:off + len(data)] = data[: len(frames) - off]
    out = AUDIO / f"{name}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames[: int(total * rate) * 2]))
    return out


# ------------------------------------------------------------------ in-page overlay: cursor, zoom, spotlight, captions
OVERLAY = r"""
(() => {
  const add = () => {
    if (document.getElementById('__cur')) return;
    const root = document.documentElement;
    const st = document.createElement('style');
    st.textContent = `
      html{background:#F8FAFC}
      body{transition:transform 1.1s cubic-bezier(.45,0,.2,1);transform-origin:0 0}
      #__cur{position:fixed;left:-50px;top:-50px;width:28px;height:28px;border-radius:50%;border:3px solid #fff;
        background:rgba(240,138,75,.18);box-shadow:0 0 0 2px rgba(15,23,42,.6),0 2px 10px rgba(0,0,0,.4);
        transform:translate(-50%,-50%);z-index:2147483647;pointer-events:none;transition:width .12s,height .12s}
      #__cur.down{width:18px;height:18px;background:rgba(240,138,75,.7)}
      #__spot{position:fixed;z-index:2147483640;pointer-events:none;border:4px solid #F08A4B;border-radius:14px;
        box-shadow:0 0 0 9999px rgba(7,12,34,.42);opacity:0;transition:opacity .35s}
      #__cap{position:fixed;bottom:34px;left:50%;transform:translateX(-50%);z-index:2147483646;pointer-events:none;
        background:rgba(15,23,42,.95);color:#fff;font:600 23px 'Segoe UI',sans-serif;padding:11px 26px;border-radius:999px;
        border:2px solid #F08A4B;white-space:nowrap;opacity:0;transition:opacity .3s}
      #__chip{position:fixed;bottom:40px;left:18px;z-index:2147483646;pointer-events:none;background:rgba(15,26,69,.94);
        color:#9CC7FF;font:700 17px 'Segoe UI',sans-serif;letter-spacing:.06em;padding:7px 16px;border-radius:999px;opacity:0;transition:opacity .3s}
      #__steps{position:fixed;bottom:40px;right:18px;z-index:2147483646;pointer-events:none;display:flex;gap:6px;opacity:0;transition:opacity .3s}
      #__steps div{font:700 16px 'Segoe UI',sans-serif;padding:7px 14px;border-radius:999px;background:rgba(15,26,69,.85);color:#9FB0CF;transition:all .3s}
      #__steps div.on{background:#F08A4B;color:#fff;transform:scale(1.08)}`;
    document.head.appendChild(st);
    for (const id of ['__spot', '__cap', '__chip', '__steps', '__cur']) {
      const d = document.createElement('div'); d.id = id; root.appendChild(d);
    }
    const cur = document.getElementById('__cur');
    document.addEventListener('mousemove', e => { cur.style.left = e.clientX + 'px'; cur.style.top = e.clientY + 'px'; }, true);
    document.addEventListener('mousedown', () => cur.classList.add('down'), true);
    document.addEventListener('mouseup', () => cur.classList.remove('down'), true);
    let target = null;
    const spot = document.getElementById('__spot');
    const loop = () => {
      if (target && target.isConnected) {
        const r = target.getBoundingClientRect(), m = 8;
        spot.style.left = (r.left - m) + 'px'; spot.style.top = (r.top - m) + 'px';
        spot.style.width = (r.width + 2 * m) + 'px'; spot.style.height = (r.height + 2 * m) + 'px';
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
    window.__spot = el => { target = el; spot.style.opacity = el ? 1 : 0; };
    window.__cap = t => { const k = document.getElementById('__cap'); k.textContent = t; k.style.opacity = t ? 1 : 0; };
    window.__chip = t => { const k = document.getElementById('__chip'); k.textContent = t; k.style.opacity = t ? 1 : 0; };
    window.__steps = (names, i) => {
      const k = document.getElementById('__steps');
      k.innerHTML = names.map((n, j) => `<div class="${j === i ? 'on' : ''}">${j + 1} ${n}</div>`).join('');
      k.style.opacity = 1;
    };
    // Zoom the page so `el` fills about `frac` of the frame, centred. scale<=1 resets.
    window.__zoom = (el, scale) => {
      const b = document.body;
      if (!el || scale <= 1) { b.style.transform = 'none'; return; }
      const prev = b.style.transform; b.style.transition = 'none'; b.style.transform = 'none';
      const r = el.getBoundingClientRect(); b.offsetHeight; b.style.transition = ''; b.style.transform = prev;
      const W = innerWidth, H = innerHeight, cx = r.left + r.width / 2 + scrollX, cy = r.top + r.height / 2 + scrollY;
      let tx = W / 2 + scrollX - scale * cx, ty = H / 2 + scrollY - scale * cy;
      const docW = b.scrollWidth, docH = Math.max(b.scrollHeight, H);
      tx = Math.min(scrollX, Math.max(tx, W + scrollX - scale * docW));
      ty = Math.min(scrollY, Math.max(ty, H + scrollY - scale * docH));
      b.style.transform = `translate(${tx - scrollX}px, ${ty - scrollY}px) scale(${scale})`;
    };
  };
  if (document.body) add(); else document.addEventListener('DOMContentLoaded', add);
})();
"""

POS = {"x": 720.0, "y": 405.0}


async def ev(page, js, arg=None, tries=4):
    """page.evaluate that survives a navigation in progress: wait for the new page, then retry."""
    for k in range(tries):
        try:
            return await page.evaluate(js, arg)
        except Exception as e:
            if k == tries - 1 or ("context was destroyed" not in str(e) and "navigat" not in str(e)):
                raise
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            await asyncio.sleep(0.4)


async def handle_eval(page, loc, js, extra=None, tries=4):
    for k in range(tries):
        try:
            h = await loc.first.element_handle(timeout=15000)
            return await page.evaluate(js, [h, extra] if extra is not None else h)
        except Exception as e:
            if k == tries - 1:
                raise
            await asyncio.sleep(0.5)


async def glide(page, x, y, dur=0.8):
    x0, y0 = POS["x"], POS["y"]
    n = max(10, int(dur * 40))
    for k in range(1, n + 1):
        t = k / n
        e = t * t * (3 - 2 * t)
        await page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
        await asyncio.sleep(dur / n)
    POS["x"], POS["y"] = x, y


async def to(page, loc, fx=0.5, dur=0.8):
    box = await loc.first.bounding_box()
    await glide(page, box["x"] + box["width"] * fx, box["y"] + box["height"] / 2, dur)


async def click(page, loc, dur=0.7):
    await to(page, loc, dur=dur)
    await page.mouse.down()
    await asyncio.sleep(0.12)
    await page.mouse.up()  # a real click at the cursor position (no second programmatic click)


async def spot(page, loc):
    await handle_eval(page, loc, "el => window.__spot(el)")


async def unspot(page):
    await ev(page, "() => window.__spot(null)")


async def zoom(page, loc, scale):
    await handle_eval(page, loc, "([el, s]) => window.__zoom(el, s)", scale)
    await asyncio.sleep(1.15)


async def unzoom(page):
    await ev(page, "() => window.__zoom(null, 1)")
    await asyncio.sleep(1.1)


async def goto(page, url):
    await ev(page, "() => { window.__spot && window.__spot(null); }")
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(0.4)


async def type_slow(page, loc, text, delay=0.035):
    await click(page, loc)
    for ch in text:
        await page.keyboard.type(ch)
        await asyncio.sleep(delay)


# ------------------------------------------------------------------ actions per sentence
STEPS4 = ["Harvest", "Read", "Link", "Answer"]


async def game_0(p):
    title = p.get_by_text(re.compile(r"Ninth Indian Expedition", re.I)).first
    await to(p, title, fx=0.4, dur=1.0)
    await spot(p, title)
    await asyncio.sleep(1.2)
    await glide(p, 700, 580, 1.2)


async def game_1(p):
    await goto(p, WEB + "/expeditions/ISEA-9")
    await chip_section(p, 2)
    h = p.locator("h1")
    await spot(p, p.locator("header").first)
    await to(p, h, dur=0.9)
    await asyncio.sleep(1.4)
    await spot(p, p.locator("section").filter(has_text="Open on DSpace").first)
    await to(p, p.get_by_text("Open on DSpace").first, dur=0.9)


async def game_2(p):
    await goto(p, WEB + "/page/167/10")
    await chip_section(p, 2)
    await spot(p, p.locator("figure").first)
    await to(p, p.locator("figure img").first, dur=0.9)


async def inn_0(p):
    await ev(p, "n => window.__steps(n, 0)", STEPS4)
    await spot(p, p.locator("section").filter(has_text="Open on DSpace").first)
    await to(p, p.get_by_text("Open on DSpace").first, dur=0.9)
    await asyncio.sleep(2.2)
    await unspot(p)
    await spot(p, p.locator("details").first)
    await to(p, p.locator("details summary").first, dur=0.8)
    await asyncio.sleep(1.5)
    await p.mouse.wheel(0, 380)


async def inn_1(p):
    await goto(p, WEB + "/page/167/10")
    await ev(p, "n => window.__steps(n, 1)", STEPS4)
    await chip_section(p, 3)
    pill = p.get_by_text("Text from the PDF").first
    await spot(p, pill)
    await to(p, pill, dur=0.8)
    await asyncio.sleep(1.6)
    await spot(p, p.locator("h1").first)
    await to(p, p.locator("h1").first, fx=0.75, dur=0.8)
    await asyncio.sleep(1.4)
    await spot(p, p.locator("figure").first)
    await zoom(p, p.locator("figure").first, 1.35)


async def inn_2(p):
    await goto(p, WEB + "/items/167")
    await ev(p, "n => window.__steps(n, 2)", STEPS4)
    await chip_section(p, 3)
    links = p.locator("section").filter(has=p.locator("h2", has_text="Links")).locator("ul").first
    await spot(p, links)
    await zoom(p, links, 1.45)
    for label in ("Confirmed by NCPOR catalogue", "Machine-linked (unconfirmed)"):
        loc = p.get_by_text(label).first
        if await loc.count():
            await to(p, loc, dur=0.9)
            await asyncio.sleep(1.6)


async def inn_3(p):
    await goto(p, WEB + "/staff/review/2")
    await ev(p, "n => window.__steps(n, 3)", STEPS4)
    await chip_section(p, 3)
    pills = p.locator("p.mt-2.flex").first
    await spot(p, pills)
    await to(p, pills, fx=0.4, dur=0.9)
    await asyncio.sleep(3.0)
    first = p.locator("ol > li").first
    await spot(p, first)
    await to(p, first, fx=0.2, dur=0.9)
    await asyncio.sleep(2.0)
    await spot(p, p.locator("aside").first)
    await to(p, p.locator("aside").first, fx=0.5, dur=0.9)


async def walk_0(p):
    q = p.locator("#q")
    await spot(p, q)
    await type_slow(p, q, "Dakshin Gangotri glacier movement")
    await click(p, p.get_by_role("button", name="Search"))
    await p.wait_for_load_state("networkidle")
    await asyncio.sleep(0.5)


async def walk_1(p):
    first = p.locator("article").first
    await spot(p, first)
    await zoom(p, first, 1.3)
    await to(p, first.locator("h3"), fx=0.3, dur=0.8)
    await asyncio.sleep(1.2)
    await to(p, first.get_by_text("printed p.").first, dur=0.8)


async def walk_2(p):
    await unzoom(p)
    await click(p, p.locator("article").first.get_by_role("link", name="View original page"))
    await p.wait_for_load_state("networkidle")
    await chip_section(p, 4)
    await asyncio.sleep(0.5)
    await spot(p, p.locator("figure").first)
    await to(p, p.locator("figure img").first, dur=0.8)


async def walk_3(p):
    await goto(p, WEB + "/staff/review/1")
    await chip_section(p, 4)
    head = p.locator("h1").first
    await spot(p, head)
    await to(p, head, fx=0.4, dur=0.8)
    await asyncio.sleep(1.2)
    await click(p, p.get_by_role("button", name=re.compile(r"Show sources")).first)
    await asyncio.sleep(0.6)
    srcs = p.locator("ol > li").first.locator("ul")
    await spot(p, srcs)


async def walk_4(p):
    third = p.locator("ol > li").nth(2)
    await spot(p, third)
    await zoom(p, third, 1.4)
    await to(p, third, fx=0.6, dur=0.8)
    await asyncio.sleep(2.2)
    await unzoom(p)
    pills = p.locator("p.mt-2.flex").first
    await spot(p, pills)
    await to(p, pills, fx=0.3, dur=0.8)


async def walk_5(p):
    await goto(p, WEB + "/ask")
    await chip_section(p, 4)
    await type_slow(p, p.locator("#question"), "How fast do Mars rovers drive?", 0.03)
    await click(p, p.get_by_role("button", name="Ask"))
    box = p.get_by_text("No NCPOR source found for this.").first
    await box.wait_for(timeout=60000)
    await spot(p, box.locator(".."))
    await to(p, box, dur=0.8)


async def walk_6(p):
    await goto(p, WEB + "/staff/review/2")
    await chip_section(p, 4)
    red = p.locator("ol > li").filter(has_text="Glaciers are large bodies of ice").first
    await spot(p, red)
    await zoom(p, red, 1.45)
    await to(p, red, fx=0.35, dur=0.9)


async def walk_7(p):
    red = p.locator("ol > li").filter(has_text="Glaciers are large bodies of ice").first
    await click(p, red.get_by_role("button", name="Delete"))
    await unspot(p)
    await unzoom(p)
    await asyncio.sleep(0.6)
    approve = p.get_by_role("button", name=re.compile(r"^Approve as"))
    await spot(p, approve)
    await click(p, approve)
    await p.get_by_role("button", name="Publish").wait_for(timeout=30000)
    await asyncio.sleep(0.5)
    pub = p.get_by_role("button", name="Publish")
    await spot(p, pub)
    await click(p, pub)
    await p.get_by_role("link", name="View public page").wait_for(timeout=30000)
    hist = p.locator("aside div").filter(has_text="Review history").first
    await spot(p, hist)


async def walk_8(p):
    hindi = p.get_by_role("button", name="Draft Hindi version")
    await spot(p, hindi)
    await click(p, hindi)
    for _ in range(600):  # client-side navigation: no 'load' event, so poll the address
        if re.search(r"/staff/review/\d+$", p.url) and not p.url.endswith("/staff/review/2"):
            break
        await asyncio.sleep(0.2)
    try:
        await p.locator("h1[lang=hi]").wait_for(timeout=20000)
    except Exception:
        # Fallback: the address changed but the screen kept the old draft; open the Hindi draft directly.
        print("hindi step: url", p.url, flush=True)
        await p.screenshot(path=str(HERE / "check" / "hindi_stall.png"))
        hid = re.search(r"/staff/review/(\d+)$", p.url)
        if hid and hid.group(1) != "2":
            await p.goto(p.url, wait_until="networkidle")
        await p.locator("h1[lang=hi]").wait_for(timeout=60000)
    await asyncio.sleep(0.4)
    await spot(p, p.locator("ol > li").first)
    await asyncio.sleep(0.8)
    approve = p.get_by_role("button", name=re.compile(r"^Approve as"))
    await spot(p, approve)
    await click(p, approve)
    pub = p.get_by_role("button", name="Publish")
    await pub.wait_for(timeout=30000)
    await click(p, pub)
    link = p.get_by_role("link", name="View public page")
    await link.wait_for(timeout=30000)
    await click(p, link)
    await p.wait_for_load_state("networkidle")
    await chip_section(p, 4)
    await spot(p, p.locator("article").first)


async def walk_9(p):
    await goto(p, WEB + "/staff/audit")
    await chip_section(p, 4)
    rows = p.locator("tbody tr")
    await spot(p, p.locator("table").first)
    await to(p, rows.first, fx=0.3, dur=0.8)
    await asyncio.sleep(1.0)
    await spot(p, rows.nth(6))  # the deleted red sentence, recorded with its text


async def walk_10(p):
    await goto(p, WEB + "/coverage")
    await chip_section(p, 4)
    await spot(p, p.locator("dl").first)
    await to(p, p.locator("dl").first, fx=0.5, dur=0.8)
    await asyncio.sleep(1.8)
    row7 = p.locator("tr").filter(has_text="ISEA-7").first
    await row7.scroll_into_view_if_needed()
    await asyncio.sleep(0.3)
    both = p.locator("tr").filter(has=p.locator("text=listed, not published"))
    await spot(p, both.first)
    await to(p, row7, fx=0.2, dur=0.8)
    await asyncio.sleep(2.4)
    row33 = p.locator("tr").filter(has_text="ISEA-33").first
    await row33.scroll_into_view_if_needed()
    await asyncio.sleep(0.3)
    await spot(p, row33)
    await to(p, row33, fx=0.2, dur=0.8)


ACTIONS = {
    "game": [game_0, game_1, game_2],
    "innovation": [inn_0, inn_1, inn_2, inn_3],
    "walk": [walk_0, walk_1, walk_2, walk_3, walk_4, walk_5, walk_6, walk_7, walk_8, walk_9, walk_10],
}


async def chip_section(p, n):
    await ev(p, "t => window.__chip(t)", SEC[n])


# ------------------------------------------------------------------ recording
async def sleep_until(t):
    d = t - time.monotonic()
    if d > 0:
        await asyncio.sleep(d)


def staff_token() -> str:
    creds = dict(re.findall(r"username=(\S+) password=(\S+)", (ROOT / "data" / "demo_users.local.txt").read_text()))
    body = f"username=reviewer&password={creds['reviewer']}".encode()
    req = urllib.request.Request(API + "/auth/login", data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["access_token"]


async def record(pw, name):
    sc = SCENES[name]
    starts, total = scene_timing(name)
    vw, vh = APP_VIEW if sc["kind"] == "app" else MOTION_VIEW
    browser = await pw.chromium.launch(channel="msedge", headless=True)
    ctx = await browser.new_context(viewport={"width": vw, "height": vh},
                                    record_video_dir=str(RAW / name), record_video_size={"width": vw, "height": vh})
    if sc["kind"] == "app":
        await ctx.add_init_script(OVERLAY)
        token = staff_token()
        await ctx.add_init_script(f"if (location.origin === {json.dumps(WEB)}) try {{ sessionStorage.setItem('ncpor-staff-token', {json.dumps(token)}); }} catch (e) {{}}")
    page = await ctx.new_page()
    t_ctx = time.monotonic()
    url = sc.get("url") or (MOTION + "?scene=card&n={n}&t={t}&s={s}".format(
        n=sc["n"], t=urllib.request.quote(sc["t"]), s=urllib.request.quote(sc.get("s", ""))))
    await page.goto(url, wait_until="networkidle", timeout=90000)
    await asyncio.sleep(1.2)
    POS.update(x=720.0, y=405.0)
    if sc["kind"] == "app":
        await page.mouse.move(720, 405)
        if "section" in sc:
            await chip_section(page, sc["section"])
        if sc.get("steps"):
            await ev(page, "n => window.__steps(n, 0)", STEPS4)
    offset = time.monotonic() - t_ctx
    t0 = time.monotonic()
    if sc["kind"] == "card":
        await ev(page, "() => window.step(0)")
    for i in range(len(starts)):
        await sleep_until(t0 + starts[i])
        if sc["kind"] == "motion":
            await ev(page, "i => window.step(i)", i)
        else:
            await ev(page, "t => window.__cap(t)", sc["sents"][i][0])
            await ACTIONS[name][i](page)
    await sleep_until(t0 + total)
    video = page.video
    await ctx.close()
    await browser.close()
    return Path(await video.path()), offset


def build_clip(name, video_path, offset):
    _, total = scene_timing(name)
    out = CLIPS / f"{name}.mp4"
    if SCENES[name]["kind"] == "card":
        audio = ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
    else:
        audio = ["-i", str(write_scene_wav(name))]
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-ss", f"{offset:.3f}", "-i", str(video_path)] + audio + [
        "-map", "0:v", "-map", "1:a",
        "-vf", f"scale={OW}:{OH}:flags=lanczos,fps={FPS},format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-t", f"{total:.3f}", str(out)]
    subprocess.run(cmd, check=True)
    return out


def concat_all():
    lst = HERE / "clips.txt"
    lst.write_text("".join(f"file '{(CLIPS / (n + '.mp4')).as_posix()}'\n" for n in ORDER), encoding="utf-8")
    final = HERE / "PolarKnowledgeIndex_Demo.mp4"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    "-movflags", "+faststart", str(final)], check=True)
    return final


async def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    only = sys.argv[2:] or ORDER
    for n in ORDER:
        await tts_scene(n)
    total = sum(scene_timing(n)[1] for n in ORDER)
    print(f"total {total:.1f}s ({total / 60:.2f} min)")
    if stage == "tts":
        for n in ORDER:
            print(f"{n:11s} {scene_timing(n)[1]:6.1f}s", [round(d, 1) for d in SCENES[n].get("dur", [])])
        return
    if stage == "assemble":
        print(concat_all())
        return
    async with async_playwright() as pw:
        for n in only:
            t = time.monotonic()
            path, offset = await record(pw, n)
            build_clip(n, path, offset)
            print("built", n, f"{time.monotonic() - t:.0f}s", flush=True)
    if only == ORDER:
        print(concat_all())


asyncio.run(main())
