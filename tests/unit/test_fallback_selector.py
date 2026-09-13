import sys
sys.path.insert(0, '.')

from crawler.parsers.fallback_selector import FallbackSelector
from bs4 import BeautifulSoup


def test_select_with_fallback():
    html = """
    <div>
        <p class="a">Text A</p>
        <p class="b">Text B</p>
        <p class="c">Text C</p>
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    # First selector matches nothing, second matches one, third matches three
    selectors = ['.nonexistent', '.a', '.b']
    result = FallbackSelector.select_with_fallback(soup, selectors, min_results=1)
    assert result is not None
    assert len(result) == 1
    assert result[0].get_text(strip=True) == 'Text A'

    # min_results=2: first selector that gives at least 2 is '.b'? Actually '.b' gives 1, '.c' not in list.
    # We need to adjust: let's make selectors: ['.nonexistent', '.a', '.b', '.c']
    selectors = ['.nonexistent', '.a', '.b', '.c']
    result = FallbackSelector.select_with_fallback(soup, selectors, min_results=2)
    # '.a' gives 1, '.b' gives 1, '.c' gives 1 -> none gives 2, so result should be None
    assert result is None

    # Now with a selector that matches multiple: let's use 'p'
    selectors = ['.nonexistent', 'p']
    result = FallbackSelector.select_with_fallback(soup, selectors, min_results=2)
    assert result is not None
    assert len(result) == 3

    # Invalid selector syntax should be skipped
    selectors = ['>>invalid', '.a']
    result = FallbackSelector.select_with_fallback(soup, selectors, min_results=1)
    assert result is not None
    assert len(result) == 1
    assert result[0].get_text(strip=True) == 'Text A'


def test_select_first_with_fallback():
    html = """
    <div>
        <p class="a">Text A</p>
        <p class="b">Text B</p>
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    selectors = ['.nonexistent', '.b', '.a']  # note: .b comes before .a
    element = FallbackSelector.select_first_with_fallback(soup, selectors)
    assert element is not None
    assert element.get_text(strip=True) == 'Text B'  # because .b is first that matches

    # No match
    selectors = ['.nonexistent', '.z']
    element = FallbackSelector.select_first_with_fallback(soup, selectors)
    assert element is None


if __name__ == '__main__':
    test_select_with_fallback()
    test_select_first_with_fallback()
    print("All tests passed")