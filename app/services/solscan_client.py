import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class SolscanAPIError(Exception):
    """Solscan API specific errors"""
    pass


class SolscanClient:
    """Solscan API client - ABSOLUTELY NO ROOT ENDPOINTS"""
    
    def __init__(self):
        self.api_key = settings.SOLSCAN_API_KEY
        self.base_url = settings.SOLSCAN_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.2  # 200ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        if not self.api_key:
            logger.warning("Solscan API key not configured")
    
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
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling and rate limiting"""
        await self._ensure_session()
        await self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Solana-Token-Analysis/1.0",
            **kwargs.pop("headers", {})
        }
        
        # Add API key if available
        if self.api_key:
            headers["token"] = self.api_key
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                content_type = response.headers.get('content-type', '').lower()
                
                logger.debug(f"Solscan {method} {endpoint} - Status: {response.status}, Content-Type: {content_type}")
                
                if response.status == 200:
                    if 'application/json' in content_type:
                        response_data = await response.json()
                        return response_data
                    else:
                        response_text = await response.text()
                        logger.warning(f"Unexpected content type from Solscan: {content_type}")
                        raise SolscanAPIError(f"Expected JSON, got {content_type}")
                        
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"Solscan rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                elif response.status == 401:
                    raise SolscanAPIError("Invalid Solscan API key")
                elif response.status == 404:
                    # Endpoint not found
                    raise SolscanAPIError(f"Solscan endpoint not found: {endpoint}")
                else:
                    try:
                        error_text = await response.text()
                        raise SolscanAPIError(f"HTTP {response.status}: {error_text[:200]}")
                    except:
                        raise SolscanAPIError(f"HTTP {response.status}: Unknown error")
                    
        except asyncio.TimeoutError:
            raise SolscanAPIError("Solscan API request timeout")
        except aiohttp.ClientError as e:
            raise SolscanAPIError(f"Solscan client error: {str(e)}")
    
    async def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive token information"""
        try:
            # Use correct Solscan token endpoint
            endpoint = "/token/meta"
            params = {"tokenAddress": token_address}
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                raise SolscanAPIError("No data returned from token/meta endpoint")
            
            data = response["data"]
            token_info = {
                "address": token_address,
                "name": data.get("name"),
                "symbol": data.get("symbol"),
                "decimals": data.get("decimals"),
                "supply": data.get("supply"),
                "icon": data.get("icon"),
                "website": data.get("website"),
                "twitter": data.get("twitter"),
                "price": data.get("price"),
                "volume_24h": data.get("volume_24h"),
                "market_cap": data.get("market_cap"),
                "price_change_24h": data.get("price_change_24h"),
                "holder_count": data.get("holder_count"),
                "created_time": data.get("created_time"),
                "updated_time": data.get("updated_time")
            }
            
            return token_info
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting token info from Solscan for {token_address}: {str(e)}")
            raise SolscanAPIError(f"Failed to get token info: {str(e)}")
    
    async def get_token_holders(self, token_address: str, limit: int = 100) -> Dict[str, Any]:
        """Get token holders list"""
        try:
            endpoint = "/token/holders"
            params = {
                "tokenAddress": token_address,
                "limit": min(limit, 1000),
                "offset": 0
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                raise SolscanAPIError("No data returned from token/holders endpoint")
            
            data = response["data"]
            holders = []
            
            for holder in data.get("data", []):
                holder_info = {
                    "address": holder.get("address"),
                    "amount": holder.get("amount"),
                    "decimals": holder.get("decimals"),
                    "owner": holder.get("owner"),
                    "rank": holder.get("rank"),
                    "percentage": holder.get("percentage")
                }
                holders.append(holder_info)
            
            return {
                "holders": holders,
                "total": data.get("total", len(holders))
            }
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting token holders from Solscan for {token_address}: {str(e)}")
            raise SolscanAPIError(f"Failed to get token holders: {str(e)}")
    
    async def search_tokens(self, keyword: str) -> List[Dict[str, Any]]:
        """Search for tokens by name or symbol"""
        try:
            endpoint = "/token/search"
            params = {"keyword": keyword}
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return []
            
            tokens = []
            for token in response["data"]:
                token_info = {
                    "address": token.get("address"),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "decimals": token.get("decimals"),
                    "icon": token.get("icon"),
                    "price": token.get("price"),
                    "volume_24h": token.get("volume_24h"),
                    "market_cap": token.get("market_cap"),
                    "holder_count": token.get("holder_count"),
                    "verified": token.get("verified", False)
                }
                tokens.append(token_info)
            
            return tokens
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.warning(f"Token search failed on Solscan for keyword '{keyword}': {str(e)}")
            raise SolscanAPIError(f"Failed to search tokens: {str(e)}")
    
    async def get_network_stats(self) -> Dict[str, Any]:
        """Get Solana network statistics - ONLY /chaininfo endpoint"""
        try:
            # Use the correct Solscan endpoint (no v2)
            endpoint = "/chaininfo"
            
            logger.debug(f"Solscan network stats: trying ONLY {endpoint}")
            response = await self._request("GET", endpoint)
            
            if response:
                logger.info(f"✅ Solscan {endpoint} successful")
                
                # Extract network stats from response
                network_stats = {
                    "endpoint_used": endpoint,
                    "response_keys": list(response.keys()) if isinstance(response, dict) else [],
                    "data_available": True
                }
                
                # Try to extract common network information
                if isinstance(response, dict):
                    common_fields = [
                        "currentSlot", "current_slot", "slot",
                        "currentEpoch", "current_epoch", "epoch", 
                        "totalValidators", "total_validators", "validators",
                        "totalStake", "total_stake", "stake",
                        "circulatingSupply", "circulating_supply", "supply"
                    ]
                    
                    for field in common_fields:
                        if field in response:
                            network_stats[field.lower()] = response[field]
                
                return network_stats
            else:
                raise SolscanAPIError("Empty response from /chaininfo endpoint")
                
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting network stats from Solscan: {str(e)}")
            raise SolscanAPIError(f"Failed to get network stats: {str(e)}")
    
    async def get_market_data(self, token_address: str) -> Dict[str, Any]:
        """Get market data for a token"""
        try:
            # Use get_token_info which includes market data
            token_info = await self.get_token_info(token_address)
            
            if token_info:
                return {
                    "price": token_info.get("price"),
                    "volume_24h": token_info.get("volume_24h"),
                    "market_cap": token_info.get("market_cap"),
                    "price_change_24h": token_info.get("price_change_24h"),
                    "holder_count": token_info.get("holder_count"),
                    "source": "solscan"
                }
            else:
                raise SolscanAPIError("No token info available for market data")
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting market data from Solscan for {token_address}: {str(e)}")
            raise SolscanAPIError(f"Failed to get market data: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Solscan API health - ONLY test /chaininfo endpoint"""
        try:
            start_time = time.time()
            
            if not self.api_key:
                return {
                    "healthy": False,
                    "api_key_configured": False,
                    "error": "Solscan API key not configured. Set SOLSCAN_API_KEY in .env file",
                    "base_url": self.base_url,
                    "response_time": 0.0,
                    "recommendation": "Get API key from https://solscan.io"
                }
            
            # Test ONLY the /chaininfo endpoint - ABSOLUTELY NO OTHER ENDPOINTS
            logger.debug("Solscan health check: testing ONLY /chaininfo endpoint")
            network_stats = await self.get_network_stats()
            response_time = time.time() - start_time
            
            return {
                "healthy": True,
                "api_key_configured": True,
                "base_url": self.base_url,
                "response_time": response_time,
                "test_data": network_stats,
                "working_endpoint": "/chaininfo"
            }
                
        except SolscanAPIError as e:
            response_time = time.time() - start_time
            return {
                "healthy": False,
                "api_key_configured": True,
                "error": f"/chaininfo endpoint failed: {str(e)}",
                "base_url": self.base_url,
                "response_time": response_time,
                "tested_endpoint": "/chaininfo"
            }
        except Exception as e:
            response_time = time.time() - start_time
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": f"Health check exception: {str(e)}",
                "base_url": self.base_url,
                "response_time": response_time
            }


# Convenience functions
async def get_solscan_client() -> SolscanClient:
    """Get configured Solscan client"""
    return SolscanClient()


async def check_solscan_health() -> Dict[str, Any]:
    """Check Solscan service health"""
    async with SolscanClient() as client:
        return await client.health_check()