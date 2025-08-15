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
    
    # Get API keys status
    api_keys_status = settings.get_all_api_keys_status()
    configured_keys = sum(1 for status in api_keys_status.values() if status['configured'])
    total_keys = len(api_keys_status)
    
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


@router.get("/discovery", response_class=HTMLResponse, summary="Discovery tools page")
async def discovery_page(request: Request):
    """
    Discovery tools page with search, whales analysis, and listings
    """
    if not templates:
        return JSONResponse({
            "error": "Web interface not available", 
            "message": "Templates not found - use API endpoints instead",
            "api_endpoints": ["/search", "/kity+dev", "/listing"]
        })
    
    context = await get_template_context(request)
    context.update({
        "page": "discovery",
        "title": "Discovery Tools - Solana AI",
        "active_nav": "discovery",
        "discovery_tools": [
            {"id": "search", "name": "Token Search", "description": "Find promising tokens", "icon": "fas fa-search"},
            {"id": "whales", "name": "Whales & Devs", "description": "Track whale movements", "icon": "fas fa-users"},
            {"id": "listings", "name": "New Listings", "description": "Latest DEX listings", "icon": "fas fa-list"}
        ]
    })
    
    return templates.TemplateResponse("pages/discovery.html", context)


@router.get("/settings", response_class=HTMLResponse, summary="Settings page")
async def settings_page(request: Request):
    """
    Settings and configuration page
    """
    if not templates:
        return JSONResponse({
            "error": "Web interface not available",
            "message": "Templates not found - use API endpoints instead",
            "config_endpoint": "/config"
        })
    
    context = await get_template_context(request)
    context.update({
        "page": "settings",
        "title": "Settings - Solana AI", 
        "active_nav": "settings",
        "api_keys_status": settings.get_all_api_keys_status(),
        "missing_critical_keys": settings.validate_critical_keys()
    })
    
    return templates.TemplateResponse("pages/settings.html", context)


@router.get("/health-dashboard", response_class=HTMLResponse, summary="Detailed health dashboard")
async def health_dashboard_page(request: Request):
    """
    Detailed system health dashboard
    """
    if not templates:
        # Redirect to API health endpoint
        return JSONResponse({
            "message": "Use /health endpoint for system health data",
            "redirect": "/health"
        })
    
    try:
        health_data = await health_check_all_services()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_data = {"error": str(e), "overall_status": False}
    
    context = await get_template_context(request)
    context.update({
        "page": "health",
        "title": "System Health - Solana AI",
        "active_nav": "health", 
        "detailed_health": health_data,
        "health_check_time": datetime.utcnow().isoformat()
    })
    
    return templates.TemplateResponse("pages/health_dashboard.html", context)


# ==============================================
# API ENDPOINTS FOR FRONTEND
# ==============================================

@router.get("/api/dashboard", summary="Dashboard data API")
async def dashboard_api():
    """
    Get dashboard data for frontend
    """
    try:
        # Get real system health
        health_data = await health_check_all_services()
        
        # Mock metrics - replace with real data from your analytics
        dashboard_data = {
            "metrics": {
                "totalAnalyses": 1247,
                "analysesGrowth": 12.5,
                "successRate": 94.2,
                "avgResponseTime": 3.2,
                "responseImprovement": 8.3,
                "activeTokens": 892,
                "newTokens": 43
            },
            "systemHealth": {
                "overall_status": health_data.get("overall_status", False),
                "healthy_services": health_data.get("summary", {}).get("healthy_services", 0),
                "total_services": health_data.get("summary", {}).get("total_services", 0)
            },
            "recentActivity": [
                {
                    "id": 1,
                    "type": "analysis", 
                    "token_symbol": "BONK",
                    "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "completed",
                    "analysis_type": "quick"
                },
                {
                    "id": 2,
                    "type": "analysis",
                    "token_symbol": "ORCA", 
                    "mint": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "completed",
                    "analysis_type": "deep"
                }
            ],
            "aiModels": {
                "mistral": {"status": "online", "avgResponse": 2.3, "queue": 0},
                "llama": {"status": "online", "avgResponse": 8.7, "queue": 0}
            },
            "todayStats": {
                "analyses": 247,
                "successRate": 94.2,
                "avgResponse": 3.2,
                "errors": 14
            }
        }
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Dashboard API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/system/status", summary="System status API")
async def system_status_api():
    """
    Get system status for frontend components
    """
    try:
        health_data = await health_check_all_services()
        
        # Transform for frontend consumption
        status_data = {
            "overall_healthy": health_data.get("overall_status", False),
            "services": {},
            "summary": health_data.get("summary", {}),
            "recommendations": health_data.get("recommendations", []),
            "timestamp": health_data.get("timestamp"),
            "environment": settings.ENV,
            "version": "1.0.0"
        }
        
        # Simplify services data for frontend
        for service_name, service_data in health_data.get("services", {}).items():
            status_data["services"][service_name] = {
                "healthy": service_data.get("healthy", False),
                "status": "online" if service_data.get("healthy") else "offline",
                "version": service_data.get("version"),
                "error": service_data.get("error"),
                "optional": service_name in ["redis", "chromadb", "cache"]
            }
        
        return status_data
        
    except Exception as e:
        logger.error(f"System status API error: {e}")
        return {
            "overall_healthy": False,
            "services": {},
            "error": str(e),
            "timestamp": datetime.utcnow().timestamp(),
            "environment": settings.ENV
        }


