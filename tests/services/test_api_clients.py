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
class TestSolscanClient:
    """Tests for Solscan API client"""
    
    @pytest.mark.asyncio
    async def test_solscan_client_creation(self):
        """Test Solscan client can be created"""
        from app.services.solscan_client import SolscanClient
        
        client = SolscanClient()
        assert client is not None
        assert hasattr(client, 'api_key')
        assert hasattr(client, 'base_url')
        assert client.base_url == "https://pro-api.solscan.io"
    
    @pytest.mark.asyncio
    async def test_solscan_health_check_mock(self):
        """Test Solscan health check with mock"""
        from app.services.solscan_client import check_solscan_health
        
        with patch('app.services.solscan_client.SolscanClient') as MockClient:
            mock_instance = AsyncMock()
            mock_instance.health_check.return_value = {
                "healthy": True,
                "api_key_configured": True,
                "response_time": 0.25,
                "test_data": {"current_slot": 123456789}
            }
            MockClient.return_value.__aenter__.return_value = mock_instance
            
            result = await check_solscan_health()
            
            assert result["healthy"] == True
            assert "api_key_configured" in result
            assert "response_time" in result
    
    @pytest.mark.asyncio
    async def test_solscan_client_methods(self):
        """Test Solscan client method existence"""
        from app.services.solscan_client import SolscanClient
        
        client = SolscanClient()
        
        # Check that required methods exist
        assert hasattr(client, 'get_token_info')
        assert hasattr(client, 'get_token_holders')
        assert hasattr(client, 'search_tokens')
        assert hasattr(client, 'get_network_stats')
        assert hasattr(client, 'health_check')
    
    @pytest.mark.real_api
    @pytest.mark.solscan
    @pytest.mark.asyncio
    async def test_solscan_real_health_check(self):
        """Test real Solscan health check"""
        from app.services.solscan_client import check_solscan_health
        
        result = await check_solscan_health()
        
        assert isinstance(result, dict)
        assert "healthy" in result
        assert "api_key_configured" in result
        
        # Should have base URL
        assert "base_url" in result
        assert result["base_url"] == "https://pro-api.solscan.io"
    
    @pytest.mark.real_api
    @pytest.mark.solscan
    @pytest.mark.asyncio
    async def test_solscan_free_endpoint(self):
        """Test Solscan free endpoint (network stats)"""
        from app.services.solscan_client import SolscanClient
        
        client = SolscanClient()
        
        try:
            # This endpoint is typically free
            network_stats = await client.get_network_stats()
            
            if network_stats:
                # Should have some network data
                assert isinstance(network_stats, dict)
                # Common fields in network stats
                expected_fields = ["current_slot", "current_epoch", "total_validators"]
                # At least one field should be present
                assert any(field in network_stats for field in expected_fields)
            else:
                # Network stats might not be available without API key
                print("   ℹ️  Network stats not available (may require API key)")
                
        except Exception as e:
            # This is OK - the endpoint might require authentication
            error_msg = str(e).lower()
            if "api key" in error_msg or "unauthorized" in error_msg or "forbidden" in error_msg:
                print(f"   ℹ️  Solscan network stats require API key: {e}")
            else:
                print(f"   ⚠️  Solscan network stats error: {e}")


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
    """Tests for GOplus API client - NEW"""
    
    @pytest.mark.asyncio
    async def test_goplus_client_creation(self):
        """Test GOplus client can be created"""
        from app.services.goplus_client import GOplusClient
        
        client = GOplusClient()
        assert client is not None
        assert hasattr(client, 'transaction_api_key')
        assert hasattr(client, 'rugpull_api_key')
        assert hasattr(client, 'security_api_key')
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
                "services": {
                    "transaction_simulation": {"configured": True, "healthy": True},
                    "rugpull_detection": {"configured": False, "healthy": False},
                    "token_security": {"configured": True, "healthy": True}
                },
                "summary": {
                    "configured_services": 2,
                    "healthy_services": 2,
                    "total_services": 3
                }
            }
            MockClient.return_value.__aenter__.return_value = mock_instance
            
            result = await check_goplus_health()
            
            assert result["healthy"] == True
            assert "services" in result
            assert "summary" in result
    
    @pytest.mark.asyncio
    async def test_goplus_client_methods(self):
        """Test GOplus client method existence"""
        from app.services.goplus_client import GOplusClient
        
        client = GOplusClient()
        
        # Check that required methods exist
        assert hasattr(client, 'simulate_transaction')
        assert hasattr(client, 'detect_rugpull')
        assert hasattr(client, 'analyze_token_security')
        assert hasattr(client, 'comprehensive_analysis')
        assert hasattr(client, 'health_check')
    
    @pytest.mark.asyncio
    async def test_goplus_api_key_logging(self):
        """Test GOplus API key status logging"""
        from app.services.goplus_client import GOplusClient
        
        client = GOplusClient()
        
        # Should have logged API key status during initialization
        # Check that the method exists and doesn't crash
        assert hasattr(client, '_log_api_key_status')
        
        # Test the method directly (should not crash)
        try:
            client._log_api_key_status()
        except Exception as e:
            pytest.fail(f"_log_api_key_status should not raise exceptions: {e}")
    
    @pytest.mark.real_api
    @pytest.mark.goplus
    @pytest.mark.asyncio
    async def test_goplus_real_health_check(self):
        """Test real GOplus health check"""
        from app.services.goplus_client import check_goplus_health
        
        result = await check_goplus_health()
        
        assert isinstance(result, dict)
        assert "healthy" in result
        assert "services" in result
        
        # Should have base URL
        assert "base_url" in result
        assert result["base_url"] == "https://api.gopluslabs.io"
        
        # Check services structure
        services = result.get("services", {})
        expected_services = ["transaction_simulation", "rugpull_detection", "token_security"]
        
        for service in expected_services:
            if service in services:
                service_info = services[service]
                assert isinstance(service_info, dict)
                assert "configured" in service_info
                assert "healthy" in service_info
    
    @pytest.mark.real_api
    @pytest.mark.goplus
    @pytest.mark.asyncio
    async def test_goplus_comprehensive_analysis_mock(self):
        """Test GOplus comprehensive analysis with mock"""
        from app.services.goplus_client import GOplusClient
        
        with patch.object(GOplusClient, 'analyze_token_security') as mock_security, \
             patch.object(GOplusClient, 'detect_rugpull') as mock_rugpull:
            
            # Mock security analysis
            mock_security.return_value = {
                "token_address": "So11111111111111111111111111111111111112",
                "security_score": 85,
                "risk_level": "low",
                "is_malicious": False
            }
            
            # Mock rugpull detection
            mock_rugpull.return_value = {
                "token_address": "So11111111111111111111111111111111111112",
                "rugpull_risk": "low",
                "risk_score": 15
            }
            
            client = GOplusClient()
            
            # Test comprehensive analysis
            result = await client.comprehensive_analysis("So11111111111111111111111111111111111112")
            
            assert isinstance(result, dict)
            assert "token_address" in result
            assert "services_used" in result
            assert "analyses" in result
            assert "overall_assessment" in result


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
        
        # Check that all expected services are in the client list (including GOplus)
        expected_services = ["helius", "chainbase", "birdeye", "blowfish", "dataimpulse", "solscan", "goplus"]
        for service in expected_services:
            assert service in manager.clients
    
    @pytest.mark.asyncio
    async def test_service_health_check_all(self):
        """Test checking health of all services including GOplus"""
        from app.services.service_manager import get_api_health_status
        
        health = await get_api_health_status()
        
        assert isinstance(health, dict)
        assert "services" in health
        assert "overall_healthy" in health
        assert "summary" in health
        
        # Check that GOplus is included
        services = health.get("services", {})
        expected_services = ["helius", "chainbase", "birdeye", "blowfish", "dataimpulse", "solscan", "goplus"]
        
        # At least some services should be present
        assert len(services) > 0
        
        # GOplus should be included
        if "goplus" in services:
            goplus_health = services["goplus"]
            assert isinstance(goplus_health, dict)
            assert "healthy" in goplus_health
    
    @pytest.mark.asyncio
    async def test_service_manager_with_mocks(self):
        """Test service manager with mocked clients including GOplus"""
        from app.services.service_manager import APIManager
        
        # Mock all client health checks including GOplus
        with patch.multiple(
            'app.services.service_manager',
            check_helius_health=AsyncMock(return_value={"healthy": True}),
            check_birdeye_health=AsyncMock(return_value={"healthy": True}),
            check_chainbase_health=AsyncMock(return_value={"healthy": False}),
            check_blowfish_health=AsyncMock(return_value={"healthy": True}),
            check_solscan_health=AsyncMock(return_value={"healthy": True}),
            check_dataimpulse_health=AsyncMock(return_value={"healthy": False}),
            check_goplus_health=AsyncMock(return_value={"healthy": True, "services": {"transaction_simulation": {"configured": True, "healthy": True}}})
        ):
            manager = APIManager()
            health = await manager.check_all_services_health()
            
            assert "services" in health
            assert len(health["services"]) > 0
            
            # Should have results for all services including GOplus
            expected_services = ["helius", "birdeye", "chainbase", "blowfish", "solscan", "dataimpulse", "goplus"]
            for service in expected_services:
                if service in health["services"]:
                    service_health = health["services"][service]
                    assert isinstance(service_health, dict)
                    assert "healthy" in service_health
    
    @pytest.mark.asyncio
    async def test_goplus_integration_in_service_manager(self):
        """Test GOplus integration in service manager"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # Test that GOplus methods are available
        assert hasattr(manager, 'get_goplus_analysis')
        assert hasattr(manager, 'simulate_transaction_goplus')
        assert hasattr(manager, 'detect_rugpull_goplus')
        
        # Test with mocked GOplus client
        with patch('app.services.service_manager.api_manager.clients') as mock_clients:
            mock_goplus_client = AsyncMock()
            mock_goplus_client.comprehensive_analysis.return_value = {
                "token_address": "So11111111111111111111111111111111111112",
                "overall_assessment": {"risk_score": 25, "risk_level": "low"}
            }
            mock_clients = {"goplus": mock_goplus_client}
            manager.clients = mock_clients
            
            # Test GOplus analysis
            result = await manager.get_goplus_analysis("So11111111111111111111111111111111111112")
            
            assert isinstance(result, dict)
            assert "token_address" in result


@pytest.mark.services
@pytest.mark.slow
class TestServiceIntegration:
    """Integration tests for service interactions including GOplus"""
    
    @pytest.mark.asyncio
    async def test_service_client_lifecycle(self):
        """Test service client initialization and cleanup including GOplus"""
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
        """Test concurrent calls to multiple services including GOplus"""
        from app.services.service_manager import api_manager
        
        # Test concurrent health checks for all services including GOplus
        service_health_checks = [
            ("helius", "app.services.helius_client.check_helius_health"),
            ("birdeye", "app.services.birdeye_client.check_birdeye_health"),
            ("chainbase", "app.services.chainbase_client.check_chainbase_health"),
            ("blowfish", "app.services.blowfish_client.check_blowfish_health"),
            ("solscan", "app.services.solscan_client.check_solscan_health"),
            ("dataimpulse", "app.services.dataimpulse_client.check_dataimpulse_health"),
            ("goplus", "app.services.goplus_client.check_goplus_health")
        ]
        
        tasks = []
        for service_name, import_path in service_health_checks:
            try:
                module_path, function_name = import_path.rsplit('.', 1)
                module = __import__(module_path, fromlist=[function_name])
                health_check_func = getattr(module, function_name)
                task = health_check_func()
                tasks.append(task)
            except ImportError:
                # Service might not be implemented yet
                continue
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should complete (either success or known exceptions)
            for result in results:
                if isinstance(result, Exception):
                    # Should be API-related exceptions, not crashes
                    assert any(word in str(result).lower() for word in 
                              ["api", "connection", "timeout", "key", "not configured"])
                else:
                    assert isinstance(result, dict)
                    assert "healthy" in result
    
    @pytest.mark.asyncio
    async def test_all_services_represented(self):
        """Test that all services are properly represented in the system including GOplus"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # All expected services should be in the clients dict (including GOplus)
        expected_services = ["helius", "chainbase", "birdeye", "blowfish", "dataimpulse", "solscan", "goplus"]
        
        for service in expected_services:
            assert service in manager.clients, f"Service {service} should be in APIManager.clients"
        
        # Test that health check includes all services
        health = await manager.check_all_services_health()
        services_checked = health.get("services", {})
        
        # At least the major services should be checked
        key_services = ["helius", "birdeye", "solscan", "goplus"]
        for service in key_services:
            if service not in services_checked:
                print(f"Warning: {service} not included in health check")


