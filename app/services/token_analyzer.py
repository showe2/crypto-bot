import asyncio
import time
from typing import Dict, Any, Optional, List
from loguru import logger
from datetime import datetime

from app.services.service_manager import api_manager
from app.utils.redis_client import get_redis_client
from app.utils.cache import cache_manager


class TokenAnalyzer:
    """Main token analyzer that coordinates all services"""
    
    def __init__(self):
        self.services = {
            # "helius": True,
            "chainbase": True,
            "birdeye": True,
            "solanafm": True,
            "goplus": True,
            "dexscreener": True,
            "rugcheck": True
        }
    
    async def analyze_token_comprehensive(self, token_address: str, source_event: str = "webhook") -> Dict[str, Any]:
        """
        Comprehensive token analysis using all available services
        """
        start_time = time.time()
        analysis_id = f"analysis_{int(time.time())}_{token_address[:8]}"
        
        logger.info(f"🔍 Starting comprehensive analysis for {token_address} from {source_event}")
        
        # Check cache first
        cache_key = f"token_analysis:{token_address}"
        cached_result = await cache_manager.get(cache_key, namespace="analysis")
        
        if cached_result and source_event == "webhook":
            logger.info(f"📋 Returning cached analysis for {token_address}")
            return cached_result
        
        # Initialize response structure
        analysis_response = {
            "analysis_id": analysis_id,
            "token_address": token_address,
            "timestamp": datetime.utcnow().isoformat(),
            "source_event": source_event
        }
        
        # Prepare service tasks
        service_tasks = {}
        
        # Chainbase - Holder analysis
        if api_manager.clients.get("chainbase"):
            service_tasks["chainbase_metadata"] = self._safe_service_call(
                api_manager.clients["chainbase"].get_token_metadata, token_address
            )
            service_tasks["chainbase_holders"] = self._safe_service_call(
                api_manager.clients["chainbase"].get_token_holders, token_address, limit=50
            )
        
        # Birdeye - Price and market data
        if api_manager.clients.get("birdeye"):
            service_tasks["birdeye_price"] = self._safe_service_call(
                api_manager.clients["birdeye"].get_token_price, token_address
            )
            service_tasks["birdeye_trades"] = self._safe_service_call(
                api_manager.clients["birdeye"].get_token_trades, token_address, limit=20
            )
        
        # SolanaFM - On-chain data
        if api_manager.clients.get("solanafm"):
            service_tasks["solanafm_token"] = self._safe_service_call(
                api_manager.clients["solanafm"].get_token_info, token_address
            )
            service_tasks["solanafm_account"] = self._safe_service_call(
                api_manager.clients["solanafm"].get_account_detail, token_address
            )
        
        # DexScreener - Trading pairs (FREE)
        if api_manager.clients.get("dexscreener"):
            service_tasks["dexscreener_pairs"] = self._safe_service_call(
                api_manager.clients["dexscreener"].get_token_pairs, token_address
            )
        
        # GOplus - Security analysis
        if api_manager.clients.get("goplus"):
            service_tasks["goplus_security"] = self._safe_service_call(
                api_manager.clients["goplus"].analyze_token_security, token_address
            )
            service_tasks["goplus_rugpull"] = self._safe_service_call(
                api_manager.clients["goplus"].detect_rugpull, token_address
            )
        
        # RugCheck - Security analysis
        if api_manager.clients.get("rugcheck"):
            service_tasks["rugcheck_report"] = self._safe_service_call(
                api_manager.clients["rugcheck"].check_token, token_address
            )
        
        # Execute all service calls concurrently
        logger.info(f"🚀 Executing {len(service_tasks)} service calls concurrently")
        results = await asyncio.gather(*service_tasks.values(), return_exceptions=True)
        
        # Process results
        task_names = list(service_tasks.keys())
        for i, task_name in enumerate(task_names):
            result = results[i]
            service_name = task_name.split("_")[0]
            
            if isinstance(result, Exception):
                error_msg = f"{task_name}: {str(result)}"
                analysis_response["errors"].append(error_msg)
                logger.warning(f"❌ {error_msg}")
                continue
            
            if result is None:
                analysis_response["warnings"].append(f"{task_name}: No data returned")
                continue
            
            # Store service response
            if service_name not in analysis_response["service_responses"]:
                analysis_response["service_responses"][service_name] = {}
            
            analysis_response["service_responses"][service_name][task_name.split("_", 1)[1]] = result
            
            # Track data sources
            if service_name not in analysis_response["data_sources"]:
                analysis_response["data_sources"].append(service_name)
        
        # Generate overall analysis
        analysis_response["overall_analysis"] = await self._generate_overall_analysis(
            analysis_response["service_responses"], token_address
        )
        
        # Calculate processing time
        processing_time = time.time() - start_time
        analysis_response["processing_time"] = round(processing_time, 3)
        
        # Cache the result (5 minutes for webhook events, 2 minutes for direct calls)
        cache_ttl = 300 if source_event == "webhook" else 120
        await cache_manager.set(cache_key, analysis_response, ttl=cache_ttl, namespace="analysis")
        
        logger.info(
            f"✅ Analysis completed for {token_address} in {processing_time:.2f}s "
            f"(sources: {len(analysis_response['data_sources'])}, errors: {len(analysis_response['errors'])})"
        )
        
        return analysis_response
    
    async def _safe_service_call(self, service_func, *args, **kwargs):
        """Execute service call with error handling"""
        try:
            return await service_func(*args, **kwargs)
        except Exception as e:
            logger.debug(f"Service call failed: {service_func.__name__} - {str(e)}")
            raise
    
    async def _generate_overall_analysis(self, service_responses: Dict[str, Any], token_address: str) -> Dict[str, Any]:
        """Generate overall analysis from all service responses"""
        
        # Initialize analysis components
        scores = []
        risk_factors = []
        positive_signals = []
        metadata_quality = 0
        price_available = False
        security_checked = False
        
        # Process each service response
        data_quality_score = 0
        total_services = len(service_responses)
        
        # Helius data
        if "helius" in service_responses:
            helius_data = service_responses["helius"]
            if helius_data.get("metadata"):
                metadata_quality += 30
                positive_signals.append("Token metadata available")
            if helius_data.get("supply"):
                positive_signals.append("Token supply information available")
        
        # Chainbase data
        if "chainbase" in service_responses:
            chainbase_data = service_responses["chainbase"]
            if chainbase_data.get("holders"):
                holders = chainbase_data["holders"]
                if isinstance(holders, dict) and holders.get("holders"):
                    holder_count = len(holders["holders"])
                    if holder_count > 100:
                        positive_signals.append(f"Good holder distribution ({holder_count} holders)")
                        scores.append(70)
                    elif holder_count > 10:
                        scores.append(50)
                    else:
                        risk_factors.append("Low holder count")
                        scores.append(20)
                    data_quality_score += 25
        
        # Birdeye data
        if "birdeye" in service_responses:
            birdeye_data = service_responses["birdeye"]
            if birdeye_data.get("price"):
                price_data = birdeye_data["price"]
                price_available = True
                data_quality_score += 20
                
                # Analyze price data
                if price_data.get("value") and float(price_data["value"]) > 0:
                    positive_signals.append("Token has market price")
                    scores.append(60)
                
                # Volume analysis
                volume_24h = price_data.get("volume_24h")
                if volume_24h and float(volume_24h) > 1000:  # $1000+ daily volume
                    positive_signals.append("Good trading volume")
                    scores.append(65)
                elif volume_24h and float(volume_24h) > 100:
                    scores.append(45)
                else:
                    risk_factors.append("Low trading volume")
                    scores.append(25)
        
        # SolanaFM data
        if "solanafm" in service_responses:
            solanafm_data = service_responses["solanafm"]
            if solanafm_data.get("token"):
                token_info = solanafm_data["token"]
                if token_info.get("name") and token_info.get("symbol"):
                    metadata_quality += 20
                    positive_signals.append("Complete token information")
            data_quality_score += 15
        
        # DexScreener data
        if "dexscreener" in service_responses:
            dexscreener_data = service_responses["dexscreener"]
            if dexscreener_data.get("pairs"):
                pairs_data = dexscreener_data["pairs"]
                if pairs_data and pairs_data.get("pairs"):
                    pairs_count = len(pairs_data["pairs"])
                    if pairs_count > 0:
                        positive_signals.append(f"Trading on {pairs_count} DEX(es)")
                        scores.append(55)
                        data_quality_score += 20
        
        # GOplus security analysis
        if "goplus" in service_responses:
            goplus_data = service_responses["goplus"]
            security_checked = True
            
            if goplus_data.get("security"):
                security_data = goplus_data["security"]
                
                # Check for honeypot
                if security_data.get("is_honeypot") == "1":
                    risk_factors.append("GOplus: Potential honeypot detected")
                    scores.append(5)
                else:
                    scores.append(60)
                
                # Check taxes
                buy_tax = security_data.get("buy_tax")
                sell_tax = security_data.get("sell_tax")
                
                if buy_tax and float(buy_tax) > 10:
                    risk_factors.append(f"High buy tax: {buy_tax}%")
                    scores.append(30)
                
                if sell_tax and float(sell_tax) > 10:
                    risk_factors.append(f"High sell tax: {sell_tax}%")
                    scores.append(20)
                
                if not risk_factors:
                    positive_signals.append("GOplus: No major security issues")
            
            data_quality_score += 25
        
        # RugCheck analysis
        if "rugcheck" in service_responses:
            rugcheck_data = service_responses["rugcheck"]
            security_checked = True
            
            if rugcheck_data.get("report"):
                report = rugcheck_data["report"]
                
                # RugCheck score (0-100, higher is safer)
                rugcheck_score = report.get("score")
                if rugcheck_score is not None:
                    if rugcheck_score > 80:
                        positive_signals.append(f"RugCheck: High safety score ({rugcheck_score})")
                        scores.append(80)
                    elif rugcheck_score > 60:
                        scores.append(65)
                    elif rugcheck_score > 40:
                        scores.append(45)
                        risk_factors.append(f"RugCheck: Moderate risk (score: {rugcheck_score})")
                    else:
                        risk_factors.append(f"RugCheck: High risk (score: {rugcheck_score})")
                        scores.append(20)
                
                # Check for rug status
                if report.get("rugged"):
                    risk_factors.append("RugCheck: Token flagged as rugged")
                    scores.append(5)
                
                data_quality_score += 25
        
        # Calculate overall score
        if scores:
            overall_score = sum(scores) / len(scores)
        else:
            overall_score = 30  # Default low score if no data
        
        # Determine risk level
        if overall_score >= 70:
            risk_level = "low"
            recommendation = "consider"
        elif overall_score >= 50:
            risk_level = "medium"
            recommendation = "caution"
        elif overall_score >= 30:
            risk_level = "high"
            recommendation = "avoid"
        else:
            risk_level = "critical"
            recommendation = "avoid"
        
        # Data quality assessment
        if data_quality_score >= 80:
            data_quality = "excellent"
        elif data_quality_score >= 60:
            data_quality = "good"
        elif data_quality_score >= 40:
            data_quality = "moderate"
        else:
            data_quality = "poor"
        
        # Confidence calculation
        confidence = min(100, data_quality_score + (10 if security_checked else 0) + (10 if price_available else 0))
        
        # Generate summary
        summary_parts = []
        if positive_signals:
            summary_parts.append(f"Positives: {', '.join(positive_signals[:3])}")
        if risk_factors:
            summary_parts.append(f"Risks: {', '.join(risk_factors[:3])}")
        
        summary = "; ".join(summary_parts) if summary_parts else "Limited data available for analysis"
        
        return {
            "score": round(overall_score, 1),
            "risk_level": risk_level,
            "recommendation": recommendation,
            "confidence": round(confidence, 1),
            "data_quality": data_quality,
            "summary": summary,
            "positive_signals": positive_signals,
            "risk_factors": risk_factors,
            "metadata_quality": metadata_quality,
            "price_available": price_available,
            "security_checked": security_checked,
            "services_responded": len(service_responses),
            "data_completeness": round(data_quality_score, 1)
        }


# Global analyzer instance
token_analyzer = TokenAnalyzer()


async def analyze_token_from_webhook(token_address: str, event_type: str = "unknown") -> Dict[str, Any]:
    """Analyze token triggered by webhook event"""
    return await token_analyzer.analyze_token_comprehensive(token_address, f"webhook_{event_type}")


async def analyze_token_on_demand(token_address: str) -> Dict[str, Any]:
    """Analyze token on demand (API call)"""
    return await token_analyzer.analyze_token_comprehensive(token_address, "api_request")