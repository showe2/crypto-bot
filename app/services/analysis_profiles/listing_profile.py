from typing import Dict, Any, Optional, List
from loguru import logger
import time
from datetime import datetime, timedelta

from .base_profile import BaseAnalysisProfile
from app.models.analysis_models import AnalysisRunResponse


class ListingAnalysisProfile(BaseAnalysisProfile):
    """New token listings and early opportunity analysis"""
    
    profile_name = "Listing Analysis"
    analysis_type = "listing"
    required_services = ["birdeye", "dexscreener", "goplus"]
    ai_focus_areas = ["listing_potential", "early_opportunity", "growth_metrics"]
    
    async def analyze(self, token_address: str, filters: Optional[Dict] = None, **kwargs) -> AnalysisRunResponse:
        """Analyze new listings and opportunities"""
        self.start_time = time.time()
        
        logger.info(f"🆕 Starting Listing analysis for {token_address}")
        
        # Gather service data
        service_data = await self._gather_service_data(token_address)
        
        # Analyze listing characteristics
        listing_data = self._analyze_listing_opportunity(service_data)
        service_data["listing_analysis"] = listing_data
        
        # Run AI analysis
        ai_data = await self._run_ai_analysis(token_address, service_data)
        
        # Extract token info
        token_info = self._extract_token_info(service_data)
        
        # Calculate metrics
        overall_score = self._calculate_listing_score(service_data, ai_data)
        risk_level = self._determine_listing_risk(listing_data, ai_data)
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
            security_status="warning",  # New listings are inherently risky
            critical_issues=0,
            warnings=len(listing_data.get("warnings", [])),
            processing_time=round(time.time() - self.start_time, 2),
            profile_data={
                "listing_metrics": listing_data,
                "ai_analysis": ai_data,
                "services_data": {k: v for k, v in service_data.items() if not k.startswith("services_")}
            }
        )
        
        # Store analysis with comprehensive format
        await self._store_analysis(response, service_data, ai_data)
        
        logger.info(f"✅ Listing analysis completed: {listing_data.get('listing_quality', 'unknown')} quality")
        return response
    
    def _analyze_listing_opportunity(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze new listing characteristics"""
        listing_data = {
            "listing_age_hours": 0,
            "early_opportunity": "unknown",
            "growth_potential": "medium",
            "listing_quality": "unknown",
            "initial_liquidity": 0.0,
            "early_volume": 0.0,
            "warnings": []
        }
        
        # Analyze DexScreener data for listing info
        dex_data = service_data.get("dexscreener")
        if dex_data and dex_data.get("pairs"):
            pairs = dex_data["pairs"]
            if isinstance(pairs, dict) and pairs.get("pairs"):
                pair_list = pairs["pairs"]
                if pair_list and len(pair_list) > 0:
                    # Get the most recent/relevant pair
                    main_pair = pair_list[0]
                    
                    # Analyze listing age
                    created_at = main_pair.get("pairCreatedAt")
                    if created_at:
                        try:
                            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            age_delta = datetime.now(created_time.tzinfo) - created_time
                            listing_data["listing_age_hours"] = round(age_delta.total_seconds() / 3600, 2)
                            
                            # Early opportunity assessment
                            if age_delta.total_seconds() < 3600:  # Less than 1 hour
                                listing_data["early_opportunity"] = "high"
                            elif age_delta.total_seconds() < 24 * 3600:  # Less than 24 hours
                                listing_data["early_opportunity"] = "medium"
                            elif age_delta.total_seconds() < 7 * 24 * 3600:  # Less than 7 days
                                listing_data["early_opportunity"] = "low"
                            else:
                                listing_data["early_opportunity"] = "none"
                                
                        except (ValueError, TypeError):
                            listing_data["warnings"].append("Could not parse listing date")
                    
                    # Analyze initial metrics
                    liquidity_usd = main_pair.get("liquidity", {}).get("usd", 0)
                    volume_24h = main_pair.get("volume", {}).get("h24", 0)
                    
                    if liquidity_usd:
                        listing_data["initial_liquidity"] = float(liquidity_usd)
                    if volume_24h:
                        listing_data["early_volume"] = float(volume_24h)
                    
                    # Quality assessment
                    if listing_data["initial_liquidity"] > 50000 and listing_data["early_volume"] > 10000:
                        listing_data["listing_quality"] = "high"
                        listing_data["growth_potential"] = "high"
                    elif listing_data["initial_liquidity"] > 10000:
                        listing_data["listing_quality"] = "medium"
                        listing_data["growth_potential"] = "medium"
                    else:
                        listing_data["listing_quality"] = "low"
                        listing_data["growth_potential"] = "low"
                        listing_data["warnings"].append("Low initial liquidity")
        
        return listing_data
    
    def _calculate_listing_score(self, service_data: Dict[str, Any], ai_data: Optional[Dict[str, Any]]) -> float:
        """Calculate score for listing opportunity"""
        listing_analysis = service_data.get("listing_analysis", {})
        
        base_score = 40.0  # Lower base for new listings (inherently risky)
        
        # Early opportunity bonus
        early_opp = listing_analysis.get("early_opportunity", "none")
        if early_opp == "high":
            base_score += 30
        elif early_opp == "medium":
            base_score += 20
        elif early_opp == "low":
            base_score += 10
        
        # Quality bonus
        quality = listing_analysis.get("listing_quality", "unknown")
        if quality == "high":
            base_score += 20
        elif quality == "medium":
            base_score += 10
        
        # AI enhancement
        if ai_data and ai_data.get("ai_score"):
            ai_score = float(ai_data["ai_score"])
            base_score = (base_score * 0.6) + (ai_score * 0.4)
        
        return round(min(100.0, base_score), 1)
    
    def _determine_listing_risk(self, listing_data: Dict[str, Any], ai_data: Optional[Dict[str, Any]]) -> str:
        """Determine risk for new listings"""
        # New listings are inherently risky
        early_opp = listing_data.get("early_opportunity", "none")
        quality = listing_data.get("listing_quality", "unknown")
        
        if quality == "low" or early_opp == "none":
            return "high"
        elif quality == "high" and early_opp in ["high", "medium"]:
            return "medium"  # Even good new listings are medium risk
        else:
            return "medium"
    
    async def build_ai_prompt(self, token_address: str, service_data: Dict[str, Any]) -> str:
        """Build listing-focused AI prompt with safe formatting"""
        listing_data = service_data.get("listing_analysis", {})
        
        # Safe value extraction with defaults
        listing_age = listing_data.get('listing_age_hours', 0) or 0
        early_opportunity = listing_data.get('early_opportunity', 'unknown') or 'unknown'
        initial_liquidity = listing_data.get('initial_liquidity', 0) or 0
        early_volume = listing_data.get('early_volume', 0) or 0
        listing_quality = listing_data.get('listing_quality', 'unknown') or 'unknown'
        
        prompt = f"""
    NEW LISTING ANALYSIS for {token_address}

    LISTING DATA:
    - Listing Age: {listing_age:.1f} hours
    - Early Opportunity: {early_opportunity}
    - Initial Liquidity: ${initial_liquidity:,.0f}
    - Early Volume: ${early_volume:,.0f}
    - Quality Assessment: {listing_quality}

    Focus on early opportunity potential and listing quality assessment.

    Respond ONLY with JSON matching this structure:
    {{
    "listing_score": 0-100,
    "opportunity_rating": "low|medium|high",
    "growth_potential": "limited|moderate|high",
    "recommendation": "BUY|CONSIDER|HOLD|CAUTION|AVOID",
    "key_insights": ["list of listing insights"],
    "early_risks": ["list of early-stage risks"]
    }}
    """
        return prompt
    
    def get_json_filters(self) -> Dict[str, Any]:
        """Get JSON filters for listing analysis"""
        return {
            "focus": ["listing_potential", "early_opportunity", "growth_metrics"],
            "required_fields": ["listing_score", "opportunity_rating", "growth_potential"],
            "format": "listing_analysis"
        }