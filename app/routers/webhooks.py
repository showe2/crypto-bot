from typing import Dict, Any
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
import json
import time
import re

# Import the webhook utilities and token analyzer
from app.utils.webhooks import webhook_manager
from app.utils.webhook_tasks import queue_webhook_task
from app.services.token_analyzer import analyze_token_from_webhook

router = APIRouter(prefix="/webhooks", tags=["WebHooks"])


def extract_token_address(payload: Dict[str, Any]) -> str:
    """Extract token addresses from webhook payload"""
    
    if not payload or not payload.get("data"): raise Exception("Payload is empty or has unexpected structure!")

    payload_data = payload["data"][0]

    if payload_data.get("accountData"):
        for data in payload_data["accountData"]:
            if data.get("mint"):
                return data["mint"]
            
    if payload_data.get("tokenTransfers") and len(payload_data.get("tokenTransfers")) > 0:
        if payload_data["tokenTransfers"][0].get("mint") and payload_data["tokenTransfers"][0].get("fromTokenAccount") == "":
            return payload_data["tokenTransfers"][0]["mint"]
        
    raise Exception("No mint address found!")


async def process_webhook_analysis(token_address: str, event_type: str, payload: Dict[str, Any]):
    """Process token analysis for webhook events in background"""
    try:
        logger.info(f"🔍 Starting webhook analysis for token: {token_address}")
        
        # Perform comprehensive analysis
        analysis_result = await analyze_token_from_webhook(token_address, event_type)
        
        logger.info(
            f"✅ Webhook analysis completed for {token_address}: "
            f"Score: {analysis_result['overall_analysis']['score']}, "
            f"Risk: {analysis_result['overall_analysis']['risk_level']}"
        )
        
        # Store result in Redis for later retrieval
        from app.utils.redis_client import get_redis_client
        redis_client = await get_redis_client()
        
        cache_key = f"webhook_analysis:{token_address}:{int(time.time())}"
        await redis_client.set(
            cache_key, 
            json.dumps(analysis_result, default=str), 
            ex=3600  # Store for 1 hour
        )
        
    except Exception as e:
        logger.error(f"❌ Webhook analysis failed for {token_address}: {str(e)}")


@router.post("/helius/mint", summary="Helius New Token Mint WebHook")
async def helius_mint_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Ultra-fast webhook for new token mints with automatic analysis
    """
    start_time = time.time()
    
    try:
        # Read raw body first
        raw_body = await request.body()
        
        if not raw_body:
            return JSONResponse({
                "status": "error", 
                "message": "Empty request body"
            }, status_code=400)
        
        # Parse JSON with flexible handling
        try:
            body_str = raw_body.decode('utf-8')
            parsed_data = json.loads(body_str)
            
            # Handle different JSON types
            if isinstance(parsed_data, dict):
                payload = parsed_data
                logger.info("✅ Mint: Received JSON object")
                
            elif isinstance(parsed_data, str):
                logger.info("🔧 Mint: Received JSON string, attempting double parse...")
                try:
                    payload = json.loads(parsed_data)
                    if isinstance(payload, dict):
                        logger.info("✅ Mint: Double-parsed successfully")
                    else:
                        payload = {"type": "HELIUS_STRING_DATA", "data": parsed_data}
                except json.JSONDecodeError:
                    payload = {"type": "HELIUS_STRING_DATA", "data": parsed_data}
                    
            elif isinstance(parsed_data, list):
                payload = {"type": "HELIUS_ARRAY_DATA", "data": parsed_data}
            else:
                payload = {"type": "HELIUS_OTHER_DATA", "data": parsed_data}
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ Mint: JSON decode error: {str(e)}")
            return JSONResponse({
                "status": "error",
                "message": f"Invalid JSON: {str(e)}"
            }, status_code=400)
        
        # Validate payload is a dictionary
        if not isinstance(payload, dict):
            return JSONResponse({
                "status": "error",
                "message": f"Payload must be a JSON object"
            }, status_code=400)
        
        # Extract token addresses from payload
        token_address = extract_token_address(payload)
        
        # Queue for background processing
        await queue_webhook_task("mint", payload, priority="normal")
        
        # Start analysis for detected tokens in background
        if token_address:
            logger.info(f"🎯 Detected a token addresses in mint webhook")
            background_tasks.add_task(
                process_webhook_analysis, 
                token_address, 
                "mint", 
                payload
            )
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse({
            "status": "received",
            "message": "Processing in background",
            "response_time_ms": round(response_time, 1),
            "tokens_detected": len(token_address),
            "tokens": token_address[:3] if token_address else [],  # Return first 3 for confirmation
            "analysis_triggered": len(token_address) > 0
        })
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Mint webhook critical error: {str(e)}")
        
        return JSONResponse({
            "status": "error",
            "message": "Internal server error",
            "error_type": type(e).__name__,
            "response_time_ms": round(response_time, 1)
        }, status_code=200)  # Return 200 to prevent Helius retries

@router.get("/status/fast", summary="Fast Webhook Status")
async def webhook_status_fast():
    """Get webhook status and queue info"""
    from app.utils.webhook_tasks import get_webhook_queue_stats
    
    queue_stats = await get_webhook_queue_stats()
    
    return {
        "webhook_system": "ultra-fast",
        "queue": queue_stats,
        "endpoints": {
            "mint": "/webhooks/helius/mint",
            "pool": "/webhooks/helius/pool", 
            "tx": "/webhooks/helius/tx"
        },
        "performance": {
            "target_response_time": "< 100ms",
            "processing_model": "immediate_response_with_background_processing"
        }
    }

@router.get("/stats", summary="Webhook Statistics")
async def webhook_stats():
    """Get detailed webhook statistics"""
    from app.utils.webhook_tasks import get_webhook_queue_stats
    from app.utils.webhooks import get_webhook_stats
    
    queue_stats = await get_webhook_queue_stats()
    webhook_stats = await get_webhook_stats()
    
    return {
        "queue_stats": queue_stats,
        "webhook_config": webhook_stats,
        "system_status": "operational"
    }