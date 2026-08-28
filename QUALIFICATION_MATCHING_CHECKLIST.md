# 全省庁統一資格・地域別ランク 実装チェックリスト

## 前提確認
- [ ] Alembicマイグレーション `d4e5f6a7b8c9` が適用済み
- [ ] Python 環境の再起動（モデル変更後）

---

## Phase 1: 企業プロファイル・資格モデル（1-10）

### データベース確認
- [ ] `company_profiles` テーブルが存在すること
- [ ] `company_region_ranks` テーブルが存在すること
- [ ] `qualification_tags.grade_required` カラムが存在すること
- [ ] `bid_qualification_tags.required_grade` カラムが存在すること

### 初期設定
- [ ] `python scripts/seed_company_profile.py` を実行して自社プロファイルを作成
- [ ] 自社プロファイルに全省庁統一資格等级（A/B/C/D）を登録
- [ ] 主要な都道府県の地域等级を追加

---

## Phase 2: 全省庁統一資格等级サポート（11-20）

### 手動テスト
- [ ] `python -c "from services.grade_matcher import can_apply; print(can_apply('A', 'B'))"` → `True` が出力
- [ ] `python -c "from services.grade_matcher import can_apply; print(can_apply('D', 'A'))"` → `False` が出力
- [ ] `python scripts/update_qualification_grades.py` を実行

### テスト実行
- [ ] `python -m pytest tests/test_grade_matcher.py -v` がパスすること

---

## Phase 3: 地域别ランクサポート（21-30）

### 手動テスト
- [ ] `python -c "from services.region_rank_matcher import get_region_block_for_prefecture_code; print(get_region_block_for_prefecture_code('13'))"` → `東京都` が出力
- [ ] ダッシュボード「🏢 自社資格」にアクセスし「地域别資格等级」タブで東京都に等级「A」を設定

---

## Phase 4: 資格マッチングエンジン（31-40）

### 手動テスト
- [ ] `python -c "from services.qualification_matcher import QualificationMatcher; print('OK')"` がパス
- [ ] 企業プロファイルが登録済みであること

---

## Phase 5: ダッシュボードUI統合（41-50）

### 確認項目
- [ ] `streamlit run app_dashboard.py` でアプリが起動すること
- [ ] サイドメニューに「🏢 自社資格」が表示されていること
- [ ] 「🏢 自社資格」ページで全省庁統一資格等级が登録・編集できること
- [ ] 「🔍 検索」ページで全省庁统一資格等级フィルタが表示されること（次ステップで実装）

---

## Phase 6: 自動タグ生成パイプライン（51-60）

### 確認項目
- [ ] `python scripts/verify_qualification_tags.py` を実行し、出力結果を確認
- [ ] Bid.qualificationsがNULLではないがBidQualificationTagが0件のBIDがある場合、不足分が報告されること

### 自動生成
- [ ] `services/bid_qualification_tagger.py` の `batch_tag_all()` メソッドが動作すること（要実装確認）

---

## Phase 7: 資格マッチアラート機能（61-68）

### 確認項目
- [ ] AlertManagerに `evaluate_qualification_alert()` メソッドが追加されていること（要コード確認）
- [ ] 応募可能案件が登録された際の通知設定が「🔔 通知設定」に存在すること（要実装）

---

## Phase 8: 運用・品質監視（69-72）

### 確認項目
- [ ] `python scripts/generate_qualification_report.py` を実行し、レポートが出力されること
- [ ] HealthCheckerに `check_qualification_system()` が追加されていること

---

## ダッシュボード機能 最終確認

1. `streamlit run app_dashboard.py`
2. 「🏢 自社資格」→ 等級「B」を登録、都道府県「東京都」に等级「A」を登録
3. 「🔍 検索」→ 「全省庁統一資格等级」で「B」を選択
4. 「🏢 自社資格」でダッシュボードに遷移し、データが表示されること

---

## トラブルシューティング

| 現象 | 確認事項 |
|------|----------|
| `company_profiles` テーブルがない | `python -m alembic upgrade head` を実行 |
| 等级マッチングが動作しない | 自社プロファイルの `unified_qualification_grade` が NULL でないことを確認 |
| 地域等级が反映されない | `company_region_ranks` テーブルに prefecture_code が正しく登録されているか確認 |
| ダッシュボードがエラー | `streamlit run app_dashboard.py` のエラーコンソールを確認し不足ライブラリをインストール |

---

*このチェックリストは実装完了後に使用し、各項目を順番に検証してください。*