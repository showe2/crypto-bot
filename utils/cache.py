import json
import pickle
import hashlib
from typing import Any, Optional, Dict, Union, Callable, TypeVar, Awaitable
from datetime import datetime, timedelta
from functools import wraps
from loguru import logger

from app.core.config import get_settings
from app.utils.redis_client import get_redis_client, RedisClient

settings = get_settings()

# Type hints for decorators
F = TypeVar('F', bound=Callable[..., Awaitable[Any]])


class CacheManager:
    """Advanced caching manager with Redis backend"""
    
    def __init__(self):
        self.redis_client: Optional[RedisClient] = None
        self.default_ttl = settings.CACHE_TTL_MEDIUM
        self.prefix = "solana_ai_cache:"
    
    async def get_client(self) -> RedisClient:
        """Get Redis client with lazy initialization"""
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client
    
    def _make_key(self, key: str, namespace: str = "default") -> str:
        """Create cache key with prefix and namespace"""
        return f"{self.prefix}{namespace}:{key}"
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize value for storage"""
        if isinstance(value, (str, int, float, bool)):
            return json.dumps({"type": "json", "value": value})
        else:
            # Use pickle for complex objects
            pickled = pickle.dumps(value)
            return json.dumps({
                "type": "pickle",
                "value": pickled.hex()
            })
    
    def _deserialize_value(self, data: str) -> Any:
        """Deserialize value from storage"""
        try:
            parsed = json.loads(data)
            if parsed["type"] == "json":
                return parsed["value"]
            elif parsed["type"] == "pickle":
                pickled_bytes = bytes.fromhex(parsed["value"])
                return pickle.loads(pickled_bytes)
        except Exception as e:
            logger.warning(f"Cache deserialization error: {str(e)}")
            return None
    
    async def get(
        self,
        key: str,
        namespace: str = "default",
        default: Any = None
    ) -> Any:
        """Get value from cache"""
        try:
            client = await self.get_client()
            cache_key = self._make_key(key, namespace)
            
            data = await client.get(cache_key)
            if data is None:
                return default
            
            return self._deserialize_value(data)
            
        except Exception as e:
            logger.warning(f"Cache GET error for key {key}: {str(e)}")
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = "default"
    ) -> bool:
        """Set value in cache with TTL"""
        try:
            client = await self.get_client()
            cache_key = self._make_key(key, namespace)
            
            serialized_value = self._serialize_value(value)
            ttl = ttl or self.default_ttl
            
            return await client.set(cache_key, serialized_value, ex=ttl)
            
        except Exception as e:
            logger.warning(f"Cache SET error for key {key}: {str(e)}")
            return False
    
    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete key from cache"""
        try:
            client = await self.get_client()
            cache_key = self._make_key(key, namespace)
            
            result = await client.delete(cache_key)
            return result > 0
            
        except Exception as e:
            logger.warning(f"Cache DELETE error for key {key}: {str(e)}")
            return False
    
    async def exists(self, key: str, namespace: str = "default") -> bool:
        """Check if key exists in cache"""
        try:
            client = await self.get_client()
            cache_key = self._make_key(key, namespace)
            
            result = await client.exists(cache_key)
            return result > 0
            
        except Exception as e:
            logger.warning(f"Cache EXISTS error for key {key}: {str(e)}")
            return False
    
    async def expire(self, key: str, ttl: int, namespace: str = "default") -> bool:
        """Set expiration for existing key"""
        try:
            client = await self.get_client()
            cache_key = self._make_key(key, namespace)
            
            return await client.expire(cache_key, ttl)
            
        except Exception as e:
            logger.warning(f"Cache EXPIRE error for key {key}: {str(e)}")
            return False
    
    async def ttl(self, key: str, namespace: str = "default") -> int:
        """Get TTL for key"""
        try:
            client = await self.get_client()
            cache_key = self._make_key(key, namespace)
            
            return await client.ttl(cache_key)
            
        except Exception as e:
            logger.warning(f"Cache TTL error for key {key}: {str(e)}")
            return -1
    
    # Hash operations for structured data
    async def hset(
        self,
        name: str,
        field: str,
        value: Any,
        namespace: str = "default"
    ) -> bool:
        """Set hash field"""
        try:
            client = await self.get_client()
            hash_key = self._make_key(name, namespace)
            
            serialized_value = self._serialize_value(value)
            return await client.hset(hash_key, field, serialized_value)
            
        except Exception as e:
            logger.warning(f"Cache HSET error for hash {name}, field {field}: {str(e)}")
            return False
    
    async def hget(
        self,
        name: str,
        field: str,
        namespace: str = "default",
        default: Any = None
    ) -> Any:
        """Get hash field"""
        try:
            client = await self.get_client()
            hash_key = self._make_key(name, namespace)
            
            data = await client.hget(hash_key, field)
            if data is None:
                return default
            
            return self._deserialize_value(data)
            
        except Exception as e:
            logger.warning(f"Cache HGET error for hash {name}, field {field}: {str(e)}")
            return default
    
    async def hgetall(self, name: str, namespace: str = "default") -> Dict[str, Any]:
        """Get all hash fields"""
        try:
            client = await self.get_client()
            hash_key = self._make_key(name, namespace)
            
            data = await client.hgetall(hash_key)
            if not data:
                return {}
            
            result = {}
            for field, value in data.items():
                result[field] = self._deserialize_value(value)
            
            return result
            
        except Exception as e:
            logger.warning(f"Cache HGETALL error for hash {name}: {str(e)}")
            return {}
    
    # List operations for queues and logs
    async def lpush(self, name: str, value: Any, namespace: str = "default") -> int:
        """Push to list from left"""
        try:
            client = await self.get_client()
            list_key = self._make_key(name, namespace)
            
            serialized_value = self._serialize_value(value)
            return await client.lpush(list_key, serialized_value)
            
        except Exception as e:
            logger.warning(f"Cache LPUSH error for list {name}: {str(e)}")
            return 0
    
    async def rpop(self, name: str, namespace: str = "default") -> Any:
        """Pop from list from right"""
        try:
            client = await self.get_client()
            list_key = self._make_key(name, namespace)
            
            data = await client.rpop(list_key)
            if data is None:
                return None
            
            return self._deserialize_value(data)
            
        except Exception as e:
            logger.warning(f"Cache RPOP error for list {name}: {str(e)}")
            return None
    
    async def llen(self, name: str, namespace: str = "default") -> int:
        """Get list length"""
        try:
            client = await self.get_client()
            list_key = self._make_key(name, namespace)
            
            return await client.llen(list_key)
            
        except Exception as e:
            logger.warning(f"Cache LLEN error for list {name}: {str(e)}")
            return 0
    
    # Pattern operations
    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in namespace"""
        try:
            client = await self.get_client()
            pattern = f"{self.prefix}{namespace}:*"
            
            # Get all keys matching pattern
            keys = []
            async for key in client.client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await client.delete(*keys)
            
            return 0
            
        except Exception as e:
            logger.warning(f"Cache clear namespace error for {namespace}: {str(e)}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            client = await self.get_client()
            info = await client.client.info()
            
            return {
                "redis_version": info.get("redis_version", "unknown"),
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": (
                    info.get("keyspace_hits", 0) / 
                    max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1)
                ) * 100
            }
            
        except Exception as e:
            logger.warning(f"Cache stats error: {str(e)}")
            return {"error": str(e)}


# Global cache manager instance
cache_manager = CacheManager()


def cache_key_from_args(*args, **kwargs) -> str:
    """Generate cache key from function arguments"""
    # Create a hash from arguments
    key_data = {
        'args': args,
        'kwargs': kwargs
    }
    key_json = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_json.encode()).hexdigest()


def cached(
    ttl: Optional[int] = None,
    namespace: str = "functions",
    key_func: Optional[Callable] = None
):
    """Decorator for caching function results"""
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                func_name = f"{func.__module__}.{func.__name__}"
                args_key = cache_key_from_args(*args, **kwargs)
                cache_key = f"{func_name}:{args_key}"
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key, namespace)
            if cached_result is not None:
                logger.debug(f"Cache HIT for {cache_key}")
                return cached_result
            
            # Execute function and cache result
            logger.debug(f"Cache MISS for {cache_key}")
            result = await func(*args, **kwargs)
            
            # Cache the result
            cache_ttl = ttl or settings.CACHE_TTL_MEDIUM
            await cache_manager.set(cache_key, result, cache_ttl, namespace)
            
            return result
        
        return wrapper
    return decorator


# Specialized cache decorators for different TTL periods
def cache_short(namespace: str = "functions"):
    """Cache with short TTL (5 minutes)"""
    return cached(ttl=settings.CACHE_TTL_SHORT, namespace=namespace)


def cache_medium(namespace: str = "functions"):
    """Cache with medium TTL (30 minutes)"""
    return cached(ttl=settings.CACHE_TTL_MEDIUM, namespace=namespace)


def cache_long(namespace: str = "functions"):
    """Cache with long TTL (2 hours)"""
    return cached(ttl=settings.CACHE_TTL_LONG, namespace=namespace)


# Cache utilities for different data types
class TokenCache:
    """Specialized cache for token data"""
    
    def __init__(self):
        self.namespace = "tokens"
    
    async def get_token_metadata(self, mint: str) -> Optional[Dict[str, Any]]:
        """Get cached token metadata"""
        return await cache_manager.hget(f"metadata", mint, self.namespace)
    
    async def set_token_metadata(self, mint: str, metadata: Dict[str, Any], ttl: int = None) -> bool:
        """Cache token metadata"""
        success = await cache_manager.hset(f"metadata", mint, metadata, self.namespace)
        if success and ttl:
            await cache_manager.expire(f"metadata", ttl, self.namespace)
        return success
    
    async def get_price_data(self, mint: str) -> Optional[Dict[str, Any]]:
        """Get cached price data"""
        return await cache_manager.get(f"price:{mint}", self.namespace)
    
    async def set_price_data(self, mint: str, price_data: Dict[str, Any]) -> bool:
        """Cache price data with short TTL"""
        return await cache_manager.set(
            f"price:{mint}", 
            price_data, 
            settings.CACHE_TTL_SHORT,  # Price data expires quickly
            self.namespace
        )
    
    async def get_analysis_result(self, mint: str, analysis_type: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis result"""
        return await cache_manager.get(f"analysis:{analysis_type}:{mint}", self.namespace)
    
    async def set_analysis_result(
        self, 
        mint: str, 
        analysis_type: str, 
        result: Dict[str, Any],
        ttl: int = None
    ) -> bool:
        """Cache analysis result"""
        cache_ttl = ttl or settings.CACHE_TTL_LONG  # Analysis results live longer
        return await cache_manager.set(
            f"analysis:{analysis_type}:{mint}",
            result,
            cache_ttl,
            self.namespace
        )


