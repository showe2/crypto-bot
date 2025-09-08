from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, Path, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pathlib import Path as PathlibPath
from loguru import logger
from datetime import datetime
import time
import io
import json

from app.core.config import get_settings
from app.core.dependencies import rate_limit_per_ip
from app.utils.health import health_check_all_services

# Import your existing token analyzer
from app.services.token_analyzer import token_analyzer
from app.services.analysis_storage import analysis_storage
from app.services.ai.ai_token_analyzer import analyze_token_deep_comprehensive
from app.services.ai.ai_service import generate_analysis_docx_from_cache

# Settings and dependencies
settings = get_settings()
router = APIRouter()

# Initialize templates
templates_dir = PathlibPath("templates")
if templates_dir.exists():
    templates = Jinja2Templates(directory="templates")
    logger.info("✅ Templates system initialized")
else:
    templates = None
    logger.warning("⚠️ Templates directory not found - web interface disabled")


# ==============================================
# TEMPLATE CONTEXT HELPER
# ==============================================

async def get_template_context(request: Request) -> dict:
    """Get common template context for all pages"""
    try:
        # Get API keys status
        api_keys_status = settings.get_all_api_keys_status()
        configured_keys = sum(1 for status in api_keys_status.values() if status['configured'])
        total_keys = len(api_keys_status)
    except Exception as e:
        logger.warning(f"Failed to get API keys status: {e}")
        configured_keys = 0
        total_keys = 0
    
    return {
        "request": request,
        "settings": settings,
        "health_data": None,  # No automatic health data
        "page_title": "Solana Token Analysis AI",
        "version": "1.0.0",
        "environment": settings.ENV,
        "debug_mode": settings.DEBUG,
        "api_keys_configured": configured_keys,
        "total_api_keys": total_keys,
        "current_time": datetime.utcnow().isoformat(),
        "health_check_note": "Health data available at /health endpoint"
    }


# ==============================================
# FRONTEND PAGES
# ==============================================

@router.get("/", response_class=HTMLResponse, summary="Main dashboard page")
async def dashboard_page(request: Request):
    """Main dashboard page with system overview and quick analysis tools"""
    if not templates:
        return JSONResponse({
            "service": "Solana Token Analysis AI System",
            "status": "running",
            "version": "1.0.0",
            "environment": settings.ENV,
            "message": "Web interface not available - templates not found",
            "api_docs": "/docs" if settings.ENV == "development" else None
        })
    
    context = await get_template_context(request)
    context.update({
        "page": "dashboard",
        "title": "Dashboard - Solana Token Analysis AI",
        "active_nav": "dashboard"
    })
    
    return templates.TemplateResponse("pages/dashboard.html", context)


@router.get("/analysis", response_class=HTMLResponse, summary="Token analysis page")
async def analysis_page(request: Request, token: Optional[str] = None):
    """Token analysis page with detailed analysis tools"""
    if not templates:
        return JSONResponse({
            "error": "Web interface not available",
            "message": "Templates not found - use API endpoints instead",
            "api_endpoints": ["/tweet/{token}", "/name/{token}"]
        })
    
    context = await get_template_context(request)
    context.update({
        "page": "analysis",
        "title": "Token Analysis - Solana AI",
        "active_nav": "analysis",
        "selected_token": token,
        "analysis_types": ["quick", "deep"],
        "example_tokens": [
            {"name": "Wrapped SOL", "mint": "So11111111111111111111111111111111111111112", "symbol": "WSOL", "type": "safe"},
            {"name": "Raydium", "mint": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "symbol": "RAY", "type": "safe"},
            {"name": "High Risk Token ⚠️", "mint": "FAqqjnPo3VidhSRb3ADYKG14NvXsWV68Ajr7P9bHq9Tt", "symbol": "FAQOFF", "type": "warning"}
        ]
    })
    
    return templates.TemplateResponse("pages/analysis.html", context)


