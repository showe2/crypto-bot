from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, Path
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path as PathlibPath
from loguru import logger
from datetime import datetime
import time

from app.core.config import get_settings
from app.core.dependencies import rate_limit_per_ip
from app.utils.health import health_check_all_services

# Import your existing token analyzer
from app.services.token_analyzer import token_analyzer
from app.services.analysis_storage import analysis_storage

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
    logger.warning("⚠️  Templates directory not found - web interface disabled")


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

@router.post("/quick/{token_mint}", summary="Quick Token Analysis - Frontend Integration")
async def quick_analysis_endpoint(
    token_mint: str = Path(..., description="Token mint address"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Quick token analysis endpoint integrated with your existing token analyzer
    This uses the comprehensive analysis from your token_analyzer service
    """
    start_time = time.time()
    
    try:
        # Validate token mint format
        if not token_mint or len(token_mint) < 32 or len(token_mint) > 44:
            raise HTTPException(
                status_code=422,
                detail="Invalid Solana token mint address format"
            )
        
        logger.info(f"🚀 Frontend quick analysis request for {token_mint}")
        
        # Use your existing token analyzer's comprehensive analysis
        analysis_result = await token_analyzer.analyze_token_comprehensive(token_mint, "frontend_quick")
        
        if analysis_result and analysis_result.get("service_responses"):
            response = {"success": True}
            response.update(analysis_result)

            return response
        
    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"❌ Frontend quick analysis failed for {token_mint}: {str(e)}")
        
        return {
            "status": "error",
            "token": token_mint,
            "timestamp": datetime.utcnow().isoformat(),
            "processing_time": round(processing_time, 2),
            "message": f"Analysis failed: {str(e)}",
            "error": str(e),
            "endpoint": "/quick",
            "analysis_type": "quick"
        }

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
        
        # 🆕 GET REAL ANALYSIS DATA FROM CHROMADB
        recent_analyses_data = await _get_recent_analyses_from_chromadb()
        total_analyses = recent_analyses_data.get("total_count", 0)
        recent_analyses = recent_analyses_data.get("analyses", [])
        
        # Calculate success rate from recent analyses
        if recent_analyses:
            successful_analyses = len([a for a in recent_analyses if a.get("status") == "completed"])
            success_rate = (successful_analyses / len(recent_analyses)) * 100
        else:
            success_rate = (healthy_services / total_services * 100) if total_services > 0 else 0
        
        # Calculate average response time from recent analyses
        if recent_analyses:
            processing_times = [a.get("processing_time", 0) for a in recent_analyses if a.get("processing_time")]
            avg_response_time = sum(processing_times) / len(processing_times) if processing_times else 0
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
            status = "completed"
            if metadata.get("analysis_stopped_at_security"):
                status = "security_failed"
            elif metadata.get("critical_issues_count", 0) > 0:
                status = "critical_issues"
            elif metadata.get("warnings_count", 0) > 0:
                status = "warnings"
            
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