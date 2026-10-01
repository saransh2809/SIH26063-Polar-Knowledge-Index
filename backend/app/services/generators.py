"""Grounded generators: cited answers, lesson units, expedition announcements, Hindi translation.

Every generator gives the model a fixed set of archive passages and requires a passage ID on every
sentence. Citations to passages outside that set are dropped in drafts.create_draft.
"""
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Chunk, Draft, Expedition, Item, ItemLink
from app.services import drafts, llm
from app.services.search import Hit, hybrid_search

REFUSAL = "No NCPOR source found for this."

GROUNDING_RULES = (
    "You write for NCPOR, India's National Centre for Polar and Ocean Research.\n"
    "Use ONLY the numbered passages provided. Every sentence that states a fact must list the IDs of the "
    "passages that directly support it. Do not add facts, numbers, dates, names or background that are not in "
    "the cited passages, even if you believe them to be true. Passages marked OCR may contain recognition "
    "errors: never repeat a number unless it is clearly legible, and never 'fix' a number. "
    "Never write about the health or psychology of identifiable individuals. "
    "Put passage IDs only in the citations field, never in the sentence text. Cite only the 1-3 passages that "
    "directly state the sentence's content; do not cite every passage you were given."
)

SENTENCE = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "integer"}},
        "is_claim": {"type": "boolean"},
    },
    "required": ["text", "citations", "is_claim"],
}
SENTENCES = {"type": "array", "items": SENTENCE}


def _chunks(db: Session, ids: list[int]) -> list[Chunk]:
    rows = {c.id: c for c in db.scalars(select(Chunk).where(Chunk.id.in_(ids)))}
    return [rows[i] for i in ids if i in rows]


def normalise_question(q: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", q.lower())).strip()


# --- Q&A ----------------------------------------------------------------------------------
def retrieve_for_question(db: Session, question: str, limit: int = 8) -> tuple[list[Hit], bool, str]:
    """Returns (hits, relevant_enough, reason)."""
    settings = get_settings()
    hits = hybrid_search(db, question, limit=limit)
    if not hits:
        return [], False, "The archive returned no passages."
    top = max((h.similarity or 0) for h in hits)
    keyword_hits = sum(1 for h in hits if h.keyword_rank)
    if top < settings.qa_min_similarity:
        return hits, False, f"Best passage similarity {top:.3f} is below the threshold {settings.qa_min_similarity}."
    if keyword_hits == 0 and top < settings.qa_strong_similarity:
        return hits, False, f"No passage shares a keyword with the question and similarity {top:.3f} is not strong."
    return hits, True, f"Best passage similarity {top:.3f}; {keyword_hits} keyword matches."


ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"answerable": {"type": "boolean"}, "sentences": SENTENCES},
    "required": ["answerable", "sentences"],
}


def published_answer(db: Session, question: str) -> Draft | None:
    return db.scalar(
        select(Draft).where(Draft.kind == "answer", Draft.status == "published",
                            Draft.params["normalised_question"].astext == normalise_question(question))
        .order_by(Draft.version.desc())
    )


def draft_answer(db: Session, question: str, hits: list[Hit], created_by: str, audience: str = "student") -> Draft | None:
    """Returns the checked draft, or None if the model says the passages do not answer the question."""
    chunks = _chunks(db, [h.chunk_id for h in hits])
    prompt = (
        f"Audience: {audience} (plain language, short sentences).\n"
        f"Question: {question}\n\nPassages:\n{drafts.format_passages(chunks)}\n\n"
        "If the passages do not answer the question, set answerable=false and return no sentences. "
        "Otherwise answer in 2-5 sentences, each with citations. If the passages discuss the topic but give no "
        "measured value, say that the report discusses it rather than inventing a value."
    )
    result = llm.generate_json(GROUNDING_RULES, prompt, ANSWER_SCHEMA)
    if not result.get("answerable") or not result.get("sentences"):
        return None
    draft = drafts.create_draft(
        db, kind="answer", title=question, audience=audience, created_by=created_by,
        sentences=[{**s, "section": "answer"} for s in result["sentences"]],
        allowed_chunk_ids={c.id for c in chunks},
        params={"question": question, "normalised_question": normalise_question(question),
                "retrieved_chunk_ids": [c.id for c in chunks]},
    )
    return drafts.check_draft(db, draft)


