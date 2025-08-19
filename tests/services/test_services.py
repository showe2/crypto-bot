import asyncio
import aiohttp
import json
import time
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class TestMode(Enum):
    """Testing modes from safest to most expensive"""
    MOCK_ONLY = "mock"           # No real API calls
    FREE_APIS = "free"           # Only free APIs  
    LIMITED_PAID = "limited"     # Minimal paid API calls
    FULL_TESTING = "full"        # All APIs (use carefully!)

@dataclass
class TestResult:
    """Test result container"""
    service: str
    endpoint: str
    success: bool
    response_time: float
    cost_estimate: str
    error: Optional[str] = None
    data_size: int = 0

class SafeServiceTester:
    """Safe service tester that prioritizes cost efficiency"""
    
    def __init__(self, base_url: str = "http://localhost:8000", mode: TestMode = TestMode.MOCK_ONLY):
        self.base_url = base_url
        self.mode = mode
        self.results: List[TestResult] = []
        self.total_estimated_cost = 0.0
        
        # Test tokens (well-known, widely supported)
        self.safe_test_tokens = [
            "So11111111111111111111111111111111111112",  # Wrapped SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        ]
        
        # API cost estimates (USD per 1000 calls - approximate)
        self.api_costs = {
            "dexscreener": 0.0,      # Free
            "solana_rpc": 0.0,       # Free tier available
            "helius": 0.10,          # ~$0.10 per 1000 calls
            "birdeye": 0.25,         # ~$0.25 per 1000 calls  
            "chainbase": 0.50,       # ~$0.50 per 1000 calls
            "blowfish": 2.00,        # ~$2.00 per 1000 scans
            "dataimpulse": 1.00,     # ~$1.00 per 1000 calls
            "solscan": 0.05          # ~$0.05 per 1000 calls (pro tier)
        }
    
    async def test_system_health(self) -> TestResult:
        """Test system health (no external API calls)"""
        print("🏥 Testing system health...")
        
        start_time = time.time()
        
        # In mock mode, if server isn't running, test system components instead
        if self.mode == TestMode.MOCK_ONLY:
            try:
                # Quick server check first
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=2)) as response:
                        data = await response.json()
                        response_time = time.time() - start_time
                        
                        result = TestResult(
                            service="system",
                            endpoint="/health",
                            success=response.status in [200, 503],
                            response_time=response_time,
                            cost_estimate="FREE",
                            data_size=len(str(data))
                        )
                        
                        print(f"   ✅ Server health check: {response.status} ({response_time:.2f}s)")
                        return result
                        
            except (aiohttp.ClientConnectorError, asyncio.TimeoutError):
                # Server not running - test system components instead
                print("   🔧 Server not running, testing system components...")
                return await self._test_system_components()
        
        # For non-mock modes, require server
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    data = await response.json()
                    response_time = time.time() - start_time
                    
                    result = TestResult(
                        service="system",
                        endpoint="/health",
                        success=response.status in [200, 503],
                        response_time=response_time,
                        cost_estimate="FREE",
                        data_size=len(str(data))
                    )
                    
                    print(f"   ✅ Health check: {response.status} ({response_time:.2f}s)")
                    return result
                    
        except aiohttp.ClientConnectorError:
            response_time = time.time() - start_time
            print(f"   ⚠️ Server not running at {self.base_url}")
            return TestResult(
                service="system",
                endpoint="/health", 
                success=False,
                response_time=response_time,
                cost_estimate="FREE",
                error=f"Server not running at {self.base_url}. Start with: python -m app.main"
            )
        except Exception as e:
            return TestResult(
                service="system",
                endpoint="/health", 
                success=False,
                response_time=time.time() - start_time,
                cost_estimate="FREE",
                error=str(e)
            )
    
    async def _test_system_components(self) -> TestResult:
        """Test system components when server is not running"""
        start_time = time.time()
        
        try:
            # Test imports
            import sys
            from pathlib import Path
            
            # Add project root to path for imports
            project_root = Path(__file__).parent.parent.parent
            sys.path.insert(0, str(project_root))
            
            # Test basic imports
            from app.core.config import get_settings
            from app.models.token import TokenMetadata
            
            # Test configuration
            settings = get_settings()
            assert settings is not None
            
            # Test model creation
            metadata = TokenMetadata(
                mint="So11111111111111111111111111111111111112",
                name="Test Token",
                symbol="TEST"
            )
            assert metadata.symbol == "TEST"
            
            response_time = time.time() - start_time
            
            print(f"   ✅ System components test passed ({response_time:.2f}s)")
            
            return TestResult(
                service="system",
                endpoint="/components",
                success=True,
                response_time=response_time,
                cost_estimate="FREE",
                data_size=0
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            print(f"   ❌ System components test failed ({response_time:.2f}s)")
            
            return TestResult(
                service="system",
                endpoint="/components",
                success=False,
                response_time=response_time,
                cost_estimate="FREE",
                error=f"System components test failed: {str(e)}"
            )
    
    async def test_free_apis(self) -> List[TestResult]:
        """Test free APIs only"""
        print("🆓 Testing free APIs...")
        results = []
        
        # Test DexScreener (free, no auth required)
        if self.mode in [TestMode.FREE_APIS, TestMode.LIMITED_PAID, TestMode.FULL_TESTING]:
            result = await self._test_dexscreener()
            results.append(result)
            
            # Test Solscan v2.0 (has free tier and pro tier)
            result = await self._test_solscan_v2()
            results.append(result)
        
        # Test public configuration endpoints
        result = await self._test_config_endpoint()
        results.append(result)
        
        return results
    
    async def _test_dexscreener(self) -> TestResult:
        """Test DexScreener API (completely free)"""
        print("   🔍 Testing DexScreener API...")
        
        start_time = time.time()
        try:
            # DexScreener is free and doesn't require API keys
            url = f"https://api.dexscreener.com/latest/dex/tokens/{self.safe_test_tokens[0]}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()
                    response_time = time.time() - start_time
                    
                    return TestResult(
                        service="dexscreener",
                        endpoint="/dex/tokens", 
                        success=response.status == 200,
                        response_time=response_time,
                        cost_estimate="FREE",
                        data_size=len(str(data))
                    )
                    
        except Exception as e:
            return TestResult(
                service="dexscreener",
                endpoint="/dex/tokens",
                success=False, 
                response_time=time.time() - start_time,
                cost_estimate="FREE",
                error=str(e)
            )
    
    async def _test_solscan_v2(self) -> TestResult:
        """Test Solscan v2.0 API (UPDATED for new endpoints)"""
        print("   📊 Testing Solscan v2.0 API...")
        
        start_time = time.time()
        
        # Try to get API key from environment with better loading
        import os
        from pathlib import Path
        
        # Load .env file if it exists
        api_key = os.getenv('SOLSCAN_API_KEY')
        
        if not api_key:
            # Try to load from .env file manually
            try:
                env_file = Path.cwd() / '.env'
                if env_file.exists():
                    with open(env_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('SOLSCAN_API_KEY=') and not line.startswith('#'):
                                api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                                break
            except Exception as e:
                print(f"   ⚠️ Error reading .env file: {e}")
        
        if not api_key:
            # Test without API key first (some v2.0 endpoints might be free)
            result = await self._test_solscan_v2_no_auth(start_time)
            if result.success:
                return result
            
            # If no auth fails, return helpful message
            response_time = time.time() - start_time
            print("   ⚠️ Solscan v2.0 requires API key for most endpoints")
            return TestResult(
                service="solscan",
                endpoint="/v2.0/auth_required",
                success=False,
                response_time=response_time,
                cost_estimate="FREE",
                error="API key not found. Get key from https://pro.solscan.io and set SOLSCAN_API_KEY in .env"
            )
        
        # Test with API key using v2.0 endpoints
        return await self._test_solscan_v2_with_auth(api_key, start_time)
    
    async def _test_solscan_v2_no_auth(self, start_time: float) -> TestResult:
        """Test Solscan v2.0 endpoints that might work without API key"""
        
        # v2.0 public endpoints to try
        public_endpoints = [
            ("https://pro-api.solscan.io/v2.0/chaininfo", "/v2.0/chaininfo"),
            # Note: Most v2.0 endpoints require authentication
        ]
        
        for full_url, endpoint_name in public_endpoints:
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Accept": "application/json",
                        "User-Agent": "Solana-Token-Analysis/1.0"
                    }
                    
                    async with session.get(full_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as response:
                        response_time = time.time() - start_time
                        
                        if response.status == 200:
                            try:
                                content_type = response.headers.get('content-type', '').lower()
                                if 'application/json' in content_type:
                                    data = await response.json()
                                    
                                    # Check v2.0 API response format
                                    if isinstance(data, dict) and data.get("success") != False:
                                        print(f"   ✅ Solscan v2.0 public endpoint {endpoint_name} working ({response_time:.2f}s)")
                                        return TestResult(
                                            service="solscan",
                                            endpoint=endpoint_name,
                                            success=True,
                                            response_time=response_time,
                                            cost_estimate="FREE",
                                            data_size=len(str(data))
                                        )
                            except Exception:
                                pass
                        elif response.status == 401:
                            # Expected for most v2.0 endpoints
                            print(f"   ⚠️ Solscan v2.0 {endpoint_name} requires authentication")
                            continue
            except Exception:
                continue
        
        # No public endpoints worked
        return TestResult(
            service="solscan",
            endpoint="/v2.0/public",
            success=False,
            response_time=time.time() - start_time,
            cost_estimate="FREE",
            error="v2.0 API requires authentication for most endpoints"
        )
    
    async def _test_solscan_v2_with_auth(self, api_key: str, start_time: float) -> TestResult:
        """Test Solscan v2.0 with API key authentication (UPDATED)"""
        
        # v2.0 API endpoints to test
        auth_endpoints = [
            ("https://pro-api.solscan.io/v2.0/chaininfo", "/v2.0/chaininfo"),
            (f"https://pro-api.solscan.io/v2.0/token/{self.safe_test_tokens[0]}", "/v2.0/token/{token}"),
            (f"https://pro-api.solscan.io/v2.0/account/{self.safe_test_tokens[0]}", "/v2.0/account/{account}"),
        ]
        
        for full_url, endpoint_name in auth_endpoints:
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Accept": "application/json",
                        "User-Agent": "Solana-Token-Analysis/1.0",
                        "Authorization": f"Bearer {api_key}"  # v2.0 uses Bearer token
                    }
                    
                    async with session.get(full_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        response_time = time.time() - start_time
                        
                        if response.status == 200:
                            try:
                                content_type = response.headers.get('content-type', '').lower()
                                if 'application/json' in content_type:
                                    data = await response.json()
                                    
                                    # Check v2.0 API response format
                                    if isinstance(data, dict):
                                        if data.get("success") == False:
                                            error_msg = data.get("error", "API returned success: false")
                                            print(f"   ⚠️ Solscan v2.0 {endpoint_name} API error: {error_msg}")
                                            return TestResult(
                                                service="solscan",
                                                endpoint=endpoint_name,
                                                success=False,
                                                response_time=response_time,
                                                cost_estimate="$0.001",
                                                error=f"API error: {error_msg}"
                                            )
                                        else:
                                            print(f"   ✅ Solscan v2.0 {endpoint_name} working ({response_time:.2f}s)")
                                            return TestResult(
                                                service="solscan",
                                                endpoint=endpoint_name,
                                                success=True,
                                                response_time=response_time,
                                                cost_estimate="$0.001",  # Minimal cost for v2.0 API call
                                                data_size=len(str(data))
                                            )
                            except Exception as parse_error:
                                print(f"   ⚠️ Solscan v2.0 {endpoint_name} auth success but parsing failed")
                                return TestResult(
                                    service="solscan",
                                    endpoint=endpoint_name,
                                    success=True,
                                    response_time=response_time,
                                    cost_estimate="$0.001",
                                    error=f"Auth success, parse error: {str(parse_error)}"
                                )
                        
                        elif response.status == 401:
                            error_text = await response.text()
                            print(f"   ❌ Solscan v2.0 {endpoint_name} - Invalid API key")
                            return TestResult(
                                service="solscan",
                                endpoint=endpoint_name,
                                success=False,
                                response_time=response_time,
                                cost_estimate="FREE",
                                error=f"Invalid API key. Check your Solscan Pro account: {error_text[:100]}"
                            )
                        
                        elif response.status == 403:
                            print(f"   ❌ Solscan v2.0 {endpoint_name} - Access forbidden")
                            return TestResult(
                                service="solscan",
                                endpoint=endpoint_name,
                                success=False,
                                response_time=response_time,
                                cost_estimate="FREE",
                                error="Access forbidden. API key might lack v2.0 permissions"
                            )
                        
                        elif response.status == 429:
                            print(f"   ⚠️ Solscan v2.0 {endpoint_name} - Rate limited")
                            return TestResult(
                                service="solscan",
                                endpoint=endpoint_name,
                                success=False,
                                response_time=response_time,
                                cost_estimate="FREE",
                                error="Rate limited. Slow down API requests"
                            )
                        
                        else:
                            error_text = await response.text()
                            return TestResult(
                                service="solscan",
                                endpoint=endpoint_name,
                                success=False,
                                response_time=response_time,
                                cost_estimate="FREE",
                                error=f"HTTP {response.status}: {error_text[:100]}"
                            )
                            
            except asyncio.TimeoutError:
                continue
            except aiohttp.ClientConnectorError:
                continue
            except Exception as e:
                continue
        
        # All auth endpoints failed
        response_time = time.time() - start_time
        print(f"   ❌ All Solscan v2.0 auth endpoints failed ({response_time:.2f}s)")
        
        return TestResult(
            service="solscan",
            endpoint="/v2.0/auth_endpoints",
            success=False,
            response_time=response_time,
            cost_estimate="FREE",
            error="All v2.0 authenticated endpoints failed. Check API key validity and v2.0 access"
        )
    
    async def _test_config_endpoint(self) -> TestResult:
        """Test configuration endpoint (free, internal)"""
        print("   ⚙️ Testing configuration endpoint...")
        
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/config", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    data = await response.json()
                    response_time = time.time() - start_time
                    
                    return TestResult(
                        service="system",
                        endpoint="/config",
                        success=response.status == 200,
                        response_time=response_time,
                        cost_estimate="FREE",
                        data_size=len(str(data))
                    )
                    
        except aiohttp.ClientConnectorError:
            response_time = time.time() - start_time
            print(f"   ⚠️ Server not running at {self.base_url}")
            return TestResult(
                service="system", 
                endpoint="/config",
                success=False,
                response_time=response_time,
                cost_estimate="FREE",
                error=f"Server not running at {self.base_url}. Start with: python -m app.main"
            )
        except Exception as e:
            return TestResult(
                service="system", 
                endpoint="/config",
                success=False,
                response_time=time.time() - start_time,
                cost_estimate="FREE",
                error=str(e)
            )
    
    async def test_service_clients(self) -> List[TestResult]:
        """Test service clients with controlled API usage"""
        print("🔌 Testing service clients...")
        results = []
        
        if self.mode in [TestMode.LIMITED_PAID, TestMode.FULL_TESTING]:
            print("   ⚠️ WARNING: This will test paid API clients!")
            
            # Ask for confirmation
            if not self._confirm_paid_testing():
                print("   ❌ Service client testing cancelled")
                return results
            
            # Test API health endpoints (usually free or very cheap)
            for service_name in ["helius", "birdeye", "chainbase", "blowfish", "solscan", "dataimpulse"]:
                result = await self._test_service_health(service_name)
                results.append(result)
        
        return results
    
    async def _test_service_health(self, service_name: str) -> TestResult:
        """Test individual service health with improved error handling"""
        print(f"   🔍 Testing {service_name} service health...")
        
        start_time = time.time()
        try:
            # Try to import and test the service client
            if service_name == "helius":
                from app.services.helius_client import check_helius_health
                health_data = await check_helius_health()
            elif service_name == "birdeye":
                from app.services.birdeye_client import check_birdeye_health  
                health_data = await check_birdeye_health()
            elif service_name == "chainbase":
                from app.services.chainbase_client import check_chainbase_health
                health_data = await check_chainbase_health()
            elif service_name == "blowfish":
                from app.services.blowfish_client import check_blowfish_health
                health_data = await check_blowfish_health()
            elif service_name == "solscan":
                from app.services.solscan_client import check_solscan_health
                health_data = await check_solscan_health()
            elif service_name == "dataimpulse":
                from app.services.dataimpulse_client import check_dataimpulse_health
                health_data = await check_dataimpulse_health()
            else:
                raise ValueError(f"Unknown service: {service_name}")
            
            response_time = time.time() - start_time
            success = health_data.get("healthy", False)
            
            # Check for specific API key issues
            api_key_configured = health_data.get("api_key_configured", False)
            error_message = health_data.get("error", "")
            
            # Determine cost estimate
            if not api_key_configured:
                cost_estimate = "FREE"  # No API calls made
            elif "invalid" in error_message.lower() or "suspended" in error_message.lower():
                cost_estimate = "FREE"  # Failed before making billable calls
            else:
                cost_estimate = f"${self.api_costs.get(service_name, 0.001):.3f}"
            
            # Create detailed error message for API key issues
            if not success and not api_key_configured:
                error = f"API key not configured. Set {service_name.upper()}_API_KEY in .env file"
            elif not success and "invalid" in error_message.lower():
                error = f"API key invalid or suspended. Check your {service_name} account"
            elif not success and "permissions" in error_message.lower():
                error = f"API key lacks permissions. Upgrade your {service_name} plan"
            else:
                error = health_data.get("error")
            
            # Special handling for Solscan v2.0
            if service_name == "solscan" and success:
                api_version = health_data.get("api_version", "unknown")
                if api_version == "v2.0":
                    print(f"   ✅ Solscan v2.0 API confirmed working")
                    cost_estimate = "$0.001"  # v2.0 API calls have minimal cost
            
            return TestResult(
                service=service_name,
                endpoint="health_check",
                success=success,
                response_time=response_time,
                cost_estimate=cost_estimate,
                data_size=len(str(health_data)),
                error=error
            )
            
        except Exception as e:
            return TestResult(
                service=service_name,
                endpoint="health_check",
                success=False,
                response_time=time.time() - start_time,
                cost_estimate="FREE",
                error=f"Health check failed: {str(e)}"
            )
    
    def _confirm_paid_testing(self) -> bool:
        """Ask user to confirm paid API testing"""
        print("\n" + "="*60)
        print("⚠️ PAID API TESTING CONFIRMATION")
        print("="*60)
        print("You are about to test paid APIs that will consume credits.")
        print("Estimated cost: $0.01 - $0.10 for minimal testing")
        print("\nAPIs that will be tested:")
        print("  • Service health checks (minimal cost)")
        print("  • Basic connectivity tests")
        print("\nServices to be tested:")
        print("  • Helius API (Solana RPC)")
        print("  • Birdeye API (Price data)")
        print("  • Chainbase API (Analytics)")
        print("  • Blowfish API (Security)")
        print("  • Solscan v2.0 API (On-chain data) - UPDATED")
        print("  • DataImpulse API (Social sentiment)")
        print("\nRecommendation: Test with ENABLE_API_MOCKS=true first")
        print("="*60)
        
        try:
            response = input("Continue with paid API testing? (yes/no): ").lower().strip()
            return response in ['yes', 'y']
        except (EOFError, KeyboardInterrupt):
            print("\n   ❌ Testing cancelled by user")
            return False
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests according to the selected mode"""
        print(f"🚀 Starting safe service testing (mode: {self.mode.value})")
        print(f"🎯 Base URL: {self.base_url}")
        
        start_time = time.time()
        all_results = []
        
        # Phase 1: System health (always safe)
        health_result = await self.test_system_health()
        all_results.append(health_result)
        
        # Phase 2: Free APIs (including Solscan v2.0 tests)
        free_results = await self.test_free_apis()
        all_results.extend(free_results)
        
        # Phase 3: Service clients (if enabled)
        service_results = await self.test_service_clients()
        all_results.extend(service_results)
        
        total_time = time.time() - start_time
        
        # Generate summary
        return self._generate_summary(all_results, total_time)
    
    def _generate_summary(self, results: List[TestResult], total_time: float) -> Dict[str, Any]:
        """Generate test summary"""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        total_estimated_cost = sum(
            float(r.cost_estimate.replace('$', '').replace('FREE', '0'))
            for r in results
        )
        
        summary = {
            "mode": self.mode.value,
            "total_tests": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "total_time": round(total_time, 2),
            "estimated_cost": f"${total_estimated_cost:.3f}",
            "avg_response_time": round(
                sum(r.response_time for r in successful) / len(successful) if successful else 0,
                3
            ),
            "results": [
                {
                    "service": r.service,
                    "endpoint": r.endpoint,
                    "success": r.success,
                    "response_time": round(r.response_time, 3),
                    "cost": r.cost_estimate,
                    "error": r.error,
                    "data_size": r.data_size
                }
                for r in results
            ]
        }
        
        return summary
    
    def print_summary(self, summary: Dict[str, Any]):
        """Print formatted test summary"""
        print("\n" + "="*80)
        print("📊 SERVICE TESTING SUMMARY")
        print("="*80)
        print(f"Mode: {summary['mode'].upper()}")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Successful: {summary['successful']} ✅")
        print(f"Failed: {summary['failed']} ❌")
        print(f"Total Time: {summary['total_time']}s")
        print(f"Estimated Cost: {summary['estimated_cost']}")
        print(f"Avg Response Time: {summary['avg_response_time']}s")
        
        print("\n📋 DETAILED RESULTS:")
        print("-" * 80)
        
        for result in summary['results']:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['service']:12} {result['endpoint']:25} "
                  f"{result['response_time']:6.3f}s {result['cost']:8}")
            
            if result['error']:
                print(f"    Error: {result['error']}")
        
        print("\n💡 RECOMMENDATIONS:")
        
        if summary['failed'] > 0:
            print("   • Check failed services before using real API keys")
            print("   • Ensure all dependencies are installed")
            print("   • Verify network connectivity")
            
            # Check for server connection issues
            server_errors = [r for r in summary['results'] if 'Server not running' in str(r.get('error', ''))]
            if server_errors:
                print("   • Start the FastAPI server first:")
                print("     python -m app.main")
                print("     # or")
                print("     uvicorn app.main:app --host 0.0.0.0 --port 8000")
        
        if summary['mode'] == 'mock':
            print("   • Mock testing complete - safe to try free APIs")
            print("   • Run with --mode free to test external APIs")
        
        if summary['estimated_cost'] != '$0.000':
            print(f"   • Total estimated cost: {summary['estimated_cost']}")
            print("   • Monitor API dashboards for actual usage")
        
        # Service-specific recommendations
        solscan_results = [r for r in summary['results'] if r['service'] == 'solscan']
        if solscan_results:
            solscan_result = solscan_results[0]
            if not solscan_result['success']:
                if 'v2.0' in str(solscan_result.get('error', '')):
                    print("   • Solscan: Upgrade to Pro API for v2.0 access at https://pro.solscan.io")
                else:
                    print("   • Solscan: Consider getting a Pro API key for v2.0 features")
            else:
                print("   • Solscan v2.0 API working - enhanced features available")
        
        print("="*80)

async def main():
    """Main testing function with v2.0 API support"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Safe Service Tester with Solscan v2.0 Support")
    parser.add_argument("--mode", choices=['mock', 'free', 'limited', 'full'], 
                       default='mock', help="Testing mode")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="Base URL for testing")
    parser.add_argument("--start-server", action="store_true",
                       help="Try to start the server if not running")
    
    args = parser.parse_args()
    
    # Convert string to enum
    mode_map = {
        'mock': TestMode.MOCK_ONLY,
        'free': TestMode.FREE_APIS, 
        'limited': TestMode.LIMITED_PAID,
        'full': TestMode.FULL_TESTING
    }
    
    tester = SafeServiceTester(
        base_url=args.url,
        mode=mode_map[args.mode]
    )
    
    # Check if server is running for mock mode
    if args.mode == 'mock':
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{args.url}/health", timeout=aiohttp.ClientTimeout(total=2)) as response:
                    pass  # Server is running
        except:
            if args.start_server:
                print("🚀 Starting FastAPI server...")
                import subprocess
                import os
                
                # Try to start the server in background
                try:
                    server_process = subprocess.Popen([
                        "python", "-m", "uvicorn", "app.main:app", 
                        "--host", "0.0.0.0", "--port", "8000"
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    # Wait a moment for server to start
                    await asyncio.sleep(3)
                    print("   ✅ Server started")
                except Exception as e:
                    print(f"   ❌ Could not start server: {e}")
            else:
                print("💡 TIP: Start the server first with:")
                print("   python -m app.main")
                print("   # or run with --start-server flag")
                print("")
    
    summary = await tester.run_all_tests()
    tester.print_summary(summary)
    
    # Create results directory
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    # Save results to file with timestamp and mode
    results_file = f"service_test_{args.mode}_{int(time.time())}.json"
    results_path = results_dir / results_file
    
    with open(results_path, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n💾 Results saved to {results_path}")
    
    # Also save a latest result for easy access
    latest_path = results_dir / f"latest_{args.mode}.json"
    with open(latest_path, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"💾 Latest results saved to {latest_path}")

if __name__ == "__main__":
    asyncio.run(main())