import pytest
import asyncio
import time
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app


@pytest.mark.integration
class TestFastAPIIntegration:
    """Integration tests for FastAPI application"""
    
    def test_app_startup_and_shutdown(self, client):
        """Test complete app lifecycle"""
        # App should start successfully with test client
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["service"] == "Solana Token Analysis AI System"
        assert data["status"] == "running"
    
    def test_health_check_endpoint_integration(self, client):
        """Test health check with real components"""
        response = client.get("/health")
        
        # Should return 200 or 503 (if services unavailable)
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "overall_status" in data
        assert "services" in data
        assert "service_categories" in data
        
        # Check that all expected services are reported
        services = data["services"]
        expected_services = ["basic_system", "file_system", "logging_system", "redis", "chromadb", "cache"]
        
        for service in expected_services:
            assert service in services
            assert "healthy" in services[service]
    
    def test_simple_health_check(self, client):
        """Test simple health check endpoint"""
        response = client.get("/health/simple")
        
        # Should work even if complex health check fails
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy"]
    
    def test_configuration_endpoint(self, client):
        """Test configuration status endpoint"""
        response = client.get("/config")
        assert response.status_code == 200
        
        data = response.json()
        required_fields = [
            "environment", "debug_mode", "host", "port",
            "api_keys_configured", "missing_critical_keys"
        ]
        
        for field in required_fields:
            assert field in data
        
        # Should have some structure in response
        assert isinstance(data["api_keys_configured"], int)
        assert isinstance(data["missing_critical_keys"], list)
    
    def test_commands_endpoint_structure(self, client):
        """Test commands reference endpoint structure"""
        response = client.get("/commands")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have command categories
        assert "basic_commands" in data
        assert "discovery_commands" in data
        assert "system_commands" in data
        
        # Each category should have commands with proper structure
        for category in ["basic_commands", "discovery_commands", "system_commands"]:
            commands = data[category]
            assert isinstance(commands, list)
            
            for command in commands:
                assert "command" in command
                assert "description" in command
                assert "method" in command
                assert "endpoint" in command
    
    def test_start_command_integration(self, client):
        """Test /start command with real system check"""
        response = client.get("/start")
        assert response.status_code == 200
        
        data = response.json()
        assert data["command"] == "start"
        assert data["system_status"] == "ready"
        assert "available_commands" in data
        assert "timestamp" in data
        
        # Should list actual available commands
        commands = data["available_commands"]
        assert isinstance(commands, list)
        assert len(commands) > 0
    
    def test_status_endpoint_integration(self, client):
        """Test system status with real configuration"""
        response = client.get("/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["system"] == "Solana Token Analysis AI System"
        assert data["version"] == "1.0.0"
        assert "configuration" in data
        assert "timestamp" in data
        
        # Configuration should reflect real settings
        config = data["configuration"]
        assert "environment" in config
        assert "debug_mode" in config
    
    def test_token_analysis_endpoints_stub(self, client):
        """Test token analysis endpoints (stub functionality)"""
        test_token = "So11111111111111111111111111111111111112"
        
        # Test tweet command
        response = client.post(f"/tweet/{test_token}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["command"] == "tweet"
        assert data["token"] == test_token
        
        # Test name command
        response = client.post(f"/name/{test_token}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["command"] == "name"
        assert data["token"] == test_token
    
    def test_discovery_endpoints_stub(self, client):
        """Test discovery endpoints (stub functionality)"""
        # Test search command
        response = client.get("/search")
        assert response.status_code == 200
        
        data = response.json()
        assert data["command"] == "search"
        
        # Test whales/dev command
        response = client.get("/kity+dev")
        assert response.status_code == 200
        
        data = response.json()
        assert data["command"] == "kity+dev"
        
        # Test listing command
        response = client.get("/listing")
        assert response.status_code == 200
        
        data = response.json()
        assert data["command"] == "listing"
    
    def test_cors_headers_integration(self, client):
        """Test CORS configuration in real app"""
        # Test preflight request
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # CORS should be configured (might return 405 for GET endpoint, that's OK)
        assert response.status_code in [200, 405]
    
    def test_request_logging_integration(self, client):
        """Test that request logging works"""
        with patch('app.main.logger') as mock_logger:
            response = client.get("/")
            assert response.status_code == 200
            
            # Should have logged the request
            # Note: In real integration, this would check actual log files
            assert mock_logger.info.called or mock_logger.log.called
    
    def test_error_handling_integration(self, client):
        """Test error handling with real error scenarios"""
        # Test 404 for non-existent endpoint
        response = client.get("/non-existent-endpoint")
        assert response.status_code == 404
        
        # Test invalid token format (should handle gracefully)
        response = client.post("/tweet/invalid-token-format")
        # Should not crash, might return error or process anyway
        assert response.status_code in [200, 400, 422, 500]
    
    @pytest.mark.slow
    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests"""
        import concurrent.futures
        
        def make_request():
            response = client.get("/")
            return response.status_code
        
        # Make multiple concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        assert all(status == 200 for status in results)
    
    def test_request_timeout_handling(self, client):
        """Test request timeout handling"""
        # Test with a normal request (should be fast)
        start_time = time.time()
        response = client.get("/")
        duration = time.time() - start_time
        
        assert response.status_code == 200
        assert duration < 5.0  # Should respond quickly
    
    def test_metrics_endpoint_integration(self, client):
        """Test metrics endpoint if available"""
        response = client.get("/metrics")
        
        # Might not be implemented yet, that's OK
        if response.status_code == 200:
            data = response.json()
            # Should have some metrics structure
            assert isinstance(data, dict)
        else:
            # Should return appropriate error
            assert response.status_code in [404, 503]
    
    def test_dashboard_endpoint_integration(self, client):
        """Test dashboard endpoint if available"""
        response = client.get("/dashboard")
        
        # Dashboard might not be available without templates
        if response.status_code == 200:
            # Should return HTML or redirect
            assert "text/html" in response.headers.get("content-type", "")
        else:
            # Should return appropriate error
            assert response.status_code in [404, 503]
            
            if response.status_code == 404:
                error_data = response.json()
                assert "Dashboard not available" in error_data.get("error", "")


@pytest.mark.integration
@pytest.mark.slow
class TestApplicationLifecycle:
    """Test complete application lifecycle"""
    
    def test_startup_with_dependencies(self):
        """Test app startup with real dependencies"""
        # Create fresh test client to trigger startup
        with TestClient(app) as client:
            # App should start successfully
            response = client.get("/health")
            assert response.status_code in [200, 503]
            
            # Should report on dependency status
            data = response.json()
            assert "services" in data
    
    def test_configuration_loading(self):
        """Test that configuration loads correctly"""
        from app.core.config import get_settings
        
        settings = get_settings()
        
        # Basic settings should be loaded
        assert settings.ENV in ["development", "staging", "production", "test"]
        assert isinstance(settings.DEBUG, bool)
        assert isinstance(settings.PORT, int)
        assert isinstance(settings.HOST, str)
    
    def test_logging_system_integration(self):
        """Test logging system in integration environment"""
        from app.core.logging import setup_logging
        
        # Should not raise exceptions
        try:
            setup_logging()
        except Exception as e:
            pytest.fail(f"Logging setup failed: {e}")
    
    def test_dependency_injection_integration(self):
        """Test dependency injection system"""
        from app.core.dependencies import get_settings_dependency
        
        # Should be able to get dependencies
        settings = get_settings_dependency()
        assert settings is not None
    
    @pytest.mark.asyncio
    async def test_async_dependencies_integration(self):
        """Test async dependencies"""
        from app.core.dependencies import get_redis_dependency, get_chroma_dependency
        
        # Should handle connection failures gracefully
        redis_client = await get_redis_dependency()
        # Should return client or None, should not raise
        assert redis_client is None or hasattr(redis_client, 'connect')
        
        chroma_client = await get_chroma_dependency()
        # Should return client or None, should not raise
        assert chroma_client is None or hasattr(chroma_client, 'connect')


@pytest.mark.integration
class TestRealWorldScenarios:
    """Test real-world usage scenarios"""
    
    def test_basic_user_workflow(self, client):
        """Test basic user workflow"""
        # 1. User checks system status
        response = client.get("/")
        assert response.status_code == 200
        
        # 2. User gets available commands
        response = client.get("/commands")
        assert response.status_code == 200
        
        # 3. User checks system health
        response = client.get("/health")
        assert response.status_code in [200, 503]
        
        # 4. User tries token analysis
        response = client.post("/tweet/So11111111111111111111111111111111111112")
        assert response.status_code == 200
    
    def test_error_recovery_scenarios(self, client):
        """Test system behavior under error conditions"""
        # Test with invalid inputs
        invalid_inputs = [
            "/tweet/",  # Missing token
            "/tweet/invalid",  # Invalid token format
            "/name/",  # Missing token
        ]
        
        for endpoint in invalid_inputs:
            response = client.post(endpoint)
            # Should handle errors gracefully, not crash
            assert response.status_code in [404, 405, 422, 500]
    
    def test_performance_baseline(self, client, performance_monitor):
        """Test basic performance expectations"""
        endpoints = ["/", "/health/simple", "/commands", "/start"]
        
        for endpoint in endpoints:
            performance_monitor.start()
            response = client.get(endpoint)
            performance_monitor.stop()
            
            assert response.status_code in [200, 503]
            # Basic endpoints should respond quickly
            assert performance_monitor.duration < 2.0