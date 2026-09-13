# サイト構造自動検出とセレクタ生成機能を導入する
## ステップ 1-24

1. `crawler/parsers/` ディレクトリ内に新しいモジュールを作成するためのベースを確認する
2. HTMLパターン検出クラスを実装する `crawler/parsers/structure_detector.py` を作成する
3. `structure_detector.py` 内に、`detect_table_structure(html)`, `detect_list_structure(html)`, `detect_card_structure(html)` などの関数またはクラスを定義する
4. 各検出関数はBeautifulSoupオブジェクトを受け取り、特定のタグパターン（例: テーブルなら<table>と<tr><td>の繰り返し）をスコアリングして構造タイプを返す
5. セレクタ自動生成クラス `crawler/parsers/selector_generator.py` を作成する
6. `selector_generator.py` 内に、検出された構造から最適なCSSセレクタを生成する `SelectorGenerator` クラスを定義する（例: テーブルなら `tbody tr td:nth-child(1)` など）
7. 生成ロジックは、ヘッダー行を推定し、データセルの位置を推定するシンプルなヒューリスティックで十分とする
8. フォールバック戦略クラス `crawler/parsers/fallback_selector.py` を作成し、優先セレクタが失敗した場合に代替セレクタリストを試すロジックを実装する
9. 構造変更検知クラス `crawler/parsers/structure_change_detector.py` を作成し、過去に成功したセレクタのハッシュを記録し、同じセレクタで取得結果が極端に減少したらフラグを立てるロジックを実装する
10. これらのモジュールが互いにインポートできるように、`__init__.py` でエクスポートする
11. `BaseCrawler` または `GenericCrawler` に、これらの機能を利用するメソッドを追加する（例: `auto_detect_and_select(selectors_list, html)`）
12. 新しいモジュールを利用するための設定やフラグを追加する（例: `use_auto_selector: bool = False`）
13. 既存のクローラー（GEPSや愛媛県設定）に影響しないように、デフォルトは従来の手動セレクタを使用するようにする
14. 動作確認用のスクリプトを作成し、サンプルHTML（愛媛県の入札ページ等）に対して構造検出とセレクタ生成を実行し、結果を出力する
15. 生成されたセレクタが実際にデータを抽出できるか、簡易的にテストする（BeautifulSoupでselectしてみる）
16. エラーハンドリングを追加し、構造が判別できない場合はフォールバックまたは従来セレクタに戻すロジックを実装する
17. 変更後のコードスタイルをチェックし、既存のフォーマッターに従う
18. 変更点をコミットする前に、`git diff` で意図しない変更がないか確認する
19. コミットメッセージ例を記録しておく（例: "feat: add automatic site structure detection and selector generation"）
20. ドキュメント（docstrings）を更新し、各モジュールの使い方を説明する
21. 設定ファイルやスクリプトからこの機能を利用する例を示すサンプルコードを書き、`docs/` に追加する
22. 必要に応じて、ユニットテスト用のモックHTMLを作成し、各検出関数のテストケースを書く
23. テストを実行し、期待通りに動作するか確認する
24. すべてのステップが完了したら、次のステップ（クロール頻度の動的調整とモニタリングシステム実装）に進む準備ができたことを確認する