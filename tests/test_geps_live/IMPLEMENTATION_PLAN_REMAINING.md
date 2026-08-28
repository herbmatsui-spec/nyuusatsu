# GEPSクローラー実動作テスト 残り43ステップ実装計画書

## 現状サマリー

| Phase | 計画 | 完了 | 残り | 状態 |
|-------|------|------|------|------|
| Phase 00 | 3 | 3 | 0 | ✅ |
| Phase 01 | 8 | 8 | 0 | ✅ |
| Phase 02 | 6 | 6 | 0 | ✅ |
| Phase 03 | 7 | 6 | 1 | ⚠️ |
| Phase 04 | 6 | 6 | 0 | ✅ |
| Phase 05 | 7 | 0 | 7 | ❌ |
| Phase 06 | 5 | 0 | 5 | ❌ |
| Phase 07 | 6 | 0 | 6 | ❌ |
| Phase 08 | 7 | 0 | 7 | ❌ |
| Phase 09 | 4 | 0 | 4 | ❌ |
| Phase 10 | 7 | 0 | 7 | ❌ |
| Phase 11 | 7 | 0 | 7 | ❌ |
| Phase 12 | 4 | 0 | 4 | ❌ |
| **合計** | **72** | **29** | **43** | |

## 残り43ステップの詳細

---

### Phase 03 残り1ステップ (Step 30)

#### Step 30: `003_07_page_content_test.py`
- **目的**: Playwrightで取得したページコンテンツがBeautifulSoupでパース可能であることを確認
- **ファイル**: `tests/test_geps_live/Phase 03/003_07_page_content_test.py`
- **テスト関数**:
  1. `test_page_content_parseable` — `page.content()` → `BeautifulSoup(html, 'lxml')` が成功
  2. `test_page_content_has_table_or_div` — パース結果に `<table>` or `<div>` が含まれる
  3. `test_page_content_links_extractable` — `soup.find_all('a', href=True)` でリンク抽出可能
- **依存**: `live_geps_url`, Playwright
- **推定行数**: ~30行

---

### Phase 05: GEPS検索結果抽出 ( Steps 31-37, 7ステップ)

#### Step 31: `005_01_search_result_table_test.py`
- **目的**: GEPS検索結果ページにテーブルが存在することを確認
- **テスト関数**:
  1. `test_search_page_has_table` — `await page.goto(search_url)` → `wait_for_selector('table')`
  2. `test_table_has_multiple_rows` — `query_selector_all('tr')` で行数 >= 2
  3. `test_table_not_empty` — テーブル内にテキストが存在する
- **依存**: `live_geps_url`, Playwright, `requests`
- **推定行数**: ~40行

#### Step 32: `005_02_title_extraction_test.py`
- **目的**: 検索結果から案件名（タイトル）を抽出できることを確認
- **テスト関数**:
  1. `test_extract_title_from_row` — 1行目の `<a>` タグテキストが取得できる
  2. `test_title_not_empty` — 抽出したタイトルが空でない
  3. `test_title_contains_japanese` — タイトルに日本語文字が含まれる
- **依存**: `BeautifulSoup`, サンプルHTML
- **推定行数**: ~35行

#### Step 33: `005_03_agency_name_extraction_test.py`
- **目的**: 検索結果から発注機関名を抽出できることを確認
- **テスト関数**:
  1. `test_extract_agency_from_table` — 2列目のセルテキストが取得できる
  2. `test_agency_not_unknown` — 機関名が "不明" ではない
  3. `test_agency_name_japanese` — 機関名に日本語が含まれる
- **依存**: `BeautifulSoup`, サンプルHTML
- **推定行数**: ~35行

#### Step 34: `005_04_publish_date_extraction_test.py`
- **目的**: 検索結果から公示日を抽出できることを確認
- **テスト関数**:
  1. `test_extract_date_yyyy_mm_dd` — "2026年7月1日" 形式の日付を抽出
  2. `test_extract_date_slash` — "2026/07/01" 形式の日付を抽出
  3. `test_date_regex_matches` — 正規表現 `r'(19|20)\d{2}[/\-年]\s*\d{1,2}[/\-月]\s*\d{1,2}日?'` でマッチ
