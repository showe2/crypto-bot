import asyncio
import time
from typing import Dict, Any
from pathlib import Path
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


async def check_file_system() -> Dict[str, Any]:
    """Check and create required directories"""
    try:
        import os
        
        paths_to_check = [
            settings.CHROMA_DB_PATH,
            settings.KNOWLEDGE_BASE_PATH, 
            settings.LOGS_DIR
        ]
        
        path_statuses = {}
        
        for path_str in paths_to_check:
            path = Path(path_str)
            path_name = path.name or path.parts[-1] if path.parts else "root"
            
            try:
                # Create directory if it doesn't exist
                path.mkdir(parents=True, exist_ok=True)
                
                # Check permissions after creation
                exists = path.exists()
                is_dir = path.is_dir() if exists else False
                writable = os.access(path, os.W_OK) if exists else False
                readable = os.access(path, os.R_OK) if exists else False
                
                path_statuses[path_name] = {
                    "exists": exists,
                    "is_directory": is_dir,
                    "readable": readable,
                    "writable": writable,
                    "path": str(path),
                    "healthy": exists and is_dir and readable
                }
                
            except Exception as path_error:
                logger.warning(f"Path issue {path}: {path_error}")
                path_statuses[path_name] = {
                    "healthy": False,
                    "error": str(path_error),
                    "path": str(path)
                }
        
        all_healthy = all(status.get("healthy", False) for status in path_statuses.values())
        
        return {
            "healthy": all_healthy,
            "paths": path_statuses,
            "total_paths": len(paths_to_check),
            "healthy_paths": sum(1 for status in path_statuses.values() if status.get("healthy", False))
        }
        
    except Exception as e:
        logger.warning(f"Filesystem check error: {str(e)}")
        return {
            "healthy": False,
            "error": str(e)
        }


async def check_basic_system() -> Dict[str, Any]:
    """Check basic system components"""
    try:
        system_info = {
            "python_version": f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}.{__import__('sys').version_info.micro}",
            "environment": settings.ENV,
            "debug_mode": settings.DEBUG,
            "host": settings.HOST,
            "port": settings.PORT
        }
        
        # Check required module availability
        required_modules = []
        try:
            import fastapi
            required_modules.append({"name": "fastapi", "version": fastapi.__version__, "available": True})
        except ImportError:
            required_modules.append({"name": "fastapi", "available": False, "error": "Not installed"})
        
        try:
            import uvicorn
            required_modules.append({"name": "uvicorn", "version": uvicorn.__version__, "available": True})
        except ImportError:
            required_modules.append({"name": "uvicorn", "available": False, "error": "Not installed"})
        
        try:
            import pydantic
            required_modules.append({"name": "pydantic", "version": pydantic.VERSION, "available": True})
        except ImportError:
            required_modules.append({"name": "pydantic", "available": False, "error": "Not installed"})
        
        # All core modules must be available
        modules_healthy = all(module.get("available", False) for module in required_modules)
        
        return {
            "healthy": modules_healthy,
            "system_info": system_info,
            "required_modules": required_modules,
            "modules_count": len(required_modules),
            "available_modules": sum(1 for m in required_modules if m.get("available", False))
        }
        
    except Exception as e:
        logger.error(f"Basic system check error: {str(e)}")
        return {
            "healthy": False,
            "error": str(e)
        }


async def check_logging_system() -> Dict[str, Any]:
    """Check logging system"""
    try:
        # Verify loguru is working
        test_logger = logger.bind(test=True)
        test_logger.info("Health check test log")
        
        logs_dir = Path(settings.LOGS_DIR)
        
        return {
            "healthy": True,
            "logs_directory": str(logs_dir),
            "logs_dir_exists": logs_dir.exists(),
            "log_level": settings.LOG_LEVEL,
            "log_format": settings.LOG_FORMAT
        }
        
    except Exception as e:
        logger.warning(f"Logging system issue: {str(e)}")
        return {
            "healthy": False,
            "error": str(e)
        }


