import time
from typing import Any, Optional, Dict
from loguru import logger

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.debug("Redis not installed - using memory fallback")

from app.core.config import get_settings

settings = get_settings()


class RedisClient:
    """Redis client with fallback to memory storage"""
    
    def __init__(self):
        self._client = None
        self._memory_store = {}  # Fallback memory storage
        self._connected = False
    
    async def connect(self):
        """Initialize Redis connection"""
        if not REDIS_AVAILABLE:
            logger.info("Redis not available - using memory fallback")
            self._connected = True
            return
        
        try:
            self._client = redis.from_url(settings.REDIS_URL)
            await self._client.ping()
            self._connected = True
            logger.info("Redis connection established")
        except Exception as e:
            logger.debug(f"Redis connection failed: {str(e)} - using memory fallback")
            self._connected = True
    
    async def disconnect(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
        self._connected = False
    
    async def is_connected(self) -> bool:
        """Check if connected (including fallback)"""
        return self._connected
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        if self._client:
            try:
                return await self._client.get(key)
            except Exception:
                pass
        
        # Fallback to memory
        return self._memory_store.get(key)
    
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set value with optional expiration"""
        if self._client:
            try:
                return await self._client.set(key, value, ex=ex)
            except Exception:
                pass
        
        # Fallback to memory
        self._memory_store[key] = value
        return True
    
    async def delete(self, *keys: str) -> int:
        """Delete keys"""
        if self._client:
            try:
                return await self._client.delete(*keys)
            except Exception:
                pass
        
        # Fallback to memory
        count = 0
        for key in keys:
            if key in self._memory_store:
                del self._memory_store[key]
                count += 1
        return count


# Global Redis client instance
redis_client = RedisClient()


async def init_redis():
    """Initialize Redis connection"""
    await redis_client.connect()


async def close_redis():
    """Close Redis connection"""
    await redis_client.disconnect()


async def get_redis_client() -> RedisClient:
    """Get Redis client (dependency injection)"""
    if not await redis_client.is_connected():
        await redis_client.connect()
    return redis_client


async def check_redis_health() -> Dict[str, Any]:
    """Check Redis health"""
    try:
        client = await get_redis_client()
        
        # Test basic operations
        test_key = f"health_check_{int(time.time())}"
        test_value = "ok"
        
        await client.set(test_key, test_value, ex=60)
        retrieved = await client.get(test_key)
        await client.delete(test_key)
        
        return {
            "healthy": retrieved == test_value,
            "connected": await client.is_connected(),
            "version": "memory_fallback" if not REDIS_AVAILABLE else "redis",
            "backend": "memory" if not client._client else "redis"
        }
        
    except Exception as e:
        logger.warning(f"Redis health check failed: {str(e)}")
        return {
            "healthy": False,
            "connected": False,
            "error": str(e)
        }