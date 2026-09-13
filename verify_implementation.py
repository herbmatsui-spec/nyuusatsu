#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from crawler.config_driven_crawler import ConfigDrivenCrawler

# Test with sample config
crawler = ConfigDrivenCrawler("/home/herbmatsui/nyuusatsu/config/sample_detail_fields.yaml")

# Test HTML with various cases
html = """
<div class="price">1,234,567円</div>
<div class="date">2026.08.27</div>
<div class="title">   平成元年   </div>
<div class="empty">   </div>
"""

print("Testing ConfigDrivenCrawler.parse_detail:")
result = crawler.parse_detail(html)
print("Result:", result)

# Verification
print("\nVerification:")
print("field1 (price):", result.get("field1"), "should be 1234567")
print("field2 (date):", result.get("field2"), "should be 2026-08-27")
print("field3 (title):", result.get("field3"), "should be ['平成元年']")

# Check types
print("\nTypes:")
print("field1 type:", type(result.get("field1")))
print("field2 type:", type(result.get("field2")))
print("field3 type:", type(result.get("field3")))
