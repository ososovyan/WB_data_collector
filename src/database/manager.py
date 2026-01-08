
from itertools import islice

from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, DataError
from typing import Optional, Generator, Type, Dict, Any, List
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
            logger.info("Инициализация структуры хранилища...")
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
            logger.info("Полное удаление хранилища...")
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

    def truncate_tables(self, schema: str = 'raw'):
        inspector = inspect(self.db.engine)
        tables = inspector.get_table_names(schema=schema)

        if not tables:
            logger.warning(f"Схема '{schema}' пуста, нечего очищать")
            return

        tables_list = ", ".join([f"{schema}.{t}" for t in tables])
        sql = f"TRUNCATE TABLE {tables_list} RESTART IDENTITY CASCADE;"
        logger.info(f"Очистка данных в схеме '{schema}' (таблицы: {tables_list})")
        self.db.execute_raw_sql(sql=sql)


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

    def load_data(
            self,
            model: Type,
            data_generator: Generator[Dict[str, Any], Any, Any],
            upsert: bool = True
    ):
        """
        Универсальная загрузка данных, работающая с любой СУБД.
        """
        total_processed = 0
        table_name = model.__tablename__
        logger.info(f"Запуск пактеной вставки в {table_name} upsert={upsert}")
        for batch in self._get_batches(data_generator):
            try:
                with self.db.get_session() as session:
                    if upsert:
                        # Стратегия: Обновление или вставка (медленнее)
                        for item_data in batch:
                            obj = model(**item_data)
                            session.merge(obj)
                    else:
                        # Стратегия: Только вставка (быстрее) Превращаем словари в объекты моделей
                        # # В случае ошибки в батче, транзакция откатится целиком
                        objs = [model(**item_data) for item_data in batch]
                        session.add_all(objs)

                    # Завершение транзакции произойдет автоматически при выходе из контекста get_session
                    total_processed += len(batch)
                    logger.info(f"Загружено {total_processed} строк")

            except SQLAlchemyError as e:
                logger.error(f"Ошибка при загрузке батча в {table_name}: {e}")
                raise e

    def load_data_postgres(
            self,
            model: Type,
            data_generator: Generator[Dict[str, Any], Any, Any],
            upsert: bool = True
    ):
        """
        Пакетная вставка данных с защитой только для Postgres
        """
        loaded = 0
        table_name = model.__tablename__
        logger.info(f"Запуск пакетной вставки в {table_name} (PostgreSQL mode, upsert={upsert})")
        # Инспекция модели для автоматического определения колонок
        inst = inspect(model)
        pk_columns = [c.name for c in inst.primary_key]
        # Все колонки, кроме первичных ключей, для обновления в режиме Upsert
        update_columns = [c.name for c in inst.columns if not c.primary_key]

        for batch in self._get_batches(data_generator):
            try:
                with self.db.get_session() as session:
                    # Создаем базовый INSERT
                    stmt = insert(model).values(batch)

                    if upsert and update_columns:
                        # Режим обновления: при конфликте PK обновляем все остальные поля
                        statement = stmt.on_conflict_do_update(
                            index_elements=pk_columns,
                            set_={col: getattr(stmt.excluded, col) for col in update_columns}
                        )
                    else:
                        # Режим игнорирования: просто пропускаем существующие ключи
                        statement = stmt.on_conflict_do_nothing(index_elements=pk_columns)

                    session.execute(statement)

                    loaded += len(batch)
                    logger.info(f"[{table_name}] Загружен батч: +{len(batch)} строк. Всего: {loaded}")

            except Exception as e:
                logger.error(f"Ошибка при загрузке батча в {table_name}: {e}")
                raise e

        logger.info(f"Загрузка в {table_name} завершена. Итого: {loaded} строк.")

    def load_data_auto(
            self,
            model: Type,
            data_generator: Generator[Dict[str, Any], Any, Any],
            upsert: bool = True
    ):
        """
        Мастер-метод: автоматически выбирает оптимальный способ загрузки
        в зависимости от текущего диалекта базы данных.
        """
        dialect = self.db.engine.name
        # Проверяем имя диалекта базы данных
        logger.debug(f"Выбор метода загрузки для диалекта '{dialect}'")
        if dialect == 'postgresql':
            return self.load_data_postgres(model, data_generator, upsert)

        # Для всех остальных БД
        return self.load_data(model, data_generator, upsert)