# スケジューラ運用ドキュメント

## 概要

本ドキュメントは、入札システムのスケジューラ（`scheduler.py`）の運用方法、ジョブ定義、例外ハンドリング、監視方法、トラブルシューティング手順を記載しています。

---

## アーキテクチャ

### コンポーネント

- **SchedulerManager**: スケジューラのライフサイクル管理、ジョブ登録・同期
- **APScheduler**: バックグラウンドスケジューラ（SQLAlchemyJobStore使用）
- **JobStore**: SQLite/PostgreSQLでジョブ永続化
- **Exception分類**: TransientError, FatalError, ConfigurationError
- **Dead Letter Queue (DLQ)**: 最大リトライ超過ジョブの保存
- **Health Checker**: Redis, DB, Queue, Schedulerの各コンポーネント監視

---

## ジョブ定義

### 定期実行ジョブ一覧

| ジョブID | 頻度 | 実行時刻 | 説明 |
|---------|------|----------|------|
| `sync_scheduler_jobs` | 10分ごと | - | DB設定とスケジュールの同期 |
| `system_health_check_job` | 60秒ごと | - | システムヘルスチェック・アラート評価 |
| `metrics_cleanup_job` | 毎日 | 04:00 | 古いメトリクスの削除 |
| `url_monitor_job` | 毎日 | 01:00 | URL監視クロール |
| `award_crawl_job` | 毎日 | 02:00 | 落札結果クロール |
| `backfill_job` | 毎日 | 03:00 | バックフィル実行・リトライ |
| `forecast_weekly_crawl_job` | 毎週日曜 | 05:00 | 発注見通し週次巡回 |
| `forecast_quarterly_crawl_job` | 四半期初め | 05:00 | 発注見通し集中巡回 |
| `morning_digest_job` | 毎日 | 08:00 | 朝のダイジェスト通知 |
| `collect_quality_metrics_job` | 毎日 | 05:30 | 品質メトリクス収集 |
| `evaluate_quality_alerts_job` | 毎日 | 05:45 | 品質アラート評価 |
| `agency_crawl_{config.id}` | 設定依存 | 設定依存 | 自治体別クロール（DB同期） |

### 自治体クロールジョブの動的スケジューリング

- DBの `CrawlConfig` からアクティブな設定を読み取り
- `frequency` (hourly/daily/weekly) に応じてトリガー生成
- IDベースの決定論的ジッターで負荷分散

---

## 例外ハンドリング

### 例外分類

| 例外クラス | 用途 | リトライ | DLQ | 通知 |
|-----------|------|---------|-----|------|
| `TransientError` | 一時的な障害（ネットワーク、タイムアウト等） | ✅ 指数バックオフ | 最大超過時 | - |
| `FatalError` | 復旧不能なエラー（データ破損等） | ❌ | 即座に | - |
| `ConfigurationError` | 設定不備 | ❌ | 即座に | ✅ Critical通知 |

### リトライポリシー

- **最大リトライ回数**: `SCHEDULER_MAX_RETRIES` (デフォルト: 3)
- **バックオフ**: `base * 2^attempt + jitter(0, 0.5)`
  - attempt=0: 2.0s + jitter
  - attempt=1: 4.0s + jitter
  - attempt=2: 8.0s + jitter
  - attempt>=3: 32.0s + jitter (キャップ)

---

## Dead Letter Queue (DLQ)

### 概要

最大リトライ回数を超えたジョブ、または FatalError/ConfigurationError のジョブを JSON ファイルに保存し、後で手動再実行可能にする。

### ファイルパス

`data/scheduler_dlq.json` (環境変数 `SCHEDULER_DLQ_PATH` で変更可)

### エントリ形式

```json
{
  "job_id": "daily_crawl",
  "error": "Connection timeout",
  "payload": {},
  "failed_at": "2026-09-12T03:00:00.123456"
}
```

### 手動再実行

```bash
# 全ジョブ再実行
python -c "from scheduler import retry_dlq_jobs; import asyncio; asyncio.run(retry_dlq_jobs())"

# 特定ジョブのみ再実行
python -c "from scheduler import retry_dlq_jobs; import asyncio; asyncio.run(retry_dlq_jobs(['daily_crawl']))"
```

---

## 監視・アラート

### ヘルスチェック

60秒ごとに実行され、以下をチェック:

| コンポーネント | チェック内容 | しきい値 |
|--------------|------------|----------|
| Redis | 接続・PING | 接続可否 |
| Database | 接続・クエリ実行 | 接続可否 |
| Queue | 深度、処理速度 | 深度 > 1000 で警告 |
| Scheduler | ジョブ実行状況 | 失敗率 > 10% で警告 |

### アラート閾値設定

`config/quality_thresholds.yaml` で設定:

```yaml
metrics:
  scheduler_job_success_rate:
    warning: 90.0
    critical: 80.0
    lower_is_worse: true
  scheduler_job_duration:
    warning: 300.0
    critical: 600.0
    lower_is_worse: false
```

