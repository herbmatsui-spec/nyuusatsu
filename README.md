# 入札システム (Bid Extraction System)

## 📖 概要
このプロジェクトは、官公庁・自治体が公開する入札情報（PDF・HTML）を自動で取得し、LLM（Large Language Model）と OCR（光学文字認識）を組み合わせて必須要件（予算、資格要件、納期、成果物等）を抽出・正規化・可視化するエンドツーエンドシステムです。

**主な拡張機能**
- **クローラ基盤**：`BaseCrawler`／`ConfigDrivenCrawler` による汎用的な URL 取得・ページ遷移（Pagination）
- **日付範囲指定クロール**：全クローラーに `start_date`/`end_date` パラメータ追加により過去データのバックフィル取得を実現
- **企業名正規化**：`services/company_normalizer.py` と `config/company_normalization_rules.py` による表記揺れ統一・業種推定
- **優先度マトリクス**：`CrawlPriority` モデルとスコアリングロジックで都道府県別・業種別のクロール優先度を算出
- **競合分析ダッシュボード**：競合企業の落札件数・勝率・監視対象フラグを可視化（`app_dashboard.py` → 競合分析タブ）
- **QA（Human Review）ワークフロー**：`QAReview` モデル、割当・承認 UI、修正パイプライン（`services/qa_assignment_service.py`、`services/qa_fix_pipeline.py`）
- **品質メトリクス**：欠損フィールド、重複、カバレッジ率、日次変化量を自動計測し、しきい値超過時に Slack/LINE 通知（`services/quality_metrics_service.py`、`services/quality_alert_service.py`）
- **高度なアラート機構**：システムヘルスチェック、コンポーネント障害の連続検知、競合出現アラート、品質警告・アラート
- **スケジューラ統合**：APScheduler によりクロール・健康チェック・朝のダイジェスト・品質メトリクス収集・落札結果クローラを自動実行（`scheduler.py`）
- **バックフィルシステム**：過去データ遡及取得ジョブ管理、`BackfillJob`/`BackfillJobLog` モデル、重複排除・データ品質向上サービス
- **認証・課金システム**：Stripe連携によるプラン管理（Free/Standard/Pro/Enterprise）、機能制限・無料トライアル、顧客ポータル
- **UI 改善**：管理画面に QA、しきい値、システム設定タブ追加、ダッシュボードにデータ品質タブ、カスタム CSS (`static/css/custom_dashboard.css`)
- **テスト・CI**：ユニットテストが 21 件全て成功、`pytest`・`py_compile` による自動検証

## 🎯 主な機能一覧
| カテゴリ | 機能 | 実装ファイル／モジュール |
|---|---|---|
| **データ取得** | 自動巡回クローラ（HTML・PDF） | `crawler/`, `scripts/` |
| **日付範囲指定取得** | 指定期間の入札情報を遡及取得 | `crawler/base_crawler.py`, `services/backfill_service.py` |
| **テキスト抽出** | OCR（Tesseract / Azure）| `ocr/` |
| **LLM 解析** | 仕様書要件抽出・業種推定 | `services/`（LLM 関連） |
| **正規化** | 企業名正規化・業種マッピング | `services/company_normalizer.py` |
| **スコアリング** | 優先度マトリクス算出 | `services/priority_scorer.py` |
| **データ保存** | SQLite + SQLAlchemy ORM | `database/models/`、`database/repositories/` |
| **品質管理** | 欠損・重複チェック・メトリクス収集 | `services/award_quality_checker.py`、`services/quality_metrics_service.py` |
| **アラート** | ヘルスチェック、競合出現、品質警告 | `services/alert_manager.py`、`services/competitor_alert_service.py`、`services/quality_alert_service.py` |
| **人手レビュー** | QA レビュー割当・承認・修正 | `services/qa_assignment_service.py`、`services/qa_fix_pipeline.py` |
| **バックフィル管理** | 過去データ取得ジョブ管理・重複排除・データ品質向上 | `services/backfill_service.py`, `services/backfill_dedup.py`, `app_admin.py`（バックフィルタブ） |
| **認証・課金** | ユーザー認証・Stripe決済・プラン管理・機能制限 | `app_billing.py`, `app_webhook.py`, `services/billing_service.py`, `utils/auth_decorator.py`, `utils/plan_gate.py`, `utils/stripe_client.py` |
| **API使用量管理** | 月間APIリクエスト制限・トラッキング | `services/api_usage.py`, `database/models/api_usage.py` |
| **可視化** | Streamlit ダッシュボード（KPI・分析・競合・データ品質） | `app_dashboard.py` |
| **管理 UI** | Flask 管理画面（組織・ユーザー・ロール・優先度・インベントリ・QA・バックフィル・しきい値） | `app_admin.py` |
| **スケジューラ** | 定期ジョブ（クロール、健康チェック、品質収集、朝ダイジェスト、バックフィル） | `scheduler.py` |
| **ユーティリティ** | ログ、認証、CSV/JSON エクスポート、iCal 出力 | `utils/`、`services/*_exporter.py` |

