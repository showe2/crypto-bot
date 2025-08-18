import pytest
import asyncio
from unittest.mock import patch, AsyncMock, Mock
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.mark.services
class TestHeliusClient:
    """Tests for Helius API client"""
    
    @pytest.mark.asyncio
    async def test_helius_client_creation(self):
        """Test Helius client can be created"""
        from app.services.helius_client import HeliusClient
        
        client = HeliusClient()
        assert client is not None
        assert hasattr(client, 'api_key')
        assert hasattr(client, 'rpc_url')
    
    @pytest.mark.asyncio
    async def test_helius_health_check_mock(self):
        """Test Helius health check with mock"""
        from app.services.helius_client import check_helius_health
        
        with patch('app.services.helius_client.HeliusClient') as MockClient:
            mock_instance = AsyncMock()
            mock_instance.health_check.return_value = {
                "healthy": True,
                "api_key_configured": True,
                "response_time": 0.1
            }
            MockClient.return_value.__aenter__.return_value = mock_instance
            
            result = await check_helius_health()
            
            assert result["healthy"] == True
            assert "api_key_configured" in result
    
    @pytest.mark.real_api
    @pytest.mark.helius
    @pytest.mark.asyncio
    async def test_helius_real_health_check(self):
        """Test real Helius health check (requires API key)"""
        from app.services.helius_client import check_helius_health
        
        result = await check_helius_health()
        
        # Should not crash, regardless of API key availability
        assert isinstance(result, dict)
        assert "healthy" in result
        assert "api_key_configured" in result


@pytest.mark.services
class TestBirdeyeClient:
    """Tests for Birdeye API client (Fixed to avoid rate limiting)"""
    
    @pytest.mark.asyncio
    async def test_birdeye_client_creation(self):
        """Test Birdeye client can be created"""
        from app.services.birdeye_client import BirdeyeClient
        
        client = BirdeyeClient()
        assert client is not None
        assert hasattr(client, 'api_key')
        assert hasattr(client, 'base_url')
        assert client.base_url == "https://public-api.birdeye.so"
    
    @pytest.mark.asyncio
    async def test_birdeye_health_check_mock(self):
        """Test Birdeye health check with mock"""
        from app.services.birdeye_client import check_birdeye_health
        
        with patch('app.services.birdeye_client.BirdeyeClient') as MockClient:
            mock_instance = AsyncMock()
            mock_instance.health_check.return_value = {
                "healthy": True,
                "api_key_configured": True,
                "response_time": 0.2,
                "test_mode": "mocked"
            }
            MockClient.return_value.__aenter__.return_value = mock_instance
            MockClient.return_value.__aexit__.return_value = None
            
            result = await check_birdeye_health()
            
            assert result["healthy"] == True
            assert "api_key_configured" in result
    
    @pytest.mark.asyncio
    async def test_birdeye_address_validation(self):
        """Test Birdeye address validation"""
        from app.services.birdeye_client import BirdeyeClient
        
        client = BirdeyeClient()
        
        # Test valid Solana address
        valid_address = "So11111111111111111111111111111111111112"
        assert client._validate_solana_address(valid_address) == True
        
        # Test invalid addresses
        invalid_addresses = ["", "short", None, "InvalidChars!@#$%"]
        for invalid_addr in invalid_addresses:
            assert client._validate_solana_address(invalid_addr) == False
    
    @pytest.mark.real_api
    @pytest.mark.birdeye
    @pytest.mark.asyncio
    async def test_birdeye_real_health_check(self):
        """Test real Birdeye health check (safe mode - no API calls)"""
        from app.services.birdeye_client import check_birdeye_health
        
        # This uses our simplified health check that doesn't make API calls
        result = await check_birdeye_health()
        
        assert isinstance(result, dict)
        assert "healthy" in result
        assert "api_key_configured" in result
        
        # Should not fail regardless of API key status
        if result["api_key_configured"]:
            assert result["healthy"] == True  # Our simplified check
            assert "test_mode" in result
        else:
            assert result["healthy"] == False
            assert "not configured" in result.get("error", "")


@pytest.mark.services
class TestChainbaseClient:
    """Tests for Chainbase API client"""
    
    @pytest.mark.asyncio
    async def test_chainbase_client_creation(self):
        """Test Chainbase client can be created"""
        from app.services.chainbase_client import ChainbaseClient
        
        client = ChainbaseClient()
        assert client is not None
        assert hasattr(client, 'api_key')
        assert hasattr(client, 'base_url')
    
    @pytest.mark.asyncio
    async def test_chainbase_health_check_mock(self):
        """Test Chainbase health check with mock"""
        from app.services.chainbase_client import check_chainbase_health
        
        with patch('app.services.chainbase_client.ChainbaseClient') as MockClient:
            mock_instance = AsyncMock()
            mock_instance.health_check.return_value = {
                "healthy": True,
                "api_key_configured": False,
                "response_time": 0.15
            }
            MockClient.return_value.__aenter__.return_value = mock_instance
            
            result = await check_chainbase_health()
            
            assert result["healthy"] == True
            assert "api_key_configured" in result


