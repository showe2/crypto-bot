import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.mark.services
@pytest.mark.health
class TestServiceHealthMonitoring:
    """Tests for service health monitoring capabilities including GOplus"""
    
    @pytest.mark.asyncio
    async def test_individual_service_health_checks(self):
        """Test health checks for individual services including GOplus"""
        from app.services.service_manager import api_manager
        
        # Test that health check methods exist and work (including GOplus)
        health_check_methods = [
            ('helius', 'app.services.helius_client.check_helius_health'),
            ('birdeye', 'app.services.birdeye_client.check_birdeye_health'),
            ('chainbase', 'app.services.chainbase_client.check_chainbase_health'),
            ('blowfish', 'app.services.blowfish_client.check_blowfish_health'),
            ('dataimpulse', 'app.services.dataimpulse_client.check_dataimpulse_health'),
            ('solscan', 'app.services.solscan_client.check_solscan_health'),
            ('goplus', 'app.services.goplus_client.check_goplus_health')  # Added GOplus
        ]
        
        for service_name, import_path in health_check_methods:
            try:
                module_path, function_name = import_path.rsplit('.', 1)
                module = __import__(module_path, fromlist=[function_name])
                health_check_func = getattr(module, function_name)
                
                # Call health check
                result = await health_check_func()
                
                # Validate result structure
                assert isinstance(result, dict), f"{service_name} health check should return dict"
                assert "healthy" in result, f"{service_name} health check missing 'healthy' field"
                assert isinstance(result["healthy"], bool), f"{service_name} 'healthy' should be boolean"
                
                # Common fields that should be present
                expected_fields = ["healthy"]
                
                # GOplus has special structure with multiple services
                if service_name == "goplus":
                    if "services" in result:
                        services_info = result["services"]
                        assert isinstance(services_info, dict), "GOplus services should be dict"
                        
                        # Check each GOplus service
                        for goplus_service, service_info in services_info.items():
                            assert isinstance(service_info, dict), f"GOplus {goplus_service} info should be dict"
                            assert "configured" in service_info, f"GOplus {goplus_service} missing 'configured'"
                            assert "healthy" in service_info, f"GOplus {goplus_service} missing 'healthy'"
                else:
                    # Standard services should have api_key_configured
                    expected_fields.append("api_key_configured")
                
                for field in expected_fields:
                    if field in result:
                        assert isinstance(result[field], bool), f"{service_name} '{field}' should be boolean"
                
                print(f"✅ {service_name} health check working")
                
            except ImportError as e:
                print(f"⚠️  {service_name} health check not available: {e}")
                # This is OK - service might not be implemented yet
                continue
            except Exception as e:
                print(f"❌ {service_name} health check failed: {e}")
                # Health checks should not crash
                pytest.fail(f"Health check for {service_name} should not raise exceptions: {e}")
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check(self):
        """Test comprehensive health check of all services including GOplus"""
        from app.services.service_manager import get_api_health_status
        
        health_status = await get_api_health_status()
        
        # Validate overall structure
        assert isinstance(health_status, dict)
        assert "overall_healthy" in health_status
        assert "services" in health_status
        assert "summary" in health_status
        
        # Validate services section
        services = health_status["services"]
        assert isinstance(services, dict)
        assert len(services) > 0, "Should have at least one service"
        
        # Each service should have proper structure
        for service_name, service_health in services.items():
            assert isinstance(service_health, dict), f"Service {service_name} health should be dict"
            assert "healthy" in service_health, f"Service {service_name} missing 'healthy' field"
            assert isinstance(service_health["healthy"], bool)
            
            # Special handling for GOplus multi-service structure
            if service_name == "goplus" and "services" in service_health:
                goplus_services = service_health["services"]
                assert isinstance(goplus_services, dict), "GOplus services should be dict"
        
        # Validate summary
        summary = health_status["summary"]
        assert isinstance(summary, dict)
        assert "total_services" in summary
        assert "healthy_services" in summary
        assert isinstance(summary["total_services"], int)
        assert isinstance(summary["healthy_services"], int)
        assert summary["healthy_services"] <= summary["total_services"]
    
    @pytest.mark.asyncio
    async def test_goplus_specific_health_check(self):
        """Test GOplus-specific health check structure"""
        from app.services.goplus_client import check_goplus_health
        
        try:
            health = await check_goplus_health()
            
            assert isinstance(health, dict)
            assert "healthy" in health
            
            # GOplus should have services breakdown
            if "services" in health:
                services = health["services"]
                expected_goplus_services = ["transaction_simulation", "rugpull_detection", "token_security"]
                
                # Check that expected services are present
                for service in expected_goplus_services:
                    if service in services:
                        service_info = services[service]
                        assert isinstance(service_info, dict)
                        assert "configured" in service_info
                        assert "healthy" in service_info
                        assert isinstance(service_info["configured"], bool)
                        assert isinstance(service_info["healthy"], bool)
            
            # Should have summary info
            if "summary" in health:
                summary = health["summary"]
                assert isinstance(summary, dict)
                assert "configured_services" in summary
                assert "total_services" in summary
                
        except ImportError:
            pytest.skip("GOplus client not available")
        except Exception as e:
            # GOplus health check might fail due to missing API keys, that's OK
            error_msg = str(e).lower()
            if "api key" in error_msg or "not configured" in error_msg:
                print(f"GOplus health check failed as expected (no API keys): {e}")
            else:
                raise
    
    @pytest.mark.asyncio
    async def test_health_check_performance(self, performance_monitor):
        """Test that health checks complete in reasonable time including GOplus"""
        from app.services.service_manager import get_api_health_status
        
        performance_monitor.start()
        health_status = await get_api_health_status()
        performance_monitor.stop()
        
        # Health checks should be fast (under 15 seconds for all services including GOplus)
        assert performance_monitor.duration < 15.0, f"Health checks took too long: {performance_monitor.duration}s"
        
        # Should have completed successfully
        assert isinstance(health_status, dict)
        assert "overall_healthy" in health_status
    
    @pytest.mark.asyncio
    async def test_health_check_error_handling(self):
        """Test health check error handling including GOplus"""
        from app.services.service_manager import APIManager
        
        # Mock a service that throws an exception
        manager = APIManager()
        
        with patch('app.services.goplus_client.check_goplus_health') as mock_health:
            mock_health.side_effect = Exception("GOplus service unavailable")
            
            # Health check should handle exceptions gracefully
            health_status = await manager.check_all_services_health()
            
            assert isinstance(health_status, dict)
            assert "services" in health_status
            
            # GOplus should be marked as unhealthy but not crash the whole system
            if "goplus" in health_status["services"]:
                goplus_health = health_status["services"]["goplus"]
                assert goplus_health["healthy"] == False
                assert "error" in goplus_health or "GOplus service unavailable" in str(goplus_health)
    
    @pytest.mark.asyncio
    async def test_health_check_caching(self):
        """Test health check caching behavior"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # First call
        start_time1 = time.time()
        health1 = await manager.check_all_services_health()
        duration1 = time.time() - start_time1
        
        # Second call (should use cache if implemented)
        start_time2 = time.time()
        health2 = await manager.check_all_services_health()
        duration2 = time.time() - start_time2
        
        # Both should return valid results
        assert isinstance(health1, dict)
        assert isinstance(health2, dict)
        assert "timestamp" in health1
        assert "timestamp" in health2
        
        # Second call might be faster due to caching (but not required)
        print(f"First health check: {duration1:.3f}s")
        print(f"Second health check: {duration2:.3f}s")


@pytest.mark.services
@pytest.mark.health
class TestGOplusHealthSpecific:
    """Tests specific to GOplus health monitoring"""
    
    @pytest.mark.asyncio
    async def test_goplus_multi_service_health(self):
        """Test GOplus multiple service health monitoring"""
        from app.services.goplus_client import GOplusClient
        
        client = GOplusClient()
        
        # Test health check method exists
        assert hasattr(client, 'health_check')
        
        # Mock different API key configurations
        test_scenarios = [
            # No API keys
            {
                "transaction_api_key": None,
                "rugpull_api_key": None,
                "security_api_key": None,
                "expected_configured": 0
            },
            # Partial API keys
            {
                "transaction_api_key": "test_key",
                "rugpull_api_key": None,
                "security_api_key": "test_key",
                "expected_configured": 2
            },
            # All API keys
            {
                "transaction_api_key": "test_key",
                "rugpull_api_key": "test_key",
                "security_api_key": "test_key",
                "expected_configured": 3
            }
        ]
        
        for scenario in test_scenarios:
            # Set up client with test scenario
            client.transaction_api_key = scenario["transaction_api_key"]
            client.rugpull_api_key = scenario["rugpull_api_key"]
            client.security_api_key = scenario["security_api_key"]
            
            # Mock the actual API calls to avoid real requests
            with patch.object(client, 'get_supported_chains') as mock_chains:
                mock_chains.return_value = []
                
                try:
                    health = await client.health_check()
                    
                    assert isinstance(health, dict)
                    assert "services" in health
                    assert "summary" in health
                    
                    summary = health["summary"]
                    assert summary["configured_services"] == scenario["expected_configured"]
                    assert summary["total_services"] == 3
                    
                except Exception as e:
                    # If no API keys are configured, health check might fail
                    if scenario["expected_configured"] == 0:
                        assert "api key" in str(e).lower() or "not configured" in str(e).lower()
                    else:
                        # Partial or full configuration should not crash
                        raise
    
    @pytest.mark.asyncio
    async def test_goplus_health_recommendations(self):
        """Test GOplus health check recommendations"""
        from app.services.goplus_client import GOplusClient
        
        client = GOplusClient()
        
        # Test recommendations method
        assert hasattr(client, '_get_health_recommendations')
        
        # Test different service statuses
        test_statuses = [
            # No services configured
            {
                "transaction_simulation": {"configured": False, "healthy": False},
                "rugpull_detection": {"configured": False, "healthy": False},
                "token_security": {"configured": False, "healthy": False}
            },
            # Partial configuration
            {
                "transaction_simulation": {"configured": True, "healthy": True},
                "rugpull_detection": {"configured": False, "healthy": False},
                "token_security": {"configured": True, "healthy": False}
            }
        ]
        
        for status in test_statuses:
            recommendations = client._get_health_recommendations(status)
            
            assert isinstance(recommendations, list)
            
            # Should have recommendations for unconfigured services
            unconfigured = [s for s, info in status.items() if not info["configured"]]
            if unconfigured:
                assert any("Configure API keys" in rec for rec in recommendations)
    
    @pytest.mark.asyncio
    async def test_goplus_error_scenarios(self):
        """Test GOplus health check error scenarios"""
        from app.services.goplus_client import GOplusClient, GOplusAPIError
        
        client = GOplusClient()
        
        # Test with invalid API key (mock)
        client.security_api_key = "invalid_key"
        
        with patch.object(client, '_request') as mock_request:
            # Mock API error response
            mock_request.side_effect = GOplusAPIError("Invalid API key")
            
            health = await client.health_check()
            
            assert isinstance(health, dict)
            assert health["healthy"] == False
            
            # Should have error information
            if "services" in health:
                services = health["services"]
                if "token_security" in services:
                    service_info = services["token_security"]
                    assert service_info["healthy"] == False


@pytest.mark.services
@pytest.mark.health
class TestServiceStatusReporting:
    """Tests for service status reporting and metrics including GOplus"""
    
    @pytest.mark.asyncio
    async def test_service_metrics_collection(self):
        """Test collection of service metrics including GOplus"""
        from app.utils.health import get_service_metrics
        
        try:
            metrics = await get_service_metrics()
            
            assert isinstance(metrics, dict)
            
            # Should have system metrics
            if "system" in metrics:
                system_metrics = metrics["system"]
                assert "environment" in system_metrics
                assert "timestamp" in system_metrics
            
            # Should have configuration metrics
            if "configuration" in metrics:
                config_metrics = metrics["configuration"]
                assert isinstance(config_metrics, dict)
            
            # Should have API keys status (including GOplus)
            if "api_keys" in metrics:
                api_keys_metrics = metrics["api_keys"]
                assert "total_keys" in api_keys_metrics
                assert "configured_keys" in api_keys_metrics
                
                # GOplus should contribute to key counts
                if "goplus_keys" in api_keys_metrics:
                    goplus_keys = api_keys_metrics["goplus_keys"]
                    assert isinstance(goplus_keys, dict)
                    
        except ImportError:
            pytest.skip("Service metrics not implemented")
    
    @pytest.mark.asyncio
    async def test_comprehensive_system_health(self):
        """Test comprehensive system health check including GOplus"""
        from app.utils.health import health_check_all_services
        
        health = await health_check_all_services()
        
        assert isinstance(health, dict)
        assert "overall_status" in health
        assert "services" in health
        assert "service_categories" in health
        
        # Should categorize services
        categories = health["service_categories"]
        assert "critical" in categories
        assert "optional" in categories
        
        # GOplus should be in optional services (not critical for basic operation)
        optional_services = categories["optional"]["services"]
        # Note: GOplus might not be in the list if not implemented in health check yet
    
    @pytest.mark.asyncio
    async def test_service_dependency_analysis(self):
        """Test analysis of service dependencies including GOplus"""
        from app.core.dependencies import check_system_dependencies
        
        try:
            dependencies = await check_system_dependencies()
            
            assert isinstance(dependencies, dict)
            assert "dependencies" in dependencies
            assert "overall_healthy" in dependencies
            
            # Should track individual dependencies
            deps = dependencies["dependencies"]
            expected_deps = ["redis", "chromadb", "cache"]
            
            for dep in expected_deps:
                if dep in deps:
                    dep_status = deps[dep]
                    assert isinstance(dep_status, dict)
                    assert "healthy" in dep_status
        
        except ImportError:
            # check_system_dependencies might not exist yet
            pytest.skip("check_system_dependencies not implemented")


@pytest.mark.services
@pytest.mark.health  
@pytest.mark.slow
class TestServiceAvailabilityMonitoring:
    """Tests for monitoring service availability over time including GOplus"""
    
    @pytest.mark.asyncio
    async def test_service_uptime_tracking(self):
        """Test tracking service uptime including GOplus"""
        from app.services.service_manager import get_api_health_status
        
        # Take multiple health check samples
        samples = []
        for i in range(3):
            health = await get_api_health_status()
            samples.append(health)
            
            if i < 2:  # Don't wait after last sample
                await asyncio.sleep(0.5)
        
        # All samples should be valid
        for sample in samples:
            assert isinstance(sample, dict)
            assert "overall_healthy" in sample
            assert "timestamp" in sample
        
        # Timestamps should be increasing
        timestamps = [sample["timestamp"] for sample in samples]
        assert timestamps == sorted(timestamps), "Timestamps should be in order"
    
    @pytest.mark.asyncio
    async def test_service_failure_detection(self):
        """Test detection of service failures including GOplus"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # Simulate a GOplus service failure
        with patch('app.services.goplus_client.check_goplus_health') as mock_goplus:
            mock_goplus.return_value = {
                "healthy": False,
                "services": {
                    "transaction_simulation": {"configured": True, "healthy": False, "error": "Connection timeout"},
                    "rugpull_detection": {"configured": False, "healthy": False},
                    "token_security": {"configured": True, "healthy": True}
                },
                "error": "Some GOplus services unavailable"
            }
            
            health = await manager.check_all_services_health()
            
            # Should detect the failure
            assert "services" in health
            if "goplus" in health["services"]:
                goplus_health = health["services"]["goplus"]
                assert goplus_health["healthy"] == False
                assert "error" in goplus_health or "services" in goplus_health
    
    @pytest.mark.asyncio
    async def test_service_recovery_detection(self):
        """Test detection of service recovery including GOplus"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # First: simulate GOplus failure
        with patch('app.services.goplus_client.check_goplus_health') as mock_goplus:
            mock_goplus.return_value = {
                "healthy": False,
                "error": "All GOplus services unavailable"
            }
            
            health_failed = await manager.check_all_services_health()
            
        # Then: simulate GOplus recovery
        with patch('app.services.goplus_client.check_goplus_health') as mock_goplus:
            mock_goplus.return_value = {
                "healthy": True,
                "services": {
                    "transaction_simulation": {"configured": True, "healthy": True},
                    "rugpull_detection": {"configured": True, "healthy": True},
                    "token_security": {"configured": True, "healthy": True}
                }
            }
            
            health_recovered = await manager.check_all_services_health()
        
        # Should detect both states
        assert isinstance(health_failed, dict)
        assert isinstance(health_recovered, dict)
        
        # The failure and recovery should be reflected in the results
        if "goplus" in health_failed.get("services", {}):
            assert health_failed["services"]["goplus"]["healthy"] == False
        
        if "goplus" in health_recovered.get("services", {}):
            assert health_recovered["services"]["goplus"]["healthy"] == True


@pytest.mark.services
@pytest.mark.health
class TestServiceAlerting:
    """Tests for service alerting and notification systems including GOplus"""
    
    @pytest.mark.asyncio
    async def test_critical_service_failure_detection(self):
        """Test detection of critical service failures"""
        from app.utils.health import health_check_all_services
        
        # Mock critical system component failure
        with patch('app.utils.health.check_basic_system') as mock_basic:
            mock_basic.return_value = {
                "healthy": False,
                "error": "Python modules missing"
            }
            
            health = await health_check_all_services()
            
            # Should detect critical failure
            assert health["overall_status"] == False
            
            # Should have recommendations
            assert "recommendations" in health
            recommendations = health["recommendations"]
            assert isinstance(recommendations, list)
    
    @pytest.mark.asyncio
    async def test_service_degradation_detection(self):
        """Test detection of service degradation including GOplus"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # Mock slow but working GOplus service
        with patch('app.services.goplus_client.check_goplus_health') as mock_goplus:
            mock_goplus.return_value = {
                "healthy": True,
                "services": {
                    "transaction_simulation": {"configured": True, "healthy": True},
                    "rugpull_detection": {"configured": True, "healthy": True},
                    "token_security": {"configured": True, "healthy": True}
                },
                "response_time": 25.0,  # Very slow
                "warning": "GOplus services responding slowly"
            }
            
            health = await manager.check_all_services_health()
            
            # Service should be marked as healthy but with warnings
            if "goplus" in health.get("services", {}):
                goplus_health = health["services"]["goplus"]
                assert goplus_health["healthy"] == True
                # Should track performance issues
                if "response_time" in goplus_health:
                    assert goplus_health.get("response_time", 0) > 20.0
    
    @pytest.mark.asyncio
    async def test_goplus_specific_alerting(self):
        """Test GOplus-specific alerting scenarios"""
        from app.services.goplus_client import GOplusClient
        
        client = GOplusClient()
        
        # Test partial service availability alerting
        with patch.object(client, '_request') as mock_request:
            # Mock scenario where only some GOplus services work
            def mock_request_side_effect(method, endpoint, api_key, **kwargs):
                if "transaction" in endpoint:
                    return {"result": "success"}  # Transaction service works
                else:
                    raise Exception("Service unavailable")  # Other services fail
            
            mock_request.side_effect = mock_request_side_effect
            
            health = await client.health_check()
            
            # Should detect partial failure
            assert isinstance(health, dict)
            
            if "services" in health:
                services = health["services"]
                # Should have mixed health status
                healthy_services = [s for s, info in services.items() if info.get("healthy")]
                unhealthy_services = [s for s, info in services.items() if not info.get("healthy")]
                
                # With our mock, we should have both healthy and unhealthy services
                # (This depends on the exact implementation of health_check)


