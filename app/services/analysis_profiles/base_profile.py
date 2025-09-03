from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from loguru import logger
from datetime import datetime
import time
import asyncio

from app.models.analysis_models import AnalysisRunResponse
from app.services.service_manager import api_manager
from app.services.analysis_storage import analysis_storage
from app.core.config import get_settings

settings = get_settings()


class BaseAnalysisProfile(ABC):
    """Abstract base class for all analysis profiles"""
    
    profile_name: str
    analysis_type: str
    required_services: List[str]
    ai_focus_areas: List[str]
    
    def __init__(self):
        """Initialize profile with service dependencies"""
        self.cache_ttl = settings.REPORT_TTL_SECONDS
        self.start_time = None
        
    @abstractmethod
    async def analyze(self, token_address: str, filters: Optional[Dict] = None, **kwargs) -> AnalysisRunResponse:
        """Perform the analysis - must be implemented by each profile"""
        pass
    
    @abstractmethod
    async def build_ai_prompt(self, token_address: str, service_data: Dict[str, Any]) -> str:
        """Build AI prompt specific to this profile"""
        pass
    
    @abstractmethod
    def get_json_filters(self) -> Dict[str, Any]:
        """Get JSON filters for AI analysis"""
        pass
    
    async def _gather_service_data(self, token_address: str) -> Dict[str, Any]:
        """Gather data from required services"""
        service_data = {
            "token_address": token_address,
            "timestamp": time.time(),
            "services_attempted": 0,
            "services_successful": 0,
            "errors": []
        }
        
        tasks = {}
        
        # Build service tasks based on required_services
        for service_name in self.required_services:
            client = api_manager.clients.get(service_name)
            if not client:
                service_data["errors"].append(f"{service_name} client not available")
                continue
                
            service_data["services_attempted"] += 1
            
            # Map service names to appropriate methods
            if service_name == "birdeye":
                tasks[service_name] = self._safe_call(client.get_multiple_data_sequential, token_address)
            elif service_name == "goplus":
                tasks[service_name] = self._safe_call(client.analyze_token_security, token_address)
            elif service_name == "rugcheck":
                tasks[service_name] = self._safe_call(client.check_token, token_address)
            elif service_name == "solsniffer":
                tasks[service_name] = self._safe_call(client.get_token_info, token_address)
            elif service_name == "helius":
                tasks[f"{service_name}_supply"] = self._safe_call(client.get_token_supply, token_address)
                tasks[f"{service_name}_metadata"] = self._safe_call(client.get_token_metadata, [token_address])
            elif service_name == "solanafm":
                tasks[service_name] = self._safe_call(client.get_token_info, token_address)
            elif service_name == "dexscreener":
                tasks[service_name] = self._safe_call(client.get_token_pairs, token_address, "solana")
        
        if not tasks:
            logger.warning(f"No services available for {self.profile_name}")
            return service_data
        
        # Execute service calls
        try:
            logger.info(f"Executing {len(tasks)} service calls for {self.profile_name}")
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            
            # Process results
            task_names = list(tasks.keys())
            for i, task_name in enumerate(task_names):
                result = results[i] if i < len(results) else None
                
                if isinstance(result, Exception):
                    service_data["errors"].append(f"{task_name}: {str(result)}")
                elif result is not None:
                    service_data[task_name] = result
                    service_data["services_successful"] += 1
                    
        except Exception as e:
            logger.error(f"Service data gathering failed for {self.profile_name}: {str(e)}")
            service_data["errors"].append(f"Service execution failed: {str(e)}")
        
        return service_data
    
    async def _safe_call(self, func, *args, **kwargs):
        """Execute service call with error handling"""
        try:
            return await func(*args, **kwargs) if kwargs else await func(*args)
        except Exception as e:
            logger.warning(f"{func.__name__} failed: {str(e)}")
            return None
    
    async def _run_ai_analysis(self, token_address: str, service_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run AI analysis if available"""
        try:
            from app.services.ai.ai_service import analyze_token_with_ai, AIAnalysisRequest
            
            # Build AI prompt with safe formatting
            ai_prompt = await self.build_ai_prompt(token_address, service_data)
            
            # Only proceed if we have a valid prompt
            if not ai_prompt or not ai_prompt.strip():
                logger.warning(f"Empty AI prompt for {self.profile_name}, skipping AI analysis")
                return None
            
            # Create AI request
            ai_request = AIAnalysisRequest(
                token_address=token_address,
                service_responses=service_data,
                security_analysis={},
                analysis_type=self.analysis_type,
                custom_prompt=ai_prompt,
                profile_type=self.analysis_type  # Add profile_type
            )
            
            # Run AI analysis
            ai_result = await analyze_token_with_ai(ai_request)
            
            if ai_result:
                return {
                    "ai_score": float(ai_result.ai_score) if ai_result.ai_score is not None else 0.0,
                    "risk_assessment": ai_result.risk_assessment or "medium",
                    "recommendation": ai_result.recommendation or "CONSIDER",
                    "confidence": float(ai_result.confidence) if ai_result.confidence is not None else 70.0,
                    "key_insights": ai_result.key_insights or [],
                    "risk_factors": ai_result.risk_factors or [],
                    "stop_flags": ai_result.stop_flags or [],
                    "market_metrics": ai_result.market_metrics or {},
                    "llama_reasoning": ai_result.llama_reasoning or "",
                    "processing_time": float(ai_result.processing_time) if ai_result.processing_time is not None else 0.0
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"AI analysis failed for {self.profile_name}: {str(e)}")
            return None
    
    def _extract_token_info(self, service_data: Dict[str, Any]) -> Dict[str, str]:
        """Extract token symbol and name from service data"""
        token_symbol = "Unknown"
        token_name = "Unknown Token"
        
        # Try to extract from different services
        # Birdeye
        if "birdeye" in service_data and service_data["birdeye"]:
            birdeye_data = service_data["birdeye"]
            if "price" in birdeye_data:
                # Extract from price data if available
                pass  # Birdeye doesn't typically include name/symbol in price endpoint
        
        # SolanaFM
        if "solanafm" in service_data and service_data["solanafm"]:
            sf_data = service_data["solanafm"]["token"]
            print(sf_data)
            if sf_data.get("symbol"):
                token_symbol = sf_data["symbol"]
            if sf_data.get("name"):
                token_name = sf_data["name"]
        
        # Helius metadata
        if "helius" in service_data and service_data["helius"]:
            metadata = service_data["helius"]["metadata"]["legacyMetadata"]
            if isinstance(metadata, dict):
                if metadata.get("symbol"):
                    token_symbol = metadata["symbol"]
                if metadata.get("name"):
                    token_name = metadata["name"]

        # DexScreener metadata
        if "dexscreener" in service_data and service_data["dexscreener"]:
            pairs_data = service_data["dexscreener"]["pairs"][0]

            base_token = pairs_data.get("baseToken")
            quote_token = pairs_data.get("quoteToken")

            if base_token is not None and quote_token is not None:
                if base_token["address"] == service_data["token_address"]:
                    token_symbol = base_token["symbol"]
                    token_name = base_token["name"]
                else:
                    token_symbol = quote_token["symbol"]
                    token_name = quote_token["name"]

        return {"symbol": token_symbol, "name": token_name}
    
    def _calculate_overall_score(self, service_data: Dict[str, Any], ai_data: Optional[Dict[str, Any]]) -> float:
        """Calculate overall score for the analysis"""
        base_score = 50.0  # Base score for having data
        
        # Add points for successful service responses
        services_bonus = (service_data.get("services_successful", 0) * 10)
        
        # Add AI score if available
        ai_bonus = 0.0
        if ai_data and ai_data.get("ai_score"):
            ai_score = float(ai_data["ai_score"])
            ai_bonus = ai_score * 0.4  # 40% weight for AI analysis
        
        final_score = min(100.0, base_score + services_bonus + ai_bonus)
        return round(final_score, 1)
    
    def _determine_risk_level(self, overall_score: float, ai_data: Optional[Dict[str, Any]]) -> str:
        """Determine risk level based on score and AI analysis"""
        # Start with score-based risk
        if overall_score >= 80:
            base_risk = "low"
        elif overall_score >= 60:
            base_risk = "medium"
        elif overall_score >= 40:
            base_risk = "medium"
        else:
            base_risk = "high"
        
        # Adjust based on AI analysis
        if ai_data:
            ai_risk = ai_data.get("risk_assessment", "medium")
            stop_flags = ai_data.get("stop_flags", [])
            
            # AI stop flags override everything
            if stop_flags:
                return "critical"
            
            # Take higher risk assessment
            risk_hierarchy = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            base_level = risk_hierarchy.get(base_risk, 2)
            ai_level = risk_hierarchy.get(ai_risk, 2)
            
            final_level = max(base_level, ai_level)
            for risk, level in risk_hierarchy.items():
                if level == final_level:
                    return risk
        
        return base_risk
    
    def _determine_recommendation(self, overall_score: float, risk_level: str, ai_data: Optional[Dict[str, Any]]) -> str:
        """Determine recommendation based on analysis"""
        # AI recommendation takes priority
        if ai_data and ai_data.get("recommendation"):
            ai_rec = ai_data["recommendation"]
            # Map AI recommendations to frontend format
            ai_mapping = {
                "BUY": "consider",
                "CONSIDER": "consider",
                "HOLD": "caution",
                "CAUTION": "caution",
                "AVOID": "avoid"
            }
            return ai_mapping.get(ai_rec, "caution")
        
        # Fallback to score-based recommendation
        if risk_level == "critical":
            return "avoid"
        elif risk_level == "high":
            return "avoid"
        elif overall_score >= 75:
            return "consider"
        else:
            return "caution"
    
    async def _store_analysis(self, response: AnalysisRunResponse) -> bool:
        """Store analysis in ChromaDB for history tracking"""
        try:
            # Convert to storage format
            storage_data = self.format_for_storage(response)
            success = await analysis_storage.store_analysis(storage_data)
            if success:
                logger.info(f"Stored {self.profile_name} analysis: {response.run_id}")
            return success
        except Exception as e:
            logger.warning(f"Failed to store {self.profile_name} analysis: {str(e)}")
            return False
    
    def format_for_frontend(self, response: AnalysisRunResponse) -> Dict[str, Any]:
        """Format response for frontend compatibility (dashboard/popup)"""
        return {
            # Required frontend fields
            "id": response.run_id,
            "token_symbol": response.token_symbol,
            "token_name": response.token_name,
            "mint": response.mint,
            "timestamp": response.timestamp,
            "risk_level": response.risk_level,
            "security_status": response.security_status,
            "overall_score": response.overall_score,
            "recommendation": response.recommendation,
            "critical_issues": response.critical_issues,
            "warnings": response.warnings,
            "processing_time": response.processing_time,
            "source_event": response.source_event,
            "status": response.status,
            
            # Additional profile data
            "profile_type": response.analysis_type,
            "profile_data": response.profile_data,
            
            # Links
            **response.links
        }
    
    def format_for_storage(self, response: AnalysisRunResponse) -> Dict[str, Any]:
        """Format response for ChromaDB storage"""
        return {
            "analysis_id": response.run_id,
            "token_address": response.token_address,
            "token_symbol": response.token_symbol,
            "token_name": response.token_name,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "timestamp_unix": response.timestamp,
                "source_event": response.source_event,
                "analysis_type": response.analysis_type,
                "overall_score": response.overall_score,
                "risk_level": response.risk_level,
                "security_status": response.security_status,
                "recommendation": response.recommendation,
                "critical_issues_count": response.critical_issues,
                "warnings_count": response.warnings,
                "processing_time": response.processing_time,
                "profile_type": response.analysis_type,
                "profile_data_available": bool(response.profile_data)
            }
        }