@router.post("/api/analysis/quick", summary="Quick analysis API")
async def quick_analysis_api(request_data: dict):
    """
    Quick analysis API endpoint for frontend
    """
    try:
        token_mint = request_data.get("token_mint")
        if not token_mint:
            raise HTTPException(status_code=400, detail="token_mint is required")
        
        # Use existing tweet command
        result = await tweet_command(token_mint)
        
        return {
            "success": True,
            "result": result,
            "analysis_type": "quick",
            "processing_time": 2.5,  # Mock processing time
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Quick analysis API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/analysis/deep", summary="Deep analysis API")
async def deep_analysis_api(request_data: dict):
    """
    Deep analysis API endpoint for frontend
    """
    try:
        token_mint = request_data.get("token_mint")
        if not token_mint:
            raise HTTPException(status_code=400, detail="token_mint is required")
        
        # Use existing name command
        result = await name_command(token_mint)
        
        return {
            "success": True,
            "result": result,
            "analysis_type": "deep",
            "processing_time": 8.7,  # Mock processing time
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Deep analysis API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/notifications", summary="Get notifications")
async def notifications_api():
    """
    Get user notifications for frontend
    """
    # Mock notifications - replace with real notification system
    notifications = [
        {
            "id": 1,
            "type": "success",
            "title": "Analysis Complete",
            "message": "BONK token analysis finished successfully",
            "timestamp": datetime.utcnow().isoformat(),
            "read": False,
            "icon": "fas fa-check-circle",
            "color": "#10b981"
        },
        {
            "id": 2,
            "type": "warning", 
            "title": "High Volume Detected",
            "message": "Unusual trading volume detected for SOL",
            "timestamp": datetime.utcnow().isoformat(),
            "read": False,
            "icon": "fas fa-exclamation-triangle",
            "color": "#f59e0b"
        },
        {
            "id": 3,
            "type": "info",
            "title": "System Update",
            "message": "AI models updated to latest version",
            "timestamp": datetime.utcnow().isoformat(),
            "read": True,
            "icon": "fas fa-info-circle", 
            "color": "#3b82f6"
        }
    ]
    
    return {
        "notifications": notifications,
        "unread_count": sum(1 for n in notifications if not n["read"]),
        "total_count": len(notifications)
    }


# ==============================================
# EXISTING COMMAND ENDPOINTS (Enhanced)
# ==============================================

@router.get("/start", summary="Check service availability")
async def start_command():
    """
    /start command – checks readiness of all system services
    Enhanced with more detailed system information
    """
    try:
        logger.info("Executing /start command – checking services")
        
        # Get detailed health check
        health_data = await health_check_all_services()
        
        response_data = {
            "command": "start",
            "system_status": "ready" if health_data.get("overall_status") else "issues",
            "message": "🚀 Solana token analysis system is ready!" if health_data.get("overall_status") else "⚠️ System has some issues",
            "services_summary": {
                "total": health_data.get("summary", {}).get("total_services", 0),
                "healthy": health_data.get("summary", {}).get("healthy_services", 0),
                "issues": health_data.get("summary", {}).get("total_services", 0) - health_data.get("summary", {}).get("healthy_services", 0)
            },
            "available_commands": [
                "/start - check services",
                "/tweet <token> - quick analysis", 
                "/name <token> - full AI analysis",
                "/search - search for promising tokens",
                "/kity+dev - whale and developer analysis",
                "/listing - listing parsing"
            ],
            "web_interface": {
                "available": templates is not None,
                "dashboard_url": "/" if templates else None,
                "analysis_url": "/analysis" if templates else None
            },
            "api_endpoints": {
                "health": "/health",
                "config": "/config", 
                "docs": "/docs" if settings.ENV == "development" else None
            },
            "timestamp": datetime.utcnow(),
            "version": "1.0.0",
            "environment": settings.ENV
        }
        return response_data
        
    except Exception as e:
        logger.error(f"Error while executing /start command: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"System check error: {str(e)}"
        )


@router.post("/tweet/{token_mint}", summary="Quick token analysis")
async def tweet_command(token_mint: str):
    """
    /tweet <token> command – quick token analysis
    Enhanced with validation and better error handling
    """
    try:
        # Basic validation
        if not token_mint or len(token_mint) < 32:
            raise HTTPException(
                status_code=400,
                detail="Invalid token mint address format"
            )
        
        logger.info(f"Executing quick analysis for token: {token_mint}")
        
        return {
            "command": "tweet",
            "token": token_mint,
            "message": "Quick analysis completed successfully",
            "status": "completed",
            "analysis_type": "quick",
            "processing_time": 2.3,
            "timestamp": datetime.utcnow(),
            "note": "This is a stub implementation. Real analysis will be implemented with AI models."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in tweet command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/name/{token_mint}", summary="Full token analysis with AI")
async def name_command(token_mint: str):
    """
    /name <token> command – full analysis with AI
    Enhanced with validation and processing simulation
    """
    try:
        # Basic validation
        if not token_mint or len(token_mint) < 32:
            raise HTTPException(
                status_code=400,
                detail="Invalid token mint address format"
            )
        
        logger.info(f"Executing deep analysis for token: {token_mint}")
        
        return {
            "command": "name",
            "token": token_mint,
            "message": "Deep AI analysis completed successfully",
            "status": "completed",
            "analysis_type": "deep",
            "ai_models_used": ["Mistral 7B", "LLaMA 3 70B"],
            "processing_time": 8.7,
            "timestamp": datetime.utcnow(),
            "note": "This is a stub implementation. Real AI analysis will be implemented with trained models."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in name command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", summary="Search for promising tokens")
async def search_command():
    """
    /search command – enhanced with more details
    """
    try:
        logger.info("Executing token search command")
        
        return {
            "command": "search",
            "message": "Token search functionality ready for implementation",
            "status": "ready",
            "search_criteria": [
                "Volume spikes", 
                "Social sentiment",
                "Whale movements",
                "Technical indicators",
                "New listings"
            ],
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error in search command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kity+dev", summary="Whale and developer analysis")
async def whales_dev_command(token_mint: Optional[str] = None):
    """
    /kity+dev command – enhanced whale and developer analysis
    """
    try:
        logger.info(f"Executing whales/dev analysis for token: {token_mint or 'all'}")
        
        return {
            "command": "kity+dev",
            "token": token_mint,
            "message": "Whale and developer analysis ready for implementation",
            "status": "ready",
            "analysis_scope": "specific_token" if token_mint else "market_wide",
            "features": [
                "Large transaction tracking",
                "Developer wallet monitoring", 
                "Smart money flow analysis",
                "Insider activity detection"
            ],
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error in whales/dev command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/listing", summary="Parse new listings")
async def listing_command(hours: int = 24):
    """
    /listing command – enhanced listing parser
    """
    try:
        # Validate hours parameter
        if hours < 1 or hours > 168:  # Max 1 week
            hours = 24
        
        logger.info(f"Executing listing parser for last {hours} hours")
        
        return {
            "command": "listing",
            "hours": hours,
            "message": f"Listing parser ready - will scan last {hours} hours",
            "status": "ready",
            "data_sources": [
                "Raydium",
                "Jupiter", 
                "Orca",
                "Serum DEX"
            ],
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error in listing command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================
# SUPPORTING ENDPOINTS (Enhanced)
# ==============================================

@router.get("/status", summary="Extended system status")
async def system_status():
    """Enhanced system status with web interface information"""
    try:
        # Get health data
        health_data = await health_check_all_services()
        
        config_status = {
            "environment": settings.ENV,
            "debug_mode": settings.DEBUG,
            "api_keys_configured": len([
                key for key, status in settings.get_all_api_keys_status().items()
                if status['configured']
            ]),
            "cache_enabled": bool(settings.REDIS_URL),
            "ai_models": {
                "mistral": bool(settings.MISTRAL_API_KEY),
                "llama": bool(settings.LLAMA_API_KEY)
            },
            "web_interface": {
                "templates_available": templates is not None,
                "static_files": Path("static").exists()
            }
        }
        
        return {
            "system": "Solana Token Analysis AI System",
            "version": "1.0.0",
            "uptime_check": health_data.get("check_duration_seconds"),
            "overall_healthy": health_data.get("overall_status"),
            "services_summary": health_data.get("summary"),
            "web_interface": {
                "available": templates is not None,
                "routes": ["/", "/analysis", "/discovery", "/settings"] if templates else []
            },
            "configuration": config_status,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting status: {str(e)}"
        )


@router.get("/commands", summary="List of available commands")
async def available_commands():
    """Enhanced commands list with web interface information"""
    
    commands_info = {
        "basic_commands": [
            {
                "command": "/start",
                "description": "Check readiness of all system services",
                "method": "GET",
                "endpoint": "/start",
                "web_available": True
            },
            {
                "command": "/tweet <token>",
                "description": "Quick token analysis",
                "method": "POST",
                "endpoint": "/tweet/{token_mint}",
                "web_available": True,
                "web_page": "/analysis"
            },
            {
                "command": "/name <token>",
                "description": "Full AI analysis",
                "method": "POST", 
                "endpoint": "/name/{token_mint}",
                "web_available": True,
                "web_page": "/analysis"
            }
        ],
        "discovery_commands": [
            {
                "command": "/search",
                "description": "Search for promising tokens",
                "method": "GET",
                "endpoint": "/search",
                "web_available": True,
                "web_page": "/discovery"
            },
            {
                "command": "/kity+dev",
                "description": "Analyze whale movements and developer activity",
                "method": "GET",
                "endpoint": "/kity+dev",
                "web_available": True,
                "web_page": "/discovery"
            },
            {
                "command": "/listing", 
                "description": "Parse new token listings on DEX",
                "method": "GET",
                "endpoint": "/listing",
                "web_available": True,
                "web_page": "/discovery"
            }
        ],
        "system_commands": [
            {
                "command": "/status",
                "description": "Extended system status information",
                "method": "GET", 
                "endpoint": "/status",
                "web_available": True
            },
            {
                "command": "/commands",
                "description": "Reference for all commands",
                "method": "GET",
                "endpoint": "/commands",
                "web_available": True
            }
        ],
        "web_interface": {
            "available": templates is not None,
            "pages": [
                {"name": "Dashboard", "url": "/", "description": "Main dashboard with system overview"},
                {"name": "Token Analysis", "url": "/analysis", "description": "Detailed token analysis tools"}, 
                {"name": "Discovery", "url": "/discovery", "description": "Token discovery and search tools"},
                {"name": "Settings", "url": "/settings", "description": "System configuration and settings"}
            ] if templates else [],
            "api_endpoints": [
                {"name": "Dashboard API", "url": "/api/dashboard"},
                {"name": "System Status API", "url": "/api/system/status"},
                {"name": "Quick Analysis API", "url": "/api/analysis/quick"},
                {"name": "Deep Analysis API", "url": "/api/analysis/deep"}
            ]
        }
    }
    
    return commands_info