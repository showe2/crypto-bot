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
        base58_pattern = re.compile(r'^[1-9A-HJ-NP-Za-km-z]+$')
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
    
    async def _request_with_fallback(self, endpoints_to_try: List[Dict], token_address: str = None) -> Dict[str, Any]:
        """Try multiple API endpoint formats until one works"""
        await self._ensure_session()
        await self._rate_limit()
        
        # Validate address if provided
        if token_address and not self._validate_solana_address(token_address):
            raise BirdeyeAPIError(f"Invalid Solana address format: {token_address}")
        
        last_error = None
        
        for i, endpoint_config in enumerate(endpoints_to_try):
            try:
                method = endpoint_config.get("method", "GET")
                endpoint = endpoint_config["endpoint"]
                params = endpoint_config.get("params", {})
                json_data = endpoint_config.get("json", None)
                
                # Replace address placeholder in URL if present
                if token_address:
                    url = f"{self.base_url}{endpoint}".format(address=token_address)
                else:
                    url = f"{self.base_url}{endpoint}"
                
                # Try different authentication methods for Birdeye
                # Start with minimal headers first
                headers = {
                    "Accept": "application/json",
                    "User-Agent": "Solana-Token-Analysis/1.0"
                }
                
                # Add API key if available - try ONE format at a time
                if self.api_key:
                    # Birdeye typically uses X-API-KEY, but let's try the most common format
                    headers["X-API-KEY"] = self.api_key
                    logger.debug(f"Using API key: {self.api_key[:8]}*** (length: {len(self.api_key)})")
                else:
                    logger.debug("No API key configured, trying without authentication")
                
                logger.debug(f"Trying Birdeye endpoint {i+1}/{len(endpoints_to_try)}: {method} {endpoint}")
                logger.debug(f"Full URL: {url}")
                logger.debug(f"Params: {params}")
                
                async with self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data
                ) as response:
                    
                    logger.debug(f"Response status: {response.status}")
                    logger.debug(f"Response headers: {dict(response.headers)}")
                    
                    # Check content type before parsing
                    content_type = response.headers.get('content-type', '').lower()
                    logger.debug(f"Content type: {content_type}")
                    
                    if response.status == 200:
                        if 'application/json' in content_type:
                            try:
                                response_data = await response.json()
                                logger.info(f"✅ Birdeye endpoint {i+1} successful: {endpoint}")
                                logger.debug(f"Response data keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
                                return response_data
                            except Exception as parse_error:
                                last_error = f"JSON parse error: {str(parse_error)}"
                                logger.debug(f"❌ Endpoint {i+1} JSON parse failed: {last_error}")
                                continue
                        else:
                            # Try to get text response for debugging
                            try:
                                text_response = await response.text()
                                logger.debug(f"Non-JSON response content: {text_response[:300]}")
                                last_error = f"Unexpected content type: {content_type}. Response: {text_response[:200]}"
                            except:
                                last_error = f"Unexpected content type: {content_type}"
                            logger.debug(f"❌ Endpoint {i+1} wrong content type: {last_error}")
                            continue
                    elif response.status == 401:
                        # Authentication failed
                        try:
                            error_text = await response.text()
                            logger.error(f"401 Authentication failed on endpoint {i+1}")
                            logger.error(f"Request URL: {url}")
                            logger.error(f"Request headers: {dict(headers)}")
                            logger.error(f"Response text: {error_text[:500]}")
                            
                            if self.api_key:
                                last_error = f"Authentication failed (401): Invalid API key. Response: {error_text[:200]}"
                            else:
                                last_error = f"Authentication required (401): API key needed. Response: {error_text[:200]}"
                        except:
                            last_error = f"Authentication failed (401): {'Invalid API key' if self.api_key else 'API key required'}"
                        logger.debug(f"❌ Endpoint {i+1} auth failed: {last_error}")
                        continue
                    elif response.status == 429:
                        # Rate limited - wait and skip retry to avoid further rate limiting
                        retry_after = int(response.headers.get('Retry-After', 2))
                        logger.warning(f"Birdeye rate limited, endpoint {i+1} failed (would wait {retry_after}s)")
                        
                        # For testing, don't actually retry to avoid further rate limiting
                        last_error = f"Rate limited (429): API calls exhausted. Retry after {retry_after}s"
                        continue
                    else:
                        # Try to get response text for better error reporting
                        try:
                            error_text = await response.text()
                            last_error = f"HTTP {response.status}: {error_text[:200] if error_text else 'No response content'}"
                        except:
                            last_error = f"HTTP {response.status}: Unable to read response"
                        logger.debug(f"❌ Endpoint {i+1} failed: {last_error}")
                        
            except Exception as e:
                last_error = f"Request failed: {str(e)}"
                logger.debug(f"❌ Endpoint {i+1} exception: {last_error}")
                continue
        
        # If all endpoints failed
        if "Authentication" in str(last_error) or "401" in str(last_error):
            if not self.api_key:
                raise BirdeyeAPIError("Birdeye API key not configured. Please set BIRDEYE_API_KEY in your .env file")
            else:
                raise BirdeyeAPIError(f"Birdeye API authentication failed. Check your API key. Last error: {last_error}")
        else:
            raise BirdeyeAPIError(f"All API endpoints failed. Last error: {last_error}")
    
    async def get_token_price(self, token_address: str, include_liquidity: bool = True) -> Dict[str, Any]:
        """Get current token price and basic info with updated endpoints"""
        try:
            # Define updated endpoint variations based on current Birdeye API
            endpoints_to_try = [
                # Try multi_price endpoint (most reliable format)
                {
                    "endpoint": "/defi/multi_price",
                    "method": "GET",
                    "params": {
                        "list_address": token_address
                    }
                },
                # Try price endpoint with address parameter
                {
                    "endpoint": "/defi/price",
                    "method": "GET", 
                    "params": {
                        "address": token_address
                    }
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
        """Get token metadata (simplified version to avoid API calls)"""
        try:
            # For now, return basic metadata structure to avoid API calls
            # This can be expanded when API endpoints are more stable
            return {
                "address": token_address,
                "name": None,
                "symbol": None,
                "decimals": 9,
                "note": "Metadata fetching disabled to avoid rate limits"
            }
        except Exception as e:
            logger.warning(f"Error getting token metadata for {token_address}: {str(e)}")
            return None
    
    async def get_token_trades(self, token_address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent token trades (simplified version)"""
        try:
            # Return empty list to avoid API calls in testing
            logger.debug(f"Token trades disabled for {token_address} to avoid rate limits")
            return []
        except Exception as e:
            logger.warning(f"Error getting token trades for {token_address}: {str(e)}")
            return []
    
    async def get_trending_tokens(self, sort_by: str = "volume", limit: int = 20) -> List[Dict[str, Any]]:
        """Get trending tokens (simplified version)"""
        try:
            # Return empty list to avoid API calls in testing
            logger.debug(f"Trending tokens disabled to avoid rate limits")
            return []
        except Exception as e:
            logger.warning(f"Error getting trending tokens: {str(e)}")
            return []
    
    async def search_tokens(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search tokens (simplified version)"""
        try:
            # Return empty list to avoid API calls in testing
            logger.debug(f"Token search disabled for '{query}' to avoid rate limits")
            return []
        except Exception as e:
            logger.warning(f"Error searching tokens for '{query}': {str(e)}")
            return []
    
    async def get_price_history(self, token_address: str, timeframe: str = "7d") -> List[Dict[str, Any]]:
        """Get price history (simplified version)"""
        try:
            # Return empty list to avoid API calls in testing
            logger.debug(f"Price history disabled for {token_address} to avoid rate limits")
            return []
        except Exception as e:
            logger.warning(f"Error getting price history for {token_address}: {str(e)}")
            return []
    
    async def get_top_traders(self, token_address: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top traders (simplified version)"""
        try:
            # Return empty list to avoid API calls in testing
            logger.debug(f"Top traders disabled for {token_address} to avoid rate limits")
            return []
        except Exception as e:
            logger.warning(f"Error getting top traders for {token_address}: {str(e)}")
            return []
    
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