- **依存**: `re`, サンプルHTML
- **推定行数**: ~30行

#### Step 35: `005_05_pdf_url_extraction_test.py`
- **目的**: 検索結果からPDF仕様書URLを抽出できることを確認
- **テスト関数**:
  1. `test_extract_pdf_url_from_link` — `<a href="...pdf">` からURLを抽出
  2. `test_pdf_url_is_absolute` — `urljoin()` で絶対URL化される
  3. `test_pdf_url_ends_with_pdf` — 抽出URLが `.pdf` で終わる
- **依存**: `urljoin`, `BeautifulSoup`
- **推定行数**: ~35行

#### Step 36: `005_06_multi_row_parse_test.py`
- **目的**: 複数行の検索結果をパースできることを確認
- **テスト関数**:
  1. `test_parse_multiple_rows` — `parse_results()` で2件以上抽出
  2. `test_each_row_has_title` — 全行にtitleが含まれる
  3. `test_each_row_has_url` — 全行にpdf_urlが含まれる
- **依存**: `GEPSCrawler.parse_results()`, サンプルHTML
- **推定行数**: ~35行

#### Step 37: `005_07_full_parse_integration_test.py`
- **目的**: GEPSCrawler の `parse_results()` を使った完全パーサーの統合テスト
- **テスト関数**:
  1. `test_parse_results_returns_list` — 戻り値が `list` 型
  2. `test_parse_results_dict_keys` — 各要素に `title`, `agency`, `pdf_url`, `publish_date` キーが存在
  3. `test_parse_results_count_matches` — 抽出件数が期待値と一致
- **依存**: `GEPSCrawler`, `CrawlerConfig`
- **推定行数**: ~40行

---

### Phase 06: ページネーション ( Steps 38-42, 5ステップ)

#### Step 38: `006_01_next_button_test.py`
- **目的**: 検索結果ページに「次へ」ボタンが存在するか確認
- **テスト関数**:
  1. `test_next_button_locator` — `page.locator("a:has-text('次へ')").count()` を実行
  2. `test_next_button_clickable` — ボタンが存在する場合、`is_visible()` がTrue
  3. `test_next_button_or_pagination` — ページ番号リンクの存在も確認
- **依存**: Playwright, `live_geps_url`
- **推定行数**: ~40行

#### Step 39: `006_02_next_page_navigation_test.py`
- **目的**: 「次へ」ボタンをクリックして次ページに遷移できるか確認
- **テスト関数**:
  1. `test_click_next_changes_url` — クリック前後でURLまたはコンテンツが変化
  2. `test_next_page_has_results` — 次ページにもテーブル行が存在
  3. `test_next_page_different_content` — 1ページ目と2ページ目で内容が異なる
- **依存**: Playwright, `live_geps_url`
- **推定行数**: ~50行

#### Step 40: `006_03_max_page_estimation_test.py`
- **目的**: 最大ページ数を推定できるか確認
- **テスト関数**:
  1. `test_get_max_pages_returns_int` — `get_max_pages()` が int 型を返す
  2. `test_max_pages_at_least_1` — 戻り値 >= 1
  3. `test_max_pages_reasonable` — 戻り値 <= 100（異常値でない）
- **依存**: `GEPSCrawler.get_max_pages()`
- **推定行数**: ~40行

#### Step 41: `006_04_final_page_test.py`
- **目的**: 最終ページで「次へ」ボタンが消えることを確認
- **テスト関数**:
  1. `test_no_next_on_last_page` — 最終ページで `locator.count() == 0` または `False`
  2. `test_goto_next_returns_false_on_last` — `goto_next_page()` が `False` を返す
  3. `test_final_page_still_has_content` — 最終ページにもテーブルが存在
- **依存**: `GEPSCrawler.goto_next_page()`
- **推定行数**: ~45行

