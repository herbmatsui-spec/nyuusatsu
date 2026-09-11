"""
Tests for Award Parser
"""
from crawler.parsers.award_parser import (
    parse_budget_amount,
    parse_contract_amount,
    calculate_award_rate,
    parse_date,
    parse_winner_name,
    extract_industry_from_text,
)
from datetime import datetime


def test_parse_budget_amount():
    """予算金額抽出のテスト"""
    assert parse_budget_amount("予定価格 12,345,678円") == 12345678
    assert parse_budget_amount("予定価格 12345678円") == 12345678
    assert parse_budget_amount("予定価格 12 345 678 円") == 12345678
    assert parse_budget_amount("予定価格\n12,345,678円") == 12345678
    assert parse_budget_amount("金額は12,345,678円です。") == 12345678
    assert parse_budget_amount("12,345,678") == 12345678  # 円なし
    assert parse_budget_amount("12,345,678円") == 12345678
    assert parse_budget_amount("円12,345,678") == 12345678  # 円が先
    assert parse_budget_amount("") is None
    assert parse_budget_amount("無し") is None
    assert parse_budget_amount("予定価格 円") is None  # 数字なし
    assert parse_budget_amount("予定価格 abcdefg円") is None  # 非数字


def test_parse_contract_amount():
    """契約金額抽出のテスト（予算金額と同じロジック）"""
    assert parse_contract_amount("落札価格 11,111,111円") == 11111111
    assert parse_contract_amount("契約金額 9999999円") == 9999999
    assert parse_contract_amount("") is None


def test_calculate_award_rate():
    """落札率計算のテスト"""
    assert calculate_award_rate(1000000, 800000) == 80.0
    assert calculate_award_rate(1000000, 1000000) == 100.0
    assert calculate_award_rate(1000000, 1200000) == 120.0
    assert calculate_award_rate(1000000, 1) == 0.0
    assert calculate_award_rate(1000000, 0) == 0.0
    assert calculate_award_rate(None, 1000000) is None
    assert calculate_award_rate(1000000, None) is None
    assert calculate_award_rate(None, None) is None
    assert calculate_award_rate(0, 1000000) is None  # バジェットゼロ
    assert calculate_award_rate(-100, 1000) is None  # 負のバジェット


def test_parse_date():
    """日付抽出のテスト"""
    # 西暦形式
    assert parse_date("2024/04/01") == datetime(2024, 4, 1)
    assert parse_date("2024-04-01") == datetime(2024, 4, 1)
    assert parse_date("2024年4月1日") == datetime(2024, 4, 1)
    assert parse_date("2024年 4月 1日") == datetime(2024, 4, 1)
    # 令和
    assert parse_date("令和6年4月1日") == datetime(2024, 4, 1)  # 令和6 = 2024
    assert parse_date("令和元年5月5日") == datetime(2019, 5, 5)  # 令和1 = 2019
    assert parse_date("令和 6 年 4 月 1 日") == datetime(2024, 4, 1)
    # 平成
    assert parse_date("平成31年4月1日") == datetime(2019, 4, 1)  # 平成31 = 2019
    assert parse_date("平成元年1月1日") == datetime(1989, 1, 1)  # 平成1 = 1989
    # エッジケース
    assert parse_date("") is None
    assert parse_date("不明") is None
    assert parse_date("2024/13/01") is None  # 無効月
    assert parse_date("2024/04/31") is None  # 無効日（4月31日は存在しない）


def test_parse_winner_name():
    """落札企業名抽出のテスト"""
    assert parse_winner_name("落札者：株式会社サンプル") == "株式会社サンプル"
    assert parse_winner_name("落札者：(株)サンプル") == "(株)サンプル"
    assert parse_winner_name("落札者：サンプル有限公司") == "サンプル有限公司"
    assert parse_winner_name("落札者：サンプル株式会社") == "サンプル株式会社"
    assert parse_winner_name("落札者：サンプル Corp.") == "サンプル Corp."
    assert parse_winner_name("落札者：サンプル Ltd") == "サンプル Ltd"
    assert parse_winner_name("落札者：サンプル") == "サンプル"
    assert parse_winner_name("株式会社サンプル") == "株式会社サンプル"
    assert parse_winner_name("(株)サンプル") == "(株)サンプル"
    assert parse_winner_name("サンプル有限公司") == "サンプル有限公司"
    assert parse_winner_name("") is None
    assert parse_winner_name("   ") is None  # 空白のみ
    assert parse_winner_name("落札者：") == ""  # 空文字列になる


def test_extract_industry_from_text():
    """業種抽出のテスト"""
    assert extract_industry_from_text("建設工事の入札") == "建設"
    assert extract_industry_from_text("建築プロジェクト") == "建設"
    assert extract_industry_from_text("土木工事") == "建設"
    assert extract_industry_from_text("舗装工事") == "建設"
    assert extract_industry_from_text("管工事") == "建設"
    assert extract_industry_from_text("造園") == "建設"
    assert extract_industry_from_text("システム開発") == "IT"
    assert extract_industry_from_text("ソフトウェア保守") == "IT"
    assert extract_industry_from_text("ネットワーク構築") == "IT"
    assert extract_industry_from_text("データセンター") == "IT"
    assert extract_industry_from_text("クラウドサービス") == "IT"
    assert extract_industry_from_text("経営コンサルティング") == "コンサル"
    assert extract_industry_from_text("市場調査") == "コンサル"
    assert extract_industry_from_text("事業計画") == "コンサル"
    assert extract_industry_from_text("基本設計") == "コンサル"
    assert extract_industry_from_text("事務用品購入") == "物品"
    assert extract_industry_from_text("コンピュータ機器") == "物品"
    assert extract_industry_from_text("設備導入") == "物品"
    assert extract_industry_from_text("清掃業務委託") == "委託"
    assert extract_industry_from_text("警備サービス") == "委託"
    assert extract_industry_from_text("食堂運営業務") == "委託"
    assert extract_industry_from_text("不明なプロジェクト") is None
    assert extract_industry_from_text("") is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])