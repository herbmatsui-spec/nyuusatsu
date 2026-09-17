# 改善案09: 競合分析の説明可能性とアクセス境界を整えるMVP

## 2026-09-17 旧計画の評価（実ソース再確認）

旧計画の「類似度・難易度・勝率サービスを新規作成する」は現状に合わない。多くが実装済みであり、まず情報漏洩の防止とスコアの意味を正す。ルール値を勝率として校正済みと誤認させないことをMVPの中心にする。以下は静的確認であり、統計的妥当性・性能の検証済みを意味しない。

|区分|実ソースの根拠|判断|
|---|---|---|
|既存・再利用|`services/text_similarity_service.py:77-85` はclean/raw/成果物/資格のフォールバック、`:157-199` はTF-IDFの疎行列構築|前処理・ベクトル化を新規実装しない。既存の `services/similarity_preprocess.py` を維持する。|
|日本語対応は既存|`services/text_similarity_service.py:56-62` はanalyzer=char_wb、ngram_range=[2,5]|文字n-gramを新規提案せず、設定を明示して日本語fixtureで回帰確認する。|
|無制限読込が残る|`services/text_similarity_service.py:96-107` は全件all()後にfingerprint、`:163-165` は後段の日付絞込、`:218` は検索時にsnapshot|期間・権限・件数上限をSQL取得前に適用する。全件走査をキャッシュヒットの前提にしない。|
|アクセス境界不足|`services/text_similarity_service.py:141` と`:305` のcache keyに利用者権限がない。`:243` は直接ID参照。`services/specification_similarity_service.py:45-69` はユーザーscopeなし|候補・基準案件・集計・キャッシュを04のscopeで統一する。UIの地域選択だけでは不十分。|
|説明用メタデータは既存|`services/win_prediction_service.py:83-102` はscore_kindとconfidence、`services/bid_difficulty_scorer.py:129-139` はevidence_coverage|新しい信頼度計算器を作らず、欠落させずにUIまで通す。coverageは正答確率ではない。|
|表示までの欠落|`services/prediction_dashboard_service.py:58-74` はscore_kind/confidenceを返していない。`services/competitor_dashboard_page.py:127-148` は警告しつつ「予測勝率（参考）」を%表示|参考機会スコアへ変更し、欠測・根拠件数・未校正を常時表示する。|
|欠測のデフォルト値|`services/win_prediction_service.py:28-32`、`:123-156` は文脈不足時の仮定値、`services/bid_difficulty_scorer.py:117-128` は欠測に0.5を使用|仮定を観測事実にしない。計算不可の状態と寄与内訳を分離する。|
|自社文脈の危険|`services/prediction_dashboard_service.py:34-44` はシステム全体の自社名へfallback、`services/win_prediction_service.py:162-170` は全Competitorから照合|04のuser/orgに結び付く確認済み企業だけを使う。任意会社名や全体既定値で別組織情報を引かない。|
|予測値の永続化は対象外|`services/prediction_dashboard_service.py:148-149` は既存score列をsummaryへ含める。`services/text_similarity_service.py:334-367` はpickle入出力|全体共通の予測列を自社分析に流用しない。旧artifactはscope不明として利用しない。|

## 範囲・非目標・依存関係

