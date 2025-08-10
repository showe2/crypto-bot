import sys
import json
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


def json_formatter(record: Dict[str, Any]) -> str:
    """Форматтер для JSON логов"""
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "function": record["function"],
        "line": record["line"],
        "message": record["message"]
    }
    
    # Добавляем дополнительные поля если есть
    if record.get("extra"):
        log_entry.update(record["extra"])
    
    return json.dumps(log_entry, ensure_ascii=False)


def text_formatter(record: Dict[str, Any]) -> str:
    """Форматтер для текстовых логов"""
    return (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} - {message}\n"
    )


def setup_logging():
    """Настройка системы логирования"""
    
    # Удаляем стандартные обработчики loguru
    logger.remove()
    
    # Создаем директорию для логов
    logs_dir = Path(settings.LOGS_DIR)
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Определяем формат в зависимости от настроек
    if settings.LOG_FORMAT.lower() == "json":
        formatter = json_formatter
        format_string = "{message}"
    else:
        formatter = text_formatter
        format_string = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
    
    # Консольный вывод
    if settings.ENV == "development":
        logger.add(
            sys.stdout,
            format=format_string,
            level=settings.LOG_LEVEL,
            colorize=True,
            backtrace=True,
            diagnose=True
        )
    else:
        # В продакшене используем JSON формат для консоли
        logger.add(
            sys.stdout,
            format="{message}",
            level=settings.LOG_LEVEL,
            serialize=settings.LOG_FORMAT.lower() == "json"
        )
    
    # Основной лог файл
    logger.add(
        logs_dir / "app.log",
        format=format_string if settings.LOG_FORMAT.lower() != "json" else "{message}",
        level=settings.LOG_LEVEL,
        rotation="10 MB",
        retention="30 days",
        compression="gz",
        serialize=settings.LOG_FORMAT.lower() == "json",
        backtrace=True,
        diagnose=settings.ENV != "production"
    )
    
    # Файл ошибок
    logger.add(
        logs_dir / "errors.log",
        format=format_string if settings.LOG_FORMAT.lower() != "json" else "{message}",
        level="ERROR",
        rotation="5 MB",
        retention="60 days",
        compression="gz",
        serialize=settings.LOG_FORMAT.lower() == "json",
        backtrace=True,
        diagnose=True
    )
    
    # Лог API запросов
    logger.add(
        logs_dir / "api_requests.log",
        format=format_string if settings.LOG_FORMAT.lower() != "json" else "{message}",
        level="INFO",
        rotation="20 MB",
        retention="14 days",
        compression="gz",
        serialize=settings.LOG_FORMAT.lower() == "json",
        filter=lambda record: "api_request" in record.get("extra", {})
    )
    
    # Лог анализа токенов
    logger.add(
        logs_dir / "token_analysis.log",
        format=format_string if settings.LOG_FORMAT.lower() != "json" else "{message}",
        level="INFO",
        rotation="50 MB",
        retention="30 days",
        compression="gz",
        serialize=settings.LOG_FORMAT.lower() == "json",
        filter=lambda record: "token_analysis" in record.get("extra", {})
    )
    
    # Лог AI операций
    logger.add(
        logs_dir / "ai_operations.log",
        format=format_string if settings.LOG_FORMAT.lower() != "json" else "{message}",
        level="INFO",
        rotation="30 MB",
        retention="21 days",
        compression="gz",
        serialize=settings.LOG_FORMAT.lower() == "json",
        filter=lambda record: "ai_operation" in record.get("extra", {})
    )
    
    # Лог WebHooks
    logger.add(
        logs_dir / "webhooks.log",
        format=format_string if settings.LOG_FORMAT.lower() != "json" else "{message}",
        level="INFO",
        rotation="10 MB",
        retention="14 days",
        compression="gz",
        serialize=settings.LOG_FORMAT.lower() == "json",
        filter=lambda record: "webhook" in record.get("extra", {})
    )
    
    # Настройка логирования для внешних библиотек
    import logging
    
    # Uvicorn
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.error").handlers = []
    
    # httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Redis
    logging.getLogger("redis").setLevel(logging.WARNING)
    
    # ChromaDB
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    
    logger.info("Система логирования настроена", extra={
        "log_level": settings.LOG_LEVEL,
        "log_format": settings.LOG_FORMAT,
        "logs_directory": str(logs_dir),
        "environment": settings.ENV
    })


def get_logger(name: str):
    """Получить именованный логгер с контекстом"""
    return logger.bind(logger_name=name)


def log_api_request(
    endpoint: str,
    method: str,
    status_code: int,
    processing_time: float,
    client_ip: str = None,
    user_agent: str = None,
    additional_data: Dict[str, Any] = None
):
    """Логирование API запроса"""
    log_data = {
        "api_request": True,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "processing_time_ms": round(processing_time * 1000, 2),
        "client_ip": client_ip,
        "user_agent": user_agent
    }
    
    if additional_data:
        log_data.update(additional_data)
    
    logger.info(
        f"{method} {endpoint} - {status_code} ({processing_time*1000:.2f}ms)",
        extra=log_data
    )


