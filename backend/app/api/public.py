"""Public, read-only endpoints. Nothing here writes, and only *published* generated text is returned."""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session

from app.api import serializers as S
from app.core.config import DATA_DIR
from app.core.db import get_db
from app.models import Draft, Expedition, Item, ItemLink, Page
from app.services import generators
from app.services.search import hybrid_search, keyword_search, vector_search

router = APIRouter(tags=["public"])


@router.get("/search")
def search(q: str = Query(min_length=2, max_length=300), mode: str = "hybrid", limit: int = Query(10, le=50),
           db: Session = Depends(get_db)) -> dict:
    fn = {"hybrid": hybrid_search, "keyword": keyword_search, "vector": vector_search}.get(mode)
    if fn is None:
        raise HTTPException(400, "mode must be hybrid, keyword or vector")
    hits = fn(db, q, limit=limit) if mode == "hybrid" else fn(db, q, limit)
    return {"query": q, "mode": mode, "results": [S.hit(h) for h in hits]}


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@router.post("/ask")
def ask(body: AskIn, db: Session = Depends(get_db)) -> dict:
    """Public question box. Returns archive passages (verbatim source text, not generated) and,
    if a reviewer has approved an answer to this question, that answer. It never returns unreviewed AI text."""
    hits, relevant, reason = generators.retrieve_for_question(db, body.question)
    if not relevant:
        return {"status": "refused", "message": generators.REFUSAL, "reason": reason, "passages": []}
    answer = generators.published_answer(db, body.question)
    return {
        "status": "answered" if answer else "passages_only",
        "message": None if answer else "No reviewed answer yet. These are the archive passages that match your question.",
        "reason": reason,
        "answer": S.draft(db, answer) if answer else None,
        "passages": [S.hit(h) for h in hits[:5]],
    }


