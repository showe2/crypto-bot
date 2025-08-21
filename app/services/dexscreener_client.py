import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class DexScreenerAPIError(Exception):
    """DexScreener API specific errors"""
    pass


class DexScreenerClient:
    """DexScreener API client for DEX data and token information (completely free)"""
    
    def __init__(self):
        self.base_url = settings.DEXSCREENER_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.5  # 500ms between requests to be respectful
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        logger.info("DexScreener client initialized (FREE service)")
    
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
            "Accept": "*/*",
            **kwargs.pop("headers", {})
        }
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                content_type = response.headers.get('content-type', '').lower()
                
                logger.debug(f"DexScreener {method} {endpoint} - Status: {response.status}, Content-Type: {content_type}")
                
                if response.status == 200:
                    if 'application/json' in content_type:
                        response_data = await response.json()
                        return response_data
                    else:
                        response_text = await response.text()
                        logger.warning(f"Unexpected content type from DexScreener: {response_text}")
                        raise DexScreenerAPIError(f"Expected JSON, got {content_type}")
                        
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"DexScreener rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                elif response.status == 404:
                    # Not found - might be normal for tokens not on DEXes
                    logger.debug(f"DexScreener 404 for {endpoint} - token may not be traded on DEXes")
                    return None
                else:
                    try:
                        error_text = await response.text()
                        raise DexScreenerAPIError(f"HTTP {response.status}: {error_text[:200]}")
                    except:
                        raise DexScreenerAPIError(f"HTTP {response.status}: Unknown error")
                    
        except asyncio.TimeoutError:
            raise DexScreenerAPIError("DexScreener API request timeout")
        except aiohttp.ClientError as e:
            raise DexScreenerAPIError(f"DexScreener client error: {str(e)}")
    
    async def get_token_pairs(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Get trading pairs for a token"""
        try:
            endpoint = f"/tokens/v1/{chain}/{token_address}"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                logger.debug(f"No trading pairs found for {token_address}")
                return None
            
            return {"pairs": response}
            
        except DexScreenerAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting token pairs from DexScreener for {token_address}: {str(e)}")
            raise DexScreenerAPIError(f"Failed to get token pairs: {str(e)}")
    
    async def search_pairs(self, query: str) -> List[Dict[str, Any]]:
        """Search for pairs by token name or symbol"""
        try:
            endpoint = "/latest/dex/search"
            params = {"q": query}
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response:
                logger.debug(f"No search results found for '{query}'")
                return []
            
            # Validate response structure
            if "pairs" not in response:
                logger.warning(f"Unexpected search response structure from DexScreener")
                return []
            
            pairs = response["pairs"]
            if not pairs:
                logger.debug(f"No pairs found in search for '{query}'")
                return []
            
            return pairs
            
        except DexScreenerAPIError:
            raise
        except Exception as e:
            logger.error(f"Error searching pairs on DexScreener for '{query}': {str(e)}")
            raise DexScreenerAPIError(f"Failed to search pairs: {str(e)}")
    
    async def get_pair_by_address(self, pair_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Get specific pair information by pair address"""
        try:
            endpoint = f"/latest/dex/pairs/{chain}/{pair_address}"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                logger.debug(f"No pair found for address {pair_address}")
                return None
            
            # Validate response structure
            if "pair" not in response:
                logger.warning(f"Unexpected pair response structure from DexScreener")
                return None
            
            pairs = response["pairs"]
            if not pairs:
                return None
            
            return pairs
            
        except DexScreenerAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting pair data from DexScreener for {pair_address}: {str(e)}")
            raise DexScreenerAPIError(f"Failed to get pair data: {str(e)}")
    
    async def get_tokens_by_addresses(self, addresses: List[str], chain: str = "solana") -> Dict[str, Any]:
        """Get token data for multiple addresses (up to 30)"""
        try:
            if len(addresses) > 30:
                logger.warning(f"DexScreener allows max 30 addresses, truncating list")
                addresses = addresses[:30]
            
            # Join addresses with comma
            addresses_str = ",".join(addresses)
            endpoint = f"/tokens/v1/{chain}/{addresses_str}"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                logger.debug(f"No data found for provided addresses")
                return {}
            
            # Process results by address
            results = {}
            if "pairs" in response:
                for pair in response["pairs"]:
                    base_address = pair.get("baseToken", {}).get("address")
                    quote_address = pair.get("quoteToken", {}).get("address")
                    
                    # Group pairs by token address
                    for addr in addresses:
                        if addr == base_address or addr == quote_address:
                            if addr not in results:
                                results[addr] = []
                            results[addr].append(pair)
            
            return results
            
        except DexScreenerAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting tokens data from DexScreener: {str(e)}")
            raise DexScreenerAPIError(f"Failed to get tokens data: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check DexScreener API health"""
        try:
            start_time = time.time()
            
            test_token1 = "So11111111111111111111111111111111111111112"
            test_token2 = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
            
            try:
                response = await self.get_tokens_by_addresses([test_token1, test_token2])
                response_time = time.time() - start_time
                
                return {
                    "healthy": True,
                    "api_key_configured": True,  # Always true since no API key needed
                    "base_url": self.base_url,
                    "response_time": response_time,
                    "test_data": response if response else "No trading pairs",
                    "note": "DexScreener is free to use, no API key required"
                }
                
            except DexScreenerAPIError as e:
                response_time = time.time() - start_time
                error_msg = str(e)
                
                if "rate limit" in error_msg.lower():
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": f"Rate limited: {error_msg}",
                        "base_url": self.base_url,
                        "response_time": response_time,
                        "recommendation": "Wait before retrying"
                    }
                else:
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": f"API error: {error_msg}",
                        "base_url": self.base_url,
                        "response_time": response_time
                    }
                
        except Exception as e:
            response_time = time.time() - start_time
            return {
                "healthy": False,
                "api_key_configured": True,  # No API key needed
                "error": f"Health check exception: {str(e)}",
                "base_url": self.base_url,
                "response_time": response_time
            }


# Convenience functions
async def get_dexscreener_client() -> DexScreenerClient:
    """Get configured DexScreener client"""
    return DexScreenerClient()


async def check_dexscreener_health() -> Dict[str, Any]:
    """Check DexScreener service health"""
    async with DexScreenerClient() as client:
        return await client.health_check()