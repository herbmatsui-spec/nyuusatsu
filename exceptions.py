class AppError(Exception):
    """Application base exception"""

class PDFExtractionError(AppError):
    """PDF text extraction failed"""

class OCRProcessingError(AppError):
    """OCR processing failed"""

class LLMAnalysisError(AppError):
    """LLM API or parsing failed"""

class LLMConnectionError(LLMAnalysisError):
    """Connection issue"""

class LLMResponseParseError(LLMAnalysisError):
    """Parsing issue"""

class RateLimitExceededError(AppError):
    """Rate limit exceeded"""

class BidProcessorError(AppError):
    """BidProcessor related base exception"""

class CrawlerError(AppError):
    """Crawler related base exception"""

class ForecastCrawlError(CrawlerError):
    """Procurement forecast crawl related exception"""

class ForecastParseError(AppError):
    """Procurement forecast parse related exception"""

class ForecastNotFoundError(AppError):
    """Procurement forecast not found exception"""
