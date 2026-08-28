import csv, json, re, time, sys, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

OUT = "docs/plans/url_probe_results"
KEYWORDS = re.compile("入札|公告|競争|指名|調達|契約|電子入札|入札情報")
HEADERS = {"User-Agent": "Mozilla/5.0"}
ZERO = [
    "愛媛県", "松山市", "今治市", "宇和島市", "八幡浜市", "新居浜市", 
    "西条市", "大洲市", "伊予市", "四国中央市", "西予市", "東温市", 
    "愛媛県上島町", "愛媛県久万高原町", "愛媛県松前町", "愛媛県砥部町", 
    "愛媛県内子町", "愛媛県伊方町", "愛媛県松野町", "愛媛県鬼北町", "愛媛県愛南町"
]

def probe(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        return r.status_code, r.text, r.url
    except Exception as e:
        return None, "", url

# agencies.csv から base_url マップを作成
base_urls = {}
with open("data/agencies.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for r in reader:
        if r["region"] == "愛媛県":
            base_urls[r["name"]] = r["base_url"]

for name in ZERO:
    base = base_urls.get(name)
    if not base:
        print(f"[{name}] base_url not found in csv")
        continue
        
    print(f"[{name}] probing depth 2 starting from {base}")
    st, html, final = probe(base)
    if st != 200:
        print(f"  -> base_url returned {st}")
        continue
        
    soup = BeautifulSoup(html, "html.parser")
    # 内部リンクのみを抽出（外部サイトへのリンクは除外）
    all_links = [urljoin(final, a.get("href","")) for a in soup.find_all("a") if a.get("href","") and (a.get("href","").startswith("/") or a.get("href","").startswith(base))]
    all_links = list(dict.fromkeys(all_links))[:50] # 重複排除、上限50件
    
    found = []
    for sub in all_links:
        s2, h2, f2 = probe(sub)
        if s2 != 200: 
            continue
        s2soup = BeautifulSoup(h2, "html.parser")
        for a in s2soup.find_all("a"):
            txt = a.get_text(strip=True)
            href = a.get("href", "")
            if KEYWORDS.search(txt) and href:
                found.append({"page": sub, "text": txt, "url": urljoin(f2, href)})
        time.sleep(1)
        
    with open(f"{OUT}/{name}_depth2.json", "w", encoding="utf-8") as f:
        json.dump({"name": name, "found": found}, f, ensure_ascii=False, indent=2)
    print(f"  -> depth2 found={len(found)}")
    time.sleep(2)

print("DONE2")
