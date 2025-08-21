#!/usr/bin/env python3
"""
Helper script to setup Helius webhooks with ngrok URLs
"""

import os
import json
import requests
import sys
from typing import Dict, Any, Optional

class HeliusWebhookHelper:
    def __init__(self):
        self.ngrok_url = None
        self.helius_api_key = None
        self.webhook_secret = None
        self.load_config()
    
    def load_config(self):
        """Load configuration from .env and ngrok"""
        # Load from .env
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('HELIUS_API_KEY='):
                        self.helius_api_key = line.split('=', 1)[1].strip()
                    elif line.startswith('HELIUS_WEBHOOK_SECRET='):
                        self.webhook_secret = line.split('=', 1)[1].strip()
                    elif line.startswith('WEBHOOK_BASE_URL='):
                        self.ngrok_url = line.split('=', 1)[1].strip()
        
        # Try to get ngrok URL from API if not in .env
        if not self.ngrok_url:
            self.ngrok_url = self.get_ngrok_url()
    
    def get_ngrok_url(self) -> Optional[str]:
        """Get ngrok public URL from local API"""
        try:
            response = requests.get('http://localhost:4040/api/tunnels', timeout=5)
            data = response.json()
            
            for tunnel in data.get('tunnels', []):
                if tunnel.get('proto') == 'https':
                    return tunnel['public_url']
                    
        except Exception as e:
            print(f"❌ Could not get ngrok URL: {e}")
            
        return None
    
    def generate_webhook_config(self) -> Dict[str, str]:
        """Generate webhook configuration"""
        if not self.ngrok_url:
            raise ValueError("No ngrok URL available")
        
        base_url = self.ngrok_url.rstrip('/')
        
        return {
            "mint_webhook": f"{base_url}/webhooks/helius/mint",
            "pool_webhook": f"{base_url}/webhooks/helius/pool", 
            "transaction_webhook": f"{base_url}/webhooks/helius/tx",
            "webhook_secret": self.webhook_secret or "your_webhook_secret_here",
            "base_url": base_url
        }
    
    def test_webhook_connectivity(self) -> bool:
        """Test if webhooks are reachable"""
        if not self.ngrok_url:
            return False
        
        test_url = f"{self.ngrok_url}/webhooks/status"
        
        try:
            response = requests.get(test_url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Webhook connectivity test failed: {e}")
            return False
    
    def print_setup_instructions(self):
        """Print setup instructions for Helius Dashboard"""
        try:
            config = self.generate_webhook_config()
        except ValueError as e:
            print(f"❌ Error: {e}")
            print("\n💡 Make sure ngrok is running: ngrok http 8000")
            return
        
        print("🎯 HELIUS WEBHOOK SETUP INSTRUCTIONS")
        print("=" * 50)
        print()
        
        if self.test_webhook_connectivity():
            print("✅ Webhook endpoints are reachable!")
        else:
            print("⚠️  Webhook endpoints may not be reachable")
            print("   Make sure your app is running!")
        
        print()
        print("📋 Copy these URLs to your Helius Dashboard:")
        print()
        print(f"🔗 Mint Webhook URL:")
        print(f"   {config['mint_webhook']}")
        print()
        print(f"🔗 Pool Webhook URL:")
        print(f"   {config['pool_webhook']}")
        print()
        print(f"🔗 Transaction Webhook URL:")
        print(f"   {config['transaction_webhook']}")
        print()
        print(f"🔐 Webhook Secret:")
        print(f"   {config['webhook_secret']}")
        print()
        print("📖 Setup Steps:")
        print("1. Go to https://dashboard.helius.xyz")
        print("2. Navigate to 'Webhooks' section")
        print("3. Click 'Create Webhook'")
        print("4. Choose webhook type (Token Mint, Pool, etc.)")
        print("5. Paste the corresponding URL from above")
        print("6. Set the webhook secret")
        print("7. Save and activate")
        print()
        print("🧪 Test your webhooks:")
        print(f"   {config['base_url']}/webhooks/status")
        print(f"   {config['base_url']}/webhooks/health")
        print()
    
    def create_helius_webhook_via_api(self, webhook_type: str, events: list):
        """Create webhook via Helius API (if API key is available)"""
        if not self.helius_api_key:
            print("❌ HELIUS_API_KEY not found in .env")
            return False
        
        # Note: This is a placeholder - actual Helius API endpoints may differ
        # Check Helius documentation for correct API endpoints
        print(f"🔧 Creating {webhook_type} webhook via API...")
        print("⚠️  Note: API webhook creation depends on Helius API availability")
        print("   Manual setup via dashboard is recommended")
        
        return False
    
    def save_config_file(self):
        """Save webhook configuration to JSON file"""
        try:
            config = self.generate_webhook_config()
            
            with open('webhook_config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ Configuration saved to webhook_config.json")
            
        except Exception as e:
            print(f"❌ Error saving config: {e}")


def main():
    """Main function"""
    print("🚀 Helius Webhook Setup Helper")
    print("=" * 40)
    
    helper = HeliusWebhookHelper()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "config":
            helper.save_config_file()
        elif command == "test":
            if helper.test_webhook_connectivity():
                print("✅ Webhooks are reachable!")
            else:
                print("❌ Webhooks are not reachable")
        elif command == "url":
            if helper.ngrok_url:
                print(f"ngrok URL: {helper.ngrok_url}")
            else:
                print("❌ No ngrok URL found")
        else:
            print(f"Unknown command: {command}")
            print("Available commands: config, test, url")
    else:
        helper.print_setup_instructions()


if __name__ == "__main__":
    main()