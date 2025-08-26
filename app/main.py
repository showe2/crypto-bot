import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
import uvicorn
from loguru import logger

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.dependencies import startup_dependencies, shutdown_dependencies
from app.routers import alex_core
from app.routers import webhooks
from app.utils.health import health_check_all_services
from app.routers.api_router import router as api_router
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
    
    # Check all services
    health_status = await health_check_all_services()
    
    if not health_status.get("overall_status"):
        logger.error("❌ Critical services unavailable!")
        for service_name, service_status in health_status.get("services", {}).items():
            if not service_status.get("healthy"):
                error_msg = service_status.get("error", "Unknown error")
                logger.error(f"   • {service_name}: {error_msg}")
        
        # Show recommendations
        for recommendation in health_status.get("recommendations", []):
            logger.warning(f"   💡 {recommendation}")
    else:
        logger.info("✅ All critical services ready")
        
        # Show optional service status with more detail
        optional_services = health_status.get("service_categories", {}).get("optional", {})
        working_optional = optional_services.get("healthy_count", 0)
        total_optional = optional_services.get("total_count", 0)
        
        if working_optional < total_optional:
            logger.info(f"ℹ️  Optional services: {working_optional}/{total_optional} available")
            
            # List which optional services are missing
            for service_name, service_status in health_status.get("services", {}).items():
                if service_name in ["redis", "chromadb", "cache"] and not service_status.get("healthy"):
                    if service_status.get("optional"):
                        logger.debug(f"   • {service_name}: not available (optional)")
                    else:
                        logger.info(f"   • {service_name}: not available")
        else:
            logger.info("✅ All optional services available")
    
    # Check analysis services specifically
    try:
        from app.services.service_manager import get_api_health_status
        api_health = await get_api_health_status()
        
        healthy_apis = api_health.get("summary", {}).get("healthy_services", 0)
        total_apis = api_health.get("summary", {}).get("total_services", 0)
        
        logger.info(f"🔗 Analysis services: {healthy_apis}/{total_apis} available")
        
        if healthy_apis >= 3:
            logger.info("✅ Sufficient analysis services for comprehensive token analysis")
        elif healthy_apis >= 1:
            logger.warning("⚠️  Limited analysis services - basic analysis available")
        else:
            logger.error("❌ No analysis services available - analysis features disabled")
            
    except Exception as e:
        logger.warning(f"⚠️  Could not check analysis services: {str(e)}")
    
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
    logger.info("   📋 Analysis Stats: http://localhost:8000/api/analyze/stats")
    
    # Log webhook endpoints
    logger.info("🔗 WebHook endpoints:")
    logger.info("   📦 Mints: http://localhost:8000/webhooks/helius/mint")
    logger.info("   🏊 Pools: http://localhost:8000/webhooks/helius/pool")
    logger.info("   💸 Transactions: http://localhost:8000/webhooks/helius/tx")
    
    # Log configuration summary
    logger.info(f"🔧 Environment: {settings.ENV}")
    logger.info(f"🔧 Debug mode: {settings.DEBUG}")
    logger.info(f"🔧 Host: {settings.HOST}:{settings.PORT}")
    
    # Show integration status
    logger.info("🔗 Service Integration Status:")
    logger.info("   ✅ Webhooks → Token Analysis Engine")
    logger.info("   ✅ API Router → Comprehensive Analysis")
    logger.info("   ✅ Redis Caching → Performance Optimization")
    logger.info("   ✅ LLM-Optimized Output Format")
    
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

# Health check endpoints (keep original simple ones)
@app.get("/health", summary="System health check")
async def health_check():
    """Detailed system component health check"""
    health_status = await health_check_all_services()
    
    status_code = (
        status.HTTP_200_OK 
        if health_status.get("overall_status") 
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    
    return JSONResponse(
        content=health_status,
        status_code=status_code
    )


@app.get("/health/simple", summary="Simple health check")
async def simple_health_check():
    """Simple health check for load balancers"""
    try:
        from app.utils.health import get_startup_readiness
        readiness = await get_startup_readiness()
        
        if readiness.get("ready"):
            return {"status": "healthy", "timestamp": readiness.get("timestamp")}
        else:
            return JSONResponse(
                content={
                    "status": "unhealthy", 
                    "message": readiness.get("message"),
                    "timestamp": readiness.get("timestamp")
                },
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    except (ImportError, AttributeError):
        # Fallback simple check
        return {"status": "healthy", "message": "Basic health check"}
    except Exception as e:
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e)
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


@app.get("/health/analysis", summary="Analysis Services Health Check")
async def analysis_health_check():
    """Check health of token analysis services specifically"""
    try:
        from app.services.service_manager import get_api_health_status
        analysis_health = await get_api_health_status()
        
        status_code = 200 if analysis_health.get("overall_healthy") else 503
        
        return JSONResponse(
            content={
                **analysis_health,
                "analysis_capabilities": {
                    "comprehensive_analysis": analysis_health.get("overall_healthy", False),
                    "security_analysis": any(
                        service in analysis_health.get("services", {}) and 
                        analysis_health["services"][service].get("healthy", False)
                        for service in ["goplus", "rugcheck"]
                    ),
                    "market_analysis": any(
                        service in analysis_health.get("services", {}) and 
                        analysis_health["services"][service].get("healthy", False)
                        for service in ["birdeye", "dexscreener"]
                    ),
                    "onchain_analysis": any(
                        service in analysis_health.get("services", {}) and 
                        analysis_health["services"][service].get("healthy", False)
                        for service in ["helius", "chainbase", "solanafm"]
                    )
                }
            },
            status_code=status_code
        )
    except Exception as e:
        return JSONResponse(
            content={
                "error": "Analysis health check failed",
                "detail": str(e)
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
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
    """Get configuration status (non-sensitive)"""
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
            "base_url_configured": bool(settings.WEBHOOK_BASE_URL),
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
        "missing_critical_keys": settings.validate_critical_keys()
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
        logger.info("   GET  /api/analyze/stats - Analysis system statistics")
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