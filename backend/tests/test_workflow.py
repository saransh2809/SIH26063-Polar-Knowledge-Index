"""Stage 6 acceptance: red flags block approval, approval is audited, rejected drafts never go public."""
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.security import hash_password
from app.models import AuditLog, Chunk, Item, Source, User
from app.services import generators, llm


@pytest.fixture
def seeded(db):
    """One source, one paper, two chunks, one reviewer. All clearly test data."""
    src = db.scalar(select(Source).where(Source.key == "test"))
    if src is None:
        src = Source(key="test", name="Test source", base_url="http://test.invalid/")
        db.add(src)
        db.flush()
        item = Item(source_id=src.id, external_id="t-1", item_type="paper", title="Test paper on glacier snout",
                    original_url="http://test.invalid/item/1", raw_metadata={})
        db.add(item)
        db.flush()
        db.add_all([
            Chunk(item_id=item.id, seq=0, page_start=1, page_end=1, text_origin="text_layer",
                  text="TEST PASSAGE: the snout of the glacier was monitored with stakes."),
            Chunk(item_id=item.id, seq=1, page_start=2, page_end=2, text_origin="text_layer",
                  text="TEST PASSAGE: aerosol concentration was measured."),
        ])
        db.flush()
    chunk_ids = db.scalars(select(Chunk.id).join(Item).where(Item.source_id == src.id).order_by(Chunk.seq)).all()
    rev = db.scalar(select(User).where(User.username == "test-reviewer"))
    if rev is None:
        rev = User(username="test-reviewer", display_name="Test Reviewer", role="reviewer",
                   password_hash=hash_password("test-password-123"))
        db.add(rev)
    db.commit()
    yield {"chunks": list(chunk_ids)}


def fake_llm(chunk_ids):
    """Lesson: one supported claim, one claim the checker marks unsupported, one question."""

    def generate_json(system, prompt, schema, use_cache=True):
        if "fact-checker" in system:
            n = prompt.count("### Sentence")
            results = []
            for i in range(n):
                block = prompt.split(f"### Sentence {i}\n")[1]
                bad = "every glacier on earth" in block.split("--- cited")[0].lower()
                results.append({"index": i, "result": "unsupported" if bad else "supported",
                                "reason": "not in passage" if bad else "stated in passage"})
            return {"results": results}
        s = lambda t, claim=True: {"text": t, "citations": [chunk_ids[0]], "is_claim": claim}
        return {
            "title": "Test lesson",
            "explainer_basic": [s("Scientists monitored the snout of the glacier."),
                                s("Every glacier on Earth is retreating fast.")],
            "explainer_advanced": [s("Stakes were used to monitor the glacier snout.")],
            "starter": [s("What is a glacier snout?", claim=False)],
            "activity": [s("Discuss with a partner.", claim=False)],
            "quiz": [{"question": "What was monitored?", "answer": "The glacier snout.", "citations": [chunk_ids[0]]}],
            "teacher_notes": [s("The source is a single test passage.")],
        }

    return generate_json


