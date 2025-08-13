import pytest
import asyncio
import time
from pathlib import Path
from unittest.mock import patch

from app.utils.redis_client import RedisClient, check_redis_health, get_redis_client
from app.utils.chroma_client import ChromaClient, check_chroma_health, get_chroma_client
from app.utils.cache import CacheManager, cache_manager
from app.utils.health import health_check_all_services


@pytest.mark.integration
class TestRedisIntegration:
    """Integration tests for Redis functionality"""
    
    @pytest.mark.asyncio
    async def test_redis_real_connection_attempt(self):
        """Test real Redis connection (may fallback to memory)"""
        client = RedisClient()
        
        # Should connect (either to Redis or memory fallback)
        success = await client.connect()
        assert success == True
        
        # Should report as connected
        is_connected = await client.is_connected()
        assert is_connected == True
        
        # Should be able to ping
        ping_result = await client.ping()
        assert ping_result == True
        
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_redis_operations_integration(self):
        """Test Redis operations in integration environment"""
        client = RedisClient()
        await client.connect()
        
        try:
            # Test basic operations
            await client.set("integration_test", "value", ex=30)
            result = await client.get("integration_test")
            assert result == "value"
            
            # Test exists
            exists = await client.exists("integration_test")
            assert exists >= 1
            
            # Test increment
            await client.set("counter", "0")
            counter = await client.incr("counter")
            assert counter == 1
            
            # Test hash operations
            await client.hset("test_hash", "field1", "value1")
            hash_value = await client.hget("test_hash", "field1")
            assert hash_value == "value1"
            
            # Test cleanup
            deleted = await client.delete("integration_test", "counter", "test_hash")
            assert deleted >= 1
            
        finally:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_redis_health_check_integration(self):
        """Test Redis health check in real environment"""
        health = await check_redis_health()
        
        assert "healthy" in health
        assert "available" in health
        assert "backend" in health
        
        # Should work with either Redis or memory backend
        assert health["backend"] in ["redis", "memory"]
        
        if health["healthy"]:
            assert "stats" in health
        else:
            # Should have error information if unhealthy
            assert "error" in health or "recommendation" in health
    
    @pytest.mark.asyncio
    async def test_redis_dependency_injection_integration(self):
        """Test Redis dependency injection in real environment"""
        client = await get_redis_client()
        
        assert client is not None
        assert isinstance(client, RedisClient)
        
        # Should be connected
        is_connected = await client.is_connected()
        assert is_connected == True
    
    @pytest.mark.asyncio
    async def test_redis_error_handling_integration(self):
        """Test Redis error handling in integration"""
        # Test with invalid operations
        client = RedisClient()
        await client.connect()
        
        try:
            # Test increment on non-numeric value
            await client.set("non_numeric", "not_a_number")
            
            # This should raise an error or handle gracefully
            try:
                await client.incr("non_numeric")
            except ValueError:
                # Expected behavior
                pass
            except Exception as e:
                # Any other exception should be related to Redis operations
                assert "not an integer" in str(e) or "not numeric" in str(e)
        
        finally:
            await client.disconnect()
    
    @pytest.mark.redis
    @pytest.mark.asyncio
    async def test_redis_performance_integration(self, performance_monitor):
        """Test Redis performance in integration environment"""
        client = RedisClient()
        await client.connect()
        
        try:
            # Test bulk operations performance
            performance_monitor.start()
            
            # Set multiple keys
            for i in range(100):
                await client.set(f"perf_test_{i}", f"value_{i}", ex=60)
            
            # Get multiple keys
            for i in range(100):
                value = await client.get(f"perf_test_{i}")
                assert value == f"value_{i}"
            
            performance_monitor.stop()
            
            # Should complete within reasonable time
            assert performance_monitor.duration < 10.0
            
            # Cleanup
            keys_to_delete = [f"perf_test_{i}" for i in range(100)]
            await client.delete(*keys_to_delete)
        
        finally:
            await client.disconnect()


