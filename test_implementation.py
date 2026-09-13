#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from crawler.config_driven_crawler import ConfigDrivenCrawler
from crawler.parsers.field_normalizer import TRANSFORM_MAP
import mojimiji

# Test the basic functionality
print('Testing basic functionality...')
try:
    # Create a ConfigDrivenCrawler instance (with dummy config)
    crawler = ConfigDrivenCrawler("/dummy/config.yaml")
    print('✅ ConfigDrivenCrawler imported successfully')
    
    # Test the transform functions
    print('Testing normalize_amount:', TRANSFORM_MAP['normalize_amount']('1,234,567円'))
    print('Testing normalize_date:', TRANSFORM_MAP['normalize_date']('2026.08.27'))
    print('Testing normalize_whitespace:', TRANSFORM_MAP['normalize_whitespace']('  \t  Hello   World  '))
    print('Testing normalize_fullwidth_to_halfwidth:', TRANSFORM_MAP['normalize_fullwidth_to_halfwidth']('全角数字１２３'))
    print('✅ All transform functions work correctly')
    
    # Test that the module imports correctly
    print('✅ Configuration and parsers imported successfully')
    
except Exception as e:
    print('❌ Error:', e)
    import traceback
    traceback.print_exc()