#### Step 42: `006_05_multi_page_extraction_test.py`
- **目的**: 複数ページにわたって検索結果を抽出できるか確認
- **テスト関数**:
  1. `test_multi_page_total_increases` — 2ページ目取得後、総件数が1ページ目より多い
  2. `test_no_duplicate_urls_across_pages` — ページ間でURLの重複がない
  3. `test_multi_page_results_structure` — 全結果に title, url, agency が含まれる
- **依存**: `GEPSCrawler.crawl()`
- **推定行数**: ~50行

---

### Phase 07: PDFダウンロード ( Steps 43-48, 6ステップ)

#### Step 43: `007_01_pdf_download_basic_test.py`
- **目的**: PDF URLに `requests.get()` でアクセスしステータス200を確認
- **テスト関数**:
  1. `test_pdf_url_returns_200` — 抽出したPDF URLにGET → `status_code == 200`
  2. `test_pdf_response_not_empty` — `response.content` が空でない
  3. `test_pdf_download_retries` — 失敗時のリトライ動作確認
- **依存**: `requests`, `live_geps_url`
- **推定行数**: ~35行

#### Step 44: `007_02_content_type_test.py`
- **目的**: PDFレスポンスのContent-Typeが `application/pdf` であることを確認
- **テスト関数**:
  1. `test_content_type_is_pdf` — `headers['content-type']` に `application/pdf` が含まれる
  2. `test_content_type_header_present` — Content-Typeヘッダーが存在する
  3. `test_pdf_magic_bytes` — コンテンツ先頭が `%PDF` で始まる
- **依存**: `requests`
- **推定行数**: ~30行

#### Step 45: `007_03_file_size_test.py`
- **目的**: ダウンロードしたPDFのファイルサイズが妥当であることを確認
- **テスト関数**:
  1. `test_pdf_size_positive` — `len(content) > 0`
  2. `test_pdf_size_under_limit` — `len(content) < 50 * 1024 * 1024` (50MB)
  3. `test_pdf_size_matches_header` — Content-Lengthヘッダーと一致（存在する場合）
- **依存**: `requests`
- **推定行数**: ~30行

#### Step 46: `007_04_temp_save_delete_test.py`
- **目的**: 一時ファイルの保存・削除フローを確認
- **テスト関数**:
  1. `test_save_pdf_to_temp` — `temp_pdfs/` にファイルが保存される
  2. `test_file_exists_after_save` — `os.path.exists()` で確認
  3. `test_file_removed_after_delete` — `os.remove()` で削除後、存在しない
- **依存**: `os`, `tmp_path`
- **推定行数**: ~35行

#### Step 47: `007_05_sha256_duplicate_test.py`
- **目的**: 同一PDFの再ダウンロード時、SHA256が一致することを確認
- **テスト関数**:
  1. `test_sha256_consistent` — 同一URLを2回ダウンロード → SHA256が同一
  2. `test_sha256_is_hex` — ハッシュ値が64文字の16進文字列
  3. `test_sha256_differs_for_different_files` — 異なるPDFのSHA256は異なる
- **依存**: `hashlib`
- **推定行数**: ~35行

#### Step 48: `007_06_filename_generation_test.py`
- **目的**: ファイル名生成ロジックの動作確認
- **テスト関数**:
  1. `test_filename_contains_date` — 生成ファイル名に日付が含まれる
  2. `test_filename_sanitized` — 不正文字 `\/:*?"<>|` が `_` に置換される
  3. `test_filename_ends_with_pdf` — 生成ファイル名が `.pdf` で終わる
- **依存**: `GEPSCrawler._make_filename()`
- **推定行数**: ~30行

---

### Phase 08: エラーハンドリング ( Steps 49-55, 7ステップ)

#### Step 49: `008_01_404_url_test.py`
- **目的**: 存在しないURLにアクセスした場合の404エラー処理
- **テスト関数**:
  1. `test_404_returns_error_status` — 存在しないパスへのGET → `status_code >= 400`
  2. `test_404_does_not_crash` — 例外が発生してもプログラムが停止しない
  3. `test_404_body_not_empty` — 404ページにも何らかのHTMLが返る
