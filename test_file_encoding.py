
import os
import sys
from crawler.detail_extractor import BidDetailExtractor

def test_file_encoding():
    fixture_path = "tests/fixtures/detail_page_sample.html"
    if not os.path.exists(fixture_path):
        print(f"Error: Fixture file not found at {fixture_path}")
        return

    print(f"--- Reading file: {fixture_path} ---")
    try:
        # UTF-8 explicitly specified
        with open(fixture_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        print(f"File read successfully. Length: {len(html_content)}")
        print(f"Raw HTML repr (first 200 chars): {repr(html_content[:200])}")

        extractor = BidDetailExtractor()
        result = extractor.extract_from_html(html_content)

        print("\n--- Extraction Result ---")
        for key, value in result.items():
            print(f"{key}: {repr(value)}")

        # Validation
        success = True
        if " budget" in result and result["budget"] and "�" in result["budget"]:
            print("\n[FAIL] Budget contains mojibake")
            success = False
        if " announcement_date" in result and result["announcement_date"] and "�" in result["announcement_date"]:
            print("\n[FAIL] Announcement date contains mojibake")
            success = False
        
        if success:
            print("\n[SUCCESS] No mojibake detected in extracted fields!")
        else:
            print("\n[FAIL] Mojibake detected in extracted fields.")

    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_file_encoding()
