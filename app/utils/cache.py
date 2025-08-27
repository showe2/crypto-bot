import json
import time
import hashlib
from typing import Any, Optional, Dict, Union, List, Callable
from datetime import datetime, timedelta
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class CacheManager:
    """Advanced cache manager with Redis backend and memory fallback"""
    
    def __init__(self):
        self._memory_cache = {}
        self._memory_expiry = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
        self.redis_client = None
        self.prefix = "cache:"

    async def get_redis_client(self):
        """Get Redis client with lazy initialization"""
        if self.redis_client is None:
            try:
                from app.utils.redis_client import get_redis_client
                self.redis_client = await get_redis_client()
            except Exception as e:
                logger.debug(f"Redis initialization failed: {str(e)}")
                self.redis_client = False
        return self.redis_client if self.redis_client != False else None
    
    def _make_key(self, key: str, namespace: str = "default") -> str:
        """Create a namespaced cache key"""
        return f"{namespace}:{key}"
    
    async def get(self, key: str, namespace: str = "default") -> Any:
        """Get value from cache with namespace support"""
        namespaced_key = self._make_key(key, namespace)
        # Clean expired keys
        self._clean_expired_memory_keys()
        
        # Try Redis first
        redis_client = await self.get_redis_client()
        if redis_client:
            try:
                data = await redis_client.get(namespaced_key)
                if data:
                    self._stats["hits"] += 1
                    return self._deserialize_value(data)
            except Exception as e:
                logger.debug(f"Redis cache GET error: {str(e)}")
                self._stats["errors"] += 1
        
        # Memory fallback
        if namespaced_key in self._memory_cache:
            if self._memory_expiry[namespaced_key] > time.time():
                self._stats["hits"] += 1
                return self._memory_cache[namespaced_key]
            else:
                # Clean up expired entry
                del self._memory_cache[namespaced_key]
                del self._memory_expiry[namespaced_key]
        
        self._stats["misses"] += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 7200, namespace: str = "default") -> bool:
        """Set cache value with namespace support"""
        try:
            namespaced_key = self._make_key(key, namespace)
            
            # Try Redis first
            client = await self.get_redis_client()
            if client:
                try:
                    serialized_value = self._serialize_value(value)
                    success = await client.set(namespaced_key, serialized_value, ex=ttl)
                    if success:
                        self._stats["sets"] += 1
                        return True
                except Exception as e:
                    logger.debug(f"Redis cache SET error: {str(e)}")
                    self._stats["errors"] += 1

            # Memory fallback
            self._memory_cache[namespaced_key] = value
            self._memory_expiry[namespaced_key] = time.time() + ttl
            self._stats["sets"] += 1
            return True
            
        except Exception as e:
            logger.debug(f"Cache SET error for key {key}: {str(e)}")
            self._stats["errors"] += 1
            return False
    
    def _clean_expired_memory_keys(self) -> None:
        """Remove expired keys from memory cache"""
        current_time = time.time()
        expired_keys = [
            k for k, exp in self._memory_expiry.items() 
            if exp <= current_time
        ]
        for k in expired_keys:
            self._memory_cache.pop(k, None)
            self._memory_expiry.pop(k, None)
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize value for storage"""
        return json.dumps(value)
    
    def _deserialize_value(self, value: str) -> Any:
        """Deserialize value from storage"""
        return json.loads(value)
    
    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete key from cache"""
        try:
            cache_key = self._make_key(key, namespace)
            deleted = False
            
            # Try Redis first
            client = await self.get_redis_client()
            if client and client != False:
                try:
                    count = await client.delete(cache_key)
                    if count > 0:
                        deleted = True
                except Exception as e:
                    logger.debug(f"Redis cache DELETE error: {str(e)}")
                    self._stats["errors"] += 1
            
            # Fallback to memory
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
                deleted = True
            self._memory_expiry.pop(cache_key, None)
            
            if deleted:
                self._stats["deletes"] += 1
            
            return deleted
            
        except Exception as e:
            logger.debug(f"Cache DELETE error for key {key}: {str(e)}")
            self._stats["errors"] += 1
            return False
    
    async def exists(self, key: str, namespace: str = "default") -> bool:
        """Check if key exists in cache"""
        try:
            cache_key = self._make_key(key, namespace)
            
            # Try Redis first
            client = await self.get_redis_client()
            if client and client != False:
                try:
                    exists = await client.exists(cache_key)
                    return exists > 0
                except Exception as e:
                    logger.debug(f"Redis cache EXISTS error: {str(e)}")
            
            # Fallback to memory
            self._clean_expired_memory_keys()
            return cache_key in self._memory_cache
            
        except Exception as e:
            logger.debug(f"Cache EXISTS error for key {key}: {str(e)}")
            return False
    
    async def expire(self, key: str, ttl: int, namespace: str = "default") -> bool:
        """Set expiration for existing key"""
        try:
            cache_key = self._make_key(key, namespace)
            
            # Try Redis first
            client = await self.get_redis_client()
            if client and client != False:
                try:
                    success = await client.expire(cache_key, ttl)
                    if success:
                        return True
                except Exception as e:
                    logger.debug(f"Redis cache EXPIRE error: {str(e)}")
            
            # Fallback to memory
            if cache_key in self._memory_cache:
                self._memory_expiry[cache_key] = time.time() + ttl
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Cache EXPIRE error for key {key}: {str(e)}")
            return False
    
    async def ttl(self, key: str, namespace: str = "default") -> int:
        """Get time to live for key"""
        try:
            cache_key = self._make_key(key, namespace)
            
            # Try Redis first
            client = await self.get_redis_client()
            if client and client != False:
                try:
                    ttl_value = await client.ttl(cache_key)
                    return ttl_value
                except Exception as e:
                    logger.debug(f"Redis cache TTL error: {str(e)}")
            
            # Fallback to memory
            if cache_key not in self._memory_cache:
                return -2  # Key doesn't exist
                
            if cache_key not in self._memory_expiry:
                return -1  # Key exists but no expiration
                
            remaining = self._memory_expiry[cache_key] - time.time()
            return max(0, int(remaining))
            
        except Exception as e:
            logger.debug(f"Cache TTL error for key {key}: {str(e)}")
            return -2
    
    async def increment(self, key: str, amount: int = 1, namespace: str = "default") -> int:
        """Increment a numeric value"""
        try:
            cache_key = self._make_key(key, namespace)
            
            # Try Redis first
            client = await self.get_redis_client()
            if client and client != False:
                try:
                    result = await client.incr(cache_key, amount)
                    return result
                except Exception as e:
                    logger.debug(f"Redis cache INCR error: {str(e)}")
            
            # Fallback to memory
            current_value = self._memory_cache.get(cache_key, 0)
            try:
                if isinstance(current_value, str):
                    current_value = int(current_value)
                elif not isinstance(current_value, int):
                    current_value = 0
                    
                new_value = current_value + amount
                self._memory_cache[cache_key] = new_value
                return new_value
            except (ValueError, TypeError):
                raise ValueError(f"Value at key '{key}' is not numeric")
            
        except Exception as e:
            logger.debug(f"Cache INCREMENT error for key {key}: {str(e)}")
            raise
    
    async def get_or_set(
        self, 
        key: str, 
        factory: Callable, 
        ttl: Optional[int] = None, 
        namespace: str = "default",
        force_refresh: bool = False
    ) -> Any:
        """Get value from cache or compute and cache it"""
        if not force_refresh:
            cached_value = await self.get(key, namespace)
            if cached_value is not None:
                return cached_value
        
        # Compute new value
        try:
            if asyncio.iscoroutinefunction(factory):
                new_value = await factory()
            else:
                new_value = factory()
            
            # Cache the new value
            await self.set(key, new_value, ttl, namespace)
            return new_value
            
        except Exception as e:
            logger.error(f"Cache factory function failed for key {key}: {str(e)}")
            raise
    
    async def get_many(self, keys: List[str], namespace: str = "default") -> Dict[str, Any]:
        """Get multiple values from cache"""
        results = {}
        
        for key in keys:
            value = await self.get(key, namespace)
            if value is not None:
                results[key] = value
        
        return results
    
    async def set_many(
        self, 
        mapping: Dict[str, Any], 
        ttl: Optional[int] = None, 
        namespace: str = "default"
    ) -> Dict[str, bool]:
        """Set multiple values in cache"""
        results = {}
        
        for key, value in mapping.items():
            success = await self.set(key, value, ttl, namespace)
            results[key] = success
        
        return results
    
    async def delete_many(self, keys: List[str], namespace: str = "default") -> Dict[str, bool]:
        """Delete multiple keys from cache"""
        results = {}
        
        for key in keys:
            success = await self.delete(key, namespace)
            results[key] = success
        
        return results
    
    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace"""
        try:
            pattern = f"{self.prefix}{namespace}:*"
            deleted_count = 0
            
            # Try Redis first
            client = await self.get_redis_client()
            if client and client != False and hasattr(client, 'client') and client.client:
                try:
                    # Get all keys matching pattern
                    keys = await client.client.keys(pattern)
                    if keys:
                        deleted_count = await client.delete(*keys)
                except Exception as e:
                    logger.debug(f"Redis cache CLEAR error: {str(e)}")
            
            # Clear from memory
            memory_keys_to_delete = [
                key for key in self._memory_cache.keys()
                if key.startswith(f"{self.prefix}{namespace}:")
            ]
            
            for key in memory_keys_to_delete:
                del self._memory_cache[key]
                self._memory_expiry.pop(key, None)
                deleted_count += 1
            
            logger.info(f"Cleared {deleted_count} keys from namespace '{namespace}'")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cache CLEAR error for namespace {namespace}: {str(e)}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            total_operations = sum(self._stats.values())
            hit_rate = (self._stats["hits"] / (self._stats["hits"] + self._stats["misses"]) * 100) if (self._stats["hits"] + self._stats["misses"]) > 0 else 0
            
            stats = {
                "operations": self._stats.copy(),
                "hit_rate": round(hit_rate, 2),
                "total_operations": total_operations,
                "memory_keys": len(self._memory_cache),
                "memory_expired_keys": len(self._memory_expiry),
                "backend": "memory" if not self.redis_client or self.redis_client == False else "redis"
            }
            
            # Get Redis stats if available
            if self.redis_client and self.redis_client != False:
                try:
                    redis_stats = await self.redis_client.get_stats()
                    stats.update({
                        "redis_version": redis_stats.get("redis_version"),
                        "redis_memory": redis_stats.get("used_memory"),
                        "redis_hit_rate": redis_stats.get("hit_rate"),
                        "redis_connected": redis_stats.get("connected")
                    })
                except Exception as e:
                    stats["redis_error"] = str(e)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {"error": str(e)}
    
    def reset_stats(self):
        """Reset cache statistics"""
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform cache health check"""
        try:
            # Test basic operations
            test_key = f"health_check_{int(time.time())}"
            test_value = {"timestamp": datetime.utcnow().isoformat(), "test": True}
            
            # Test set
            set_success = await self.set(test_key, test_value, 60, "health")
            
            # Test get
            retrieved = await self.get(test_key, "health")
            get_success = retrieved == test_value
            
            # Test delete
            delete_success = await self.delete(test_key, "health")
            
            # Test exists (should be False after delete)
            exists_success = not await self.exists(test_key, "health")
            
            all_operations_successful = all([set_success, get_success, delete_success, exists_success])
            
            return {
                "healthy": all_operations_successful,
                "operations": {
                    "set": set_success,
                    "get": get_success,
                    "delete": delete_success,
                    "exists": exists_success
                },
                "backend": "memory" if not self.redis_client or self.redis_client == False else "redis",
                "stats": await self.get_stats()
            }
            
        except Exception as e:
            logger.warning(f"Cache health check failed: {str(e)}")
            return {
                "healthy": False,
                "error": str(e)
            }


