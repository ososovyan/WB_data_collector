
from sqlalchemy import create_engine, text, Engine, Sequence, Row, NullPool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, Session

from typing import Optional, Generator
from contextlib import contextmanager

from src.config import DatabaseConfig
from src.database.utils import run_sql_script
import logging
logger = logging.getLogger(__name__)
"""
            try:
                self._engine = create_engine(
                    self.config.url,
                    pool_pre_ping=True,
                    echo=self.config.echo,
                    pool_size=self.config.pool_size,
                    max_overflow=self.config.max_overflow
                )
"""
class DatabaseConnection:
    """
    Управление подключением к базе данных
    """
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None

    @property
    def engine(self) -> Engine:
        """
        Ленивая инициализация движка
        """
        if self._engine is None:
            logger.info(f"Инициализация движка БД для: {self.config.host}")
            try:
                self._engine = create_engine(
                    self.config.url,
                    poolclass=NullPool,
                    echo=self.config.echo,
                    connect_args={
                        "sslmode": "require",
                        "options": "-c prepared_statements=off",
                        # Даем 20 секунд на ПЕРВОЕ подключение (важно для "спящих" баз)
                        "connect_timeout": 20,
                        "keepalives": 1,
                        "keepalives_idle": 30
                    }
                )
            except Exception as e:
                logger.error(f"Не удалось инициализировать движок БД: {e}")
                raise
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """
        Фабрика сессий
        """
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
        return self._session_factory

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Контекстный менеджер для работы с сессиями
        """
        session = self.session_factory()
        logger.debug("Открытие новой сессии БД")
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка в транзакции: {e}. Выполнен откат (rollback).")
            raise
        finally:
            session.close()
            logger.debug("Сессия БД закрыта")

    def execute_raw_sql(self, sql: str, **params) -> Sequence[Row]:
        """
        Выполнение сырого SQL-запроса
        """
        with self.engine.begin() as conn:
            result = conn.execute(text(sql), params)
            return result.fetchall()

    def execute_sql_file(self, file_path: str) -> bool:
        """
        Выполнение SQL из файла
        """
        logger.info(f"Выполнение SQL-скрипта из файла: {file_path}")
        try:
            with self.engine.begin() as conn:
                result = run_sql_script(conn, file_path)
                logger.info(f"Скрипт {file_path} успешно выполнен.")
                return result
        except Exception as e:
            logger.error(f"Ошибка при выполнении файла {file_path}: {e}")
            return False

    def health_check(self) -> bool:
        """
        Проверка подключения к БД
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning(f"Проверка связи с БД не удалась: {e}")
            return False

    def close(self):
        """Закрытие подключения"""
        if self._engine:
            logger.info("Закрытие пула соединений БД (dispose).")
            self._engine.dispose()
            self._engine = None