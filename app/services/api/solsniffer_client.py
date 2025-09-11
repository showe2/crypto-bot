import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class SolSnifferAPIError(Exception):
    """SolSniffer API specific errors"""
    pass


class SolSnifferClient:
    """SolSniffer API client for Solana token analysis and monitoring"""
    
    def __init__(self):
        self.api_key = settings.SOLSNIFFER_API_KEY
        self.base_url = settings.SOLSNIFFER_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.5  # 500ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        if self.api_key:
            logger.debug(f"SolSniffer API key configured")
        else:
            logger.warning("SolSniffer API key not configured - set SOLSNIFFER_API_KEY")
    
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
    
    async def _request(self, method: str, endpoint: str, retries: int = 0, **kwargs) -> Dict[str, Any]:
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
            headers["X-API-KEY"] = self.api_key
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                content_type = response.headers.get('content-type', '').lower()
                
                logger.debug(f"SolSniffer {method} {endpoint} - Status: {response.status}, Content-Type: {content_type}")
                
                if response.status == 200:
                    if 'application/json' in content_type:
                        response_data = await response.json()
                        return response_data
                    else:
                        response_text = await response.text()
                        logger.warning(f"Unexpected content type from SolSniffer: {content_type}")
                        raise SolSnifferAPIError(f"Expected JSON, got {content_type}")
                        
                elif response.status == 429 and retries < 3:
                    # Rate limited
                    retries += 1
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"SolSniffer rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, retries, **kwargs)
                elif response.status == 401:
                    raise SolSnifferAPIError("Invalid SolSniffer API key or unauthorized access")
                elif response.status == 403:
                    raise SolSnifferAPIError("Forbidden - check API key permissions")
                elif response.status == 404:
                    logger.debug(f"SolSniffer 404 for {endpoint} - endpoint may not exist")
                    return None
                else:
                    try:
                        error_text = await response.text()
                        raise SolSnifferAPIError(f"HTTP {response.status}: {error_text[:200]}")
                    except:
                        raise SolSnifferAPIError(f"HTTP {response.status}: Unknown error")
                    
        except asyncio.TimeoutError:
            raise SolSnifferAPIError("SolSniffer API request timeout")
        except aiohttp.ClientError as e:
            raise SolSnifferAPIError(f"SolSniffer client error: {str(e)}")
    
    async def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """Analyze token for potential issues and risks"""
        try:
            endpoint = f"/v2/token/{token_address}"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                logger.debug(f"No analysis data found for {token_address}")
                return None
            
            return response.get("tokenData", {})
            
        except SolSnifferAPIError:
            raise
        except Exception as e:
            logger.error(f"Error analyzing token {token_address} with SolSniffer: {str(e)}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check SolSniffer API health"""
        try:
            start_time = time.time()
            
            # Check if API key is configured
            api_key_configured = bool(self.api_key)
            
            if not api_key_configured:
                return {
                    "healthy": False,
                    "api_key_configured": False,
                    "error": "SolSniffer API key not configured. Set SOLSNIFFER_API_KEY in .env file",
                    "base_url": self.base_url,
                    "response_time": 0.0,
                    "recommendation": "Get API key from SolSniffer service"
                }
            
            # Test a simple endpoint
            try:
                test_response = await self.get_token_info("4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R")
                response_time = time.time() - start_time
                
                if test_response is not None:
                    return {
                        "healthy": True,
                        "api_key_configured": True,
                        "base_url": self.base_url,
                        "response_time": response_time,
                        "test_endpoint": "/v1/trending",
                        "note": "API accessible via trending endpoint"
                    }
                else:
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": "No response from test endpoints",
                        "base_url": self.base_url,
                        "response_time": response_time
                    }
                
            except SolSnifferAPIError as e:
                response_time = time.time() - start_time
                error_msg = str(e)
                
                if "401" in error_msg or "unauthorized" in error_msg.lower():
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": "Authentication failed - check API key validity",
                        "base_url": self.base_url,
                        "response_time": response_time
                    }
                elif "403" in error_msg or "forbidden" in error_msg.lower():
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": "Forbidden - check API key permissions",
                        "base_url": self.base_url,
                        "response_time": response_time
                    }
                else:
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": error_msg,
                        "base_url": self.base_url,
                        "response_time": response_time
                    }
            
        except Exception as e:
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": str(e),
                "base_url": self.base_url
            }


# Convenience functions
async def get_solsniffer_client() -> SolSnifferClient:
    """Get configured SolSniffer client"""
    return SolSnifferClient()


async def check_solsniffer_health() -> Dict[str, Any]:
    """Check SolSniffer service health"""
    async with SolSnifferClient() as client:
        return await client.health_check()