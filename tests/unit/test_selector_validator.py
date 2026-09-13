import sys
sys.path.insert(0, '.')

from crawler.utils.selector_validator import validate_selector, validate_selectors, find_first_valid_selector


def test_validate_selector():
    html = '''
    <div class="item">
        <span class="title">Test</span>
        <span class="price">1000</span>
    </div>
    '''
    # Valid selector
    is_valid, count = validate_selector(html, '.title')
    assert is_valid == True
    assert count == 1

    # Valid selector with multiple matches
    html2 = '''
    <div>
        <span class="price">100</span>
        <span class="price">200</span>
        <span class="price">300</span>
    </div>
    '''
    is_valid, count = validate_selector(html2, '.price')
    assert is_valid == True
    assert count == 3

    # Invalid selector (no match)
    is_valid, count = validate_selector(html, '.nonexistent')
    assert is_valid == False
    assert count == 0

    # Invalid selector syntax
    is_valid, count = validate_selector(html, '>>invalid')
    assert is_valid == False
    assert count == 0


def test_validate_selectors():
    html = '''
    <div class="item">
        <span class="title">Test</span>
        <span class="price">1000</span>
    </div>
    '''
    selectors = ['.title', '.price', '.nonexistent']
    results = validate_selectors(html, selectors)
    assert len(results) == 3
    assert results[0] == ('.title', True, 1)
    assert results[1] == ('.price', True, 1)
    assert results[2] == ('.nonexistent', False, 0)


def test_find_first_valid_selector():
    html = '''
    <div>
        <span class="first">First</span>
        <span class="second">Second</span>
    </div>
    '''
    # First selector is valid
    selector, count = find_first_valid_selector(html, ['.first', '.second'])
    assert selector == '.first'
    assert count == 1

    # First selector invalid, second valid
    selector, count = find_first_valid_selector(html, ['.nonexistent', '.second'])
    assert selector == '.second'
    assert count == 1

    # All invalid
    selector, count = find_first_valid_selector(html, ['.nonexistent1', '.nonexistent2'])
    assert selector == ''
    assert count == 0


if __name__ == '__main__':
    test_validate_selector()
    test_validate_selectors()
    test_find_first_valid_selector()
    print("All tests passed")