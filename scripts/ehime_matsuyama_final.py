"""松山市の各入札種別ページから実際の案件PDFを収集し、件数と最新日付を計測する最終検証スクリプト。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
DATE_RE = re.compile(r"(R\s*(\d{1,2})\.(\d{1,2})\.(\d{1,2}))|((?:20\d{2})[\-/\s年](\d{1,2})[\-/\s月](\d{1,2}))")

def fetch(url):
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": UA})
        return r.status_code, r.text
    except Exception:
        return -1, ""

def collect_pdfs(url):
    st, html = fetch(url)
    if st != 200:
        return st, []
    soup = BeautifulSoup(html, "html.parser")
    pdfs = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(url, href)
        if full.lower().endswith(".pdf") or ".pdf?" in full.lower():
            if full in seen:
                continue
            seen.add(full)
            text = a.get_text(strip=True) or "PDF"
            date = "不明"
            m = DATE_RE.search(f"{text} | {a.parent.get_text() if a.parent else ''}")
            if m:
                if m.group(1):
                    date = f"R{m.group(2)}.{m.group(3)}.{m.group(4)}"
                else:
                    date = f"{m.group(5)}-{int(m.group(6)):02d}-{int(m.group(7)):02d}"
            pdfs.append((text[:70], date, full))
    return st, pdfs

CATEGORIES = {
    "一般競争入札のお知らせ": "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/jouhou/oshirase/ippann.html",
    "総合評価競争入札のお知らせ": "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/jouhou/oshirase/sougou.html",
    "入札の中止": "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/jouhou/oshirase/nyuusatutyuusi.html",
    "変更通知等": "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/jouhou/oshirase/hendou.html",
    "工事等発注注通知公告": "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/jouhou/oshirase/hattyumitooshi.html",
}

total_pdfs = 0
all_pdfs = []
for cat, url in CATEGORIES.items():
    st, pdfs = collect_pdfs(url)
    print(f"\n=== {cat} : {url}")
    print(f"  status={st}  PDF数={len(pdfs)}")
    total_pdfs += len(pdfs)
    for t, d, u in pdfs:
        print(f"    [{d}] {t!r:50} {u}")
        all_pdfs.append((cat, t, d, u))

print(f"\n=== 松山市 全入札種別合計 PDF数: {total_pdfs} ===")

# 最新1件PDFを実際にダウンロードしてテキスト抽出を試みる
if all_pdfs:
    import subprocess
    print("\n=== 実際のPDFダウンロード&テキスト抽出テスト ===")
    for cat, t, d, u in all_pdfs[:3]:
        print(f"\n  [取得] {u}")
        r = requests.get(u, timeout=30, headers={"User-Agent": UA})
        print(f"    status={r.status_code} bytes={len(r.content)}")
        if r.status_code == 200:
            with open("temp_ehime_test.pdf", "wb") as f:
                f.write(r.content)
            # pypdfでテキスト抽出を試みる
            try:
                from pypdf import PdfReader
                reader = PdfReader("temp_ehime_test.pdf")
                txt = ""
                for pg in reader.pages[:5]:
                    txt += pg.extract_text() or ""
                print(f"    pypdf 抽出文字数: {len(txt)}")
                print(f"    先頭200字: {txt[:200]!r}")
            except Exception as e:
                print(f"    pypdf抽出失敗: {e}")
                try:
                    import pdfplumber
                    with pdfplumber.open("temp_ehime_test.pdf") as pdf:
                        txt = ""
                        for pg in pdf.pages[:5]:
                            txt += pg.extract_text() or ""
                    print(f"    pdfplumber 抽出文字数: {len(txt)}")
                    print(f"    先頭200字: {txt[:200]!r}")
                except Exception as e2:
                    print(f"    pdfplumber抽出失敗: {e2}")
