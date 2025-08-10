import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
import uvicorn
from loguru import logger

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.routers import alex_core
from app.utils.health import health_check_all_services

# Global settings
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Startup
    logger.info("🚀 Starting Solana Token Analysis System...")
    
    # Check all dependencies
    health_status = await health_check_all_services()
    if not health_status.get("overall_status"):
        logger.error("❌ Critical services unavailable!")
        for service, status in health_status.get("services", {}).items():
            if not status.get("healthy"):
                logger.error(f"   • {service}: {status.get('error', 'Unknown error')}")
    else:
        logger.info("✅ All services ready")
    
    yield
    
    # Shutdown
    logger.info("🛑 Stopping Token Analysis System...")


# Create FastAPI application
app = FastAPI(
    title="Solana Token Analysis AI System",
    description="Integrated Solana token analysis system with AI capabilities",
    version="1.0.0",
    docs_url="/docs" if settings.ENV == "development" else None,
    redoc_url="/redoc" if settings.ENV == "development" else None,
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENV == "development" else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted hosts
if settings.ENV == "production":
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
    )

# Static files (for web interface)
if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

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
        "docs_url": "/docs" if settings.ENV == "development" else "disabled"
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


@app.get("/dashboard", summary="Web dashboard interface")
async def dashboard(request: Request):
    """Web interface for system management"""
    context = {
        "request": request,
        "title": "Solana Token Analysis Dashboard",
        "environment": settings.ENV
    }
    return templates.TemplateResponse("dashboard.html", context)


# Validation error handling
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Input data validation error handler"""
    logger.warning(f"Validation error for {request.url}: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "message": "Please check input data validity"
        }
    )


def create_app() -> FastAPI:
    """Application factory"""
    setup_logging()
    return app


if __name__ == "__main__":
    # Configure logging
    setup_logging()
    
    # Run in development mode
    logger.info(f"🔥 Starting in development mode on port {settings.PORT}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENV == "development",
        log_level="info" if settings.ENV == "production" else "debug",
        access_log=True
    )