def login(client):
    r = client.post("/auth/login", data={"username": "test-reviewer", "password": "test-password-123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_red_flags_block_approval_then_edit_approve_publish(client, seeded, monkeypatch):
    monkeypatch.setattr(llm, "generate_json", fake_llm(seeded["chunks"]))
    h = login(client)
    d = client.post("/staff/drafts/lesson", headers=h,
                    json={"chunk_ids": seeded["chunks"], "topic": "Glaciers", "level": "Class 11"}).json()
    assert d["status"] == "auto_checked"
    red = [s for s in d["sentences"] if s["check_result"] == "unsupported"]
    assert len(red) == 1 and "Every glacier" in red[0]["text"]
    assert all(s["check_result"] is None for s in d["sentences"] if not s["is_claim"])

    # Approval is refused while a red sentence remains.
    r = client.post(f"/staff/drafts/{d['id']}/approve", headers=h, json={})
    assert r.status_code == 409

    # Reviewer deletes the red sentence, approves, publishes.
    client.delete(f"/staff/drafts/{d['id']}/sentences/{red[0]['id']}", headers=h)
    r = client.post(f"/staff/drafts/{d['id']}/approve", headers=h, json={"comment": "ok"})
    assert r.status_code == 200 and r.json()["approved_by"] == "Test Reviewer"
    assert client.get(f"/published/{d['id']}").status_code == 404  # approved is not yet public
    client.post(f"/staff/drafts/{d['id']}/publish", headers=h)
    pub = client.get(f"/published/{d['id']}")
    assert pub.status_code == 200 and pub.json()["approved_by"] == "Test Reviewer"

    actions = [a["action"] for a in client.get(f"/staff/audit?target_type=draft&target_id={d['id']}", headers=h).json()]
    assert {"draft_created", "auto_checked", "sentence_deleted", "draft_approve", "draft_publish"} <= set(actions)


def test_rejected_draft_never_public(client, seeded, monkeypatch):
    monkeypatch.setattr(llm, "generate_json", fake_llm(seeded["chunks"]))
    h = login(client)
    d = client.post("/staff/drafts/lesson", headers=h,
                    json={"chunk_ids": seeded["chunks"], "topic": "Glaciers", "level": "Class 11"}).json()
    assert client.post(f"/staff/drafts/{d['id']}/reject", headers=h, json={"comment": "no"}).status_code == 200
    assert client.get(f"/published/{d['id']}").status_code == 404
    assert d["id"] not in [p["id"] for p in client.get("/published").json()]
    # A rejected draft cannot be approved or published afterwards.
    assert client.post(f"/staff/drafts/{d['id']}/approve", headers=h, json={}).status_code == 409
    assert client.post(f"/staff/drafts/{d['id']}/publish", headers=h).status_code == 409


def test_public_cannot_write(client, seeded):
    assert client.post("/staff/drafts/lesson", json={"chunk_ids": [1], "topic": "x", "level": "y"}).status_code == 401
    assert client.post("/staff/links/1/confirm").status_code == 401


def test_audit_log_is_append_only(db):
    db.add(AuditLog(actor="test", action="probe", target_type="test", target_id=None, details={}))
    db.commit()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE audit_log SET actor = 'tampered'"))
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM audit_log"))
    db.rollback()


def test_refusal_when_nothing_relevant(db, monkeypatch):
    monkeypatch.setattr(generators, "hybrid_search", lambda db, q, limit=8: [])
    hits, relevant, reason = generators.retrieve_for_question(db, "How fast do Mars rovers drive?")
    assert not relevant and hits == []


def test_model_cannot_exempt_claims_from_checking():
    from app.services.drafts import is_claim

    assert is_claim("The glacier snout receded 81 cm.", "answer", model_says_claim=False)
    assert is_claim("Q1. What was monitored? — Answer: the snout.", "quiz", model_says_claim=False)
    assert is_claim("Stakes were used on the snout.", "explainer_basic", model_says_claim=False)
    assert not is_claim("What is a glacier snout?", "starter", model_says_claim=True)
    assert not is_claim("Discuss with a partner.", "activity", model_says_claim=False)
    assert not is_claim("#Antarctica #NCPOR", "social_instagram", model_says_claim=False)


def test_passage_ids_stripped_but_years_kept():
    import re as _re

    from app.services.drafts import PASSAGE_IDS_RE

    allowed = {3221, 6118}
    strip = lambda t: PASSAGE_IDS_RE.sub(
        lambda m: "" if set(map(int, _re.findall(r"\d+", m.group(0)))) <= allowed else m.group(0), t)
    assert strip("The snout is monitored (3221, 6118).") == "The snout is monitored."
    assert strip("Mapped between (1988, 1991) by survey.") == "Mapped between (1988, 1991) by survey."
