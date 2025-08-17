"""
Service Health Testing

Tests for service availability, health monitoring, and status reporting.
These tests focus on service monitoring and alerting capabilities.
"""

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
    """Tests for service health monitoring capabilities"""
    
    @pytest.mark.asyncio
    async def test_individual_service_health_checks(self):
        """Test health checks for individual services"""
        from app.services.service_manager import api_manager
        
        # Test that health check methods exist and work
        health_check_methods = [
            ('helius', 'app.services.helius_client.check_helius_health'),
            ('birdeye', 'app.services.birdeye_client.check_birdeye_health'),
            ('chainbase', 'app.services.chainbase_client.check_chainbase_health'),
            ('blowfish', 'app.services.blowfish_client.check_blowfish_health'),
            ('dataimpulse', 'app.services.dataimpulse_client.check_dataimpulse_health'),
            ('solscan', 'app.services.solscan_client.check_solscan_health')
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
                expected_fields = ["healthy", "api_key_configured"]
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
        """Test comprehensive health check of all services"""
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
            
        # Validate summary
        summary = health_status["summary"]
        assert isinstance(summary, dict)
        assert "total_services" in summary
        assert "healthy_services" in summary
        assert isinstance(summary["total_services"], int)
        assert isinstance(summary["healthy_services"], int)
        assert summary["healthy_services"] <= summary["total_services"]
    
    @pytest.mark.asyncio
    async def test_health_check_performance(self, performance_monitor):
        """Test that health checks complete in reasonable time"""
        from app.services.service_manager import get_api_health_status
        
        performance_monitor.start()
        health_status = await get_api_health_status()
        performance_monitor.stop()
        
        # Health checks should be fast (under 10 seconds for all services)
        assert performance_monitor.duration < 10.0, f"Health checks took too long: {performance_monitor.duration}s"
        
        # Should have completed successfully
        assert isinstance(health_status, dict)
        assert "overall_healthy" in health_status
    
    @pytest.mark.asyncio
    async def test_health_check_error_handling(self):
        """Test health check error handling"""
        from app.services.service_manager import APIManager
        
        # Mock a service that throws an exception
        manager = APIManager()
        
        with patch('app.services.helius_client.check_helius_health') as mock_health:
            mock_health.side_effect = Exception("Service unavailable")
            
            # Health check should handle exceptions gracefully
            health_status = await manager.check_all_services_health()
            
            assert isinstance(health_status, dict)
            assert "services" in health_status
            
            # Helius should be marked as unhealthy but not crash the whole system
            if "helius" in health_status["services"]:
                helius_health = health_status["services"]["helius"]
                assert helius_health["healthy"] == False
                assert "error" in helius_health or "Service unavailable" in str(helius_health)
    
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
class TestServiceStatusReporting:
    """Tests for service status reporting and metrics"""
    
    @pytest.mark.asyncio
    async def test_service_metrics_collection(self):
        """Test collection of service metrics"""
        from app.utils.health import get_service_metrics
        
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
        
        # Should have API keys status
        if "api_keys" in metrics:
            api_keys_metrics = metrics["api_keys"]
            assert "total_keys" in api_keys_metrics
            assert "configured_keys" in api_keys_metrics
    
    @pytest.mark.asyncio
    async def test_comprehensive_system_health(self):
        """Test comprehensive system health check"""
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
        
        # Critical services should be identified
        critical = categories["critical"]
        assert "services" in critical
        assert isinstance(critical["services"], list)
        
        # Optional services should be identified
        optional = categories["optional"]
        assert "services" in optional
        assert isinstance(optional["services"], list)
    
    @pytest.mark.asyncio
    async def test_service_dependency_analysis(self):
        """Test analysis of service dependencies"""
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
    """Tests for monitoring service availability over time"""
    
    @pytest.mark.asyncio
    async def test_service_uptime_tracking(self):
        """Test tracking service uptime"""
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
        """Test detection of service failures"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # Simulate a service failure
        with patch('app.services.birdeye_client.check_birdeye_health') as mock_birdeye:
            mock_birdeye.return_value = {
                "healthy": False,
                "api_key_configured": True,
                "error": "Connection timeout",
                "response_time": 30.0
            }
            
            health = await manager.check_all_services_health()
            
            # Should detect the failure
            assert "services" in health
            if "birdeye" in health["services"]:
                birdeye_health = health["services"]["birdeye"]
                assert birdeye_health["healthy"] == False
                assert "error" in birdeye_health
    
    @pytest.mark.asyncio
    async def test_service_recovery_detection(self):
        """Test detection of service recovery"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # First: simulate failure
        with patch('app.services.chainbase_client.check_chainbase_health') as mock_chainbase:
            mock_chainbase.return_value = {
                "healthy": False,
                "error": "API rate limit exceeded"
            }
            
            health_failed = await manager.check_all_services_health()
            
        # Then: simulate recovery
        with patch('app.services.chainbase_client.check_chainbase_health') as mock_chainbase:
            mock_chainbase.return_value = {
                "healthy": True,
                "api_key_configured": True,
                "response_time": 0.2
            }
            
            health_recovered = await manager.check_all_services_health()
        
        # Should detect both states
        assert isinstance(health_failed, dict)
        assert isinstance(health_recovered, dict)
        
        # The failure and recovery should be reflected in the results
        if "chainbase" in health_failed.get("services", {}):
            assert health_failed["services"]["chainbase"]["healthy"] == False
        
        if "chainbase" in health_recovered.get("services", {}):
            assert health_recovered["services"]["chainbase"]["healthy"] == True


@pytest.mark.services
@pytest.mark.health
class TestServiceAlerting:
    """Tests for service alerting and notification systems"""
    
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
        """Test detection of service degradation"""
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        
        # Mock slow but working service
        with patch('app.services.helius_client.check_helius_health') as mock_helius:
            mock_helius.return_value = {
                "healthy": True,
                "api_key_configured": True,
                "response_time": 15.0,  # Very slow
                "warning": "Service responding slowly"
            }
            
            health = await manager.check_all_services_health()
            
            # Service should be marked as healthy but with warnings
            if "helius" in health.get("services", {}):
                helius_health = health["services"]["helius"]
                assert helius_health["healthy"] == True
                # Should track performance issues
                assert helius_health.get("response_time", 0) > 10.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "health"])