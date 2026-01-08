from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Generator

from requests.adapters import HTTPAdapter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests
import logging

from urllib3 import Retry

logger = logging.getLogger(__name__)
from src.config import ApiSettings


class APIClientError(Exception):
    pass

class _BaseApiClient(ABC):
    """
    База для подключения разных API
    """
    def __init__(
            self,
            api_settings: ApiSettings
    ):
        self.api_settings = api_settings
        self._connected = False
        self.session: Optional[requests.Session] = None

    def connect(self) -> None:
        if self.session is None:
            self.session = requests.Session()

            if self.api_settings.headers:
                self.session.headers.update(self.api_settings.headers)
            if self.api_settings.auth_token:
                self.session.headers["Authorization"] = f"Bearer {self.api_settings.auth_token}"
            self._connected = True


    def disconnect(self) -> None:
        if self.session:
            self.session.close()
            self._connected = False
            self.session = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    @abstractmethod
    def params(self) -> Dict[str, Any]:
        """
        Базовый набор параметров запроса
        """
        pass

    @retry(
        stop=stop_after_attempt(7),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(APIClientError),
        reraise=True,
    )
    def get(
            self,
            endpoint: Optional[str] = None,
            params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        В общем виде get-запрос к апи без отработки пагинации однако с retry при APIClientError
        """
        logger.info(f"session closed={self.session is None}")
        logger.info(f"Запрос к API: {endpoint} (params: {params})")
        if endpoint is None:
            endpoint = self.api_settings.endpoint
        if params is None:
            params = self.params
        if not self.session:
            raise APIClientError("Client is not connected")

        url = f"{self.api_settings.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.get(url, params=params, timeout=5)
        except requests.RequestException as e:
            raise APIClientError(f"Network error: {e}") from e
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise APIClientError(f"HTTP {response.status_code}: {response.text}") from e

        try:
            payload = response.json()
        except ValueError as exc:
            raise APIClientError("Invalid JSON response") from exc

        return payload



    @abstractmethod
    def _extract_data(self, payload: Any) -> list:
        pass

    @abstractmethod
    def _extract_metadata(self, payload: Any) -> Any:
        pass

    @abstractmethod
    def _should_continue_pagination(self, metadata: Any, page_count: int) -> bool:
        pass

    @abstractmethod
    def _get_next_page_params(self, metadata: Any, current_params: Dict, page_count: int) -> Dict:
        pass

    def fetch(
            self,
            endpoint: Optional[str] = None,
            params: Optional[Dict[str, Any]] = None
    ) -> Generator[list, None, None]:
        """
        get-запрос с отработкой пагинации в общем виде
        """
        if endpoint is None:
            endpoint = self.api_settings.endpoint
        if params is None:
            current_params = self.params.copy()
        else:
            current_params = params.copy()

        page_count = 0

        while True:

            payload = self.get(endpoint, current_params)
            data = self._extract_data(payload)
            metadata = self._extract_metadata(payload)

            if data:
                yield data

            page_count += 1

            # Проверяем, нужно ли продолжать
            if not self._should_continue_pagination(metadata, page_count):
                break

            # Получаем параметры следующей страницы
            next_params = self._get_next_page_params(metadata, current_params, page_count)
            if not next_params:
                break
            current_params = next_params.copy()