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

    # GOplus API - Simplified to single APP Key + APP Secret pair
    GOPLUS_APP_KEY: Optional[str] = None
    GOPLUS_APP_SECRET: Optional[str] = None
    GOPLUS_BASE_URL: str = "https://api.gopluslabs.io"

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
            'PUMPFUN_API_KEY', 'RUGCHECK_API_KEY',
            # Simplified GOplus keys
            'GOPLUS_APP_KEY', 'GOPLUS_APP_SECRET'
        ]
        
        for key in api_keys:
            value = getattr(self, key)
            keys_status[key] = {
                'configured': bool(value),
                'masked_value': f"{value[:8]}***" if value else None
            }
        return keys_status

    def get_goplus_keys_status(self) -> dict:
        """Get GOplus API keys status (simplified)"""
        app_key = self.GOPLUS_APP_KEY
        app_secret = self.GOPLUS_APP_SECRET
        
        both_configured = bool(app_key and app_secret)
        
        return {
            'app_key_present': bool(app_key),
            'app_secret_present': bool(app_secret),
            'both_configured': both_configured,
            'masked_app_key': f"{app_key[:8]}***" if app_key else None,
            'base_url': self.GOPLUS_BASE_URL,
            'authentication_method': 'Bearer token (from APP_KEY + APP_SECRET)',
            'services_available': [
                'token_security',
                'rugpull_detection', 
                'supported_chains'
            ] if both_configured else []
        }

    def get_api_services_summary(self) -> dict:
        """Get summary of all API services including GOplus"""
        all_keys = self.get_all_api_keys_status()
        goplus_status = self.get_goplus_keys_status()
        
        # Count configured keys
        standard_keys = [k for k in all_keys.keys() if not k.startswith('GOPLUS_')]
        configured_standard = sum(1 for k in standard_keys if all_keys[k]['configured'])
        
        # GOplus counts as 1 service with 2 required keys
        goplus_configured = 1 if goplus_status['both_configured'] else 0
        
        total_services = len(standard_keys) + 1  # +1 for GOplus
        total_configured = configured_standard + goplus_configured
        
        return {
            'total_services': total_services,
            'configured_services': total_configured,
            'configuration_percentage': round((total_configured / total_services) * 100, 1),
            'standard_apis': {
                'total': len(standard_keys),
                'configured': configured_standard
            },
            'goplus_api': {
                'configured': goplus_configured == 1,
                'services_available': len(goplus_status['services_available'])
            },
            'missing_services': [
                k.replace('_API_KEY', '').lower() 
                for k in standard_keys 
                if not all_keys[k]['configured']
            ] + (['goplus'] if not goplus_status['both_configured'] else [])
        }

    def get_service_endpoints_config(self) -> dict:
        """Get configuration for all service endpoints"""
        return {
            'blockchain_services': {
                'helius': {
                    'base_url': self.HELIUS_RPC_URL,
                    'configured': bool(self.HELIUS_API_KEY),
                    'type': 'RPC + API'
                },
                'chainbase': {
                    'base_url': self.CHAINBASE_BASE_URL,
                    'configured': bool(self.CHAINBASE_API_KEY),
                    'type': 'Analytics API'
                },
                'birdeye': {
                    'base_url': self.BIRDEYE_BASE_URL,
                    'configured': bool(self.BIRDEYE_API_KEY),
                    'type': 'Price API'
                },
                'solscan': {
                    'base_url': self.SOLSCAN_BASE_URL,
                    'configured': bool(self.SOLSCAN_API_KEY),
                    'type': 'On-chain API'
                }
            },
            'security_services': {
                'blowfish': {
                    'base_url': self.BLOWFISH_BASE_URL,
                    'configured': bool(self.BLOWFISH_API_KEY),
                    'type': 'Security Analysis'
                },
                'goplus': {
                    'base_url': self.GOPLUS_BASE_URL,
                    'configured': bool(self.GOPLUS_APP_KEY and self.GOPLUS_APP_SECRET),
                    'type': 'Security + Rugpull Detection',
                    'authentication': 'Bearer Token',
                    'services': ['token_security', 'rugpull_detection']
                }
            },
            'social_services': {
                'dataimpulse': {
                    'base_url': self.DATAIMPULSE_BASE_URL,
                    'configured': bool(self.DATAIMPULSE_API_KEY),
                    'type': 'Social Sentiment'
                }
            },
            'ai_services': {
                'mistral': {
                    'base_url': self.MISTRAL_API_URL,
                    'configured': bool(self.MISTRAL_API_KEY),
                    'model': self.MISTRAL_MODEL
                },
                'llama': {
                    'base_url': self.LLAMA_API_URL,
                    'configured': bool(self.LLAMA_API_KEY),
                    'model': self.LLAMA_MODEL
                }
            },
            'free_services': {
                'dexscreener': {
                    'base_url': self.DEXSCREENER_BASE_URL,
                    'configured': True,  # No API key required
                    'type': 'Free DEX Data'
                },
                'jupiter': {
                    'base_url': self.JUPITER_API_URL,
                    'configured': True,  # No API key required
                    'type': 'DEX Aggregator'
                }
            }
        }

    def get_goplus_configuration_guide(self) -> dict:
        """Get configuration guide for GOplus"""
        current_status = self.get_goplus_keys_status()
        
        guide = {
            'current_status': current_status,
            'required_env_vars': {
                'GOPLUS_APP_KEY': {
                    'description': 'Your GOplus application key',
                    'example': 'your_app_key_here',
                    'required': True,
                    'configured': current_status['app_key_present']
                },
                'GOPLUS_APP_SECRET': {
                    'description': 'Your GOplus application secret',
                    'example': 'your_app_secret_here',
                    'required': True,
                    'configured': current_status['app_secret_present']
                },
                'GOPLUS_BASE_URL': {
                    'description': 'GOplus API base URL',
                    'example': 'https://api.gopluslabs.io',
                    'required': False,
                    'configured': True,
                    'current_value': self.GOPLUS_BASE_URL
                }
            },
            'setup_steps': [
                '1. Visit https://gopluslabs.io/',
                '2. Create an account or log in',
                '3. Navigate to API section',
                '4. Generate APP_KEY and APP_SECRET',
                '5. Add to your .env file:',
                '   GOPLUS_APP_KEY=your_app_key_here',
                '   GOPLUS_APP_SECRET=your_app_secret_here',
                '6. Restart your application'
            ],
            'available_endpoints': [
                '/api/v1/token_security/{chain_id} - Token security analysis',
                '/api/v1/rugpull_detecting/{chain_id} - Rugpull detection',
                '/api/v1/supported_chains - Get supported blockchains'
            ],
            'supported_chains': [
                {'name': 'Ethereum', 'chain_id': '1'},
                {'name': 'BSC', 'chain_id': '56'},
                {'name': 'Polygon', 'chain_id': '137'},
                {'name': 'Solana', 'chain_id': '101'}
            ],
            'authentication_flow': [
                '1. POST /api/v1/token with APP_KEY + APP_SECRET',
                '2. Receive bearer token',
                '3. Use token in Authorization header for all requests',
                '4. Token auto-refreshes when expired'
            ]
        }
        
        return guide

    def validate_goplus_configuration(self) -> dict:
        """Validate GOplus configuration"""
        validation_result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'recommendations': []
        }
        
        # Check required fields
        if not self.GOPLUS_APP_KEY:
            validation_result['errors'].append('GOPLUS_APP_KEY is required')
        elif len(self.GOPLUS_APP_KEY) < 8:
            validation_result['warnings'].append('GOPLUS_APP_KEY seems too short')
        
        if not self.GOPLUS_APP_SECRET:
            validation_result['errors'].append('GOPLUS_APP_SECRET is required')
        elif len(self.GOPLUS_APP_SECRET) < 16:
            validation_result['warnings'].append('GOPLUS_APP_SECRET seems too short')
        
        # Check base URL
        if not self.GOPLUS_BASE_URL.startswith('https://'):
            validation_result['warnings'].append('GOPLUS_BASE_URL should use HTTPS')
        
        if not self.GOPLUS_BASE_URL.endswith('gopluslabs.io'):
            validation_result['warnings'].append('GOPLUS_BASE_URL should point to gopluslabs.io')
        
        # Overall validation
        validation_result['valid'] = len(validation_result['errors']) == 0
        
        if validation_result['valid']:
            validation_result['recommendations'].append('Configuration looks good!')
            validation_result['recommendations'].append('Test with: python tests/services/goplus_simple_test.py')
        else:
            validation_result['recommendations'].append('Fix configuration errors first')
            validation_result['recommendations'].append('Get API keys from https://gopluslabs.io/')
        
        return validation_result


@lru_cache()
def get_settings() -> Settings:
    return Settings()