# バックフィル実装 - Phase 0 調査結果サマリー (Steps 1-6)

## Step 1: 既存クローラの日付範囲対応確認 ✅

**結果: 対応なし**

| クローラー | 現状 | 必要な追加 |
|-----------|------|-----------|
| `BaseCrawler` | `__init__` に retry/timeout/backoff のみ | `start_date`, `end_date` パラメータ追加、`crawl_range()` メソッド実装 |
| `GenericCrawler` | `parser_type`, `delay`, `categories`, `priority_levels` | `crawl_site()` に `start_date`, `end_date` 引数追加 |
| `GEPSCrawler` | `delay`, `timeout` のみ | `search_bids()` に `start_date`, `end_date` パラメータ追加、GEPS検索フォームの日付項目へ設定 |

**結論**: 全クローラーに日付範囲指定機能を新規実装する必要あり

---

## Step 2: 既存Bidモデルの日付フィールド確認 ✅

**`database/models/_generated.py` の `Bid` クラス (lines 127-152)**

| フィールド名 | 型 | Nullable | 用途 |
|-------------|----|----------|------|
| `analyzed_at` | DateTime | False | 解析実行日時 |
| `created_at` | DateTime | False | レコード作成日時 |
| `updated_at` | DateTime | False | レコード更新日時 |
| `awarded_date` | DateTime | True | 落札日 |
| `announcement_date` | DateTime | True | **公告日（バックフィルのフィルタ基準として最重要）** |
| `updated_date` | DateTime | True | 更新日（詳細不明） |

**結論**: `announcement_date` をバックフィルの日付フィルタ基準として使用可能。`created_at` は取得日時なのでフィルタには不向き。

---

## Step 3: 既存CrawlConfigの頻度設定確認 ✅

**`database/models/_generated.py` の `CrawlConfig` クラス (lines 203-212)**

| フィールド名 | 型 | Nullable | 備考 |
|-------------|----|----------|------|
| `frequency` | String | False | 例: "daily", "weekly", "monthly" 等の文字列で管理 |

**結論**: 頻度設定は文字列で管理されている。バックフィル用には別途ジョブ管理テーブルが必要。

---

## Step 4: 重複判定キーの確認 ✅

**`services/bid_storage_service.py` (lines 14-17, 22-41)**

```python
# source_urlで重複チェック
existing_bid = db.query(Bid).filter(
    Bid.source_url == bid_data.get("source_url")
).first()

if existing_bid:
    # upsert処理：既存レコードを更新
    for key, value in update_data.items():
        if value is not None:
            setattr(existing_bid, key, value)
```

**結論**: `source_url` をユニークキーとして upsert（INSERT OR UPDATE）を実装済み。バックフィルでも同ロジックを流用可能。

---

## Step 5: 対象発注機関の抽出条件整理 ✅

### 候補1: AgencyInventory (新規テーブル)
**`database/models/agency_inventory.py`**
```python
is_crawled = Column(Boolean, default=False)  # クロール済みフラグ
crawler_config_id = Column(Integer, ForeignKey("crawl_configs.id"))  # 設定紐付け
```

### 候補2: BidSource (既存テーブル)  
**`database/models/_generated.py` - BidSource (lines 99-116)**
```python
is_active = Column(Boolean, nullable=False)  # 有効フラグ
last_crawled_at = Column(DateTime)  # 最終クロール日時
```

### 候補3: Agency (基本マスタ)
```python
category_id = Column(Integer, ForeignKey('agency_categories.id'))  # カテゴリ
priority_level = Column(Integer)  # 優先度
system_type = Column(Text)  # システム種別
```

**推奨抽出条件**:
```sql
-- メイン: クロール実績のある機関
SELECT * FROM agency_inventory WHERE is_crawled = true

-- または: アクティブなクロール設定がある機関
SELECT * FROM bid_sources WHERE is_active = true

-- カテゴリ・優先度でフィルタ
JOIN agencies ON ... WHERE agencies.category_id IN (1,2,3) AND agencies.priority_level >= 2
```

---

## Step 6: 過去データの取得可能範囲調査 ✅

**現状**: 自動調査機能なし。手動確認が必要。

**想定される制限**:
| サイト種別 | 想定取得可能範囲 | 備考 |
|-----------|----------------|------|
| GEPS | 過去数年 | 検索フォームに日付範囲指定あり |
| 都道府県サイト | 過去1-2年 | ページネーションの深度制限あり |
| 市区町村サイト | 過去1年程度 | 古いデータはアーカイブ移動の可能性 |
| 外郭団体 | サイトによる | 認証必要な場合あり |

**結論**: 実装時に各サイトで実際に遡及テストを実施し、取得可能範囲を動的に判定する仕組みが必要

---

## Phase 0 総合判定

| 項目 | 状況 | 対応方針 |
|------|------|---------|
| 日付範囲クロール | 未実装 | Phase 2 で全クローラーに実装 |
| フィルタ用日付フィールド | `announcement_date` 存在 | これを基準に使用 |
| 重複排除 | `source_url` で実装済み | 既存ロジック流用 |
| 対象機関抽出 | AgencyInventory/BidSource 利用可能 | 両方併用で対象特定 |
| 取得可能範囲 | 要実測 | 実装後スモークテストで確認 |

**次のアクション**: Phase 1 (Steps 7-18) - BackfillJobモデル作成・マイグレーションへ着手