- **依存**: `requests`
- **推定行数**: ~30行

#### Step 50: `008_02_timeout_test.py`
- **目的**: タイムアウト発生時のリトライ動作確認
- **テスト関数**:
  1. `test_short_timeout_raises` — 極短タイムアウト(0.001秒)で `Timeout` 例外発生
  2. `test_retry_on_timeout` — リトライ後、成功する可能性がある
  3. `test_timeout_does_not_hang` — タイムアウト後、処理が完了する
- **依存**: `requests`
- **推定行数**: ~35行

#### Step 51: `008_03_network_error_test.py`
- **目的**: ネットワーク切断時の例外処理
- **テスト関数**:
  1. ` test_invalid_host_raises` — `https://nonexistent.invalid/` → `ConnectionError`
  2. `test_error_caught_not_raised` — try-except で例外をキャッチできる
  3. `test_error_message_meaningful` — エラーメッセージが空でない
- **依存**: `requests`
- **推定行数**: ~30行

#### Step 52: `008_04_empty_html_test.py`
- **目的**: 空HTML応答時のパース結果確認
- **テスト関数**:
  1. `test_empty_html_returns_empty_list` — `parse_results("", url)` → `[]`
  2. `test_none_html_returns_empty_list` — `parse_results(None, url)` → `[]`
  3. `test_no_table_html_returns_empty` — テーブルなしHTML → `[]`
- **依存**: `GEPSCrawler.parse_results()`
- **推定行数**: ~30行

#### Step 53: `008_05_html_structure_anomaly_test.py`
- **目的**: HTML構造が予期しない形式でもクラッシュしないことを確認
- **テスト関数**:
  1. `test_div_only_html_does_not_crash` — `<div>` のみのHTML → `parse_results()` 成功
  2. `test_malformed_html_parses` — 閉じタグなしHTML → 例外発生しない
  3. `test_nested_tables_parse` — ネストされたテーブル → エラーなく処理
- **依存**: `BeautifulSoup`, `GEPSCrawler`
- **推定行数**: ~35行

#### Step 54: `008_06_encoding_garble_test.py`
- **目的**: 文字化け時のencoding判定確認
- **テスト関数**:
  1. `test_utf8_response_decoded` — UTF-8レスポンスが正しくデコードされる
  2. `test_shift_jis_response_decoded` — Shift_JISレスポンスのデコード確認
  3. `test_unknown_encoding_fallback` — 不明エンコーディング → フォールバック動作
- **依存**: `requests`
- **推定行数**: ~35行

#### Step 55: `008_07_large_response_test.py`
- **目的**: 大きなレスポンスの処理確認
- **テスト関数**:
  1. `test_large_html_parses` — 100KB以上のHTML → BeautifulSoupでパース成功
  2. `test_many_rows_handled` — 100+行のテーブル → 全行処理可能
  3. `test_large_response_memory_ok` — メモリ使用量が異常でない
- **依存**: `BeautifulSoup`
- **推定行数**: ~35行

---

### Phase 09: パフォーマンス・ベンチマーク ( Steps 56-59, 4ステップ)

#### Step 56: `009_01_single_page_timing_test.py`
- **目的**: 1ページあたりの取得所要時間を測定
- **テスト関数**:
  1. `test_single_page_under_10s` — `time.time()` で計測 → 10秒以内
  2. `test_parse_time_under_1s` — HTMLパース時間 → 1秒以内
  3. ` test_total_flow_under_15s` — 取得+パース合計 → 15秒以内
- **依存**: `time`, `requests`
- **推定行数**: ~35行

#### Step 57: `009_02_100_item_timing_test.py`
- **目的**: 100件取得の合計時間を測定
- **テスト関数**:
  1. `test_100_items_under_60s` — 100件抽出 → 60秒以内
  2. `test_avg_per_item_under_1s` — 1件あたり平均1秒以内
  3. `test_timing_logged` — 計測結果がログ出力される
- **依存**: `time`, `GEPSCrawler`
- **推定行数**: ~40行

