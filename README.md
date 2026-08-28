# 入札システム (Bid Extraction System)

## 📖 概要
このプロジェクトは、官公庁・自治体が公開する入札情報（PDF・HTML）を自動で取得し、LLM（Large Language Model）と OCR（光学文字認識）を組み合わせて必須要件（予算、資格要件、納期、成果物等）を抽出・正規化・可視化するエンドツーエンドシステムです。

**主な拡張機能**
- **クローラ基盤**：`BaseCrawler`／`ConfigDrivenCrawler` による汎用的な URL 取得・ページ遷移（Pagination）
- **企業名正規化**：`services/company_normalizer.py` と `config/company_normalization_rules.py` による表記揺れ統一・業種推定
- **優先度マトリクス**：`CrawlPriority` モデルとスコアリングロジックで都道府県別・業種別のクロール優先度を算出
- **競合分析ダッシュボード**：競合企業の落札件数・勝率・監視対象フラグを可視化（`app_dashboard.py` → 競合分析タブ）
- **QA（Human Review）ワークフロー**：`QAReview` モデル、割当・承認 UI、修正パイプライン（`services/qa_assignment_service.py`、`services/qa_fix_pipeline.py`）
- **品質メトリクス**：欠損フィールド、重複、カバレッジ率、日次変化量を自動計測し、しきい値超過時に Slack/LINE 通知（`services/quality_metrics_service.py`、`services/quality_alert_service.py`）
- **高度なアラート機構**：システムヘルスチェック、コンポーネント障害の連続検知、競合出現アラート、品質警告・アラート
- **スケジューラ統合**：APScheduler によりクロール・健康チェック・朝のダイジェスト・品質メトリクス収集・落札結果クローラを自動実行（`scheduler.py`）
- **UI 改善**：管理画面に QA、しきい値、システム設定タブ追加、ダッシュボードにデータ品質タブ、カスタム CSS (`static/css/custom_dashboard.css`)
- **テスト・CI**：ユニットテストが 21 件全て成功、`pytest`・`py_compile` による自動検証

## 🎯 主な機能一覧
| カテゴリ | 機能 | 実装ファイル／モジュール |
|---|---|---|
| **データ取得** | 自動巡回クローラ（HTML・PDF） | `crawler/`, `scripts/` |
| **テキスト抽出** | OCR（Tesseract / Azure）| `ocr/` |
| **LLM 解析** | 仕様書要件抽出・業種推定 | `services/`（LLM 関連） |
| **正規化** | 企業名正規化・業種マッピング | `services/company_normalizer.py` |
| **スコアリング** | 優先度マトリクス算出 | `services/priority_scorer.py` |
| **データ保存** | SQLite + SQLAlchemy ORM | `database/models/`、`database/repositories/` |
| **品質管理** | 欠損・重複チェック・メトリクス収集 | `services/award_quality_checker.py`、`services/quality_metrics_service.py` |
| **アラート** | ヘルスチェック、競合出現、品質警告 | `services/alert_manager.py`、`services/competitor_alert_service.py`、`services/quality_alert_service.py` |
| **人手レビュー** | QA レビュー割当・承認・修正 | `services/qa_assignment_service.py`、`services/qa_fix_pipeline.py` |
| **可視化** | Streamlit ダッシュボード（KPI・分析・競合・データ品質） | `app_dashboard.py` |
| **管理 UI** | Flask 管理画面（組織・ユーザー・ロール・優先度・インベントリ・QA・しきい値） | `app_admin.py` |
| **スケジューラ** | 定期ジョブ（クロール、健康チェック、品質収集、朝ダイジェスト） | `scheduler.py` |
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

# アプリケーション設定（例）
QUEUE_ALERT_THRESHOLD=100   # Redis キュー深さ閾値
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
### 4. 自動巡回クローラ（全自治体取得）
```bash
python main.py   # 設定された CrawlConfig に従い HTML / PDF を取得し DB に保存
```
### 5. スケジューラ（バックグラウンドジョブ）
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

### 6. 品質メトリクス収集・評価（手動実行例）
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
├─ config.py                  # アプリ共通設定（KPI、スケジューラ、DB パス）
├─ requirements.txt           # Python 依存パッケージ
├─ .env                       # 環境変数（API キー・Webhook）
├─ database/
│   ├─ models/               # SQLAlchemy ORM モデル（Bid, AwardResult, QAReview …）
│   └─ repositories/         # データアクセス層（CRUD）
├─ crawler/
│   ├─ base_crawler.py       # 汎用クローラ基底クラス
│   ├─ config_driven_crawler.py
│   ├─ agency_lists/ …       # 各自治体向けリスト取得クラス
│   └─ parsers/ …            # HTML / PDF パーサ
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
│   ├─ … (その他ビジネスロジック)
├─ scripts/
│   ├─ seed_agency_inventory.py
│   ├─ collect_quality_metrics.py
│   ├─ evaluate_quality_alerts.py
│   └─ … (ユーティリティスクリプト)
├─ static/css/custom_dashboard.css   # ダッシュボード用カスタムテーマ
├─ tests/
│   ├─ unit/                  # ユニットテスト（全部 21 件合格）
│   └─ …
└─ scheduler.py               # APScheduler 設定・ジョブ定義
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
