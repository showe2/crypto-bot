import asyncio
import aiohttp
import time
import hmac
import hashlib
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
    
    def _generate_signature(self, app_secret: str, method: str, endpoint: str, params: Dict[str, Any] = None, body: str = None) -> Dict[str, str]:
        """Generate GOplus API signature"""
        timestamp = str(int(time.time()))
        
        # Create signature string
        # Common pattern: METHOD + endpoint + params + timestamp + body
        signature_parts = [method.upper(), endpoint]
        
        # Add sorted query parameters
        if params:
            param_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
            signature_parts.append(param_string)
        
        signature_parts.append(timestamp)
        
        # Add body if present
        if body:
            signature_parts.append(body)
        
        # Create signature string
        signature_string = "|".join(signature_parts)
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            app_secret.encode('utf-8'),
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "timestamp": timestamp,
            "signature": signature,
            "signature_string": signature_string  # For debugging
        }
    
    async def _request(self, method: str, endpoint: str, app_key: str, app_secret: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with GOplus APP Key/Secret authentication"""
        if not app_key or not app_secret:
            raise GOplusAPIError("GOplus APP key and secret not configured for this service")
        
        await self._ensure_session()
        await self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        params = kwargs.pop("params", {})
        json_data = kwargs.pop("json", None)
        
        # Generate signature
        body_string = None
        if json_data:
            import json
            body_string = json.dumps(json_data, sort_keys=True, separators=(',', ':'))
        
        auth_data = self._generate_signature(
            app_secret=app_secret,
            method=method,
            endpoint=endpoint,
            params=params,
            body=body_string
        )
        
        # GOplus authentication methods to try
        auth_methods = [
            # Method 1: Headers with signature
            {
                "headers": {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Solana-Token-Analysis/1.0",
                    "X-API-Key": app_key,
                    "X-Timestamp": auth_data["timestamp"],
                    "X-Signature": auth_data["signature"],
                    **kwargs.pop("headers", {})
                },
                "params": params
            },
            # Method 2: All in query parameters
            {
                "headers": {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Solana-Token-Analysis/1.0",
                    **kwargs.pop("headers", {})
                },
                "params": {
                    **params,
                    "app_key": app_key,
                    "timestamp": auth_data["timestamp"],
                    "signature": auth_data["signature"]
                }
            },
            # Method 3: Simple API key only
            {
                "headers": {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Solana-Token-Analysis/1.0",
                    "Authorization": f"Bearer {app_key}",
                    **kwargs.pop("headers", {})
                },
                "params": params
            }
        ]
        
        last_error = None
        
        for i, auth_method in enumerate(auth_methods):
            try:
                logger.debug(f"GOplus auth method {i+1}: {method} {endpoint}")
                
                request_kwargs = {
                    "headers": auth_method["headers"],
                    "params": auth_method["params"],
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
                                if error_code and error_code not in [0, 1]:  # 0 or 1 usually means success
                                    error_msg = response_data.get('message', 'Unknown API error')
                                    logger.error(f"GOplus API error (code {error_code}): {error_msg}")
                                    
                                    if error_code == 4012:
                                        # Signature verification failure - try next auth method
                                        logger.debug(f"Auth method {i+1} failed with signature error, trying next method")
                                        last_error = f"Signature verification failed with method {i+1}"
                                        continue
                                    else:
                                        raise GOplusAPIError(f"API error (code {error_code}): {error_msg}")
                            
                            logger.info(f"✅ GOplus auth method {i+1} successful")
                            return response_data
                        else:
                            response_text = await response.text()
                            logger.error(f"Unexpected content type from GOplus: {content_type}")
                            last_error = f"Expected JSON, got {content_type}"
                            continue
                    
                    elif response.status == 401:
                        logger.debug(f"Auth method {i+1}: 401 Unauthorized")
                        last_error = "Invalid credentials"
                        continue
                    elif response.status == 403:
                        logger.debug(f"Auth method {i+1}: 403 Forbidden")
                        last_error = "Access forbidden"
                        continue
                    else:
                        try:
                            error_text = await response.text()
                            last_error = f"HTTP {response.status}: {error_text[:200]}"
                            continue
                        except:
                            last_error = f"HTTP {response.status}: Unknown error"
                            continue
            
            except asyncio.TimeoutError:
                last_error = "Request timeout"
                continue
            except aiohttp.ClientError as e:
                last_error = f"Client error: {str(e)}"
                continue
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                continue
        
        # If we get here, all auth methods failed
        raise GOplusAPIError(f"All authentication methods failed. Last error: {last_error}")
    
    # ==============================================
    # TOKEN SECURITY API
    # ==============================================
    
    async def analyze_token_security(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Comprehensive token security analysis"""
        try:
            endpoint = "/v1/token_security"
            
            # GOplus chain mapping
            chain_mapping = {
                "solana": "101",  # Solana mainnet chain ID
                "ethereum": "1",
                "bsc": "56",
                "polygon": "137"
            }
            
            chain_id = chain_mapping.get(chain.lower(), chain)
            
            params = {
                "chain_id": chain_id,
                "contract_addresses": token_address
            }
            
            response = await self._request(
                "GET", 
                endpoint, 
                self.security_app_key, 
                self.security_app_secret,
                params=params
            )
            
            if not response.get("result"):
                logger.warning(f"GOplus API returned no result for {token_address}")
                return None
            
            # GOplus returns results keyed by contract address
            token_results = response["result"].get(token_address.lower()) or response["result"].get(token_address)
            if not token_results:
                logger.warning(f"No security data for {token_address} in GOplus response")
                return None
            
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
            
        except Exception as e:
            logger.error(f"Error analyzing token security for {token_address} with GOplus: {str(e)}")
            return None
    
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
            endpoint = "/v1/rugpull_detecting"
            
            chain_mapping = {"solana": "101", "ethereum": "1", "bsc": "56", "polygon": "137"}
            chain_id = chain_mapping.get(chain.lower(), chain)
            
            params = {
                "chain_id": chain_id,
                "contract_addresses": token_address
            }
            
            response = await self._request(
                "GET",
                endpoint,
                self.rugpull_app_key,
                self.rugpull_app_secret,
                params=params
            )
            
            if not response.get("result"):
                return None
            
            token_results = response["result"].get(token_address.lower()) or response["result"].get(token_address)
            if not token_results:
                return None
            
            rugpull_analysis = {
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
            
            return rugpull_analysis
            
        except Exception as e:
            logger.error(f"Error detecting rugpull for {token_address} with GOplus: {str(e)}")
            return None
    
    # ==============================================
    # TRANSACTION SIMULATION API
    # ==============================================
    
    async def simulate_transaction(self, transaction_data: Dict[str, Any], chain: str = "solana") -> Dict[str, Any]:
        """Simulate a transaction before execution"""
        try:
            endpoint = "/v1/transaction/simulate"
            payload = {
                "chain": chain,
                "transaction": transaction_data
            }
            
            response = await self._request(
                "POST",
                endpoint,
                self.transaction_app_key,
                self.transaction_app_secret,
                json=payload
            )
            
            if not response.get("result"):
                return None
            
            return response["result"]
            
        except Exception as e:
            logger.error(f"Error simulating transaction with GOplus: {str(e)}")
            return None
    
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
                    # Simple test with a well-known token
                    test_result = await self.analyze_token_security("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")  # USDC
                    services_status["token_security"]["healthy"] = test_result is not None
                    if test_result is None:
                        services_status["token_security"]["error"] = "No data returned for test token"
                except Exception as e:
                    services_status["token_security"]["error"] = str(e)
            
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