@router.get("/items/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)) -> dict:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    links = db.scalars(select(ItemLink).where(ItemLink.item_id == item_id, ItemLink.status != "rejected")).all()
    return {
        **S.item_summary(item),
        "report": S.item_summary(item.parent) if item.parent else None,
        "links": [S.link(l) for l in links],
        "children": [S.item_summary(c) for c in sorted(item.children, key=lambda c: c.id)],
        "raw_metadata": item.raw_metadata,
    }


@router.get("/items/{item_id}/pages/{page_no}")
def get_page(item_id: int, page_no: int, db: Session = Depends(get_db)) -> dict:
    p = db.scalar(select(Page).where(Page.item_id == item_id, Page.page_no == page_no))
    if p is None:
        raise HTTPException(404, "Page not extracted")
    return S.page(p, p.item)


@router.get("/pages/{item_id}/{page_no}/image")
def page_image(item_id: int, page_no: int, db: Session = Depends(get_db)) -> FileResponse:
    path = db.scalar(select(Page.image_path).where(Page.item_id == item_id, Page.page_no == page_no))
    if not path or not (DATA_DIR / path).exists():
        raise HTTPException(404, "No page image")
    return FileResponse(DATA_DIR / path, media_type="image/jpeg")


# --- expeditions and coverage ---------------------------------------------------------------
def _expedition_rows(db: Session) -> list[dict]:
    exps = db.scalars(select(Expedition).order_by(Expedition.number.nulls_last(), Expedition.code)).all()
    counts: dict[int, dict] = defaultdict(lambda: defaultdict(int))
    # Literal key, so GROUP BY sees the same expression as SELECT.
    not_published = Item.raw_metadata.op("->>")(literal_column("'not_published'"))
    extracted = Item.page_count.is_not(None)
    rows = db.execute(
        select(ItemLink.expedition_id, Item.item_type, extracted, not_published, func.count())
        .join(Item, Item.id == ItemLink.item_id)
        .where(ItemLink.link_type == "expedition", ItemLink.status != "rejected")
        .group_by(ItemLink.expedition_id, Item.item_type, extracted, not_published)
    ).all()
    for exp_id, item_type, extracted, not_published, n in rows:
        c = counts[exp_id]
        c[item_type] += n
        if item_type == "paper" and extracted:
            c["papers_extracted"] += n
        if item_type == "report" and not_published == "true":
            c["report_not_published"] += n
    stories = dict(db.execute(
        select(Draft.expedition_id, func.count()).where(Draft.status == "published", Draft.expedition_id.is_not(None))
        .group_by(Draft.expedition_id)
    ).all())
    out = []
    for e in exps:
        c = counts[e.id]
        report_listed = c["report"] > 0
        report_public = report_listed and c["report"] > c["report_not_published"] and c["paper"] > 0
        out.append({
            "code": e.code, "number": e.number, "name": e.name, "region": e.region, "season": e.season,
            "source_url": e.source_url,
            "report": "published" if report_public else ("listed, not published" if report_listed else "none found"),
            "papers": c["paper"], "papers_extracted": c["papers_extracted"],
            "datasets": c["dataset_link"], "photos": c["photo"], "news": c["news"], "videos": c["video"],
            "public_stories": stories.get(e.id, 0),
        })
    return out


@router.get("/expeditions")
def expeditions(db: Session = Depends(get_db)) -> list[dict]:
    return _expedition_rows(db)


@router.get("/expeditions/{code}")
def expedition(code: str, db: Session = Depends(get_db)) -> dict:
    e = db.scalar(select(Expedition).where(Expedition.code == code.upper()))
    if e is None:
        raise HTTPException(404, "Expedition not found")
    links = db.scalars(
        select(ItemLink).where(ItemLink.expedition_id == e.id, ItemLink.status != "rejected")
    ).all()
    items = sorted((l.item for l in links), key=lambda i: i.id)
    by_type: dict[str, list] = defaultdict(list)
    link_state = {l.item_id: S.link(l) for l in links}
    for i in items:
        entry = {**S.item_summary(i), "link": link_state[i.id]}
        if i.item_type == "paper":
            entry["topics"] = [
                S.link(l)["label"] for l in i.links if l.link_type == "topic" and l.status != "rejected"
            ]
            entry["stations"] = [
                S.link(l)["label"] for l in i.links if l.link_type == "station" and l.status != "rejected"
            ]
        by_type[i.item_type].append(entry)
    stories = db.scalars(
        select(Draft).where(Draft.expedition_id == e.id, Draft.status == "published").order_by(Draft.published_at.desc())
    ).all()
    row = next(r for r in _expedition_rows(db) if r["code"] == e.code)
    return {**row, "items": by_type, "stories": [S.draft(db, d, with_sources=False) for d in stories]}


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


@router.get("/coverage")
def coverage(db: Session = Depends(get_db)) -> dict:
    rows = _expedition_rows(db)
    numbered = [r["number"] for r in rows if r["number"]]
    highest = max(numbered) if numbered else 0
    known = set(numbered)
    # Expedition numbers below the highest known one must exist; we have no record of them in any
    # harvested source. They are shown as inferred rows, clearly labelled, never as facts.
    inferred = [
        {"code": f"ISEA-{n}", "number": n, "name": f"{_ordinal(n)} Indian Expedition to Antarctica (inferred from numbering)",
         "region": "Antarctic", "season": None, "source_url": None, "report": "none found", "papers": 0,
         "papers_extracted": 0, "datasets": 0, "photos": 0, "news": 0, "videos": 0, "public_stories": 0,
         "inferred": True}
        for n in range(1, highest) if n not in known
    ]
    all_rows = sorted(rows + inferred, key=lambda r: (r["number"] is None, r["number"] or 0, r["code"]))
    summary = {
        "expeditions": len(all_rows),
        "with_public_report": sum(1 for r in all_rows if r["report"] == "published"),
        "report_listed_not_published": sum(1 for r in all_rows if r["report"] == "listed, not published"),
        "no_report_found": sum(1 for r in all_rows if r["report"] == "none found"),
        "with_dataset_link": sum(1 for r in all_rows if r["datasets"]),
        "with_public_story": sum(1 for r in all_rows if r["public_stories"] or r["news"]),
    }
    return {"summary": summary, "rows": all_rows}


@router.get("/evaluation")
def evaluation() -> dict:
    """The latest evaluation run (written by `python -m eval.run`), shown as-is."""
    import json

    path = DATA_DIR / "eval_latest.json"
    if not path.exists():
        return {"available": False}
    return {"available": True, **json.loads(path.read_text(encoding="utf-8"))}


# --- published content --------------------------------------------------------------------------
@router.get("/published")
def published(kind: str | None = None, language: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    q = select(Draft).where(Draft.status == "published")
    if kind:
        q = q.where(Draft.kind == kind)
    if language:
        q = q.where(Draft.language == language)
    drafts = db.scalars(q.order_by(Draft.published_at.desc())).all()
    superseded = {d.supersedes_id for d in drafts if d.supersedes_id}
    return [S.draft(db, d, with_sources=False) for d in drafts if d.id not in superseded]


@router.get("/published/{draft_id}")
def published_one(draft_id: int, db: Session = Depends(get_db)) -> dict:
    d = db.get(Draft, draft_id)
    if d is None or d.status != "published":
        raise HTTPException(404, "Not found")  # drafts, rejected and unapproved items are invisible here
    newer = db.scalar(select(Draft).where(Draft.supersedes_id == d.id, Draft.status == "published"))
    history = []
    cursor = d
    while cursor.supersedes_id:
        cursor = db.get(Draft, cursor.supersedes_id)
        history.append({"id": cursor.id, "version": cursor.version, "published_at":
                        cursor.published_at.isoformat() if cursor.published_at else None})
    data = S.draft(db, d)
    data["translations"] = [t for t in data["translations"] if t["status"] == "published"]
    return {**data, "superseded_by": newer.id if newer else None, "history": history}
