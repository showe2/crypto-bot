import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from app.utils.redis_client import RedisClient, check_redis_health


@pytest.mark.unit
class TestRedisClient:
    """Unit tests for Redis client"""
    
    @pytest.mark.asyncio
    async def test_redis_client_creation(self):
        """Test Redis client creation"""
        client = RedisClient()
        assert client is not None
        assert client._connected == False
        assert client.client is None
    
    @pytest.mark.asyncio
    async def test_redis_client_connection_attempt(self):
        """Test Redis connection attempt (with fallback)"""
        client = RedisClient()
        
        # Should connect (either to Redis or memory fallback)
        success = await client.connect()
        assert success == True
        
        # Should report as connected
        is_connected = await client.is_connected()
        assert is_connected == True
        
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_redis_basic_operations(self):
        """Test Redis basic operations"""
        client = RedisClient()
        await client.connect()
        
        try:
            # Test set/get
            await client.set("test_key", "test_value", ex=30)
            result = await client.get("test_key")
            assert result == "test_value"
            
            # Test exists
            exists = await client.exists("test_key")
            assert exists >= 1
            
            # Test delete
            deleted = await client.delete("test_key")
            assert deleted >= 1
            
        finally:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_redis_memory_fallback(self):
        """Test Redis memory fallback when Redis unavailable"""
        with patch('app.utils.redis_client.REDIS_AVAILABLE', False):
            client = RedisClient()
            await client.connect()
            
            # Should use memory fallback
            assert await client.is_connected()
            
            # Operations should still work
            await client.set("fallback_test", "value")
            result = await client.get("fallback_test")
            assert result == "value"
            
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_redis_with_mock(self, mock_redis):
        """Test Redis with mocked Redis instance"""
        with patch('redis.asyncio.Redis', return_value=mock_redis):
            client = RedisClient()
            await client.connect()
            
            # Test with mock
            await client.set("mock_test", "mock_value")
            mock_redis.set.assert_called()
            
            result = await client.get("mock_test")
            mock_redis.get.assert_called()
            
            await client.disconnect()


@pytest.mark.unit
class TestRedisHealth:
    """Tests for Redis health checks"""
    
    @pytest.mark.asyncio
    async def test_redis_health_check(self):
        """Test Redis health check function"""
        health = await check_redis_health()
        
        assert "healthy" in health
        assert "available" in health
        assert "backend" in health
        
        # Should work with either Redis or memory backend
        assert health["backend"] in ["redis", "memory"]
    
    @pytest.mark.asyncio
    async def test_redis_health_with_unavailable_redis(self):
        """Test health check when Redis is unavailable"""
        with patch('app.utils.redis_client.REDIS_AVAILABLE', False):
            health = await check_redis_health()
            
            assert health["healthy"] == False
            assert health["available"] == False
            assert "not installed" in health["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])