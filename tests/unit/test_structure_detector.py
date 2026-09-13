import sys
sys.path.insert(0, '.')

from crawler.parsers.structure_detector import StructureDetector
from bs4 import BeautifulSoup


def test_detect_table_structure():
    # Simple table with header and two rows
    html = """
    <table>
        <tr><th>Name</th><th>Value</th></tr>
        <tr><td>A</td><td>1</td></tr>
        <tr><td>B</td><td>2</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    score = StructureDetector.detect_table_structure(soup)
    assert score > 0.5, f"Expected high score for table, got {score}"

    # No table
    html = "<div><p>Hello</p></div>"
    soup = BeautifulSoup(html, 'html.parser')
    score = StructureDetector.detect_table_structure(soup)
    assert score == 0.0, f"Expected 0 for no table, got {score}"


def test_detect_list_structure():
    # Simple list with three items
    html = """
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
        <li>Item 3</li>
    </ul>
    """
    soup = BeautifulSoup(html, 'html.parser')
    score = StructureDetector.detect_list_structure(soup)
    assert score > 0.5, f"Expected high score for list, got {score}"

    # No list
    html = "<div><p>Hello</p></div>"
    soup = BeautifulSoup(html, 'html.parser')
    score = StructureDetector.detect_list_structure(soup)
    assert score == 0.0, f"Expected 0 for no list, got {score}"


def test_detect_card_structure():
    # Simple cards: two divs with same class
    html = """
    <div class="card"><h2>Title</h2><p>Desc</p></div>
    <div class="card"><h2>Title2</h2><p>Desc2</p></div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    score = StructureDetector.detect_card_structure(soup)
    assert score > 0.5, f"Expected high score for card, got {score}"

    # No cards (only one div with class)
    html = """
    <div class="card"><h2>Title</h2><p>Desc</p></div>
    <div><p>Other</p></div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    score = StructureDetector.detect_card_structure(soup)
    # Should be low because we need at least two similar cards
    assert score < 0.5, f"Expected low score for insufficient cards, got {score}"


def test_detect_structure():
    # Table
    html = """
    <table><tr><th>Name</th><th>Value</th></tr><tr><td>A</td><td>1</td></tr></table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    struct = StructureDetector.detect_structure(soup)
    assert struct == 'table', f"Expected 'table', got {struct}"

    # List
    html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
    soup = BeautifulSoup(html, 'html.parser')
    struct = StructureDetector.detect_structure(soup)
    assert struct == 'list', f"Expected 'list', got {struct}"

    # Card
    html = """
    <div class='card'><h2>Title</h2><p>Desc</p></div>
    <div class='card'><h2>Title2</h2><p>Desc2</p></div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    struct = StructureDetector.detect_structure(soup)
    assert struct == 'card', f"Expected 'card', got {struct}"

    # Unknown
    html = "<div><p>Hello</p></div>"
    soup = BeautifulSoup(html, 'html.parser')
    struct = StructureDetector.detect_structure(soup)
    assert struct == 'unknown', f"Expected 'unknown', got {struct}"


if __name__ == '__main__':
    test_detect_table_structure()
    test_detect_list_structure()
    test_detect_card_structure()
    test_detect_structure()
    print("All tests passed")