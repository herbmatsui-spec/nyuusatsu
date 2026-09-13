"""
Structure detection module for automatic selector generation.
"""
from bs4 import BeautifulSoup, Tag
from typing import List, Optional


class StructureDetector:
    """Detects common HTML structures like tables, lists, and cards."""

    @staticmethod
    def detect_table_structure(soup: BeautifulSoup) -> float:
        """
        Detects if the HTML contains a table-like structure.
        Returns a confidence score between 0.0 and 1.0.
        """
        tables = soup.find_all('table')
        if not tables:
            return 0.0

        # Score based on number of rows and cells
        max_score = 0.0
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2:  # need at least header and one data row
                continue
            # Count cells per row to ensure consistency
            cell_counts = []
            for row in rows:
                cells = row.find_all(['td', 'th'])
                cell_counts.append(len(cells))
            if not cell_counts:
                continue
            # Consistency: low variance in cell count
            import statistics
            if len(cell_counts) > 1:
                try:
                    stdev = statistics.stdev(cell_counts)
                    consistency = max(0.0, 1.0 - stdev / (max(cell_counts) + 1))
                except statistics.StatisticsError:
                    consistency = 0.0
            else:
                consistency = 1.0 if cell_counts[0] > 0 else 0.0
            # Row count factor
            row_factor = min(1.0, len(rows) / 20)  # saturate at 20 rows
            score = (consistency * 0.6 + row_factor * 0.4)
            if score > max_score:
                max_score = score
        return max_score

    @staticmethod
    def detect_list_structure(soup: BeautifulSoup) -> float:
        """
        Detects if the HTML contains a list-like structure (ul/ol with repeated li).
        Returns a confidence score between 0.0 and 1.0.
        """
        lists = soup.find_all(['ul', 'ol'])
        if not lists:
            return 0.0

        max_score = 0.0
        for lst in lists:
            items = lst.find_all('li', recursive=False)  # only direct children
            if len(items) < 2:
                continue
            # Check if items have similar structure (e.g., each contains similar tags)
            # Simple heuristic: count of child elements per li
            child_counts = []
            for item in items:
                child_counts.append(len(list(item.find_all())))
            if not child_counts:
                continue
            import statistics
            if len(child_counts) > 1:
                try:
                    stdev = statistics.stdev(child_counts)
                    consistency = max(0.0, 1.0 - stdev / (max(child_counts) + 1))
                except statistics.StatisticsError:
                    consistency = 0.0
            else:
                consistency = 1.0 if child_counts[0] > 0 else 0.0
            # Item count factor
            item_factor = min(1.0, len(items) / 30)  # saturate at 30 items
            score = (consistency * 0.6 + item_factor * 0.4)
            if score > max_score:
                max_score = score
        return max_score

    @staticmethod
    def detect_card_structure(soup: BeautifulSoup) -> float:
        """
        Detects if the HTML contains a card-like structure (repeated divs with similar class patterns).
        Returns a confidence score between 0.0 and 1.0.
        This is a simplified heuristic.
        """
        # Find all div elements that might be cards
        divs = soup.find_all('div', class_=True)
        if not divs:
            return 0.0

        # Group by class attribute
        class_groups = {}
        for div in divs:
            classes = tuple(sorted(div.get('class', [])))
            class_groups.setdefault(classes, []).append(div)

        max_score = 0.0
        for classes, group in class_groups.items():
            if len(group) < 2:
                continue
            # Check similarity of internal structure (e.g., number of child elements)
            child_counts = []
            for div in group:
                child_counts.append(len(list(div.find_all())))
            if not child_counts:
                continue
            import statistics
            if len(child_counts) > 1:
                try:
                    stdev = statistics.stdev(child_counts)
                    consistency = max(0.0, 1.0 - stdev / (max(child_counts) + 1))
                except statistics.StatisticsError:
                    consistency = 0.0
            else:
                consistency = 1.0 if child_counts[0] > 0 else 0.0
            # Group size factor
            group_factor = min(1.0, len(group) / 10)  # saturate at 10 cards
            score = (consistency * 0.6 + group_factor * 0.4)
            if score > max_score:
                max_score = score
        return max_score

    @staticmethod
    def detect_structure(soup: BeautifulSoup) -> str:
        """
        Detects the most likely structure type among table, list, card.
        Returns one of 'table', 'list', 'card', or 'unknown'.
        """
        scores = {
            'table': StructureDetector.detect_table_structure(soup),
            'list': StructureDetector.detect_list_structure(soup),
            'card': StructureDetector.detect_card_structure(soup),
        }
        # Determine max score
        max_type = max(scores, key=scores.get)
        max_score = scores[max_type]
        if max_score < 0.3:  # threshold for detection
            return 'unknown'
        return max_type
