# Replace the content of app/services/solscan_client.py with this:

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
    """Solscan API client - Updated with correct endpoints"""
    
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
        
        # Add API key if available - Solscan uses 'token' header
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
        """Get comprehensive token information - FIXED ENDPOINT"""
        try:
            # Use correct Solscan token endpoint
            endpoint = f"/token/meta?tokenAddress={token_address}"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                raise SolscanAPIError("No data returned from token/meta endpoint")
            
            # Handle both success and data structures
            if isinstance(response, dict):
                # Direct data or wrapped in 'data' field
                data = response.get("data", response)
                
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
                    "volume_24h": data.get("volume24h") or data.get("volume_24h"),
                    "market_cap": data.get("marketCap") or data.get("market_cap"),
                    "price_change_24h": data.get("priceChange24h") or data.get("price_change_24h"),
                    "holder_count": data.get("holderCount") or data.get("holder_count"),
                    "created_time": data.get("createdTime") or data.get("created_time"),
                    "updated_time": data.get("updatedTime") or data.get("updated_time")
                }
                
                return token_info
            else:
                raise SolscanAPIError("Unexpected response format")
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting token info from Solscan for {token_address}: {str(e)}")
            raise SolscanAPIError(f"Failed to get token info: {str(e)}")
    
    async def get_token_holders(self, token_address: str, limit: int = 100) -> Dict[str, Any]:
        """Get token holders list - FIXED ENDPOINT"""
        try:
            # Use correct endpoint structure
            endpoint = f"/token/holders?tokenAddress={token_address}&offset=0&limit={min(limit, 1000)}"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                raise SolscanAPIError("No data returned from token/holders endpoint")
            
            # Handle response structure
            data = response.get("data", response) if isinstance(response, dict) else response
            
            holders = []
            
            # Handle different response formats
            holder_list = data if isinstance(data, list) else data.get("data", [])
            
            for holder in holder_list:
                holder_info = {
                    "address": holder.get("address"),
                    "amount": holder.get("amount"),
                    "decimals": holder.get("decimals"),
                    "owner": holder.get("owner"),
                    "rank": holder.get("rank"),
                    "percentage": holder.get("percentage")
                }
                holders.append(holder_info)
            
            total_count = data.get("total", len(holders)) if isinstance(data, dict) else len(holders)
            
            return {
                "holders": holders,
                "total": total_count
            }
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting token holders from Solscan for {token_address}: {str(e)}")
            raise SolscanAPIError(f"Failed to get token holders: {str(e)}")
    
    async def search_tokens(self, keyword: str) -> List[Dict[str, Any]]:
        """Search for tokens by name or symbol - FIXED ENDPOINT"""
        try:
            # Use current search endpoint
            endpoint = f"/token/search?keyword={keyword}"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                return []
            
            # Handle response structure
            data = response.get("data", response) if isinstance(response, dict) else response
            token_list = data if isinstance(data, list) else data.get("data", [])
            
            tokens = []
            for token in token_list:
                token_info = {
                    "address": token.get("address"),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "decimals": token.get("decimals"),
                    "icon": token.get("icon"),
                    "price": token.get("price"),
                    "volume_24h": token.get("volume24h") or token.get("volume_24h"),
                    "market_cap": token.get("marketCap") or token.get("market_cap"),
                    "holder_count": token.get("holderCount") or token.get("holder_count"),
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
        """Get Solana network statistics - FIXED ENDPOINT"""
        try:
            # Use the correct current endpoint for chain info
            endpoint = "/chaininfo"
            
            logger.debug(f"Solscan network stats: trying {endpoint}")
            response = await self._request("GET", endpoint)
            
            if response:
                logger.info(f"✅ Solscan {endpoint} successful")
                
                # Extract network stats from response
                network_stats = {
                    "endpoint_used": endpoint,
                    "response_keys": list(response.keys()) if isinstance(response, dict) else [],
                    "data_available": True
                }
                
                # Handle response structure (may be wrapped in 'data' or direct)
                data = response.get("data", response) if isinstance(response, dict) else response
                
                # Try to extract common network information with multiple field name variations
                field_mappings = {
                    "current_slot": ["currentSlot", "current_slot", "slot", "latestSlot"],
                    "current_epoch": ["currentEpoch", "current_epoch", "epoch", "latestEpoch"], 
                    "total_validators": ["totalValidators", "total_validators", "validators", "validatorCount"],
                    "total_stake": ["totalStake", "total_stake", "stake", "totalStakeAmount"],
                    "circulating_supply": ["circulatingSupply", "circulating_supply", "supply", "totalSupply"]
                }
                
                for standard_key, possible_fields in field_mappings.items():
                    for field in possible_fields:
                        if field in data:
                            network_stats[standard_key] = data[field]
                            break
                
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
                    "recommendation": "Get API key from https://solscan.io or use free tier"
                }
            
            # Test the /chaininfo endpoint which should work
            logger.debug("Solscan health check: testing /chaininfo endpoint")
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