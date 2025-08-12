from typing import Annotated, Optional, Dict, Any
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from functools import lru_cache
import time
from datetime import datetime, timedelta
from loguru import logger

from app.core.config import get_settings

# Try to import utils from app directory
try:
    from app.utils.redis_client import get_redis_client, RedisClient, check_rate_limit
    from app.utils.chroma_client import get_chroma_client, ChromaClient  
    from app.utils.cache import cache_manager
    from app.utils.validation import ValidationMiddleware
    UTILS_AVAILABLE = True
    logger.debug("✅ Utils imported successfully from app.utils")
except ImportError as e:
    logger.warning(f"⚠️  App utils import failed: {str(e)} - using fallbacks")
    UTILS_AVAILABLE = False


# ==============================================
# CONFIGURATION DEPENDENCIES
# ==============================================

@lru_cache()
def get_settings_dependency():
    """Get application settings (cached)"""
    return get_settings()


# ==============================================
# STORAGE DEPENDENCIES
# ==============================================

async def get_redis_dependency() -> Optional[RedisClient]:
    """Get Redis client"""
    if not UTILS_AVAILABLE:
        logger.debug("Utils not available - Redis disabled")
        return None
        
    try:
        return await get_redis_client()
    except Exception as e:
        logger.debug(f"Redis connection failed: {str(e)}")
        return None


async def get_chroma_dependency() -> Optional[ChromaClient]:
    """Get ChromaDB client"""
    if not UTILS_AVAILABLE:
        logger.debug("Utils not available - ChromaDB disabled")
        return None
        
    try:
        return await get_chroma_client()
    except Exception as e:
        logger.debug(f"ChromaDB connection failed: {str(e)}")
        return None


async def get_cache_dependency():
    """Get cache manager"""
    if not UTILS_AVAILABLE:
        logger.debug("Utils not available - using simple cache")
        return SimpleFallbackCache()
        
    try:
        return cache_manager
    except Exception as e:
        logger.debug(f"Cache initialization failed: {str(e)}")
        return SimpleFallbackCache()


class SimpleFallbackCache:
    """Simple in-memory fallback cache when Redis is not available"""
    
    def __init__(self):
        self._cache = {}
        self._expiry = {}
    
    async def get(self, key: str, namespace: str = "default", default=None):
        full_key = f"{namespace}:{key}"
        
        # Check expiry
        if full_key in self._expiry and time.time() > self._expiry[full_key]:
            self._cache.pop(full_key, None)
            self._expiry.pop(full_key, None)
            
        return self._cache.get(full_key, default)
    
    async def set(self, key: str, value, ttl: int = None, namespace: str = "default"):
        full_key = f"{namespace}:{key}"
        self._cache[full_key] = value
        
        if ttl:
            self._expiry[full_key] = time.time() + ttl
        else:
            self._expiry.pop(full_key, None)
            
        return True
    
    async def delete(self, key: str, namespace: str = "default"):
        full_key = f"{namespace}:{key}"
        self._cache.pop(full_key, None)
        self._expiry.pop(full_key, None)
        return True


# ==============================================
# AUTHENTICATION DEPENDENCIES
# ==============================================

security = HTTPBearer(auto_error=False)


async def get_optional_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """Get optional authentication token"""
    if credentials:
        return credentials.credentials
    return None


async def get_required_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Get required authentication token"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return credentials.credentials


async def verify_api_key(
    token: str = Depends(get_required_token),
    settings = Depends(get_settings_dependency)
) -> Dict[str, Any]:
    """Verify API key authentication"""
    # This is a basic implementation - in production you'd want:
    # - Database lookup for API keys
    # - Rate limiting per key
    # - Key expiration
    # - Scoped permissions
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )
    
    # For development, accept any non-empty token
    if settings.ENV == "development" and token:
        return {
            "api_key": token,
            "user_id": "dev_user",
            "permissions": ["read", "write"],
            "rate_limit": 1000
        }
    
    # In production, implement proper key validation
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key"
    )


