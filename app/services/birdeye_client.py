import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class BirdeyeAPIError(Exception):
    """Birdeye API specific errors"""
    pass


class BirdeyeClient:
    """Birdeye API client for price data, volumes, and historical data"""
    
    def __init__(self):
        self.api_key = settings.BIRDEYE_API_KEY
        self.base_url = settings.BIRDEYE_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.15  # 150ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        # API endpoint variations to try
        self.api_endpoints = {
            "price_v1": "/defi/price",
            "price_v2": "/defi/token_overview", 
            "price_v3": "/defi/tokens/{address}/price",
            "overview": "/defi/token_overview",
            "multi_price": "/defi/multi_price"
        }
        
        if not self.api_key:
            logger.warning("Birdeye API key not configured")
    
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
    
    def _validate_solana_address(self, address: str) -> bool:
        """Validate Solana address format"""
        if not address or not isinstance(address, str):
            return False
        
        # Solana addresses are base58 encoded, 32-44 characters
        if len(address) < 32 or len(address) > 44:
            return False
        
        # Check for valid base58 characters
        import re
        base58_pattern = re.compile(r'^[1-9A-HJ-NP-Za-km-z]+$')
        return bool(base58_pattern.match(address))
    
    async def _request_with_fallback(self, endpoints_to_try: List[Dict], token_address: str) -> Dict[str, Any]:
        """Try multiple API endpoint formats until one works"""
        if not self.api_key:
            raise BirdeyeAPIError("Birdeye API key not configured")
        
        await self._ensure_session()
        await self._rate_limit()
        
        # Validate address first
        if not self._validate_solana_address(token_address):
            raise BirdeyeAPIError(f"Invalid Solana address format: {token_address}")
        
        last_error = None
        
        for i, endpoint_config in enumerate(endpoints_to_try):
            try:
                method = endpoint_config.get("method", "GET")
                endpoint = endpoint_config["endpoint"]
                params = endpoint_config.get("params", {})
                json_data = endpoint_config.get("json", None)
                
                # Replace address placeholder in URL
                url = f"{self.base_url}{endpoint}".format(address=token_address)
                
                headers = {
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                }
                
                logger.debug(f"Trying Birdeye API endpoint {i+1}/{len(endpoints_to_try)}: {method} {url}")
                
                async with self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data
                ) as response:
                    
                    response_data = await response.json()
                    
                    if response.status == 200:
                        logger.debug(f"✅ Birdeye API endpoint {i+1} successful")
                        return response_data
                    elif response.status == 429:
                        # Rate limited - wait and retry this endpoint
                        retry_after = int(response.headers.get('Retry-After', 2))
                        logger.warning(f"Birdeye rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        # Retry the same endpoint once
                        async with self.session.request(
                            method=method,
                            url=url,
                            headers=headers,
                            params=params,
                            json=json_data
                        ) as retry_response:
                            retry_data = await retry_response.json()
                            if retry_response.status == 200:
                                return retry_data
                            else:
                                last_error = f"HTTP {retry_response.status}: {retry_data.get('message', 'Unknown error')}"
                    else:
                        last_error = f"HTTP {response.status}: {response_data.get('message', 'Unknown error')}"
                        logger.debug(f"❌ Endpoint {i+1} failed: {last_error}")
                        
            except Exception as e:
                last_error = f"Request failed: {str(e)}"
                logger.debug(f"❌ Endpoint {i+1} exception: {last_error}")
                continue
        
        # If all endpoints failed
        raise BirdeyeAPIError(f"All API endpoints failed. Last error: {last_error}")
    
    async def get_token_price(self, token_address: str, include_liquidity: bool = True) -> Dict[str, Any]:
        """Get current token price and basic info with multiple endpoint fallbacks"""
        try:
            # Define endpoint variations to try in order of preference
            endpoints_to_try = [
                # Try the most common current format first
                {
                    "endpoint": "/defi/token_overview",
                    "method": "GET",
                    "params": {
                        "address": token_address,
                        "include_liquidity": str(include_liquidity).lower()
                    }
                },
                # Try alternative parameter name
                {
                    "endpoint": "/defi/token_overview", 
                    "method": "GET",
                    "params": {
                        "token_address": token_address,
                        "include_liquidity": str(include_liquidity).lower()
                    }
                },
                # Try the old price endpoint
                {
                    "endpoint": "/defi/price",
                    "method": "GET", 
                    "params": {
                        "address": token_address,
                        "include_liquidity": str(include_liquidity).lower()
                    }
                },
                # Try with mint parameter
                {
                    "endpoint": "/defi/price",
                    "method": "GET",
                    "params": {
                        "mint": token_address,
                        "include_liquidity": str(include_liquidity).lower()
                    }
                },
                # Try POST method
                {
                    "endpoint": "/defi/price",
                    "method": "POST",
                    "json": {
                        "address": token_address,
                        "include_liquidity": include_liquidity
                    }
                },
                # Try path-based endpoint
                {
                    "endpoint": "/defi/tokens/{address}/price",
                    "method": "GET",
                    "params": {
                        "include_liquidity": str(include_liquidity).lower()
                    } if include_liquidity else {}
                }
            ]
            
            response = await self._request_with_fallback(endpoints_to_try, token_address)
            
            if not response.get("data") and not response.get("success"):
                logger.warning(f"Birdeye API returned empty data for {token_address}")
                return None
            
            # Handle different response formats
            data = response.get("data", response)
            
            # Standardize the response format
            price_info = {
                "address": token_address,
                "value": data.get("value") or data.get("price") or data.get("priceUsd"),
                "updateUnixTime": data.get("updateUnixTime") or data.get("lastTradeUnixTime"),
                "updateHumanTime": data.get("updateHumanTime") or data.get("lastTradeHumanTime"),
                "priceChange24h": data.get("priceChange24h") or data.get("price24hChange"),
                "priceChange24hPercent": data.get("priceChange24hPercent") or data.get("price24hChangePercent"),
                "liquidity": data.get("liquidity") if include_liquidity else None,
                "volume24h": data.get("v24hUSD") or data.get("volume24h"),
                "marketCap": data.get("mc") or data.get("marketCap")
            }
            
            return price_info
            
        except BirdeyeAPIError:
            # Re-raise Birdeye specific errors
            raise
        except Exception as e:
            logger.error(f"Error getting token price from Birdeye for {token_address}: {str(e)}")
            return None
    
    async def get_token_metadata(self, token_address: str) -> Dict[str, Any]:
        """Get token metadata from Birdeye with fallback endpoints"""
        try:
            endpoints_to_try = [
                {
                    "endpoint": "/defi/token_overview",
                    "method": "GET",
                    "params": {"address": token_address}
                },
                {
                    "endpoint": "/defi/token_overview",
                    "method": "GET", 
                    "params": {"token_address": token_address}
                },
                {
                    "endpoint": "/defi/tokens/{address}",
                    "method": "GET"
                }
            ]
            
            response = await self._request_with_fallback(endpoints_to_try, token_address)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            metadata = {
                "address": token_address,
                "name": data.get("name"),
                "symbol": data.get("symbol"),
                "decimals": data.get("decimals"),
                "logoURI": data.get("logoURI") or data.get("image"),
                "mc": data.get("mc") or data.get("marketCap"),
                "v24hUSD": data.get("v24hUSD") or data.get("volume24h"),
                "v24hChangePercent": data.get("v24hChangePercent") or data.get("volume24hChangePercent"),
                "liquidity": data.get("liquidity"),
                "lastTradeUnixTime": data.get("lastTradeUnixTime"),
                "lastTradeHumanTime": data.get("lastTradeHumanTime"),
                "buy24h": data.get("buy24h"),
                "sell24h": data.get("sell24h"),
                "holder": data.get("holder") or data.get("holderCount"),
                "supply": data.get("supply") or data.get("totalSupply"),
                "extensions": data.get("extensions", {})
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting token metadata from Birdeye for {token_address}: {str(e)}")
            return None
    
    async def search_tokens(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search tokens by keyword with fallback endpoints"""
        try:
            endpoints_to_try = [
                {
                    "endpoint": "/defi/search",
                    "method": "GET",
                    "params": {
                        "keyword": keyword,
                        "limit": min(limit, 50)
                    }
                },
                {
                    "endpoint": "/defi/search_token",
                    "method": "GET",
                    "params": {
                        "q": keyword,
                        "limit": min(limit, 50)
                    }
                },
                {
                    "endpoint": "/defi/tokenlist",
                    "method": "GET",
                    "params": {
                        "search": keyword,
                        "limit": min(limit, 50)
                    }
                }
            ]
            
            response = await self._request_with_fallback(endpoints_to_try, keyword)
            
            if not response.get("data"):
                return []
            
            data = response["data"]
            
            # Handle different response structures
            tokens_list = data.get("tokens", data.get("results", data if isinstance(data, list) else []))
            
            tokens = []
            for token in tokens_list:
                token_info = {
                    "address": token.get("address") or token.get("mint"),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "decimals": token.get("decimals"),
                    "logoURI": token.get("logoURI") or token.get("image"),
                    "mc": token.get("mc") or token.get("marketCap"),
                    "price": token.get("price") or token.get("priceUsd"),
                    "v24hUSD": token.get("v24hUSD") or token.get("volume24h"),
                    "liquidity": token.get("liquidity")
                }
                tokens.append(token_info)
            
            return tokens
            
        except Exception as e:
            logger.warning(f"Token search failed on Birdeye for keyword '{keyword}': {str(e)}")
            return []
    
    async def get_trending_tokens(self, sort_by: str = "v24hUSD", sort_type: str = "desc", 
                                 offset: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """Get trending tokens with fallback endpoints"""
        try:
            endpoints_to_try = [
                {
                    "endpoint": "/defi/tokenlist",
                    "method": "GET",
                    "params": {
                        "sort_by": sort_by,
                        "sort_type": sort_type,
                        "offset": offset,
                        "limit": min(limit, 50)
                    }
                },
                {
                    "endpoint": "/defi/trending",
                    "method": "GET",
                    "params": {
                        "sort": sort_by,
                        "order": sort_type,
                        "limit": min(limit, 50)
                    }
                },
                {
                    "endpoint": "/defi/tokens/top",
                    "method": "GET",
                    "params": {
                        "sortBy": sort_by,
                        "limit": min(limit, 50)
                    }
                }
            ]
            
            response = await self._request_with_fallback(endpoints_to_try, "")
            
            if not response.get("data"):
                return []
            
            data = response["data"]
            tokens_list = data.get("tokens", data.get("results", data if isinstance(data, list) else []))
            
            trending = []
            for token in tokens_list:
                token_info = {
                    "address": token.get("address") or token.get("mint"),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "decimals": token.get("decimals"),
                    "logoURI": token.get("logoURI") or token.get("image"),
                    "mc": token.get("mc") or token.get("marketCap"),
                    "v24hUSD": token.get("v24hUSD") or token.get("volume24h"),
                    "v24hChangePercent": token.get("v24hChangePercent"),
                    "priceChange24hPercent": token.get("priceChange24hPercent"),
                    "liquidity": token.get("liquidity"),
                    "price": token.get("price") or token.get("priceUsd"),
                    "holder": token.get("holder") or token.get("holderCount"),
                    "supply": token.get("supply") or token.get("totalSupply")
                }
                trending.append(token_info)
            
            return trending
            
        except Exception as e:
            logger.warning(f"Error getting trending tokens from Birdeye: {str(e)}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Birdeye API health"""
        try:
            start_time = time.time()
            
            # Test with a well-known token (Wrapped SOL)
            sol_address = "So11111111111111111111111111111111111112"
            price_data = await self.get_token_price(sol_address, include_liquidity=False)
            
            response_time = time.time() - start_time
            
            return {
                "healthy": price_data is not None,
                "api_key_configured": bool(self.api_key),
                "base_url": self.base_url,
                "response_time": response_time,
                "test_token": sol_address,
                "test_data": price_data,
                "endpoints_available": len(self.api_endpoints)
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": str(e),
                "base_url": self.base_url,
                "test_token": "So11111111111111111111111111111111111112"
            }


# Convenience functions
async def get_birdeye_client() -> BirdeyeClient:
    """Get configured Birdeye client"""
    return BirdeyeClient()


async def check_birdeye_health() -> Dict[str, Any]:
    """Check Birdeye service health"""
    async with BirdeyeClient() as client:
        return await client.health_check()