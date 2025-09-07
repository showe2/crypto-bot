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
    BASE_URL: str = Field(description="Base URL for all endpoints (REQUIRED)")

    # ==============================================
    # ALEX SYSTEM
    # ==============================================
    ALEX_INGEST_URL: str = f"{BASE_URL}/api/ingest"
    INTERNAL_TOKEN: Optional[str] = None

    # ==============================================
    # AI CONFIGURATION
    # ==============================================
    GROQ_API_KEY: Optional[str] = None

    # ==============================================
    # BLOCKCHAIN API KEYS
    # ==============================================
    
    # Helius
    HELIUS_API_KEY: Optional[str] = None
    HELIUS_RPC_URL: str = "https://rpc.helius.xyz/?api-key="
    HELIUS_BASE_URL: str = "https://mainnet.helius-rpc.com"

    # Birdeye
    BIRDEYE_API_KEY: Optional[str] = None
    BIRDEYE_BASE_URL: str = "https://public-api.birdeye.so"

    # SolanaFM (replaces Solscan) - No API key required
    SOLANAFM_BASE_URL: str = "https://api.solana.fm"

    # DexScreener
    DEXSCREENER_BASE_URL: str = "https://api.dexscreener.com"

    # SolSniffer - Solana token analysis and monitoring
    SOLSNIFFER_API_KEY: Optional[str] = None
    SOLSNIFFER_BASE_URL: str = "https://api.solsniffer.com"

    # PumpFun API
    PUMPFUN_API_KEY: Optional[str] = None

    # RugCheck API
    RUGCHECK_BASE_URL: str = "https://api.rugcheck.xyz"

    # GOplus API - Simplified to single APP Key + APP Secret pair
    GOPLUS_APP_KEY: Optional[str] = None
    GOPLUS_APP_SECRET: Optional[str] = None
    GOPLUS_BASE_URL: str = "https://api.gopluslabs.io"

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
    # SNAPSHOT SERVICE
    # ==============================================
    SNAPSHOT_INTERVAL_SECONDS: int = Field(default=3600, description="How often to run scheduled snapshots (seconds)")
    SNAPSHOT_ENABLED: bool = Field(default=True, description="Enable/disable scheduled snapshot service")
    SNAPSHOT_MAX_TOKENS_PER_RUN: int = Field(default=100, description="Max tokens per scheduled batch")
    SNAPSHOT_RATE_LIMIT_DELAY: float = Field(default=1.0, description="Delay between token snapshots (seconds)")
    SNAPSHOT_RETRY_FAILED_AFTER: int = Field(default=24, description="Retry failed tokens after N hours")

    # ==============================================
    # TRADING APIS
    # ==============================================
    JUPITER_API_URL: str = "https://quote-api.jup.ag/v6"

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
    REPORT_TTL_SECONDS: int = 7200
    
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

    @validator('BASE_URL')
    def validate_base_url(cls, v):
        if not v:
            raise ValueError('BASE_URL is required and cannot be empty')
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('BASE_URL must start with http:// or https://')
        # Remove trailing slash for consistency
        return v.rstrip('/')

    @validator('CHROMA_DB_PATH', 'KNOWLEDGE_BASE_PATH', 'LOGS_DIR')
    def validate_paths(cls, v):
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path.absolute())

    @validator('SNAPSHOT_INTERVAL_SECONDS')
    def validate_snapshot_interval(cls, v):
        if v < 60:
            raise ValueError('SNAPSHOT_INTERVAL_SECONDS must be at least 60 seconds')
        return v

    @validator('SNAPSHOT_MAX_TOKENS_PER_RUN')
    def validate_snapshot_max_tokens(cls, v):
        if v < 1 or v > 1000:
            raise ValueError('SNAPSHOT_MAX_TOKENS_PER_RUN must be between 1 and 1000')
        return v

    @validator('SNAPSHOT_RATE_LIMIT_DELAY')
    def validate_snapshot_rate_limit(cls, v):
        if v < 0.1:
            raise ValueError('SNAPSHOT_RATE_LIMIT_DELAY must be at least 0.1 seconds')
        return v

    # ==============================================
    # CONFIGURATION READING
    # ==============================================
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "allow"
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

    def get_webhook_urls(self) -> dict[str, str]:
        """Get all webhook endpoint URLs"""
        return {
            "mint": f"{self.BASE_URL}/webhooks/helius/mint",
        }

    def get_snapshot_config(self) -> dict[str, any]:
        """Get snapshot service configuration"""
        return {
            "enabled": self.SNAPSHOT_ENABLED,
            "interval_seconds": self.SNAPSHOT_INTERVAL_SECONDS,
            "interval_hours": round(self.SNAPSHOT_INTERVAL_SECONDS / 3600, 2),
            "max_tokens_per_run": self.SNAPSHOT_MAX_TOKENS_PER_RUN,
            "rate_limit_delay": self.SNAPSHOT_RATE_LIMIT_DELAY,
            "retry_failed_after_hours": self.SNAPSHOT_RETRY_FAILED_AFTER,
            "estimated_run_time_minutes": round((self.SNAPSHOT_MAX_TOKENS_PER_RUN * self.SNAPSHOT_RATE_LIMIT_DELAY) / 60, 1)
        }

    def validate_critical_keys(self) -> list[str]:
        missing = []
        critical_keys = [
            ('BASE_URL', 'Base URL'),
            ('HELIUS_API_KEY', 'Helius API'),
            ('GROQ_API_KEY', 'Groq AI API')
        ]
        for key, name in critical_keys:
            if not getattr(self, key):
                missing.append(name)
        return missing

    def get_all_api_keys_status(self) -> dict:
        """Get status of all configured API keys"""
        keys_status = {}
        api_keys = [
            'HELIUS_API_KEY', 'BIRDEYE_API_KEY',
            'PUMPFUN_API_KEY', 'SOLSNIFFER_API_KEY',
            'GOPLUS_APP_KEY', 'GOPLUS_APP_SECRET',
            'WALLET_SECRET_KEY', 'INTERNAL_TOKEN', 'GROQ_API_KEY'
        ]
        
        for key in api_keys:
            value = getattr(self, key)
            keys_status[key] = {
                'configured': bool(value),
                'masked_value': f"{value[:8]}***" if value else None
            }
        
        # Add BASE_URL status
        keys_status['BASE_URL'] = {
            'configured': bool(self.BASE_URL),
            'value': self.BASE_URL  # Not sensitive, show full URL
        }
        
        return keys_status

@lru_cache()
def get_settings() -> Settings:
    return Settings()