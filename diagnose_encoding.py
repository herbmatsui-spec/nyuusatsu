"""文字化け診断スクリプト — BeautifulSoup抽出パイプラインの各段階でrepr()を出力し、
どの段階で日本語文字が破損するかを特定する。"""

import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bs4 import BeautifulSoup

# テスト用HTML (UTF-8)
HTML_SIMPLE = """<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"></head>
<body>
<table>
<tr><th>公告日</th><td>令和7年4月1日</td></tr>
<tr><th>予算額</th><td>15,000,000円</td></tr>
<tr><th>入札期限</th><td>令和7年5月15日 17時00分</td></tr>
</table>
</body>
</html>"""


def diagnose():
    print("=" * 60)
    print("【診断】BeautifulSoup 文字化け調査")
    print("=" * 60)

    # Stage 0: ソース文字列のrepr
    print("\n--- Stage 0: ソースHTMLのrepr() ---")
    print(repr(HTML_SIMPLE[:200]))
    print(f"  文字列長: {len(HTML_SIMPLE)}")
    print(f"  '令和' in source: {'令和' in HTML_SIMPLE}")
    print(f"  '円' in source: {'円' in HTML_SIMPLE}")

    # Stage 1: BeautifulSoupでパース
    print("\n--- Stage 1: BeautifulSoup(html, 'html.parser') ---")
    soup = BeautifulSoup(HTML_SIMPLE, "html.parser")

    # Stage 2: get_text()
    print("\n--- Stage 2: soup.get_text('\\n', strip=True) ---")
    text = soup.get_text("\n", strip=True)
    print(repr(text[:300]))
    print(f"  '令和' in text: {'令和' in text}")
    print(f"  '円' in text: {'円' in text}")
    print(f"  '15,000,000円' in text: {'15,000,000円' in text}")
    print(f"  '令和7年4月1日' in text: {'令和7年4月1日' in text}")
    print(f"  '令和7年5月15日' in text: {'令和7年5月15日' in text}")

    # Stage 3: テーブル行ごとに抽出
    print("\n--- Stage 3: テーブル行ごとのテキスト抽出 ---")
    for i, row in enumerate(soup.find_all("tr")):
        cells = row.find_all(["th", "td"])
        cell_texts = [c.get_text(strip=True) for c in cells]
        print(f"  Row {i}: {cell_texts}")
        for j, ct in enumerate(cell_texts):
            print(f"    Cell {j} repr: {repr(ct)}")

    # Stage 4: lxmlパーサーでも試す
    print("\n--- Stage 4: BeautifulSoup(html, 'lxml') ---")
    try:
        soup_lxml = BeautifulSoup(HTML_SIMPLE, "lxml")
        text_lxml = soup_lxml.get_text("\n", strip=True)
        print(repr(text_lxml[:300]))
        print(f"  '令和' in text_lxml: {'令和' in text_lxml}")
        print(f"  '円' in text_lxml: {'円' in text_lxml}")
    except Exception as e:
        print(f"  lxml利用不可: {e}")

    # Stage 5: html5libパーサーでも試す
    print("\n--- Stage 5: BeautifulSoup(html, 'html5lib') ---")
    try:
        soup_h5 = BeautifulSoup(HTML_SIMPLE, "html5lib")
        text_h5 = soup_h5.get_text("\n", strip=True)
        print(repr(text_h5[:300]))
        print(f"  '令和' in text_h5: {'令和' in text_h5}")
        print(f"  '円' in text_h5: {'円' in text_h5}")
    except Exception as e:
        print(f"  html5lib利用不可: {e}")

    # Stage 6: BidDetailExtractor での抽出結果
    print("\n--- Stage 6: BidDetailExtractor.extract_from_html() ---")
    try:
        from crawler.detail_extractor import BidDetailExtractor
        extractor = BidDetailExtractor()
        result = extractor.extract_from_html(HTML_SIMPLE, url="test://diagnostic")
        for key, value in result.items():
            print(f"  {key}: {repr(value)}")
            if value:
                print(f"    '令和' in {key}: {'令和' in str(value)}")
                print(f"    '円' in {key}: {'円' in str(value)}")
    except Exception as e:
        print(f"  抽出エラー: {e}")
        import traceback
        traceback.print_exc()

    # Stage 7: scripts/crawl_hokkaido.py のフィクスチャでテスト
    print("\n--- Stage 7: crawl_hokkaido.py の DETAIL_IT_SYSTEM フィクスチャ ---")
    try:
        from scripts.crawl_hokkaido import DETAIL_IT_SYSTEM
        print(f"  ソースrepr最初の200文字: {repr(DETAIL_IT_SYSTEM[:200])}")
        print(f"  '令和' in fixture: {'令和' in DETAIL_IT_SYSTEM}")
        print(f"  '円' in fixture: {'円' in DETAIL_IT_SYSTEM}")
        
        soup_fix = BeautifulSoup(DETAIL_IT_SYSTEM, "html.parser")
        text_fix = soup_fix.get_text("\n", strip=True)
        print(f"  get_text repr最初の200文字: {repr(text_fix[:200])}")
        print(f"  '令和' in text_fix: {'令和' in text_fix}")
        print(f"  '円' in text_fix: {'円' in text_fix}")
        
        result_fix = extractor.extract_from_html(DETAIL_IT_SYSTEM, url="test://fixture")
        for key, value in result_fix.items():
            print(f"  {key}: {repr(value)}")
    except Exception as e:
        print(f"  フィクスチャテストエラー: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("診断完了")
    print("=" * 60)


if __name__ == "__main__":
    diagnose()