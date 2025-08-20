import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock, Mock
from pathlib import Path
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class TestResult:
    """Enhanced test result tracking"""
    def __init__(self, service: str, endpoint: str, success: bool, response_time: float, data: Any = None, error: str = None):
        self.service = service
        self.endpoint = endpoint
        self.success = success
        self.response_time = response_time
        self.data = data
        self.error = error
        self.timestamp = time.time()

class APITestMode(Enum):
    """API testing modes"""
    MOCK = "mock"
    HEALTH_ONLY = "health"
    LIMITED = "limited"
    FULL = "full"

# Test configuration
TEST_TOKENS = {
    "solana": [
        "So11111111111111111111111111111111111112",  # Wrapped SOL
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    ],
    "ethereum": [
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        "0xA0b86a33E6411E1e2d088c4dDfC1B8F31Efa6a95",  # ELF
        "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
    ]
}

@pytest.mark.services
class TestHeliusClient:
    """🌞 Advanced Helius API Client Tests"""
    
    @pytest.mark.asyncio
    async def test_helius_client_initialization(self):
        """Test Helius client initialization and configuration"""
        from app.services.helius_client import HeliusClient
        
        print("\n🌞 Testing Helius client initialization...")
        
        client = HeliusClient()
        assert client is not None
        assert hasattr(client, 'api_key')
        assert hasattr(client, 'rpc_url')
        assert hasattr(client, 'base_url')
        
        print(f"   ✅ Client initialized successfully")
        print(f"   📊 API key configured: {bool(client.api_key)}")
        print(f"   🔗 RPC URL: {client.rpc_url[:50]}..." if client.rpc_url else "   🔗 No RPC URL")
    
    @pytest.mark.asyncio
    async def test_helius_health_check_comprehensive(self):
        """Comprehensive Helius health check"""
        from app.services.helius_client import check_helius_health
        
        print("\n🌞 Running comprehensive Helius health check...")
        start_time = time.time()
        
        result = await check_helius_health()
        response_time = time.time() - start_time
        
        # Validate response structure
        assert isinstance(result, dict)
        assert "healthy" in result
        assert "api_key_configured" in result
        
        # Log detailed results
        print(f"   🏥 Health status: {'✅ Healthy' if result.get('healthy') else '❌ Unhealthy'}")
        print(f"   🔑 API key configured: {'✅ Yes' if result.get('api_key_configured') else '❌ No'}")
        print(f"   ⏱️ Response time: {response_time:.3f}s")
        
        if result.get("error"):
            print(f"   ⚠️ Error: {result['error']}")
        
        if result.get("response_time"):
            print(f"   📈 API response time: {result['response_time']:.3f}s")
    
    @pytest.mark.real_api
    @pytest.mark.helius
    @pytest.mark.asyncio
    async def test_helius_token_operations(self):
        """Test Helius token operations with real API calls"""
        from app.services.helius_client import HeliusClient
        
        print("\n🌞 Testing Helius token operations...")
        
        async with HeliusClient() as client:
            results = []
            
            for token_address in TEST_TOKENS["solana"][:2]:  # Test first 2 tokens
                print(f"   🪙 Testing token: {token_address[:8]}...{token_address[-4:]}")
                
                try:
                    # Test token metadata
                    start_time = time.time()
                    metadata = await client.get_token_metadata(token_address)
                    metadata_time = time.time() - start_time
                    
                    if metadata:
                        print(f"      ✅ Metadata: {metadata.get('name', 'Unknown')} ({metadata_time:.3f}s)")
                        results.append(TestResult("helius", "metadata", True, metadata_time, metadata))
                    else:
                        print(f"      ⚠️ No metadata available ({metadata_time:.3f}s)")
                        results.append(TestResult("helius", "metadata", False, metadata_time, error="No metadata"))
                    
                    # Test token supply
                    start_time = time.time()
                    supply = await client.get_token_supply(token_address)
                    supply_time = time.time() - start_time
                    
                    if supply:
                        total_supply = supply.get('value', {}).get('amount', 0)
                        decimals = supply.get('value', {}).get('decimals', 0)
                        print(f"      ✅ Supply: {total_supply} (decimals: {decimals}) ({supply_time:.3f}s)")
                        results.append(TestResult("helius", "supply", True, supply_time, supply))
                    else:
                        print(f"      ⚠️ No supply data available ({supply_time:.3f}s)")
                        results.append(TestResult("helius", "supply", False, supply_time, error="No supply data"))
                
                except Exception as e:
                    print(f"      ❌ Error: {str(e)}")
                    results.append(TestResult("helius", "token_ops", False, 0, error=str(e)))
                
                # Rate limiting
                await asyncio.sleep(0.5)
            
            # Summary
            successful = len([r for r in results if r.success])
            total = len(results)
            print(f"\n   📊 Helius operations summary: {successful}/{total} successful")
            
            assert len(results) > 0, "Should have at least some test results"


