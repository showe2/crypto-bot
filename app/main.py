import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from loguru import logger
import uvicorn
from datetime import datetime
from typing import Dict, Any

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.dependencies import startup_dependencies, shutdown_dependencies
from app.routers import alex_core
from app.routers import webhooks
from app.routers import alex_ingest  # Add this import
from app.utils.health import health_check_all_services
from app.routers.api_router import router as api_router
from app.routers.analysis_runs import router as analysis_runs_router
from app.services.service_manager import initialize_api_services, cleanup_api_services

# Global settings
settings = get_settings()

# Simple logging middleware
async def logging_middleware(request: Request, call_next):
    """Simple HTTP request logging middleware"""
    import time
    
    start_time = time.time()
    client_ip = request.client.host
    method = request.method
    url = str(request.url)
    
    try:
        response = await call_next(request)
        processing_time = time.time() - start_time
        
        logger.info(
            f"{method} {url} - {response.status_code} ({processing_time*1000:.1f}ms)",
            extra={
                "api_request": True,
                "method": method,
                "url": url,
                "status_code": response.status_code,
                "processing_time_ms": round(processing_time * 1000, 1),
                "client_ip": client_ip
            }
        )
        
        return response
        
    except Exception as e:
        processing_time = time.time() - start_time
        
        logger.error(
            f"{method} {url} - ERROR ({processing_time*1000:.1f}ms): {str(e)}",
            extra={
                "api_request": True,
                "method": method,
                "url": url,
                "status_code": 500,
                "processing_time_ms": round(processing_time * 1000, 1),
                "client_ip": client_ip,
                "error": str(e)
            }
        )
        
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management with service integration"""
    # Startup
    logger.info("🚀 Starting Solana Token Analysis System with Service Integration...")
    
    # Check for frontend files
    templates_dir = Path("templates")
    static_dir = Path("static")
    
    if templates_dir.exists():
        logger.info("✅ Templates directory found - web interface enabled")
    else:
        logger.warning("⚠️  Templates directory not found - creating basic structure...")
        templates_dir.mkdir(exist_ok=True)
        (templates_dir / "components").mkdir(exist_ok=True)
        (templates_dir / "pages").mkdir(exist_ok=True)
        logger.info("📁 Created templates directory structure")
    
    if static_dir.exists():
        logger.info("✅ Static files directory found")
    else:
        logger.info("📁 Creating static files directory...")
        static_dir.mkdir(exist_ok=True)
        (static_dir / "css").mkdir(exist_ok=True)
        (static_dir / "js").mkdir(exist_ok=True)
        (static_dir / "img").mkdir(exist_ok=True)
        logger.info("✅ Created static files directory structure")
    
    # Initialize system dependencies
    try:
        await startup_dependencies()
        logger.info("✅ System dependencies initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize dependencies: {str(e)}")
        # Continue anyway - some services might still work
    
    # Initialize API services for token analysis
    try:
        await initialize_api_services()
        logger.info("✅ API services initialized for token analysis")
    except Exception as e:
        logger.error(f"❌ Failed to initialize API services: {str(e)}")
        logger.warning("Some token analysis features may be limited")
    
    # Start webhook workers
    try:
        from app.utils.webhook_tasks import start_webhook_workers
        await start_webhook_workers()
        logger.info("✅ Webhook background workers started")
    except Exception as e:
        logger.warning(f"⚠️  Webhook workers failed to start: {str(e)}")

    # Start snapshot scheduler
    try:
        from app.services.snapshots.snapshot_scheduler import start_snapshot_scheduler
        scheduler_started = await start_snapshot_scheduler()
        
        if scheduler_started:
            logger.info("✅ Snapshot scheduler started")
        else:
            logger.info("📸 Snapshot scheduler disabled in configuration")
            
    except Exception as e:
        logger.warning(f"⚠️  Snapshot scheduler failed to start: {str(e)}")
    
    # Check web interface status
    templates_available = templates_dir.exists() and any(templates_dir.iterdir())
    
    if templates_available:
        logger.info("🌐 Web interface: ENABLED")
        logger.info("   📊 Dashboard: http://localhost:8000/")
        logger.info("   🔍 Analysis: http://localhost:8000/analysis")
    else:
        logger.warning("🌐 Web interface: DISABLED (templates not found)")
        logger.info("   Use API endpoints or create templates directory")
    
    # Log API endpoints
    logger.info("🔗 API endpoints:")
    logger.info("   📊 Token Analysis: http://localhost:8000/api/analyze/token")
    logger.info("   📈 Batch Analysis: http://localhost:8000/api/analyze/batch")
    logger.info("   🏥 API Health: http://localhost:8000/api/health")
    
    # Log webhook endpoints
    logger.info("🔗 WebHook endpoints:")
    logger.info("   📦 Mints: http://localhost:8000/webhooks/helius/mint")
    
    # Log configuration summary
    logger.info(f"🔧 Environment: {settings.ENV}")
    logger.info(f"🔧 Debug mode: {settings.DEBUG}")
    logger.info(f"🔧 Host: {settings.HOST}:{settings.PORT}")
    
    # Show integration status
    logger.info("🔗 Service Integration Status:")
    logger.info("   ✅ Mint Webhooks → AI-Enhanced Deep Analysis")
    logger.info("   ✅ API Router → Comprehensive Analysis")
    logger.info("   ✅ Redis Caching → Performance Optimization")
    logger.info("   ✅ ChromaDB Storage → Analysis History")
    logger.info("   ✅ Llama 3.0 AI → Enhanced Insights")
    
    yield
    
    # Shutdown
    logger.info("🛑 Stopping Token Analysis System...")
    
    # Stop webhook workers
    try:
        from app.utils.webhook_tasks import stop_webhook_workers
        await stop_webhook_workers()
        logger.info("✅ Webhook workers stopped")
    except Exception as e:
        logger.warning(f"⚠️  Error stopping webhook workers: {str(e)}")

    # Start snapshot scheduler
    try:
        from app.services.snapshots.snapshot_scheduler import start_snapshot_scheduler
        scheduler_started = await start_snapshot_scheduler()
        
        if scheduler_started:
            logger.info("✅ Snapshot scheduler started")
        else:
            logger.info("📸 Snapshot scheduler disabled in configuration")
            
    except Exception as e:
        logger.warning(f"⚠️  Snapshot scheduler failed to start: {str(e)}")
    
    # Cleanup API services
    try:
        await cleanup_api_services()
        logger.info("✅ API services cleaned up")
    except Exception as e:
        logger.warning(f"⚠️  Error cleaning up API services: {str(e)}")
    
    try:
        await shutdown_dependencies()
        logger.info("✅ System dependencies cleaned up")
    except Exception as e:
        logger.warning(f"⚠️  Dependency cleanup warning: {str(e)}")
    
    logger.info("👋 System shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Solana Token Analysis AI System",
    description="Integrated Solana token analysis system with AI capabilities, comprehensive service integration, and LLM-optimized responses",
    version="1.0.0",
    docs_url="/docs" if settings.ENV == "development" else None,
    redoc_url="/redoc" if settings.ENV == "development" else None,
    lifespan=lifespan
)

# Add logging middleware
app.middleware("http")(logging_middleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENV == "development" else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted hosts for production
if settings.ENV == "production":
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
    )

# Static files (for web interface)
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("✅ Static files mounted at /static")
else:
    logger.warning("⚠️  Static files directory not found")

# Include routers
app.include_router(
    alex_core.router,
    prefix="",
    tags=["core", "frontend"]
)

app.include_router(
    api_router,
    prefix="",
    tags=["api", "analysis"]
)

app.include_router(
    webhooks.router,
    prefix="",
    tags=["webhooks"]
)

app.include_router(alex_ingest.router)
app.include_router(analysis_runs_router, prefix="/api", tags=["Analysis Profiles"])


# Health check endpoints
@app.get("/health", summary="System health check")
async def health_check():
    """Detailed system component health check - RUNS ONLY ON REQUEST"""
    logger.info("🏥 Running comprehensive health check (on-demand)")
    
    # Import here to avoid startup delays
    from app.utils.health import health_check_all_services
    
    health_status = await health_check_all_services()
    
    status_code = (
        status.HTTP_200_OK 
        if health_status.get("overall_status") 
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    
    # Log health check result
    healthy_services = health_status.get("summary", {}).get("healthy_services", 0)
    total_services = health_status.get("summary", {}).get("total_services", 0)
    logger.info(f"🏥 Health check completed: {healthy_services}/{total_services} services healthy")
    
    return JSONResponse(
        content=health_status,
        status_code=status_code
    )


@app.get("/metrics", summary="System metrics")
async def system_metrics():
    """Get detailed system metrics"""
    try:
        from app.utils.health import get_service_metrics
        metrics = await get_service_metrics()
        return metrics
    except ImportError:
        return JSONResponse(
            content={
                "error": "Metrics not available",
                "reason": "get_service_metrics function not found"
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


@app.get("/config", summary="Configuration status")
async def config_status():
    """Get configuration status (non-sensitive) - NO HEALTH CHECKS"""
    config_info = {
        "environment": settings.ENV,
        "debug_mode": settings.DEBUG,
        "host": settings.HOST,
        "port": settings.PORT,
        "log_level": settings.LOG_LEVEL,
        "log_format": settings.LOG_FORMAT,
        "web_interface": {
            "templates_available": Path("templates").exists(),
            "static_files_available": Path("static").exists(),
            "routes": ["/", "/analysis"] if Path("templates").exists() else []
        },
        "webhooks": {
            "enabled": True,
            "endpoints": ["/webhooks/helius/mint", "/webhooks/helius/pool", "/webhooks/helius/tx"],
            "base_url_configured": bool(settings.BASE_URL),
            "analysis_integration": True
        },
        "analysis_engine": {
            "enabled": True,
            "llm_optimized": True,
            "comprehensive_analysis": True,
            "webhook_triggered_analysis": True,
            "caching_enabled": True
        },
        "cache_settings": {
            "ttl_short": settings.CACHE_TTL_SHORT,
            "ttl_medium": settings.CACHE_TTL_MEDIUM,
            "ttl_long": settings.CACHE_TTL_LONG
        },
        "performance_settings": {
            "api_timeout": settings.API_TIMEOUT,
            "ai_timeout": settings.AI_TIMEOUT,
            "http_pool_size": settings.HTTP_POOL_SIZE,
            "http_max_retries": settings.HTTP_MAX_RETRIES
        },
        "security_settings": {
            "jwt_algorithm": settings.JWT_ALGORITHM,
            "jwt_expire_minutes": settings.JWT_EXPIRE_MINUTES,
            "wallet_configured": bool(settings.WALLET_SECRET_KEY),
            "rate_limits": {
                "per_minute": settings.RATE_LIMIT_PER_MINUTE,
                "per_hour": settings.RATE_LIMIT_PER_HOUR
            }
        },
        "api_urls": {
            "helius_rpc": bool(settings.HELIUS_RPC_URL),
            "birdeye": bool(settings.BIRDEYE_BASE_URL),
            "solanafm": bool(settings.SOLANAFM_BASE_URL),
            "dexscreener": bool(settings.DEXSCREENER_BASE_URL),
            "goplus": bool(settings.GOPLUS_BASE_URL),
            "rugcheck": bool(settings.RUGCHECK_BASE_URL)
        },
        "api_keys_configured": len([
            key for key, status in settings.get_all_api_keys_status().items()
            if status['configured']
        ]),
        "missing_critical_keys": settings.validate_critical_keys(),
        "health_check_info": {
            "automated_checks_disabled": True,
            "available_endpoints": ["/health", "/health/simple", "/health/analysis", "/metrics"],
            "note": "Health checks run only on explicit request"
        }
    }
    
    return config_info


# Error handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Input data validation error handler"""
    logger.warning(f"Validation error for {request.url}: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "message": "Please check input data validity",
            "endpoint": str(request.url.path)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    logger.error(f"Unhandled exception for {request.url}: {str(exc)}", exc_info=True)
    
    # Don't expose internal errors in production
    if settings.ENV == "production":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "An internal error occurred. Please try again later."
            }
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "detail": str(exc),
                "type": type(exc).__name__,
                "endpoint": str(request.url.path)
            }
        )


