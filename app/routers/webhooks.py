from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from loguru import logger

from app.utils.webhooks import process_helius_webhook, get_webhook_stats
from app.utils.webhook_tasks import get_webhook_queue_stats
from app.core.dependencies import get_settings_dependency

router = APIRouter(prefix="/webhooks", tags=["WebHooks"])

settings = get_settings_dependency()


@router.post("/helius/mint", summary="Helius New Token Mint WebHook")
async def helius_mint_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Helius webhook for new token mints
    
    This endpoint receives notifications when new tokens are minted on Solana.
    Configure this URL in your Helius dashboard: {base_url}/webhooks/helius/mint
    """
    try:
        # Parse JSON payload FAST
        payload = await request.json()

        print("Payload:", payload)
        
        logger.info(f"Received Helius mint webhook: {payload.get('type', 'unknown')}")
        
        # IMMEDIATE response to prevent timeout
        background_tasks.add_task(process_webhook_background, request, "mint", payload)
        
        return JSONResponse(
            content={"status": "received", "message": "Processing in background"},
            status_code=200
        )
        
    except ValueError as e:
        logger.error(f"Invalid JSON in mint webhook: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": "Invalid JSON"},
            status_code=400
        )
    except Exception as e:
        logger.error(f"Mint webhook error: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": "Internal error"},
            status_code=200  # Return 200 to prevent retries
        )


@router.post("/helius/pool", summary="Helius New Liquidity Pool WebHook")
async def helius_pool_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Helius webhook for new liquidity pools
    
    This endpoint receives notifications when new liquidity pools are created.
    Configure this URL in your Helius dashboard: {base_url}/webhooks/helius/pool
    """
    try:
        # Parse JSON payload FAST
        payload = await request.json()\
        
        print("Payload:", payload)
        
        logger.info(f"Received Helius pool webhook: {payload.get('type', 'unknown')}")
        
        # IMMEDIATE response to prevent timeout
        background_tasks.add_task(process_webhook_background, request, "pool", payload)
        
        return JSONResponse(
            content={"status": "received", "message": "Processing in background"},
            status_code=200
        )
        
    except ValueError as e:
        logger.error(f"Invalid JSON in pool webhook: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": "Invalid JSON"},
            status_code=400
        )
    except Exception as e:
        logger.error(f"Pool webhook error: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": "Internal error"},
            status_code=200  # Return 200 to prevent retries
        )


@router.post("/helius/tx", summary="Helius Large Transaction WebHook")
async def helius_transaction_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Helius webhook for large transactions
    
    This endpoint receives notifications for significant transactions.
    Configure this URL in your Helius dashboard: {base_url}/webhooks/helius/tx
    """
    try:
        # Parse JSON payload FAST
        payload = await request.json()

        print("Payload:", payload)
        
        logger.info(f"Received Helius transaction webhook: {payload.get('type', 'unknown')}")
        
        # IMMEDIATE response to prevent timeout
        background_tasks.add_task(process_webhook_background, request, "tx", payload)
        
        return JSONResponse(
            content={"status": "received", "message": "Processing in background"},
            status_code=200
        )
        
    except ValueError as e:
        logger.error(f"Invalid JSON in transaction webhook: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": "Invalid JSON"},
            status_code=400
        )
    except Exception as e:
        logger.error(f"Transaction webhook error: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": "Internal error"},
            status_code=200  # Return 200 to prevent retries
        )


async def process_webhook_background(request: Request, webhook_type: str, payload: dict):
    """Process webhook in background to prevent timeouts"""
    try:
        logger.info(f"Background processing {webhook_type} webhook")
        
        # Process the webhook (this was causing timeouts before)
        result = await process_helius_webhook(request, webhook_type, payload)
        
        logger.info(f"Background processing completed: {webhook_type} - {result.get('status')}")
        
    except Exception as e:
        logger.error(f"Background webhook processing failed: {webhook_type} - {str(e)}")


@router.get("/status", summary="WebHook Configuration Status")
async def webhook_status():
    """
    Get webhook configuration status and statistics
    """
    try:
        stats = await get_webhook_stats()
        
        return {
            "webhook_system": "operational",
            "configuration": stats,
            "endpoints": {
                "mint": "/webhooks/helius/mint",
                "pool": "/webhooks/helius/pool", 
                "transaction": "/webhooks/helius/tx"
            },
            "helius_configuration": {
                "webhook_secret_configured": stats.get("webhook_secret_set", False),
                "base_url_configured": bool(stats.get("base_url")),
                "security_enabled": stats.get("security_enabled", False)
            },
            "setup_instructions": {
                "step_1": "Set HELIUS_WEBHOOK_SECRET in .env file",
                "step_2": "Set WEBHOOK_BASE_URL to your domain",
                "step_3": "Configure webhook URLs in Helius dashboard",
                "mint_url": f"{stats.get('base_url', 'https://your-domain.com')}/webhooks/helius/mint",
                "pool_url": f"{stats.get('base_url', 'https://your-domain.com')}/webhooks/helius/pool",
                "tx_url": f"{stats.get('base_url', 'https://your-domain.com')}/webhooks/helius/tx"
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting webhook status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", summary="WebHook Health Check")
async def webhook_health():
    """
    Health check for webhook system
    """
    try:
        stats = await get_webhook_stats()
        queue_stats = await get_webhook_queue_stats()
        
        # Check if webhooks are properly configured
        is_healthy = all([
            stats.get("webhook_secret_set", False),
            stats.get("base_url") is not None
        ])
        
        health_data = {
            "healthy": is_healthy,
            "webhook_secret_configured": stats.get("webhook_secret_set", False),
            "base_url_configured": bool(stats.get("base_url")),
            "supported_webhook_types": stats.get("supported_types", []),
            "background_processing": {
                "enabled": queue_stats.get("running", False),
                "workers_count": queue_stats.get("workers_count", 0),
                "queue_size": queue_stats.get("queue_size", 0),
                "total_processed": queue_stats.get("total_processed", 0),
                "success_rate": queue_stats.get("success_rate", 0)
            },
            "security_features": {
                "signature_verification": stats.get("security_enabled", False),
                "payload_validation": True,
                "request_logging": True
            }
        }
        
        if not is_healthy:
            health_data["issues"] = []
            if not stats.get("webhook_secret_set"):
                health_data["issues"].append("HELIUS_WEBHOOK_SECRET not configured")
            if not stats.get("base_url"):
                health_data["issues"].append("WEBHOOK_BASE_URL not configured")
        
        return health_data
        
    except Exception as e:
        logger.error(f"WebHook health check failed: {str(e)}")
        return {
            "healthy": False,
            "error": str(e)
        }


@router.get("/queue/stats", summary="WebHook Queue Statistics")
async def webhook_queue_stats():
    """
    Get webhook background processing queue statistics
    """
    try:
        stats = await get_webhook_queue_stats()
        
        return {
            "queue_status": "running" if stats.get("running") else "stopped",
            "statistics": stats,
            "performance": {
                "success_rate_percent": round(stats.get("success_rate", 0), 2),
                "current_queue_size": stats.get("queue_size", 0),
                "workers_active": stats.get("workers_count", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting webhook queue stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))