- 今回の変更は本計画書のみ。以下は将来の実装手順。ソース・DB・migration・ベクトル再構築・外部LLM/API・バッチを自動実行しない。
- MVPは既存TF-IDFによる限定候補の類似表示、説明可能な難易度/参考機会スコア、欠測表示、権限境界、隔離テスト。既存サービスを差分改修し、新しい予測基盤を作らない。
- 03が真の観測済み履歴率を所有する。分母は確認された応札/結果であり、公開落札一覧全体を自社応札数にしない。分母不明は `insufficient_data`。09は03の値と根拠を消費し、観測率とヒューリスティックを混ぜない。
- 09の参考機会スコアは未校正の0〜100点。勝率・確率・成功保証ではない。既存 `score_kind=uncalibrated_rule_based_score` と `confidence.kind=evidence_coverage, calibrated=False` を保持する。ProcurementForecastは調達見通しであり、この分析の勝率予測データではない。
- 04の `utils/plan_gate.py`（既存・再利用予定）がactive user、features、地域集合、履歴範囲を解決する。空/未知のscopeは拒否。基準案件・候補・履歴集計・count・詳細・export・aggregateの前に適用し、user/org・policy versionをcache keyへ含める。09が独自のプラン表を作らない。
- 01の `services/search_criteria.py`（01で新規予定・09では作成しない）のSearchCriteria v1を案件選択の共通契約に使う。`keyword, exclude_keywords, use_or, prefecture, organization, bid_type, announcement_from/to`、prefecture値は2桁文字列、ページ応答は `results,total,offset,limit`。06の `budget_min/max, qualification_keywords, deadline_from/to, deliverables_keyword, sort_column/direction` を保持し、sortは許可リストのみ。raw予算の税区分は不明のまま扱う。
- 保存条件を利用する場合は `SavedSearch.criteria_json` が正本。legacy `mobile_ui/use_not` は01/02の明示変換のみを使い、条件を黙って捨てない。02の通知基盤や05の画面を09から変更しない。07への公開はMVP契約・scope検証完了後の依存作業。
- 非目標: 校正済み予測モデル、ANN/KD木、Embedding/外部LLM追加、夜間全件再計算、新しい学習データ収集、フィードバック送信、管理者による自由な重み変更、広告の「勝率予測」。これらは別の評価ゲートを満たしてから再計画する。
- 総工数目安: **40時間（実装・隔離テスト込み、03/04/01の実装・モデル研究・運用環境復旧は除外）**。各ステップ4時間以内。列挙するソース/テストは全て既存・再利用し、新規ファイルは本MVPでは予定しない。

## テスト実行前の必須条件

`tests/conftest.py:12-21` は永続 `tests/fixtures/test.db` を初期化する。通常のpytestをそのまま実行しない。ステップ1でtmp_path/インメモリDBと注入sessionを使い、clock/config/company context/外部サービスをfake化する。`.env` を読まず、HTTP・LLM・メール・本番DBを遮断してからテストする。`--noconftest` は対象テストの全fixture自立とimport安全性を確認した場合だけ使う。

### ステップ 1: 隔離fixtureと既存出力を固定
- **対象**: `tests/unit/test_text_similarity_service.py`、`tests/unit/test_win_prediction_service.py`、`tests/unit/test_prediction_dashboard_service.py`、`tests/unit/test_bid_difficulty_scorer.py`（既存・再利用）。
- **作業**:
  1. 各テストのsession/cache/config依存を読み、永続DBと既定pickleを利用する経路を列挙する。
  2. インメモリDBとtmp_path cache、固定時計2026-09-17、user A/org X/地域13とuser B/org Y/地域27を用意する。
  3. 日本語同一本文2件、無関係本文1件、空本文1件、scope外1件を作り、外部呼出しを失敗するfakeへ置換する。
- **確認**: 既定data/cacheとDBへの読書き0、`.env` 読込0、HTTP0。既存のscore_kind/confidenceキーをfixtureの期待値として記録する。
- **完了条件**: データの実取得や実設定読込なしで回帰検証できる。
- **工数目安**: 3時間（依存1、fixture1、確認1）。

### ステップ 2: 基準案件と候補のアクセス範囲
- **対象**: `services/specification_similarity_service.py`、`services/prediction_dashboard_service.py`、`services/text_similarity_service.py`、`tests/unit/test_specification_similarity_service.py`（既存・再利用）。
- **作業**:
  1. 04で解決済みのscopeを各サービスの入口に必須で受け取り、未解決時は拒否する。
  2. 基準案件ID・候補検索・最近の案件・地域/業種の選択肢取得に同じscopeを適用する。
  3. `_query_vector` の直接ID参照もscope付きとし、対象外IDから本文/存在有無を返さない。
