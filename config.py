from __future__ import annotations
from dataclasses import dataclass, field
import os
from dataclasses import field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

def _get_env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    return int(val) if val and val.isdigit() else default

def _get_env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    return val.lower() in ("true", "1", "yes") if val else default

def _get_env_users() -> List[dict]:
    """ALLOWED_USERS_JSON からユーザー一覧を読み込む。未設定時は既定値を返す。"""
    raw = os.getenv("ALLOWED_USERS_JSON")
    if raw and raw.strip():
        try:
            import json as _json
            users = _json.loads(raw)
            if isinstance(users, list) and users:
                return users
        except Exception:
            pass
    return [{"username": "admin", "password": "changeme123"}]

@dataclass
class LLMConfig:
    active_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "deepseek").lower())
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_available_models: List[str] = field(default_factory=lambda: ["deepseek-chat", "deepseek-coder"])
    gemini_model_name: str = "gemini-3.1-flash-lite"
    gemini_available_models: List[str] = field(default_factory=lambda: ["gemini-3.1-flash-lite", "gemini-3.1-flash"])
    system_prompt: str = "あなたは入札仕様書の分析専門家です。提供された入札仕様書の本文テキストから、業務代行の可否を判断するために必要な必須要件を読み取り、必ず以下のJSON形式で出力してください。\n\n【出力ルール】\n1. Markdownのコードブロック（```など）や説明文は一切出力しないこと。有効なJSONのみを出力すること。\n2. 該当項目が仕様書内に記載されていない場合は、値を \"記載なし\" とすること。\n3. deliverables は300文字以内で、五感でイメージできるレベルで要約すること。\n4. 値はすべて文字列（string）とし、JSONとしてパス可能な形式を維持すること。\n5. 日付は YYYY-MM-DD 形式で記載すること。不明な場合は \"記載なし\" とすること。"

@dataclass
class ChunkingConfig:
    """テキスト分割設定
    
    Attributes:
        max_text_chars: 1チャンクあたりの最大文字数
        enable_smart_chunking: インテリジェントなチャンク分割を有効にするか
        priority_keywords: 優先的に分割対象とするキーワードリスト
    """
    max_text_chars: int = field(default_factory=lambda: _get_env_int("MAX_TEXT_CHARS", 12000))
    enable_smart_chunking: bool = field(default_factory=lambda: _get_env_bool("ENABLE_SMART_CHUNKING", True))
    priority_keywords: List[str] = field(
        default_factory=lambda: [
            "予算",
            "予定価格",
            "資格",
            "等級",
            "納期",
            "履行期間",
            "成果物",
            "作業内容",
        ]
    )

@dataclass
class AuthConfig:
    """認証設定
    
    Attributes:
        enable_auth: ログインを必須にするか
        session_timeout_minutes: セッション有効期限（分）
        allowed_users: 許可ユーザー一覧（username/password の辞書）
    """
    enable_auth: bool = field(default_factory=lambda: _get_env_bool("ENABLE_AUTH", False))
    session_timeout_minutes: int = field(default_factory=lambda: _get_env_int("SESSION_TIMEOUT_MIN", 60))
    allowed_users: List[dict] = field(default_factory=lambda: _get_env_users())

@dataclass
class RateLimitConfig:
    """アプリ側レートリミット設定（利用者ごとのアップロード抑制）"""
    enable_rate_limit: bool = field(default_factory=lambda: _get_env_bool("ENABLE_RATE_LIMIT", True))
    max_requests_per_minute: int = field(default_factory=lambda: _get_env_int("RATE_LIMIT_REQUESTS_PER_MIN", 10))

@dataclass
class CrawlerConfig:
    """クローラー設定"""
    sleep_interval: float = 1.0  # リクエスト間の待機時間(秒)
    """クローラー設定
    
    Attributes:
        target_url: クロール対象のベースURL
        temp_dir: 一時ファイル保存ディレクトリ
        output_dir: 出力ディレクトリ
        user_agent: HTTPリクエストに使用するUser-Agent
        request_timeout: HTTPリクエストタイムアウト（秒）
        pdf_timeout: PDFダウンロードタイムアウト（秒）
        api_retry_delay: APIリトライ間隔（秒）
        parallel_downloads: 並列ダウンロード数
    """
    target_url: str = "https://example.gov.jp/bids"
    temp_dir: str = "./temp_pdfs"
    output_dir: str = "./output"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    request_timeout: int = 30
    pdf_timeout: int = 60
    api_retry_delay: int = 10
    parallel_downloads: int = 4

