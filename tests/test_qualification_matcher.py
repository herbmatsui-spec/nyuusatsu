"""
Tests for Qualification Matcher (Phase4 Step38)
"""
import pytest
from services.qualification_matcher import MatchResult


class TestMatchResult:
    def test_full_match(self):
        result = MatchResult(
            bid_id=1,
            can_apply=True,
            match_level="full",
            score=1.0,
        )
        assert result.can_apply is True
        assert result.match_level == "full"
        assert result.score == 1.0
        assert len(result.missing_qualifications) == 0

    def test_partial_match(self):
        result = MatchResult(
            bid_id=2,
            can_apply=True,
            match_level="partial",
            missing_qualifications=["等級不足: B"],
            score=0.5,
        )
        assert result.can_apply is True
        assert result.match_level == "partial"
        assert result.score == 0.5
        assert "等級不足" in result.missing_qualifications[0]

    def test_no_match(self):
        result = MatchResult(
            bid_id=3,
            can_apply=False,
            match_level="none",
            missing_qualifications=["等級不足: A", "地域不足: 東京都"],
            score=0.0,
        )
        assert result.can_apply is False
        assert result.match_level == "none"
        assert result.score == 0.0
        assert len(result.missing_qualifications) == 2


class TestMatchResultDefaults:
    def test_defaults(self):
        result = MatchResult(bid_id=1, can_apply=True, match_level="full")
        assert result.missing_qualifications == []
        assert result.missing_regions == []
        assert result.score == 0.0
        assert result.messages == []