import sqlparse
from sqlalchemy import text, Connection
import logging

logger = logging.getLogger(__name__)

def run_sql_script(connection: Connection, file_path: str) -> bool:
    """
    Универсальный исполнитель SQL-скриптов.
    """
    try:
        logger.info(f"Выполнение SQL-скрипта: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Надежное разбиение на команды (sqlparse учитывает комментарии и кавычки)
        statements = sqlparse.split(content)
        for statement in statements:
            clean_stmt = statement.strip()
            if clean_stmt:
                connection.execute(text(clean_stmt))
        return True
    except Exception as e:
        logger.error(f"Ошибка выполнения SQL-скрипта {file_path}: {e}")
        return False
