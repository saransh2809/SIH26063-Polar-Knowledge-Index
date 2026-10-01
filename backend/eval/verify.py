"""Walk through unverified test questions and record a human verdict for each.

For an answerable row, the page (scan beside its text) opens in your browser. Find the expected
fact on the SCAN, not only in the extracted text, then answer:
  y = verified   n = wrong (row is marked rejected)   e = edit the fact   r = reword the question
  s = skip   q = quit

Reject a row (n) if the fact is OCR garbage, the question just repeats the answer, or it asks about
an identifiable person's health. Reword (r) if the question needs context, e.g. which expedition.

The website must be running (http://localhost:3000). Progress is saved after every answer, so you
can stop and continue later; several people can split the work with --from / --to.

    .venv\\Scripts\\python -m eval.verify --name "Your Name"
    .venv\\Scripts\\python -m eval.verify --name "Asha" --from 1 --to 30
"""
import argparse
import webbrowser

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Item
from eval.common import load, save

FRONTEND = "http://localhost:3000"


def describe(db, item_id: str) -> str:
    item = db.get(Item, int(item_id)) if item_id else None
    if item is None:
        return "(item not found)"
    report = item.parent.title if item.parent else ""
    return f"{item.title}\n   in {report}" if report else item.title


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="your name, recorded as verified_by")
    ap.add_argument("--from", dest="start", type=int, default=0, help="first row id to check")
    ap.add_argument("--to", dest="end", type=int, default=10**9, help="last row id to check")
    ap.add_argument("--no-browser", action="store_true", help="print page links instead of opening them")
    args = ap.parse_args()

    rows = load()
    todo = [r for r in rows if r["status"] == "unverified" and args.start <= int(r["id"]) <= args.end]
    print(f"{len(todo)} rows to verify. Answer y / n / e / s / q.\n")
    with SessionLocal() as db:
        for n, r in enumerate(todo, start=1):
            print("=" * 80)
            print(f"[{n}/{len(todo)}]  #{r['id']}  {r['question']}")
            if r["answerable"] == "yes":
                url = f"{FRONTEND}/page/{r['expected_item_id']}/{r['expected_page']}"
                print(f"Expected fact : “{r['expected_fact']}”")
                print(f"Source        : {describe(db, r['expected_item_id'])}, PDF page {r['expected_page']}")
                print(f"Page          : {url}")
                if not args.no_browser:
                    webbrowser.open(url)
                print("Is the fact on that page, and does it answer the question?")
            else:
                print("Expected: the system should REFUSE. Is this really something the NCPOR archive does not answer?")
            choice = input("[y]es / [n]o / [e]dit fact / [r]eword question / [s]kip / [q]uit: ").strip().lower()
            if choice == "q":
                break
            if choice == "r":
                # e.g. add the missing context: "...sail from Mauritius on the 1st Expedition?"
                r["question"] = input("Reworded question: ").strip() or r["question"]
                choice = input("Now: [y]es / [n]o / [e]dit fact / [s]kip: ").strip().lower()
            if choice == "e" and r["answerable"] == "yes":
                r["expected_fact"] = input("Exact phrase as printed on the page: ").strip()
                choice = "y"
            if choice == "y":
                r["status"], r["verified_by"] = "verified", args.name
            elif choice == "n":
                r["status"], r["verified_by"] = "rejected", args.name
            save(rows)
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in ("verified", "rejected", "unverified")}
    print(f"\nVerified {counts['verified']} · rejected {counts['rejected']} · still unverified "
          f"{counts['unverified']}. Saved to eval/questions.csv")


if __name__ == "__main__":
    main()
