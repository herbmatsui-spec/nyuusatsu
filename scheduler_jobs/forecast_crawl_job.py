import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from database.session import get_db
from database.models.agency import Agency
from services.forecast_collection_service import ForecastCollectionService
from services.forecast_batch_service import ForecastBatchService
from services.forecast_dedup_service import ForecastDedupService
from services.forecast_text_extractor import ForecastTextExtractor
from services.forecast_llm_analyzer import ForecastLlmAnalyzer
from services.forecast_validator import ForecastValidator
from utils.forecast_logger import ForecastLogger


async def _collect_and_store(agency: Agency, session) -> Dict[str, Any]:
    logger = ForecastLogger("ForecastJob")
    collection = ForecastCollectionService(session)
    extractor = ForecastTextExtractor()
    analyzer = ForecastLlmAnalyzer()
    validator = ForecastValidator()
    dedup = ForecastDedupService(session)

    items = await collection.collect_for_agency(
        agency_id=agency.id,
        agency_name=agency.name,
        base_url=agency.base_url or "",
        agency_type=agency.type or "municipality",
    )

    stored = 0
    for item in items:
        try:
            text = ""
            if item["type"] == "pdf" and item.get("metadata", {}).get("filepath"):
                text = extractor.extract_text_from_pdf(item["metadata"]["filepath"])
            else:
                text = item.get("text", "")

            if not text:
                continue

            parsed = analyzer.analyze(text)
            parsed["agency_id"] = agency.id
            parsed["source_url"] = item["url"]
            if item["type"] == "pdf":
                parsed["pdf_url"] = item["url"]

            validated = validator.validate(parsed)
            if not validated["is_valid"]:
                logger.warning(f"Validation failed", agency=agency.name, errors=validated["errors"])
                continue

            data = validated["data"]
            fiscal_year = data.get("fiscal_year")
            if dedup.is_duplicate(agency.id, data.get("title", ""), fiscal_year):
                logger.info(f"Duplicate skipped", title=data.get("title"))
                continue

            batch = ForecastBatchService(session)
            batch.save_forecasts(agency.id, [data])
            stored += 1
        except Exception as e:
            logger.error(f"Item processing failed", url=item.get("url"), error=str(e))

    await collection.cleanup()
    return {"agency": agency.name, "found": len(items), "stored": stored}


def crawl_all_forecasts() -> Dict[str, Any]:
    """全アクティブ機関の発注見通しを収集・保存する（スケジューラから呼び出し）。"""
    logger = ForecastLogger("ForecastJob")
    summary: Dict[str, Any] = {"started_at": datetime.utcnow().isoformat(), "results": [], "total_stored": 0}
    with get_db() as session:
        agencies = session.query(Agency).all()
        for agency in agencies:
            try:
                result = asyncio.run(_collect_and_store(agency, session))
                summary["results"].append(result)
                summary["total_stored"] += result["stored"]
            except Exception as e:
                logger.error(f"Agency crawl failed", agency=agency.name, error=str(e))
                summary["results"].append({"agency": agency.name, "error": str(e)})
    summary["finished_at"] = datetime.utcnow().isoformat()
    return summary


def crawl_agency_forecasts(agency_id: int) -> Dict[str, Any]:
    with get_db() as session:
        agency = session.query(Agency).filter(Agency.id == agency_id).first()
        if not agency:
            return {"error": "agency not found"}
        return asyncio.run(_collect_and_store(agency, session))
