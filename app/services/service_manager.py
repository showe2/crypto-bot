import asyncio
import time
from typing import Dict, Any, List, Optional, Union
from loguru import logger

from app.services.helius_client import HeliusClient, check_helius_health
from app.services.chainbase_client import ChainbaseClient, check_chainbase_health
from app.services.birdeye_client import BirdeyeClient, check_birdeye_health
from app.services.blowfish_client import BlowfishClient, check_blowfish_health
from app.services.dataimpulse_client import DataImpulseClient, check_dataimpulse_health
from app.services.solanafm_client import SolanaFMClient, check_solanafm_health
from app.services.goplus_client import GOplusClient, check_goplus_health


class APIManager:
    """Unified API manager for all external services including GOplus"""
    
    def __init__(self):
        self.clients = {
            "helius": None,
            "chainbase": None,
            "birdeye": None,
            "blowfish": None,
            "dataimpulse": None,
            "solanafm": None,
            "goplus": None
        }
        self._health_cache = {}
        self._cache_duration = 300  # 5 minutes
    
    async def initialize_clients(self):
        """Initialize all API clients including GOplus"""
        try:
            self.clients = {
                "helius": HeliusClient(),
                "chainbase": ChainbaseClient(),
                "birdeye": BirdeyeClient(),
                "blowfish": BlowfishClient(),
                "dataimpulse": DataImpulseClient(),
                "solanafm": SolanaFMClient(),
                "goplus": GOplusClient()
            }
            logger.info("✅ All API clients initialized (including GOplus)")
        except Exception as e:
            logger.error(f"❌ Error initializing API clients: {str(e)}")
            raise
    
    async def cleanup_clients(self):
        """Cleanup all API clients"""
        for name, client in self.clients.items():
            if client and hasattr(client, '__aexit__'):
                try:
                    await client.__aexit__(None, None, None)
                    logger.debug(f"✅ {name} client cleaned up")
                except Exception as e:
                    logger.warning(f"⚠️  Error cleaning up {name} client: {str(e)}")
    
    async def check_all_services_health(self) -> Dict[str, Any]:
        """Check health of all API services including GOplus"""
        current_time = time.time()
        
        # Check cache
        if self._health_cache and (current_time - self._health_cache.get('timestamp', 0)) < self._cache_duration:
            return self._health_cache['data']
        
        logger.info("🔍 Checking health of all API services (including GOplus)...")
        
        # Health check functions
        health_checks = {
            "helius": check_helius_health(),
            "chainbase": check_chainbase_health(),
            "birdeye": check_birdeye_health(),
            "blowfish": check_blowfish_health(),
            "dataimpulse": check_dataimpulse_health(),
            "solanafm": check_solanafm_health(),
            "goplus": check_goplus_health()
        }
        
        # Run all health checks concurrently
        results = await asyncio.gather(*health_checks.values(), return_exceptions=True)
        
        # Compile results
        health_status = {}
        service_names = list(health_checks.keys())
        
        for i, service_name in enumerate(service_names):
            result = results[i]
            if isinstance(result, Exception):
                health_status[service_name] = {
                    "healthy": False,
                    "error": str(result),
                    "api_key_configured": False
                }
            else:
                health_status[service_name] = result
        
        # Calculate overall statistics
        total_services = len(health_status)
        healthy_services = sum(1 for status in health_status.values() if status.get("healthy", False))
        configured_services = sum(1 for status in health_status.values() if status.get("api_key_configured", False))
        
        overall_health = {
            "services": health_status,
            "summary": {
                "total_services": total_services,
                "healthy_services": healthy_services,
                "configured_services": configured_services,
                "health_percentage": round((healthy_services / total_services) * 100, 1),
                "configuration_percentage": round((configured_services / total_services) * 100, 1)
            },
            "overall_healthy": healthy_services >= (total_services * 0.6),  # 60% threshold
            "timestamp": current_time,
            "recommendations": []
        }
        
        # Add service-specific recommendations
        if configured_services < total_services:
            missing_keys = [name for name, status in health_status.items() 
                           if not status.get("api_key_configured", False)]
            overall_health["recommendations"].append(
                f"Configure API keys for: {', '.join(missing_keys)}"
            )
        
        if healthy_services < total_services:
            unhealthy = [name for name, status in health_status.items() 
                        if not status.get("healthy", False)]
            overall_health["recommendations"].append(
                f"Check service status for: {', '.join(unhealthy)}"
            )
        
        # GOplus-specific recommendations
        if "goplus" in health_status:
            goplus_status = health_status["goplus"]
            if not goplus_status.get("healthy"):
                if goplus_status.get("services"):
                    services_info = goplus_status["services"]
                    if not services_info.get("configured"):
                        overall_health["recommendations"].append(
                            f"GOplus: Configure API keys for {', '.join(services_info)} services"
                        )
                else:
                    overall_health["recommendations"].append(
                        "GOplus: Get API keys from https://gopluslabs.io/"
                    )
        
        # Cache results
        self._health_cache = {
            "data": overall_health,
            "timestamp": current_time
        }
        
        logger.info(f"📊 Health check completed: {healthy_services}/{total_services} services healthy")
        return overall_health
    
    async def get_comprehensive_token_data(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive token data from all available sources including GOplus"""
        logger.info(f"🔍 Gathering comprehensive data for token: {token_address}")
        
        # Prepare tasks for parallel execution
        tasks = {}
        
        # Basic token information
        if self.clients["helius"]:
            tasks["helius_metadata"] = self.clients["helius"].get_token_metadata(token_address)
            tasks["helius_supply"] = self.clients["helius"].get_token_supply(token_address)
        
        if self.clients["chainbase"]:
            tasks["chainbase_metadata"] = self.clients["chainbase"].get_token_metadata(token_address)
            tasks["chainbase_holders"] = self.clients["chainbase"].get_token_holders(token_address, 100)
            tasks["chainbase_market"] = self.clients["chainbase"].get_market_data(token_address)
        
        if self.clients["birdeye"]:
            tasks["birdeye_price"] = self.clients["birdeye"].get_token_price(token_address)
            tasks["birdeye_metadata"] = self.clients["birdeye"].get_token_metadata(token_address)
            tasks["birdeye_trades"] = self.clients["birdeye"].get_token_trades(token_address, 50)
        
        # SolanaFM data collection (replaces Solscan)
        if self.clients["solanafm"]:
            tasks["solanafm_info"] = self.clients["solanafm"].get_token_info(token_address)
            tasks["solanafm_holders"] = self.clients["solanafm"].get_token_holders(token_address, 50)
        
        # Security analysis
        if self.clients["blowfish"]:
            tasks["blowfish_scan"] = self.clients["blowfish"].scan_token(token_address)
            tasks["blowfish_risks"] = self.clients["blowfish"].get_risk_indicators(token_address)
        
        # GOplus comprehensive analysis
        if self.clients["goplus"]:
            tasks["goplus_comprehensive"] = self.clients["goplus"].comprehensive_analysis(token_address)
            # Individual GOplus services for more detailed data
            tasks["goplus_security"] = self.clients["goplus"].analyze_token_security(token_address)
            tasks["goplus_rugpull"] = self.clients["goplus"].detect_rugpull(token_address)
        
        # Execute all tasks concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        processing_time = time.time() - start_time
        
        # Compile results
        compiled_data = {
            "token_address": token_address,
            "data_sources": [],
            "metadata": {},
            "price_data": {},
            "holder_analysis": {},
            "trading_data": {},
            "security_analysis": {},
            "market_data": {},
            "network_data": {},
            "goplus_analysis": {},  # Dedicated section for GOplus data
            "processing_time": processing_time,
            "timestamp": int(time.time()),
            "errors": []
        }
        
        # Process results
        task_names = list(tasks.keys())
        for i, task_name in enumerate(task_names):
            result = results[i]
            
            if isinstance(result, Exception):
                compiled_data["errors"].append(f"{task_name}: {str(result)}")
                continue
            
            if result is None:
                continue
            
            source = task_name.split("_")[0]
            data_type = "_".join(task_name.split("_")[1:])
            
            if source not in compiled_data["data_sources"]:
                compiled_data["data_sources"].append(source)
            
            # Organize data by type
            if data_type in ["metadata", "info"]:
                compiled_data["metadata"][source] = result
            elif data_type in ["price"]:
                compiled_data["price_data"][source] = result
            elif data_type in ["holders"]:
                compiled_data["holder_analysis"][source] = result
            elif data_type in ["trades", "trading"]:
                compiled_data["trading_data"][source] = result
            elif data_type in ["scan", "risks", "security"]:
                compiled_data["security_analysis"][source] = result
            elif data_type in ["market"]:
                compiled_data["market_data"][source] = result
            elif source == "goplus":
                # Special handling for GOplus data
                compiled_data["goplus_analysis"][data_type] = result
            elif data_type == "supply":
                compiled_data["metadata"][f"{source}_supply"] = result
        
        # Merge and standardize data (now includes GOplus)
        compiled_data["standardized"] = self._standardize_token_data(compiled_data)
        
        logger.info(f"✅ Comprehensive data compiled for {token_address} from {len(compiled_data['data_sources'])} sources in {processing_time:.2f}s")
        return compiled_data
    
    def _standardize_token_data(self, compiled_data: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize token data from different sources including GOplus"""
        standardized = {
            "basic_info": {},
            "price_info": {},
            "holder_info": {},
            "security_info": {},
            "trading_info": {},
            "network_info": {},
            "goplus_summary": {}  # Summary of GOplus analysis
        }
        
        # Standardize basic info (now includes SolanaFM data)
        for source, metadata in compiled_data["metadata"].items():
            if not metadata:
                continue
                
            if "name" in metadata and not standardized["basic_info"].get("name"):
                standardized["basic_info"]["name"] = metadata["name"]
            if "symbol" in metadata and not standardized["basic_info"].get("symbol"):
                standardized["basic_info"]["symbol"] = metadata["symbol"]
            if "decimals" in metadata and not standardized["basic_info"].get("decimals"):
                standardized["basic_info"]["decimals"] = metadata["decimals"]
            
            # SolanaFM-specific fields
            if source == "solanafm":
                if "price" in metadata:
                    standardized["price_info"]["solanafm_price"] = metadata["price"]
                if "volume_24h" in metadata:
                    standardized["trading_info"]["solanafm_volume_24h"] = metadata["volume_24h"]
                if "holder_count" in metadata:
                    standardized["holder_info"]["solanafm_holder_count"] = metadata["holder_count"]
        
        # Standardize price info
        for source, price_data in compiled_data["price_data"].items():
            if not price_data:
                continue
                
            if "value" in price_data:  # Birdeye format
                standardized["price_info"]["current_price"] = price_data["value"]
                standardized["price_info"]["price_change_24h"] = price_data.get("priceChange24hPercent")
            elif "price" in price_data:  # Other formats
                standardized["price_info"]["current_price"] = price_data["price"]
        
        # Standardize holder info (enhanced with SolanaFM data)
        total_holders = 0
        all_holders = []
        
        for source, holder_data in compiled_data["holder_analysis"].items():
            if not holder_data:
                continue
                
            if "total" in holder_data:
                total_holders = max(total_holders, holder_data["total"])
            elif source == "solanafm" and "total" in holder_data:
                total_holders = max(total_holders, holder_data["total"])
            
            if "holders" in holder_data:
                all_holders.extend(holder_data["holders"])
        
        standardized["holder_info"] = {
            "total_holders": total_holders,
            "top_holders": all_holders[:20] if all_holders else []
        }
        
        # Standardize security info (now includes GOplus)
        security_scores = []
        security_flags = []
        
        for source, security_data in compiled_data["security_analysis"].items():
            if not security_data:
                continue
                
            if "risk_score" in security_data:
                security_scores.append(security_data["risk_score"])
            if "security_flags" in security_data:
                security_flags.extend(security_data["security_flags"])
            if "is_scam" in security_data and security_data["is_scam"]:
                security_flags.append("potential_scam")
        
        # Process GOplus analysis
        goplus_data = compiled_data.get("goplus_analysis", {})
        if goplus_data:
            # Extract GOplus comprehensive analysis
            comprehensive = goplus_data.get("comprehensive")
            if comprehensive and comprehensive.get("overall_assessment"):
                assessment = comprehensive["overall_assessment"]
                standardized["goplus_summary"] = {
                    "risk_score": assessment.get("risk_score", 0),
                    "risk_level": assessment.get("risk_level", "unknown"),
                    "is_safe": assessment.get("is_safe"),
                    "major_risks": assessment.get("major_risks", []),
                    "confidence": assessment.get("confidence", 0),
                    "services_used": comprehensive.get("services_used", [])
                }
                
                # Add GOplus risk score to overall security assessment
                if assessment.get("risk_score"):
                    security_scores.append(assessment["risk_score"])
            
            # Extract specific GOplus security data
            security_analysis = goplus_data.get("security")
            if security_analysis:
                goplus_security = {
                    "is_honeypot": security_analysis.get("is_honeypot", False),
                    "is_malicious": security_analysis.get("is_malicious", False),
                    "security_score": security_analysis.get("security_score", 0),
                    "contract_verified": security_analysis.get("contract_security", {}).get("is_verified", False),
                    "trading_taxes": {
                        "buy_tax": security_analysis.get("trading_security", {}).get("buy_tax"),
                        "sell_tax": security_analysis.get("trading_security", {}).get("sell_tax")
                    }
                }
                standardized["goplus_summary"]["security_details"] = goplus_security
            
            # Extract GOplus rugpull data
            rugpull_analysis = goplus_data.get("rugpull")
            if rugpull_analysis:
                standardized["goplus_summary"]["rugpull_risk"] = {
                    "risk_level": rugpull_analysis.get("rugpull_risk", "unknown"),
                    "risk_score": rugpull_analysis.get("risk_score", 0),
                    "liquidity_locked": rugpull_analysis.get("risk_factors", {}).get("liquidity_locked"),
                    "ownership_renounced": rugpull_analysis.get("risk_factors", {}).get("ownership_renounced")
                }
        
        standardized["security_info"] = {
            "average_risk_score": sum(security_scores) / len(security_scores) if security_scores else 0,
            "security_flags": list(set(security_flags)),
            "is_high_risk": any(score > 70 for score in security_scores) if security_scores else False,
            "goplus_enhanced": bool(goplus_data)
        }
        
        return standardized
    
    async def get_goplus_analysis(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive GOplus analysis for a token"""
        if not self.clients["goplus"]:
            return {"error": "GOplus client not available"}
        
        logger.info(f"🔒 Running GOplus analysis for {token_address}")
        
        try:
            comprehensive_analysis = await self.clients["goplus"].comprehensive_analysis(token_address)
            return comprehensive_analysis
        except Exception as e:
            logger.error(f"Error getting GOplus analysis for {token_address}: {str(e)}")
            return {"error": str(e)}
    
    async def simulate_transaction_goplus(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate transaction using GOplus"""
        if not self.clients["goplus"]:
            return {"error": "GOplus client not available"}
        
        logger.info("🎯 Simulating transaction with GOplus")
        
        try:
            simulation_result = await self.clients["goplus"].simulate_transaction(transaction_data)
            return simulation_result
        except Exception as e:
            logger.error(f"Error simulating transaction with GOplus: {str(e)}")
            return {"error": str(e)}
    
    async def detect_rugpull_goplus(self, token_address: str) -> Dict[str, Any]:
        """Detect rugpull using GOplus"""
        if not self.clients["goplus"]:
            return {"error": "GOplus client not available"}
        
        logger.info(f"🚨 Detecting rugpull risk for {token_address} with GOplus")
        
        try:
            rugpull_analysis = await self.clients["goplus"].detect_rugpull(token_address)
            return rugpull_analysis
        except Exception as e:
            logger.error(f"Error detecting rugpull for {token_address} with GOplus: {str(e)}")
            return {"error": str(e)}
    
    def _get_service_capabilities(self, service_name: str) -> List[str]:
        """Get capabilities for each service including GOplus"""
        capabilities = {
            "helius": ["token_metadata", "transaction_history", "account_info", "rpc_calls"],
            "chainbase": ["token_metadata", "holder_analysis", "smart_contract_analysis", "whale_tracking"],
            "birdeye": ["price_data", "trading_history", "market_data", "trending_tokens"],
            "blowfish": ["security_analysis", "scam_detection", "risk_assessment", "transaction_simulation"],
            "dataimpulse": ["social_sentiment", "trending_analysis", "influencer_tracking", "meme_analysis"],
            "solanafm": ["on_chain_data", "transaction_details", "network_stats", "validator_info", "token_info", "holder_analysis"],
            "goplus": ["transaction_simulation", "rugpull_detection", "token_security", "comprehensive_analysis", "multi_service_analysis"]
        }
        return capabilities.get(service_name, [])


# Global API manager instance
api_manager = APIManager()


# Convenience functions
async def initialize_api_services():
    """Initialize all API services including GOplus"""
    await api_manager.initialize_clients()


async def cleanup_api_services():
    """Cleanup all API services including GOplus"""
    await api_manager.cleanup_clients()


async def get_token_analysis(token_address: str) -> Dict[str, Any]:
    """Get comprehensive token analysis including GOplus data"""
    return await api_manager.get_comprehensive_token_data(token_address)


async def get_api_health_status() -> Dict[str, Any]:
    """Get health status of all APIs including GOplus"""
    return await api_manager.check_all_services_health()


async def search_for_tokens(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search for tokens across all sources including GOplus verification"""
    return await api_manager.search_tokens(query, limit)


async def get_trending_analysis(limit: int = 20) -> List[Dict[str, Any]]:
    """Get trending tokens analysis from all sources"""
    return await api_manager.discover_trending_tokens(limit)


# GOplus-specific convenience functions
async def get_goplus_comprehensive_analysis(token_address: str) -> Dict[str, Any]:
    """Get comprehensive GOplus analysis for a token"""
    return await api_manager.get_goplus_analysis(token_address)


async def simulate_transaction_with_goplus(transaction_data: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate transaction using GOplus"""
    return await api_manager.simulate_transaction_goplus(transaction_data)


async def detect_rugpull_with_goplus(token_address: str) -> Dict[str, Any]:
    """Detect rugpull using GOplus"""
    return await api_manager.detect_rugpull_goplus(token_address)