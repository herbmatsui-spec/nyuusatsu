# 実装計画書 P3: テスト・品質・ライブクローラ改善 (36ステップ)

## 概要
ライブテスト環境の自動化、GEPSクローラのセレクタ堅牢化、品質メトリクス・アラートの完全動作を実現する。

---

## Phase 1: ライブテスト環境の自動化 (ステップ 1-12)

### Step 1: conftest.py にタイムスタンプ付き一時ディレクトリ fixture 追加
```python
@pytest.fixture(scope="session")
def live_test_dir(tmp_path_factory):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = tmp_path_factory.mktemp(f"live_test_{ts}")
    yield d
    # クリーンアップ: 成功時のみ削除、失敗時は残す
    if not getattr(live_test_dir, "_failed", False):
        shutil.rmtree(d, ignore_errors=True)
```

### Step 2: 失敗時フックで `_failed = True` 設定
- `pytest_runtest_makereport` フックで失敗検知 → `live_test_dir._failed = True`

### Step 3: run_live_tests.py にレポート生成機能追加
- `pytest --json-report --json-report-file=report.json` 実行
- `report.json` を読み込み、Markdown サマリ生成 (`live_test_report_<ts>.md`)

### Step 4: レポートテンプレート作成
- 実行時刻、対象自治体、成功/失敗件数、所要時間、エラー詳細

### Step 5: Slack/LINE 通知連携 (オプション)
- `services/alert_manager.py` の `send_slack_alert` を流用し、レポート要約を投稿

### Step 6: GitHub Actions ワークフロー追加
- `.github/workflows/live-tests.yml` : スケジュール実行 (週1) + 手動実行
- アーティファクトとしてレポート保存 (30日)

### Step 7: 実行前の環境チェック追加
- 必須環境変数 (`DEEPSEEK_API_KEY` 等) 未設定時はスキップ (`pytest.mark.skipif`)

### Step 8: テスト対象自治体リストの外部化
- `tests/test_geps_live/targets.yaml` に `{prefecture: [city1, city2...]}` 形式で定義
- `conftest.py` で読み込み、パラメータライズ

### Step 9: 並列実行対応 (pytest-xdist)
- `-n auto` で並列化、各ワーカーが独立した一時ディレクトリ使用

### Step 10: タイムアウト設定
- `@pytest.mark.timeout(300)` で 5 分超過時は失敗扱い

### Step 11: リトライロジック (flaky 対策)
- `@pytest.mark.flaky(reruns=2, reruns_delay=10)` 付与

### Step 12: ドキュメント更新 (README にライブテスト実行手順追加)

---

## Phase 2: GEPSクローラ セレクタ堅牢化 (ステップ 13-24)

### Step 13: セレクタを外部設定ファイル化
- `crawler/config/geps_selectors.yaml` にページ種別ごとのセレクタマップ定義
- `geps_crawler.py` で `_load_selectors()` 呼び出し

### Step 14: バージョニング導入
- `selectors_version: "2026.09"` キー追加、サイト改版時に新バージョン追加

### Step 15: セレクタ検証ユーティリティ作成
- `crawler/utils/selector_validator.py` : 実 HTML に対してセレクタがマッチするか検証

### Step 16: 既存プレースホルダセレクタ (`input[placeholder*="開始"]`) を実セレクタに置換
- 実際の GEPS サイト HTML 解析し、安定した `id`/`class`/`name` 属性ベースに書き換え

### Step 17: フォールバックセレクタ複数指定対応
- `selectors: ["#startDate", "input[name='startDate']", "input[placeholder*='開始']"]` 形式で優先順位付け

### Step 18: 日付入力フィールド自動検出ロジック追加
- `type="date"` または `class*="datepicker"` 等のヒューリスティックで検出

### Step 19: ページ遷移待機の明示的待機化
- `WebDriverWait` 相当を `requests-html` / `playwright` 併用で実装 (JS レンダリング対応)

### Step 20: 単体テスト用 HTML フィクスチャ追加
- `tests/fixtures/geps/` にリストページ・詳細ページ・検索フォームの生 HTML 保存

### Step 21: セレクタ回帰テスト作成
- `tests/unit/test_geps_selectors.py` : フィクスチャ HTML に対して全セレクタがマッチするか検証

### Step 22: 実サイト対応統合テスト (手動実行用スクリプト)
- `scripts/test_geps_live.py` : 実サイトアクセス → 件数取得 → ログ出力

### Step 23: 監視用メトリクス追加
- `services/quality_metrics_service.py` に `geps_crawler_success_rate`, `geps_selector_match_rate` 追加

### Step 24: アラート閾値設定 (成功率 90% 未満で警告)

---

## Phase 3: 品質メトリクス・アラート完全動作 (ステップ 25-36)

### Step 25: quality_metrics_service.py の収集対象拡充
- 欠損フィールド率 (bid_title, budget, deadline, etc.)
- 重複率 (同一 bid_number の多重登録)
- 取得遅延 (公開日 → DB 登録日の中央値)
- カバレッジ率 (対象自治体数 / 登録済み自治体数)

### Step 26: 日次収集スクリプトの cron 登録確認
- `scheduler.py` の `collect_quality_metrics_job` が毎日実行されるかログ確認

### Step 27: evaluate_quality_alerts.py の閾値外部化
- `config/quality_thresholds.yaml` に各指標の `warning` / `critical` 値定義

### Step 28: アラート通知チャネル追加 (Slack + LINE 両対応)
- `services/quality_alert_service.py` で `send_slack_alert` / `send_line_alert` 両方呼出し

### Step 29: アラート重複抑制 (同一指標・同一日で 1 回のみ通知)
- Redis に `alert_sent:{metric}:{date}` キーで 24h TTL 設定

### Step 30: アラート履歴 DB 保存
- `QualityAlert` モデル作成 (`metric`, `level`, `value`, `threshold`, `sent_at`)
- `services/quality_alert_service.py` で保存

### Step 31: 管理画面 (app_admin.py) に品質アラート履歴タブ追加
- 一覧表示 (フィルタ: 期間、レベル、指標)
- 詳細モーダルで閾値・実測値・通知先表示

### Step 32: ダッシュボード (app_dashboard.py) に品質メトリクスタブ強化
- 時系列グラフ (Plotly) で過去 30 日分の推移表示
- 閾値ライン (warning/critical) 重ね合わせ

### Step 33: 手動実行コマンドのヘルプ整備
- `python scripts/collect_quality_metrics.py --help` でオプション表示
- `--date-range START END` で過去分再収集可能に

### Step 34: 単体テスト拡充 (test_quality_metrics_service.py)
- モック DB で各指標計算ロジック検証
- 閾値判定ロジック (warning/critical/normal) 検証

### Step 35: 統合テスト (実 DB で収集→評価→通知フロー確認)
- テストデータ投入 → 収集実行 → アラート発火 → Slack/LINE 受信確認

### Step 36: 運用ドキュメント作成 (docs/operations/quality_monitoring.md)
- 指標定義、閾値設定手順、アラート対応フロー、ダッシュボード見方