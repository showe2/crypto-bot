import asyncio
import time
from typing import Dict, Any, Optional
import httpx
import redis.asyncio as redis
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


async def check_redis_connection() -> Dict[str, Any]:
    """Проверка подключения к Redis"""
    try:
        redis_client = redis.from_url(settings.get_redis_url())
        
        # Тест ping
        start_time = time.time()
        await redis_client.ping()
        response_time = (time.time() - start_time) * 1000
        
        # Тест записи/чтения
        test_key = "health_check_test"
        await redis_client.set(test_key, "ok", ex=60)
        test_value = await redis_client.get(test_key)
        
        await redis_client.close()
        
        return {
            "healthy": True,
            "response_time_ms": round(response_time, 2),
            "test_write_read": test_value.decode() == "ok" if test_value else False,
            "url": settings.REDIS_URL.split('@')[-1] if '@' in settings.REDIS_URL else settings.REDIS_URL
        }
        
    except Exception as e:
        logger.warning(f"Redis недоступен: {str(e)}")
        return {
            "healthy": False,
            "error": str(e),
            "url": settings.REDIS_URL.split('@')[-1] if '@' in settings.REDIS_URL else settings.REDIS_URL
        }


async def check_chromadb_connection() -> Dict[str, Any]:
    """Проверка подключения к ChromaDB"""
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        
        # Подключение к ChromaDB
        client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_PATH,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        start_time = time.time()
        
        # Тест создания коллекции или получения существующей
        try:
            collection = client.get_or_create_collection(
                name=f"health_test_{int(time.time())}"
            )
            
            # Тест добавления документа
            collection.add(
                documents=["health check test document"],
                metadatas=[{"test": True}],
                ids=["health_test_1"]
            )
            
            # Тест поиска
            results = collection.query(
                query_texts=["health test"],
                n_results=1
            )
            
            # Удаление тестовой коллекции
            client.delete_collection(collection.name)
            
        except Exception as collection_error:
            # Если не удалось создать коллекцию, проверяем основную
            collections = client.list_collections()
            if not any(col.name == settings.CHROMA_COLLECTION_NAME for col in collections):
                # Создаем основную коллекцию
                client.get_or_create_collection(name=settings.CHROMA_COLLECTION_NAME)
        
        response_time = (time.time() - start_time) * 1000
        
        return {
            "healthy": True,
            "response_time_ms": round(response_time, 2),
            "path": settings.CHROMA_DB_PATH,
            "main_collection": settings.CHROMA_COLLECTION_NAME
        }
        
    except Exception as e:
        logger.warning(f"ChromaDB недоступен: {str(e)}")
        return {
            "healthy": False,
            "error": str(e),
            "path": settings.CHROMA_DB_PATH
        }


async def check_api_endpoint(name: str, url: str, headers: Dict[str, str] = None, timeout: int = 10) -> Dict[str, Any]:
    """Проверка доступности API эндпоинта"""
    try:
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Простой GET или HEAD запрос для проверки доступности
            try:
                response = await client.head(url, headers=headers or {})
            except:
                # Если HEAD не поддерживается, пробуем GET
                response = await client.get(url, headers=headers or {})
        
        response_time = (time.time() - start_time) * 1000
        
        return {
            "healthy": response.status_code < 500,
            "status_code": response.status_code,
            "response_time_ms": round(response_time, 2),
            "url": url.split('?')[0]  # Убираем параметры для безопасности
        }
        
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "url": url.split('?')[0]
        }


