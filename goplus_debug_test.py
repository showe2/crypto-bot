#!/usr/bin/env python3
"""
Simple GOplus API test script
Test the GOplus client with bearer token authentication
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def test_goplus_authentication():
    """Test GOplus authentication and basic functionality"""
    print("🔒 Testing GOplus API Authentication")
    print("=" * 50)
    
    try:
        from app.services.goplus_client import GOplusClient, check_goplus_health
        from app.core.config import get_settings
        
        # Check configuration
        settings = get_settings()
        app_key = getattr(settings, 'GOPLUS_APP_KEY', None)
        app_secret = getattr(settings, 'GOPLUS_APP_SECRET', None)
        
        print(f"APP_KEY configured: {bool(app_key)}")
        print(f"APP_SECRET configured: {bool(app_secret)}")
        
        if not app_key or not app_secret:
            print("\n❌ Missing GOplus credentials!")
            print("Set the following in your .env file:")
            print("GOPLUS_APP_KEY=your_app_key_here")
            print("GOPLUS_APP_SECRET=your_app_secret_here")
            print("\nGet your credentials from: https://gopluslabs.io/")
            return False
        
        print(f"APP_KEY: {app_key[:8]}{'*' * 8}")
        print(f"Base URL: {settings.GOPLUS_BASE_URL}")
        
        # Test health check
        print("\n🏥 Testing health check...")
        health = await check_goplus_health()
        
        print(f"Healthy: {health.get('healthy')}")
        print(f"API Key Configured: {health.get('api_key_configured')}")
        
        if health.get('error'):
            print(f"Error: {health['error']}")
            return False
        
        if not health.get('healthy'):
            print("❌ Health check failed")
            return False
        
        print("✅ Health check passed!")
        
        # Test basic functionality
        print("\n🛡️ Testing token security analysis...")
        
        async with GOplusClient() as client:
            # Test with a well-known Ethereum token
            test_token = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # ELF token
            
            try:
                print(f"Analyzing token: {test_token}")
                result = await client.analyze_token_security(test_token, "ethereum")
                
                if result:
                    print("✅ Token security analysis successful!")
                    print(f"Token: {result.get('metadata', {}).get('token_name', 'Unknown')}")
                    print(f"Symbol: {result.get('metadata', {}).get('token_symbol', 'Unknown')}")
                    print(f"Is Honeypot: {result.get('is_honeypot', False)}")
                    print(f"Is Blacklisted: {result.get('is_blacklisted', False)}")
                    print(f"Buy Tax: {result.get('buy_tax', '0')}%")
                    print(f"Sell Tax: {result.get('sell_tax', '0')}%")
                    
                    warnings = result.get('warnings', [])
                    if warnings:
                        print(f"Warnings: {', '.join(warnings[:3])}")
                    else:
                        print("No warnings found")
                        
                    return True
                else:
                    print("❌ No security data returned")
                    return False
                    
            except Exception as e:
                print(f"❌ Token security analysis failed: {e}")
                return False
                
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running from the project root directory")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

async def test_supported_chains():
    """Test supported chains endpoint"""
    print("\n🔗 Testing supported chains...")
    
    try:
        from app.services.goplus_client import GOplusClient
        
        async with GOplusClient() as client:
            chains = await client.get_supported_chains()
            
            if chains:
                print(f"✅ Found {len(chains)} supported chains:")
                for chain in chains[:10]:  # Show first 10
                    if isinstance(chain, dict):
                        name = chain.get('name', 'Unknown')
                        chain_id = chain.get('chain_id', 'Unknown')
                        supported = chain.get('supported', False)
                        status = "✅" if supported else "❌"
                        print(f"  {status} {name} (ID: {chain_id})")
                
                return True
            else:
                print("❌ No chains data returned")
                return False
                
    except Exception as e:
        print(f"❌ Supported chains test failed: {e}")
        return False

async def main():
    """Run all GOplus tests"""
    print("🚀 Starting GOplus API Tests")
    print("=" * 50)
    
    # Test authentication and basic functionality
    auth_success = await test_goplus_authentication()
    
    if auth_success:
        # Test additional endpoints
        await test_supported_chains()
        
        print("\n🎉 All GOplus tests completed successfully!")
        print("\nNext steps:")
        print("- Your GOplus integration is working")
        print("- You can now use GOplus in your token analysis")
        print("- Run the full test suite: python tests/services/test_services.py --mode limited")
    else:
        print("\n❌ GOplus tests failed")
        print("\nTroubleshooting:")
        print("1. Check your .env file has GOPLUS_APP_KEY and GOPLUS_APP_SECRET")
        print("2. Verify your GOplus account is active")
        print("3. Check your internet connection")
        print("4. Visit https://gopluslabs.io/ for support")

if __name__ == "__main__":
    asyncio.run(main())