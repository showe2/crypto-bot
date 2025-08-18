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
        self._rate_limit_delay = 0.15  # 150ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        # Updated API endpoints based on current Birdeye API documentation
        self.api_endpoints = {
            "multi_price": "/defi/multi_price"
        }
        
        # Log API key status (masked for security)
        if self.api_key:
            masked_key = f"{self.api_key[:8]}***{self.api_key[-4:]}" if len(self.api_key) > 12 else f"{self.api_key[:4]}***"
            logger.info(f"Birdeye API key configured: {masked_key} (length: {len(self.api_key)})")
        else:
            logger.warning("Birdeye API key not configured - check BIRDEYE_API_KEY in .env file")
        
        logger.info(f"Birdeye base URL: {self.base_url}")
    
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
                            if retry_response.status == 200:
                                retry_data = await retry_response.json()
                                return retry_data
                            else:
                                last_error = f"Retry failed - HTTP {retry_response.status}"
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
                # Try current API format with address
                {
                    "endpoint": "/defi/token_overview",
                    "method": "GET",
                    "params": {
                        "address": token_address
                    }
                },
                # Try price endpoint with different parameter names
                {
                    "endpoint": "/defi/price",
                    "method": "GET", 
                    "params": {
                        "address": token_address
                    }
                },
                # Try with list_address parameter (used by multi_price)
                {
                    "endpoint": "/defi/multi_price",
                    "method": "GET",
                    "params": {
                        "list_address": token_address
                    }
                },
                # Try with different parameter name
                {
                    "endpoint": "/defi/price",
                    "method": "GET",
                    "params": {
                        "token_address": token_address
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
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Birdeye API health with multiple endpoint tests"""
        try:
            # Log detailed API key information
            logger.info("=== BIRDEYE HEALTH CHECK START ===")
            logger.info(f"Base URL: {self.base_url}")
            
            if self.api_key:
                logger.info(f"API Key configured: YES")
                logger.info(f"API Key length: {len(self.api_key)}")
                logger.info(f"API Key first 12 chars: {self.api_key[:12]}...")
                logger.info(f"API Key last 4 chars: ...{self.api_key[-4:]}")
                logger.info(f"API Key type: {type(self.api_key)}")
                # Check for common issues
                if ' ' in self.api_key:
                    logger.warning("API Key contains spaces - this might be an issue")
                if self.api_key.startswith('"') or self.api_key.startswith("'"):
                    logger.warning("API Key starts with quotes - this might be an issue")
            else:
                logger.info("API Key configured: NO")
                logger.info("BIRDEYE_API_KEY environment variable not set")
            
            start_time = time.time()
            
            # Test with a well-known token (Wrapped SOL) using simplest endpoint
            sol_address = "So11111111111111111111111111111111111112"
            
            # Updated endpoints based on current Birdeye API (2024/2025)
            health_endpoints = [
                # Try price endpoint with correct format  
                {
                    "endpoint": "/defi/price",
                    "method": "GET",
                    "params": {"address": sol_address}
                },
                # Try multi-price endpoint (often works)
                {
                    "endpoint": "/defi/multi_price", 
                    "method": "GET",
                    "params": {"list_address": sol_address}
                }
            ]
            
            try:
                logger.info(f"Testing endpoints for token: {sol_address}")
                response = await self._request_with_fallback(health_endpoints, sol_address)
                response_time = time.time() - start_time
                
                logger.info("=== BIRDEYE HEALTH CHECK SUCCESS ===")
                
                # If we get here, at least one endpoint worked
                return {
                    "healthy": True,
                    "api_key_configured": bool(self.api_key),
                    "base_url": self.base_url,
                    "response_time": response_time,
                    "test_token": sol_address,
                    "test_data_available": response is not None,
                    "endpoints_tested": len(health_endpoints)
                }
                
            except BirdeyeAPIError as api_error:
                response_time = time.time() - start_time
                error_msg = str(api_error)
                
                logger.error(f"=== BIRDEYE HEALTH CHECK FAILED ===")
                logger.error(f"Error: {error_msg}")
                
                # Check if it's an API key issue
                if "not configured" in error_msg:
                    return {
                        "healthy": False,
                        "api_key_configured": False,
                        "error": "Birdeye API key not configured. Set BIRDEYE_API_KEY in .env file",
                        "base_url": self.base_url,
                        "response_time": response_time,
                        "recommendation": "Get API key from https://birdeye.so"
                    }
                elif "authentication failed" in error_msg.lower() or "invalid api key" in error_msg.lower():
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": "Birdeye API key is invalid or expired",
                        "base_url": self.base_url,
                        "response_time": response_time,
                        "recommendation": "Check your API key at https://birdeye.so"
                    }
                else:
                    return {
                        "healthy": False,
                        "api_key_configured": bool(self.api_key),
                        "error": error_msg,
                        "base_url": self.base_url,
                        "response_time": response_time,
                        "test_token": sol_address
                    }
            
        except Exception as e:
            logger.error(f"=== BIRDEYE HEALTH CHECK EXCEPTION ===")
            logger.error(f"Exception: {str(e)}")
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": f"Health check failed: {str(e)}",
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