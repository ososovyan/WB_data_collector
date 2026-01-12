import pathlib
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def auto_refresh_marts(func):
    """Декоратор слоя оркестрации для обновления витрин"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):

        result = func(self, *args, **kwargs)

        self.db_connection.execute_raw_sql("CALL mart.refresh_analytics();")

        return result
    return wrapper