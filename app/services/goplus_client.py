import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class GOplusAPIError(Exception):
    """GOplus API specific errors"""
    pass


class GOplusClient:
    """GOplus API client for Solana transaction simulation, rug pull detection, and token security"""
    
    def __init__(self):
        # GOplus uses APP Key + APP Secret pairs for each service
        self.transaction_app_key = getattr(settings, 'GOPLUS_TRANSACTION_APP_KEY', None)
        self.transaction_app_secret = getattr(settings, 'GOPLUS_TRANSACTION_APP_SECRET', None)
        
        self.rugpull_app_key = getattr(settings, 'GOPLUS_RUGPULL_APP_KEY', None)
        self.rugpull_app_secret = getattr(settings, 'GOPLUS_RUGPULL_APP_SECRET', None)
        
        self.security_app_key = getattr(settings, 'GOPLUS_SECURITY_APP_KEY', None)
        self.security_app_secret = getattr(settings, 'GOPLUS_SECURITY_APP_SECRET', None)
        
        self.base_url = settings.GOPLUS_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.3  # 300ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        # Token cache
        self._access_tokens = {}  # Cache tokens by service
        self._token_expiry = {}   # Track token expiry times
        
        # Log API key status
        self._log_api_key_status()
    
    def _log_api_key_status(self):
        """Log masked API key status"""
        keys_status = {
            "transaction": bool(self.transaction_app_key and self.transaction_app_secret),
            "rugpull": bool(self.rugpull_app_key and self.rugpull_app_secret),
            "security": bool(self.security_app_key and self.security_app_secret)
        }
        
        configured_count = sum(keys_status.values())
        logger.debug(f"GOplus APP keys configured: {configured_count}/3 ({keys_status})")
        
        if configured_count < 3:
            missing_keys = [service for service, configured in keys_status.items() if not configured]
            logger.warning(f"GOplus missing APP key pairs: {missing_keys}")
    
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
    
    async def _get_access_token(self, app_key: str, app_secret: str, service_name: str) -> str:
        """Get access token using app_key and app_secret"""
        
        # Check if we have a valid cached token
        current_time = time.time()
        if (service_name in self._access_tokens and 
            service_name in self._token_expiry and 
            current_time < self._token_expiry[service_name]):
            return self._access_tokens[service_name]
        
        await self._ensure_session()
        
        # Get new access token
        token_url = f"{self.base_url}/api/v1/token"
        
        payload = {
            "app_key": app_key,
            "app_secret": app_secret
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            async with self.session.post(token_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check for success
                    if data.get("code") == 1 and data.get("result"):
                        access_token = data["result"].get("access_token")
                        expires_in = data["result"].get("expires_in", 3600)  # Default 1 hour
                        
                        if access_token:
                            # Cache the token
                            self._access_tokens[service_name] = access_token
                            self._token_expiry[service_name] = current_time + expires_in - 60  # Refresh 1 min early
                            
                            logger.debug(f"GOplus access token obtained for {service_name}, expires in {expires_in}s")
                            return access_token
                    
                    error_msg = data.get("message", "Failed to get access token")
                    raise GOplusAPIError(f"Token request failed: {error_msg}")
                else:
                    error_text = await response.text()
                    raise GOplusAPIError(f"Token request HTTP {response.status}: {error_text}")
                    
        except asyncio.TimeoutError:
            raise GOplusAPIError("Token request timeout")
        except aiohttp.ClientError as e:
            raise GOplusAPIError(f"Token request error: {str(e)}")
    
    async def _request_with_token(self, method: str, endpoint: str, app_key: str, app_secret: str, service_name: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with bearer token authentication"""
        if not app_key or not app_secret:
            raise GOplusAPIError(f"GOplus APP key and secret not configured for {service_name}")
        
        await self._ensure_session()
        await self._rate_limit()
        
        # Get access token
        access_token = await self._get_access_token(app_key, app_secret, service_name)
        
        url = f"{self.base_url}{endpoint}"
        params = kwargs.pop("params", {})
        json_data = kwargs.pop("json", None)
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
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
                            if error_code != 1:  # 1 means success in GOplus
                                error_msg = response_data.get('message', 'Unknown API error')
                                logger.error(f"GOplus API error (code {error_code}): {error_msg}")
                                
                                # Handle token expiry
                                if error_code in [4001, 4002]:  # Token expired or invalid
                                    # Clear cached token and retry once
                                    if service_name in self._access_tokens:
                                        del self._access_tokens[service_name]
                                    if service_name in self._token_expiry:
                                        del self._token_expiry[service_name]
                                    
                                    logger.debug(f"Token expired for {service_name}, retrying with new token")
                                    return await self._request_with_token(method, endpoint, app_key, app_secret, service_name, params=params, json=json_data, **kwargs)
                                
                                raise GOplusAPIError(f"API error (code {error_code}): {error_msg}")
                        
                        return response_data
                    else:
                        response_text = await response.text()
                        logger.error(f"Unexpected content type from GOplus: {content_type}")
                        raise GOplusAPIError(f"Expected JSON, got {content_type}")
                
                elif response.status == 401:
                    # Token might be expired, clear cache and retry once
                    if service_name in self._access_tokens:
                        del self._access_tokens[service_name]
                        logger.debug(f"401 error, clearing token cache for {service_name}")
                        return await self._request_with_token(method, endpoint, app_key, app_secret, service_name, params=params, json=json_data, **kwargs)
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
    
    async def analyze_token_security(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Comprehensive token security analysis"""
        try:
            # Map chains to chain IDs for the correct endpoint format
            chain_mapping = {
                "ethereum": "1",
                "eth": "1", 
                "bsc": "56",
                "polygon": "137",
                "solana": "101",
                "sol": "101"
            }
            
            chain_id = chain_mapping.get(chain.lower(), "1")  # Default to Ethereum
            
            # Use the correct API endpoint format from the docs
            endpoint = f"/api/v1/token_security/{chain_id}"
            
            params = {
                "contract_addresses": token_address
            }
            
            response = await self._request_with_token(
                "GET", 
                endpoint, 
                self.security_app_key, 
                self.security_app_secret,
                "security",
                params=params
            )
            
            if response and response.get("result"):
                # GOplus returns results keyed by contract address
                token_results = response["result"].get(token_address.lower()) or response["result"].get(token_address)
                if token_results:
                    return self._parse_security_response(token_results, token_address, chain)
            
            logger.warning(f"No results returned for {token_address} on chain {chain_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing token security for {token_address} with GOplus: {str(e)}")
            return None
    
    def _parse_security_response(self, token_results: Dict[str, Any], token_address: str, chain: str) -> Dict[str, Any]:
        """Parse GOplus security response"""
        security_analysis = {
            "token_address": token_address,
            "chain": chain,
            "security_score": token_results.get("security_score", 0),
            "risk_level": token_results.get("risk_level", "unknown"),
            "is_malicious": token_results.get("is_malicious", False),
            "is_honeypot": token_results.get("is_honeypot", "0") == "1",
            "contract_security": {
                "is_verified": token_results.get("is_verified", "0") == "1",
                "is_proxy": token_results.get("is_proxy", "0") == "1",
                "can_take_back_ownership": token_results.get("can_take_back_ownership", "0") == "1",
                "owner_change_balance": token_results.get("owner_change_balance", "0") == "1",
                "hidden_owner": token_results.get("hidden_owner", "0") == "1",
                "selfdestruct": token_results.get("selfdestruct", "0") == "1",
                "external_call": token_results.get("external_call", "0") == "1"
            },
            "trading_security": {
                "buy_tax": token_results.get("buy_tax"),
                "sell_tax": token_results.get("sell_tax"),
                "is_blacklisted": token_results.get("is_blacklisted", "0") == "1",
                "is_whitelisted": token_results.get("is_whitelisted", "0") == "1",
                "transfer_pausable": token_results.get("transfer_pausable", "0") == "1",
                "trading_cooldown": token_results.get("trading_cooldown", "0") == "1",
                "anti_whale_modifiable": token_results.get("anti_whale_modifiable", "0") == "1"
            },
            "metadata": {
                "token_name": token_results.get("token_name"),
                "token_symbol": token_results.get("token_symbol"),
                "total_supply": token_results.get("total_supply"),
                "decimals": token_results.get("decimals")
            },
            "warnings": self._extract_security_warnings(token_results),
            "last_updated": token_results.get("update_time"),
        }
        
        return security_analysis
    
    def _extract_security_warnings(self, token_results: Dict[str, Any]) -> List[str]:
        """Extract security warnings from token results"""
        warnings = []
        
        if token_results.get("is_honeypot", "0") == "1":
            warnings.append("Token appears to be a honeypot")
        
        if token_results.get("is_malicious", False):
            warnings.append("Token flagged as malicious")
        
        if token_results.get("can_take_back_ownership", "0") == "1":
            warnings.append("Contract owner can take back ownership")
        
        if token_results.get("hidden_owner", "0") == "1":
            warnings.append("Contract has hidden owner")
        
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
            
            chain_id = chain_mapping.get(chain.lower(), "1")  # Default to Ethereum
            endpoint = f"/api/v1/rugpull_detecting/{chain_id}"
            
            params = {
                "contract_addresses": token_address
            }
            
            response = await self._request_with_token(
                "GET",
                endpoint,
                self.rugpull_app_key,
                self.rugpull_app_secret,
                "rugpull",
                params=params
            )
            
            if response and response.get("result"):
                token_results = response["result"].get(token_address.lower()) or response["result"].get(token_address)
                if token_results:
                    return {
                        "token_address": token_address,
                        "chain": chain,
                        "rugpull_risk": token_results.get("rugpull_risk", "unknown"),
                        "risk_score": token_results.get("risk_score", 0),
                        "risk_factors": {
                            "liquidity_locked": token_results.get("liquidity_locked"),
                            "lock_ratio": token_results.get("lock_ratio"),
                            "ownership_renounced": token_results.get("ownership_renounced"),
                            "creator_balance": token_results.get("creator_balance"),
                            "creator_percent": token_results.get("creator_percent"),
                        },
                        "warnings": token_results.get("warnings", []),
                        "last_updated": token_results.get("last_updated")
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting rugpull for {token_address} with GOplus: {str(e)}")
            return None
    
    # ==============================================
    # TRANSACTION SIMULATION API
    # ==============================================
    
    async def simulate_transaction(self, transaction_data: Dict[str, Any], chain: str = "solana") -> Dict[str, Any]:
        """Simulate a transaction before execution"""
        try:
            endpoint = "/api/v1/transaction/simulate"
            payload = {
                "chain": chain,
                "transaction": transaction_data
            }
            
            response = await self._request_with_token(
                "POST",
                endpoint,
                self.transaction_app_key,
                self.transaction_app_secret,
                "transaction",
                json=payload
            )
            
            if response and response.get("result"):
                return response["result"]
            
            return None
            
        except Exception as e:
            logger.error(f"Error simulating transaction with GOplus: {str(e)}")
            return None
    
    # ==============================================
    # SUPPORTED CHAINS
    # ==============================================
    
    async def get_supported_chains(self) -> List[Dict[str, Any]]:
        """Get supported chains"""
        try:
            # Return commonly supported chains based on GOplus documentation
            supported_chains = [
                {"chain_id": "1", "name": "Ethereum", "supported": True},
                {"chain_id": "56", "name": "BSC", "supported": True},
                {"chain_id": "137", "name": "Polygon", "supported": True},
                {"chain_id": "101", "name": "Solana", "supported": True},
                {"chain_id": "43114", "name": "Avalanche", "supported": True}
            ]
            
            logger.debug("Returning common supported chains for GOplus")
            return supported_chains
            
        except Exception as e:
            logger.error(f"Error getting supported chains: {str(e)}")
            return []
    
    # ==============================================
    # COMPREHENSIVE ANALYSIS
    # ==============================================
    
    async def comprehensive_analysis(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Run comprehensive analysis using all available GOplus services"""
        logger.info(f"🔍 Running comprehensive GOplus analysis for {token_address}")
        
        # Run available analyses in parallel
        tasks = {}
        
        if self.security_app_key and self.security_app_secret:
            tasks["security"] = self.analyze_token_security(token_address, chain)
        
        if self.rugpull_app_key and self.rugpull_app_secret:
            tasks["rugpull"] = self.detect_rugpull(token_address, chain)
        
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
        
        risk_scores = []
        all_warnings = []
        
        # Collect data from successful analyses
        for service_name, result in analyses.items():
            if result.get("success") and result.get("data"):
                data = result["data"]
                
                if "risk_score" in data:
                    risk_scores.append(data["risk_score"])
                elif "security_score" in data:
                    risk_scores.append(100 - data["security_score"])
                
                if "warnings" in data:
                    all_warnings.extend(data["warnings"])
                
                if data.get("is_malicious") or data.get("is_honeypot"):
                    overall["major_risks"].append("Token flagged as malicious/honeypot")
        
        # Calculate overall risk score
        if risk_scores:
            overall["risk_score"] = sum(risk_scores) / len(risk_scores)
            overall["confidence"] = len(risk_scores) / len(analyses) * 100
            
            if overall["risk_score"] >= 80:
                overall["risk_level"] = "critical"
                overall["is_safe"] = False
            elif overall["risk_score"] >= 60:
                overall["risk_level"] = "high"
                overall["is_safe"] = False
            elif overall["risk_score"] >= 40:
                overall["risk_level"] = "medium"
                overall["is_safe"] = None
            else:
                overall["risk_level"] = "low"
                overall["is_safe"] = True
        
        return overall
    
    # ==============================================
    # HEALTH CHECK
    # ==============================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check GOplus API services health"""
        try:
            start_time = time.time()
            
            # Check which APP key pairs are configured
            services_status = {
                "transaction_simulation": {
                    "configured": bool(self.transaction_app_key and self.transaction_app_secret),
                    "healthy": False,
                    "error": None
                },
                "rugpull_detection": {
                    "configured": bool(self.rugpull_app_key and self.rugpull_app_secret),
                    "healthy": False,
                    "error": None
                },
                "token_security": {
                    "configured": bool(self.security_app_key and self.security_app_secret),
                    "healthy": False,
                    "error": None
                }
            }
            
            # Test token security service if configured
            if services_status["token_security"]["configured"]:
                try:
                    # Test with the working endpoint and token authentication
                    test_result = await self.analyze_token_security("0xA0b86a33E6411E1e2d088c4dDfC1B8F31Efa6a95", "ethereum")
                    services_status["token_security"]["healthy"] = test_result is not None
                    if test_result is None:
                        services_status["token_security"]["error"] = "No data returned for test token"
                    else:
                        services_status["token_security"]["note"] = "Successfully tested with Ethereum token"
                        
                except Exception as e:
                    error_msg = str(e)
                    services_status["token_security"]["error"] = error_msg
                    
                    # Check for specific error types
                    if "token request failed" in error_msg.lower():
                        services_status["token_security"]["error"] = "Failed to get access token - check API key and secret"
                    elif "invalid credentials" in error_msg.lower():
                        services_status["token_security"]["error"] = "Invalid API credentials"
            
            # For other services, mark as healthy if configured (to avoid extra API calls)
            for service in ["transaction_simulation", "rugpull_detection"]:
                if services_status[service]["configured"]:
                    services_status[service]["healthy"] = True
                    services_status[service]["note"] = "APP keys configured (not tested to avoid charges)"
            
            response_time = time.time() - start_time
            
            # Overall health
            configured_services = sum(1 for status in services_status.values() if status["configured"])
            healthy_services = sum(1 for status in services_status.values() if status["healthy"])
            
            return {
                "healthy": healthy_services > 0,
                "services": services_status,
                "summary": {
                    "configured_services": configured_services,
                    "healthy_services": healthy_services,
                    "total_services": 3
                },
                "base_url": self.base_url,
                "response_time": response_time,
                "recommendations": self._get_health_recommendations(services_status)
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "base_url": self.base_url,
                "services": {
                    "transaction_simulation": {"configured": bool(self.transaction_app_key and self.transaction_app_secret), "healthy": False},
                    "rugpull_detection": {"configured": bool(self.rugpull_app_key and self.rugpull_app_secret), "healthy": False},
                    "token_security": {"configured": bool(self.security_app_key and self.security_app_secret), "healthy": False}
                }
            }
    
    def _get_health_recommendations(self, services_status: Dict[str, Any]) -> List[str]:
        """Generate health check recommendations"""
        recommendations = []
        
        unconfigured_services = [
            service for service, status in services_status.items() 
            if not status["configured"]
        ]
        
        if unconfigured_services:
            recommendations.append(
                f"Configure APP key pairs for: {', '.join(unconfigured_services)}"
            )
            recommendations.append(
                "Each service needs both APP_KEY and APP_SECRET"
            )
        
        if not any(status["configured"] for status in services_status.values()):
            recommendations.append("Get GOplus APP keys from https://gopluslabs.io/")
        
        return recommendations


# Convenience functions
async def get_goplus_client() -> GOplusClient:
    """Get configured GOplus client"""
    return GOplusClient()


async def check_goplus_health() -> Dict[str, Any]:
    """Check GOplus service health"""
    async with GOplusClient() as client:
        return await client.health_check()