import os
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from dotenv import load_dotenv
import json
from pathlib import Path

load_dotenv()

@dataclass(frozen=True)
class DatabaseConfig:
    host: str = os.getenv("DB_HOST", "")
    port: int = int(os.getenv("DB_PORT", 6543))
    user: str = os.getenv("DB_USER", "")
    dbname: str = os.getenv("DB_NAME", "postgres")
    password: str = os.getenv("DB_PASSWORD", "")

    @property
    def url(self) -> str:
        return  f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"

    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 5
    batch_size: int = 600

@dataclass(frozen=True)
class ApiSettings:
    name: str = "WB_API"
    base_url: str = "https://api.worldbank.org/v2"
    batch_size: int = 500
    retries: int = 3
    timeout: int = 5
    endpoint: Optional[str] = None
    headers: Optional[Dict[str, str]] = field(default=None)
    auth_token: Optional[str] = None

@dataclass(frozen=True)
class WBSettings:
    countries: List[str]
    indicators: List[str]
    date_intervals: List[str]
    api_settings: ApiSettings = field(default_factory=ApiSettings)

    @classmethod
    def from_json(cls, file_name: str) -> "WBSettings":
        current_file_path = Path(__file__).resolve()

        project_root = current_file_path.parent.parent

        settings_path = project_root / file_name
        if not os.path.exists(settings_path):
            raise FileNotFoundError(f"Конфигурационный файл не найден: {settings_path}")

        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

