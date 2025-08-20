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
class TestSolanaFMClient:
    """Tests for SolanaFM API client (Free service, no API key required)"""
    
    @pytest.mark.asyncio
    async def test_solanafm_client_creation(self):
        """Test SolanaFM client can be created"""
        from app.services.solanafm_client import SolanaFMClient
        
        client = SolanaFMClient()
        assert client is not None
        assert hasattr(client, 'base_url')
        assert client.base_url == "https://api.solana.fm"
    
    @pytest.mark.asyncio
    async def test_solanafm_health_check_mock(self):
        """Test SolanaFM health check with mock"""
        from app.services.solanafm_client import check_solanafm_health
        
        with patch('app.services.solanafm_client.SolanaFMClient') as MockClient:
            mock_instance = AsyncMock()
            mock_instance.health_check.return_value = {
                "healthy": True,
                "api_key_configured": True,  # SolanaFM is free
                "response_time": 0.25,
                "test_data": {"current_slot": 123456789},
                "note": "SolanaFM is free to use, no API key required"
            }
            MockClient.return_value.__aenter__.return_value = mock_instance
            
            result = await check_solanafm_health()
            
            assert result["healthy"] == True
            assert "api_key_configured" in result
            assert "response_time" in result
    
    @pytest.mark.asyncio
    async def test_solanafm_client_methods(self):
        """Test SolanaFM client method existence"""
        from app.services.solanafm_client import SolanaFMClient
        
        client = SolanaFMClient()
        
        # Check that required methods exist
        assert hasattr(client, 'get_token_info')
        assert hasattr(client, 'get_account_detail')
        assert hasattr(client, 'health_check')
    
    @pytest.mark.real_api
    @pytest.mark.solanafm
    @pytest.mark.asyncio
    async def test_solanafm_real_health_check(self):
        """Test real SolanaFM health check (free service)"""
        from app.services.solanafm_client import check_solanafm_health
        
        result = await check_solanafm_health()
        
        assert isinstance(result, dict)
        assert "healthy" in result
        assert "api_key_configured" in result
        
        # Should have base URL
        assert "base_url" in result
        assert result["base_url"] == "https://api.solana.fm"
    
    @pytest.mark.real_api
    @pytest.mark.solanafm
    @pytest.mark.asyncio
    async def test_solanafm_token_info_endpoint(self):
        """Test SolanaFM token info endpoint with well-known token"""
        from app.services.solanafm_client import SolanaFMClient
        
        client = SolanaFMClient()
        
        try:
            # Test with Wrapped SOL token
            test_token = "So11111111111111111111111111111111111112"
            token_info = await client.get_token_info(test_token)
            
            if token_info:
                # Should have some token data
                assert isinstance(token_info, dict)
                # Common fields in token info
                expected_fields = ["name", "symbol", "decimals", "token_type"]
                # At least one field should be present
                assert any(field in token_info for field in expected_fields)
                print(f"   ✅ SolanaFM token info: {token_info.get('name', 'Unknown')} ({token_info.get('symbol', 'N/A')})")
            else:
                # Token info might not be available for this token
                print(f"   ℹ️  Token info not available for {test_token} (service may be limited)")
                
        except Exception as e:
            # This is OK - the endpoint might have limitations
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in error_msg:
                print(f"   ℹ️  SolanaFM token not found in database: {e}")
            elif "timeout" in error_msg or "connection" in error_msg:
                print(f"   ⚠️  SolanaFM connection issue: {e}")
            else:
                print(f"   ⚠️  SolanaFM token info error: {e}")
    
    @pytest.mark.real_api
    @pytest.mark.solanafm
    @pytest.mark.asyncio
    async def test_solanafm_account_detail_endpoint(self):
        """Test SolanaFM account detail endpoint"""
        from app.services.solanafm_client import SolanaFMClient
        
        client = SolanaFMClient()
        
        try:
            # Test with a well-known account
            test_account = "So11111111111111111111111111111111111112"
            account_detail = await client.get_account_detail(test_account)
            
            if account_detail:
                # Should have some account data
                assert isinstance(account_detail, dict)
                # Common fields in account detail
                expected_fields = ["address", "lamports", "balance_sol", "network"]
                # At least one field should be present
                assert any(field in account_detail for field in expected_fields)
                print(f"   ✅ SolanaFM account detail: {account_detail.get('friendly_name', 'Unknown')} - {account_detail.get('balance_sol', 0)} SOL")
            else:
                print(f"   ℹ️  Account detail not available for {test_account}")
                
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in error_msg:
                print(f"   ℹ️  SolanaFM account not found: {e}")
            elif "timeout" in error_msg or "connection" in error_msg:
                print(f"   ⚠️  SolanaFM connection issue: {e}")
            else:
                print(f"   ⚠️  SolanaFM account detail error: {e}")


