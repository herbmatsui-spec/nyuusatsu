"""
Award URL Patterns
公開される「落札結果情報」のURLパターン・テンプレート定義。
"""
from typing import Dict, Optional

AWARD_URL_PATTERNS: Dict[str, Dict[str, str]] = {
    "hokkaido": {
        "name": "北海道",
        "list_url": "https://www.pref.hokkaido.lg.jp/sm/sum/kenchiku/result/kekka.html",
        "detail_pattern": "https://www.pref.hokkaido.lg.jp/sm/sum/kenchiku/result/detail_{}.html",
    },
    "aomori": {
        "name": "青森県",
        "list_url": "https://www.pref.aomori.lg.jp/soshiki/soumu/keiyaku/kekka.html",
        "detail_pattern": "",
    },
    "iwate": {
        "name": "岩手県",
        "list_url": "https://www.pref.iwate.jp/kurashi/shigoto/nyusatsu/kekka.html",
        "detail_pattern": "",
    },
    "miyagi": {
        "name": "宮城県",
        "list_url": "https://www.pref.miyagi.jp/soshiki/soumu/keiyaku/kekka.html",
        "detail_pattern": "",
    },
    "akita": {
        "name": "秋田県",
        "list_url": "https://www.pref.akita.lg.jp/pages/gia120010",
        "detail_pattern": "",
    },
    "yamagata": {
        "name": "山形県",
        "list_url": "https://www.pref.yamagata.jp/category/10135.html",
        "detail_pattern": "",
    },
    "fukushima": {
        "name": "福島県",
        "list_url": "https://www.pref.fukushima.lg.jp/sec/21020/kekka.html",
        "detail_pattern": "",
    },
    "tokyo": {
        "name": "東京都",
        "list_url": "https://www.tender.metro.tokyo.jp/result/index.html",
        "detail_pattern": "https://www.tender.metro.tokyo.jp/result/detail_{}.html",
    },
    "kanagawa": {
        "name": "神奈川県",
        "list_url": "https://www.pref.kanagawa.jp/docs/r2q/cnt/f500/index.html",
        "detail_pattern": "",
    },
    "niigata": {
        "name": "新潟県",
        "list_url": "https://www.pref.niigata.lg.jp/site/nyusatsu/kekka.html",
        "detail_pattern": "",
    },
    "toyama": {
        "name": "富山県",
        "list_url": "https://www.pref.toyama.jp/site/kikaku/nyusatsukekka.html",
        "detail_pattern": "",
    },
    "ishikawa": {
        "name": "石川県",
        "list_url": "https://www.pref.ishikawa.lg.jp/site/kikaku/nyusatsukekka.html",
        "detail_pattern": "",
    },
    "fukui": {
        "name": "福井県",
        "list_url": "https://www.pref.fukui.lg.jp/doc/nyusatukekka.html",
        "detail_pattern": "",
    },
    "yamanashi": {
        "name": "山梨県",
        "list_url": "https://www.pref.yamanashi.jp/shutchoku/kekka.html",
        "detail_pattern": "",
    },
    "nagano": {
        "name": "長野県",
        "list_url": "https://www.pref.nagano.lg.jp/site/nyusatsu/kekka.html",
        "detail_pattern": "",
    },
    "gifu": {
        "name": "岐阜県",
        "list_url": "https://www.pref.gifu.lg.jp/site/nyusatsu/kekka.html",
        "detail_pattern": "",
    },
    "shizuoka": {
        "name": "静岡県",
        "list_url": "https://www.pref.shizuoka.jp/kikaku/nyusatsukekka.html",
        "detail_pattern": "",
    },
    "aichi": {
        "name": "愛知県",
        "list_url": "https://www.pref.aichi.jp/site/nyusatsukekka/",
        "detail_pattern": "",
    },
    "osaka": {
        "name": "大阪府",
        "list_url": "https://www.pref.osaka.lg.jp/kikan/keiyaku/kekka.html",
        "detail_pattern": "",
    },
    "fukuoka": {
        "name": "福岡県",
        "list_url": "https://www.pref.fukuoka.lg.jp/keiei/k boeki/kekka.html",
        "detail_pattern": "",
    },
    "saga": {
        "name": "佐賀県",
        "list_url": "https://www.pref.saga.lg.jp/kikaku/nyusatsu/kekka.html",
        "detail_pattern": "",
    },
    "nagasaki": {
        "name": "長崎県",
        "list_url": "https://www.pref.nagasaki.jp/site/kikaku/nyusatsukekka.html",
        "detail_pattern": "",
    },
    "kumamoto": {
        "name": "熊本県",
        "list_url": "https://www.pref.kumamoto.jp/soshiki/40/kekka.html",
        "detail_pattern": "",
    },
    "oita": {
        "name": "大分県",
        "list_url": "https://www.pref.oita.jp/site/kikaku/nyusatsu.html",
        "detail_pattern": "",
    },
    "miyazaki": {
        "name": "宮崎県",
        "list_url": "https://www.pref.miyazaki.lg.jp/soshiki/soumu/keiyaku/kekka.html",
        "detail_pattern": "",
    },
    "kagoshima": {
        "name": "鹿児島県",
        "list_url": "https://www.pref.kagoshima.jp/site/kikaku/nyusatsu.html",
        "detail_pattern": "",
    },
    "tokushima": {
        "name": "徳島県",
        "list_url": "https://www.pref.tokushima.lg.jp/soshiki/soumu/keiyaku/kekka.html",
        "detail_pattern": "",
    },
    "kagawa": {
        "name": "香川県",
        "list_url": "https://www.pref.kagawa.lg.jp/site/nyusatsu/kekka.html",
        "detail_pattern": "",
    },
    "ehime": {
        "name": "愛媛県",
        "list_url": "https://www.pref.ehime.jp/soshiki/soumu/keiyaku/kekka.html",
        "detail_pattern": "",
    },
    "kochi": {
        "name": "高知県",
        "list_url": "https://www.pref.kochi.lg.jp/soshiki/soumu/keiyaku/kekka.html",
        "detail_pattern": "",
    },
    "saitama": {
        "name": "埼玉県",
        "list_url": "https://www.pref.saitama.lg.jp/a0202/nyusatsukekka/index.html",
        "detail_pattern": "",
    },
    "chiba": {
        "name": "千葉県",
        "list_url": "https://www.pref.chiba.lg.jp/syazaigai/nyusatukekka/",
        "detail_pattern": "",
    },
    "kyoto": {
        "name": "京都府",
        "list_url": "https://www.pref.kyoto.jp/nyusatsukekka/",
        "detail_pattern": "",
    },
    "hyogo": {
        "name": "兵庫県",
        "list_url": "https://web.pref.hyogo.lg.jp/kf01/nyusatsu/",
        "detail_pattern": "",
    },
    "nara": {
        "name": "奈良県",
        "list_url": "https://www.pref.nara.jp/nyusatsukekka/",
        "detail_pattern": "",
    },
    "shiga": {
        "name": "滋賀県",
        "list_url": "https://www.pref.shiga.lg.jp/kikaku/nyusatsu/kekka.html",
        "detail_pattern": "",
    },
    "miye": {
        "name": "三重県",
        "list_url": "https://www.pref.mie.lg.jp/nyusatsukekka/",
        "detail_pattern": "",
    },
    "shizuoka_city": {
        "name": "静岡市",
        "list_url": "https://www.city.shizuoka.lg.jp/000_003341.html",
        "detail_pattern": "",
    },
    "hamamatsu_city": {
        "name": "浜松市",
        "list_url": "https://www.city.hamamatsu.shizuoka.jp/shisei/shiseijoho/nyusatsu/index.html",
        "detail_pattern": "",
    },
    "nagoya_city": {
        "name": "名古屋市",
        "list_url": "https://www.city.nagoya.jp/shiseikitai/page/0000000000",
        "detail_pattern": "",
    },
    "kyoto_city": {
        "name": "京都市",
        "list_url": "https://www.city.kyoto.lg.jp/sogo/page/0000232182.html",
        "detail_pattern": "",
    },
    "osaka_city": {
        "name": "大阪市",
        "list_url": "https://www.city.osaka.lg.jp/shiseikeiei/page/0000000000",
        "detail_pattern": "",
    },
    "kobe_city": {
        "name": "神戸市",
        "list_url": "https://www.city.kobe.lg.jp/a32000/shiseikeiei/nyusatsukekka/index.html",
        "detail_pattern": "",
    },
    "geps": {
        "name": "GEPS（政府電子調達システム）",
        "list_url": "https://www.geps.go.jp/index.html",
        "detail_pattern": "",
    },
}
# 暫定的な都道府県URLリスト（Step 9-10で順次拡充）
# 現時点では主要都市を中心に構成し、クローラの実装に合わせて詳細化する。

DEFAULT_AWARD_KEYWORDS: list = [
    "落札結果",
    "入札結果",
    "結果一覧",
    "契約結果",
    "kekka",
    "result",
]


def get_award_list_url(agency_key: str) -> Optional[str]:
    """指定キーの一覧URLを返す。見つからない場合はNone。"""
    entry = AWARD_URL_PATTERNS.get(agency_key)
    return entry["list_url"] if entry else None


def get_detail_url(agency_key: str, suffix: str) -> Optional[str]:
    """詳細URLを返す。pattern が空の場合はNone。"""
    entry = AWARD_URL_PATTERNS.get(agency_key)
    if not entry or not entry.get("detail_pattern"):
        return None
    return entry["detail_pattern"].format(suffix)
