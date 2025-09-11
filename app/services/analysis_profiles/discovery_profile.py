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
        """Perform discovery analysis using deep analysis + store as run + return simple schema"""
        self.start_time = time.time()
        
        logger.info(f"🔍 Starting Discovery analysis for {token_address}")
        
        try:
            # Use existing deep analysis (unchanged)
            from app.services.ai.ai_token_analyzer import analyze_token_deep_comprehensive
            
            deep_result = await analyze_token_deep_comprehensive(
                token_address, 
                "discovery_report"
            )
            
            # Store as discovery run (existing)
            await self._store_discovery_run(token_address, deep_result)
            
            # Transform to simple schema with Russian timing
            simple_response = self._transform_to_simple_schema(deep_result)
            
            logger.info(f"✅ Discovery analysis completed for {token_address}")
            return simple_response
            
        except Exception as e:
            logger.error(f"❌ Discovery analysis failed for {token_address}: {str(e)}")
            raise

    def _transform_to_simple_schema(self, deep_result: Dict[str, Any]) -> Dict[str, Any]:
        """Transform deep analysis to simple schema with Russian timing"""
        try:
            # Extract basic info
            service_responses = deep_result.get("service_responses", {})
            overall_analysis = deep_result.get("overall_analysis", {})
            ai_analysis = deep_result.get("ai_analysis", {})
            token_address = deep_result.get("token_address", "")
            
            # Extract token name
            token_name = "Unknown"
            if service_responses.get("solanafm", {}).get("token", {}).get("name"):
                token_name = service_responses["solanafm"]["token"]["name"]
            elif service_responses.get("helius", {}).get("metadata", {}).get("name"):
                token_name = service_responses["helius"]["metadata"]["name"]
            
            # Extract market data with None handling
            birdeye_price = service_responses.get("birdeye", {}).get("price", {})
            liq = int(birdeye_price.get("liquidity") or 0)
            mcap = int(birdeye_price.get("market_cap") or 0)
            
            # Fallback for mcap with None handling
            if mcap == 0:
                solsniffer_mcap = service_responses.get("solsniffer", {}).get("marketCap")
                if solsniffer_mcap is not None:
                    mcap = int(solsniffer_mcap)
            
            # Extract risk level
            risk_level = overall_analysis.get("risk_level", "medium").upper()
            if risk_level == "CRITICAL":
                risk_level = "HIGH"
            
            # Extract security status
            security_analysis = deep_result.get("security_analysis", {})
            
            def get_security_status(service_name, data_key, threshold_func):
                try:
                    if service_name == "goplus":
                        goplus_data = security_analysis.get("goplus_result", {})
                        critical_issues = security_analysis.get("critical_issues", [])
                        return "BAD" if critical_issues else "OK"
                    
                    elif service_name == "rug":
                        rugcheck_data = security_analysis.get("rugcheck_result", {})
                        if rugcheck_data.get("rugged"):
                            return "BAD"
                        score = rugcheck_data.get("score")
                        if score is not None and float(score) < 20:
                            return "BAD"
                        return "OK"
                    
                    elif service_name == "sniffer":
                        solsniffer_data = service_responses.get("solsniffer", {})
                        score = solsniffer_data.get("score")
                        if score is not None and float(score) < 5:
                            return "BAD"
                        return "OK"
                    
                    return "OK"
                except:
                    return "OK"
            
            # Extract timing from AI analysis

            timing_analysis = {}
            if ai_analysis and ai_analysis.get("market_metrics", {}).get("timing_analysis"):
                timing_analysis = ai_analysis["market_metrics"]["timing_analysis"]

            last_pump = timing_analysis.get("last_pump", "Неизвестно")
            next_window = timing_analysis.get("next_window", "Неизвестно")

            logger.info(f"🔍 Timing data: last_pump={last_pump}, next_window={next_window}")
            if not timing_analysis:
                logger.warning(f"🔍 No timing analysis found in market_metrics.timing_analysis")
            
            # Extract verdict from recommendation
            recommendation = overall_analysis.get("recommendation", "caution")
            verdict_mapping = {
                "consider": "BUY",
                "caution": "WATCH",
                "avoid": "SELL"
            }
            verdict = verdict_mapping.get(recommendation, "HOLD")
            
            # Build simplified response
            simple_response = {
                "name": token_name,
                "contract": token_address,
                "liq": liq,
                "mcap": mcap,
                "risk": risk_level,
                "links": {
                    "birdeye": f"https://birdeye.so/solana/token/{token_address}",
                    "pumpfun": f"https://pump.fun/coin/{token_address}",
                },
                "social": {
                    "x": "+0%",  # Placeholder - no social data available
                    "tg": "0/ч"   # Placeholder - no social data available
                },
                "security": {
                    "goplus": get_security_status("goplus", None, None),
                    "rug": get_security_status("rug", None, None),
                    "sniffer": get_security_status("sniffer", None, None)
                },
                "lastPump": last_pump,
                "nextWindow": next_window,
                "verdict": verdict,
                "mint": token_address,
                
                # Keep full deep analysis for backward compatibility
                "_full_analysis": deep_result
            }
            
            return simple_response
            
        except Exception as e:
            logger.error(f"Error transforming response: {str(e)}")
            # Return fallback response
            return {
                "name": "Unknown",
                "contract": deep_result.get("token_address", ""),
                "liq": 0,
                "mcap": 0,
                "risk": "HIGH",
                "links": {"pumpfun": "", "birdeye": ""},
                "social": {"x": "+0%", "tg": "0/ч"},
                "security": {"goplus": "OK", "rug": "OK", "sniffer": "OK"},
                "lastPump": "Неизвестно",
                "nextWindow": "Неизвестно", 
                "verdict": "HOLD",
                "mint": deep_result.get("token_address", ""),
                "_full_analysis": deep_result
            }
    
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