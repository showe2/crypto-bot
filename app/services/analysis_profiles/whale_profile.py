from typing import Dict, Any, Optional, List
from loguru import logger
import time

from .base_profile import BaseAnalysisProfile
from app.models.analysis_models import AnalysisRunResponse


class WhaleAnalysisProfile(BaseAnalysisProfile):
    """Whale holder distribution and movements analysis"""
    
    profile_name = "Whale Analysis"
    analysis_type = "whale"
    required_services = ["goplus", "rugcheck", "birdeye"]
    ai_focus_areas = ["whale_metrics", "holder_distribution", "concentration_analysis"]
    
    async def analyze(self, token_address: str, filters: Optional[Dict] = None, **kwargs) -> AnalysisRunResponse:
        """Analyze token for whale distribution and risks"""
        self.start_time = time.time()
        
        logger.info(f"🐋 Starting Whale analysis for {token_address}")
        
        # Gather service data
        service_data = await self._gather_service_data(token_address)
        
        # Enhanced whale analysis
        whale_data = self._analyze_whale_distribution(service_data)
        service_data["whale_analysis"] = whale_data
        
        # Run AI analysis
        ai_data = await self._run_ai_analysis(token_address, service_data)
        
        # Extract token info
        token_info = self._extract_token_info(service_data)
        
        # Calculate metrics
        overall_score = self._calculate_whale_score(service_data, ai_data)
        risk_level = self._determine_whale_risk(whale_data, ai_data)
        recommendation = self._determine_recommendation(overall_score, risk_level, ai_data)
        
        # Determine security status and issues
        critical_issues = self._count_critical_whale_issues(whale_data)
        warnings = len(whale_data.get("warnings", [])) + len(service_data.get("errors", []))
        security_status = "failed" if critical_issues > 0 else "warning" if warnings > 0 else "passed"
        
        # Build response
        response = AnalysisRunResponse(
            analysis_type=self.analysis_type,
            token_address=token_address,
            token_symbol=token_info["symbol"],
            token_name=token_info["name"],
            overall_score=overall_score,
            risk_level=risk_level,
            recommendation=recommendation,
            security_status=security_status,
            critical_issues=critical_issues,
            warnings=warnings,
            processing_time=round(time.time() - self.start_time, 2),
            profile_data={
                "whale_metrics": whale_data,
                "ai_analysis": ai_data,
                "services_data": {k: v for k, v in service_data.items() if not k.startswith("services_")}
            }
        )
        
        # Store analysis
        await self._store_analysis(response)
        
        logger.info(f"✅ Whale analysis completed: {whale_data['whale_count']} whales, {whale_data['concentration_risk']} risk")
        return response
    
    def _analyze_whale_distribution(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced whale distribution analysis"""
        whale_data = {
            "whale_count": 0,
            "whale_control_percent": 0.0,
            "top_whale_percent": 0.0,
            "concentration_risk": "unknown",
            "distribution_score": 50.0,
            "dump_risk": "medium",
            "warnings": [],
            "top_100_whales": [],
            "movement_patterns": {}
        }
        
        # Analyze GOplus holder data
        goplus_data = service_data.get("goplus")
        if goplus_data and goplus_data.get("holders"):
            holders = goplus_data["holders"]
            if isinstance(holders, list):
                whale_list = []
                total_whale_percent = 0.0
                
                for holder in holders:
                    if isinstance(holder, dict):
                        try:
                            percent_str = holder.get("percent", "0")
                            percent = float(percent_str)
                            
                            # Whale threshold: >1% = whale
                            if percent > 1.0:
                                whale_info = {
                                    "address": holder.get("address", "unknown"),
                                    "percent": percent,
                                    "tag": holder.get("tag", "unknown")
                                }
                                whale_list.append(whale_info)
                                total_whale_percent += percent
                                
                        except (ValueError, TypeError):
                            continue
                
                # Store whale data
                whale_data["whale_count"] = len(whale_list)
                whale_data["whale_control_percent"] = round(total_whale_percent, 2)
                whale_data["top_100_whales"] = whale_list[:100]  # Store top 100
                
                if whale_list:
                    whale_data["top_whale_percent"] = round(max(w["percent"] for w in whale_list), 2)
                
                # Risk assessment
                if total_whale_percent > 60:
                    whale_data["concentration_risk"] = "critical"
                    whale_data["dump_risk"] = "high"
                    whale_data["warnings"].append("Extreme whale concentration (>60%)")
                elif total_whale_percent > 40:
                    whale_data["concentration_risk"] = "high"
                    whale_data["dump_risk"] = "medium"
                    whale_data["warnings"].append("High whale concentration (>40%)")
                elif total_whale_percent > 25:
                    whale_data["concentration_risk"] = "medium"
                    whale_data["dump_risk"] = "medium"
                elif total_whale_percent > 15:
                    whale_data["concentration_risk"] = "low"
                    whale_data["dump_risk"] = "low"
                else:
                    whale_data["concentration_risk"] = "very_low"
                    whale_data["dump_risk"] = "very_low"
                
                # Distribution score
                if total_whale_percent < 15:
                    whale_data["distribution_score"] = 90.0
                elif total_whale_percent < 25:
                    whale_data["distribution_score"] = 75.0
                elif total_whale_percent < 40:
                    whale_data["distribution_score"] = 50.0
                else:
                    whale_data["distribution_score"] = 25.0
        
        # Enhance with RugCheck data if available
        rugcheck_data = service_data.get("rugcheck")
        if rugcheck_data:
            # Look for creator/dev analysis
            creator_balance = rugcheck_data.get("creator_balance")
            if creator_balance:
                try:
                    dev_percent = float(creator_balance) * 100
                    if dev_percent > 20:
                        whale_data["warnings"].append(f"High dev holding: {dev_percent:.1f}%")
                        whale_data["dump_risk"] = "high"
                except (ValueError, TypeError):
                    pass
        
        return whale_data
    
    def _count_critical_whale_issues(self, whale_data: Dict[str, Any]) -> int:
        """Count critical issues in whale analysis"""
        critical_count = 0
        
        # Critical: >80% whale control
        if whale_data.get("whale_control_percent", 0) > 80:
            critical_count += 1
        
        # Critical: Single whale >50%
        if whale_data.get("top_whale_percent", 0) > 50:
            critical_count += 1
        
        return critical_count
    
    def _calculate_whale_score(self, service_data: Dict[str, Any], ai_data: Optional[Dict[str, Any]]) -> float:
        """Calculate score focusing on whale distribution"""
        whale_analysis = service_data.get("whale_analysis", {})
        
        # Start with distribution score
        base_score = whale_analysis.get("distribution_score", 50.0)
        
        # Penalty for high concentration
        concentration_risk = whale_analysis.get("concentration_risk", "medium")
        if concentration_risk == "critical":
            base_score *= 0.3  # Severe penalty
        elif concentration_risk == "high":
            base_score *= 0.6  # High penalty
        elif concentration_risk == "medium":
            base_score *= 0.8  # Moderate penalty
        
        # AI enhancement
        if ai_data and ai_data.get("ai_score"):
            ai_score = float(ai_data["ai_score"])
            base_score = (base_score * 0.7) + (ai_score * 0.3)
        
        return round(base_score, 1)
    
    def _determine_whale_risk(self, whale_data: Dict[str, Any], ai_data: Optional[Dict[str, Any]]) -> str:
        """Determine risk level based on whale concentration"""
        concentration_risk = whale_data.get("concentration_risk", "medium")
        
        # Map concentration risk to overall risk
        risk_mapping = {
            "critical": "critical",
            "high": "high", 
            "medium": "medium",
            "low": "low",
            "very_low": "low"
        }
        
        base_risk = risk_mapping.get(concentration_risk, "medium")
        
        # AI can only increase risk, not decrease it
        if ai_data and ai_data.get("stop_flags"):
            return "critical"
        
        return base_risk
    
    async def build_ai_prompt(self, token_address: str, service_data: Dict[str, Any]) -> str:
        """Build whale-focused AI prompt with safe formatting"""
        whale_data = service_data.get("whale_analysis", {})
        
        # Safe value extraction with defaults
        whale_count = whale_data.get('whale_count', 0) or 0
        whale_control = whale_data.get('whale_control_percent', 0) or 0
        top_whale = whale_data.get('top_whale_percent', 0) or 0
        concentration_risk = whale_data.get('concentration_risk', 'unknown') or 'unknown'
        distribution_score = whale_data.get('distribution_score', 50) or 50
        
        prompt = f"""
    WHALE ANALYSIS for {token_address}

    WHALE DISTRIBUTION DATA:
    - Whale Count: {whale_count}
    - Whale Control: {whale_control:.2f}%
    - Top Whale: {top_whale:.2f}%
    - Concentration Risk: {concentration_risk}
    - Distribution Score: {distribution_score:.1f}

    Focus on whale behavior and holder concentration risks. Assess distribution fairness and dump risk.

    Respond ONLY with JSON matching this structure:
    {{
    "whale_risk": 0-100,
    "distribution_score": 0-100,
    "movement_risk": "low|medium|high",
    "recommendation": "BUY|CONSIDER|HOLD|CAUTION|AVOID",
    "key_insights": ["list of whale insights"],
    "whale_risks": ["list of whale-related risks"]
    }}
    """
        return prompt
    
    def get_json_filters(self) -> Dict[str, Any]:
        """Get JSON filters for whale analysis"""
        return {
            "focus": ["whale_metrics", "holder_distribution", "concentration_analysis"],
            "required_fields": ["whale_risk", "distribution_score", "movement_risk"],
            "format": "whale_analysis"
        }