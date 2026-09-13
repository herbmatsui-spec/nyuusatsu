# 低性能LLM向け実装完了チェックリスト

## P1: DB統合 (ステップ 1-24)
- [ ] db_manager.py がSQLAlchemyモデルに移行済み
- [ ] CrawlHistory, CrawledUrl, Settings モデルが定義済み
- [ ] 基本的なエンジンとセッション管理が実装済み

## P2: 品質メトリクス改善 (ステップ 25-48)
- [ ] quality_metrics_service.py にコメントが追加済み
- [ ] 各メソッドのロジックが理解しやすい状態
- [ ] acquisition_delay_median 等の複雑関数に最適化の予定が示されている

## P3: クローラー改善 (ステップ 49-72)
- [ ] base_crawler.py に非同期化の準備が完了
- [ ] award_crawler.py にセッター外部化の準備が完了
- [ ] 設定ファイルの雛形が docs/ ディレクトリに作成済み
- [ ] 基本的なテストファイルが作成済み

## 次のステップ
- 実際の設定ファイルを crawler/config/ にコピー
- 段階的に非同期機能を実装
- 段階的に設定可能なセッターを実装
- パフォーマンス最適化（特に acquisition_delay_median）を実装