"""Draft CANDIDATE test questions from real chunks. Every row is written as `unverified`.

A person must open the page image, confirm the expected fact is on that page, and mark the row
verified (python -m eval.verify). Until then the row does not count toward any score.

    .venv\\Scripts\\python -m eval.draft_candidates --answerable 60 --unanswerable 15
"""
import argparse
import random

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import Chunk, Item
from app.services import llm
from eval.common import load, norm, save

SYSTEM = (
    "You write test questions for a search system over India's Antarctic expedition reports. "
    "Given ONE passage, write one question a student or researcher might ask that this passage answers, "
    "and copy an exact short phrase (3-12 words) from the passage that contains the answer. "
    "The phrase must appear verbatim in the passage. If the passage is garbled, a table of numbers, a list of "
    "names, or about the health of identifiable people, return usable=false."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "usable": {"type": "boolean"},
        "question": {"type": "string"},
        "expected_fact": {"type": "string"},
    },
    "required": ["usable", "question", "expected_fact"],
}

UNANSWERABLE_SYSTEM = (
    "Write questions that sound like plausible queries to a polar-science archive but that India's "
    "Antarctic expedition reports from 1981-2011 would not answer (other planets, other countries' "
    "programmes, sports, current prices, future events, fiction). One per line, no numbering."
)
UNANSWERABLE_SCHEMA = {"type": "object", "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
                       "required": ["questions"]}


def candidate_chunks(db, n: int, seed: int) -> list[Chunk]:
    """Readable paper chunks spread across reports: text-layer or OCR with confidence >= 80."""
    rows = db.scalars(
        select(Chunk).join(Item, Item.id == Chunk.item_id)
        .where(Item.item_type == "paper", func.length(Chunk.text) > 400,
               (Chunk.text_origin == "text_layer") | (Chunk.ocr_confidence >= 80))
    ).all()
    by_report: dict[int, list[Chunk]] = {}
    for c in rows:
        by_report.setdefault(c.item.parent_id, []).append(c)
    rng = random.Random(seed)
    picked: list[Chunk] = []
    pools = [rng.sample(v, len(v)) for v in by_report.values()]
    while len(picked) < n * 2 and any(pools):  # oversample; some will be unusable
        for pool in pools:
            if pool:
                picked.append(pool.pop())
    return picked


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--answerable", type=int, default=60)
    ap.add_argument("--unanswerable", type=int, default=15)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rows = load()
    next_id = max((int(r["id"]) for r in rows), default=0) + 1
    made = 0
    with SessionLocal() as db:
        for chunk in candidate_chunks(db, args.answerable, args.seed):
            if made >= args.answerable:
                break
            result = llm.generate_json(SYSTEM, f"Passage (page {chunk.page_start} of \"{chunk.item.title}\"):\n{chunk.text}", SCHEMA,
                                     purpose="bulk")
            fact = (result.get("expected_fact") or "").strip()
            if not result.get("usable") or not fact or norm(fact) not in norm(chunk.text):
                continue  # the phrase must really be in the passage
            rows.append({
                "id": next_id, "question": result["question"].strip(), "answerable": "yes",
                "expected_fact": fact, "expected_item_id": chunk.item_id, "expected_page": chunk.page_start,
                "status": "unverified", "verified_by": "",
                "notes": f"drafted by model from chunk {chunk.id}; check the page image",
            })
            next_id += 1
            made += 1

        extra = llm.generate_json(UNANSWERABLE_SYSTEM, f"Write {args.unanswerable} questions.", UNANSWERABLE_SCHEMA,
                                 purpose="bulk")
        for q in extra.get("questions", [])[: args.unanswerable]:
            rows.append({
                "id": next_id, "question": q.strip(), "answerable": "no", "expected_fact": "",
                "expected_item_id": "", "expected_page": "", "status": "unverified", "verified_by": "",
                "notes": "drafted by model; confirm the archive really has no answer",
            })
            next_id += 1
    save(rows)
    print(f"Added {made} answerable and {min(args.unanswerable, len(extra.get('questions', [])))} unanswerable "
          f"candidates to eval/questions.csv, all marked unverified.")


if __name__ == "__main__":
    main()
