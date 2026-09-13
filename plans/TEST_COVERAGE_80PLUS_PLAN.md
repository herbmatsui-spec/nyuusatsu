# テストカバレッジ率80%以上達成に向けた実装計画

## 1. 目的

このプロジェクトのテストカバレッジ率を80%以上に引き上げ、主要機能の回帰品質を担保する。

## 2. 現状分析

### 2.1 現状のテスト構成

- `tests/` 配下に `test_*.py` が 99 ファイル存在
- `pytest --collect-only` では 151 テストを収集できるが、収集時エラー 4 件あり
- `pytest.ini` のカバレッジ対象は `crawler`, `config`, `services`, `repositories`
- 現在の下限は `--cov-fail-under=10`

### 2.2 既存のテストカバレッジ計画

既存の [`TEST_COVERAGE_IMPROVEMENT_PLAN.md`](plans/TEST_COVERAGE_IMPROVEMENT_PLAN.md) と [`test_coverage_plan.md`](plans/test_coverage_plan.md) には、以下の7フェーズの計画が記載されている。

- Phase 1: パーサ・正規化ユーティリティ
- Phase 2: クローラ基盤
- Phase 3: 品質管理・アラート
- Phase 4: リポジトリ層
- Phase 5: 分析・認証・ヘルスサービス
- Phase 6: バックフィル・クロール・タスクキュー
- Phase 7: OCR・プラン制限・その他ユーティリティ

### 2.3 現状の主要な未テスト領域

AST でソース関数とテスト関数名を突合した結果、`crawler`, `services`, `repositories`, `ocr`, `events`, `database`, `utils` 配下の 222 関数定義ファイルのうち 213 ファイルに未テスト関数が存在した。

優先度が高い未テスト関数を持つモジュール:

| モジュール | 未テスト関数数 | 優先度 |
|---|---:|---|
| `database/repositories/__init__.py` | 24 | 高 |
| `services/analysis_service.py` | 22 | 高 |
| `services/quality_metrics_service.py` | 14 | 高 |
| `repositories/forecast_repository.py` | 14 | 高 |
| `crawler/detail_extractor.py` | 12 | 高 |
| `services/sqlite_task_queue.py` | 12 | 中 |
| `services/quality_alert_service.py` | 12 | 高 |
| `services/backfill_service.py` | 12 | 中 |
| `crawler/base_crawler.py` | 11 | 高 |
| `services/health_checker.py` | 9 | 高 |
| `services/auth_service.py` | 9 | 高 |
| `services/alert_manager.py` | 7 | 高 |
| `crawler/parsers/award_parser.py` | 6 | 高 |
| `services/bid_analysis_service.py` | 6 | 高 |

### 2.4 既存テストの傾向

- クローラ、パーサ、Grade Matcher、Forecast Repository、Quality Metrics などは一部テスト済み
- 一方、DB リポジトリ、分析集計、アラート、認証、OCR、ユーティリティは未テストまたは薄くしかテストされていない
- 外部依存を含むテストはモック化が不十分で、収集エラーや環境依存が発生している

## 3. 目標

### 3.1 数値目標

- Phase 1〜3 完了後: カバレッジ 40% 以上
- Phase 4〜6 完了後: カバレッジ 60% 以上
- Phase 7 完了後: カバレッジ 80% 以上
- `pytest.ini` の `--cov-fail-under` は段階的に 10 → 40 → 60 → 80 に引き上げる

### 3.2 品質目標

- 外部 API、Redis、DB、ネットワークに依存するテストは原則モック化
- 空文字、`None`、不正フォーマット、境界値を必ず含める
- HTML/PDF/JSON フィクスチャを `tests/fixtures/` に集約
- 既存の E2E ライブテストは維持し、単体テストとは分離する

## 4. 実装フェーズ

### Phase 1: パーサ・正規化ユーティリティ（高優先度・低コスト）

#### 対象

- `crawler/parsers/award_parser.py`
- `crawler/parsers/field_normalizer.py`
- `crawler/parsers/grade_parser.py`
- `crawler/utils/company_name_normalizer.py`

#### テスト内容

- 金額、日付、企業名、業種の抽出
- 和暦、全角数字、カンマ区切りの正常・異常系
- 等級抽出、13 桁資格番号抽出、表記正規化
- 会社名サフィックス除去、法人番号抽出、類似度、業種推定

