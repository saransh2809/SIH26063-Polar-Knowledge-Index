"""Stage 3: turn cached paper PDFs into page text, page images and searchable chunks.

For every page:
  * use the PDF's own text layer if it is usable (born-digital or already OCR'd scans);
  * otherwise render the page and OCR it with Tesseract, recording its confidence (0-100).
A page image is always saved so the UI can show "view original page".

Chunks never cross a page boundary, so every chunk cites exactly one page.

Run from backend/:
    .venv\\Scripts\\python -m ingest.extract --reports 1,9,15     # extract these reports
    .venv\\Scripts\\python -m ingest.extract --quality            # print the quality table
"""
import argparse
import csv
import logging
import os
import re
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import fitz  # PyMuPDF
from sqlalchemy import delete, select

from app.core.config import DATA_DIR, OCR_DIR, get_settings
from app.core.db import SessionLocal
from app.models import Chunk, Item, Page

log = logging.getLogger(__name__)

OCR_DPI = 300
VIEW_DPI = 130
MAX_CHUNK_CHARS = 1500
MIN_TEXT_LAYER_LETTERS = 120
PRINTED_PAGE_RE = re.compile(r"^\s*[-–(]?\s*(\d{1,3})\s*[-–)]?\s*$")


# --- per-page helpers (run inside worker processes) ------------------------------
def text_layer_usable(text: str) -> bool:
    letters = sum(c.isalpha() for c in text)
    if letters < MIN_TEXT_LAYER_LETTERS:
        return False
    tokens = text.split()
    wordlike = sum(1 for t in tokens if len(t) >= 2 and sum(c.isalpha() for c in t) >= 0.7 * len(t))
    return wordlike / max(len(tokens), 1) >= 0.5


def ocr_page(page: "fitz.Page") -> tuple[str, float | None]:
    import pytesseract
    from PIL import Image

    pix = page.get_pixmap(dpi=OCR_DPI, colorspace=fitz.csGRAY)
    image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    data = pytesseract.image_to_data(image, lang="eng", output_type=pytesseract.Output.DICT)
    lines: dict[tuple, list[str]] = {}
    confidences = []
    for i, word in enumerate(data["text"]):
        conf = float(data["conf"][i])
        if conf < 0 or not word.strip():
            continue
        confidences.append(conf)
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
    text_lines, last_block = [], None
    for key in sorted(lines):
        if last_block is not None and key[:2] != last_block:
            text_lines.append("")  # blank line between paragraphs
        text_lines.append(" ".join(lines[key]))
        last_block = key[:2]
    return "\n".join(text_lines), (round(statistics.mean(confidences), 1) if confidences else None)


def find_printed_page(text: str) -> str | None:
    lines = [l for l in text.splitlines() if l.strip()]
    for line in lines[:2] + lines[-2:]:
        m = PRINTED_PAGE_RE.match(line)
        if m and 0 < int(m.group(1)) < 1000:
            return m.group(1)
    return None


