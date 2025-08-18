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
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Solana-Token-Analysis/1.0",
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
    
    async def get_token_metadata(self, mint_address: str) -> Dict[str, Any]:
        """Get comprehensive token metadata"""
        try:
            # Try different endpoint formats that might work with Chainbase
            endpoints_to_try = [
                {
                    "endpoint": "/v1/token/metadata",
                    "params": {"address": mint_address}
                },
                {
                    "endpoint": "/v1/token/metadata", 
                    "params": {"contract_address": mint_address}
                },
                {
                    "endpoint": "/v1/solana/token/metadata",
                    "params": {"address": mint_address}
                }
            ]
            
            for attempt in endpoints_to_try:
                try:
                    logger.debug(f"Trying Chainbase endpoint: {attempt['endpoint']} with params: {attempt['params']}")
                    response = await self._request("GET", attempt["endpoint"], params=attempt["params"])
                    
                    if response and response.get("data"):
                        logger.info(f"✅ Chainbase endpoint successful: {attempt['endpoint']}")
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
                    logger.debug(f"❌ Chainbase endpoint {attempt['endpoint']} failed: {str(e)}")
                    continue  # Try next endpoint
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting token metadata from Chainbase for {mint_address}: {str(e)}")
            return None
    
    async def get_token_holders(self, mint_address: str, limit: int = 100, page: int = 1) -> Dict[str, Any]:
        """Get token holders analysis"""
        try:
            endpoints_to_try = [
                {
                    "endpoint": "/v1/token/holders",
                    "params": {"address": mint_address, "limit": min(limit, 1000), "page": page}
                },
                {
                    "endpoint": "/v1/token/holders",
                    "params": {"contract_address": mint_address, "limit": min(limit, 1000), "page": page}
                }
            ]
            
            for attempt in endpoints_to_try:
                try:
                    response = await self._request("GET", attempt["endpoint"], params=attempt["params"])
                    
                    if response and response.get("data"):
                        data = response["data"]
                        holders = []
                        
                        for holder in data.get("holders", []):
                            holder_info = {
                                "address": holder.get("address"),
                                "balance": holder.get("balance"),
                                "balance_usd": holder.get("balance_usd"),
                                "percentage": holder.get("percentage"),
                                "rank": holder.get("rank"),
                                "first_transaction": holder.get("first_transaction"),
                                "last_transaction": holder.get("last_transaction"),
                                "transaction_count": holder.get("transaction_count")
                            }
                            holders.append(holder_info)
                        
                        distribution = self._calculate_holder_distribution(holders)
                        
                        return {
                            "holders": holders,
                            "total_holders": data.get("total_holders", len(holders)),
                            "distribution": distribution,
                            "pagination": {
                                "page": page,
                                "limit": limit,
                                "has_next": len(holders) == limit
                            }
                        }
                except ChainbaseAPIError as e:
                    logger.debug(f"❌ Chainbase search endpoint {attempt['endpoint']} failed: {str(e)}")
                    continue
            
            return {
                "holders": [],
                "total_holders": 0,
                "distribution": {}
            }
            
        except Exception as e:
            logger.error(f"Error getting token holders from Chainbase for {mint_address}: {str(e)}")
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
    
    async def search_tokens(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for tokens by name or symbol"""
        try:
            endpoints_to_try = [
                {
                    "endpoint": "/v1/token/search",
                    "params": {"keyword": query, "limit": limit}
                },
                {
                    "endpoint": "/v1/search/tokens",
                    "params": {"query": query, "limit": limit}
                }
            ]
            
            for attempt in endpoints_to_try:
                try:
                    response = await self._request("GET", attempt["endpoint"], params=attempt["params"])
                    
                    if response and response.get("data"):
                        tokens = []
                        for token in response["data"]:
                            token_info = {
                                "mint": token.get("contract_address") or token.get("address"),
                                "name": token.get("name"),
                                "symbol": token.get("symbol"),
                                "decimals": token.get("decimals"),
                                "verified": token.get("verified", False),
                                "market_cap": token.get("market_cap"),
                                "price": token.get("price"),
                                "volume_24h": token.get("volume_24h"),
                                "holders_count": token.get("holders_count"),
                                "created_at": token.get("created_at")
                            }
                            tokens.append(token_info)
                        
                        return tokens
                except ChainbaseAPIError as e:
                    logger.debug(f"❌ Chainbase market endpoint {attempt['endpoint']} failed: {str(e)}")
                    continue
            
            return []
            
        except Exception as e:
            logger.warning(f"Token search failed on Chainbase for query '{query}': {str(e)}")
            return []
    
    async def get_market_data(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive market data for token"""
        try:
            endpoints_to_try = [
                {
                    "endpoint": "/v1/token/market",
                    "params": {"address": token_address}
                },
                {
                    "endpoint": "/v1/market/token",
                    "params": {"contract_address": token_address}
                }
            ]
            
            for attempt in endpoints_to_try:
                try:
                    response = await self._request("GET", attempt["endpoint"], params=attempt["params"])
                    
                    if response and response.get("data"):
                        data = response["data"]
                        return {
                            "price": data.get("price"),
                            "price_change_24h": data.get("price_change_24h"),
                            "price_change_7d": data.get("price_change_7d"),
                            "volume_24h": data.get("volume_24h"),
                            "volume_change_24h": data.get("volume_change_24h"),
                            "market_cap": data.get("market_cap"),
                            "market_cap_rank": data.get("market_cap_rank"),
                            "circulating_supply": data.get("circulating_supply"),
                            "total_supply": data.get("total_supply"),
                            "max_supply": data.get("max_supply"),
                            "ath": data.get("ath"),
                            "ath_date": data.get("ath_date"),
                            "atl": data.get("atl"),
                            "atl_date": data.get("atl_date"),
                            "liquidity": data.get("liquidity"),
                            "fdv": data.get("fdv")  # Fully Diluted Valuation
                        }
                except ChainbaseAPIError:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting market data from Chainbase for {token_address}: {str(e)}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Chainbase API health"""
        try:
            start_time = time.time()
            
            if not self.api_key:
                return {
                    "healthy": False,
                    "api_key_configured": False,
                    "error": "Chainbase API key not configured. Set CHAINBASE_API_KEY in .env file",
                    "base_url": self.base_url,
                    "response_time": 0.0
                }
            
            # Try a simple endpoint that's likely to work
            simple_endpoints = [
                {"endpoint": "/v1/health", "params": None},
                {"endpoint": "/v1/status", "params": None},
                {"endpoint": "/health", "params": None},
                {"endpoint": "/", "params": None}
            ]
            
            for endpoint_config in simple_endpoints:
                try:
                    logger.debug(f"Trying Chainbase health endpoint: {endpoint_config['endpoint']}")
                    if endpoint_config["params"]:
                        response = await self._request("GET", endpoint_config["endpoint"], params=endpoint_config["params"])
                    else:
                        response = await self._request("GET", endpoint_config["endpoint"])
                    
                    response_time = time.time() - start_time
                    logger.info(f"✅ Chainbase health check successful with endpoint: {endpoint_config['endpoint']}")
                    
                    return {
                        "healthy": True,
                        "api_key_configured": True,
                        "base_url": self.base_url,
                        "response_time": response_time,
                        "working_endpoint": endpoint_config["endpoint"]
                    }
                    
                except ChainbaseAPIError as e:
                    logger.debug(f"❌ Chainbase health endpoint {endpoint_config['endpoint']} failed: {str(e)}")
                    continue  # Try next endpoint
            
            # If simple endpoints failed, the API might not have standard health endpoints
            # Just return that we can't determine health but API key is configured
            response_time = time.time() - start_time
            return {
                "healthy": False,
                "api_key_configured": True,
                "error": "No accessible health endpoints found",
                "base_url": self.base_url,
                "response_time": response_time,
                "recommendation": "API key configured but unable to verify connectivity"
            }
            
        except Exception as e:
            response_time = time.time() - start_time
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": str(e),
                "base_url": self.base_url,
                "response_time": response_time
            }


# Convenience functions
async def get_chainbase_client() -> ChainbaseClient:
    """Get configured Chainbase client"""
    return ChainbaseClient()


async def check_chainbase_health() -> Dict[str, Any]:
    """Check Chainbase service health"""
    async with ChainbaseClient() as client:
        return await client.health_check()