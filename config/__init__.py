"""
Config module for the nyuusatsu project.
This package contains configuration files and utilities for the application.
"""

# The root-level config.py defines AppConfig and PlanConfig.
# Due to Python's import system, the config/ package shadows config.py,
# so we import dynamically from the parent directory.
import importlib.util
import sys
import os

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.py")
_spec = importlib.util.spec_from_file_location("_root_config", _config_path)
if _spec and _spec.loader:
    _root_config = importlib.util.module_from_spec(_spec)
    sys.modules["_root_config"] = _root_config
    _spec.loader.exec_module(_root_config)
    AppConfig = _root_config.AppConfig
    PlanConfig = _root_config.PlanConfig
    CrawlerConfig = _root_config.CrawlerConfig
    LLMConfig = _root_config.LLMConfig

__all__ = ["AppConfig", "PlanConfig", "CrawlerConfig", "LLMConfig"]