async def check_blockchain_apis() -> Dict[str, Dict[str, Any]]:
    """Проверка всех blockchain API"""
    api_checks = {}
    
    # Helius RPC
    if settings.HELIUS_API_KEY:
        api_checks["helius_rpc"] = await check_api_endpoint(
            "Helius RPC",
            settings.get_helius_rpc_url(),
            {"Content-Type": "application/json"}
        )
    
    # Chainbase API
    if settings.CHAINBASE_API_KEY:
        api_checks["chainbase"] = await check_api_endpoint(
            "Chainbase",
            f"{settings.CHAINBASE_BASE_URL}/account/tokens",
            {"X-API-KEY": settings.CHAINBASE_API_KEY}
        )
    
    # Birdeye API
    if settings.BIRDEYE_API_KEY:
        api_checks["birdeye"] = await check_api_endpoint(
            "Birdeye",
            f"{settings.BIRDEYE_BASE_URL}/defi/tokenlist",
            {"X-API-KEY": settings.BIRDEYE_API_KEY}
        )
    
    # Blowfish API
    if settings.BLOWFISH_API_KEY:
        api_checks["blowfish"] = await check_api_endpoint(
            "Blowfish",
            f"{settings.BLOWFISH_BASE_URL}/v0/sol/scan",
            {"X-API-Key": settings.BLOWFISH_API_KEY}
        )
    
    # Solscan API
    if settings.SOLSCAN_API_KEY:
        api_checks["solscan"] = await check_api_endpoint(
            "Solscan",
            f"{settings.SOLSCAN_BASE_URL}/token/holders",
            {"token": settings.SOLSCAN_API_KEY}
        )
    
    # DataImpulse API
    if settings.DATAIMPULSE_API_KEY:
        api_checks["dataimpulse"] = await check_api_endpoint(
            "DataImpulse", 
            f"{settings.DATAIMPULSE_BASE_URL}/status",
            {"Authorization": f"Bearer {settings.DATAIMPULSE_API_KEY}"}
        )
    
    return api_checks


async def check_ai_models() -> Dict[str, Dict[str, Any]]:
    """Проверка доступности AI моделей"""
    ai_checks = {}
    
    # Mistral API
    if settings.MISTRAL_API_KEY:
        ai_checks["mistral_7b"] = await check_api_endpoint(
            "Mistral 7B",
            f"{settings.MISTRAL_API_URL}/models",
            {"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"}
        )
    
    # LLaMA API
    if settings.LLAMA_API_KEY:
        ai_checks["llama_70b"] = await check_api_endpoint(
            "LLaMA 3 70B",
            f"{settings.LLAMA_API_URL}/models",
            {"Authorization": f"Bearer {settings.LLAMA_API_KEY}"}
        )
    
    return ai_checks


async def check_file_system() -> Dict[str, Any]:
    """Проверка файловой системы и путей"""
    try:
        import os
        from pathlib import Path
        
        paths_to_check = [
            settings.CHROMA_DB_PATH,
            settings.KNOWLEDGE_BASE_PATH,
            settings.LOGS_DIR
        ]
        
        path_statuses = {}
        
        for path_str in paths_to_check:
            path = Path(path_str)
            path_name = path.name or "root"
            
            try:
                # Проверяем существование и права
                exists = path.exists()
                is_dir = path.is_dir() if exists else False
                writable = os.access(path, os.W_OK) if exists else False
                readable = os.access(path, os.R_OK) if exists else False
                
                # Пробуем создать тестовый файл
                test_file_path = path / "health_test.tmp"
                can_write = False
                try:
                    if path.exists():
                        test_file_path.touch()
                        test_file_path.unlink()
                        can_write = True
                except:
                    pass
                
                path_statuses[path_name] = {
                    "exists": exists,
                    "is_directory": is_dir,
                    "readable": readable,
                    "writable": writable and can_write,
                    "path": str(path),
                    "healthy": exists and is_dir and readable and (writable and can_write)
                }
                
            except Exception as path_error:
                path_statuses[path_name] = {
                    "healthy": False,
                    "error": str(path_error),
                    "path": str(path)
                }
        
        # Общий статус
        all_healthy = all(status.get("healthy", False) for status in path_statuses.values())
        
        return {
            "healthy": all_healthy,
            "paths": path_statuses,
            "total_paths": len(paths_to_check),
            "healthy_paths": sum(1 for status in path_statuses.values() if status.get("healthy", False))
        }
        
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e)
        }


