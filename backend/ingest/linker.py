"""Stage 4: link every item to its expedition, stations, topics and year.

Status rule:
  * confirmed   - NCPOR's own catalogue or printed page says so (report title, the DSpace section a
                  paper sits in, the year in a paper's printed header)
  * unconfirmed - our inference (keywords in titles/text, or the language model) until a curator checks

Re-running is safe: existing links (including curator decisions) are never overwritten.

Run from backend/:  .venv\\Scripts\\python -m ingest.linker [--no-model]
"""
import argparse
import logging
import re
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import Chunk, Expedition, Item, ItemLink, Page, Station, Topic
from app.services import llm
from ingest.reference import STATIONS, TOPICS, expedition_number, keyword_pattern

log = logging.getLogger(__name__)

SEASON_RE = re.compile(r"\b((?:19|20)\d{2})\s*[-–/]\s*(\d{2,4})\b")
PRINTED_YEAR_RE = re.compile(r"Scientific\s+Report,?\s+((?:19|20)\d{2})\b", re.I)
MIN_TEXT_MENTIONS = 2


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# --- reference data ----------------------------------------------------------------
def seed_reference(db: Session) -> None:
    for s in STATIONS:
        row = db.scalar(select(Station).where(Station.name == s["name"])) or Station(name=s["name"])
        row.region, row.aliases = s["region"], s["aliases"]
        db.add(row)
    for t in TOPICS:
        row = db.scalar(select(Topic).where(Topic.key == t["key"])) or Topic(key=t["key"])
        row.label, row.keywords = t["label"], t["keywords"]
        db.add(row)
    db.flush()


def ensure_expedition(db: Session, code: str, **fields) -> Expedition:
    exp = db.scalar(select(Expedition).where(Expedition.code == code))
    if exp is None:
        exp = Expedition(code=code, **fields)
        db.add(exp)
        db.flush()
    else:
        for key, value in fields.items():
            if value is not None and getattr(exp, key) is None:
                setattr(exp, key, value)
    return exp


def expedition_for_report(db: Session, report: Item) -> tuple[Expedition | None, str]:
    title = report.title
    found = expedition_number(title)
    season = SEASON_RE.search(title)
    season_text = f"{season.group(1)}-{season.group(2)}" if season else None
    if found:
        number, words = found
        exp = ensure_expedition(
            db,
            f"ISEA-{number}",
            number=number,
            region="Antarctic",
            name=f"{ordinal(number)} Indian Expedition to Antarctica",
            source_url=report.original_url,
        )
        if season_text and exp.season is None:
            exp.season = season_text
            exp.source_url = report.original_url  # the season comes from this record's title
        return exp, f'report title contains "{words}"'
    if "weddell" in title.lower():
        exp = ensure_expedition(
            db, "WEDDELL-SEA", number=None, region="Antarctic",
            name="Indian Expedition to Weddell Sea", source_url=report.original_url,
        )
        return exp, 'report title contains "Expedition To Weddell Sea"'
    return None, ""


# --- link writing ------------------------------------------------------------------------
def add_link(db: Session, item: Item, link_type: str, target_id: int, method: str, status: str, evidence: str,
             confirmed_by: str | None = None) -> bool:
    values = {
        "item_id": item.id, "link_type": link_type, "method": method, "status": status,
        "evidence": evidence[:500], "confirmed_by": confirmed_by,
        "expedition_id": None, "station_id": None, "topic_id": None, "year": None,
    }
    values[{"expedition": "expedition_id", "station": "station_id", "topic": "topic_id", "year": "year"}[link_type]] = target_id
    if status == "confirmed":
        values["confirmed_at"] = func.now()
    stmt = (
        insert(ItemLink).values(**values)
        .on_conflict_do_nothing(constraint="uq_item_links_target")
        .returning(ItemLink.id)
    )
    return db.execute(stmt).scalar() is not None


def item_text(db: Session, item: Item) -> str:
    return "\n".join(db.scalars(select(Chunk.text).where(Chunk.item_id == item.id).order_by(Chunk.seq)).all())


