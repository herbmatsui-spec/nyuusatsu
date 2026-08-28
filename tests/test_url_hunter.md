# url_hunter テスト計画書

## 目的
`url_hunter.py` が正常に入札情報を収集・判定できるか検証する。

## テスト手順
1. **環境準備**: `requirements.txt` のインストールと `playwright install` を完了させる。
2. **キー設定**: `.env` に `GEMINI_API_KEY` を配置。
3. **テスト実行**:
   ```bash
   python url_hunter.py --query "宇和島市 入札情報"
   ```
4. **結果確認**: `url_hunter_result.json` が生成され、内容が妥当か確認する。

## テスト項目
- [ ] 検索結果が正しく取得できるか
- [ ] 各ページの HTML 解析が成功するか
- [ ] Gemini が入札一覧ページ URL を正しく抽出できるか
- [ ] 結果が JSON として正しく保存されるか
- [ ] タイムアウトやネットワークエラー発生時にスクリプトが止まらないか
