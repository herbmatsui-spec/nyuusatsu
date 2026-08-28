"""松山市入札情報お知らせページから実際の案件PDFを収集し、各PDFのテキスト抽出を試みる検証スクリプト。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
DATE_RE = re.compile(r"(R?(\d{1,2}))[\.\s年]*(\d{1,2})[\.\s月]*(\d{1,2})")


def fetch(url):
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": UA})
        return r.status_code, r.text, r
    except Exception as e:
        return -1, str(e), None


def list_pdfs_and_links(url, label):
    print(f"\n### {label} : {url}")
    st, html, _ = fetch(url)
    if st != 200:
        print(f"  status={st}")
        return []
    soup = BeautifulSoup(html, "html.parser")
    print(f"  size={len(html)}")
    # すべてのaタグでPDFと「入札/公告」系を分類
    pdfs = []
    bid_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto"):
            continue
        full = urljoin(url, href)
        text = a.get_text(strip=True)
        if full.lower().endswith(".pdf") or ".pdf?" in full.lower():
            pdfs.append((text[:60], full))
        elif any(k in text for k in ["入札", "公告", "調達", "公募", "仕様書", "案件"]) or \
             any(k in href.lower() for k in ["nyusatsu", "koukoku", "bid"]):
            bid_links.append((text[:40], full))
    print(f"  PDF数={len(pdfs)}  入札系トップーリンク数={len(bid_links)}")
    print("  -- PDF(最大25件) --")
    for t, u in pdfs[:25]:
        print(f"    {t!r:50} {u}")
    print("  -- 入札系リンク(最大12件) --")
    for t, u in bid_links[:12]:
        print(f"    {t!r:32} {u}")
    return pdfs


matsuyama_base = "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/jouhou/index.html"
# 入札情報トップを取得
st, html, _ = fetch(matsuyama_base)
soup = BeautifulSoup(html, "html.parser")
print("=== 松山市 入札情報TOP 内のリンク一覧 ===")
for a in soup.find_all("a", href=True):
    t = a.get_text(strip=True)
    h = urljoin(matsuyama_base, a["href"])
    print(f"  {t!r:34} -> {h}")

# お知らせページ
list_pdfs_and_links(
    "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/jouhou/oshirase/index.html",
    "松山市 入札情報お知らせ")

# 工事のお知らせ
list_pdfs_and_links(
    "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/kouji/index.html",
    "松山市 工事の委託業務のお知らせ")
