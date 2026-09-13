import csv
import sys

# Mapping from prefecture name to region code (numeric)
# We'll define regions as per standard Japanese regions
region_map = {
    "北海道": 1,
    "青森県": 2, "岩手県": 2, "宮城県": 2, "秋田県": 2, "山形県": 2, "福島県": 2,
    "茨城県": 3, "栃木県": 3, "群馬県": 3, "埼玉県": 3, "千葉県": 3, "東京都": 3, "神奈川県": 3,
    "新潟県": 4, "富山県": 4, "石川県": 4, "福井県": 4, "山梨県": 4, "長野県": 4,
    "岐阜県": 4, "静岡県": 4, "愛知県": 4,
    "三重県": 5, "滋賀県": 5, "京都府": 5, "大阪府": 5, "兵庫県": 5, "奈良県": 5, "和歌山県": 5,
    "鳥取県": 6, "島根県": 6, "岡山県": 6, "広島県": 6, "山口県": 6,
    "徳島県": 7, "香川県": 7, "愛媛県": 7, "高知県": 7,
    "福岡県": 8, "佐賀県": 8, "長崎県": 8, "熊本県": 8, "大分県": 8, "宮崎県": 8, "鹿児島県": 8,
    "沖縄県": 9,
}

def main():
    input_path = '/tmp/pref_raw.csv'
    output_path = 'data/prefectures.csv'
    
    with open(input_path, 'r', encoding='utf-8') as f_in:
        reader = csv.reader(f_in)
        header = next(reader)  # skip header
        rows = []
        pref_id = 1
        for row in reader:
            # row: [団体コード, 都道府県名(漢字), 市区町村名(漢字), 都道府県名(カナ), 市区町村名(カナ)]
            if row[2] == '' and row[4] == '':  # prefecture level
                pref_code_full = row[0]  # e.g., '010006'
                pref_code = pref_code_full[:2]  # first two digits
                pref_name = row[1]
                pref_kana = row[3]
                region = region_map.get(pref_name, '')
                rows.append([pref_id, pref_name, pref_code, pref_kana, region])
                pref_id += 1
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f_out:
        writer = csv.writer(f_out)
        writer.writerow(['id', 'name', 'code', 'kana_name', 'region_code'])
        writer.writerows(rows)
    
    print(f'Created {output_path} with {len(rows)} prefectures.')

if __name__ == '__main__':
    main()