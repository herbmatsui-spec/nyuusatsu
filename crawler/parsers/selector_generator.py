"""
Selector generation module for automatic selector generation.
"""
from bs4 import BeautifulSoup, Tag
from typing import Optional, List
import re


class SelectorGenerator:
    """Generates CSS selectors based on detected HTML structure."""

    @staticmethod
    def generate_table_selector(soup: BeautifulSoup) -> Optional[str]:
        """
        Generates a CSS selector for table data cells.
        Assumes the first row may be header and selects data cells in each row.
        Returns selector like 'tbody tr td:nth-child(1)' for first column,
        but we need to return a selector that can extract all cells? Actually we need
        a selector that selects the data elements we want to extract.
        For simplicity, we return a selector that selects all td elements in rows
        after the first row (assuming first row is header).
        """
        table = soup.find('table')
        if not table:
            return None
        # Determine if there is a thead or tbody
        # We'll generate a selector for td elements in rows that are not the first row.
        # Use: 'tr:not(:first-child) td'
        # However, CSS :not(:first-child) may not be supported in older browsers but
        # BeautifulSoup's selector uses SoupSieve which supports :not.
        # Let's generate a more robust selector: 'tr td' and then we can skip first row in code.
        # But the requirement is to generate a CSS selector string.
        # We'll generate 'tbody tr td' if tbody exists, else 'tr td'.
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
        else:
            rows = table.find_all('tr')
        if len(rows) < 2:
            return None
        # Assume first row is header; we want data rows.
        # Generate selector for td/th in data rows.
        # We'll generate a selector that selects all td elements in rows after the first.
        # Use: 'tr td' but we need to skip first row. Use 'tr:nth-child(n+2) td'
        if tbody:
            selector = 'tbody tr:nth-child(n+2) td'
        else:
            selector = 'tr:nth-child(n+2) td'
        return selector

    @staticmethod
    def generate_list_selector(soup: BeautifulSoup) -> Optional[str]:
        """
        Generates a CSS selector for list items.
        Returns selector like 'li' or 'ul li', 'ol li'.
        """
        lst = soup.find(['ul', 'ol'])
        if not lst:
            return None
        # Determine if ul or ol
        tag = lst.name
        # Selector for direct child li elements
        selector = f'{tag} > li'
        return selector

    @staticmethod
    def generate_card_selector(soup: BeautifulSoup) -> Optional[str]:
        """
        Generates a CSS selector for card containers.
        Attempts to find repeated div patterns with similar class.
        Returns selector like 'div.card' or more specific.
        """
        # Find all div with class
        divs = soup.find_all('div', class_=True)
        if not divs:
            return None
        # Group by class tuple
        class_groups = {}
        for div in divs:
            classes = tuple(sorted(div.get('class', [])))
            class_groups.setdefault(classes, []).append(div)
        # Find the group with most members (at least 2)
        best_group = None
        best_count = 0
        for classes, group in class_groups.items():
            if len(group) >= 2 and len(group) > best_count:
                best_count = len(group)
                best_group = (classes, group)
        if not best_group:
            return None
        classes, _ = best_group
        # Build selector: div.class1.class2...
        class_str = '.'.join(classes)
        selector = f'div.{class_str}'
        return selector

    @staticmethod
    def generate_selector(soup: BeautifulSoup, structure_type: str) -> Optional[str]:
        """
        Dispatches to appropriate generator based on structure_type.
        """
        if structure_type == 'table':
            return SelectorGenerator.generate_table_selector(soup)
        elif structure_type == 'list':
            return SelectorGenerator.generate_list_selector(soup)
        elif structure_type == 'card':
            return SelectorGenerator.generate_card_selector(soup)
        else:
            return None
