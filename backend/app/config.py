from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "Skylark BI Agent"
    environment: str = Field(default="development", env="ENV")
    
    # Monday.com Configuration
    monday_api_token: str = Field(default="", env="MONDAY_API_TOKEN")
    monday_api_url: str = Field(default="https://api.monday.com/v2", env="MONDAY_API_URL")
    monday_work_orders_board_id: Optional[str] = Field(default=None, env="MONDAY_WO_BOARD_ID")
    monday_deals_board_id: Optional[str] = Field(default=None, env="MONDAY_DEALS_BOARD_ID")
    
    # In-memory board cache TTL in seconds (default 5 minutes per §3)
    board_cache_ttl_seconds: int = Field(default=300, env="BOARD_CACHE_TTL_SECONDS")
    
    # Anthropic Claude API
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    claude_model: str = Field(default="claude-3-5-sonnet-20241022", env="CLAUDE_MODEL")
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
