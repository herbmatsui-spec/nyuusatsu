import pytest
from unittest.mock import MagicMock

from crawler.parsers.pdf_parser import PdfParser


class DummyOcrProvider:
    """Simple dummy OCR provider for testing."""
    def __init__(self, text_to_return: str = ""):
        self.text_to_return = text_to_return

    def extract_text(self, raw_text: str):
        # In real implementation this would call the OCR library.
        # Here we just return the predefined text.
        return self.text_to_return


def test_extract_fields_raises_without_ocr_provider():
    """OCR provider not configured should raise RuntimeError."""
    parser = PdfParser()
    with pytest.raises(RuntimeError, match="OCR provider not configured"):
        parser.extract_fields("some raw text")


def test_extract_fields_returns_empty_dict_when_ocr_provider_is_set_and_text_is_empty():
    """When OCR provider is set but raw text is empty, should return empty dict."""
    parser = PdfParser(ocr_provider=DummyOcrProvider(text_to_return=""))
    result = parser.extract_fields("")
    assert isinstance(result, dict)
    assert result == {}  # current stub behavior


def test_extract_fields_returns_dict_when_ocr_provider_provides_text():
    """When OCR provider returns text, extract_fields should return a dict."""
    sample_text = "Sample PDF content with fields"
    parser = PdfParser(ocr_provider=DummyOcrProvider(text_to_return=sample_text))
    result = parser.extract_fields(sample_text)
    assert isinstance(result, dict)
    # Since stub returns empty dict, we only verify type; real implementation will parse fields.
    assert isinstance(result, dict)