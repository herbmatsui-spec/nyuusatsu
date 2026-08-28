"""愛媛県各自治体の入札関連ページを深さ2まで再帰的に巡回し、PDF仕様書リンクを収集するスクリプト。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from collections import deque

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
DATE_RE = re.compile(r"((?:19|20)\d{2})[\s/\-年]\s*(0?[1-9]|1[0-2])[\s/\-月]\s*(0?[1-9]|[12]\d|3[01])日?")

KEYWORDS = ["入札", "公告", "調達", "契約", "公募", "指名", "仕様書", "見積", "選定", "告示"]

def fetch(url):
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": UA})
        return r.status_code, r.text
    except Exception:
        return -1, ""

def is_bid_link(text, href):
    return any(k in text for k in KEYWORDS) or any(k in href.lower() for k in
        ["nyusatsu", "bid", "chotatsu", "koukoku", "itaku", "shiyousho"])

def same_host(u1, u2):
    from urllib.parse import urlparse
    return urlparse(u1).netloc == urlparse(u2).netloc

def crawl(root_url, max_depth=2, max_visit=40):
    visited = set()
    pdfs = []
    q = deque([(root_url, 0)])
    bid_pages = []
    while q and len(visited) < max_visit:
        url, depth = q.popleft()
        if url in visited or depth > max_depth:
            continue
        visited.add(url)
        st, html = fetch(url)
        if st != 200:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip().split("#")[0]
            if not href:
                continue
            full = urljoin(url, href)
            text = a.get_text(strip=True)
            if full.lower().endswith(".pdf") or ".pdf?" in full.lower():
                date = "不明"
                m = DATE_RE.search(f"{text} | {a.parent.get_text() if a.parent else ''}")
                if m:
                    y, mo, d = m.groups()
                    date = f"{y}-{int(mo):02d}-{int(d):02d}"
                pdfs.append((text[:60] or "仕様書PDF", date, full, url))
                continue
            if same_host(full, root_url) and is_bid_link(text, full):
                bid_pages.append((text[:40], full, depth))
                if full not in visited and depth + 1 <= max_depth:
                    q.append((full, depth + 1))
    return pdfs, bid_pages, visited

TARGETS = {
    "松山市 入札情報": "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/jouhou/index.html",
    "松山市 一般競争入札": "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/gyoumuitaku/info/index.html",
    "今治市 広報公掲": "https://www.city.imabari.ehime.jp/kouhou/koukoku/",
    "宇和島市 入札候補": "https://www.city.uwajima.ehime.jp/",
    "愛媛県庁": "https://www.pref.ehime.jp/",
}

summary = {}
for name, url in TARGETS.items():
    print(f"\n### {name} : {url}")
    pdfs, bid_pages, visited = crawl(url, max_depth=2, max_visit=25)
    print(f"  訪問ページ数={len(visited)}  入札関連ページ={len(bid_pages)}  PDF={len(pdfs)}")
    summary[name] = (len(visited), len(bid_pages), len(pdfs))
    print("  -- 入札関連ページ(最大8件) --")
    for t, u, d in bid_pages[:8]:
        print(f"    [d{d}] {t!r:30} -> {u}")
    print("  -- PDF仕様書(最大15件) --")
    for t, dt, u, fr in pdfs[:15]:
        print(f"    [{dt}] {t!r:40} {u}")

print("\n=== サマリ ===")
for name, (v, b, p) in summary.items():
    print(f"  {name:24}: 訪問={v:3}  入札リンク={b:3}  PDF={p}")
