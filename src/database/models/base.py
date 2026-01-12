import pathlib

from sqlalchemy import event, text, inspect
from sqlalchemy.orm import DeclarativeBase, ColumnProperty
from sqlalchemy.sql.ddl import CreateSchema, DropSchema

from src.database.utils import run_sql_script
import logging

logger = logging.getLogger(__name__)
CURRENT_DIR = pathlib.Path(__file__).parent


class Base(DeclarativeBase):
    def to_dict(self) -> dict:
        table = self.__table__
        res = {}

        # .values() возвращает итерируемый список объектов Column
        for column in table.columns.values():
            field_name = column.name
            val = getattr(self, field_name)

            # Проверяем является ли поле автоматическим (PK или дефолты)
            is_auto = (
                    column.primary_key or
                    column.server_default is not None or
                    column.default is not None
            )

            # Исключаем поле из словаря только если оно автоматическое и значение None
            if not (is_auto and val is None):
                res[field_name] = val

        return res

TARGET_SCHEMAS = ["raw", "normalized", "mart"]
INIT_SCRIPTS = [
    str(CURRENT_DIR/"sql"/"mart"/"create_mat_views.sql"),
    str(CURRENT_DIR/"sql"/"mart"/"create_views.sql"),
    str(CURRENT_DIR/"sql"/"triggers"/"trigger_country_row_to_norm.sql"),
    str(CURRENT_DIR/"sql"/"triggers"/"trigger_indicator_row_to_norm.sql"),
    str(CURRENT_DIR/"sql"/"triggers"/"trigger_indicator_data_row_to_norm.sql"),
    str(CURRENT_DIR/"sql"/"maintenance"/"setup_maintenance.sql"),
]
DROP_SCRIPTS = [
    str(CURRENT_DIR/"sql"/"mart"/"drop_views.sql"),
    str(CURRENT_DIR/"sql"/"mart"/"drop_mat_views.sql"),
]
#
@event.listens_for(Base.metadata, "before_create")
def create_schemas(target, connection, **kw):
    """
    Привязываем создание схем к событию "перед выполнением Base.metadat.create_all"
    """
    inspector = inspect(connection)
    existing_schemas = inspector.get_schema_names()

    for schema in TARGET_SCHEMAS:
        if schema not in existing_schemas:
            logger.info(f"Создание новой схемы: {schema}")
            connection.execute(CreateSchema(schema, if_not_exists=True))

@event.listens_for(Base.metadata, "after_create")
def initialize_mart_layer(target, connection, **kw):
    """
    Привязываем создание наполнения аналитического слоя  также триггеров к событию "после выполнения Base.metadat.create_all"
    """
    if not INIT_SCRIPTS:
        logger.warning("Список INIT_SCRIPTS пуст. Инфраструктура (триггеры/вью) не будет настроена!")
        return
    for filename in INIT_SCRIPTS:
        run_sql_script(connection, filename)

@event.listens_for(Base.metadata, "before_drop")
def drop_mart_layer(target, connection, **kw):
    """
    Привязываем удаление наполнения аналитического слоя к событию "перед выполнением Base.metadat.drop_all"
    """
    if not DROP_SCRIPTS:
        logger.warning("Список DROP_SCRIPTS пуст")
        return
    for filename in DROP_SCRIPTS:
        run_sql_script(connection, filename)

    has_cron = connection.execute(text(
        "SELECT 1 FROM pg_extension WHERE extname = 'pg_cron'"
    )).scalar()

    if has_cron:
        logger.warning("Удаление запланированных задач pg_cron...")
        # Удаляем задачи по именам, которые мы давали при инициализации
        connection.execute(text("""
                SELECT cron.unschedule(jobname) 
                FROM cron.job 
                WHERE jobname IN ('nightly-cleanup', 'nightly-refresh')
            """))

@event.listens_for(Base.metadata, "after_drop")
def drop_schemas(target, connection, **kw):
    """
    Привязываем удаление схем к событию "после выполнения Base.metadat.drop_all"
    """
    inspector = inspect(connection)
    existing_schemas = inspector.get_schema_names()

    for schema in TARGET_SCHEMAS:
        if schema in existing_schemas:
            logger.info(f"Удаление новой схемы: {schema}")
            connection.execute(DropSchema(schema, cascade=True))
