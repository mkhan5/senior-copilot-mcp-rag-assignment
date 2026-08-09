import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    cmms_api_base_url: str = "http://maintenance-cmms:8001"
    cmms_api_token: str = ""
    request_timeout: float = 30.0
    max_retries: int = 3
    retry_base_delay: float = 0.5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


settings = Settings()