#### 作成・拡充ファイル

- `tests/test_award_parser.py`
- `tests/test_field_normalizer.py`
- `tests/test_grade_parser.py`
- `tests/unit/test_company_name_normalizer.py`

#### 想定効果

- カバレッジ +10〜15%

### Phase 2: クローラ基盤（高優先度・中コスト）

#### 対象

- `crawler/base_crawler.py`
- `crawler/config_driven_crawler.py`
- `crawler/detail_extractor.py`
- `crawler/utils/selector_validator.py`
- `crawler/utils/forecast_url_detector.py`

#### テスト内容

- HTTP リトライ、タイムアウト、バックオフ
- YAML 設定読み込み、CSS セレクタ抽出、URL 結合
- HTML/PDF 詳細抽出、複数金額から最大値抽出
- セレクタ検証、フォールバック、予測 URL 検出

#### 作成・拡充ファイル

- `tests/unit/test_base_crawler.py`
- `tests/test_config_driven_crawler.py`
- `tests/test_detail_extractor.py`
- `tests/unit/test_selector_validator.py`
- `tests/unit/test_forecast_url_detector.py`

#### 想定効果

- カバレッジ +15〜20%

### Phase 3: 品質管理・アラート（高優先度・中コスト）

#### 対象

- `services/quality_metrics_service.py`
- `services/quality_alert_service.py`
- `services/alert_manager.py`
- `services/health_checker.py`

#### テスト内容

- 欠損フィールド率、重複率、取得遅延中央値、カバレッジ率
- YAML/DB 閾値読み込み、Redis 重複抑制、Slack/LINE 通知
- アラート履歴保存、ヘルスチェック結果の辞書化
- 各チェック項目の成功・失敗パターン

#### 作成・拡充ファイル

- `tests/unit/test_quality_metrics_service.py`
- `tests/unit/test_quality_alert_service.py`
- `tests/unit/test_alert_manager.py`
- `tests/test_health_checker.py`

#### 想定効果

- カバレッジ +10〜15%

### Phase 4: リポジトリ層（高優先度・中コスト）

#### 対象

- `database/repositories/__init__.py`
- `repositories/forecast_repository.py`
- `database/repositories/base.py`

#### テスト内容

- インメモリ SQLite による CRUD
- バッチ保存、UPSERT、集計クエリ
- 予測データの検索、ステータス更新、カテゴリ別取得
- 基底リポジトリの汎用クエリ操作

#### 作成・拡充ファイル

- `tests/unit/test_repositories.py`
- `tests/repositories/test_forecast_repository.py`
- `tests/unit/test_base_repository.py`

#### 想定効果

- カバレッジ +8〜12%

### Phase 5: 分析・認証・ヘルスサービス（中優先度・高コスト）

#### 対象

- `services/analysis_service.py`
- `services/analysis_service_core.py`
- `services/auth_service.py`
- `services/billing_service.py`
- `services/notification_service.py`

#### テスト内容

- テキスト分割、コンテキスト圧縮、統計集計
- JSON パース、PDF メタデータ抽出、レポート生成
- 認証、トークン、権限、パスワードハッシュ
- 課金セッション、通知チャネル、メール/Slack/Teams/LINE

#### 作成・拡充ファイル

- `tests/test_analysis_service.py`
- `tests/unit/test_analysis_service_core.py`
- `tests/unit/test_auth_service.py`
- `tests/unit/test_billing_service.py`
- `tests/unit/test_notification_service.py`

#### 想定効果

- カバレッジ +10〜15%

### Phase 6: バックフィル・クロール・タスクキュー（中優先度）

#### 対象

- `services/backfill_service.py`
- `services/backfill_dedup.py`
- `services/crawl_scheduler.py`
- `services/sqlite_task_queue.py`
- `crawler/pipeline.py`

#### テスト内容

- バックフィルジョブ作成、実行、結果変換、ログ
- 重複検出、マージ、孤立データ削除、整合性チェック
- 都道府県別クロール、GEPS/Web 切り分け
- タスクキューの enqueue/run/mark 状態遷移
- PDF ダウンロード、分析、通知タスク

#### 作成・拡充ファイル

- `tests/test_backfill_service.py`
- `tests/test_backfill_dedup.py`
- `tests/unit/test_crawl_scheduler.py`
- `tests/unit/test_sqlite_task_queue.py`
- `tests/test_pipeline.py`

