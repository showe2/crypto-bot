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


async def health_check_all_services() -> Dict[str, Any]:
    """Simplified health check for only required services"""
    logger.info("Starting core system health checks...")
    
    start_time = time.time()
    
    # Run only necessary checks
    try:
        results = await asyncio.gather(
            check_basic_system(),
            check_file_system(),
            check_logging_system(),
            return_exceptions=True
        )
    except Exception as e:
        logger.error(f"Service check error: {str(e)}")
        results = [
            {"healthy": False, "error": str(e)},
            {"healthy": False, "error": str(e)}, 
            {"healthy": False, "error": str(e)}
        ]
    
    # Unpack results
    basic_system = results[0] if not isinstance(results[0], Exception) else {"healthy": False, "error": str(results[0])}
    file_system = results[1] if not isinstance(results[1], Exception) else {"healthy": False, "error": str(results[1])}
    logging_system = results[2] if not isinstance(results[2], Exception) else {"healthy": False, "error": str(results[2])}
    
    # Aggregate results
    all_services = {
        "basic_system": basic_system,
        "file_system": file_system,
        "logging_system": logging_system
    }
    
    # Calculate overall status
    total_services = len(all_services)
    healthy_services = sum(1 for service in all_services.values() if service.get("healthy", False))
    
    # System is considered healthy if core components work
    critical_services_healthy = basic_system.get("healthy", False)
    overall_status = critical_services_healthy  # Depends only on critical services
    
    total_time = time.time() - start_time
    
    health_report = {
        "overall_status": overall_status,
        "summary": {
            "total_services": total_services,
            "healthy_services": healthy_services,
            "critical_services_ok": critical_services_healthy,
            "system_ready": overall_status
        },
        "services": all_services,
        "recommendations": [],
        "check_duration_seconds": round(total_time, 3),
        "timestamp": time.time()
    }
    
    # Problem resolution recommendations
    if not critical_services_healthy:
        health_report["recommendations"].append("Critical system components unavailable - check Python package installation")
    
    if not file_system.get("healthy", False):
        health_report["recommendations"].append("Filesystem issues - check directory permissions")
        
    if not logging_system.get("healthy", False):
        health_report["recommendations"].append("Logging system issues - check log settings")
    
    status_msg = "ready" if overall_status else "has issues"
    logger.info(f"Health check completed in {total_time:.2f}s: System {status_msg} ({healthy_services}/{total_services} components working)")
    
    return health_report


async def get_service_metrics() -> Dict[str, Any]:
    """Get system metrics"""
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
        
        # Configuration information
        metrics["configuration"] = {
            "log_level": settings.LOG_LEVEL,
            "log_format": settings.LOG_FORMAT,
            "knowledge_base_path": settings.KNOWLEDGE_BASE_PATH,
            "chroma_db_path": settings.CHROMA_DB_PATH
        }
        
        return metrics
        
    except Exception as e:
        logger.warning(f"Failed to get system metrics: {str(e)}")
        return {
            "error": str(e),
            "timestamp": time.time()
        }