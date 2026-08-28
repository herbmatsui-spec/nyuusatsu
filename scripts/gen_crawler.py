"""クローラ雛形自動生成スクリプト

- コマンドライン引数 `--name` と `--url` を受け取り、YAML 設定とベーススケルトンファイルを生成
- 例: `python scripts/gen_crawler.py --name "示例市" --url "https://example.com/bids"`
"""

import argparse
import sys
from pathlib import Path

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

TEMPLATE_FETCHER = """{name} クローラ

- 自動生成された雛形です。必要に応じて実装を追加してください。

from crawler.base_crawler import BaseCrawler

class {class_name}(BaseCrawler):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_url = "{url}"

    def parse_list(self, html: str):
        # TODO: implement list parsing (BeautifulSoup)
        return []

    def parse_detail(self, html: str):
        # TODO: implement detail parsing
        return {}

    def save(self, items):
        # TODO: implement persistence logic
        print("[SAVE]", items)
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
    with open(fetcher_path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE_FETCHER.format(name=args.name, class_name=class_name, url=args.url))

    print(f"Generated config: {config_path}")
    print(f"Generated fetcher: {fetcher_path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
