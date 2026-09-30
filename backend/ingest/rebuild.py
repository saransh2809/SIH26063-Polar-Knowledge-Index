"""Rebuild the whole index in one command, from cached files where they exist.

    .venv\\Scripts\\python -m ingest.rebuild

Steps (each is safe to re-run; cached downloads are never fetched again):
  1. database migrations      4. news feed                7. embeddings
  2. DSpace metadata          5. text extraction + OCR    8. demo staff accounts (first run only)
  3. DSpace PDFs (10 reports) 6. linker (rules; AI fallback if a key is set)
"""
import subprocess
import sys
from pathlib import Path

from app.core.config import DATA_DIR

BACKEND = Path(__file__).resolve().parents[1]
REPORTS = "1,4,9,11,13,16,19,22,26,30"
PY = sys.executable


def step(title: str, *args: str) -> None:
    print(f"\n=== {title} ===", flush=True)
    result = subprocess.run(list(args), cwd=BACKEND)
    if result.returncode != 0:
        raise SystemExit(f"Step failed: {title}")


def main() -> None:
    step("1/8 Database migrations", PY, "-m", "alembic", "upgrade", "head")
    step("2-3/8 DSpace metadata and PDFs", PY, "-m", "ingest.dspace", "--download", REPORTS)
    step("4/8 NCPOR news feed", PY, "-m", "ingest.news")
    step("5/8 Text extraction and OCR", PY, "-W", "ignore", "-m", "ingest.extract", "--reports", REPORTS)
    step("6/8 Linker", PY, "-m", "ingest.linker")
    step("7/8 Embeddings", PY, "-m", "ingest.embed")
    if not (DATA_DIR / "demo_users.local.txt").exists():
        step("8/8 Demo staff accounts", PY, "-m", "app.cli", "demo-users")
    else:
        print("\n=== 8/8 Demo staff accounts: already created (see data/demo_users.local.txt) ===")
    print("\nDone. Start the API with:  .venv\\Scripts\\uvicorn app.main:app")


if __name__ == "__main__":
    main()
