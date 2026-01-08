from datetime import datetime
from typing import List, Optional, Any, Dict

from sqlalchemy import (
    Integer,
    String,
    Float,
    DateTime,
    UniqueConstraint,
    JSON, func,
    Text, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base

__all__ = [
    "RawCountry",
    "RawIndicator",
    "RawIndicatorData",
]
# Модели слоя raw: RawCountry, RawIndicator, RawIndicatorData - по сути каждая из моделей
# представление запроса к API WB
class RawCountry(Base):
    __tablename__ = "countries"
    __table_args__ = {"schema": "raw"}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    iso2_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    capital_city: Mapped[str] = mapped_column(String(50), nullable=True)
    longitude: Mapped[float] = mapped_column(String(50), nullable=True)
    latitude: Mapped[float] = mapped_column(String(50), nullable=True)

    region_id: Mapped[str] = mapped_column(String(20),  nullable=False)
    region_iso2_code: Mapped[str] = mapped_column(String(20), nullable=False)
    region_name: Mapped[str] = mapped_column(String(50), nullable=False)

    income_level_id: Mapped[str] = mapped_column(String(20),  nullable=False)
    income_level_iso2_code: Mapped[str] = mapped_column(String(20), nullable=False)
    income_level_name: Mapped[str] = mapped_column(String(50), nullable=False)

    api_response: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RawIndicator(Base):
    __tablename__ = "indicators"
    __table_args__ = {"schema": "raw"}

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=True)
    source_note: Mapped[str] = mapped_column(Text, nullable=True)
    source_organisation: Mapped[str] = mapped_column(Text, nullable=True)
    source_id: Mapped[str] = mapped_column(String(20), nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)

    api_response: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RawIndicatorData(Base):
    __tablename__ = "indicator_data"
    __table_args__ = (
        UniqueConstraint("indicator_id", "country_id", "year", name="uq_raw_data"),
        {"schema": "raw"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indicator_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    country_id: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    value: Mapped[Optional[str]] = mapped_column(String(100))

    api_response: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())