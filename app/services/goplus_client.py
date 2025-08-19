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
        # GOplus uses 3 different API keys for different services
        self.transaction_api_key = settings.GOPLUS_TRANSACTION_API_KEY
        self.rugpull_api_key = settings.GOPLUS_RUGPULL_API_KEY
        self.security_api_key = settings.GOPLUS_SECURITY_API_KEY
        
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
            "transaction": bool(self.transaction_api_key),
            "rugpull": bool(self.rugpull_api_key),
            "security": bool(self.security_api_key)
        }
        
        configured_count = sum(keys_status.values())
        logger.debug(f"GOplus API keys configured: {configured_count}/3 ({keys_status})")
        
        if configured_count < 3:
            missing_keys = [service for service, configured in keys_status.items() if not configured]
            logger.warning(f"GOplus missing API keys: {missing_keys}")
    
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
    
    async def _request(self, method: str, endpoint: str, api_key: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling and rate limiting"""
        if not api_key:
            raise GOplusAPIError("GOplus API key not configured for this service")
        
        await self._ensure_session()
        await self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Solana-Token-Analysis/1.0",
            **kwargs.pop("headers", {})
        }
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                content_type = response.headers.get('content-type', '').lower()
                
                logger.debug(f"GOplus {method} {endpoint} - Status: {response.status}, Content-Type: {content_type}")
                
                if response.status == 200:
                    if 'application/json' in content_type:
                        response_data = await response.json()
                        
                        # Check for GOplus API-level errors
                        if isinstance(response_data, dict):
                            if response_data.get('code') != 1 and 'code' in response_data:
                                error_msg = response_data.get('message') or 'Unknown API error'
                                logger.error(f"GOplus API error (code {response_data.get('code')}): {error_msg}")
                                raise GOplusAPIError(f"API error (code {response_data.get('code')}): {error_msg}")
                        
                        return response_data
                    else:
                        response_text = await response.text()
                        logger.error(f"Unexpected content type from GOplus: {content_type}")
                        raise GOplusAPIError(f"Expected JSON, got {content_type}. Response: {response_text[:200]}")
                        
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"GOplus rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, api_key, **kwargs)
                elif response.status == 401:
                    raise GOplusAPIError("Invalid GOplus API key")
                elif response.status == 403:
                    raise GOplusAPIError("GOplus API access forbidden - check API key permissions")
                else:
                    try:
                        error_text = await response.text()
                        raise GOplusAPIError(f"HTTP {response.status}: {error_text[:200]}")
                    except:
                        raise GOplusAPIError(f"HTTP {response.status}: Unknown error")
                    
        except asyncio.TimeoutError:
            raise GOplusAPIError("GOplus API request timeout")
        except aiohttp.ClientError as e:
            raise GOplusAPIError(f"GOplus client error: {str(e)}")
    
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
            
            response = await self._request("POST", endpoint, self.transaction_api_key, json=payload)
            
            if not response.get("result"):
                return None
            
            result = response["result"]
            simulation = {
                "chain": chain,
                "simulation_id": result.get("simulation_id"),
                "success": result.get("success", False),
                "gas_used": result.get("gas_used"),
                "gas_limit": result.get("gas_limit"),
                "gas_price": result.get("gas_price"),
                "transaction_fee": result.get("transaction_fee"),
                "balance_changes": result.get("balance_changes", []),
                "token_transfers": result.get("token_transfers", []),
                "events": result.get("events", []),
                "error_message": result.get("error_message"),
                "warnings": result.get("warnings", []),
                "risk_score": result.get("risk_score"),
                "risk_level": result.get("risk_level"),
                "simulation_time": result.get("simulation_time"),
                "timestamp": result.get("timestamp")
            }
            
            return simulation
            
        except Exception as e:
            logger.error(f"Error simulating transaction with GOplus: {str(e)}")
            return None
    
    async def validate_transaction(self, transaction_hash: str, chain: str = "solana") -> Dict[str, Any]:
        """Validate an existing transaction"""
        try:
            endpoint = f"/v1/transaction/validate"
            params = {
                "chain": chain,
                "tx_hash": transaction_hash
            }
            
            response = await self._request("GET", endpoint, self.transaction_api_key, params=params)
            
            if not response.get("result"):
                return None
            
            result = response["result"]
            validation = {
                "transaction_hash": transaction_hash,
                "chain": chain,
                "is_valid": result.get("is_valid", False),
                "status": result.get("status"),
                "block_number": result.get("block_number"),
                "confirmations": result.get("confirmations"),
                "gas_used": result.get("gas_used"),
                "transaction_fee": result.get("transaction_fee"),
                "from_address": result.get("from_address"),
                "to_address": result.get("to_address"),
                "value": result.get("value"),
                "timestamp": result.get("timestamp"),
                "risk_assessment": result.get("risk_assessment", {}),
                "security_flags": result.get("security_flags", [])
            }
            
            return validation
            
        except Exception as e:
            logger.error(f"Error validating transaction {transaction_hash} with GOplus: {str(e)}")
            return None
    
    # ==============================================
    # RUG PULL DETECTION API
    # ==============================================
    
    async def detect_rugpull(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Detect rug pull risks for a token"""
        try:
            endpoint = "/v1/rugpull_detecting"
            params = {
                "chain_id": "101" if chain == "solana" else chain,  # Solana mainnet chain ID
                "contract_addresses": token_address
            }
            
            response = await self._request("GET", endpoint, self.rugpull_api_key, params=params)
            
            if not response.get("result"):
                return None
            
            # GOplus rugpull API returns results keyed by contract address
            token_results = response["result"].get(token_address.lower())
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
                    "lock_time": token_results.get("lock_time"),
                    "ownership_renounced": token_results.get("ownership_renounced"),
                    "creator_balance": token_results.get("creator_balance"),
                    "creator_percent": token_results.get("creator_percent"),
                    "top_holders": token_results.get("top_holders", []),
                    "holder_concentration": token_results.get("holder_concentration"),
                    "trading_volume": token_results.get("trading_volume"),
                    "price_volatility": token_results.get("price_volatility"),
                    "suspicious_transactions": token_results.get("suspicious_transactions", [])
                },
                "warnings": token_results.get("warnings", []),
                "recommendations": token_results.get("recommendations", []),
                "last_updated": token_results.get("last_updated"),
                "data_sources": token_results.get("data_sources", [])
            }
            
            return rugpull_analysis
            
        except Exception as e:
            logger.error(f"Error detecting rugpull for {token_address} with GOplus: {str(e)}")
            return None
    
    async def get_rugpull_history(self, token_address: str, chain: str = "solana", days: int = 30) -> List[Dict[str, Any]]:
        """Get historical rugpull risk data for a token"""
        try:
            endpoint = "/v1/rugpull_history"
            params = {
                "chain_id": "101" if chain == "solana" else chain,
                "contract_address": token_address,
                "days": min(days, 365)  # Limit to 1 year
            }
            
            response = await self._request("GET", endpoint, self.rugpull_api_key, params=params)
            
            if not response.get("result") or not response["result"].get("history"):
                return []
            
            history = []
            for entry in response["result"]["history"]:
                history_item = {
                    "timestamp": entry.get("timestamp"),
                    "risk_score": entry.get("risk_score"),
                    "risk_level": entry.get("risk_level"),
                    "liquidity_change": entry.get("liquidity_change"),
                    "holder_change": entry.get("holder_change"),
                    "significant_events": entry.get("significant_events", [])
                }
                history.append(history_item)
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting rugpull history for {token_address}: {str(e)}")
            return []
    
    # ==============================================
    # TOKEN SECURITY API
    # ==============================================
    
    async def analyze_token_security(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Comprehensive token security analysis"""
        try:
            endpoint = "/v1/token_security"
            params = {
                "chain_id": "101" if chain == "solana" else chain,
                "contract_addresses": token_address
            }
            
            response = await self._request("GET", endpoint, self.security_api_key, params=params)
            
            if not response.get("result"):
                return None
            
            # GOplus security API returns results keyed by contract address
            token_results = response["result"].get(token_address.lower())
            if not token_results:
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
                "liquidity_security": {
                    "dex": token_results.get("dex", []),
                    "liquidity": token_results.get("liquidity"),
                    "liquidity_locked": token_results.get("liquidity_locked", "0") == "1",
                    "lock_ratio": token_results.get("lock_ratio"),
                    "unlock_time": token_results.get("unlock_time")
                },
                "holder_analysis": {
                    "holder_count": token_results.get("holder_count"),
                    "creator_address": token_results.get("creator_address"),
                    "creator_balance": token_results.get("creator_balance"),
                    "creator_percent": token_results.get("creator_percent"),
                    "top_10_holders": token_results.get("top_10_holders", []),
                    "concentration_risk": self._calculate_concentration_risk(token_results)
                },
                "metadata": {
                    "token_name": token_results.get("token_name"),
                    "token_symbol": token_results.get("token_symbol"),
                    "total_supply": token_results.get("total_supply"),
                    "decimals": token_results.get("decimals")
                },
                "warnings": self._extract_security_warnings(token_results),
                "recommendations": self._generate_security_recommendations(token_results),
                "last_updated": token_results.get("update_time"),
                "data_freshness": self._calculate_data_freshness(token_results.get("update_time"))
            }
            
            return security_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing token security for {token_address} with GOplus: {str(e)}")
            return None
    
    def _calculate_concentration_risk(self, token_results: Dict[str, Any]) -> str:
        """Calculate holder concentration risk"""
        try:
            creator_percent = float(token_results.get("creator_percent", 0))
            if creator_percent > 50:
                return "very_high"
            elif creator_percent > 30:
                return "high"
            elif creator_percent > 15:
                return "medium"
            else:
                return "low"
        except:
            return "unknown"
    
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
        
        if token_results.get("selfdestruct", "0") == "1":
            warnings.append("Contract can self-destruct")
        
        if float(token_results.get("creator_percent", 0)) > 50:
            warnings.append("Creator holds majority of tokens")
        
        if token_results.get("transfer_pausable", "0") == "1":
            warnings.append("Token transfers can be paused")
        
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
    
    def _generate_security_recommendations(self, token_results: Dict[str, Any]) -> List[str]:
        """Generate security recommendations"""
        recommendations = []
        
        if token_results.get("is_verified", "0") == "0":
            recommendations.append("Verify contract source code before investing")
        
        if token_results.get("liquidity_locked", "0") == "0":
            recommendations.append("Check if liquidity is locked to prevent rug pulls")
        
        if float(token_results.get("creator_percent", 0)) > 30:
            recommendations.append("Be cautious of high creator token concentration")
        
        if not token_results.get("dex"):
            recommendations.append("Token not listed on major DEXs - exercise caution")
        
        return recommendations
    
    def _calculate_data_freshness(self, update_time: str) -> str:
        """Calculate how fresh the data is"""
        if not update_time:
            return "unknown"
        
        try:
            from datetime import datetime
            update_dt = datetime.fromisoformat(update_time.replace('Z', '+00:00'))
            now = datetime.now(update_dt.tzinfo)
            diff = now - update_dt
            
            if diff.total_seconds() < 3600:  # 1 hour
                return "fresh"
            elif diff.total_seconds() < 86400:  # 24 hours
                return "recent"
            elif diff.total_seconds() < 604800:  # 7 days
                return "stale"
            else:
                return "outdated"
        except:
            return "unknown"
    
    async def get_supported_chains(self) -> List[Dict[str, Any]]:
        """Get list of supported blockchain networks"""
        try:
            endpoint = "/v1/supported_chains"
            response = await self._request("GET", endpoint, self.security_api_key)
            
            if response.get("result"):
                return response["result"].get("chains", [])
            
            return []
            
        except Exception as e:
            logger.warning(f"Error getting supported chains from GOplus: {str(e)}")
            return []
    
    # ==============================================
    # COMPREHENSIVE ANALYSIS
    # ==============================================
    
    async def comprehensive_analysis(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Run comprehensive analysis using all GOplus services"""
        logger.info(f"🔍 Running comprehensive GOplus analysis for {token_address}")
        
        # Run all analyses in parallel
        tasks = {}
        
        if self.security_api_key:
            tasks["security"] = self.analyze_token_security(token_address, chain)
        
        if self.rugpull_api_key:
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
        all_recommendations = []
        
        # Collect data from successful analyses
        for service_name, result in analyses.items():
            if result.get("success") and result.get("data"):
                data = result["data"]
                
                # Extract risk scores
                if "risk_score" in data:
                    risk_scores.append(data["risk_score"])
                elif "security_score" in data:
                    risk_scores.append(100 - data["security_score"])  # Invert security score
                
                # Extract warnings and recommendations
                if "warnings" in data:
                    all_warnings.extend(data["warnings"])
                if "recommendations" in data:
                    all_recommendations.extend(data["recommendations"])
                
                # Check for critical flags
                if data.get("is_malicious") or data.get("is_honeypot"):
                    overall["major_risks"].append("Token flagged as malicious/honeypot")
                
                if service_name == "rugpull" and data.get("rugpull_risk") == "high":
                    overall["major_risks"].append("High rugpull risk detected")
        
        # Calculate overall risk score
        if risk_scores:
            overall["risk_score"] = sum(risk_scores) / len(risk_scores)
            overall["confidence"] = len(risk_scores) / len(analyses) * 100
            
            # Determine risk level
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
        
        # Consolidate recommendations
        overall["recommendations"] = list(set(all_recommendations))[:10]  # Top 10 unique
        
        return overall
    
    # ==============================================
    # HEALTH CHECK
    # ==============================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check GOplus API services health"""
        try:
            start_time = time.time()
            
            # Check which API keys are configured
            services_status = {
                "transaction_simulation": {
                    "configured": bool(self.transaction_api_key),
                    "healthy": False,
                    "error": None
                },
                "rugpull_detection": {
                    "configured": bool(self.rugpull_api_key),
                    "healthy": False,
                    "error": None
                },
                "token_security": {
                    "configured": bool(self.security_api_key),
                    "healthy": False,
                    "error": None
                }
            }
            
            # Test each configured service
            if self.security_api_key:
                try:
                    chains = await self.get_supported_chains()
                    services_status["token_security"]["healthy"] = True
                    services_status["token_security"]["chains_count"] = len(chains)
                except Exception as e:
                    services_status["token_security"]["error"] = str(e)
            
            # For other services, we'd need a test endpoint or a known test address
            # Since we don't want to waste API calls, we'll just check if keys are configured
            if self.transaction_api_key:
                services_status["transaction_simulation"]["healthy"] = True
                services_status["transaction_simulation"]["note"] = "API key configured (not tested to avoid charges)"
            
            if self.rugpull_api_key:
                services_status["rugpull_detection"]["healthy"] = True
                services_status["rugpull_detection"]["note"] = "API key configured (not tested to avoid charges)"
            
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
                    "transaction_simulation": {"configured": bool(self.transaction_api_key), "healthy": False},
                    "rugpull_detection": {"configured": bool(self.rugpull_api_key), "healthy": False},
                    "token_security": {"configured": bool(self.security_api_key), "healthy": False}
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
                f"Configure API keys for: {', '.join(unconfigured_services)}"
            )
        
        unhealthy_services = [
            service for service, status in services_status.items()
            if status["configured"] and not status["healthy"]
        ]
        
        if unhealthy_services:
            recommendations.append(
                f"Check API connectivity for: {', '.join(unhealthy_services)}"
            )
        
        if not any(status["configured"] for status in services_status.values()):
            recommendations.append("Get GOplus API keys from https://gopluslabs.io/")
        
        return recommendations


# Convenience functions
async def get_goplus_client() -> GOplusClient:
    """Get configured GOplus client"""
    return GOplusClient()


async def check_goplus_health() -> Dict[str, Any]:
    """Check GOplus service health"""
    async with GOplusClient() as client:
        return await client.health_check()