@dataclass
class FallbackConfig:
    """Playwrightとrequestsのフォールバック設定
    
    Attributes:
        enable_fallback: Playwrightが失敗時にrequestsに切り替える
        strategy: フォールバック戦略("only_requests", "try_playwright_first", "try_requests_first")
        retry_on_playwright: Playwright失敗時にリトライ回数
        max_retries: 最大リトライ回数
        use_robots_txt: robots.txtチェックを有効にする
        timeout_seconds: リクエストタイムアウト
    """
    enable_fallback: bool = field(default_factory=lambda: _get_env_bool("ENABLE_FALLBACK", True))
    strategy: str = field(default_factory=lambda: os.getenv("FALLBACK_STRATEGY", "try_playwright_first"))
    retry_on_playwright: int = field(default_factory=lambda: _get_env_int("FALLBACK_RETRY_ON_PLAYWRIGHT", 2))
    max_retries: int = field(default_factory=lambda: _get_env_int("MAX_RETRIES", 3))
    use_robots_txt: bool = field(default_factory=lambda: _get_env_bool("USE_ROBOTS_TXT", True))
    timeout_seconds: int = field(default_factory=lambda: _get_env_int("REQUEST_TIMEOUT_SECONDS", 30))

@dataclass
class ObservabilityConfig:
    """可観測性（Observability）設定"""
    log_format: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "json").lower())
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())
    metrics_enabled: bool = field(default_factory=lambda: _get_env_bool("METRICS_ENABLED", True))
    metrics_retention_days: int = field(default_factory=lambda: _get_env_int("METRICS_RETENTION_DAYS", 30))
    health_check_interval_seconds: int = field(default_factory=lambda: _get_env_int("HEALTH_CHECK_INTERVAL_SEC", 60))
    alert_on_consecutive_failures: int = field(default_factory=lambda: _get_env_int("ALERT_ON_CONSECUTIVE_FAILURES", 3))

@dataclass
class RedisConfig:
    """Redis接続設定"""
    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port: int = field(default_factory=lambda: _get_env_int("REDIS_PORT", 6379))
    db: int = field(default_factory=lambda: _get_env_int("REDIS_DB", 0))

@dataclass
class ArchiveConfig:
    """アーカイブ（魚拓）保存設定"""
    archive_dir: str = field(default_factory=lambda: os.getenv("ARCHIVE_DIR", "./data/archives"))

@dataclass
class PlanConfig:
    """Subscription plan definitions."""
    FREE: str = "free"
    STANDARD: str = "standard"
    PRO: str = "pro"
    ENTERPRISE: str = "enterprise"
    
    LIMITS: dict = field(default_factory=lambda: {
        "free": {"search_days": 7, "pdf_extract_daily": 10, "api_requests_monthly": 0, "export": False},
        "standard": {"search_days": None, "pdf_extract_daily": None, "api_requests_monthly": 1000, "export": True},
        "pro": {"search_days": None, "pdf_extract_daily": None, "api_requests_monthly": 10000, "export": True},
        "enterprise": {"search_days": None, "pdf_extract_daily": None, "api_requests_monthly": 100000, "export": True},
    })
    
    PRICES: dict = field(default_factory=lambda: {
        "free": 0,
        "standard": 30000,
        "pro": 80000,
        "enterprise": 200000,
    })
    
    STRIPE_PRICE_IDS: dict = field(default_factory=lambda: {
        "standard": os.getenv("STRIPE_PRICE_STANDARD", "price_standard"),
        "pro": os.getenv("STRIPE_PRICE_PRO", "price_pro"),
        "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", "price_enterprise"),
    })

@dataclass
class StripeConfig:
    """Stripe configuration."""
    secret_key: str = field(default_factory=lambda: os.getenv("STRIPE_SECRET_KEY", ""))
    publishable_key: str = field(default_factory=lambda: os.getenv("STRIPE_PUBLISHABLE_KEY", ""))
    webhook_secret: str = field(default_factory=lambda: os.getenv("STRIPE_WEBHOOK_SECRET", ""))
    success_url: str = field(default_factory=lambda: os.getenv("STRIPE_SUCCESS_URL", "http://localhost:8501/billing/success"))
    cancel_url: str = field(default_factory=lambda: os.getenv("STRIPE_CANCEL_URL", "http://localhost:8501/billing/cancel"))
    portal_url: str = field(default_factory=lambda: os.getenv("STRIPE_PORTAL_URL", "http://localhost:8501/billing/portal"))

