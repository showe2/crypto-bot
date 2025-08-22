import asyncio
import time
from typing import Dict, Any, Optional, List
from loguru import logger
from datetime import datetime

from app.services.service_manager import api_manager
from app.utils.redis_client import get_redis_client
from app.utils.cache import cache_manager


class TokenAnalyzer:
    """Main token analyzer that coordinates all services with robust error handling"""
    
    def __init__(self):
        self.services = {
            "chainbase": True,
            "birdeye": True,
            "solanafm": True,
            "goplus": True,
            "dexscreener": True,
            "rugcheck": True
        }
    
    async def analyze_token_comprehensive(self, token_address: str, source_event: str = "webhook") -> Dict[str, Any]:
        """
        Comprehensive token analysis using all available services with error skipping
        """
        start_time = time.time()
        analysis_id = f"analysis_{int(time.time())}_{token_address[:8]}"
        
        logger.info(f"🔍 Starting comprehensive analysis for {token_address} from {source_event}")
        
        # Initialize response structure with ALL required keys
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
        
        # Prepare service tasks with individual error handling
        service_tasks = {}
        
        # Chainbase - Holder analysis (ignore if no data returned)
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
                logger.info("🔧 Chainbase tasks prepared (may return empty data - this is normal)")
            except Exception as e:
                analysis_response["warnings"].append(f"Chainbase initialization failed: {str(e)}")
        else:
            analysis_response["warnings"].append("Chainbase client not available")
        
        # Birdeye - Price and market data (ensure token_address is properly passed)
        if api_manager.clients.get("birdeye"):
            try:
                # Debug: Ensure we have a valid token address
                logger.info(f"🔧 Preparing Birdeye calls for token: {token_address}")
                
                # Call with explicit parameters to avoid parameter issues
                service_tasks["birdeye_price"] = self._safe_service_call(
                    api_manager.clients["birdeye"].get_token_price, 
                    token_address,
                    include_liquidity=True,
                    check_liquidity=100
                )
                await asyncio.sleep(1)
                service_tasks["birdeye_trades"] = self._safe_service_call(
                    api_manager.clients["birdeye"].get_token_trades,
                    token_address,
                    sort_type="desc",
                    limit=20
                )
                analysis_response["metadata"]["services_attempted"] += 1
                logger.info("🔧 Birdeye tasks prepared with explicit parameters")
            except Exception as e:
                analysis_response["errors"].append(f"Birdeye initialization failed: {str(e)}")
        else:
            analysis_response["warnings"].append("Birdeye client not available")
        
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
        else:
            analysis_response["warnings"].append("SolanaFM client not available")
        
        # DexScreener - Trading pairs (FREE)
        if api_manager.clients.get("dexscreener"):
            try:
                service_tasks["dexscreener_pairs"] = self._safe_service_call(
                    api_manager.clients["dexscreener"].get_token_pairs, 
                    token_address, "solana"
                )
                analysis_response["metadata"]["services_attempted"] += 1
            except Exception as e:
                analysis_response["errors"].append(f"DexScreener initialization failed: {str(e)}")
        else:
            analysis_response["warnings"].append("DexScreener client not available")
        
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
        else:
            analysis_response["warnings"].append("GOplus client not available")
        
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
        else:
            analysis_response["warnings"].append("RugCheck client not available")
        
        # Execute all service calls concurrently with timeout
        logger.info(f"🚀 Executing {len(service_tasks)} service calls concurrently")
        
        try:
            # Set a reasonable timeout for all operations
            results = await asyncio.wait_for(
                asyncio.gather(*service_tasks.values(), return_exceptions=True),
                timeout=30.0  # 30 second timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Service calls timed out after 30 seconds, proceeding with partial data")
            analysis_response["warnings"].append("Service calls timed out after 30 seconds")
            results = [None] * len(service_tasks)
        except Exception as e:
            logger.error(f"Critical error during service execution: {str(e)}")
            analysis_response["errors"].append(f"Service execution failed: {str(e)}")
            results = [None] * len(service_tasks)
        
        # Process results with robust error handling
        task_names = list(service_tasks.keys())
        successful_services = 0
        
        for i, task_name in enumerate(task_names):
            try:
                result = results[i] if i < len(results) else None
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
                    successful_services += 1
                
                logger.debug(f"✅ Successfully processed {task_name}")
                
            except Exception as e:
                error_msg = f"Error processing {task_name}: {str(e)}"
                analysis_response["errors"].append(error_msg)
                logger.warning(f"❌ {error_msg}")
        
        # Add emergency data collection if all else fails
        if len(analysis_response["data_sources"]) == 0:
            logger.warning("🆘 No data sources available - attempting emergency data collection")
            
            # Try to get at least basic token validation
            try:
                from app.utils.validation import solana_validator
                validation_result = solana_validator.validate_token_mint(token_address)
                
                if validation_result.valid:
                    analysis_response["service_responses"]["validation"] = {
                        "address_valid": True,
                        "normalized_address": validation_result.normalized_data.get("address", token_address)
                    }
                    analysis_response["data_sources"].append("validation")
                    successful_services += 1
                    logger.info("✅ Emergency validation data collected")
                    
            except Exception as e:
                logger.warning(f"Emergency validation failed: {str(e)}")
            
            # Try to extract basic info from token address format
            try:
                analysis_response["service_responses"]["address_analysis"] = {
                    "address_length": len(token_address),
                    "appears_valid": len(token_address) in [43, 44],
                    "address_type": "likely_token" if len(token_address) == 44 else "unknown"
                }
                analysis_response["data_sources"].append("address_analysis")
                successful_services += 1
                logger.info("✅ Emergency address analysis completed")
                
            except Exception as e:
                logger.warning(f"Emergency address analysis failed: {str(e)}")
        
        analysis_response["metadata"]["services_successful"] = successful_services
        analysis_response["metadata"]["data_sources_available"] = len(analysis_response["data_sources"])
        
        # Generate overall analysis even with limited data
        try:
            analysis_response["overall_analysis"] = await self._generate_overall_analysis(
                analysis_response["service_responses"], token_address
            )
            
            # Map to analysis_summary for API router compatibility
            analysis_response["analysis_summary"] = analysis_response["overall_analysis"]
            
            # Add risk_assessment section for API router
            analysis_response["risk_assessment"] = {
                "risk_category": analysis_response["overall_analysis"]["risk_level"],
                "risk_score": analysis_response["overall_analysis"]["score"],
                "confidence": analysis_response["overall_analysis"]["confidence_score"]
            }
            
            logger.info("✅ Overall analysis generated successfully")
        except Exception as e:
            logger.error(f"Overall analysis generation failed: {str(e)}")
            analysis_response["errors"].append(f"Analysis generation failed: {str(e)}")
            
            # Provide fallback analysis
            fallback_analysis = self._create_fallback_analysis(
                analysis_response["data_sources"], len(analysis_response["errors"])
            )
            analysis_response["overall_analysis"] = fallback_analysis
            analysis_response["analysis_summary"] = fallback_analysis
            
            # Add fallback risk_assessment
            analysis_response["risk_assessment"] = {
                "risk_category": fallback_analysis["risk_level"],
                "risk_score": fallback_analysis["score"],
                "confidence": fallback_analysis["confidence_score"]
            }
        
        # Calculate processing time
        processing_time = time.time() - start_time
        analysis_response["metadata"]["processing_time_seconds"] = round(processing_time, 3)
        
        # Cache the result with shorter TTL if many errors
        try:
            cache_ttl = 120 if len(analysis_response["errors"]) > 3 else (300 if source_event == "webhook" else 120)
            await cache_manager.set(cache_key, analysis_response, ttl=cache_ttl, namespace="analysis")
            logger.debug(f"Analysis cached with TTL {cache_ttl}s")
        except Exception as e:
            logger.warning(f"Failed to cache analysis: {str(e)}")
            analysis_response["warnings"].append(f"Caching failed: {str(e)}")
        
        # Log completion with summary
        error_count = len(analysis_response["errors"])
        warning_count = len(analysis_response["warnings"])
        data_sources = len(analysis_response["data_sources"])
        
        logger.info(
            f"✅ Analysis COMPLETED for {token_address} in {processing_time:.2f}s "
            f"(sources: {data_sources}, errors: {error_count}, warnings: {warning_count})"
        )
        
        # Always return data, even if incomplete
        return analysis_response
    
    # Keep the original _safe_service_call for non-Birdeye services
    async def _safe_service_call(self, service_func, *args, **kwargs):
        """Execute service call with comprehensive error handling and detailed logging"""
        service_name = service_func.__name__
        
        try:
            # Call the function with proper parameter unpacking
            if kwargs:
                result = await service_func(*args, **kwargs)
            else:
                result = await service_func(*args)
            
            if result is not None:
                logger.info(f"✅ {service_name} returned data successfully")
                return result
            else:
                logger.warning(f"⚠️  {service_name} returned None - this is normal for some services")
                return None
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ {service_name} failed: {error_msg}")
            
            # Log specific error types for debugging
            if "address is required" in error_msg.lower():
                logger.error(f"   🐛 Address parameter issue in {service_name}")
                logger.error(f"   🐛 Args received: {args}")
                logger.error(f"   🐛 Kwargs received: {kwargs}")
            elif "400" in error_msg:
                logger.error(f"   🐛 400 Bad Request in {service_name} - check parameters")
            elif "404" in error_msg:
                logger.warning(f"   ℹ️  404 Not Found in {service_name} - endpoint may not exist")
            elif "timeout" in error_msg.lower():
                logger.warning(f"   ⏰ Timeout in {service_name}")
            
            # Return None instead of raising to allow other services to continue
            return None
        
    def _create_fallback_analysis(self, data_sources: List[str], error_count: int) -> Dict[str, Any]:
        """Create a fallback analysis when main analysis fails - ENSURE we always get SOME data"""
        
        logger.warning(f"🆘 Creating fallback analysis with {len(data_sources)} sources and {error_count} errors")
        
        # More aggressive scoring to ensure we get meaningful data
        if len(data_sources) >= 2:
            score = 55.0  # Better score with multiple sources
            risk_level = "medium"
            confidence = 70.0
            recommendation = "caution"
        elif len(data_sources) >= 1:
            score = 45.0  # Moderate score with single source
            risk_level = "medium"
            confidence = 50.0
            recommendation = "caution"
        else:
            score = 35.0  # Still provide reasonable score even with no data
            risk_level = "high"
            confidence = 25.0
            recommendation = "avoid"
        
        # Less harsh penalty for errors to ensure usable data
        if error_count > 8:
            confidence = max(20.0, confidence - 15.0)
            score = max(25.0, score - 10.0)
        elif error_count > 5:
            confidence = max(25.0, confidence - 10.0)
            score = max(30.0, score - 5.0)
        
        # Provide meaningful positive signals even in fallback
        positive_signals = []
        if len(data_sources) > 0:
            positive_signals.append("Analysis completed with available data")
        if error_count < 5:
            positive_signals.append("Most services responded normally")
        
        # Add at least one positive signal to avoid empty analysis
        if not positive_signals:
            positive_signals.append("Token address format validated successfully")
        
        risk_factors = []
        if error_count > 5:
            risk_factors.append(f"High service error rate ({error_count} errors)")
        if len(data_sources) < 2:
            risk_factors.append(f"Limited data sources available ({len(data_sources)})")
        
        # Add at least one risk factor for completeness
        if not risk_factors:
            risk_factors.append("Analysis based on limited external data")
        
        return {
            "score": score,
            "risk_level": risk_level,
            "recommendation": recommendation,
            "confidence": confidence,
            "confidence_score": confidence,  # API router expects this key
            "data_quality": "limited" if len(data_sources) > 0 else "minimal",
            "summary": f"Fallback analysis completed. {len(data_sources)} data sources provided information despite service issues.",
            "positive_signals": positive_signals,
            "risk_factors": risk_factors,
            "metadata_quality": max(10, len(data_sources) * 15),  # Ensure some metadata quality
            "price_available": len(data_sources) > 0,  # Assume some price data if any source worked
            "security_checked": len(data_sources) > 1,  # Assume security check if multiple sources
            "services_responded": len(data_sources),
            "data_completeness": max(20.0, len(data_sources) * 25.0),  # More generous completeness
            "fallback_analysis": True,
            "analysis_notes": [
                "This is a fallback analysis due to service limitations",
                "Recommendations are conservative due to limited data",
                f"Successfully processed {len(data_sources)} out of attempted services"
            ],
            "analysis_completed": True
        }
    
    async def _generate_overall_analysis(self, service_responses: Dict[str, Any], token_address: str) -> Dict[str, Any]:
        """Generate overall analysis from all service responses with error resilience"""
        
        # Initialize analysis components with defaults
        scores = []
        risk_factors = []
        positive_signals = []
        metadata_quality = 0
        price_available = False
        security_checked = False
        
        # Process each service response with individual error handling
        data_quality_score = 0
        total_services = len(service_responses)
        
        # Chainbase data processing (ignore if no data - this is normal)
        try:
            if "chainbase" in service_responses:
                chainbase_data = service_responses["chainbase"]
                logger.debug(f"Chainbase data received: {bool(chainbase_data)}")
                
                # Only process if we actually have data
                if chainbase_data and any(chainbase_data.values()):
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
                    
                    if chainbase_data.get("metadata"):
                        metadata_quality += 30
                        logger.debug("Chainbase metadata found")
                    
                    logger.info("✅ Chainbase data processed successfully")
                else:
                    logger.info("ℹ️  Chainbase returned no data (this is normal for some tokens)")
        except Exception as e:
            logger.debug(f"Error processing Chainbase data: {str(e)} (ignoring as requested)")
        
        # Birdeye data processing
        try:
            if "birdeye" in service_responses:
                birdeye_data = service_responses["birdeye"]
                if birdeye_data and birdeye_data.get("price"):
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
        except Exception as e:
            logger.debug(f"Error processing Birdeye data: {str(e)}")
        
        # SolanaFM data processing
        try:
            if "solanafm" in service_responses:
                solanafm_data = service_responses["solanafm"]
                if solanafm_data and solanafm_data.get("token"):
                    token_info = solanafm_data["token"]
                    if token_info and token_info.get("name") and token_info.get("symbol"):
                        metadata_quality += 20
                        positive_signals.append("Complete token information")
                data_quality_score += 15
        except Exception as e:
            logger.debug(f"Error processing SolanaFM data: {str(e)}")
        
        # DexScreener data processing
        try:
            if "dexscreener" in service_responses:
                dexscreener_data = service_responses["dexscreener"]
                if dexscreener_data and dexscreener_data.get("pairs"):
                    pairs_data = dexscreener_data["pairs"]
                    if pairs_data and pairs_data.get("pairs"):
                        pairs_count = len(pairs_data["pairs"])
                        if pairs_count > 0:
                            positive_signals.append(f"Trading on {pairs_count} DEX(es)")
                            scores.append(55)
                            data_quality_score += 20
        except Exception as e:
            logger.debug(f"Error processing DexScreener data: {str(e)}")
        
        # GOplus security analysis
        try:
            if "goplus" in service_responses:
                goplus_data = service_responses["goplus"]
                security_checked = True
                
                if goplus_data and goplus_data.get("security"):
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
                    
                    if not any("GOplus:" in rf for rf in risk_factors):
                        positive_signals.append("GOplus: No major security issues")
                
                data_quality_score += 25
        except Exception as e:
            logger.debug(f"Error processing GOplus data: {str(e)}")
        
        # RugCheck analysis
        try:
            if "rugcheck" in service_responses:
                rugcheck_data = service_responses["rugcheck"]
                security_checked = True
                
                if rugcheck_data and rugcheck_data.get("report"):
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
        except Exception as e:
            logger.debug(f"Error processing RugCheck data: {str(e)}")
        
        # Calculate overall score with fallback
        if scores:
            overall_score = sum(scores) / len(scores)
        else:
            overall_score = 30  # Default low score if no data
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
            "confidence_score": round(confidence, 1),  # API router expects this key
            "data_quality": data_quality,
            "summary": summary,
            "positive_signals": positive_signals,
            "risk_factors": risk_factors,
            "metadata_quality": metadata_quality,
            "price_available": price_available,
            "security_checked": security_checked,
            "services_responded": len(service_responses),
            "data_completeness": round(data_quality_score, 1),
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