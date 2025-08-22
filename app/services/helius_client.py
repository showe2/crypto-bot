import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from decimal import Decimal
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class HeliusAPIError(Exception):
    """Helius API specific errors"""
    pass


class HeliusClient:
    """Helius API client for Solana blockchain data"""
    
    def __init__(self):
        self.api_key = settings.HELIUS_API_KEY
        self.rpc_url = settings.get_helius_rpc_url()
        self.base_url = settings.HELIUS_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.1  # 100ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        if not self.api_key:
            logger.warning("Helius API key not configured")
    
    async def __aenter__(self):
        """Async context manager entry"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _ensure_session(self):
        """Ensure session is available"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)
        
        self._last_request_time = time.time()
    
    async def _request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling and rate limiting"""
        await self._ensure_session()
        await self._rate_limit()
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                response_data = await response.json()
                
                if response.status == 200:
                    return response_data
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 1))
                    logger.warning(f"Helius rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, url, **kwargs)
                else:
                    error_msg = response_data.get('error', f'HTTP {response.status}')
                    raise HeliusAPIError(f"Helius API error: {error_msg}")
                    
        except asyncio.TimeoutError:
            raise HeliusAPIError("Helius API request timeout")
        except aiohttp.ClientError as e:
            raise HeliusAPIError(f"Helius client error: {str(e)}")
    
    async def _rpc_request(self, method: str, params: List[Any] = None) -> Dict[str, Any]:
        """Make RPC request to Helius"""
        if not self.api_key:
            raise HeliusAPIError("Helius API key not configured")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or []
        }
        
        response = await self._request(
            "POST",
            self.base_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            params={"api-key": self.api_key}
        )
        
        if "error" in response:
            raise HeliusAPIError(f"RPC error: {response['error']}")
        
        return response.get("result", {})
    
    async def get_token_accounts(self, mint_address: str) -> List[Dict[str, Any]]:
        """Get token accounts (holders) for a token"""
        try:
            result = await self._rpc_request("getTokenLargestAccounts", [mint_address])
            
            if not result or "value" not in result:
                return []
            
            holders = []
            for account in result["value"]:
                holder_info = {
                    "address": account.get("address"),
                    "amount": account.get("amount"),
                    "decimals": account.get("decimals"),
                    "ui_amount": account.get("uiAmount"),
                    "ua_amount_string": account.get("uiAmountString"),
                }
                holders.append(holder_info)
            
            return holders
            
        except Exception as e:
            logger.error(f"Error getting token accounts for {mint_address}: {str(e)}")
            return []
    
    async def get_token_supply(self, mint_address: str) -> Dict[str, Any]:
        """Get token supply information"""
        try:
            result = await self._rpc_request("getTokenSupply", [mint_address])
            
            if not result or "value" not in result:
                return None
            
            supply_info = result["value"]
            return {
                "amount": supply_info.get("amount"),
                "decimals": supply_info.get("decimals"),
                "ui_amount": supply_info.get("uiAmount"),
                "ui_amount_string": supply_info.get("uiAmountString")
            }
            
        except Exception as e:
            logger.error(f"Error getting token supply for {mint_address}: {str(e)}")
            return None

    # DEPRECATED ENDPOINT
    async def get_token_metadata(self, mint_addresses: List[str]) -> List[Dict[str, Any]]:
        """Get token metadata by mint [DEPRECATED]"""
        try:
            url = f"https://api.helius.xyz/v0/token-metadata"

            payload = {
                "mintAccounts": mint_addresses,
                "includeOffChain": False,
                "disableCache": False
            }

            response = await self._request("POST", url, headers={"Content-Type": "application/json"}, json=payload, params={"api-key":self.api_key})

            return response[0]
            
        except Exception as e:
            logger.warning(f"Token metadata endpoint failed: {str(e)}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Helius API health"""
        try:
            # Simple health check using getHealth RPC method
            result = await self._rpc_request("getHealth")

            health_check = False

            if result["result"] == "ok":
                health_check = True

            return {
                "healthy": health_check,
                "api_key_configured": bool(self.api_key),
                "rpc_url": self.rpc_url,
                "response_time": time.time(),
                "status": result
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": str(e),
                "rpc_url": self.rpc_url
            }


# Convenience functions
async def get_helius_client() -> HeliusClient:
    """Get configured Helius client"""
    return HeliusClient()


async def check_helius_health() -> Dict[str, Any]:
    """Check Helius service health"""
    async with HeliusClient() as client:
        return await client.health_check()