async def health_check_all_services() -> Dict[str, Any]:
    """Комплексная проверка здоровья всех сервисов"""
    logger.info("Запуск комплексной проверки здоровья сервисов...")
    
    start_time = time.time()
    
    # Выполняем все проверки параллельно
    results = await asyncio.gather(
        check_redis_connection(),
        check_chromadb_connection(),
        check_blockchain_apis(),
        check_ai_models(),
        check_file_system(),
        return_exceptions=True
    )
    
    # Распаковка результатов
    redis_status = results[0] if not isinstance(results[0], Exception) else {"healthy": False, "error": str(results[0])}
    chromadb_status = results[1] if not isinstance(results[1], Exception) else {"healthy": False, "error": str(results[1])}
    blockchain_apis = results[2] if not isinstance(results[2], Exception) else {}
    ai_models = results[3] if not isinstance(results[3], Exception) else {}
    file_system = results[4] if not isinstance(results[4], Exception) else {"healthy": False, "error": str(results[4])}
    
    # Агрегация результатов
    all_services = {
        "redis": redis_status,
        "chromadb": chromadb_status,
        "file_system": file_system,
        **{f"api_{name}": status for name, status in blockchain_apis.items()},
        **{f"ai_{name}": status for name, status in ai_models.items()}
    }
    
    # Подсчет общего статуса
    total_services = len(all_services)
    healthy_services = sum(1 for service in all_services.values() if service.get("healthy", False))
    
    # Критические сервисы (без них система не может работать)
    critical_services = ["redis", "chromadb", "file_system"]
    critical_healthy = all(
        all_services.get(service, {}).get("healthy", False) 
        for service in critical_services
    )
    
    # Проверка минимального набора API
    has_blockchain_api = any(
        all_services.get(f"api_{api}", {}).get("healthy", False)
        for api in ["helius_rpc", "birdeye"]
    )
    
    has_ai_model = any(
        all_services.get(f"ai_{model}", {}).get("healthy", False)
        for model in ["mistral_7b", "llama_70b"]
    )
    
    # Общий статус системы
    overall_status = critical_healthy and (has_blockchain_api or settings.ENABLE_API_MOCKS) and (has_ai_model or settings.MOCK_AI_RESPONSES)
    
    total_time = time.time() - start_time
    
    health_report = {
        "overall_status": overall_status,
        "summary": {
            "total_services": total_services,
            "healthy_services": healthy_services,
            "critical_services_ok": critical_healthy,
            "blockchain_apis_available": has_blockchain_api,
            "ai_models_available": has_ai_model
        },
        "services": all_services,
        "recommendations": [],
        "check_duration_seconds": round(total_time, 3),
        "timestamp": time.time()
    }
    
    # Рекомендации по исправлению проблем
    if not critical_healthy:
        health_report["recommendations"].append("Критические сервисы недоступны - проверьте Redis, ChromaDB и файловую систему")
    
    if not has_blockchain_api and not settings.ENABLE_API_MOCKS:
        health_report["recommendations"].append("Нет доступных blockchain API - настройте Helius или Birdeye")
    
    if not has_ai_model and not settings.MOCK_AI_RESPONSES:
        health_report["recommendations"].append("Нет доступных AI моделей - настройте Mistral или LLaMA API ключи")
    
    if healthy_services < total_services:
        failed_services = [name for name, status in all_services.items() if not status.get("healthy", False)]
        health_report["recommendations"].append(f"Проблемы с сервисами: {', '.join(failed_services)}")
    
    logger.info(f"Проверка здоровья завершена за {total_time:.2f}s: {healthy_services}/{total_services} сервисов работают")
    
    return health_report


async def get_service_metrics() -> Dict[str, Any]:
    """Получение метрик производительности сервисов"""
    try:
        # Метрики Redis
        redis_metrics = {}
        try:
            redis_client = redis.from_url(settings.get_redis_url())
            info = await redis_client.info()
            redis_metrics = {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0)
            }
            await redis_client.close()
        except Exception as e:
            redis_metrics = {"error": str(e)}
        
        # Метрики файловой системы
        fs_metrics = {}
        try:
            import psutil
            disk_usage = psutil.disk_usage(settings.LOGS_DIR)
            fs_metrics = {
                "disk_total_gb": round(disk_usage.total / (1024**3), 2),
                "disk_used_gb": round(disk_usage.used / (1024**3), 2),
                "disk_free_gb": round(disk_usage.free / (1024**3), 2),
                "disk_usage_percent": round((disk_usage.used / disk_usage.total) * 100, 1)
            }
        except:
            fs_metrics = {"error": "psutil not available"}
        
        return {
            "redis": redis_metrics,
            "filesystem": fs_metrics,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения метрик сервисов: {str(e)}")
        return {"error": str(e)}