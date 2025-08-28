import asyncio
import time
from typing import Dict, Any, List, Optional, Union
from loguru import logger

from app.services.api.helius_client import HeliusClient, check_helius_health
from app.services.api.birdeye_client import BirdeyeClient, check_birdeye_health
from app.services.api.solanafm_client import SolanaFMClient, check_solanafm_health
from app.services.api.goplus_client import GOplusClient, check_goplus_health
from app.services.api.dexscreener_client import DexScreenerClient, check_dexscreener_health
from app.services.api.rugcheck_client import RugCheckClient, check_rugcheck_health
from app.services.api.solsniffer_client import SolSnifferClient, check_solsniffer_health


class APIManager:
    """Unified API manager for all external services"""
    
    def __init__(self):
        self.clients = {
            "helius": None,
            "birdeye": None,
            "solanafm": None,
            "goplus": None,
            "dexscreener": None,
            "rugcheck": None,
            "solsniffer": None
        }
        self._health_cache = {}
        self._cache_duration = 300  # 5 minutes
    
    async def initialize_clients(self):
        """Initialize all API clients"""
        try:
            self.clients = {
                "helius": HeliusClient(),
                "birdeye": BirdeyeClient(),
                "solanafm": SolanaFMClient(),
                "goplus": GOplusClient(),
                "dexscreener": DexScreenerClient(),
                "rugcheck": RugCheckClient(),
                "solsniffer": SolSnifferClient()
            }
            logger.info("✅ All API clients initialized")
        except Exception as e:
            logger.error(f"❌ Error initializing API clients: {str(e)}")
            raise
    
    async def cleanup_clients(self):
        """Cleanup all API clients"""
        for name, client in self.clients.items():
            if client and hasattr(client, '__aexit__'):
                try:
                    await client.__aexit__(None, None, None)
                    logger.debug(f"✅ {name} client cleaned up")
                except Exception as e:
                    logger.warning(f"⚠️  Error cleaning up {name} client: {str(e)}")
    
    # async def check_all_services_health(self) -> Dict[str, Any]:
    #     """Check health of all API services"""
    #     current_time = time.time()
        
    #     # Check cache
    #     if self._health_cache and (current_time - self._health_cache.get('timestamp', 0)) < self._cache_duration:
    #         return self._health_cache['data']
        
    #     logger.info("🔍 Checking health of all API services...")
        
    #     # Health check functions
    #     health_checks = {
    #         "helius": check_helius_health(),
    #         "birdeye": check_birdeye_health(),
    #         "solanafm": check_solanafm_health(),
    #         "goplus": check_goplus_health(),
    #         "dexscreener": check_dexscreener_health(),
    #         "rugcheck": check_rugcheck_health(),
    #         "solsniffer": check_solsniffer_health()
    #     }
        
    #     # Run all health checks concurrently
    #     results = await asyncio.gather(*health_checks.values(), return_exceptions=True)
        
    #     # Compile results
    #     health_status = {}
    #     service_names = list(health_checks.keys())
        
    #     for i, service_name in enumerate(service_names):
    #         result = results[i]
    #         if isinstance(result, Exception):
    #             health_status[service_name] = {
    #                 "healthy": False,
    #                 "error": str(result),
    #                 "api_key_configured": False
    #             }
    #         else:
    #             health_status[service_name] = result
        
    #     # Calculate overall statistics
    #     total_services = len(health_status)
    #     healthy_services = sum(1 for status in health_status.values() if status.get("healthy", False))
    #     configured_services = sum(1 for status in health_status.values() if status.get("api_key_configured", False))
        
    #     overall_health = {
    #         "services": health_status,
    #         "summary": {
    #             "total_services": total_services,
    #             "healthy_services": healthy_services,
    #             "configured_services": configured_services,
    #             "health_percentage": round((healthy_services / total_services) * 100, 1),
    #             "configuration_percentage": round((configured_services / total_services) * 100, 1)
    #         },
    #         "overall_healthy": healthy_services >= (total_services * 0.6),  # 60% threshold
    #         "timestamp": current_time,
    #         "recommendations": []
    #     }
        
    #     # Add service-specific recommendations
    #     if configured_services < total_services:
    #         missing_keys = [name for name, status in health_status.items() 
    #                        if not status.get("api_key_configured", False) and name not in ["solanafm", "dexscreener"]]
    #         if missing_keys:
    #             overall_health["recommendations"].append(
    #                 f"Configure API keys for: {', '.join(missing_keys)}"
    #             )
        
    #     if healthy_services < total_services:
    #         unhealthy = [name for name, status in health_status.items() 
    #                     if not status.get("healthy", False)]
    #         overall_health["recommendations"].append(
    #             f"Check service status for: {', '.join(unhealthy)}"
    #         )
        
    #     # Free services recommendations
    #     free_services = ["solanafm", "dexscreener"]
    #     for service in free_services:
    #         if service in health_status:
    #             service_status = health_status[service]
    #             if not service_status.get("healthy"):
    #                 overall_health["recommendations"].append(
    #                     f"{service.upper()}: Free service - check network connectivity"
    #                 )
        
    #     # Cache results
    #     self._health_cache = {
    #         "data": overall_health,
    #         "timestamp": current_time
    #     }
        
    #     logger.info(f"📊 Health check completed: {healthy_services}/{total_services} services healthy")
    #     return overall_health

# Global API manager instance
api_manager = APIManager()


# Convenience functions
async def initialize_api_services():
    """Initialize all API services"""
    await api_manager.initialize_clients()


async def cleanup_api_services():
    """Cleanup all API services"""
    await api_manager.cleanup_clients()


async def get_api_health_status() -> Dict[str, Any]:
    """Get health status of all APIs"""
    return await api_manager.check_all_services_health()