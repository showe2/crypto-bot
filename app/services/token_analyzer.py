import asyncio
import time
import json
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger
from datetime import datetime

from app.services.service_manager import api_manager
from app.utils.redis_client import get_redis_client
from app.utils.cache import cache_manager
from app.services.analysis_storage import analysis_storage


class TokenAnalyzer:
    """Token analyzer with security-first approach"""
    
    def __init__(self):
        """Initialize analyzer with cache manager"""
        self.cache = cache_manager
        self.cache_namespace = "token_analysis"
        self.cache_ttl = {
            "webhook": 7200,  # 2 hours for webhook requests
            "api_request": 3600,  # 1 hour for API requests
            "frontend_quick": 1800,  # 30 minutes for frontend
            "frontend_deep": 7200   # 2 hours for frontend deep
        }
        self.services = {
            "helius": True,
            "birdeye": True,
            "solanafm": True,
            "goplus": True,
            "dexscreener": True,
            "rugcheck": True,
            "solsniffer": True
        }
    
    async def analyze_token_comprehensive(self, token_address: str, source_event: str = "webhook") -> Dict[str, Any]:
        """Comprehensive token analysis with security-first approach"""
        start_time = time.time()
        analysis_id = f"analysis_{int(time.time())}_{token_address[:8]}"
        
        # Initialize response structure
        analysis_response = {
            "analysis_id": analysis_id,
            "token_address": token_address,
            "timestamp": datetime.utcnow().isoformat(),
            "source_event": source_event,
            "analysis_type": "quick",
            "warnings": [],
            "errors": [],
            "data_sources": [],
            "service_responses": {},
            "security_analysis": {},
            "metadata": {
                "processing_time_seconds": 0,
                "data_sources_available": 0,
                "services_attempted": 0,
                "services_successful": 0,
                "security_check_passed": False,
                "analysis_stopped_at_security": False
            }
        }
        
        # Check cache first with proper namespace
        cache_key = f"analysis:{token_address}"
        try:
            cached_result = await self.cache.get(
                key=cache_key, 
                namespace=self.cache_namespace
            )
            if cached_result:
                logger.info(f"Found cached analysis for {token_address}")
                return cached_result
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {str(e)}")
            analysis_response["warnings"].append(f"Cache retrieval failed: {str(e)}")
        
        # STEP 1: SECURITY CHECKS FIRST (GOplus, RugCheck, SolSniffer)
        logger.info("STEP 1: Running security checks (GOplus + RugCheck + SolSniffer)")
        security_passed, security_data = await self._run_security_checks(token_address, analysis_response)
        
        # Store security data
        analysis_response["security_analysis"] = security_data
        analysis_response["metadata"]["security_check_passed"] = security_passed
        
        # STEP 2: Decide whether to continue based on security results
        if not security_passed:
            logger.warning(f"SECURITY CHECK FAILED for {token_address} - STOPPING ANALYSIS")
            analysis_response["metadata"]["analysis_stopped_at_security"] = True
            
            # Generate security-focused analysis and return early
            analysis_response["overall_analysis"] = await self._generate_security_focused_analysis(
                security_data, token_address, False
            )
            analysis_response["analysis_summary"] = analysis_response["overall_analysis"]
            analysis_response["risk_assessment"] = {
                "risk_category": "critical",
                "risk_score": 10,
                "confidence": 95,
                "reason": "Failed security checks"
            }
            
            processing_time = time.time() - start_time
            analysis_response["metadata"]["processing_time_seconds"] = round(processing_time, 3)
            
            asyncio.create_task(self._store_analysis_async(analysis_response))
            
            logger.warning(f"Analysis STOPPED for {token_address} due to security issues in {processing_time:.2f}s")
            return analysis_response
        
        logger.info(f"SECURITY CHECKS PASSED for {token_address} - CONTINUING WITH FULL ANALYSIS")
        
        # STEP 3: Run all other services (Birdeye, Helius, etc.)
        logger.info("STEP 2: Running market and technical analysis services")
        await self._run_market_analysis_services(token_address, analysis_response)
        
        # STEP 4: Generate comprehensive analysis
        analysis_response["overall_analysis"] = await self._generate_comprehensive_analysis(
            analysis_response["service_responses"], security_data, token_address
        )
        analysis_response["analysis_summary"] = analysis_response["overall_analysis"]
        analysis_response["risk_assessment"] = {
            "risk_category": analysis_response["overall_analysis"]["risk_level"],
            "risk_score": analysis_response["overall_analysis"]["score"],
            "confidence": analysis_response["overall_analysis"]["confidence_score"]
        }
        
        # Calculate processing time and cache result
        processing_time = time.time() - start_time
        analysis_response["metadata"]["processing_time_seconds"] = round(processing_time, 3)
        
        # Cache the result with proper TTL
        try:
            ttl = self.cache_ttl.get(source_event, 7200)  # default 2 hours
            await self.cache.set(
                key=cache_key,
                value=analysis_response,
                ttl=ttl,
                namespace=self.cache_namespace
            )
            logger.info(f"Cached analysis for {token_address} with TTL {ttl}s")
        except Exception as e:
            logger.warning(f"Failed to cache analysis: {str(e)}")
            analysis_response["warnings"].append(f"Caching failed: {str(e)}")
        
        asyncio.create_task(self._store_analysis_async(analysis_response))
        
        # Log completion
        logger.info(
            f"FULL Analysis COMPLETED for {token_address} in {processing_time:.2f}s "
            f"(security passed, sources: {len(analysis_response['data_sources'])})"
        )
        
        return analysis_response
    
    # Async ChromaDB Storage
    async def _store_analysis_async(self, analysis_response: Dict[str, Any]) -> None:
        """Store analysis in ChromaDB asynchronously (non-blocking)"""
        try:
            success = await analysis_storage.store_analysis(analysis_response)
            if success:
                logger.debug(f"Analysis stored in ChromaDB: {analysis_response.get('analysis_id')}")
            else:
                logger.debug(f"ChromaDB storage skipped for: {analysis_response.get('analysis_id')}")
        except Exception as e:
            # Don't let ChromaDB errors affect the main analysis flow
            logger.warning(f"ChromaDB storage error: {str(e)}")
    
    async def _run_security_checks(self, token_address: str, analysis_response: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Run security checks first (GOplus + RugCheck + SolSniffer)"""
        security_data = {
            "goplus_result": None,
            "rugcheck_result": None,
            "solsniffer_result": None,
            "critical_issues": [],
            "warnings": [],
            "overall_safe": False
        }
                
        security_tasks = {}
        
        # Prepare GOplus security check
        if api_manager.clients.get("goplus"):
            security_tasks["goplus"] = self._safe_service_call(
                api_manager.clients["goplus"].analyze_token_security, 
                token_address
            )
            analysis_response["metadata"]["services_attempted"] += 1
            logger.info("GOplus security check prepared")
        else:
            logger.warning("GOplus client not available")
            analysis_response["warnings"].append("GOplus security check unavailable")
        
        # Prepare RugCheck analysis
        if api_manager.clients.get("rugcheck"):
            security_tasks["rugcheck"] = self._safe_service_call(
                api_manager.clients["rugcheck"].check_token, 
                token_address
            )
            analysis_response["metadata"]["services_attempted"] += 1
            logger.info("RugCheck analysis prepared")
        else:
            logger.warning("RugCheck client not available")
            analysis_response["warnings"].append("RugCheck analysis unavailable")

        # Prepare SolSniffer analysis
        if api_manager.clients.get("solsniffer"):
            security_tasks["solsniffer"] = self._safe_service_call(
                api_manager.clients["solsniffer"].get_token_info, 
                token_address
            )
            analysis_response["metadata"]["services_attempted"] += 1
            logger.info("SolSniffer analysis prepared")
        else:
            logger.warning("SolSniffer client not available")
            analysis_response["warnings"].append("SolSniffer analysis unavailable")
        
        if not security_tasks:
            logger.error("NO SECURITY SERVICES AVAILABLE - Cannot perform security check")
            analysis_response["errors"].append("No security services available")
            return False, security_data
        
        # Execute security checks
        try:
            logger.info(f"Executing {len(security_tasks)} security checks")
            results = await asyncio.wait_for(
                asyncio.gather(*security_tasks.values(), return_exceptions=True),
                timeout=15.0  # Shorter timeout for security checks
            )
        except asyncio.TimeoutError:
            logger.warning("Security checks timed out")
            analysis_response["warnings"].append("Security checks timed out")
            return False, security_data
        except Exception as e:
            logger.error(f"Security checks failed: {str(e)}")
            analysis_response["errors"].append(f"Security checks failed: {str(e)}")
            return False, security_data
        
        # Process security results
        task_names = list(security_tasks.keys())
        critical_issues_found = False
        
        for i, task_name in enumerate(task_names):
            try:
                result = results[i] if i < len(results) else None
                
                if isinstance(result, Exception):
                    logger.error(f"{task_name} failed: {str(result)}")
                    analysis_response["errors"].append(f"{task_name}: {str(result)}")
                    continue
                
                if result is None:
                    logger.warning(f"{task_name} returned no data")
                    analysis_response["warnings"].append(f"{task_name}: No data returned")
                    continue
                
                # Store security service response
                analysis_response["service_responses"][task_name] = result
                analysis_response["data_sources"].append(task_name)
                analysis_response["metadata"]["services_successful"] += 1
                
                # Analyze GOplus results
                if task_name == "goplus":
                    security_data["goplus_result"] = result
                    goplus_issues = self._analyze_goplus_security(result)
                    if goplus_issues["critical"]:
                        critical_issues_found = True
                        security_data["critical_issues"].extend(goplus_issues["critical"])
                    security_data["warnings"].extend(goplus_issues["warnings"])
                    
                    # Check if GOplus has insufficient data
                    if goplus_issues.get("insufficient_data"):
                        security_data["goplus_insufficient_data"] = True
                        logger.warning("GOplus returned insufficient data")
                    
                    logger.info(f"GOplus analysis completed: {len(goplus_issues['critical'])} critical, {len(goplus_issues['warnings'])} warnings")
                
                # Analyze RugCheck results
                elif task_name == "rugcheck":
                    security_data["rugcheck_result"] = result
                    rugcheck_issues = self._analyze_rugcheck_security(result)
                    if rugcheck_issues["critical"]:
                        critical_issues_found = True
                        security_data["critical_issues"].extend(rugcheck_issues["critical"])
                    security_data["warnings"].extend(rugcheck_issues["warnings"])
                    
                    # Check if RugCheck has insufficient data
                    if rugcheck_issues.get("insufficient_data"):
                        security_data["rugcheck_insufficient_data"] = True
                        logger.warning("RugCheck returned insufficient data - ignoring for security decision")
                    
                    logger.info(f"RugCheck analysis completed: {len(rugcheck_issues['critical'])} critical, {len(rugcheck_issues['warnings'])} warnings")

                # Analyze SolSniffer results
                elif task_name == "solsniffer":
                    security_data["solsniffer_result"] = result
                    solsniffer_issues = self._analyze_solsniffer_security(result)
                    if solsniffer_issues["critical"]:
                        critical_issues_found = True
                        security_data["critical_issues"].extend(solsniffer_issues["critical"])
                    security_data["warnings"].extend(solsniffer_issues["warnings"])
                    
                    # Check if SolSniffer has insufficient data
                    if solsniffer_issues.get("insufficient_data"):
                        security_data["solsniffer_insufficient_data"] = True
                        logger.warning("SolSniffer returned insufficient data - ignoring for security decision")
                    
                    logger.info(f"SolSniffer analysis completed: {len(solsniffer_issues['critical'])} critical, {len(solsniffer_issues['warnings'])} warnings")
                    
            except Exception as e:
                logger.error(f"Error processing {task_name}: {str(e)}")
                analysis_response["errors"].append(f"Error processing {task_name}: {str(e)}")
        
        # Determine if security checks passed
        if critical_issues_found:
            logger.warning(f"CRITICAL SECURITY ISSUES FOUND: {security_data['critical_issues']}")
            security_data["overall_safe"] = False
            return False, security_data
        
        # Check if we have at least one successful security check with meaningful data
        goplus_meaningful = "goplus" in analysis_response["data_sources"] and not security_data.get("goplus_insufficient_data", False)
        rugcheck_meaningful = "rugcheck" in analysis_response["data_sources"] and not security_data.get("rugcheck_insufficient_data", False)
        solsniffer_meaningful = "solsniffer" in analysis_response["data_sources"] and not security_data.get("solsniffer_insufficient_data", False)

        if not goplus_meaningful and not rugcheck_meaningful and not solsniffer_meaningful:
            logger.warning("NO MEANINGFUL SECURITY DATA - Cannot verify safety")
            security_data["overall_safe"] = False
            return False, security_data

        # If we have at least one meaningful security check and no critical issues, pass
        meaningful_checks = sum([goplus_meaningful, rugcheck_meaningful, solsniffer_meaningful])
        logger.info(f"SECURITY CHECKS PASSED ({meaningful_checks} meaningful security services responded)")
        security_data["overall_safe"] = True
        return True, security_data
    
    def _analyze_goplus_security(self, goplus_result: Dict[str, Any]) -> Dict[str, List[str]]:
        """Analyze GOplus results for critical security issues - focus on security mechanisms only"""
        critical_issues = []
        warnings = []
        
        if not goplus_result:
            return {"critical": critical_issues, "warnings": warnings}
        
        # Handle both single dict and list formats
        token_data = goplus_result
        if isinstance(goplus_result, list) and len(goplus_result) > 0:
            token_data = goplus_result[0]
        
        # CRITICAL: Check minting authority - can create unlimited tokens
        mintable = token_data.get("mintable", {})
        if isinstance(mintable, dict) and mintable.get("status") == "1":
            critical_issues.append("Token has active mint authority - unlimited supply possible")
        
        # CRITICAL: Check freeze authority - can freeze user accounts
        freezable = token_data.get("freezable", {})
        if isinstance(freezable, dict) and freezable.get("status") == "1":
            critical_issues.append("Token has freeze authority - accounts can be frozen")
        
        # CRITICAL: Check balance mutation authority - can change balances
        balance_mutable = token_data.get("balance_mutable_authority", {})
        if isinstance(balance_mutable, dict) and balance_mutable.get("status") == "1":
            critical_issues.append("Balance can be modified by authority")
        
        # CRITICAL: Check if token is non-transferable
        non_transferable = token_data.get("non_transferable")
        if non_transferable == "1":
            critical_issues.append("Token is non-transferable")
        
        # WARNING: Check if transfer fees can be upgraded
        transfer_fee_upgradable = token_data.get("transfer_fee_upgradable", {})
        if isinstance(transfer_fee_upgradable, dict) and transfer_fee_upgradable.get("status") == "1":
            warnings.append("Transfer fees can be upgraded by authority")
        
        # WARNING: Check if accounts can be closed
        closable = token_data.get("closable", {})
        if isinstance(closable, dict) and closable.get("status") == "1":
            warnings.append("Token accounts can be closed by authority")
        
        # WARNING: Check for extremely low holder count (possible fake/test token)
        holder_count = token_data.get("holder_count")
        if holder_count:
            try:
                holder_count_int = int(holder_count.replace(",", "")) if isinstance(holder_count, str) else int(holder_count)
                if holder_count_int < 10:
                    warnings.append(f"Very low holder count: {holder_count}")
            except (ValueError, TypeError):
                pass
        
        return {"critical": critical_issues, "warnings": warnings}
    
    def _analyze_rugcheck_security(self, rugcheck_result: Dict[str, Any]) -> Dict[str, List[str]]:
        """Analyze RugCheck results for critical security issues - ignore if insufficient data"""
        critical_issues = []
        warnings = []
        
        if not rugcheck_result:
            # No data is not necessarily bad - RugCheck might not have analyzed this token yet
            return {"critical": critical_issues, "warnings": warnings, "insufficient_data": True}
        
        # Check if token is explicitly marked as rugged
        rugged = rugcheck_result.get("rugged")
        if rugged is True:
            critical_issues.append("Token marked as rugged by RugCheck")
        
        # Check for explicit high-risk factors
        risks = rugcheck_result.get("risks", [])
        has_risks = risks and isinstance(risks, list) and len(risks) > 0
        if has_risks:
            for risk in risks:
                if isinstance(risk, dict):
                    risk_level = risk.get("level", "").lower()
                    risk_description = risk.get("description", "")
                    
                    # Only flag critical and high risks
                    if risk_level == "critical" and risk_description:
                        critical_issues.append(f"RugCheck critical risk: {risk_description}")
                    elif risk_level == "high" and risk_description:
                        warnings.append(f"RugCheck high risk: {risk_description}")
        
        # Check verification data
        verification = rugcheck_result.get("verification")
        has_verification = verification and isinstance(verification, dict)
        if has_verification:
            # Look for negative verification results
            verified = verification.get("verified", None)
            if verified is False:
                warnings.append("Token not verified by RugCheck")
        
        # Check RugCheck score - but consider context of other data
        score = rugcheck_result.get("score")
        if score is not None:
            try:
                score_value = float(score)
                
                # THIS IS THE KEY FIX: If score is 1 AND no other meaningful data exists, treat as no data
                if score_value == 1 and not rugged and not has_risks and not has_verification:
                    logger.warning("RugCheck returned score 1 with no meaningful data - ignoring for security decision")
                    return {"critical": [], "warnings": [], "insufficient_data": True}
                
                # If score is 1 but we have other meaningful data, treat score 1 as legitimate low score
                if score_value == 1 and (rugged or has_risks or has_verification):
                    critical_issues.append(f"Very low RugCheck score: {score_value}")
                elif score_value < 20:
                    critical_issues.append(f"Very low RugCheck score: {score_value}")
                elif score_value < 40:
                    warnings.append(f"Low RugCheck score: {score_value}")
                    
            except (ValueError, TypeError):
                # Invalid score format - ignore
                pass
        
        # If RugCheck returned very little useful data overall, don't penalize the token
        has_meaningful_data = any([
            rugged is not None,
            has_risks,
            has_verification,
            (score is not None and score != 1)  # Score other than 1 is meaningful
        ])
        
        if not has_meaningful_data:
            # RugCheck has no meaningful data - ignore this service for security decision
            logger.warning("RugCheck returned insufficient data - ignoring for security decision")
            return {"critical": [], "warnings": [], "insufficient_data": True}
        
        return {"critical": critical_issues, "warnings": warnings}
    
    def _analyze_solsniffer_security(self, solsniffer_result: Dict[str, Any]) -> Dict[str, List[str]]:
        """Analyze SolSniffer results for critical security issues"""
        critical_issues = []
        warnings = []
        
        if not solsniffer_result:
            return {"critical": critical_issues, "warnings": warnings, "insufficient_data": True}
        
        # Extract the main data
        token_data = None
        if isinstance(solsniffer_result, list) and len(solsniffer_result) > 0:
            token_data = solsniffer_result[0]
        elif isinstance(solsniffer_result, dict):
            token_data = solsniffer_result
        
        if not token_data or not token_data.get("indicatorData"):
            return {"critical": critical_issues, "warnings": warnings, "insufficient_data": True}
        
        # Check SolSniffer score - only extremely low scores matter
        score = token_data.get("score")
        if score is not None:
            try:
                score_value = float(score)
                # Only flag scores below 3 as critical (extremely low threshold)
                if score_value < 3:
                    critical_issues.append(f"Extremely low SolSniffer score: {score_value}")
                elif score_value < 10:
                    warnings.append(f"Low SolSniffer score: {score_value}")
            except (ValueError, TypeError):
                pass
        
        # Only flag a few specific high-risk indicators as warnings
        # Skip most common risks that are normal for established tokens
        indicator_data = token_data["indicatorData"]
        
        high_risks = indicator_data.get("high", {})
        if high_risks.get("count", 0) > 3:  # Only if many high risks
            try:
                high_details = json.loads(high_risks.get("details", "{}"))
                
                # Only warn about liquidity issues, skip control/authority warnings
                if high_details.get("Very low liquidity"):
                    warnings.append("Very low liquidity detected")
                    
            except json.JSONDecodeError:
                pass
        
        # Skip moderate warnings entirely - they're too common
        
        # Always return meaningful data if we have any indicator data
        return {"critical": critical_issues, "warnings": warnings}

    async def _run_market_analysis_services(self, token_address: str, analysis_response: Dict[str, Any]) -> None:
        """Run market analysis services (Birdeye, Helius, SolanaFM, DexScreener)"""
        
        # BIRDEYE - Handle separately with sequential processing (for rate limiting)
        birdeye_data = {}
        if api_manager.clients.get("birdeye"):
            try:
                logger.info("Processing Birdeye requests sequentially")
                birdeye_client = api_manager.clients["birdeye"]
                
                # Price endpoint
                try:
                    price_data = await birdeye_client.get_token_price(
                        token_address, include_liquidity=True, check_liquidity=100
                    )
                    if price_data:
                        birdeye_data["price"] = price_data
                        logger.info("Birdeye price data collected")
                except Exception as e:
                    logger.warning(f"Birdeye price endpoint failed: {str(e)}")
                    analysis_response["warnings"].append(f"Birdeye price failed: {str(e)}")
                
                # Wait between Birdeye calls
                await asyncio.sleep(1.0)
                
                # Trades endpoint
                try:
                    trades_data = await birdeye_client.get_token_trades(
                        token_address, sort_type="desc", limit=20
                    )
                    if trades_data:
                        birdeye_data["trades"] = trades_data
                        logger.info("Birdeye trades data collected")
                except Exception as e:
                    logger.warning(f"Birdeye trades endpoint failed: {str(e)}")
                    analysis_response["warnings"].append(f"Birdeye trades failed: {str(e)}")
                
                if birdeye_data:
                    analysis_response["service_responses"]["birdeye"] = birdeye_data
                    analysis_response["data_sources"].append("birdeye")
                    analysis_response["metadata"]["services_attempted"] += 1
                    analysis_response["metadata"]["services_successful"] += 1
                    
            except Exception as e:
                logger.error(f"Birdeye sequential processing failed: {str(e)}")
                analysis_response["errors"].append(f"Birdeye failed: {str(e)}")
        
        # OTHER SERVICES - Run in parallel
        other_tasks = {}
        
        # Helius
        if api_manager.clients.get("helius"):
            other_tasks["helius_supply"] = self._safe_service_call(
                api_manager.clients["helius"].get_token_supply, token_address
            )
            other_tasks["helius_metadata"] = self._safe_service_call(
                api_manager.clients["helius"].get_token_metadata, [token_address]
            )
            analysis_response["metadata"]["services_attempted"] += 1
        
        # SolanaFM
        if api_manager.clients.get("solanafm"):
            other_tasks["solanafm_token"] = self._safe_service_call(
                api_manager.clients["solanafm"].get_token_info, token_address
            )
            analysis_response["metadata"]["services_attempted"] += 1
        
        # DexScreener
        if api_manager.clients.get("dexscreener"):
            other_tasks["dexscreener_pairs"] = self._safe_service_call(
                api_manager.clients["dexscreener"].get_token_pairs, token_address, "solana"
            )
            analysis_response["metadata"]["services_attempted"] += 1
        
        # Execute other services if any
        if other_tasks:
            try:
                logger.info(f"Executing {len(other_tasks)} market analysis services")
                results = await asyncio.wait_for(
                    asyncio.gather(*other_tasks.values(), return_exceptions=True),
                    timeout=20.0
                )
                
                # Process results
                task_names = list(other_tasks.keys())
                for i, task_name in enumerate(task_names):
                    try:
                        result = results[i] if i < len(results) else None
                        service_name = task_name.split("_")[0]
                        
                        if isinstance(result, Exception):
                            analysis_response["errors"].append(f"{task_name}: {str(result)}")
                            continue
                        
                        if result is None:
                            analysis_response["warnings"].append(f"{task_name}: No data returned")
                            continue
                        
                        # Store service response
                        if service_name not in analysis_response["service_responses"]:
                            analysis_response["service_responses"][service_name] = {}
                        
                        analysis_response["service_responses"][service_name][task_name.split("_", 1)[1]] = result
                        
                        if service_name not in analysis_response["data_sources"]:
                            analysis_response["data_sources"].append(service_name)
                            analysis_response["metadata"]["services_successful"] += 1
                        
                        logger.debug(f"{task_name} processed successfully")
                        
                    except Exception as e:
                        logger.warning(f"Error processing {task_name}: {str(e)}")
                        analysis_response["errors"].append(f"Error processing {task_name}: {str(e)}")
                        
            except asyncio.TimeoutError:
                logger.warning("Market analysis services timed out")
                analysis_response["warnings"].append("Some market services timed out")
            except Exception as e:
                logger.error(f"Market analysis execution failed: {str(e)}")
                analysis_response["errors"].append(f"Market analysis failed: {str(e)}")

    async def _generate_security_focused_analysis(self, security_data: Dict[str, Any], token_address: str, passed: bool) -> Dict[str, Any]:
        """Generate analysis focused on security results when security check fails"""
        
        if passed:
            return {
                "score": 70.0,
                "risk_level": "low",
                "recommendation": "consider",
                "confidence": 90.0,
                "confidence_score": 90.0,
                "summary": "Security checks passed",
                "positive_signals": ["Security verification completed"],
                "risk_factors": [],
                "security_focused": True
            }
        
        critical_count = len(security_data.get("critical_issues", []))
        warning_count = len(security_data.get("warnings", []))
        
        return {
            "score": 10.0,
            "risk_level": "critical",
            "recommendation": "avoid",
            "confidence": 95.0,
            "confidence_score": 95.0,
            "summary": f"SECURITY FAILED: {critical_count} critical issues, {warning_count} warnings",
            "positive_signals": [],
            "risk_factors": security_data.get("critical_issues", []) + security_data.get("warnings", []),
            "security_focused": True,
            "critical_security_issues": security_data.get("critical_issues", []),
            "security_warnings": security_data.get("warnings", [])
        }
    
    async def _generate_comprehensive_analysis(self, service_responses: Dict[str, Any], security_data: Dict[str, Any], token_address: str) -> Dict[str, Any]:
        """Generate comprehensive analysis when security checks pass"""
        
        # START WITH SECURITY BASE SCORE (60-95 range)
        security_base = 60  # Minimum for passing security
        if not security_data.get("warnings"):
            security_base = 95  # Excellent security, no warnings
        else:
            warning_count = len(security_data.get("warnings", []))
            security_base = max(60, 90 - (warning_count * 8))  # Reduce by 8 per warning
        
        total_points = security_base
        positive_signals = ["Security checks passed"]
        risk_factors = []
        
        # Add security warnings to risk factors
        if security_data.get("warnings"):
            risk_factors.extend(security_data["warnings"])
        
        # MARKET DATA QUALITY SCORING (0-20 points)
        birdeye_data = service_responses.get("birdeye", {})
        if birdeye_data:
            price_data = birdeye_data.get("price")
            if price_data and price_data.get("value") and float(price_data["value"]) > 0:
                total_points += 10  # Has price data
                positive_signals.append("Token has market price")
                
                # Additional points for price stability/change data
                if price_data.get("price_change_24h") is not None:
                    total_points += 5  # Has price change data
                if price_data.get("update_unix_time"):
                    total_points += 5  # Recent price update
        
        # VOLUME RANGE SCORING (0-25 points)
        if birdeye_data and birdeye_data.get("price"):
            volume = birdeye_data["price"].get("volume_24h")
            if volume:
                try:
                    volume_val = float(volume)
                    if volume_val >= 1000000:  # $1M+
                        total_points += 25
                        positive_signals.append("Excellent trading volume ($1M+)")
                    elif volume_val >= 100000:  # $100K+
                        total_points += 20
                        positive_signals.append("Very good trading volume ($100K+)")
                    elif volume_val >= 10000:  # $10K+
                        total_points += 15
                        positive_signals.append("Good trading volume ($10K+)")
                    elif volume_val >= 1000:  # $1K+
                        total_points += 10
                        positive_signals.append("Moderate trading volume")
                    else:  # < $1K
                        total_points += 3
                        risk_factors.append("Low trading volume")
                except (ValueError, TypeError):
                    pass
        
        # LIQUIDITY RANGE SCORING (0-15 points)
        if birdeye_data and birdeye_data.get("price"):
            liquidity = birdeye_data["price"].get("liquidity")
            if liquidity:
                try:
                    liquidity_val = float(liquidity)
                    if liquidity_val >= 500000:  # $500K+
                        total_points += 15
                        positive_signals.append("Excellent liquidity ($500K+)")
                    elif liquidity_val >= 100000:  # $100K+
                        total_points += 12
                        positive_signals.append("Very good liquidity ($100K+)")
                    elif liquidity_val >= 50000:  # $50K+
                        total_points += 10
                        positive_signals.append("Good liquidity ($50K+)")
                    elif liquidity_val >= 10000:  # $10K+
                        total_points += 6
                        positive_signals.append("Moderate liquidity")
                    else:  # < $10K
                        total_points += 2
                        risk_factors.append("Low liquidity")
                except (ValueError, TypeError):
                    pass
        
        # PRICE STABILITY SCORING (0-10 points)
        if birdeye_data and birdeye_data.get("price"):
            price_change = birdeye_data["price"].get("price_change_24h")
            if price_change is not None:
                try:
                    change_val = abs(float(price_change))
                    if change_val <= 5:  # Very stable
                        total_points += 10
                        positive_signals.append("Price stability (±5%)")
                    elif change_val <= 15:  # Moderate volatility
                        total_points += 6
                    elif change_val <= 30:  # High volatility but not extreme
                        total_points += 3
                    else:  # Extreme volatility
                        risk_factors.append("High price volatility")
                except (ValueError, TypeError):
                    pass
        
        # DATA SOURCE DIVERSITY (0-10 points)
        source_count = len(service_responses)
        if source_count >= 5:
            total_points += 10
            positive_signals.append("Comprehensive data coverage (5+ sources)")
        elif source_count >= 4:
            total_points += 8
            positive_signals.append("Very good data coverage")
        elif source_count >= 3:
            total_points += 6
            positive_signals.append("Good data coverage")
        elif source_count >= 2:
            total_points += 3
            positive_signals.append("Basic data coverage")
        else:
            risk_factors.append("Limited data sources")
        
        # METADATA COMPLETENESS (0-5 points)
        has_name = False
        has_symbol = False
        
        # Check Helius metadata
        helius_data = service_responses.get("helius", {})
        if helius_data:
            if helius_data.get("supply"):
                total_points += 2
                positive_signals.append("On-chain supply data available")
            if helius_data.get("metadata"):
                total_points += 2
                positive_signals.append("Token metadata available")
                # Try to extract name/symbol from metadata
                metadata = helius_data["metadata"]
                if isinstance(metadata, dict):
                    has_name = bool(metadata.get("name"))
                    has_symbol = bool(metadata.get("symbol"))
        
        # Check SolanaFM data
        solanafm_data = service_responses.get("solanafm", {})
        if solanafm_data and solanafm_data.get("token"):
            token_info = solanafm_data["token"]
            if token_info.get("name"):
                has_name = True
            if token_info.get("symbol"):
                has_symbol = True
        
        if has_name and has_symbol:
            total_points += 1
            positive_signals.append("Complete token information")
        
        # NORMALIZE TO 0-100 SCALE
        # Maximum possible points: 95 (security) + 20 (market) + 25 (volume) + 15 (liquidity) + 10 (stability) + 10 (sources) + 5 (metadata) = 180
        max_possible = 180
        final_score = min(100, (total_points / max_possible) * 100)
        
        # Ensure minimum score for tokens that pass security
        final_score = max(60, final_score)
        
        # Determine risk level
        if final_score >= 85:
            risk_level = "low"
            recommendation = "consider"
        elif final_score >= 70:
            risk_level = "low"
            recommendation = "consider"
        elif final_score >= 55:
            risk_level = "medium"
            recommendation = "caution"
        else:
            risk_level = "medium"  # Max medium risk if security passed
            recommendation = "caution"
        
        confidence = min(100, 80 + len(service_responses) * 5)
        
        return {
            "score": round(final_score, 1),
            "risk_level": risk_level,
            "recommendation": recommendation,
            "confidence": round(confidence, 1),
            "confidence_score": round(confidence, 1),
            "summary": f"Security verified. Market analysis from {len(service_responses)} sources.",
            "positive_signals": positive_signals,
            "risk_factors": risk_factors,
            "security_passed": True,
            "services_analyzed": len(service_responses)
        }
    
    async def _safe_service_call(self, service_func, *args, **kwargs):
        """Execute service call with error handling"""
        try:
            result = await service_func(*args, **kwargs) if kwargs else await service_func(*args)
            return result if result is not None else None
        except Exception as e:
            logger.error(f"{service_func.__name__} failed: {str(e)}")
            return None


# Global analyzer instance
token_analyzer = TokenAnalyzer()


async def analyze_token_from_webhook(
    token_address: str, 
    event_type: str = "unknown",
    store_result: bool = True  # Add this parameter
) -> Dict[str, Any]:
    """Analyze token from webhook trigger with storage"""
    try:
        from app.services.ai.ai_token_analyzer import analyze_token_deep_comprehensive
        logger.info(f"🤖 Webhook triggering DEEP AI-enhanced analysis for {token_address}")
        
        # Get analysis result
        analysis_result = await analyze_token_deep_comprehensive(
            token_address=token_address,
            source_event=f"webhook_{event_type}"
        )
        
        # Store result if requested
        if store_result and analysis_result:
            from app.services.analysis_storage import analysis_storage
            
            # Add webhook metadata
            analysis_result["metadata"] = {
                **analysis_result.get("metadata", {}),
                "source_type": "webhook",
                "event_type": event_type,
                "webhook_timestamp": datetime.utcnow().isoformat()
            }
            
            # Store in database
            try:
                await analysis_storage.store_analysis(analysis_result)
                logger.info(f"✅ Webhook analysis stored for {token_address}")
            except Exception as e:
                logger.error(f"❌ Failed to store webhook analysis: {str(e)}")
                # Continue execution even if storage fails
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"❌ Webhook analysis failed for {token_address}: {str(e)}")
        raise


async def analyze_token_on_demand(token_address: str, analysis_type: str = "quick") -> Dict[str, Any]:
    """Analyze token on demand (API call) - supports both quick and deep analysis"""
    
    if analysis_type == "deep":
        from app.services.ai.ai_token_analyzer import analyze_token_deep_comprehensive
        logger.info(f"🤖 API triggering DEEP AI-enhanced analysis for {token_address}")
        return await analyze_token_deep_comprehensive(token_address, "api_deep")
    else:
        # Keep quick analysis for API calls when explicitly requested
        return await token_analyzer.analyze_token_comprehensive(token_address, "api_quick")