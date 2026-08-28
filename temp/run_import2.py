import sys
sys.path.append('D:/入札システム')
from scripts.import_master_agencies import import_agencies_from_csv
import_agencies_from_csv('data/master_ministries.csv', '国', priority_default=1)
import_agencies_from_csv('data/master_prefectures.csv', '都道府県', priority_default=1)
import_agencies_from_csv('data/master/municipality_codes.csv', '市区町村', priority_default=2)
print('Import executed')
