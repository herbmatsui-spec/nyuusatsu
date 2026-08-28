"""愛媛県/市町村の入札情報ページを実際に巡回し、PDF仕様書リンクを抽出・件数を計測する検証スクリプト。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
DATE_RE = re.compile(r"((?:19|20)\d{2})[\s/\-年]\s*(0?[1-9]|1[0-2])[\s/\-月]\s*(0?[1-9]|[12]\d|3[01])日?")

def fetch(url):
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": UA})
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)

def extract_pdf_links(url):
    html = requests.get(url, timeout=25, headers={"User-Agent": UA}).text
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(url, href)
        if full.lower().endswith(".pdf") or ".pdf?" in full.lower():
            if full in seen:
                continue
            seen.add(full)
            text = a.get_text(strip=True) or "仕様書PDF"
            date = "不明"
            m = DATE_RE.search(f"{text} | {a.parent.get_text() if a.parent else ''}")
            if m:
                y, mo, d = m.groups()
                date = f"{y}-{int(mo):02d}-{int(d):02d}"
            out.append((text[:50], date, full))
    return out

TARGETS = {
    "松山市 入札情報": "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/jouhou/index.html",
    "松山市 一般競争入札": "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/gyoumuitaku/info/index.html",
    "今治市 公告": "https://www.city.imabari.ehime.jp/kouhou/koukoku/",
    "宇和島市 TOP": "https://www.city.uwajima.ehime.jp/",
    "愛媛県 TOP": "https://www.pref.ehime.jp/",
}

for name, url in TARGETS.items():
    print(f"\n=== {name} : {url} ===")
    st, html = fetch(url)
    print(f"  status={st}, size={len(html)}")
    if st != 200:
        continue
    soup = BeautifulSoup(html, "html.parser")
    # 入札関連の深いリンクを10件表示
    cnt = 0
    for a in soup.find_all("a", href=True):
        t = a.get_text(strip=True)
        h = a["href"]
        if any(k in t for k in ["入札", "公告", "調達", "契約", "公募"]) or \
           any(k in h.lower() for k in ["nyusatsu", "bid", "koukoku", "chotatsu"]):
            print(f"    link: {t[:30]!r:32} -> {urljoin(url, h)}")
            cnt += 1
            if cnt >= 12:
                break

# 松山市の入札情報ページから実際の PDF を列挙
print("\n=== 松山市 入札情報ページ の PDF 一覧 ===")
try:
    pdfs = extract_pdf_links("https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/jouhou/index.html")
    print(f"  PDF数: {len(pdfs)}")
    for t, d, u in pdfs[:30]:
        print(f"    [{d}] {t!r:40} {u}")
except Exception as e:
    print(f"  ERROR: {e}")
