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

# Глобальные настройки
settings = get_settings()

# Настройка шаблонов
templates = Jinja2Templates(directory="templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("🚀 Запуск системы анализа токенов Solana...")
    
    # Проверка всех зависимостей
    health_status = await health_check_all_services()
    if not health_status.get("overall_status"):
        logger.error("❌ Критические сервисы недоступны!")
        for service, status in health_status.get("services", {}).items():
            if not status.get("healthy"):
                logger.error(f"   • {service}: {status.get('error', 'Неизвестная ошибка')}")
    else:
        logger.info("✅ Все сервисы готовы к работе")
    
    yield
    
    # Shutdown
    logger.info("🛑 Остановка системы анализа токенов...")


# Создание FastAPI приложения
app = FastAPI(
    title="Solana Token Analysis AI System",
    description="Интегрированная система анализа токенов Solana с использованием ИИ",
    version="1.0.0",
    docs_url="/docs" if settings.ENV == "development" else None,
    redoc_url="/redoc" if settings.ENV == "development" else None,
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENV == "development" else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Доверенные хосты
if settings.ENV == "production":
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
    )

# Статические файлы (для веб-интерфейса)
if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключение роутеров
app.include_router(
    alex_core.router,
    prefix="",
    tags=["core"]
)


@app.get("/", summary="Статус системы")
async def root():
    """Главная страница - статус системы"""
    return {
        "service": "Solana Token Analysis AI System",
        "status": "running",
        "version": "1.0.0",
        "environment": settings.ENV,
        "docs_url": "/docs" if settings.ENV == "development" else "disabled"
    }


@app.get("/health", summary="Проверка здоровья системы")
async def health_check():
    """Детальная проверка состояния всех компонентов системы"""
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


@app.get("/dashboard", summary="Веб-интерфейс dashboard")
async def dashboard(request: Request):
    """Веб-интерфейс для управления системой"""
    context = {
        "request": request,
        "title": "Solana Token Analysis Dashboard",
        "environment": settings.ENV
    }
    return templates.TemplateResponse("dashboard.html", context)


# Обработка ошибок валидации
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации входящих данных"""
    logger.warning(f"Ошибка валидации для {request.url}: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "message": "Проверьте корректность входящих данных"
        }
    )


def create_app() -> FastAPI:
    """Фабрика для создания приложения"""
    setup_logging()
    return app


if __name__ == "__main__":
    # Настройка логирования
    setup_logging()
    
    # Запуск в режиме разработки
    logger.info(f"🔥 Запуск в режиме разработки на порту {settings.PORT}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENV == "development",
        log_level="info" if settings.ENV == "production" else "debug",
        access_log=True
    )
