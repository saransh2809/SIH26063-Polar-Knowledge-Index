"""Plain-dict views of database rows for the API. Kept in one place so every page shows the same fields."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk, Draft, Item, ItemLink, Page, Review
from app.services.search import Hit

LINK_STATE = {"confirmed": "Curator-confirmed", "unconfirmed": "Machine-linked (unconfirmed)", "rejected": "Rejected"}
DRAFT_STATE = {
    "ai_draft": "AI draft", "auto_checked": "Auto-checked", "approved": "Approved",
    "rejected": "Rejected", "published": "Published",
}


def page_image_url(item_id: int, page_no: int) -> str:
    return f"/pages/{item_id}/{page_no}/image"


def hit(h: Hit) -> dict:
    return {
        "chunk_id": h.chunk_id, "item_id": h.item_id, "page": h.page, "printed_page": h.printed_page,
        "text": h.text, "item_title": h.item_title, "report_title": h.report_title,
        "original_url": h.original_url, "file_url": h.file_url,
        "page_image": page_image_url(h.item_id, h.page) if h.image_path else None,
        "text_origin": h.text_origin, "ocr_confidence": h.ocr_confidence,
        "keyword_rank": h.keyword_rank, "vector_rank": h.vector_rank, "similarity": h.similarity,
        "score": round(h.score, 5),
    }


def link(l: ItemLink) -> dict:
    target = l.expedition or l.station or l.topic
    label = (
        l.expedition.name if l.expedition else l.station.name if l.station else l.topic.label if l.topic else str(l.year)
    )
    return {
        "id": l.id, "item_id": l.item_id, "type": l.link_type, "label": label,
        "code": l.expedition.code if l.expedition else (l.topic.key if l.topic else None),
        "target_id": target.id if target else l.year, "method": l.method, "status": l.status,
        "state": LINK_STATE[l.status] if not (l.status == "confirmed" and l.confirmed_by and l.confirmed_by.startswith("rule:"))
        else "Confirmed by NCPOR catalogue",
        "evidence": l.evidence, "confirmed_by": l.confirmed_by,
        "confirmed_at": l.confirmed_at.isoformat() if l.confirmed_at else None,
    }


def item_summary(i: Item) -> dict:
    return {
        "id": i.id, "type": i.item_type, "title": i.title, "original_url": i.original_url, "file_url": i.file_url,
        "source": i.source.name if i.source else None, "published_date": i.published_date.isoformat() if i.published_date else None,
        "page_count": i.page_count, "section": i.raw_metadata.get("collection"),
        "authors": i.raw_metadata.get("creators", []), "parent_id": i.parent_id,
        "harvested_at": i.harvested_at.isoformat() if i.harvested_at else None,
    }


def page(p: Page, item: Item) -> dict:
    return {
        "item_id": p.item_id, "page_no": p.page_no, "printed_page": p.printed_page, "text": p.text,
        "text_origin": p.text_origin, "ocr_confidence": p.ocr_confidence,
        "image": page_image_url(p.item_id, p.page_no) if p.image_path else None,
        "item_title": item.title, "report_title": item.parent.title if item.parent else None,
        "original_url": item.original_url, "file_url": item.file_url, "page_count": item.page_count,
    }


def citation(c: Chunk) -> dict:
    return {
        "chunk_id": c.id, "item_id": c.item_id, "page": c.page_start, "item_title": c.item.title,
        "report_title": c.item.parent.title if c.item.parent else None, "original_url": c.item.original_url,
        "page_image": page_image_url(c.item_id, c.page_start), "text": c.text, "text_origin": c.text_origin,
        "ocr_confidence": c.ocr_confidence,
    }


def draft(db: Session, d: Draft, with_sources: bool = True) -> dict:
    cited_ids = sorted({cid for s in d.sentences for cid in s.cited_chunk_ids})
    sources = {}
    if with_sources and cited_ids:
        for c in db.scalars(select(Chunk).where(Chunk.id.in_(cited_ids))):
            sources[c.id] = citation(c)
            p = db.scalar(select(Page.printed_page).where(Page.item_id == c.item_id, Page.page_no == c.page_start))
            sources[c.id]["printed_page"] = p
    reviews = db.scalars(select(Review).where(Review.draft_id == d.id).order_by(Review.created_at)).all()
    approval = next((r for r in reversed(reviews) if r.decision == "approve"), None)
    translations = db.scalars(select(Draft).where(Draft.translation_of_id == d.id)).all()
    return {
        "id": d.id, "kind": d.kind, "title": d.title, "audience": d.audience, "language": d.language,
        "status": d.status, "state": DRAFT_STATE[d.status], "created_by": d.created_by,
        "created_at": d.created_at.isoformat(), "published_at": d.published_at.isoformat() if d.published_at else None,
        "version": d.version, "supersedes_id": d.supersedes_id, "correction_note": d.correction_note,
        "translation_of_id": d.translation_of_id, "expedition_id": d.expedition_id, "params": d.params,
        "approved_by": approval.reviewer_name if approval else None,
        "approved_at": approval.created_at.isoformat() if approval else None,
        "reviews": [{"reviewer": r.reviewer_name, "decision": r.decision, "comment": r.comment,
                     "at": r.created_at.isoformat()} for r in reviews],
        "translations": [{"id": t.id, "language": t.language, "status": t.status} for t in translations],
        "sentences": [
            {"id": s.id, "seq": s.seq, "section": s.section, "text": s.text, "is_claim": s.is_claim,
             "citations": s.cited_chunk_ids, "check_result": s.check_result, "check_reason": s.check_reason,
             "edited_by": s.edited_by}
            for s in d.sentences
        ],
        "sources": list(sources.values()),
        "check_summary": {
            k: sum(1 for s in d.sentences if s.check_result == k) for k in ("supported", "partial", "unsupported")
        },
    }
