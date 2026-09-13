#!/usr/bin/env python3
"""
Verification script for automatic site structure detection and selector generation.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler.parsers.structure_detector import StructureDetector
from crawler.parsers.selector_generator import SelectorGenerator
from crawler.parsers.fallback_selector import FallbackSelector
from crawler.parsers.structure_change_detector import StructureChangeDetector
from bs4 import BeautifulSoup


def main():
    print("=== Automatic Structure Detection and Selector Generation Verification ===\n")

    # Sample HTMLs for each structure type
    table_html = """
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

    list_html = """
    <html><body>
    <ul>
        <li>入札情報1</li>
        <li>入札情報2</li>
        <li>入札情報3</li>
    </ul>
    </body></html>
    """

    card_html = """
    <html><body>
    <div class="item">
        <h3>タイトル1</h3>
        <p>説明文1</p>
    </div>
    <div class="item">
        <h3>タイトル2</h3>
        <p>説明文2</p>
    </div>
    <div class="item">
        <h3>タイトル3</h3>
        <p>説明文3</p>
    </div>
    </body></html>
    """

    # Initialize components
    detector = StructureDetector()
    generator = SelectorGenerator()
    fallback = FallbackSelector()
    change_detector = StructureChangeDetector()

    # Test each structure
    for name, html in [("Table", table_html), ("List", list_html), ("Card", card_html)]:
        print(f"--- Testing {name} ---")
        soup = BeautifulSoup(html, 'html.parser')

        # Structure detection
        struct_type = detector.detect_structure(soup)
        print(f"Detected structure: {struct_type}")

        # Generate selector
        selector = generator.generate_selector(soup, struct_type)
        print(f"Generated selector: {selector}")

        # Validate selector by selecting elements
        if selector:
            elements = soup.select(selector)
            print(f"Selected {len(elements)} elements with generated selector")
            for i, el in enumerate(elements[:3]):  # show first 3
                print(f"  {i+1}: {el.get_text(strip=True)[:50]}")
        else:
            print("No selector generated")

        # Test fallback selector
        fallback_selectors = [
            selector if selector else "",
            "div.item",  # generic fallback
            "li",
            "td"
        ]
        # Remove empty strings
        fallback_selectors = [s for s in fallback_selectors if s]
        fallback_result = fallback.select_with_fallback(soup, fallback_selectors, min_results=1)
        if fallback_result:
            print(f"Fallback selector selected {len(fallback_result)} elements")
        else:
            print("Fallback selector failed")

        # Test change detector
        change_detector.record_success(selector if selector else "li", soup)
        changed = change_detector.has_changed(selector if selector else "li", soup, threshold=0.5)
        print(f"Change detector (same HTML): changed={changed}")

        # Simulate change by reducing elements
        if name == "Table":
            changed_html = "<table><tr><td>Only one</td></tr></table>"
        elif name == "List":
            changed_html = "<ul><li>Only one</li></ul>"
        else:
            changed_html = "<div class='item'><h3>Only one</h3></div>"
        changed_soup = BeautifulSoup(changed_html, 'html.parser')
        changed = change_detector.has_changed(selector if selector else "li", changed_soup, threshold=0.5)
        print(f"Change detector (reduced HTML): changed={changed}")

        print()

    print("=== Verification completed ===")


if __name__ == "__main__":
    main()