@pytest.mark.services
class TestBirdeyeClient:
    """🦅 Advanced Birdeye API Client Tests"""
    
    @pytest.mark.asyncio
    async def test_birdeye_client_initialization(self):
        """Test Birdeye client initialization and configuration"""
        from app.services.birdeye_client import BirdeyeClient
        
        print("\n🦅 Testing Birdeye client initialization...")
        
        client = BirdeyeClient()
        assert client is not None
        assert hasattr(client, 'api_key')
        assert hasattr(client, 'base_url')
        assert client.base_url == "https://public-api.birdeye.so"
        
        print(f"   ✅ Client initialized successfully")
        print(f"   📊 API key configured: {bool(client.api_key)}")
        print(f"   🔗 Base URL: {client.base_url}")
    
    @pytest.mark.asyncio
    async def test_birdeye_health_check_advanced(self):
        """Advanced Birdeye health check with performance metrics"""
        from app.services.birdeye_client import check_birdeye_health
        
        print("\n🦅 Running advanced Birdeye health check...")
        start_time = time.time()
        
        result = await check_birdeye_health()
        response_time = time.time() - start_time
        
        # Validate response
        assert isinstance(result, dict)
        assert "healthy" in result
        
        # Enhanced logging
        print(f"   🏥 Health status: {'✅ Healthy' if result.get('healthy') else '❌ Unhealthy'}")
        print(f"   🔑 API key configured: {'✅ Yes' if result.get('api_key_configured') else '❌ No'}")
        print(f"   ⏱️ Test response time: {response_time:.3f}s")
        
        if result.get("response_time"):
            print(f"   📈 API response time: {result['response_time']:.3f}s")
        
        if result.get("test_mode"):
            print(f"   🧪 Test mode: {result['test_mode']}")
        
        if result.get("error"):
            print(f"   ⚠️ Error: {result['error']}")
    
    @pytest.mark.real_api
    @pytest.mark.birdeye
    @pytest.mark.asyncio
    async def test_birdeye_market_operations(self):
        """Test Birdeye market operations with real API calls"""
        from app.services.birdeye_client import BirdeyeClient
        
        print("\n🦅 Testing Birdeye market operations...")
        
        async with BirdeyeClient() as client:
            results = []
            
            # Test price data
            for token_address in TEST_TOKENS["solana"][:2]:
                print(f"   💰 Testing price for: {token_address[:8]}...{token_address[-4:]}")
                
                try:
                    start_time = time.time()
                    price_data = await client.get_token_price(token_address)
                    price_time = time.time() - start_time
                    
                    if price_data:
                        price = price_data.get('value', 'N/A')
                        change_24h = price_data.get('price_change_24h_percent', 'N/A')
                        print(f"      ✅ Price: ${price} (24h: {change_24h}%) ({price_time:.3f}s)")
                        results.append(TestResult("birdeye", "price", True, price_time, price_data))
                    else:
                        print(f"      ⚠️ No price data available ({price_time:.3f}s)")
                        results.append(TestResult("birdeye", "price", False, price_time, error="No price data"))
                
                except Exception as e:
                    print(f"      ❌ Price error: {str(e)}")
                    results.append(TestResult("birdeye", "price", False, 0, error=str(e)))
                
                await asyncio.sleep(0.5)  # Rate limiting
            
            # Test trending tokens
            try:
                print(f"   📈 Testing trending tokens...")
                start_time = time.time()
                trending = await client.get_trending_tokens(limit=5)
                trending_time = time.time() - start_time
                
                if trending and len(trending) > 0:
                    print(f"      ✅ Found {len(trending)} trending tokens ({trending_time:.3f}s)")
                    for i, token in enumerate(trending[:3]):  # Show first 3
                        name = token.get('name', 'Unknown')
                        symbol = token.get('symbol', 'N/A')
                        rank = token.get('rank', i+1)
                        print(f"         {rank}. {name} ({symbol})")
                    results.append(TestResult("birdeye", "trending", True, trending_time, trending))
                else:
                    print(f"      ⚠️ No trending data available ({trending_time:.3f}s)")
                    results.append(TestResult("birdeye", "trending", False, trending_time, error="No trending data"))
            
            except Exception as e:
                print(f"      ❌ Trending error: {str(e)}")
                results.append(TestResult("birdeye", "trending", False, 0, error=str(e)))
            
            # Test top traders
            try:
                print(f"   👥 Testing top traders...")
                start_time = time.time()
                top_traders = await client.get_top_traders(TEST_TOKENS["solana"][0], limit=3)
                traders_time = time.time() - start_time
                
                if top_traders and len(top_traders) > 0:
                    print(f"      ✅ Found {len(top_traders)} top traders ({traders_time:.3f}s)")
                    results.append(TestResult("birdeye", "top_traders", True, traders_time, top_traders))
                else:
                    print(f"      ⚠️ No trader data available ({traders_time:.3f}s)")
                    results.append(TestResult("birdeye", "top_traders", False, traders_time, error="No trader data"))
            
            except Exception as e:
                print(f"      ❌ Traders error: {str(e)}")
                results.append(TestResult("birdeye", "top_traders", False, 0, error=str(e)))
            
            # Summary
            successful = len([r for r in results if r.success])
            total = len(results)
            avg_time = sum(r.response_time for r in results if r.success) / max(successful, 1)
            
            print(f"\n   📊 Birdeye operations summary: {successful}/{total} successful")
            print(f"   ⏱️ Average response time: {avg_time:.3f}s")


