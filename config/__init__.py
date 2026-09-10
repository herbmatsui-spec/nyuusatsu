"""Application configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class PlanConfig:
    """Subscription plan definitions."""
    FREE = "free"
    STANDARD = "standard"
    PRO = "pro"
    ENTERPRISE = "enterprise"

    LIMITS = {
        FREE: {"search_days": 7, "pdf_extract_daily": 10, "api_requests_monthly": 0, "export": False},
        STANDARD: {"search_days": None, "pdf_extract_daily": None, "api_requests_monthly": 1000, "export": True},
        PRO: {"search_days": None, "pdf_extract_daily": None, "api_requests_monthly": 10000, "export": True},
        ENTERPRISE: {"search_days": None, "pdf_extract_daily": None, "api_requests_monthly": 100000, "export": True},
    }

    PRICES = {
        FREE: 0,
        STANDARD: 30000,
        PRO: 80000,
        ENTERPRISE: 200000,
    }

    STRIPE_PRICE_IDS = {
        STANDARD: os.getenv("STRIPE_PRICE_STANDARD", "price_standard"),
        PRO: os.getenv("STRIPE_PRICE_PRO", "price_pro"),
        ENTERPRISE: os.getenv("STRIPE_PRICE_ENTERPRISE", "price_enterprise"),
    }


class AuthConfig:
    """Authentication configuration."""
    def __init__(self):
        self.enable_auth = os.getenv("ENABLE_AUTH", "false").lower() == "true"
        self.session_timeout_minutes = int(os.getenv("SESSION_TIMEOUT_MIN", "60"))

    @property
    def allowed_users(self):
        import json
        raw = os.getenv("ALLOWED_USERS_JSON", "[]")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []


class RateLimitConfig:
    """Rate limiting configuration."""
    def __init__(self):
        self.enable_rate_limit = os.getenv("ENABLE_RATE_LIMIT", "true").lower() == "true"
        self.max_requests_per_minute = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MIN", "10"))


class ChunkingConfig:
    """Text chunking configuration."""
    def __init__(self):
        self.max_text_chars = int(os.getenv("MAX_TEXT_CHARS", "12000"))
        self.enable_smart_chunking = os.getenv("ENABLE_SMART_CHUNKING", "true").lower() == "true"


class StripeConfig:
    """Stripe configuration."""
    def __init__(self):
        self.secret_key = os.getenv("STRIPE_SECRET_KEY")
        self.publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        self.success_url = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:8501/billing/success")
        self.cancel_url = os.getenv("STRIPE_CANCEL_URL", "http://localhost:8501/billing/cancel")
        self.portal_url = os.getenv("STRIPE_PORTAL_URL", "http://localhost:8501/billing/portal")


class AppConfig:
    """Main application configuration."""

    def __init__(self):
        self.llm_provider = os.getenv("LLM_PROVIDER", "deepseek")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

        self.ocr_provider = os.getenv("OCR_PROVIDER", "tesseract")
        self.tesseract_cmd = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        self.tesseract_lang = os.getenv("TESSERACT_LANG", "jpn")
        self.ocr_dpi = int(os.getenv("OCR_DPI", "300"))
        self.ocr_max_pages = int(os.getenv("OCR_MAX_PAGES", "50"))
        self.ocr_confidence_threshold = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.6"))

        self.azure_document_intelligence_endpoint = os.getenv("AZURE_DOCUMENTINTELLIGENCE_ENDPOINT")
        self.azure_document_intelligence_key = os.getenv("AZURE_DOCUMENTINTELLIGENCE_KEY")

        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./bids_system.db")

        self.auth = AuthConfig()
        self.rate_limit = RateLimitConfig()
        self.chunking = ChunkingConfig()
        self.stripe = StripeConfig()
        self.plan = PlanConfig()

    def validate(self):
        errors = []
        if not self.deepseek_api_key and not self.gemini_api_key:
            errors.append("DEEPSEEK_API_KEY or GEMINI_API_KEY must be set")
        if self.auth.enable_auth and not self.auth.allowed_users:
            errors.append("ALLOWED_USERS_JSON must be set when ENABLE_AUTH=true")
        return errors


config = AppConfig()