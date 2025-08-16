import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings"""

    # ==============================================
    # BASIC SETTINGS
    # ==============================================
    ENV: str = Field(default="development", description="Environment mode")
    DEBUG: bool = Field(default=True, description="Debug mode")
    PORT: int = Field(default=8000, description="Application port")
    HOST: str = Field(default="0.0.0.0", description="Application host")

    # ==============================================
    # BLOCKCHAIN API KEYS
    # ==============================================
    QUICKNODE_RPC: Optional[str] = None
    QUICKNODE_WSS: Optional[str] = None

    # Helius
    HELIUS_API_KEY: Optional[str] = None
    HELIUS_RPC_URL: str = "https://rpc.helius.xyz/?api-key="

    # Chainbase
    CHAINBASE_API_KEY: Optional[str] = None
    CHAINBASE_BASE_URL: str = "https://api.chainbase.online/v1"

    # Birdeye
    BIRDEYE_API_KEY: Optional[str] = None
    BIRDEYE_BASE_URL: str = "https://public-api.birdeye.so"

    # Blowfish
    BLOWFISH_API_KEY: Optional[str] = None
    BLOWFISH_BASE_URL: str = "https://api.blowfish.xyz"

    # Solscan
    SOLSCAN_API_KEY: Optional[str] = None
    SOLSCAN_BASE_URL: str = "https://public-api.solscan.io"

    # DexScreener
    DEXSCREENER_BASE_URL: str = "https://api.dexscreener.com/latest/dex/tokens"

    # PumpFun API
    PUMPFUN_API_KEY: Optional[str] = None

    # RugCheck API
    RUGCHECK_API_KEY: Optional[str] = None

    # ==============================================
    # SOCIAL NETWORKS
    # ==============================================
    DATAIMPULSE_API_KEY: Optional[str] = None
    DATAIMPULSE_BASE_URL: str = "https://api.dataimpulse.com"

    # ==============================================
    # WEBHOOKS
    # ==============================================
    QUICKNODE_WEBHOOK_SECRET: Optional[str] = None
    QUICKNODE_WEBHOOK_URL: Optional[str] = None
    HELIUS_WEBHOOK_SECRET: Optional[str] = None
    WEBHOOK_BASE_URL: Optional[str] = None

    # ==============================================
    # STORAGE
    # ==============================================
    CHROMA_DB_PATH: str = "./shared_data/chroma"
    CHROMA_COLLECTION_NAME: str = "solana_tokens_knowledge"
    KNOWLEDGE_BASE_PATH: str = "./shared_data/knowledge_base"
    LOGS_DIR: str = "./shared_data/logs"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0

    # ==============================================
    # CELERY
    # ==============================================
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: str = "json"
    CELERY_TIMEZONE: str = "UTC"

    # ==============================================
    # AI MODELS
    # ==============================================
    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_API_URL: str = "https://api.mistral.ai/v1"
    MISTRAL_MODEL: str = "mistral-7b-instruct"

    LLAMA_API_KEY: Optional[str] = None
    LLAMA_API_URL: str = "https://api.together.xyz/v1"
    LLAMA_MODEL: str = "meta-llama/Llama-3-70b-chat-hf"

    # ==============================================
    # TRADING APIS
    # ==============================================
    JUPITER_API_URL: str = "https://quote-api.jup.ag/v6"

    # ==============================================
    # NOTIFICATIONS
    # ==============================================
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # ==============================================
    # SECURITY
    # ==============================================
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    WALLET_SECRET_KEY: Optional[str] = None
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000

    # ==============================================
    # PERFORMANCE
    # ==============================================
    API_TIMEOUT: int = 30
    AI_TIMEOUT: int = 60
    WEBHOOK_TIMEOUT: int = 5
    HTTP_POOL_SIZE: int = 100
    HTTP_MAX_RETRIES: int = 3
    CACHE_TTL_SHORT: int = 300
    CACHE_TTL_MEDIUM: int = 1800
    CACHE_TTL_LONG: int = 7200

    # ==============================================
    # MONITORING
    # ==============================================
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    SENTRY_DSN: Optional[str] = None

    # ==============================================
    # DEVELOPMENT
    # ==============================================
    TEST_TOKEN_MINT: str = "So11111111111111111111111111111111111112"
    TEST_SOCIAL_DATA_FILE: str = "test_social_data.json"
    ENABLE_API_MOCKS: bool = False
    MOCK_AI_RESPONSES: bool = False

    # ==============================================
    # VALIDATION
    # ==============================================
    @validator('ENV')
    def validate_env(cls, v):
        allowed = ['development', 'staging', 'production']
        if v not in allowed:
            raise ValueError(f'ENV must be one of: {allowed}')
        return v

    @validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        allowed = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed:
            raise ValueError(f'LOG_LEVEL must be one of: {allowed}')
        return v.upper()

    @validator('CHROMA_DB_PATH', 'KNOWLEDGE_BASE_PATH', 'LOGS_DIR')
    def validate_paths(cls, v):
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path.absolute())

    # ==============================================
    # CONFIGURATION READING
    # ==============================================
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "allow"  # <--- Allow extra keys in .env
    }

    # ==============================================
    # HELPER METHODS
    # ==============================================
    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.ENV == "development"

    def get_redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return self.REDIS_URL.replace('redis://', f'redis://:{self.REDIS_PASSWORD}@')
        return self.REDIS_URL

    def get_helius_rpc_url(self) -> str:
        if self.HELIUS_API_KEY:
            return f"{self.HELIUS_RPC_URL}{self.HELIUS_API_KEY}"
        return self.HELIUS_RPC_URL

    def validate_critical_keys(self) -> list[str]:
        missing = []
        critical_keys = [
            ('HELIUS_API_KEY', 'Helius API'),
            ('MISTRAL_API_KEY', 'Mistral AI'),
            ('LLAMA_API_KEY', 'LLaMA AI'),
        ]
        for key, name in critical_keys:
            if not getattr(self, key):
                missing.append(name)
        return missing

    def get_all_api_keys_status(self) -> dict:
        keys_status = {}
        api_keys = [
            'HELIUS_API_KEY', 'CHAINBASE_API_KEY', 'BIRDEYE_API_KEY',
            'BLOWFISH_API_KEY', 'SOLSCAN_API_KEY', 'DATAIMPULSE_API_KEY',
            'MISTRAL_API_KEY', 'LLAMA_API_KEY', 'TELEGRAM_BOT_TOKEN',
            'PUMPFUN_API_KEY', 'RUGCHECK_API_KEY'
        ]
        for key in api_keys:
            value = getattr(self, key)
            keys_status[key] = {
                'configured': bool(value),
                'masked_value': f"{value[:8]}***" if value else None
            }
        return keys_status


@lru_cache()
def get_settings() -> Settings:
    return Settings()