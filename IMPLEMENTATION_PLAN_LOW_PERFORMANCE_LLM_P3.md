# 低性能LLM向け実装計画書 P3: クローラー非同期化とセレクター改善 (ステップ 49-72)

## 概要
低性能なLLMでも実装可能なように、クローラーの非同期化、セレクターの外部化・堅牢化、スケジューラの改善を極小ステップに分割しました。各ステップは5-10行程度の変更で完了します。

---

## ステップ 49-54: crawler/base_crawler.py の非同期化準備

### ステップ 49: ファイルのバックアップ作成
- `crawler/base_crawler.py` を `crawler/base_crawler.py.backup` にコピーする

### ステップ 50: 非同期関連インポートの追加準備
- ファイル冒頭のインポートブロックに `# 将来的に非同期機能を追加するためのインポート準備` コメントを追加
- `import asyncio` の行の上に `# TODO: 非同期処理のために追加` コメントを追加（実際はまだ追加しない）
- `from typing import List, Any, Optional` の行の下に `# 将来的に追加する型注釈のためのスペース` コメントを追加

### ステップ 51: 抽象メソッドの非同期版のプレースホルダー追加
- `parse_list` メソッドの定義の上に `# 将来的に非同期版も追加予定: async def parse_list_async(self, html: str) -> List[Any]:` コメントを追加
- `parse_detail` メソッドの定義の上に `# 将来的に非同期版も追加予定: async def parse_detail_async(self, html: str) -> Any:` コメントを追加

### ステップ 52: コンストラクターの非同期パラメータ準備
- `__init__` メソッドのパラメータリストの末尾に `, use_async: bool = False` を追加（ただし、実際にはまだ使用しない）
- コンストラクター内部に `self.use_async = use_async` を追加（ただし、実際にはまだ使用しない）
- `self.use_async = use_async` の行の上に `# 将来的に非同期モードを切り替えるフラグ` コメントを追加

### ステップ 53: fetch メソッドの非同期版の準備
- `fetch` メソッドの定義の上に `# 将来的に非同期版も追加予定: async def async_fetch(self, url: str) -> str:` コメントを追加
- `fetch` メソッド内部の最初の行に `# TODO: 将来的にここを非同期HTTPクライアントに置き換える` コメントを追加

### ステップ 54: crawl_range メソッドの非同期版の準備
- `crawl_range` メソッドの定義の上に `# 将来的に非同期版も追加予定: async def async_crawl_range(...)` コメントを追加
- `crawl_range` メソッド内部の最初の行に `# TODO: 将来的にここを非同期バージョンに置き換える` コメントを追加

---

## ステップ 55-60: 基本的な非同期インフラストラクチャーの追加

### ステップ 55: 実際にasyncioインポートを追加（準備完了後）
- ファイル冒頭のインポートブロックで、`import asyncio` の行の `# TODO: 非同期処理のために追加` コメントを削除し、実際にインポートを有効にする
- 他のインポートと同様の形式で配置する

### ステップ 56: 基本的な非同期ヘルパーメソッドのスタブ追加
- ファイル末尾（すべてのメソッドの後、`if __name__ == "__main__":` ブロックの前）に以下を追加:
```python
    async def async_fetch_stub(self, url: str) -> str:
        """将来的に実装される非同期フェッチのスタブ"""
        # TODO: 実際の非同期HTTPクライアント実装
        return await asyncio.sleep(0, result="")  # プレースホルダー
```

### ステップ 57: コンストラクターのuse_asyncフラグを実際に使用する準備
- `__init__` メソッド内部の `self.use_async = use_async` の行の上に `# 実際にフラグを設定` コメントを追加
- コンストラクター内部の最後に `if self.use_async: logger.info(f"Async mode enabled for {self.__class__.__name__}")` を追加

