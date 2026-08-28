from typing import Dict, Any, Optional
from datetime import datetime

from database.models.forecast_status import ForecastStatusEnum
from utils.forecast_logger import ForecastLogger


class ForecastValidator:
    """発注見通し抽出結果のバリデーションを行う。"""

    REQUIRED_FIELDS = ["title", "fiscal_year"]

    def __init__(self):
        self.logger = ForecastLogger("Validator")

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        errors: List[str] = []

        if not data.get("title") or not str(data.get("title")).strip():
            errors.append("title が空です")

        fiscal_year = data.get("fiscal_year")
        if not fiscal_year or not isinstance(fiscal_year, int):
            # LLMの出力では年度が含まれない場合があるため補完
            data["fiscal_year"] = self._guess_fiscal_year()
        else:
            current_year = datetime.now().year
            if not (current_year - 2 <= data["fiscal_year"] <= current_year + 3):
                errors.append(f"fiscal_year が範囲外です: {fiscal_year}")

        if data.get("estimated_budget_amount") is not None:
            try:
                data["estimated_budget_amount"] = int(data["estimated_budget_amount"])
            except (ValueError, TypeError):
                data["estimated_budget_amount"] = None

        status = data.get("status")
        if status and status not in [e.value for e in ForecastStatusEnum]:
            data["status"] = ForecastStatusEnum.DRAFT.value

        data.setdefault("status", ForecastStatusEnum.DRAFT.value)
        return {"is_valid": len(errors) == 0, "errors": errors, "data": data}

    def _guess_fiscal_year(self) -> int:
        now = datetime.now()
        # 日本の会計年度: 4月以降は当年を年度とする
        return now.year if now.month >= 4 else now.year - 1
