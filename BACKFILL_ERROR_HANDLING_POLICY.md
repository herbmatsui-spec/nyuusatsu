# バックフィル実装 - エラーハンドリング方針 (Step 8)

## 方針概要

バックフィル処理は長時間実行・大量データ処理・外部サイト依存のため、堅牢なエラーハンドリングが必須。

---

## 1. エラー分類と対応

| エラー分類 | 例 | 対応 | リトライ |
|-----------|-----|------|----------|
| **ネットワークエラー** | Timeout, ConnectionError, DNS失敗 | 指数バックオフでリトライ（最大3回） | ✅ 3回 |
| **HTTPエラー** | 404, 403, 500, 502, 503 | 4xxはスキップ、5xxはリトライ | 5xxのみ✅ |
| **パースエラー** | HTML構造変更、セレクタ不一致 | ログ記録してスキップ、構造変更検知アラート | ❌ |
| **DBエラー** | IntegrityError, OperationalError | ロールバックしてリトライ（最大3回） | ✅ 3回 |
| **データ異常** | 予算額0、未来日付、必須フィールド欠落 | 警告ログ、フラグ付けして継続 | ❌ |
| **リソース枯渇** | メモリ不足、ディスク満杯 | 即座に停止、アラート通知 | ❌ |

---

## 2. リトライ戦略

```python
# 基本方針: 指数バックオフ + ジッター
max_retries = 3
base_delay = 2  # seconds
max_delay = 60  # seconds

for attempt in range(max_retries):
    try:
        result = operation()
        break
    except RetryableError as e:
        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
        logger.warning(f"Attempt {attempt+1}/{max_retries} failed: {e}. Retrying in {delay:.1f}s")
        time.sleep(delay)
    except NonRetryableError as e:
        logger.error(f"Non-retryable error: {e}")
        raise
```

---

## 3. ジョブレベルのエラー処理

### BackfillJob.status 遷移
```
pending → running → done
              ↘ failed (エラー時)
              ↘ skipped (重複ジョブ時)
```

### エラー時の記録
- `BackfillJob.error_message`: 最後のエラー内容（直近1件）
- `BackfillJobLog`: 全ステップの詳細ログ（level: INFO/WARNING/ERROR）

### 部分失敗の扱い
- ページ単位の失敗: そのページをスキップして継続、エラーカウント増加
- 機関単位の失敗: ジョブを failed にして終了、次回リトライ対象に
- 致命的エラー: 即座に failed、アラート通知

---

## 4. 通知ルール

| 条件 | 通知先 | テンプレート |
|------|--------|-------------|
| ジョブ完了（done） | Slack #backfill | ✅ 件数・所要時間・補完フィールド数 |
| ジョブ失敗（failed） | Slack #backfill + LINE管理者 | 🔴 エラー詳細・機関名・期間 |
| 連続失敗（3回以上） | Slack #alert + メール | 🔴 要人手介入 |
| 重複ジョブスキップ | ログのみ | - |

---

## 5. データ品質異常の検知・記録

```python
# 異常値検知ルール
ANOMALY_RULES = {
    "budget_amount": {"min": 1000, "max": 10_000_000_000},  # 1千円〜100億
    "announcement_date": {"past_years_max": 10, "future_days_max": 365},
    "award_rate": {"min": 0.0, "max": 100.0},
}
```

検知時: `BackfillJobLog` に WARNING 記録、ジョブ完了時サマリーに含める

---

## 6. 実装箇所

| ファイル | 責務 |
|----------|------|
| `services/backfill_service.py` | メイン実行ロジック、リトライ、ログ記録 |
| `services/backfill_dedup.py` | 重複排除時のエラー処理 |
| `notifier.py` | 通知送信（既存拡張） |
| `crawler/base_crawler.py` | 共通リトライ・エラー処理の基盤 |

---

## 7. 次ステップへの引き継ぎ

この方針に基づき、Step 9-12 でモデル作成時に：
- `BackfillJob.error_message` は Text 型で最後のエラーを保存
- `BackfillJobLog.level` で ERROR/WARNING/INFO を使い分け
- `status` Enum に failed を含める

次のStep 9で BackfillJobモデルを作成