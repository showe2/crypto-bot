import asyncio
import time
import json
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger
from datetime import datetime

from app.services.service_manager import api_manager
from app.utils.redis_client import get_redis_client
from app.utils.cache import cache_manager
from app.services.analysis_storage import analysis_storage
from app.services.ai.ai_service import analyze_token_with_ai, AIAnalysisResponse


class EnhancedTokenAnalyzer:
    """Enhanced token analyzer with AI integration and deep analysis"""
    
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
    
    async def analyze_token_deep(self, token_address: str, source_event: str = "api_request") -> Dict[str, Any]:
        """
        Perform deep token analysis with AI integration
        
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
        
        # STEP 1: SECURITY CHECKS (same as original)
        logger.info("🛡️ STEP 1: Running security checks (GOplus + RugCheck + SolSniffer)")
        security_passed, security_data = await self._run_security_checks(token_address, analysis_response)
        
        # Store security data
        analysis_response["security_analysis"] = security_data
        analysis_response["metadata"]["security_check_passed"] = security_passed
        
        # STEP 2: Handle security failure (same logic as original)
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
                "risk_score": 10,
                "confidence": 95,
                "reason": "Failed security checks"
            }
            
            processing_time = time.time() - start_time
            analysis_response["metadata"]["processing_time_seconds"] = round(processing_time, 3)
            
            asyncio.create_task(self._store_analysis_async(analysis_response))
            
            logger.warning(f"❌ Analysis STOPPED for {token_address} due to security issues in {processing_time:.2f}s")
            return analysis_response
        
        logger.info(f"✅ SECURITY CHECKS PASSED for {token_address} - CONTINUING WITH DEEP ANALYSIS")
        
        # STEP 3: Run market analysis services (same as original)
        logger.info("📊 STEP 2: Running market and technical analysis services")
        await self._run_market_analysis_services(token_address, analysis_response)
        
        # STEP 4: NEW - AI ANALYSIS WITH LLAMA 3.0
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
        
        # STEP 5: Generate enhanced comprehensive analysis (with AI integration)
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
            ttl = self.cache_ttl.get(source_event, 7200)  # default 2 hours
            await self.cache.set(
                key=cache_key,
                value=analysis_response,
                ttl=ttl,
                namespace=self.cache_namespace
            )
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
        """Run security checks (reuse existing logic from token_analyzer)"""
        from app.services.token_analyzer import token_analyzer
        
        # Use existing security check logic
        return await token_analyzer._run_security_checks(token_address, analysis_response)
    
    async def _run_market_analysis_services(self, token_address: str, analysis_response: Dict[str, Any]) -> None:
        """Run market analysis services (reuse existing logic)"""
        from app.services.token_analyzer import token_analyzer
        
        # Use existing market analysis logic
        await token_analyzer._run_market_analysis_services(token_address, analysis_response)
    
    async def _run_ai_analysis(
        self, 
        token_address: str, 
        service_responses: Dict[str, Any],
        security_data: Dict[str, Any],
        analysis_response: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Run AI analysis using Llama 3.0 with proper null safety
        """
        try:
            logger.info(f"🤖 Starting AI analysis for {token_address}")
            
            # Call AI service
            ai_result = await analyze_token_with_ai(
                token_address=token_address,
                service_responses=service_responses,
                security_analysis=security_data,
                analysis_type="deep"
            )
            
            # Check if AI analysis succeeded
            if ai_result is None:
                logger.warning(f"AI analysis returned None for {token_address}")
                analysis_response["warnings"].append("AI analysis service unavailable")
                return None
            
            # Convert to dict for storage
            ai_analysis_dict = {
                "ai_score": float(ai_result.ai_score) if ai_result.ai_score is not None else 0.0,
                "risk_assessment": ai_result.risk_assessment or "unknown",
                "recommendation": ai_result.recommendation or "HOLD",
                "confidence": float(ai_result.confidence) if ai_result.confidence is not None else 0.0,
                "key_insights": ai_result.key_insights or [],
                "risk_factors": ai_result.risk_factors or [],
                "stop_flags": ai_result.stop_flags or [],
                "market_metrics": ai_result.market_metrics or {},
                "llama_reasoning": ai_result.llama_reasoning or "No reasoning provided",
                "processing_time": float(ai_result.processing_time) if ai_result.processing_time is not None else 0.0,
                "model_used": "llama-3.0-70b-instruct",
                "analysis_successful": True
            }
            
            logger.info(f"✅ AI analysis completed: Score {ai_result.ai_score}, Recommendation {ai_result.recommendation}")
            
            return ai_analysis_dict
            
        except Exception as e:
            logger.error(f"❌ AI analysis failed for {token_address}: {str(e)}")
            analysis_response["errors"].append(f"AI analysis failed: {str(e)}")
            
            # Return None instead of empty dict to clearly indicate failure
            return None
    
    async def _generate_enhanced_comprehensive_analysis(
        self, 
        service_responses: Dict[str, Any], 
        security_data: Dict[str, Any], 
        ai_analysis: Optional[Dict[str, Any]],
        token_address: str
    ) -> Dict[str, Any]:
        """
        Generate enhanced comprehensive analysis that combines traditional analysis with AI insights
        Enhanced with proper null safety for AI analysis
        """
        # Start with traditional analysis
        from app.services.token_analyzer import token_analyzer
        traditional_analysis = await token_analyzer._generate_comprehensive_analysis(
            service_responses, security_data, token_address
        )
        
        # If no AI analysis available, return traditional analysis with AI enhancement flag
        if not ai_analysis or not isinstance(ai_analysis, dict):
            logger.warning("No AI analysis available, using traditional analysis only")
            traditional_analysis["ai_enhanced"] = False
            traditional_analysis["ai_available"] = False
            traditional_analysis["ai_reason"] = "AI analysis service unavailable"
            return traditional_analysis
        
        # Verify AI analysis has required fields
        if not ai_analysis.get("analysis_successful"):
            logger.warning("AI analysis marked as unsuccessful")
            traditional_analysis["ai_enhanced"] = False
            traditional_analysis["ai_available"] = False
            traditional_analysis["ai_reason"] = "AI analysis failed"
            return traditional_analysis
        
        # Enhance with AI insights
        logger.info("🧠 Enhancing analysis with AI insights")
        
        # AI-enhanced scoring system with safe extraction
        traditional_score = float(traditional_analysis.get("score", 60))
        ai_score = float(ai_analysis.get("ai_score", 50)) if ai_analysis.get("ai_score") is not None else 50.0
        
        # Weighted combination: 60% traditional, 40% AI
        enhanced_score = (traditional_score * 0.6) + (ai_score * 0.4)
        
        # AI recommendation takes precedence for critical issues
        ai_recommendation = ai_analysis.get("recommendation", "HOLD") or "HOLD"
        traditional_recommendation = traditional_analysis.get("recommendation", "consider")
        
        # Map AI recommendations to traditional format
        ai_to_traditional = {
            "BUY": "consider",
            "CONSIDER": "consider", 
            "HOLD": "caution",
            "CAUTION": "caution",
            "AVOID": "avoid"
        }
        
        enhanced_recommendation = ai_to_traditional.get(ai_recommendation, traditional_recommendation)
        
        # Risk level enhancement with safe extraction
        ai_risk = ai_analysis.get("risk_assessment", "medium") or "medium"
        traditional_risk = traditional_analysis.get("risk_level", "medium")
        
        # AI takes precedence for high/critical risk
        if ai_risk in ["high", "critical"]:
            enhanced_risk = ai_risk
        elif ai_risk == "low" and traditional_risk in ["medium", "high"]:
            enhanced_risk = "low"  # AI confidence in low risk
        else:
            enhanced_risk = traditional_risk
        
        # Combine insights with safe list operations
        traditional_positives = traditional_analysis.get("positive_signals", []) or []
        ai_insights = ai_analysis.get("key_insights", []) or []
        combined_positive_signals = list(set(traditional_positives + ai_insights))
        
        traditional_risks = traditional_analysis.get("risk_factors", []) or []
        ai_risk_factors = ai_analysis.get("risk_factors", []) or []
        combined_risk_factors = list(set(traditional_risks + ai_risk_factors))
        
        # Add AI stop flags as critical risk factors with safe list operations
        ai_stop_flags = ai_analysis.get("stop_flags", []) or []
        if ai_stop_flags:
            combined_risk_factors.extend([f"AI Alert: {flag}" for flag in ai_stop_flags])
        
        # Enhanced confidence calculation with safe float conversion
        traditional_confidence = float(traditional_analysis.get("confidence", 70))
        ai_confidence = float(ai_analysis.get("confidence", 70)) if ai_analysis.get("confidence") is not None else 70.0
        
        # Higher confidence if both systems agree
        if abs(traditional_score - ai_score) < 15:
            enhanced_confidence = min(100, max(traditional_confidence, ai_confidence) + 10)
        else:
            enhanced_confidence = (traditional_confidence + ai_confidence) / 2
        
        # Build enhanced analysis with comprehensive null safety
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
            "security_passed": True,
            "services_analyzed": len(service_responses),
            "ai_enhanced": True,
            "ai_available": True,
            "ai_recommendation": ai_recommendation,
            "ai_score": float(ai_analysis.get("ai_score", 0)) if ai_analysis.get("ai_score") is not None else 0.0,
            "ai_reasoning": ai_analysis.get("llama_reasoning", "No reasoning provided") or "No reasoning provided",
            "traditional_score": traditional_score,
            "score_breakdown": {
                "traditional_weight": 0.6,
                "ai_weight": 0.4,
                "traditional_score": traditional_score,
                "ai_score": ai_score,
                "final_score": enhanced_score
            },
            "ai_processing_time": float(ai_analysis.get("processing_time", 0.0)) if ai_analysis.get("processing_time") is not None else 0.0,
            "ai_model": ai_analysis.get("model_used", "llama-3.0-70b-instruct") or "llama-3.0-70b-instruct"
        }
        
        return enhanced_analysis
    
    def _generate_enhanced_summary(
        self, 
        service_responses: Dict[str, Any], 
        ai_analysis: Optional[Dict[str, Any]],
        enhanced_score: float,
        enhanced_risk: str
    ) -> str:
        """Generate enhanced summary with AI insights and null safety"""
        sources_count = len(service_responses)
        
        # Safe extraction of AI recommendation
        ai_recommendation = "UNAVAILABLE"
        if ai_analysis and isinstance(ai_analysis, dict):
            ai_recommendation = ai_analysis.get("recommendation", "HOLD") or "HOLD"
        
        summary_parts = [
            f"AI-Enhanced Analysis: {enhanced_score:.1f}/100 score",
        ]
        
        # Only add AI recommendation if available
        if ai_recommendation != "UNAVAILABLE":
            summary_parts.append(f"AI Recommendation: {ai_recommendation}")
        
        summary_parts.extend([
            f"Risk Level: {enhanced_risk.upper()}",
            f"Data from {sources_count} sources"
        ])
        
        return " | ".join(summary_parts)
    
    async def _generate_security_focused_analysis(self, security_data: Dict[str, Any], token_address: str, passed: bool) -> Dict[str, Any]:
        """Generate security-focused analysis (reuse from token_analyzer)"""
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
        Enhanced analysis result with AI insights
    """
    return await enhanced_token_analyzer.analyze_token_deep(token_address, source_event)