from typing import Dict, Any, Optional
from loguru import logger
import time

from .base_profile import BaseAnalysisProfile
from app.models.analysis_models import AnalysisRunResponse


class TokenDiscoveryProfile(BaseAnalysisProfile):
    """Complete token discovery and assessment (wrapper around existing deep analysis)"""
    
    profile_name = "Token Discovery"
    analysis_type = "discovery"
    required_services = ["birdeye", "goplus", "rugcheck", "solsniffer", "helius", "solanafm", "dexscreener"]
    ai_focus_areas = ["comprehensive_analysis", "investment_potential", "risk_assessment"]
    
    async def analyze(self, token_address: str, filters: Optional[Dict] = None, **kwargs) -> AnalysisRunResponse:
        """Perform comprehensive discovery analysis"""
        self.start_time = time.time()
        
        logger.info(f"🔍 Starting Discovery analysis for {token_address}")
        
        # Use existing deep analysis
        from app.services.ai.ai_token_analyzer import analyze_token_deep_comprehensive
        
        deep_result = await analyze_token_deep_comprehensive(
            token_address, 
            "profile_discovery"
        )
        
        # Transform to new response format
        response = self._transform_deep_analysis_response(deep_result)
        
        # Store analysis
        await self._store_analysis(response)
        
        logger.info(f"✅ Discovery analysis completed: {response.overall_score}% score")
        return response
    
    def _transform_deep_analysis_response(self, deep_result: Dict[str, Any]) -> AnalysisRunResponse:
        """Transform existing deep analysis to new response format"""
        
        # Extract data from deep analysis result
        overall_analysis = deep_result.get("overall_analysis", {})
        ai_analysis = deep_result.get("ai_analysis", {})
        metadata = deep_result.get("metadata", {})
        
        # Extract token info
        token_symbol = "Unknown"
        token_name = "Unknown Token"
        
        # Try to extract from service responses
        service_responses = deep_result.get("service_responses", {})
        for service_name, service_data in service_responses.items():
            if service_name == "solanafm" and service_data:
                if service_data.get("symbol"):
                    token_symbol = service_data["symbol"]
                if service_data.get("name"):
                    token_name = service_data["name"]
                break
        
        # Build response
        response = AnalysisRunResponse(
            analysis_type=self.analysis_type,
            token_address=deep_result.get("token_address", ""),
            token_symbol=token_symbol,
            token_name=token_name,
            overall_score=float(overall_analysis.get("score", 0)),
            risk_level=overall_analysis.get("risk_level", "medium"),
            recommendation=overall_analysis.get("recommendation", "caution"),
            security_status=overall_analysis.get("security_passed", False) and "passed" or "failed",
            critical_issues=len(deep_result.get("security_analysis", {}).get("critical_issues", [])),
            warnings=len(deep_result.get("warnings", [])),
            processing_time=round(metadata.get("processing_time_seconds", 0), 2),
            profile_data={
                "comprehensive_analysis": overall_analysis,
                "ai_analysis": ai_analysis,
                "security_analysis": deep_result.get("security_analysis", {}),
                "service_responses": service_responses,
                "metadata": metadata
            }
        )
        
        return response
    
    async def build_ai_prompt(self, token_address: str, service_data: Dict[str, Any]) -> str:
        """This profile uses existing AI analysis from deep analysis"""
        return ""  # Not used - deep analysis handles AI
    
    def get_json_filters(self) -> Dict[str, Any]:
        """This profile uses existing AI filters from deep analysis"""
        return {}  # Not used - deep analysis handles filters