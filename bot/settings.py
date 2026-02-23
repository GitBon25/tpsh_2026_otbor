from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str

    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "videos"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    gigachat_credentials: str
    gigachat_model: str = "GigaChat"
    gigachat_scope: str = "GIGACHAT_API_PERS"


settings = Settings()