#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
愛媛県自治体の entry_url を検証するスクリプト (Step 2-3)
"""

import json
import sys
import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CONFIG_PATH = "crawler/parsers/agency_config/ehime.json"

def check_url(url: str) -> tuple[int, str]:
    try:
        r = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        return r.status_code, str(r.url)
    except Exception as e:
        return 0, str(e)

def main():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    print(f"{'Status':<8} {'Name':<20} {'URL':<80}")
    print("-" * 110)
    
    results = []
    for name, cfg in config.items():
        if not cfg.get("enabled", True):
            print(f"{'SKIP':<8} {name:<20} {cfg['entry_url']:<80}")
            continue
        code, final = check_url(cfg["entry_url"])
        status = "OK" if code == 200 else f"NG({code})"
        print(f"{status:<8} {name:<20} {cfg['entry_url']:<80}")
        print(f"{'':<8} {'':<20} {'->':<80} {final}")
        results.append((name, code, cfg["entry_url"], final))

    # Summary
    ok = sum(1 for r in results if r[1] == 200)
    ng = sum(1 for r in results if r[1] != 200)
    print(f"\nSummary: OK={ok}, NG={ng}, Total={len(results)}")

if __name__ == "__main__":
    main()