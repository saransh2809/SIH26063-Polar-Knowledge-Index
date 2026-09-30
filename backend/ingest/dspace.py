"""Harvest expedition reports from DSpace at NCAOR.

Structure on the server:
    community  = one report   ("09] Scientific Report Of Ninth Indian Expedition To Antarctica")
    collection = one section  ("5]Earth Sciences")
    item       = one paper, with its own PDF

Metadata comes from OAI-PMH (a standard protocol for copying catalogue records). OAI records
carry no PDF link, so the paper's public page is read once to find it.

Run from backend/:
    .venv\\Scripts\\python -m ingest.dspace                       # metadata for all reports
    .venv\\Scripts\\python -m ingest.dspace --download 1,9,15     # + PDFs for those reports (max 10)
"""
import argparse
import html
import logging
import re
from datetime import datetime, timezone

from lxml import etree
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DATA_DIR
from app.core.db import SessionLocal
from app.models import Item, Source
from ingest.http import EmptyResponse, PoliteClient

log = logging.getLogger(__name__)

BASE = "http://14.139.119.23:8080"
OAI = BASE + "/dspace-oai/request"
MAX_REPORTS_TO_DOWNLOAD = 10

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
}
COMMUNITY_RE = re.compile(r'<strong><A HREF="/dspace/handle/([\d/]+)">(.*?)</A></strong>', re.I | re.S)
COLLECTION_RE = re.compile(
    r'class="collectionListItem">\s*<A HREF="/dspace/handle/([\d/]+)">(.*?)</A>', re.I | re.S
)
BITSTREAM_RE = re.compile(r'HREF="(/dspace/bitstream/[^"]+?\.pdf)"', re.I)
REPORT_NUMBER_RE = re.compile(r"^\s*(\d{1,2})\]")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def handle_url(handle: str) -> str:
    return f"{BASE}/dspace/handle/{handle}"


# --- community list ----------------------------------------------------------
def parse_community_list(page: str) -> list[dict]:
    """Walk the page in order: each community is followed by its collections."""
    events = [(m.start(), "community", m) for m in COMMUNITY_RE.finditer(page)]
    events += [(m.start(), "collection", m) for m in COLLECTION_RE.finditer(page)]
    communities: list[dict] = []
    for _, kind, m in sorted(events, key=lambda e: e[0]):
        if kind == "community":
            communities.append({"handle": m.group(1), "title": clean(m.group(2)), "collections": []})
        elif communities:
            communities[-1]["collections"].append({"handle": m.group(1), "name": clean(m.group(2))})
    return communities


def is_expedition_report(community: dict) -> bool:
    return "expedition" in community["title"].lower()


# --- OAI-PMH -------------------------------------------------------------------
def oai_records(client: PoliteClient, set_spec: str, refresh: bool) -> list[dict]:
    """All records in one OAI set, following resumption tokens."""
    records: list[dict] = []
    url = f"{OAI}?verb=ListRecords&metadataPrefix=oai_dc&set={set_spec}"
    parser = etree.XMLParser(recover=True)  # the server emits unescaped '&'
    while url:
        root = etree.fromstring(client.get(url, suffix=".xml", refresh=refresh), parser=parser)
        if root is None:
            break
        error = root.find("oai:error", NS)
        if error is not None:
            if error.get("code") != "noRecordsMatch":
                log.warning("OAI error for %s: %s", set_spec, error.text)
            break
        for rec in root.iterfind(".//oai:record", NS):
            header = rec.find("oai:header", NS)
            if header.get("status") == "deleted":
                continue
            identifier = header.findtext("oai:identifier", namespaces=NS) or ""
            dc = rec.find(".//{http://www.openarchives.org/OAI/2.0/oai_dc/}dc")
            values = lambda tag: [clean(e.text or "") for e in dc.iterfind(f"dc:{tag}", NS)] if dc is not None else []
            records.append(
                {
                    "handle": identifier.rsplit(":", 1)[-1],
                    "datestamp": header.findtext("oai:datestamp", namespaces=NS),
                    "title": (values("title") or [""])[0],
                    "creators": values("creator"),
                    "subjects": values("subject"),
                    "relation": values("relation"),
                    "type": values("type"),
                    "format": values("format"),
                    "language": values("language"),
                    "dc_date": values("date"),
                }
            )
        token = root.findtext(".//oai:resumptionToken", namespaces=NS)
        url = f"{OAI}?verb=ListRecords&resumptionToken={token}" if token else None
    return records


# --- database upserts --------------------------------------------------------
def get_source(db: Session) -> Source:
    source = db.scalar(select(Source).where(Source.key == "dspace"))
    if source is None:
        source = Source(
            key="dspace",
            name="DSpace at NCAOR",
            base_url=BASE + "/dspace/",
            notes="Scanned Scientific Reports of Indian Expeditions to Antarctica; harvested via OAI-PMH.",
        )
        db.add(source)
        db.flush()
    return source