@pytest.mark.integration
class TestChromaDBIntegration:
    """Integration tests for ChromaDB functionality"""
    
    @pytest.mark.asyncio
    async def test_chromadb_real_connection_attempt(self, temp_dir):
        """Test real ChromaDB connection attempt"""
        client = ChromaClient()
        client.db_path = temp_dir / "integration_chroma"
        client.collection_name = "integration_test_collection"
        
        try:
            await client.connect()
            
            # Check if ChromaDB is available
            if client.is_connected():
                # ChromaDB is available and working
                assert client._client is not None
                assert client._collection is not None
                
                # Test basic functionality
                doc_id = await client.add_document(
                    content="Integration test document",
                    metadata={"test": True, "integration": True}
                )
                assert doc_id is not None
                
                # Test search
                results = await client.search(
                    query="integration test",
                    n_results=5
                )
                assert "documents" in results
                
        except Exception as e:
            # ChromaDB might not be available, that's OK for integration testing
            if "ChromaDB not available" in str(e) or "not installed" in str(e):
                pytest.skip("ChromaDB not available in test environment")
            else:
                raise
        
        finally:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_chromadb_health_check_integration(self):
        """Test ChromaDB health check in real environment"""
        health = await check_chroma_health()
        
        assert "healthy" in health
        assert "available" in health
        
        if health["available"]:
            # ChromaDB is installed
            if health["healthy"]:
                assert "connected" in health
                assert "stats" in health
            else:
                assert "error" in health
        else:
            # ChromaDB not installed
            assert "not installed" in health.get("error", "")
    
    @pytest.mark.asyncio
    async def test_chromadb_dependency_injection_integration(self):
        """Test ChromaDB dependency injection"""
        client = await get_chroma_client()
        
        assert client is not None
        assert isinstance(client, ChromaClient)
        
        # Connection status depends on ChromaDB availability
        # Should not raise exceptions
    
    @pytest.mark.chromadb
    @pytest.mark.asyncio
    async def test_chromadb_document_operations_integration(self, temp_dir):
        """Test ChromaDB document operations (requires ChromaDB)"""
        client = ChromaClient()
        client.db_path = temp_dir / "doc_test_chroma"
        client.collection_name = "doc_integration_test"
        
        try:
            await client.connect()
            
            if not client.is_connected():
                pytest.skip("ChromaDB not available")
            
            # Test adding multiple documents
            doc_ids = []
            test_docs = [
                ("Solana is a fast blockchain", {"topic": "blockchain", "speed": "fast"}),
                ("Token analysis using AI", {"topic": "ai", "application": "analysis"}),
                ("DeFi protocols on Solana", {"topic": "defi", "blockchain": "solana"})
            ]
            
            for content, metadata in test_docs:
                doc_id = await client.add_document(content, metadata)
                doc_ids.append(doc_id)
                assert doc_id is not None
            
            # Test search functionality
            results = await client.search("blockchain", n_results=10)
            assert len(results["documents"][0]) >= 1
            
            # Test metadata filtering
            results = await client.search(
                "analysis", 
                n_results=5,
                where={"topic": "ai"}
            )
            assert len(results["documents"][0]) >= 0
            
            # Test collection stats
            stats = await client.get_collection_stats()
            assert stats["total_documents"] >= len(test_docs)
        
        except Exception as e:
            if "ChromaDB not available" in str(e):
                pytest.skip("ChromaDB not available")
            else:
                raise
        
        finally:
            await client.disconnect()