- **確認**: Aが27の案件IDを指定しても類似結果・本文・タイトルを返さない。選択肢にscope外業種は出ない。inactive/空scopeは候補count前に拒否。地域未指定は全国許可を意味しない。
- **完了条件**: UIを介さないサービス呼出しでも基準案件と候補の両方を保護する。
- **工数目安**: 4時間（入口1、候補1、ID1、テスト1）。

### ステップ 3: 全件snapshotを限定SQLへ置換
- **対象**: `services/text_similarity_service.py:96-116`、`:201-230`、`tests/unit/test_text_similarity_service.py`（既存・再利用）。
- **作業**:
  1. `_snapshot` のSQLにscopeと履歴/要求期間の交差条件を適用してから必要列だけ取得する。
  2. MVPでは直近6か月・上限5000件を既定とし、公告日降順/ID降順の安定順にする。無制限指定は公開経路で拒否する。
  3. 上限超過を1件余分の取得で検知し、応答に候補件数・期間・打切り有無を含める。fingerprintは取得した限定候補だけで作る。
- **確認**: 5001件fixtureで取得行数は最大5001、比較対象5000、打切りtrue。7か月前とscope外の本文はベクトル化0件。0件なら空応答と理由で、全件再検索しない。
- **完了条件**: 全件all()後のフィルターがなく、選択範囲が結果の制約として表示可能。
- **工数目安**: 4時間（SQL1、上限1、応答1、テスト1）。

### ステップ 4: 権限を含むキャッシュと旧artifactの拒否
- **対象**: `services/text_similarity_service.py`、`tests/unit/test_text_similarity_service.py`（既存・再利用）。
- **作業**:
  1. artifact/resultの両キーにDB識別子、user/org、scopeの地域/履歴/features、policy version、期間、上限、TF-IDF設定版、候補更新指紋を含める。
  2. 失効・権限縮小・会社切替・本文変更で対応artifactを破棄し、同一権限キー以外と共有しない。
  3. scope情報のない旧pickleを読み込まない。MVPの要求経路ではディスクpickleの自動load/saveを停止し、プロセス内の上限付きcacheを使う。
- **確認**: Aで温めてもBのcache hitは0。policy v1→v2で旧結果なし。同一利用者/条件では再利用し、本文変更でスコアが再計算される。旧pickleを置いてもdeserialize呼出し0。
- **完了条件**: キャッシュが認可を迂回せず、信頼できないファイルを要求処理からloadしない。
- **工数目安**: 4時間（キー1、失効1、pickle停止1、テスト1）。

### ステップ 5: 日本語類似度の回帰と説明
- **対象**: `services/similarity_preprocess.py`、`services/text_similarity_service.py`、`tests/unit/test_similarity_preprocess.py`、`tests/unit/test_text_similarity_service.py`（既存・再利用）。
- **作業**:
  1. 既存前処理と文字n-gram設定を再利用し、本文の出典がclean/raw/成果物代替のどれかを結果に付ける。
  2. 空本文・短すぎる本文・空語彙を計算不可として分離し、類似度0と混同しない。
  3. sparse行列のまま上位10件を計算し、自己ID除外と同点時ID順を固定する。
- **確認**: 十分長い同一日本語本文2件の類似度は1.0±0.0001、無関係本文はそれより低い。空本文はinsufficient_data。自己IDは0件、同点結果のID順は毎回同じ。
- **完了条件**: 既存文字n-gramを置換せず、類似度は関連性の指標であって落札確率でないと説明できる。
- **工数目安**: 3時間（出典1、境界1、テスト1）。

### ステップ 6: 自社文脈と観測履歴率を分離
- **対象**: `services/win_prediction_service.py`、`services/prediction_dashboard_service.py`、`tests/unit/test_win_prediction_service.py`（既存・再利用）。03の観測履歴サービス（依存先）。
- **作業**:
  1. 自社を04のuser/orgに紐付く確認済み企業IDから選び、システム全体の既定会社名fallbackを分析経路から外す。
  2. 自社過去率は03の分子/分母/観測期間/不足状態を消費し、09独自の勝率集計を増やさない。
  3. 同機関の公開落札構成比は参考傾向として別ラベルにし、応札ベースの過去率へ転用しない。
  4. 基準案件より後の結果、scope外履歴、重複参加レコードを除外する契約を03のfakeで検査する。