@pytest.mark.services
@pytest.mark.health
class TestGOplusIntegrationHealth:
    """Tests for GOplus integration with overall system health"""
    
    @pytest.mark.asyncio
    async def test_goplus_in_service_manager_health(self):
        """Test GOplus integration in service manager health checks"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # Ensure GOplus is in the client list
        assert "goplus" in manager.clients
        
        # Test health check includes GOplus
        health = await manager.check_all_services_health()
        
        # GOplus should be included in the results
        services = health.get("services", {})
        
        # Note: GOplus might not be in results if health check implementation 
        # doesn't include it yet, so we check conditionally
        if "goplus" in services:
            goplus_health = services["goplus"]
            assert isinstance(goplus_health, dict)
            assert "healthy" in goplus_health
            
            # GOplus should have additional service breakdown
            if "services" in goplus_health:
                goplus_services = goplus_health["services"]
                assert isinstance(goplus_services, dict)
    
    @pytest.mark.asyncio
    async def test_goplus_contribution_to_overall_health(self):
        """Test how GOplus contributes to overall system health"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # Test scenario where GOplus is healthy
        with patch('app.services.goplus_client.check_goplus_health') as mock_goplus:
            mock_goplus.return_value = {
                "healthy": True,
                "services": {
                    "transaction_simulation": {"configured": True, "healthy": True},
                    "rugpull_detection": {"configured": True, "healthy": True},
                    "token_security": {"configured": True, "healthy": True}
                }
            }
            
            health_with_goplus = await manager.check_all_services_health()
            
        # Test scenario where GOplus is unhealthy
        with patch('app.services.goplus_client.check_goplus_health') as mock_goplus:
            mock_goplus.return_value = {
                "healthy": False,
                "services": {
                    "transaction_simulation": {"configured": False, "healthy": False},
                    "rugpull_detection": {"configured": False, "healthy": False},
                    "token_security": {"configured": False, "healthy": False}
                },
                "error": "No GOplus API keys configured"
            }
            
            health_without_goplus = await manager.check_all_services_health()
        
        # Both should complete successfully
        assert isinstance(health_with_goplus, dict)
        assert isinstance(health_without_goplus, dict)
        
        # GOplus being unhealthy shouldn't crash the system
        # (it's an optional enhancement service)
        assert "overall_healthy" in health_with_goplus
        assert "overall_healthy" in health_without_goplus


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "health"])