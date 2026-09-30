"""Harvest NCPOR news posts from the public RSS feed and link them to expeditions/stations/topics.

The feed (found on https://ncpor.res.in/rssfeeds) has no per-post links, so each item's
original_url is the feed itself, which is exactly where the text was harvested from.

News is also how expeditions after the 30th (not in DSpace) enter the index: a post that says
"46th Indian Scientific Expedition to Antarctica" creates ISEA-46 with the feed as its source.

Run from backend/:  .venv\\Scripts\\python -m ingest.news [--refresh]
"""
import argparse
import hashlib
import html
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

from lxml import etree
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import Chunk, Expedition, Item, Page, Source, Station, Topic
from ingest.extract import split_page
from ingest.http import PoliteClient
from ingest.linker import add_link, ensure_expedition, ordinal, seed_reference
from ingest.reference import find_expeditions, keyword_pattern

FEED_URL = "https://ncpor.res.in/upload/rssfeed/news.xml"
LISTING_URL = "https://ncpor.res.in/rssfeeds"

REGIONS = [  # checked in order; "antarctic" before "arctic"
    ("southern ocean", "Southern Ocean", "SOE", "Indian Scientific Expedition to the Southern Ocean"),
    ("antarctic", "Antarctic", "ISEA", "Indian Expedition to Antarctica"),
    ("arctic", "Arctic", "ARC", "Indian Arctic Expedition"),
]


def clean_html(text: str) -> str:
    text = html.unescape(html.unescape(text or ""))
    text = re.sub(r"<[^>]+>", " ", text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def dedupe_repeats(text: str) -> str:
    """Some old posts repeat the same sentence many times; keep one copy."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    seen, out = set(), []
    for s in sentences:
        key = s.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(s.strip())
    return " ".join(out)


def parse_feed(data: bytes) -> list[dict]:
    root = etree.fromstring(data, parser=etree.XMLParser(recover=True, huge_tree=True))
    posts = []
    for it in root.iterfind(".//item"):
        title = clean_html(it.findtext("title") or "")
        body = dedupe_repeats(clean_html(it.findtext("description") or ""))
        pub = it.findtext("pubDate")
        try:
            published = parsedate_to_datetime(pub) if pub else None
        except (TypeError, ValueError):
            published = None
        if not title:
            continue
        key = hashlib.sha1(f"{title}|{pub}".encode()).hexdigest()[:20]
        posts.append({"external_id": f"news:{key}", "title": title, "body": body, "pub_raw": pub,
                      "published": published})
    return posts


def expedition_mentions(text: str) -> list[tuple[str, int, str, str, str]]:
    """[(code, number, region, name, evidence sentence)] for numbered expeditions named in the text."""
    found = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        for number, words, end, is_isea in find_expeditions(sentence):
            # Region comes only from the matched words and the few words after them
            # ("... Expedition to the Southern Ocean"), never from elsewhere in the sentence.
            window = (words + sentence[end : end + 40]).lower()
            if is_isea:
                region = REGIONS[1]
            else:
                region = next((r for r in REGIONS if re.search(rf"\b{r[0]}", window)), None)
            if region is None:
                continue
            _, region_name, prefix, base = region
            found.append((f"{prefix}-{number}", number, region_name, f"{ordinal(number)} {base}", sentence.strip()[:300]))
    return found


def get_source(db: Session) -> Source:
    source = db.scalar(select(Source).where(Source.key == "ncpor_rss"))
    if source is None:
        source = Source(key="ncpor_rss", name="NCPOR news (RSS)", base_url=FEED_URL,
                        notes=f"News feed listed at {LISTING_URL}")
        db.add(source)
        db.flush()
    return source


def harvest(refresh: bool) -> None:
    client = PoliteClient()
    try:
        data = client.get(FEED_URL, suffix=".xml", refresh=refresh)
    finally:
        client.close()
    posts = parse_feed(data)

    with SessionLocal() as db:
        seed_reference(db)
        source = get_source(db)
        stations = db.scalars(select(Station)).all()
        topics = db.scalars(select(Topic)).all()
        new = 0
        exp_links = 0
        for post in posts:
            item = db.scalar(select(Item).where(Item.source_id == source.id, Item.external_id == post["external_id"]))
            if item is None:
                item = Item(source_id=source.id, external_id=post["external_id"], item_type="news",
                            title=post["title"], original_url=FEED_URL)
                db.add(item)
                new += 1
            item.published_date = post["published"].date() if post["published"] else None
            item.published_year = post["published"].year if post["published"] else None
            item.raw_metadata = {"pubDate": post["pub_raw"], "feed": FEED_URL, "listing": LISTING_URL,
                                 "language": "hi" if re.search(r"[ऀ-ॿ]", post["title"]) else "en"}
            item.page_count = 1
            db.flush()

            full = f"{post['title']}\n\n{post['body']}".strip()
            current = db.scalar(select(Page.text).where(Page.item_id == item.id, Page.page_no == 1))
            if current != full:  # rebuild only on change, so chunk IDs cited by drafts stay stable
                db.execute(delete(Chunk).where(Chunk.item_id == item.id))
                db.execute(delete(Page).where(Page.item_id == item.id))
                db.add(Page(item_id=item.id, page_no=1, text=full, text_origin="text_layer"))
                for seq, piece in enumerate(split_page(full) or [full]):
                    db.add(Chunk(item_id=item.id, seq=seq, section_title=post["title"], page_start=1, page_end=1,
                                 text=piece, text_origin="text_layer"))

            # Links: our inference from the post's words, so all start unconfirmed.
            for code, number, region, name, sentence in expedition_mentions(full):
                exp = ensure_expedition(db, code, number=number, region=region, name=name, source_url=FEED_URL)
                exp_links += add_link(db, item, "expedition", exp.id, "rule", "unconfirmed", f'post says: "{sentence}"')
            if item.published_year:
                add_link(db, item, "year", item.published_year, "rule", "confirmed",
                         f"RSS pubDate {post['pub_raw']}", "rule:ncpor-catalogue")
            for st in stations:
                if keyword_pattern(st.aliases).search(full):
                    add_link(db, item, "station", st.id, "rule", "unconfirmed", f'post mentions "{st.name}"')
            for tp in topics:
                if m := keyword_pattern(tp.keywords).search(post["title"]):
                    add_link(db, item, "topic", tp.id, "rule", "unconfirmed", f'title contains "{m.group(0)}"')
        db.commit()
        exps = db.scalars(select(Expedition).where(Expedition.source_url == FEED_URL).order_by(Expedition.code)).all()
        print(f"News posts in feed: {len(posts)}  new: {new}  expedition links added: {exp_links}")
        print("Expeditions first seen in news:", ", ".join(e.code for e in exps) or "none")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-download the feed")
    harvest(ap.parse_args().refresh)


if __name__ == "__main__":
    main()
