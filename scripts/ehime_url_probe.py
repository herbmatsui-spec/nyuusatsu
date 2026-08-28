"""愛媛県および市町村の入札情報ページ URL を実際に HTTP 取得して現状を確認する調査スクリプト。"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"

CANDIDATES = {
    "愛媛県": [
        "https://www.pref.ehime.jp/",
        "https://www.pref.ehime.jp/chijitsu/nyusatsu/",
        "https://www.pref.ehime.jp/kenmin/nyusatsu/",
        "https://www.pref.ehime.jp/bid",
    ],
    "松山市": [
        "https://www.city.matsuyama.ehime.jp/",
        "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/",
        "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/gyoumuitaku/",
        "https://www.city.matsuyama.ehime.jp/shisei/denshinyusatsu/nyusatsu/",
    ],
    "今治市": [
        "https://www.city.imabari.ehime.jp/",
        "https://www.city.imabari.ehime.jp/soshiki/somusho/nyusatsu/",
        "https://www.city.imabari.ehime.jp/nyusatsu/",
        "https://www.city.imabari.ehime.jp/bid/",
    ],
    "宇和島市": [
        "https://www.city.uwajima.ehime.jp/",
        "https://www.city.uwajima.ehime.jp/shisei/nyusatsu/index.html",
        "https://www.city.uwajima.ehime.jp/nyusatsu/",
        "https://www.city.uwajima.ehime.jp/bid/",
    ],
}

def probe(url):
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": UA})
        return r.status_code, len(r.text), r.text
    except Exception as e:
        return -1, 0, str(e)

def find_bid_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    hits = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True)
        if any(k in text for k in ["入札", "調達", "契約", "公告", "公募", "指名"]) or \
           any(k in href.lower() for k in ["nyusatsu", "bid", "chotatsu", "koukoku"]):
            from urllib.parse import urljoin
            hits.append((text[:40], urljoin(base_url, href)))
    # 重複排除
    seen = set()
    out = []
    for t, u in hits:
        if u not in seen:
            seen.add(u)
            out.append((t, u))
    return out

for agency, urls in CANDIDATES.items():
    print(f"\n=== {agency} ===")
    for u in urls:
        status, size, html = probe(u)
        print(f"  [{status}] {u}  (size={size})")
        if status == 200:
            for t, link in find_bid_links(html, u)[:15]:
                print(f"      -> {t!r:40} {link}")
