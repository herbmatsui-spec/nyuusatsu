# 本番GEPSクローラーテスト (test_geps_live)

## 概要

本番GEPSクローラーテストスイートは、オープンソースの政府調達サイト（GEPS）の動作テストに特化しています。既存のモックベースのテスト（test_geps_crawler/）を補完し、実際のクローラーコンポーネントの統合と本番環境での動作を確認します。

## 特徴

- **72段階分割**: 実動作テストを段階的に実施し、本番環境での精度を低性能LLMでも実現可能にします
- **環境ベースのスキップ**: `GEPS_SKIP_LIVE=true` または `GEPS_LIVE_URL` を設定で無効化可能
- **パフォーマンス追跡**: 各テストの実行時間と結果の統計
- **プロセス終了時のレポート**: `atexit` によるテスト概要
- **I: ドライブフリーズ対応**: テストランナーは C: ドライブから実行を推奨

## ディレクトリ構造

```
tests/test_geps_live/
  │
  ├─ conftest.py                    # 共通フィクスチャとヘルパー
  ├─ README.md                       # 本ファイル
  │
  ├─ Phase 0: 001_01_connectivity_test.py          # Steps 6-12: HTTP接続テスト
  ├─ Phase 1: 001_02_browser_init_test.py           # Steps 13-18: Playwright初期化
  ├─ Phase 1: 001_03_navigation_test.py             # Steps 19-24: ナビゲーション
  ├─ Phase 1: 001_04_html_parsing_test.py           # Steps 25-30: HTMLパース
  ├─ Phase 1: 001_05_geps_extract_test.py            # Steps 31-36: GEPS検索結果抽出
  ├─ Phase 1: 001_06_pagination_test.py             # Steps 37-41: ページネーション
  ├─ Phase 1: 001_07_download_test.py               # Steps 42-46: PDFダウンロード
  ├─ Phase 2: 002_01_error_handling_test.py         # Steps 47-52: エラーハンドリング
  ├─ Phase 2: 002_02_performance_benchmark_test.py  # Steps 53-56: パフォーマンス
  ├─ Phase 3: 003_01_pipeline_test.py              # Steps 57-62: パイプライン連携
  ├─ Phase 3: 003_02_real_data_test.py              # Steps 63-68: 実データ検証
  ├─ Phase 4: 004_01_integration_test.py           # Steps 69-72: 最終統合
  │
  └─ scripts/
      ├─ run_live_tests.py              # 本番テスト実行スクリプト
      └─ report_generator.py            # テストレポート生成
```

## 実行方法

### 方法1: 自動テストランナー（推奨）

```powershell
# C: ドライブから実行
C:\Users\%USERNAME%\>
python "I:\入札システム\tests\test_geps_live\scripts\run_live_tests.py" --phase 1-5

# 本番環境アクセスをスキップ
C:\Users\%USERNAME%\>
python "I:\入札システム\tests\test_geps_live\scripts\run_live_tests.py" --no-live

# 特定のフェーズのみ実行
C:\Users\%USERNAME%\>
python "I:\入札システム\tests\test_geps_live\scripts\run_live_tests.py" --phase 34-68
```

### 方法2: 直接pytest実行

```powershell
# 各本番テストディレクトリを実行（推奨しない）
cd C:\Users\%USERNAME%
set GEPS_LIVE_URL=https://www.geps.go.jp
python -m pytest "I:\入札システム\tests\test_geps_live" -v --no-cov
```

## 重要設定

| 環境変数 | 説明 | デフォルト |
|------------|-------------|----------|
| `GEPS_LIVE_URL` | 本番GEPSサイトのベースURL | `https://www.geps.go.jp` |
| `GEPS_TEST_TIMEOUT` | 各テストのタイムアウト値（秒） | `30` |
| `GEPS_SKIP_LIVE` | テスト全体をスキップ (`true`, `1`, `yes`) | なし |

## ファイル命名規則

- `test_< PHASE >_< NUMBER >_< DESCRIPTION > .py`
- フェーズ番号: `001` (接続性開始) → `004` (最終統合)
- 番号はフェーズ内1から始まる
- 例: `test_001_01_connectivity_test.py`

## テスト結果

本番テストの実行後、同じセクションで概要が表示されます:

```
============================================================
本番テスト概要
============================================================
総実行テスト数: 42
成功: 38
失敗: 3
スキップ: 1
開始時間: 2026-07-11 11:47:00.123456
所要時間: 67.89 秒
============================================================
```

## ライセンス

本テストファイルはGEPSクローラープロジェクトの下にあります。
