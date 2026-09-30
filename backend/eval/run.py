"""Run the test set and print the two accuracy numbers.

  1. Citation accuracy: of verified answerable questions, the share whose answer cites a passage
     on the expected page of the expected item that contains the expected fact.
  2. Refusal accuracy: of verified unanswerable questions, the share the system refused.

Also prints retrieval recall (expected page among the passages retrieved), which needs no LLM.
Nothing is saved: drafts made during the run are rolled back.

    .venv\\Scripts\\python -m eval.run                 # verified rows only (the real score)
    .venv\\Scripts\\python -m eval.run --include-unverified   # dry run while the set is being built
"""
import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import DATA_DIR
from app.core.db import SessionLocal
from app.models import Chunk
from app.services import generators, llm
from eval.common import is_verified, load, norm


def cited_ok(db, draft, item_id: int, page: int, fact: str) -> bool:
    ids = {cid for s in draft.sentences for cid in s.cited_chunk_ids}
    for c in db.scalars(select(Chunk).where(Chunk.id.in_(ids))):
        if c.item_id == item_id and c.page_start <= page <= c.page_end and norm(fact) in norm(c.text):
            return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--include-unverified", action="store_true")
    ap.add_argument("--retrieval-only", action="store_true", help="skip the LLM; report retrieval recall only")
    args = ap.parse_args()

    rows = [r for r in load() if r["status"] != "rejected" and (args.include_unverified or is_verified(r))]
    if not rows:
        raise SystemExit("No rows to score. Draft candidates (eval.draft_candidates) and verify them (eval.verify).")

    answerable = [r for r in rows if r["answerable"] == "yes"]
    unanswerable = [r for r in rows if r["answerable"] == "no"]
    ok_cite = ok_refuse = retrieved = 0
    failures = []

    with SessionLocal() as db:
        for r in answerable:
            item_id, page = int(r["expected_item_id"]), int(r["expected_page"])
            hits, relevant, reason = generators.retrieve_for_question(db, r["question"])
            if any(h.item_id == item_id and h.page == page for h in hits):
                retrieved += 1
            if args.retrieval_only:
                continue
            if not relevant:
                failures.append((r["id"], r["question"], f"refused: {reason}"))
                continue
            try:
                draft = generators.draft_answer(db, r["question"], hits, created_by="system:eval")
            except (llm.LLMNotConfigured, llm.LLMUnavailable) as exc:
                raise SystemExit(f"LLM needed for the full evaluation: {exc}. Use --retrieval-only.")
            if draft is None:
                failures.append((r["id"], r["question"], "model said the passages do not answer it"))
            elif cited_ok(db, draft, item_id, page, r["expected_fact"]):
                ok_cite += 1
            else:
                failures.append((r["id"], r["question"], "no citation on the expected page contains the expected fact"))

        for r in unanswerable:
            hits, relevant, reason = generators.retrieve_for_question(db, r["question"])
            refused = not relevant
            if relevant and not args.retrieval_only:
                refused = generators.draft_answer(db, r["question"], hits, created_by="system:eval") is None
            if refused:
                ok_refuse += 1
            else:
                failures.append((r["id"], r["question"], "answered, but should have been refused"))
        db.rollback()  # evaluation drafts are never stored

    pct = lambda a, b: f"{100 * a / b:.1f}% ({a}/{b})" if b else "n/a (0 rows)"
    label = "INCLUDING UNVERIFIED ROWS (dry run, not a reportable score)" if args.include_unverified else "verified rows only"
    print(f"\nEvaluation on {len(rows)} questions, {label}")
    print(f"  Retrieval recall (expected page retrieved): {pct(retrieved, len(answerable))}")
    if not args.retrieval_only:
        print(f"  1. Citation accuracy:  {pct(ok_cite, len(answerable))}")
    print(f"  2. Refusal accuracy:   {pct(ok_refuse, len(unanswerable))}"
          + ("  (retrieval threshold only)" if args.retrieval_only else ""))
    if failures:
        print("\nFailures:")
        for fid, q, why in failures:
            print(f"  #{fid} {q[:80]} -> {why}")

    result = {
        "at": datetime.now(timezone.utc).isoformat(), "verified_only": not args.include_unverified,
        "retrieval_only": args.retrieval_only, "answerable": len(answerable), "unanswerable": len(unanswerable),
        "retrieval_recall": retrieved, "citation_ok": None if args.retrieval_only else ok_cite, "refusal_ok": ok_refuse,
        "failures": [{"id": f[0], "question": f[1], "why": f[2]} for f in failures],
    }
    out = DATA_DIR / "eval_latest.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