# Global token cache instance
token_cache = TokenCache()


class SocialCache:
    """Specialized cache for social media data"""
    
    def __init__(self):
        self.namespace = "social"
    
    async def get_social_data(self, token_symbol: str, platform: str) -> Optional[Dict[str, Any]]:
        """Get cached social data"""
        return await cache_manager.get(f"{platform}:{token_symbol}", self.namespace)
    
    async def set_social_data(
        self, 
        token_symbol: str, 
        platform: str, 
        data: Dict[str, Any]
    ) -> bool:
        """Cache social data"""
        return await cache_manager.set(
            f"{platform}:{token_symbol}",
            data,
            settings.CACHE_TTL_MEDIUM,  # Social data moderate TTL
            self.namespace
        )
    
    async def add_social_mention(self, token_symbol: str, mention: Dict[str, Any]) -> int:
        """Add social mention to list"""
        return await cache_manager.lpush(f"mentions:{token_symbol}", mention, self.namespace)
    
    async def get_recent_mentions(self, token_symbol: str, limit: int = 100) -> list:
        """Get recent social mentions"""
        mentions = []
        for i in range(min(limit, await cache_manager.llen(f"mentions:{token_symbol}", self.namespace))):
            mention = await cache_manager.rpop(f"mentions:{token_symbol}", self.namespace)
            if mention:
                mentions.append(mention)
        return mentions