def upsert_item(db: Session, source: Source, external_id: str, **fields) -> tuple[Item, bool]:
    item = db.scalar(select(Item).where(Item.source_id == source.id, Item.external_id == external_id))
    created = item is None
    if created:
        item = Item(source_id=source.id, external_id=external_id, **fields)
        db.add(item)
    else:
        for key, value in fields.items():
            setattr(item, key, value)
        item.updated_at = datetime.now(timezone.utc)
    db.flush()
    return item, created


def harvest_metadata(db: Session, client: PoliteClient, refresh: bool = False) -> dict:
    source = get_source(db)
    page = client.get(BASE + "/dspace/community-list", suffix=".html", refresh=refresh).decode("utf-8", "replace")
    communities = parse_community_list(page)
    stats = {"reports": 0, "papers_new": 0, "papers_seen": 0, "skipped_communities": []}

    for com in communities:
        if not is_expedition_report(com):
            stats["skipped_communities"].append(com["title"] or com["handle"])
            continue
        number = REPORT_NUMBER_RE.match(com["title"])
        report, _ = upsert_item(
            db,
            source,
            com["handle"],
            item_type="report",
            title=com["title"],
            original_url=handle_url(com["handle"]),
            raw_metadata={
                "dspace_community": com["handle"],
                "listing_number": int(number.group(1)) if number else None,
                "not_published": "not published" in com["title"].lower(),
                "collections": com["collections"],
            },
        )
        stats["reports"] += 1

        for col in com["collections"]:
            set_spec = "hdl_" + col["handle"].replace("/", "_")
            for rec in oai_records(client, set_spec, refresh):
                if not rec["handle"] or not rec["title"]:
                    continue
                existing = db.scalar(
                    select(Item).where(Item.source_id == source.id, Item.external_id == rec["handle"])
                )
                _, created = upsert_item(
                    db,
                    source,
                    rec["handle"],
                    item_type="paper",
                    parent_id=report.id,
                    title=rec["title"],
                    original_url=handle_url(rec["handle"]),
                    # Keep what we already learned (PDF link, cache path) on re-harvest.
                    file_url=existing.file_url if existing else None,
                    cache_path=existing.cache_path if existing else None,
                    raw_metadata={**rec, "collection": col["name"], "collection_handle": col["handle"]},
                )
                stats["papers_new" if created else "papers_seen"] += 1
        db.commit()
        log.info("report %s: done", com["title"])
    return stats


# --- PDFs ----------------------------------------------------------------------
def download_pdfs(db: Session, client: PoliteClient, report_numbers: list[int]) -> dict:
    if len(report_numbers) > MAX_REPORTS_TO_DOWNLOAD:
        raise SystemExit(f"Refusing: at most {MAX_REPORTS_TO_DOWNLOAD} reports may be downloaded at this stage.")
    reports = db.scalars(select(Item).where(Item.item_type == "report")).all()
    chosen = [r for r in reports if r.raw_metadata.get("listing_number") in report_numbers]
    stats = {"reports": len(chosen), "pdfs": 0, "no_pdf": 0, "empty": 0}
    for report in chosen:
        for paper in db.scalars(select(Item).where(Item.parent_id == report.id).order_by(Item.id)):
            if not paper.file_url:
                page = client.get(paper.original_url, suffix=".html").decode("utf-8", "replace")
                match = BITSTREAM_RE.search(page)
                if not match:
                    stats["no_pdf"] += 1
                    continue
                paper.file_url = BASE + html.unescape(match.group(1))
            path = client.cache_path_for(paper.file_url, ".pdf")
            try:
                client.get(paper.file_url, suffix=".pdf")
            except EmptyResponse:
                log.warning("DSpace returned an empty file for %s", paper.file_url)
                paper.cache_path = None
                stats["empty"] += 1
                continue
            paper.cache_path = path.relative_to(DATA_DIR).as_posix()
            stats["pdfs"] += 1
        db.commit()
        log.info("PDFs for %s: done", report.title)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--download", help="comma-separated report numbers whose PDFs to download (max 10)")
    ap.add_argument("--refresh", action="store_true", help="re-fetch metadata instead of using the cache")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    client = PoliteClient()
    try:
        with SessionLocal() as db:
            stats = harvest_metadata(db, client, refresh=args.refresh)
            print(f"Reports: {stats['reports']}  papers new: {stats['papers_new']}  already known: {stats['papers_seen']}")
            print("Skipped (not expedition reports):", "; ".join(stats["skipped_communities"]))
            if args.download:
                numbers = [int(n) for n in args.download.split(",") if n.strip()]
                dl = download_pdfs(db, client, numbers)
                print(f"PDFs: {dl['pdfs']} cached for {dl['reports']} reports; {dl['no_pdf']} papers had no PDF link; "
                      f"{dl['empty']} came back empty from the server")
    finally:
        print(f"Network requests this run: {client.network_requests}")
        client.close()


if __name__ == "__main__":
    main()
