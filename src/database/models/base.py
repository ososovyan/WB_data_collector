import pathlib

from sqlalchemy import event, text, inspect
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.ddl import CreateSchema, DropSchema

from src.database.utils import run_sql_script
import logging

logger = logging.getLogger(__name__)
CURRENT_DIR = pathlib.Path(__file__).parent

class Base(DeclarativeBase):
    def to_dict(self) -> dict:
        mapper = inspect(self.__class__).mapper
        return {
            c.name: getattr(self, c.name)
            for c in mapper.columns
            # Проверяем, есть ли у колонки дефолт на стороне сервера
            # Если есть, и значение в объекте None — не включаем её в словарь
            if not (c.server_default is not None and getattr(self, c.name) is None)
        }


TARGET_SCHEMAS = ["raw", "normalized", "mart"]
INIT_SCRIPTS = [
    #".sql/mart/create_views.sql",
    #".sql/mart/create_mart_views.sql",
    str(CURRENT_DIR/"sql"/"triggers"/"trigger_country_row_to_norm.sql"),
    #str(CURRENT_DIR/"sql"/"triggers"/"trigger_indicator_row_to_norm.sql"),
    #".sql/triggers/trigger_indicator_row_to_norm.sql",
    #".sql/triggers/trigger_indicator_data_row_to_norm.sql",
]
DROP_SCRIPTS = [
            #"sql/mart/drop_views.sql", "sql/mart/drop_mart_views.sql"
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