# --- lesson unit ----------------------------------------------------------------------------
LESSON_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "explainer_basic": SENTENCES,
        "explainer_advanced": SENTENCES,
        "starter": SENTENCES,
        "activity": SENTENCES,
        "quiz": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                    "citations": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["question", "answer", "citations"],
            },
        },
        "teacher_notes": SENTENCES,
    },
    "required": ["title", "explainer_basic", "explainer_advanced", "starter", "activity", "quiz", "teacher_notes"],
}
LESSON_SECTIONS = ["explainer_basic", "explainer_advanced", "starter", "activity", "quiz", "teacher_notes"]


def generate_lesson(db: Session, chunk_ids: list[int], topic: str, level: str, created_by: str) -> Draft:
    chunks = _chunks(db, chunk_ids)
    if not chunks:
        raise drafts.WorkflowError("Select at least one archive passage as a source.")
    prompt = (
        f"Write a one-period lesson unit on '{topic}' for {level} in India, using Indian polar research as the "
        f"example. Structure: starter -> main activity -> follow-up.\n"
        "- explainer_basic: 3-5 sentences for younger or struggling readers.\n"
        "- explainer_advanced: 4-6 sentences with more scientific detail.\n"
        "- starter: 1-2 questions to open the class (is_claim=false).\n"
        "- activity: a short classroom activity that uses ONLY facts or numbers from the passages; "
        "instructions have is_claim=false, facts have is_claim=true with citations.\n"
        "- quiz: exactly 5 questions whose answers are stated in the passages, with citations.\n"
        "- teacher_notes: 2-4 sentences on what the sources do and do not cover; point out OCR uncertainty.\n\n"
        f"Passages:\n{drafts.format_passages(chunks)}"
    )
    result = llm.generate_json(GROUNDING_RULES, prompt, LESSON_SCHEMA)
    sentences = []
    for section in LESSON_SECTIONS:
        if section == "quiz":
            for n, q in enumerate(result.get("quiz", [])[:5], start=1):
                sentences.append({"section": "quiz", "is_claim": True, "citations": q.get("citations", []),
                                  "text": f"Q{n}. {q['question']} — Answer: {q['answer']}"})
        else:
            sentences += [{**s, "section": section} for s in result.get(section, [])]
    draft = drafts.create_draft(
        db, kind="lesson", title=result.get("title") or f"{topic} ({level})", audience=level,
        created_by=created_by, sentences=sentences, allowed_chunk_ids={c.id for c in chunks},
        params={"topic": topic, "level": level, "source_chunk_ids": [c.id for c in chunks]},
    )
    return drafts.check_draft(db, draft)


# --- expedition announcement ---------------------------------------------------------------
ANNOUNCE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "web_post": SENTENCES,
        "social_x": SENTENCES,
        "social_facebook": SENTENCES,
        "social_instagram": SENTENCES,
    },
    "required": ["headline", "web_post", "social_x", "social_facebook", "social_instagram"],
}
ANNOUNCE_SECTIONS = ["web_post", "social_x", "social_facebook", "social_instagram"]


def announcement_sources(db: Session, expedition: Expedition, limit: int = 12) -> list[Chunk]:
    """Opening passage of each paper that is confirmed-linked to the expedition, best OCR first."""
    item_ids = db.scalars(
        select(ItemLink.item_id).where(ItemLink.expedition_id == expedition.id, ItemLink.status == "confirmed")
    ).all()
    first_chunks = db.scalars(
        select(Chunk).where(Chunk.item_id.in_(item_ids), Chunk.seq == 0)
        .order_by(func.coalesce(Chunk.ocr_confidence, 100).desc(), Chunk.id)
        .limit(limit)
    ).all()
    return list(first_chunks)