async def check_redis_system() -> Dict[str, Any]:
    """Check Redis connection"""
    try:
        from app.utils.redis_client import check_redis_health
        return await check_redis_health()
    except ImportError:
        logger.debug("Redis client not available - this is optional")
        return {
            "healthy": False,
            "available": False,
            "optional": True,
            "error": "Redis client not installed (install with: pip install redis)"
        }
    except Exception as e:
        logger.debug(f"Redis check error: {str(e)}")
        return {
            "healthy": False,
            "error": str(e)
        }


async def check_chroma_system() -> Dict[str, Any]:
    """Check ChromaDB connection"""
    try:
        from app.utils.chroma_client import check_chroma_health
        return await check_chroma_health()
    except ImportError:
        logger.debug("ChromaDB client not available - this is optional")
        return {
            "healthy": False,
            "available": False,
            "optional": True,
            "error": "ChromaDB not installed (install with: pip install chromadb)"
        }
    except Exception as e:
        logger.debug(f"ChromaDB check error: {str(e)}")
        return {
            "healthy": False,
            "error": str(e)
        }


async def check_cache_system() -> Dict[str, Any]:
    """Check cache system"""
    try:
        from app.utils.cache import get_cache_health
        return await get_cache_health()
    except ImportError:
        logger.debug("Cache system not available")
        return {
            "healthy": False,
            "available": False,
            "optional": True,
            "error": "Cache system not imported"
        }
    except Exception as e:
        logger.debug(f"Cache check error: {str(e)}")
        return {
            "healthy": False,
            "error": str(e)
        }


async def health_check_all_services() -> Dict[str, Any]:
    """Complete health check for all services"""
    logger.info("Starting comprehensive system health checks...")
    
    start_time = time.time()
    
    # Run all health checks concurrently
    try:
        results = await asyncio.gather(
            check_basic_system(),
            check_file_system(),
            check_logging_system(),
            check_redis_system(),
            check_chroma_system(),
            check_cache_system(),
            return_exceptions=True
        )
    except Exception as e:
        logger.error(f"Service check error: {str(e)}")
        results = [{"healthy": False, "error": str(e)}] * 6
    
    # Unpack results
    basic_system = results[0] if not isinstance(results[0], Exception) else {"healthy": False, "error": str(results[0])}
    file_system = results[1] if not isinstance(results[1], Exception) else {"healthy": False, "error": str(results[1])}
    logging_system = results[2] if not isinstance(results[2], Exception) else {"healthy": False, "error": str(results[2])}
    redis_system = results[3] if not isinstance(results[3], Exception) else {"healthy": False, "error": str(results[3])}
    chroma_system = results[4] if not isinstance(results[4], Exception) else {"healthy": False, "error": str(results[4])}
    cache_system = results[5] if not isinstance(results[5], Exception) else {"healthy": False, "error": str(results[5])}
    
    # Aggregate results
    all_services = {
        "basic_system": basic_system,
        "file_system": file_system,
        "logging_system": logging_system,
        "redis": redis_system,
        "chromadb": chroma_system,
        "cache": cache_system
    }
    
    # Calculate overall status
    total_services = len(all_services)
    healthy_services = sum(1 for service in all_services.values() if service.get("healthy", False))
    
    # Critical services that must work for basic operation
    critical_services = ["basic_system", "file_system", "logging_system"]
    critical_services_healthy = all(
        all_services[service].get("healthy", False) 
        for service in critical_services
    )
    
    # Optional services that enhance functionality
    optional_services = ["redis", "chromadb", "cache"]
    optional_services_healthy = sum(
        1 for service in optional_services 
        if all_services[service].get("healthy", False)
    )
    
    # System is ready if critical services work
    overall_status = critical_services_healthy
    
    total_time = time.time() - start_time
    
    health_report = {
        "overall_status": overall_status,
        "summary": {
            "total_services": total_services,
            "healthy_services": healthy_services,
            "critical_services_healthy": len(critical_services),
            "critical_services_working": sum(
                1 for service in critical_services 
                if all_services[service].get("healthy", False)
            ),
            "optional_services_healthy": len(optional_services),
            "optional_services_working": optional_services_healthy,
            "system_ready": overall_status
        },
        "services": all_services,
        "service_categories": {
            "critical": {
                "services": critical_services,
                "description": "Essential services required for basic operation",
                "all_healthy": critical_services_healthy
            },
            "optional": {
                "services": optional_services,
                "description": "Enhanced functionality services",
                "healthy_count": optional_services_healthy,
                "total_count": len(optional_services)
            }
        },
        "recommendations": [],
        "check_duration_seconds": round(total_time, 3),
        "timestamp": time.time(),
        "environment": settings.ENV
    }
    
    # Generate recommendations
    if not critical_services_healthy:
        health_report["recommendations"].append("Critical system components unavailable - check Python package installation")
    
    if not file_system.get("healthy", False):
        health_report["recommendations"].append("Filesystem issues - check directory permissions")
        
    if not logging_system.get("healthy", False):
        health_report["recommendations"].append("Logging system issues - check log settings")
    
    if not redis_system.get("healthy", False):
        health_report["recommendations"].append("Redis unavailable - caching and background tasks disabled")
    
    if not chroma_system.get("healthy", False):
        health_report["recommendations"].append("ChromaDB unavailable - vector storage and knowledge base disabled")
    
    if not cache_system.get("healthy", False):
        health_report["recommendations"].append("Cache system issues - performance may be degraded")
    
    # Performance recommendations
    if optional_services_healthy < len(optional_services):
        health_report["recommendations"].append(
            f"Only {optional_services_healthy}/{len(optional_services)} optional services available - "
            "install missing dependencies for full functionality"
        )
    
    # Environment-specific recommendations
    if settings.ENV == "production" and not all([
        redis_system.get("healthy", False),
        cache_system.get("healthy", False)
    ]):
        health_report["recommendations"].append(
            "Production environment should have Redis and cache systems available"
        )
    
    status_msg = "ready" if overall_status else "has critical issues"
    logger.info(
        f"Health check completed in {total_time:.2f}s: System {status_msg} "
        f"({healthy_services}/{total_services} services working)"
    )
    
    return health_report


