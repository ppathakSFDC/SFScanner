from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )

    SF_CLIENT_ID: str = ""
    SF_CLIENT_SECRET: str = ""
    PORT: int = 8080
    SF_REDIRECT_URI: str = "http://localhost:8080/auth/callback"
    SF_LOGIN_URL: str = "https://login.salesforce.com"
    SESSION_SECRET: str = "change-me-in-production"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = ""
    ANTHROPIC_CUSTOM_HEADERS: str = ""
    ANTHROPIC_DEFAULT_SONNET_MODEL: str = "claude-sonnet-4-5-20250929"

    # Salesforce LLM Gateway (OpenAI-compatible).
    # When LLMGW_API_KEY is set the app uses llmgw instead of Anthropic.
    LLMGW_API_KEY: str = ""
    LLMGW_BASE_URL: str = "https://eng-ai-model-gateway.sfproxy.devx-preprod.aws-esvc1-useast2.aws.sfdc.cl/v1"
    LLMGW_MODEL: str = "gpt-5.6-sol"
    FRONTEND_URL: str = "http://localhost:8080"
    MCP_API_KEY: str = ""


settings = Settings()
