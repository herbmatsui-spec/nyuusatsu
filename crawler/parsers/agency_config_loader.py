import json
import os
from typing import Any, Dict

class AgencyConfigLoader:
    """
    自治体ごとの抽出設定（JSON）を読み込むローダー。
    該当する設定がない場合はデフォルト設定を返す。
    """
    def __init__(self, config_dir: str = "crawler/parsers/agency_config"):
        self.config_dir = config_dir
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_config = {
            "enabled": True,
            "url_includes": [],
            "title_keywords": [],
            "css_selectors": [],
            "requires_login": False,
            "dynamic_strategy": "network_idle",
            "max_depth": 2,
            "link_keywords": ["nyusatsu", "bid"]
        }

    def load(self, agency_name: str) -> Dict[str, Any]:
        """
        自治体名に基づいて設定を読み込む。
        設定ディレクトリおよびそのサブディレクトリ内の全JSONファイルを検索する。
        """
        if agency_name in self.cache:
            return self.cache[agency_name]

        try:
            if not os.path.exists(self.config_dir):
                return self.default_config

            for root, dirs, files in os.walk(self.config_dir):
                for filename in files:
                    if filename.endswith(".json"):
                        filepath = os.path.join(root, filename)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if agency_name in data:
                                config = data[agency_name]
                                self.cache[agency_name] = config
                                return config
        except Exception as e:
            print(f"Error loading agency config for {agency_name}: {e}")

        return self.default_config
