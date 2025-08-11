import redis.asyncio as redis
import json
import pickle
from typing import Any, Optional, Dict, Union
from datetime import datetime, timedelta
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class RedisClient:
    """Redis async client with connection management"""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connection_pool = None
    
    async def connect(self):
        """Initialize Redis connection"""
        try:
            if self._client is None:
                # Parse Redis URL
                redis_config = {
                    'decode_responses': True,
                    'socket_keepalive': True,
                    'socket_keepalive_options': {},
                    'health_check_interval': 30,
                    'retry_on_timeout': True,
                    'max_connections': 20
                }
                
                if settings.REDIS_PASSWORD:
                    redis_config['password'] = settings.REDIS_PASSWORD
                
                # Create connection pool
                self._connection_pool = redis.ConnectionPool.from_url(
                    settings.REDIS_URL,
                    **redis_config
                )
                
                # Create client
                self._client = redis.Redis(connection_pool=self._connection_pool)
                
                # Test connection
                await self._client.ping()
                logger.info("Redis connection established successfully")
                
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self._client = None
            raise
    
    async def disconnect(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis connection closed")
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance"""
        if self._client is None:
            raise ConnectionError("Redis client not connected. Call connect() first.")
        return self._client
    
    async def is_connected(self) -> bool:
        """Check if Redis is connected"""
        try:
            if self._client is None:
                return False
            await self._client.ping()
            return True
        except:
            return False
    
    # Basic operations
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.warning(f"Redis GET error for key {key}: {str(e)}")
            return None
    
    async def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """Set value with optional expiration"""
        try:
            return await self.client.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
        except Exception as e:
            logger.warning(f"Redis SET error for key {key}: {str(e)}")
            return False
    
    async def delete(self, *keys: str) -> int:
        """Delete keys"""
        try:
            return await self.client.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis DELETE error for keys {keys}: {str(e)}")
            return 0
    
    async def exists(self, *keys: str) -> int:
        """Check if keys exist"""
        try:
            return await self.client.exists(*keys)
        except Exception as e:
            logger.warning(f"Redis EXISTS error for keys {keys}: {str(e)}")
            return 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for key"""
        try:
            return await self.client.expire(key, seconds)
        except Exception as e:
            logger.warning(f"Redis EXPIRE error for key {key}: {str(e)}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get TTL for key"""
        try:
            return await self.client.ttl(key)
        except Exception as e:
            logger.warning(f"Redis TTL error for key {key}: {str(e)}")
            return -1
    
    # Hash operations
    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field"""
        try:
            return await self.client.hget(name, key)
        except Exception as e:
            logger.warning(f"Redis HGET error for hash {name}, key {key}: {str(e)}")
            return None
    
    async def hset(self, name: str, key: str, value: str) -> bool:
        """Set hash field"""
        try:
            return await self.client.hset(name, key, value) >= 0
        except Exception as e:
            logger.warning(f"Redis HSET error for hash {name}, key {key}: {str(e)}")
            return False
    
    async def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields"""
        try:
            return await self.client.hgetall(name)
        except Exception as e:
            logger.warning(f"Redis HGETALL error for hash {name}: {str(e)}")
            return {}
    
    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields"""
        try:
            return await self.client.hdel(name, *keys)
        except Exception as e:
            logger.warning(f"Redis HDEL error for hash {name}, keys {keys}: {str(e)}")
            return 0
    
    # List operations
    async def lpush(self, name: str, *values: str) -> int:
        """Push to list from left"""
        try:
            return await self.client.lpush(name, *values)
        except Exception as e:
            logger.warning(f"Redis LPUSH error for list {name}: {str(e)}")
            return 0
    
    async def rpush(self, name: str, *values: str) -> int:
        """Push to list from right"""
        try:
            return await self.client.rpush(name, *values)
        except Exception as e:
            logger.warning(f"Redis RPUSH error for list {name}: {str(e)}")
            return 0
    
    async def lpop(self, name: str) -> Optional[str]:
        """Pop from list from left"""
        try:
            return await self.client.lpop(name)
        except Exception as e:
            logger.warning(f"Redis LPOP error for list {name}: {str(e)}")
            return None
    
    async def rpop(self, name: str) -> Optional[str]:
        """Pop from list from right"""
        try:
            return await self.client.rpop(name)
        except Exception as e:
            logger.warning(f"Redis RPOP error for list {name}: {str(e)}")
            return None
    
    async def llen(self, name: str) -> int:
        """Get list length"""
        try:
            return await self.client.llen(name)
        except Exception as e:
            logger.warning(f"Redis LLEN error for list {name}: {str(e)}")
            return 0
    
    # Set operations
    async def sadd(self, name: str, *values: str) -> int:
        """Add to set"""
        try:
            return await self.client.sadd(name, *values)
        except Exception as e:
            logger.warning(f"Redis SADD error for set {name}: {str(e)}")
            return 0
    
    async def srem(self, name: str, *values: str) -> int:
        """Remove from set"""
        try:
            return await self.client.srem(name, *values)
        except Exception as e:
            logger.warning(f"Redis SREM error for set {name}: {str(e)}")
            return 0
    
    async def smembers(self, name: str) -> set:
        """Get all set members"""
        try:
            return await self.client.smembers(name)
        except Exception as e:
            logger.warning(f"Redis SMEMBERS error for set {name}: {str(e)}")
            return set()
    
    async def scard(self, name: str) -> int:
        """Get set cardinality"""
        try:
            return await self.client.scard(name)
        except Exception as e:
            logger.warning(f"Redis SCARD error for set {name}: {str(e)}")
            return 0


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
        if not await redis_client.is_connected():
            await redis_client.connect()
        
        # Test basic operations
        test_key = "health_check_" + str(datetime.utcnow().timestamp())
        test_value = "ok"
        
        # Set and get test
        await redis_client.set(test_key, test_value, ex=60)
        retrieved = await redis_client.get(test_key)
        await redis_client.delete(test_key)
        
        # Get Redis info
        info = await redis_client.client.info()
        
        return {
            "healthy": retrieved == test_value,
            "connected": True,
            "version": info.get("redis_version", "unknown"),
            "used_memory": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "total_commands_processed": info.get("total_commands_processed", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0)
        }
        
    except Exception as e:
        logger.warning(f"Redis health check failed: {str(e)}")
        return {
            "healthy": False,
            "connected": False,
            "error": str(e)
        }