#### Step 58: `009_03_concurrent_vs_sequential_test.py`
- **目的**: 並列 vs 逐次リクエストの速度比較
- **テスト関数**:
  1. `test_sequential_timing` — 逐次2ページ取得の時間を計測
  2. `test_concurrent_timing` — 並列2ページ取得の時間を計測
  3. `test_concurrent_faster` — 並列の方が速い（または同等）
- **依存**: `asyncio`, `time`
- **推定行数**: ~45行

#### Step 59: `009_04_playwright_vs_requests_test.py`
- **目的**: Playwright vs requests の速度比較
- **テスト関数**:
  1. `test_requests_timing` — requests での取得時間を計測
  2. `test_playwright_timing` — Playwright での取得時間を計測
  3. `test_requests_faster` — requests の方が速いことを確認
- **依存**: `requests`, Playwright, `time`
- **推定行数**: ~50行

---

### Phase 10: パイプライン連携 ( Steps 60-66, 7ステップ)

#### Step 60: `010_01_download_pdf_task_test.py`
- **目的**: `download_pdf_task()` が呼び出し可能であることを確認
- **テスト関数**:
  1. `test_download_task_callable` — `callable(download_pdf_task)` == True
  2. `test_download_task_signature` — 関数の引数数が期待通り
  3. `test_download_task_returns_none_or_int` — 戻り値が None or int
- **依存**: `crawler.pipeline`
- **推定行数**: ~25行

#### Step 61: `010_02_redis_connection_test.py`
- **目的**: Redis接続が確立できることを確認
- **テスト関数**:
  1. `test_redis_importable` — `from database.redis_conn import redis_conn` 成功
  2. `test_redis_ping_ok` — `redis_conn.ping()` がTrue（またはスキップ）
  3. `test_redis_connection_graceful_fail` — 接続失敗時もクラッシュしない
- **依存**: `database.redis_conn`
- **推定行数**: ~30行

#### Step 62: `010_03_queue_registration_test.py`
- **目的**: RQキューにタスクが登録できることを確認
- **テスト関数**:
  1. `test_queue_importable` — `from crawler.pipeline import download_queue` 成功
  2. `test_queue_enqueue_callable` — `download_queue.enqueue` が呼び出し可能
  3. `test_queue_name_correct` — キュー名が `'download_tasks'` である
- **依存**: `crawler.pipeline`, `rq`
- **推定行数**: ~25行

#### Step 63: `010_04_crawl_agency_async_test.py`
- **目的**: `crawl_agency_async()` の呼び出し確認
- **テスト関数**:
  1. `test_crawl_agency_async_callable` — `callable(crawl_agency_async)` == True
  2. `test_crawl_agency_async_coroutine` — `asyncio.iscoroutinefunction()` == True
  3. `test_crawl_agency_async_returns_list` — モック環境で `[]` を返す
- **依存**: `crawler.pipeline`
- **推定行数**: ~30行

#### Step 64: `010_05_generic_crawler_test.py`
- **目的**: `GenericCrawler.crawl_site()` の実動作確認
- **テスト関数**:
  1. `test_generic_crawler_initializable` — `GenericCrawler()` が初期化可能
  2. `test_crawl_site_returns_list` — モック環境で `list` 型を返す
  3. `test_crawl_site_results_are_crawl_result` — 要素が `CrawlResult` 型
- **依存**: `crawler.generic_crawler`
- **推定行数**: ~35行

#### Step 65: `010_06_trigger_agency_crawl_test.py`
- **目的**: `trigger_agency_crawl()` の呼び出し確認
- **テスト関数**:
  1. `test_trigger_callable` — `callable(trigger_agency_crawl)` == True
  2. `test_trigger_enqueues_task` — 呼び出し後、キューにタスクが追加される（モック）
  3. `test_trigger_logs_execution` — 実行ログが出力される
- **依存**: `crawler.pipeline`
- **推定行数**: ~30行

