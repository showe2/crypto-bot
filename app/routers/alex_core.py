from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Path, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pathlib import Path as PathlibPath
from loguru import logger
from datetime import datetime
from pydantic import BaseModel
import os
import time
import io
import json

from app.core.config import get_settings
from app.core.dependencies import rate_limit_per_ip
from app.utils.health import health_check_all_services

# Import your existing token analyzer
from app.services.analysis_storage import analysis_storage

# Settings and dependencies
settings = get_settings()
router = APIRouter()

class ApiKeyUpdate(BaseModel):
    key: str
    value: str

class FilterRequest(BaseModel):
    adsDEX: bool = True
    globalFee: float = 0
    liqMax: float = 120000
    liqMin: float = 4000
    mcapMax: float = 250000
    mcapMin: float = 10000
    socialMin: float = 50
    timeMax: float = 60
    timeMin: float = 5
    volMax: float = 120000
    volMin: float = 2000
    whales1hMin: float = 800

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

@router.post("/api/keys", summary="Update API Keys")
async def update_api_key(
    key_data: ApiKeyUpdate,
    _: None = Depends(rate_limit_per_ip)
):
    """
    Update API key values at runtime
    
    Accepts:
    - key: The environment variable name (e.g., "HELIUS_API_KEY")
    - value: The new API key value
    """
    try:
        key_name = key_data.key.upper()
        key_value = key_data.value.strip()
        
        # Validate key name (only allow known API keys for security)
        valid_keys = [
            'HELIUS_API_KEY', 'BIRDEYE_API_KEY', 'PUMPFUN_API_KEY', 
            'SOLSNIFFER_API_KEY', 'GOPLUS_APP_KEY', 'GOPLUS_APP_SECRET',
            'GROQ_API_KEY', 'INTERNAL_TOKEN', 'WALLET_SECRET_KEY'
        ]
        
        if key_name not in valid_keys:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid key name. Allowed keys: {', '.join(valid_keys)}"
            )
        
        print("before", os.environ[key_name])
        # Update environment variable
        os.environ[key_name] = key_value

        print("after", os.environ[key_name])
        
        # Update settings instance
        from app.core.config import get_settings
        settings = get_settings()
        setattr(settings, key_name, key_value)
        
        logger.info(f"✅ API key updated: {key_name}")
        
        return {
            "status": "success",
            "message": f"API key {key_name} updated successfully",
            "key": key_name,
            "value_preview": f"{key_value[:8]}***" if key_value else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update API key {key_data.key}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update API key: {str(e)}")
    
    
@router.post("/api/filters", summary="Filter Pump Candidates from Snapshots")
async def filter_pump_candidates(
    filters: FilterRequest,
    _: None = Depends(rate_limit_per_ip)
):
    """Filter pump candidates from existing snapshots"""
    start_time = time.time()
    
    try:
        logger.info(f"🔍 Starting pump filter analysis with filters: {filters.dict()}")
        
        # Get snapshot-based pump analysis
        from app.services.analysis_profiles.pump_profile import PumpAnalysisProfile
        pump_analyzer = PumpAnalysisProfile()
        
        # Run snapshot-based analysis (it handles run_id generation and storage)
        result = await pump_analyzer.analyze_snapshots_for_pumps(filters.dict())
        
        # Extract candidates and run_id from pump analyzer
        candidates = result.get("candidates", [])
        run_id = result.get("run_id")
        
        processing_time = time.time() - start_time
        logger.info(f"✅ Pump filter completed in {processing_time:.2f}s: {len(candidates)} candidates found")
        
        if run_id:
            logger.info(f"📊 Pump analysis saved with run_id: {run_id}")
        
        # Return the exact run_id that was saved in the database
        return {
            "candidates": candidates,
            "total_found": result.get("total_found", len(candidates)),
            "snapshots_analyzed": result.get("snapshots_analyzed", 0),
            "run_id": run_id
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"❌ Pump filter failed: {str(e)}")
        
        return {
            "candidates": [],
            "total_found": 0,
            "snapshots_analyzed": 0,
            "run_id": None
        }
    

@router.get("/api/token/report", summary="Generate Comprehensive Token Report")
async def generate_token_report(
    query: str = Query(..., description="Token address (name/symbol lookup coming soon)"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Generate comprehensive token report using discovery profile
    
    Current: Token address only
    Future: Token names, symbols, URLs (FROG, PEPE, pump.fun, etc.)
    """
    start_time = time.time()
    
    try:
        # For now, only handle token addresses
        token_address = query.strip()
        
        # TODO: Add name/symbol lookup logic
        # if not _is_token_address(token_address):
        #     # Try to resolve name/symbol to address
        #     resolved_address = await _resolve_token_query(query)
        #     if not resolved_address:
        #         raise HTTPException(status_code=400, detail=f"Could not resolve '{query}' to token address")
        #     token_address = resolved_address
        
        # Validate token address format
        if not token_address or len(token_address) < 32 or len(token_address) > 44:
            raise HTTPException(
                status_code=422,
                detail="Invalid Solana token address format"
            )
        
        logger.info(f"🔍 Token report request for {token_address}")
        
        # Use discovery profile for analysis
        from app.services.analysis_profiles.discovery_profile import TokenDiscoveryProfile
        discovery_profile = TokenDiscoveryProfile()
        
        # Run discovery analysis
        result = await discovery_profile.analyze(token_address)
        
        # Log the run_id if present
        if result.get("run_id"):
            logger.info(f"📊 Discovery analysis completed with run_id: {result['run_id']}")
        
        # Return the result
        return result 
        
    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"❌ Token report failed for {query}: {str(e)}")
        
        # Return error (no run_id on failure)
        return {
            "status": "error",
            "analysis_type": "discovery",
            "token_address": query,
            "timestamp": time.time(),
            "processing_time": round(processing_time, 2),
            "message": f"Token report failed: {str(e)}",
            "error": str(e),
            "run_id": None
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

@router.post("/api/docx/{run_id}")
async def generate_run_docx(
    run_id: str = Path(..., description="Analysis run ID"),
    type: str = Query(..., description="Run type: pump, discovery, etc."),
    _: None = Depends(rate_limit_per_ip)
):
    """Generate DOCX report from analysis run data"""
    
    try:
        logger.info(f"📄 DOCX generation request: run_id={run_id}, type={type}")
        
        # Validate type parameter and map to actual profile types
        valid_types = ["pump", "discovery", "whale", "twitter", "listing"]
        if type not in valid_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid type. Must be one of: {', '.join(valid_types)}"
            )
        
        # Map frontend type to actual stored profile type
        profile_type_mapping = {
            "pump": ["pump", "pump_filter"],
            "discovery": ["discovery"],
            "whale": ["whale"],
            "twitter": ["twitter"],
            "listing": ["listing"]
        }
        
        # Try to get run data with different profile type variations
        run_data = None
        for profile_variant in profile_type_mapping[type]:
            run_data = await analysis_storage.get_analysis_run(run_id, profile_variant)
            if run_data:
                logger.info(f"✅ Found run with profile type: {profile_variant}")
                break
        
        if not run_data:
            # Try broader search using ChromaDB directly
            logger.info(f"❌ Run not found with standard profile types, trying broader search...")
            try:
                search_results = await analysis_storage.search_analyses(
                    query=f"run_id {run_id}",
                    limit=5,
                    filters={"doc_type": "analysis_run"}
                )
                
                for result in search_results:
                    metadata = result.get("metadata", {})
                    if metadata.get("run_id") == run_id:
                        # Convert metadata to run_data format
                        try:
                            results_data = json.loads(metadata.get("results_json", "[]"))
                            filters_data = json.loads(metadata.get("filters_applied", "{}"))
                            
                            run_data = {
                                "run_id": metadata.get("run_id"),
                                "profile_type": metadata.get("profile_type"),
                                "timestamp": metadata.get("timestamp_unix"),
                                "tokens_analyzed": metadata.get("tokens_analyzed", 0),
                                "successful_analyses": metadata.get("successful_analyses", 0),
                                "processing_time": metadata.get("processing_time", 0),
                                "status": metadata.get("run_status", "completed"),
                                "results": results_data,
                                "filters": filters_data,
                                "results_count": metadata.get("results_count", 0),
                                "snapshots_analyzed": metadata.get("snapshots_analyzed", 0),
                                "candidates_found": len(results_data)
                            }
                            logger.info(f"✅ Found run via search: {metadata.get('profile_type')}")
                            break
                        except Exception as e:
                            logger.warning(f"Error parsing run data: {e}")
                            continue
            except Exception as e:
                logger.warning(f"Broader search failed: {e}")
        
        if not run_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Run {run_id} not found for type {type}"
            )
        
        logger.info(f"✅ Found run data: {run_data.get('profile_type', 'unknown')} analysis")
        
        # Generate DOCX using the service
        from app.services.ai.docx_service import docx_service
        docx_content = await docx_service.generate_run_docx(run_data, type)
        
        if not docx_content:
            raise HTTPException(
                status_code=500, 
                detail="Failed to generate DOCX content"
            )
        
        # Create filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"{type}_analysis_{run_id[:8]}_{timestamp}.docx"
        
        logger.info(f"✅ DOCX generated successfully ({len(docx_content)} bytes)")
        
        return StreamingResponse(
            io.BytesIO(docx_content),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ DOCX generation failed: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"DOCX generation failed: {str(e)}"
        )

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