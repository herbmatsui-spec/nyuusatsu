"""OCRパッケージ"""
from .ocr_result import OCRBlock, OCRResult
from .base import OCRProvider
from .config import OCRConfig


def create_ocr_provider(config: OCRConfig = None) -> OCRProvider:
    """Step 9: 設定に基づいてOCRプロバイダーを生成する工場関数"""
    if config is None:
        config = OCRConfig.from_env()

    if config.provider == "azure":
        from .azure_doc_int import AzureDocIntProvider
        provider = AzureDocIntProvider(config)
        if provider.is_available():
            return provider
        # Azureが利用不可ならTesseractにフォールバック
        from .tesseract_ocr import TesseractOCRProvider
        return TesseractOCRProvider(config)
    else:
        from .tesseract_ocr import TesseractOCRProvider
        return TesseractOCRProvider(config)


def is_scanned_pdf(file_data: bytes, char_threshold: int = 50) -> bool:
    """Step 27: PDFがスキャンPDFかどうかを判定"""
    import io
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_data)) as pdf:
            text = ""
            for page in pdf.pages[:3]:
                text += page.extract_text() or ""
            return len(text.strip()) < char_threshold
    except Exception:
        return True


def ocr_extract_text(file_data: bytes, source_name: str = "") -> str:
    """Step 35: 既存コード統合用エントリポイント

    スキャンPDFを自動認識し、設定されたプロバイダーでOCRを実行。
    通常PDFの場合はpdfplumberで抽出したテキストを返す。
    """
    from .logger import setup_ocr_logging
    logger = setup_ocr_logging()

    # Step 27: スキャン判定
    if not is_scanned_pdf(file_data):
        logger.info("通常PDF: pdfplumberでテキスト抽出")
        import pdfplumber
        import io
        with pdfplumber.open(io.BytesIO(file_data)) as pdf:
            text_parts = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                text_parts.append(t)
            return "\n\n".join(text_parts)

    logger.info("スキャンPDF判定: OCRを実行します")
    provider = create_ocr_provider()

    if not provider.is_available():
        logger.warning("OCRプロバイダーが利用できません")
        return ""

    result = provider.extract_text_from_bytes(file_data)

    # Step 25-30: 品質管理
    from .confidence_scorer import ConfidenceScorer
    scorer = ConfidenceScorer()
    scorer.log_quality_metrics(result, source=source_name)

    return result.full_text


def extract_text_from_file(file_path: str, source_name: str = "") -> str:
    """Step 17: ファイルパスからのOCR対応テキスト抽出 (pipeline.py 用エントリポイント)

    スキャンPDFを自動認識し、設定されたプロバイダーでOCRを実行。
    通常PDFの場合はpdfplumberで抽出したテキストを返す。
    """
    from .logger import setup_ocr_logging
    logger = setup_ocr_logging()

    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
    except Exception as e:
        logger.error("Failed to read PDF file: %s", e)
        raise

    # Step 27: スキャン判定
    if not is_scanned_pdf(file_data, char_threshold=100):
        logger.info("Normal PDF: pdfplumberでテキスト抽出")
        import pdfplumber
        import io
        with pdfplumber.open(io.BytesIO(file_data)) as pdf:
            text_parts = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                text_parts.append(t)
            return "\n\n".join(text_parts)

    logger.info("スキャンPDF判定: OCRを実行します")
    provider = create_ocr_provider()

    if not provider.is_available():
        logger.warning("OCRプロバイダーが利用できません")
        return ""

    result = provider.extract_text(file_path)

    # Step 25-30: 品質管理
    from .confidence_scorer import ConfidenceScorer
    scorer = ConfidenceScorer()
    scorer.log_quality_metrics(result, source=source_name)

    return result.full_text


__all__ = [
    "OCRBlock",
    "OCRResult",
    "OCRProvider",
    "OCRConfig",
    "create_ocr_provider",
    "is_scanned_pdf",
    "ocr_extract_text",
    "extract_text_from_file",
]
