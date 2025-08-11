import json
import time
from typing import Any, Optional, Dict
from datetime import datetime
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class CacheManager:
    """Simple cache manager with memory fallback"""
    
    def __init__(self):
        self.redis_client = None
        self._memory_cache = {}
        self.default_ttl = settings.CACHE_TTL_MEDIUM
        self.prefix = "solana_ai_cache:"
    
    async def get_client(self):
        """Get Redis client with lazy initialization"""
        if self.redis_client is None:
            try:
                from app.utils.redis_client import get_redis_client
                self.redis_client = await get_redis_client()
            except Exception as e:
                logger.debug(f"Redis not available for cache: {str(e)}")
                self.redis_client = False  # Mark as unavailable
        return self.redis_client
    
    def _make_key(self, key: str, namespace: str = "default") -> str:
        """Create cache key with prefix and namespace"""
        return f"{self.prefix}{namespace}:{key}"
    
    async def get(self, key: str, namespace: str = "default", default: Any = None) -> Any:
        """Get value from cache"""
        try:
            cache_key = self._make_key(key, namespace)
            
            # Try Redis first
            client = await self.get_client()
            if client and client != False:
                try:
                    data = await client.get(cache_key)
                    if data is not None:
                        return json.loads(data)
                except Exception:
                    pass
            
            # Fallback to memory
            if cache_key in self._memory_cache:
                entry = self._memory_cache[cache_key]
                if entry['expires'] > time.time():
                    return entry['value']
                else:
                    del self._memory_cache[cache_key]
            
            return default
            
        except Exception as e:
            logger.debug(f"Cache GET error for key {key}: {str(e)}")
            return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, namespace: str = "default") -> bool:
        """Set value in cache with TTL"""
        try:
            cache_key = self._make_key(key, namespace)
            cache_ttl = ttl or self.default_ttl
            
            # Try Redis first
            client = await self.get_client()
            if client and client != False:
                try:
                    serialized_value = json.dumps(value, default=str)
                    success = await client.set(cache_key, serialized_value, ex=cache_ttl)
                    if success:
                        return True
                except Exception:
                    pass
            
            # Fallback to memory
            self._memory_cache[cache_key] = {
                'value': value,
                'expires': time.time() + cache_ttl
            }
            return True
            
        except Exception as e:
            logger.debug(f"Cache SET error for key {key}: {str(e)}")
            return False
    
    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete key from cache"""
        try:
            cache_key = self._make_key(key, namespace)
            
            # Try Redis first
            client = await self.get_client()
            if client and client != False:
                try:
                    await client.delete(cache_key)
                except Exception:
                    pass
            
            # Fallback to memory
            self._memory_cache.pop(cache_key, None)
            return True
            
        except Exception as e:
            logger.debug(f"Cache DELETE error for key {key}: {str(e)}")
            return False


# Global cache manager instance
cache_manager = CacheManager()


async def get_cache_health() -> Dict[str, Any]:
    """Get cache health status"""
    try:
        # Test basic operations
        test_key = "health_check"
        test_value = {"timestamp": datetime.utcnow().isoformat()}
        
        # Test set/get
        await cache_manager.set(test_key, test_value, 60)
        retrieved = await cache_manager.get(test_key)
        await cache_manager.delete(test_key)
        
        return {
            "healthy": retrieved is not None,
            "operations_working": retrieved == test_value,
            "backend": "redis" if cache_manager.redis_client and cache_manager.redis_client != False else "memory"
        }
        
    except Exception as e:
        logger.warning(f"Cache health check failed: {str(e)}")
        return {
            "healthy": False,
            "error": str(e)
        }