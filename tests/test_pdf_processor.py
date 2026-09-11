import pytest
from unittest.mock import Mock, patch, mock_open
from io import BytesIO

from services.pdf_processor import PDFProcessor
from exceptions import PDFExtractionError, OCRProcessingError
from config import AppConfig
from pdfplumber.utils.exceptions import PdfminerException


class TestPDFProcessor:
    def test_init_with_config(self):
        config = AppConfig()
        processor = PDFProcessor(config=config)
        assert processor.config is config

    def test_init_without_config(self):
        processor = PDFProcessor()
        assert isinstance(processor.config, AppConfig)

    def test_extract_text_from_path_success(self):
        # Mock pdfplumber.open to return a mock PDF with one page containing text
        mock_pdf = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "Hello world"
        mock_page.extract_tables.return_value = []
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)

        with patch("services.pdf_processor.pdfplumber.open", return_value=mock_pdf) as mock_open:
            processor = PDFProcessor()
            result = processor.extract_text("/fake/path.pdf", source_name="test.pdf")
            assert result == "Hello world"
            mock_open.assert_called_once_with("/fake/path.pdf")

    def test_extract_text_from_bytes_success(self):
        mock_pdf = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "Hello from bytes"
        mock_page.extract_tables.return_value = []
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)

        with patch("services.pdf_processor.pdfplumber.open", return_value=mock_pdf):
            processor = PDFProcessor()
            pdf_bytes = BytesIO(b"dummy")
            result = processor.extract_text(pdf_bytes, source_name="test.pdf")
            assert result == "Hello from bytes"

    def test_extract_text_with_tables(self):
        mock_pdf = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "Page text"
        mock_page.extract_tables.return_value = [[["Cell1", "Cell2"], ["Cell3", "Cell4"]]]
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)

        with patch("services.pdf_processor.pdfplumber.open", return_value=mock_pdf):
            processor = PDFProcessor()
            result = processor.extract_text("/fake/path.pdf")
            # Expect the page text plus the table rows joined by spaces and newline
            assert "Page text" in result
            assert "Cell1 Cell2" in result
            assert "Cell3 Cell4" in result

    def test_extract_text_pdfplumber_exception_raises_pdfextractionerror(self):
        with patch("services.pdf_processor.pdfplumber.open", side_effect=PdfminerException("PDF error")):
            processor = PDFProcessor()
            with pytest.raises(PDFExtractionError, match="PDFの読み込みに失敗しました"):
                processor.extract_text("/fake/path.pdf")

    def test_extract_text_permission_error_raises_pdfextractionerror(self):
        with patch("services.pdf_processor.pdfplumber.open", side_effect=PermissionError("no access")):
            processor = PDFProcessor()
            with pytest.raises(PDFExtractionError, match="PDFファイルにアクセス権限がありません"):
                processor.extract_text("/fake/path.pdf")

    def test_handle_extracted_text_returns_original_when_long_enough(self):
        processor = PDFProcessor()
        result = processor._handle_extracted_text("This is a long enough text", BytesIO(), "test.pdf")
        assert result == "This is a long enough text"

    def test_handle_extracted_text_returns_original_when_empty(self):
        processor = PDFProcessor()
        result = processor._handle_extracted_text("", BytesIO(), "test.pdf")
        assert result == ""

    def test_handle_extracted_text_attempts_ocr_when_short_text_and_ocr_available(self):
        processor = PDFProcessor()
        # Mock _run_ocr to return some OCR text
        with patch.object(processor, '_run_ocr', return_value="OCR text"):
            result = processor._handle_extracted_text("short", BytesIO(), "test.pdf")
            assert result == "OCR text"

    def test_handle_extracted_text_returns_original_when_ocr_fails_ocrprocessingerror(self):
        processor = PDFProcessor()
        with patch.object(processor, '_run_ocr', side_effect=OCRProcessingError("OCR failed")):
            result = processor._handle_extracted_text("short", BytesIO(), "test.pdf")
            assert result == "short"  # falls back to original

    def test_handle_extracted_text_returns_original_when_ocr_fails_generic_exception(self):
        processor = PDFProcessor()
        with patch.object(processor, '_run_ocr', side_effect=Exception("OCR error")):
            result = processor._handle_extracted_text("short", BytesIO(), "test.pdf")
            assert result == "short"

    def test_handle_extracted_text_does_not_attempt_ocr_when_ocr_not_available(self):
        processor = PDFProcessor()
        processor._ocr_available = False
        with patch.object(processor, '_run_ocr') as mock_ocr:
            result = processor._handle_extracted_text("short", BytesIO(), "test.pdf")
            mock_ocr.assert_not_called()
            assert result == "short"

    def test_run_ocr_with_bytesio_source(self):
        processor = PDFProcessor()
        mock_file_data = b"dummy pdf bytes"
        mock_ocr_text = "OCR result"
        with patch("services.pdf_processor.ocr_extract_text", return_value=mock_ocr_text) as mock_ocr:
            # We need to mock the source to have read and seek
            source = BytesIO(b"dummy")
            source.read = Mock(return_value=mock_file_data)
            result = processor._run_ocr(source, "test.pdf")
            assert result == mock_ocr_text
            mock_ocr.assert_called_once_with(mock_file_data, source_name="test.pdf")

    def test_run_ocr_with_string_source(self):
        processor = PDFProcessor()
        mock_file_data = b"dummy pdf bytes"
        mock_ocr_text = "OCR result"
        with patch("builtins.open", mock_open(read_data=mock_file_data)) as mock_file:
            with patch("services.pdf_processor.ocr_extract_text", return_value=mock_ocr_text) as mock_ocr:
                result = processor._run_ocr("/fake/path.pdf", "test.pdf")
                assert result == mock_ocr_text
                mock_ocr.assert_called_once_with(mock_file_data, source_name="test.pdf")

    def test_run_ocr_returns_none_when_no_data(self):
        processor = PDFProcessor()
        with patch("services.pdf_processor.ocr_extract_text") as mock_ocr:
            # Mock source that returns empty bytes
            source = BytesIO(b"")
            source.read = Mock(return_value=b"")
            result = processor._run_ocr(source, "test.pdf")
            assert result is None
            mock_ocr.assert_not_called()