# ==============================================
# ENHANCED RATE LIMITING DEPENDENCIES
# ==============================================

class RateLimiter:
    """Enhanced rate limiter using Redis with sliding window"""
    
    def __init__(self, redis_client: Optional[RedisClient] = None):
        self.redis_client = redis_client
        self._memory_requests = {}  # Fallback for when Redis is unavailable
    
    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window_seconds: int = 60,
        namespace: str = "rate_limit"
    ) -> Dict[str, Any]:
        """Check if rate limit is exceeded using sliding window algorithm"""
        
        # Use Redis-based rate limiting if available
        if self.redis_client and UTILS_AVAILABLE:
            try:
                return await check_rate_limit(
                    identifier=identifier,
                    limit=limit,
                    window_seconds=window_seconds,
                    namespace=namespace
                )
            except Exception as e:
                logger.debug(f"Redis rate limiting failed: {str(e)}, falling back to memory")
        
        # Fallback to memory-based rate limiting
        return await self._memory_rate_limit(identifier, limit, window_seconds)
    
    async def _memory_rate_limit(
        self, 
        identifier: str, 
        limit: int, 
        window_seconds: int
    ) -> Dict[str, Any]:
        """Memory-based rate limiting fallback"""
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # Initialize or get request history
        if identifier not in self._memory_requests:
            self._memory_requests[identifier] = []
        
        request_times = self._memory_requests[identifier]
        
        # Remove old requests outside the window
        request_times[:] = [req_time for req_time in request_times if req_time > window_start]
        
        # Check if limit exceeded
        if len(request_times) >= limit:
            oldest_request = min(request_times) if request_times else current_time
            reset_time = oldest_request + window_seconds
            
            return {
                "allowed": False,
                "limit": limit,
                "remaining": 0,
                "reset_time": reset_time,
                "retry_after": max(0, int(reset_time - current_time)),
                "backend": "memory"
            }
        
        # Add current request
        request_times.append(current_time)
        
        return {
            "allowed": True,
            "limit": limit,
            "remaining": limit - len(request_times),
            "reset_time": current_time + window_seconds,
            "retry_after": 0,
            "backend": "memory"
        }


async def get_rate_limiter(
    redis_client: Optional[RedisClient] = Depends(get_redis_dependency)
) -> RateLimiter:
    """Get rate limiter instance"""
    return RateLimiter(redis_client)


async def rate_limit_per_ip(
    request: Request,
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    settings = Depends(get_settings_dependency)
) -> None:
    """Rate limit by IP address"""
    client_ip = request.client.host
    
    result = await rate_limiter.check_rate_limit(
        identifier=client_ip,
        limit=settings.RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        namespace="ip_rate_limit"
    )
    
    if not result["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "limit": result["limit"],
                "remaining": result["remaining"],
                "reset_time": result["reset_time"],
                "retry_after": result["retry_after"]
            },
            headers={
                "X-RateLimit-Limit": str(result["limit"]),
                "X-RateLimit-Remaining": str(result["remaining"]),
                "X-RateLimit-Reset": str(int(result["reset_time"])),
                "Retry-After": str(result["retry_after"])
            }
        )
    
    # Add rate limit headers to successful responses
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(result["limit"]),
        "X-RateLimit-Remaining": str(result["remaining"]),
        "X-RateLimit-Reset": str(int(result["reset_time"]))
    }


