from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    database_url: str = "sqlite:///./yapper_dash.db"  # SQLite 기본값
    telegram_bot_token: str = ""
    api_base_url: str = "http://localhost:8000/api"
    allowed_chat_ids: List[str] = []
    
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_token_secret: str = ""
    
    rate_limit_per_hour: int = 10
    max_tweets_per_page: int = 100
    
    debug: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()