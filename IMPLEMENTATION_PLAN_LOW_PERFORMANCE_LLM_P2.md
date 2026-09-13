# 低性能LLM向け実装計画書 P2: 品質メトリクス改善とクローラ基盤 (ステップ 25-48)

## 概要
低性能なLLMでも実装可能なように、品質メトリクスの改善とクローラ基盤の非同期化を極小ステップに分割しました。各ステップは5-10行程度の変更で完了します。

---

## ステップ 25-30: quality_metrics_service.py の基盤整備

### ステップ 25: ファイルのバックアップ作成
- `services/quality_metrics_service.py` を `services/quality_metrics_service.py.backup` にコピーする

### ステップ 26: SQLAlchemy インポート追加（既存がある場合は確認）
- ファイル冒付近に `from sqlalchemy.orm import Session` があることを確認
- 無い場合は追加
- ファイル冒付近に `from sqlalchemy import func, and_` があることを確認
- 無い場合は追加

### ステップ 27: 必須フィールドリストのコメント追加
- `REQUIRED_FIELDS` の定義の上に `# 必須フィールドリスト - 将来的に設定ファイルから読み込む` コメントを追加

### ステップ 28: コンストラクターの引数確認
- `__init__` メソッドの `session: Session` 型注釈があることを確認
- 無い場合は追加
- `date_start` と `date_end` の型注釈 `datetime | None` を確認
- 無い場合は追加

### ステップ 29: _bid_query メソッドの名前変更準備
- メソッド名の上に `# 将来的にプライベートメソッドとして残す` コメントを追加
- メソッド名の前にアンダースコアが付いていることを確認（既に付いているはず）

### ステップ 30: count_missing_fields メソッドの構造確認
- メソッドの最初に `# タイプヒント: -> dict[ str, int ]` コメントを追加（将来のため）
- メソッドが `total = self._bid_query().count()` から始まっていることを確認

---

## ステップ 31-36: 欠損フィールド関数の段階的改善

### ステンプレート

### ステップ 31: count_missing_fields メソッドのループ部分にコメント追加
- `for field in REQUIRED_FIELDS:` の行の上に `# 各フィールドの欠損をチェック` コメントを追加

### ステップ 32: count_missing_fields メソッドの属性チェック部分にコメント追加
- `if hasattr(Bid, field):` の行の上に `# Bid モデルにフィールドが存在するかチェック` コメントを追加

### スteps 33: count_missing_fields メソッドのカウント取得部分にコメント追加
- `cnt = self._bid_query().filter(getattr(Bid, field) == None).count()` の行の上に `# NULL 値の件数を取得` コメントを追加

### ステップ 34: count_missing_fields メソッドの結果格納部分にコメント追加
- `if cnt:` の行の上に `# 欠損がある場合のみ結果に追加` コメントを追加
- `missing[field] = cnt` の行の上に `# フィールド名をキーとして欠損件数を格納` コメントを追加

### ステップ 35: missing_field_rate メソッドの構造確認
- メソッドが `total = self._bid_query().count()` から始まっていることを確認
- メソッドの最後に `return 0.0` があることを確認（総数が0の場合）

### ステップ 36: missing_field_rate メソッドの計算ロジックにコメント追加
- `total_missing = sum(missing_counts.values())` の行の上に `# すべてのフィールドの欠損合計を計算` コメントを追加
- `avg_missing_per_field = total_missing / len(REQUIRED_FIELDS)` の行の上に `# フィールドあたりの平均欠損数を計算` コメントを追加
- 最後の返却行の上に `# パーセンテージに変換して小数点2位で丸め` コメントを追加

---

## ステップ 37-42: 重複関数の段階的改善テンプレート

### ステップ 37: count_duplicates メソッドの構造確認
- メソッドが `dup_sub = ...` から始まっていることを確認
- メソッドが `dup_count = ...` で終わっていることを確認