async def rate_limit_per_user(
    request: Request,
    token: Optional[str] = Depends(get_optional_token),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    settings = Depends(get_settings_dependency)
) -> None:
    """Rate limit by user/API key with different limits for authenticated vs anonymous"""
    
    if token:
        # Rate limit by token for authenticated users
        identifier = f"token:{token[:8]}"
        limit = settings.RATE_LIMIT_PER_HOUR
        window_seconds = 3600
        namespace = "user_rate_limit"
    else:
        # Rate limit by IP for unauthenticated requests
        identifier = f"ip:{request.client.host}"
        limit = settings.RATE_LIMIT_PER_MINUTE
        window_seconds = 60
        namespace = "anonymous_rate_limit"
    
    result = await rate_limiter.check_rate_limit(
        identifier=identifier,
        limit=limit,
        window_seconds=window_seconds,
        namespace=namespace
    )
    
    if not result["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "limit": result["limit"],
                "remaining": result["remaining"],
                "reset_time": result["reset_time"],
                "retry_after": result["retry_after"],
                "authenticated": bool(token)
            },
            headers={
                "X-RateLimit-Limit": str(result["limit"]),
                "X-RateLimit-Remaining": str(result["remaining"]),
                "X-RateLimit-Reset": str(int(result["reset_time"])),
                "Retry-After": str(result["retry_after"])
            }
        )
    
    # Add rate limit headers
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(result["limit"]),
        "X-RateLimit-Remaining": str(result["remaining"]),
        "X-RateLimit-Reset": str(int(result["reset_time"]))
    }


# ==============================================
# VALIDATION DEPENDENCIES
# ==============================================

async def get_validation_middleware() -> ValidationMiddleware:
    """Get validation middleware"""
    return ValidationMiddleware()


async def validate_token_mint(token_mint: str) -> str:
    """Validate token mint address"""
    from app.utils.validation import solana_validator
    
    result = solana_validator.validate_token_mint(token_mint)
    if not result.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "Invalid token mint address",
                "details": result.errors,
                "warnings": result.warnings
            }
        )
    
    return result.normalized_data["address"]


# ==============================================
# MONITORING DEPENDENCIES
# ==============================================

async def log_request_info(request: Request) -> Dict[str, Any]:
    """Log request information for monitoring"""
    request_info = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "timestamp": datetime.utcnow().isoformat(),
        "endpoint": request.url.path
    }
    
    # Log API request
    logger.info("API request received", extra={
        "api_request": True,
        **request_info
    })
    
    return request_info


# ==============================================
# HEALTH CHECK DEPENDENCIES
# ==============================================

async def check_system_dependencies() -> Dict[str, Any]:
    """Check all system dependencies health"""
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {}
    }
    
    # Check Redis
    try:
        redis_client = await get_redis_dependency()
        if redis_client:
            ping_result = await redis_client.ping()
            if ping_result:
                stats = await redis_client.get_stats()
                health_status["dependencies"]["redis"] = {
                    "healthy": True,
                    "backend": stats.get("backend", "unknown"),
                    "version": stats.get("redis_version"),
                    "connected_clients": stats.get("connected_clients")
                }
            else:
                health_status["dependencies"]["redis"] = {
                    "healthy": False, 
                    "error": "Ping failed"
                }
        else:
            health_status["dependencies"]["redis"] = {
                "healthy": False, 
                "error": "Not available"
            }
    except Exception as e:
        health_status["dependencies"]["redis"] = {
            "healthy": False, 
            "error": str(e)
        }
    
    # Check ChromaDB
    try:
        chroma_client = await get_chroma_dependency()
        if chroma_client and chroma_client.is_connected():
            health_status["dependencies"]["chromadb"] = {"healthy": True}
        else:
            health_status["dependencies"]["chromadb"] = {"healthy": False, "error": "Not connected"}
    except Exception as e:
        health_status["dependencies"]["chromadb"] = {"healthy": False, "error": str(e)}
    
    # Check cache
    try:
        cache = await get_cache_dependency()
        test_key = "health_check"
        await cache.set(test_key, "ok", 30)
        result = await cache.get(test_key)
        await cache.delete(test_key)
        
        health_status["dependencies"]["cache"] = {
            "healthy": result == "ok"
        }
    except Exception as e:
        health_status["dependencies"]["cache"] = {"healthy": False, "error": str(e)}
    
    # Overall health
    all_healthy = all(
        dep.get("healthy", False) 
        for dep in health_status["dependencies"].values()
    )
    health_status["overall_healthy"] = all_healthy
    
    return health_status


# ==============================================
# COMMON DEPENDENCY COMBINATIONS
# ==============================================

