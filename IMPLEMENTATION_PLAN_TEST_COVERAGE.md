# テストカバレッジ率向上 実装計画書

## 1. 現状分析

### 1.1 現在のカバレッジ状況
- **全体カバレッジ: 0%** (主要モジュールすべてで 0% )
- テスト対象: `crawler/`, `services/`, `repositories/`, `queue/` の4ディレクトリ
- 既存テスト: 約73テストファイル存在するが、カバレッジ計測対象モジュールをインポートしていないため0%

### 1.2 主要モジュール数
| ディレクトリ | ファイル数 | 総ステートメント数 |
|------------|-----------|-------------------|
| crawler/ | ~25 | ~1,100 |
| services/ | ~75 | ~5,500 |
| repositories/ | 3 | ~200 |
| queue/ | ~10 | ~600 |
| **合計** | **~113** | **~7,400** |

### 1.3 既存テストの課題
- テストファイルが存在しても、実装モジュールをテストしていない
- `pytest.ini` の `--cov` 設定に `services`, `repositories`, `queue` が含まれていない
- 多くのテストが統合テスト/E2Eテスト寄りで、ユニットテストが不足

---

## 2. 目標設定

### 2.1 カバレッジ目標
| フェーズ | 目標カバレッジ | 期間 |
|---------|--------------|------|
| Phase 1 (即時) | **30%** | 1週間 |
| Phase 2 (短期) | **60%** | 3週間 |
| Phase 3 (中期) | **80%** | 6週間 |
| Phase 4 (継続) | **90%+** | 継続的 |

### 2.2 品質目標
- **ブランチカバレッジ**: 80%以上
- **クリティカルパス**: 100% (決済、認証、データ整合性)
- **新規コード**: 100% カバレッジ必須 (CI で強制)

---

## 3. 実装アプローチ

### 3.1 優先度マトリクス

| 優先度 | モジュール | 理由 | 推定工数 |
|-------|-----------|------|---------|
| **P0 (Critical)** | `services/qualification_matcher.py` | ビジネスロジック核心、バグ影響大 | 3日 |
| **P0** | `services/bid_normalizer.py` | データ正規化の基盤 | 2日 |
| **P0** | `services/forecast_dedup_service.py` | 重複排除ロジック | 2日 |
| **P0** | `crawler/detail_extractor.py` | 入札情報抽出の核心 | 3日 |
| **P0** | `crawler/parsers/*.py` | パーサー群、バグ混入リスク高 | 5日 |
| **P1 (High)** | `services/qualification_normalizer.py` | 資格正規化 | 2日 |
| **P1** | `services/grade_matcher.py` | グレードマッチング | 2日 |
| **P1** | `repositories/*.py` | DB操作層 | 3日 |
| **P1** | `queue/tasks/*.py` | 非同期タスク処理 | 4日 |
| **P2 (Medium)** | `services/llm_service.py` | LLM連携 | 3日 |
| **P2** | `services/crawl_scheduler.py` | スケジューラ | 3日 |
| **P2** | `services/notification_service.py` | 通知機能 | 2日 |
| **P3 (Low)** | 残りのサービス・クローラー | 段階的改善 | 継続 |

---

## 4. 詳細実装計画

### Phase 1: 基盤整備と即効性の高いモジュール (Week 1)

#### 4.1.1 pytest設定の修正
```ini
# pytest.ini 更新
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
python_classes = Test*
addopts = -v --cov=crawler --cov=services --cov=repositories --cov=queue --cov-report=term-missing --cov-fail-under=30 --no-cov-on-fail
asyncio_mode = auto
```

#### 4.1.2 共通テストユーティリティの整備
- `tests/conftest.py` に共通フィクスチャ追加
- `tests/factories/` - ファクトリーパターンでテストデータ生成
- `tests/mocks/` - 既存モックの整理・拡充

#### 4.1.3 P0モジュールのユニットテスト作成

**`services/qualification_matcher.py` (90行)**
- テストケース: 15-20ケース
- 正常系: 完全一致、部分一致、キーワードマッチ
- 異常系: 空入力、None、不正データ
- 境界値: 閾値ギリギリ、大量データ

**`services/bid_normalizer.py`**
- 正規化ルールごとのテスト
- 企業名正規化、金額正規化、日付正規化

**`crawler/detail_extractor.py` (223行)**
- 各抽出メソッドの個別テスト
- HTMLフィクスチャを用いた統合テスト
- 正規表現パターンの網羅的テスト

#### 4.1.4 CI/CDパイプラインへの組み込み
- GitHub Actions でカバレッジチェック必須化
- PR でカバレッジ低下時はマージブロック

---

### Phase 2: コアビジネスロジックの網羅 (Week 2-3)

#### 4.2.1 サービス層の体系的テスト

**リポジトリ層 (3ファイル)**
```python
# tests/repositories/test_forecast_repository.py
- CRUD操作の全メソッド
- トランザクション境界テスト
- クエリビルダーの条件分岐
```

