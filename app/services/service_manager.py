import asyncio
import time
from typing import Dict, Any, List, Optional, Union
from loguru import logger

from app.services.helius_client import HeliusClient, check_helius_health
from app.services.chainbase_client import ChainbaseClient, check_chainbase_health
from app.services.birdeye_client import BirdeyeClient, check_birdeye_health
from app.services.blowfish_client import BlowfishClient, check_blowfish_health
from app.services.dataimpulse_client import DataImpulseClient, check_dataimpulse_health
from app.services.solscan_client import SolscanClient, check_solscan_health


class APIManager:
    """Unified API manager for all external services"""
    
    def __init__(self):
        self.clients = {
            "helius": None,
            "chainbase": None,
            "birdeye": None,
            "blowfish": None,
            "dataimpulse": None,
            "solscan": None
        }
        self._health_cache = {}
        self._cache_duration = 300  # 5 minutes
    
    async def initialize_clients(self):
        """Initialize all API clients"""
        try:
            self.clients = {
                "helius": HeliusClient(),
                "chainbase": ChainbaseClient(),
                "birdeye": BirdeyeClient(),
                "blowfish": BlowfishClient(),
                "dataimpulse": DataImpulseClient(),
                "solscan": SolscanClient()
            }
            logger.info("✅ All API clients initialized")
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
        """Check health of all API services"""
        current_time = time.time()
        
        # Check cache
        if self._health_cache and (current_time - self._health_cache.get('timestamp', 0)) < self._cache_duration:
            return self._health_cache['data']
        
        logger.info("🔍 Checking health of all API services...")
        
        # Health check functions
        health_checks = {
            "helius": check_helius_health(),
            "chainbase": check_chainbase_health(),
            "birdeye": check_birdeye_health(),
            "blowfish": check_blowfish_health(),
            "dataimpulse": check_dataimpulse_health(),
            "solscan": check_solscan_health()
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
        
        # Add recommendations
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
        
        # Cache results
        self._health_cache = {
            "data": overall_health,
            "timestamp": current_time
        }
        
        logger.info(f"📊 Health check completed: {healthy_services}/{total_services} services healthy")
        return overall_health
    
    async def get_comprehensive_token_data(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive token data from all available sources"""
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
        
        if self.clients["solscan"]:
            tasks["solscan_info"] = self.clients["solscan"].get_token_info(token_address)
            tasks["solscan_holders"] = self.clients["solscan"].get_token_holders(token_address, 50)
        
        # Security analysis
        if self.clients["blowfish"]:
            tasks["blowfish_scan"] = self.clients["blowfish"].scan_token(token_address)
            tasks["blowfish_risks"] = self.clients["blowfish"].get_risk_indicators(token_address)
        
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
            elif data_type == "supply":
                compiled_data["metadata"][f"{source}_supply"] = result
        
        # Merge and standardize data
        compiled_data["standardized"] = self._standardize_token_data(compiled_data)
        
        logger.info(f"✅ Comprehensive data compiled for {token_address} from {len(compiled_data['data_sources'])} sources in {processing_time:.2f}s")
        return compiled_data
    
    def _standardize_token_data(self, compiled_data: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize token data from different sources"""
        standardized = {
            "basic_info": {},
            "price_info": {},
            "holder_info": {},
            "security_info": {},
            "trading_info": {}
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
        
        # Standardize price info
        for source, price_data in compiled_data["price_data"].items():
            if not price_data:
                continue
                
            if "value" in price_data:  # Birdeye format
                standardized["price_info"]["current_price"] = price_data["value"]
                standardized["price_info"]["price_change_24h"] = price_data.get("priceChange24hPercent")
            elif "price" in price_data:  # Other formats
                standardized["price_info"]["current_price"] = price_data["price"]
        
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
        
        standardized["holder_info"] = {
            "total_holders": total_holders,
            "top_holders": all_holders[:20] if all_holders else []
        }
        
        # Standardize security info
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
        
        standardized["security_info"] = {
            "average_risk_score": sum(security_scores) / len(security_scores) if security_scores else 0,
            "security_flags": list(set(security_flags)),
            "is_high_risk": any(score > 70 for score in security_scores) if security_scores else False
        }
        
        return standardized
    
    async def get_social_sentiment(self, token_symbol: str, token_name: str = None) -> Dict[str, Any]:
        """Get social sentiment analysis for a token"""
        if not self.clients["dataimpulse"]:
            return {"error": "DataImpulse client not available"}
        
        logger.info(f"📱 Analyzing social sentiment for {token_symbol}")
        
        try:
            sentiment_data = await self.clients["dataimpulse"].analyze_token_buzz(
                token_symbol, token_name, "24h"
            )
            return sentiment_data
        except Exception as e:
            logger.error(f"Error getting social sentiment for {token_symbol}: {str(e)}")
            return {"error": str(e)}
    
    async def get_security_analysis(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive security analysis"""
        if not self.clients["blowfish"]:
            return {"error": "Blowfish client not available"}
        
        logger.info(f"🔒 Running security analysis for {token_address}")
        
        try:
            security_report = await self.clients["blowfish"].get_security_report(token_address)
            return security_report
        except Exception as e:
            logger.error(f"Error getting security analysis for {token_address}: {str(e)}")
            return {"error": str(e)}
    
    async def get_market_analysis(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive market analysis"""
        logger.info(f"📈 Running market analysis for {token_address}")
        
        market_data = {}
        
        # Birdeye price and trading data
        if self.clients["birdeye"]:
            try:
                price_data = await self.clients["birdeye"].get_token_price(token_address)
                metadata = await self.clients["birdeye"].get_token_metadata(token_address)
                price_history = await self.clients["birdeye"].get_price_history(token_address, "7d")
                
                market_data["birdeye"] = {
                    "current_price": price_data,
                    "metadata": metadata,
                    "price_history": price_history
                }
            except Exception as e:
                market_data["birdeye_error"] = str(e)
        
        # Chainbase market data
        if self.clients["chainbase"]:
            try:
                chainbase_market = await self.clients["chainbase"].get_market_data(token_address)
                market_data["chainbase"] = chainbase_market
            except Exception as e:
                market_data["chainbase_error"] = str(e)
        
        # Solscan additional data
        if self.clients["solscan"]:
            try:
                solscan_market = await self.clients["solscan"].get_market_data(token_address)
                market_data["solscan"] = solscan_market
            except Exception as e:
                market_data["solscan_error"] = str(e)
        
        return market_data
    
    async def discover_trending_tokens(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Discover trending tokens from multiple sources"""
        logger.info(f"🔥 Discovering trending tokens (limit: {limit})")
        
        trending_tokens = []
        
        # Get trending from Birdeye
        if self.clients["birdeye"]:
            try:
                birdeye_trending = await self.clients["birdeye"].get_trending_tokens(
                    sort_by="v24hUSD", limit=limit
                )
                for token in birdeye_trending:
                    token["source"] = "birdeye"
                    trending_tokens.append(token)
            except Exception as e:
                logger.warning(f"Error getting trending tokens from Birdeye: {str(e)}")
        
        # Get top tokens from Solscan
        if self.clients["solscan"]:
            try:
                solscan_top = await self.clients["solscan"].get_top_tokens(
                    sort_by="volume_24h", limit=limit
                )
                for token in solscan_top:
                    token["source"] = "solscan"
                    trending_tokens.append(token)
            except Exception as e:
                logger.warning(f"Error getting top tokens from Solscan: {str(e)}")
        
        # Get trending topics from DataImpulse
        if self.clients["dataimpulse"]:
            try:
                trending_topics = await self.clients["dataimpulse"].get_trending_topics(
                    platform="all", time_range="24h"
                )
                for topic in trending_topics[:limit//2]:  # Limit social trending
                    if topic.get("related_tokens"):
                        for token_symbol in topic["related_tokens"]:
                            trending_tokens.append({
                                "symbol": token_symbol,
                                "source": "social_trending",
                                "mention_count": topic.get("mention_count"),
                                "sentiment_score": topic.get("sentiment_score")
                            })
            except Exception as e:
                logger.warning(f"Error getting trending topics from DataImpulse: {str(e)}")
        
        # Remove duplicates and sort by relevance
        unique_tokens = {}
        for token in trending_tokens:
            key = token.get("address") or token.get("symbol", "unknown")
            if key not in unique_tokens:
                unique_tokens[key] = token
            else:
                # Merge data from multiple sources
                existing = unique_tokens[key]
                existing["sources"] = existing.get("sources", [existing.get("source")])
                if token.get("source") not in existing["sources"]:
                    existing["sources"].append(token.get("source"))
        
        return list(unique_tokens.values())[:limit]
    
    async def analyze_whale_activity(self, token_address: str) -> Dict[str, Any]:
        """Analyze whale activity for a token"""
        logger.info(f"🐋 Analyzing whale activity for {token_address}")
        
        whale_data = {}
        
        # Chainbase whale activity
        if self.clients["chainbase"]:
            try:
                whale_activity = await self.clients["chainbase"].get_whale_activity(token_address)
                whale_data["chainbase"] = whale_activity
            except Exception as e:
                whale_data["chainbase_error"] = str(e)
        
        # Birdeye top traders
        if self.clients["birdeye"]:
            try:
                top_traders = await self.clients["birdeye"].get_top_traders(token_address)
                whale_data["birdeye_traders"] = top_traders
            except Exception as e:
                whale_data["birdeye_error"] = str(e)
        
        # Analyze whale impact
        if whale_data:
            whale_data["analysis"] = self._analyze_whale_impact(whale_data)
        
        return whale_data
    
    def _analyze_whale_impact(self, whale_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze whale impact on token"""
        analysis = {
            "whale_count": 0,
            "total_whale_volume": 0,
            "average_whale_size": 0,
            "whale_sentiment": "neutral",
            "risk_level": "low"
        }
        
        # Analyze Chainbase whale activity
        chainbase_whales = whale_data.get("chainbase", [])
        if chainbase_whales:
            analysis["whale_count"] += len(chainbase_whales)
            for whale in chainbase_whales:
                volume = whale.get("amount_usd", 0)
                if isinstance(volume, (int, float)):
                    analysis["total_whale_volume"] += volume
        
        # Analyze Birdeye top traders
        birdeye_traders = whale_data.get("birdeye_traders", [])
        if birdeye_traders:
            large_traders = [t for t in birdeye_traders if t.get("totalVolumeInUSD", 0) > 50000]
            analysis["whale_count"] += len(large_traders)
            
            for trader in large_traders:
                volume = trader.get("totalVolumeInUSD", 0)
                if isinstance(volume, (int, float)):
                    analysis["total_whale_volume"] += volume
        
        # Calculate averages and risk
        if analysis["whale_count"] > 0:
            analysis["average_whale_size"] = analysis["total_whale_volume"] / analysis["whale_count"]
            
            # Determine risk level based on whale activity
            if analysis["whale_count"] > 10 and analysis["average_whale_size"] > 100000:
                analysis["risk_level"] = "high"
                analysis["whale_sentiment"] = "very_active"
            elif analysis["whale_count"] > 5:
                analysis["risk_level"] = "medium"
                analysis["whale_sentiment"] = "active"
        
        return analysis
    
    async def search_tokens(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for tokens across multiple sources"""
        logger.info(f"🔍 Searching for tokens: '{query}' (limit: {limit})")
        
        search_results = []
        
        # Search tasks
        search_tasks = {}
        
        if self.clients["birdeye"]:
            search_tasks["birdeye"] = self.clients["birdeye"].search_tokens(query, limit)
        
        if self.clients["chainbase"]:
            search_tasks["chainbase"] = self.clients["chainbase"].search_tokens(query, limit)
        
        if self.clients["solscan"]:
            search_tasks["solscan"] = self.clients["solscan"].search_tokens(query)
        
        # Execute searches
        if search_tasks:
            results = await asyncio.gather(*search_tasks.values(), return_exceptions=True)
            
            for i, (source, task) in enumerate(search_tasks.items()):
                result = results[i]
                if not isinstance(result, Exception) and result:
                    for token in result:
                        token["source"] = source
                        search_results.append(token)
        
        # Remove duplicates and rank results
        unique_results = {}
        for token in search_results:
            key = token.get("address") or token.get("mint") or f"{token.get('symbol')}_{token.get('name')}"
            if key not in unique_results:
                unique_results[key] = token
        
        return list(unique_results.values())[:limit]
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get detailed status of all API services"""
        health_data = await self.check_all_services_health()
        
        status = {
            "overall_status": health_data["overall_healthy"],
            "services": {},
            "summary": health_data["summary"],
            "recommendations": health_data["recommendations"],
            "last_checked": health_data["timestamp"]
        }
        
        for service_name, health_info in health_data["services"].items():
            status["services"][service_name] = {
                "status": "operational" if health_info.get("healthy") else "down",
                "configured": health_info.get("api_key_configured", False),
                "response_time": health_info.get("response_time"),
                "error": health_info.get("error"),
                "capabilities": self._get_service_capabilities(service_name)
            }
        
        return status
    
    def _get_service_capabilities(self, service_name: str) -> List[str]:
        """Get capabilities for each service"""
        capabilities = {
            "helius": ["token_metadata", "transaction_history", "account_info", "rpc_calls"],
            "chainbase": ["token_metadata", "holder_analysis", "smart_contract_analysis", "whale_tracking"],
            "birdeye": ["price_data", "trading_history", "market_data", "trending_tokens"],
            "blowfish": ["security_analysis", "scam_detection", "risk_assessment", "transaction_simulation"],
            "dataimpulse": ["social_sentiment", "trending_analysis", "influencer_tracking", "meme_analysis"],
            "solscan": ["on_chain_data", "transaction_details", "network_stats", "validator_info"]
        }
        return capabilities.get(service_name, [])


# Global API manager instance
api_manager = APIManager()


# Convenience functions
async def initialize_api_services():
    """Initialize all API services"""
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
    """Search for tokens across all sources"""
    return await api_manager.search_tokens(query, limit)


async def get_trending_analysis(limit: int = 20) -> List[Dict[str, Any]]:
    """Get trending tokens analysis"""
    return await api_manager.discover_trending_tokens(limit)