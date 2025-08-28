import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()


class AIAnalysisRequest(BaseModel):
    """Request model for AI analysis"""
    token_address: str
    service_responses: Dict[str, Any]
    security_analysis: Dict[str, Any]
    market_data: Dict[str, Any]
    analysis_type: str = "deep"


class AIAnalysisResponse(BaseModel):
    """Response model for AI analysis"""
    ai_score: float  # 0-100
    risk_assessment: str  # low, medium, high, critical
    recommendation: str  # BUY, CONSIDER, HOLD, CAUTION, AVOID
    confidence: float  # 0-100
    key_insights: List[str]
    risk_factors: List[str]
    stop_flags: List[str]
    market_metrics: Dict[str, Any]
    processing_time: float
    llama_reasoning: str


class LlamaAIService:
    """Service for Llama 3.0 AI token analysis"""
    
    def __init__(self):
        self.model_name = "llama-3.0-70b-instruct"  # Configure based on your setup
        self.max_tokens = 4000
        self.temperature = 0.1  # Low temperature for consistent analysis
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt for token analysis"""
        return """You are an expert Solana token analyst specializing in meme coin evaluation. Your task is to analyze token data and provide structured investment recommendations.

ANALYSIS FRAMEWORK:
You must evaluate tokens based on these critical metrics with specific thresholds:

MARKET CAP (MCAP):
- Excellent: <$1M (high growth potential)
- Acceptable: $1M-$10M (moderate growth)
- Poor: >$50M (limited growth)

LIQUIDITY:
- Excellent: $200K-$2M (optimal for pumps)
- Acceptable: $50K-$200K or $2M-$5M
- Poor: <$50K (rug risk) or >$10M (too heavy)

VOLUME/LIQUIDITY RATIO:
- Excellent: >20% (active trading)
- Acceptable: 5-20%
- Poor: <5% (dead token)

TOP 10 HOLDERS:
- Excellent: <15% (fair distribution)
- Acceptable: 15-30%
- Poor: >30% (dump risk)

DEV HOLDINGS:
- Excellent: <5% (safe)
- Acceptable: 5-10% (with vesting)
- Poor: >10% (rug risk)

SNIPERS/BUNDLERS:
- Excellent: <5% (clean launch)
- Acceptable: 5-10%
- Poor: >10% (manipulated)

LP STATUS:
- Excellent: 100% burned/locked
- Acceptable: Locked >6 months
- Poor: Unlocked (rug risk)

HOLDERS COUNT:
- Excellent: >1000 (strong community)
- Acceptable: 300-1000
- Poor: <300 (dead token)

SECURITY FLAGS (STOP FLAGS):
- Tax >5%
- LP not locked
- Mint/freeze authority active
- Transfer restrictions
- Honeypot indicators

RESPONSE FORMAT:
Provide analysis in JSON format with:
- ai_score (0-100): Overall token score
- risk_assessment: "low", "medium", "high", "critical"
- recommendation: "BUY", "CONSIDER", "HOLD", "CAUTION", "AVOID"
- confidence (0-100): Analysis confidence
- key_insights: List of positive factors
- risk_factors: List of concerns
- stop_flags: List of critical red flags
- market_metrics: Key calculated metrics
- llama_reasoning: Detailed explanation of your analysis

DECISION LOGIC:
- BUY: >70% metrics excellent, MCAP <$1M, no stop flags
- CONSIDER: 50-70% metrics good, manageable risks
- HOLD: Mixed signals, wait for better entry
- CAUTION: Multiple risk factors present
- AVOID: Stop flags present or >50% poor metrics