- **確認**: 既知の応札10件・落札2件は観測率0.2。落札2件だけで応札分母不明ならinsufficient_data、1.0にしない。企業名衝突2件は未確定。Bの企業IDをAから指定しても拒否。
- **完了条件**: 観測履歴と機会スコアが別データで、任意企業名から他社の非公開文脈を取得しない。
- **工数目安**: 4時間（会社1、03接続1、時点/重複1、テスト1）。

### ステップ 7: スコアの欠測契約を固定
- **対象**: `services/win_prediction_service.py`、`services/bid_difficulty_scorer.py`、`tests/unit/test_win_prediction_service.py`、`tests/unit/test_bid_difficulty_scorer.py`（既存・再利用）。
- **作業**:
  1. 内部の未校正スコアを0〜100の参考機会点として返すアダプターを定義し、score_kind/calibrated=Falseを必須にする。既存win_rateキーの互換扱いは07と合意してから変更する。
  2. 各要因に実測/仮定/欠測、元値、weight、寄与、根拠件数を付ける。重みと欠測扱いを版管理し、全要因欠測ならscore=nullにする。
  3. 難易度の資格項目数/文字数は形式的負荷指標と表示し、参加資格判定・難易度の実証値と呼ばない。
- **確認**: 内部値0.4は40/100点であり40%ではない。全欠測はnull/insufficient_data、仮定値だけで推奨を出さない。weights合計1、寄与合計と表示点の差は丸め許容0.1以内。
- **完了条件**: デフォルト値を観測値として表示せず、根拠充足率をモデルの正解確率と呼ばない。
- **工数目安**: 3時間（契約1、欠測1、テスト1）。

### ステップ 8: メタデータを画面まで保持
- **対象**: `services/prediction_dashboard_service.py:46-74`、`tests/unit/test_prediction_dashboard_service.py`（既存・再利用）。
- **作業**:
  1. difficulty/opportunityの各結果にscore_kind、confidence、missing_factors、sample_counts、算出時点、設定版を欠落なく渡す。
  2. `_bid_summary` で予算不明を0へ変えずnullに保ち、全体共通のwin_prediction_scoreを自社結果に混ぜない。
  3. 未確定企業/取得不能/不足を別statusで返し、サービス例外をもっともらしい点数へ置換しない。
- **確認**: fake scorerのcoverage=0.25・missing_factors2件が同値で返る。budget_amount=NoneはNone。企業未確定は自社score=nullで、過去のDB scoreがあっても採用しない。
- **完了条件**: バックエンドの制約情報がUIで全て参照できる。
- **工数目安**: 3時間（透過1、summary1、テスト1）。

### ステップ 9: 「予測勝率」を参考機会スコアへ変更
- **対象**: `services/competitor_dashboard_page.py`、`services/prediction_dashboard_service.py`、`tests/unit/test_prediction_dashboard_service.py`（既存・再利用）。
- **作業**:
  1. 「予測勝率」「勝率の内訳」と%ゲージを「参考機会スコア」「要因の内訳」、点/100へ置換する。
  2. 根拠充足率・観測件数・欠測要因・算出時点・候補期間/打切りを常時表示し、null時は「データ不足」とする。
  3. 観測済み過去率は分子/分母/期間付きの別欄だけに表示し、将来確率との違いを短い日本語で示す。
- **確認**: fake結果0.4を表示して「40.0 / 100」「未校正」が出る。「予測勝率」「40%」は出ない。観測率2/10のみ「20%（2/10、対象期間）」と表示。nullでゲージを描かない。
- **完了条件**: 注意書きとタイトル/数値形式が矛盾せず、根拠を開閉操作なしでも認識できる。
- **工数目安**: 3時間（ラベル1、根拠1、表示検証1）。

