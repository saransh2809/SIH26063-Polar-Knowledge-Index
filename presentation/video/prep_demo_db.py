"""Prepare throwaway database copies for recording the demo video. The real database is never changed.

    python prep_demo_db.py prewarm   # copy -> run the full on-camera sequence once (fills the AI cache) -> drop copy
    python prep_demo_db.py record    # fresh copy 'ncpor_demo' with the off-camera steps done; prints its URL
    python prep_demo_db.py drop      # remove 'ncpor_demo' after recording

The on-camera sequence (lesson draft 2): delete the red "Glaciers are large bodies..." sentence,
approve, publish, draft the Hindi version, approve it, publish it. Off camera, beforehand, the
other unsupported sentences (teacher-note meta lines) are deleted to keep the video short.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import get_settings  # noqa: E402

BASE_URL = make_url(get_settings().database_url)
LESSON_ID, ANSWER_ID = 2, 1
ON_CAMERA_DELETE = "Glaciers are large bodies of ice"
STATE = Path(__file__).with_name("demo_state.json")


def admin():
    return create_engine(BASE_URL, isolation_level="AUTOCOMMIT")


def clone(name: str) -> str:
    eng = admin()
    with eng.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {name} TEMPLATE {BASE_URL.database}"))
    eng.dispose()
    return BASE_URL.set(database=name).render_as_string(hide_password=False)


def drop(name: str) -> None:
    eng = admin()
    with eng.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
    eng.dispose()


def client_for(url: str):
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    import importlib

    import app.core.db as dbmod
    importlib.reload(dbmod)
    from fastapi.testclient import TestClient

    import app.main as main
    main.app.dependency_overrides[dbmod.get_db] = dbmod.get_db
    return TestClient(main.app)


def login(c, role: str) -> dict:
    creds = dict(re.findall(r"username=(\S+) password=(\S+)", (ROOT / "data" / "demo_users.local.txt").read_text()))
    tok = c.post("/auth/login", data={"username": role, "password": creds[role]}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def off_camera(c, h) -> dict:
    d = c.get(f"/staff/drafts/{LESSON_ID}", headers=h).json()
    for s in d["sentences"]:
        if s["check_result"] == "unsupported" and ON_CAMERA_DELETE not in s["text"]:
            c.delete(f"/staff/drafts/{LESSON_ID}/sentences/{s['id']}", headers=h)
    d = c.get(f"/staff/drafts/{LESSON_ID}", headers=h).json()
    return d["check_summary"]


def on_camera(c, h) -> dict:
    d = c.get(f"/staff/drafts/{LESSON_ID}", headers=h).json()
    red = next(s for s in d["sentences"] if ON_CAMERA_DELETE in s["text"])
    c.delete(f"/staff/drafts/{LESSON_ID}/sentences/{red['id']}", headers=h)
    r = c.post(f"/staff/drafts/{LESSON_ID}/approve", headers=h, json={"comment": "rehearsal"})
    assert r.status_code == 200, r.text
    assert c.post(f"/staff/drafts/{LESSON_ID}/publish", headers=h).status_code == 200
    hi = c.post(f"/staff/drafts/{LESSON_ID}/translate", headers=h).json()
    print("Hindi draft", hi.get("id"), hi.get("check_summary"), hi.get("detail"))
    for s in hi.get("sentences", []):
        if s["check_result"] in ("unsupported", "partial"):
            print("   ", s["check_result"], "|", s["text"][:90], "|", (s["check_reason"] or "")[:90])
    r = c.post(f"/staff/drafts/{hi['id']}/approve", headers=h, json={"comment": "rehearsal"})
    print("Hindi approve:", r.status_code, r.json().get("detail") if r.status_code != 200 else "ok")
    return {"hindi_id": hi.get("id"), "hindi_summary": hi.get("check_summary"), "hindi_approve": r.status_code}


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "prewarm":
        url = clone("ncpor_prewarm")
        c = client_for(url)
        h = login(c, "reviewer")
        print("after off-camera deletions:", off_camera(c, h))
        result = on_camera(c, h)
        c.close()
        drop("ncpor_prewarm")
        print("rehearsal:", result)
    elif cmd == "record":
        url = clone("ncpor_demo")
        c = client_for(url)
        h = login(c, "reviewer")
        print("after off-camera deletions:", off_camera(c, h))
        c.close()
        STATE.write_text(json.dumps({"database_url": url}), encoding="utf-8")
        print("demo database ready")
    elif cmd == "drop":
        drop("ncpor_demo")
        STATE.unlink(missing_ok=True)
        print("demo database removed")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
