import requests, bs4, re
from urllib.parse import urljoin
import sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

urls = [
    'https://www.city.imabari.ehime.jp/', 
    'https://www.city.uwajima.ehime.jp/', 
    'https://www.city.yawatahama.ehime.jp/', 
    'https://www.city.niihama.lg.jp/', 
    'https://www.city.saijo.ehime.jp/', 
    'https://www.city.ozu.ehime.jp/', 
    'https://www.city.iyo.lg.jp/', 
    'https://www.city.shikokuchuo.ehime.jp/', 
    'https://www.city.seiyo.ehime.jp/', 
    'https://www.city.toon.ehime.jp/', 
    'https://www.town.kamijima.lg.jp/', 
    'https://www.kumakogen.jp/', 
    'https://www.town.masaki.ehime.jp/', 
    'https://www.town.tobe.ehime.jp/', 
    'https://www.town.uchiko.ehime.jp/', 
    'https://www.town.ikata.ehime.jp/', 
    'https://www.town.matsuno.ehime.jp/', 
    'https://www.town.kihoku.ehime.jp/', 
    'https://www.town.ainan.ehime.jp/'
]

KEYWORDS = re.compile('入札|公告|競争|指名|調達|契約|電子入札|入札情報')
HEADERS = {'User-Agent': 'Mozilla/5.0'}

for u in urls:
    print(f'--- {u} ---')
    try:
        r = requests.get(u, headers=HEADERS, timeout=10)
        soup = bs4.BeautifulSoup(r.text, 'html.parser')
        links_found = False
        for a in soup.find_all('a'):
            text = a.get_text(strip=True)
            href = a.get('href', '')
            if KEYWORDS.search(text):
                print(f'{text} | {urljoin(u, href)}')
                links_found = True
        if not links_found:
            print('No links found.')
    except Exception as e:
        print(f'Error: {e}')
    print()
