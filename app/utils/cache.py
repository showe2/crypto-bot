import json
import time
import hashlib
import asyncio
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
    
    async def get(self, key: str) -> Any:
        """Get value from cache"""
        # Clean expired keys
        self._clean_expired_memory_keys()
        
        # Try Redis first
        redis_client = await self.get_redis_client()
        if redis_client:
            try:
                data = await redis_client.get(key)
                if data:
                    self._stats["hits"] += 1
                    # Handle empty or non-JSON data
                    if isinstance(data, str) and data.strip():
                        try:
                            return self._deserialize_value(data)
                        except json.JSONDecodeError:
                            # If it's not JSON, return as string
                            return data
                    elif data:
                        return data
            except Exception as e:
                logger.debug(f"Redis cache GET error: {str(e)}")
                self._stats["errors"] += 1
        
        # Memory fallback
        if key in self._memory_cache:
            if self._memory_expiry.get(key, 0) > time.time():
                self._stats["hits"] += 1
                return self._memory_cache[key]
            else:
                # Clean up expired entry
                self._memory_cache.pop(key, None)
                self._memory_expiry.pop(key, None)
        
        self._stats["misses"] += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 7200) -> bool:
        """Set cache value"""
        try:
            redis_success = False
            
            # Try Redis first
            client = await self.get_redis_client()
            if client:
                try:
                    serialized_value = self._serialize_value(value)
                    success = await client.set(key, serialized_value, ex=ttl)
                    if success:
                        redis_success = True
                except Exception as e:
                    logger.debug(f"Redis cache SET error: {str(e)}")
                    self._stats["errors"] += 1

            # ALWAYS store in memory as backup
            self._memory_cache[key] = value
            self._memory_expiry[key] = time.time() + ttl
            
            self._stats["sets"] += 1
            return True  # Return True if either Redis OR memory succeeded
            
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
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            deleted = False
            
            # Try Redis first
            client = await self.get_redis_client()
            if client and client != False:
                try:
                    count = await client.delete(key)
                    if count > 0:
                        deleted = True
                    else:
                        logger.debug(f"Redis DELETE: key {key} not found")
                except Exception as e:
                    logger.debug(f"Redis cache DELETE error: {str(e)}")
                    self._stats["errors"] += 1
            
            # Fallback to memory
            if key in self._memory_cache:
                self._memory_cache.pop(key, None)
                deleted = True
            self._memory_expiry.pop(key, None)
            
            if deleted:
                self._stats["deletes"] += 1
            
            logger.debug(f"DELETE operation result for {key}: {deleted}")
            return deleted
            
        except Exception as e:
            logger.debug(f"Cache DELETE error for key {key}: {str(e)}")
            self._stats["errors"] += 1
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            # Try Redis first
            client = await self.get_redis_client()
            if client and client != False:
                try:
                    exists = await client.exists(key)
                    return exists > 0
                except Exception as e:
                    logger.debug(f"Redis cache EXISTS error: {str(e)}")
            
            # Fallback to memory
            self._clean_expired_memory_keys()
            return key in self._memory_cache
            
        except Exception as e:
            logger.debug(f"Cache EXISTS error for key {key}: {str(e)}")
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for existing key"""
        try:
            # Try Redis first
            client = await self.get_redis_client()
            if client and client != False:
                try:
                    success = await client.expire(key, ttl)
                    if success:
                        return True
                except Exception as e:
                    logger.debug(f"Redis cache EXPIRE error: {str(e)}")
            
            # Fallback to memory
            if key in self._memory_cache:
                self._memory_expiry[key] = time.time() + ttl
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Cache EXPIRE error for key {key}: {str(e)}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get time to live for key"""
        try:
            # Try Redis first
            client = await self.get_redis_client()
            if client and client != False:
                try:
                    ttl_value = await client.ttl(key)
                    return ttl_value
                except Exception as e:
                    logger.debug(f"Redis cache TTL error: {str(e)}")
            
            # Fallback to memory
            if key not in self._memory_cache:
                return -2  # Key doesn't exist
                
            if key not in self._memory_expiry:
                return -1  # Key exists but no expiration
                
            remaining = self._memory_expiry[key] - time.time()
            return max(0, int(remaining))
            
        except Exception as e:
            logger.debug(f"Cache TTL error for key {key}: {str(e)}")
            return -2
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a numeric value"""
        try:
            # Try Redis first
            client = await self.get_redis_client()
            if client and client != False:
                try:
                    result = await client.incr(key, amount)
                    return result
                except Exception as e:
                    logger.debug(f"Redis cache INCR error: {str(e)}")
            
            # Fallback to memory
            current_value = self._memory_cache.get(key, 0)
            try:
                if isinstance(current_value, str):
                    current_value = int(current_value)
                elif not isinstance(current_value, int):
                    current_value = 0
                    
                new_value = current_value + amount
                self._memory_cache[key] = new_value
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
        force_refresh: bool = False
    ) -> Any:
        """Get value from cache or compute and cache it"""
        if not force_refresh:
            cached_value = await self.get(key)
            if cached_value is not None:
                return cached_value
        
        # Compute new value
        try:
            if asyncio.iscoroutinefunction(factory):
                new_value = await factory()
            else:
                new_value = factory()
            
            # Cache the new value
            await self.set(key, new_value, ttl)
            return new_value
            
        except Exception as e:
            logger.error(f"Cache factory function failed for key {key}: {str(e)}")
            raise
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache"""
        results = {}
        
        for key in keys:
            value = await self.get(key)
            if value is not None:
                results[key] = value
        
        return results
    
    async def set_many(
        self, 
        mapping: Dict[str, Any], 
        ttl: Optional[int] = None, 
    ) -> Dict[str, bool]:
        """Set multiple values in cache"""
        results = {}
        
        for key, value in mapping.items():
            success = await self.set(key, value, ttl)
            results[key] = success
        
        return results
    
    async def delete_many(self, keys: List[str]) -> Dict[str, bool]:
        """Delete multiple keys from cache"""
        results = {}
        
        for key in keys:
            success = await self.delete(key)
            results[key] = success
        
        return results
    
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
            # Use unique test key to avoid conflicts
            test_key = f"cache_mgr_health_{int(time.time() * 1000)}_{id(self)}"
            test_value = {"timestamp": datetime.utcnow().isoformat(), "test": True}
            
            # Test set
            set_success = await self.set(test_key, test_value, 60)
            
            # Test get
            retrieved = await self.get(test_key)
            get_success = retrieved == test_value
            
            # Test delete
            delete_success = await self.delete(test_key)
            
            # Test exists (should be False after delete)
            exists_success = not await self.exists(test_key)
            
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