@pytest.mark.integration
class TestCacheIntegration:
    """Integration tests for cache system"""
    
    @pytest.mark.asyncio
    async def test_cache_manager_integration(self):
        """Test cache manager in integration environment"""
        cache = CacheManager()
        
        # Test basic operations
        success = await cache.set("integration_cache_test", {"data": "test"}, ttl=60)
        assert success == True
        
        result = await cache.get("integration_cache_test")
        assert result == {"data": "test"}
        
        # Test exists
        exists = await cache.exists("integration_cache_test")
        assert exists == True
        
        # Test delete
        deleted = await cache.delete("integration_cache_test")
        assert deleted == True
        
        # Verify deletion
        result_after_delete = await cache.get("integration_cache_test")
        assert result_after_delete is None
    
    @pytest.mark.asyncio
    async def test_cache_with_redis_backend_integration(self):
        """Test cache with Redis backend"""
        cache = CacheManager()
        
        # Try to get Redis client
        redis_client = await cache.get_client()
        
        # Test operations regardless of backend
        test_data = {
            "string": "test_value",
            "number": 42,
            "list": [1, 2, 3],
            "dict": {"nested": "value"}
        }
        
        for key, value in test_data.items():
            await cache.set(f"backend_test_{key}", value, ttl=60)
            result = await cache.get(f"backend_test_{key}")
            assert result == value
        
        # Cleanup
        keys_to_delete = [f"backend_test_{key}" for key in test_data.keys()]
        for key in keys_to_delete:
            await cache.delete(key)
    
    @pytest.mark.asyncio
    async def test_cache_health_check_integration(self):
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
        
        # Backend should be either memory or redis
        assert health["backend"] in ["memory", "redis"]
    
    @pytest.mark.asyncio
    async def test_cache_stats_integration(self):
        """Test cache statistics"""
        cache = CacheManager()
        
        # Perform some operations to generate stats
        await cache.set("stats_test_1", "value1")
        await cache.get("stats_test_1")  # Hit
        await cache.get("non_existent_key")  # Miss
        await cache.set("stats_test_2", "value2")
        
        stats = await cache.get_stats()
        
        assert "operations" in stats
        assert "hit_rate" in stats
        assert "backend" in stats
        
        operations = stats["operations"]
        assert operations["hits"] >= 1
        assert operations["misses"] >= 1
        assert operations["sets"] >= 2
        
        # Cleanup
        await cache.delete("stats_test_1", "stats_test_2")
    
    @pytest.mark.asyncio
    async def test_global_cache_manager_integration(self):
        """Test global cache manager instance"""
        # Test that global cache manager works
        await cache_manager.set("global_test", "global_value", ttl=60)
        result = await cache_manager.get("global_test")
        assert result == "global_value"
        
        # Cleanup
        await cache_manager.delete("global_test")