**キュー/タスク層 (10ファイル)**
```python
# tests/queue/tasks/test_crawl_tasks.py
- タスク実行フロー
- リトライロジック
- エラーハンドリング
- べき等性確認
```

**パーサー群 (crawler/parsers/)**
- 各パーサーの `parse()` メソッド
- 入力バリエーション (HTML, PDF, JSON)
- エラーケース (不正フォーマット、欠損フィールド)

#### 4.2.2 モック戦略の統一
- 外部依存: `responses` / `httpx_mock` / `pytest-mock`
- DB: SQLite in-memory + トランザクションロールバック
- LLM: 事前定義レスポンスによるモック
- ブラウザ: Playwright モック / HTMLフィクスチャ

#### 4.2.3 パラメータ化テストの活用
```python
@pytest.mark.parametrize("input_text,expected", [
    ("予算額：1,000,000円", "1,000,000円"),
    ("予定価格 500万円", "500万円"),
    # ... 20+ ケース
])
def test_extract_budget_variations(extractor, input_text, expected):
    assert extractor.extract_budget(input_text) == expected
```

---

### Phase 3: 統合テストとE2Eテストの強化 (Week 4-6)

#### 4.3.1 パイプライン統合テスト
```python
# tests/integration/test_forecast_pipeline.py
- 全フェーズ通しテスト
- データフロー検証
- エラー時の補償トランザクション
```

#### 4.3.2 クローラー統合テスト
- HTMLフィクスチャを用いた実クロールシミュレーション
- ページネーション、レート制限、プロキシ切替の検証

#### 4.3.3 パフォーマンステスト
- 大量データ処理時のメモリ/CPU
- 並列処理時の競合・デッドロック検出

---

## 5. テスト戦略とベストプラクティス

### 5.1 テストピラミッドの適用
```
        /\
       /  \  E2Eテスト (少数・高コスト)
      /----\
     /      \  統合テスト (中程度)
    /--------\
   /          \ ユニットテスト (多数・低コスト・高速)
  /------------\
```

**目標比率**: Unit 70% : Integration 20% : E2E 10%

### 5.2 命名規則
| 種別 | 命名パターン | 例 |
|------|-------------|-----|
| ユニット | `test_<module>_<function>_<scenario>` | `test_qualification_matcher_match_exact` |
| 統合 | `test_integration_<flow>_<scenario>` | `test_integration_forecast_crawl_to_db` |
| E2E | `test_e2e_<feature>_<scenario>` | `test_e2e_bid_registration_to_notification` |

### 5.3 テストデータ管理
- `tests/fixtures/` - 静的フィクスチャ (HTML, JSON, PDF)
- `tests/factories/` - 動的データ生成 (factory_boy 推奨)
- 本番データの匿名化サンプルをフィクスチャ化

### 5.4 アサーション戦略
- **1テスト1アサーション** 原則 (複数可だが関連するもののみ)
- ハードコード値避け: 期待値は定数/フィクスチャから
- エラーメッセージ検証: `pytest.raises(..., match="...")`

---

## 6. ツール・ライブラリ導入

### 6.1 必須ツール
| ツール | 用途 | 導入コマンド |
|--------|------|-------------|
| `pytest-cov` | カバレッジ計測 | 既存 |
| `pytest-mock` | モック作成 | `pip install pytest-mock` |
| `factory-boy` | テストデータ生成 | `pip install factory-boy` |
| `faker` | ダミーデータ生成 | `pip install faker` |
| `responses` | HTTPモック | `pip install responses` |
| `pytest-asyncio` | 非同期テスト | 既存 |
| `pytest-xdist` | 並列実行 | `pip install pytest-xdist` |

### 6.2 開発支援ツール
| ツール | 用途 |
|--------|------|
| `coverage-badge` | README用バッジ生成 |
| `pytest-html` | HTMLレポート出力 |
| `mutmut` | ミューテーションテスト (Phase 3+) |

---

## 7. 実行スケジュール

### Week 1: 基盤整備
| 日 | タスク | 担当 | 成果物 |
|----|--------|------|--------|
| Mon | pytest.ini修正、共通フィクスチャ整備 | - | 設定ファイル更新 |
| Tue | qualification_matcher テスト作成 | - | test_qualification_matcher.py |
| Wed | bid_normalizer テスト作成 | - | test_bid_normalizer.py |
| Thu | detail_extractor テスト作成 | - | test_detail_extractor.py (拡充) |
| Fri | パーサー群テスト開始、CI設定 | - | CI設定、テスト雛形 |

### Week 2: サービス層コア
| 日 | タスク | 成果物 |
|----|--------|--------|
| Mon | forecast_dedup_service テスト | test_forecast_dedup_service.py |
| Tue | qualification_normalizer テスト | test_qualification_normalizer.py |
| Wed | grade_matcher テスト | test_grade_matcher.py |
| Thu | repositories テスト | test_forecast_repository.py 等 |
| Fri | queue/tasks テスト開始 | test_crawl_tasks.py 等 |

### Week 3: 残りP1/P2モジュール
| 日 | タスク |
|----|--------|
| Mon-Tue | llm_service, crawl_scheduler |
| Wed-Thu | notification_service, pdf_processor |
| Fri | 統合テスト開始、カバレッジ確認 |

