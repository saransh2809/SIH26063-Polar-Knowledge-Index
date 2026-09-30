"""Compute embeddings for every chunk that does not have one yet.

Run from backend/:  .venv\\Scripts\\python -m ingest.embed
The first run downloads the model (about 1 GB) into the Hugging Face cache.
"""
import time

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import Chunk
from app.services.embeddings import embed_passages

BATCH = 64


def main() -> None:
    with SessionLocal() as db:
        todo = db.scalar(select(func.count()).select_from(Chunk).where(Chunk.embedding.is_(None)))
        print(f"{todo} chunks need embeddings")
        done, started = 0, time.monotonic()
        while True:
            batch = db.scalars(select(Chunk).where(Chunk.embedding.is_(None)).order_by(Chunk.id).limit(BATCH)).all()
            if not batch:
                break
            texts = [f"{c.section_title or ''}\n{c.text}" for c in batch]
            for chunk, vector in zip(batch, embed_passages(texts)):
                chunk.embedding = vector
            db.commit()
            done += len(batch)
            rate = done / max(time.monotonic() - started, 1e-6)
            print(f"  {done}/{todo}  ({rate:.1f} chunks/s)")


if __name__ == "__main__":
    main()
