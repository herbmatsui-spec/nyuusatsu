"""優先度スコア計算ユーティリティ

- `calc_score` は機関数と業種一致度から 0-100 のスコアを算出
- `rank_prefectures` はスコア降順でリストを返す
"""

from typing import List, Tuple


def calc_score(agency_count: int, industry_match: float) -> float:
    """機関数と業種一致度からスコアを計算。
    agency_count: 発注機関数（整数）
    industry_match: 0.0~1.0 の一致率
    返り値: 0.0~100.0 のスコア
    """
    # 重みは業務的に決定済み: 機関数 0.6, 業種一致度 0.4
    # スケールを 100 点満点に正規化
    normalized_agency = min(agency_count, 100)  # 上限 100 でクリップ
    score = (normalized_agency * 0.6) + (industry_match * 100 * 0.4)
    return round(score, 2)


def rank_prefectures(data: List[Tuple[str, int, float]]) -> List[Tuple[str, float]]:
    """(pref_code, agency_count, industry_match) のリストをスコア降順に並べ替える。
    返り値は (pref_code, score) のタプルリスト。
    """
    scored = [(pref, calc_score(cnt, match)) for pref, cnt, match in data]
    # 降順ソート
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
