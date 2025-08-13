import pytest
import asyncio
import tempfile
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Add the app directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app
from app.core.config import get_settings
from app.utils.redis_client import RedisClient
from app.utils.cache import CacheManager

# ChromaDB imports with error handling
try:
    from app.utils.chroma_client import ChromaClient
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    ChromaClient = None
    chromadb = None


# ==========================================
# PYTEST CONFIGURATION
# ==========================================

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "redis: marks tests that require Redis"
    )
    config.addinivalue_line(
        "markers", "chromadb: marks tests that require ChromaDB"
    )
    config.addinivalue_line(
        "markers", "api: marks tests that test API endpoints"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on location and requirements"""
    for item in items:
        # Mark tests in integration folder
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Mark tests in unit folder
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Auto-mark API tests
        if "test_api" in item.name or "test_endpoint" in item.name:
            item.add_marker(pytest.mark.api)
        
        # Auto-mark slow tests
        if "slow" in item.name or "integration" in str(item.fspath):
            item.add_marker(pytest.mark.slow)
        
        # Auto-mark ChromaDB tests
        if "chromadb" in item.name.lower() or "chroma" in str(item.fspath).lower():
            item.add_marker(pytest.mark.chromadb)


# ==========================================
# CORE FIXTURES
# ==========================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def settings():
    """Get application settings"""
    return get_settings()


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


# ==========================================
# FASTAPI FIXTURES
# ==========================================

@pytest.fixture
def client():
    """Create FastAPI test client"""
    from fastapi.testclient import TestClient
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_dependencies():
    """Mock external dependencies for FastAPI tests"""
    with patch('app.core.dependencies.startup_dependencies') as mock_startup, \
         patch('app.core.dependencies.shutdown_dependencies') as mock_shutdown, \
         patch('app.utils.health.health_check_all_services') as mock_health:
        
        # Configure mocks
        mock_startup.return_value = AsyncMock()
        mock_shutdown.return_value = AsyncMock()
        mock_health.return_value = {
            "overall_status": True,
            "services": {
                "basic_system": {"healthy": True},
                "file_system": {"healthy": True},
                "logging_system": {"healthy": True},
                "redis": {"healthy": True, "optional": True},
                "chromadb": {"healthy": True, "optional": True},
                "cache": {"healthy": True}
            },
            "service_categories": {
                "optional": {
                    "healthy_count": 2,
                    "total_count": 2
                }
            },
            "recommendations": []
        }
        
        yield {
            'startup': mock_startup,
            'shutdown': mock_shutdown,
            'health': mock_health
        }


# ==========================================
# REDIS FIXTURES
# ==========================================

@pytest.fixture
async def redis_client():
    """Create Redis client for testing"""
    client = RedisClient()
    await client.connect()
    yield client
    await client.disconnect()


@pytest.fixture
def mock_redis():
    """Mock Redis for isolated testing"""
    with patch('redis.asyncio.Redis') as mock_redis_class:
        mock_instance = AsyncMock()
        mock_instance.ping.return_value = True
        mock_instance.set.return_value = True
        mock_instance.get.return_value = "test_value"
        mock_instance.delete.return_value = 1
        mock_instance.exists.return_value = 1
        mock_instance.info.return_value = {
            'redis_version': '7.0.0',
            'used_memory_human': '1M',
            'connected_clients': 1,
            'keyspace_hits': 100,
            'keyspace_misses': 10
        }
        
        mock_redis_class.return_value = mock_instance
        yield mock_instance


# ==========================================
# CHROMADB FIXTURES
# ==========================================

@pytest.fixture
def temp_chroma_dir():
    """Temporary directory specifically for ChromaDB"""
    with tempfile.TemporaryDirectory(prefix="chromadb_test_") as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
async def chroma_client(temp_chroma_dir):
    """Create ChromaDB client for testing"""
    if not CHROMADB_AVAILABLE:
        pytest.skip("ChromaDB not installed - install with: pip install chromadb sentence-transformers")
    
    client = ChromaClient()
    client.db_path = temp_chroma_dir / "test_chroma"
    client.collection_name = f"test_collection_{id(client)}"
    
    yield client
    
    # Cleanup
    try:
        await client.disconnect()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
async def connected_chroma_client(chroma_client):
    """ChromaDB client that's already connected (or skipped if unavailable)"""
    try:
        await chroma_client.connect()
        
        if not chroma_client.is_connected():
            pytest.skip("ChromaDB connection failed (this is OK in test environment)")
        
        yield chroma_client
        
    except Exception as e:
        if "ChromaDB not available" in str(e) or "not installed" in str(e):
            pytest.skip("ChromaDB not available in test environment")
        else:
            raise
    finally:
        try:
            await chroma_client.disconnect()
        except Exception:
            pass


@pytest.fixture
def mock_chromadb():
    """Mock ChromaDB for isolated testing"""
    with patch('chromadb.PersistentClient') as mock_chroma_class, \
         patch('app.utils.chroma_client.CHROMADB_AVAILABLE', True):
        
        # Mock collection
        mock_collection = Mock()
        mock_collection.add = Mock()
        mock_collection.query.return_value = {
            "documents": [["test document"]],
            "metadatas": [[{"test": True}]],
            "distances": [[0.1]]
        }
        mock_collection.count.return_value = 1
        
        # Mock client
        mock_client = Mock()
        mock_client.create_collection.return_value = mock_collection
        mock_client.get_collection.return_value = mock_collection
        mock_client.delete_collection = Mock()
        
        mock_chroma_class.return_value = mock_client
        yield {
            'client': mock_client,
            'collection': mock_collection
        }


# ==========================================
# CACHE FIXTURES
# ==========================================

@pytest.fixture
async def cache_manager():
    """Create cache manager for testing"""
    cache = CacheManager()
    yield cache


# ==========================================
# MODEL FIXTURES
# ==========================================

@pytest.fixture
def sample_token_metadata():
    """Sample token metadata for testing"""
    from app.models.token import TokenMetadata
    return TokenMetadata(
        mint="So11111111111111111111111111111111111112",
        name="Wrapped SOL",
        symbol="WSOL",
        decimals=9,
        description="Wrapped Solana token"
    )


@pytest.fixture
def sample_price_data():
    """Sample price data for testing"""
    from app.models.token import PriceData
    from decimal import Decimal
    return PriceData(
        current_price=Decimal("100.50"),
        price_change_24h=Decimal("5.2"),
        volume_24h=Decimal("1000000"),
        market_cap=Decimal("50000000")
    )


@pytest.fixture
def validator():
    """Get Solana address validator"""
    from app.utils.validation import SolanaAddressValidator
    return SolanaAddressValidator()


# ==========================================
# CLEANUP
# ==========================================

@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Automatically cleanup test data after each test"""
    yield
    
    # Clean up any test files
    test_files = [
        "test_report.json",
        "test_*.log"
    ]
    
    for pattern in test_files:
        for file in Path(".").glob(pattern):
            try:
                file.unlink()
            except Exception:
                pass