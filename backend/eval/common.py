"""The test set lives in eval/questions.csv (reviewable in Git). Only rows whose `status` is
`verified` and that name a `verified_by` person count toward the scores."""
import csv
import re
from pathlib import Path

CSV_PATH = Path(__file__).with_name("questions.csv")
FIELDS = [
    "id", "question", "answerable", "expected_fact", "expected_item_id", "expected_page",
    "status", "verified_by", "notes",
]


def load() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save(rows: list[dict]) -> None:
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in FIELDS})


def is_verified(row: dict) -> bool:
    return row.get("status") == "verified" and bool(row.get("verified_by", "").strip())


def norm(text: str) -> str:
    """Case-, whitespace- and hyphenation-insensitive form for 'does this chunk contain the fact'."""
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text.lower())
    return re.sub(r"\s+", " ", text).strip()
