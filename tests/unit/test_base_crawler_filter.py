"""ベースクローラーのフィルタリング機能テスト

BaseCrawler に追加された categories / priority_levels フィルタリングパラメータの
ユニットテスト。
"""
import pytest
from datetime import datetime
from typing import List, Any, Optional

from crawler.base_crawler import BaseCrawler, PRIORITY_LEVEL_MAP


class _ConcreteCrawler(BaseCrawler):
    """テスト用の具象サブクラス（抽象メソッドを実装）"""

    def parse_list(self, html: str) -> List[Any]:
        return []

    def parse_detail(self, html: str) -> Any:
        return None

    def save(self, items: List[Any]):
        pass


def _make_agency(name, category_id, priority_level):
    from database.models import Agency
    return Agency(
        name=name,
        category_id=category_id,
        priority_level=priority_level,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


class TestBaseCrawlerFiltering:
    """フィルタリングパラメータのテスト"""

    @pytest.fixture(autouse=True)
    def _clean_tables(self, db_session):
        """各テスト前に agencies と agency_categories テーブルをクリア"""
        from database.models import Agency, AgencyCategory
        db_session.query(Agency).delete()
        db_session.query(AgencyCategory).delete()
        db_session.commit()
        yield

    def test_default_params_no_filter(self):
        """デフォルトでは categories/priority_levels が None"""
        crawler = _ConcreteCrawler()
        assert crawler.categories is None
        assert crawler.priority_levels is None
        assert crawler.delay == 0.0

    def test_logger_set(self):
        """self.logger が設定されている"""
        crawler = _ConcreteCrawler()
        assert crawler.logger is not None

    def test_categories_stored(self):
        """categories パラメータがインスタンス変数に保存される"""
        crawler = _ConcreteCrawler(categories=["都道府県", "市区町村"])
        assert crawler.categories == ["都道府県", "市区町村"]

    def test_priority_levels_stored(self):
        """priority_levels パラメータがインスタンス変数に保存される"""
        crawler = _ConcreteCrawler(priority_levels=["高"])
        assert crawler.priority_levels == ["高"]

    def test_resolve_priority_string_high(self):
        """'高' -> 0"""
        crawler = _ConcreteCrawler(priority_levels=["高"])
        assert crawler._resolve_priority_levels() == [0]

    def test_resolve_priority_string_medium(self):
        """'中' -> 1"""
        crawler = _ConcreteCrawler(priority_levels=["中"])
        assert crawler._resolve_priority_levels() == [1]

    def test_resolve_priority_string_low(self):
        """'低' -> 2"""
        crawler = _ConcreteCrawler(priority_levels=["低"])
        assert crawler._resolve_priority_levels() == [2]

    def test_resolve_priority_int(self):
        """整数はそのまま返される"""
        crawler = _ConcreteCrawler(priority_levels=[0, 2])
        assert crawler._resolve_priority_levels() == [0, 2]

    def test_resolve_priority_mixed(self):
        """文字列と整数が混在"""
        crawler = _ConcreteCrawler(priority_levels=["高", 2])
        assert crawler._resolve_priority_levels() == [0, 2]

    def test_resolve_priority_none(self):
        """None の場合は空リスト"""
        crawler = _ConcreteCrawler()
        assert crawler._resolve_priority_levels() == []

    def test_resolve_priority_invalid_string(self):
        """不明な文字列は警告を出し空リストになる"""
        crawler = _ConcreteCrawler(priority_levels=["unknown"])
        resolved = crawler._resolve_priority_levels()
        assert resolved == []

    def test_priority_level_map(self):
        """PRIORITY_LEVEL_MAP の内容確認"""
        assert PRIORITY_LEVEL_MAP == {"高": 0, "中": 1, "低": 2}

    def test_get_target_agencies_no_filter(self, db_session):
        """フィルタなしの場合は全件取得"""
        from database.models import AgencyCategory

        cat = AgencyCategory(name="テストカテゴリ", description="test", priority=1)
        db_session.add(cat)
        db_session.flush()
        db_session.add(_make_agency("機関A", cat.id, 0))
        db_session.add(_make_agency("機関B", cat.id, 1))
        db_session.commit()

        crawler = _ConcreteCrawler()
        agencies = crawler._get_target_agencies(db_session)
        assert len(agencies) == 2

    def test_get_target_agencies_by_category(self, db_session):
        """categories フィルタで絞り込み"""
        from database.models import AgencyCategory

        cat1 = AgencyCategory(name="国", description="test", priority=1)
        cat2 = AgencyCategory(name="都道府県", description="test", priority=1)
        db_session.add_all([cat1, cat2])
        db_session.flush()

        db_session.add(_make_agency("機関A", cat1.id, 0))
        db_session.add(_make_agency("機関B", cat2.id, 0))
        db_session.commit()

        crawler = _ConcreteCrawler(categories=["都道府県"])
        agencies = crawler._get_target_agencies(db_session)
        assert len(agencies) == 1
        assert agencies[0].name == "機関B"

    def test_get_target_agencies_by_priority_high(self, db_session):
        """priority_levels=['高'] で絞り込み"""
        from database.models import AgencyCategory

        cat = AgencyCategory(name="テスト", description="test", priority=1)
        db_session.add(cat)
        db_session.flush()

        db_session.add(_make_agency("高優先", cat.id, 0))
        db_session.add(_make_agency("中優先", cat.id, 1))
        db_session.add(_make_agency("低優先", cat.id, 2))
        db_session.commit()

        crawler = _ConcreteCrawler(priority_levels=["高"])
        agencies = crawler._get_target_agencies(db_session)
        assert len(agencies) == 1
        assert agencies[0].name == "高優先"

    def test_get_target_agencies_by_priority_int(self, db_session):
        """priority_levels=[0] (整数) で絞り込み"""
        from database.models import AgencyCategory

        cat = AgencyCategory(name="テスト", description="test", priority=1)
        db_session.add(cat)
        db_session.flush()

        db_session.add(_make_agency("高優先", cat.id, 0))
        db_session.add(_make_agency("中優先", cat.id, 1))
        db_session.commit()

        crawler = _ConcreteCrawler(priority_levels=[0])
        agencies = crawler._get_target_agencies(db_session)
        assert len(agencies) == 1
        assert agencies[0].name == "高優先"

    def test_get_target_agencies_combined_filter(self, db_session):
        """categories + priority_levels 複合フィルタ"""
        from database.models import AgencyCategory

        cat1 = AgencyCategory(name="国", description="test", priority=1)
        cat2 = AgencyCategory(name="都道府県", description="test", priority=1)
        db_session.add_all([cat1, cat2])
        db_session.flush()

        db_session.add(_make_agency("国高", cat1.id, 0))
        db_session.add(_make_agency("国中", cat1.id, 1))
        db_session.add(_make_agency("県高", cat2.id, 0))
        db_session.add(_make_agency("県中", cat2.id, 1))
        db_session.commit()

        crawler = _ConcreteCrawler(categories=["都道府県"], priority_levels=["高"])
        agencies = crawler._get_target_agencies(db_session)
        assert len(agencies) == 1
        assert agencies[0].name == "県高"

    def test_get_target_agencies_no_matching_category(self, db_session):
        """存在しないカテゴリでフィルタ -> 0件"""
        from database.models import AgencyCategory

        cat = AgencyCategory(name="国", description="test", priority=1)
        db_session.add(cat)
        db_session.flush()

        db_session.add(_make_agency("機関A", cat.id, 0))
        db_session.commit()

        crawler = _ConcreteCrawler(categories=["存在しないカテゴリ"])
        agencies = crawler._get_target_agencies(db_session)
        assert len(agencies) == 0
