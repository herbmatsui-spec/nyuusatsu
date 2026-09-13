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
        If tbody exists, selects all td inside tbody (assuming header is in thead).
        If no tbody, selects td in tr that are not the first tr (imperfect but works for simple tables).
        """
        table = soup.find('table')
        if not table:
            return None
        tbody = table.find('tbody')
        if tbody:
            # Assume header is in thead, all tr in tbody are data rows
            selector = 'tbody td'
        else:
            # No tbody, try to skip the first tr (header) if possible
            rows = table.find_all('tr')
            if len(rows) < 2:
                return None
            selector = 'table tr:not(:first-child) td'
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
    def generate_card_selector(soup) -> Optional[str]:
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