### メトリクス収集

実行完了時に `quality_metric` テーブルに記録:

- `scheduler_job_{job_id}`: 実行時間（秒）
- 成否: `success`, `failed`, `config_error`, `fatal`

---

## トラブルシューティング

### よくある問題と対処

#### 1. ジョブが実行されない

**確認事項:**
- スケジューラが起動しているか (`scheduler_manager._is_running`)
- ジョブが登録されているか (`scheduler.get_jobs()`)
- DBの `CrawlConfig.is_active` が True か

**対処:**
```python
from scheduler import scheduler_manager
jobs = scheduler_manager.list_jobs()
for job in jobs:
    print(job.id, job.next_run_time)
```

#### 2. ジョブが頻繁に失敗してDLQに入る

**確認事項:**
- DLQファイルの内容確認
- エラーメッセージの分析
- 依存サービス（Redis, DB, 外部API）の状態

**対処:**
```bash
cat data/scheduler_dlq.json
# 原因特定後、修正して再実行
python -c "from scheduler import retry_dlq_jobs; import asyncio; asyncio.run(retry_dlq_jobs())"
```

#### 3. ヘルスチェックアラートが頻発する

**確認事項:**
- `config/quality_thresholds.yaml` の閾値が適切か
- 一時的な負荷増大ではないか

**対処:**
- 閾値の調整
- アラート抑制期間の確認（Redis デフォルト 24時間）

#### 4. 自治体クロールジョブが同期されない

**確認事項:**
- `sync_scheduler_jobs` が10分ごとに実行されているか
- DBの `CrawlConfig` にアクティブなレコードがあるか
- `trigger_agency_crawl` 関数が正常に動作するか

---

## 運用手順

### スケジューラ起動

```python
from scheduler import scheduler_manager
scheduler_manager.start()
```

### スケジューラ停止

```python
from scheduler import scheduler_manager
scheduler_manager.stop()
```

### ジョブ手動実行

```python
from scheduler import scheduler_manager
from crawler_task import execute_crawl

# クロールジョブ手動実行
result = execute_crawl()
print(f"New bids: {result.get('new_count', 0)}")
```

### メトリクス手動収集

```bash
python scripts/collect_quality_metrics.py
```

### アラート手動評価

```bash
python scripts/evaluate_quality_alerts.py
```

---

## 設定

### 環境変数

| 変数名 | デフォルト | 説明 |
|-------|-----------|------|
| `DATABASE_URL` | `sqlite:///./bids_system.db` | DB接続URL |
| `SCHEDULER_DLQ_PATH` | `data/scheduler_dlq.json` | DLQファイルパス |
| `SCHEDULER_MAX_RETRIES` | `3` | 最大リトライ回数 |
| `SCHEDULER_BASE_RETRY_DELAY` | `2.0` | ベースバックオフ秒数 |
| `QUALITY_THRESHOLDS_PATH` | `config/quality_thresholds.yaml` | アラート閾値設定 |

### ログ設定

JSON構造化ログを標準出力に出力。以下のフィールドを含む:

```json
{
  "timestamp": "2026-09-12T03:00:00.123456+00:00",
  "level": "INFO",
  "logger": "scheduler",
  "message": "Scheduler started.",
  "event": "scheduler_started"
}
```

---

## CI/CD 統合

### GitHub Actions

`.github/workflows/scheduler.yml` で以下を自動実行:

1. 構文チェック (Python `-m py_compile`)
2. 単体テスト (`pytest tests/test_scheduler.py`)
3. ヘルスチェックエンドポイントテスト
4. 依存関係の脆弱性スキャン

---

## セキュリティ

- 認証必須モード (`ENABLE_AUTH=true`) では管理APIへのアクセス制限
- 機能ゲート (`plan_gate.py`) でプラン別機能制限
- DLQファイルのアクセス制御（ファイルパーミッション 600 推奨）

---

## パフォーマンスチューニング

### 推奨設定

| 項目 | 推奨値 | 備考 |
|------|-------|------|
| 同時実行ジョブ数 | CPUコア数 × 2 | `apscheduler.executors.default` の `max_workers` |
| ジョブストア接続プール | 10-20 | DB負荷に応じて調整 |
| メトリクス保持期間 | 30日 | `metrics_retention_days` |

### ボトルネック対策

- ジョブ実行時間が長い場合: `max_workers` 増加、またはジョブ分割
- DB接続枯渇: 接続プールサイズ増加、トランザクション短縮
- DLQ増加: 根本原因特定、リトライポリシー見直し

---

## 変更履歴

| バージョン | 日付 | 変更内容 | 作成者 |
|----------|------|----------|--------|
| 1.0 | 2026-09-12 | 初版作成 | Architect Mode |

---

## 参考リンク

- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [品質メトリクス設計書](../architecture/quality_metrics.md)
- [アラート管理設計書](../architecture/alerting.md)