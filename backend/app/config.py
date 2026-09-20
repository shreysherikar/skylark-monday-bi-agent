
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Skylark BI Agent"
    environment: str = Field(default="development", validation_alias=AliasChoices("ENV", "ENVIRONMENT"))
    
    # Monday.com Configuration
    monday_api_token: str = Field(default="", validation_alias=AliasChoices("MONDAY_API_TOKEN"))
    monday_api_url: str = Field(default="https://api.monday.com/v2", validation_alias=AliasChoices("MONDAY_API_URL"))
    monday_work_orders_board_id: str | None = Field(
        default="5031416769",
        validation_alias=AliasChoices("MONDAY_WORK_ORDERS_BOARD_ID", "MONDAY_WO_BOARD_ID")
    )
    monday_deals_board_id: str | None = Field(
        default="5031416803",
        validation_alias=AliasChoices("MONDAY_DEALS_BOARD_ID")
    )
    
    # In-memory board cache TTL in seconds (default 5 minutes per §3)
    board_cache_ttl_seconds: int = Field(default=300, validation_alias=AliasChoices("BOARD_CACHE_TTL_SECONDS"))
    
    # Groq API Configuration (Official Python Groq SDK)
    groq_api_key: str = Field(default="", validation_alias=AliasChoices("GROQ_API_KEY"))
    groq_model: str = Field(default="openai/gpt-oss-120b", validation_alias=AliasChoices("GROQ_MODEL"))
    
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


settings = Settings()