Be strict with security analysis. Any critical security issues should result in AVOID recommendation regardless of other metrics."""

    async def analyze_token(self, request: AIAnalysisRequest) -> AIAnalysisResponse:
        """Perform comprehensive AI analysis of token"""
        start_time = time.time()
        
        try:
            # Extract and structure data for AI analysis
            analysis_data = self._prepare_analysis_data(request)
            
            # Build analysis prompt
            analysis_prompt = self._build_analysis_prompt(analysis_data)
            
            # Call Llama model (using Claude API as proxy for now)
            ai_response = await self._call_llama_model(analysis_prompt)
            
            # Parse and validate response
            parsed_response = self._parse_ai_response(ai_response)
            
            processing_time = time.time() - start_time
            parsed_response.processing_time = processing_time
            
            logger.info(f"AI analysis completed for {request.token_address} in {processing_time:.2f}s")
            
            return parsed_response
            
        except Exception as e:
            logger.error(f"AI analysis failed for {request.token_address}: {str(e)}")
            
            # Return fallback analysis
            return self._create_fallback_response(request.token_address, time.time() - start_time)
    
    def _prepare_analysis_data(self, request: AIAnalysisRequest) -> Dict[str, Any]:
        """Extract and calculate key metrics from service responses"""
        data = {
            "token_address": request.token_address,
            "analysis_type": request.analysis_type
        }
        
        # Extract market data
        if request.service_responses.get("birdeye", {}).get("price"):
            birdeye_price = request.service_responses["birdeye"]["price"]
            data["price_usd"] = birdeye_price.get("value", 0)
            data["price_change_24h"] = birdeye_price.get("price_change_24h", 0)
            data["volume_24h"] = birdeye_price.get("volume_24h", 0)
            data["liquidity"] = birdeye_price.get("liquidity", 0)
            data["market_cap"] = birdeye_price.get("market_cap", 0)
        
        # Extract supply data
        if request.service_responses.get("helius", {}).get("supply"):
            supply_data = request.service_responses["helius"]["supply"]
            data["total_supply"] = supply_data.get("ui_amount", 0)
        
        # Extract holder data from GOplus
        if request.service_responses.get("goplus"):
            goplus_data = request.service_responses["goplus"]
            data["holder_count"] = int(goplus_data.get("holder_count", "0").replace(",", ""))
            
            # Calculate top 10 holders percentage
            if goplus_data.get("holders"):
                top_10_percent = sum(float(holder.get("percent", "0")) for holder in goplus_data["holders"][:10])
                data["top_10_holders_percent"] = top_10_percent
            else:
                data["top_10_holders_percent"] = 0
        
        # Extract RugCheck analysis
        if request.service_responses.get("rugcheck"):
            rugcheck_data = request.service_responses["rugcheck"]
            data["rugcheck_score"] = rugcheck_data.get("score", 0)
            data["rugcheck_risks"] = rugcheck_data.get("risks", [])
            data["lp_holders_count"] = rugcheck_data.get("total_LP_providers", 0)
            
            # Calculate DEV percentage (from creator analysis)
            creator_analysis = rugcheck_data.get("creator_analysis", {})
            if creator_analysis.get("creator_balance"):
                total_supply = data.get("total_supply", 1)
                dev_balance = creator_analysis["creator_balance"]
                data["dev_percent"] = (dev_balance / total_supply) * 100 if total_supply > 0 else 0
            else:
                data["dev_percent"] = 0
        
        # Extract security flags
        data["security_analysis"] = request.security_analysis
        data["mint_authority"] = not (request.security_analysis.get("goplus_result", {}).get("mintable", {}).get("status") == "0")
        data["freeze_authority"] = not (request.security_analysis.get("goplus_result", {}).get("freezable", {}).get("status") == "0")
        data["lp_burned"] = self._check_lp_status(request.service_responses)
        
        # Calculate derived metrics
        if data.get("volume_24h") and data.get("liquidity"):
            data["volume_liquidity_ratio"] = (data["volume_24h"] / data["liquidity"]) * 100
        else:
            data["volume_liquidity_ratio"] = 0
            
        return data
    
    def _check_lp_status(self, service_responses: Dict[str, Any]) -> bool:
        """Check if LP is burned/locked based on available data"""
        # Check RugCheck for LP status
        rugcheck_data = service_responses.get("rugcheck", {})
        if rugcheck_data.get("lockers_data", {}).get("lockers"):
            return True
            
        # Check GOplus for LP holders
        goplus_data = service_responses.get("goplus", {})
        if goplus_data.get("lp_holders"):
            # Check if LP is concentrated in known locker addresses
            for lp_holder in goplus_data["lp_holders"]:
                if float(lp_holder.get("percent", "0")) > 50:
                    # High concentration might indicate locked LP
                    return True
                    
        return False
    
    def _build_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Build analysis prompt for Llama model"""
        prompt = f"""Analyze this Solana token and provide a structured investment recommendation:

TOKEN: {data['token_address']}

MARKET DATA:
- Market Cap: ${data.get('market_cap', 0):,.0f}
- Liquidity: ${data.get('liquidity', 0):,.0f}
- Volume 24h: ${data.get('volume_24h', 0):,.0f}
- Volume/Liquidity Ratio: {data.get('volume_liquidity_ratio', 0):.1f}%
- Price: ${data.get('price_usd', 0):.8f}
- Price Change 24h: {data.get('price_change_24h', 0):+.2f}%

SUPPLY & HOLDERS:
- Total Supply: {data.get('total_supply', 0):,.0f}
- Holder Count: {data.get('holder_count', 0):,}
- Top 10 Holders: {data.get('top_10_holders_percent', 0):.1f}%
- Dev Holdings: {data.get('dev_percent', 0):.1f}%

SECURITY STATUS:
- LP Burned/Locked: {'Yes' if data.get('lp_burned') else 'No'}
- Mint Authority: {'Active' if data.get('mint_authority') else 'Disabled'}
- Freeze Authority: {'Active' if data.get('freeze_authority') else 'Disabled'}
- RugCheck Score: {data.get('rugcheck_score', 0)}

SECURITY ISSUES:
{json.dumps(data.get('security_analysis', {}), indent=2)}

Based on the thresholds in your system prompt, analyze this token and provide your recommendation in the specified JSON format."""

        return prompt
    
    async def _call_llama_model(self, prompt: str) -> str:
        """Call Llama model for analysis (using Claude API as proxy)"""
        try:
            # For now, using Claude API as a proxy - replace with actual Llama API call
            response = await self._call_claude_api(prompt)
            return response
            
        except Exception as e:
            logger.error(f"Llama model call failed: {str(e)}")
            raise
    
    async def _call_claude_api(self, prompt: str) -> str:
        """Call Claude API as proxy for Llama (replace with actual Llama integration)"""
        try:
            import aiohttp
            
            # This is a placeholder - replace with your actual Llama API endpoint
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": self.max_tokens,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                }
                
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"Content-Type": "application/json"},
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["content"][0]["text"]
                    else:
                        raise Exception(f"API call failed: {response.status}")
                        
        except Exception as e:
            logger.error(f"Claude API call failed: {str(e)}")
            raise
    
    def _parse_ai_response(self, ai_response: str) -> AIAnalysisResponse:
        """Parse AI response into structured format"""
        try:
            # Try to extract JSON from response
            if "```json" in ai_response:
                json_start = ai_response.find("```json") + 7
                json_end = ai_response.find("```", json_start)
                json_content = ai_response[json_start:json_end].strip()
            else:
                json_content = ai_response
            
            # Parse JSON response
            parsed_data = json.loads(json_content)
            
            return AIAnalysisResponse(
                ai_score=float(parsed_data.get("ai_score", 50)),
                risk_assessment=parsed_data.get("risk_assessment", "medium"),
                recommendation=parsed_data.get("recommendation", "HOLD"),
                confidence=float(parsed_data.get("confidence", 70)),
                key_insights=parsed_data.get("key_insights", []),
                risk_factors=parsed_data.get("risk_factors", []),
                stop_flags=parsed_data.get("stop_flags", []),
                market_metrics=parsed_data.get("market_metrics", {}),
                llama_reasoning=parsed_data.get("llama_reasoning", "Analysis completed"),
                processing_time=0.0  # Will be set by caller
            )
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {str(e)}")
            logger.debug(f"Raw AI response: {ai_response}")
            
            # Return fallback response
            return AIAnalysisResponse(
                ai_score=50.0,
                risk_assessment="medium",
                recommendation="HOLD",
                confidence=50.0,
                key_insights=["Analysis parsing failed"],
                risk_factors=["Unable to parse AI response"],
                stop_flags=[],
                market_metrics={},
                llama_reasoning=f"Failed to parse AI response: {str(e)}",
                processing_time=0.0
            )
    
    def _create_fallback_response(self, token_address: str, processing_time: float) -> AIAnalysisResponse:
        """Create fallback response when AI analysis fails"""
        return AIAnalysisResponse(
            ai_score=0.0,
            risk_assessment="critical",
            recommendation="AVOID",
            confidence=0.0,
            key_insights=[],
            risk_factors=["AI analysis failed"],
            stop_flags=["Analysis system error"],
            market_metrics={},
            llama_reasoning="AI analysis system encountered an error and could not complete the analysis.",
            processing_time=processing_time
        )