# Global social cache instance
social_cache = SocialCache()


async def warm_up_cache():
    """Warm up cache with essential data"""
    logger.info("Warming up cache...")
    try:
        # Test cache connectivity
        test_key = "warmup_test"
        await cache_manager.set(test_key, {"status": "ok", "timestamp": datetime.utcnow()}, 60)
        result = await cache_manager.get(test_key)
        
        if result:
            logger.info("Cache warmup successful")
            await cache_manager.delete(test_key)
        else:
            logger.warning("Cache warmup failed - data not retrieved")
            
    except Exception as e:
        logger.error(f"Cache warmup error: {str(e)}")


async def cleanup_cache():
    """Clean up expired and old cache entries"""
    logger.info("Starting cache cleanup...")
    try:
        # Get cache stats before cleanup
        stats_before = await cache_manager.get_stats()
        
        # Clear old analysis results (older than 24 hours)
        old_analysis_cleared = await cache_manager.clear_namespace("tokens")
        
        # Clear old social data (older than 12 hours)
        old_social_cleared = await cache_manager.clear_namespace("social")
        
        stats_after = await cache_manager.get_stats()
        
        logger.info(f"Cache cleanup completed: cleared {old_analysis_cleared + old_social_cleared} entries")
        
    except Exception as e:
        logger.error(f"Cache cleanup error: {str(e)}")


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
        
        # Get stats
        stats = await cache_manager.get_stats()
        
        return {
            "healthy": retrieved is not None,
            "operations_working": retrieved == test_value,
            "statistics": stats
        }
        
    except Exception as e:
        logger.warning(f"Cache health check failed: {str(e)}")
        return {
            "healthy": False,
            "error": str(e)
        }