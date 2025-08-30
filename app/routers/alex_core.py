from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, Path, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pathlib import Path as PathlibPath
from loguru import logger
from datetime import datetime
import time
import io

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
        # Get system health
        health_data = await health_check_all_services()
    except Exception as e:
        logger.warning(f"Failed to get health data for template: {e}")
        health_data = None
    
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
        "health_data": health_data,
        "page_title": "Solana Token Analysis AI",
        "version": "1.0.0",
        "environment": settings.ENV,
        "debug_mode": settings.DEBUG,
        "api_keys_configured": configured_keys,
        "total_api_keys": total_keys,
        "current_time": datetime.utcnow().isoformat()
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
            {"name": "Wrapped SOL", "mint": "So11111111111111111111111111111111111111112", "symbol": "WSOL"},
            {"name": "USD Coin", "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "symbol": "USDC"},
            {"name": "Raydium", "mint": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "symbol": "RAY"}
        ]
    })
    
    return templates.TemplateResponse("pages/analysis.html", context)


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
    background_tasks: BackgroundTasks
):
    """Download DOCX report for cached analysis - FIXED"""
    
    try:
        logger.info(f"📄 DOCX download request for cache key: {cache_key}")
        
        # Generate DOCX
        docx_content = await generate_analysis_docx_from_cache(cache_key)
        
        if not docx_content:
            logger.warning(f"❌ No DOCX content found for cache key: {cache_key}")
            raise HTTPException(
                status_code=404, 
                detail="Analysis data not found or expired (available for 2 hours only)"
            )
        
        # Extract token info from cache key for filename
        try:
            # Extract token address from key: "namespace:type:TOKEN_ADDRESS"
            if ":" in cache_key:
                parts = cache_key.split(":")
                if len(parts) >= 3:
                    token_part = parts[-1][:8]  # Last part (token), first 8 chars
                elif len(parts) >= 2:
                    token_part = parts[-1][:8]  # Last part, first 8 chars
                else:
                    token_part = "unknown"
            else:
                token_part = cache_key[:8]  # First 8 chars of key
        except Exception:
            token_part = "unknown"
        
        filename = f"token_analysis_{token_part}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
        
        logger.info(f"✅ DOCX ready for download, filename: {filename}")
        
        # Return as downloadable file
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

# ==============================================
# API ENDPOINTS FOR FRONTEND
# ==============================================

