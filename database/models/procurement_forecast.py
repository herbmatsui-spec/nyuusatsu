# Re-export for database.models.procurement_forecast.* imports
from ._generated import (
    ProcurementForecast as ProcurementForecast,
)

from ._generated import ForecastStatus as ForecastStatus
from ._generated import CompetitorAlertConfig as ForecastAlertConfig
from ._generated import Base, Column, Integer


class CustomerForecastLink(Base):
    __tablename__ = 'customer_forecast_links'
    id = Column(Integer, primary_key=True)
