import sys
sys.path.insert(0, '.')

from crawler.parsers.selector_generator import SelectorGenerator
from bs4 import BeautifulSoup


def test_generate_table_selector():
    # Case 1: table with thead and tbody
    html = """
    <table>
        <thead><tr><th>Name</th><th>Value</th></tr></thead>
        <tbody>
            <tr><td>A</td><td>1</td></tr>
            <tr><td>B</td><td>2</td></tr>
        </tbody>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    selector = SelectorGenerator.generate_table_selector(soup)
    assert selector is not None, "Expected a selector for table"
    # With tbody, we expect 'tbody td'
    assert selector == 'tbody td', f"Expected 'tbody td', got {selector}"
    selected = soup.select(selector)
    # Expect 4 td elements: A,1,B,2
    assert len(selected) == 4, f"Expected 4 td elements, got {len(selected)}"
    texts = [elem.get_text(strip=True) for elem in selected]
    assert texts == ['A', '1', 'B', '2'], f"Expected ['A', '1', 'B', '2'], got {texts}"

    # Case 2: table without thead/tbody (just tr under table)
    html = """
    <table>
        <tr><th>Name</th><th>Value</th></tr>
        <tr><td>A</td><td>1</td></tr>
        <tr><td>B</td><td>2</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    selector = SelectorGenerator.generate_table_selector(soup)
    assert selector is not None, "Expected a selector for table without tbody"
    # Expect 'table tr:not(:first-child) td'
    assert selector == 'table tr:not(:first-child) td', f"Expected 'table tr:not(:first-child) td', got {selector}"
    selected = soup.select(selector)
    # Expect 2 td elements: A,1 from the second tr? Wait, the selector will select td from tr that are not the first tr.
    # The tr elements: first tr is header, second tr is first data row, third tr is second data row.
    # The selector will select the second and third tr (because they are not the first tr).
    # So we expect td from second and third tr: A,1,B,2 -> 4 elements.
    # But note: the selector 'table tr:not(:first-child) td' has the same flaw as before: it selects tr that are not the first child of their parent.
    # In this case, all tr are direct children of table, so:
    #   first tr: index 1 -> first child -> excluded
    #   second tr: index 2 -> not first child -> included
    #   third tr: index 3 -> not first child -> included
    # So we get both data rows -> 4 elements.
    assert len(selected) == 4, f"Expected 4 td elements, got {len(selected)}"
    texts = [elem.get_text(strip=True) for elem in selected]
    assert texts == ['A', '1', 'B', '2'], f"Expected ['A', '1', 'B', '2'], got {texts}"

    # Case 3: table with less than 2 rows
    html = "<table><tr><th>Name</th><th>Value</th></tr></table>"
    soup = BeautifulSoup(html, 'html.parser')
    selector = SelectorGenerator.generate_table_selector(soup)
    assert selector is None, f"Expected None for table with one row, got {selector}"


def test_generate_list_selector():
    html = """
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
    </ul>
    """
    soup = BeautifulSoup(html, 'html.parser')
    selector = SelectorGenerator.generate_list_selector(soup)
    assert selector == "ul > li", f"Expected 'ul > li', got {selector}"
    selected = soup.select(selector)
    assert len(selected) == 2
    texts = [elem.get_text(strip=True) for elem in selected]
    assert texts == ['Item 1', 'Item 2']

    html = """
    <ol>
        <li>Item 1</li>
        <li>Item 2</li>
    </ol>
    """
    soup = BeautifulSoup(html, 'html.parser')
    selector = SelectorGenerator.generate_list_selector(soup)
    assert selector == "ol > li"
    selected = soup.select(selector)
    assert len(selected) == 2

    # No list
    html = "<div><p>Hello</p></div>"
    soup = BeautifulSoup(html, 'html.parser')
    selector = SelectorGenerator.generate_list_selector(soup)
    assert selector is None


def test_generate_card_selector():
  html = """
  <div class="card"><h2>Title</h2><p>Desc</p></div>
  <div class="card"><h2>Title2</h2><p>Desc2</p></div>
  """
  soup = BeautifulSoup(html, 'html.parser')
  selector = SelectorGenerator.generate_card_selector(soup)
  assert selector == "div.card", f"Expected 'div.card', got {selector}"
  selected = soup.select(selector)
  assert len(selected) == 2

  # Different classes
  html = """
  <div class="card"><h2>Title</h2><p>Desc</p></div>
  <div class="card alt"><h2>Title2</h2><p>Desc2</p></div>
  """
  soup = BeautifulSoup(html, 'html.parser')
  selector = SelectorGenerator.generate_card_selector(soup)
  # Should still find the group with most members? Both classes appear once each, so no group with >=2?
  # Actually, we group by class tuple. First div: ('card',), second div: ('card', 'alt')
  # So each group has size 1 -> no selector generated.
  assert selector is None, f"Expected None for mismatched classes, got {selector}"

  # No divs with class
  html = "<div><h2>Title</h2><p>Desc</p></div><div><h2>Title2</h2><p>Desc2</p></div>"
  soup = BeautifulSoup(html, 'html.parser')
  selector = SelectorGenerator.generate_card_selector(soup)
  assert selector is None


def test_generate_selector():
  # Table
  html = "<table><tr><th>Name</th><th>Value</th></tr><tr><td>A</td><td>1</td></tr></table>"
  soup = BeautifulSoup(html, 'html.parser')
  selector = SelectorGenerator.generate_selector(soup, 'table')
  assert selector is not None
  # List
  html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
  soup = BeautifulSoup(html, 'html.parser')
  selector = SelectorGenerator.generate_selector(soup, 'list')
  assert selector is not None
  # Card
  html = """
  <div class='card'><h2>Title</h2><p>Desc</p></div>
  <div class='card'><h2>Title2</h2><p>Desc2</p></div>
  """
  soup = BeautifulSoup(html, 'html.parser')
  selector = SelectorGenerator.generate_selector(soup, 'card')
  assert selector is not None
  # Unknown
  html = "<div><p>Hello</p></div>"
  soup = BeautifulSoup(html, 'html.parser')
  selector = SelectorGenerator.generate_selector(soup, 'unknown')
  assert selector is None


if __name__ == '__main__':
  test_generate_table_selector()
  test_generate_list_selector()
  test_generate_card_selector()
  test_generate_selector()
  print("All tests passed")