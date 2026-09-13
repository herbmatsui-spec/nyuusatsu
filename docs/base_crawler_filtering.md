# BaseCrawler カテゴリ・優先度フィルタリング

`BaseCrawler` は `categories` と `priority_levels` パラメータを受け取り、
データベースから対象となる agency をフィルタリングできます。

## パラメータ

| パラメータ | 型 | 説明 |
|---|---|---|
| `categories` | `Optional[List[str]]` | `agency_categories.name` でフィルタ。`None` ならすべて対象。 |
| `priority_levels` | `Optional[List[Union[str, int]]]` | `agency.priority_level` でフィルタ。日本語 `'高'`/`'中'`/`'低'` または整数 `0`/`1`/`2` 指定。`None` ならすべて対象。 |
| `delay` | `float` | クローリング間遅延秒数。 |

## 使用例

### 都道府県のみクロール

```python
from crawler.generic_crawler import GenericCrawler
from database.session import SessionLocal

db = SessionLocal()
try:
    crawler = GenericCrawler(
        categories=["都道府県"],
        delay=3.0,
    )
    agencies = crawler._get_target_agencies(db)
    print(f"対象都道府県機関数: {len(agencies)}")
    for a in agencies:
        print(f"  - {a.name} (priority_level={a.priority_level})")
finally:
    db.close()
```

### 高優先度のみクロール

```python
from crawler.generic_crawler import GenericCrawler
from database.session import SessionLocal

db = SessionLocal()
try:
    crawler = GenericCrawler(
        priority_levels=["高"],
    )
    agencies = crawler._get_target_agencies(db)
    print(f"高優先度機関数: {len(agencies)}")
finally:
    db.close()
```

### 複合フィルタ

```python
crawler = GenericCrawler(
    categories=["都道府県", "市区町村"],
    priority_levels=["高", "中"],  # 整数でも可: [0, 1]
)
agencies = crawler._get_target_agencies(db)
```

## 優先度マッピング

| 文字列 | 整数値 |
|---|---|
| `'高'` | `0` |
| `'中'` | `1` |
| `'低'` | `2` |

## 互換性

`categories` と `priority_levels` はデフォルトで `None` です。
`None` の場合はフィルタリングを行わず、全件が対象となります。
既存の呼び出しコードは変更不要です。