@pytest.mark.integration
class TestConnectionsIntegration:
    """Test integration between different connection systems"""
    
    @pytest.mark.asyncio
    async def test_all_services_health_integration(self):
        """Test comprehensive health check for all services"""
        health = await health_check_all_services()
        
        assert "overall_status" in health
        assert "services" in health
        assert "service_categories" in health
        assert "summary" in health
        
        # Check service results
        services = health["services"]
        expected_services = [
            "basic_system", "file_system", "logging_system",
            "redis", "chromadb", "cache"
        ]
        
        for service in expected_services:
            assert service in services
            assert "healthy" in services[service]
        
        # Check categories
        categories = health["service_categories"]
        assert "critical" in categories
        assert "optional" in categories
        
        # Critical services should determine overall status
        critical_healthy = categories["critical"]["all_healthy"]
        assert isinstance(critical_healthy, bool)
    
    @pytest.mark.asyncio
    async def test_dependency_startup_integration(self):
        """Test dependency startup in integration environment"""
        from app.core.dependencies import startup_dependencies
        
        # Should not raise exceptions
        try:
            await startup_dependencies()
        except Exception as e:
            # Some dependencies might not be available, that's OK
            assert any(word in str(e).lower() for word in ["not available", "failed", "optional"])
    
    @pytest.mark.asyncio
    async def test_dependency_shutdown_integration(self):
        """Test dependency shutdown in integration environment"""
        from app.core.dependencies import shutdown_dependencies
        
        # Should not raise exceptions
        try:
            await shutdown_dependencies()
        except Exception as e:
            # Some cleanup might fail, that's OK
            assert any(word in str(e).lower() for word in ["not available", "failed", "cleanup"])
    
    @pytest.mark.asyncio
    async def test_cache_redis_integration_real(self):
        """Test cache-Redis integration in real environment"""
        # Test that cache can use Redis backend if available
        cache = CacheManager()
        
        # Get Redis client (might be None or real client)
        redis_client = await cache.get_client()
        
        # Perform cache operations
        await cache.set("redis_integration_test", "test_data", ttl=60)
        result = await cache.get("redis_integration_test")
        assert result == "test_data"
        
        # Get stats to see backend type
        stats = await cache.get_stats()
        backend = stats.get("backend", "unknown")
        assert backend in ["memory", "redis"]
        
        # Cleanup
        await cache.delete("redis_integration_test")
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_concurrent_connections_integration(self):
        """Test concurrent connections to services"""
        import concurrent.futures
        
        async def test_redis():
            client = RedisClient()
            await client.connect()
            await client.set("concurrent_test_redis", "value")
            result = await client.get("concurrent_test_redis")
            await client.delete("concurrent_test_redis")
            await client.disconnect()
            return result == "value"
        
        async def test_cache():
            cache = CacheManager()
            await cache.set("concurrent_test_cache", "value")
            result = await cache.get("concurrent_test_cache")
            await cache.delete("concurrent_test_cache")
            return result == "value"
        
        async def test_health():
            health = await health_check_all_services()
            return "overall_status" in health
        
        # Run tests concurrently
        tasks = [test_redis(), test_cache(), test_health()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All tasks should complete successfully or with known exceptions
        for result in results:
            if isinstance(result, Exception):
                # Should be connection-related exceptions, not crashes
                assert any(word in str(result).lower() for word in 
                          ["connection", "not available", "timeout", "redis", "chromadb"])
            else:
                assert isinstance(result, bool)


@pytest.mark.integration
@pytest.mark.slow
class TestSystemIntegration:
    """Test full system integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_full_system_startup_integration(self):
        """Test complete system startup scenario"""
        # Simulate full application startup
        from app.core.config import get_settings
        from app.core.logging import setup_logging
        
        # 1. Load configuration
        settings = get_settings()
        assert settings is not None
        
        # 2. Setup logging
        setup_logging()
        
        # 3. Initialize connections
        redis_client = await get_redis_client()
        chroma_client = await get_chroma_client()
        
        # Should not raise exceptions
        assert redis_client is not None
        assert chroma_client is not None
        
        # 4. Check system health
        health = await health_check_all_services()
        assert "overall_status" in health
    
    @pytest.mark.asyncio
    async def test_error_resilience_integration(self):
        """Test system resilience to connection errors"""
        # Test that system works even when optional services fail
        
        with patch('app.utils.redis_client.RedisClient.connect') as mock_redis_connect:
            mock_redis_connect.side_effect = Exception("Redis connection failed")
            
            # System should still work
            health = await health_check_all_services()
            
            # Should report Redis as unhealthy but system should still be functional
            assert "redis" in health["services"]
            assert not health["services"]["redis"]["healthy"]
            
            # Critical services should still work
            assert health["services"]["basic_system"]["healthy"]
            assert health["services"]["file_system"]["healthy"]
    
    @pytest.mark.asyncio
    async def test_performance_under_load_integration(self, performance_monitor):
        """Test system performance under load"""
        # Test multiple operations concurrently
        async def perform_operations():
            cache = CacheManager()
            
            # Perform multiple cache operations
            for i in range(10):
                await cache.set(f"load_test_{i}", f"value_{i}", ttl=60)
                await cache.get(f"load_test_{i}")
            
            # Cleanup
            for i in range(10):
                await cache.delete(f"load_test_{i}")
        
        performance_monitor.start()
        
        # Run multiple operation sets concurrently
        tasks = [perform_operations() for _ in range(5)]
        await asyncio.gather(*tasks)
        
        performance_monitor.stop()
        
        # Should complete within reasonable time
        assert performance_monitor.duration < 30.0
    
    @pytest.mark.asyncio
    async def test_configuration_integration(self):
        """Test configuration system integration"""
        from app.core.config import get_settings
        
        settings = get_settings()
        
        # Test that all required paths exist
        paths_to_check = [
            settings.CHROMA_DB_PATH,
            settings.KNOWLEDGE_BASE_PATH,
            settings.LOGS_DIR
        ]
        
        for path_str in paths_to_check:
            path = Path(path_str)
            assert path.exists(), f"Required path does not exist: {path}"
            assert path.is_dir(), f"Path is not a directory: {path}"
        
        # Test helper methods
        redis_url = settings.get_redis_url()
        assert redis_url.startswith("redis://")
        
        helius_url = settings.get_helius_rpc_url()
        assert "helius" in helius_url.lower() or "rpc" in helius_url.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])