async def get_service_metrics() -> Dict[str, Any]:
    """Get detailed system metrics"""
    try:
        metrics = {
            "system": {
                "environment": settings.ENV,
                "debug_mode": settings.DEBUG,
                "host": settings.HOST,
                "port": settings.PORT,
                "timestamp": time.time()
            }
        }
        
        # Filesystem metrics
        try:
            logs_dir = Path(settings.LOGS_DIR)
            if logs_dir.exists():
                log_files = list(logs_dir.glob("*.log"))
                total_size = sum(f.stat().st_size for f in log_files if f.exists())
                
                metrics["filesystem"] = {
                    "logs_directory": str(logs_dir),
                    "log_files_count": len(log_files),
                    "total_logs_size_mb": round(total_size / (1024*1024), 2),
                    "logs_dir_writable": logs_dir.is_dir() and __import__('os').access(logs_dir, __import__('os').W_OK)
                }
        except Exception as e:
            metrics["filesystem"] = {"error": str(e)}
        
        # Configuration metrics
        metrics["configuration"] = {
            "log_level": settings.LOG_LEVEL,
            "log_format": settings.LOG_FORMAT,
            "knowledge_base_path": settings.KNOWLEDGE_BASE_PATH,
            "chroma_db_path": settings.CHROMA_DB_PATH,
            "redis_url_configured": bool(settings.REDIS_URL),
            "cache_ttl_settings": {
                "short": settings.CACHE_TTL_SHORT,
                "medium": settings.CACHE_TTL_MEDIUM,
                "long": settings.CACHE_TTL_LONG
            }
        }
        
        # API keys status (masked)
        api_keys_status = settings.get_all_api_keys_status()
        configured_keys = sum(1 for status in api_keys_status.values() if status['configured'])
        total_keys = len(api_keys_status)
        
        metrics["api_keys"] = {
            "total_keys": total_keys,
            "configured_keys": configured_keys,
            "configuration_percentage": round((configured_keys / total_keys) * 100, 1) if total_keys > 0 else 0,
            "missing_critical": settings.validate_critical_keys()
        }
        
        # Performance settings
        metrics["performance"] = {
            "api_timeout": settings.API_TIMEOUT,
            "ai_timeout": settings.AI_TIMEOUT,
            "webhook_timeout": settings.WEBHOOK_TIMEOUT,
            "http_pool_size": settings.HTTP_POOL_SIZE,
            "http_max_retries": settings.HTTP_MAX_RETRIES
        }
        
        # Redis metrics (if available)
        try:
            from utils.redis_client import check_redis_health
            redis_health = await check_redis_health()
            if redis_health.get("healthy"):
                metrics["redis"] = {
                    "status": "healthy",
                    "version": redis_health.get("version"),
                    "used_memory": redis_health.get("used_memory"),
                    "connected_clients": redis_health.get("connected_clients"),
                    "keyspace_hits": redis_health.get("keyspace_hits"),
                    "keyspace_misses": redis_health.get("keyspace_misses")
                }
            else:
                metrics["redis"] = {"status": "unavailable", "error": redis_health.get("error")}
        except Exception as e:
            metrics["redis"] = {"status": "error", "error": str(e)}
        
        # ChromaDB metrics (if available)
        try:
            from utils.chroma_client import get_chroma_client
            chroma_client = await get_chroma_client()
            if chroma_client.is_connected():
                stats = await chroma_client.get_collection_stats()
                metrics["chromadb"] = {
                    "status": "healthy",
                    "collection_name": stats.get("collection_name"),
                    "document_count": stats.get("total_documents"),
                    "data_types": stats.get("data_types", {}),
                    "db_path": stats.get("db_path")
                }
            else:
                metrics["chromadb"] = {"status": "unavailable"}
        except Exception as e:
            metrics["chromadb"] = {"status": "error", "error": str(e)}
        
        # Cache metrics (if available)
        try:
            from utils.cache import cache_manager
            cache_stats = await cache_manager.get_stats()
            if not cache_stats.get("error"):
                metrics["cache"] = {
                    "status": "healthy",
                    "hit_rate": cache_stats.get("hit_rate", 0),
                    "redis_version": cache_stats.get("redis_version"),
                    "used_memory": cache_stats.get("used_memory")
                }
            else:
                metrics["cache"] = {"status": "error", "error": cache_stats.get("error")}
        except Exception as e:
            metrics["cache"] = {"status": "error", "error": str(e)}
        
        return metrics
        
    except Exception as e:
        logger.warning(f"Failed to get system metrics: {str(e)}")
        return {
            "error": str(e),
            "timestamp": time.time()
        }