@pytest.mark.services
class TestChainbaseClient:
    """🔗 Advanced Chainbase API Client Tests"""
    
    @pytest.mark.asyncio
    async def test_chainbase_client_initialization(self):
        """Test Chainbase client initialization"""
        from app.services.chainbase_client import ChainbaseClient
        
        print("\n🔗 Testing Chainbase client initialization...")
        
        client = ChainbaseClient()
        assert client is not None
        assert hasattr(client, 'api_key')
        assert hasattr(client, 'base_url')
        
        print(f"   ✅ Client initialized successfully")
        print(f"   📊 API key configured: {bool(client.api_key)}")
        print(f"   🔗 Base URL: {client.base_url}")
    
    @pytest.mark.real_api
    @pytest.mark.chainbase
    @pytest.mark.asyncio
    async def test_chainbase_analytics_operations(self):
        """Test Chainbase analytics operations"""
        from app.services.chainbase_client import ChainbaseClient
        
        print("\n🔗 Testing Chainbase analytics operations...")
        
        async with ChainbaseClient() as client:
            results = []
            
            # Test Ethereum token (Chainbase works best with Ethereum)
            test_token = TEST_TOKENS["ethereum"][0]  # WETH
            print(f"   🪙 Testing token: {test_token[:8]}...{test_token[-4:]}")
            
            try:
                # Test token metadata
                start_time = time.time()
                metadata = await client.get_token_metadata(test_token, "ethereum")
                metadata_time = time.time() - start_time

                print(metadata)
                
                if metadata:
                    name = metadata.get('name', 'Unknown')
                    symbol = metadata.get('symbol', 'N/A')
                    decimals = metadata.get('decimals', 'N/A')
                    print(f"      ✅ Metadata: {name} ({symbol}) - {decimals} decimals ({metadata_time:.3f}s)")
                    results.append(TestResult("chainbase", "metadata", True, metadata_time, metadata))
                else:
                    print(f"      ⚠️ No metadata available ({metadata_time:.3f}s)")
                    results.append(TestResult("chainbase", "metadata", False, metadata_time, error="No metadata"))
                
                await asyncio.sleep(1)  # Rate limiting
                
                # Test token holders
                start_time = time.time()
                holders = await client.get_token_holders(test_token, "ethereum", limit=10)
                holders_time = time.time() - start_time
                
                if holders and holders.get('holders'):
                    holder_count = len(holders['holders'])
                    total_holders = holders.get('total_holders', 0)
                    print(f"      ✅ Holders: {holder_count} returned (total: {total_holders}) ({holders_time:.3f}s)")
                    
                    # Show top holder info
                    if holder_count > 0:
                        top_holder = holders['holders'][0]
                        percentage = top_holder.get('percentage', 0)
                        print(f"         Top holder: {percentage:.2f}% of supply")
                    
                    results.append(TestResult("chainbase", "holders", True, holders_time, holders))
                else:
                    print(f"      ⚠️ No holder data available ({holders_time:.3f}s)")
                    results.append(TestResult("chainbase", "holders", False, holders_time, error="No holder data"))
            
            except Exception as e:
                print(f"      ❌ Error: {str(e)}")
                results.append(TestResult("chainbase", "analytics", False, 0, error=str(e)))
            
            # Summary
            successful = len([r for r in results if r.success])
            total = len(results)
            print(f"\n   📊 Chainbase operations summary: {successful}/{total} successful")


