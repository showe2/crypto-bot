import pytest
import time


@pytest.mark.integration
class TestFastAPIEndpoints:
    """Integration tests for FastAPI application"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["service"] == "Solana Token Analysis AI System"
        assert data["status"] == "running"
        assert data["version"] == "1.0.0"
    
    def test_health_check_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        
        # Should return 200 or 503 (if some services unavailable)
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "overall_status" in data
        assert "services" in data
        
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
    
    def test_config_endpoint(self, client):
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
    
    def test_commands_endpoint(self, client):
        """Test commands reference endpoint"""
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
    
    def test_start_command(self, client):
        """Test /start command"""
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
    
    def test_status_endpoint(self, client):
        """Test system status endpoint"""
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
    
    def test_token_analysis_stubs(self, client):
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
    
    def test_discovery_endpoints_stubs(self, client):
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
    
    def test_error_handling(self, client):
        """Test error handling"""
        # Test 404 for non-existent endpoint
        response = client.get("/non-existent-endpoint")
        assert response.status_code == 404
        
        # Test invalid token format (should handle gracefully)
        response = client.post("/tweet/invalid-token-format")
        # Should not crash, might return error or process anyway
        assert response.status_code in [200, 400, 422, 500]
    
    def test_performance_baseline(self, client, performance_monitor):
        """Test basic performance expectations"""
        endpoints = ["/", "/health/simple", "/commands", "/start"]
        
        for endpoint in endpoints:
            performance_monitor.start()
            response = client.get(endpoint)
            performance_monitor.stop()
            
            assert response.status_code in [200, 503]
            # Basic endpoints should respond quickly
            assert performance_monitor.duration < 5.0


@pytest.mark.integration
class TestApplicationStartup:
    """Test application startup behavior"""
    
    def test_app_startup_with_client(self, client):
        """Test app startup with test client"""
        # App should start successfully with test client
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["service"] == "Solana Token Analysis AI System"
        assert data["status"] == "running"
    
    def test_configuration_loading(self, settings):
        """Test that configuration loads correctly"""
        # Basic settings should be loaded
        assert settings.ENV in ["development", "staging", "production"]
        assert isinstance(settings.DEBUG, bool)
        assert isinstance(settings.PORT, int)
        assert isinstance(settings.HOST, str)
    
    def test_logging_system(self):
        """Test logging system initialization"""
        from app.core.logging import setup_logging
        
        # Should not raise exceptions
        try:
            setup_logging()
        except Exception as e:
            pytest.fail(f"Logging setup failed: {e}")


@pytest.mark.integration
class TestBasicWorkflow:
    """Test basic user workflow"""
    
    def test_user_workflow(self, client):
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
    
    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests"""
        import concurrent.futures
        
        def make_request():
            response = client.get("/")
            return response.status_code
        
        # Make multiple concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])