#### Step 66: `010_07_whole_workflow_test.py`
- **目的**: クロール → ダウンロード → 解析 → 通知の全体ワークフロー確認
- **テスト関数**:
  1. `test_pipeline_functions_exist` — 全パイプライン関数がインポート可能
  2. `test_pipeline_order_correct` — 実行順序が期待通り
  3. `test_pipeline_metrics_recorded` — メトリクスが記録される（モック）
- **依存**: `crawler.pipeline`
- **推定行数**: ~40行

---

### Phase 11: 実データ検証 ( Steps 67-73, 7ステップ)

#### Step 67: `011_01_100_item_collection_test.py`
- **目的**: 複数ページを巡回し100件以上のCrawlResultを収集
- **テスト関数**:
  1. `test_collect_at_least_100` — `GEPSCrawler.crawl()` で100件以上取得
  2. `test_results_are_dicts` — 全結果が `dict` 型
  3. `test_collection_completes` — 収集処理が完了する（タイムアウトしない）
- **依存**: `GEPSCrawler`, `live_geps_url`
- **推定行数**: ~40行

#### Step 68: `011_02_duplicate_url_test.py`
- **目的**: 100件中に同一URLが含まれていないことを確認
- **テスト関数**:
  1. `test_no_duplicate_urls` — `set(urls)` の長さ == `len(urls)`
  2. `test_unique_pdf_urls` — PDF URLがすべて一意
  3. `test_dedup_by_url` — URLベースで重複排除が機能する
- **依存**: `GEPSCrawler`
- **推定行数**: ~30行

#### Step 69: `011_03_required_fields_test.py`
- **目的**: 全件について必須フィールドが空でないことを確認
- **テスト関数**:
  1. `test_all_titles_nonempty` — 全結果の `title` が空でない
  2. `test_all_urls_nonempty` — 全結果の `url` or `pdf_url` が空でない
  3. `test_all_agencies_nonempty` — 全結果の `agency` が空でない
- **依存**: `GEPSCrawler`
- **推定行数**: ~35行

#### Step 70: `011_04_url_format_test.py`
- **目的**: 全件のURLが妥当なフォーマットであることを確認
- **テスト関数**:
  1. `test_all_urls_start_https` — 全URLが `https://` で始まる
  2. `test_all_urls_valid_format` — `urlparse` で scheme と netloc が存在
  3. `test_pdf_urls_end_with_pdf` — PDF URLが `.pdf` で終わる
- **依存**: `urllib.parse`
- **推定行数**: ~30行

#### Step 71: `011_05_date_format_test.py`
- **目的**: 抽出した日付が統一フォーマットであることを確認
- **テスト関数**:
  1. `test_dates_match_pattern` — 日付が `YYYY-MM-DD` or `YYYY年M月D日` 形式
  2. `test_dates_parseable` — 全日付が `datetime.strptime` でパース可能
  3. `test_dates_in_valid_range` — 日付が2020年〜2030年の範囲内
- **依存**: `re`, `datetime`
- **推定行数**: ~35行

#### Step 72: `011_06_agency_name_test.py`
- **目的**: 全結果に発注機関名が設定されていることを確認
- **テスト関数**:
  1. `test_all_agencies_set` — 全結果に `agency` キーが存在
  2. `test_agencies_not_unknown` — 機関名が "不明" ではない（可能な限り）
  3. `test_agencies_are_japanese` — 機関名に日本語文字が含まれる
- **依存**: `GEPSCrawler`
- **推定行数**: ~30行

#### Step 73: `011_07_data_consistency_test.py`
- **目的**: データの一貫性を確認（タイトルとURLの対応など）
- **テスト関数**:
  1. `test_title_url_count_match` — タイトル数とURL数が一致
  2. `test_no_orphan_titles` — URLがないタイトルが存在しない
  3. `test_results_sorted_or_groupable` — 結果が機関名または日付でソート可能
- **依存**: `GEPSCrawler`
- **推定行数**: ~35行

---

### Phase 12: 最終統合・品質保証 ( Steps 74-?, 4ステップ)

