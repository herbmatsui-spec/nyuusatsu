import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def run_isolated(tmp_path, script):
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'bids.db'}"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("first_import", ["app_mobile", "database.session"])
def test_session_helpers_preserve_generated_bid_mapping(tmp_path, first_import):
    run_isolated(tmp_path, f"import {first_import}\n" + """
from datetime import datetime
from importlib import import_module

from sqlalchemy import select

from database.engine import SessionLocal, engine
from database.models import Base, Bid
from database.models._generated import Bid as GeneratedBid
from database.models.bid import Bid as ModuleBid
from services.specification_similarity_service import SpecificationSimilarityService

assert Bid is GeneratedBid is ModuleBid
Base.metadata.create_all(engine)
now = datetime.now()
with SessionLocal() as session:
    session.add(Bid(
        id=1, filename="test.pdf", current_status="new", analyzed_at=now,
        created_at=now, updated_at=now, announcement_date=now,
        specification_text="specification", specification_text_clean="clean text",
        bid_difficulty_score=25.0, win_prediction_score=0.4,
    ))
    session.commit()

for name in ("database", "database.base", "database.engine", "database.session"):
    module = import_module(name)
    assert module.SessionLocal is SessionLocal
    with module.get_session() as session:
        queried = session.query(Bid).one()
        fetched = session.get(Bid, 1)
        selected = session.scalars(select(Bid)).one()
        assert type(queried) is GeneratedBid
        assert queried is fetched is selected
        assert queried.specification_text == "specification"
        assert queried.specification_text_clean == "clean text"
        assert queried.bid_difficulty_score == 25.0
        assert queried.win_prediction_score == 0.4
        service = SpecificationSimilarityService(session)
        assert service.search_bids()[0]["specification_text"] == "specification"
        assert service.search_bids(keyword="specification")[0]["id"] == 1
        assert service.get_bid_detail(1)["specification_text"] == "specification"
    generator = module.get_db()
    try:
        assert type(next(generator).get(Bid, 1)) is GeneratedBid
    finally:
        generator.close()
""")


def test_fresh_mobile_competitive_analysis_with_real_session(tmp_path):
    run_isolated(tmp_path, """
from datetime import datetime

from database.engine import SessionLocal, engine
from database.models import Base, Bid

Base.metadata.create_all(engine)
now = datetime.now()
with SessionLocal() as session:
    session.add(Bid(
        id=1, filename="test.pdf", current_status="new", analyzed_at=now,
        created_at=now, updated_at=now, announcement_date=now,
        specification_text="システム開発仕様書", specification_text_clean="システム開発仕様書",
    ))
    session.commit()
engine.dispose()
""")
    run_isolated(tmp_path, """
from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app_mobile.py", default_timeout=60).run()
assert not at.exception, [element.value for element in at.exception]
at.radio[0].set_value("競合分析").run()
assert not at.exception, [element.value for element in at.exception]
assert not at.error, [element.value for element in at.error]
assert at.selectbox(key="similarity_selected").value == 1
assert at.selectbox(key="prediction_selected").value == 1
""")