### ステップ 58: logger インポートの確認と非同期ロギング用コメント追加
- ファイル冒頭に `import logging` があることを確認
- `logger = logging.getLogger(__name__)` があることを確認
- ファイル冒頭のインポートブロックの下に `# 将来的に非同期ロガーも検討` コメントを追加

### ステップ 59: 非同期コンテキストマネージャーの準備コメント追加
- クラス定義の直前に `# 将来的に非同期コンテキストマネージャーも検討: async def __aenter__(self) / async def __aexit__(self)` コメントを追加

### ステップ 60: 基本的な非同期テスト用スタブ追加
- ファイル末尾の `if __name__ == "__main__":` ブロック内に以下を追加:
```python
    # 非同期機能の非常に基本的なテスト
    import asyncio
    async def test_async():
        crawler = cls()  # 抽象クラスなので実際には子クラスでテスト
        print("Async test placeholder")
    # asyncio.run(test_async())  # 現在はコメントアウト
```

---

## ステップ 61-66: crawler/geps/award_crawler.py のセレクター改善準備

### ステップ 61: ファイルのバックアップ作成
- `crawler/geps/award_crawler.py` を `crawler/geps/award_crawler.py.backup` にコピーする

### ステップ 62: YAML関連インポートの準備コメント追加
- ファイル冒頭のインポートブロックの下に `# 将来的にYAMLからセッターを読み込むためのインポート準備` コメントを追加
- インポートブロックの下に `# import yaml  # 将来的に追加` コメントを追加（現在はコメントアウト状態）

### ステップ 63: 定数・設定関連の準備コメント追加
- クラス定義の直前に `# 将来的にセッター設定を外部ファイルから読み込む` コメントを追加
- クラス定義の直後に `# SELECTORS_CONFIG_PATH = "crawler/config/geps_selectors.yaml"` コメントを追加（現在はコメントアウト状態）

### ステップ 64: プレースホルダーセレクターの特定とコメント追加
- `DATE_RE = re.compile(r"(19|20)\d{1,2}[/\-年]\s*\d{1,2}[/\-月]\s*\d{1,2}日?")` の行の上に `# 日付抽出用正規表現` コメントを追加
- `rows = soup.select("table tr")` の行の上に `# テーブル行を選択 - 将来的に設定可能なセレクターに置き換える` コメントを追加
- `title_el = row.find("a")` の行の上に `# タイトルリンクを取得 - 将来的に設定可能なセレクターに置き換える` コメントを追加
- `pdf_link = row.find("a", href=lambda x: x and x.lower().endswith(".pdf"))` の行の上に `# PDFリンクを取得 - 将来的に設定可能なセレクターに置き換える` コメントを追加

### ステップ 65: 設定可能なセレクターのための準備メソッドスタブ追加
- クラス定義内部、他のメソッドの間に以下を追加:
```python
    def _get_configurable_selector(self, selector_name: str, default: str) -> str:
        """将来的に設定ファイルからセレクターを取得する（現在はデフォルト値を返す）"""
        # TODO: 実際にはYAMLファイルから読み込む
        return default
```

### ステップ 66: プレースホルダーセレクターを設定可能なメソッド呼び出しに置き換える準備
- `rows = soup.select("table tr")` の行をコメントアウトし、代わりに以下を追加:
```python
        # table_selector = self._get_configurable_selector("table_row", "table tr")
        # rows = soup.select(table_selector)
        rows = soup.select("table tr")  # 一時的に元のコードを維持
```
- 同様に他のセレクター使用部分についても準備作業を行う（ただし実際の置き換えは次のステップで）

---

## ステップ 67-72: 基本的なインフラストラクチャーとテスト改善

### ステップ 67: 設定ディレクトリの作成準備
- プロジェクトのルートディレクトリに `crawler/config/` ディレクトリを作成するための準備として、`docs/` ディレクトリ内に `TODO_create_config_dir.md` ファイルを作成し、以下を追加:
```
# TODO: crawler/config/ ディレクトリを作成し、以下のファイルを配置する
# - geps_selectors.yaml
# - quality_thresholds.yaml
```

