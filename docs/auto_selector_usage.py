#!/usr/bin/env python3
"""
Example usage of automatic site structure detection and selector generation.

This script demonstrates how to use the automatic selector feature
added to BaseCrawler in the crawler module.
"""

from crawler.base_crawler import BaseCrawler
from bs4 import BeautifulSoup


# Example subclass of BaseCrawler for demonstration
class ExampleCrawler(BaseCrawler):
    def parse_list(self, html):
        # Not used in this example
        return []

    def parse_detail(self, html):
        # Not used in this example
        return None

    def extract_item_date(self, item):
        # Not used in this example
        return None

    def save(self, items):
        # Not used in this example
        pass


def main():
    # Create a crawler instance with automatic selector enabled
    crawler = ExampleCrawler(use_auto_selector=True)

    # Sample HTML containing a table
    html_table = """
    <html><body>
    <table>
        <thead><tr><th>項目</th><th>価格</th></tr></thead>
        <tbody>
            <tr><td>商品A</td><td>1000円</td></tr>
            <tr><td>商品B</td><td>2000円</td></tr>
            <tr><td>商品C</td><td>1500円</td></tr>
        </tbody>
    </table>
    </body></html>
    """

    # Use automatic selector with fallback to traditional selectors
    # For table data, we might want to extract each cell, but for example
    # we'll just get all td elements after the header (as generated selector does)
    fallback_selectors = [
        'td',  # fallback to all td cells
        'div.data',  # another fallback
    ]

    selected = crawler.auto_select_with_fallback(html_table, fallback_selectors)
    print(f"Automatically selected {len(selected)} elements:")
    for i, elem in enumerate(selected[:5]):  # show first 5
        print(f"  {i+1}: {elem.get_text(strip=True)}")

    # If we want to record success for change detection
    if selected:
        # We need a selector string to record; we can generate one again
        # or use the one that was selected (but we don't have it stored).
        # For simplicity, we'll generate a selector from the structure.
        from crawler.parsers.structure_detector import StructureDetector
        from crawler.parsers.selector_generator import SelectorGenerator
        soup = BeautifulSoup(html_table, 'html.parser')
        struct_type = StructureDetector.detect_structure(soup)
        selector = SelectorGenerator.generate_selector(soup, struct_type)
        if selector:
            crawler.record_selector_success(selector, html_table)
            print(f"\nRecorded success for selector: {selector}")

            # Later, we can check if the selector results have changed
            # (using new HTML)
            html_table_changed = """
            <html><body>
            <table>
                <thead><tr><th>項目</th><th>価格</th></tr></thead>
                <tbody>
                    <tr><td>商品A</td><td>1000円</td></tr>
                    <!-- Only one row now -->
                </tbody>
            </table>
            </body></html>
            """
            changed = crawler.has_selector_changed(selector, html_table_changed, threshold=0.5)
            print(f"Selector changed? (should be True due to fewer rows): {changed}")

    # Example with list HTML
    html_list = """
    <html><body>
    <ul>
        <li>入札情報1</li>
        <li>入札情報2</li>
        <li>入札情報3</li>
    </ul>
    </body></html>
    """
    selected_list = crawler.auto_select_with_fallback(html_list, ['li'])
    print(f"\nFor list HTML, selected {len(selected_list)} elements:")
    for i, elem in enumerate(selected_list[:5]):
        print(f"  {i+1}: {elem.get_text(strip=True)}")


if __name__ == "__main__":
    main()