@dataclass
class KanbanConfig:
    """カンバンボード設定"""
    columns: List[str] = field(default_factory=lambda: [
        "未確認",
        "検討中",
        "書類作成中",
        "入札済",
        "結果待ち",
        "落札",
        "失注",
    ])

@dataclass
class ForecastConfig:
    """入札予測設定"""
    enable_prediction: bool = field(default_factory=lambda: _get_env_bool("ENABLE_PREDICTION", True))
    min_historical_data: int = field(default_factory=lambda: _get_env_int("MIN_HISTORICAL_DATA", 3))
    prediction_threshold: float = 0.6

@dataclass
class ProcurementForecastConfig:
    """発注見通し（先行営業支援）クロール設定"""
    forecast_crawl_interval_hours: int = field(default_factory=lambda: _get_env_int("FORECAST_CRAWL_INTERVAL_HOURS", 168))
    forecast_retention_days: int = field(default_factory=lambda: _get_env_int("FORECAST_RETENTION_DAYS", 365))
    forecast_parallel_limit: int = field(default_factory=lambda: _get_env_int("FORECAST_PARALLEL_LIMIT", 5))
    forecast_pdf_temp_dir: str = field(default_factory=lambda: os.getenv("FORECAST_PDF_TEMP_DIR", "./temp_forecasts"))
    forecast_max_text_chars: int = field(default_factory=lambda: _get_env_int("FORECAST_MAX_TEXT_CHARS", 50000))
    forecast_quarterly_crawl_enabled: bool = field(default_factory=lambda: _get_env_bool("FORECAST_QUARTERLY_CRAWL", True))
    forecast_weekly_crawl_enabled: bool = field(default_factory=lambda: _get_env_bool("FORECAST_WEEKLY_CRAWL", True))
    forecast_url_patterns: List[str] = field(default_factory=lambda: [
        "*://*/*発注見通し*",
        "*://*/*事業計画*",
        "*://*/*入札予定*",
        "*://*/*工事予定*",
        "*://*/*調達予定*",
        "*://*/*yotei*",
        "*://*/*forecast*",
    ])

@dataclass
class AppConfig:
    use_event_event_pipeline: bool = field(default_factory=lambda: _get_env_bool("USE_EVENT_PIPELINE", True))
    redis: RedisConfig = field(default_factory=RedisConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    crawler: CrawlerConfig = field(default_factory=CrawlerConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    fallback: FallbackConfig = field(default_factory=FallbackConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    archive: ArchiveConfig = field(default_factory=ArchiveConfig)
    kanban: KanbanConfig = field(default_factory=KanbanConfig)
    forecast: ForecastConfig = field(default_factory=ForecastConfig)
    forecast_crawl: ProcurementForecastConfig = field(default_factory=ProcurementForecastConfig)
    plan: PlanConfig = field(default_factory=PlanConfig)
    stripe: StripeConfig = field(default_factory=StripeConfig)
    required_keys: List[str] = field(
        default_factory=lambda: ["budget", "qualifications", "deadline", "deliverables"]
    )
    
    def validate(self) -> List[str]:
        errors = []
        # 少なくとも一つのAPIキーが設定されていることを確認
        has_deepseek = bool(os.getenv("DEEPSEEK_API_KEY"))
        has_gemini = bool(os.getenv("GEMINI_API_KEY"))
        
        if not has_deepseek and not has_gemini:
            errors.append("LLM_PROVIDER が設定されているか、DEEPSEEK_API_KEY または GEMINI_API_KEY のいずれかが設定されている必要があります")
        
        if self.chunking.max_text_chars < 1000:
            errors.append("max_text_chars は1000以上に設定してください")
        if self.chunking.max_text_chars > 100000:
            errors.append("max_text_chars は100000以下に設定してください")
        
        if self.fallback.strategy not in ["only_requests", "try_playwright_first", "try_requests_first"]:
            errors.append("FALLBACK_STRATEGY は only_requests, try_playwright_first, または try_requests_first のいずれかでなければなりません")
        
        return errors