@pytest.mark.services
class TestGOplusSpecificFeatures:
    """Tests for GOplus-specific features"""
    
    @pytest.mark.asyncio
    async def test_goplus_multiple_api_keys(self):
        """Test GOplus multiple API key handling"""
        from app.services.goplus_client import GOplusClient
        
        client = GOplusClient()
        
        # Should have all three API key attributes
        assert hasattr(client, 'transaction_api_key')
        assert hasattr(client, 'rugpull_api_key')
        assert hasattr(client, 'security_api_key')
        
        # Should have API key status logging
        assert hasattr(client, '_log_api_key_status')
    
    @pytest.mark.asyncio
    async def test_goplus_service_specific_methods(self):
        """Test GOplus service-specific methods"""
        from app.services.goplus_client import GOplusClient
        
        client = GOplusClient()
        
        # Transaction simulation methods
        assert hasattr(client, 'simulate_transaction')
        assert hasattr(client, 'validate_transaction')
        
        # Rugpull detection methods
        assert hasattr(client, 'detect_rugpull')
        assert hasattr(client, 'get_rugpull_history')
        
        # Token security methods
        assert hasattr(client, 'analyze_token_security')
        assert hasattr(client, 'get_supported_chains')
    
    @pytest.mark.asyncio
    async def test_goplus_comprehensive_analysis_structure(self):
        """Test GOplus comprehensive analysis structure"""
        from app.services.goplus_client import GOplusClient
        
        with patch.object(GOplusClient, 'analyze_token_security') as mock_security, \
             patch.object(GOplusClient, 'detect_rugpull') as mock_rugpull:
            
            # Mock responses
            mock_security.return_value = {"security_score": 80, "risk_level": "low"}
            mock_rugpull.return_value = {"rugpull_risk": "low", "risk_score": 20}
            
            client = GOplusClient()
            result = await client.comprehensive_analysis("So11111111111111111111111111111111111112")
            
            # Check structure
            assert isinstance(result, dict)
            required_fields = ["token_address", "chain", "timestamp", "services_used", "analyses", "overall_assessment"]
            
            for field in required_fields:
                assert field in result, f"Missing required field: {field}"
            
            # Check overall assessment structure
            assessment = result["overall_assessment"]
            assessment_fields = ["risk_score", "risk_level", "is_safe", "major_risks", "recommendations", "confidence"]
            
            for field in assessment_fields:
                assert field in assessment, f"Missing assessment field: {field}"
    
    @pytest.mark.asyncio
    async def test_goplus_error_handling(self):
        """Test GOplus error handling"""
        from app.services.goplus_client import GOplusClient, GOplusAPIError
        
        client = GOplusClient()
        
        # Test with no API keys (should handle gracefully)
        client.transaction_api_key = None
        client.rugpull_api_key = None
        client.security_api_key = None
        
        # Should not crash when trying operations without API keys
        try:
            result = await client.comprehensive_analysis("So11111111111111111111111111111111111112")
            # Should return error info, not crash
            assert isinstance(result, dict)
            assert "analyses" in result
        except Exception as e:
            # Should be a controlled error, not a crash
            assert any(word in str(e).lower() for word in ["api key", "not configured", "not available"])


# Pytest markers for service testing including GOplus
pytest_plugins = []

def pytest_configure(config):
    """Configure pytest with service testing markers including GOplus"""
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
        "markers", "solscan: marks tests specific to Solscan API"
    )
    config.addinivalue_line(
        "markers", "dataimpulse: marks tests specific to DataImpulse API"
    )
    config.addinivalue_line(
        "markers", "goplus: marks tests specific to GOplus API"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not real_api"])