import csv
import io
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from streamlit.testing.v1 import AppTest

from app_unified_search import results_to_csv
from database.models import Bid
from services import search_service


APP = str(Path(__file__).resolve().parents[2] / "app_unified_search.py")


@pytest.fixture
def app(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Bid.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    now = datetime(2026, 9, 17)
    with factory() as session:
        for bid_id in range(1, 46):
            session.add(Bid(
                id=bid_id, filename=f"道路工事 {bid_id}", notes=None,
                prefecture_code="13" if bid_id <= 25 else "27",
                organization_name="東京都建設局" if bid_id <= 25 else "大阪府",
                bid_type="一般競争入札" if bid_id <= 25 else "随意契約",
                current_status="新規", analyzed_at=now, created_at=now,
                updated_at=now, announcement_date=now,
            ))
        session.commit()
    monkeypatch.setattr(search_service, "get_session", factory)
    yield AppTest.from_file(APP, default_timeout=15).run()
    engine.dispose()


def test_initial_screen(app):
    assert not app.exception
    assert app.info[0].value == "検索キーワードを入力してください"
    assert not app.dataframe
    assert app.selectbox(key="bid_type").value == ""
    assert "東京都" in app.multiselect(key="prefecture").options


def test_pagination_and_new_search(app):
    app.text_input(key="keyword").set_value("道路")
    app.button[0].click().run()
    assert not app.exception
    assert list(app.dataframe[0].value["id"]) == list(range(1, 21))
    app.selectbox(key="current_page").select(2).run()
    assert not app.exception
    assert list(app.dataframe[0].value["id"]) == list(range(21, 41))
    app.selectbox(key="current_page").select(3).run()
    assert list(app.dataframe[0].value["id"]) == list(range(41, 46))
    app.text_input(key="keyword").set_value("不存在")
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["current_page"] == 1
    assert app.info[0].value == "検索結果が見つかりませんでした"
    assert not app.dataframe
    assert not app.get("download_button")


def test_submitted_filters_are_retained(app):
    app.text_input(key="keyword").set_value("道路 工事")
    app.text_input(key="organization").set_value("建設")
    app.multiselect(key="prefecture").select("13")
    app.selectbox(key="bid_type").select("一般競争入札")
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["search_results"]["total"] == 25
    app.text_input(key="keyword").set_value("未送信")
    app.selectbox(key="current_page").select(2).run()
    assert not app.exception
    assert list(app.dataframe[0].value["id"]) == list(range(21, 26))
    assert app.session_state["search_conditions"]["keyword"] == "道路 工事"
    rows = app.session_state["search_results"]["results"]
    downloaded = list(csv.reader(io.StringIO(results_to_csv(rows).decode("utf-8-sig"))))
    assert downloaded[0] == ["案件番号", "タイトル", "発注機関", "公開日", "予算額（円）", "資格要件", "納期限", "成果物"]
    assert [int(row[0]) for row in downloaded[1:]] == list(range(21, 26))
    assert all(row[4] == "" and row[6] == "" for row in downloaded[1:])
    assert len(app.get("download_button")) == 1


def test_or_not_controls(app):
    app.text_input(key="keyword").set_value("道路 存在しない")
    app.toggle(key="use_or").set_value(True)
    app.button[0].click().run()
    assert app.session_state["search_results"]["total"] == 45
    app.toggle(key="use_not").set_value(True)
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["search_results"]["total"] == 0


def test_database_failure_is_safe(app, monkeypatch):
    def fail(**kwargs):
        raise OperationalError("private SQL", {}, Exception("private password"))

    monkeypatch.setattr(search_service, "search_bids", fail)
    app.button[0].click().run()
    assert not app.exception
    assert "DB接続" in app.error[0].value
    assert "private" not in app.error[0].value
    assert not app.dataframe


def test_csv_encoding_escaping_and_formula_safety():
    from datetime import date

    data = results_to_csv([
        {"id": 1, "title": '=HYPERLINK("example")', "organization": None},
        {"id": 2, "title": "日本語,改行\n次の行", "organization": "\t=1+1"},
        {
            "id": 3, "title": "通常", "organization": "組織",
            "budget_amount": 1000000, "qualification_requirements": None,
            "delivery_deadline": date(2026, 10, 1), "deliverables": "報告書\n資料",
        },
    ])
    assert data.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    assert rows[1][1] == '\'=HYPERLINK("example")'
    assert rows[1][2:] == ["", "", "", "", "", ""]
    assert rows[2][1] == "日本語,改行\n次の行"
    assert rows[2][2] == "'\t=1+1"
    assert rows[3] == ["3", "通常", "組織", "", "1000000", "", "2026-10-01", "報告書\n資料"]


def test_css_loaded_outside_project_directory(app, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app.run()
    assert not app.exception
    assert any("stFormSubmitButton" in item.value for item in app.markdown)


def test_missing_css_uses_default_style(app, monkeypatch):
    original = Path.read_text

    def read_text(path, *args, **kwargs):
        if path.name == "custom_unified_search.css":
            raise FileNotFoundError(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    app.run()
    assert not app.exception
    assert "標準表示" in app.warning[0].value
    assert app.info[0].value == "検索キーワードを入力してください"


def test_page_clamped_when_records_disappear(app):
    app.button[0].click().run()
    app.selectbox(key="current_page").select(3).run()
    with search_service.get_session() as session:
        session.query(Bid).filter(Bid.id > 5).delete()
        session.commit()
    app.run()
    assert not app.exception
    assert app.session_state["current_page"] == 1
    assert list(app.dataframe[0].value["id"]) == list(range(1, 6))