@pytest.mark.services
class TestSolanaFMClient:
    """📊 Advanced SolanaFM API Client Tests"""
    
    @pytest.mark.asyncio
    async def test_solanafm_client_initialization(self):
        """Test SolanaFM client initialization"""
        from app.services.solanafm_client import SolanaFMClient
        
        print("\n📊 Testing SolanaFM client initialization...")
        
        client = SolanaFMClient()
        assert client is not None
        assert hasattr(client, 'base_url')
        assert client.base_url == "https://api.solana.fm"
        
        print(f"   ✅ Client initialized successfully")
        print(f"   🔗 Base URL: {client.base_url}")
        print(f"   💰 Service: FREE (no API key required)")
    
    @pytest.mark.real_api
    @pytest.mark.solanafm
    @pytest.mark.asyncio
    async def test_solanafm_comprehensive_operations(self):
        """Comprehensive SolanaFM operations test"""
        from app.services.solanafm_client import SolanaFMClient
        
        print("\n📊 Testing SolanaFM comprehensive operations...")
        
        async with SolanaFMClient() as client:
            results = []
            
            # Test well-known accounts
            test_accounts = [
                ("AK2VbkdYLHSiJKS6AGUfNZYNaejABkV6VYDX1Vrgxfo", "Test Account"),
                ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "USDC Token"),
                ("So11111111111111111111111111111111111112", "Wrapped SOL"),
            ]
            
            for account_address, account_name in test_accounts:
                print(f"   👤 Testing account: {account_name} ({account_address[:8]}...{account_address[-4:]})")
                
                try:
                    # Test account details
                    start_time = time.time()
                    account_detail = await client.get_account_detail(account_address)
                    account_time = time.time() - start_time
                    
                    if account_detail:
                        balance_sol = account_detail.get('balance_sol', 0)
                        friendly_name = account_detail.get('friendly_name', 'Unknown')
                        lamports = account_detail.get('lamports', 0)
                        
                        print(f"      ✅ Account: {friendly_name}")
                        print(f"         Balance: {balance_sol} SOL ({lamports} lamports)")
                        print(f"         Response time: {account_time:.3f}s")
                        
                        results.append(TestResult("solanafm", "account_detail", True, account_time, account_detail))
                    else:
                        print(f"      ⚠️ No account data available ({account_time:.3f}s)")
                        results.append(TestResult("solanafm", "account_detail", False, account_time, error="No account data"))
                
                except Exception as e:
                    print(f"      ❌ Account error: {str(e)}")
                    results.append(TestResult("solanafm", "account_detail", False, 0, error=str(e)))
                
                await asyncio.sleep(0.3)  # Rate limiting
            
            # Test token info for known tokens
            test_tokens = [
                ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "USDC"),
                ("So11111111111111111111111111111111111112", "Wrapped SOL"),
            ]
            
            for token_address, token_name in test_tokens:
                print(f"   🪙 Testing token: {token_name} ({token_address[:8]}...{token_address[-4:]})")
                
                try:
                    start_time = time.time()
                    token_info = await client.get_token_info(token_address)
                    token_time = time.time() - start_time
                    
                    if token_info:
                        name = token_info.get('name', 'Unknown')
                        symbol = token_info.get('symbol', 'N/A')
                        decimals = token_info.get('decimals', 'N/A')
                        token_type = token_info.get('token_type', 'N/A')
                        
                        print(f"      ✅ Token: {name} ({symbol})")
                        print(f"         Decimals: {decimals}, Type: {token_type}")
                        print(f"         Response time: {token_time:.3f}s")
                        
                        results.append(TestResult("solanafm", "token_info", True, token_time, token_info))
                    else:
                        print(f"      ⚠️ No token data available ({token_time:.3f}s)")
                        results.append(TestResult("solanafm", "token_info", False, token_time, error="No token data"))
                
                except Exception as e:
                    print(f"      ❌ Token error: {str(e)}")
                    results.append(TestResult("solanafm", "token_info", False, 0, error=str(e)))
                
                await asyncio.sleep(0.3)  # Rate limiting
            
            # Summary
            successful = len([r for r in results if r.success])
            total = len(results)
            avg_time = sum(r.response_time for r in results if r.success) / max(successful, 1)
            
            print(f"\n   📊 SolanaFM operations summary: {successful}/{total} successful")
            print(f"   ⏱️ Average response time: {avg_time:.3f}s")
            print(f"   💰 Total cost: FREE")


