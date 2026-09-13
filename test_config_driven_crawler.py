#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from crawler.config_driven_crawler import ConfigDrivenCrawler

# Load sample config
config_path = os.path.join(os.path.dirname(__file__), "config", "sample_detail_fields.yaml")
crawler = ConfigDrivenCrawler(config_path)

# Sample HTML with elements matching the selectors
html = """
<div class="price">1,234,567円</div>
<div class="date">2026.08.27</div>
<div class="title">   平成元年   </div>
"""

# Test parse_detail
result = crawler.parse_detail(html)
print("Parsed result:")
print(result)
