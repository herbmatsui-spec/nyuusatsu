import sys, io, time, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent":"Mozilla/5.0"}
with open("docs/plans/url_probe_results/_final.tsv", encoding="utf-8") as f:
    lines = f.readlines()
    # Skip header
    for line in lines[1:]:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 2: continue
        name, url, src = parts[0], parts[1], parts[2] if len(parts)>2 else "unknown"
        try:
            r = requests.get(url, headers=H, timeout=20)
            print(f"{r.status_code}\t{name}\t{url}")
        except Exception as e:
            print(f"ERR\t{name}\t{url}\t{e}")
        time.sleep(2)
