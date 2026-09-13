# 市区町村のポータルURL辞書
# 構造: { 都道府県名: { 市区町村名: URL, ... }, ... }
# 実際のデータは data/master/municipality_codes.csv などから生成することを想定

MUNICIPALITY_SOURCES = {
    # 例: "東京都": {
    #     "千代田区": "https://www.city.chiyoda.lg.jp/",
    #     "中央区": "https://www.city.chuo.lg.jp/",
    # },
}
# 実際の運用では、データファイルから自動生成するスクリプトを用意すること