#### 想定効果

- カバレッジ +8〜12%

### Phase 7: OCR・プラン制限・その他ユーティリティ（低優先度）

#### 対象

- `ocr/metrics.py`
- `ocr/text_corrector.py`
- `utils/plan_gate.py`
- `ocr/azure_doc_int.py`
- `ocr/tesseract_ocr.py`

#### テスト内容

- OCR メトリクス記録、平均信頼度、リセット
- OCR 結果補正履歴、補正適用
- プラン制限、日次/月次制限、デコレータ
- OCR フォールバック、Azure/Tesseract 呼び出しモック

#### 作成・拡充ファイル

- `tests/unit/test_ocr_metrics.py`
- `tests/unit/test_text_corrector.py`
- `tests/unit/test_plan_gate.py`
- `tests/unit/test_ocr_backends.py`

#### 想定効果

- カバレッジ +5〜8%

## 5. テスト設計方針

### 5.1 モックの使い分け

- HTTP: `requests_mock` または `unittest.mock.patch`
- DB: インメモリ SQLite + SQLAlchemy `Session`
- Redis: `fakeredis` または `MagicMock`
- 外部 API: レスポンスモデルをモック
- 非同期: `pytest.mark.asyncio`

### 5.2 境界値・異常系

各関数について最低限以下をテストする。

- 空文字
- `None`
- 不正フォーマット
- 最大値・最小値
- 重複入力
- 部分一致・完全一致の差

### 5.3 フィクスチャ

`tests/fixtures/` に以下を集約する。

- HTML 一覧ページ
- HTML 詳細ページ
- PDF 抽出テキスト
- JSON レスポンス
- YAML 設定
- DB シードデータ

## 6. 実行コマンド

### 6.1 全体テスト

```bash
python -m pytest
```

### 6.2 カバレッジ確認

```bash
python -m pytest --cov=crawler --cov=config --cov=services --cov=repositories --cov-report=term-missing
```

### 6.3 モジュール別カバレッジ

```bash
python -m pytest --cov=crawler.parsers.award_parser --cov-report=term-missing tests/test_award_parser.py
```

### 6.4 高速フィードバック

```bash
python -m pytest tests/unit tests/test_award_parser.py tests/test_field_normalizer.py
```

## 7. 実装順序と完了条件

1. Phase 1 を実装し、対象モジュールのカバレッジを 80% 以上にする
2. Phase 2 を実装し、クローラ基盤の主要分岐を網羅する
3. Phase 3 を実装し、品質・アラート系の正常/異常系を網羅する
4. Phase 4 を実装し、DB 操作をインメモリ SQLite で安定化させる
5. Phase 5〜7 を順に実装する
6. 各 Phase 完了時に `pytest.ini` の `--cov-fail-under` を引き上げる
7. 最終的に全対象モジュールで 80% 以上を目指す

## 8. リスクと対応

| リスク | 対応 |
|---|---|
| 外部 API 依存でテストが不安定 | API クライアントを注入可能にし、テストではモック化 |
| DB 状態の相互汚染 | テストごとに DB を初期化し、フィクスチャで隔離 |
| 収集エラーが残る | エラー原因を個別に特定し、インポート時の副作用を排除 |
| テスト増加で実行時間が増大 | `tests/unit` は高速実行、E2E は分離して選択実行 |
| カバレッジだけ上がって品質が上がらない | 分岐・境界値・異常系を必須条件にする |

## 9. 完了条件チェックリスト

- [ ] Phase 1: パーサ・正規化ユーティリティのテスト完了（カバレッジ 80% 以上）
- [ ] Phase 2: クローラ基盤のテスト完了（カバレッジ向上）
- [ ] Phase 3: 品質管理・アラートのテスト完了（カバレッジ向上）
- [ ] Phase 4: リポジトリ層のテスト完了（カバレッジ向上）
- [ ] Phase 5: 分析・認証・ヘルスサービスのテスト完了（カバレッジ向上）
- [ ] Phase 6: バックフィル・クロール・タスクキューのテスト完了（カバレッジ向上）
- [ ] Phase 7: OCR・プラン制限・その他ユーティリティのテスト完了（カバレッジ向上）
- [ ] `pytest.ini` の `--cov-fail-under` を 80 に引き上げる
- [ ] 全モジュールでカバレッジ 80% 以上を達成