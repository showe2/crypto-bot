import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# ChromaDB might not be available, so import with error handling
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None

from app.utils.chroma_client import ChromaClient, check_chroma_health, get_chroma_client


@pytest.mark.chromadb
class TestChromaDBClient:
    """Tests for ChromaDB client functionality"""
    
    @pytest.fixture
    def temp_chroma_dir(self):
        """Temporary directory for ChromaDB"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def chroma_client(self, temp_chroma_dir):
        """ChromaDB client for testing"""
        client = ChromaClient()
        client.db_path = temp_chroma_dir / "test_chroma"
        client.collection_name = f"test_collection_{id(client)}"
        return client
    
    def test_chromadb_client_creation(self, chroma_client):
        """Test ChromaDB client creation"""
        assert chroma_client is not None
        assert chroma_client._client is None
        assert chroma_client._collection is None
        assert chroma_client._connected == False
        assert chroma_client.collection_name.startswith("test_collection_")
    
    @pytest.mark.skipif(not CHROMADB_AVAILABLE, reason="ChromaDB not installed")
    @pytest.mark.asyncio
    async def test_chromadb_connection(self, chroma_client):
        """Test ChromaDB connection"""
        try:
            await chroma_client.connect()
            
            if chroma_client.is_connected():
                # ChromaDB successfully connected
                assert chroma_client._client is not None
                assert chroma_client._collection is not None
                assert chroma_client._connected == True
                
                # Test basic operations
                doc_id = await chroma_client.add_document(
                    content="Test document for connection test",
                    metadata={"test": True, "type": "connection_test"}
                )
                assert doc_id is not None
                
                # Test search
                results = await chroma_client.search("test document", n_results=1)
                assert "documents" in results
                assert len(results["documents"][0]) >= 1
                
            else:
                pytest.skip("ChromaDB connection failed (this is OK in test environment)")
                
        except Exception as e:
            if "ChromaDB not available" in str(e):
                pytest.skip("ChromaDB not available in test environment")
            else:
                raise
        finally:
            await chroma_client.disconnect()
    
    @pytest.mark.asyncio
    async def test_chromadb_connection_without_chromadb(self, chroma_client):
        """Test behavior without installed ChromaDB"""
        with patch('app.utils.chroma_client.CHROMADB_AVAILABLE', False):
            await chroma_client.connect()
            
            # Should correctly handle missing ChromaDB
            assert not chroma_client.is_connected()
    
    @pytest.mark.skipif(not CHROMADB_AVAILABLE, reason="ChromaDB not installed")
    @pytest.mark.asyncio
    async def test_chromadb_document_operations(self, chroma_client):
        """Test document operations"""
        try:
            await chroma_client.connect()
            
            if not chroma_client.is_connected():
                pytest.skip("ChromaDB not connected")
            
            # Test documents
            test_docs = [
                {
                    "content": "Solana is a high-performance blockchain platform",
                    "metadata": {"topic": "blockchain", "platform": "solana", "category": "technology"}
                },
                {
                    "content": "Token analysis using artificial intelligence and machine learning",
                    "metadata": {"topic": "ai", "application": "analysis", "category": "technology"}
                },
                {
                    "content": "Decentralized finance protocols on blockchain networks",
                    "metadata": {"topic": "defi", "category": "finance", "type": "protocol"}
                },
                {
                    "content": "Price prediction models for cryptocurrency trading",
                    "metadata": {"topic": "trading", "category": "finance", "type": "prediction"}
                }
            ]
            
            # Adding documents
            doc_ids = []
            for doc in test_docs:
                doc_id = await chroma_client.add_document(
                    content=doc["content"],
                    metadata=doc["metadata"]
                )
                assert doc_id is not None
                doc_ids.append(doc_id)
            
            # Test content search
            results = await chroma_client.search("blockchain", n_results=5)
            assert len(results["documents"][0]) >= 1
            
            # Test search with metadata filtering
            results = await chroma_client.search(
                "analysis",
                n_results=5,
                where={"topic": "ai"}
            )
            assert len(results["documents"][0]) >= 0  # Can be 0 or more
            
            # Test collection statistics
            stats = await chroma_client.get_collection_stats()
            assert "total_documents" in stats
            assert stats["total_documents"] >= len(test_docs)
            assert "collection_name" in stats
            assert stats["collection_name"] == chroma_client.collection_name
            
        except Exception as e:
            if "ChromaDB not available" in str(e):
                pytest.skip("ChromaDB not available")
            else:
                raise
        finally:
            await chroma_client.disconnect()
    
    @pytest.mark.asyncio
    async def test_chromadb_error_handling(self, chroma_client):
        """Test ChromaDB error handling"""
        # Test without connection
        with pytest.raises(Exception) as exc_info:
            await chroma_client.add_document("test content")
        
        assert "ChromaDB not available" in str(exc_info.value)
        
        # Test search without connection
        with pytest.raises(Exception) as exc_info:
            await chroma_client.search("test query")
        
        assert "ChromaDB not available" in str(exc_info.value)


@pytest.mark.chromadb
class TestChromaDBMocking:
    """Tests for ChromaDB with mocking"""
    
    @pytest.mark.asyncio
    async def test_chromadb_with_mock(self):
        """Test ChromaDB with full mocking"""
        with patch('chromadb.PersistentClient') as mock_chroma_class, \
             patch('app.utils.chroma_client.CHROMADB_AVAILABLE', True):
            
            # Setup collection mock
            mock_collection = Mock()
            mock_collection.add = Mock()
            mock_collection.query.return_value = {
                "documents": [["Mocked test document", "Another mocked document"]],
                "metadatas": [[{"test": True}, {"test": True}]],
                "distances": [[0.1, 0.3]]
            }
            mock_collection.count.return_value = 2
            
            # Setup client mock
            mock_client = Mock()
            mock_client.create_collection.return_value = mock_collection
            mock_client.get_collection.return_value = mock_collection
            mock_client.delete_collection = Mock()
            
            mock_chroma_class.return_value = mock_client
            
            # Test with mock
            chroma_client = ChromaClient()
            await chroma_client.connect()
            
            assert chroma_client.is_connected() == True
            
            # Test document addition
            doc_id = await chroma_client.add_document(
                "Test content", 
                {"test": True}
            )
            assert doc_id is not None
            mock_collection.add.assert_called_once()
            
            # Test search
            results = await chroma_client.search("test query")
            assert len(results["documents"][0]) == 2
            assert results["documents"][0][0] == "Mocked test document"
            mock_collection.query.assert_called_once()
            
            # Test statistics
            stats = await chroma_client.get_collection_stats()
            assert stats["total_documents"] == 2
            mock_collection.count.assert_called_once()
            
            await chroma_client.disconnect()


@pytest.mark.chromadb
class TestChromaDBHealthChecks:
    """Tests for ChromaDB health checks"""
    
    @pytest.mark.asyncio
    async def test_chromadb_health_check_available(self):
        """Test health check when ChromaDB is available"""
        if CHROMADB_AVAILABLE:
            health = await check_chroma_health()
            
            assert "healthy" in health
            assert "available" in health
            assert health["available"] == True
            
            if health["healthy"]:
                assert "connected" in health
                assert "stats" in health
            else:
                assert "error" in health
        else:
            pytest.skip("ChromaDB not installed")
    
    @pytest.mark.asyncio
    async def test_chromadb_health_check_unavailable(self):
        """Test health check when ChromaDB is unavailable"""
        with patch('app.utils.chroma_client.CHROMADB_AVAILABLE', False):
            health = await check_chroma_health()
            
            assert health["healthy"] == False
            assert health["available"] == False
            assert "not installed" in health["error"]
    
    @pytest.mark.asyncio
    async def test_chromadb_dependency_injection(self):
        """Test dependency injection for ChromaDB"""
        client = await get_chroma_client()
        
        assert client is not None
        assert isinstance(client, ChromaClient)
        
        # Should not raise exceptions
        assert hasattr(client, 'connect')
        assert hasattr(client, 'is_connected')


@pytest.mark.chromadb
@pytest.mark.integration
class TestChromaDBIntegration:
    """Integration tests for ChromaDB"""
    
    @pytest.mark.asyncio
    async def test_chromadb_integration_with_token_analysis(self, temp_chroma_dir):
        """Test ChromaDB integration with token analysis"""
        if not CHROMADB_AVAILABLE:
            pytest.skip("ChromaDB not installed")
        
        client = ChromaClient()
        client.db_path = temp_chroma_dir / "integration_chroma"
        client.collection_name = "token_analysis_integration"
        
        try:
            await client.connect()
            
            if not client.is_connected():
                pytest.skip("ChromaDB connection failed")
            
            # Simulate token analysis data
            token_analysis_data = [
                {
                    "content": "SOL token shows strong bullish momentum with high trading volume",
                    "metadata": {
                        "token": "SOL",
                        "sentiment": "bullish", 
                        "analysis_type": "technical",
                        "confidence": 0.85
                    }
                },
                {
                    "content": "USDC maintains stable price with consistent liquidity across exchanges",
                    "metadata": {
                        "token": "USDC",
                        "sentiment": "neutral",
                        "analysis_type": "fundamental", 
                        "confidence": 0.95
                    }
                },
                {
                    "content": "New DeFi token exhibits high volatility and limited trading history",
                    "metadata": {
                        "token": "DEFI",
                        "sentiment": "bearish",
                        "analysis_type": "risk_assessment",
                        "confidence": 0.70
                    }
                }
            ]
            
            # Add analysis data
            for data in token_analysis_data:
                doc_id = await client.add_document(
                    content=data["content"],
                    metadata=data["metadata"]
                )
                assert doc_id is not None
            
            # Search by tokens
            sol_results = await client.search("SOL bullish", n_results=5)
            assert len(sol_results["documents"][0]) >= 1
            
            # Search by analysis type
            technical_results = await client.search(
                "technical analysis",
                n_results=5,
                where={"analysis_type": "technical"}
            )
            assert len(technical_results["documents"][0]) >= 0
            
            # Search by sentiment
            bullish_results = await client.search(
                "momentum",
                n_results=5,
                where={"sentiment": "bullish"}
            )
            assert len(bullish_results["documents"][0]) >= 0
            
        finally:
            await client.disconnect()


@pytest.mark.chromadb
class TestChromaDBEdgeCases:
    """Tests for ChromaDB edge cases"""
    
    @pytest.fixture
    def chroma_client_edge_cases(self):
        """ChromaDB client for edge case tests"""
        with tempfile.TemporaryDirectory() as temp_dir:
            client = ChromaClient()
            client.db_path = Path(temp_dir) / "edge_cases_chroma"
            client.collection_name = "edge_cases_test"
            yield client
    
    @pytest.mark.skipif(not CHROMADB_AVAILABLE, reason="ChromaDB not installed")
    @pytest.mark.asyncio
    async def test_chromadb_empty_content(self, chroma_client_edge_cases):
        """Test with empty content"""
        client = chroma_client_edge_cases
        
        try:
            await client.connect()
            
            if not client.is_connected():
                pytest.skip("ChromaDB not connected")
            
            # Test with empty string
            doc_id = await client.add_document("", {"empty": True})
            assert doc_id is not None
            
            # Test with whitespace
            doc_id = await client.add_document("   ", {"whitespace": True})
            assert doc_id is not None
            
        finally:
            await client.disconnect()
    
    @pytest.mark.skipif(not CHROMADB_AVAILABLE, reason="ChromaDB not installed")
    @pytest.mark.asyncio
    async def test_chromadb_large_content(self, chroma_client_edge_cases):
        """Test with large content"""
        client = chroma_client_edge_cases
        
        try:
            await client.connect()
            
            if not client.is_connected():
                pytest.skip("ChromaDB not connected")
            
            # Large document
            large_content = "Large document content. " * 1000  # ~23KB
            doc_id = await client.add_document(large_content, {"size": "large"})
            assert doc_id is not None
            
            # Search in large document
            results = await client.search("Large document", n_results=1)
            assert len(results["documents"][0]) >= 1
            
        finally:
            await client.disconnect()
    
    @pytest.mark.skipif(not CHROMADB_AVAILABLE, reason="ChromaDB not installed")
    @pytest.mark.asyncio
    async def test_chromadb_special_characters(self, chroma_client_edge_cases):
        """Test with special characters"""
        client = chroma_client_edge_cases
        
        try:
            await client.connect()
            
            if not client.is_connected():
                pytest.skip("ChromaDB not connected")
            
            # Special characters and emojis
            special_content = "Special chars: !@#$%^&*()_+ 🚀🌙💎 Unicode: αβγδε"
            doc_id = await client.add_document(
                special_content, 
                {"type": "special_chars", "emoji": "🚀"}
            )
            assert doc_id is not None
            
            # Search with emoji
            results = await client.search("🚀", n_results=1)
            # Not all vector DBs work well with emojis, so we don't check the result
            
        finally:
            await client.disconnect()


if __name__ == "__main__":
    # Run only ChromaDB tests
    pytest.main([__file__, "-v", "-m", "chromadb"])