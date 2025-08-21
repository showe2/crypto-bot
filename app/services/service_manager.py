import asyncio
import time
from typing import Dict, Any, List, Optional, Union
from loguru import logger

from app.services.helius_client import HeliusClient, check_helius_health
from app.services.chainbase_client import ChainbaseClient, check_chainbase_health
from app.services.birdeye_client import BirdeyeClient, check_birdeye_health
from app.services.dataimpulse_client import DataImpulseClient, check_dataimpulse_health
from app.services.solanafm_client import SolanaFMClient, check_solanafm_health
from app.services.goplus_client import GOplusClient, check_goplus_health
from app.services.dexscreener_client import DexScreenerClient, check_dexscreener_health
from app.services.rugcheck_client import RugCheckClient, check_rugcheck_health


class APIManager:
    """Unified API manager for all external services including RugCheck"""
    
    def __init__(self):
        self.clients = {
            "helius": None,
            "chainbase": None,
            "birdeye": None,
            "dataimpulse": None,
            "solanafm": None,
            "goplus": None,
            "dexscreener": None,
            "rugcheck": None  # Added RugCheck
        }
        self._health_cache = {}
        self._cache_duration = 300  # 5 minutes
    
    async def initialize_clients(self):
        """Initialize all API clients including RugCheck"""
        try:
            self.clients = {
                "helius": HeliusClient(),
                "chainbase": ChainbaseClient(),
                "birdeye": BirdeyeClient(),
                "dataimpulse": DataImpulseClient(),
                "solanafm": SolanaFMClient(),
                "goplus": GOplusClient(),
                "dexscreener": DexScreenerClient(),
                "rugcheck": RugCheckClient()  # Added RugCheck
            }
            logger.info("✅ All API clients initialized (including RugCheck)")
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
        """Check health of all API services including RugCheck"""
        current_time = time.time()
        
        # Check cache
        if self._health_cache and (current_time - self._health_cache.get('timestamp', 0)) < self._cache_duration:
            return self._health_cache['data']
        
        logger.info("🔍 Checking health of all API services (including RugCheck)...")
        
        # Health check functions
        health_checks = {
            "helius": check_helius_health(),
            "chainbase": check_chainbase_health(),
            "birdeye": check_birdeye_health(),
            "dataimpulse": check_dataimpulse_health(),
            "solanafm": check_solanafm_health(),
            "goplus": check_goplus_health(),
            "dexscreener": check_dexscreener_health(),
            "rugcheck": check_rugcheck_health()  # Added RugCheck
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
                           if not status.get("api_key_configured", False) and name not in ["solanafm", "dexscreener"]]
            if missing_keys:
                overall_health["recommendations"].append(
                    f"Configure API keys for: {', '.join(missing_keys)}"
                )
        
        if healthy_services < total_services:
            unhealthy = [name for name, status in health_status.items() 
                        if not status.get("healthy", False)]
            overall_health["recommendations"].append(
                f"Check service status for: {', '.join(unhealthy)}"
            )
        
        # Free services recommendations
        free_services = ["solanafm", "dexscreener"]
        for service in free_services:
            if service in health_status:
                service_status = health_status[service]
                if not service_status.get("healthy"):
                    overall_health["recommendations"].append(
                        f"{service.upper()}: Free service - check network connectivity"
                    )
        
        # Cache results
        self._health_cache = {
            "data": overall_health,
            "timestamp": current_time
        }
        
        logger.info(f"📊 Health check completed: {healthy_services}/{total_services} services healthy")
        return overall_health
    
    async def get_comprehensive_token_data(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive token data from all available sources including RugCheck"""
        logger.info(f"🔍 Gathering comprehensive data for token: {token_address}")
        
        # Prepare tasks for parallel execution
        tasks = {}
        
        # Basic token information
        if self.clients["helius"]:
            tasks["helius_metadata"] = self.clients["helius"].get_token_metadata(token_address)
            tasks["helius_supply"] = self.clients["helius"].get_token_supply(token_address)
        
        if self.clients["chainbase"]:
            tasks["chainbase_metadata"] = self.clients["chainbase"].get_token_metadata(token_address)
            tasks["chainbase_holders"] = self.clients["chainbase"].get_token_holders(token_address, limit=100)
        
        if self.clients["birdeye"]:
            tasks["birdeye_price"] = self.clients["birdeye"].get_token_price(token_address)
            tasks["birdeye_metadata"] = self.clients["birdeye"].get_token_metadata(token_address)
            tasks["birdeye_trades"] = self.clients["birdeye"].get_token_trades(token_address, limit=50)
        
        # SolanaFM data collection
        if self.clients["solanafm"]:
            tasks["solanafm_token_info"] = self.clients["solanafm"].get_token_info(token_address)
            tasks["solanafm_account_detail"] = self.clients["solanafm"].get_account_detail(token_address)
        
        # DexScreener data collection (FREE)
        if self.clients["dexscreener"]:
            tasks["dexscreener_pairs"] = self.clients["dexscreener"].get_token_pairs(token_address)
        
        # GOplus comprehensive analysis
        if self.clients["goplus"]:
            tasks["goplus_comprehensive"] = self.clients["goplus"].comprehensive_analysis(token_address)
            tasks["goplus_security"] = self.clients["goplus"].analyze_token_security(token_address)
            tasks["goplus_rugpull"] = self.clients["goplus"].detect_rugpull(token_address)
        
        # RugCheck security analysis
        if self.clients["rugcheck"]:
            tasks["rugcheck_report"] = self.clients["rugcheck"].check_token(token_address)
            tasks["rugcheck_holders"] = self.clients["rugcheck"].get_token_holders(token_address, limit=50)
        
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
            "solanafm_data": {},
            "goplus_analysis": {},
            "dexscreener_data": {},
            "rugcheck_data": {},  # Added RugCheck section
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
            
            # Organize data by type and source
            if data_type in ["metadata", "token_info"]:
                compiled_data["metadata"][source] = result
            elif data_type in ["price"]:
                compiled_data["price_data"][source] = result
            elif data_type in ["holders"]:
                compiled_data["holder_analysis"][source] = result
            elif data_type in ["trades", "trading"]:
                compiled_data["trading_data"][source] = result
            elif data_type in ["scan", "risks", "security"]:
                compiled_data["security_analysis"][source] = result
            elif data_type in ["pairs"]:  # DexScreener pairs data
                compiled_data["dexscreener_data"][data_type] = result
            elif source == "solanafm":
                compiled_data["solanafm_data"][data_type] = result
            elif source == "goplus":
                compiled_data["goplus_analysis"][data_type] = result
            elif source == "dexscreener":
                compiled_data["dexscreener_data"][data_type] = result
            elif source == "rugcheck":  # RugCheck data
                compiled_data["rugcheck_data"][data_type] = result
            elif data_type == "supply":
                compiled_data["metadata"][f"{source}_supply"] = result
            else:
                compiled_data["network_data"][f"{source}_{data_type}"] = result
        
        # Merge and standardize data (now includes RugCheck)
        compiled_data["standardized"] = self._standardize_token_data(compiled_data)
        
        logger.info(f"✅ Comprehensive data compiled for {token_address} from {len(compiled_data['data_sources'])} sources in {processing_time:.2f}s")
        return compiled_data
    
    def _standardize_token_data(self, compiled_data: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize token data from different sources including RugCheck"""
        standardized = {
            "basic_info": {},
            "price_info": {},
            "holder_info": {},
            "security_info": {},
            "trading_info": {},
            "network_info": {},
            "solanafm_summary": {},
            "goplus_summary": {},
            "dexscreener_summary": {},
            "rugcheck_summary": {}  # Added RugCheck summary
        }
        
        # Standardize basic info
        for source, metadata in compiled_data["metadata"].items():
            if not metadata:
                continue
                
            if "name" in metadata and not standardized["basic_info"].get("name"):
                standardized["basic_info"]["name"] = metadata["name"]
            if "symbol" in metadata and not standardized["basic_info"].get("symbol"):
                standardized["basic_info"]["symbol"] = metadata["symbol"]
            if "decimals" in metadata and not standardized["basic_info"].get("decimals"):
                standardized["basic_info"]["decimals"] = metadata["decimals"]
        
        # Process RugCheck data
        rugcheck_data = compiled_data.get("rugcheck_data", {})
        if rugcheck_data:
            report_data = rugcheck_data.get("report")
            if report_data:
                standardized["rugcheck_summary"] = {
                    "score": report_data.get("score"),
                    "is_scam": report_data.get("is_scam", False),
                    "is_honeypot": report_data.get("is_honeypot", False),
                    "risks": report_data.get("risks", []),
                    "creator_analysis": report_data.get("creator_analysis", {}),
                    "liquidity_analysis": report_data.get("liquidity_analysis", {}),
                    "last_updated": report_data.get("last_updated")
                }
            
            holders_data = rugcheck_data.get("holders")
            if holders_data:
                standardized["rugcheck_summary"]["holders_analysis"] = {
                    "total_holders": holders_data.get("total_holders"),
                    "distribution": holders_data.get("distribution", {}),
                    "suspicious_holders": len(holders_data.get("suspicious_holders", []))
                }
        
        # Process DexScreener data
        dexscreener_data = compiled_data.get("dexscreener_data", {})
        if dexscreener_data:
            pairs_data = dexscreener_data.get("pairs")
            if pairs_data and pairs_data.get("pairs"):
                pairs = pairs_data["pairs"]
                
                # Extract summary from DexScreener pairs
                standardized["dexscreener_summary"] = {
                    "pairs_count": len(pairs),
                    "total_liquidity_usd": sum(
                        float(pair.get("liquidity", {}).get("usd", 0) or 0) 
                        for pair in pairs
                    ),
                    "total_volume_24h": sum(
                        float(pair.get("volume", {}).get("24h", 0) or 0)
                        for pair in pairs
                    ),
                    "best_price_usd": None,
                    "active_dexes": list(set(pair.get("dex_id") for pair in pairs if pair.get("dex_id"))),
                    "chains": list(set(pair.get("chain_id") for pair in pairs if pair.get("chain_id")))
                }
                
                # Find best price (highest liquidity pair)
                best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                if best_pair:
                    standardized["dexscreener_summary"]["best_price_usd"] = best_pair.get("price_usd")
                    
                    # Use DexScreener price if no other price data available
                    if not standardized["price_info"].get("current_price") and best_pair.get("price_usd"):
                        standardized["price_info"]["current_price"] = best_pair["price_usd"]
                        standardized["price_info"]["price_change_24h"] = best_pair.get("price_change", {}).get("24h")
                        standardized["price_info"]["volume_24h"] = best_pair.get("volume", {}).get("24h")
                        standardized["price_info"]["source"] = "dexscreener"
        
        # Process SolanaFM data
        solanafm_data = compiled_data.get("solanafm_data", {})
        if solanafm_data:
            token_info = solanafm_data.get("token_info")
            if token_info:
                standardized["solanafm_summary"]["token_info"] = {
                    "name": token_info.get("name"),
                    "symbol": token_info.get("symbol"),
                    "decimals": token_info.get("decimals"),
                    "token_type": token_info.get("token_type"),
                    "mint_authority": token_info.get("mint_authority"),
                    "freeze_authority": token_info.get("freeze_authority"),
                    "tags": token_info.get("tags", [])
                }
            
            account_detail = solanafm_data.get("account_detail")
            if account_detail:
                standardized["solanafm_summary"]["account_detail"] = {
                    "lamports": account_detail.get("lamports"),
                    "balance_sol": account_detail.get("balance_sol"),
                    "friendly_name": account_detail.get("friendly_name"),
                    "tags": account_detail.get("tags"),
                    "flag": account_detail.get("flag")
                }
        
        # Standardize price info (now includes DexScreener)
        for source, price_data in compiled_data["price_data"].items():
            if not price_data:
                continue
                
            if "value" in price_data:  # Birdeye format
                standardized["price_info"]["current_price"] = price_data["value"]
                standardized["price_info"]["price_change_24h"] = price_data.get("priceChange24hPercent")
                standardized["price_info"]["source"] = source
            elif "price" in price_data:  # Other formats
                standardized["price_info"]["current_price"] = price_data["price"]
                standardized["price_info"]["source"] = source
        
        # Standardize holder info
        total_holders = 0
        all_holders = []
        
        for source, holder_data in compiled_data["holder_analysis"].items():
            if not holder_data:
                continue
                
            if "total" in holder_data:
                total_holders = max(total_holders, holder_data["total"])
            
            if "holders" in holder_data:
                all_holders.extend(holder_data["holders"])
            elif "top_holders" in holder_data:  # RugCheck format
                all_holders.extend(holder_data["top_holders"])
        
        standardized["holder_info"] = {
            "total_holders": total_holders,
            "top_holders": all_holders[:20] if all_holders else []
        }
        
        # Standardize security info (includes GOplus and RugCheck)
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
        
        # Add RugCheck security data
        if rugcheck_data.get("report"):
            rugcheck_report = rugcheck_data["report"]
            if rugcheck_report.get("score"):
                # Convert RugCheck score (0-100, higher=safer) to risk score (0-100, higher=riskier)
                rugcheck_risk_score = 100 - rugcheck_report["score"]
                security_scores.append(rugcheck_risk_score)
            
            if rugcheck_report.get("is_scam"):
                security_flags.append("rugcheck_scam")
            if rugcheck_report.get("is_honeypot"):
                security_flags.append("rugcheck_honeypot")
            if rugcheck_report.get("risks"):
                security_flags.extend([f"rugcheck_{risk}" for risk in rugcheck_report["risks"]])
        
        # Process GOplus analysis
        goplus_data = compiled_data.get("goplus_analysis", {})
        if goplus_data:
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
                
                if assessment.get("risk_score"):
                    security_scores.append(assessment["risk_score"])
            
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
            "solanafm_enhanced": bool(solanafm_data),
            "goplus_enhanced": bool(goplus_data),
            "dexscreener_enhanced": bool(dexscreener_data),
            "rugcheck_enhanced": bool(rugcheck_data)  # Added RugCheck flag
        }
        
        return standardized
    
    def _get_service_capabilities(self, service_name: str) -> List[str]:
        """Get capabilities for each service including RugCheck"""
        capabilities = {
            "helius": ["token_metadata", "transaction_history", "account_info", "rpc_calls"],
            "chainbase": ["token_metadata", "holder_analysis", "smart_contract_analysis", "whale_tracking"],
            "birdeye": ["price_data", "trading_history", "market_data", "trending_tokens"],
            "dataimpulse": ["social_sentiment", "trending_analysis", "influencer_tracking", "meme_analysis"],
            "solanafm": ["on_chain_data", "transaction_details", "network_stats", "token_info", "account_details"],
            "goplus": ["transaction_simulation", "rugpull_detection", "token_security", "comprehensive_analysis", "multi_service_analysis"],
            "dexscreener": ["dex_data", "trading_pairs", "price_discovery", "liquidity_analysis", "free_access"],
            "rugcheck": ["rug_detection", "token_security", "creator_analysis", "holder_analysis", "scam_detection"]  # Added RugCheck
        }
        return capabilities.get(service_name, [])