@router.get("/api/dashboard", summary="Dashboard data API")
async def dashboard_api():
    """Get dashboard data for frontend - using real system metrics and ChromaDB data"""
    try:
        # Get real system health
        health_data = await health_check_all_services()
        
        # Calculate real metrics based on system data
        healthy_services = health_data.get("summary", {}).get("healthy_services", 0)
        total_services = health_data.get("summary", {}).get("total_services", 1)
        
        recent_analyses_data = await _get_recent_analyses_from_chromadb()
        total_analyses = recent_analyses_data.get("total_count", 0)
        recent_analyses = recent_analyses_data.get("analyses", [])
        
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
            "recentActivity": recent_analyses,  # 🆕 Real data from ChromaDB
            "aiModels": {
                "mistral": {"status": "ready", "type": "Quick Analysis"},
                "llama": {"status": "coming_soon", "type": "Deep Analysis"}
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
    Get paginated list of all analyses with filtering options
    """
    try:
        logger.info(f"📊 Retrieving analyses - Page {page}, Per page {per_page}")
        
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
            
        logger.info(f"✅ Retrieved {len(result.get('analyses', []))} analyses")
        
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
    Get paginated analyses with filtering - integrates with existing ChromaDB
    """
    try:
        from app.utils.chroma_client import get_chroma_client
        
        chroma_client = await get_chroma_client()
        if not chroma_client.is_connected():
            logger.debug("ChromaDB not available for paginated analyses")
            return None
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Build search parameters
        search_params = {
            "limit": per_page + offset,  # Get more to handle offset
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
                    limit=1000  # Get more results for filtering
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
        
        # Sort results by date (most recent first)
        results.sort(key=lambda x: x.get("metadata", {}).get("timestamp_unix", 0), reverse=True)
        logger.debug(f"Results sorted by date (most recent first)")
        
        # Get total count for pagination
        total_items = len(results)  # Total filtered results
        
        # Apply pagination to results (slice the results we got)
        paginated_results = results[offset:offset + per_page] if len(results) > offset else []
        logger.debug(f"After pagination: {len(paginated_results)} results for page {page}")
        
        # Process results for frontend display
        analyses = []
        for result in paginated_results:
            metadata = result.get("metadata", {})
            
            # Determine status
            status = "completed"
            if metadata.get("analysis_stopped_at_security"):
                status = "security_failed"
            elif metadata.get("critical_issues_count", 0) > 0:
                status = "critical_issues"
            elif metadata.get("warnings_count", 0) > 0:
                status = "warnings"
            
            analysis = {
                "id": metadata.get("analysis_id", "unknown"),
                "token_address": metadata.get("token_address", ""),
                "token_name": metadata.get("token_name", "Unknown Token"),
                "token_symbol": metadata.get("token_symbol", "N/A"),
                "mint": metadata.get("token_address", ""),
                "timestamp": metadata.get("timestamp_unix", 0),
                "risk_level": metadata.get("risk_level", "unknown"),
                "security_status": metadata.get("security_status", "unknown"),
                "source_event": metadata.get("source_event", "unknown"),
                "overall_score": metadata.get("overall_score", 0),
                "critical_issues": metadata.get("critical_issues_count", 0),
                "warnings": metadata.get("warnings_count", 0),
                "processing_time": metadata.get("processing_time", 0),
                "recommendation": metadata.get("recommendation", "HOLD"),
                "time": _format_analysis_date(metadata.get("timestamp_unix", 0)),  # Use detailed date format
                "status": status
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
    """Get recent analyses from ChromaDB for dashboard display"""
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
        
        # Search for recent analyses (ordered by recency)
        results = await analysis_storage.search_analyses(
            query="recent token analysis",
            limit=limit,
            filters={}
        )
        
        # Get collection stats for total count
        stats = await chroma_client.get_collection_stats()
        total_count = stats.get("total_documents", 0)
        
        # Transform results for dashboard display
        dashboard_analyses = []
        for result in results:
            metadata = result.get("metadata", {})
            
            # Determine status based on analysis result
            status = "completed"  # Default to completed
            if metadata.get("analysis_stopped_at_security"):
                status = "security_failed"
            elif metadata.get("critical_issues_count", 0) > 0:
                status = "critical_issues"
            elif metadata.get("warnings_count", 0) > 0:
                status = "warnings"
            # Note: "warnings" status is still considered successful for success rate calculation
            
            # Format for dashboard display
            analysis_item = {
                "id": metadata.get("analysis_id", "unknown"),
                "token_symbol": metadata.get("token_symbol", "N/A"),
                "token_name": _extract_token_name_from_content(result.get("content", "")),
                "mint": metadata.get("token_address"),
                "status": status,
                "security_status": metadata.get("security_status", "unknown"),
                "risk_level": metadata.get("risk_level", "unknown"),
                "overall_score": metadata.get("overall_score", 0),
                "recommendation": metadata.get("recommendation", "unknown"),
                "processing_time": metadata.get("processing_time", 0),
                "timestamp": metadata.get("timestamp_unix", 0),
                "time": _format_relative_time(metadata.get("timestamp_unix", 0)),
                "source_event": metadata.get("source_event", "unknown"),
                # Additional useful info
                "price_usd": metadata.get("price_usd", 0),
                "volume_24h": metadata.get("volume_24h", 0),
                "critical_issues": metadata.get("critical_issues_count", 0),
                "warnings": metadata.get("warnings_count", 0)
            }
            
            dashboard_analyses.append(analysis_item)
        
        # Sort by timestamp (most recent first)
        dashboard_analyses.sort(key=lambda x: x["timestamp"], reverse=True)
        
        logger.debug(f"📊 Retrieved {len(dashboard_analyses)} recent analyses from ChromaDB")
        
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


def _extract_token_name_from_content(content: str) -> str:
    """Extract token name from analysis content string"""
    try:
        # Look for "Token: TokenName (SYMBOL)" pattern
        import re
        match = re.search(r'Token: ([^(]+)', content)
        if match:
            return match.group(1).strip()
        return "Unknown Token"
    except Exception:
        return "Unknown Token"


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