# Global AI service instance
llama_ai_service = LlamaAIService()


async def analyze_token_with_ai(
    token_address: str,
    service_responses: Dict[str, Any],
    security_analysis: Dict[str, Any],
    analysis_type: str = "deep"
) -> AIAnalysisResponse:
    """
    Perform AI analysis of token using Llama 3.0
    
    Args:
        token_address: Token mint address
        service_responses: Raw responses from all API services
        security_analysis: Security analysis results
        analysis_type: Type of analysis (deep/quick)
    
    Returns:
        AIAnalysisResponse with AI recommendations
    """
    request = AIAnalysisRequest(
        token_address=token_address,
        service_responses=service_responses,
        security_analysis=security_analysis,
        market_data={},  # Will be extracted from service_responses
        analysis_type=analysis_type
    )
    
    return await llama_ai_service.analyze_token(request)


# Health check function
async def check_ai_service_health() -> Dict[str, Any]:
    """Check AI service health"""
    try:
        # Test with minimal data
        test_request = AIAnalysisRequest(
            token_address="test",
            service_responses={},
            security_analysis={},
            market_data={}
        )
        
        start_time = time.time()
        # Don't actually call the AI for health check, just validate setup
        response_time = time.time() - start_time
        
        return {
            "healthy": True,
            "model_name": llama_ai_service.model_name,
            "response_time": response_time,
            "status": "AI service ready"
        }
        
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "status": "AI service error"
        }