def rule_links(db: Session, item: Item, stations: list[Station], topics: list[Topic],
               expedition: Expedition | None, exp_evidence: str) -> None:
    if expedition is not None:
        add_link(db, item, "expedition", expedition.id, "rule", "confirmed", exp_evidence, "rule:ncpor-catalogue")
        if expedition.season:
            start = int(expedition.season[:4])
            add_link(db, item, "year", start, "rule", "confirmed",
                     f"expedition season {expedition.season} stated in {expedition.source_url}", "rule:ncpor-catalogue")

    section = item.raw_metadata.get("collection", "") if item.item_type == "paper" else ""
    text = item_text(db, item)

    # Publication year printed in the paper's running header, e.g.
    # "Ninth Indian Expedition to Antarctica, Scientific Report, 1994".
    if item.item_type == "paper":
        first_page = db.scalar(select(Page.text).where(Page.item_id == item.id, Page.page_no == 1)) or ""
        m = PRINTED_YEAR_RE.search(first_page[:600])
        if m:
            year = int(m.group(1))
            item.published_year = year
            add_link(db, item, "year", year, "rule", "confirmed",
                     f'page 1 header reads "{m.group(0).strip()}" (publication year)', "rule:printed-header")

    for st in stations:
        pat = keyword_pattern(st.aliases)
        if pat.search(item.title):
            add_link(db, item, "station", st.id, "rule", "unconfirmed", f'title mentions "{st.name}"')
            continue
        hits = pat.findall(text)
        if len(hits) >= MIN_TEXT_MENTIONS:
            add_link(db, item, "station", st.id, "rule", "unconfirmed", f'text mentions "{st.name}" {len(hits)} times')

    for tp in topics:
        pat = keyword_pattern(tp.keywords)
        if section and pat.search(section):
            add_link(db, item, "topic", tp.id, "rule", "confirmed",
                     f'NCPOR filed this paper under section "{section}"', "rule:ncpor-catalogue")
        elif m := pat.search(item.title):
            add_link(db, item, "topic", tp.id, "rule", "unconfirmed", f'title contains "{m.group(0)}"')


# --- model fallback ------------------------------------------------------------------------
CLASSIFY_SYSTEM = (
    "You classify documents from India's polar research archive. Choose ONLY from the lists given. "
    "If the text does not clearly support a choice, return an empty list. Never guess an expedition number "
    "that is not written in the text."
)


def model_links(db: Session, item: Item, topics: list[Topic], expeditions: list[Expedition], need_expedition: bool) -> int:
    text = item_text(db, item)[:4000]
    topic_keys = [t.key for t in topics]
    prompt = (
        f"Title: {item.title}\n\nText (may contain OCR errors):\n{text or '(no text extracted)'}\n\n"
        f"Allowed topic keys: {topic_keys}\n"
        f"Allowed expedition codes: {[e.code for e in expeditions] if need_expedition else []}\n"
        "Return the topic keys (at most 2) and the expedition code (or null) this document is about, "
        "with a short quote from the text as evidence for each."
    )
    schema = {
        "type": "object",
        "properties": {
            "topics": {"type": "array", "items": {"type": "object", "properties": {
                "key": {"type": "string", "enum": topic_keys}, "evidence": {"type": "string"}},
                "required": ["key", "evidence"]}},
            "expedition": {"type": "object", "nullable": True, "properties": {
                "code": {"type": "string"}, "evidence": {"type": "string"}}, "required": ["code", "evidence"]},
        },
        "required": ["topics"],
    }
    result = llm.generate_json(CLASSIFY_SYSTEM, prompt, schema, purpose="bulk")
    added = 0
    by_key = {t.key: t for t in topics}
    for choice in result.get("topics", [])[:2]:
        if choice.get("key") in by_key:
            added += add_link(db, item, "topic", by_key[choice["key"]].id, "model", "unconfirmed",
                              f'model: "{choice.get("evidence", "")}"')
    exp_choice = result.get("expedition")
    if need_expedition and exp_choice:
        exp = next((e for e in expeditions if e.code == exp_choice.get("code")), None)
        if exp:
            added += add_link(db, item, "expedition", exp.id, "model", "unconfirmed",
                              f'model: "{exp_choice.get("evidence", "")}"')
    return added