@pytest.mark.services
class TestGOplusClient:
    """🔒 Advanced GOplus API Client Tests"""
    
    @pytest.mark.asyncio
    async def test_goplus_client_initialization(self):
        """Test GOplus client initialization"""
        from app.services.goplus_client import GOplusClient
        
        print("\n🔒 Testing GOplus client initialization...")
        
        client = GOplusClient()
        assert client is not None
        assert hasattr(client, 'app_key')
        assert hasattr(client, 'app_secret')
        assert hasattr(client, 'base_url')
        assert client.base_url == "https://api.gopluslabs.io"
        
        print(f"   ✅ Client initialized successfully")
        print(f"   📊 APP key configured: {bool(client.app_key)}")
        print(f"   🔐 APP secret configured: {bool(client.app_secret)}")
        print(f"   🔗 Base URL: {client.base_url}")
    
    @pytest.mark.real_api
    @pytest.mark.goplus
    @pytest.mark.asyncio
    async def test_goplus_security_operations(self):
        """Test GOplus security operations"""
        from app.services.goplus_client import GOplusClient
        
        print("\n🔒 Testing GOplus security operations...")
        
        async with GOplusClient() as client:
            results = []
            
            # Test token security analysis
            test_scenarios = [
                ("0xA0b86a33E6411E1e2d088c4dDfC1B8F31Efa6a95", "ethereum", "ELF Token"),
                ("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "ethereum", "WETH"),
                ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "solana", "USDC-SOL"),
            ]
            
            for token_address, chain, token_name in test_scenarios:
                print(f"   🛡️ Testing security for: {token_name} ({chain})")
                print(f"      Address: {token_address[:8]}...{token_address[-4:]}")
                
                try:
                    start_time = time.time()
                    security_result = await client.analyze_token_security(token_address, chain)
                    security_time = time.time() - start_time
                    
                    if security_result:
                        is_honeypot = security_result.get("is_honeypot", False)
                        is_blacklisted = security_result.get("is_blacklisted", False)
                        buy_tax = security_result.get("buy_tax", "0")
                        sell_tax = security_result.get("sell_tax", "0")
                        warnings = security_result.get("warnings", [])
                        
                        print(f"      ✅ Security analysis completed ({security_time:.3f}s)")
                        print(f"         Honeypot: {'⚠️ YES' if is_honeypot else '✅ No'}")
                        print(f"         Blacklisted: {'⚠️ YES' if is_blacklisted else '✅ No'}")
                        print(f"         Buy Tax: {buy_tax}%, Sell Tax: {sell_tax}%")
                        
                        if warnings:
                            print(f"         ⚠️ Warnings: {len(warnings)} found")
                            for warning in warnings[:2]:  # Show first 2 warnings
                                print(f"            - {warning}")
                        
                        results.append(TestResult("goplus", "security", True, security_time, security_result))
                        break  # Success, no need to test more
                    else:
                        print(f"      ⚠️ No security data available ({security_time:.3f}s)")
                        results.append(TestResult("goplus", "security", False, security_time, error="No security data"))
                
                except Exception as e:
                    error_msg = str(e)
                    print(f"      ❌ Security error: {error_msg}")
                    
                    if "authentication" in error_msg.lower():
                        print(f"         💡 Check GOPLUS_APP_KEY and GOPLUS_APP_SECRET configuration")
                        results.append(TestResult("goplus", "security", False, 0, error="Authentication failed"))
                        break  # No point testing more if auth fails
                    else:
                        results.append(TestResult("goplus", "security", False, 0, error=error_msg))
                
                await asyncio.sleep(1)  # Rate limiting
            
            # Test comprehensive analysis if security worked
            if any(r.success for r in results):
                try:
                    print(f"   🔍 Testing comprehensive analysis...")
                    start_time = time.time()
                    comprehensive = await client.comprehensive_analysis(test_scenarios[0][0], test_scenarios[0][1])
                    comp_time = time.time() - start_time
                    
                    if comprehensive:
                        overall_assessment = comprehensive.get("overall_assessment", {})
                        risk_score = overall_assessment.get("risk_score", 0)
                        risk_level = overall_assessment.get("risk_level", "unknown")
                        is_safe = overall_assessment.get("is_safe")
                        
                        print(f"      ✅ Comprehensive analysis completed ({comp_time:.3f}s)")
                        print(f"         Risk Score: {risk_score}/100")
                        print(f"         Risk Level: {risk_level}")
                        print(f"         Assessment: {'✅ Safe' if is_safe else '⚠️ Risky' if is_safe is False else '❓ Unknown'}")
                        
                        results.append(TestResult("goplus", "comprehensive", True, comp_time, comprehensive))
                    else:
                        print(f"      ⚠️ No comprehensive data available ({comp_time:.3f}s)")
                        results.append(TestResult("goplus", "comprehensive", False, comp_time, error="No comprehensive data"))
                
                except Exception as e:
                    print(f"      ❌ Comprehensive analysis error: {str(e)}")
                    results.append(TestResult("goplus", "comprehensive", False, 0, error=str(e)))
            
            # Summary
            successful = len([r for r in results if r.success])
            total = len(results)
            total_cost = successful * 0.002  # Estimate cost
            
            print(f"\n   📊 GOplus operations summary: {successful}/{total} successful")
            print(f"   💰 Estimated cost: ${total_cost:.3f}")


@pytest.mark.services
class TestBlowfishClient:
    """🐡 Advanced Blowfish API Client Tests"""
    
    @pytest.mark.asyncio
    async def test_blowfish_client_initialization(self):
        """Test Blowfish client initialization"""
        from app.services.blowfish_client import BlowfishClient
        
        print("\n🐡 Testing Blowfish client initialization...")
        
        client = BlowfishClient()
        assert client is not None
        assert hasattr(client, 'api_key')
        assert hasattr(client, 'base_url')
        
        print(f"   ✅ Client initialized successfully")
        print(f"   📊 API key configured: {bool(client.api_key)}")
        print(f"   🔗 Base URL: {client.base_url}")
    
    @pytest.mark.asyncio
    async def test_blowfish_health_check_detailed(self):
        """Detailed Blowfish health check"""
        from app.services.blowfish_client import check_blowfish_health
        
        print("\n🐡 Running detailed Blowfish health check...")
        start_time = time.time()
        
        result = await check_blowfish_health()
        response_time = time.time() - start_time
        
        assert isinstance(result, dict)
        assert "healthy" in result
        
        print(f"   🏥 Health status: {'✅ Healthy' if result.get('healthy') else '❌ Unhealthy'}")
        print(f"   🔑 API key configured: {'✅ Yes' if result.get('api_key_configured') else '❌ No'}")
        print(f"   ⏱️ Response time: {response_time:.3f}s")
        
        if result.get("error"):
            print(f"   ⚠️ Error: {result['error']}")
            if "api key" in result["error"].lower():
                print(f"   💡 Get API key from: https://blowfish.xyz")


