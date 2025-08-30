import asyncio
import time
import json
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger
from datetime import datetime, timedelta

from app.utils.redis_client import get_redis_client
from app.utils.cache import cache_manager
from app.services.analysis_storage import analysis_storage
from app.services.ai.ai_service import analyze_token_with_ai, AIAnalysisResponse


class EnhancedTokenAnalyzer:
    """Enhanced token analyzer with proper security stopping and AI integration"""
    
    def __init__(self):
        """Initialize enhanced analyzer"""
        self.cache = cache_manager
        self.cache_namespace = "enhanced_token_analysis"
        self.cache_ttl = {
            "webhook": 7200,  # 2 hours for webhook requests
            "api_request": 3600,  # 1 hour for API requests
            "frontend_quick": 1800,  # 30 minutes for frontend quick
            "frontend_deep": 7200   # 2 hours for frontend deep
        }
        self.services = {
            "helius": True,
            "birdeye": True,
            "solanafm": True,
            "goplus": True,
            "dexscreener": True,
            "rugcheck": True,
            "solsniffer": True
        }

    async def _cache_analysis_for_docx(self, analysis_response: Dict[str, Any]) -> str:
        """Cache analysis data for DOCX generation with 2-hour TTL"""
        try:
            from app.utils.redis_client import get_redis_client
            
            redis_client = await get_redis_client()
            
            # Generate cache key
            token_address = analysis_response.get("token_address", "unknown")
            timestamp = int(time.time())
            cache_key = f"analysis_docx:{token_address}:{timestamp}"
            
            # Store for 2 hours
            import json
            success = await redis_client.set(
                cache_key, 
                json.dumps(analysis_response), 
                ex=7200  # 2 hours
            )
            
            if success:
                logger.info(f"Cached analysis for DOCX generation: {cache_key}")
                return cache_key
            else:
                logger.warning("Failed to cache analysis for DOCX")
                return None
                
        except Exception as e:
            logger.error(f"Failed to cache analysis for DOCX: {str(e)}")
            return None
        
    async def analyze_token_deep(self, token_address: str, source_event: str = "api_request") -> Dict[str, Any]:
        """
        Perform deep token analysis with AI integration - STOPS on security failure
        
        Flow: Security checks -> Market analysis -> AI analysis -> Storage -> Response
        """
        start_time = time.time()
        analysis_id = f"deep_analysis_{int(time.time())}_{token_address[:8]}"
        
        # Initialize response structure
        analysis_response = {
            "analysis_id": analysis_id,
            "token_address": token_address,
            "timestamp": datetime.utcnow().isoformat(),
            "source_event": source_event,
            "analysis_type": "deep",
            "warnings": [],
            "errors": [],
            "data_sources": [],
            "service_responses": {},
            "security_analysis": {},
            "ai_analysis": {},
            "metadata": {
                "processing_time_seconds": 0,
                "data_sources_available": 0,
                "services_attempted": 0,
                "services_successful": 0,
                "security_check_passed": False,
                "analysis_stopped_at_security": False,
                "ai_analysis_completed": False
            }
        }
        
        # Check cache first
        cache_key = f"deep_analysis:{token_address}"
        try:
            cached_result = await self.cache.get(
                key=cache_key, 
                namespace=self.cache_namespace
            )
            if cached_result:
                logger.info(f"Found cached deep analysis for {token_address}")
                return cached_result
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {str(e)}")
            analysis_response["warnings"].append(f"Cache retrieval failed: {str(e)}")
        
        # STEP 1: SECURITY CHECKS (using existing token_analyzer logic)
        logger.info("🛡️ STEP 1: Running security checks (GOplus + RugCheck + SolSniffer)")
        security_passed, security_data = await self._run_security_checks(token_address, analysis_response)
        
        # Store security data
        analysis_response["security_analysis"] = security_data
        analysis_response["metadata"]["security_check_passed"] = security_passed
        
        # STEP 2: STOP ANALYSIS IF SECURITY FAILS (no changes needed - use existing logic)
        if not security_passed:
            logger.warning(f"⚠️ SECURITY CHECK FAILED for {token_address} - STOPPING ANALYSIS")
            analysis_response["metadata"]["analysis_stopped_at_security"] = True
            
            # Generate security-focused analysis and return early
            analysis_response["overall_analysis"] = await self._generate_security_focused_analysis(
                security_data, token_address, False
            )
            analysis_response["analysis_summary"] = analysis_response["overall_analysis"]
            analysis_response["risk_assessment"] = {
                "risk_category": "critical",
                "risk_score": 15,
                "confidence": 95,
                "reason": "Critical security issues detected"
            }
            
            processing_time = time.time() - start_time
            analysis_response["metadata"]["processing_time_seconds"] = round(processing_time, 3)
            
            asyncio.create_task(self._store_analysis_async(analysis_response))
            
            logger.warning(f"❌ Analysis STOPPED for {token_address} due to security issues in {processing_time:.2f}s")
            return analysis_response
        
        logger.info(f"✅ SECURITY CHECKS PASSED for {token_address} - CONTINUING WITH DEEP ANALYSIS")
        
        # STEP 3: Run market analysis services
        logger.info("📊 STEP 2: Running market and technical analysis services")
        await self._run_market_analysis_services(token_address, analysis_response)
        
        # STEP 4: AI ANALYSIS (only if security passed)
        logger.info("🤖 STEP 3: Running AI analysis with Llama 3.0")
        ai_analysis_result = await self._run_ai_analysis(
            token_address, 
            analysis_response["service_responses"],
            security_data,
            analysis_response
        )
        
        # Store AI results
        analysis_response["ai_analysis"] = ai_analysis_result
        analysis_response["metadata"]["ai_analysis_completed"] = bool(ai_analysis_result)
        
        # STEP 5: Generate enhanced comprehensive analysis
        logger.info("🧠 STEP 4: Generating enhanced comprehensive analysis")
        analysis_response["overall_analysis"] = await self._generate_enhanced_comprehensive_analysis(
            analysis_response["service_responses"], 
            security_data, 
            ai_analysis_result,
            token_address
        )
        analysis_response["analysis_summary"] = analysis_response["overall_analysis"]
        analysis_response["risk_assessment"] = {
            "risk_category": analysis_response["overall_analysis"]["risk_level"],
            "risk_score": analysis_response["overall_analysis"]["score"],
            "confidence": analysis_response["overall_analysis"]["confidence_score"],
            "ai_enhanced": bool(ai_analysis_result)
        }
        
        # Calculate processing time and cache result
        processing_time = time.time() - start_time
        analysis_response["metadata"]["processing_time_seconds"] = round(processing_time, 3)
        
        # Cache the result
        try:
            ttl = self.cache_ttl.get(source_event, 7200)
            await self.cache.set(
                key=cache_key,
                value=analysis_response,
                ttl=ttl,
                namespace=self.cache_namespace
            )

            full_cache_key = f"{self.cache_namespace}:{cache_key}"
            analysis_response["docx_cache_key"] = full_cache_key
            analysis_response["docx_expires_at"] = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()

            logger.info(f"💾 Cached deep analysis for {token_address} with TTL {ttl}s")
        except Exception as e:
            logger.warning(f"Failed to cache deep analysis: {str(e)}")
            analysis_response["warnings"].append(f"Caching failed: {str(e)}")
        
        # Store in ChromaDB asynchronously
        asyncio.create_task(self._store_analysis_async(analysis_response))
        
        # Log completion
        logger.info(
            f"✅ DEEP ANALYSIS COMPLETED for {token_address} in {processing_time:.2f}s "
            f"(security passed, AI analysis: {bool(ai_analysis_result)}, sources: {len(analysis_response['data_sources'])})"
        )
        
        return analysis_response
    
    async def _run_security_checks(self, token_address: str, analysis_response: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Run security checks - delegate to existing token_analyzer logic without changes"""
        from app.services.token_analyzer import token_analyzer
        
        # Use the existing security check logic from token_analyzer
        # This already has the proper logic for determining when to stop
        return await token_analyzer._run_security_checks(token_address, analysis_response)
    
    async def _run_market_analysis_services(self, token_address: str, analysis_response: Dict[str, Any]) -> None:
        """Run market analysis services - delegate to existing logic"""
        from app.services.token_analyzer import token_analyzer
        
        await token_analyzer._run_market_analysis_services(token_address, analysis_response)
    
    async def _run_ai_analysis(
        self, 
        token_address: str, 
        service_responses: Dict[str, Any],
        security_data: Dict[str, Any],
        analysis_response: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Run AI analysis - only called if security checks passed
        """
        try:
            logger.info(f"Starting AI analysis for {token_address}")
            
            # Log data availability for transparency
            self._log_data_availability(service_responses)
            
            # Call AI service
            ai_result = await analyze_token_with_ai(
                token_address=token_address,
                service_responses=service_responses,
                security_analysis=security_data,
                analysis_type="deep"
            )
            
            # Handle AI analysis result
            if ai_result is None:
                logger.info(f"AI analysis unavailable for {token_address} - using traditional analysis")
                analysis_response["warnings"].append("AI analysis service temporarily unavailable")
                return None
            
            # Convert to dict for storage
            ai_analysis_dict = {
                "ai_score": float(ai_result.ai_score) if ai_result.ai_score is not None else 65.0,
                "risk_assessment": ai_result.risk_assessment or "medium",
                "recommendation": ai_result.recommendation or "CONSIDER",
                "confidence": float(ai_result.confidence) if ai_result.confidence is not None else 70.0,
                "key_insights": ai_result.key_insights or ["Analysis completed with available data"],
                "risk_factors": ai_result.risk_factors or [],
                "stop_flags": ai_result.stop_flags or [],
                "market_metrics": ai_result.market_metrics or {},
                "llama_reasoning": ai_result.llama_reasoning or "Analysis completed using available market data",
                "processing_time": float(ai_result.processing_time) if ai_result.processing_time is not None else 0.0,
                "model_used": "llama-3.3-70b-versatile",
                "analysis_successful": True,
                "data_driven": True
            }
            
            logger.info(f"✅ AI analysis completed: Score {ai_result.ai_score}, Recommendation {ai_result.recommendation}")
            
            return ai_analysis_dict
            
        except Exception as e:
            logger.error(f"AI analysis failed for {token_address}: {str(e)}")
            analysis_response["errors"].append(f"AI analysis failed: {str(e)}")
            
            # Return None - let traditional analysis handle it
            return None
    
    def _log_data_availability(self, service_responses: Dict[str, Any]) -> None:
        """Log data availability for transparency"""
        logger.info("Data availability summary:")
        
        # Check each service
        for service_name, data in service_responses.items():
            if data:
                if service_name == "birdeye":
                    has_price = bool(data.get("price", {}).get("value"))
                    has_volume = bool(data.get("price", {}).get("volume_24h"))
                    has_liquidity = bool(data.get("price", {}).get("liquidity"))
                    logger.info(f"  {service_name}: Price={has_price}, Volume={has_volume}, Liquidity={has_liquidity}")
                
                elif service_name == "goplus":
                    has_holders = bool(data.get("holder_count"))
                    has_security = bool(data.get("mintable") or data.get("freezable"))
                    logger.info(f"  {service_name}: Holders={has_holders}, Security={has_security}")
                
                elif service_name == "rugcheck":
                    has_score = bool(data.get("score"))
                    has_risks = bool(data.get("risks"))
                    logger.info(f"  {service_name}: Score={has_score}, Risks={has_risks}")
                
                else:
                    logger.info(f"  {service_name}: Available")
            else:
                logger.info(f"  {service_name}: No data")
    
    async def _generate_enhanced_comprehensive_analysis(
        self, 
        service_responses: Dict[str, Any], 
        security_data: Dict[str, Any], 
        ai_analysis: Optional[Dict[str, Any]],
        token_address: str
    ) -> Dict[str, Any]:
        """
        Generate enhanced comprehensive analysis with AI integration
        """
        # Start with traditional analysis
        from app.services.token_analyzer import token_analyzer
        traditional_analysis = await token_analyzer._generate_comprehensive_analysis(
            service_responses, security_data, token_address
        )
        
        # If no AI analysis available, return traditional analysis
        if not ai_analysis or not isinstance(ai_analysis, dict):
            logger.info("No AI analysis available, using traditional analysis")
            traditional_analysis["ai_enhanced"] = False
            traditional_analysis["ai_available"] = False
            traditional_analysis["ai_reason"] = "AI analysis temporarily unavailable"
            return traditional_analysis
        
        # Enhance with AI insights
        logger.info("Enhancing analysis with AI insights")
        
        # Combine scores: 60% traditional (proven), 40% AI (enhancement)
        traditional_score = float(traditional_analysis.get("score", 65))
        ai_score = float(ai_analysis.get("ai_score", 65)) if ai_analysis.get("ai_score") is not None else 65.0
        
        enhanced_score = (traditional_score * 0.6) + (ai_score * 0.4)
        
        # AI recommendation takes priority for critical issues
        ai_recommendation = ai_analysis.get("recommendation", "CONSIDER") or "CONSIDER"
        traditional_recommendation = traditional_analysis.get("recommendation", "consider")
        
        # Check for AI stop flags - these should influence final recommendation
        ai_stop_flags = ai_analysis.get("stop_flags", []) or []
        has_critical_ai_flags = any(
            critical in str(flag).lower() for flag in ai_stop_flags
            for critical in ['mint authority', 'freeze authority', 'rug', 'scam', 'honeypot']
        )
        
        if has_critical_ai_flags:
            enhanced_recommendation = "avoid"
            enhanced_score = min(enhanced_score, 25)  # Cap score if AI found critical issues
        else:
            enhanced_recommendation = self._determine_enhanced_recommendation(
                ai_recommendation, traditional_recommendation, enhanced_score, ai_analysis
            )
        
        # Risk level enhancement
        ai_risk = ai_analysis.get("risk_assessment", "medium") or "medium"
        traditional_risk = traditional_analysis.get("risk_level", "medium")
        
        enhanced_risk = self._determine_enhanced_risk_level(ai_risk, traditional_risk, ai_analysis)
        
        # Combine insights intelligently
        traditional_positives = traditional_analysis.get("positive_signals", []) or []
        ai_insights = ai_analysis.get("key_insights", []) or []
        combined_positive_signals = self._merge_insights(traditional_positives, ai_insights)
        
        traditional_risks = traditional_analysis.get("risk_factors", []) or []
        ai_risk_factors = ai_analysis.get("risk_factors", []) or []
        
        # Add AI stop flags as risk factors if present
        if ai_stop_flags:
            ai_risk_factors.extend([f"AI Alert: {flag}" for flag in ai_stop_flags])
        
        combined_risk_factors = self._merge_insights(traditional_risks, ai_risk_factors)
        
        # Enhanced confidence calculation
        traditional_confidence = float(traditional_analysis.get("confidence", 70))
        ai_confidence = float(ai_analysis.get("confidence", 70)) if ai_analysis.get("confidence") is not None else 70.0
        
        # Confidence boost when both systems agree
        score_agreement = abs(traditional_score - ai_score) < 20
        recommendation_agreement = self._recommendations_align(ai_recommendation, traditional_recommendation)
        
        if score_agreement and recommendation_agreement:
            enhanced_confidence = min(100, max(traditional_confidence, ai_confidence) + 15)
        elif score_agreement or recommendation_agreement:
            enhanced_confidence = min(100, (traditional_confidence + ai_confidence) / 2 + 5)
        else:
            enhanced_confidence = (traditional_confidence + ai_confidence) / 2
        
        # Build enhanced analysis
        enhanced_analysis = {
            "score": round(enhanced_score, 1),
            "risk_level": enhanced_risk,
            "recommendation": enhanced_recommendation,
            "confidence": round(enhanced_confidence, 1),
            "confidence_score": round(enhanced_confidence, 1),
            "summary": self._generate_enhanced_summary(
                service_responses, ai_analysis, enhanced_score, enhanced_risk
            ),
            "positive_signals": combined_positive_signals,
            "risk_factors": combined_risk_factors,
            "security_passed": True,  # Only reached if security passed
            "services_analyzed": len(service_responses),
            "ai_enhanced": True,
            "ai_available": True,
            "ai_recommendation": ai_recommendation,
            "ai_score": float(ai_analysis.get("ai_score", 0)) if ai_analysis.get("ai_score") is not None else 0.0,
            "ai_reasoning": ai_analysis.get("llama_reasoning", "No reasoning provided") or "No reasoning provided",
            "traditional_score": traditional_score,
            "score_breakdown": {
                "traditional_weight": 0.6,  # Traditional gets more weight (proven logic)
                "ai_weight": 0.4,           # AI enhancement
                "traditional_score": traditional_score,
                "ai_score": ai_score,
                "final_score": enhanced_score,
                "agreement_bonus": score_agreement,
                "ai_stop_flags": len(ai_stop_flags)
            },
            "ai_processing_time": float(ai_analysis.get("processing_time", 0.0)) if ai_analysis.get("processing_time") is not None else 0.0,
            "ai_model": ai_analysis.get("model_used", "llama-3.3-70b-versatile") or "llama-3.3-70b-versatile",
            "ai_stop_flags": ai_stop_flags
        }
        
        return enhanced_analysis
    
    def _determine_enhanced_recommendation(
        self, 
        ai_recommendation: str, 
        traditional_recommendation: str, 
        enhanced_score: float,
        ai_analysis: Dict[str, Any]
    ) -> str:
        """Determine enhanced recommendation with intelligent logic"""
        
        # Map AI recommendations to traditional format
        ai_to_traditional = {
            "BUY": "consider",
            "CONSIDER": "consider", 
            "HOLD": "caution",
            "CAUTION": "caution",
            "AVOID": "avoid"
        }
        
        mapped_ai_rec = ai_to_traditional.get(ai_recommendation, "caution")
        
        # If both systems agree, use that recommendation
        if mapped_ai_rec == traditional_recommendation:
            return mapped_ai_rec
        
        # If one is more conservative, go with the more conservative option
        recommendation_hierarchy = {"consider": 3, "caution": 2, "avoid": 1}
        
        traditional_level = recommendation_hierarchy.get(traditional_recommendation, 2)
        ai_level = recommendation_hierarchy.get(mapped_ai_rec, 2)
        
        # Use the more conservative recommendation
        final_level = min(traditional_level, ai_level)
        
        for rec, level in recommendation_hierarchy.items():
            if level == final_level:
                return rec
        
        return "caution"  # Safe fallback
    
    def _determine_enhanced_risk_level(
        self, 
        ai_risk: str, 
        traditional_risk: str, 
        ai_analysis: Dict[str, Any]
    ) -> str:
        """Determine enhanced risk level"""
        
        # AI stop flags override everything
        ai_stop_flags = ai_analysis.get("stop_flags", [])
        if ai_stop_flags:
            return "critical"
        
        # Take the higher (more conservative) risk assessment
        risk_hierarchy = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        
        ai_risk_level = risk_hierarchy.get(ai_risk, 2)
        traditional_risk_level = risk_hierarchy.get(traditional_risk, 2)
        
        max_risk_level = max(ai_risk_level, traditional_risk_level)
        
        # Convert back to string
        for risk_name, level in risk_hierarchy.items():
            if level == max_risk_level:
                return risk_name
        
        return "medium"
    
    def _merge_insights(self, list1: List[str], list2: List[str]) -> List[str]:
        """Merge two lists of insights, removing duplicates"""
        combined = list(list1)
        
        for item in list2:
            if item not in combined:
                combined.append(item)
        
        return combined
    
    def _recommendations_align(self, ai_rec: str, traditional_rec: str) -> bool:
        """Check if AI and traditional recommendations are aligned"""
        
        # Map to risk levels
        risk_mapping = {
            "BUY": 1, "consider": 1,
            "CONSIDER": 2, "HOLD": 2,
            "caution": 3, "CAUTION": 3,
            "AVOID": 4, "avoid": 4
        }
        
        ai_risk_level = risk_mapping.get(ai_rec, 2)
        traditional_risk_level = risk_mapping.get(traditional_rec, 2)
        
        # Consider aligned if within 1 level of each other
        return abs(ai_risk_level - traditional_risk_level) <= 1
    
    def _generate_enhanced_summary(
        self, 
        service_responses: Dict[str, Any], 
        ai_analysis: Optional[Dict[str, Any]],
        enhanced_score: float,
        enhanced_risk: str
    ) -> str:
        """Generate enhanced summary with AI insights"""
        sources_count = len(service_responses)
        
        summary_parts = [
            f"AI-Enhanced Analysis: {enhanced_score:.1f}/100"
        ]
        
        # Add AI recommendation if available
        if ai_analysis and isinstance(ai_analysis, dict):
            ai_recommendation = ai_analysis.get("recommendation", "HOLD") or "HOLD"
            summary_parts.append(f"AI Recommendation: {ai_recommendation}")
        
        summary_parts.extend([
            f"Risk: {enhanced_risk.upper()}",
            f"{sources_count} data sources"
        ])
        
        # Add AI stop flags warning if present
        ai_stop_flags = ai_analysis.get("stop_flags", []) if ai_analysis else []
        if ai_stop_flags:
            summary_parts.append(f"AI ALERTS: {len(ai_stop_flags)}")
        
        return " | ".join(summary_parts)
    
    async def _generate_security_focused_analysis(self, security_data: Dict[str, Any], token_address: str, passed: bool) -> Dict[str, Any]:
        """Generate security-focused analysis - delegate to existing logic"""
        from app.services.token_analyzer import token_analyzer
        return await token_analyzer._generate_security_focused_analysis(security_data, token_address, passed)
    
    async def _store_analysis_async(self, analysis_response: Dict[str, Any]) -> None:
        """Store analysis in ChromaDB asynchronously"""
        try:
            success = await analysis_storage.store_analysis(analysis_response)
            if success:
                logger.debug(f"Deep analysis stored in ChromaDB: {analysis_response.get('analysis_id')}")
            else:
                logger.debug(f"ChromaDB storage skipped for: {analysis_response.get('analysis_id')}")
        except Exception as e:
            logger.warning(f"ChromaDB storage error: {str(e)}")


# Global enhanced analyzer instance
enhanced_token_analyzer = EnhancedTokenAnalyzer()


async def analyze_token_deep_comprehensive(token_address: str, source_event: str = "api_request") -> Dict[str, Any]:
    """
    Perform deep comprehensive token analysis with AI integration
    
    Args:
        token_address: Token mint address
        source_event: Source of analysis request
    
    Returns:
        Enhanced analysis result with AI insights (only if security passes)
    """
    return await enhanced_token_analyzer.analyze_token_deep(token_address, source_event)