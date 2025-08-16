import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class BlowfishAPIError(Exception):
    """Blowfish API specific errors"""
    pass


class BlowfishClient:
    """Blowfish API client for token security analysis and smart contract vulnerability detection"""
    
    def __init__(self):
        self.api_key = settings.BLOWFISH_API_KEY
        self.base_url = settings.BLOWFISH_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.3  # 300ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        if not self.api_key:
            logger.warning("Blowfish API key not configured")
    
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
            raise BlowfishAPIError("Blowfish API key not configured")
        
        await self._ensure_session()
        await self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **kwargs.pop("headers", {})
        }
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                response_data = await response.json()
                
                if response.status == 200:
                    return response_data
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"Blowfish rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                elif response.status == 401:
                    raise BlowfishAPIError("Invalid Blowfish API key")
                else:
                    error_msg = response_data.get('message', f'HTTP {response.status}')
                    raise BlowfishAPIError(f"Blowfish API error: {error_msg}")
                    
        except asyncio.TimeoutError:
            raise BlowfishAPIError("Blowfish API request timeout")
        except aiohttp.ClientError as e:
            raise BlowfishAPIError(f"Blowfish client error: {str(e)}")
    
    async def scan_token(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Comprehensive token security scan"""
        try:
            endpoint = f"/v1/scan/token"
            payload = {
                "address": token_address,
                "chain": chain
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            scan_result = {
                "token_address": token_address,
                "chain": chain,
                "risk_score": data.get("risk_score"),  # 0-100, higher = more risky
                "risk_level": data.get("risk_level"),  # low, medium, high, critical
                "is_scam": data.get("is_scam", False),
                "is_honeypot": data.get("is_honeypot", False),
                "is_rugpull": data.get("is_rugpull", False),
                "security_flags": data.get("security_flags", []),
                "warnings": data.get("warnings", []),
                "contract_analysis": data.get("contract_analysis", {}),
                "liquidity_analysis": data.get("liquidity_analysis", {}),
                "holder_analysis": data.get("holder_analysis", {}),
                "trading_analysis": data.get("trading_analysis", {}),
                "metadata_analysis": data.get("metadata_analysis", {}),
                "social_analysis": data.get("social_analysis", {}),
                "scan_timestamp": data.get("scan_timestamp"),
                "confidence": data.get("confidence")
            }
            
            return scan_result
            
        except Exception as e:
            logger.error(f"Error scanning token {token_address} with Blowfish: {str(e)}")
            return None
    
    async def analyze_transaction(self, transaction_hash: str, chain: str = "solana") -> Dict[str, Any]:
        """Analyze a specific transaction for security risks"""
        try:
            endpoint = f"/v1/scan/transaction"
            payload = {
                "transaction_hash": transaction_hash,
                "chain": chain
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            analysis = {
                "transaction_hash": transaction_hash,
                "chain": chain,
                "risk_score": data.get("risk_score"),
                "risk_level": data.get("risk_level"),
                "is_malicious": data.get("is_malicious", False),
                "transaction_type": data.get("transaction_type"),
                "security_flags": data.get("security_flags", []),
                "warnings": data.get("warnings", []),
                "involved_addresses": data.get("involved_addresses", []),
                "token_interactions": data.get("token_interactions", []),
                "value_at_risk": data.get("value_at_risk"),
                "analysis_details": data.get("analysis_details", {}),
                "recommendations": data.get("recommendations", []),
                "scan_timestamp": data.get("scan_timestamp")
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing transaction {transaction_hash} with Blowfish: {str(e)}")
            return None
    
    async def analyze_smart_contract(self, contract_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Deep analysis of smart contract for vulnerabilities"""
        try:
            endpoint = f"/v1/scan/contract"
            payload = {
                "address": contract_address,
                "chain": chain,
                "deep_scan": True
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            contract_analysis = {
                "contract_address": contract_address,
                "chain": chain,
                "risk_score": data.get("risk_score"),
                "risk_level": data.get("risk_level"),
                "is_verified": data.get("is_verified", False),
                "is_proxy": data.get("is_proxy", False),
                "vulnerabilities": data.get("vulnerabilities", []),
                "security_flags": data.get("security_flags", []),
                "code_analysis": {
                    "has_mint_function": data.get("code_analysis", {}).get("has_mint_function"),
                    "has_burn_function": data.get("code_analysis", {}).get("has_burn_function"),
                    "has_pause_function": data.get("code_analysis", {}).get("has_pause_function"),
                    "has_blacklist_function": data.get("code_analysis", {}).get("has_blacklist_function"),
                    "has_ownership_renounced": data.get("code_analysis", {}).get("has_ownership_renounced"),
                    "has_liquidity_lock": data.get("code_analysis", {}).get("has_liquidity_lock"),
                    "has_anti_whale": data.get("code_analysis", {}).get("has_anti_whale"),
                    "has_reflection": data.get("code_analysis", {}).get("has_reflection"),
                    "has_fee_modification": data.get("code_analysis", {}).get("has_fee_modification")
                },
                "ownership_analysis": data.get("ownership_analysis", {}),
                "proxy_analysis": data.get("proxy_analysis", {}),
                "function_analysis": data.get("function_analysis", []),
                "event_analysis": data.get("event_analysis", []),
                "recommendations": data.get("recommendations", []),
                "scan_timestamp": data.get("scan_timestamp")
            }
            
            return contract_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing smart contract {contract_address} with Blowfish: {str(e)}")
            return None
    
    async def check_wallet_reputation(self, wallet_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Check wallet reputation and risk profile"""
        try:
            endpoint = f"/v1/scan/wallet"
            payload = {
                "address": wallet_address,
                "chain": chain
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            reputation = {
                "wallet_address": wallet_address,
                "chain": chain,
                "risk_score": data.get("risk_score"),
                "risk_level": data.get("risk_level"),
                "is_blacklisted": data.get("is_blacklisted", False),
                "is_suspicious": data.get("is_suspicious", False),
                "reputation_score": data.get("reputation_score"),
                "labels": data.get("labels", []),
                "activity_analysis": {
                    "transaction_count": data.get("activity_analysis", {}).get("transaction_count"),
                    "total_volume": data.get("activity_analysis", {}).get("total_volume"),
                    "first_seen": data.get("activity_analysis", {}).get("first_seen"),
                    "last_seen": data.get("activity_analysis", {}).get("last_seen"),
                    "interaction_patterns": data.get("activity_analysis", {}).get("interaction_patterns", [])
                },
                "security_flags": data.get("security_flags", []),
                "associated_risks": data.get("associated_risks", []),
                "known_associations": data.get("known_associations", []),
                "scan_timestamp": data.get("scan_timestamp")
            }
            
            return reputation
            
        except Exception as e:
            logger.error(f"Error checking wallet reputation for {wallet_address} with Blowfish: {str(e)}")
            return None
    
    async def bulk_scan_tokens(self, token_addresses: List[str], chain: str = "solana") -> Dict[str, Dict[str, Any]]:
        """Bulk scan multiple tokens for efficiency"""
        try:
            endpoint = f"/v1/scan/tokens/bulk"
            payload = {
                "addresses": token_addresses[:50],  # Limit to 50 tokens per request
                "chain": chain
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data"):
                return {}
            
            results = {}
            for address, scan_data in response["data"].items():
                results[address] = {
                    "risk_score": scan_data.get("risk_score"),
                    "risk_level": scan_data.get("risk_level"),
                    "is_scam": scan_data.get("is_scam", False),
                    "is_honeypot": scan_data.get("is_honeypot", False),
                    "security_flags": scan_data.get("security_flags", []),
                    "warnings": scan_data.get("warnings", []),
                    "scan_timestamp": scan_data.get("scan_timestamp")
                }
            
            return results
            
        except Exception as e:
            logger.error(f"Error bulk scanning tokens with Blowfish: {str(e)}")
            return {}
    
    async def get_risk_indicators(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Get detailed risk indicators for a token"""
        try:
            endpoint = f"/v1/risk/indicators"
            params = {
                "address": token_address,
                "chain": chain
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            indicators = {
                "token_address": token_address,
                "chain": chain,
                "liquidity_risk": {
                    "score": data.get("liquidity_risk", {}).get("score"),
                    "locked_percentage": data.get("liquidity_risk", {}).get("locked_percentage"),
                    "lock_duration": data.get("liquidity_risk", {}).get("lock_duration"),
                    "can_remove_liquidity": data.get("liquidity_risk", {}).get("can_remove_liquidity")
                },
                "ownership_risk": {
                    "score": data.get("ownership_risk", {}).get("score"),
                    "owner_percentage": data.get("ownership_risk", {}).get("owner_percentage"),
                    "can_mint": data.get("ownership_risk", {}).get("can_mint"),
                    "can_pause": data.get("ownership_risk", {}).get("can_pause"),
                    "ownership_renounced": data.get("ownership_risk", {}).get("ownership_renounced")
                },
                "trading_risk": {
                    "score": data.get("trading_risk", {}).get("score"),
                    "can_blacklist": data.get("trading_risk", {}).get("can_blacklist"),
                    "has_trading_cooldown": data.get("trading_risk", {}).get("has_trading_cooldown"),
                    "has_max_transaction": data.get("trading_risk", {}).get("has_max_transaction"),
                    "buy_tax": data.get("trading_risk", {}).get("buy_tax"),
                    "sell_tax": data.get("trading_risk", {}).get("sell_tax")
                },
                "holder_risk": {
                    "score": data.get("holder_risk", {}).get("score"),
                    "concentration": data.get("holder_risk", {}).get("concentration"),
                    "whale_percentage": data.get("holder_risk", {}).get("whale_percentage"),
                    "suspicious_holders": data.get("holder_risk", {}).get("suspicious_holders", [])
                },
                "market_risk": {
                    "score": data.get("market_risk", {}).get("score"),
                    "volume_anomalies": data.get("market_risk", {}).get("volume_anomalies"),
                    "price_manipulation": data.get("market_risk", {}).get("price_manipulation"),
                    "wash_trading": data.get("market_risk", {}).get("wash_trading")
                }
            }
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error getting risk indicators for {token_address} with Blowfish: {str(e)}")
            return None
    
    async def simulate_transaction(self, transaction_data: Dict[str, Any], chain: str = "solana") -> Dict[str, Any]:
        """Simulate a transaction before execution to check for risks"""
        try:
            endpoint = f"/v1/simulate/transaction"
            payload = {
                "transaction": transaction_data,
                "chain": chain
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            simulation = {
                "simulation_id": data.get("simulation_id"),
                "success": data.get("success", False),
                "risk_score": data.get("risk_score"),
                "risk_level": data.get("risk_level"),
                "warnings": data.get("warnings", []),
                "expected_effects": data.get("expected_effects", []),
                "value_changes": data.get("value_changes", []),
                "token_flows": data.get("token_flows", []),
                "gas_estimate": data.get("gas_estimate"),
                "potential_losses": data.get("potential_losses", []),
                "recommendations": data.get("recommendations", []),
                "simulation_timestamp": data.get("simulation_timestamp")
            }
            
            return simulation
            
        except Exception as e:
            logger.error(f"Error simulating transaction with Blowfish: {str(e)}")
            return None
    
    async def get_security_report(self, token_address: str, chain: str = "solana") -> Dict[str, Any]:
        """Generate comprehensive security report"""
        try:
            # Combine multiple security checks
            token_scan = await self.scan_token(token_address, chain)
            contract_analysis = await self.analyze_smart_contract(token_address, chain)
            risk_indicators = await self.get_risk_indicators(token_address, chain)
            
            if not any([token_scan, contract_analysis, risk_indicators]):
                return None
            
            # Compile comprehensive report
            report = {
                "token_address": token_address,
                "chain": chain,
                "overall_risk_score": 0,
                "overall_risk_level": "unknown",
                "is_safe": True,
                "critical_issues": [],
                "warnings": [],
                "recommendations": [],
                "detailed_analysis": {
                    "token_scan": token_scan,
                    "contract_analysis": contract_analysis,
                    "risk_indicators": risk_indicators
                },
                "report_timestamp": int(time.time())
            }
            
            # Calculate overall risk score
            risk_scores = []
            if token_scan and token_scan.get("risk_score") is not None:
                risk_scores.append(token_scan["risk_score"])
            if contract_analysis and contract_analysis.get("risk_score") is not None:
                risk_scores.append(contract_analysis["risk_score"])
            
            if risk_scores:
                report["overall_risk_score"] = sum(risk_scores) / len(risk_scores)
                
                # Determine risk level
                if report["overall_risk_score"] >= 80:
                    report["overall_risk_level"] = "critical"
                    report["is_safe"] = False
                elif report["overall_risk_score"] >= 60:
                    report["overall_risk_level"] = "high"
                    report["is_safe"] = False
                elif report["overall_risk_score"] >= 40:
                    report["overall_risk_level"] = "medium"
                else:
                    report["overall_risk_level"] = "low"
            
            # Collect critical issues
            if token_scan:
                if token_scan.get("is_scam"):
                    report["critical_issues"].append("Token identified as scam")
                    report["is_safe"] = False
                if token_scan.get("is_honeypot"):
                    report["critical_issues"].append("Token appears to be honeypot")
                    report["is_safe"] = False
                if token_scan.get("is_rugpull"):
                    report["critical_issues"].append("Rugpull risk detected")
                    report["is_safe"] = False
            
            # Collect warnings and recommendations
            for analysis in [token_scan, contract_analysis]:
                if analysis:
                    report["warnings"].extend(analysis.get("warnings", []))
                    report["recommendations"].extend(analysis.get("recommendations", []))
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating security report for {token_address} with Blowfish: {str(e)}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Blowfish API health"""
        try:
            start_time = time.time()
            
            # Simple API test
            endpoint = "/v1/health"
            response = await self._request("GET", endpoint)
            
            response_time = time.time() - start_time
            
            return {
                "healthy": True,
                "api_key_configured": bool(self.api_key),
                "base_url": self.base_url,
                "response_time": response_time,
                "status": response.get("status", "unknown")
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": str(e),
                "base_url": self.base_url
            }


# Convenience functions
async def get_blowfish_client() -> BlowfishClient:
    """Get configured Blowfish client"""
    return BlowfishClient()


async def check_blowfish_health() -> Dict[str, Any]:
    """Check Blowfish service health"""
    async with BlowfishClient() as client:
        return await client.health_check()