from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    default_ai_provider: str = "deepseek"
    database_url: str = "sqlite+aiosqlite:///./data/dota2.db"
    redis_url: str = ""
    dev_mode: bool = False
    share_base_url: str = "http://localhost:8000"
    wechat_appid: str = ""
    wechat_secret: str = ""
    steam_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
