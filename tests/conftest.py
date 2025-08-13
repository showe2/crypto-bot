import pytest
import asyncio
import tempfile
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Add the app directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

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


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on location and requirements"""
    for item in items:
        # Mark tests in integration folder
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Mark tests in unit folder
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Auto-mark slow tests
        if "slow" in item.name or "integration" in str(item.fspath):
            item.add_marker(pytest.mark.slow)


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
    from app.core.config import get_settings
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
    from app.main import app
    
    with TestClient(app) as test_client:
        yield test_client


# ==========================================
# MOCK FIXTURES
# ==========================================

@pytest.fixture
def mock_redis():
    """Mock Redis for isolated testing"""
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
    return mock_instance


@pytest.fixture
def mock_chromadb():
    """Mock ChromaDB for isolated testing"""
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
    
    return {
        'client': mock_client,
        'collection': mock_collection
    }


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


# ==========================================
# UTILITY FIXTURES
# ==========================================

@pytest.fixture
def performance_monitor():
    """Simple performance monitoring fixture"""
    import time
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.duration = 0
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
            if self.start_time:
                self.duration = self.end_time - self.start_time
            else:
                self.duration = 0
    
    return PerformanceMonitor()


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