### Week 4-6: 統合・E2E・仕上げ
- 統合テストシナリオ作成
- パフォーマンステスト
- カバレッジ80%達成確認
- ドキュメント整備

---

## 8. 進捗管理・品質ゲート

### 8.1 週次レビュー項目
- [ ] カバレッジ推移 (目標値とのギャップ)
- [ ] 新規テストケース数
- [ ] バグ検出数 (テストによる発見)
- [ ] フレーキーテスト有無
- [ ] 実行時間推移

### 8.2 品質ゲート (CIで強制)
```yaml
# .github/workflows/test.yml 抜粋
- name: Coverage Check
  run: |
    pytest --cov=crawler --cov=services --cov=repositories --cov=queue \
           --cov-fail-under=30  # Phase 1: 30%, Phase 2: 60%, Phase 3: 80%
```

### 8.3 メトリクスダッシュボード
- Coverage Trend (週次)
- Test Execution Time
- Flaky Test Rate
- Defect Detection Rate

---

## 9. リスクと対策

| リスク | 影響度 | 対策 |
|--------|-------|------|
| 既存コードのテスタビリティ低い | 高 | リファクタリング並行実施、DI導入 |
| 外部API依存でテスト不安定 | 中 | 完全モック化、契約テスト導入 |
| テスト実行時間増大 | 中 | 並列実行、テスト分類(quick/slow) |
| メンテナンスコスト増大 | 中 | 共通ユーティリティ化、DRY原則 |
| カバレッジ数値だけ追う | 低 | ミューテーションテストで実効性検証 |

---

## 10. 成功基準 (Definition of Done)

### Phase 1 完了条件
- [ ] 全体カバレッジ 30% 以上
- [ ] P0モジュール 80% 以上
- [ ] CI でカバレッジゲート動作
- [ ] フレーキーテスト 0件

### Phase 2 完了条件
- [ ] 全体カバレッジ 60% 以上
- [ ] P1モジュール 80% 以上
- [ ] 統合テスト 10シナリオ以上
- [ ] 実行時間 5分以内 (並列込み)

### Phase 3 完了条件
- [ ] 全体カバレッジ 80% 以上
- [ ] ブランチカバレッジ 70% 以上
- [ ] E2Eテスト 主要フロー 100%
- [ ] ミューテーションスコア 60% 以上

---

## 11. 付録: モジュール別テスト作成チェックリスト

### crawler/ (25ファイル)
- [ ] base_crawler.py
- [ ] award_base_crawler.py
- [ ] award_list_crawler.py
- [ ] detail_extractor.py ✅ (既存・拡充)
- [ ] downloader.py
- [ ] forecast_base_crawler.py
- [ ] forecast_list_crawler.py
- [ ] forecast_pdf_crawler.py
- [ ] forecast_parallel_crawler.py
- [ ] generic_crawler.py
- [ ] generic_award_crawler.py
- [ ] config_driven_crawler.py
- [ ] geps_crawler.py / geps_crawler_updated.py
- [ ] pipeline.py
- [ ] pagination.py
- [ ] exceptions.py
- [ ] parsers/ (15ファイル)
- [ ] utils/ (10ファイル)
- [ ] hokkaido/, tokyo/, osaka/, geps/ (地域別)

### services/ (75ファイル) - 主要のみ抜粋
- [ ] qualification_matcher.py (P0)
- [ ] bid_normalizer.py (P0)
- [ ] forecast_dedup_service.py (P0)
- [ ] qualification_normalizer.py (P1)
- [ ] grade_matcher.py (P1)
- [ ] llm_service.py (P2)
- [ ] crawl_scheduler.py (P2)
- [ ] notification_service.py (P2)
- [ ] forecast_collection_service.py
- [ ] forecast_validator.py
- [ ] pipeline_service.py
- [ ] analysis_service.py
- [ ] bid_service.py
- [ ] award_pipeline.py
- [ ] 他 50+ ファイル

### repositories/ (3ファイル)
- [ ] forecast_repository.py
- [ ] agency_inventory_repository.py

### queue/ (10ファイル)
- [ ] tasks/crawl_tasks.py
- [ ] tasks/pdf_tasks.py
- [ ] tasks/ocr_tasks.py
- [ ] tasks/analysis_tasks.py
- [ ] tasks/notification_tasks.py
- [ ] enqueue.py
- [ ] rq_config.py
- [ ] queues.py
- [ ] retry_config.py

---

## 12. 最初のアクションアイテム (今すぐ開始)

1. **pytest.ini 修正** - `--cov=services --cov=repositories --cov=queue --cov-fail-under=10` 追加
2. **tests/conftest.py 拡充** - 共通フィクスチャ、モックヘルパー追加
3. **qualification_matcher テスト作成** - 最優先P0モジュール
4. **GitHub Actions ワークフロー作成** - カバレッジチェック自動化

---

*作成日: 2026-09-10*
*バージョン: 1.0*
*ステータス: 実装待ち*