## 🛠️ セットアップ
### 1. 必要環境
- **Python** 3.10 以上（推奨 3.12）
- **依存パッケージ**：`requirements.txt` に記載
- **外部サービス**：
  - DeepSeek / Gemini API キー（LLM）
  - Slack / LINE Webhook（通知）
  - （任意）Azure Document Intelligence またはローカル Tesseract（OCR）

### 2. インストール
```bash
# 仮想環境作成（推奨）
python -m venv .venv && source .venv/bin/activate

# 依存パッケージインストール
pip install -r requirements.txt
```

### 3. 設定ファイル (`.env`)
```dotenv
# LLM API キー
DEEPSEEK_API_KEY=your_deepseek_key
GEMINI_API_KEY=your_gemini_key

# OCR（Azure）
AZURE_DOCUMENTINTELLIGENCE_ENDPOINT=your_endpoint
AZURE_DOCUMENTINTELLIGENCE_KEY=your_key

# 通知設定（Slack / LINE）
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz
LINE_CHANNEL_ACCESS_TOKEN=your_line_token
LINE_USER_ID=your_line_user_id

# Stripe 認証・課金
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_STANDARD=price_standard_id
STRIPE_PRICE_PRO=price_pro_id
STRIPE_PRICE_ENTERPRISE=price_enterprise_id
STRIPE_SUCCESS_URL=http://localhost:8501/billing/success
STRIPE_CANCEL_URL=http://localhost:8501/billing/cancel
STRIPE_PORTAL_URL=http://localhost:8501/billing/portal

# アプリケーション設定（例）
QUEUE_ALERT_THRESHOLD=100   # Redis キュー深さ閾値
```
> 設定が不足している項目はアプリ起動時に警告が表示されます。
```
> 設定が不足している項目はアプリ起動時に警告が表示されます。

### 4. データベース初期化・マイグレーション
```bash
# Alembic マイグレーション適用（SQLite がデフォルト）
alembic upgrade head

# DB の内容確認（optional）
python verify_db.py
```

## 🚀 起動方法
### 1. Web UI（基本抽出・検索）
```bash
streamlit run app.py   # PDF 1 件抽出・簡易検索 UI
```
### 2. 分析ダッシュボード（KPI・競合・品質）
```bash
streamlit run app_dashboard.py
```
### 3. 管理画面（Flask）
```bash
python app_admin.py
# http://localhost:5000 にアクセス
```
### 4. 課金・プラン管理 UI
```bash
streamlit run app_billing.py
# 認証後、サイドバーの「💳 プラン・請求」からもアクセス可能
```
### 5. Stripe Webhook エンドポイント
```bash
# 別ターミナルで実行（開発時）
uvicorn app_webhook:app --host 0.0.0.0 --port 8000
```
### 6. 自動巡回クローラ（全自治体取得）
```bash
python main.py   # 設定された CrawlConfig に従い HTML / PDF を取得し DB に保存
```
### 7. スケジューラ（バックグラウンドジョブ）
```bash
python - <<'PY'
from scheduler import scheduler_manager
scheduler_manager.start()
PY
```
> バックグラウンドで定期的に以下を実行します：
> - 各自治体の入札ページクロール（毎日）
> - ヘルスチェック・アラート（1 分）
> - 品質メトリクス収集（毎日）
> - 朝のダイジェスト通知（毎日 08:00）
> - バックフィルジョブ（週1回、日曜深夜）
>
### 8. 品質メトリクス収集・評価（手動実行例）
```bash
# メトリクス収集
python scripts/collect_quality_metrics.py

