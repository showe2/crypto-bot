import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class SolanaFMAPIError(Exception):
    """SolanaFM API specific errors"""
    pass


class SolanaFMClient:
    """SolanaFM API client for Solana on-chain data and analytics"""
    
    def __init__(self):
        self.base_url = "https://api.solana.fm"
        self.session = None
        self._rate_limit_delay = 0.2  # 200ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        logger.info("SolanaFM client initialized (no API key required)")
    
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
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                content_type = response.headers.get('content-type', '').lower()
                
                logger.debug(f"SolanaFM {method} {endpoint} - Status: {response.status}, Content-Type: {content_type}")
                
                if response.status == 200:
                    if 'application/json' in content_type:
                        response_data = await response.json()
                        return response_data
                    else:
                        response_text = await response.text()
                        logger.warning(f"Unexpected content type from SolanaFM: {content_type}")
                        raise SolanaFMAPIError(f"Expected JSON, got {content_type}")
                        
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"SolanaFM rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                elif response.status == 401:
                    raise SolanaFMAPIError("Invalid SolanaFM API key or unauthorized access")
                elif response.status == 403:
                    raise SolanaFMAPIError("Forbidden - check API key permissions")
                elif response.status == 404:
                    # Endpoint not found
                    raise SolanaFMAPIError(f"SolanaFM endpoint not found: {endpoint}")
                else:
                    try:
                        error_text = await response.text()
                        raise SolanaFMAPIError(f"HTTP {response.status}: {error_text[:200]}")
                    except:
                        raise SolanaFMAPIError(f"HTTP {response.status}: Unknown error")
                    
        except asyncio.TimeoutError:
            raise SolanaFMAPIError("SolanaFM API request timeout")
        except aiohttp.ClientError as e:
            raise SolanaFMAPIError(f"SolanaFM client error: {str(e)}")
    
    async def get_account_detail(self, account_address: str) -> Dict[str, Any]:
        """Get account details"""
        try:
            endpoint = f"/v0/accounts/{account_address}"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                raise SolanaFMAPIError("No data returned from account detail endpoint")
            
            # Handle response structure
            if isinstance(response, dict):
                if response.get("error"):
                    error_msg = response.get("message", "Unknown API error")
                    raise SolanaFMAPIError(f"API error: {error_msg}")
                
                data = response["result"]["data"]
                
                account_info = {
                    "address": account_address,
                    "network": data.get("network"),
                    "lamports": data.get("lamports"),
                    "friendly_name": data.get("friendlyName"),
                    "balance_sol": float(data.get("lamports", 0)) / 1e9 if data.get("lamports") else 0,
                    "tags": None if len(data.get("tags")) == 0 else data.get("tags"),
                    "flag": None if len(data.get("flag")) == 0 else data.get("flag")
                }
                
                return account_info
            else:
                raise SolanaFMAPIError("Unexpected response format")
            
        except SolanaFMAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting account detail from SolanaFM for {account_address}: {str(e)}")
            raise SolanaFMAPIError(f"Failed to get account detail: {str(e)}")
    
    async def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """Get token information"""
        try:
            endpoint = f"/v1/tokens/{token_address}"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                raise SolanaFMAPIError("No data returned from token info endpoint")
            
            # Handle response structure
            if isinstance(response, dict):
                if response.get("error"):
                    error_msg = response.get("message", "Unknown API error")
                    raise SolanaFMAPIError(f"API error: {error_msg}")
                
                data = response.get("data", response)
                token_list = data.get("tokenList")
                
                token_info = {
                    "address": token_address,
                    "name": token_list.get("name"),
                    "symbol": token_list.get("symbol"),
                    "decimals": data.get("decimals"),
                    "token_type": data.get("tokenType"),
                    "mint_authority": data.get("mintAuthority"),
                    "freeze_authority": data.get("freezeAuthority"),
                    "extensions": token_list.get("extensions"),
                    "token_metadata": data.get("tokenMetadata"),
                    "tags": data.get("tags", []),
                }
                
                return token_info
            else:
                raise SolanaFMAPIError("Unexpected response format")
            
        except SolanaFMAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting token info from SolanaFM for {token_address}: {str(e)}")
            raise SolanaFMAPIError(f"Failed to get token info: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check SolanaFM API health"""
        try:
            start_time = time.time()
            
            # Test a simple endpoint that doesn't require authentication
            logger.debug("SolanaFM health check: testing public endpoint")
            
            try:
                # Test with a well-known token address
                test_token = "So11111111111111111111111111111111111112"  # Wrapped SOL
                endpoint = f"/v1/tokens/{test_token}"
                
                response = await self._request("GET", endpoint)
                response_time = time.time() - start_time
                
                return {
                    "healthy": True,
                    "api_key_configured": True,  # No API key needed
                    "base_url": self.base_url,
                    "response_time": response_time,
                    "test_data": response if response else "No data",
                    "working_endpoint": endpoint,
                    "note": "SolanaFM is free to use, no API key required"
                }
                
            except SolanaFMAPIError as e:
                response_time = time.time() - start_time
                error_msg = str(e)
                
                # Check if it's a rate limit or temporary issue
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
                        "error": f"API endpoint failed: {error_msg}",
                        "base_url": self.base_url,
                        "response_time": response_time,
                        "tested_endpoint": "/v1/tokens/{test_token}"
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
async def get_solanafm_client() -> SolanaFMClient:
    """Get configured SolanaFM client"""
    return SolanaFMClient()


async def check_solanafm_health() -> Dict[str, Any]:
    """Check SolanaFM service health"""
    async with SolanaFMClient() as client:
        return await client.health_check()