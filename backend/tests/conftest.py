"""Tests run against a separate database (ncpor_test) in the same container, migrated from scratch.
The language model is replaced by a fake, so tests never call Gemini."""
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

DEV_URL = make_url(get_settings().database_url)
TEST_URL = DEV_URL.set(database="ncpor_test")


@pytest.fixture(scope="session")
def engine():
    admin = create_engine(DEV_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS ncpor_test WITH (FORCE)"))
        conn.execute(text("CREATE DATABASE ncpor_test"))
    admin.dispose()

    from alembic import command
    from alembic.config import Config

    os.environ["DATABASE_URL"] = TEST_URL.render_as_string(hide_password=False)
    get_settings.cache_clear()
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.upgrade(cfg, "head")

    eng = create_engine(TEST_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        yield session


@pytest.fixture
def client(engine, monkeypatch):
    from fastapi.testclient import TestClient

    from app.core import db as db_module
    from app.main import app

    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        with Session() as s:
            yield s

    app.dependency_overrides[db_module.get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
