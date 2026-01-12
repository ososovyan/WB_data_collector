import logging
import sys
from typing import Iterable, Dict, Any, Generator, List

from src.api import WBApiClient
from src.config import WBSettings, DatabaseConfig
from src.database import DatabaseConnection, DataBaseManager
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.database.models import RawCountry, RawIndicator, RawIndicatorData
from src.pipline.mappers import map_raw_country, map_collection, map_raw_indicator, map_raw_indicator_data
from src.pipline.utils import auto_refresh_marts


class DBConnectionError(Exception):
    pass

class WBPiplineManager:
    def __init__(
            self,
            wb_cfg: WBSettings,
            db_cfg: DatabaseConfig,
    ):
        self.logger = logging.getLogger(__name__)

        self.wb_cfg = wb_cfg
        self.db_connection = DatabaseConnection(db_cfg)
        self.data_collector = DataBaseManager(self.db_connection)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(DBConnectionError),
        reraise=True,
    )
    def set_connection(self):
        """
        Здесь через мы пытаемся подключиться к бд - ленивая инициализация подключения к бд
        """
        self.logger.debug("Проверка подключения к БД....")
        if not self.db_connection.health_check():
            self.logger.error("Ошибка подключения к БД")
            raise DBConnectionError
        self.logger.debug("Подключение к БД установлено")

    def clear_data(self, table: str = None, schema: str = 'raw'):
        """
        Удаление данных без удаления структуры таблиц
        """
        self.set_connection()
        self.logger.debug(f"Очистка данных: таблица={table}, схема={schema}...")
        self.data_collector.truncate_table(table_name=table, schema=schema)
        self.logger.debug(f"Очистка данных: таблица={table}, схема={schema} успешно осуществлена")

    def close_connection(self):
        """
        Здесь мы закрываем соединение
        """
        self.logger.debug("Отключение от БД...")
        self.db_connection.close()
        self.logger.debug("Отключение от БД")

    def init_data_storage(self):
        """
        Создание полной базы данных схем, таблиц, триггеров, функций, представлний
        """
        self.set_connection()
        self.logger.debug("Запуск инициализации структуры хранилища данных...")
        self.data_collector.create_all()
        self.logger.debug("Структура хранилища данных успешно создана")

    def drop_data_storage(self):
        """
        Удаление полной базы данных схем, таблиц, триггеров, функций, представлний
        """
        self.set_connection()
        self.logger.debug("Запуск удаления структуры хранилища данных...")
        self.data_collector.drop_all()
        self.logger.debug("Структура хранилища данных успешно удалена")

    @staticmethod
    def flatten_pages(pages: Iterable[list[Dict]]) -> Generator[Dict, None, None]:
        for page in pages:
            yield from page

    def sync_countries(self, upsert=False):
        """
        Заполнение данными справочников связанными со странами
        """
        self.set_connection()
        self.logger.debug(f"Запуск заполнения справочника стран upsert={upsert}...")
        with WBApiClient(self.wb_cfg) as client:
            pages = client.get_countries()
            items = self.flatten_pages(pages)
            mapped_items = map_collection(items, map_raw_country)
            self.data_collector.load_data_auto(
                model=RawCountry,
                data_generator=mapped_items,
                upsert=upsert,
            )

        self.logger.debug("Заполнение выполнено!")

    def sync_indicators(self, upsert=False):
        """
        Заполнение данными справочников связанными с индикаторами
        """
        self.set_connection()
        self.logger.debug(f"Запуск заполнения справочника показателей upsert={upsert}...")
        with WBApiClient(self.wb_cfg) as client:
            pages = client.get_indicators()
            items = self.flatten_pages(pages)
            mapped_items = map_collection(items, map_raw_indicator)
            self.data_collector.load_data_auto(
                model=RawIndicator,
                data_generator=mapped_items,
                upsert=upsert,
            )
        self.logger.debug("Заполнение выполнено!")

    @auto_refresh_marts
    def sync_data(self, upsert=False):
        """
        Заполнение данных таблицы фактов на нужном для исследования временном диапазоне
        """
        self.set_connection()
        self.logger.debug(f"Запуск заполнения фактов - значений показателей upsert={upsert}...")
        with WBApiClient(self.wb_cfg) as client:
            pages = client.fetch_all()
            items = self.flatten_pages(pages)
            mapped_items = map_collection(items, map_raw_indicator_data)
            self.data_collector.load_data_auto(
                model=RawIndicatorData,
                data_generator=mapped_items,
                upsert=upsert,
            )
        self.logger.debug("Заполнение выполнено!")






