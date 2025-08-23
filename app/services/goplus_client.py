import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from loguru import logger
from goplus.auth import Auth

from app.core.config import get_settings

settings = get_settings()


class GOplusAPIError(Exception):
    """GOplus API specific errors"""
    pass


class GOplusClient:
    """GOplus API client for token security analysis using bearer token authentication"""
    
    def __init__(self):
        # Single APP_KEY and APP_SECRET pair for getting bearer token
        self.app_key = getattr(settings, 'GOPLUS_APP_KEY', None)
        self.app_secret = getattr(settings, 'GOPLUS_APP_SECRET', None)
        
        self.base_url = settings.GOPLUS_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.3  # 300ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        # Token management
        self._access_token = None
        self._token_expiry = 0
        
        # Log API key status
        self._log_api_key_status()
    
    def _log_api_key_status(self):
        """Log masked API key status"""
        if self.app_key and self.app_secret:
            masked_key = f"{self.app_key[:8]}***" if len(self.app_key) > 8 else f"{self.app_key[:4]}***"
            logger.debug(f"GOplus APP key configured: {masked_key}")
        else:
            logger.warning("GOplus APP key/secret not configured - set GOPLUS_APP_KEY and GOPLUS_APP_SECRET")
    
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
    
    async def _get_access_token(self) -> str:
        """Get access token using APP_KEY and APP_SECRET"""
        
        # Check if we have a valid cached token
        current_time = time.time()
        if self._access_token and current_time < self._token_expiry:
            return self._access_token
        
        if not self.app_key or not self.app_secret:
            raise GOplusAPIError("GOplus APP_KEY and APP_SECRET not configured")
        
        await self._ensure_session()
        
        try:
            response = Auth(key=self.app_key, secret=self.app_secret).get_access_token()
            response_data = response.to_dict()
            if response_data["code"] == 1:
                self._access_token = response_data["result"]["access_token"]
                self._token_expiry = response_data["result"]["expires_in"]

                print(self._access_token)

                logger.debug(f"GOplus access token obtained")
                return response_data["result"]["access_token"]
                
            else:
                raise GOplusAPIError("Failed to optain access token")
                    
        except asyncio.TimeoutError:
            raise GOplusAPIError("Token request timeout")
        except aiohttp.ClientError as e:
            raise GOplusAPIError(f"Token request error: {str(e)}")
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with bearer token authentication"""
        await self._ensure_session()
        await self._rate_limit()
        
        # Get access token
        access_token = await self._get_access_token()
        
        url = f"{self.base_url}{endpoint}"
        params = kwargs.pop("params", {})
        json_data = kwargs.pop("json", None)
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": access_token,
            **kwargs.pop("headers", {})
        }
        
        try:
            request_kwargs = {
                "headers": headers,
                "params": params,
                **kwargs
            }
            
            if json_data:
                request_kwargs["json"] = json_data
            
            async with self.session.request(method, url, **request_kwargs) as response:
                content_type = response.headers.get('content-type', '').lower()
                
                logger.debug(f"GOplus {method} {endpoint} - Status: {response.status}, Content-Type: {content_type}")
                
                if response.status == 200:
                    if 'application/json' in content_type:
                        response_data = await response.json()
                        
                        # Check for GOplus API-level errors
                        if isinstance(response_data, dict):
                            error_code = response_data.get('code')
                            if error_code != 1:
                                error_msg = response_data.get('message', 'Unknown API error')
                                logger.error(f"GOplus API error (code {error_code}): {error_msg}")
                                
                                # Handle token expiry
                                if error_code in [4001, 4002]:  # Token expired or invalid
                                    # Clear cached token and retry once
                                    self._access_token = None
                                    self._token_expiry = 0
                                    
                                    logger.debug("Token expired, retrying with new token")
                                    return await self._request(method, endpoint, params=params, json=json_data, **kwargs)
                                
                                raise GOplusAPIError(f"API error (code {error_code}): {error_msg}")
                        
                        return response_data
                    else:
                        logger.error(f"Unexpected content type from GOplus: {content_type}")
                        raise GOplusAPIError(f"Expected JSON, got {content_type}")
                
                elif response.status == 401:
                    # Token might be expired, clear cache and retry once
                    if self._access_token:
                        self._access_token = None
                        self._token_expiry = 0
                        logger.debug("401 error, clearing token cache")
                        return await self._request(method, endpoint, params=params, json=json_data, **kwargs)
                    else:
                        raise GOplusAPIError("Authentication failed")
                else:
                    try:
                        error_text = await response.text()
                        raise GOplusAPIError(f"HTTP {response.status}: {error_text[:200]}")
                    except:
                        raise GOplusAPIError(f"HTTP {response.status}: Unknown error")
        
        except asyncio.TimeoutError:
            raise GOplusAPIError("Request timeout")
        except aiohttp.ClientError as e:
            raise GOplusAPIError(f"Client error: {str(e)}")
    
    # ==============================================
    # TOKEN SECURITY API
    # ==============================================
    
    async def analyze_token_security(self, token_address: str) -> Dict[str, Any]:
        """Comprehensive token security analysis"""
        try:
            # Use the correct API endpoint format
            endpoint = f"/api/v1/solana/token_security"
            
            params = {
                "contract_addresses": token_address
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if response and response.get("result"):
                # GOplus returns results keyed by contract address
                token_results = response["result"].get(token_address.lower()) or response["result"].get(token_address)
                if token_results:
                    return token_results
            
            logger.warning(f"No results returned for {token_address}")
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing token security for {token_address} with GOplus: {str(e)}")
            return None
    
    def _extract_security_warnings(self, token_results: Dict[str, Any]) -> List[str]:
        """Extract security warnings from token results"""
        warnings = []
        
        if token_results.get("is_honeypot", "0") == "1":
            warnings.append("Token appears to be a honeypot")
        
        if token_results.get("is_blacklisted", "0") == "1":
            warnings.append("Token is blacklisted")
        
        if token_results.get("can_take_back_ownership", "0") == "1":
            warnings.append("Contract owner can take back ownership")
        
        if token_results.get("hidden_owner", "0") == "1":
            warnings.append("Contract has hidden owner")
        
        if token_results.get("external_call", "0") == "1":
            warnings.append("Contract makes external calls")
        
        try:
            buy_tax = float(token_results.get("buy_tax", 0))
            sell_tax = float(token_results.get("sell_tax", 0))
            
            if buy_tax > 10:
                warnings.append(f"High buy tax: {buy_tax}%")
            if sell_tax > 10:
                warnings.append(f"High sell tax: {sell_tax}%")
        except:
            pass
        
        return warnings
    
    # ==============================================
    # RUGPULL DETECTION API
    # ==============================================
    
    async def detect_rugpull(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Detect rug pull risks for a token"""
        try:
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
            endpoint = f"/api/v1/rugpull_detecting/{chain_id}"
            
            params = {
                "contract_addresses": token_address
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if response and response.get("result"):
                token_results = response["result"]
                if token_results:
                    for param in token_results:
                        token_results[param] = True if token_results[param] == 1 else False
                        
                    return token_results
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting rugpull for {token_address} with GOplus: {str(e)}")
            return None
    
    # ==============================================
    # SUPPORTED CHAINS
    # ==============================================
    
    async def get_supported_chains(self, name: str) -> List[Dict[str, Any]]:
        """Get supported chains"""
        try:
            endpoint = "/api/v1/supported_chains"
            params = {
                "name": name
            }
            response = await self._request("GET", endpoint, params=params)

            if response and response.get("result"):
                return response["result"]
            
            # Return common supported chains if endpoint doesn't exist
            return [
                {"chain_id": "1", "name": "Ethereum", "supported": True},
                {"chain_id": "56", "name": "BSC", "supported": True},
                {"chain_id": "137", "name": "Polygon", "supported": True},
                {"chain_id": "101", "name": "Solana", "supported": True}
            ]
            
        except Exception as e:
            logger.debug(f"Error getting supported chains: {str(e)}")
            # Return fallback data
            return [
                {"chain_id": "1", "name": "Ethereum", "supported": True},
                {"chain_id": "56", "name": "BSC", "supported": True},
                {"chain_id": "137", "name": "Polygon", "supported": True},
                {"chain_id": "101", "name": "Solana", "supported": True}
            ]
    
    # ==============================================
    # COMPREHENSIVE ANALYSIS
    # ==============================================
    
    async def comprehensive_analysis(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Run comprehensive analysis using available GOplus services"""
        logger.info(f"🔍 Running comprehensive GOplus analysis for {token_address}")
        
        # Run available analyses in parallel
        tasks = {
            "security": self.analyze_token_security(token_address, chain),
            "rugpull": self.detect_rugpull(token_address, chain)
        }
        
        # Execute all tasks
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Compile results
        analysis = {
            "token_address": token_address,
            "chain": chain,
            "timestamp": int(time.time()),
            "services_used": list(tasks.keys()),
            "analyses": {}
        }
        
        # Process results
        for i, (service_name, task) in enumerate(tasks.items()):
            result = results[i]
            if isinstance(result, Exception):
                analysis["analyses"][service_name] = {
                    "success": False,
                    "error": str(result)
                }
            else:
                analysis["analyses"][service_name] = {
                    "success": True,
                    "data": result
                }
        
        # Generate overall assessment
        analysis["overall_assessment"] = self._generate_overall_assessment(analysis["analyses"])
        
        return analysis
    
    def _generate_overall_assessment(self, analyses: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall risk assessment from all analyses"""
        overall = {
            "risk_score": 0,
            "risk_level": "unknown",
            "is_safe": None,
            "major_risks": [],
            "recommendations": [],
            "confidence": 0
        }
        
        all_warnings = []
        
        # Collect data from successful analyses
        for service_name, result in analyses.items():
            if result.get("success") and result.get("data"):
                data = result["data"]
                
                if "warnings" in data:
                    all_warnings.extend(data["warnings"])
                
                if data.get("is_honeypot"):
                    overall["major_risks"].append("Token identified as honeypot")
                    overall["is_safe"] = False
                
                if data.get("is_blacklisted"):
                    overall["major_risks"].append("Token is blacklisted")
                    overall["is_safe"] = False
        
        # Calculate risk level based on warnings and issues
        risk_count = len(all_warnings) + len(overall["major_risks"])
        
        if overall["major_risks"]:
            overall["risk_level"] = "critical"
            overall["risk_score"] = 90
            overall["is_safe"] = False
        elif risk_count >= 5:
            overall["risk_level"] = "high"
            overall["risk_score"] = 70
            overall["is_safe"] = False
        elif risk_count >= 3:
            overall["risk_level"] = "medium"
            overall["risk_score"] = 50
        elif risk_count >= 1:
            overall["risk_level"] = "low"
            overall["risk_score"] = 20
        else:
            overall["risk_level"] = "low"
            overall["risk_score"] = 10
            overall["is_safe"] = True
        
        return overall
    
    # ==============================================
    # HEALTH CHECK
    # ==============================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check GOplus API health"""
        try:
            start_time = time.time()
            
            # Check if APP_KEY and APP_SECRET are configured
            api_key_configured = bool(self.app_key and self.app_secret)
            
            if not api_key_configured:
                return {
                    "healthy": False,
                    "api_key_configured": False,
                    "error": "GOplus APP_KEY and APP_SECRET not configured",
                    "base_url": self.base_url,
                    "response_time": 0.0,
                    "recommendation": "Get API keys from https://gopluslabs.io/"
                }
            
            # Test token endpoint (should work if credentials are valid)
            try:
                access_token = await self._get_access_token()
                
                if access_token:
                    response_time = time.time() - start_time
                    
                    return {
                        "healthy": True,
                        "api_key_configured": True,
                        "base_url": self.base_url,
                        "response_time": response_time,
                        "access_token_obtained": True
                    }
                else:
                    raise GOplusAPIError("No access token received")
                    
            except GOplusAPIError as e:
                response_time = time.time() - start_time
                error_msg = str(e)
                
                if "invalid" in error_msg.lower() or "authentication" in error_msg.lower():
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": "Invalid API credentials - check your GOplus account",
                        "base_url": self.base_url,
                        "response_time": response_time
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
            return {
                "healthy": False,
                "api_key_configured": bool(self.app_key and self.app_secret),
                "error": str(e),
                "base_url": self.base_url
            }


# Convenience functions
async def get_goplus_client() -> GOplusClient:
    """Get configured GOplus client"""
    return GOplusClient()


async def check_goplus_health() -> Dict[str, Any]:
    """Check GOplus service health"""
    async with GOplusClient() as client:
        return await client.health_check()