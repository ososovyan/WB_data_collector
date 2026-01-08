import logging
import sys
from typing import Iterable, Dict, Any, Generator, List

from src.api import WBApiClient
from src.config import WBSettings, DatabaseConfig
from src.database import DatabaseConnection, DataBaseManager
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.database.models import RawCountry, RawIndicator, RawIndicatorData
from src.database.utils import auto_refresh_marts
from src.pipline.mappers import map_raw_country, map_collection, map_raw_indicator, map_raw_indicator_data


class DBConnectionError(Exception):
    pass

class WBPiplineManager:
    def __init__(
            self,
            wb_cfg: WBSettings,
            db_cfg: DatabaseConfig,
    ):
        self.setup_logging()
        self.logger = logging.getLogger(__name__)

        self.wb_cfg = wb_cfg
        self.db_connection = DatabaseConnection(db_cfg)
        self.data_collector = DataBaseManager(self.db_connection)

    @staticmethod
    def setup_logging(level=logging.INFO):
        """Централизованная настройка логов для всех модулей проекта"""
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)

        # Корневой логгер пакета
        root_logger = logging.getLogger("src")
        root_logger.setLevel(level)

        if not root_logger.handlers:
            root_logger.addHandler(handler)

        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
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
        if not self.db_connection.health_check():
            raise DBConnectionError

    def close_connection(self):
        """
        Здесь мы закрываем соединение
        """
        self.db_connection.close()

    def init_data_storage(self):
        """
        Создание полной базы данных схем, таблиц, триггеров, функций, представлний
        """
        self.set_connection()
        self.logger.info("Запуск инициализации структуры хранилища данных...")
        self.data_collector.create_all()
        self.logger.info("Структура хранилища данных успешно создана")

    def drop_data_storage(self):
        """
        Удаление полной базы данных схем, таблиц, триггеров, функций, представлний
        """
        self.set_connection()
        self.logger.info("Запуск удаления структуры хранилища данных...")
        self.data_collector.drop_all()
        self.logger.info("Структура хранилища данных успешно удалена")

    def buffer(self, source: Iterable[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:

        buffer_size = self.db_connection.config.batch_size

        buffer = []
        for item in source:
            buffer.append(item)
            while len(buffer) >= buffer_size:
                yield from buffer[:buffer_size]
                buffer = buffer[buffer_size:]
        if buffer:
            yield from buffer


    @staticmethod
    def flatten_pages(pages: Iterable[list[Dict]]) -> Generator[Dict, None, None]:
        for page in pages:
            yield from page

    def sync_countries(self, upsert=False):
        """
        Заполнение данными справочников связанными со странами
        """
        self.set_connection()
        self.logger.info(f"Запуск заполнения справочника стран upsert={upsert}...")
        with WBApiClient(self.wb_cfg) as client:
            # 1. API pages (по 250)
            pages = client.get_countries()

            # 2. flatten → поток элементов
            items = self.flatten_pages(pages)

            # 3. mapping
            mapped_items = map_collection(items, map_raw_country)

            # 5. загрузка
            self.data_collector.load_data_auto(
                model=RawCountry,
                data_generator=mapped_items,
                upsert=upsert,
            )

            self.logger.info("Заполнение выполнено!")

    def sync_indicators(self, upsert=False):
        """
        Заполнение данными справочников связанными с индикаторами
        """
        self.set_connection()
        self.logger.info(f"Запуск заполнения справочника показателей upsert={upsert}...")
        with WBApiClient(self.wb_cfg) as client:
            pages = client.get_indicators()
            items = self.flatten_pages(pages)
            mapped_items = map_collection(items, map_raw_indicator)
            self.data_collector.load_data_auto(
                model=RawIndicator,
                data_generator=mapped_items,
                upsert=upsert,
            )



    @auto_refresh_marts
    def sync_data(self, upsert=False):
        """
        Заполнение данных таблицы фактов на нужном для исследования временном диапазоне
        """
        self.set_connection()
        self.logger.info(f"Запуск заполнения фактов - значений показателей upsert={upsert}...")
        client =  WBApiClient(self.wb_cfg)
        mapped_gen = map_collection(client.fetch_all(), map_raw_indicator_data)
        self.data_collector.load_data_auto(
            model=RawIndicatorData,
            data_generator=mapped_gen,
            upsert=upsert
        )
        self.logger.info("Заполнение выполнено!")

    def full_sync(self):
        """
        Заполнение данных для/после инициализации
        """
        self.set_connection()
        self.logger.info(f"Полное заполнение хранилища данных: справочники + исторические факты")
        # Загружаем справочники
        self.sync_countries()
        self.sync_indicators()
        # Загружаем факты
        self.sync_data()
        self.logger.info(f"Полное заполнение выполнено успешно")