### ステップ 38: count_duplicates メソッドのサブクエリー部分にコメント追加
- `dup_sub = self._bid_query().with_entities(Bid.source_url).group_by(Bid.source_url).having(` の行の上に `# source_urlでグループ化し、2件以上のレコードを抽出` コメントを追加
- `func.count(Bid.id) > 1` の行の上に `# 重複条件: 同じsource_urlが2件以上` コメントを追加

### ステップ 39: count_duplicates メソッドのメインクエリー部分にコメント追加
- `dup_count = self._bid_query().filter(Bid.source_url.in_(self.session.query(dup_sub.c.source_url))).count()` の行の上に `# 重複しているsource_urlを持つレコードをカウント` コメントを追加

### ステップ 40: duplicate_rate メソッドの構造確認
- メソッドが `total = self._bid_query().count()` から始まっていることを確認
- メソッドが `dup_count = self.count_duplicates()` で続き、`return 0.0` で終わっていることを確認

### ステップ 41: duplicate_rate メソッドの計算ロジックにコメント追加
- `return round((dup_count / total) * 100, 2)` の行の上に `# 重複率をパーセンテージで計算し、小数点2位で丸め` コメントを追加

### ステップ 42: 複雑な関数への着手前の準備作業
- `acquisition_delay_median` メソッドの上に `# TODO: この関数は後でSQL最適化する` コメントを追加
- 同じように `coverage_rate`, `coverage_municipality_rate`, `daily_delta` メソッドの上にも同様のコメントを追加

---

## ステップ 43-48: GEPS関連メトリクスの基盤整備

### ステップ 43: geps_crawler_success_rate メソッドの構造確認
- メソッドが `successful_runs: int | None = None, total_runs: int | None = None,` から始まっていることを確認
- メソッド内部に `try/except` ブロックがあることを確認

### ステップ 44: geps_crawler_success_rate メソッドのロジックにコメント追加
- `if total_runs is None:` の行の上に `# total_runsが提供されていない場合はDBから取得` コメントを追加
- `query = self.session.query(CrawlLog)` の行の上に `# CrawlLogテーブルからクエリー作成` コメントを追加
- `total_runs = query.count()` の行の上に `# 全実行回数を取得` コメントを追加
- `successful_runs = query.filter(CrawlLog.status.in_(["success", "completed", "ok"])).count()` の行の上に `# 成功した実行回数を取得` コメントを追加

### ステップ 45: geps_crawler_success_rate メソッドの防衛ロジックにコメント追加
- `if not total_runs:` の行の上に `# 総実行数が0の場合はゼロを返す` コメントを追加
- `if successful_runs is None:` の行の上に `# 成功回数が提供されていない場合は0とする` コメントを追加

### ステップ 46: geps_crawler_match_rate メソッドの構造確認
- メソッドが `matched_selectors: int | None = None, total_selectors: int | None = None,` から始まっていることを確認
- メソッドが `if total_selectors is None or total_selectors == 0:` で始まっていることを確認

### ステップ 47: geps_crawler_match_rate メソッドのロジックにコメント追加
- `if total_selectors is None or total_selectors == 0:` の行の上に `# セレクタ総数が0または未設定の場合はゼロを返す` コメントを追加
- `if matched_selectors is None:` の行の上に `# マッチ数が提供されていない場合は0とする` コメントを追加
- `return round((matched_selectors / total_selectors) * 100, 2)` の行の上に `# マッチ率をパーセンテージで計算し、小数点2位で丸め` コメントを追加

### ステップ 48: collect_all_metrics メソッドの構造確認
- メソッドが辞書を返していることを確認（`return {` で始まっている）
- 各メトリクス呼び出しが正しく行われていることを確認
- メソッドの最後に `# すべてのメトリクスを一つの辞書にまとめて返す` コメントを追加

---
*次は P3 ファイル（ステップ 49-72）に続きます*