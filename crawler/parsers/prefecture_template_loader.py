import json
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class PrefectureTemplateLoader:
    """
    都道府県別の巡回設定をテンプレートから読み込み、個別のコンフィグを生成する。
    """
    def __init__(self, template_path: str = "crawler/patterns/prefectures/template.json"):
        self.template_path = template_path
        self.template = self._load_template()

    def _load_template(self) -> Dict[str, Any]:
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load template: {e}")
            return {"common_patterns": {}, "prefectures": {}}

    def get_config_for_prefecture(self, prefecture_name: str) -> Optional[Dict[str, Any]]:
        """
        指定された都道府県のコンフィグを共通パターンとマージして生成する。
        """
        common = self.template.get("common_patterns", {})
        pref_data = self.template.get("prefectures", {}).get(prefecture_name)
        
        if not pref_data:
            logger.warning(f"No specific data for {prefecture_name} in template.")
            return None

        # 共通パターンをベースに個別設定で上書き
        config = {
            "enabled": True,
            "entry_url": pref_data.get("entry_url"),
            "url_includes": pref_data.get("url_includes", []),
            "title_keywords": pref_data.get("title_keywords", common.get("default_title_keywords", [])),
            "css_selectors": pref_data.get("css_selectors", common.get("default_css_selectors", [])),
            "requires_login": pref_data.get("requires_login", False),
            "dynamic_strategy": pref_data.get("dynamic_strategy", common.get("default_dynamic_strategy", "network_idle")),
            "notes": pref_data.get("notes", ""),
            "max_depth": pref_data.get("max_depth", common.get("default_max_depth", 2)),
            "link_keywords": pref_data.get("link_keywords", common.get("default_link_keywords", []))
        }
        
        return config

    def generate_all_configs(self, output_dir: str = "crawler/parsers/agency_config/generated") -> None:
        """
        テンプレートにある全ての都道府県のコンフィグファイルを生成する。
        """
        os.makedirs(output_dir, exist_ok=True)
        prefectures = self.template.get("prefectures", {})
        
        for name in prefectures:
            config = self.get_config_for_prefecture(name)
            if config:
                file_path = os.path.join(output_dir, f"{name}.json")
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump({name: config}, f, ensure_ascii=False, indent=2)
                logger.info(f"Generated config for {name}: {file_path}")
