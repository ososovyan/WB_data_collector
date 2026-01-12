import argparse
import logging
import os
import sys
from pathlib import Path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) # папка src
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)              # корень проекта
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
import traceback
from src.pipline.manager import WBPiplineManager
from src.config import WBSettings, DatabaseConfig

logger = logging.getLogger(__name__)

def setup_logging(verbose=False, silent=False):
    """Централизованная настройка логирования"""
    level = logging.WARNING if silent else (logging.DEBUG if verbose else logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Убираем старые обработчики
    for hdlr in root_logger.handlers[:]:
        root_logger.removeHandler(hdlr)

    root_logger.addHandler(handler)

    # Устанавливаем уровни для внешних библиотек
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

def create_parser():
    parser = argparse.ArgumentParser(
        prog='wb-pipeline',
        description='World Bank Data Pipeline Manager'
    )

    parser.add_argument('-v', '--verbose', action='store_true', help='Подробный вывод')
    parser.add_argument('-q', '--quiet', action='store_true', help='Только ошибки')
    parser.add_argument('-c', '--config', type=Path, help='Конфиг для данных')
    parser.add_argument('-y', '--yes', action='store_true', help='Не спрашивать подтверждение')

    subparsers = parser.add_subparsers(dest='command', metavar='<command>', required=True)

    # 2. Команда structure
    structure = subparsers.add_parser('structure', help='Управление структурой БД')
    structure_sub = structure.add_subparsers(dest='subcommand', metavar='<action>', required=True)
    structure_sub.add_parser('init', help='Инициализация структуры')
    structure_sub.add_parser('drop', help='Удаление структуры')

    # 3. Команда clear
    clear = subparsers.add_parser('clear', help='Очистка данных')
    clear.add_argument('target_table', nargs='?', choices=['all', 'countries', 'indicators', 'data'],
                       default='all', help='Что очистить')
    clear.add_argument('target_schema', nargs='?', choices=['public', 'raw', 'normalize'],
                       default='public', help='Где очистить')

    # 4. Команда load
    load = subparsers.add_parser('load', help='Загрузка данных')
    load.add_argument('target', choices=['all', 'countries', 'indicators', 'data', 'refs'], help='Что загрузить')
    load.add_argument('-u', '--upsert', action='store_true', help='Обновить существующие записи')

    return parser


def validate_db_config(example_file='.env.example'):
    load_dotenv() # Загружаем текущий .env
    required_vars = []
    if not os.path.exists(example_file):
        # Если примера нет, используем список по умолчанию
        required_vars = ['DB_HOST', 'DB_USER', 'DB_NAME']
    else:
        # Читаем ключи из .env.example (отбрасываем комментарии и пустые строки)
        with open(example_file, 'r') as f:
            required_vars = [
                line.split('=')[0].strip()
                for line in f
                if line.strip() and not line.startswith('#')
            ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        raise EnvironmentError(
            f"Ошибка! В окружении отсутствуют переменные: {', '.join(missing_vars)}\n"
            f"Пожалуйста, заполните их в файле .env на основе {example_file}"
        )

def create_wb_settings_for_refs() -> WBSettings:
    """
    Создание настроек WBSettings для справочников
    """
    return WBSettings(
        countries=[],
        indicators=[],
        date_intervals=[],
    )


def create_wb_settings_from_json(json_path: Path) -> WBSettings:
    """
    Создание настроек WBSettings из JSON файла для загрузки фактов
    """
    if not json_path.exists():
        raise FileNotFoundError(f"Конфигурационный файл для данных не найден: {json_path}")

    return WBSettings.from_json(str(json_path))

def main():
    parser = create_parser()
    args = parser.parse_args()

    setup_logging(verbose=args.verbose, silent=args.quiet)

    try:
        if args.command == 'load' and args.target in ['data', 'all'] and not args.config:
            logger.error("Для загрузки данных требуется --config")
            return
        elif args.config:
            wb_settings = create_wb_settings_from_json(args.config)
        else:
            wb_settings = create_wb_settings_for_refs()

        validate_db_config()
        db_config = DatabaseConfig()

        # Инициализация менеджера
        manager = WBPiplineManager(wb_settings, DatabaseConfig())
        manager.set_connection()

        if args.command == 'structure':

            if args.subcommand == 'init':
                logger.info("Инициализация структуры БД...")
                manager.init_data_storage()
                logger.info("Готово!")
            elif args.subcommand == 'drop':
                if args.yes or input("Удалить ВСЮ структуру БД? [y/N]: ").lower() in ('y', 'yes'):
                    logger.warning("Удаление структуры БД...")
                    manager.drop_data_storage()
                    logger.info("Структура удалена")
                else:
                    logger.info("Отменено")

        elif args.command == 'clear':
            name = args.target_table
            schema = args.target_schema
            if args.yes or input(f"Очистить {schema}.{name}? [y/N]: ").lower() in ('y', 'yes'):
                logger.warning(f"Очистка {schema}.{name}...")
                if name == "all":
                    manager.clear_data(schema=schema)
                else:
                    manager.clear_data(table=name, schema=schema)
                logger.info(f"{schema}.{name} очищены")
            else:
                logger.info("Отменено")

        elif args.command == 'load':
            logger.info(f"Загрузка {args.target}...")
            if args.target in ['refs', 'countries', 'all']:
                manager.sync_countries(upsert=args.upsert)
                logger.info("Справочники стран загружены")
            if args.target in ['refs', 'indicators', 'all']:
                manager.sync_indicators(upsert=args.upsert)
                logger.info("Справочники показателей загружены")
            if args.target in ['data', 'all']:
                manager.sync_data(upsert=args.upsert)
                logger.info("Значения показателей загружены")
            logger.info("Загрузка завершена")

    except FileNotFoundError as e:
        logger.error(f"Файл не найден: {e}")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        if args.verbose:  # Детали ошибки только в verbose режиме

            logger.debug(traceback.format_exc())

if __name__ == "__main__":
    main()