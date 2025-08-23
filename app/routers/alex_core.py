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
# HELPER FUNCTIONS FOR DATA TRANSFORMATION
# ==============================================

def _map_risk_to_recommendation(risk_category: str) -> str:
    """Map risk category to frontend recommendation format"""
    risk_mapping = {
        "low": "CONSIDER",
        "medium": "HOLD", 
        "high": "CAUTION",
        "critical": "AVOID"
    }
    return risk_mapping.get(risk_category, "HOLD")


def _extract_price_data(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and format price data for frontend"""
    market_data = analysis_result.get("market_data", {})
    price_info = market_data.get("price_information", {})
    
    return {
        "current_price": price_info.get("current_price", "0"),
        "price_change_24h": price_info.get("price_change_24h", "0"),
        "volume_24h": price_info.get("volume_24h", "0"),
        "market_cap": price_info.get("market_cap", "0"),
        "holders_count": market_data.get("holder_count", 0)
    }


def _calculate_pump_probability(analysis_result: Dict[str, Any], timeframe: str) -> float:
    """Calculate pump probability based on analysis results"""
    score = analysis_result.get("overall_analysis", {}).get("score", 50)
    confidence = analysis_result.get("overall_analysis", {}).get("confidence_score", 50)
    
    # Simple calculation based on score and confidence
    base_prob = (score + confidence) / 200  # Average and normalize to 0-1
    
    # Adjust for timeframe
    if timeframe == "1h":
        return max(0.1, min(0.9, base_prob * 0.7))  # Lower for shorter timeframe
    else:  # 24h
        return max(0.2, min(0.95, base_prob * 1.1))  # Higher for longer timeframe


def _extract_patterns(analysis_result: Dict[str, Any]) -> List[str]:
    """Extract trading patterns from analysis"""
    patterns = []
    
    # Check for volume patterns
    market_data = analysis_result.get("market_data", {})
    if market_data.get("volume_24h"):
        patterns.append("volume_analysis")
    
    # Check for positive signals
    positive_signals = analysis_result.get("overall_analysis", {}).get("positive_signals", [])
    if any("volume" in signal.lower() for signal in positive_signals):
        patterns.append("volume_spike")
    
    if any("social" in signal.lower() for signal in positive_signals):
        patterns.append("social_buzz")
    
    return patterns[:3]  # Limit to 3 patterns


def _generate_price_targets(analysis_result: Dict[str, Any]) -> Dict[str, str]:
    """Generate price targets based on current analysis"""
    price_data = _extract_price_data(analysis_result)
    current_price = float(price_data.get("current_price", 0))
    
    if current_price <= 0:
        return {}
    
    score = analysis_result.get("overall_analysis", {}).get("score", 50)
    multiplier = 1 + (score - 50) / 200  # Adjust based on score
    
    return {
        "1h": f"{current_price * multiplier * 1.02:.6f}",
        "24h": f"{current_price * multiplier * 1.08:.6f}",
        "7d": f"{current_price * multiplier * 1.15:.6f}"
    }


def _extract_market_analysis(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract market analysis data"""
    return {
        "holder_data": analysis_result.get("on_chain_metrics", {}).get("holder_analysis", {}),
        "trading_activity": analysis_result.get("trading_analysis", {}),
        "liquidity_analysis": analysis_result.get("market_data", {}).get("liquidity", {})
    }


def _extract_security_analysis(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract security analysis data"""
    return {
        "overall_security_score": analysis_result.get("security_analysis", {}).get("overall_security_score", 50),
        "risk_factors": analysis_result.get("overall_analysis", {}).get("risk_factors", []),
        "security_checks": analysis_result.get("security_analysis", {}).get("security_checks", {}),
        "rugpull_indicators": analysis_result.get("security_analysis", {}).get("rugpull_indicators", {})
    }


# ==============================================
# SEARCH AND OTHER ENDPOINTS
# ==============================================

@router.get("/search", summary="Search trending tokens")
async def search_trending_tokens(_: None = Depends(rate_limit_per_ip)):
    """Search for trending tokens - placeholder implementation"""
    try:
        return {
            "status": "success",
            "message": "Search functionality coming soon",
            "trending_tokens": [],
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Search failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }


# ==============================================
# API ENDPOINTS FOR FRONTEND
# ==============================================

@router.get("/api/dashboard", summary="Dashboard data API")
async def dashboard_api():
    """Get dashboard data for frontend - using real system metrics"""
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
                "llama": {"status": "coming_soon", "type": "Deep Analysis"}
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