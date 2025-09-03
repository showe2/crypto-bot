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
    """Groq-powered Llama 3.0 service for token analysis with multi-source data aggregation"""
    
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model_name = "llama-3.3-70b-versatile"
        self.max_tokens = 4000
        self.temperature = 0.1
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt for token analysis"""
        return """You are an expert Solana token analyst specializing in cryptocurrency evaluation with multi-source data aggregation capabilities. Your task is to analyze token data from multiple sources and provide structured investment recommendations with realistic expectations about data availability.

CRITICAL: You must respond ONLY with valid JSON. No explanations, no markdown, no additional text.

ENHANCED MULTI-SOURCE ANALYSIS FRAMEWORK:
You will receive data aggregated from multiple sources. When multiple sources provide the same metric, trust has been established through cross-verification.

MARKET DATA ASSESSMENT (Multi-Source Enhanced):
- Price data from multiple sources = Higher confidence
- Single source price = Lower confidence but still usable
- Volume/Liquidity cross-confirmed = More reliable metrics
- Market cap verified across sources = Better accuracy assessment

CONFIDENCE SCALING WITH SOURCES:
- Multi-source confirmation: +20 confidence points
- Single reliable source: Baseline confidence
- Cross-source contradictions: -10 confidence points
- Source attribution provided: +5 confidence points

LIQUIDITY ASSESSMENT (Enhanced):
- Excellent: $500K+ confirmed across sources
- Good: $100K-$500K from reliable source
- Acceptable: $25K-$100K single source
- Poor: <$25K or conflicting data

HOLDER ANALYSIS (Multi-Source):
- Multiple holder data sources = Higher accuracy
- GOplus + RugCheck confirmation = Most reliable
- LP provider data supplements holder analysis
- Cross-reference distribution metrics when available

SECURITY PRIORITIES (Critical Only):
- Active mint authority - CRITICAL
- Active freeze authority - CRITICAL  
- Verified rug pull evidence - CRITICAL
- Multi-source security confirmation - CRITICAL

DATA QUALITY PHILOSOPHY:
- Aggregated data > Single source data
- Filtered dummy responses improve accuracy
- Source attribution builds confidence
- Multi-source gaps indicate genuine data unavailability

RESPONSE FORMAT (JSON ONLY):
{
  "ai_score": 0-100,
  "risk_assessment": "low|medium|high|critical", 
  "recommendation": "BUY|CONSIDER|HOLD|CAUTION|AVOID",
  "confidence": 0-100,
  "key_insights": ["positive factors with source attribution"],
  "risk_factors": ["actual concerns, not data gaps"],
  "stop_flags": ["critical security issues only"],
  "market_metrics": {
    "data_quality": 0-100,
    "multi_source_score": 0-100,
    "source_reliability": 0-100
  },
  "llama_reasoning": "Brief explanation emphasizing multi-source validation"
}

ENHANCED DECISION LOGIC:
- BUY: >85 score with multi-source confirmation
- CONSIDER: 70-85 score with good source coverage
- HOLD: 50-70 score or single-source limitations
- CAUTION: 30-50 score with some concerns
- AVOID: <30 score or critical security issues

Remember: Multi-source data validation significantly improves analysis accuracy and confidence."""

    async def send_request(self, prompt: str) -> Optional[AIAnalysisResponse]:
        """Analyze token using Groq LLM with enhanced multi-source data processing"""
        try:
            # Call Groq API
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Enhanced Groq Llama analysis failed: {str(e)}")

# Global service instance
groq_llama_service = GroqLlamaService()