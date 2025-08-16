from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
from loguru import logger
from datetime import datetime

from app.core.config import get_settings
from app.models.token import TokenAnalysisRequest, TokenAnalysisResponse
from app.utils.health import health_check_all_services

# Settings and dependencies
settings = get_settings()
router = APIRouter()

# Initialize templates
templates_dir = Path("templates")
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
    """
    Main dashboard page with system overview and quick analysis tools
    """
    if not templates:
        # Fallback to JSON response if templates not available
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
    """
    Token analysis page with detailed analysis tools
    """
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
            {"name": "Wrapped SOL", "mint": "So11111111111111111111111111111111111112", "symbol": "WSOL"},
            {"name": "USD Coin", "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "symbol": "USDC"},
            {"name": "Raydium", "mint": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "symbol": "RAY"}
        ]
    })
    
    return templates.TemplateResponse("pages/analysis.html", context)


# ==============================================
# API ENDPOINTS FOR FRONTEND
# ==============================================

@router.get("/api/dashboard", summary="Dashboard data API")
async def dashboard_api():
    """
    Get dashboard data for frontend - using real system metrics
    """
    try:
        # Get real system health
        health_data = await health_check_all_services()
        
        # Calculate real metrics based on system data
        healthy_services = health_data.get("summary", {}).get("healthy_services", 0)
        total_services = health_data.get("summary", {}).get("total_services", 1)
        
        # Real metrics based on actual system state
        dashboard_data = {
            "metrics": {
                "totalAnalyses": 0,  # Will be updated by actual usage
                "successRate": (healthy_services / total_services * 100) if total_services > 0 else 0,
                "avgResponseTime": 0,  # Will be tracked in real usage
                "activeTokens": 0  # Will be updated by actual analysis count
            },
            "systemHealth": {
                "overall_status": health_data.get("overall_status", False),
                "healthy_services": healthy_services,
                "total_services": total_services
            },
            "recentActivity": [],  # Will be populated with real analysis data
            "aiModels": {
                "mistral": {"status": "ready", "type": "Quick Analysis"},
                "llama": {"status": "ready", "type": "Deep Analysis"}
            }
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
            }
        }
    

# ==============================================
# MARKETPLACE ENDPOINTS (COMMING SOON)
# ==============================================
    
@router.get("/marketplace", response_class=HTMLResponse, summary="Token marketplace page")
async def marketplace_page(request: Request):
    """
    Token marketplace page (coming soon)
    """
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


@router.get("/analysis", response_class=HTMLResponse, summary="Token analysis page")
async def analysis_page(request: Request, token: Optional[str] = None):
    """
    Token analysis page with detailed analysis tools
    """
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
            {"name": "Wrapped SOL", "mint": "So11111111111111111111111111111111111112", "symbol": "WSOL"},
            {"name": "USD Coin", "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "symbol": "USDC"},
            {"name": "Raydium", "mint": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "symbol": "RAY"}
        ]
    })
    
    return templates.TemplateResponse("pages/analysis.html", context)


@router.get("/marketplace", response_class=HTMLResponse, summary="Token marketplace page")
async def marketplace_page(request: Request):
    """
    Token marketplace page (coming soon)
    """
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