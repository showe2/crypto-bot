from typing import Dict, Any, Optional
import random
import time
from loguru import logger

from .base_profile import BaseAnalysisProfile
from app.models.analysis_models import AnalysisRunResponse


class TwitterAnalysisProfile(BaseAnalysisProfile):
    """Social media analysis profile for trending tokens"""
    
    profile_name = "Twitter Analysis"
    analysis_type = "twitter"
    required_services = ["birdeye", "goplus"]  # Basic security + price
    ai_focus_areas = ["social_metrics", "viral_potential", "community_sentiment"]
    
    async def analyze(self, token_address: str, filters: Optional[Dict] = None, **kwargs) -> AnalysisRunResponse:
        """Analyze token for social media potential"""
        self.start_time = time.time()
        
        logger.info(f"🐦 Starting Twitter analysis for {token_address}")
        
        # Gather service data
        service_data = await self._gather_service_data(token_address)
        
        # Generate dummy social data
        social_data = self._generate_dummy_social_data(token_address)
        service_data["social_metrics"] = social_data
        
        # Run AI analysis
        ai_data = await self._run_ai_analysis(token_address, service_data)
        
        # Extract token info
        token_info = self._extract_token_info(service_data)
        
        # Calculate metrics
        overall_score = self._calculate_social_score(service_data, ai_data)
        risk_level = self._determine_risk_level(overall_score, ai_data)
        recommendation = self._determine_recommendation(overall_score, risk_level, ai_data)
        
        # Build response
        response = AnalysisRunResponse(
            analysis_type=self.analysis_type,
            token_address=token_address,
            token_symbol=token_info["symbol"],
            token_name=token_info["name"],
            overall_score=overall_score,
            risk_level=risk_level,
            recommendation=recommendation,
            security_status="passed",  # Basic assumption for Twitter analysis
            critical_issues=0,
            warnings=len(service_data.get("errors", [])),
            processing_time=round(time.time() - self.start_time, 2),
            profile_data={
                "social_metrics": social_data,
                "ai_analysis": ai_data,
                "services_data": {k: v for k, v in service_data.items() if not k.startswith("services_")}
            }
        )
        
        # Store analysis with comprehensive format
        await self._store_analysis(response, service_data, ai_data)
        
        logger.info(f"✅ Twitter analysis completed: {overall_score}% score, {recommendation}")
        return response
    
    def _generate_dummy_social_data(self, token_address: str) -> Dict[str, Any]:
        """Generate realistic dummy social data"""
        # Seed random with token address for consistency
        random.seed(hash(token_address) % 2**32)
        
        return {
            "followers": random.randint(1000, 100000),
            "mentions_24h": random.randint(10, 500),
            "sentiment_score": round(random.uniform(0.3, 0.9), 2),
            "viral_score": round(random.uniform(0.1, 0.8), 2),
            "trending_rank": random.randint(1, 100),
            "hashtag_count": random.randint(5, 50),
            "community_engagement": round(random.uniform(0.2, 0.9), 2),
            "influencer_mentions": random.randint(0, 15),
            "social_volume_24h": random.randint(100, 5000)
        }
    
    def _calculate_social_score(self, service_data: Dict[str, Any], ai_data: Optional[Dict[str, Any]]) -> float:
        """Calculate score focusing on social metrics"""
        base_score = 50.0
        
        social_metrics = service_data.get("social_metrics", {})
        
        # Social scoring
        if social_metrics:
            # Viral score contribution (0-25 points)
            viral_score = social_metrics.get("viral_score", 0)
            base_score += viral_score * 25
            
            # Sentiment contribution (0-15 points)
            sentiment = social_metrics.get("sentiment_score", 0.5)
            base_score += (sentiment - 0.5) * 30  # Scale from -15 to +15
            
            # Community engagement (0-10 points)
            engagement = social_metrics.get("community_engagement", 0)
            base_score += engagement * 10
        
        # AI enhancement
        if ai_data and ai_data.get("ai_score"):
            ai_score = float(ai_data["ai_score"])
            base_score = (base_score * 0.6) + (ai_score * 0.4)  # 60/40 blend
        
        return min(100.0, max(0.0, base_score))
    
    async def build_ai_prompt(self, token_address: str, service_data: Dict[str, Any]) -> str:
        """Build Twitter-focused AI prompt with safe formatting"""
        social_data = service_data.get("social_metrics", {})
        price_data = service_data.get("birdeye", {}).get("price", {}) if service_data.get("birdeye") else {}
        
        # Safe value extraction with defaults
        followers = social_data.get('followers', 0) or 0
        mentions_24h = social_data.get('mentions_24h', 0) or 0
        sentiment_score = social_data.get('sentiment_score', 0) or 0
        viral_score = social_data.get('viral_score', 0) or 0
        community_engagement = social_data.get('community_engagement', 0) or 0
        
        price_value = price_data.get('value', 0) or 0
        volume_24h = price_data.get('volume_24h', 0) or 0
        liquidity = price_data.get('liquidity', 0) or 0
        
        prompt = f"""
    TWITTER SOCIAL ANALYSIS for {token_address}

    SOCIAL DATA AVAILABLE:
    - Followers: {followers:,}
    - 24h Mentions: {mentions_24h}
    - Sentiment Score: {sentiment_score:.2f}
    - Viral Score: {viral_score:.2f}
    - Community Engagement: {community_engagement:.2f}

    MARKET DATA:
    - Price: ${price_value:.8f}
    - Volume 24h: ${volume_24h:,.0f}
    - Liquidity: ${liquidity:,.0f}

    Focus on social metrics and viral potential. Analyze the social momentum and community strength.

    Respond ONLY with JSON matching this structure:
    {{
    "social_score": 0-100,
    "viral_potential": "low|medium|high",
    "community_strength": "weak|moderate|strong", 
    "recommendation": "BUY|CONSIDER|HOLD|CAUTION|AVOID",
    "key_insights": ["list of social insights"],
    "social_risks": ["list of social risks"]
    }}
    """
        return prompt
    
    def get_json_filters(self) -> Dict[str, Any]:
        """Get JSON filters for Twitter analysis"""
        return {
            "focus": ["social_metrics", "viral_indicators", "community_sentiment"],
            "required_fields": ["social_score", "viral_potential", "community_strength"],
            "format": "twitter_analysis"
        }