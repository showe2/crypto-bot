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
            "dataimpulse": 1.00      # ~$1.00 per 1000 calls
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
            print(f"   ⚠️  Server not running at {self.base_url}")
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
    
    async def _test_config_endpoint(self) -> TestResult:
        """Test configuration endpoint (free, internal)"""
        print("   ⚙️  Testing configuration endpoint...")
        
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
            print(f"   ⚠️  Server not running at {self.base_url}")
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
            print("   ⚠️  WARNING: This will test paid API clients!")
            
            # Ask for confirmation
            if not self._confirm_paid_testing():
                print("   ❌ Service client testing cancelled")
                return results
            
            # Test API health endpoints (usually free or very cheap)
            for service_name in ["helius", "birdeye", "chainbase", "blowfish"]:
                result = await self._test_service_health(service_name)
                results.append(result)
        
        return results
    
    async def _test_service_health(self, service_name: str) -> TestResult:
        """Test individual service health"""
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
            else:
                raise ValueError(f"Unknown service: {service_name}")
            
            response_time = time.time() - start_time
            success = health_data.get("healthy", False)
            
            # Estimate cost (health checks are usually free or very cheap)
            cost_estimate = self.api_costs.get(service_name, 0.001)
            cost_str = f"${cost_estimate:.3f}" if cost_estimate > 0 else "FREE"
            
            return TestResult(
                service=service_name,
                endpoint="health_check",
                success=success,
                response_time=response_time,
                cost_estimate=cost_str,
                data_size=len(str(health_data))
            )
            
        except Exception as e:
            return TestResult(
                service=service_name,
                endpoint="health_check",
                success=False,
                response_time=time.time() - start_time,
                cost_estimate="FREE",
                error=str(e)
            )
    
    def _confirm_paid_testing(self) -> bool:
        """Ask user to confirm paid API testing"""
        print("\n" + "="*60)
        print("⚠️  PAID API TESTING CONFIRMATION")
        print("="*60)
        print("You are about to test paid APIs that will consume credits.")
        print("Estimated cost: $0.01 - $0.10 for minimal testing")
        print("\nAPIs that will be tested:")
        print("  • Service health checks (minimal cost)")
        print("  • Basic connectivity tests")
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
        print(f"📍 Base URL: {self.base_url}")
        
        start_time = time.time()
        all_results = []
        
        # Phase 1: System health (always safe)
        health_result = await self.test_system_health()
        all_results.append(health_result)
        
        # Phase 2: Free APIs
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
            print(f"{status} {result['service']:12} {result['endpoint']:20} "
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
        
        print("="*80)

async def main():
    """Main testing function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Safe Service Tester")
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