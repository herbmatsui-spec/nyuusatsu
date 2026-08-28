from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class OCRConfig:
    # Provider selection: 'azure' or 'tesseract'
    provider: str = os.environ.get("OCR_PROVIDER", "azure")
    
    # Azure Settings
    azure_endpoint: str = os.environ.get("AZURE_DOCUMENTINTELLIGENCE_ENDPOINT", "")
    azure_key: str = os.environ.get("AZURE_DOCUMENTINTELLIGENCE_KEY", "")
    
    # Tesseract Settings
    tesseract_cmd: str = os.environ.get("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    tesseract_lang: str = "jpn"
    dpi: int = 300
    max_pages: int = 50
    
    # General Settings
    confidence_threshold: float = 0.6
    cache_dir: str = "data/ocr_cache"
    correction_storage_dir: str = "corrected_texts"
    
    @classmethod
    def from_env(cls) -> "OCRConfig":
        """Create OCRConfig from environment variables."""
        return cls()
