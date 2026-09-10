"""日付フィルタリングユーティリティ

アイテムリストを日付範囲でフィルタリングする共通関数
"""
from typing import List, Any, Optional, Callable
from datetime import date


def filter_by_date_range(
    items: List[Any],
    start_date: Optional[date],
    end_date: Optional[date],
    date_extractor: Callable[[Any], Optional[date]],
) -> List[Any]:
    """アイテムリストを日付範囲でフィルタリング

    Args:
        items: フィルタ対象のアイテムリスト
        start_date: 開始日（この日以降を含む）
        end_date: 終了日（この日以前を含む）
        date_extractor: アイテムから date オブジェクトを抽出する関数

    Returns:
        範囲内のアイテムのみを含むリスト
    """
    if not start_date and not end_date:
        return items

    filtered = []
    for item in items:
        try:
            item_date = date_extractor(item)
            if item_date is None:
                # 日付が取得できない場合は含める（保守的）
                filtered.append(item)
                continue

            if start_date and item_date < start_date:
                continue
            if end_date and item_date > end_date:
                continue

            filtered.append(item)
        except Exception:
            # パースエラー時は含める（保守的）
            filtered.append(item)

    return filtered


def should_stop_early(
    items: List[Any],
    start_date: date,
    date_extractor: Callable[[Any], Optional[date]],
) -> bool:
    """現在のページのアイテムがすべて start_date より古いか判定

    ページネーション時の早期終了判定用。
    アイテムが新しい順（降順）で並んでいる前提。

    Args:
        items: 判定対象のアイテムリスト
        start_date: 基準日
        date_extractor: アイテムから date オブジェクトを抽出する関数

    Returns:
        すべてのアイテムが start_date より古い場合 True
    """
    if not items:
        return False

    for item in items:
        try:
            item_date = date_extractor(item)
            if item_date is None:
                # 日付不明のアイテムがある場合は継続
                return False
            if item_date >= start_date:
                # 範囲内のアイテムがあれば継続
                return False
        except Exception:
            # パースエラー時は継続
            return False

    # すべてのアイテムが start_date より古い
    return True