def create_app() -> FastAPI:
    """Application factory"""
    setup_logging()
    return app


if __name__ == "__main__":
    # Configure logging
    setup_logging()
    
    # Log startup information
    logger.info(f"🔥 Starting in {settings.ENV} mode")
    logger.info(f"🌐 Server will be available at http://{settings.HOST}:{settings.PORT}")
    
    if settings.ENV == "development":
        logger.info("📖 API Documentation: http://localhost:8000/docs")
        logger.info("🏥 Health Check: http://localhost:8000/health")
        logger.info("🔍 Analysis Health: http://localhost:8000/health/analysis")
        logger.info("📊 Metrics: http://localhost:8000/metrics")
        logger.info("🌐 Web Interface: http://localhost:8000/")
        logger.info("🔗 WebHooks Status: http://localhost:8000/webhooks/status/fast")
        logger.info("")
        logger.info("🚀 Token Analysis Endpoints:")
        logger.info("   POST /api/analyze/token - Comprehensive token analysis")
        logger.info("   POST /api/analyze/batch - Batch token analysis")
        logger.info("   GET  /api/analyze/cached/{token} - Get cached analysis")
        logger.info("   GET  /api/llm/analysis-format - LLM format documentation")
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENV == "development",
        log_level="info" if settings.ENV == "production" else "debug",
        access_log=True,
        workers=1  # Single worker for development, configure for production
    )