"""クローラ雛形自動生成スクリプト

- コマンドライン引数 `--name` と `--url` を受け取り、YAML 設定とベーススケルトンファイルを生成
- 例: `python scripts/gen_crawler.py --name "示例市" --url "https://example.com/bids"`
"""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

try:
    import validators
except ImportError:
    validators = None

# テンプレート文字列
TEMPLATE_CONFIG = """agency_name: {name}
base_url: {url}
list_url: {url}/list.html
list_selector: "a.bid-link"
detail_selector: "div.detail"
pagination_selector: "a.next"
page_format: "html"
parser: "html"
"""

TEMPLATE_FETCHER = """# {name} クローラ

from urllib.parse import urljoin

from bs4 import BeautifulSoup
from crawler.base_crawler import BaseCrawler
from crawler.parsers.field_normalizer import TRANSFORM_MAP
from database.repositories import BidRepository
from database.session import get_session

class {class_name}(BaseCrawler):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_url = "{url}"
        self.list_selector = "{list_selector}"
        self.detail_selector = "{detail_selector}"
        self.detail_fields = {detail_fields}

    def parse_list(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for element in soup.select(self.list_selector):
            href = element.get("href")
            if href:
                links.append(urljoin(self.base_url, href))
        return links

    def parse_detail(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        detail = soup.select_one(self.detail_selector) if self.detail_selector else None
        if detail is None:
            return soup.get_text(separator="\\n", strip=True)

        result = {{}}
        for field_name, field_config in self.detail_fields.items():
            selector = field_config.get("selector")
            attr = field_config.get("attr", "text")
            transform_name = field_config.get("transform")
            multiple = field_config.get("multiple", False)
            elements = soup.select(selector) if multiple else ([element] if (element := soup.select_one(selector)) else [])
            values = []
            for element in elements:
                if attr == "text":
                    value = element.get_text(strip=True)
                else:
                    value = element.get(attr)
                transform = TRANSFORM_MAP.get(transform_name) if transform_name else None
                if transform and value is not None:
                    value = transform(value)
                values.append(value)
            result[field_name] = values if multiple else (values[0] if values else None)
        return result

    def save(self, items):
        with get_session() as session:
            repository = BidRepository(session)
            for item in items:
                repository.upsert_bid(item)
"""

def main():
    parser = argparse.ArgumentParser(description="Generate crawler config and skeleton")
    parser.add_argument("--name", required=True, help="Agency name (e.g., 示例市)")
    parser.add_argument("--url", required=True, help="Base URL for the agency")
    args = parser.parse_args()

    safe_name = args.name.replace(" ", "_")
    config_dir = Path("config")
    fetcher_dir = Path("crawler/agency_lists")
    config_dir.mkdir(parents=True, exist_ok=True)
    fetcher_dir.mkdir(parents=True, exist_ok=True)

    # Write YAML config
    config_path = config_dir / f"{safe_name.lower()}_crawler.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE_CONFIG.format(name=args.name, url=args.url))

    # Write fetcher skeleton
    class_name = f"{args.name.replace(' ', '')}Fetcher"
    fetcher_path = fetcher_dir / f"{safe_name.lower()}_fetcher.py"
    detail_fields = {
        "title": {"selector": "h1", "attr": "text"},
        "budget": {"selector": ".budget", "attr": "text"},
        "deadline": {"selector": ".deadline", "attr": "text"},
    }
    with open(fetcher_path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE_FETCHER.format(
            name=args.name,
            class_name=class_name,
            url=args.url,
            list_selector="a.bid-link",
            detail_selector="div.detail",
            detail_fields=repr(detail_fields),
        ))

    print(f"Generated config: {config_path}")
    print(f"Generated fetcher: {fetcher_path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