# Type annotations for commonly used dependencies
RedisClientDep = Annotated[Optional[RedisClient], Depends(get_redis_dependency)]
ChromaClientDep = Annotated[Optional[ChromaClient], Depends(get_chroma_dependency)]
CacheDep = Annotated[Any, Depends(get_cache_dependency)]
SettingsDep = Annotated[Any, Depends(get_settings_dependency)]
ValidationDep = Annotated[ValidationMiddleware, Depends(get_validation_middleware)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]

# Authentication combinations
OptionalAuthDep = Annotated[Optional[str], Depends(get_optional_token)]
RequiredAuthDep = Annotated[str, Depends(get_required_token)]
ApiKeyAuthDep = Annotated[Dict[str, Any], Depends(verify_api_key)]

# Rate limiting combinations
IPRateLimitDep = Annotated[None, Depends(rate_limit_per_ip)]
UserRateLimitDep = Annotated[None, Depends(rate_limit_per_user)]


# ==============================================
# STARTUP/SHUTDOWN DEPENDENCIES
# ==============================================

async def startup_dependencies():
    """Initialize all dependencies on startup"""
    logger.info("Initializing system dependencies...")
    
    try:
        # Initialize Redis
        try:
            redis_client = await get_redis_dependency()
            if redis_client:
                connected = await redis_client.is_connected()
                if connected:
                    stats = await redis_client.get_stats()
                    backend = stats.get("backend", "unknown")
                    if backend == "redis":
                        logger.info("✅ Redis connection established")
                    else:
                        logger.info("ℹ️  Redis using memory fallback")
                else:
                    logger.debug("ℹ️  Redis not connected (optional service)")
            else:
                logger.debug("ℹ️  Redis not available (optional service)")
        except Exception as e:
            logger.debug(f"ℹ️  Redis initialization skipped: {str(e)}")
        
        # Initialize ChromaDB
        try:
            chroma_client = await get_chroma_dependency()
            if chroma_client and chroma_client.is_connected():
                logger.info("✅ ChromaDB connection established")
            else:
                logger.debug("ℹ️  ChromaDB not available (optional service)")
        except Exception as e:
            logger.debug(f"ℹ️  ChromaDB initialization skipped: {str(e)}")
        
        # Test cache
        try:
            cache = await get_cache_dependency()
            await cache.set("startup_test", "ok", 30)
            result = await cache.get("startup_test")
            await cache.delete("startup_test")
            
            if result == "ok":
                logger.info("✅ Cache system working")
            else:
                logger.debug("ℹ️  Cache system issues (optional service)")
        except Exception as e:
            logger.debug(f"ℹ️  Cache initialization skipped: {str(e)}")
        
        logger.info("System dependencies initialization completed")
        
    except Exception as e:
        logger.error(f"❌ Dependency initialization failed: {str(e)}")
        raise


async def shutdown_dependencies():
    """Clean up dependencies on shutdown"""
    logger.info("Shutting down system dependencies...")
    
    try:
        # Close Redis
        from app.utils.redis_client import close_redis
        await close_redis()
        logger.info("✅ Redis connection closed")
        
        # Close ChromaDB
        from app.utils.chroma_client import close_chroma
        await close_chroma()
        logger.info("✅ ChromaDB connection closed")
        
        logger.info("System dependencies shutdown completed")
        
    except Exception as e:
        logger.error(f"❌ Dependency shutdown failed: {str(e)}")


# ==============================================
# UTILITY FUNCTIONS
# ==============================================

def create_dependency_override(test_dependencies: Dict[str, Any]):
    """Create dependency overrides for testing"""
    overrides = {}
    
    if "redis" in test_dependencies:
        overrides[get_redis_dependency] = lambda: test_dependencies["redis"]
    
    if "chroma" in test_dependencies:
        overrides[get_chroma_dependency] = lambda: test_dependencies["chroma"]
    
    if "cache" in test_dependencies:
        overrides[get_cache_dependency] = lambda: test_dependencies["cache"]
    
    return overrides