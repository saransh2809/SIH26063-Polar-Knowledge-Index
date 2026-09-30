"""Drafts: creation from model output, the faithfulness checker, and the review workflow.

Lifecycle:  ai_draft -> auto_checked -> approved (named reviewer) -> published
            (rejected is terminal; published text is corrected by a new version, never edited in place)
"""
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk, Draft, DraftSentence, Review, User
from app.services import audit, llm

CHECK_BATCH = 20


class WorkflowError(HTTPException):
    def __init__(self, message: str):
        super().__init__(status_code=409, detail=message)


def now() -> datetime:
    return datetime.now(timezone.utc)


# --- passages ------------------------------------------------------------------------
def format_passages(chunks: list[Chunk]) -> str:
    blocks = []
    for c in chunks:
        item = c.item
        where = f"page {c.page_start}"
        blocks.append(
            f"[{c.id}] from \"{item.title}\""
            + (f" in \"{item.parent.title}\"" if item.parent else "")
            + f", {where}"
            + (" (OCR text, may contain recognition errors)" if c.text_origin == "ocr" else "")
            + f"\n{c.text}"
        )
    return "\n\n".join(blocks)


# --- creation ------------------------------------------------------------------------
NON_CLAIM_SECTIONS = ("starter", "activity")
PASSAGE_IDS_RE = re.compile(r"\s*[\(\[]\s*\d{3,}(?:\s*,\s*\d{3,})*\s*[\)\]]")


def is_claim(text: str, section: str | None, model_says_claim: bool) -> bool:
    """The model may not exempt its own sentences from fact-checking. A sentence skips the check
    only if it is a question, a hashtag line, or an instruction in a starter/activity section."""
    stripped = text.strip()
    if stripped.endswith("?") and section != "quiz":
        return False
    if stripped.startswith("#") and all(w.startswith("#") for w in stripped.split()):
        return False
    if section in NON_CLAIM_SECTIONS and not model_says_claim:
        return False
    return True


def create_draft(
    db: Session,
    *,
    kind: str,
    title: str,
    sentences: list[dict],
    allowed_chunk_ids: set[int],
    created_by: str,
    audience: str | None = None,
    language: str = "en",
    params: dict | None = None,
    expedition_id: int | None = None,
    translation_of_id: int | None = None,
) -> Draft:
    """`sentences`: [{section, text, citations, is_claim}]. Citations outside the sources we gave
    the model are dropped, so a sentence can never cite a passage it was not shown."""
    draft = Draft(
        kind=kind, title=title, audience=audience, language=language, status="ai_draft",
        created_by=created_by, params=params or {}, expedition_id=expedition_id,
        translation_of_id=translation_of_id,
    )
    for seq, s in enumerate(sentences):
        # Drop passage IDs the model wrote into the text, e.g. "(3221, 6118)" or "[6111]".
        # Only brackets whose numbers are all passages it was given: "(1988, 1991)" stays.
        text = PASSAGE_IDS_RE.sub(
            lambda m: "" if set(map(int, re.findall(r"\d+", m.group(0)))) <= allowed_chunk_ids else m.group(0),
            s.get("text") or "",
        ).strip()
        if not text:
            continue
        cited = [int(c) for c in s.get("citations", []) if int(c) in allowed_chunk_ids]
        draft.sentences.append(
            DraftSentence(
                seq=seq, section=s.get("section"), text=text,
                is_claim=is_claim(text, s.get("section"), bool(s.get("is_claim", True))),
                cited_chunk_ids=list(dict.fromkeys(cited)),
            )
        )
    db.add(draft)
    db.flush()
    audit.record(db, created_by, "draft_created", "draft", draft.id, kind=kind, language=language,
                 sentences=len(draft.sentences), sources=sorted(allowed_chunk_ids))
    return draft


# --- faithfulness checker ---------------------------------------------------------------
CHECK_SYSTEM = (
    "You are a strict fact-checker for a government science archive. For each numbered sentence you get "
    "the passages it cites. Judge ONLY against those passages; your own knowledge does not count.\n"
    "supported: every factual detail (names, numbers, dates, places, causes) is stated in the cited passages.\n"
    "partial: the main point is supported but some detail is not, or the sentence overstates the passage.\n"
    "unsupported: the passages do not state it, or contradict it.\n"
    "The sentence may be in Hindi while passages are in English; compare meaning. "
    "Give a one-line reason naming what is or is not in the passage."
)
CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "result": {"type": "string", "enum": ["supported", "partial", "unsupported"]},
                    "reason": {"type": "string"},
                },
                "required": ["index", "result", "reason"],
            },
        }
    },
    "required": ["results"],
}


def check_sentences(db: Session, sentences: list[DraftSentence]) -> None:
    """Fill check_result/check_reason for claim sentences."""
    to_check = []
    for s in sentences:
        if not s.is_claim:
            s.check_result, s.check_reason = None, "Not a factual claim (question or instruction)."
        elif not s.cited_chunk_ids:
            s.check_result, s.check_reason = "unsupported", "No valid citation to an archive passage."
        else:
            to_check.append(s)

    for start in range(0, len(to_check), CHECK_BATCH):
        batch = to_check[start : start + CHECK_BATCH]
        chunk_ids = {cid for s in batch for cid in s.cited_chunk_ids}
        chunks = {c.id: c for c in db.scalars(select(Chunk).where(Chunk.id.in_(chunk_ids)))}
        parts = []
        for i, s in enumerate(batch):
            cited = "\n".join(f"[{cid}] {chunks[cid].text}" for cid in s.cited_chunk_ids if cid in chunks)
            parts.append(f"### Sentence {i}\n{s.text}\n--- cited passages ---\n{cited}")
        result = llm.generate_json(CHECK_SYSTEM, "\n\n".join(parts), CHECK_SCHEMA)
        verdicts = {r["index"]: r for r in result.get("results", [])}
        for i, s in enumerate(batch):
            v = verdicts.get(i)
            if v is None:
                s.check_result, s.check_reason = "unsupported", "Checker returned no verdict; treat as unchecked."
            else:
                s.check_result, s.check_reason = v["result"], v["reason"]


