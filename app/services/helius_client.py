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
        self.base_url = "https://api.helius.xyz/v0"
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
            self.rpc_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if "error" in response:
            raise HeliusAPIError(f"RPC error: {response['error']}")
        
        return response.get("result", {})
    
    async def get_token_accounts(self, mint_address: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get token accounts (holders) for a token"""
        try:
            result = await self._rpc_request("getTokenAccounts", [
                mint_address,
                {
                    "limit": limit,
                    "displayOptions": {
                        "showNativeBalance": True,
                        "showZeroBalance": False
                    }
                }
            ])
            
            if not result or "token_accounts" not in result:
                return []
            
            holders = []
            for account in result["token_accounts"]:
                holder_info = {
                    "address": account.get("address"),
                    "amount": account.get("amount"),
                    "decimals": account.get("decimals"),
                    "uiAmount": account.get("uiAmount"),
                    "owner": account.get("owner")
                }
                holders.append(holder_info)
            
            return holders
            
        except Exception as e:
            logger.error(f"Error getting token accounts for {mint_address}: {str(e)}")
            return []
    
    async def get_transaction_history(self, address: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get transaction history for an address"""
        try:
            result = await self._rpc_request("getSignaturesForAddress", [
                address,
                {"limit": limit}
            ])
            
            if not result:
                return []
            
            transactions = []
            for tx in result:
                tx_info = {
                    "signature": tx.get("signature"),
                    "slot": tx.get("slot"),
                    "blockTime": tx.get("blockTime"),
                    "confirmationStatus": tx.get("confirmationStatus"),
                    "err": tx.get("err"),
                    "memo": tx.get("memo")
                }
                transactions.append(tx_info)
            
            return transactions
            
        except Exception as e:
            logger.error(f"Error getting transaction history for {address}: {str(e)}")
            return []
    
    async def get_transaction_details(self, signature: str) -> Dict[str, Any]:
        """Get detailed transaction information"""
        try:
            result = await self._rpc_request("getTransaction", [
                signature,
                {
                    "encoding": "jsonParsed",
                    "maxSupportedTransactionVersion": 0
                }
            ])
            
            if not result:
                return None
            
            # Parse transaction details
            transaction = {
                "signature": signature,
                "slot": result.get("slot"),
                "blockTime": result.get("blockTime"),
                "meta": result.get("meta", {}),
                "transaction": result.get("transaction", {}),
                "version": result.get("version")
            }
            
            return transaction
            
        except Exception as e:
            logger.error(f"Error getting transaction details for {signature}: {str(e)}")
            return None
    
    async def get_balance(self, address: str) -> Optional[Decimal]:
        """Get SOL balance for an address"""
        try:
            result = await self._rpc_request("getBalance", [address])
            
            if result is not None and "value" in result:
                # Convert lamports to SOL
                lamports = result["value"]
                sol_balance = Decimal(lamports) / Decimal(10**9)
                return sol_balance
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting balance for {address}: {str(e)}")
            return None
    
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
                "uiAmount": supply_info.get("uiAmount"),
                "uiAmountString": supply_info.get("uiAmountString")
            }
            
        except Exception as e:
            logger.error(f"Error getting token supply for {mint_address}: {str(e)}")
            return None
    
    async def get_token_price_history(self, mint_address: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get token price history (using enhanced API if available)"""
        try:
            # Use enhanced API endpoint
            url = f"{self.base_url}/token-metadata"
            params = {
                "api-key": self.api_key,
                "mint": mint_address,
                "includeOffChain": "true"
            }
            
            response = await self._request("GET", url, params=params)
            
            # This is a simplified response, actual implementation would depend on Helius enhanced API
            return response.get("priceHistory", [])
            
        except Exception as e:
            logger.warning(f"Price history not available for {mint_address}: {str(e)}")
            return []
    
    async def get_nft_events(self, mint_address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get NFT events (if token is NFT)"""
        try:
            url = f"{self.base_url}/nft-events"
            params = {
                "api-key": self.api_key,
                "accounts": [mint_address],
                "limit": limit
            }
            
            response = await self._request("GET", url, params=params)
            return response.get("result", [])
            
        except Exception as e:
            logger.warning(f"NFT events not available for {mint_address}: {str(e)}")
            return []
    
    async def search_tokens(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for tokens by name or symbol"""
        try:
            url = f"{self.base_url}/token-metadata"
            params = {
                "api-key": self.api_key,
                "query": query,
                "limit": limit
            }
            
            response = await self._request("GET", url, params=params)
            return response.get("result", [])
            
        except Exception as e:
            logger.warning(f"Token search failed for query '{query}': {str(e)}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Helius API health"""
        try:
            # Simple health check using getHealth RPC method
            result = await self._rpc_request("getHealth")
            
            return {
                "healthy": True,
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