import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from decimal import Decimal
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class ChainbaseAPIError(Exception):
    """Chainbase API specific errors"""
    pass


class ChainbaseClient:
    """Chainbase API client for blockchain analytics and smart contract data"""
    
    def __init__(self):
        self.api_key = settings.CHAINBASE_API_KEY
        self.base_url = settings.CHAINBASE_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.2  # 200ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        if not self.api_key:
            logger.warning("Chainbase API key not configured")
    
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
        if not self.api_key:
            raise ChainbaseAPIError("Chainbase API key not configured")
        
        await self._ensure_session()
        await self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "x-api-key": self.api_key,
            **kwargs.pop("headers", {})
        }
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                content_type = response.headers.get('content-type', '').lower()
                
                logger.debug(f"Chainbase {method} {endpoint} - Status: {response.status}, Content-Type: {content_type}")
                
                if response.status == 200:
                    if 'application/json' in content_type:
                        response_data = await response.json()
                        
                        logger.debug(f"Response data keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
                        
                        # Check for Chainbase API-level errors (they return 200 but with error codes)
                        if isinstance(response_data, dict):
                            if response_data.get('code') != 0 and response_data.get('code') is not None:
                                error_msg = response_data.get('message') or response_data.get('error') or 'Unknown API error'
                                logger.error(f"Chainbase API error (code {response_data.get('code')}): {error_msg}")
                                raise ChainbaseAPIError(f"API error (code {response_data.get('code')}): {error_msg}")
                        
                        return response_data
                    else:
                        response_text = await response.text()
                        logger.error(f"Unexpected content type from Chainbase: {content_type}")
                        logger.debug(f"Response text: {response_text[:500]}")
                        raise ChainbaseAPIError(f"Expected JSON, got {content_type}. Response: {response_text[:200]}")
                        
                elif response.status == 400:
                    response_text = await response.text()
                    logger.error(f"Chainbase 400 Bad Request: {response_text[:500]}")
                    try:
                        if 'application/json' in content_type:
                            error_data = await response.json()
                            error_msg = error_data.get('message') or error_data.get('error') or 'Parameter error'
                            logger.error(f"API Error Details: {error_data}")
                            raise ChainbaseAPIError(f"Bad request: {error_msg}")
                        else:
                            raise ChainbaseAPIError(f"Bad request: {response_text[:200]}")
                    except ChainbaseAPIError:
                        raise
                    except Exception:
                        raise ChainbaseAPIError(f"Bad request: {response_text[:200]}")
                        
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"Chainbase rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                elif response.status == 401:
                    logger.error("Chainbase 401 Authentication failed")
                    raise ChainbaseAPIError("Invalid Chainbase API key")
                elif response.status == 404:
                    logger.error(f"Chainbase 404 Not Found: {endpoint}")
                    raise ChainbaseAPIError(f"Chainbase endpoint not found: {endpoint}")
                else:
                    response_text = await response.text()
                    logger.error(f"Chainbase API error {response.status}: {response_text[:500]}")
                    raise ChainbaseAPIError(f"HTTP {response.status}: {response_text[:200]}")
                    
        except asyncio.TimeoutError:
            raise ChainbaseAPIError("Chainbase API request timeout")
        except aiohttp.ClientError as e:
            raise ChainbaseAPIError(f"Chainbase client error: {str(e)}")
    
    async def get_token_metadata(self, mint_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Get comprehensive token metadata"""

        # Map chains to chain IDs
        chain_mapping = {
                "ethereum": "1",
                "eth": "1", 
                "bsc": "56", 
                "polygon": "137",
                "solana": "101",
                "sol": "101"
            }
            
        chain_id = chain_mapping.get(chain.lower(), "1")

        try:
            endpoint = "/token/metadata"
            querystring = {"chain_id": chain_id, "contract_address": mint_address}

            response = await self._request("GET", endpoint, params=querystring)
            
            if response and response.get("data"):
                logger.info(f"✅ Chainbase token metadata endpoint successful")
                data = response["data"]
                return {
                    "mint": mint_address,
                    "name": data.get("name"),
                    "symbol": data.get("symbol"),
                    "decimals": data.get("decimals"),
                    "total_supply": data.get("total_supply"),
                    "description": data.get("description"),
                    "image": data.get("image"),
                    "external_url": data.get("external_url"),
                    "creator": data.get("creator"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "verified": data.get("verified", False),
                    "tags": data.get("tags", [])
                }
        except ChainbaseAPIError as e:
            logger.debug(f"❌ Chainbase token metadata endpoint failed: {str(e)}")
    
        return None
    
    async def get_token_holders(self, mint_address: str, chain: str = "solana", limit: int = 100, page: int = 1) -> Dict[str, Any]:
        """Get token holders analysis"""

        # Map chains to chain IDs
        chain_mapping = {
                "ethereum": "1",
                "eth": "1", 
                "bsc": "56", 
                "polygon": "137",
                "solana": "101",
                "sol": "101"
            }
            
        chain_id = chain_mapping.get(chain.lower(), "1")

        try:
            endpoint = "/token/top-holders"
            querystring = {"chain_id": chain_id, "contract_address": mint_address, "limit": limit, "page": page}

            response = await self._request("GET", endpoint, params=querystring)
            
            if response and response.get("data"):
                logger.info(f"✅ Chainbase token holders successful")
                holders_data = response["data"]
                holders = []
                
                for holder in holders_data:
                    holder_info = {
                        "address": holder.get("wallet_address"),
                        "balance": float(holder.get("original_amount")),
                        "balance_usd": float(holder.get("usd_value")),
                        "percentage": (float(holder.get("amount"))/float(holder.get("original_amount")))*100.0
                    }
                    holders.append(holder_info)
                
                distribution = self._calculate_holder_distribution(holders)
                
                return {
                    "holders": holders,
                    "total_holders": len(holders),
                    "distribution": distribution,
                    "pagination": {
                        "page": page,
                        "limit": limit,
                        "has_next": len(holders) == limit
                    }
                }
        except ChainbaseAPIError as e:
            logger.debug(f"❌ Chainbase token holders endpoint failed: {str(e)}")
            
        return {
            "holders": [],
            "total_holders": 0,
            "distribution": {}
        }
    
    
    def _calculate_holder_distribution(self, holders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate holder distribution statistics"""
        if not holders:
            return {}
        
        # Categorize holders
        whales = [h for h in holders if float(h.get("percentage", 0)) >= 1.0]  # 1%+
        large_holders = [h for h in holders if 0.1 <= float(h.get("percentage", 0)) < 1.0]  # 0.1-1%
        medium_holders = [h for h in holders if 0.01 <= float(h.get("percentage", 0)) < 0.1]  # 0.01-0.1%
        small_holders = [h for h in holders if float(h.get("percentage", 0)) < 0.01]  # <0.01%
        
        return {
            "whales": {
                "count": len(whales),
                "total_percentage": sum(float(h.get("percentage", 0)) for h in whales)
            },
            "large_holders": {
                "count": len(large_holders),
                "total_percentage": sum(float(h.get("percentage", 0)) for h in large_holders)
            },
            "medium_holders": {
                "count": len(medium_holders),
                "total_percentage": sum(float(h.get("percentage", 0)) for h in medium_holders)
            },
            "small_holders": {
                "count": len(small_holders),
                "total_percentage": sum(float(h.get("percentage", 0)) for h in small_holders)
            },
            "concentration": {
                "top_10_percentage": sum(float(h.get("percentage", 0)) for h in holders[:10]),
                "top_100_percentage": sum(float(h.get("percentage", 0)) for h in holders[:100]),
                "gini_coefficient": self._calculate_gini_coefficient(holders)
            }
        }
    
    def _calculate_gini_coefficient(self, holders: List[Dict[str, Any]]) -> float:
        """Calculate Gini coefficient for wealth distribution"""
        if not holders:
            return 0.0
        
        balances = [float(h.get("balance", 0)) for h in holders]
        balances.sort()
        
        n = len(balances)
        cumsum = sum((i + 1) * balance for i, balance in enumerate(balances))
        total = sum(balances)
        
        if total == 0:
            return 0.0
        
        return (2 * cumsum) / (n * total) - (n + 1) / n
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Chainbase API service health and connectivity"""
        health_status = {
            "healthy": True,
            "api_key_configured": bool(self.api_key),
            "error": None,
            "base_url": self.base_url,
            "response_time": None,
        }
        
        if not self.api_key:
            health_status.update({
                "healthy": False,
                "error": "API key not configured"
            })
            logger.warning("Chainbase health check failed: API key not configured")
            return health_status
        
        start_time = time.time()
        
        try:
            test_endpoint = "/token/metadata"
            test_params = {
                "chain_id": "1",
                "contract_address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
            }
            
            response = await self._request("GET", test_endpoint, params=test_params)
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Check if we got a valid response structure
            if response and isinstance(response, dict):
                if response.get('code') == 0 or response.get('data') is not None:
                    health_status.update({
                        "response_time": round(response_time, 2)
                    })
                    logger.info(f"✅ Chainbase health check passed ({response_time:.2f}ms)")
                else:
                    health_status.update({
                        "healthy": False,
                        "response_time": round(response_time, 2),
                        "error": f"API returned unexpected response: {response.get('message', 'Unknown error')}"
                    })
                    logger.warning(f"⚠️ Chainbase health check degraded: {health_status['error']}")
            else:
                health_status.update({
                    "healthy": False,
                    "response_time": round(response_time, 2),
                    "error": "Invalid response format"
                })
                logger.error("❌ Chainbase health check failed: Invalid response format")
                
        except ChainbaseAPIError as e:
            response_time = (time.time() - start_time) * 1000
            health_status.update({
                "healthy": False,
                "response_time": round(response_time, 2),
                "error": str(e)
            })
            logger.error(f"❌ Chainbase health check failed: {str(e)}")
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            health_status.update({
                "healthy": False,
                "response_time": round(response_time, 2),
                "error": f"Unexpected error: {str(e)}"
            })
            logger.error(f"❌ Chainbase health check failed with unexpected error: {str(e)}")
        
        return health_status
   
   
# Convenience functions
async def get_chainbase_client() -> ChainbaseClient:
    """Get configured Chainbase client"""
    return ChainbaseClient()


async def check_chainbase_health() -> Dict[str, Any]:
    """Check Chainbase service health"""
    async with ChainbaseClient() as client:
        return await client.health_check()