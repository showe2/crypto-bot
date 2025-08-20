import pytest
import asyncio
import time
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.mark.services
@pytest.mark.health
class TestBasicServiceHealth:
    """Basic service health monitoring tests"""
    
    @pytest.mark.asyncio
    async def test_service_manager_health(self):
        """Test service manager health check functionality"""
        try:
            from app.services.service_manager import get_api_health_status
            
            print("\n🔍 Testing service manager health check...")
            start_time = time.time()
            
            health_status = await get_api_health_status()
            response_time = time.time() - start_time
            
            # Validate response structure
            assert isinstance(health_status, dict)
            assert "overall_healthy" in health_status
            assert "services" in health_status
            assert "summary" in health_status
            
            services = health_status["services"]
            summary = health_status["summary"]
            
            print(f"   ✅ Health check completed ({response_time:.3f}s)")
            print(f"   📊 Total services: {summary.get('total_services', 0)}")
            print(f"   ✅ Healthy services: {summary.get('healthy_services', 0)}")
            print(f"   🔑 Configured services: {summary.get('configured_services', 0)}")
            
            # Basic validation
            assert summary["total_services"] > 0
            assert summary["healthy_services"] >= 0
            assert summary["configured_services"] >= 0
            
        except ImportError:
            pytest.skip("Service manager not available")
    
    @pytest.mark.asyncio
    async def test_individual_service_health_checks(self):
        """Test that individual service health checks work"""
        service_health_modules = [
            ("helius", "app.services.helius_client.check_helius_health"),
            ("birdeye", "app.services.birdeye_client.check_birdeye_health"),
            ("chainbase", "app.services.chainbase_client.check_chainbase_health"),
            ("solanafm", "app.services.solanafm_client.check_solanafm_health"),
            ("dexscreener", "app.services.dexscreener_client.check_dexscreener_health"),
            ("goplus", "app.services.goplus_client.check_goplus_health"),
            ("rugcheck", "app.services.rugcheck_client.check_rugcheck_health"),
        ]
        
        working_services = 0
        total_services = len(service_health_modules)
        
        for service_name, module_path in service_health_modules:
            try:
                module_path_parts = module_path.rsplit('.', 1)
                module = __import__(module_path_parts[0], fromlist=[module_path_parts[1]])
                health_check_func = getattr(module, module_path_parts[1])
                
                # Call health check
                result = await health_check_func()
                
                # Validate result structure
                assert isinstance(result, dict)
                assert "healthy" in result
                
                status = "✅ Working" if result.get("healthy") else "⚠️ Issues"
                api_key_status = "🔑 Configured" if result.get("api_key_configured") else "🔓 Not configured"
                
                print(f"   {status} {api_key_status} {service_name}")
                working_services += 1
                
            except ImportError:
                print(f"   ❌ Module not found: {service_name}")
            except Exception as e:
                print(f"   ❌ Error testing {service_name}: {str(e)}")
        
        print(f"\n   📊 Service health summary: {working_services}/{total_services} services accessible")
        
        # At least some services should be accessible
        assert working_services > 0, "No services are accessible"
    
    @pytest.mark.asyncio
    async def test_configuration_validation(self):
        """Test configuration system"""
        try:
            from app.core.config import get_settings
            
            print("\n⚙️ Testing configuration system...")
            
            settings = get_settings()
            assert settings is not None
            
            # Test basic settings
            assert hasattr(settings, 'ENV')
            assert hasattr(settings, 'DEBUG')
            assert hasattr(settings, 'PORT')
            
            print(f"   ✅ Settings loaded successfully")
            print(f"   🌍 Environment: {settings.ENV}")
            print(f"   🐛 Debug mode: {settings.DEBUG}")
            print(f"   🔌 Port: {settings.PORT}")
            
            # Test API key status
            if hasattr(settings, 'get_all_api_keys_status'):
                api_status = settings.get_all_api_keys_status()
                configured_count = sum(1 for status in api_status.values() if status.get('configured'))
                total_count = len(api_status)
                
                print(f"   🔑 API keys configured: {configured_count}/{total_count}")
                
                if configured_count == 0:
                    print(f"   💡 Configure API keys in .env file for full functionality")
                elif configured_count < total_count:
                    print(f"   💡 Some services may have limited functionality")
                else:
                    print(f"   🎉 All API keys configured")
            
        except ImportError:
            pytest.skip("Configuration system not available")
    
    @pytest.mark.asyncio
    async def test_system_components(self):
        """Test basic system components"""
        print("\n🔧 Testing system components...")
        
        try:
            # Test model imports
            from app.models.token import TokenMetadata, PriceData
            from decimal import Decimal
            
            # Test model creation
            metadata = TokenMetadata(
                mint="So11111111111111111111111111111111111112",
                name="Test Token",
                symbol="TEST"
            )
            
            price_data = PriceData(current_price=Decimal("100.0"))
            
            assert metadata.symbol == "TEST"
            assert price_data.current_price == Decimal("100.0")
            
            print(f"   ✅ Pydantic models working")
            
        except ImportError as e:
            print(f"   ❌ Model import failed: {e}")
            pytest.fail("Core models should be importable")
        
        try:
            # Test FastAPI app
            from app.main import app
            assert app is not None
            print(f"   ✅ FastAPI app available")
            
        except ImportError as e:
            print(f"   ❌ FastAPI app import failed: {e}")
            pytest.fail("FastAPI app should be importable")


@pytest.mark.services
class TestServiceConfiguration:
    """Test service configuration and setup"""
    
    @pytest.mark.asyncio
    async def test_service_client_initialization(self):
        """Test that service clients can be initialized"""
        service_clients = [
            ("HeliusClient", "app.services.helius_client.HeliusClient"),
            ("BirdeyeClient", "app.services.birdeye_client.BirdeyeClient"),
            ("ChainbaseClient", "app.services.chainbase_client.ChainbaseClient"),
            ("SolanaFMClient", "app.services.solanafm_client.SolanaFMClient"),
            ("DexScreenerClient", "app.services.dexscreener_client.DexScreenerClient"),
            ("GOplusClient", "app.services.goplus_client.GOplusClient"),
            ("RugCheckClient", "app.services.rugcheck_client.RugCheckClient"),
        ]
        
        initialized_clients = 0
        total_clients = len(service_clients)
        
        for client_name, module_path in service_clients:
            try:
                module_path_parts = module_path.rsplit('.', 1)
                module = __import__(module_path_parts[0], fromlist=[module_path_parts[1]])
                client_class = getattr(module, module_path_parts[1])
                
                # Initialize client
                client = client_class()
                assert client is not None
                
                print(f"   ✅ {client_name} initialized successfully")
                initialized_clients += 1
                
            except ImportError:
                print(f"   ❌ {client_name} module not found")
            except Exception as e:
                print(f"   ❌ {client_name} initialization failed: {str(e)}")
        
        print(f"\n   📊 Client initialization: {initialized_clients}/{total_clients} successful")
        
        # At least some clients should initialize
        assert initialized_clients > 0, "No service clients could be initialized"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])