@pytest.mark.services
class TestDataImpulseClient:
    """📱 Advanced DataImpulse API Client Tests"""
    
    @pytest.mark.asyncio
    async def test_dataimpulse_client_initialization(self):
        """Test DataImpulse client initialization"""
        from app.services.dataimpulse_client import DataImpulseClient
        
        print("\n📱 Testing DataImpulse client initialization...")
        
        client = DataImpulseClient()
        assert client is not None
        assert hasattr(client, 'api_key')
        assert hasattr(client, 'base_url')
        
        print(f"   ✅ Client initialized successfully")
        print(f"   📊 API key configured: {bool(client.api_key)}")
        print(f"   🔗 Base URL: {client.base_url}")
    
    @pytest.mark.asyncio
    async def test_dataimpulse_health_check_comprehensive(self):
        """Comprehensive DataImpulse health check"""
        from app.services.dataimpulse_client import check_dataimpulse_health
        
        print("\n📱 Running comprehensive DataImpulse health check...")
        start_time = time.time()
        
        result = await check_dataimpulse_health()
        response_time = time.time() - start_time
        
        assert isinstance(result, dict)
        assert "healthy" in result
        
        print(f"   🏥 Health status: {'✅ Healthy' if result.get('healthy') else '❌ Unhealthy'}")
        print(f"   🔑 API key configured: {'✅ Yes' if result.get('api_key_configured') else '❌ No'}")
        print(f"   ⏱️ Response time: {response_time:.3f}s")
        
        if result.get("error"):
            print(f"   ⚠️ Error: {result['error']}")


