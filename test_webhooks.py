#!/usr/bin/env python3
"""
Quick webhook test without signature verification
"""

import requests
import json
import time

# Configuration
BASE_URL = "https://b14ed1080bda.ngrok-free.app"  # Используйте ваш ngrok URL когда готово

def test_webhook_fast(endpoint: str):
    """Test webhook endpoint with minimal payload"""
    url = f"{BASE_URL}/webhooks/helius/{endpoint}"
    
    # Minimal test payload
    payload = {
        "type": f"TEST_{endpoint.upper()}",
        "timestamp": int(time.time())
    }
    
    print(f"🧪 Testing {endpoint} webhook...")
    print(f"📡 URL: {url}")
    
    try:
        # Fast request with short timeout
        response = requests.post(
            url, 
            json=payload, 
            timeout=5,  # 5 second timeout
            headers={"Content-Type": "application/json"}
        )
        
        print(f"✅ Status: {response.status_code}")
        print(f"⏰ Response time: {response.elapsed.total_seconds():.2f}s")
        print(f"📄 Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhook working!")
        else:
            print("⚠️  Webhook returned non-200 status")
            
    except requests.exceptions.Timeout:
        print("❌ Timeout! Webhook too slow")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - is server running?")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    print("-" * 50)

def main():
    """Test all webhook endpoints"""
    print("🚀 Quick Webhook Test")
    print("=" * 30)
    
    # Test each endpoint
    endpoints = ["mint", "pool", "tx"]
    
    for endpoint in endpoints:
        test_webhook_fast(endpoint)
    
    print("🎉 Tests completed!")
    print()
    print("💡 If you see timeouts:")
    print("1. Make sure your app is running")
    print("2. Check ngrok is forwarding correctly")
    print("3. Look at app logs for errors")

if __name__ == "__main__":
    main()