@router.get("/pump", response_class=HTMLResponse)
async def pump_page(request: Request, token: str = None):
    """Pump analysis page"""
    
    # Example tokens for the input field
    example_tokens = [
        {"name": "Solana", "symbol": "SOL", "mint": "So11111111111111111111111111111111111111112"},
        {"name": "Bonk", "symbol": "BONK", "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
        {"name": "Jupiter", "symbol": "JUP", "mint": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"}
    ]
    
    return templates.TemplateResponse("pages/pump.html", {
        "request": request,
        "selected_token": token,
        "example_tokens": example_tokens
    })


@router.get("/analyses", response_class=HTMLResponse, summary="All analyses page")
async def analyses_page(request: Request):
    """All analyses page with filtering and pagination"""
    if not templates:
        return JSONResponse({
            "error": "Web interface not available",
            "message": "Templates not found - use API endpoints instead",
            "api_endpoints": ["/api/analyses"]
        })
    
    context = await get_template_context(request)
    context.update({
        "page": "analyses",
        "title": "All Analyses - Solana AI",
        "active_nav": "analyses"
    })
    
    return templates.TemplateResponse("pages/analyses.html", context)


@router.get("/marketplace", response_class=HTMLResponse, summary="Token marketplace page")
async def marketplace_page(request: Request):
    """Token marketplace page (coming soon)"""
    if not templates:
        return JSONResponse({
            "error": "Web interface not available",
            "message": "Templates not found - use API endpoints instead",
            "feature": "marketplace",
            "status": "coming_soon"
        })
    
    context = await get_template_context(request)
    context.update({
        "page": "marketplace",
        "title": "Marketplace - Solana AI",
        "active_nav": "marketplace"
    })
    
    return templates.TemplateResponse("pages/marketplace.html", context)

# ==============================================
# PROFILES AND RUNS ANALYSIS ENDPOINTS
# ==============================================
@router.get("/api/pump/results", summary="Get Pump Scan Results")
async def get_pump_scan_results_api(
    run_id: Optional[str] = Query(None, description="Specific run ID to get results from"),
    min_age_hours: Optional[float] = Query(None, description="Maximum pool age in hours"),
    min_liquidity: Optional[float] = Query(None, description="Minimum liquidity USD"),
    min_volume_5m: Optional[float] = Query(None, description="Minimum 5m volume USD"),
    min_buy_sell_ratio: Optional[float] = Query(None, description="Minimum buy/sell ratio"),
    min_trades_5m: Optional[int] = Query(None, description="Minimum trades in 5m"),
    security_gate_only: bool = Query(False, description="Only tokens that passed security gate"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results to return"),
    _: None = Depends(rate_limit_per_ip)
):
    """Get pump scan results with filtering - from specific run or latest run"""
    try:
        from app.services.analysis_storage import analysis_storage
        
        # Build filters
        filters = {}
        if min_age_hours is not None:
            filters["min_age_hours"] = min_age_hours
        if min_liquidity is not None:
            filters["min_liquidity"] = min_liquidity
        if min_volume_5m is not None:
            filters["min_volume_5m"] = min_volume_5m
        if min_buy_sell_ratio is not None:
            filters["min_buy_sell_ratio"] = min_buy_sell_ratio
        if min_trades_5m is not None:
            filters["min_trades_5m"] = min_trades_5m
        if security_gate_only:
            filters["security_gate_only"] = True

        if run_id:
            # Get specific run results
            results = await analysis_storage.get_run_results_with_filters(
                run_id=run_id,
                profile_type="pump",
                filters=filters,
                limit=limit
            )
        else:
            # Get latest pump run
            recent_runs = await analysis_storage.get_recent_runs(profile_type="pump", limit=1)
            if not recent_runs:
                return {
                    "status": "success",
                    "results": [],
                    "run_info": None,
                    "total_results": 0,
                    "message": "No pump scan runs found"
                }
            
            latest_run = recent_runs[0]
            results = await analysis_storage.get_run_results_with_filters(
                run_id=latest_run["run_id"],
                profile_type="pump",
                filters=filters,
                limit=limit
            )
        
        return {
            "status": "success",
            "results": results.get("results", []),
            "run_info": results.get("run_info"),
            "total_results": results.get("total_results", 0),
            "filters_applied": filters,
            "run_id": run_id or (results.get("run_info", {}).get("run_id"))
        }
        
    except Exception as e:
        logger.error(f"Error getting pump scan results: {e}")
        return {
            "status": "error",
            "error": str(e),
            "results": [],
            "run_info": None,
            "total_results": 0
        }

@router.get("/api/pump/status", summary="Get Pump Scan Status") 
async def get_pump_scan_status_api():
    """Get status of pump scanning system"""
    try:
        from app.services.analysis_storage import analysis_storage
        
        # Get tokens eligible for pump analysis (pump: false)
        eligible_tokens = await analysis_storage.get_tokens_for_profile_analysis("pump", limit=100)
        
        # Get recent pump runs
        recent_runs = await analysis_storage.get_recent_runs(profile_type="pump", limit=5)
        
        # Get latest run info
        latest_run = recent_runs[0] if recent_runs else None
        
        # Calculate summary statistics
        total_eligible = len(eligible_tokens)
        
        # Categorize eligible tokens by criteria
        high_liquidity = len([t for t in eligible_tokens if t.get("liquidity", 0) >= 10000])
        high_volume = len([t for t in eligible_tokens if t.get("volume_24h", 0) >= 50000])
        
        status_data = {
            "eligible_tokens": total_eligible,
            "system_ready": total_eligible > 0,
            "last_scan": latest_run,
            "recent_runs": recent_runs,
            "token_breakdown": {
                "total_eligible": total_eligible,
                "high_liquidity": high_liquidity,
                "high_volume": high_volume
            },
            "message": f"{total_eligible} tokens ready for pump scanning (never analyzed by pump profile)" if eligible_tokens else "No eligible tokens found - all tokens have been pump-analyzed"
        }
        
        return status_data
        
    except Exception as e:
        logger.error(f"Error getting pump scan status: {e}")
        return {
            "eligible_tokens": 0,
            "system_ready": False,
            "last_scan": None,
            "recent_runs": [],
            "token_breakdown": {
                "total_eligible": 0,
                "high_liquidity": 0,
                "high_volume": 0
            },
            "message": f"Status check failed: {e}"
        }

@router.get("/api/pump/runs", summary="Get Pump Run History")
async def get_pump_runs_api(
    limit: int = Query(10, ge=1, le=50, description="Number of runs to return"),
    _: None = Depends(rate_limit_per_ip)
):
    """Get pump scan run history"""
    try:
        from app.services.analysis_storage import analysis_storage
        
        runs = await analysis_storage.get_recent_runs(profile_type="pump", limit=limit)
        
        return {
            "status": "success",
            "runs": runs,
            "total_runs": len(runs)
        }
        
    except Exception as e:
        logger.error(f"Error getting pump runs: {e}")
        return {
            "status": "error",
            "error": str(e),
            "runs": [],
            "total_runs": 0
        }

@router.get("/api/runs/{profile_type}", summary="Get Analysis Runs by Profile Type")
async def get_analysis_runs_api(
    profile_type: str = Path(..., description="Profile type (pump, twitter, whale, etc.)"),
    limit: int = Query(10, ge=1, le=50, description="Number of runs to return"),
    _: None = Depends(rate_limit_per_ip)
):
    """Get analysis run history for any profile type"""
    try:
        from app.services.analysis_storage import analysis_storage
        
        # Validate profile type
        valid_profiles = ["pump", "twitter", "whale", "discovery", "listing"]
        if profile_type not in valid_profiles:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid profile type. Must be one of: {', '.join(valid_profiles)}"
            )
        
        runs = await analysis_storage.get_recent_runs(profile_type=profile_type, limit=limit)
        
        return {
            "status": "success",
            "profile_type": profile_type,
            "runs": runs,
            "total_runs": len(runs)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting {profile_type} runs: {e}")
        return {
            "status": "error",
            "error": str(e),
            "profile_type": profile_type,
            "runs": [],
            "total_runs": 0
        }

@router.get("/api/run/{run_id}", summary="Get Specific Analysis Run")
async def get_specific_run_api(
    run_id: str = Path(..., description="Run ID"),
    profile_type: Optional[str] = Query(None, description="Profile type for faster lookup"),
    _: None = Depends(rate_limit_per_ip)
):
    """Get specific analysis run by ID"""
    try:
        from app.services.analysis_storage import analysis_storage
        
        if profile_type:
            # Direct lookup with profile type
            run_data = await analysis_storage.get_analysis_run(run_id, profile_type)
        else:
            # Try each profile type to find the run
            valid_profiles = ["pump", "twitter", "whale", "discovery", "listing"]
            run_data = None
            
            for profile in valid_profiles:
                run_data = await analysis_storage.get_analysis_run(run_id, profile)
                if run_data:
                    break
        
        if not run_data:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        
        return {
            "status": "success",
            "run": run_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting run {run_id}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "run": None
        }

@router.get("/api/profile/{profile_type}/status", summary="Get Profile Analysis Status")
async def get_profile_status_api(
    profile_type: str = Path(..., description="Profile type (pump, twitter, whale, etc.)"),
    _: None = Depends(rate_limit_per_ip)
):
    """Get status for any profile analysis type"""
    try:
        from app.services.analysis_storage import analysis_storage
        
        # Validate profile type
        valid_profiles = ["pump", "twitter", "whale", "discovery", "listing"]
        if profile_type not in valid_profiles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid profile type. Must be one of: {', '.join(valid_profiles)}"
            )
        
        # Get tokens eligible for this profile analysis
        eligible_tokens = await analysis_storage.get_tokens_for_profile_analysis(profile_type, limit=100)
        
        # Get recent runs for this profile
        recent_runs = await analysis_storage.get_recent_runs(profile_type=profile_type, limit=5)
        
        # Get latest run info
        latest_run = recent_runs[0] if recent_runs else None
        
        # Calculate summary statistics
        total_eligible = len(eligible_tokens)
        
        status_data = {
            "profile_type": profile_type,
            "eligible_tokens": total_eligible,
            "system_ready": total_eligible > 0,
            "last_scan": latest_run,
            "recent_runs": recent_runs,
            "message": f"{total_eligible} tokens ready for {profile_type} analysis" if eligible_tokens else f"No eligible tokens found for {profile_type} analysis"
        }
        
        return status_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting {profile_type} status: {e}")
        return {
            "profile_type": profile_type,
            "eligible_tokens": 0,
            "system_ready": False,
            "last_scan": None,
            "recent_runs": [],
            "message": f"Status check failed: {e}"
        }

# ==============================================
# TOKEN ANALYSIS ENDPOINTS (Frontend Integration)
# ==============================================

@router.post("/deep/{token_mint}", summary="Deep Token Analysis with AI Integration")
async def deep_analysis_endpoint(
    token_mint: str = Path(..., description="Token mint address"),
    force_refresh: bool = Query(False, description="Force refresh cached data"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Deep token analysis with AI integration using Llama 3.0
    
    This endpoint provides comprehensive analysis including:
    - Security checks (GOplus, RugCheck, SolSniffer)  
    - Market analysis (Birdeye, Helius, SolanaFM, DexScreener)
    - AI analysis with Llama 3.0 (MCAP, liquidity, volume, holders, LP, dev %, snipers/bundlers)
    - Enhanced scoring system combining traditional + AI insights
    - Structured recommendations with stop flags
    
    Flow: Security → Market → AI → Enhanced Analysis → Database → Response
    """
    start_time = time.time()
    
    try:
        # Validate token mint format
        if not token_mint or len(token_mint) < 32 or len(token_mint) > 44:
            raise HTTPException(
                status_code=422,
                detail="Invalid Solana token mint address format"
            )
        
        logger.info(f"🔍 Deep analysis request for {token_mint}")
        
        # Determine source event
        source_event = "api_deep"
        if force_refresh:
            source_event = "api_deep_refresh"
        
        # Perform deep comprehensive analysis with AI
        analysis_result = await analyze_token_deep_comprehensive(token_mint, source_event)
        
        # Add endpoint metadata
        analysis_result["metadata"]["from_cache"] = not force_refresh
        analysis_result["metadata"]["force_refresh"] = force_refresh
        analysis_result["metadata"]["api_response_time"] = round((time.time() - start_time) * 1000, 1)
        analysis_result["metadata"]["endpoint"] = "/deep"
        
        # Log successful analysis
        ai_enhanced = analysis_result.get("ai_analysis", {})
        ai_score = ai_enhanced.get("ai_score", 0) if ai_enhanced else 0
        overall_score = analysis_result.get("overall_analysis", {}).get("score", 0)
        
        logger.info(
            f"✅ Deep analysis completed for {token_mint} in {analysis_result['metadata']['processing_time_seconds']}s "
            f"(AI score: {ai_score}, Overall: {overall_score}, "
            f"Recommendation: {analysis_result.get('overall_analysis', {}).get('recommendation', 'N/A')})"
        )
        
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"❌ Deep analysis failed for {token_mint}: {str(e)}")
        
        # Return structured error response
        return {
            "status": "error",
            "analysis_type": "deep",
            "token_address": token_mint,
            "timestamp": time.time(),
            "processing_time": round(processing_time, 2),
            "message": f"Deep analysis failed: {str(e)}",
            "error": str(e),
            "endpoint": "/deep",
            "ai_analysis_attempted": True,
            "ai_analysis_completed": False,
            "metadata": {
                "processing_time_seconds": processing_time,
                "services_attempted": 0,
                "services_successful": 0,
                "security_check_passed": False,
                "ai_analysis_completed": False,
                "analysis_stopped_at_security": False
            }
        }


@router.get("/deep/{token_mint}", summary="Get Deep Token Analysis (GET endpoint)")
async def get_deep_analysis(
    token_mint: str = Path(..., description="Token mint address"),
    force_refresh: bool = Query(False, description="Force refresh cached data"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Alternative GET endpoint for deep token analysis
    """
    return await deep_analysis_endpoint(token_mint, force_refresh)


# Update the existing quick analysis to clearly differentiate from deep
@router.post("/quick/{token_mint}", summary="Quick Token Analysis - Security + Market Only")
async def quick_analysis_endpoint(
    token_mint: str = Path(..., description="Token mint address"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Quick token analysis without AI integration
    
    Includes:
    - Security checks (GOplus, RugCheck, SolSniffer)
    - Market analysis (Birdeye, Helius, SolanaFM, DexScreener)  
    - Traditional scoring system
    
    For AI-enhanced analysis, use /deep endpoint instead.
    """
    start_time = time.time()
    
    try:
        # Validate token mint format
        if not token_mint or len(token_mint) < 32 or len(token_mint) > 44:
            raise HTTPException(
                status_code=422,
                detail="Invalid Solana token mint address format"
            )
        
        logger.info(f"⚡ Quick analysis request for {token_mint}")
        
        # Use existing comprehensive analysis from token_analyzer
        from app.services.token_analyzer import token_analyzer
        analysis_result = await token_analyzer.analyze_token_comprehensive(token_mint, "api_quick")
        
        # Add endpoint metadata
        analysis_result["metadata"]["api_response_time"] = round((time.time() - start_time) * 1000, 1)
        analysis_result["metadata"]["endpoint"] = "/quick"
        analysis_result["analysis_type"] = "quick"
        
        # Log successful analysis
        logger.info(
            f"✅ Quick analysis completed for {token_mint} in {analysis_result['metadata']['processing_time_seconds']}s "
            f"(Score: {analysis_result['overall_analysis']['score']}, "
            f"Risk: {analysis_result['overall_analysis']['risk_level']})"
        )
        
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"❌ Quick analysis failed for {token_mint}: {str(e)}")
        
        return {
            "status": "error",
            "analysis_type": "quick", 
            "token_address": token_mint,
            "timestamp": time.time(),
            "processing_time": round(processing_time, 2),
            "message": f"Quick analysis failed: {str(e)}",
            "error": str(e),
            "endpoint": "/quick",
            "metadata": {
                "processing_time_seconds": processing_time,
                "services_attempted": 0,
                "services_successful": 0,
                "security_check_passed": False,
                "analysis_stopped_at_security": False
            }
        }
    
@router.get("/document/{cache_key:path}")
async def download_analysis_document(
    cache_key: str,
    background_tasks: BackgroundTasks,
    source: Optional[str] = Query(None)
):
    """Download DOCX report - runs fresh analysis if cache miss"""
    
    try:
        logger.info(f"📄 DOCX download request for cache key: {cache_key}")
        
        # Try cache first
        docx_content = await generate_analysis_docx_from_cache(cache_key)
        
        if not docx_content:
            logger.info("❌ Cache miss, running fresh analysis...")
            
            # Extract token address and type
            token_address = _extract_token_info_from_cache_key(cache_key)

            analysis_type = "deep"
            source_event = "api_deep"

            if source is not None and "quick" in source:
                analysis_type = "quick"
                source_event = source

            if not token_address:
                raise HTTPException(status_code=404, detail="Invalid cache key")
            
            logger.info(f"🔄 Running fresh {analysis_type} analysis for {token_address}")
            
            # Run fresh analysis
            if analysis_type == "deep":
                analysis_result = await analyze_token_deep_comprehensive(token_address, source_event)
            else:
                analysis_result = await token_analyzer.analyze_token_comprehensive(token_address, source_event)
            
            if not analysis_result or analysis_result.get("status") == "error":
                raise HTTPException(status_code=500, detail="Fresh analysis failed")
            
            # Generate DOCX directly from fresh data
            docx_content = await _generate_docx_from_fresh_data(analysis_result)
            
            if not docx_content:
                raise HTTPException(status_code=500, detail="DOCX generation failed")
        
        # Get filename
        token_address = _extract_token_info_from_cache_key(cache_key)
        token_part = token_address[:8] if token_address else "unknown"
        filename = f"token_analysis_{token_part}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
        
        return StreamingResponse(
            io.BytesIO(docx_content),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Document download failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate document: {str(e)}")
    
def _extract_token_info_from_cache_key(cache_key: str) -> str:
    """Extract token address and analysis type from cache key"""
    try:
        logger.debug(f"Extracting token info from cache key: {cache_key}")
        
        # Split cache key
        parts = cache_key.split("_")
        
        if len(parts) < 2:
            logger.warning(f"Invalid cache key format: {cache_key}")
            return None
        
        # Extract token address (should be the last part)
        token_address = parts[-1]
        
        logger.debug(f"Extracted: token={token_address}")
        
        # Validate token address format (basic Solana address validation)
        if not token_address or len(token_address) < 32 or len(token_address) > 44:
            logger.warning(f"Invalid token address format: {token_address}")
            return None
        
        return token_address
        
    except Exception as e:
        logger.error(f"Error extracting token info from cache key: {e}")
        return None
    
async def _generate_docx_from_fresh_data(analysis_result: Dict[str, Any]) -> Optional[bytes]:
    """Generate DOCX directly from fresh analysis data"""
    
    try:
        logger.info("📄 Generating DOCX from fresh analysis data")
        
        # Use the existing DOCX service
        from app.services.ai.docx_service import docx_service
        
        # Generate DOCX directly from analysis data
        docx_bytes = await docx_service.generate_analysis_docx_from_data(analysis_result)
        
        if docx_bytes:
            logger.info(f"✅ DOCX generated successfully ({len(docx_bytes)} bytes)")
            return docx_bytes
        else:
            logger.error("❌ DOCX service returned no content")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error generating DOCX from fresh data: {str(e)}")
        return None

# ==============================================
# API ENDPOINTS FOR FRONTEND
# ==============================================

@router.get("/api/dashboard", summary="Dashboard data API")
async def dashboard_api():
    """Get dashboard data for frontend - using real system metrics and ChromaDB data"""
    try:
        # Get real system health
        # No automatic health checks - use fallback data
        health_data = {"overall_status": True, "summary": {"healthy_services": 0, "total_services": 1}}
        
        # Calculate real metrics based on system data
        healthy_services = health_data.get("summary", {}).get("healthy_services", 0)
        total_services = health_data.get("summary", {}).get("total_services", 1)
        
        recent_analyses_data = await _get_recent_analyses_from_chromadb(limit=10)
        total_analyses = recent_analyses_data.get("total_count", 0)
        recent_analyses = recent_analyses_data.get("analyses", [])
        
        # Log recent analyses order
        if recent_analyses:
            logger.info(f"📊 Dashboard showing {len(recent_analyses)} most recent analyses:")
            for i, analysis in enumerate(recent_analyses[:3]):  # Show first 3
                logger.info(f"  {i+1}. {analysis['token_symbol']} - {analysis['time']} (timestamp: {analysis['timestamp']})")
        
        # Calculate success rate from recent analyses
        if recent_analyses:
            # Count successful analyses (completed, warnings are still successful)
            successful_analyses = len([a for a in recent_analyses if a.get("status") in ["completed", "warnings"]])
            success_rate = (successful_analyses / len(recent_analyses)) * 100
            logger.debug(f"Success rate calculation: {successful_analyses}/{len(recent_analyses)} = {success_rate}%")
        else:
            # Fallback to system health if no analysis data
            success_rate = (healthy_services / total_services * 100) if total_services > 0 else 0
        
        # Calculate average response time from recent analyses (only successful ones)
        if recent_analyses:
            processing_times = [a.get("processing_time", 0) for a in recent_analyses 
                              if a.get("processing_time", 0) > 0 and a.get("status") in ["completed", "warnings"]]
            avg_response_time = sum(processing_times) / len(processing_times) if processing_times else 0
            logger.debug(f"Avg response time: {avg_response_time}s from {len(processing_times)} analyses")
        else:
            avg_response_time = 0
        
        # Count unique active tokens from recent analyses
        if recent_analyses:
            unique_tokens = set(a.get("token_address") for a in recent_analyses if a.get("token_address"))
            active_tokens = len(unique_tokens)
        else:
            active_tokens = 0
        
        # Real metrics based on actual analysis data
        dashboard_data = {
            "metrics": {
                "totalAnalyses": total_analyses,
                "successRate": round(success_rate, 1),
                "avgResponseTime": round(avg_response_time, 2),
                "activeTokens": active_tokens
            },
            "systemHealth": {
                "overall_status": health_data.get("overall_status", False),
                "healthy_services": healthy_services,
                "total_services": total_services
            },
            "recentActivity": recent_analyses,  # 🆕 Now contains most recent analyses
            "aiModels": {
                "mistral": {"status": "ready", "type": "Quick Analysis"},
                "llama": {"status": "ready", "type": "Deep Analysis"}  # Updated status
            },
            "chromadb_status": recent_analyses_data.get("chromadb_available", False)
        }
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Dashboard API error: {e}")
        return {
            "metrics": {
                "totalAnalyses": 0,
                "successRate": 0,
                "avgResponseTime": 0,
                "activeTokens": 0
            },
            "systemHealth": {
                "overall_status": False,
                "healthy_services": 0,
                "total_services": 0
            },
            "recentActivity": [],
            "aiModels": {
                "mistral": {"status": "unknown", "type": "Quick Analysis"},
                "llama": {"status": "unknown", "type": "Deep Analysis"}
            },
            "chromadb_status": False
        }


@router.get("/api/analyses", summary="Get All Analyses with Pagination and Filters")
async def get_all_analyses_api(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    source_event: Optional[str] = Query(None, description="Filter by source event"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    security_status: Optional[str] = Query(None, description="Filter by security status"),
    search: Optional[str] = Query(None, description="Search by token address, name, or symbol"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Get paginated list of all analyses with filtering options - ORDERED BY MOST RECENT FIRST
    """
    try:
        logger.info(f"📊 Retrieving analyses - Page {page}, Per page {per_page} (most recent first)")
        
        # Build filters
        filters = {}
        if source_event:
            filters["source_event"] = source_event
        if date_from:
            filters["date_from"] = date_from
        if date_to:
            filters["date_to"] = date_to
        if risk_level:
            filters["risk_level"] = risk_level
        if security_status:
            filters["security_status"] = security_status
        if search:
            filters["search"] = search
            
        # Get analyses with pagination using existing ChromaDB integration
        result = await _get_analyses_paginated(
            page=page,
            per_page=per_page,
            filters=filters
        )
        
        if not result:
            # Return empty result if ChromaDB not available
            return {
                "analyses": [],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_items": 0,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False
                },
                "filters_applied": filters,
                "chromadb_available": False,
                "message": "Analysis history not available - ChromaDB not connected"
            }
        
        analyses = result.get("analyses", [])
        if analyses:
            analyses.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            logger.debug(f"✅ Frontend backup sort applied: {len(analyses)} analyses")
            
            # Debug: Show first few results
            for i, analysis in enumerate(analyses[:3]):
                logger.debug(f"  {i+1}. {analysis['token_symbol']} - {_format_analysis_date(analysis['timestamp'])}")
        
        result["analyses"] = analyses  # Update with sorted analyses
            
        logger.info(f"✅ Retrieved {len(analyses)} analyses (most recent first)")
        
        return {
            **result,
            "filters_applied": filters,
            "chromadb_available": True
        }
        
    except Exception as e:
        logger.error(f"❌ Error retrieving analyses: {str(e)}")
        
        # Return graceful fallback instead of error
        return {
            "analyses": [],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_items": 0,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False
            },
            "filters_applied": filters,
            "chromadb_available": False,
            "error": str(e),
            "message": "Failed to retrieve analyses"
        }


async def _get_analyses_paginated(page: int = 1, per_page: int = 20, filters: dict = None) -> dict:
    """
    Get paginated analyses with filtering - integrates with existing ChromaDB - FIXED for most recent first
    """
    try:
        from app.utils.chroma_client import get_chroma_client
        
        chroma_client = await get_chroma_client()
        if not chroma_client.is_connected():
            logger.debug("ChromaDB not available for paginated analyses")
            return None
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Build search parameters - GET MORE results for proper sorting
        search_params = {
            "limit": 500,  # 🆕 Get many more results to ensure proper sorting
        }
        
        # For ChromaDB, we need to handle filtering differently
        # If no filters, get all analyses without where clause
        if not filters or not any(filters.get(k) for k in ['source_event', 'risk_level', 'security_status', 'date_from', 'date_to']):
            # No filters - use simple search
            logger.debug("No filters applied, using simple search")
            if filters and filters.get("search"):
                search_query = filters["search"]
                results = await analysis_storage.search_analyses(
                    query=search_query,
                    limit=search_params["limit"]
                )
            else:
                results = await analysis_storage.search_analyses(
                    query="token analysis",
                    limit=search_params["limit"]
                )
        else:
            # We have filters - need to work around ChromaDB limitations
            # Get all results first, then filter in Python
            logger.debug(f"Filters applied: {filters}, getting all results for manual filtering")
            
            if filters and filters.get("search"):
                search_query = filters["search"]
                all_results = await analysis_storage.search_analyses(
                    query=search_query,
                    limit=1000  # Get even more results for filtering
                )
            else:
                all_results = await analysis_storage.search_analyses(
                    query="token analysis",
                    limit=1000  # Get more results for filtering
                )
            
            # Filter results in Python
            if all_results:
                filtered_results = []
                for result in all_results:
                    metadata = result.get("metadata", {})
                    include = True
                    
                    # Apply filters
                    if filters.get("source_event") and metadata.get("source_event") != filters["source_event"]:
                        include = False
                    
                    if filters.get("risk_level") and metadata.get("risk_level") != filters["risk_level"]:
                        include = False
                    
                    if filters.get("security_status") and metadata.get("security_status") != filters["security_status"]:
                        include = False
                    
                    # Date filters
                    if filters.get("date_from"):
                        try:
                            from datetime import datetime
                            date_from_ts = datetime.strptime(filters["date_from"], "%Y-%m-%d").timestamp()
                            if metadata.get("timestamp_unix", 0) < date_from_ts:
                                include = False
                        except ValueError:
                            pass
                    
                    if filters.get("date_to"):
                        try:
                            from datetime import datetime
                            date_to_ts = datetime.strptime(filters["date_to"], "%Y-%m-%d").timestamp() + 86400
                            if metadata.get("timestamp_unix", 0) > date_to_ts:
                                include = False
                        except ValueError:
                            pass
                    
                    if include:
                        filtered_results.append(result)
                
                results = filtered_results
                logger.debug(f"After Python filtering: {len(results)} results")
            else:
                results = []
        
        logger.debug(f"Search returned {len(results) if results else 0} results")
        
        if not results:
            return {
                "analyses": [],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_items": 0,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": page > 1
                }
            }
        
        # Sort results by date (most recent first) BEFORE pagination
        results.sort(key=lambda x: x.get("metadata", {}).get("timestamp_unix", 0), reverse=True)
        logger.debug(f"Results sorted by date (most recent first)")
        
        # Get total count for pagination
        total_items = len(results)  # Total filtered results
        
        # Apply pagination to sorted results (slice the results we got)
        paginated_results = results[offset:offset + per_page] if len(results) > offset else []
        logger.debug(f"After pagination: {len(paginated_results)} results for page {page}")
        
        # Log first few results to verify sorting
        if paginated_results:
            logger.debug(f"📊 Page {page} most recent analyses:")
            for i, result in enumerate(paginated_results[:3]):
                metadata = result.get("metadata", {})
                timestamp = metadata.get("timestamp_unix", 0)
                token_symbol = metadata.get("token_symbol", "Unknown")
                logger.debug(f"  {i+1}. {token_symbol} - {_format_analysis_date(timestamp)} (ts: {timestamp})")
        
        # Process results for frontend display
        analyses = []
        for result in paginated_results:
            metadata = result.get("metadata", {})
            
            # Skip if no valid timestamp
            if not metadata.get("timestamp_unix"):
                continue
            
            # Determine status
            status = "completed"
            if metadata.get("analysis_stopped_at_security"):
                status = "security_failed"
            elif metadata.get("critical_issues_count", 0) > 0:
                status = "critical_issues"
            elif metadata.get("warnings_count", 0) > 0:
                status = "warnings"

            try:
                critical_issues_list = json.loads(metadata.get("critical_issues_list", "[]"))
            except (json.JSONDecodeError, TypeError):
                critical_issues_list = []

            try:
                warnings_list = json.loads(metadata.get("warnings_list", "[]"))
            except (json.JSONDecodeError, TypeError):
                warnings_list = []

            if metadata.get("warnings_count", 0) > 0 and metadata.get("critical_issues_count", 0) == 0:
                security_status = "warning" 
            else:
                security_status = metadata.get("security_status", "unknown")
            
            analysis = {
                # Basic identifiers
                "id": metadata.get("analysis_id", "unknown"),
                "token_symbol": metadata.get("token_symbol", "N/A"),
                "token_name": metadata.get("token_name", "Unknown Token"),
                "token_address": metadata.get("token_address"),
                "mint": metadata.get("token_address"),  # For backward compatibility
                "status": status,
                
                # Keep NEW schema field names (don't convert)
                "security_status": security_status,  # Keep as "safe"/"unsafe"/"warning"
                "critical_issues_count": metadata.get("critical_issues_count", 0),  # Keep new name
                "warnings_count": metadata.get("warnings_count", 0),  # Keep new name
                "critical_issues_list": critical_issues_list,
                "warnings_list": warnings_list,
                
                # All the new fields your popup expects
                "has_ai_analysis": metadata.get("has_ai_analysis", False),
                "ai_score": metadata.get("ai_score", 0),
                "ai_recommendation": metadata.get("ai_recommendation"),
                "ai_risk_assessment": metadata.get("ai_risk_assessment", "unknown"),
                "ai_stop_flags_count": metadata.get("ai_stop_flags_count", 0),
                
                # Market data
                "price_usd": metadata.get("price_usd"),
                "price_change_24h": metadata.get("price_change_24h"),
                "volume_24h": metadata.get("volume_24h"),
                "market_cap": metadata.get("market_cap"),
                "liquidity": metadata.get("liquidity"),
                
                # Enhanced metrics
                "whale_count": metadata.get("whale_count", 0),
                "whale_control_percent": metadata.get("whale_control_percent", 0),
                "sniper_risk": metadata.get("sniper_risk", "unknown"),
                "volatility_risk": metadata.get("volatility_risk", "unknown"),
                
                # Security details
                "security_score": metadata.get("security_score", 0),
                "mint_authority_active": metadata.get("mint_authority_active", False),
                "freeze_authority_active": metadata.get("freeze_authority_active", False),
                
                # Metadata
                "risk_level": metadata.get("risk_level", "unknown"),
                "overall_score": metadata.get("overall_score", 0),
                "recommendation": metadata.get("recommendation", "HOLD"),
                "processing_time": metadata.get("processing_time", 0),
                "services_successful": metadata.get("services_successful", 0),
                "data_completeness": metadata.get("data_completeness", 0),
                "analysis_type": metadata.get("analysis_type", "unknown"),
                "timestamp": metadata.get("timestamp_unix", 0),
                "time": _format_relative_time(metadata.get("timestamp_unix", 0)),
                "source_event": metadata.get("source_event", "unknown")
            }
            analyses.append(analysis)
        
        # Calculate pagination
        total_pages = (total_items + per_page - 1) // per_page
        has_next = page < total_pages
        has_prev = page > 1
        
        logger.debug(f"Returning {len(analyses)} analyses, total_items: {total_items}, total_pages: {total_pages}")
        
        return {
            "analyses": analyses,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev
            }
        }
        
    except Exception as e:
        logger.error(f"Error in paginated analyses query: {str(e)}")
        return None


async def _get_recent_analyses_from_chromadb(limit: int = 10) -> Dict[str, Any]:
    """Get recent analyses from ChromaDB for dashboard display - FIXED to get most recent"""
    try:
        from app.utils.chroma_client import get_chroma_client
        
        chroma_client = await get_chroma_client()
        if not chroma_client.is_connected():
            logger.debug("ChromaDB not available for dashboard data")
            return {
                "chromadb_available": False,
                "total_count": 0,
                "analyses": []
            }
        
        # Search for recent analyses - GET MORE than we need to sort properly
        results = await analysis_storage.search_analyses(
            query="recent token analysis",
            limit=50,  # Get more results to ensure proper sorting
            filters={}
        )
        
        # Get collection stats for total count
        try:
            stats = await chroma_client.get_collection_stats()
            total_count = stats.get("total_documents", 0)
        except Exception:
            total_count = len(results) if results else 0
        
        # Transform results for dashboard display
        dashboard_analyses = []
        for result in results:
            metadata = result.get("metadata", {})
            
            # Skip entries without valid timestamps
            if not metadata.get("timestamp_unix"):
                continue
            
            # Determine status based on analysis result
            status = "completed"  # Default to completed
            if metadata.get("analysis_stopped_at_security"):
                status = "security_failed"
            elif metadata.get("critical_issues_count", 0) > 0:
                status = "critical_issues"
            elif metadata.get("warnings_count", 0) > 0:
                status = "warnings"
            # Note: "warnings" status is still considered successful for success rate calculation
            
            try:
                critical_issues_list = json.loads(metadata.get("critical_issues_list", "[]"))
            except (json.JSONDecodeError, TypeError):
                critical_issues_list = []

            try:
                warnings_list = json.loads(metadata.get("warnings_list", "[]"))
            except (json.JSONDecodeError, TypeError):
                warnings_list = []

            if metadata.get("warnings_count", 0) > 0 and metadata.get("critical_issues_count", 0) == 0:
                security_status = "warning" 
            else:
                security_status = metadata.get("security_status", "unknown")

            # Format for dashboard display
            analysis_item = {
                # Basic identifiers
                "id": metadata.get("analysis_id", "unknown"),
                "token_symbol": metadata.get("token_symbol", "N/A"),
                "token_name": metadata.get("token_name", "Unknown Token"),
                "token_address": metadata.get("token_address"),
                "mint": metadata.get("token_address"),  # For backward compatibility
                "status": status,
                
                # Keep NEW schema field names (don't convert)
                "security_status": security_status,  # Keep as "safe"/"unsafe"/"warning"
                "critical_issues_count": metadata.get("critical_issues_count", 0),  # Keep new name
                "warnings_count": metadata.get("warnings_count", 0),  # Keep new name
                "critical_issues_list": critical_issues_list,
                "warnings_list": warnings_list,
                
                # All the new fields your popup expects
                "has_ai_analysis": metadata.get("has_ai_analysis", False),
                "ai_score": metadata.get("ai_score", 0),
                "ai_recommendation": metadata.get("ai_recommendation"),
                "ai_risk_assessment": metadata.get("ai_risk_assessment", "unknown"),
                "ai_stop_flags_count": metadata.get("ai_stop_flags_count", 0),
                
                # Market data
                "price_usd": metadata.get("price_usd"),
                "price_change_24h": metadata.get("price_change_24h"),
                "volume_24h": metadata.get("volume_24h"),
                "market_cap": metadata.get("market_cap"),
                "liquidity": metadata.get("liquidity"),
                
                # Enhanced metrics
                "whale_count": metadata.get("whale_count", 0),
                "whale_control_percent": metadata.get("whale_control_percent", 0),
                "sniper_risk": metadata.get("sniper_risk", "unknown"),
                "volatility_risk": metadata.get("volatility_risk", "unknown"),
                
                # Security details
                "security_score": metadata.get("security_score", 0),
                "mint_authority_active": metadata.get("mint_authority_active", False),
                "freeze_authority_active": metadata.get("freeze_authority_active", False),
                
                # Metadata
                "risk_level": metadata.get("risk_level", "unknown"),
                "overall_score": metadata.get("overall_score", 0),
                "recommendation": metadata.get("recommendation", "HOLD"),
                "processing_time": metadata.get("processing_time", 0),
                "services_successful": metadata.get("services_successful", 0),
                "data_completeness": metadata.get("data_completeness", 0),
                "analysis_type": metadata.get("analysis_type", "unknown"),
                "timestamp": metadata.get("timestamp_unix", 0),
                "time": _format_relative_time(metadata.get("timestamp_unix", 0)),
                "source_event": metadata.get("source_event", "unknown")
            }
            
            dashboard_analyses.append(analysis_item)
        
        dashboard_analyses.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        dashboard_analyses = dashboard_analyses[:limit]
        
        logger.debug(f"📊 Retrieved {len(dashboard_analyses)} most recent analyses from ChromaDB")
        if dashboard_analyses:
            logger.debug(f"📊 Most recent analysis: {dashboard_analyses[0]['token_symbol']} at {_format_relative_time(dashboard_analyses[0]['timestamp'])}")
        
        return {
            "chromadb_available": True,
            "total_count": total_count,
            "analyses": dashboard_analyses
        }
        
    except Exception as e:
        logger.warning(f"Error getting recent analyses from ChromaDB: {str(e)}")
        return {
            "chromadb_available": False,
            "total_count": 0,
            "analyses": [],
            "error": str(e)
        }

def _format_relative_time(timestamp_unix: int) -> str:
    """Format unix timestamp as relative time"""
    try:
        from datetime import datetime
        import time
        
        if not timestamp_unix:
            return "Unknown"
        
        now = time.time()
        diff = now - timestamp_unix
        
        if diff < 60:
            return "Just now"
        elif diff < 3600:
            minutes = int(diff / 60)
            return f"{minutes}m ago"
        elif diff < 86400:
            hours = int(diff / 3600)
            return f"{hours}h ago"
        elif diff < 2592000:  # 30 days
            days = int(diff / 86400)
            return f"{days}d ago"
        else:
            dt = datetime.fromtimestamp(timestamp_unix)
            return dt.strftime("%b %d")
            
    except Exception:
        return "Unknown"


def _format_analysis_date(timestamp_unix: int) -> str:
    """Format unix timestamp as date for analyses page"""
    try:
        from datetime import datetime
        import time
        
        if not timestamp_unix:
            return "Unknown"
        
        now = time.time()
        diff = now - timestamp_unix
        
        # For analyses page, show more detailed date information
        if diff < 86400:  # Less than 24 hours
            dt = datetime.fromtimestamp(timestamp_unix)
            return dt.strftime("Today %H:%M")
        elif diff < 172800:  # Less than 48 hours (2 days)
            dt = datetime.fromtimestamp(timestamp_unix)
            return dt.strftime("Yesterday %H:%M")
        elif diff < 604800:  # Less than 7 days
            dt = datetime.fromtimestamp(timestamp_unix)
            return dt.strftime("%A %H:%M")  # Day name + time
        else:
            dt = datetime.fromtimestamp(timestamp_unix)
            return dt.strftime("%b %d, %Y")  # Full date
            
    except Exception:
        return "Unknown"