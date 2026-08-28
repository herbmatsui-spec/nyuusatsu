from typing import Dict, Optional, Any
from dataclasses import dataclass
from config import CrawlerConfig
from config.award_urls import AWARD_URL_PATTERNS

@dataclass
class CrawlTarget:
    """
    クローリング対象の統合設定。
    CrawlerConfig の汎用設定と award_urls.py の個別URL定義を統合して保持する。
    """
    agency_key: str
    name: str
    list_url: str
    detail_pattern: str
    user_agent: str
    timeout: int
    parallel_downloads: int

def get_crawl_config_for_agency(agency_key: str, base_config: CrawlerConfig) -> Optional[CrawlTarget]:
    """
    指定された機関（agency_key）に対する統合的なクロール設定を生成する。
    award_urls.py に定義がない場合は None を返す。
    """
    url_info = AWARD_URL_PATTERNS.get(agency_key)
    if not url_info:
        return None

    return CrawlTarget(
        agency_key=agency_key,
        name=url_info.get("name", "不明"),
        list_url=url_info.get("list_url", ""),
        detail_pattern=url_info.get("detail_pattern", ""),
        user_agent=base_config.user_agent,
        timeout=base_config.request_timeout,
        parallel_downloads=base_config.parallel_downloads
    )

def get_all_crawl_targets(base_config: CrawlerConfig) -> Dict[str, CrawlTarget]:
    """
    すべての定義済み機関に対する CrawlTarget の辞書を生成する。
    """
    targets = {}
    for key in AWARD_URL_PATTERNS.keys():
        target = get_crawl_config_for_agency(key, base_config)
        if target:
            targets[key] = target
    return targets