async def get_startup_readiness() -> Dict[str, Any]:
    """Check if system is ready for startup"""
    try:
        # Quick health check focused on startup requirements
        basic_check = await check_basic_system()
        file_check = await check_file_system()
        logging_check = await check_logging_system()
        
        ready = all([
            basic_check.get("healthy", False),
            file_check.get("healthy", False),
            logging_check.get("healthy", False)
        ])
        
        readiness_report = {
            "ready": ready,
            "checks": {
                "basic_system": basic_check.get("healthy", False),
                "file_system": file_check.get("healthy", False),
                "logging_system": logging_check.get("healthy", False)
            },
            "message": "System ready for startup" if ready else "System not ready - check failed components",
            "timestamp": time.time()
        }
        
        if not ready:
            readiness_report["issues"] = []
            if not basic_check.get("healthy", False):
                readiness_report["issues"].append("Basic system check failed")
            if not file_check.get("healthy", False):
                readiness_report["issues"].append("File system check failed")
            if not logging_check.get("healthy", False):
                readiness_report["issues"].append("Logging system check failed")
        
        return readiness_report
        
    except Exception as e:
        logger.error(f"Startup readiness check failed: {str(e)}")
        return {
            "ready": False,
            "error": str(e),
            "message": "Startup readiness check failed",
            "timestamp": time.time()
        }