@pytest.mark.services  
class TestBlowfishClient:
    """Tests for Blowfish API client"""
    
    @pytest.mark.asyncio
    async def test_blowfish_client_creation(self):
        """Test Blowfish client can be created"""
        from app.services.blowfish_client import BlowfishClient
        
        client = BlowfishClient()
        assert client is not None
        assert hasattr(client, 'api_key')
        assert hasattr(client, 'base_url')
    
    @pytest.mark.asyncio
    async def test_blowfish_health_check_mock(self):
        """Test Blowfish health check with mock"""
        from app.services.blowfish_client import check_blowfish_health
        
        with patch('app.services.blowfish_client.BlowfishClient') as MockClient:
            mock_instance = AsyncMock()
            mock_instance.health_check.return_value = {
                "healthy": False,
                "api_key_configured": False,
                "error": "API key not configured"
            }
            MockClient.return_value.__aenter__.return_value = mock_instance
            
            result = await check_blowfish_health()
            
            assert "healthy" in result
            assert "api_key_configured" in result


@pytest.mark.services
class TestServiceManager:
    """Tests for Service Manager that coordinates all API clients"""
    
    @pytest.mark.asyncio
    async def test_service_manager_creation(self):
        """Test service manager can be created"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        assert manager is not None
        assert hasattr(manager, 'clients')
        assert isinstance(manager.clients, dict)
    
    @pytest.mark.asyncio
    async def test_service_health_check_all(self):
        """Test checking health of all services"""
        from app.services.service_manager import get_api_health_status
        
        health = await get_api_health_status()
        
        assert isinstance(health, dict)
        assert "services" in health
        assert "overall_healthy" in health
        assert "summary" in health
    
    @pytest.mark.asyncio
    async def test_service_manager_with_mocks(self):
        """Test service manager with mocked clients"""
        from app.services.service_manager import APIManager
        
        # Mock all client health checks
        with patch.multiple(
            'app.services.service_manager',
            check_helius_health=AsyncMock(return_value={"healthy": True}),
            check_birdeye_health=AsyncMock(return_value={"healthy": True}),
            check_chainbase_health=AsyncMock(return_value={"healthy": False}),
            check_blowfish_health=AsyncMock(return_value={"healthy": True})
        ):
            manager = APIManager()
            health = await manager.check_all_services_health()
            
            assert "services" in health
            assert len(health["services"]) > 0


@pytest.mark.services
@pytest.mark.slow
class TestServiceIntegration:
    """Integration tests for service interactions"""
    
    @pytest.mark.asyncio
    async def test_service_client_lifecycle(self):
        """Test service client initialization and cleanup"""
        from app.services.service_manager import initialize_api_services, cleanup_api_services
        
        # Should not raise exceptions
        try:
            await initialize_api_services()
            await cleanup_api_services()
        except Exception as e:
            # Some services might not be available, that's OK
            assert any(word in str(e).lower() for word in ["not available", "api key", "connection"])
    
    @pytest.mark.asyncio 
    async def test_concurrent_service_calls(self):
        """Test concurrent calls to multiple services"""
        from app.services.service_manager import api_manager
        
        # Test concurrent health checks
        tasks = []
        for service in ["helius", "birdeye", "chainbase"]:
            if hasattr(api_manager, f'check_{service}_health'):
                task = getattr(api_manager, f'check_{service}_health')()
                tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should complete (either success or known exceptions)
            for result in results:
                if isinstance(result, Exception):
                    # Should be API-related exceptions, not crashes
                    assert any(word in str(result).lower() for word in 
                              ["api", "connection", "timeout", "key"])
                else:
                    assert isinstance(result, dict)


# Pytest markers for service testing
pytest_plugins = []

def pytest_configure(config):
    """Configure pytest with service testing markers"""
    config.addinivalue_line(
        "markers", "services: marks tests as service/API tests"
    )
    config.addinivalue_line(
        "markers", "real_api: marks tests that use real API calls (may cost money)"
    )
    config.addinivalue_line(
        "markers", "helius: marks tests specific to Helius API"
    )
    config.addinivalue_line(
        "markers", "birdeye: marks tests specific to Birdeye API"
    )
    config.addinivalue_line(
        "markers", "chainbase: marks tests specific to Chainbase API" 
    )
    config.addinivalue_line(
        "markers", "blowfish: marks tests specific to Blowfish API"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not real_api"])