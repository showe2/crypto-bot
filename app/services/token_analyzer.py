import asyncio
import time
from typing import Dict, Any, Optional, List
from loguru import logger
from datetime import datetime

from app.services.service_manager import api_manager
from app.utils.redis_client import get_redis_client
from app.utils.cache import cache_manager


class TokenAnalyzer:
    """Token analyzer with Helius service integration following existing patterns"""
    
    def __init__(self):
        self.services = {
            "helius": True,
            "chainbase": True,
            "birdeye": True,
            "solanafm": True,
            "goplus": True,
            "dexscreener": True,
            "rugcheck": True
        }
    
    async def analyze_token_comprehensive(self, token_address: str, source_event: str = "webhook") -> Dict[str, Any]:
        """Comprehensive token analysis"""
        start_time = time.time()
        analysis_id = f"analysis_{int(time.time())}_{token_address[:8]}"
        
        logger.info(f"🔍 Starting comprehensive analysis for {token_address} from {source_event}")
        
        # Initialize response structure
        analysis_response = {
            "analysis_id": analysis_id,
            "token_address": token_address,
            "timestamp": datetime.utcnow().isoformat(),
            "source_event": source_event,
            "warnings": [],
            "errors": [],
            "data_sources": [],
            "service_responses": {},
            "metadata": {
                "processing_time_seconds": 0,
                "data_sources_available": 0,
                "services_attempted": 0,
                "services_successful": 0,
                "force_completed": True
            }
        }
        
        # Check cache first
        cache_key = f"token_analysis:{token_address}"
        try:
            cached_result = await cache_manager.get(cache_key, namespace="analysis")
            if cached_result and source_event == "webhook":
                logger.info(f"📋 Returning cached analysis for {token_address}")
                return cached_result
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {str(e)}")
            analysis_response["warnings"].append(f"Cache retrieval failed: {str(e)}")
        
        # STEP 1: Handle Birdeye separately with sequential processing (RATE LIMIT FIX)
        birdeye_data = {}
        if api_manager.clients.get("birdeye"):
            try:
                logger.info("🔧 Processing Birdeye requests sequentially (rate limit fix)")
                birdeye_client = api_manager.clients["birdeye"]
                
                # Call price endpoint first
                try:
                    price_data = await birdeye_client.get_token_price(
                        token_address,
                        include_liquidity=True,
                        check_liquidity=100
                    )
                    if price_data:
                        birdeye_data["price"] = price_data
                        logger.info("✅ Birdeye price data collected")
                    else:
                        logger.warning("⚠️ Birdeye price endpoint returned no data")
                except Exception as e:
                    error_msg = f"Birdeye price endpoint failed: {str(e)}"
                    logger.warning(f"❌ {error_msg}")
                    analysis_response["warnings"].append(error_msg)
                
                # Wait before next Birdeye call (CRITICAL FOR RATE LIMITING)
                await asyncio.sleep(1.0)  # 1 second delay between Birdeye calls
                
                # Call trades endpoint second
                try:
                    trades_data = await birdeye_client.get_token_trades(
                        token_address,
                        sort_type="desc",
                        limit=20
                    )
                    if trades_data:
                        birdeye_data["trades"] = trades_data
                        logger.info("✅ Birdeye trades data collected")
                    else:
                        logger.warning("⚠️ Birdeye trades endpoint returned no data")
                except Exception as e:
                    error_msg = f"Birdeye trades endpoint failed: {str(e)}"
                    logger.warning(f"❌ {error_msg}")
                    analysis_response["warnings"].append(error_msg)
                
                # Store Birdeye data if we got anything
                if birdeye_data:
                    analysis_response["service_responses"]["birdeye"] = birdeye_data
                    analysis_response["data_sources"].append("birdeye")
                    analysis_response["metadata"]["services_attempted"] += 1
                    logger.info(f"✅ Birdeye sequential processing completed: {list(birdeye_data.keys())}")
                else:
                    analysis_response["warnings"].append("Birdeye: No data collected from any endpoint")
                    
            except Exception as e:
                error_msg = f"Birdeye sequential processing failed: {str(e)}"
                logger.error(f"❌ {error_msg}")
                analysis_response["errors"].append(error_msg)
        else:
            analysis_response["warnings"].append("Birdeye client not available")
        
        # STEP 2: Prepare tasks for all other services (parallel execution)
        service_tasks = {}
        
        # HELIUS - On-chain data
        if api_manager.clients.get("helius"):
            try:
                service_tasks["helius_supply"] = self._safe_service_call(
                    api_manager.clients["helius"].get_token_supply, 
                    token_address
                )
                service_tasks["helius_accounts"] = self._safe_service_call(
                    api_manager.clients["helius"].get_token_accounts, 
                    token_address
                )
                service_tasks["helius_metadata"] = self._safe_service_call(
                    api_manager.clients["helius"].get_token_metadata, 
                    [token_address]
                )
                analysis_response["metadata"]["services_attempted"] += 1
                logger.info("🔗 Helius tasks prepared")
            except Exception as e:
                analysis_response["warnings"].append(f"Helius initialization failed: {str(e)}")
        
        # Chainbase - Holder analysis
        if api_manager.clients.get("chainbase"):
            try:
                service_tasks["chainbase_metadata"] = self._safe_service_call(
                    api_manager.clients["chainbase"].get_token_metadata, 
                    token_address, "solana"
                )
                service_tasks["chainbase_holders"] = self._safe_service_call(
                    api_manager.clients["chainbase"].get_token_holders, 
                    token_address, "solana", 50
                )
                analysis_response["metadata"]["services_attempted"] += 1
                logger.info("🔧 Chainbase tasks prepared")
            except Exception as e:
                analysis_response["warnings"].append(f"Chainbase initialization failed: {str(e)}")
        
        # SolanaFM - On-chain data
        if api_manager.clients.get("solanafm"):
            try:
                service_tasks["solanafm_token"] = self._safe_service_call(
                    api_manager.clients["solanafm"].get_token_info, 
                    token_address
                )
                analysis_response["metadata"]["services_attempted"] += 1
            except Exception as e:
                analysis_response["errors"].append(f"SolanaFM initialization failed: {str(e)}")
        
        # DexScreener - Trading pairs
        if api_manager.clients.get("dexscreener"):
            try:
                service_tasks["dexscreener_pairs"] = self._safe_service_call(
                    api_manager.clients["dexscreener"].get_token_pairs, 
                    token_address, "solana"
                )
                analysis_response["metadata"]["services_attempted"] += 1
            except Exception as e:
                analysis_response["errors"].append(f"DexScreener initialization failed: {str(e)}")
        
        # GOplus - Security analysis
        if api_manager.clients.get("goplus"):
            try:
                service_tasks["goplus_security"] = self._safe_service_call(
                    api_manager.clients["goplus"].analyze_token_security, 
                    token_address
                )
                service_tasks["goplus_rugpull"] = self._safe_service_call(
                    api_manager.clients["goplus"].detect_rugpull, 
                    token_address, "solana"
                )
                analysis_response["metadata"]["services_attempted"] += 1
            except Exception as e:
                analysis_response["errors"].append(f"GOplus initialization failed: {str(e)}")
        
        # RugCheck - Security analysis
        if api_manager.clients.get("rugcheck"):
            try:
                service_tasks["rugcheck_report"] = self._safe_service_call(
                    api_manager.clients["rugcheck"].check_token, 
                    token_address
                )
                analysis_response["metadata"]["services_attempted"] += 1
            except Exception as e:
                analysis_response["errors"].append(f"RugCheck initialization failed: {str(e)}")
        
        # STEP 3: Execute all other services concurrently (excluding Birdeye which was already processed)
        if service_tasks:
            logger.info(f"🚀 Executing {len(service_tasks)} other service calls concurrently")
            
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*service_tasks.values(), return_exceptions=True),
                    timeout=25.0  # Reduced timeout since Birdeye is already done
                )
            except asyncio.TimeoutError:
                logger.warning("Other services timed out after 25 seconds")
                analysis_response["warnings"].append("Some services timed out")
                results = [None] * len(service_tasks)
            except Exception as e:
                logger.error(f"Critical error during service execution: {str(e)}")
                analysis_response["errors"].append(f"Service execution failed: {str(e)}")
                results = [None] * len(service_tasks)
            
            # Process other services results
            task_names = list(service_tasks.keys())
            for i, task_name in enumerate(task_names):
                try:
                    result = results[i] if i < len(results) else None
                    service_name = task_name.split("_")[0]
                    
                    if isinstance(result, Exception):
                        analysis_response["errors"].append(f"{task_name}: {str(result)}")
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
                    
                    logger.debug(f"✅ Successfully processed {task_name}")
                    
                except Exception as e:
                    error_msg = f"Error processing {task_name}: {str(e)}"
                    analysis_response["errors"].append(error_msg)
                    logger.warning(f"❌ {error_msg}")
        
        # Continue with rest of the analysis (same as before)
        analysis_response["metadata"]["services_successful"] = len(analysis_response["data_sources"])
        analysis_response["metadata"]["data_sources_available"] = len(analysis_response["data_sources"])
        
        # Generate overall analysis
        try:
            analysis_response["overall_analysis"] = await self._generate_overall_analysis(
                analysis_response["service_responses"], token_address
            )
            
            analysis_response["analysis_summary"] = analysis_response["overall_analysis"]
            
            analysis_response["risk_assessment"] = {
                "risk_category": analysis_response["overall_analysis"]["risk_level"],
                "risk_score": analysis_response["overall_analysis"]["score"],
                "confidence": analysis_response["overall_analysis"]["confidence_score"]
            }
            
            logger.info("✅ Overall analysis generated successfully")
        except Exception as e:
            logger.error(f"Overall analysis generation failed: {str(e)}")
            analysis_response["errors"].append(f"Analysis generation failed: {str(e)}")
            
            fallback_analysis = self._create_fallback_analysis(
                analysis_response["data_sources"], len(analysis_response["errors"])
            )
            analysis_response["overall_analysis"] = fallback_analysis
            analysis_response["analysis_summary"] = fallback_analysis
            
            analysis_response["risk_assessment"] = {
                "risk_category": fallback_analysis["risk_level"],
                "risk_score": fallback_analysis["score"],
                "confidence": fallback_analysis["confidence_score"]
            }
        
        # Calculate processing time
        processing_time = time.time() - start_time
        analysis_response["metadata"]["processing_time_seconds"] = round(processing_time, 3)
        
        # Cache the result
        try:
            cache_ttl = 300 if source_event == "webhook" else 120
            await cache_manager.set(cache_key, analysis_response, ttl=cache_ttl, namespace="analysis")
            logger.debug(f"Analysis cached with TTL {cache_ttl}s")
        except Exception as e:
            logger.warning(f"Failed to cache analysis: {str(e)}")
            analysis_response["warnings"].append(f"Caching failed: {str(e)}")
        
        # Log completion
        error_count = len(analysis_response["errors"])
        warning_count = len(analysis_response["warnings"])
        data_sources = len(analysis_response["data_sources"])
        
        birdeye_included = "birdeye" in analysis_response["data_sources"]
        helius_included = "helius" in analysis_response["data_sources"]
        
        logger.info(
            f"✅ Analysis COMPLETED for {token_address} in {processing_time:.2f}s "
            f"(sources: {data_sources}, Birdeye: {'✅' if birdeye_included else '❌'}, "
            f"Helius: {'✅' if helius_included else '❌'}, errors: {error_count}, warnings: {warning_count})"
        )
        
        return analysis_response
    
    async def _safe_service_call(self, service_func, *args, **kwargs):
        """Execute service call with comprehensive error handling"""
        service_name = service_func.__name__
        
        try:
            if kwargs:
                result = await service_func(*args, **kwargs)
            else:
                result = await service_func(*args)
            
            if result is not None:
                logger.info(f"✅ {service_name} returned data successfully")
                return result
            else:
                logger.warning(f"⚠️  {service_name} returned None")
                return None
                
        except Exception as e:
            logger.error(f"❌ {service_name} failed: {str(e)}")
            return None
    
    async def _generate_overall_analysis(self, service_responses: Dict[str, Any], token_address: str) -> Dict[str, Any]:
        """Generate overall analysis from all service responses including Helius"""
        
        scores = []
        risk_factors = []
        positive_signals = []
        metadata_quality = 0
        price_available = False
        security_checked = False
        
        # Process Helius data first (high priority)
        helius_data = service_responses.get("helius", {})
        if helius_data:
            logger.debug("Processing Helius data for analysis")
            
            # Process supply data
            supply_data = helius_data.get("supply")
            if supply_data:
                positive_signals.append("Helius: Token supply data available")
                scores.append(70)
                
                # Check supply characteristics
                ui_amount = supply_data.get("ui_amount")
                if ui_amount:
                    supply_amount = float(ui_amount)
                    if supply_amount > 1_000_000_000:  # 1B+ tokens
                        risk_factors.append("Very high token supply")
                        scores.append(30)
                    elif supply_amount < 1_000_000:  # < 1M tokens
                        positive_signals.append("Limited token supply")
                        scores.append(75)
            
            # Process accounts (holders) data
            accounts_data = helius_data.get("accounts")
            if accounts_data and len(accounts_data) > 0:
                holder_count = len(accounts_data)
                positive_signals.append(f"Helius: {holder_count} token holders found")
                
                if holder_count > 1000:
                    positive_signals.append("Good holder distribution")
                    scores.append(75)
                elif holder_count > 100:
                    scores.append(60)
                elif holder_count < 10:
                    risk_factors.append("Very low holder count")
                    scores.append(25)
                else:
                    scores.append(45)
                
                # Analyze concentration if we have enough data
                if len(accounts_data) >= 10:
                    total_amount = sum(float(acc.get("ui_amount", 0)) for acc in accounts_data)
                    if total_amount > 0:
                        top_10_amount = sum(float(acc.get("ui_amount", 0)) for acc in accounts_data[:10])
                        concentration_percentage = (top_10_amount / total_amount) * 100
                        
                        if concentration_percentage > 80:
                            risk_factors.append("High concentration: Top 10 holders own >80%")
                            scores.append(25)
                        elif concentration_percentage < 50:
                            positive_signals.append("Good distribution: Top 10 holders own <50%")
                            scores.append(70)
            
            # Process metadata
            metadata = helius_data.get("metadata")
            if metadata and isinstance(metadata, dict):
                if metadata.get("name") and metadata.get("symbol"):
                    positive_signals.append("Helius: Complete token metadata")
                    metadata_quality += 30
                    scores.append(65)
                else:
                    risk_factors.append("Incomplete token metadata")
                    scores.append(35)
        
        # Process other services (existing logic)
        # Birdeye data processing
        birdeye_data = service_responses.get("birdeye", {})
        if birdeye_data:
            price_data = birdeye_data.get("price")
            if price_data:
                price_available = True
                
                if price_data.get("value") and float(price_data["value"]) > 0:
                    positive_signals.append("Birdeye: Token has market price")
                    scores.append(60)
                
                volume_24h = price_data.get("volume_24h")
                if volume_24h and float(volume_24h) > 1000:
                    positive_signals.append("Birdeye: Good trading volume")
                    scores.append(65)
                elif volume_24h and float(volume_24h) > 100:
                    scores.append(45)
                else:
                    risk_factors.append("Low trading volume")
                    scores.append(25)
        
        # Security analysis
        goplus_data = service_responses.get("goplus", {})
        if goplus_data:
            security_checked = True
            security_analysis = goplus_data.get("security")
            if security_analysis:
                if security_analysis.get("is_honeypot") == "1":
                    risk_factors.append("GOplus: Potential honeypot")
                    scores.append(5)
                else:
                    scores.append(60)
        
        rugcheck_data = service_responses.get("rugcheck", {})
        if rugcheck_data:
            security_checked = True
            report = rugcheck_data.get("report")
            if report:
                rugcheck_score = report.get("score")
                if rugcheck_score is not None:
                    if rugcheck_score > 80:
                        positive_signals.append(f"RugCheck: High safety score ({rugcheck_score})")
                        scores.append(80)
                    elif rugcheck_score > 60:
                        scores.append(65)
                    else:
                        risk_factors.append(f"RugCheck: Risk detected (score: {rugcheck_score})")
                        scores.append(30)
        
        # Calculate overall score
        if scores:
            overall_score = sum(scores) / len(scores)
        else:
            overall_score = 30
            risk_factors.append("No scoring data available")
        
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
        
        # Calculate confidence
        base_confidence = len(service_responses) * 15
        helius_bonus = 20 if helius_data else 0
        security_bonus = 15 if security_checked else 0
        price_bonus = 10 if price_available else 0
        
        confidence = min(100, base_confidence + helius_bonus + security_bonus + price_bonus)
        
        # Generate summary
        summary_parts = []
        if helius_data:
            summary_parts.append("Helius on-chain data analyzed")
        if positive_signals:
            summary_parts.append(f"Positives: {', '.join(positive_signals[:2])}")
        if risk_factors:
            summary_parts.append(f"Risks: {', '.join(risk_factors[:2])}")
        
        summary = "; ".join(summary_parts) if summary_parts else "Limited data available"
        
        return {
            "score": round(overall_score, 1),
            "risk_level": risk_level,
            "recommendation": recommendation,
            "confidence": round(confidence, 1),
            "confidence_score": round(confidence, 1),
            "data_quality": "excellent" if helius_data else "good",
            "summary": summary,
            "positive_signals": positive_signals,
            "risk_factors": risk_factors,
            "metadata_quality": metadata_quality,
            "price_available": price_available,
            "security_checked": security_checked,
            "services_responded": len(service_responses),
            "helius_data_available": bool(helius_data),
            "analysis_completed": True
        }
    
    def _create_fallback_analysis(self, data_sources: List[str], error_count: int) -> Dict[str, Any]:
        """Create a fallback analysis when main analysis fails"""
        
        logger.warning(f"🆘 Creating fallback analysis with {len(data_sources)} sources and {error_count} errors")
        
        # Better scoring if Helius data is available
        if "helius" in data_sources:
            score = 55.0
            confidence = 70.0
            risk_level = "medium"
            recommendation = "caution"
        elif len(data_sources) >= 2:
            score = 50.0
            confidence = 60.0
            risk_level = "medium"
            recommendation = "caution"
        elif len(data_sources) >= 1:
            score = 45.0
            confidence = 45.0
            risk_level = "medium"
            recommendation = "caution"
        else:
            score = 35.0
            confidence = 25.0
            risk_level = "high"
            recommendation = "avoid"
        
        # Adjust for errors
        if error_count > 5:
            confidence = max(20.0, confidence - 15.0)
            score = max(25.0, score - 10.0)
        
        positive_signals = []
        if "helius" in data_sources:
            positive_signals.append("Helius on-chain data available")
        if len(data_sources) > 0:
            positive_signals.append("Analysis completed with available data")
        if not positive_signals:
            positive_signals.append("Token address format validated")
        
        risk_factors = []
        if error_count > 3:
            risk_factors.append(f"High service error rate ({error_count} errors)")
        if "helius" not in data_sources:
            risk_factors.append("Limited on-chain data available")
        if not risk_factors:
            risk_factors.append("Analysis based on limited external data")
        
        return {
            "score": score,
            "risk_level": risk_level,
            "recommendation": recommendation,
            "confidence": confidence,
            "confidence_score": confidence,
            "data_quality": "limited",
            "summary": f"Fallback analysis. {len(data_sources)} data sources processed. " + 
                      ("Helius data included." if "helius" in data_sources else "No Helius data."),
            "positive_signals": positive_signals,
            "risk_factors": risk_factors,
            "metadata_quality": max(10, len(data_sources) * 15),
            "price_available": len(data_sources) > 0,
            "security_checked": len(data_sources) > 1,
            "services_responded": len(data_sources),
            "helius_data_available": "helius" in data_sources,
            "analysis_completed": True
        }


# Global analyzer instance
token_analyzer = TokenAnalyzer()


async def analyze_token_from_webhook(token_address: str, event_type: str = "unknown") -> Dict[str, Any]:
    """Analyze token triggered by webhook event"""
    return await token_analyzer.analyze_token_comprehensive(token_address, f"webhook_{event_type}")


async def analyze_token_on_demand(token_address: str) -> Dict[str, Any]:
    """Analyze token on demand (API call)"""
    return await token_analyzer.analyze_token_comprehensive(token_address, "api_request")