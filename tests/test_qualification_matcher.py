"""
Tests for Qualification Matcher - Improved Coverage
"""
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

# Create a mock module for config.qualification_grades
mock_qualification_grades = MagicMock()
mock_qualification_grades.can_apply.return_value = True
mock_qualification_grades.normalize_grade.return_value = "A"
mock_qualification_grades.get_compatible_grades.return_value = ["A", "B"]

# Register the mock module in sys.modules before importing anything
sys.modules['config.qualification_grades'] = mock_qualification_grades


class TestQualificationMatcher:
    """QualificationMatcherクラスのテスト"""

    @pytest.fixture
    def matcher(self):
        """QualificationMatcherのインスタンスを提供"""
        # モックが登録された状態でインポート
        from services.qualification_matcher import QualificationMatcher, MatchResult
        self.MatchResult = MatchResult  # テストクラスで使えるように保存
        return QualificationMatcher(company_profile_id=1)

    @pytest.fixture
    def mock_db_session(self):
        """データベースセッションのモックを提供"""
        with patch('services.qualification_matcher.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value.__enter__.return_value = mock_session
            yield mock_session

    @pytest.fixture
    def mock_company_profile_repo(self):
        """CompanyProfileRepositoryのモックを提供"""
        with patch('services.qualification_matcher.CompanyProfileRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            yield mock_repo

    @pytest.fixture
    def mock_company_region_rank_repo(self):
        """CompanyRegionRankRepositoryのモックを提供"""
        with patch('services.qualification_matcher.CompanyRegionRankRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            yield mock_repo

    @pytest.fixture
    def mock_bid_repo(self):
        """BidRepositoryのモックを提供"""
        with patch('services.qualification_matcher.BidRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            yield mock_repo

    def test_init(self, matcher):
        """初期化のテスト"""
        assert matcher.company_profile_id == 1

    def test_load_company_profile_success(self, matcher, mock_db_session, mock_company_profile_repo, mock_company_region_rank_repo):
        """企業プロファイルのロード成功テスト"""
        # モックの設定
        mock_profile = Mock()
        mock_profile.id = 1
        mock_profile.name = "テスト会社"
        mock_profile.unified_qualification_grade = "A"
        mock_profile.industry_category = "IT"
        
        mock_region_ranks = [
            Mock(prefecture_code="13", region_rank="A"),  # 東京都
            Mock(prefecture_code="14", region_rank="B"),  # 神奈川県
        ]
        
        mock_company_profile_repo.get_by_id.return_value = mock_profile
        mock_company_region_rank_repo.list_by_company.return_value = mock_region_ranks
        
        # 実行
        result = matcher._load_company_profile()
        
        # 検証
        assert result is not None
        assert result["id"] == 1
        assert result["name"] == "テスト会社"
        assert result["unified_qualification_grade"] == "A"
        assert result["industry_category"] == "IT"
        assert result["region_ranks"]["13"] == "A"
        assert result["region_ranks"]["14"] == "B"
        
        # モックが正しく呼ばれたことを確認
        mock_company_profile_repo.get_by_id.assert_called_once_with(1)
        mock_company_region_rank_repo.list_by_company.assert_called_once_with(1)

    def test_load_company_profile_not_found(self, matcher, mock_db_session, mock_company_profile_repo):
        """企業プロファイルが見つからない場合のテスト"""
        mock_company_profile_repo.get_by_id.return_value = None
        
        result = matcher._load_company_profile()
        
        assert result is None
        mock_company_profile_repo.get_by_id.assert_called_once_with(1)

    def test_match_bid_company_not_found(self, matcher):
        """企業プロファイルが見つからない場合のmatch_bidテスト"""
        with patch.object(matcher, '_load_company_profile', return_value=None):
            result = matcher.match_bid(bid_id=1)
            
            assert result.bid_id == 1
            assert result.can_apply is False
            assert result.match_level == "none"
            assert result.score == 0.0
            assert "企業プロファイルが見つかりません" in result.messages

    def test_match_bid_bid_not_found(self, matcher, mock_db_session):
        """案件が見つからない場合のmatch_bidテスト"""
        # 企業プロファイルは見つかるようにモック
        with patch.object(matcher, '_load_company_profile', return_value={
            "id": 1,
            "name": "テスト会社",
            "unified_qualification_grade": "A",
            "industry_category": "IT",
            "region_ranks": {}
        }):
            # データベースセッションのモックを設定
            # まず、Bidの取得ではNoneを返す
            mock_db_session.get.return_value = None
            
            # 次に、資格タグのクエリでは空のリストを返す
            mock_query = Mock()
            mock_db_session.query.return_value = mock_query
            mock_query.join.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = []  # 空のリストを返す
            
            result = matcher.match_bid(bid_id=999)
            
            assert result.bid_id == 999
            assert result.can_apply is False
            assert result.match_level == "none"
            assert result.score == 0.0
            assert "案件が見つかりません" in result.messages

    def test_match_bid_full_match(self, matcher, mock_db_session, mock_company_profile_repo, mock_company_region_rank_repo, mock_bid_repo):
        """完全一致のケースのテスト"""
        # 企業プロファイルのモック
        mock_profile = Mock()
        mock_profile.id = 1
        mock_profile.name = "テスト会社"
        mock_profile.unified_qualification_grade = "A"
        mock_profile.industry_category = "IT"
        
        mock_region_ranks = [Mock(prefecture_code="13", region_rank="A")]  # 東京都
        
        mock_company_profile_repo.get_by_id.return_value = mock_profile
        mock_company_region_rank_repo.list_by_company.return_value = mock_region_ranks
        
        # Bidと関連データのモック
        mock_bid = Mock()
        mock_bid.id = 1
        
        mock_bid_qualification_tag = Mock()
        mock_bid_qualification_tag.required_grade = "A"
        mock_bid_qualification_tag.required_region = "13"
        
        mock_qualification_tag = Mock()
        mock_qualification_tag.grade_required = "A"
        mock_qualification_tag.region_required = "13"
        
        # データベースクエリのモック
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.join.return_value.filter.return_value.all.return_value = [
            (mock_bid_qualification_tag, mock_qualification_tag)
        ]
        mock_db_session.get.return_value = mock_bid
        
        # サービス依存のモック
        with patch('services.qualification_matcher.check_grade_requirement') as mock_check_grade, \
             patch('services.qualification_matcher.can_apply_in_region') as mock_can_apply_region:
            
            mock_check_grade.return_value = True  # グレードOK
            mock_can_apply_region.return_value = True  # 地域OK
            
            # 実行
            result = matcher.match_bid(bid_id=1)
            
            # 検証
            assert result.bid_id == 1
            assert result.can_apply is True
            assert result.match_level == "full"
            assert result.score == 1.0
            assert len(result.missing_qualifications) == 0
            assert len(result.missing_regions) == 0
            assert len(result.messages) == 0

    def test_match_bid_partial_match_grade_missing(self, matcher, mock_db_session, mock_company_profile_repo, mock_company_region_rank_repo, mock_bid_repo):
        """等級不足による部分一致のテスト"""
        # 企業プロファイルのモック（等級B）
        mock_profile = Mock()
        mock_profile.id = 1
        mock_profile.name = "テスト会社"
        mock_profile.unified_qualification_grade = "B"
        mock_profile.industry_category = "IT"
        
        mock_region_ranks = [Mock(prefecture_code="13", region_rank="A")]
        
        mock_company_profile_repo.get_by_id.return_value = mock_profile
        mock_company_region_rank_repo.list_by_company.return_value = mock_region_ranks
        
        # Bidと関連データのモック（等級Aが必要）
        mock_bid = Mock()
        mock_bid.id = 1
        
        mock_bid_qualification_tag = Mock()
        mock_bid_qualification_tag.required_grade = "A"
        mock_bid_qualification_tag.required_region = "13"
        
        mock_qualification_tag = Mock()
        mock_qualification_tag.grade_required = "A"
        mock_qualification_tag.region_required = "13"
        
        # データベースクエリのモック
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.join.return_value.filter.return_value.all.return_value = [
            (mock_bid_qualification_tag, mock_qualification_tag)
        ]
        mock_db_session.get.return_value = mock_bid
        
        # サービス依存のモック
        with patch('services.qualification_matcher.check_grade_requirement') as mock_check_grade, \
             patch('services.qualification_matcher.can_apply_in_region') as mock_can_apply_region:
            
            mock_check_grade.return_value = False  # グレードNG
            mock_can_apply_region.return_value = True  # 地域OK
            
            # 実行
            result = matcher.match_bid(bid_id=1)
            
            # 検証
            assert result.bid_id == 1
            assert result.can_apply is True  # 部分一致なので適用可能
            assert result.match_level == "partial"
            assert result.score == 0.5  # 1チェック中0.5点なので0.5
            assert "等級不足: A" in result.missing_qualifications
            assert len(result.missing_regions) == 0

    def test_match_bid_partial_match_region_missing(self, matcher, mock_db_session, mock_company_profile_repo, mock_company_region_rank_repo, mock_bid_repo):
        """地域不足による部分一致のテスト"""
        # 企業プロファイルのモック
        mock_profile = Mock()
        mock_profile.id = 1
        mock_profile.name = "テスト会社"
        mock_profile.unified_qualification_grade = "A"
        mock_profile.industry_category = "IT"
        
        mock_region_ranks = [Mock(prefecture_code="14", region_rank="B")]  # 神奈川県のみBランク
        
        mock_company_profile_repo.get_by_id.return_value = mock_profile
        mock_company_region_rank_repo.list_by_company.return_value = mock_region_ranks
        
        # Bidと関連データのモック（東京都が必要だが、会社は神奈川県しか持っていない）
        mock_bid = Mock()
        mock_bid.id = 1
        
        mock_bid_qualification_tag = Mock()
        mock_bid_qualification_tag.required_grade = "A"
        mock_bid_qualification_tag.required_region = "13"  # 東京都
        
        mock_qualification_tag = Mock()
        mock_qualification_tag.grade_required = "A"
        mock_qualification_tag.region_required = "13"
        
        # データベースクエリのモック
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.join.return_value.filter.return_value.all.return_value = [
            (mock_bid_qualification_tag, mock_qualification_tag)
        ]
        mock_db_session.get.return_value = mock_bid
        
        # サービス依存のモック
        with patch('services.qualification_matcher.check_grade_requirement') as mock_check_grade, \
             patch('services.qualification_matcher.can_apply_in_region') as mock_can_apply_region:
            
            mock_check_grade.return_value = True  # グレードOK
            mock_can_apply_region.return_value = False  # 地域NG
            
            # 実行
            result = matcher.match_bid(bid_id=1)
            
            # 検証
            assert result.bid_id == 1
            assert result.can_apply is True  # 部分一致なので適用可能
            assert result.match_level == "partial"
            assert result.score == 0.5  # 1チェック中0.5点なので0.5
            assert len(result.missing_qualifications) == 0
            assert "地域不足: 13" in result.missing_regions

    def test_match_bid_no_match(self, matcher, mock_db_session, mock_company_profile_repo, mock_company_region_rank_repo, mock_bid_repo):
        """不一致のケースのテスト"""
        # 企業プロファイルのモック（等級C、地域ランクなし）
        mock_profile = Mock()
        mock_profile.id = 1
        mock_profile.name = "テスト会社"
        mock_profile.unified_qualification_grade = "C"
        mock_profile.industry_category = "IT"
        
        mock_region_ranks = []
        
        mock_company_profile_repo.get_by_id.return_value = mock_profile
        mock_company_region_rank_repo.list_by_company.return_value = mock_region_ranks
        
        # Bidと関連データのモック（等級A、東京都が必要）
        mock_bid = Mock()
        mock_bid.id = 1
        
        mock_bid_qualification_tag = Mock()
        mock_bid_qualification_tag.required_grade = "A"
        mock_bid_qualification_tag.required_region = "13"
        
        mock_qualification_tag = Mock()
        mock_qualification_tag.grade_required = "A"
        mock_qualification_tag.region_required = "13"
        
        # データベースクエリのモック
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.join.return_value.filter.return_value.all.return_value = [
            (mock_bid_qualification_tag, mock_qualification_tag)
        ]
        mock_db_session.get.return_value = mock_bid
        
        # サービス依存のモック
        with patch('services.qualification_matcher.check_grade_requirement') as mock_check_grade, \
             patch('services.qualification_matcher.can_apply_in_region') as mock_can_apply_region:
            
            mock_check_grade.return_value = False  # グレードNG
            mock_can_apply_region.return_value = False  # 地域NG
            
            # 実行
            result = matcher.match_bid(bid_id=1)
            
            # 検証
            assert result.bid_id == 1
            assert result.can_apply is False
            assert result.match_level == "none"
            assert result.score == 0.0
            assert "等級不足: A" in result.missing_qualifications
            assert "地域不足: 13" in result.missing_regions

    def test_match_bids_empty_company(self, matcher):
        """企業プロファイルが見つからない場合のmatch_bidsテスト"""
        with patch.object(matcher, '_load_company_profile', return_value=None):
            result = matcher.match_bids()
            assert result == []

    def test_match_bids_with_filter(self, matcher, mock_db_session, mock_company_profile_repo, mock_company_region_rank_repo, mock_bid_repo):
        """フィルター付きmatch_bidsのテスト"""
        # 企業プロファイルは見つかるようにモック
        mock_profile = Mock()
        mock_profile.id = 1
        mock_profile.name = "テスト会社"
        mock_profile.unified_qualification_grade = "A"
        mock_profile.industry_category = "IT"
        
        mock_region_ranks = []
        
        mock_company_profile_repo.get_by_id.return_value = mock_profile
        mock_company_region_rank_repo.list_by_company.return_value = mock_region_ranks
        
        # Bidのリストをモック
        mock_bid1 = Mock()
        mock_bid1.id = 1
        mock_bid2 = Mock()
        mock_bid2.id = 2
        
        mock_bid_repo.list_all.return_value = [mock_bid1, mock_bid2]
        
        # match_bidのモック（1つ目は適用可能、2つ目は適用不可）
        with patch.object(matcher, 'match_bid') as mock_match_bid:
            mock_match_bid.side_effect = [
                Mock(bid_id=1, can_apply=True, match_level="full", score=1.0,
                     missing_qualifications=[], missing_regions=[], messages=[]),
                Mock(bid_id=2, can_apply=False, match_level="none", score=0.0,
                     missing_qualifications=["等級不足"], missing_regions=[], messages=[])
            ]
            
            # フィルターありで実行（my_qualifications_only=True）
            result = matcher.match_bids(filters={"my_qualifications_only": True})
            
            # 検証：適用可能な案件のみが返される
            assert len(result) == 1
            assert result[0].bid_id == 1
            assert result[0].can_apply is True
            
            # match_bidが2回呼ばれたことを確認
            assert mock_match_bid.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])