# Global API manager instance
api_manager = APIManager()


# Convenience functions
async def initialize_api_services():
    """Initialize all API services including RugCheck"""
    await api_manager.initialize_clients()


async def cleanup_api_services():
    """Cleanup all API services"""
    await api_manager.cleanup_clients()


async def get_token_analysis(token_address: str) -> Dict[str, Any]:
    """Get comprehensive token analysis"""
    return await api_manager.get_comprehensive_token_data(token_address)


async def get_api_health_status() -> Dict[str, Any]:
    """Get health status of all APIs"""
    return await api_manager.check_all_services_health()


async def search_for_tokens(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search for tokens across all sources including RugCheck"""
    results = []
    
    # Use DexScreener for search (free)
    if api_manager.clients.get("dexscreener"):
        try:
            dexscreener_results = await api_manager.clients["dexscreener"].search_pairs(query)
            
            # Convert DexScreener results to standard format
            for pair in dexscreener_results[:limit]:
                result = {
                    "address": pair.get("base_token", {}).get("address"),
                    "name": pair.get("base_token", {}).get("name"),
                    "symbol": pair.get("base_token", {}).get("symbol"),
                    "price_usd": pair.get("price_usd"),
                    "volume_24h": pair.get("volume_24h"),
                    "liquidity_usd": pair.get("liquidity_usd"),
                    "market_cap": pair.get("market_cap"),
                    "source": "dexscreener",
                    "pair_address": pair.get("pair_address"),
                    "dex_id": pair.get("dex_id"),
                    "chain_id": pair.get("chain_id")
                }
                results.append(result)
                
        except Exception as e:
            logger.error(f"DexScreener search failed: {str(e)}")
    
    # Use RugCheck for search (if available)
    if api_manager.clients.get("rugcheck"):
        try:
            rugcheck_results = await api_manager.clients["rugcheck"].search_tokens(query, limit)
            
            # Convert RugCheck results to standard format
            for token in rugcheck_results[:limit]:
                result = {
                    "address": token.get("token_address"),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "score": token.get("score"),
                    "risk_level": token.get("risk_level"),
                    "is_verified": token.get("is_verified"),
                    "market_cap": token.get("market_cap"),
                    "holder_count": token.get("holder_count"),
                    "source": "rugcheck",
                    "last_checked": token.get("last_checked")
                }
                results.append(result)
                
        except Exception as e:
            logger.error(f"RugCheck search failed: {str(e)}")
    
    return results


async def get_trending_analysis(limit: int = 20) -> List[Dict[str, Any]]:
    """Get trending tokens analysis from all sources"""
    # Implementation would aggregate from multiple sources including RugCheck
    return []


# RugCheck-specific convenience functions
async def get_rugcheck_token_data(token_address: str) -> Dict[str, Any]:
    """Get RugCheck token data for a token"""
    if not api_manager.clients.get("rugcheck"):
        return {"error": "RugCheck client not available"}
    
    try:
        token_report = await api_manager.clients["rugcheck"].check_token(token_address)
        return {
            "token_report": token_report,
            "source": "rugcheck",
            "cost": "PAID"
        }
    except Exception as e:
        logger.error(f"Error getting RugCheck data for {token_address}: {str(e)}")
        return {"error": str(e)}


async def get_rugcheck_creator_analysis(creator_address: str) -> Dict[str, Any]:
    """Get RugCheck creator analysis"""
    if not api_manager.clients.get("rugcheck"):
        return {"error": "RugCheck client not available"}
    
    try:
        creator_analysis = await api_manager.clients["rugcheck"].analyze_creator(creator_address)
        return {
            "creator_analysis": creator_analysis,
            "source": "rugcheck",
            "cost": "PAID"
        }
    except Exception as e:
        logger.error(f"Error getting RugCheck creator analysis for {creator_address}: {str(e)}")
        return {"error": str(e)}


async def get_trending_rugs() -> List[Dict[str, Any]]:
    """Get trending rug pulls from RugCheck"""
    if not api_manager.clients.get("rugcheck"):
        return []
    
    try:
        return await api_manager.clients["rugcheck"].get_trending_rugs()
    except Exception as e:
        logger.error(f"RugCheck trending rugs failed: {str(e)}")
        return []


async def search_rugcheck_tokens(query: str) -> List[Dict[str, Any]]:
    """Search RugCheck for tokens"""
    if not api_manager.clients.get("rugcheck"):
        return []
    
    try:
        return await api_manager.clients["rugcheck"].search_tokens(query)
    except Exception as e:
        logger.error(f"RugCheck search failed for '{query}': {str(e)}")
        return []


# DexScreener-specific convenience functions
async def get_dexscreener_token_data(token_address: str) -> Dict[str, Any]:
    """Get DexScreener token data for a token"""
    if not api_manager.clients.get("dexscreener"):
        return {"error": "DexScreener client not available"}
    
    try:
        pairs_data = await api_manager.clients["dexscreener"].get_token_pairs(token_address)
        return {
            "pairs_data": pairs_data,
            "source": "dexscreener",
            "cost": "FREE"
        }
    except Exception as e:
        logger.error(f"Error getting DexScreener data for {token_address}: {str(e)}")
        return {"error": str(e)}


async def search_dexscreener_pairs(query: str) -> List[Dict[str, Any]]:
    """Search DexScreener for trading pairs"""
    if not api_manager.clients.get("dexscreener"):
        return []
    
    try:
        return await api_manager.clients["dexscreener"].search_pairs(query)
    except Exception as e:
        logger.error(f"DexScreener search failed for '{query}': {str(e)}")
        return []