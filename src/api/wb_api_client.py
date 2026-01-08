from dataclasses import dataclass
from typing import List, Dict, Any, Generator, Optional

from src.api.base_client import _BaseApiClient
from src.config import WBSettings


class WBApiClient(_BaseApiClient):
    def __init__(self, wb_settings: WBSettings):
        super().__init__(api_settings=wb_settings.api_settings)

        self.countries: list[str] = wb_settings.countries
        self.indicators: list[str] = wb_settings.indicators
        self.date_list: list[str] = wb_settings.date_intervals

        self.merged_countries: str = ";".join(self.countries) if self.countries else ""
        self.merged_dates = ";".join(map(str, self.date_list)) if self.date_list else ""

    @property
    def params(self) -> Dict[str, Any]:
        params = {
            "format": "json",
            "per_page": self.api_settings.batch_size,
            "page": 1,
        }
        # Добавляем дату только если она есть
        if self.merged_dates:
            params["date"] = self.merged_dates
        return params

    def _extract_data(self, payload: Any) -> List[Dict[str, Any]]:
        if (isinstance(payload, list)
            and len(payload) >= 2
            and isinstance(payload[1], list)
        ):
            return payload[1]
        return []

    def _extract_metadata(self, payload: Any) -> Any:
        if isinstance(payload, list) and len(payload) > 0:
            metadata = payload[0]
            if isinstance(metadata, dict):
                return metadata
        return {}

    def _get_next_page_params(self, metadata: Any, current_params: Dict[str, Any], page_count: int) -> Optional[Dict[str, Any]]:
        if not metadata or not isinstance(metadata, dict):
            return None

        current_page = metadata.get("page", 1)
        new_params = current_params.copy()
        new_params["page"] = current_page + 1
        return new_params

    def _should_continue_pagination(self, metadata: Any, page_count: int) -> bool:
        if not isinstance(metadata, dict) or not metadata:
            return False
        current_page = metadata.get("page", 1)
        total_pages = metadata.get("pages", 1)
        return current_page < total_pages

    def get_endpoints(self) -> Generator[str, None, None]:
        if self.merged_countries:
            for indicator in self.indicators:
                yield f"country/{self.merged_countries}/indicator/{indicator}"
        else:
            for indicator in self.indicators:
                yield f"indicator/{indicator}"

    def fetch_all(self, **kwargs) -> Generator[list, None, None]:
        for endpoint in self.get_endpoints():
            yield from self.fetch(endpoint, **kwargs)

    def get_countries(self) -> Generator[list, None, None]:
        special_params = {
            "format": "json",
            "per_page": 100,
            "page": 1
        }
        return self.fetch(endpoint="country", params=special_params)

    def get_indicators(self) -> Generator[list, None, None]:
        special_params = {
            "format": "json",
            "per_page": 200,
            "page": 1
        }
        return self.fetch(endpoint="indicator", params=special_params)