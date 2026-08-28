import csv, json, re, time, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

OUT = "docs/plans/url_probe_results"
os.makedirs(OUT, exist_ok=True)
KEYWORDS = re.compile("入札|公告|競争|指名|調達|契約|電子入札|入札情報")
HEADERS = {"User-Agent": "Mozilla/5.0"}

with open("data/agencies.csv", encoding="utf-8") as f:
    rows = [r for r in csv.DictReader(f) if r["region"] == "愛媛県"]

for row in rows:
    name = row["name"]
    url = row["base_url"]
    print(f"[{name}] base={url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        status = r.status_code
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""
        candidates = []
        for a in soup.find_all("a"):
            txt = a.get_text(strip=True)
            href = a.get("href", "")
            if KEYWORDS.search(txt) and href:
                candidates.append({"text": txt, "url": urljoin(r.url, href)})
        result = {"name": name, "base_url": url, "status": status, "title": title, "candidates": candidates}
        with open(f"{OUT}/{name}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  -> status={status} candidates={len(candidates)}")
    except Exception as e:
        print(f"  -> ERROR {e}")
    time.sleep(5)
print("DONE")
