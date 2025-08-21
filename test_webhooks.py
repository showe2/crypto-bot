#!/usr/bin/env python3
"""
Webhook Performance Test - Measure response times
"""

import requests
import time
import json
import asyncio
import aiohttp

# Configuration
BASE_URL = "https://68342b6d262f.ngrok-free.app"  # Local testing
# BASE_URL = "https://your-ngrok-url.ngrok-free.app"  # For Helius testing

async def test_webhook_speed(session, endpoint: str, payload: dict):
    """Test webhook response time"""
    url = f"{BASE_URL}/webhooks/helius/{endpoint}"
    
    start_time = time.time()
    
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as response:
            await response.text()  # Read response
            response_time = (time.time() - start_time) * 1000
            
            return {
                "endpoint": endpoint,
                "status_code": response.status,
                "response_time_ms": round(response_time, 1),
                "success": response.status == 200
            }
    
    except asyncio.TimeoutError:
        return {
            "endpoint": endpoint,
            "status_code": 0,
            "response_time_ms": 5000,
            "success": False,
            "error": "TIMEOUT"
        }
    except Exception as e:
        return {
            "endpoint": endpoint, 
            "status_code": 0,
            "response_time_ms": (time.time() - start_time) * 1000,
            "success": False,
            "error": str(e)
        }

async def run_performance_tests():
    """Run comprehensive webhook performance tests"""
    
    print("🚀 Webhook Performance Test")
    print("=" * 50)
    
    # Test payloads
    test_payloads = {
        "mint": {
            "type": "NEW_TOKEN_MINT",
            "mint": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "blockTime": int(time.time()),
            "slot": 123456789,
            "signature": "test_signature_" + str(int(time.time()))
        },
        "pool": {
            "type": "NEW_LIQUIDITY_POOL",
            "pool": "8xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tokenA": "So11111111111111111111111111111111111112",
            "tokenB": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "blockTime": int(time.time()),
            "slot": 123456789
        },
        "tx": {
            "type": "LARGE_TRANSACTION", 
            "signature": "test_tx_" + str(int(time.time())),
            "amount": 1000000,
            "mint": "So11111111111111111111111111111111111112",
            "blockTime": int(time.time()),
            "slot": 123456789
        }
    }
    
    async with aiohttp.ClientSession() as session:
        
        # Test each endpoint multiple times
        for endpoint, payload in test_payloads.items():
            print(f"\n📊 Testing {endpoint} webhook:")
            print("-" * 30)
            
            results = []
            
            # Run 10 tests for each endpoint
            for i in range(10):
                result = await test_webhook_speed(session, endpoint, payload)
                results.append(result)
                
                status = "✅" if result["success"] else "❌"
                print(f"{status} Test {i+1}: {result['response_time_ms']}ms (Status: {result['status_code']})")
                
                if not result["success"] and "error" in result:
                    print(f"   Error: {result['error']}")
                
                # Small delay between tests
                await asyncio.sleep(0.1)
            
            # Calculate statistics
            successful_results = [r for r in results if r["success"]]
            
            if successful_results:
                response_times = [r["response_time_ms"] for r in successful_results]
                
                print(f"\n📈 Statistics for {endpoint}:")
                print(f"   Success rate: {len(successful_results)}/{len(results)} ({len(successful_results)/len(results)*100:.1f}%)")
                print(f"   Average response time: {sum(response_times)/len(response_times):.1f}ms")
                print(f"   Min response time: {min(response_times):.1f}ms")
                print(f"   Max response time: {max(response_times):.1f}ms")
                
                # Check if meets Helius requirements
                avg_time = sum(response_times)/len(response_times)
                max_time = max(response_times)
                
                if avg_time < 100:
                    print("   ✅ EXCELLENT: Average < 100ms")
                elif avg_time < 500:
                    print("   ✅ GOOD: Average < 500ms")
                elif avg_time < 1000:
                    print("   ⚠️  ACCEPTABLE: Average < 1000ms")
                else:
                    print("   ❌ TOO SLOW: Average > 1000ms")
                
                if max_time < 5000:
                    print("   ✅ Max time acceptable for Helius")
                else:
                    print("   ❌ Max time too slow for Helius")
            else:
                print(f"   ❌ ALL TESTS FAILED for {endpoint}")

async def main():
    """Main test function"""
    try:
        # Test connection first
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        print(f"✅ Server is running at {BASE_URL}")
                    else:
                        print(f"⚠️  Server responded with status {response.status}")
            except Exception as e:
                print(f"❌ Cannot connect to server: {str(e)}")
                print(f"   Make sure your app is running at {BASE_URL}")
                return
        
        # Run performance tests
        await run_performance_tests()
            
        print("\n" + "=" * 50)
        print("🎯 RECOMMENDATIONS:")
        print("✅ Response times < 100ms: Excellent for Helius")
        print("⚠️  Response times 100-500ms: Good, should work")
        print("❌ Response times > 1000ms: Too slow, will timeout")
        print("\n💡 If tests are slow:")
        print("1. Use the ultra-fast webhook handler")
        print("2. Remove blocking operations from main thread")
        print("3. Disable signature verification for testing")
        print("4. Check your internet connection")
        
    except KeyboardInterrupt:
        print("\n⏹️  Tests cancelled")
    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())