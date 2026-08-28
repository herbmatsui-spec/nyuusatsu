from typing import Any, Dict, List

class ResultMerger:
    def __init__(self, required_keys: List[str]):
        self.required_keys = required_keys

    def merge(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        複数のチャンクから得られた抽出結果を統合する。
        同じキーがある場合は、より具体的（文字数が多い）な情報を優先して採用する。
        """
        merged: Dict[str, Any] = {}

        if not results:
            return merged

        keys = self.required_keys if self.required_keys else list(results[0].keys())

        for key in keys:
            best_value = "記載なし"
            max_len = -1

            for res in results:
                val = res.get(key, "記載なし")
                if val is None or (isinstance(val, str) and not val.strip()):
                    continue
                str_val = str(val).strip()
                if str_val != "記載なし" and len(str_val) > max_len:
                    max_len = len(str_val)
                    best_value = str_val

            merged[key] = best_value

        return merged
