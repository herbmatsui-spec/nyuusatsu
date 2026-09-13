# 品質モニタリング運用ドキュメント

## 指標定義

| 指標 | 意味 | 単位 | 正常範囲 |
|------|------|------|----------|
| `missing_field_rate` | 必須フィールド欠損率 | % | 0-50%（警告値50%） |
| `duplicate_rate` | 重複率 | % | 0-25%（警告値10%） |
| `acquisition_delay_median` | 公開日からDB登録までの遅延中央値 | 分 | 0-1440min（警告値1440min=24時間） |
| `coverage_rate` | クロール済み件数の比率 | % | 0-100%（警告値20%） |
| `coverage_municipality_rate` | 対象自治体カバレッジ率 | % | 0-100%（警告値20%） |
| `geps_crawler_success_rate` | GEPSクロール成功率 | % | 90%以上（警告値90%） |
| `geps_selector_match_rate` | GEPSセレクタマッチ率 | % | 90%以上（警告値90%） |
| `daily_new` | 日次の新規件数変化 | 件 | 0件未満（警告値0） |
| `daily_updated` | 日次の更新件数変化 | 件 | 0件未満（警告値0） |

## 閾値設定

品質閾値は `config/quality_thresholds.yaml` で管理されています。

### 警告・Critical値

| 指標 | warning | critical | lower_is_worse |
|------|---------|----------|----------------|
| `missing_field_rate` | 50.0 | 80.0 | false |
| `duplicate_rate` | 10.0 | 25.0 | false |
| `acquisition_delay_median` | 1440.0 | 4320.0 | false |
| `coverage_rate` | 20.0 | 10.0 | true |
| `coverage_municipality_rate` | 20.0 | N/A | - |
| `geps_crawler_success_rate` | 90.0 | 80.0 | true |
| `geps_selector_match_rate` | 90.0 | 80.0 | true |
| `daily_new` | 0.0 | 0.0 | true |
| `daily_updated` | 0.0 | 0.0 | true |

## アラート対応フロー

1. **メトリクス収集** (毎日 05:30)
   - `scripts/collect_quality_metrics.py` 実行
   - `scheduler.py` の `collect_quality_metrics_job` が動作確認

2. **アラート評価** (毎日 05:45)
   - `scripts/evaluate_quality_alerts.py` 実行
   - しきい値を超過しているか判定
   - 該当する場合、Slack/LINE に通知

3. **通知チャネル**
   - **Slack**: `SLACK_WEBHOOK_URL` が設定されている場合に送信
   - **LINE**: `LINE_CHANNEL_ACCESS_TOKEN` と `LINE_USER_ID` が設定されている場合に送信

4. **重複抑制**
   - Redis キー `alert_sent:{metric}:{date}` (24h TTL) で同日一回のみ通知
   - 24時間経過後に再通知可能

5. **履歴保存**
   - DB `QualityAlert` モデル に記録
   - `metric`, `level`, `value`, `threshold`, `sent_at` フィールドを保持

## ダッシュボードの見方 (app_dashboard.py)

1. サイドメニューから `🏢 データ品質` → `📊 品質メトリクス` を選択
2. 過去30日間のメトリクス推移グラフ (Plotly) が表示されます
3. 各指標に `warning` (黄色) および `critical` (赤色) の閾値ラインが重なります
4. グラフ上に現在の実測値がポイントで表示されます
5. メトリクス名をクリックすると詳細モーダルで閾値・実測値・通知先を確認できます

## 手動実行コマンド

```bash
# 品質メトリクス収集
python scripts/collect_quality_metrics.py

# 期間指定で過去分再収集
python scripts/collect_quality_metrics.py --date-range 2024-01-01 2024-01-31

# アラート評価
python scripts/evaluate_quality_alerts.py
```

## トラブルシューティング

- アラートが届かない場合: Redis が稼働しているか、Slack/LINE のシークレットが設定されているか確認
- メトリクスデータが空の場合: 品質メトリクス収集ジョブ (05:30) が正常に実行されているか確認
- しきい値の見直し: `config/quality_thresholds.yaml` を編集して再デプロイ