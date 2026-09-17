# 改善案10：統一検索CSVにLLM抽出4項目を追加（最新検証済み）

作成日: 2026-09-17。以下は2026-09-17時点の実測に基づく小さな差分計画。前提として正確な現状:

- `app_unified_search.py:139-144` の `CSV_COLUMNS` は4項目（id/title/organization/announcement_date）。
- `app_unified_search.py:13-31` の表示 `COLUMNS` は抽出4項目を含む8列で、ヘルプに「税抜」と記載（`:19`、`:100`）。
- `services/search_service.py:124-133` の results は抽出4項目を返す。
- `tests/unit/test_unified_search_ui.py:88` は4列ヘッダーを期待し、`:116` の安全化テストは合格（本日検証、全50件合格）。

## 実装手順

### ステップ 1: CSV_COLUMNSへ4項目を追加
- 対象: `app_unified_search.py:139-144`。
- 作業: `budget_amount`→「予算額（円）」、`qualification_requirements`→「資格要件」、`delivery_deadline`→「納期限」、`deliverables`→「成果物」を順に追加。表示列名（`:18-30`）と同じ語にする。
- 確認: 表示ヘッダーとCSVヘッダーの名前差分がゼロ。
- 工数目安: 0.5〜1時間。

### ステップ 2: 日付整形を納期限へ一般化
- 対象: `app_unified_search.py:155-156`。
- 作業: `announcement_date` 固定の分岐を `delivery_deadline` も対象にした共通分岐へ変更（date型をISO文字列化）。
- 確認: 両日付列がISO形式、Noneは空文字。
- 工数目安: 0.5時間。

### ステップ 3: 税抜表記の是正
- 対象: `app_unified_search.py:19`、`:100`。
- 作業: 「税抜」の断定を「税区分は出典未確認」へ変更。ヘルプ例・キャプションを修正。
- 確認: UI文言に「税抜」が残らない。
- 工数目安: 0.5時間。

### ステップ 4: テスト更新
- 対象: `tests/unit/test_unified_search_ui.py:88`、`:116-126`。
- 作業: 期待ヘッダーを8列へ、fixtureに抽出値（1000000 / None / 日付 / 改行成果物 / `=`開始文字列）を追加。
- 確認: 8列ヘッダー、NULLと0の区別、数式無効化・BOMが保持される。
- 工数目安: 1〜2時間。

### ステップ 5: 回帰と完了
- コマンド（実行済みと同じ隔離方法）:
  ```bash
  PYTHONDONTWRITEBYTECODE=1 DATABASE_URL=sqlite:///:memory: python -m pytest --noconftest -p no:cacheprovider -o addopts= -q tests/unit/test_unified_search_ui.py
  ```
- 確認: 全件合格、表示とCSVの列差ゼロ、DBや外部サービス不要。
- 工数目安: 0.5〜1時間。

合計工数目安: 3〜5時間。
