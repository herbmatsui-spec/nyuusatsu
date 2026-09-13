import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
import sys
import os

# プロジェクトルートを sys.path に追加
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from repositories.agency_inventory_repository import AgencyInventoryRepository
from database.models.agency_inventory import AgencyInventory


class TestAgencyInventoryRepository:
    @pytest.fixture
    def mock_session(self):
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def repository(self, mock_session):
        return AgencyInventoryRepository(mock_session)

    @pytest.fixture
    def sample_agency_inventory(self):
        return AgencyInventory(
            id=1,
            agency_name="テスト市",
            prefecture_code="13",
            municipality="テスト区",
            bid_page_url="https://example.com/bid",
            page_format="html",
            is_crawled=False
        )

    def test_upsert_insert_new_record(self, mock_session):
        """新規レコードの挿入をテスト"""
        # モックの設定: 既存レコードが見つからない場合
        mock_query = MagicMock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # リポジトリのインスタンス化
        repo = AgencyInventoryRepository(mock_session)
        
        # upsertの実行
        result = repo.upsert(
            agency_name="テスト市",
            prefecture_code="13",
            bid_page_url="https://example.com/bid",
            municipality="テスト区"
        )
        
        # 検証
        mock_session.query.assert_called_once_with(AgencyInventory)
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        
        # 戻り値がAgencyInventoryのインスタンスであることを確認
        assert isinstance(result, AgencyInventory)
        assert result.agency_name == "テスト市"
        assert result.prefecture_code == "13"
        assert result.municipality == "テスト区"
        assert result.bid_page_url == "https://example.com/bid"
        assert result.page_format == "html"  # bid_page_urlがあるのでhtml
        assert result.is_crawled == False

    def test_upsert_update_existing_record(self, mock_session, sample_agency_inventory):
        """既存レコードの更新をテスト"""
        # モックの設定: 既存レコードが見つかる場合
        mock_query = MagicMock()
        mock_query.filter_by.return_value.first.return_value = sample_agency_inventory
        mock_session.query.return_value = mock_query
        
        # リポジトリのインスタンス化
        repo = AgencyInventoryRepository(mock_session)
        
        # upsertの実行（新しいURLで更新）
        result = repo.upsert(
            agency_name="テスト市",
            prefecture_code="13",
            bid_page_url="https://example.com/new-bid",
            municipality="テスト区"
        )
        
        # 検証
        mock_session.query.assert_called_once_with(AgencyInventory)
        mock_session.add.assert_not_called()  # 既存レコードなのでaddは呼ばれない
        mock_session.commit.assert_called_once()
        
        # 既存レコードが更新されていることを確認
        assert result == sample_agency_inventory
        assert result.bid_page_url == "https://example.com/new-bid"
        assert result.is_crawled == False  # upsertではis_crawledをFalseにリセット

    def test_upsert_update_without_url(self, mock_session, sample_agency_inventory):
        """URLを指定しない場合の更新をテスト"""
        # 初期状態ではURLがあるものとする
        sample_agency_inventory.bid_page_url = "https://example.com/old-bid"
        
        # モックの設定
        mock_query = MagicMock()
        mock_query.filter_by.return_value.first.return_value = sample_agency_inventory
        mock_session.query.return_value = mock_query
        
        # リポジトリのインスタンス化
        repo = AgencyInventoryRepository(mock_session)
        
        # upsertの実行（URLを指定しない）
        result = repo.upsert(
            agency_name="テスト市",
            prefecture_code="13",
            municipality="テスト区"
            # bid_page_urlは指定しない
        )
        
        # 検証: URLは変更されないはず
        assert result == sample_agency_inventory
        assert result.bid_page_url == "https://example.com/old-bid"  # 元のURLのまま
        assert result.is_crawled == False

    def test_upsert_with_municipality_none(self, mock_session):
        """municipalityがNoneの場合のテスト"""
        mock_query = MagicMock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        repo = AgencyInventoryRepository(mock_session)
        
        result = repo.upsert(
            agency_name="テスト県",
            prefecture_code="13",
            bid_page_url="https://example.com/bid"
            # municipalityは指定しない（Noneになる）
        )
        
        mock_session.query.assert_called_once_with(AgencyInventory)
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        
        assert isinstance(result, AgencyInventory)
        assert result.agency_name == "テスト県"
        assert result.prefecture_code == "13"
        assert result.municipality is None
        assert result.bid_page_url == "https://example.com/bid"
        assert result.page_format == "html"
        assert result.is_crawled == False

    def test_list_uncrawled_with_results(self, mock_session):
        """未クロールレコードが存在する場合のlist_uncrawledテスト"""
        # モックの設定
        mock_agencies = [
            AgencyInventory(id=1, agency_name="市 A", prefecture_code="13", is_crawled=False),
            AgencyInventory(id=2, agency_name="市 B", prefecture_code="14", is_crawled=False),
        ]
        mock_query = MagicMock()
        mock_query.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = mock_agencies
        mock_session.query.return_value = mock_query
        
        repo = AgencyInventoryRepository(mock_session)
        
        result = repo.list_uncrawled(limit=10)
        
        mock_session.query.assert_called_once_with(AgencyInventory)
        mock_query.filter_by.assert_called_once_with(is_crawled=False)
        mock_query.filter_by.return_value.order_by.assert_called_once_with(AgencyInventory.id)
        mock_query.filter_by.return_value.order_by.return_value.limit.assert_called_once_with(10)
        
        assert len(result) == 2
        assert result[0].agency_name == "市 A"
        assert result[1].agency_name == "市 B"

    def test_list_uncrawled_empty_result(self, mock_session):
        """未クロールレコードが存在しない場合のlist_uncrawledテスト"""
        mock_query = MagicMock()
        mock_query.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_session.query.return_value = mock_query
        
        repo = AgencyInventoryRepository(mock_session)
        
        result = repo.list_uncrawled(limit=10)
        
        assert result == []
        mock_session.query.assert_called_once_with(AgencyInventory)
        mock_query.filter_by.assert_called_once_with(is_crawled=False)

    def test_list_uncrawled_default_limit(self, mock_session):
        """デフォルトリミット(100)のテスト"""
        mock_query = MagicMock()
        mock_query.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_session.query.return_value = mock_query
        
        repo = AgencyInventoryRepository(mock_session)
        
        repo.list_uncrawled()  # limitを指定しない
        
        mock_query.filter_by.return_value.order_by.return_value.limit.assert_called_once_with(100)

    def test_mark_crawled_success(self, mock_session, sample_agency_inventory):
        """mark_crawledの成功ケースをテスト"""
        # 初期状態では未クロール
        sample_agency_inventory.is_crawled = False
        
        # モックの設定
        mock_query = MagicMock()
        mock_query.filter_by.return_value.first.return_value = sample_agency_inventory
        mock_session.query.return_value = mock_query
        
        repo = AgencyInventoryRepository(mock_session)
        
        result = repo.mark_crawled(agency_id=1)
        
        mock_session.query.assert_called_once_with(AgencyInventory)
        mock_query.filter_by.assert_called_once_with(id=1)
        mock_session.commit.assert_called_once()
        
        assert result == sample_agency_inventory
        assert result.is_crawled == True

    def test_mark_crawled_not_found(self, mock_session):
        """指定IDのレコードが見つからない場合のmark_crawledテスト"""
        mock_query = MagicMock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        repo = AgencyInventoryRepository(mock_session)
        
        result = repo.mark_crawled(agency_id=999)  # 存在しないID
        
        mock_session.query.assert_called_once_with(AgencyInventory)
        mock_query.filter_by.assert_called_once_with(id=999)
        mock_session.commit.assert_not_called()  # レコードがないのでcommitは呼ばれない
        
        assert result is None

    def test_mark_crawled_already_crawled(self, mock_session, sample_agency_inventory):
        """既にクロール済みのレコードをmark_crawledするテスト"""
        sample_agency_inventory.is_crawled = True  # 既にクロール済み
        
        mock_query = MagicMock()
        mock_query.filter_by.return_value.first.return_value = sample_agency_inventory
        mock_session.query.return_value = mock_query
        
        repo = AgencyInventoryRepository(mock_session)
        
        result = repo.mark_crawled(agency_id=1)
        
        assert result == sample_agency_inventory
        assert result.is_crawled == True  # 変更なし
        mock_session.commit.assert_called_once()  # ただしcommitは呼ばれる