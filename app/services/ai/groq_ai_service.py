import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger
from groq import AsyncGroq
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()

class AIAnalysisRequest(BaseModel):
    """Pydantic model for AI analysis request"""
    token_address: str
    service_responses: dict
    security_analysis: dict
    analysis_type: str

class AIAnalysisResponse(BaseModel):
    """Pydantic model for AI analysis response"""
    ai_score: float
    risk_assessment: str
    recommendation: str
    confidence: float
    key_insights: List[str]
    risk_factors: List[str]
    stop_flags: List[str]
    market_metrics: dict
    llama_reasoning: str
    processing_time: float

class GroqLlamaService:
    """Groq-powered Llama 3.0 service for token analysis"""
    
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model_name = "llama-3.3-70b-versatile"
        self.max_tokens = 4000
        self.temperature = 0.1
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt for token analysis"""
        return """You are an expert Solana token analyst specializing in meme coin evaluation. Your task is to analyze token data and provide structured investment recommendations.

CRITICAL: You must respond ONLY with valid JSON. No explanations, no markdown, no additional text.

ANALYSIS FRAMEWORK:
Evaluate tokens based on these metrics:

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

SECURITY FLAGS (CRITICAL):
- Mint authority active (can create unlimited tokens)
- Freeze authority active (can freeze accounts)
- LP not locked (rug pull risk)
- High dev holdings (>10%)

RESPONSE FORMAT (JSON ONLY):
{
  "ai_score": 0-100,
  "risk_assessment": "low|medium|high|critical",
  "recommendation": "BUY|CONSIDER|HOLD|CAUTION|AVOID",
  "confidence": 0-100,
  "key_insights": ["insight1", "insight2"],
  "risk_factors": ["risk1", "risk2"],
  "stop_flags": ["flag1", "flag2"],
  "market_metrics": {
    "liquidity_score": 0-100,
    "volume_score": 0-100,
    "holder_distribution": 0-100
  },
  "llama_reasoning": "Brief explanation of analysis"
}

DECISION LOGIC:
- BUY: >80 score, no critical security issues
- CONSIDER: 60-80 score, minor risks acceptable
- HOLD: 40-60 score, mixed signals
- CAUTION: 20-40 score, significant risks
- AVOID: <20 score or any critical security issues"""

    async def analyze_token(self, request: AIAnalysisRequest) -> Optional[AIAnalysisResponse]:
        """Analyze token using Groq LLM"""
        try:
            start_time = datetime.utcnow()
            
            # Access model fields directly
            token_address = request.token_address
            service_responses = request.service_responses
            security_analysis = request.security_analysis
            
            # Build analysis prompt
            prompt = self._build_analysis_prompt(request.dict())
            
            # Call Groq API
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            # Parse response
            ai_response = response.choices[0].message.content
            parsed_response = self._parse_ai_response(ai_response)
            
            # Calculate processing time before creating response
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Create proper AIAnalysisResponse with all fields
            response = AIAnalysisResponse(
                ai_score=parsed_response.get('ai_score', 0.0),
                risk_assessment=parsed_response.get('risk_assessment', 'unknown'),
                recommendation=parsed_response.get('recommendation', 'HOLD'),
                confidence=parsed_response.get('confidence', 0.0),
                key_insights=parsed_response.get('key_insights', []),
                risk_factors=parsed_response.get('risk_factors', []),
                stop_flags=parsed_response.get('stop_flags', []),
                market_metrics=parsed_response.get('market_metrics', {}),
                llama_reasoning=parsed_response.get('llama_reasoning', ''),
                processing_time=processing_time  # Add processing time here
            )
            
            logger.info(f"✅ Groq Llama analysis completed in {processing_time:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"❌ Groq Llama analysis failed: {str(e)}")
            return None
    
    def _build_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Build analysis prompt with token data"""
        return f"""Analyze this Solana token:

TOKEN: {data.get('token_address', 'N/A')}

MARKET DATA:
- Market Cap: ${data.get('market_cap', 0):,.0f}
- Liquidity: ${data.get('liquidity', 0):,.0f}
- Volume 24h: ${data.get('volume_24h', 0):,.0f}
- Price: ${data.get('price_usd', 0):.8f}
- Price Change 24h: {data.get('price_change_24h', 0):+.2f}%

SECURITY:
- LP Burned/Locked: {'Yes' if data.get('lp_burned') else 'No'}
- Mint Authority: {'Active' if data.get('mint_authority') else 'Disabled'}  
- Freeze Authority: {'Active' if data.get('freeze_authority') else 'Disabled'}
- Dev Holdings: {data.get('dev_percent', 0):.1f}%
- Holder Count: {data.get('holder_count', 0):,}

Provide your analysis in the specified JSON format only."""

    def _parse_ai_response(self, ai_response: str):
        """Parse Groq response into structured format"""
        try:
            parsed_data = json.loads(ai_response)
            
            return {
                "ai_score": float(parsed_data.get("ai_score", 50)),
                "risk_assessment": parsed_data.get("risk_assessment", "medium"),
                "recommendation": parsed_data.get("recommendation", "HOLD"),
                "confidence": float(parsed_data.get("confidence", 70)),
                "key_insights": parsed_data.get("key_insights", []),
                "risk_factors": parsed_data.get("risk_factors", []),
                "stop_flags": parsed_data.get("stop_flags", []),
                "market_metrics": parsed_data.get("market_metrics", {}),
                "llama_reasoning": parsed_data.get("llama_reasoning", "Analysis completed"),
                "processing_time": 0.0,
            }
            
        except Exception as e:
            logger.error(f"Failed to parse Groq response: {str(e)}")
            return self._create_fallback_response("unknown", 0.0)
    
    def _create_fallback_response(self, token_address: str, processing_time: float):
        """Create fallback response when analysis fails"""
        return {
            "ai_score": 0.0,
            "risk_assessment": "critical",
            "recommendation": "AVOID",
            "confidence": 0.0,
            "key_insights": [],
            "risk_factors": ["AI analysis failed"],
            "stop_flags": ["Analysis system error"],
            "market_metrics": {},
            "llama_reasoning": "Groq Llama analysis system encountered an error.",
            "processing_time": processing_time,
        }

# Global service instance
groq_llama_service = GroqLlamaService()