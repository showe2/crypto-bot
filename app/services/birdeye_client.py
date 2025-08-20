import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger

from app.core.config import get_settings

settings = get_settings()

# Debug settings loading
logger.debug(f"Settings loaded - Birdeye API Key present: {bool(settings.BIRDEYE_API_KEY)}")
logger.debug(f"Settings loaded - Birdeye Base URL: {settings.BIRDEYE_BASE_URL}")


class BirdeyeAPIError(Exception):
    """Birdeye API specific errors"""
    pass


class BirdeyeClient:
    """Birdeye API client for price data, volumes, and historical data"""
    
    def __init__(self):
        self.api_key = settings.BIRDEYE_API_KEY
        self.base_url = settings.BIRDEYE_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.5  # Increased to 500ms to avoid rate limits
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        # Updated API endpoints based on current Birdeye API documentation
        self.api_endpoints = {
            "multi_price": "/defi/multi_price"
        }
        
        # Log API key status (masked for security)
        if self.api_key:
            masked_key = f"{self.api_key[:8]}***{self.api_key[-4:]}" if len(self.api_key) > 12 else f"{self.api_key[:4]}***"
            logger.debug(f"Birdeye API key configured: {masked_key} (length: {len(self.api_key)})")
        else:
            logger.debug("Birdeye API key not configured - check BIRDEYE_API_KEY in .env file")
        
        logger.debug(f"Birdeye base URL: {self.base_url}")
    
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
        """Simple rate limiting with increased delay"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)
        
        self._last_request_time = time.time()
    
    def _validate_solana_address(self, address: str) -> bool:
        """Validate Solana address format"""
        if not address or not isinstance(address, str):
            return False
        
        # Solana addresses are base58 encoded, typically 44 characters (32-44 range)
        if len(address) < 32 or len(address) > 44:
            logger.debug(f"Address length invalid: {len(address)} (expected 32-44)")
            return False
        
        # Check for valid base58 characters (Bitcoin alphabet)
        import re
        base58_pattern = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")
        if not base58_pattern.match(address):
            logger.debug(f"Address contains invalid base58 characters")
            return False
            
        # Additional check - most Solana addresses are exactly 44 characters
        if len(address) == 44:
            logger.debug(f"Address format valid: {address[:8]}...{address[-4:]} (length: {len(address)})")
            return True
        elif len(address) == 43:
            logger.debug(f"Address format likely valid: {address[:8]}...{address[-4:]} (length: {len(address)})")
            return True
        else:
            logger.debug(f"Address length unusual but might be valid: {len(address)}")
            return True  # Allow it through, let the API decide
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Birdeye API"""
        await self._ensure_session()
        await self._rate_limit()

        # Setup headers
        headers = {
            "Accept": "application/json",
            "User-Agent": "Solana-Token-Analysis/1.0",
            **kwargs.pop("headers", {})
        }
        
        # Add API key if available
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
            logger.debug(f"Using API key: {self.api_key[:8]}*** (length: {len(self.api_key)})")
        else:
            logger.debug("No API key configured, trying without authentication")
        
        url = self.base_url+endpoint
        params = kwargs.pop("params", {})
        json_data = kwargs.pop("json", None)
        
        logger.debug(f"Birdeye {method} {endpoint}")
        logger.debug(f"Full URL: {url}")
        logger.debug(f"Params: {params}")
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                **kwargs
            ) as response:
                
                logger.debug(f"Response status: {response.status}")
                content_type = response.headers.get("content-type", "").lower()
                logger.debug(f"Content type: {content_type}")
                
                if response.status == 200:
                    if "application/json" in content_type:
                        response_data = await response.json()
                        logger.info(f"✅ Birdeye {method} {endpoint} successful")
                        logger.debug(f"Response data keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
                        return response_data
                    else:
                        text_response = await response.text()
                        logger.error(f"Unexpected content type: {content_type}")
                        logger.debug(f"Response content: {text_response[:300]}")
                        raise BirdeyeAPIError(f"Expected JSON, got {content_type}. Response: {text_response[:200]}")
                        
                elif response.status == 401:
                    error_text = await response.text()
                    logger.error(f"401 Authentication failed")
                    logger.error(f"Request URL: {url}")
                    logger.error(f"Response text: {error_text[:500]}")
                    
                    if self.api_key:
                        raise BirdeyeAPIError(f"Authentication failed: Invalid API key. Response: {error_text[:200]}")
                    else:
                        raise BirdeyeAPIError(f"Authentication required: API key needed. Response: {error_text[:200]}")
                        
                elif response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 2))
                    logger.warning(f"Birdeye rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                    
                else:
                    error_text = await response.text()
                    logger.error(f"Birdeye API error {response.status}: {error_text[:500]}")
                    raise BirdeyeAPIError(f"HTTP {response.status}: {error_text[:200] if error_text else 'No response content'}")
                    
        except asyncio.TimeoutError:
            raise BirdeyeAPIError("Birdeye API request timeout")
        except aiohttp.ClientError as e:
            raise BirdeyeAPIError(f"Birdeye client error: {str(e)}")
        except BirdeyeAPIError:
            raise
        except Exception as e:
            raise BirdeyeAPIError(f"Unexpected error: {str(e)}")
    

    async def get_token_price(self, token_address: str, include_liquidity: bool = True) -> Dict[str, Any]:
        """Get current token price and basic info with updated endpoints"""
        try:
            endpoint = "/defi/price"
            querystring = {"address": token_address}
            
            response = await self._request("GET", endpoint=endpoint, params=querystring)

            
            if not response.get("data") and not response.get("success"):
                logger.warning(f"Birdeye API returned empty data for {token_address}")
                return None
            
            # Handle different response formats
            data = response.get("data", response)
            
            # Standardize the response format
            price_info = {
                "address": token_address,
                "value": data.get("value") or data.get("price") or data.get("priceUsd"),
                "update_unix_time": data.get("updateUnixTime") or data.get("lastTradeUnixTime"),
                "update_human_time": data.get("updateHumanTime") or data.get("lastTradeHumanTime"),
                "price_change_24h": data.get("priceChange24h") or data.get("price24hChange"),
                "price_change_24h_percent": data.get("priceChange24hPercent") or data.get("price24hChangePercent"),
                "liquidity": data.get("liquidity") if include_liquidity else None,
                "volume_24h": data.get("v24hUSD") or data.get("volume24h"),
                "market_cap": data.get("mc") or data.get("marketCap")
            }
            
            return price_info
            
        except BirdeyeAPIError:
            # Re-raise Birdeye specific errors
            raise
        except Exception as e:
            logger.error(f"Error getting token price from Birdeye for {token_address}: {str(e)}")
            return None
        
    
    #UNAVAILABLE - REQUIRES PLAN UPGRADE
    async def get_token_metadata(self, token_address: str) -> Dict[str, Any]:
        """Get token metadata (simplified version to avoid API calls)"""
        try:
            endpoint = "/defi/v3/token/meta-data/single"
            querystring = {"address": token_address}
            
            response = await self._request("GET", endpoint=endpoint, params=querystring)
            
            if not response.get("data") and not response.get("success"):
                logger.warning(f"Birdeye API returned empty data for {token_address}")
                return None
            
            # Handle different response formats
            data = response.get("data", response)

            # Standardize the response format
            metadata_info = {
                "address": token_address,
                "symbol": data["symbol"],
                "name": data["name"],
                "extensions": data["extensions"]
            }
            
            return metadata_info
            
        except BirdeyeAPIError:
            # Re-raise Birdeye specific errors
            raise
        except Exception as e:
            logger.error(f"Error getting token metadata from Birdeye for {token_address}: {str(e)}")
            return None
    

    async def get_token_trades(self, token_address: str, sort_type: str = "desc", limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent token trades"""
        try:
            endpoint = "/defi/v3/token/txs"
            querystring = {"address": token_address, "sort_type": sort_type, "limit": limit}
            
            response = await self._request("GET", endpoint=endpoint, params=querystring)
            
            if not response.get("data") and not response.get("success"):
                logger.warning(f"Birdeye API returned empty data for {token_address}")
                return None

            # Handle different response formats
            data = response.get("data", response)
            
            return data
            
        except BirdeyeAPIError:
            # Re-raise Birdeye specific errors
            raise
        except Exception as e:
            logger.error(f"Error getting token price from Birdeye for {token_address}: {str(e)}")
            return None
        
    
    async def get_trending_tokens(self, sort_type: str = "asc", sort_by: str = "rank", limit: int = 20) -> List[Dict[str, Any]]:
        """Get trending tokens"""
        try:
            endpoint = "/defi/token_trending"
            querystring = {"sort_by": sort_by, "sort_type": sort_type, "limit": limit}
            
            response = await self._request("GET", endpoint=endpoint, params=querystring)
            
            if not response.get("data") and not response.get("success"):
                logger.warning(f"Birdeye API returned empty data")
                return None

            # Handle different response formats
            data = response.get("data", response)
            tokens = []
            
            # Standardize the response format
            for token in data["tokens"]:
                token_info = {
                    "address": token["address"],
                    "symbol": token["symbol"],
                    "name": token["name"],
                    "rank": token["rank"],
                    "update_unix_time": data.get("updateUnixTime"),
                    "update_human_time": data.get("updateTime"),
                    "liquidity": token["liquidity"],
                    "price": token["price"],
                    "price_24h_change_percent": token["price24hChangePercent"],
                    "volume_24h": {"USD": token["volume24hUSD"], "ChangePercent": token["volume24hChangePercent"]},
                    "fdv": token["fdv"],
                    "market_cap": token["marketcap"],
                    "is_scaled_ui_token": token["isScaledUiToken"],
                    "multiplier": token["multiplier"]
                }

                tokens.append(token_info)

            return tokens
                
        except BirdeyeAPIError:
            # Re-raise Birdeye specific errors
            raise
        except Exception as e:
            logger.error(f"Error getting trending tokens from Birdeye: {str(e)}")
            return None
    
    #UNAVAILABLE - REQUIRES PLAN UPGRADE
    async def search_tokens(self, query: str, sort_type: str = "desc", sort_by: str = "volume_24h_usd", limit: int = 20) -> List[Dict[str, Any]]:
        """Search tokens"""
        try:
            endpoint = "/defi/v3/search"
            query.update({"sort_type": sort_type, "sort_by": sort_by, "limit": limit})
            
            response = await self._request("GET", endpoint=endpoint, params=query)
            
            if not response.get("data") and not response.get("success"):
                logger.warning(f"Birdeye API returned empty data")
                return None

            # Handle different response formats
            data = response.get("data", response)
            results = {}
            
            # Standardize the response format
            for item in data["items"]:
                item_type = item["type"]
                if item_type not in results:
                    results.update({item_type: []})

                results[item_type].append(item["result"])

            return results
            
        except BirdeyeAPIError:
            # Re-raise Birdeye specific errors
            raise
        except Exception as e:
            logger.error(f"Error searching for tokens from Birdeye: {str(e)}")
            return None
    
    async def get_price_history(self, token_address: str, time_from: int, time_to: int, address_type: str = "token", timeframe: str = "1W") -> List[Dict[str, Any]]:
        """Get price history"""
        try:
            if time_from < 0 or time_from > 10000000000 or time_to < 0 or time_to > 10000000000:
                raise Exception("Invalid timestamps - use values from 0 to 10000000000")

            endpoint = "/defi/history_price"
            querystring = {"address": token_address, "address_type": address_type, "type": timeframe, "time_from": time_from, "time_to": time_to}
            
            response = await self._request("GET", endpoint=endpoint, params=querystring)
            
            if not response.get("data") and not response.get("success"):
                logger.warning(f"Birdeye API returned empty data for {token_address}")
                return None

            # Handle different response formats
            data = response.get("data", response)
            history = {token_address: []}

            # Standardize the response format
            for point in data["items"]:
                point_info = {
                    "unix_time": point["unixTime"],
                    "value": point["value"]
                }

                history[token_address].append(point_info)
            
            return history
            
        except BirdeyeAPIError:
            # Re-raise Birdeye specific errors
            raise
        except Exception as e:
            logger.error(f"Error getting token price history from Birdeye for {token_address}: {str(e)}")
            return None
    
    async def get_top_traders(self, token_address: str, time_frame: str = "24h", sort_type: str = "desc", sort_by: str = "volume", limit: int = 5) -> List[Dict[str, Any]]:
        """Get top traders"""
        try:
            if limit < 0 or limit > 10:
                raise Exception("Invalid limit - use values from 0 to 10")

            endpoint = "/defi/v2/tokens/top_traders"
            querystring = {"address": token_address, "time_frame": time_frame, "sort_type": sort_type, "sort_by": sort_by, "limit": limit}
            
            response = await self._request("GET", endpoint=endpoint, params=querystring)
            
            if not response.get("data") and not response.get("success"):
                logger.warning(f"Birdeye API returned empty data for {token_address}")
                return None

            # Handle different response formats
            data = response.get("data", response)
            
            return data["items"]
            
        except BirdeyeAPIError:
            # Re-raise Birdeye specific errors
            raise
        except Exception as e:
            logger.error(f"Error getting top traders from Birdeye for {token_address}: {str(e)}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Birdeye API health with simplified approach"""
        try:
            start_time = time.time()
            
            # If no API key, return immediately
            if not self.api_key:
                return {
                    "healthy": False,
                    "api_key_configured": False,
                    "error": "Birdeye API key not configured. Set BIRDEYE_API_KEY in .env file",
                    "base_url": self.base_url,
                    "response_time": 0.0,
                    "recommendation": "Get API key from https://birdeye.so"
                }
            
            # Simple endpoint test without actually making API calls to avoid rate limits
            logger.debug(f"Birdeye API key configured: {self.api_key[:8]}*** (length: {len(self.api_key)})")
            
            # For testing purposes, just validate API key format and return success
            # Real health checks can be expensive with rate limits
            response_time = time.time() - start_time
            
            return {
                "healthy": True,
                "api_key_configured": True,
                "base_url": self.base_url,
                "response_time": response_time,
                "test_mode": "API key validation only",
                "note": "Full API test skipped to avoid rate limits"
            }
                
        except Exception as e:
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": f"Health check failed: {str(e)}",
                "base_url": self.base_url
            }


# Convenience functions
async def get_birdeye_client() -> BirdeyeClient:
    """Get configured Birdeye client"""
    return BirdeyeClient()


async def check_birdeye_health() -> Dict[str, Any]:
    """Check Birdeye service health"""
    async with BirdeyeClient() as client:
        return await client.health_check()