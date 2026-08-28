import logging
import os
import json
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright
from crawler.parsers.llm_structure_analyzer import LLMStructureAnalyzer
from crawler.parsers.prefecture_template_loader import PrefectureTemplateLoader
from config import AppConfig

logger = logging.getLogger(__name__)

class AutoConfigGenerator:
    """
    未知のサイト構造を分析し、自動的にクローラコンフィグを生成・検証・保存するクラス。
    """
    def __init__(self, api_key: str, template_loader: PrefectureTemplateLoader):
        self.analyzer = LLMStructureAnalyzer(api_key)
        self.template_loader = template_loader
        self.generated_dir = "crawler/parsers/agency_config/generated"

    async def generate_and_validate_config(self, agency_name: str, url: str) -> bool:
        """
        サイトを分析し、コンフィグを生成して検証する。
        """
        logger.info(f"Starting auto-config generation for {agency_name} ({url})")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle")
                content = await page.content()
                await browser.close()

            # 1. LLMによる構造分析
            analysis_result = await self.analyzer.analyze_page_structure(content, url)
            
            if analysis_result.get("confidence", 0) < 0.5:
                logger.warning(f"LLM confidence too low ({analysis_result.get('confidence')}) for {agency_name}")
                return False

            # 2. テンプレートベースのデフォルト設定とマージ
            base_config = self.template_create_base_config(agency_name, url)
            
            # LLMの提案を反映
            final_config = {
                **base_config,
                "css_selectors": analysis_result.get("suggested_css_selectors", base_config["css_selectors"]),
                "title_keywords": analysis_result.get("suggested_title_keywords", base_config["title_keywords"]),
                "link_keywords": analysis_result.get("suggested_link_keywords", base_config["link_keywords"]),
            }

            # 3. コンフィグの保存
            self._save_config(agency_name, final_config)
            
            logger.info(f"Successfully generated and saved config for {agency_name}")
            return True

        except Exception as e:
            logger.exception(f"Error during auto-config generation for {agency_name}: {e}")
            return False

    def _create_base_config(self, agency_name: str, url: str) -> Dict[str, Any]:
        """基本となるコンフィグ構造を作成"""
        # テンプレートから都道府県名などで検索し、ベースを取得（なければデフォルト）
        # ここでは簡易的にデフォルトを返す
        common = self.template_loader.template.get("common_patterns", {})
        return {
            "enabled": True,
            "entry_url": url,
            "url_includes": [url],
            "title_keywords": common.get("default_title_keywords", []),
            "css_selectors": common.get("default_css_selectors", []),
            "requires_login": False,
            "dynamic_strategy": common.get("default_dynamic_strategy", "network_idle"),
            "notes": "LLM-generated",
            "max_depth": common.get("default_max_depth", 2),
            "link_keywords": common.get("default_link_keywords", [])
        }

    def _save_config(self, agency_name: str, config: Dict[str, Any]) -> None:
        os.makedirs(self.generated_dir, exist_ok=True)
        file_path = os.path.join(self.generated_dir, f"{agency_name}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({agency_name: config}, f, ensure_ascii=False, indent=2)

class ConfigAutoUpdater:
    """
    巡回失敗時にコンフィグを自動更新する仕組み。
    """
    def __init__(self, generator: AutoConfigGenerator):
        self.generator = generator

    async def handle_crawl_failure(self, agency_name: str, url: str, error_msg: str):
        """
        巡回失敗時に呼ばれ、構造変更の可能性がある場合に再分析を行う。
        """
        logger.warning(f"Crawl failure detected for {agency_name}: {error_msg}. Triggering auto-update...")
        # 構造変更の可能性があるエラー（例：リンクが見つからない）場合に再生成を試みる
        if "no links found" in error_msg.lower() or "selector not found" in error_msg.lower():
            success = await self.generator.generate_and_validate_config(agency_name, url)
            if success:
                logger.info(f"Successfully updated config for {agency_name} after failure.")
            else:
                logger.error(f"Failed to auto-update config for {agency_name}.")
        else:
            logger.info(f"Failure for {agency_name} does not seem to be a structural issue. Skipping auto-update.")
