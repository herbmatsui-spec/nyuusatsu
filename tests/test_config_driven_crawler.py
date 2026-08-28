"""ConfigDrivenCrawler の基本テスト

- サンプル YAML 設定を利用し、`parse_list` が正しくリンク抽出できるかを検証
- `parse_detail` のプレースホルダーは文字列取得だけを確認
"""

import os
import tempfile
from pathlib import Path

import yaml

from crawler.config_driven_crawler import ConfigDrivenCrawler

sample_html_list = """
<html><body>
<a class=\"bid-link\" href=\"/detail/1\">案件1</a>
<a class=\"bid-link\" href=\"/detail/2\">案件2</a>
</body></html>
"""

sample_html_detail = """
<html><body><h1>案件詳細</h1><p>内容</p></body></html>
"""

def test_parse_list_and_detail(tmp_path: Path):
    yaml_path = tmp_path / "test.yaml"
    config = {
        "agency_name": "テスト県",
        "base_url": "https://example.com",
        "list_selector": "a.bid-link",
        "detail_selector": "div.detail",
        "pagination_selector": None,
        "page_format": "html",
        "parser": "html",
    }
    yaml_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    crawler = ConfigDrivenCrawler(str(yaml_path))
    links = crawler.parse_list(sample_html_list)
    assert len(links) == 2
    assert links[0] == "https://example.com/detail/1"
    assert links[1] == "https://example.com/detail/2"

    detail_text = crawler.parse_detail(sample_html_detail)
    assert "案件詳細" in detail_text