@pytest.mark.services
class TestServiceManager:
    """🎛️ Advanced Service Manager Tests"""
    
    @pytest.mark.asyncio
    async def test_service_manager_initialization(self):
        """Test service manager initialization"""
        from app.services.service_manager import APIManager
        
        print("\n🎛️ Testing service manager initialization...")
        
        manager = APIManager()
        assert manager is not None
        assert hasattr(manager, 'clients')
        assert isinstance(manager.clients, dict)
        
        # Check all expected services are configured
        expected_services = ["helius", "chainbase", "birdeye", "blowfish", "dataimpulse", "solanafm", "goplus"]
        
        print(f"   ✅ Service manager initialized")
        print(f"   📊 Expected services: {len(expected_services)}")
        
        for service in expected_services:
            assert service in manager.clients
            print(f"      ✅ {service} client configured")
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_monitoring(self):
        """Comprehensive health monitoring test"""
        from app.services.service_manager import get_api_health_status
        
        print("\n🎛️ Running comprehensive health monitoring...")
        start_time = time.time()
        
        health = await get_api_health_status()
        monitoring_time = time.time() - start_time
        
        # Validate response structure
        assert isinstance(health, dict)
        assert "services" in health
        assert "overall_healthy" in health
        assert "summary" in health
        
        services = health.get("services", {})
        summary = health.get("summary", {})
        
        print(f"   🏥 Health check completed ({monitoring_time:.3f}s)")
        print(f"   📊 Total services: {summary.get('total_services', 0)}")
        print(f"   ✅ Healthy services: {summary.get('healthy_services', 0)}")
        print(f"   🔑 Configured services: {summary.get('configured_services', 0)}")
        print(f"   📈 Health percentage: {summary.get('health_percentage', 0)}%")
        
        # Detailed service status
        print(f"\n   📋 Service Status Details:")
        for service_name, service_health in services.items():
            status_icon = "✅" if service_health.get("healthy") else "❌"
            config_icon = "🔑" if service_health.get("api_key_configured") else "🔓"
            response_time = service_health.get("response_time", 0)
            
            print(f"      {status_icon} {config_icon} {service_name:12} ({response_time:.3f}s)")
            
            if service_health.get("error"):
                error_msg = service_health["error"]
                if len(error_msg) > 60:
                    error_msg = error_msg[:60] + "..."
                print(f"         ⚠️ {error_msg}")
        
        # Recommendations
        if health.get("recommendations"):
            print(f"\n   💡 Recommendations:")
            for rec in health["recommendations"][:3]:  # Show first 3
                print(f"      • {rec}")
        
        assert len(services) > 0, "Should have at least one service"
    
    @pytest.mark.asyncio
    async def test_token_analysis_pipeline(self):
        """Test comprehensive token analysis pipeline"""
        from app.services.service_manager import get_token_analysis
        
        print("\n🎛️ Testing token analysis pipeline...")
        
        test_token = "So11111111111111111111111111111111111112"  # Wrapped SOL
        print(f"   🪙 Analyzing token: {test_token[:8]}...{test_token[-4:]}")
        
        start_time = time.time()
        analysis = await get_token_analysis(test_token)
        analysis_time = time.time() - start_time
        
        # Validate analysis structure
        assert isinstance(analysis, dict)
        assert "token_address" in analysis
        assert analysis["token_address"] == test_token
        
        print(f"   ✅ Analysis completed ({analysis_time:.3f}s)")
        print(f"   📊 Data sources: {len(analysis.get('data_sources', []))}")
        print(f"   ⏱️ Processing time: {analysis.get('processing_time', 0):.3f}s")
        
        # Check different data sections
        sections = ["metadata", "price_data", "security_analysis", "solanafm_data", "goplus_analysis"]
        for section in sections:
            if section in analysis and analysis[section]:
                source_count = len(analysis[section]) if isinstance(analysis[section], dict) else 1
                print(f"      ✅ {section}: {source_count} source(s)")
            else:
                print(f"      ⚠️ {section}: No data")
        
        # Show standardized data if available
        if "standardized" in analysis:
            std_data = analysis["standardized"]
            print(f"\n   📋 Standardized Analysis:")
            
            # Basic info
            basic_info = std_data.get("basic_info", {})
            if basic_info:
                name = basic_info.get("name", "Unknown")
                symbol = basic_info.get("symbol", "N/A")
                decimals = basic_info.get("decimals", "N/A")
                print(f"      🪙 Token: {name} ({symbol}) - {decimals} decimals")
            
            # Price info
            price_info = std_data.get("price_info", {})
            if price_info.get("current_price"):
                price = price_info["current_price"]
                change = price_info.get("price_change_24h", "N/A")
                print(f"      💰 Price: ${price} (24h: {change}%)")
            
            # Security info
            security_info = std_data.get("security_info", {})
            if security_info:
                risk_score = security_info.get("average_risk_score", 0)
                is_high_risk = security_info.get("is_high_risk", False)
                flags_count = len(security_info.get("security_flags", []))
                
                risk_icon = "🔴" if is_high_risk else "🟡" if risk_score > 30 else "🟢"
                print(f"      {risk_icon} Security: Risk score {risk_score}/100, {flags_count} flags")
            
            # SolanaFM summary
            solanafm_summary = std_data.get("solanafm_summary", {})
            if solanafm_summary:
                print(f"      📊 SolanaFM: Enhanced data available")
            
            # GOplus summary
            goplus_summary = std_data.get("goplus_summary", {})
            if goplus_summary:
                risk_level = goplus_summary.get("risk_level", "unknown")
                is_safe = goplus_summary.get("is_safe")
                safety_icon = "✅" if is_safe else "⚠️" if is_safe is False else "❓"
                print(f"      🔒 GOplus: {safety_icon} Risk level: {risk_level}")
        
        # Error summary
        if analysis.get("errors"):
            error_count = len(analysis["errors"])
            print(f"   ⚠️ Errors encountered: {error_count}")
            for error in analysis["errors"][:3]:  # Show first 3 errors
                print(f"      • {error}")


# Test configuration and utilities
@pytest.mark.services
class TestConfiguration:
    """⚙️ Test Configuration and Setup"""
    
    @pytest.mark.asyncio
    async def test_environment_setup(self):
        """Test environment setup and configuration"""
        from app.core.config import get_settings
        
        print("\n⚙️ Testing environment setup...")
        
        settings = get_settings()
        assert settings is not None
        
        print(f"   ✅ Settings loaded successfully")
        print(f"   🌍 Environment: {settings.ENV}")
        print(f"   🐛 Debug mode: {settings.DEBUG}")
        print(f"   🔌 Port: {settings.PORT}")
        
        # Check critical API key status
        api_key_status = settings.get_all_api_keys_status()
        
        print(f"\n   🔑 API Key Configuration Status:")
        configured_count = 0
        total_keys = len(api_key_status)
        
        for key_name, status in api_key_status.items():
            is_configured = status.get("configured", False)
            if is_configured:
                configured_count += 1
            
            icon = "✅" if is_configured else "❌"
            masked_value = status.get("masked_value", "Not set")
            print(f"      {icon} {key_name}: {masked_value}")
        
        print(f"\n   📊 Configuration Summary: {configured_count}/{total_keys} keys configured")
        
        if configured_count == 0:
            print(f"   💡 To configure API keys, add them to your .env file")
        elif configured_count < total_keys:
            print(f"   💡 Some services may have limited functionality")
        else:
            print(f"   🎉 All API keys configured - full functionality available")