#### Step 74: `012_01_test_runner_completion_test.py`
- **目的**: テストランナー `run_live_tests.py` が実行可能であることを確認
- **テスト関数**:
  1. `test_runner_file_exists` — `run_live_tests.py` が存在する
  2. `test_runner_importable` — Python構文エラーなくインポート可能
  3. `test_runner_has_argparse` — `argparse` で `--phase`, `--no-live` オプションが定義されている
- **依存**: `scripts/run_live_tests.py`
- **推定行数**: ~30行

#### Step 75: `012_02_skip_option_test.py`
- **目的**: `--no-live` オプションでライブテストをスキップできることを確認
- **テスト関数**:
  1. `test_skip_env_var_recognized` — `GEPS_SKIP_LIVE=true` でスキップ判定
  2. `test_skip_flag_in_conftest` — `conftest.py` にスキップロジックが存在
  3. ` test_skip_does_not_fail` — スキップ時もテスト全体がFAILしない
- **依存**: `conftest.py`
- **推定行数**: ~30行

#### Step 76: `012_03_report_generation_test.py`
- **目的**: 100件実動作テストレポートが生成されることを確認
- **テスト関数**:
  1. `test_report_dir_exists` — `reports/` ディレクトリが作成される
  2. `test_report_json_valid` — 生成されたJSONが `json.load()` で読める
  3. `test_report_contains_summary` — レポートに `total`, `passed`, `failed` キーが含まれる
- **依存**: `json`, `conftest.py`
- **推定行数**: ~35行

#### Step 77: `012_04_final_code_review_test.py`
- **目的**: 全テストファイルのimport整合・構文チェック
- **テスト関数**:
  1. `test_all_py_files_parse` — `ast.parse()` で全 `.py` ファイルが構文エラーなし
  2. `test_all_test_functions_start_with_test` — 全テスト関数名が `test_` で始まる
  3. `test_no_syntax_errors_in_phase_dirs` — Phase 00-12 ディレクトリ内の全ファイル構文OK
- **依存**: `ast`, `pathlib`
- **推定行数**: ~40行

---

## 各ステップの実装ガイドライン

### 1ファイルの構造テンプレート

```python
"""
Phase XX: <フェーズ名>
Step XX: <ステップ名>
目的: <1行で説明>
"""
import pytest
# 必要なimport

def test_xxx_yyy_1(live_geps_url):
    """<テストの概要>"""
    # 1つのassertion
    pass

def test_xxx_yyy_2(live_geps_url):
    """<テストの概要>"""
    # 1つのassertion
    pass

def test_xxx_yyy_3(live_geps_url):
    """<テストの概要>"""
    # 1つのassertion
    pass
```

### 実装ルール

1. **1ファイル = 1ステップ = 3つのテスト関数**
2. **1テスト関数 = 1つのassertion**（可能な限り）
3. **ファイルサイズ = 25〜50行**（簡潔に）
4. **importは最小限** — `pytest`, `requests`, `BeautifulSoup`, `time` のみ
5. **エラー時は `pytest.skip()`** — 本番サイト不可時はスキップ
6. **日本語docstring** — 各テスト関数に1行の日本語説明

### 実装優先順位

| 優先度 | Phase | ステップ | 理由 |
|--------|-------|---------|------|
| 🔴 最高 | Phase 03 | Step 30 (1ステップ) | 不足分の補完 |
| 🔴 最高 | Phase 05 | Steps 31-37 (7ステップ) | GEPS抽出の中核 |
| 🟠 高 | Phase 06 | Steps 38-42 (5ステップ) | ページネーション |
| 🟠 高 | Phase 07 | Steps 43-48 (6ステップ) | PDFダウンロード |
| 🟡 中 | Phase 08 | Steps 49-55 (7ステップ) | エラーハンドリング |
| 🟡 中 | Phase 11 | Steps 67-73 (7ステップ) | 100件データ検証 |
| 🟢 低 | Phase 09 | Steps 56-59 (4ステップ) | パフォーマンス |
| 🟢 低 | Phase 10 | Steps 60-66 (7ステップ) | パイプライン連携 |
| 🟢 低 | Phase 12 | Steps 74-77 (4ステップ) | 最終統合 |
