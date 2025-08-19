#!/usr/bin/env python3
"""
GOplus Diagnostic Test
Debug what's happening with GOplus API responses
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

async def test_goplus_response():
    """Test GOplus API and show detailed response"""
    
    print("🔒 GOplus API Diagnostic Test")
    print("="*50)
    
    try:
        from app.services.goplus_client import GOplusClient
        
        async with GOplusClient() as client:
            # Check API key configuration
            print(f"Security API Key: {'✅ Configured' if client.security_app_key else '❌ Missing'}")
            print(f"Security API Secret: {'✅ Configured' if client.security_app_secret else '❌ Missing'}")
            
            if not client.security_app_key or not client.security_app_secret:
                print("\n❌ API keys not configured!")
                print("Set these in your .env file:")
                print("GOPLUS_SECURITY_APP_KEY=your_key_here")
                print("GOPLUS_SECURITY_APP_SECRET=your_secret_here")
                return
            
            print(f"API Key (masked): {client.security_app_key[:8]}***")
            print(f"API Secret (masked): {client.security_app_secret[:8]}***")
            print(f"Base URL: {client.base_url}")
            
            # Test with a known Ethereum token
            test_token = "0xA0b86a33E6411E1e2d088c4dDfC1B8F31Efa6a95"  # ELF token
            print(f"\n🧪 Testing with token: {test_token}")
            print(f"Chain: ethereum (ID: 1)")
            
            try:
                result = await client.analyze_token_security(test_token, "ethereum")
                
                print(f"\n📊 Response Analysis:")
                print(f"Response type: {type(result)}")
                
                if result is None:
                    print("❌ Result is None - no data returned")
                elif isinstance(result, dict):
                    print(f"✅ Response is a dictionary with {len(result)} keys")
                    print(f"Keys: {list(result.keys())}")
                    
                    # Show each field in detail
                    for key, value in result.items():
                        if value is not None:
                            if isinstance(value, dict):
                                print(f"  {key}: dict with {len(value)} keys -> {list(value.keys())}")
                                # Show some sample values
                                for subkey, subvalue in list(value.items())[:3]:
                                    print(f"    {subkey}: {str(subvalue)[:50]}")
                                if len(value) > 3:
                                    print(f"    ... and {len(value) - 3} more fields")
                            elif isinstance(value, list):
                                print(f"  {key}: list with {len(value)} items")
                                if value:
                                    print(f"    Sample: {str(value[0])[:50]}")
                            else:
                                print(f"  {key}: {type(value).__name__} = {str(value)[:100]}")
                        else:
                            print(f"  {key}: None")
                    
                    # Check for specific expected fields
                    expected_fields = [
                        "token_address", "chain", "risk_level", "security_score",
                        "is_malicious", "is_honeypot", "contract_security", 
                        "trading_security", "metadata", "warnings"
                    ]
                    
                    print(f"\n🔍 Expected Field Analysis:")
                    for field in expected_fields:
                        if field in result:
                            value = result[field]
                            if value is not None:
                                print(f"  ✅ {field}: {type(value).__name__} = {str(value)[:50]}")
                            else:
                                print(f"  ⚠️ {field}: present but None")
                        else:
                            print(f"  ❌ {field}: missing")
                    
                    # Check if this looks like a successful response
                    has_security_data = any([
                        result.get("risk_level"),
                        result.get("security_score") is not None,
                        result.get("is_malicious") is not None,
                        result.get("contract_security"),
                        result.get("trading_security")
                    ])
                    
                    print(f"\n🎯 Assessment:")
                    if has_security_data:
                        print("✅ Response contains security data - GOplus is working!")
                        
                        # Show key findings
                        risk_level = result.get("risk_level", "unknown")
                        is_malicious = result.get("is_malicious", False)
                        security_score = result.get("security_score", "unknown")
                        
                        print(f"  Risk Level: {risk_level}")
                        print(f"  Security Score: {security_score}")
                        print(f"  Malicious: {is_malicious}")
                        
                        warnings = result.get("warnings", [])
                        if warnings:
                            print(f"  Warnings: {warnings}")
                        
                    else:
                        print("❌ Response lacks expected security data")
                        print("This might indicate:")
                        print("  • Token not found in GOplus database")
                        print("  • API response format changed")
                        print("  • Account limitations")
                        
                else:
                    print(f"❌ Unexpected response type: {type(result)}")
                    print(f"Response: {str(result)[:200]}")
                
            except Exception as api_error:
                print(f"\n❌ API Error: {str(api_error)}")
                
                error_msg = str(api_error).lower()
                if "signature verification" in error_msg:
                    print("🔧 Issue: Signature verification failed")
                    print("   Check that your APP_KEY and APP_SECRET are a matching pair")
                elif "invalid credentials" in error_msg:
                    print("🔧 Issue: Invalid credentials")
                    print("   Check your GOplus account status and API key validity")
                elif "rate limit" in error_msg:
                    print("🔧 Issue: Rate limited")
                    print("   Wait a moment before trying again")
                elif "timeout" in error_msg:
                    print("🔧 Issue: Request timeout")
                    print("   GOplus API might be slow, try again")
                else:
                    print("🔧 Issue: Unknown error")
                    print(f"   Full error: {str(api_error)}")
            
            # Test a second token for comparison
            print(f"\n🧪 Testing second token for comparison...")
            test_token2 = "0xdAC17F958D2ee523a2206206994597C13D831ec7"  # USDT
            print(f"Token: {test_token2}")
            
            try:
                result2 = await client.analyze_token_security(test_token2, "ethereum")
                if result2:
                    print("✅ Second token also returned data - API is working consistently")
                else:
                    print("⚠️ Second token returned no data - might be token-specific")
            except Exception as e2:
                print(f"❌ Second token failed: {str(e2)}")
    
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running from the project root directory")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(test_goplus_response())