def generate_announcement(db: Session, expedition: Expedition, created_by: str, angle: str | None = None) -> Draft:
    chunks = announcement_sources(db, expedition)
    if not chunks:
        raise drafts.WorkflowError("No confirmed, text-extracted records are linked to this expedition yet.")
    prompt = (
        f"Draft public outreach about the {expedition.name} ({expedition.code}), built only from its archived "
        f"scientific reports below. {('Angle: ' + angle) if angle else 'Angle: what this expedition studied.'}\n"
        "- headline: under 12 words.\n"
        "- web_post: 5-8 sentences for the NCPOR website.\n"
        "- social_x: 1-2 sentences, under 270 characters in total.\n"
        "- social_facebook: 2-4 sentences.\n"
        "- social_instagram: 2-3 sentences; hashtags as a final sentence with is_claim=false.\n"
        "Do not state dates, years or seasons unless a passage states them.\n\n"
        f"Passages:\n{drafts.format_passages(chunks)}"
    )
    result = llm.generate_json(GROUNDING_RULES, prompt, ANNOUNCE_SCHEMA)
    sentences = []
    for section in ANNOUNCE_SECTIONS:
        sentences += [{**s, "section": section} for s in result.get(section, [])]
    draft = drafts.create_draft(
        db, kind="announcement", title=result.get("headline") or expedition.name, audience="public",
        created_by=created_by, sentences=sentences, allowed_chunk_ids={c.id for c in chunks},
        expedition_id=expedition.id,
        params={"expedition": expedition.code, "angle": angle, "source_chunk_ids": [c.id for c in chunks]},
    )
    return drafts.check_draft(db, draft)


# --- Hindi translation ---------------------------------------------------------------------------
TRANSLATE_SYSTEM = (
    "Translate outreach text from English to clear, simple standard Hindi (Devanagari) for Indian students. "
    "Translate meaning faithfully; add nothing and drop nothing. Keep numbers, units, station names "
    "(Dakshin Gangotri, Maitri, Bharati, Himadri, Himansh) and scientific terms recognisable; you may add the "
    "English term in brackets after a technical Hindi word.\n"
    "Glossary (use these; 'austral' means southern-hemisphere, never 'Australian'):\n"
    "austral summer = दक्षिणी गोलार्ध की गर्मी (austral summer); glacier = हिमनद (glacier); "
    "glacier snout = हिमनद का अग्रभाग (snout); ice shelf = हिम शेल्फ (ice shelf); "
    "iceberg = हिमशैल (iceberg); expedition = अभियान; recession (of a glacier) = पीछे हटना (recession)."
)
TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "sentences": {"type": "array", "items": {"type": "object", "properties": {
            "index": {"type": "integer"}, "text": {"type": "string"}}, "required": ["index", "text"]}},
    },
    "required": ["title", "sentences"],
}


def translate_to_hindi(db: Session, source: Draft, created_by: str) -> Draft:
    if source.language != "en":
        raise drafts.WorkflowError("Only English drafts can be translated.")
    if source.status not in ("approved", "published"):
        raise drafts.WorkflowError("Approve the English version first; the Hindi draft is translated from it.")
    lines = "\n".join(f"{i}: {s.text}" for i, s in enumerate(source.sentences))
    result = llm.generate_json(TRANSLATE_SYSTEM, f"Title: {source.title}\n\nSentences:\n{lines}", TRANSLATE_SCHEMA)
    translated = {r["index"]: r["text"] for r in result.get("sentences", [])}
    sentences = [
        {"section": s.section, "is_claim": s.is_claim, "citations": s.cited_chunk_ids,
         "text": translated.get(i, "")}
        for i, s in enumerate(source.sentences)
    ]
    missing = [i for i in range(len(source.sentences)) if not translated.get(i)]
    allowed = {cid for s in source.sentences for cid in s.cited_chunk_ids}
    draft = drafts.create_draft(
        db, kind=source.kind, title=result.get("title") or source.title, audience=source.audience,
        language="hi", created_by=created_by, sentences=sentences, allowed_chunk_ids=allowed,
        params={**source.params, "translated_from": source.id, "untranslated_indexes": missing},
        expedition_id=source.expedition_id, translation_of_id=source.id,
    )
    return drafts.check_draft(db, draft)