# アラート評価（しきい値超過時に Slack/LINE 通知）
python scripts/evaluate_quality_alerts.py
```

## 📂 ディレクトリ構成（概要）
```
.
├─ app.py                     # Streamlit – PDF 1 件抽出 UI
├─ app_dashboard.py           # Streamlit – 全体分析・競合・データ品質 UI
├─ app_admin.py               # Flask 管理画面（ユーザー・ロール・QA など）
├─ app_billing.py             # Streamlit – 課金・プラン管理 UI
├─ app_webhook.py             # FastAPI – Stripe Webhook エンドポイント
├─ backfill_investigation_report.md  # バックフィル調査レポート
├─ backfill_error_handling_policy.md # バックフィルエラーハンドリング方針
├─ config.py                  # アプリ共通設定（KPI、スケジューラ、DB パス）
├─ requirements.txt           # Python 依存パッケージ
├─ .env                       # 環境変数（API キー・Webhook・Stripe）
├─ database/
│   ├─ models/               # SQLAlchemy ORM モデル（Bid, AwardResult, QAReview, BackfillJob, BackfillJobLog, ApiUsage …）
│   └─ repositories/         # データアクセス層（CRUD）
├─ crawler/
│   ├─ base_crawler.py       # 汎用クローラ基底クラス（日付範囲指定対応）
│   ├─ config_driven_crawler.py
│   ├─ generic_crawler.py    # 汎用クローラー（カテゴリ・優先度フィルタ対応）
│   ├─ geps_crawler.py       # GEPS クローラー（全省庁対応）
│   ├─ agency_lists/ …       # 各自治体向けリスト取得クラス
│   ├─ parsers/ …            # HTML / PDF パーサ
│   ├─ registry/             # URL レジストリシステム
│   │   ├─ prefecture_registry.py
│   │   ├─ city_registry.py
│   │   └─ municipality_registry.py
│   ├─ patterns/             # パターンライブラリ
│   │   └─ prefectures/      # 都道府県別パターン
│   └─ utils/                # クローラユーティリティ
│       ├─ date_filter.py    # 日付範囲フィルタ
│   │   └─ date_parser.py    # 日付パース（和暦・西暦両対応）
├─ ocr/                       # OCR ライブラリ・ユーティリティ（Tesseract, Azure）
├─ services/
│   ├─ company_normalizer.py  # 企業名正規化・業種判定
│   ├─ priority_scorer.py    # 優先度スコア計算
│   ├─ qa_assignment_service.py
│   ├─ qa_fix_pipeline.py
│   ├─ quality_metrics_service.py
│   ├─ quality_alert_service.py
│   ├─ alert_manager.py
│   ├─ competitor_alert_service.py
│   ├─ award_quality_checker.py
│   ├─ backfill_service.py    # バックフィル実行サービス
│   ├─ backfill_dedup.py      # バックフィル重複排除・データ品質向上
│   ├─ billing_service.py     # Stripe課金・サブスクリプション管理
│   ├─ api_usage.py           # API使用量トラッキング・制限
│   ├─ … (その他ビジネスロジック)
├─ scripts/
│   ├─ seed_agency_inventory.py
│   ├─ collect_quality_metrics.py
│   ├─ evaluate_quality_alerts.py
│   ├─ seed_backfill_jobs.py          # バックフィルジョブ初期投入スクリプト
│   ├─ check_backfill_integrity.py    # バックフィル整合性チェック
│   ├─ gen_backfill_quality_report.py # バックフィル品質レポート生成
│   └─ … (ユーティリティスクリプト)
├─ static/css/custom_dashboard.css   # ダッシュボード用カスタムテーマ
├─ tests/
│   ├─ unit/                  # ユニットテスト（全部 21 件合格）
│   ├─ test_backfill_service.py       # バックフィルサービステスト
│   ├─ test_backfill_dedup.py         # 重複排除テスト
│   ├─ test_date_range_crawl.py       # 日付範囲フィルタテスト
│   ├─ test_backfill_pipeline.py      # バックフィルパイプラインテスト
│   └─ …
└─ scheduler.py               # APScheduler 設定・ジョブ定義（バックフィルジョブ対応）
```

## 🧪 テスト・品質保証
```bash
# ユニットテスト実行（全て成功）
python -m pytest tests/unit/ -v

# 静的構文チェック
python -m py_compile **/*.py
```
テストカバレッジは主要ロジック（クローラ、正規化、QA、品質メトリクス、アラート）を網羅しています。

## 🤝 コントリビュート
1. フォーク → ブランチ作成（`feature/your-feature`）
2. 変更をコミット → プルリクエスト作成
3. 既存テストが全てパスすることを確認してください。

## 📜 ライセンス
本プロジェクトは MIT ライセンスの下で提供されます。