def check_draft(db: Session, draft: Draft, actor: str = "system:checker") -> Draft:
    check_sentences(db, list(draft.sentences))
    if draft.status == "ai_draft":
        draft.status = "auto_checked"
    draft.updated_at = now()
    counts = {k: sum(1 for s in draft.sentences if s.check_result == k) for k in ("supported", "partial", "unsupported")}
    audit.record(db, actor, "auto_checked", "draft", draft.id, **counts)
    return draft


# --- review workflow ------------------------------------------------------------------------
EDITABLE = ("ai_draft", "auto_checked")


def _require_status(draft: Draft, allowed: tuple[str, ...], action: str) -> None:
    if draft.status not in allowed:
        raise WorkflowError(f"Cannot {action} a draft in status '{draft.status}'.")


def edit_sentence(db: Session, draft: Draft, sentence_id: int, user: User, text: str | None,
                  citations: list[int] | None) -> DraftSentence:
    _require_status(draft, EDITABLE, "edit")
    s = next((s for s in draft.sentences if s.id == sentence_id), None)
    if s is None:
        raise HTTPException(404, "Sentence not found in this draft")
    before = {"text": s.text, "citations": s.cited_chunk_ids}
    if text is not None:
        s.text = text.strip()
    if citations is not None:
        valid = set(db.scalars(select(Chunk.id).where(Chunk.id.in_(citations))).all())
        s.cited_chunk_ids = [c for c in citations if c in valid]
    s.edited_by = user.display_name
    check_sentences(db, [s])  # an edited sentence is re-checked immediately
    draft.updated_at = now()
    audit.record(db, user.display_name, "sentence_edited", "draft", draft.id, sentence_id=s.id,
                 before=before, after={"text": s.text, "citations": s.cited_chunk_ids}, check=s.check_result)
    return s


def delete_sentence(db: Session, draft: Draft, sentence_id: int, user: User) -> None:
    _require_status(draft, EDITABLE, "edit")
    s = next((s for s in draft.sentences if s.id == sentence_id), None)
    if s is None:
        raise HTTPException(404, "Sentence not found in this draft")
    audit.record(db, user.display_name, "sentence_deleted", "draft", draft.id, sentence_id=s.id, text=s.text)
    draft.sentences.remove(s)
    draft.updated_at = now()


def _review(db: Session, draft: Draft, user: User, decision: str, comment: str | None) -> None:
    db.add(Review(draft_id=draft.id, reviewer_id=user.id, reviewer_name=user.display_name,
                  decision=decision, comment=comment))
    audit.record(db, user.display_name, f"draft_{decision}", "draft", draft.id, comment=comment,
                 reviewer_role=user.role)


def approve(db: Session, draft: Draft, user: User, comment: str | None = None) -> Draft:
    _require_status(draft, ("auto_checked",), "approve")
    blocking = [s for s in draft.sentences if s.is_claim and s.check_result in (None, "unsupported")]
    if blocking:
        raise WorkflowError(
            f"{len(blocking)} sentence(s) are unsupported or unchecked. Edit, cite a source, or delete them first."
        )
    if not draft.sentences:
        raise WorkflowError("An empty draft cannot be approved.")
    draft.status = "approved"
    draft.updated_at = now()
    _review(db, draft, user, "approve", comment)
    return draft


def reject(db: Session, draft: Draft, user: User, comment: str | None = None) -> Draft:
    _require_status(draft, ("ai_draft", "auto_checked", "approved"), "reject")
    draft.status = "rejected"
    draft.updated_at = now()
    _review(db, draft, user, "reject", comment)
    return draft


def publish(db: Session, draft: Draft, user: User) -> Draft:
    _require_status(draft, ("approved",), "publish")
    draft.status = "published"
    draft.published_at = now()
    draft.updated_at = now()
    _review(db, draft, user, "publish", None)
    return draft


def start_correction(db: Session, draft: Draft, user: User, note: str) -> Draft:
    """A published item is corrected by a new version that must itself be checked and approved."""
    _require_status(draft, ("published",), "correct")
    new = Draft(
        kind=draft.kind, title=draft.title, audience=draft.audience, language=draft.language,
        status="ai_draft", created_by=user.display_name, params=draft.params,
        expedition_id=draft.expedition_id, translation_of_id=draft.translation_of_id,
        supersedes_id=draft.id, version=draft.version + 1, correction_note=note,
    )
    for s in draft.sentences:
        new.sentences.append(DraftSentence(seq=s.seq, section=s.section, text=s.text, is_claim=s.is_claim,
                                           cited_chunk_ids=list(s.cited_chunk_ids),
                                           check_result=s.check_result, check_reason=s.check_reason))
    new.status = "auto_checked"
    db.add(new)
    db.flush()
    audit.record(db, user.display_name, "correction_started", "draft", new.id, supersedes=draft.id, note=note)
    return new
