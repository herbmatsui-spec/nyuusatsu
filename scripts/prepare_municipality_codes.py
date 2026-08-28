import csv
import os

def generate_municipality_code_list():
    """
    全国の市区町村コード（地方公共団体コード）のダミー/構造を生成します。
    実際には総務省のデータをインポートしますが、実装計画のステップ19として
    構造を定義し、インポート準備を整えます。
    """
    # 実際には数千件になりますが、ここでは主要なサンプルを定義し、
    # 形式を確定させます。
    # 形式: municipality_code, prefecture_name, municipality_name, type (city/town/village)
    
    municipalities = [
        ["011001", "北海道", "札幌市", "city"],
        ["021001", "青森県", "青森市", "city"],
        ["031001", "岩手県", "盛岡市", "city"],
        ["041001", "宮城県", "仙台市", "city"],
        ["382001", "愛媛県", "松山市", "city"],
        ["382002", "愛媛県", "今治市", "city"],
        ["382003", "愛媛県", "宇和島市", "city"],
        ["382004", "愛媛県", "八幡浜市", "city"],
        ["382005", "愛媛県", "新居浜市", "city"],
        ["382006", "愛媛県", "西条市", "city"],
        ["382007", "愛媛県", "大洲市", "city"],
        ["382008", "愛媛県", "伊予市", "city"],
        ["382009", "愛媛県", "四国中央市", "city"],
        ["382010", "愛媛県", "西予市", "city"],
        ["382011", "愛媛県", "東温市", "city"],
        ["384001", "愛媛県", "上島町", "town"],
        ["384002", "愛媛県", "久万高原町", "town"],
        ["384003", "愛媛県", "松前町", "town"],
        ["384004", "愛媛県", "砥部町", "town"],
        ["384005", "愛媛県", "内子町", "town"],
        ["384006", "愛媛県", "伊方町", "town"],
        ["384007", "愛媛県", "松野町", "town"],
        ["384008", "愛媛県", "鬼北町", "town"],
        ["384009", "愛媛県", "愛南町", "town"],
    ]

    file_path = "data/master_municipalities.csv"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["municipality_code", "prefecture_name", "municipality_name", "type"])
        writer.writerows(municipalities)

    print(f"Successfully created {file_path} with {len(municipalities)} entries.")

if __name__ == "__main__":
    generate_municipality_code_list()
