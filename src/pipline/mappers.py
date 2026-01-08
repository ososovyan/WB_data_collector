from typing import Optional, Dict, Any

from src.database.models import RawCountry, RawIndicator, RawIndicatorData


def map_collection(items_gen, mapper_func):
    """Универсальный помощник для маппинга и фильтрации"""
    for item in items_gen:
        if (model_obj := mapper_func(item)) is not None:
            yield model_obj.to_dict()

def map_raw_country(raw_item: Dict[str, Any]) -> Optional[RawCountry]:
    # Фильтрация агрегированных регионов на этапе заливки в бд
    region_id = raw_item.get("region", {}).get("id")
    if region_id == "NA" or not region_id:
        return None
    return RawCountry(
        id=raw_item["id"],
        iso2_code=raw_item["iso2Code"],
        name=raw_item["name"],
        capital_city=raw_item["capitalCity"],
        longitude=raw_item["longitude"],
        latitude=raw_item["latitude"],

        # Регион
        region_id=region_id,
        region_iso2_code=raw_item["region"]["iso2code"],
        region_name=raw_item["region"]["value"],

        # Уровень дохода
        income_level_id=raw_item["incomeLevel"]["id"],
        income_level_iso2_code=raw_item["incomeLevel"]["iso2code"],
        income_level_name=raw_item["incomeLevel"]["value"],

        # Полный ответ для истории
        api_response=raw_item
    )


def map_raw_indicator(raw_item: Dict[str, Any]) -> RawIndicator:

    source_data = raw_item.get("source", {})

    return RawIndicator(
        id=raw_item["id"],
        name=raw_item["name"],
        unit=raw_item.get("unit"),  # Может быть пустым в API
        source_note=raw_item.get("sourceNote"),
        source_organisation=raw_item.get("sourceOrganization"),

        # Данные источника
        source_id=source_data.get("id", "NA"),
        source_name=source_data.get("value", "Unknown Source"),

        # Полный ответ для истории
        api_response=raw_item,
    )

def map_raw_indicator_data(raw_item: Dict[str, Any]) -> RawIndicatorData:
    """
    """
    return RawIndicatorData(
        indicator_id=raw_item["indicator"]["id"],
        country_id=raw_item["countryiso3code"], # Берем 'RUS' здесь напрямую
        year=int(raw_item["date"]),
        value=str(raw_item["value"]) if raw_item["value"] is not None else None,
        api_response=raw_item
    )