def log_token_analysis(
    token_mint: str,
    analysis_type: str,
    processing_time: float,
    result_score: float = None,
    errors: list = None,
    data_sources: list = None
):
    """Логирование анализа токена"""
    log_data = {
        "token_analysis": True,
        "token_mint": token_mint,
        "analysis_type": analysis_type,
        "processing_time_seconds": round(processing_time, 3),
        "result_score": result_score,
        "errors_count": len(errors) if errors else 0,
        "data_sources": data_sources or []
    }
    
    if errors:
        log_data["errors"] = errors
    
    logger.info(
        f"Token analysis completed: {token_mint} ({analysis_type}) - {processing_time:.2f}s",
        extra=log_data
    )


def log_ai_operation(
    model_name: str,
    operation: str,
    processing_time: float,
    input_tokens: int = None,
    output_tokens: int = None,
    cost_estimate: float = None,
    success: bool = True,
    error_message: str = None
):
    """Логирование AI операции"""
    log_data = {
        "ai_operation": True,
        "model": model_name,
        "operation": operation,
        "processing_time_seconds": round(processing_time, 3),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": (input_tokens or 0) + (output_tokens or 0),
        "cost_estimate": cost_estimate,
        "success": success
    }
    
    if error_message:
        log_data["error"] = error_message
    
    level = "INFO" if success else "ERROR"
    message = f"AI operation: {model_name} {operation} - {'success' if success else 'failed'} ({processing_time:.2f}s)"
    
    logger.log(level, message, extra=log_data)


def log_webhook_event(
    webhook_type: str,
    event_data: Dict[str, Any],
    processing_time: float,
    success: bool = True,
    error_message: str = None
):
    """Логирование WebHook события"""
    log_data = {
        "webhook": True,
        "webhook_type": webhook_type,
        "processing_time_ms": round(processing_time * 1000, 2),
        "success": success,
        "event_size": len(str(event_data))
    }
    
    # Добавляем безопасную информацию о событии
    if isinstance(event_data, dict):
        safe_data = {}
        for key, value in event_data.items():
            if key in ["mint", "signature", "blockTime", "slot", "type"]:
                safe_data[key] = value
        log_data.update(safe_data)
    
    if error_message:
        log_data["error"] = error_message
    
    level = "INFO" if success else "ERROR"
    message = f"WebHook {webhook_type}: {'processed' if success else 'failed'} ({processing_time*1000:.1f}ms)"
    
    logger.log(level, message, extra=log_data)


def log_external_api_call(
    api_name: str,
    endpoint: str,
    method: str,
    status_code: int,
    response_time: float,
    success: bool = True,
    error_message: str = None,
    rate_limit_remaining: int = None
):
    """Логирование вызова внешнего API"""
    log_data = {
        "external_api": True,
        "api_name": api_name,
        "endpoint": endpoint.split('?')[0],  # Убираем параметры для безопасности
        "method": method,
        "status_code": status_code,
        "response_time_ms": round(response_time * 1000, 2),
        "success": success,
        "rate_limit_remaining": rate_limit_remaining
    }
    
    if error_message:
        log_data["error"] = error_message
    
    level = "INFO" if success else "WARNING"
    message = f"External API {api_name}: {method} {endpoint.split('?')[0]} - {status_code} ({response_time*1000:.1f}ms)"
    
    logger.log(level, message, extra=log_data)


def log_system_event(
    event_type: str,
    description: str,
    severity: str = "INFO",
    additional_data: Dict[str, Any] = None
):
    """Логирование системного события"""
    log_data = {
        "system_event": True,
        "event_type": event_type,
        "severity": severity
    }
    
    if additional_data:
        log_data.update(additional_data)
    
    logger.log(severity, f"System event ({event_type}): {description}", extra=log_data)


def log_performance_metrics(
    operation: str,
    metrics: Dict[str, Any]
):
    """Логирование метрик производительности"""
    log_data = {
        "performance_metrics": True,
        "operation": operation,
        **metrics
    }
    
    logger.info(f"Performance metrics for {operation}", extra=log_data)


class LoggingMiddleware:
    """Middleware для логирования HTTP запросов"""
    
    def __init__(self):
        self.logger = get_logger("http")
    
    async def __call__(self, request, call_next):
        import time
        
        start_time = time.time()
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent")
        
        try:
            response = await call_next(request)
            processing_time = time.time() - start_time
            
            log_api_request(
                endpoint=str(request.url.path),
                method=request.method,
                status_code=response.status_code,
                processing_time=processing_time,
                client_ip=client_ip,
                user_agent=user_agent
            )
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            log_api_request(
                endpoint=str(request.url.path),
                method=request.method,
                status_code=500,
                processing_time=processing_time,
                client_ip=client_ip,
                user_agent=user_agent,
                additional_data={"error": str(e)}
            )
            
            raise