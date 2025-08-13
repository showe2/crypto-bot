import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from app.utils.chroma_client import ChromaClient, check_chroma_health


@pytest.mark.unit
class TestChromaDBClient:
    """Unit tests for ChromaDB client"""
    
    def test_chromadb_client_creation(self):
        """Test ChromaDB client creation"""
        client = ChromaClient()
        assert client is not None
        assert client._client is None
        assert client._collection is None
        assert client._connected == False
    
    @pytest.mark.asyncio
    async def test_chromadb_connection_attempt(self, temp_dir):
        """Test ChromaDB connection attempt"""
        client = ChromaClient()
        client.db_path = temp_dir / "test_chroma"
        client.collection_name = "test_collection"
        
        try:
            await client.connect()
            
            # ChromaDB might not be available, that's OK
            # Just test that it doesn't crash
            
        except Exception as e:
            # Expected if ChromaDB not installed
            if "ChromaDB not available" in str(e) or "not installed" in str(e):
                pytest.skip("ChromaDB not available in test environment")
            else:
                # Re-raise unexpected errors
                raise
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass  # Ignore cleanup errors
    
    @pytest.mark.asyncio
    async def test_chromadb_without_installation(self):
        """Test ChromaDB behavior without installation"""
        with patch('app.utils.chroma_client.CHROMADB_AVAILABLE', False):
            client = ChromaClient()
            await client.connect()
            
            # Should correctly handle missing ChromaDB
            assert not client.is_connected()
    
    @pytest.mark.asyncio
    async def test_chromadb_with_mock(self, mock_chromadb):
        """Test ChromaDB with mocking"""
        with patch('chromadb.PersistentClient', return_value=mock_chromadb['client']), \
             patch('app.utils.chroma_client.CHROMADB_AVAILABLE', True):
            
            client = ChromaClient()
            await client.connect()
            
            assert client.is_connected() == True
            
            # Test document addition
            doc_id = await client.add_document("Test content", {"test": True})
            assert doc_id is not None
            mock_chromadb['collection'].add.assert_called_once()
            
            # Test search
            results = await client.search("test query")
            assert len(results["documents"][0]) == 1
            mock_chromadb['collection'].query.assert_called_once()
            
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_chromadb_error_handling(self):
        """Test ChromaDB error handling"""
        client = ChromaClient()
        
        # Test without connection
        with pytest.raises(Exception) as exc_info:
            await client.add_document("test content")
        
        assert "ChromaDB not available" in str(exc_info.value)


@pytest.mark.unit
class TestChromaDBHealth:
    """Tests for ChromaDB health checks"""
    
    @pytest.mark.asyncio
    async def test_chromadb_health_check(self):
        """Test ChromaDB health check function"""
        health = await check_chroma_health()
        
        assert "healthy" in health
        assert "available" in health
        
        if health["available"]:
            # ChromaDB is installed
            if health["healthy"]:
                assert "connected" in health
            else:
                assert "error" in health
        else:
            # ChromaDB not installed
            assert "not installed" in health.get("error", "")
    
    @pytest.mark.asyncio
    async def test_chromadb_health_unavailable(self):
        """Test health check when ChromaDB is unavailable"""
        with patch('app.utils.chroma_client.CHROMADB_AVAILABLE', False):
            health = await check_chroma_health()
            
            assert health["healthy"] == False
            assert health["available"] == False
            assert "not installed" in health["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])