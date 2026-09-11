"""Application configuration - re-exports from root config.py"""
import importlib.util
import os

# Load root config.py directly
root_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.py")
spec = importlib.util.spec_from_file_location("root_config", root_config_path)
root_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(root_config)

# Re-export all public names
AppConfig = root_config.AppConfig
PlanConfig = root_config.PlanConfig
StripeConfig = root_config.StripeConfig
AuthConfig = root_config.AuthConfig
RateLimitConfig = root_config.RateLimitConfig
ChunkingConfig = root_config.ChunkingConfig
LLMConfig = root_config.LLMConfig
CrawlerConfig = root_config.CrawlerConfig
FallbackConfig = root_config.FallbackConfig
ObservabilityConfig = root_config.ObservabilityConfig
RedisConfig = root_config.RedisConfig
ArchiveConfig = root_config.ArchiveConfig
KanbanConfig = root_config.KanbanConfig
ForecastConfig = root_config.ForecastConfig
ProcurementForecastConfig = root_config.ProcurementForecastConfig

# Global config instance for backward compatibility
config = AppConfig()