"""Keyword, meaning-based and hybrid search over chunks.

Hybrid ranking uses Reciprocal Rank Fusion (RRF): each chunk scores sum(1 / (60 + rank)) over
the two ranked lists, so a chunk near the top of either list rises, with no weights to tune.
"""
import re
from dataclasses import dataclass, field

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.services.embeddings import embed_query

RRF_K = 60
CANDIDATES = 30

_HIT_COLUMNS = """
    c.id, c.item_id, c.page_start, c.page_end, c.text, c.text_origin, c.ocr_confidence,
    i.title AS item_title, i.original_url, i.file_url, r.title AS report_title,
    p.printed_page, p.image_path
"""
_HIT_JOINS = """
    JOIN items i ON i.id = c.item_id
    LEFT JOIN items r ON r.id = i.parent_id
    LEFT JOIN pages p ON p.item_id = c.item_id AND p.page_no = c.page_start
"""


@dataclass
class Hit:
    chunk_id: int
    item_id: int
    page: int
    printed_page: str | None
    text: str
    item_title: str
    report_title: str | None
    original_url: str
    file_url: str | None
    image_path: str | None
    text_origin: str
    ocr_confidence: float | None
    keyword_rank: int | None = None
    vector_rank: int | None = None
    similarity: float | None = None
    score: float = 0.0
    extra: dict = field(default_factory=dict)


def _hit(row) -> Hit:
    return Hit(
        chunk_id=row.id, item_id=row.item_id, page=row.page_start, printed_page=row.printed_page,
        text=row.text, item_title=row.item_title, report_title=row.report_title,
        original_url=row.original_url, file_url=row.file_url, image_path=row.image_path,
        text_origin=row.text_origin, ocr_confidence=row.ocr_confidence,
    )


def _or_query(q: str) -> str:
    """'Is the glacier moving?' -> 'is | the | glacier | moving' (stop words are dropped by Postgres)."""
    words = re.findall(r"[A-Za-z0-9]{2,}", q)
    return " | ".join(dict.fromkeys(w.lower() for w in words))


def keyword_search(db: Session, q: str, limit: int = CANDIDATES) -> list[Hit]:
    tsq = _or_query(q)
    if not tsq:
        return []
    rows = db.execute(
        text(f"""
            SELECT {_HIT_COLUMNS}, ts_rank_cd(c.tsv, query) AS rank
            FROM chunks c {_HIT_JOINS}, to_tsquery('english', :tsq) query
            WHERE c.tsv @@ query
            ORDER BY rank DESC, c.id
            LIMIT :limit
        """),
        {"tsq": tsq, "limit": limit},
    ).all()
    hits = [_hit(r) for r in rows]
    for rank, h in enumerate(hits, start=1):
        h.keyword_rank = rank
    return hits


def vector_search(db: Session, q: str, limit: int = CANDIDATES, query_vector: list[float] | None = None) -> list[Hit]:
    vector = query_vector or embed_query(q)
    rows = db.execute(
        text(f"""
            SELECT {_HIT_COLUMNS}, 1 - (c.embedding <=> CAST(:vec AS vector)) AS similarity
            FROM chunks c {_HIT_JOINS}
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(:vec AS vector)
            LIMIT :limit
        """).bindparams(bindparam("vec", value=str(vector))),
        {"limit": limit},
    ).all()
    hits = []
    for rank, r in enumerate(rows, start=1):
        h = _hit(r)
        h.vector_rank, h.similarity = rank, round(float(r.similarity), 4)
        hits.append(h)
    return hits


def hybrid_search(db: Session, q: str, limit: int = 10) -> list[Hit]:
    vector = embed_query(q)
    merged: dict[int, Hit] = {}
    for h in vector_search(db, q, query_vector=vector):
        merged[h.chunk_id] = h
    for h in keyword_search(db, q):
        if h.chunk_id in merged:
            merged[h.chunk_id].keyword_rank = h.keyword_rank
        else:
            merged[h.chunk_id] = h
    missing = [cid for cid, h in merged.items() if h.similarity is None]
    if missing:  # keyword-only hits: fetch their similarity so the refusal threshold can use it
        rows = db.execute(
            text("SELECT id, 1 - (embedding <=> CAST(:vec AS vector)) AS s FROM chunks WHERE id = ANY(:ids)")
            .bindparams(bindparam("vec", value=str(vector))),
            {"ids": missing},
        ).all()
        for r in rows:
            merged[r.id].similarity = round(float(r.s), 4) if r.s is not None else None
    for h in merged.values():
        h.score = sum(1 / (RRF_K + rank) for rank in (h.keyword_rank, h.vector_rank) if rank)
    return sorted(merged.values(), key=lambda h: h.score, reverse=True)[:limit]
