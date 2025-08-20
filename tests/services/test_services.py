import asyncio
import aiohttp
import json
import time
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import argparse
from datetime import datetime

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class TestMode(Enum):
    """🎯 Testing modes from safest to most comprehensive"""
    MOCK_ONLY = "mock"           # 🛡️ No real API calls - completely safe
    FREE_APIS = "free"           # 💚 Only free APIs (SolanaFM, DexScreener)
    LIMITED_PAID = "limited"     # 💛 Minimal paid API calls (~$0.01-0.05)
    FULL_TESTING = "full"        # 🔴 All APIs (use carefully! ~$0.10-0.50)

class ServiceCategory(Enum):
    """📊 Service categories"""
    FREE = "free"
    PAID = "paid"
    PREMIUM = "premium"

@dataclass
class TestResult:
    """🔬 Enhanced test result tracking"""
    service: str
    endpoint: str
    success: bool
    response_time: float
    cost_estimate: str
    data_size: int = 0
    error: Optional[str] = None
    category: ServiceCategory = ServiceCategory.PAID
    timestamp: float = 0
    
    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary"""
        return {
            "service": self.service,
            "endpoint": self.endpoint,
            "success": self.success,
            "response_time": self.response_time,
            "cost_estimate": self.cost_estimate,
            "data_size": self.data_size,
            "error": self.error,
            "category": self.category.value,  # Convert enum to string
            "timestamp": self.timestamp
        }

@dataclass  
class ServiceConfig:
    """⚙️ Service configuration"""
    name: str
    category: ServiceCategory
    cost_per_1k: float  # USD per 1000 calls
    requires_auth: bool
    health_check_module: str
    client_module: str
    test_methods: List[str]
    icon: str = "🔧"

class ComprehensiveServiceTester:
    """🧪 Advanced service tester with comprehensive features"""
    
    def __init__(self, base_url: str = "http://localhost:8000", mode: TestMode = TestMode.MOCK_ONLY):
        self.base_url = base_url
        self.mode = mode
        self.results: List[TestResult] = []
        self.start_time = time.time()
        
        # 🎯 Test tokens - carefully selected for maximum compatibility
        self.test_tokens = {
            "solana": [
                "So11111111111111111111111111111111111111112",  # Wrapped SOL - most supported
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC - widely available
                "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT - good coverage
            ],
            "ethereum": [
                "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH - excellent for testing
                "0xA0b86a33E6411E1e2d088c4dDfC1B8F31Efa6a95",  # ELF - GOplus friendly
                "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT - universal
            ]
        }
        
        # 🔧 Service configurations with your specific structure
        self.services = {
            "helius": ServiceConfig(
                name="Helius",
                category=ServiceCategory.PAID,
                cost_per_1k=0.10,
                requires_auth=True,
                health_check_module="app.services.helius_client.check_helius_health",
                client_module="app.services.helius_client.HeliusClient",
                test_methods=["get_token_metadata", "get_token_supply"],
                icon="🌞"
            ),
            "birdeye": ServiceConfig(
                name="Birdeye",
                category=ServiceCategory.PAID,
                cost_per_1k=0.25,
                requires_auth=True,
                health_check_module="app.services.birdeye_client.check_birdeye_health",
                client_module="app.services.birdeye_client.BirdeyeClient",
                test_methods=["get_token_price", "get_trending_tokens", "get_token_trades", "get_price_history", "get_top_traders"],
                icon="🦅"
            ),
            "chainbase": ServiceConfig(
                name="Chainbase",
                category=ServiceCategory.PAID,
                cost_per_1k=0.50,
                requires_auth=True,
                health_check_module="app.services.chainbase_client.check_chainbase_health",
                client_module="app.services.chainbase_client.ChainbaseClient",
                test_methods=["get_token_metadata", "get_token_holders"],
                icon="🔗"
            ),
            "solanafm": ServiceConfig(
                name="SolanaFM",
                category=ServiceCategory.FREE,
                cost_per_1k=0.0,
                requires_auth=False,
                health_check_module="app.services.solanafm_client.check_solanafm_health",
                client_module="app.services.solanafm_client.SolanaFMClient",
                test_methods=["get_token_info", "get_account_detail"],
                icon="📊"
            ),
            "goplus": ServiceConfig(
                name="GOplus",
                category=ServiceCategory.PAID,
                cost_per_1k=0.15,
                requires_auth=True,
                health_check_module="app.services.goplus_client.check_goplus_health",
                client_module="app.services.goplus_client.GOplusClient",
                test_methods=["analyze_token_security", "detect_rugpull", "comprehensive_analysis"],
                icon="🔒"
            ),
            "blowfish": ServiceConfig(
                name="Blowfish",
                category=ServiceCategory.PREMIUM,
                cost_per_1k=2.00,
                requires_auth=True,
                health_check_module="app.services.blowfish_client.check_blowfish_health",
                client_module="app.services.blowfish_client.BlowfishClient",
                test_methods=["scan_token", "get_risk_indicators"],
                icon="🐡"
            ),
            "dataimpulse": ServiceConfig(
                name="DataImpulse",
                category=ServiceCategory.PREMIUM,
                cost_per_1k=1.00,
                requires_auth=True,
                health_check_module="app.services.dataimpulse_client.check_dataimpulse_health",
                client_module="app.services.dataimpulse_client.DataImpulseClient",
                test_methods=["analyze_token_buzz"],
                icon="📱"
            )
        }
    
    def print_header(self):
        """🎨 Print fancy header"""
        print("\n" + "="*80)
        print("🧪 COMPREHENSIVE SERVICE TESTING SUITE")
        print("="*80)
        print(f"🎯 Mode: {self.mode.value.upper()}")
        print(f"🔗 Base URL: {self.base_url}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if self.mode == TestMode.MOCK_ONLY:
            print("🛡️ SAFE MODE: No real API calls will be made")
        elif self.mode == TestMode.FREE_APIS:
            print("💚 FREE MODE: Only testing free APIs")
        elif self.mode == TestMode.LIMITED_PAID:
            print("💛 LIMITED MODE: Minimal paid API usage (~$0.01-0.05)")
        elif self.mode == TestMode.FULL_TESTING:
            print("🔴 FULL MODE: ⚠️ All APIs - may cost $0.10-0.50!")
        
        print("="*80)
    
    async def test_system_health(self) -> TestResult:
        """🏥 Test system health and connectivity"""
        print(f"\n🏥 Testing system health...")
        
        start_time = time.time()
        
        # Mock mode - test system components
        if self.mode == TestMode.MOCK_ONLY:
            try:
                # Quick server check
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=2)) as response:
                        data = await response.json()
                        response_time = time.time() - start_time
                        
                        print(f"   ✅ Server health: {response.status} ({response_time:.3f}s)")
                        return TestResult(
                            service="system",
                            endpoint="/health",
                            success=response.status in [200, 503],
                            response_time=response_time,
                            cost_estimate="FREE",
                            category=ServiceCategory.FREE,
                            data_size=len(str(data))
                        )
                        
            except (aiohttp.ClientConnectorError, asyncio.TimeoutError):
                print("   🔧 Server not running, testing system components...")
                return await self._test_system_components()
        
        # Other modes require server
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    data = await response.json()
                    response_time = time.time() - start_time
                    
                    print(f"   ✅ Server health: {response.status} ({response_time:.3f}s)")
                    return TestResult(
                        service="system",
                        endpoint="/health",
                        success=response.status in [200, 503],
                        response_time=response_time,
                        cost_estimate="FREE",
                        category=ServiceCategory.FREE,
                        data_size=len(str(data))
                    )
                    
        except aiohttp.ClientConnectorError:
            response_time = time.time() - start_time
            print(f"   ⚠️ Server not running at {self.base_url}")
            return TestResult(
                service="system",
                endpoint="/health",
                success=False,
                response_time=response_time,
                cost_estimate="FREE",
                category=ServiceCategory.FREE,
                error=f"Server not running. Start with: python -m app.main"
            )
    
    async def _test_system_components(self) -> TestResult:
        """🔧 Test system components when server is not running"""
        start_time = time.time()
        
        try:
            # Test core imports
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
            print(f"   ✅ System components: All working ({response_time:.3f}s)")
            
            return TestResult(
                service="system",
                endpoint="/components",
                success=True,
                response_time=response_time,
                cost_estimate="FREE",
                category=ServiceCategory.FREE
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            print(f"   ❌ System components failed ({response_time:.3f}s)")
            
            return TestResult(
                service="system",
                endpoint="/components",
                success=False,
                response_time=response_time,
                cost_estimate="FREE",
                category=ServiceCategory.FREE,
                error=f"Component test failed: {str(e)}"
            )
    
    async def test_free_services(self) -> List[TestResult]:
        """💚 Test free services (SolanaFM, DexScreener)"""
        print(f"\n💚 Testing free services...")
        results = []
        
        if self.mode in [TestMode.FREE_APIS, TestMode.LIMITED_PAID, TestMode.FULL_TESTING]:
            # Test SolanaFM
            solanafm_results = await self._test_solanafm_comprehensive()
            results.extend(solanafm_results)
            
            # Test DexScreener
            dexscreener_result = await self._test_dexscreener()
            results.append(dexscreener_result)
        
        return results
    
    async def _test_solanafm_comprehensive(self) -> List[TestResult]:
        """📊 Comprehensive SolanaFM testing"""
        print(f"   📊 Testing SolanaFM (FREE service)...")
        results = []
        
        try:
            from app.services.solanafm_client import SolanaFMClient
            
            async with SolanaFMClient() as client:
                # Test 1: Account detail
                print(f"      👤 Testing account detail...")
                start_time = time.time()
                
                try:
                    account_info = await client.get_account_detail("AK2VbkdYLHSiJKS6AGUfNZYNaejABkV6VYDX1Vrgxfo")
                    account_time = time.time() - start_time
                    
                    if account_info:
                        balance_sol = account_info.get('balance_sol', 0)
                        friendly_name = account_info.get('friendly_name', 'Unknown')
                        print(f"         ✅ Account: {friendly_name} ({balance_sol} SOL) ({account_time:.3f}s)")
                        
                        results.append(TestResult(
                            service="solanafm",
                            endpoint="/v0/accounts/{account}",
                            success=True,
                            response_time=account_time,
                            cost_estimate="FREE",
                            category=ServiceCategory.FREE,
                            data_size=len(str(account_info))
                        ))
                    else:
                        print(f"         ⚠️ No account data ({account_time:.3f}s)")
                        results.append(TestResult(
                            service="solanafm",
                            endpoint="/v0/accounts/{account}",
                            success=False,
                            response_time=account_time,
                            cost_estimate="FREE",
                            category=ServiceCategory.FREE,
                            error="No account data returned"
                        ))
                        
                except Exception as e:
                    account_time = time.time() - start_time
                    print(f"         ❌ Account detail error: {str(e)} ({account_time:.3f}s)")
                    results.append(TestResult(
                        service="solanafm",
                        endpoint="/v0/accounts/{account}",
                        success=False,
                        response_time=account_time,
                        cost_estimate="FREE",
                        category=ServiceCategory.FREE,
                        error=str(e)
                    ))
                
                await asyncio.sleep(0.3)  # Rate limiting
                
                # Test 2: Token info (from your example)
                print(f"      🪙 Testing token info...")
                start_time = time.time()
                
                try:
                    token_info = await client.get_token_info("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
                    token_time = time.time() - start_time
                    
                    if token_info:
                        name = token_info.get('name', 'Unknown')
                        symbol = token_info.get('symbol', 'N/A')
                        decimals = token_info.get('decimals', 'N/A')
                        print(f"         ✅ Token: {name} ({symbol}) - {decimals} decimals ({token_time:.3f}s)")
                        
                        results.append(TestResult(
                            service="solanafm",
                            endpoint="/v1/tokens/{token}",
                            success=True,
                            response_time=token_time,
                            cost_estimate="FREE",
                            category=ServiceCategory.FREE,
                            data_size=len(str(token_info))
                        ))
                    else:
                        print(f"         ⚠️ No token data ({token_time:.3f}s)")
                        results.append(TestResult(
                            service="solanafm",
                            endpoint="/v1/tokens/{token}",
                            success=False,
                            response_time=token_time,
                            cost_estimate="FREE",
                            category=ServiceCategory.FREE,
                            error="No token data returned"
                        ))
                        
                except Exception as e:
                    token_time = time.time() - start_time
                    print(f"         ❌ Token info error: {str(e)} ({token_time:.3f}s)")
                    results.append(TestResult(
                        service="solanafm",
                        endpoint="/v1/tokens/{token}",
                        success=False,
                        response_time=token_time,
                        cost_estimate="FREE",
                        category=ServiceCategory.FREE,
                        error=str(e)
                    ))
                
        except ImportError:
            print(f"      ❌ SolanaFM client not available")
            results.append(TestResult(
                service="solanafm",
                endpoint="/import",
                success=False,
                response_time=0,
                cost_estimate="FREE",
                category=ServiceCategory.FREE,
                error="SolanaFM client not available"
            ))
        except Exception as e:
            print(f"      ❌ SolanaFM test failed: {str(e)}")
            results.append(TestResult(
                service="solanafm",
                endpoint="/test",
                success=False,
                response_time=0,
                cost_estimate="FREE",
                category=ServiceCategory.FREE,
                error=str(e)
            ))
        
        return results
    
    async def _test_dexscreener(self) -> TestResult:
        """🔍 Test DexScreener API (completely free)"""
        print(f"      🔍 Testing DexScreener...")
        
        start_time = time.time()
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{self.test_tokens['solana'][0]}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    data = await response.json()
                    response_time = time.time() - start_time
                    
                    if response.status == 200 and data:
                        pairs_count = len(data.get('pairs', []))
                        print(f"         ✅ DexScreener: {pairs_count} trading pairs found ({response_time:.3f}s)")
                        
                        return TestResult(
                            service="dexscreener",
                            endpoint="/dex/tokens",
                            success=True,
                            response_time=response_time,
                            cost_estimate="FREE",
                            category=ServiceCategory.FREE,
                            data_size=len(str(data))
                        )
                    else:
                        print(f"         ⚠️ DexScreener: No data ({response_time:.3f}s)")
                        return TestResult(
                            service="dexscreener",
                            endpoint="/dex/tokens",
                            success=False,
                            response_time=response_time,
                            cost_estimate="FREE",
                            category=ServiceCategory.FREE,
                            error=f"HTTP {response.status}"
                        )
                        
        except Exception as e:
            response_time = time.time() - start_time
            print(f"         ❌ DexScreener error: {str(e)} ({response_time:.3f}s)")
            return TestResult(
                service="dexscreener",
                endpoint="/dex/tokens",
                success=False,
                response_time=response_time,
                cost_estimate="FREE",
                category=ServiceCategory.FREE,
                error=str(e)
            )
    
    async def test_paid_services(self) -> List[TestResult]:
        """💛 Test paid services with health checks and limited calls"""
        print(f"\n💛 Testing paid services...")
        results = []
        
        if self.mode not in [TestMode.LIMITED_PAID, TestMode.FULL_TESTING]:
            print(f"   ⚠️ Paid service testing requires 'limited' or 'full' mode")
            return results
        
        # Ask for confirmation
        if not await self._confirm_paid_testing():
            print(f"   ❌ Paid service testing cancelled by user")
            return results
        
        # Test each paid service
        for service_name, config in self.services.items():
            if config.category in [ServiceCategory.PAID, ServiceCategory.PREMIUM]:
                service_results = await self._test_service_comprehensive(service_name, config)
                results.extend(service_results)
        
        return results
    
    async def _confirm_paid_testing(self) -> bool:
        """⚠️ Confirm paid API testing with user"""
        print(f"\n" + "="*60)
        print(f"⚠️ PAID API TESTING CONFIRMATION")
        print(f"="*60)
        print(f"You are about to test APIs that may consume credits.")
        
        if self.mode == TestMode.LIMITED_PAID:
            print(f"💛 LIMITED MODE: Estimated cost $0.01-$0.05")
            print(f"   • Health checks only")
            print(f"   • Minimal data requests")
        elif self.mode == TestMode.FULL_TESTING:
            print(f"🔴 FULL MODE: Estimated cost $0.10-$0.50")
            print(f"   • Full API testing")
            print(f"   • Multiple endpoints")
        
        print(f"\nServices to test:")
        for service_name, config in self.services.items():
            if config.category != ServiceCategory.FREE:
                cost_info = f"${config.cost_per_1k:.3f}/1k calls"
                print(f"  {config.icon} {config.name}: {cost_info}")
        
        print(f"="*60)
        
        try:
            response = input("Continue with paid API testing? (yes/no): ").lower().strip()
            return response in ['yes', 'y']
        except (EOFError, KeyboardInterrupt):
            print(f"\n   ❌ Testing cancelled by user")
            return False
    
    async def _test_service_comprehensive(self, service_name: str, config: ServiceConfig) -> List[TestResult]:
        """🔧 Comprehensive service testing based on your examples"""
        print(f"   {config.icon} Testing {config.name}...")
        results = []
        
        # Test 1: Health check
        health_result = await self._test_service_health(service_name, config)
        results.append(health_result)
        
        # Only continue with API calls if health check passed and we have auth
        if health_result.success and self.mode == TestMode.FULL_TESTING:
            # Test specific API calls based on service
            if service_name == "birdeye":
                api_results = await self._test_birdeye_api_calls()
                results.extend(api_results)
            elif service_name == "chainbase":
                api_results = await self._test_chainbase_api_calls()
                results.extend(api_results)
            elif service_name == "goplus":
                api_results = await self._test_goplus_api_calls()
                results.extend(api_results)
        
        return results
    
    async def _test_service_health(self, service_name: str, config: ServiceConfig) -> TestResult:
        """🏥 Test service health check"""
        print(f"      🏥 Health check...")
        
        start_time = time.time()
        try:
            # Import health check function
            module_path, function_name = config.health_check_module.rsplit('.', 1)
            module = __import__(module_path, fromlist=[function_name])
            health_check_func = getattr(module, function_name)
            
            health_data = await health_check_func()
            response_time = time.time() - start_time
            
            success = health_data.get("healthy", False)
            api_key_configured = health_data.get("api_key_configured", False)
            error_message = health_data.get("error", "")
            
            # Determine cost
            if not api_key_configured or not success:
                cost_estimate = "FREE"
            else:
                cost_estimate = f"${config.cost_per_1k:.3f}"
            
            # Generate status message
            if success:
                status_msg = f"✅ Healthy"
                if not config.requires_auth:
                    status_msg += " (no auth required)"
                elif api_key_configured:
                    status_msg += " (authenticated)"
            else:
                if not config.requires_auth:
                    status_msg = f"❌ Service issues"
                elif not api_key_configured:
                    status_msg = f"⚠️ No API key configured"
                else:
                    status_msg = f"❌ Authentication failed"
            
            print(f"         {status_msg} ({response_time:.3f}s)")
            
            if error_message and not success:
                print(f"         💭 {error_message[:60]}...")
            
            return TestResult(
                service=service_name,
                endpoint="health_check",
                success=success,
                response_time=response_time,
                cost_estimate=cost_estimate,
                category=config.category,
                data_size=len(str(health_data)),
                error=error_message if not success else None
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            print(f"         ❌ Health check failed: {str(e)} ({response_time:.3f}s)")
            
            return TestResult(
                service=service_name,
                endpoint="health_check",
                success=False,
                response_time=response_time,
                cost_estimate="FREE",
                category=config.category,
                error=f"Health check failed: {str(e)}"
            )
    
    async def _test_birdeye_api_calls(self) -> List[TestResult]:
        """🦅 Test Birdeye API calls"""
        print(f"      🦅 Testing Birdeye API calls...")
        results = []
        
        try:
            from app.services.birdeye_client import BirdeyeClient
            
            async with BirdeyeClient() as client:
                # Test Birdeye endpoints
                print(f"         💸 Testing token price...")
                start_time = time.time()

                try:
                    token_price = await client.get_token_price(self.test_tokens['solana'][0])
                    price_time = time.time() - start_time

                    if token_price and len(token_price) > 0:
                        print(f"            ✅ Received token price ({price_time:.3f}s)")

                        results.append(TestResult(
                            service="birdeye",
                            endpoint="/defi/price",
                            success=True,
                            response_time=price_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            data_size=len(str(token_price))
                        ))
                    else:
                        print(f"            ⚠️ No price data ({price_time:.3f}s)")
                        results.append(TestResult(
                            service="birdeye",
                            endpoint="/defi/price",
                            success=False,
                            response_time=price_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            error="No price data returned"
                        ))
                
                except Exception as e:
                    price_time = time.time() - start_time
                    print(f"            ❌ Top traders error: {str(e)} ({price_time:.3f}s)")
                    results.append(TestResult(
                        service="birdeye",
                        endpoint="/defi/price",
                        success=False,
                        response_time=price_time,
                        cost_estimate="FREE",
                        category=ServiceCategory.PAID,
                        error=str(e)
                    ))

                # Rate limiting between calls
                await asyncio.sleep(1)

                print(f"         📈 Testing trending tokens...")
                start_time = time.time()

                try:
                    trending_tokens = await client.get_trending_tokens(limit=5)
                    trending_time = time.time() - start_time

                    if trending_tokens and len(trending_tokens) > 0:
                        print(f"            ✅ Received tokens ({trending_time:.3f}s)")

                        results.append(TestResult(
                            service="birdeye",
                            endpoint="/defi/token_trending",
                            success=True,
                            response_time=trending_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            data_size=len(str(trending_tokens))
                        ))
                    else:
                        print(f"            ⚠️ No data ({trending_time:.3f}s)")
                        results.append(TestResult(
                            service="birdeye",
                            endpoint="/defi/token_trending",
                            success=False,
                            response_time=trending_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            error="No data returned"
                        ))
                
                except Exception as e:
                    trending_time = time.time() - start_time
                    print(f"            ❌ Trending tokens error: {str(e)} ({trending_time:.3f}s)")
                    results.append(TestResult(
                        service="birdeye",
                        endpoint="defi/token_trending",
                        success=False,
                        response_time=trending_time,
                        cost_estimate="FREE",
                        category=ServiceCategory.PAID,
                        error=str(e)
                    ))

                # Rate limiting between calls
                await asyncio.sleep(1)

                print(f"         🗃️ Testing price history...")
                start_time = time.time()

                try:
                    history = await client.get_price_history(token_address=self.test_tokens["solana"][0], time_from=1700000000, time_to=1726704000)
                    history_time = time.time() - start_time

                    if history and len(history) > 0:
                        print(f"            ✅ Received price history ({history_time:.3f}s)")

                        results.append(TestResult(
                            service="birdeye",
                            endpoint="/defi/history_price",
                            success=True,
                            response_time=history_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            data_size=len(str(history))
                        ))
                    else:
                        print(f"            ⚠️ No price history data ({history_time:.3f}s)")
                        results.append(TestResult(
                            service="birdeye",
                            endpoint="/defi/history_price",
                            success=False,
                            response_time=history_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            error="No price history data returned"
                        ))
                
                except Exception as e:
                    history_time = time.time() - start_time
                    print(f"            ❌ Price history error: {str(e)} ({history_time:.3f}s)")
                    results.append(TestResult(
                        service="birdeye",
                        endpoint="/defi/history_price",
                        success=False,
                        response_time=history_time,
                        cost_estimate="FREE",
                        category=ServiceCategory.PAID,
                        error=str(e)
                    ))

                # Rate limiting between calls
                await asyncio.sleep(1)

                print(f"         🤝 Testing token trades...")
                start_time = time.time()

                try:
                    trades = await client.get_token_trades(token_address=self.test_tokens["solana"][0], limit=5)
                    trades_time = time.time() - start_time

                    if trades and len(trades) > 0:
                        print(f"            ✅ Received trades ({trades_time:.3f}s)")

                        results.append(TestResult(
                            service="birdeye",
                            endpoint="/defi/v3/token/txs",
                            success=True,
                            response_time=trades_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            data_size=len(str(trades))
                        ))
                    else:
                        print(f"            ⚠️ No trades data ({trades_time:.3f}s)")
                        results.append(TestResult(
                            service="birdeye",
                            endpoint="/defi/v3/token/txs",
                            success=False,
                            response_time=trades_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            error="No trades data returned"
                        ))
                
                except Exception as e:
                    trades_time = time.time() - start_time
                    print(f"            ❌ Token trades error: {str(e)} ({trades_time:.3f}s)")
                    results.append(TestResult(
                        service="birdeye",
                        endpoint="/defi/v3/token/txs",
                        success=False,
                        response_time=trades_time,
                        cost_estimate="FREE",
                        category=ServiceCategory.PAID,
                        error=str(e)
                    ))

                # Rate limiting between calls
                await asyncio.sleep(1)

                print(f"         👥 Testing top traders...")
                start_time = time.time()
                
                try:
                    top_traders = await client.get_top_traders(
                        token_address=self.test_tokens["solana"][0],
                        limit=3
                    )
                    traders_time = time.time() - start_time
                    
                    if top_traders and len(top_traders) > 0:
                        print(f"            ✅ Found {len(top_traders)} top traders ({traders_time:.3f}s)")
                        results.append(TestResult(
                            service="birdeye",
                            endpoint="defi/v2/tokens/top_traders",
                            success=True,
                            response_time=traders_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            data_size=len(str(top_traders))
                        ))
                    else:
                        print(f"            ⚠️ No trader data ({traders_time:.3f}s)")
                        results.append(TestResult(
                            service="birdeye",
                            endpoint="defi/v2/tokens/top_traders",
                            success=False,
                            response_time=traders_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            error="No trader data returned"
                        ))
                        
                except Exception as e:
                    traders_time = time.time() - start_time
                    print(f"            ❌ Top traders error: {str(e)} ({traders_time:.3f}s)")
                    results.append(TestResult(
                        service="birdeye",
                        endpoint="defi/v2/tokens/top_traders",
                        success=False,
                        response_time=traders_time,
                        cost_estimate="FREE",
                        category=ServiceCategory.PAID,
                        error=str(e)
                    ))
                
        except Exception as e:
            print(f"         ❌ Birdeye client error: {str(e)}")
            results.append(TestResult(
                service="birdeye",
                endpoint="/client_error",
                success=False,
                response_time=0,
                cost_estimate="FREE",
                category=ServiceCategory.PAID,
                error=str(e)
            ))
        
        return results
    
    async def _test_chainbase_api_calls(self) -> List[TestResult]:
        """🔗 Test Chainbase API calls"""
        print(f"      🔗 Testing Chainbase API calls...")
        results = []
        
        try:
            from app.services.chainbase_client import ChainbaseClient
            
            async with ChainbaseClient() as client:
                # Test metadata and holders
                test_token = self.test_tokens["ethereum"][0]  # WETH
                print(f"         🪙 Testing token: {test_token[:8]}...{test_token[-4:]}")
                
                print(f"         📊 Testing token metadata...")
                start_time = time.time()
                
                try:
                    metadata = await client.get_token_metadata(test_token, "ethereum")
                    metadata_time = time.time() - start_time
                    
                    if metadata:                        
                        results.append(TestResult(
                            service="chainbase",
                            endpoint="/token/metadata",
                            success=True,
                            response_time=metadata_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            data_size=len(str(metadata))
                        ))
                    else:
                        print(f"            ⚠️ No metadata returned ({metadata_time:.3f}s)")
                        print(f"            📋 Response was: {metadata}")
                        results.append(TestResult(
                            service="chainbase",
                            endpoint="/token/metadata",
                            success=False,
                            response_time=metadata_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            error="No metadata returned"
                        ))
                        
                except Exception as e:
                    metadata_time = time.time() - start_time
                    print(f"            ❌ Metadata error: {str(e)} ({metadata_time:.3f}s)")
                    print(f"            📋 Full error: {repr(e)}")
                    results.append(TestResult(
                        service="chainbase",
                        endpoint="/token/metadata",
                        success=False,
                        response_time=metadata_time,
                        cost_estimate="FREE",
                        category=ServiceCategory.PAID,
                        error=str(e)
                    ))
                
                # Rate limiting between calls
                await asyncio.sleep(1)
                
                # Test token holders
                print(f"         👥 Testing token holders...")
                start_time = time.time()
                
                try:
                    holders = await client.get_token_holders(test_token, "ethereum", limit=5)
                    holders_time = time.time() - start_time
                    
                    if holders:                        
                        if isinstance(holders, dict):
                            print(f"            ✅ Holders data retrieved")
                            print(f"               Response time: {holders_time:.3f}s")
                            
                        results.append(TestResult(
                            service="chainbase",
                            endpoint="/token/top-holders",
                            success=True,
                            response_time=holders_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            data_size=len(str(holders))
                        ))
                    else:
                        print(f"            ⚠️ No holder data returned ({holders_time:.3f}s)")
                        print(f"            📋 Response was: {holders}")
                        results.append(TestResult(
                            service="chainbase",
                            endpoint="/token/top-holders",
                            success=False,
                            response_time=holders_time,
                            cost_estimate="$0.001",
                            category=ServiceCategory.PAID,
                            error="No holder data returned"
                        ))
                        
                except Exception as e:
                    holders_time = time.time() - start_time
                    print(f"            ❌ Holders error: {str(e)} ({holders_time:.3f}s)")
                    print(f"            📋 Full error: {repr(e)}")
                    results.append(TestResult(
                        service="chainbase",
                        endpoint="/token/top-holders",
                        success=False,
                        response_time=holders_time,
                        cost_estimate="FREE",
                        category=ServiceCategory.PAID,
                        error=str(e)
                    ))
                
        except Exception as e:
            print(f"         ❌ Chainbase client error: {str(e)}")
            print(f"         📋 Full client error: {repr(e)}")
            results.append(TestResult(
                service="chainbase",
                endpoint="/client_error",
                success=False,
                response_time=0,
                cost_estimate="FREE",
                category=ServiceCategory.PAID,
                error=str(e)
            ))
        
        return results
    
    async def _test_goplus_api_calls(self) -> List[TestResult]:
        """🔒 Test GOplus API calls"""
        print(f"      🔒 Testing GOplus API calls...")
        results = []
        
        try:
            from app.services.goplus_client import GOplusClient
            
            async with GOplusClient() as client:
                # Test token security analysis
                test_scenarios = [
                    ("0xA0b86a33E6411E1e2d088c4dDfC1B8F31Efa6a95", "ethereum", "ELF Token"),
                    ("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "ethereum", "WETH"),
                ]
                
                for token_address, chain, token_name in test_scenarios:
                    print(f"         🛡️ Testing security for {token_name}...")
                    start_time = time.time()
                    
                    try:
                        security_result = await client.analyze_token_security(token_address, chain)
                        security_time = time.time() - start_time
                        
                        if security_result:
                            is_honeypot = security_result.get("is_honeypot", False)
                            is_blacklisted = security_result.get("is_blacklisted", False)
                            
                            status = "🟢 Safe"
                            if is_honeypot or is_blacklisted:
                                status = "🔴 Risky"
                            
                            print(f"            ✅ Security: {status} ({security_time:.3f}s)")
                            results.append(TestResult(
                                service="goplus",
                                endpoint="/api/v1/token_security",
                                success=True,
                                response_time=security_time,
                                cost_estimate="$0.002",
                                category=ServiceCategory.PAID,
                                data_size=len(str(security_result))
                            ))
                            break  # Success, no need to test more
                        else:
                            print(f"            ⚠️ No security data ({security_time:.3f}s)")
                            results.append(TestResult(
                                service="goplus",
                                endpoint="/api/v1/token_security",
                                success=False,
                                response_time=security_time,
                                cost_estimate="$0.002",
                                category=ServiceCategory.PAID,
                                error="No security data returned"
                            ))
                            
                    except Exception as e:
                        security_time = time.time() - start_time
                        print(f"            ❌ Security error: {str(e)} ({security_time:.3f}s)")
                        results.append(TestResult(
                            service="goplus",
                            endpoint="/api/v1/token_security",
                            success=False,
                            response_time=security_time,
                            cost_estimate="FREE",
                            category=ServiceCategory.PAID,
                            error=str(e)
                        ))
                        
                        if "authentication" in str(e).lower():
                            break  # No point testing more if auth fails
                    
                    await asyncio.sleep(1)  # Rate limiting
                
        except Exception as e:
            print(f"         ❌ GOplus client error: {str(e)}")
            results.append(TestResult(
                service="goplus",
                endpoint="/client_error",
                success=False,
                response_time=0,
                cost_estimate="FREE",
                category=ServiceCategory.PAID,
                error=str(e)
            ))
        
        return results
    
    async def run_comprehensive_tests(self) -> Dict[str, Any]:
        """🚀 Run comprehensive test suite"""
        self.print_header()
        
        all_results = []
        
        # Phase 1: System Health
        print(f"\n🏥 PHASE 1: SYSTEM HEALTH")
        health_result = await self.test_system_health()
        all_results.append(health_result)
        
        # Phase 2: Free Services
        print(f"\n💚 PHASE 2: FREE SERVICES")
        free_results = await self.test_free_services()
        all_results.extend(free_results)
        
        # Phase 3: Paid Services
        if self.mode in [TestMode.LIMITED_PAID, TestMode.FULL_TESTING]:
            print(f"\n💛 PHASE 3: PAID SERVICES")
            paid_results = await self.test_paid_services()
            all_results.extend(paid_results)
        
        # Generate comprehensive summary
        return self._generate_comprehensive_summary(all_results)
    
    def _generate_comprehensive_summary(self, results: List[TestResult]) -> Dict[str, Any]:
        """📊 Generate comprehensive test summary"""
        total_time = time.time() - self.start_time
        
        # Categorize results
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        # Calculate costs by category
        free_results = [r for r in results if r.category == ServiceCategory.FREE]
        paid_results = [r for r in results if r.category == ServiceCategory.PAID]
        premium_results = [r for r in results if r.category == ServiceCategory.PREMIUM]
        
        total_estimated_cost = sum(
            float(r.cost_estimate.replace('$', '').replace('FREE', '0'))
            for r in results
        )
        
        # Service breakdown
        service_summary = {}
        for result in results:
            if result.service not in service_summary:
                service_summary[result.service] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                    "cost": 0.0,
                    "avg_response_time": 0.0
                }
            
            service_summary[result.service]["total"] += 1
            if result.success:
                service_summary[result.service]["successful"] += 1
            else:
                service_summary[result.service]["failed"] += 1
            
            cost = float(result.cost_estimate.replace('$', '').replace('FREE', '0'))
            service_summary[result.service]["cost"] += cost
        
        # Calculate average response times
        for service_name in service_summary:
            service_results = [r for r in results if r.service == service_name and r.success]
            if service_results:
                avg_time = sum(r.response_time for r in service_results) / len(service_results)
                service_summary[service_name]["avg_response_time"] = avg_time
        
        return {
            "mode": self.mode.value,
            "total_time": round(total_time, 2),
            "total_tests": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": round((len(successful) / len(results)) * 100, 1) if results else 0,
            "estimated_cost": f"${total_estimated_cost:.3f}",
            "category_breakdown": {
                "free": len(free_results),
                "paid": len(paid_results),
                "premium": len(premium_results)
            },
            "service_summary": service_summary,
            "detailed_results": [r.to_dict() for r in results],
            "timestamp": datetime.now().isoformat()
        }
    
    def print_comprehensive_summary(self, summary: Dict[str, Any]):
        """🎨 Print fancy comprehensive summary"""
        print(f"\n" + "="*80)
        print(f"📊 COMPREHENSIVE TEST RESULTS")
        print(f"="*80)
        
        # Overall stats
        print(f"🎯 Mode: {summary['mode'].upper()}")
        print(f"⏱️ Total Time: {summary['total_time']}s")
        print(f"🧪 Total Tests: {summary['total_tests']}")
        print(f"✅ Successful: {summary['successful']}")
        print(f"❌ Failed: {summary['failed']}")
        print(f"📈 Success Rate: {summary['success_rate']}%")
        print(f"💰 Estimated Cost: {summary['estimated_cost']}")
        
        # Category breakdown
        category_breakdown = summary['category_breakdown']
        print(f"\n📋 Test Categories:")
        print(f"   💚 Free Services: {category_breakdown['free']}")
        print(f"   💛 Paid Services: {category_breakdown['paid']}")
        print(f"   🔴 Premium Services: {category_breakdown['premium']}")
        
        # Service summary
        print(f"\n🔧 Service Performance:")
        service_summary = summary['service_summary']
        
        for service_name, stats in service_summary.items():
            config = self.services.get(service_name, None)
            icon = config.icon if config else "🔧"
            
            success_rate = round((stats['successful'] / stats['total']) * 100, 1) if stats['total'] > 0 else 0
            avg_time = stats['avg_response_time']
            cost = stats['cost']
            
            status_icon = "✅" if success_rate >= 80 else "⚠️" if success_rate >= 50 else "❌"
            
            print(f"   {status_icon} {icon} {service_name:12} "
                  f"{stats['successful']}/{stats['total']} ({success_rate:5.1f}%) "
                  f"{avg_time:6.3f}s ${cost:5.3f}")
        
        # Detailed results
        print(f"\n📋 DETAILED RESULTS:")
        print(f"-" * 80)
        
        for result_data in summary['detailed_results']:
            service = result_data['service']
            endpoint = result_data['endpoint']
            success = result_data['success']
            response_time = result_data['response_time']
            cost = result_data['cost_estimate']
            error = result_data.get('error')
            
            config = self.services.get(service, None)
            icon = config.icon if config else "🔧"
            
            status_icon = "✅" if success else "❌"
            
            print(f"{status_icon} {icon} {service:12} {endpoint:25} "
                  f"{response_time:6.3f}s {cost:8}")
            
            if error:
                error_short = error[:60] + "..." if len(error) > 60 else error
                print(f"    💭 {error_short}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        
        if summary['failed'] > 0:
            print(f"   • Check failed services configuration")
            print(f"   • Verify API keys are valid and have proper permissions")
            print(f"   • Ensure network connectivity")
        
        if summary['mode'] == 'mock':
            print(f"   • Mock testing complete - ready for free API testing")
            print(f"   • Run with --mode free to test external APIs")
        
        if float(summary['estimated_cost'].replace('$', '')) > 0:
            print(f"   • Monitor API usage in your dashboards")
            print(f"   • Consider implementing rate limiting for production")
        
        # Service-specific recommendations
        failed_services = [name for name, stats in service_summary.items() if stats['successful'] == 0]
        if failed_services:
            print(f"   • Failed services: {', '.join(failed_services)}")
            
            if 'solanafm' in failed_services:
                print(f"     - SolanaFM: Check service availability at https://api.solana.fm")
            if 'goplus' in failed_services:
                print(f"     - GOplus: Get API keys from https://gopluslabs.io/")
            if 'birdeye' in failed_services:
                print(f"     - Birdeye: Get API keys from https://birdeye.so")
        
        successful_services = [name for name, stats in service_summary.items() if stats['successful'] > 0]
        if successful_services:
            print(f"   • Working services: {', '.join(successful_services)}")
            print(f"   • These services are ready for production use")
        
        print(f"="*80)


async def main():
    """🚀 Main function with comprehensive argument handling"""
    parser = argparse.ArgumentParser(
        description="🧪 Comprehensive Service Testing Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tests.services.test_services --mode free
  python -m tests.services.test_services --mode limited --service birdeye
  python -m tests.services.test_services --solanafm-only
  python -m tests.services.test_services --goplus-only --mode limited
  python -m tests.services.test_services --mode full --confirm
        """
    )
    
    parser.add_argument("--mode", choices=['mock', 'free', 'limited', 'full'], 
                       default='mock', help="Testing mode")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="Base URL for testing")
    parser.add_argument("--service", choices=['helius', 'birdeye', 'chainbase', 'solanafm', 'goplus', 'blowfish', 'dataimpulse'],
                       help="Test only specific service")
    parser.add_argument("--solanafm-only", action="store_true",
                       help="Test only SolanaFM services (FREE)")
    parser.add_argument("--goplus-only", action="store_true",
                       help="Test only GOplus services")
    parser.add_argument("--birdeye-only", action="store_true",
                       help="Test only Birdeye services")
    parser.add_argument("--chainbase-only", action="store_true",
                       help="Test only Chainbase services")
    parser.add_argument("--confirm", action="store_true",
                       help="Auto-confirm paid testing (use carefully!)")
    parser.add_argument("--save-results", default="auto",
                       help="Save results to file (auto/path/none)")
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
    
    tester = ComprehensiveServiceTester(
        base_url=args.url,
        mode=mode_map[args.mode]
    )
    
    # Handle service-specific testing
    if args.solanafm_only:
        print(f"📊 SolanaFM-only testing mode (FREE)")
        start_time = time.time()
        
        results = await tester._test_solanafm_comprehensive()
        total_time = time.time() - start_time
        
        summary = {
            "mode": "solanafm_only",
            "total_time": round(total_time, 2),
            "total_tests": len(results),
            "successful": len([r for r in results if r.success]),
            "failed": len([r for r in results if not r.success]),
            "success_rate": round((len([r for r in results if r.success]) / len(results)) * 100, 1) if results else 0,
            "estimated_cost": "FREE",
            "category_breakdown": {"free": len(results), "paid": 0, "premium": 0},
            "service_summary": {"solanafm": {
                "total": len(results),
                "successful": len([r for r in results if r.success]),
                "failed": len([r for r in results if not r.success]),
                "cost": 0.0,
                "avg_response_time": sum(r.response_time for r in results if r.success) / max(len([r for r in results if r.success]), 1)
            }},
            "detailed_results": [r.to_dict() for r in results],
            "timestamp": datetime.now().isoformat()
        }
        
        tester.print_comprehensive_summary(summary)
        
        if args.save_results != "none":
            await save_results(summary, "solanafm_test", args.save_results)
        
        return
    
    if args.goplus_only:
        if args.mode == 'mock':
            print(f"⚠️ GOplus testing requires at least 'limited' mode")
            print(f"   Use --mode limited for minimal GOplus testing")
            return
        
        print(f"🔒 GOplus-only testing mode")
        start_time = time.time()
        
        results = await tester._test_goplus_api_calls()
        total_time = time.time() - start_time
        
        summary = {
            "mode": "goplus_only",
            "total_time": round(total_time, 2),
            "total_tests": len(results),
            "successful": len([r for r in results if r.success]),
            "failed": len([r for r in results if not r.success]),
            "success_rate": round((len([r for r in results if r.success]) / len(results)) * 100, 1) if results else 0,
            "estimated_cost": f"${sum(float(r.cost_estimate.replace('$', '').replace('FREE', '0')) for r in results):.3f}",
            "category_breakdown": {"free": 0, "paid": len(results), "premium": 0},
            "service_summary": {"goplus": {
                "total": len(results),
                "successful": len([r for r in results if r.success]),
                "failed": len([r for r in results if not r.success]),
                "cost": sum(float(r.cost_estimate.replace('$', '').replace('FREE', '0')) for r in results),
                "avg_response_time": sum(r.response_time for r in results if r.success) / max(len([r for r in results if r.success]), 1)
            }},
            "detailed_results": [r.to_dict() for r in results],
            "timestamp": datetime.now().isoformat()
        }
        
        tester.print_comprehensive_summary(summary)
        
        if args.save_results != "none":
            await save_results(summary, "goplus_test", args.save_results)
        
        return
    
    if args.birdeye_only:
        if args.mode == 'mock':
            print(f"⚠️ Birdeye testing requires at least 'limited' mode")
            return
        
        print(f"🦅 Birdeye-only testing mode")
        start_time = time.time()
        
        results = await tester._test_birdeye_api_calls()
        total_time = time.time() - start_time
        
        summary = {
            "mode": "birdeye_only", 
            "total_time": round(total_time, 2),
            "total_tests": len(results),
            "successful": len([r for r in results if r.success]),
            "failed": len([r for r in results if not r.success]),
            "success_rate": round((len([r for r in results if r.success]) / len(results)) * 100, 1) if results else 0,
            "estimated_cost": f"${sum(float(r.cost_estimate.replace('$', '').replace('FREE', '0')) for r in results):.3f}",
            "category_breakdown": {"free": 0, "paid": len(results), "premium": 0},
            "service_summary": {"birdeye": {
                "total": len(results),
                "successful": len([r for r in results if r.success]),
                "failed": len([r for r in results if not r.success]),
                "cost": sum(float(r.cost_estimate.replace('$', '').replace('FREE', '0')) for r in results),
                "avg_response_time": sum(r.response_time for r in results if r.success) / max(len([r for r in results if r.success]), 1)
            }},
            "detailed_results": [r.to_dict() for r in results],
            "timestamp": datetime.now().isoformat()
        }
        
        tester.print_comprehensive_summary(summary)
        
        if args.save_results != "none":
            await save_results(summary, "birdeye_test", args.save_results)
        
        return
    
    if args.chainbase_only:
        if args.mode == 'mock':
            print(f"⚠️ Chainbase testing requires at least 'limited' mode")
            return
        
        print(f"🔗 Chainbase-only testing mode")
        start_time = time.time()
        
        results = await tester._test_chainbase_api_calls()
        total_time = time.time() - start_time
        
        summary = {
            "mode": "chainbase_only",
            "total_time": round(total_time, 2),
            "total_tests": len(results),
            "successful": len([r for r in results if r.success]),
            "failed": len([r for r in results if not r.success]),
            "success_rate": round((len([r for r in results if r.success]) / len(results)) * 100, 1) if results else 0,
            "estimated_cost": f"${sum(float(r.cost_estimate.replace('$', '').replace('FREE', '0')) for r in results):.3f}",
            "category_breakdown": {"free": 0, "paid": len(results), "premium": 0},
            "service_summary": {"chainbase": {
                "total": len(results),
                "successful": len([r for r in results if r.success]),
                "failed": len([r for r in results if not r.success]),
                "cost": sum(float(r.cost_estimate.replace('$', '').replace('FREE', '0')) for r in results),
                "avg_response_time": sum(r.response_time for r in results if r.success) / max(len([r for r in results if r.success]), 1)
            }},
            "detailed_results": [r.to_dict() for r in results],
            "timestamp": datetime.now().isoformat()
        }
        
        tester.print_comprehensive_summary(summary)
        
        if args.save_results != "none":
            await save_results(summary, "chainbase_test", args.save_results)
        
        return
    
    # Check if server needs to be started for mock mode
    if args.mode == 'mock' and args.start_server:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{args.url}/health", timeout=aiohttp.ClientTimeout(total=2)) as response:
                    pass  # Server is running
        except:
            print(f"🚀 Starting FastAPI server...")
            import subprocess
            
            try:
                server_process = subprocess.Popen([
                    "python", "-m", "uvicorn", "app.main:app", 
                    "--host", "0.0.0.0", "--port", "8000"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                await asyncio.sleep(3)
                print(f"   ✅ Server started")
            except Exception as e:
                print(f"   ❌ Could not start server: {e}")
    
    # Auto-confirm for paid testing if flag is set
    if args.confirm and args.mode in ['limited', 'full']:
        # Temporarily override the confirmation method
        original_confirm = tester._confirm_paid_testing
        tester._confirm_paid_testing = lambda: asyncio.sleep(0.1) or True
    
    # Run comprehensive tests
    summary = await tester.run_comprehensive_tests()
    tester.print_comprehensive_summary(summary)
    
    # Save results
    if args.save_results != "none":
        await save_results(summary, f"service_test_{args.mode}", args.save_results)


async def save_results(summary: Dict[str, Any], filename_prefix: str, save_option: str):
    """💾 Save test results to file"""
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    timestamp = int(time.time())
    
    if save_option == "auto":
        # Save with timestamp
        results_file = f"{filename_prefix}_{timestamp}.json"
        results_path = results_dir / results_file
        
        # Also save as latest
        latest_path = results_dir / f"latest_{filename_prefix.split('_')[-1]}.json"
    else:
        # Custom path
        results_path = Path(save_option)
        latest_path = None
    
    # Save main results
    with open(results_path, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n💾 Results saved to {results_path}")
    
    # Save latest if using auto
    if latest_path:
        with open(latest_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"💾 Latest results saved to {latest_path}")


if __name__ == "__main__":
    print("🧪 Comprehensive Service Testing Suite")
    print("=" * 40)
    print("🎯 Modes: mock (safe) → free → limited → full (expensive)")
    print("🔧 Services: SolanaFM (free), Birdeye, Chainbase, GOplus, etc.")
    print("💡 Use --help for all options")
    print()
    
    asyncio.run(main())