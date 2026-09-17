# モバイルUI 実装の収束計画（2026-09-17）

## 背景
- 改善案5（モバイルファーストUI）のステップ1〜12は実装済み（15テスト成功、README追記済み）。
- ただし現時点で計画範囲外の状態が残っている: `app_mobile.py` に第5タブ「競合分析」が存在（改善案5の計画は4タブ。テストも4タブ前提）。
- README の採番編集を複数回繰り返した履歴あり → **以後の化粧的編集は禁止**し、本計画の検証のみ行う。

## 目標
計画範囲（4タブ）への整合と、最終検証の一括実行・収束。

## ステップ（各ステップ後に検証し、失敗時のみ修正）

### Step A: 現状の事実確認（読み取りのみ）
- `python -m unittest tests.unit.test_mobile_ui tests.unit.test_mobile_ui_service` を実行し、現在の合否を記録。
- `git diff --stat` で変更対象ファイルを一覧化。
- 判定基準: 「競合分析」タブの有無でテストが落ちるか、落ちないかを事実として確認。

### Step B: 計画範囲外要素の处置（1回のみ・検証付き）
- 判定: 改善案5は「検索／マイ検索／お知らせ／設定」の4タブと明記しているため、**第5タブ「競合分析」は削除**する。
  - 理由: 未検証の追加機能を計画の完了宣言に含めることはテスト虚偽装備（False Confidence）になる。
  - `render_competitive_analysis` / TABSから削除し、main の切替辞書からも削除。
  - 競合分析は `app_dashboard.py` 等の既存画面で既に提供されているため、モバイルからは別計画（改善案9）で扱う。
- 検証: `python -m unittest tests.unit.test_mobile_ui tests.unit.test_mobile_ui_service` で15テスト全成功を確認。失敗した場合のみその失敗原因を修正。

### Step C: 最終検証（編集禁止・1回ずつ）
1. モバイル全スイート: `python -m unittest tests.unit.test_mobile_ui tests.unit.test_mobile_ui_service -v` → 15テスト成功。
2. 構文・lint: `python -m py_compile app_mobile.py services/mobile_ui_service.py` および `python -m pyflakes` 対象4ファイル → エラー0。
3. 変更範囲確認: `git diff --stat`（app_mobile.py / services/mobile_ui_service.py / static/css/mobile.css / tests/unit/test_mobile_ui*.py / README.md / plans/ 本計画ファイルのみ増減）。
4. README の状態確認: `grep -n '^### [0-9]' README.md` を表示するのみ。**採番の再編集は行わない**（現状は起動方法節内で1〜10が連続しており問題なしと判断）。

### Step D: 完了報告
- 上記の証拠（テスト結果・lint結果・diff一覧）を添えてサマリーを提示し、編集作業を終了する。

## 範囲外（明示的に実施しない）
- README 採番の再調整、CSS 調整、追加機能の実装、既存スクリプト（unittest discover ルート直下6件）の修復、mypy のインストール。
