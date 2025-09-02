import asyncio
import json
import time
from typing import Any, Optional, Dict, Union, List
from urllib.parse import urlparse
from loguru import logger

try:
    import redis.asyncio as redis
    from redis.asyncio import Redis
    from redis.exceptions import RedisError, ConnectionError, TimeoutError
    REDIS_AVAILABLE = True
    logger.debug("✅ Redis available")
except ImportError:
    REDIS_AVAILABLE = False
    logger.debug("⚠️  Redis not installed - using memory fallback")

from app.core.config import get_settings

settings = get_settings()


class RedisClient:
    """Async Redis client with automatic fallback to memory storage"""
    
    def __init__(self):
        self.client: Optional[Redis] = None
        self._memory_store: Dict[str, Any] = {}  # Fallback memory storage
        self._memory_expiry: Dict[str, float] = {}  # Track expiry times for memory
        self._connected = False
        self._connection_pool = None
        self._lock = asyncio.Lock()
        
    async def connect(self) -> bool:
        """Initialize Redis connection with connection pooling"""
        if not REDIS_AVAILABLE:
            logger.info("🔄 Redis not available - using memory fallback")
            self._connected = True
            return True
            
        async with self._lock:
            if self._connected and self.client:
                return True
                
            try:
                # Parse Redis URL
                redis_url = settings.get_redis_url()
                parsed_url = urlparse(redis_url)
                
                # Connection parameters
                connection_kwargs = {
                    'host': parsed_url.hostname or 'localhost',
                    'port': parsed_url.port or 6379,
                    'db': int(parsed_url.path.lstrip('/')) if parsed_url.path else settings.REDIS_DB,
                    'password': parsed_url.password or settings.REDIS_PASSWORD,
                    'decode_responses': True,  # Automatically decode responses to strings
                    'socket_timeout': 5.0,
                    'socket_connect_timeout': 5.0,
                    'retry_on_timeout': True,
                    'health_check_interval': 30,
                    'max_connections': 20,
                    'socket_keepalive': True,
                    'socket_keepalive_options': {
                        1: 1,  # TCP_KEEPIDLE
                        2: 3,  # TCP_KEEPINTVL  
                        3: 5,  # TCP_KEEPCNT
                    } if hasattr(redis, 'TCP_KEEPIDLE') else {}
                }
                
                # Create connection pool
                self._connection_pool = redis.ConnectionPool(**connection_kwargs)
                
                # Create Redis client
                self.client = Redis(connection_pool=self._connection_pool)
                
                # Test connection
                await self.client.ping()
                
                # Get Redis info
                info = await self.client.info()
                redis_version = info.get('redis_version', 'unknown')
                
                self._connected = True
                logger.info(f"✅ Redis connection established (version: {redis_version})")
                
                return True
                
            except Exception as e:
                logger.warning(f"⚠️  Redis connection failed: {str(e)} - using memory fallback")
                self.client = None
                self._connection_pool = None
                self._connected = True  # Still "connected" via memory fallback
                return True
    
    async def disconnect(self):
        """Close Redis connection and cleanup resources"""
        async with self._lock:
            if self.client:
                try:
                    await self.client.close()
                    logger.info("✅ Redis connection closed")
                except Exception as e:
                    logger.warning(f"⚠️  Error closing Redis connection: {str(e)}")
                    
            if self._connection_pool:
                try:
                    await self._connection_pool.disconnect()
                except Exception as e:
                    logger.warning(f"⚠️  Error closing connection pool: {str(e)}")
                    
            self.client = None
            self._connection_pool = None
            self._connected = False
            
            # Clear memory fallback
            self._memory_store.clear()
            self._memory_expiry.clear()
    
    def _clean_expired_memory_keys(self):
        """Clean expired keys from memory storage"""
        current_time = time.time()
        expired_keys = [
            key for key, expiry_time in self._memory_expiry.items()
            if expiry_time <= current_time
        ]
        
        for key in expired_keys:
            self._memory_store.pop(key, None)
            self._memory_expiry.pop(key, None)
    
    async def is_connected(self) -> bool:
        """Check if Redis is connected (including memory fallback)"""
        return self._connected
    
    async def ping(self) -> bool:
        """Ping Redis server to check connectivity"""
        if not self._connected:
            await self.connect()
            
        if self.client:
            try:
                await self.client.ping()
                return True
            except Exception:
                logger.warning("Redis ping failed - connection may be lost")
                return False
        
        # Memory fallback is always "pingable"
        return True
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                value = await self.client.get(key)
                return value
            except Exception as e:
                logger.debug(f"Redis GET failed for key '{key}': {str(e)}")
        
        # Fallback to memory
        self._clean_expired_memory_keys()
        return self._memory_store.get(key)
    
    async def set(
        self, 
        key: str, 
        value: Union[str, int, float], 
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """Set value with optional expiration and conditions"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                result = await self.client.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
                return bool(result)
            except Exception as e:
                logger.debug(f"Redis SET failed for key '{key}': {str(e)}")
        
        # Fallback to memory
        if nx and key in self._memory_store:
            return False
        if xx and key not in self._memory_store:
            return False
            
        self._memory_store[key] = value  # Store serialized value as-is
        
        # Handle expiration
        if ex:
            self._memory_expiry[key] = time.time() + ex
        elif px:
            self._memory_expiry[key] = time.time() + (px / 1000)
        else:
            self._memory_expiry.pop(key, None)
            
        return True
    
    async def delete(self, *keys: str) -> int:
        """Delete one or more keys"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                count = await self.client.delete(*keys)
                return count
            except Exception as e:
                logger.debug(f"Redis DELETE failed for keys {keys}: {str(e)}")
        
        # Fallback to memory
        count = 0
        for key in keys:
            if key in self._memory_store:
                del self._memory_store[key]
                count += 1
            self._memory_expiry.pop(key, None)
        return count
    
    async def exists(self, *keys: str) -> int:
        """Check if keys exist"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                count = await self.client.exists(*keys)
                return count
            except Exception as e:
                logger.debug(f"Redis EXISTS failed for keys {keys}: {str(e)}")
        
        # Fallback to memory
        self._clean_expired_memory_keys()
        count = sum(1 for key in keys if key in self._memory_store)
        return count
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for a key"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                result = await self.client.expire(key, seconds)
                return bool(result)
            except Exception as e:
                logger.debug(f"Redis EXPIRE failed for key '{key}': {str(e)}")
        
        # Fallback to memory
        if key in self._memory_store:
            self._memory_expiry[key] = time.time() + seconds
            return True
        return False
    
    async def ttl(self, key: str) -> int:
        """Get time to live for a key"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                ttl_value = await self.client.ttl(key)
                return ttl_value
            except Exception as e:
                logger.debug(f"Redis TTL failed for key '{key}': {str(e)}")
        
        # Fallback to memory
        if key not in self._memory_store:
            return -2  # Key doesn't exist
            
        if key not in self._memory_expiry:
            return -1  # Key exists but no expiration
            
        remaining = self._memory_expiry[key] - time.time()
        return max(0, int(remaining))
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment a key's value"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                result = await self.client.incr(key, amount)
                return result
            except Exception as e:
                logger.debug(f"Redis INCR failed for key '{key}': {str(e)}")
        
        # Fallback to memory
        current_value = self._memory_store.get(key, "0")
        try:
            new_value = int(current_value) + amount
            self._memory_store[key] = str(new_value)
            return new_value
        except ValueError:
            raise ValueError(f"Value at key '{key}' is not an integer")
    
    async def decr(self, key: str, amount: int = 1) -> int:
        """Decrement a key's value"""
        return await self.incr(key, -amount)
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get field from hash"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                value = await self.client.hget(name, key)
                return value
            except Exception as e:
                logger.debug(f"Redis HGET failed for hash '{name}' key '{key}': {str(e)}")
        
        # Fallback to memory (simulate hash with nested dict)
        hash_data = self._memory_store.get(name)
        if isinstance(hash_data, dict):
            return hash_data.get(key)
        return None
    
    async def hset(self, name: str, key: str, value: Union[str, int, float]) -> int:
        """Set field in hash"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                result = await self.client.hset(name, key, str(value))
                return result
            except Exception as e:
                logger.debug(f"Redis HSET failed for hash '{name}' key '{key}': {str(e)}")
        
        # Fallback to memory
        if name not in self._memory_store or not isinstance(self._memory_store[name], dict):
            self._memory_store[name] = {}
            
        was_new = key not in self._memory_store[name]
        self._memory_store[name][key] = str(value)
        return 1 if was_new else 0
    
    async def hgetall(self, name: str) -> Dict[str, str]:
        """Get all fields from hash"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                result = await self.client.hgetall(name)
                return result
            except Exception as e:
                logger.debug(f"Redis HGETALL failed for hash '{name}': {str(e)}")
        
        # Fallback to memory
        hash_data = self._memory_store.get(name, {})
        if isinstance(hash_data, dict):
            return hash_data
        return {}
    
    async def lpush(self, name: str, *values: Union[str, int, float]) -> int:
        """Push values to left of list"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                result = await self.client.lpush(name, *[str(v) for v in values])
                return result
            except Exception as e:
                logger.debug(f"Redis LPUSH failed for list '{name}': {str(e)}")
        
        # Fallback to memory
        if name not in self._memory_store or not isinstance(self._memory_store[name], list):
            self._memory_store[name] = []
            
        # Insert at beginning (left push)
        for value in reversed(values):
            self._memory_store[name].insert(0, str(value))
            
        return len(self._memory_store[name])
    
    async def rpop(self, name: str) -> Optional[str]:
        """Pop value from right of list"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                result = await self.client.rpop(name)
                return result
            except Exception as e:
                logger.debug(f"Redis RPOP failed for list '{name}': {str(e)}")
        
        # Fallback to memory
        if name in self._memory_store and isinstance(self._memory_store[name], list):
            if self._memory_store[name]:
                return self._memory_store[name].pop()
        return None
    
    async def llen(self, name: str) -> int:
        """Get length of list"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                result = await self.client.llen(name)
                return result
            except Exception as e:
                logger.debug(f"Redis LLEN failed for list '{name}': {str(e)}")
        
        # Fallback to memory
        if name in self._memory_store and isinstance(self._memory_store[name], list):
            return len(self._memory_store[name])
        return 0
    
    async def zadd(self, name: str, mapping: Dict[str, float]) -> int:
        """Add members to sorted set"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                result = await self.client.zadd(name, mapping)
                return result
            except Exception as e:
                logger.debug(f"Redis ZADD failed for sorted set '{name}': {str(e)}")
        
        # Fallback to memory (simulate sorted set with list of tuples)
        if name not in self._memory_store or not isinstance(self._memory_store[name], list):
            self._memory_store[name] = []
            
        sorted_set = self._memory_store[name]
        added_count = 0
        
        for member, score in mapping.items():
            # Remove existing member if present
            sorted_set[:] = [(m, s) for m, s in sorted_set if m != member]
            # Add new member
            sorted_set.append((member, score))
            added_count += 1
            
        # Keep sorted by score
        sorted_set.sort(key=lambda x: x[1])
        return added_count
    
    async def zcard(self, name: str) -> int:
        """Get size of sorted set"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                result = await self.client.zcard(name)
                return result
            except Exception as e:
                logger.debug(f"Redis ZCARD failed for sorted set '{name}': {str(e)}")
        
        # Fallback to memory
        if name in self._memory_store and isinstance(self._memory_store[name], list):
            return len(self._memory_store[name])
        return 0
    
    async def zremrangebyscore(self, name: str, min_score: float, max_score: float) -> int:
        """Remove members from sorted set by score range"""
        if not self._connected:
            await self.connect()
            
        # Try Redis first
        if self.client:
            try:
                result = await self.client.zremrangebyscore(name, min_score, max_score)
                return result
            except Exception as e:
                logger.debug(f"Redis ZREMRANGEBYSCORE failed for sorted set '{name}': {str(e)}")
        
        # Fallback to memory
        if name in self._memory_store and isinstance(self._memory_store[name], list):
            sorted_set = self._memory_store[name]
            original_length = len(sorted_set)
            
            # Remove members in score range
            sorted_set[:] = [
                (member, score) for member, score in sorted_set
                if not (min_score <= score <= max_score)
            ]
            
            return original_length - len(sorted_set)
        return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Redis statistics"""
        stats = {
            "connected": self._connected,
            "backend": "memory" if not self.client else "redis",
            "memory_keys": len(self._memory_store),
            "memory_expired_keys": len(self._memory_expiry)
        }
        
        if self.client:
            try:
                info = await self.client.info()
                stats.update({
                    "redis_version": info.get('redis_version'),
                    "used_memory": info.get('used_memory_human'),
                    "connected_clients": info.get('connected_clients'),
                    "total_commands_processed": info.get('total_commands_processed'),
                    "keyspace_hits": info.get('keyspace_hits', 0),
                    "keyspace_misses": info.get('keyspace_misses', 0),
                    "uptime_in_seconds": info.get('uptime_in_seconds'),
                })
                
                # Calculate hit rate
                hits = info.get('keyspace_hits', 0)
                misses = info.get('keyspace_misses', 0)
                if hits + misses > 0:
                    stats['hit_rate'] = round(hits / (hits + misses) * 100, 2)
                else:
                    stats['hit_rate'] = 0
                    
            except Exception as e:
                logger.debug(f"Failed to get Redis info: {str(e)}")
                stats['redis_error'] = str(e)
        
        return stats


# Global Redis client instance
redis_client = RedisClient()


async def init_redis() -> bool:
    """Initialize Redis connection"""
    return await redis_client.connect()


async def close_redis():
    """Close Redis connection"""
    await redis_client.disconnect()


async def get_redis_client() -> RedisClient:
    """Get Redis client (dependency injection)"""
    if not await redis_client.is_connected():
        await redis_client.connect()
    return redis_client


async def check_redis_health() -> Dict[str, Any]:
    """Check Redis health and return detailed status"""
    try:
        if not REDIS_AVAILABLE:
            return {
                "healthy": False,
                "available": False,
                "error": "Redis not installed (install with: pip install redis)",
                "recommendation": "Run: pip install redis"
            }
        
        client = await get_redis_client()
        
        if not await client.is_connected():
            await client.connect()
        
        # Test basic operations
        test_key = f"redis_health_{int(time.time() * 1000)}"
        test_value = "health_test_value"
        
        # Test SET/GET/DELETE
        await client.set(test_key, test_value, ex=60)
        retrieved = await client.get(test_key)
        await client.delete(test_key)
        
        # Test ping
        ping_success = await client.ping()
        
        # Get stats
        stats = await client.get_stats()
        
        operations_working = retrieved == test_value
        
        return {
            "healthy": operations_working and ping_success,
            "available": True,
            "connected": await client.is_connected(),
            "ping_success": ping_success,
            "operations_working": operations_working,
            "backend": stats.get("backend", "unknown"),
            "redis_version": stats.get("redis_version"),
            "used_memory": stats.get("used_memory"),
            "connected_clients": stats.get("connected_clients"),
            "hit_rate": stats.get("hit_rate"),
            "stats": stats
        }
        
    except Exception as e:
        logger.warning(f"Redis health check failed: {str(e)}")
        return {
            "healthy": False,
            "available": REDIS_AVAILABLE,
            "connected": False,
            "error": str(e),
            "recommendation": "Check Redis server status and connection settings"
        }


# Utility functions for common Redis patterns
async def cache_set(key: str, value: Any, ttl: int = 3600) -> bool:
    """Cache a value with JSON serialization"""
    try:
        client = await get_redis_client()
        serialized_value = json.dumps(value, default=str)
        return await client.set(key, serialized_value, ex=ttl)
    except Exception as e:
        logger.warning(f"Cache SET failed for key '{key}': {str(e)}")
        return False


async def cache_get(key: str, default: Any = None) -> Any:
    """Get cached value with JSON deserialization"""
    try:
        client = await get_redis_client()
        value = await client.get(key)
        if value is not None:
            return json.loads(value)
        return default
    except Exception as e:
        logger.warning(f"Cache GET failed for key '{key}': {str(e)}")
        return default


async def cache_delete(*keys: str) -> int:
    """Delete cached values"""
    try:
        client = await get_redis_client()
        return await client.delete(*keys)
    except Exception as e:
        logger.warning(f"Cache DELETE failed for keys {keys}: {str(e)}")
        return 0


# Rate limiting utilities using Redis sorted sets
async def check_rate_limit(
    identifier: str, 
    limit: int, 
    window_seconds: int = 60, 
    namespace: str = "rate_limit"
) -> Dict[str, Any]:
    """Check and update rate limit using sliding window"""
    try:
        client = await get_redis_client()
        key = f"{namespace}:{identifier}"
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # Clean old entries
        await client.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        current_count = await client.zcard(key)
        
        if current_count >= limit:
            # Get the oldest request time to calculate reset time
            oldest_requests = await client.client.zrange(key, 0, 0, withscores=True) if client.client else []
            if oldest_requests:
                reset_time = oldest_requests[0][1] + window_seconds
            else:
                reset_time = current_time + window_seconds
                
            return {
                "allowed": False,
                "limit": limit,
                "remaining": 0,
                "reset_time": reset_time,
                "retry_after": max(0, int(reset_time - current_time))
            }
        
        # Add current request
        await client.zadd(key, {str(current_time): current_time})
        await client.expire(key, window_seconds)
        
        return {
            "allowed": True,
            "limit": limit,
            "remaining": limit - current_count - 1,
            "reset_time": current_time + window_seconds,
            "retry_after": 0
        }
        
    except Exception as e:
        logger.warning(f"Rate limit check failed for '{identifier}': {str(e)}")
        # On error, allow the request (fail open)
        return {
            "allowed": True,
            "limit": limit,
            "remaining": limit - 1,
            "reset_time": time.time() + window_seconds,
            "retry_after": 0,
            "error": str(e)
        }