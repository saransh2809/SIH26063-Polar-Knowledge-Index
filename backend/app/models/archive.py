"""Archive tables: what we harvested, its text, and what it is linked to."""
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_column

EMBEDDING_DIM = 768  # intfloat/multilingual-e5-base

ITEM_TYPES = ("report", "paper", "news", "video", "photo", "dataset_link")
TEXT_ORIGINS = ("text_layer", "ocr", "mixed")
LINK_TYPES = ("expedition", "station", "topic", "year")
LINK_METHODS = ("rule", "model", "manual")
LINK_STATUSES = ("confirmed", "unconfirmed", "rejected")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class Source(Base):
    """An external system we harvest from (DSpace, NCPOR RSS, YouTube, manual entry)."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    base_url: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["Item"]] = relationship(back_populates="source")


class Item(Base):
    """One harvested record. The original always stays at `original_url`."""

    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id"),
        CheckConstraint(_in("item_type", ITEM_TYPES), name="item_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    # A paper points to the report (DSpace community) it was published in.
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), index=True)
    # Stable ID inside the source system (e.g. a DSpace handle), used to avoid duplicates.
    external_id: Mapped[str] = mapped_column(String(300))
    item_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(Text)
    original_url: Mapped[str] = mapped_column(Text)
    # Direct link to the file (e.g. the PDF bitstream), if different from the landing page.
    file_url: Mapped[str | None] = mapped_column(Text)
    published_date: Mapped[date | None] = mapped_column(Date)
    published_year: Mapped[int | None] = mapped_column(Integer)
    raw_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Local cache path relative to data/, never served publicly.
    cache_path: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    harvested_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source: Mapped[Source] = relationship(back_populates="items")
    parent: Mapped["Item | None"] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list["Item"]] = relationship(back_populates="parent")
    pages: Mapped[list["Page"]] = relationship(back_populates="item", order_by="Page.page_no")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="item", order_by="Chunk.seq")
    links: Mapped[list["ItemLink"]] = relationship(back_populates="item")


class Page(Base):
    """Extracted text of one PDF page. Lets us show text beside the page image."""

    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("item_id", "page_no"),
        CheckConstraint(_in("text_origin", TEXT_ORIGINS), name="text_origin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    page_no: Mapped[int] = mapped_column(Integer)  # 1-based PDF page index
    # Page number printed on the scan (e.g. "241"), when it could be read.
    printed_page: Mapped[str | None] = mapped_column(String(20))
    text:Mapped[str] = mapped_column(Text, default="")
    text_origin: Mapped[str] = mapped_column(String(20))
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    image_path: Mapped[str | None] = mapped_column(Text)

    item: Mapped[Item] = relationship(back_populates="pages")


class Chunk(Base):
    """A searchable piece of an item's text, always with its page range."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("item_id", "seq"),
        CheckConstraint(_in("text_origin", TEXT_ORIGINS), name="text_origin"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(Text)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(section_title, '') || ' ' || text)", persisted=True),
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    text_origin: Mapped[str] = mapped_column(String(20))

    item: Mapped[Item] = relationship(back_populates="chunks")


class Expedition(Base):
    """An expedition. Facts beyond code/number/region need a `source_url`."""

    __tablename__ = "expeditions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)  # e.g. ISEA-9
    number: Mapped[int | None] = mapped_column(Integer)
    region: Mapped[str] = mapped_column(String(30))  # Antarctic / Arctic / Southern Ocean / Himalaya
    name: Mapped[str] = mapped_column(Text)
    season: Mapped[str | None] = mapped_column(String(30))
    source_url: Mapped[str | None] = mapped_column(Text)


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    region: Mapped[str] = mapped_column(String(30))
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)
    label: Mapped[str] = mapped_column(String(100))
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)


class ItemLink(Base):
    """Links an item to exactly one expedition, station, topic or year."""

    __tablename__ = "item_links"
    __table_args__ = (
        CheckConstraint(_in("link_type", LINK_TYPES), name="link_type"),
        CheckConstraint(_in("method", LINK_METHODS), name="method"),
        CheckConstraint(_in("status", LINK_STATUSES), name="status"),
        CheckConstraint(
            "(link_type = 'expedition') = (expedition_id IS NOT NULL) AND "
            "(link_type = 'station') = (station_id IS NOT NULL) AND "
            "(link_type = 'topic') = (topic_id IS NOT NULL) AND "
            "(link_type = 'year') = (year IS NOT NULL)",
            name="one_target",
        ),
        UniqueConstraint(
            "item_id", "link_type", "expedition_id", "station_id", "topic_id", "year",
            name="uq_item_links_target",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    link_type: Mapped[str] = mapped_column(String(20))
    expedition_id: Mapped[int | None] = mapped_column(ForeignKey("expeditions.id"))
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"))
    year: Mapped[int | None] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    # Why the link was made, e.g. 'title matched "Ninth Indian Expedition"'.
    evidence: Mapped[str | None] = mapped_column(Text)
    confirmed_by: Mapped[str | None] = mapped_column(String(100))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_column()

    item: Mapped[Item] = relationship(back_populates="links")
    expedition: Mapped[Expedition | None] = relationship()
    station: Mapped[Station | None] = relationship()
    topic: Mapped[Topic | None] = relationship()
