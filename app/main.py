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
from app.utils.health import health_check_all_services

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
    """Application lifecycle management"""
    # Startup
    logger.info("🚀 Starting Solana Token Analysis System...")
    
    # Initialize dependencies
    try:
        await startup_dependencies()
        logger.info("✅ System dependencies initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize dependencies: {str(e)}")
        # Continue anyway - some services might still work
    
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
    
    # Log configuration summary
    logger.info(f"🔧 Environment: {settings.ENV}")
    logger.info(f"🔧 Debug mode: {settings.DEBUG}")
    logger.info(f"🔧 Host: {settings.HOST}:{settings.PORT}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Stopping Token Analysis System...")
    
    try:
        await shutdown_dependencies()
        logger.info("✅ System dependencies cleaned up")
    except Exception as e:
        logger.warning(f"⚠️  Dependency cleanup warning: {str(e)}")
    
    logger.info("👋 System shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Solana Token Analysis AI System",
    description="Integrated Solana token analysis system with AI capabilities",
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

# Templates (for web interface) - optional
templates = None
templates_dir = Path("templates")
if templates_dir.exists():
    try:
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="templates")
        logger.info("✅ Templates system initialized")
    except ImportError:
        logger.warning("⚠️  Jinja2 not installed - dashboard disabled")
    except Exception as e:
        logger.warning(f"⚠️  Template initialization failed: {str(e)}")
else:
    logger.info("ℹ️  Templates directory not found - dashboard disabled")

# Include routers
app.include_router(
    alex_core.router,
    prefix="",
    tags=["core"]
)


@app.get("/", summary="System status")
async def root():
    """Homepage - system status"""
    return {
        "service": "Solana Token Analysis AI System",
        "status": "running",
        "version": "1.0.0",
        "environment": settings.ENV,
        "debug": settings.DEBUG,
        "docs_url": "/docs" if settings.ENV == "development" else "disabled",
        "health_check": "/health",
        "api_commands": "/commands"
    }


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
        "rate_limits": {
            "per_minute": settings.RATE_LIMIT_PER_MINUTE,
            "per_hour": settings.RATE_LIMIT_PER_HOUR
        },
        "api_keys_configured": len([
            key for key, status in settings.get_all_api_keys_status().items()
            if status['configured']
        ]),
        "missing_critical_keys": settings.validate_critical_keys()
    }
    
    return config_info


@app.get("/dashboard", summary="Web dashboard interface")
async def dashboard(request: Request):
    """Web interface for system management"""
    if not templates or not templates_dir.exists():
        return JSONResponse(
            content={
                "error": "Dashboard not available", 
                "reason": "Templates not configured or Jinja2 not installed",
                "install_command": "pip install jinja2"
            },
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    try:
        # Get system status for dashboard
        health_status = await health_check_all_services()
        
        # Try to get metrics, fallback if not available
        try:
            from app.utils.health import get_service_metrics
            metrics = await get_service_metrics()
        except (ImportError, AttributeError):
            metrics = {"error": "Metrics not available"}
        
        context = {
            "request": request,
            "title": "Solana Token Analysis Dashboard",
            "environment": settings.ENV,
            "system_status": health_status,
            "metrics": metrics,
            "version": "1.0.0"
        }
        
        return templates.TemplateResponse("dashboard.html", context)
        
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return JSONResponse(
            content={
                "error": "Dashboard temporarily unavailable",
                "detail": str(e)
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


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
        logger.info("📊 Metrics: http://localhost:8000/metrics")
    
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