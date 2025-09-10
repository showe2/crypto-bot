from typing import Dict, Any, Optional
from loguru import logger
import time
import asyncio

from .base_profile import BaseAnalysisProfile
from app.models.analysis_models import AnalysisRunResponse
from app.services.analysis_storage import analysis_storage


class TokenDiscoveryProfile(BaseAnalysisProfile):
    """Simplified token discovery using deep analysis + run storage"""
    
    profile_name = "Token Discovery"
    analysis_type = "discovery"
    required_services = ["birdeye", "goplus", "rugcheck", "solsniffer", "helius", "solanafm", "dexscreener"]
    ai_focus_areas = ["comprehensive_analysis", "investment_potential", "risk_assessment"]
    
    async def analyze(self, token_address: str, filters: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Perform discovery analysis using deep analysis + store as run"""
        self.start_time = time.time()
        
        logger.info(f"🔍 Starting Discovery analysis for {token_address}")
        
        try:
            # Use existing deep analysis
            from app.services.ai.ai_token_analyzer import analyze_token_deep_comprehensive
            
            deep_result = await analyze_token_deep_comprehensive(
                token_address, 
                "discovery_report"
            )
            
            # Store as discovery run
            await self._store_discovery_run(token_address, deep_result)
            
            # Return same format as deep analysis
            logger.info(f"✅ Discovery analysis completed for {token_address}")
            return deep_result
            
        except Exception as e:
            logger.error(f"❌ Discovery analysis failed for {token_address}: {str(e)}")
            raise
    
    async def _store_discovery_run(self, token_address: str, analysis_result: Dict[str, Any]) -> None:
        """Store discovery analysis as a run"""
        try:
            processing_time = time.time() - self.start_time
            
            # Extract token info from analysis result
            token_symbol = "Unknown"
            token_name = "Unknown Token"
            
            # Try to get token info from service responses
            service_responses = analysis_result.get("service_responses", {})
            for service_name, service_data in service_responses.items():
                if service_name == "solanafm" and service_data:
                    if service_data.get("token", {}).get("symbol"):
                        token_symbol = service_data["token"]["symbol"]
                    if service_data.get("token", {}).get("name"):
                        token_name = service_data["token"]["name"]
                    break
            
            # Build run data
            run_data = {
                "run_id": f"run_{int(time.time())}",
                "profile_type": "discovery",
                "timestamp": int(time.time()),
                "token_address": token_address,
                "processing_time": processing_time,
                "status": "completed" if analysis_result.get("overall_analysis") else "failed",
                "results": [{
                    "token_address": token_address,
                    "token_symbol": token_symbol,
                    "token_name": token_name,
                    "success": bool(analysis_result.get("overall_analysis")),
                    "analysis_result": analysis_result,
                    "timestamp": int(time.time())
                }],
                "summary": f"Discovery analysis for {token_symbol} ({token_name})",
                "metadata": {
                    "analysis_type": "discovery",
                    "ai_enhanced": bool(analysis_result.get("ai_analysis")),
                    "security_passed": analysis_result.get("metadata", {}).get("security_check_passed", False),
                    "services_successful": analysis_result.get("metadata", {}).get("services_successful", 0)
                }
            }
            
            # Store run asynchronously
            asyncio.create_task(analysis_storage.store_analysis_run(run_data))
            logger.info(f"📊 Discovery run stored: {run_data['run_id']}")
            
        except Exception as e:
            logger.warning(f"Failed to store discovery run: {str(e)}")
    
    async def build_ai_prompt(self, token_address: str, service_data: Dict[str, Any]) -> str:
        """Not used - deep analysis handles AI"""
        return ""
    
    def get_json_filters(self) -> Dict[str, Any]:
        """Not used - deep analysis handles filters"""
        return {}