# --- orchestration -------------------------------------------------------------------------
def run(use_model: bool = True) -> None:
    with SessionLocal() as db:
        seed_reference(db)
        stations = db.scalars(select(Station)).all()
        topics = db.scalars(select(Topic)).all()

        reports = db.scalars(select(Item).where(Item.item_type == "report")).all()
        for report in reports:
            exp, evidence = expedition_for_report(db, report)
            rule_links(db, report, stations, topics, exp, evidence)
            for paper in db.scalars(select(Item).where(Item.parent_id == report.id)):
                paper_evidence = f'paper is part of report "{report.title}"'
                rule_links(db, paper, stations, topics, exp, paper_evidence)
            db.commit()

        # DSpace records rules could not classify: no expedition link, or (papers) no topic link.
        # News posts are left alone: most are not about any expedition, and guessing one would be wrong.
        expeditions = db.scalars(select(Expedition)).all()
        linked = lambda link_type: select(ItemLink.item_id).where(
            ItemLink.link_type == link_type, ItemLink.status != "rejected")
        archive = Item.item_type.in_(("report", "paper"))
        no_exp = db.scalars(select(Item).where(archive, Item.id.not_in(linked("expedition")))).all()
        no_topic = db.scalars(select(Item).where(Item.item_type == "paper", Item.id.not_in(linked("topic")))).all()
        pending = {i.id: i for i in no_exp + no_topic}
        model_added, model_skipped, failures_in_row = 0, 0, 0
        for item in pending.values():
            if not use_model or failures_in_row >= 5:
                model_skipped += 1
                continue
            try:
                model_added += model_links(db, item, topics, expeditions, need_expedition=item in no_exp)
                db.commit()
                failures_in_row = 0
            except llm.LLMNotConfigured as exc:
                print(f"Model fallback skipped: {exc}")
                use_model = False
                model_skipped += 1
            except llm.LLMUnavailable:
                db.rollback()
                failures_in_row += 1
                model_skipped += 1
        if failures_in_row >= 5:
            print("Model fallback stopped after 5 failures in a row (API busy or rate-limited). Re-run later.")

        summarise(db, model_skipped)


def summarise(db: Session, model_skipped: int) -> None:
    rows = db.execute(
        select(ItemLink.link_type, ItemLink.method, ItemLink.status, func.count())
        .group_by(ItemLink.link_type, ItemLink.method, ItemLink.status)
        .order_by(ItemLink.link_type, ItemLink.method, ItemLink.status)
    ).all()
    print(f"\n{'link type':<11} {'method':<7} {'status':<12} {'count':>6}")
    for r in rows:
        print(f"{r[0]:<11} {r[1]:<7} {r[2]:<12} {r[3]:>6}")
    by_method = Counter()
    for r in rows:
        by_method[r[1]] += r[3]
    print(f"\nLinks from rules: {by_method['rule']}   from model: {by_method['model']}")
    has_exp = select(ItemLink.item_id).where(ItemLink.link_type == "expedition", ItemLink.status != "rejected")
    for item_type in ("report", "paper", "news"):
        total = db.scalar(select(func.count()).select_from(Item).where(Item.item_type == item_type))
        with_exp = db.scalar(select(func.count()).select_from(Item).where(Item.item_type == item_type, Item.id.in_(has_exp)))
        print(f"{item_type:>7} items with an expedition link: {with_exp} / {total}")
    missing = db.scalars(select(Item.title).where(Item.item_type.in_(("report", "paper")), Item.id.not_in(has_exp))).all()
    for title in missing[:10]:
        print(f"  archive item with no expedition: {title[:90]}")
    if model_skipped:
        print(f"Items still waiting for model classification: {model_skipped}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-model", action="store_true", help="rules only; skip the language-model fallback")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(use_model=not args.no_model)


if __name__ == "__main__":
    main()