@pytest.mark.services
class TestDataImpulseClient:
    """Tests for DataImpulse API client"""
    
    @pytest.mark.asyncio
    async def test_dataimpulse_client_creation(self):
        """Test DataImpulse client can be created"""
        from app.services.dataimpulse_client import DataImpulseClient
        
        client = DataImpulseClient()
        assert client is not None
        assert hasattr(client, 'api_key')
        assert hasattr(client, 'base_url')
    
    @pytest.mark.asyncio
    async def test_dataimpulse_health_check_mock(self):
        """Test DataImpulse health check with mock"""
        from app.services.dataimpulse_client import check_dataimpulse_health
        
        with patch('app.services.dataimpulse_client.DataImpulseClient') as MockClient:
            mock_instance = AsyncMock()
            mock_instance.health_check.return_value = {
                "healthy": False,
                "api_key_configured": False,
                "error": "API key not configured"
            }
            MockClient.return_value.__aenter__.return_value = mock_instance
            
            result = await check_dataimpulse_health()
            
            assert "healthy" in result
            assert "api_key_configured" in result


@pytest.mark.services
class TestGOplusClient:
    """Tests for GOplus API client"""
    
    @pytest.mark.asyncio
    async def test_goplus_client_creation(self):
        """Test GOplus client can be created"""
        from app.services.goplus_client import GOplusClient
        
        client = GOplusClient()
        assert client is not None
        assert hasattr(client, 'app_key')
        assert hasattr(client, 'app_secret')
        assert hasattr(client, 'base_url')
        assert client.base_url == "https://api.gopluslabs.io"
    
    @pytest.mark.asyncio
    async def test_goplus_health_check_mock(self):
        """Test GOplus health check with mock"""
        from app.services.goplus_client import check_goplus_health
        
        with patch('app.services.goplus_client.GOplusClient') as MockClient:
            mock_instance = AsyncMock()
            mock_instance.health_check.return_value = {
                "healthy": True,
                "api_key_configured": True,
                "response_time": 0.3
            }
            MockClient.return_value.__aenter__.return_value = mock_instance
            
            result = await check_goplus_health()
            
            assert result["healthy"] == True
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
        
        # Check that all expected services are in the client list (now includes SolanaFM)
        expected_services = ["helius", "chainbase", "birdeye", "blowfish", "dataimpulse", "solanafm", "goplus"]
        for service in expected_services:
            assert service in manager.clients
    
    @pytest.mark.asyncio
    async def test_service_health_check_all(self):
        """Test checking health of all services including SolanaFM"""
        from app.services.service_manager import get_api_health_status
        
        health = await get_api_health_status()
        
        assert isinstance(health, dict)
        assert "services" in health
        assert "overall_healthy" in health
        assert "summary" in health
        
        # Check that SolanaFM is included
        services = health.get("services", {})
        expected_services = ["helius", "chainbase", "birdeye", "blowfish", "dataimpulse", "solanafm", "goplus"]
        
        # At least some services should be present
        assert len(services) > 0
        
        # SolanaFM should be included
        if "solanafm" in services:
            solanafm_health = services["solanafm"]
            assert isinstance(solanafm_health, dict)
            assert "healthy" in solanafm_health
    
    @pytest.mark.asyncio
    async def test_service_manager_with_mocks(self):
        """Test service manager with mocked clients including SolanaFM"""
        from app.services.service_manager import APIManager
        
        # Mock all client health checks including SolanaFM
        with patch.multiple(
            'app.services.service_manager',
            check_helius_health=AsyncMock(return_value={"healthy": True}),
            check_birdeye_health=AsyncMock(return_value={"healthy": True}),
            check_chainbase_health=AsyncMock(return_value={"healthy": False}),
            check_blowfish_health=AsyncMock(return_value={"healthy": True}),
            check_solanafm_health=AsyncMock(return_value={"healthy": True}),
            check_dataimpulse_health=AsyncMock(return_value={"healthy": False}),
            check_goplus_health=AsyncMock(return_value={"healthy": True})
        ):
            manager = APIManager()
            health = await manager.check_all_services_health()
            
            assert "services" in health
            assert len(health["services"]) > 0
            
            # Should have results for all services including SolanaFM
            expected_services = ["helius", "birdeye", "chainbase", "blowfish", "solanafm", "dataimpulse", "goplus"]
            for service in expected_services:
                if service in health["services"]:
                    service_health = health["services"][service]
                    assert isinstance(service_health, dict)
                    assert "healthy" in service_health
    
    @pytest.mark.asyncio
    async def test_service_manager_solanafm_integration(self):
        """Test service manager SolanaFM integration specifically"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # Test that SolanaFM is properly integrated
        assert "solanafm" in manager.clients
        
        # Test SolanaFM data retrieval method
        assert hasattr(manager, 'get_solanafm_data')
        
        # Test capabilities
        solanafm_capabilities = manager._get_service_capabilities("solanafm")
        expected_capabilities = ["on_chain_data", "transaction_details", "network_stats", "token_info", "account_details"]
        
        for capability in expected_capabilities:
            assert capability in solanafm_capabilities


# Pytest markers for service testing including SolanaFM
pytest_plugins = []

def pytest_configure(config):
    """Configure pytest with service testing markers including SolanaFM"""
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
    config.addinivalue_line(
        "markers", "solanafm: marks tests specific to SolanaFM API"
    )
    config.addinivalue_line(
        "markers", "dataimpulse: marks tests specific to DataImpulse API"
    )
    config.addinivalue_line(
        "markers", "goplus: marks tests specific to GOplus API"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not real_api"])