### ステップ 68: 基本的なYAML設定ファイルの雛形作成
- `docs/` ディレクトリ内に `geps_selectors.yaml.template` ファイルを作成し、以下を追加:
```yaml
selectors_version: "2026.09"
pages:
  search_form:
    query: "input[name='query']"
    start_date: "input[name='startDate']"
    end_date: "input[name='endDate']"
    submit: "button[type='submit']"
  search_results:
    item: "tr.result-item"
    title: "td.title a"
    organization: "td.organization"
    budget: "td.budget"
    deadline: "td.deadline"
  detail:
    title: "h1.detail-title"
    organization: "div.organization-name"
    budget: "span.budget-amount"
    deadline: "span.deadline-date"
```

### ステップ 69: 品質閾値設定ファイルの雛形作成
- `docs/` ディレクトリ内に `quality_thresholds.yaml.template` ファイルを作成し、以下を追加:
```yaml
missing_field_rate:
  warning: 5.0
  critical: 15.0
duplicate_rate:
  warning: 1.0
  critical: 5.0
acquisition_delay_median:
  warning: 60.0  # 分
  critical: 1440.0  # 分 (24時間)
coverage_rate:
  warning: 95.0
  critical: 90.0
  lower_is_worse: true
coverage_municipality_rate:
  warning: 80.0
  critical: 70.0
  lower_is_worse: true
geps_crawler_success_rate:
  warning: 95.0
  critical: 90.0
  lower_is_worse: true
geps_selector_match_rate:
  warning: 80.0
  critical: 70.0
  lower_is_worse: true
```

### ステップ 70: 基本的なテストファイルの雛形作成（品質メトリクス）
- `tests/unit/` ディレクトリ内に `test_quality_metrics_basic.py` ファイルを作成し、以下を追加:
```python
"""品質メトリクスサービスの基本テスト"""
def test_import():
    """インポートできるかテスト"""
    from services.quality_metrics_service import QualityMetricsService
    assert QualityMetricsService is not None
```

### ステップ 71: 基本的なテストファイルの雛形作成（クローラー）
- `tests/unit/` ディレクトリ内に `test_crawler_basic.py` ファイルを作成し、以下を追加:
```python
"""クローラー基底クラスの基本テスト"""
def test_import():
    """インポートできるかテスト"""
    from crawler.base_crawler import BaseCrawler
    assert BaseCrawler is not None
```

### ステップ 72: 実装完了確認用チェックリスト作成
- プロジェクトのルートディレクトリに `IMPLEMENTATION_CHECKP_LLM.md` ファイルを作成し、以下を追加:
```markdown
# 低性能LLM向け実装完了チェックリスト

## P1: DB統合 (ステップ 1-24)
- [ ] db_manager.py がSQLAlchemyモデルに移行済み
- [ ] CrawlHistory, CrawledUrl, Settings モデルが定義済み
- [ ] 基本的なエンジンとセッション管理が実装済み

## P2: 品質メトリクス改善 (ステップ 25-48)
- [ ] quality_metrics_service.py にコメントが追加済み
- [ ] 各メソッドのロジックが理解しやすい状態
- [ ] acquisition_delay_median 等の複雑関数に最適化の予定が示されている

## P3: クローラー改善 (ステップ 49-72)
- [ ] base_crawler.py に非同期化の準備が完了
- [ ] award_crawler.py にセッター外部化の準備が完了
- [ ] 設定ファイルの雛形が docs/ ディレクトリに作成済み
- [ ] 基本的なテストファイルが作成済み

## 次のステップ
- 実際の設定ファイルを crawler/config/ にコピー
- 段階的に非同期機能を実装
- 段階的に設定可能なセッターを実装
- パフォーマンス最適化（特に acquisition_delay_median）を実装
```