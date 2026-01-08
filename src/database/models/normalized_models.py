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

# Модели слоя normalized
__all__ = [
    "NormRegion",
    "NormIncomeLevel",
    "NormCountry",
    "NormSource",
    "NormIndicator",
    "NormIndicatorData",
]
class NormRegion(Base):
    __tablename__ = "regions"
    __table_args__ = {"schema": "normalized"}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    iso2_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    countries: Mapped[List["NormCountry"]] = relationship(
        "NormCountry",
        back_populates="region",
        cascade="all, delete-orphan"
    )

class NormIncomeLevel(Base):
    __tablename__ = "income_levels"
    __table_args__ = {"schema": "normalized"}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    iso2_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    countries: Mapped[List["NormCountry"]] = relationship(
        "NormCountry",
        back_populates="income_level"
    )

class NormCountry(Base):
    __tablename__ = "countries"
    __table_args__ = {"schema": "normalized"}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    iso2_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    capital_city: Mapped[str] = mapped_column(String(50), nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)

    region_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("normalized.regions.id", ondelete="CASCADE"), nullable=False
    )

    income_level_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("normalized.income_levels.id", ondelete="SET NULL"), nullable=False
    )


    region: Mapped["NormRegion"] = relationship("NormRegion", back_populates="countries")
    income_level: Mapped["NormIncomeLevel"] = relationship("NormIncomeLevel", back_populates="countries")

class NormSource(Base):
    __tablename__ = "sources"
    __table_args__ = {"schema": "normalized"}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    indicators: Mapped[List["NormIndicator"]] = relationship(
        "NormIndicator",
        back_populates="source"
    )

class NormIndicator(Base):
    __tablename__ = "indicators"
    __table_args__ = {"schema": "normalized"}

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(100), nullable=True)
    source_note: Mapped[str] = mapped_column(String(200), nullable=True)
    source_organisation: Mapped[str] = mapped_column(String(100), nullable=True)

    source_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("normalized.sources.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped["NormSource"] = relationship("NormSource", back_populates="indicators")

class NormIndicatorData(Base):
    __tablename__ = "indicator_data"
    __table_args__ = (
        UniqueConstraint("indicator_id", "country_id", "year", name="uq_norm_data"),
        {"schema": "normalized"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    country_id: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    value_numeric: Mapped[Optional[float]] = mapped_column(Float)
    value_string: Mapped[Optional[str]] = mapped_column(String(255))
    unit: Mapped[Optional[str]] = mapped_column(String(50))

    extra_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    normalized_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    country: Mapped[Optional["NormCountry"]] = relationship(
        "NormCountry",
        primaryjoin="foreign(NormIndicatorData.country_id)==NormCountry.id",
        viewonly=True
    )
    indicator: Mapped[Optional["NormIndicator"]] = relationship(
        "NormIndicator",
        primaryjoin="foreign(NormIndicatorData.indicator_id)==NormIndicator.id",
        viewonly=True
    )