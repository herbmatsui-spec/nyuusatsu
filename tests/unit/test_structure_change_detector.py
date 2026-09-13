import sys
sys.path.insert(0, '.')

from crawler.parsers.structure_change_detector import StructureChangeDetector
from bs4 import BeautifulSoup


def test_record_and_has_changed():
    detector = StructureChangeDetector()
    html1 = """
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
        <li>Item 3</li>
    </ul>
    """
    soup1 = BeautifulSoup(html1, 'html.parser')
    selector = "ul > li"
    # Record success
    detector.record_success(selector, soup1)
    # Same HTML should not be changed
    assert not detector.has_changed(selector, soup1, threshold=0.5)

    # Reduced items: only one li
    html2 = """
    <ul>
        <li>Item 1</li>
    </ul>
    """
    soup2 = BeautifulSoup(html2, 'html.parser')
    assert detector.has_changed(selector, soup2, threshold=0.5)  # count dropped from 3 to 1 (< 3*0.5=1.5)

    # Increased items: 5 lis
    html3 = """
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
        <li>Item 3</li>
        <li>Item 4</li>
        <li>Item 5</li>
    </ul>
    """
    soup3 = BeautifulSoup(html3, 'html.parser')
    # Increased count should also be considered changed? Our implementation considers change if count < threshold * original OR text hash changed.
    # For increased count, count is not less than threshold * original, so we rely on text hash change.
    # The text hash will be different because we have more items, so it should be changed.
    assert detector.has_changed(selector, soup3, threshold=0.5)

    # Same count but different text: should change due to text hash
    html4 = """
    <ul>
        <li>Item 1 changed</li>
        <li>Item 2</li>
        <li>Item 3</li>
    </ul>
    """
    soup4 = BeautifulSoup(html4, 'html.parser')
    assert detector.has_changed(selector, soup4, threshold=0.5)

    # No prior record: should return False
    detector2 = StructureChangeDetector()
    assert not detector2.has_changed(selector, soup1, threshold=0.5)


def test_selector_hash():
    detector = StructureChangeDetector()
    hash1 = detector._selector_hash("selector")
    hash2 = detector._selector_hash("selector")
    assert hash1 == hash2
    hash3 = detector._selector_hash("different")
    assert hash1 != hash3


if __name__ == '__main__':
    test_record_and_has_changed()
    test_selector_hash()
    print("All tests passed")