# Performance testing
@pytest.mark.services
@pytest.mark.slow
class TestPerformance:
    """⚡ Performance Testing Suite"""
    
    @pytest.mark.asyncio
    async def test_concurrent_service_calls(self):
        """Test concurrent service calls performance"""
        print("\n⚡ Testing concurrent service calls performance...")
        
        from app.services.service_manager import get_api_health_status
        
        # Test multiple concurrent health checks
        concurrent_calls = 5
        print(f"   🔄 Running {concurrent_calls} concurrent health checks...")
        
        start_time = time.time()
        
        tasks = [get_api_health_status() for _ in range(concurrent_calls)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        successful_calls = len([r for r in results if isinstance(r, dict) and not isinstance(r, Exception)])
        
        print(f"   ✅ Completed {successful_calls}/{concurrent_calls} calls successfully")
        print(f"   ⏱️ Total time: {total_time:.3f}s")
        print(f"   📈 Average time per call: {total_time/concurrent_calls:.3f}s")
        print(f"   🚀 Calls per second: {concurrent_calls/total_time:.2f}")
        
        # Performance assertions
        assert total_time < 30.0, f"Concurrent calls took too long: {total_time}s"
        assert successful_calls >= concurrent_calls * 0.8, f"Too many failed calls: {successful_calls}/{concurrent_calls}"
    
    @pytest.mark.asyncio
    async def test_service_response_times(self):
        """Test individual service response times"""
        print("\n⚡ Testing individual service response times...")
        
        from app.services.service_manager import APIManager
        
        manager = APIManager()
        response_times = {}
        
        # Test each service health check individually
        service_health_checks = {
            "helius": "app.services.helius_client.check_helius_health",
            "birdeye": "app.services.birdeye_client.check_birdeye_health", 
            "chainbase": "app.services.chainbase_client.check_chainbase_health",
            "blowfish": "app.services.blowfish_client.check_blowfish_health",
            "solanafm": "app.services.solanafm_client.check_solanafm_health",
            "dataimpulse": "app.services.dataimpulse_client.check_dataimpulse_health",
            "goplus": "app.services.goplus_client.check_goplus_health"
        }
        
        for service_name, import_path in service_health_checks.items():
            try:
                module_path, function_name = import_path.rsplit('.', 1)
                module = __import__(module_path, fromlist=[function_name])
                health_check_func = getattr(module, function_name)
                
                start_time = time.time()
                result = await health_check_func()
                response_time = time.time() - start_time
                
                response_times[service_name] = response_time
                
                status_icon = "✅" if result.get("healthy") else "⚠️"
                cost_info = " (FREE)" if service_name in ["solanafm"] else ""
                
                print(f"   {status_icon} {service_name:12} {response_time:6.3f}s{cost_info}")
                
            except Exception as e:
                print(f"   ❌ {service_name:12} ERROR: {str(e)}")
        
        # Performance summary
        if response_times:
            avg_response_time = sum(response_times.values()) / len(response_times)
            fastest_service = min(response_times.items(), key=lambda x: x[1])
            slowest_service = max(response_times.items(), key=lambda x: x[1])
            
            print(f"\n   📊 Performance Summary:")
            print(f"      ⚡ Fastest: {fastest_service[0]} ({fastest_service[1]:.3f}s)")
            print(f"      🐌 Slowest: {slowest_service[0]} ({slowest_service[1]:.3f}s)")
            print(f"      📈 Average: {avg_response_time:.3f}s")
            
            # Performance assertions
            assert avg_response_time < 5.0, f"Average response time too slow: {avg_response_time}s"
            assert fastest_service[1] < 10.0, f"Even fastest service is too slow: {fastest_service[1]}s"


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with enhanced markers"""
    config.addinivalue_line("markers", "services: API service tests")
    config.addinivalue_line("markers", "real_api: Tests with real API calls (may cost money)")
    config.addinivalue_line("markers", "helius: Helius API specific tests")
    config.addinivalue_line("markers", "birdeye: Birdeye API specific tests")
    config.addinivalue_line("markers", "chainbase: Chainbase API specific tests")
    config.addinivalue_line("markers", "blowfish: Blowfish API specific tests")
    config.addinivalue_line("markers", "solanafm: SolanaFM API specific tests")
    config.addinivalue_line("markers", "dataimpulse: DataImpulse API specific tests")
    config.addinivalue_line("markers", "goplus: GOplus API specific tests")
    config.addinivalue_line("markers", "slow: Slow tests that can be skipped")


if __name__ == "__main__":
    print("🧪 Advanced API Client Testing Suite")
    print("=====================================")
    print("Available test modes:")
    print("  pytest tests/services/test_api_clients.py -v              # All mock tests")
    print("  pytest tests/services/test_api_clients.py -v -m \"not real_api\"  # Mock only")
    print("  pytest tests/services/test_api_clients.py -v -m \"real_api\"      # Real API calls")
    print("  pytest tests/services/test_api_clients.py -v -m \"solanafm\"      # SolanaFM only")
    print("  pytest tests/services/test_api_clients.py -v -m \"goplus\"        # GOplus only")
    print("")
    print("⚠️  Real API tests may consume credits/cost money!")
    print("💡 Use mock tests for development and CI/CD")
    
    pytest.main([__file__, "-v", "--tb=short", "-m", "not real_api"])