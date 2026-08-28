# 入札システム (Bid Extraction System)

官公庁・自治体の入札仕様書PDFから、業務代行判断に必要な必須要件をLLMを用いて自動抽出し、可視化・保存するツールです。

## 機能
- **PDF 要件抽出**: 仕様書PDFから予算、参加資格、納期、成果物を自動抽出
- **OCR 対応**: テキスト抽出不可のPDF（スキャンPDF）をOCRでテキスト化
- **自動巡回**: 指定URLからPDFを自動収集し、一括で要件を抽出してCSV保存
- **DB 管理**: 抽出結果の永続化、検索履歴管理、お気に入り機能
- **ダッシュボード**: 抽出結果の可視化と分析

## セットアップ

### 1. 必要環境
- Python 3.10 以上
- DeepSeek API Key / Gemini API Key
- (OCR利用時) Tesseract OCR または Azure Document Intelligence

### 2. インストール
```powershell
pip install -r requirements.txt
```

### 3. APIキーの設定
`.env` ファイルを作成し、以下を設定してください。
設定が不足している場合、アプリケーション起動時に警告が表示されます。
```env
DEEPSEEK_API_KEY=your_deepseek_key
GEMINI_API_KEY=your_gemini_key
# OCRを使用する場合
AZURE_DOCUMENTINTELLIGENCE_ENDPOINT=your_endpoint
AZURE_DOCUMENTINTELLIGENCE_KEY=your_key
```

## 使い方

### Web UI (Streamlit)
- PDF1件抽出: `streamlit run app.py`
- 分析ダッシュボード: `streamlit run app_dashboard.py`

### 管理画面 (Flask)
```powershell
python app_admin.py
```
アクセス先: http://localhost:5000

### 自動巡回クローラ
```powershell
python main.py
```

## ディレクトリ構成
- `app.py`: Streamlit Webアプリケーション
- `main.py`: 自動巡回・一括抽出スクリプト
- `config.py`: アプリ共通設定
- `ocr/`: OCR処理モジュール
- `database/`: DBモデルおよびリポジトリ
- `services/`: ビジネスロジック
- `utils/`: 共通ユーティリティ (ロガー等)
- `docs/`: 実装計画書およびマニュアル