def process_pdf(item_id: int, pdf_path: str, image_dir: str, tesseract_cmd: str | None) -> list[dict]:
    """Extract every page of one PDF. Runs in a worker process; touches no database."""
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # one Tesseract thread per worker
    if tesseract_cmd:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    out_dir = Path(image_dir) / str(item_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            layer = page.get_text("text")
            if text_layer_usable(layer):
                text, origin, conf = layer, "text_layer", None
            else:
                text, conf = ocr_page(page)
                origin = "ocr"
            image_path = out_dir / f"{index}.jpg"
            if not image_path.exists():
                page.get_pixmap(dpi=VIEW_DPI).pil_save(image_path, format="JPEG", quality=75)
            pages.append(
                {
                    "page_no": index,
                    "text": text.replace("\x00", ""),
                    "text_origin": origin,
                    "ocr_confidence": conf,
                    "printed_page": find_printed_page(text),
                    "image_path": image_path.relative_to(DATA_DIR).as_posix(),
                }
            )
    return pages


# --- chunking --------------------------------------------------------------------
def normalise(text: str) -> str:
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join words hyphenated across lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_page(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split one page's text at paragraph, then line, boundaries into pieces <= limit."""
    pieces, current = [], ""
    for para in re.split(r"\n\s*\n", text):
        units = [para] if len(para) <= limit else para.split("\n")
        for unit in units:
            while len(unit) > limit:  # a single enormous line: hard split at a space
                cut = unit.rfind(" ", 0, limit)
                cut = cut if cut > limit // 2 else limit
                if current:
                    pieces.append(current)
                    current = ""
                pieces.append(unit[:cut])
                unit = unit[cut:].lstrip()
            if len(current) + len(unit) + 2 > limit and current:
                pieces.append(current)
                current = unit
            else:
                current = f"{current}\n\n{unit}" if current else unit
    if current.strip():
        pieces.append(current)
    return [p.strip() for p in pieces if len(p.strip()) >= 20]


def build_chunks(item: Item, pages: list[dict]) -> list[Chunk]:
    chunks, seq = [], 0
    for page in pages:
        for piece in split_page(normalise(page["text"])):
            chunks.append(
                Chunk(
                    item_id=item.id,
                    seq=seq,
                    section_title=item.title,
                    page_start=page["page_no"],
                    page_end=page["page_no"],
                    text=piece,
                    ocr_confidence=page["ocr_confidence"],
                    text_origin=page["text_origin"],
                )
            )
            seq += 1
    return chunks


# --- orchestration -----------------------------------------------------------------
def papers_for_reports(db, report_numbers: list[int]) -> list[Item]:
    reports = db.scalars(select(Item).where(Item.item_type == "report")).all()
    ids = [r.id for r in reports if r.raw_metadata.get("listing_number") in report_numbers]
    return db.scalars(
        select(Item).where(Item.parent_id.in_(ids), Item.cache_path.is_not(None)).order_by(Item.id)
    ).all()


def extract(report_numbers: list[int], workers: int, force: bool) -> None:
    settings = get_settings()
    image_dir = OCR_DIR / "pages"
    with SessionLocal() as db:
        papers = papers_for_reports(db, report_numbers)
        done = set(db.scalars(select(Page.item_id).distinct()).all())
        todo = [p for p in papers if force or p.id not in done]
        print(f"{len(papers)} papers with PDFs; {len(todo)} to extract using {workers} workers")
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(process_pdf, p.id, str(DATA_DIR / p.cache_path), str(image_dir), settings.tesseract_cmd): p
                for p in todo
            }
            for n, future in enumerate(as_completed(futures), start=1):
                paper = futures[future]
                try:
                    pages = future.result()
                except Exception as exc:  # a broken PDF must not stop the batch
                    log.error("FAILED item %s (%s): %s", paper.id, paper.title[:60], exc)
                    continue
                db.execute(delete(Chunk).where(Chunk.item_id == paper.id))
                db.execute(delete(Page).where(Page.item_id == paper.id))
                db.add_all(Page(item_id=paper.id, **pg) for pg in pages)
                db.add_all(build_chunks(paper, pages))
                paper.page_count = len(pages)
                db.commit()
                if n % 10 == 0 or n == len(todo):
                    print(f"  {n}/{len(todo)} papers extracted")


def quality_report() -> None:
    """One row per report: pages, share OCR'd, mean OCR confidence, empty pages."""
    rows = []
    with SessionLocal() as db:
        for report in db.scalars(select(Item).where(Item.item_type == "report").order_by(Item.id)):
            pages = db.scalars(
                select(Page).join(Item, Item.id == Page.item_id).where(Item.parent_id == report.id)
            ).all()
            if not pages:
                continue
            ocr = [p for p in pages if p.text_origin == "ocr"]
            confs = [p.ocr_confidence for p in ocr if p.ocr_confidence is not None]
            empty = sum(1 for p in pages if len(p.text.strip()) < 20)
            rows.append(
                {
                    "report": report.raw_metadata.get("listing_number"),
                    "title": report.title,
                    "papers": len({p.item_id for p in pages}),
                    "pages": len(pages),
                    "pct_ocr": round(100 * len(ocr) / len(pages), 1),
                    "mean_ocr_conf": round(statistics.mean(confs), 1) if confs else None,
                    "low_conf_pages": sum(1 for c in confs if c < 70),
                    "empty_pages": empty,
                }
            )
    out = OCR_DIR / "quality_report.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["report"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{'No':>3} {'papers':>6} {'pages':>5} {'%OCR':>5} {'conf':>5} {'<70':>4} {'empty':>5}  title")
    for r in rows:
        conf = "-" if r["mean_ocr_conf"] is None else f"{r['mean_ocr_conf']:.1f}"
        print(
            f"{r['report'] or '-':>3} {r['papers']:>6} {r['pages']:>5} {r['pct_ocr']:>5} {conf:>5} "
            f"{r['low_conf_pages']:>4} {r['empty_pages']:>5}  {r['title'][:70]}"
        )
    print(f"\nSaved to {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", help="comma-separated report numbers to extract")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true", help="re-extract papers already done")
    ap.add_argument("--quality", action="store_true", help="print the per-report quality table")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.reports:
        extract([int(n) for n in args.reports.split(",")], args.workers, args.force)
    if args.quality or args.reports:
        quality_report()


if __name__ == "__main__":
    main()