### ステップ 10: 限定コーパスで性能と漏洩を検証
- **対象**: `tests/unit/test_text_similarity_service.py`、`tests/unit/test_specification_similarity_service.py`、`tests/unit/test_prediction_dashboard_service.py`（既存・再利用）。
- **作業**:
  1. 各200文字の日本語本文5000件、期間外1000件、権限外1000件を隔離DBへ用意する。
  2. 冷起動・同一条件再検索・policy変更を計測し、SQL件数と取得行数、行列がsparseのままであることを記録する。
  3. 候補上限5000を越えないことと別scopeの文字列が応答/例外に入らないことを検査する。時間は端末仕様を記録して評価する。
- **確認**: 候補5000以下・応答10以下・全件dense変換なし。試験目標は冷起動5秒/再検索2秒以内だが未測定値を保証しない。未達なら上限を下げ再測定し、ANNへ自動拡張しない。
- **完了条件**: 性能結果に環境・候補数・打切りが付記され、速度のためにscopeを外さない。
- **工数目安**: 3時間（fixture1、計測1、境界確認1）。

### ステップ 11: 高度化の評価ゲートを明文化
- **対象**: 本計画書、`services/prediction_model_config.py`、`tests/unit/test_prediction_model_config.py`（既存・参照/再利用）。
- **作業**:
  1. MVP設定はレビュー済み固定値とし、自由な管理者調整やフィードバック自動学習を対象外にする。
  2. 将来の校正モデルには確認済み応札分母、観測打切り、企業/案件単位重複除外、時系列分割、将来情報漏洩防止、独立検証集合を必須条件として記録する。
  3. 実装前に最低必要標本数とBrier score/校正曲線/ベースライン比較の合否基準を担当者が決定するゲート、ANNにはRecall@10と権限分離/性能比較のゲートを記録する。
- **確認**: 正解ラベルがないfixtureでは校正済みフラグをtrueにできない。ProcurementForecastだけでは予測学習の入力資格を満たさない。MVPにANN/学習バッチ/送信の起動経路が増えない。
- **完了条件**: 「直感的に良さそう」を予測モデル合格理由にせず、評価計画未承認なら高度化しない。
- **工数目安**: 2時間（設定/境界1、ゲート確認1）。

### ステップ 12: 受入・静的検査・安全な切り戻し
- **対象**: 上記既存テスト群と本計画書（既存・再利用）。
- **作業**:
  1. 隔離条件と全fixture自立を確認後のみ `pytest --noconftest tests/unit/test_similarity_preprocess.py tests/unit/test_text_similarity_service.py tests/unit/test_specification_similarity_service.py tests/unit/test_bid_difficulty_scorer.py tests/unit/test_win_prediction_service.py tests/unit/test_prediction_dashboard_service.py tests/unit/test_prediction_model_config.py` を実行する。
  2. `.github/workflows/test.yml:18-20` の `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics` と `mypy .` の実行結果/不能を記録し、fake UIで受入する。
  3. 将来の不具合時は分析機能を非公開にし、今回追加した表示/計算差分のみを戻す。旧scopeなしcache・「予測勝率」表示へ戻さず、専用cacheは失効させる。DB列削除や全件再計算を切り戻しに含めない。
- **確認**: A/B隔離、空scope拒否、分母未知の不足、40/100表示、欠測null、5000件上限、pickle不使用が全て満たされる。03/04依存未完なら本番公開不可。
- **完了条件**: 12ステップの検証表が揃い、校正モデル/ANNは未実装と明記。実運用DB・API・メール・ベクトル構築バッチは受入中も実行しない。
- **工数目安**: 4時間（テスト1、静的確認1、画面受入1、切り戻し1）。

## 検証記録・最終完了判定

2026-09-17の計画編集ではソース/文書の静的確認のみで、実装テストやモデル評価は未実行。今回再実行した結果でもflake8は `EntryPoints.get` のAttributeErrorで検査不能、mypyは未導入。通過扱いせず、依存を自動インストールしない。今回の成果物/切り戻し対象は本計画書の差分だけであり、他の計画・既存実装・DB・cacheを操作しない。
