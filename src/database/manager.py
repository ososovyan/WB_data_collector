
from itertools import islice

from sqlalchemy import inspect, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, DataError
from typing import Optional, Generator, Type, Dict, Any, List

from tenacity import retry, stop_after_attempt, wait_exponential

from src.database.connection import DatabaseConnection
from src.database.models import Base
import logging

logger = logging.getLogger(__name__)

class DataBaseManager:
    """
    Менеджер для выполнения основных операций над базой данных
    """
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self.batch_size = db_connection.config.batch_size

    def create_all(self) -> bool:
        """
        Создает все таблицы
        """
        try:
            logger.debug("Инициализация структуры хранилища...")
            Base.metadata.create_all(self.db.engine)
            return True
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при инициализации структуры: {e}")
            return False

    def drop_all(self) -> bool:
        """
        Удаляет все таблицы
        """
        try:
            # Удаление таблиц
            logger.debug("Полное удаление хранилища...")
            Base.metadata.drop_all(self.db.engine)
            return True
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении структуры: {e}")
            return False

    def get_database_info(self):
        """
        Собирает всю необходимую информацию о БД
        """
        pass

    def vacuum_analyze(self):
        pass

    def truncate_table(self, table_name: str = None, schema: str = None):
        """
        Очистка таблиц в БД.
        :param table_name: Имя конкретной таблицы. Если None — чистим всю схему.
        :param schema: Имя схемы. Если None или пусто — по умолчанию 'public'.
        """
        # Определяем схему (если не передана, используем public по стандарту Postgres)
        target_schema = schema if schema else 'public'

        inspector = inspect(self.db.engine)

        # Получаем список существующих таблиц в целевой схеме
        existing_tables = inspector.get_table_names(schema=target_schema)

        if not existing_tables:
            logger.warning(f"Схема '{target_schema}' пуста или не существует")
            return

        # Формируем список таблиц для удаления
        if table_name:
            # Если указана конкретная таблица, проверяем её наличие
            if table_name not in existing_tables:
                logger.warning(f"Таблица '{table_name}' не найдена в схеме '{target_schema}'")
                return
            tables_to_truncate = [f"{target_schema}.{table_name}"]
        else:
            # Если имя таблицы не указано — берем все таблицы из схемы
            tables_to_truncate = [f"{target_schema}.{t}" for t in existing_tables]


        tables_list_str = ", ".join(tables_to_truncate)
        sql = f"TRUNCATE TABLE {tables_list_str} RESTART IDENTITY CASCADE;"

        logger.debug(f"Запуск TRUNCATE: {tables_list_str}")

        try:
            self.db.execute_raw_sql(sql=sql)
            logger.debug(f"Очистка завершена успешно.")
        except Exception as e:
            logger.error(f"Ошибка при очистке таблиц: {e}")
            raise e


    def _get_batches(
            self,
            data_generator: Generator[Dict[str, Any], Any, Any],
            size: int = None
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Вспомогательный генератор для нарезки данных на батчи.
        Берет бесконечный или длинный поток данных и отдает его кусками.
        """
        batch_size = size or self.batch_size

        while True:
            batch = list(islice(data_generator, batch_size))
            if not batch:
                break
            yield batch

    @staticmethod
    def _get_model_metadata(model: Type):
        """
        Универсальный инспектор: находит уникальные ключи и поля для обновления.
        """
        inst = inspect(model)
        table = inst.mapper.local_table

        # 1. Ищем бизнес-ключи (UniqueConstraint)
        conflict_targets = next(
            ([c.name for c in const.columns]
             for const in table.constraints if isinstance(const, UniqueConstraint)),
            [c.name for c in inst.primary_key]  # Если нет UC, берем Primary Key
        )

        # 2. Поля для обновления (все кроме PK и ключей конфликта)
        update_cols = [
            c.name for c in table.columns
            if not c.primary_key and c.name not in conflict_targets
        ]

        return conflict_targets, update_cols

    @staticmethod
    def _execute_postgres_batch(session, model, batch, upsert, targets, update_cols):
        """
        Логика вставки специально для PostgreSQL (быстрая)
        """
        stmt = insert(model).values(batch)
        if upsert and targets:
            statement = stmt.on_conflict_do_update(
                index_elements=targets,
                set_={c: getattr(stmt.excluded, c) for c in update_cols}
            )
        else:
            statement = stmt.on_conflict_do_nothing(index_elements=targets)
        session.execute(statement)

    @staticmethod
    def _execute_universal_batch(session, model, batch, upsert, **kwargs):
        """
        Логика вставки для остальных БД (через ORM)
        """
        if upsert:
            for item in batch:
                session.merge(model(**item))
        else:
            session.add_all([model(**item) for item in batch])

    def load_data_auto(self, model: Type, data_generator: Generator, upsert: bool = True):
        """
        Мастер-метод: Общая логика подготовки и распределения задач
        """
        table_name = model.__tablename__
        dialect = self.db.engine.name

        # Общая подготовка метаданных
        targets, update_cols = self._get_model_metadata(model)

        # Выбор исполнителя в зависимости от СУБД
        batch_executor = (
            self._execute_postgres_batch if dialect == 'postgresql'
            else self._execute_universal_batch
        )

        logger.info(f"Запуск загрузки в {table_name} [{dialect}]. Keys: {targets}")

        # Общий цикл обработки батчей
        total = 0
        for batch in self._get_batches(data_generator):
            try:
                with self.db.get_session() as session:
                    batch_executor(
                        session=session,
                        model=model,
                        batch=batch,
                        upsert=upsert,
                        targets=targets,
                        update_cols=update_cols
                    )
                total += len(batch)
                logger.info(f"[{table_name}] Загружено всего: {total}")
            except Exception as e:
                logger.error(f"Критическая ошибка батча в {table_name}: {e}")
                raise e