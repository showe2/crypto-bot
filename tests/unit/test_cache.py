import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from app.utils.cache import CacheManager, cache_manager


@pytest.mark.unit
class TestCacheManager:
    """Unit tests for Cache Manager"""
    
    @pytest.mark.asyncio
    async def test_cache_manager_creation(self):
        """Test cache manager creation"""
        cache = CacheManager()
        assert cache is not None
        assert cache.redis_client is None
        assert cache._memory_cache == {}
        assert cache._memory_expiry == {}
    
    @pytest.mark.asyncio
    async def test_cache_basic_operations(self):
        """Test basic cache operations"""
        cache = CacheManager()
        
        # Test set/get with memory fallback
        success = await cache.set("test_key", "test_value", ttl=60)
        assert success == True
        
        result = await cache.get("test_key")
        assert result == "test_value"
        
        # Test exists
        exists = await cache.exists("test_key")
        assert exists == True
        
        # Test delete
        deleted = await cache.delete("test_key")
        assert deleted == True
        
        # Verify deletion
        result_after_delete = await cache.get("test_key")
        assert result_after_delete is None
    
    @pytest.mark.asyncio
    async def test_cache_with_redis_backend(self):
        """Test cache with Redis backend"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "redis_value"
        mock_redis.set.return_value = True
        mock_redis.delete.return_value = 1
        mock_redis.exists.return_value = 1
        
        cache = CacheManager()
        cache.redis_client = mock_redis
        
        # Test operations with Redis backend
        await cache.set("redis_test", "redis_value", ttl=60)
        mock_redis.set.assert_called()
        
        result = await cache.get("redis_test")
        mock_redis.get.assert_called()
        
        await cache.delete("redis_test")
        mock_redis.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_cache_serialization(self):
        """Test cache value serialization"""
        cache = CacheManager()
        
        # Test with different data types
        test_data = {
            "string": "test_value",
            "number": 42,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "boolean": True
        }
        
        for key, value in test_data.items():
            await cache.set(f"serial_test_{key}", value, ttl=60)
            result = await cache.get(f"serial_test_{key}")
            assert result == value
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test cache expiration (memory fallback)"""
        import time
        
        cache = CacheManager()
        
        # Set with short TTL
        await cache.set("expire_test", "expire_value", ttl=1)
        
        # Should exist immediately
        result = await cache.get("expire_test")
        assert result == "expire_value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired (manually clean in memory cache)
        cache._clean_expired_memory_keys()
        result = await cache.get("expire_test")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test cache statistics"""
        cache = CacheManager()
        
        # Perform some operations to generate stats
        await cache.set("stats_test_1", "value1")
        await cache.get("stats_test_1")  # Hit
        await cache.get("non_existent_key")  # Miss
        
        stats = await cache.get_stats()
        
        assert "operations" in stats
        assert "hit_rate" in stats
        assert "backend" in stats
        
        operations = stats["operations"]
        assert operations["hits"] >= 1
        assert operations["misses"] >= 1
        assert operations["sets"] >= 1
        
        # Backend should be memory (no Redis in unit tests)
        assert stats["backend"] == "memory"
    
    @pytest.mark.asyncio
    async def test_cache_health_check(self):
        """Test cache health check"""
        cache = CacheManager()
        
        health = await cache.health_check()
        
        assert "healthy" in health
        assert "operations" in health
        assert "backend" in health
        
        # All basic operations should work
        ops = health["operations"]
        assert ops["set"] == True
        assert ops["get"] == True
        assert ops["delete"] == True
        assert ops["exists"] == True
        
        # Should be healthy with memory backend
        assert health["healthy"] == True
        assert health["backend"] == "memory"
    
    @pytest.mark.asyncio
    async def test_cache_namespace_operations(self):
        """Test cache operations with namespaces"""
        cache = CacheManager()
        
        # Set values in different namespaces
        await cache.set("test_key", "namespace1_value", namespace="ns1")
        await cache.set("test_key", "namespace2_value", namespace="ns2")
        
        # Should get different values from different namespaces
        result1 = await cache.get("test_key", namespace="ns1")
        result2 = await cache.get("test_key", namespace="ns2")
        
        assert result1 == "namespace1_value"
        assert result2 == "namespace2_value"
        
        # Cleanup
        await cache.delete("test_key", namespace="ns1")
        await cache.delete("test_key", namespace="ns2")


@pytest.mark.unit
class TestGlobalCacheManager:
    """Test global cache manager instance"""
    
    @pytest.mark.asyncio
    async def test_global_cache_manager(self):
        """Test that global cache manager works"""
        # Test that global cache manager is available
        assert cache_manager is not None
        assert isinstance(cache_manager, CacheManager)
        
        # Test basic operations
        await cache_manager.set("global_test", "global_value", ttl=60)
        result = await cache_manager.get("global_test")
        assert result == "global_value"
        
        # Cleanup
        await cache_manager.delete("global_test")
    
    @pytest.mark.asyncio
    async def test_cache_manager_singleton_behavior(self):
        """Test cache manager singleton-like behavior"""
        # The global cache_manager should be consistent
        await cache_manager.set("singleton_test", "test_value")
        
        # Should be able to retrieve from the same instance
        result = await cache_manager.get("singleton_test")
        assert result == "test_value"
        
        # Cleanup
        await cache_manager.delete("singleton_test")


@pytest.mark.unit
class TestCacheEdgeCases:
    """Test cache edge cases"""
    
    @pytest.mark.asyncio
    async def test_cache_with_none_values(self):
        """Test cache with None values"""
        cache = CacheManager()
        
        # Setting None should work
        await cache.set("none_test", None)
        result = await cache.get("none_test")
        assert result is None
        
        # But should distinguish from missing key
        exists = await cache.exists("none_test")
        assert exists == True
        
        missing_result = await cache.get("definitely_missing_key")
        assert missing_result is None
        
        missing_exists = await cache.exists("definitely_missing_key")
        assert missing_exists == False
    
    @pytest.mark.asyncio
    async def test_cache_with_empty_values(self):
        """Test cache with empty values"""
        cache = CacheManager()
        
        empty_values = ["", [], {}, 0, False]
        
        for i, value in enumerate(empty_values):
            key = f"empty_test_{i}"
            await cache.set(key, value)
            result = await cache.get(key)
            assert result == value
            
            # Cleanup
            await cache.delete(key)
    
    @pytest.mark.asyncio
    async def test_cache_error_handling(self):
        """Test cache error handling"""
        cache = CacheManager()
        
        # Test operations on non-existent keys
        result = await cache.get("non_existent")
        assert result is None
        
        exists = await cache.exists("non_existent")
        assert exists == False
        
        deleted = await cache.delete("non_existent")
        assert deleted == False
        
        # Test TTL on non-existent key
        ttl = await cache.ttl("non_existent")
        assert ttl == -2  # Key doesn't exist


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])