# Global cache manager instance
cache_manager = CacheManager()


# Convenience functions for common cache operations
async def get_cache_health() -> Dict[str, Any]:
    """Get cache health status"""
    return await cache_manager.health_check()


# Decorators for caching
def cache_result(
    ttl: int = None, 
    namespace: str = "function_cache",
    key_prefix: str = None
):
    """Decorator to cache function results"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix or func.__name__]
            
            # Add args to key
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    key_parts.append(str(arg))
                else:
                    key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
            
            # Add kwargs to key
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (str, int, float, bool)):
                    key_parts.append(f"{k}:{v}")
                else:
                    key_parts.append(f"{k}:{hashlib.md5(str(v).encode()).hexdigest()[:8]}")
            
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key, namespace)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl, namespace)
            return result
        
        def sync_wrapper(*args, **kwargs):
            import asyncio
            
            # Generate cache key (same logic as async)
            key_parts = [key_prefix or func.__name__]
            
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    key_parts.append(str(arg))
                else:
                    key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
            
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (str, int, float, bool)):
                    key_parts.append(f"{k}:{v}")
                else:
                    key_parts.append(f"{k}:{hashlib.md5(str(v).encode()).hexdigest()[:8]}")
            
            cache_key = ":".join(key_parts)
            
            # Get event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Try to get from cache
            cached_result = loop.run_until_complete(cache_manager.get(cache_key, namespace))
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            loop.run_until_complete(cache_manager.set(cache_key, result, ttl, namespace))
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Import asyncio for async detection
import asyncio