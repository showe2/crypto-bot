from typing import Dict, Any
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
import json
import time

# Import the webhook utilities
from app.utils.webhooks import webhook_manager
from app.utils.webhook_tasks import queue_webhook_task

router = APIRouter(prefix="/webhooks", tags=["WebHooks"])

@router.post("/helius/mint", summary="Helius New Token Mint WebHook")
async def helius_mint_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Ultra-fast webhook that handles both JSON objects and JSON strings from Helius
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
                logger.info("✅ Mint: Received JSON object (normal case)")
                
            elif isinstance(parsed_data, str):
                # Helius case: JSON string that needs to be parsed again
                logger.info("🔧 Mint: Received JSON string, attempting double parse...")
                try:
                    payload = json.loads(parsed_data)
                    if isinstance(payload, dict):
                        logger.info("✅ Mint: Double-parsed JSON string to object successfully")
                    else:
                        logger.warning(f"⚠️ Mint: Double-parsed result is not an object: {type(payload)}")
                        payload = {"type": "HELIUS_STRING_DATA", "data": parsed_data}
                except json.JSONDecodeError:
                    logger.info("🔧 Mint: String is not JSON, wrapping in object")
                    payload = {"type": "HELIUS_STRING_DATA", "data": parsed_data}
                    
            elif isinstance(parsed_data, list):
                logger.info("🔧 Mint: Received JSON array, wrapping in object")
                payload = {"type": "HELIUS_ARRAY_DATA", "data": parsed_data}
                
            else:
                logger.info(f"🔧 Mint: Received JSON {type(parsed_data)}, wrapping in object")
                payload = {"type": "HELIUS_OTHER_DATA", "data": parsed_data}
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ Mint: JSON decode error: {str(e)}")
            return JSONResponse({
                "status": "error",
                "message": f"Invalid JSON: {str(e)}",
                "raw_body_preview": raw_body.decode('utf-8', errors='replace')[:200]
            }, status_code=400)
        
        except UnicodeDecodeError as e:
            logger.error(f"❌ Mint: Unicode decode error: {str(e)}")
            return JSONResponse({
                "status": "error", 
                "message": f"Cannot decode request body: {str(e)}"
            }, status_code=400)
        
        # Validate payload is a dictionary
        if not isinstance(payload, dict):
            logger.error(f"❌ Mint: Final payload is not a dict: {type(payload)}")
            return JSONResponse({
                "status": "error",
                "message": f"Payload must be a JSON object, got {type(payload).__name__}",
            }, status_code=400)
        
        # Queue for background processing using the task queue
        await queue_webhook_task("mint", payload, priority="normal")
        
        response_time = (time.time() - start_time) * 1000
        
        logger.info(f"✅ Mint webhook processed successfully in {response_time:.1f}ms")
        logger.info(f"   Final payload keys: {list(payload.keys())}")
        
        return JSONResponse({
            "status": "received",
            "message": "Processing in background",
            "response_time_ms": round(response_time, 1),
            "payload_type": type(payload).__name__,
            "payload_keys": list(payload.keys())
        })
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Mint webhook critical error in {response_time:.1f}ms: {str(e)}")
        
        import traceback
        logger.error(f"❌ Mint traceback: {traceback.format_exc()}")
        
        return JSONResponse({
            "status": "error",
            "message": "Internal server error",
            "error_type": type(e).__name__,
            "response_time_ms": round(response_time, 1)
        }, status_code=200)  # Return 200 to prevent Helius retries

@router.post("/helius/pool", summary="Helius New Liquidity Pool WebHook")
async def helius_pool_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Ultra-fast pool webhook that handles both JSON objects and JSON strings from Helius
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
                logger.info("✅ Pool: Received JSON object (normal case)")
                
            elif isinstance(parsed_data, str):
                logger.info("🔧 Pool: Received JSON string, attempting double parse...")
                try:
                    payload = json.loads(parsed_data)
                    if isinstance(payload, dict):
                        logger.info("✅ Pool: Double-parsed JSON string to object successfully")
                    else:
                        logger.warning(f"⚠️ Pool: Double-parsed result is not an object: {type(payload)}")
                        payload = {"type": "HELIUS_POOL_STRING_DATA", "data": parsed_data}
                except json.JSONDecodeError:
                    logger.info("🔧 Pool: String is not JSON, wrapping in object")
                    payload = {"type": "HELIUS_POOL_STRING_DATA", "data": parsed_data}
                    
            elif isinstance(parsed_data, list):
                logger.info("🔧 Pool: Received JSON array, wrapping in object")
                payload = {"type": "HELIUS_POOL_ARRAY_DATA", "data": parsed_data}
                
            else:
                logger.info(f"🔧 Pool: Received JSON {type(parsed_data)}, wrapping in object")
                payload = {"type": "HELIUS_POOL_OTHER_DATA", "data": parsed_data}
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ Pool: JSON decode error: {str(e)}")
            return JSONResponse({
                "status": "error",
                "message": f"Invalid JSON: {str(e)}",
                "raw_body_preview": raw_body.decode('utf-8', errors='replace')[:200]
            }, status_code=400)
        
        except UnicodeDecodeError as e:
            logger.error(f"❌ Pool: Unicode decode error: {str(e)}")
            return JSONResponse({
                "status": "error", 
                "message": f"Cannot decode request body: {str(e)}"
            }, status_code=400)
        
        # Validate payload is a dictionary
        if not isinstance(payload, dict):
            logger.error(f"❌ Pool: Final payload is not a dict: {type(payload)}")
            return JSONResponse({
                "status": "error",
                "message": f"Payload must be a JSON object, got {type(payload).__name__}",
            }, status_code=400)
        
        # Queue for background processing using the task queue
        await queue_webhook_task("pool", payload, priority="normal")
        
        response_time = (time.time() - start_time) * 1000
        
        logger.info(f"✅ Pool webhook processed successfully in {response_time:.1f}ms")
        logger.info(f"   Final payload keys: {list(payload.keys())}")
        
        return JSONResponse({
            "status": "received",
            "message": "Processing in background",
            "response_time_ms": round(response_time, 1),
            "payload_type": type(payload).__name__,
            "payload_keys": list(payload.keys())
        })
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Pool webhook critical error in {response_time:.1f}ms: {str(e)}")
        
        import traceback
        logger.error(f"❌ Pool traceback: {traceback.format_exc()}")
        
        return JSONResponse({
            "status": "error",
            "message": "Internal server error",
            "error_type": type(e).__name__,
            "response_time_ms": round(response_time, 1)
        }, status_code=200)  # Return 200 to prevent Helius retries

@router.post("/helius/tx", summary="Helius Large Transaction WebHook")
async def helius_transaction_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Ultra-fast transaction webhook that handles both JSON objects and JSON strings from Helius
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
                logger.info("✅ TX: Received JSON object (normal case)")
                
            elif isinstance(parsed_data, str):
                logger.info("🔧 TX: Received JSON string, attempting double parse...")
                try:
                    payload = json.loads(parsed_data)
                    if isinstance(payload, dict):
                        logger.info("✅ TX: Double-parsed JSON string to object successfully")
                    else:
                        logger.warning(f"⚠️ TX: Double-parsed result is not an object: {type(payload)}")
                        payload = {"type": "HELIUS_TX_STRING_DATA", "data": parsed_data}
                except json.JSONDecodeError:
                    logger.info("🔧 TX: String is not JSON, wrapping in object")
                    payload = {"type": "HELIUS_TX_STRING_DATA", "data": parsed_data}
                    
            elif isinstance(parsed_data, list):
                logger.info("🔧 TX: Received JSON array, wrapping in object")
                payload = {"type": "HELIUS_TX_ARRAY_DATA", "data": parsed_data}
                
            else:
                logger.info(f"🔧 TX: Received JSON {type(parsed_data)}, wrapping in object")
                payload = {"type": "HELIUS_TX_OTHER_DATA", "data": parsed_data}
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ TX: JSON decode error: {str(e)}")
            return JSONResponse({
                "status": "error",
                "message": f"Invalid JSON: {str(e)}",
                "raw_body_preview": raw_body.decode('utf-8', errors='replace')[:200]
            }, status_code=400)
        
        except UnicodeDecodeError as e:
            logger.error(f"❌ TX: Unicode decode error: {str(e)}")
            return JSONResponse({
                "status": "error", 
                "message": f"Cannot decode request body: {str(e)}"
            }, status_code=400)
        
        # Validate payload is a dictionary
        if not isinstance(payload, dict):
            logger.error(f"❌ TX: Final payload is not a dict: {type(payload)}")
            return JSONResponse({
                "status": "error",
                "message": f"Payload must be a JSON object, got {type(payload).__name__}",
            }, status_code=400)
        
        # Queue for background processing using the task queue
        await queue_webhook_task("transaction", payload, priority="normal")
        
        response_time = (time.time() - start_time) * 1000
        
        logger.info(f"✅ TX webhook processed successfully in {response_time:.1f}ms")
        logger.info(f"   Final payload keys: {list(payload.keys())}")
        
        return JSONResponse({
            "status": "received",
            "message": "Processing in background",
            "response_time_ms": round(response_time, 1),
            "payload_type": type(payload).__name__,
            "payload_keys": list(payload.keys())
        })
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"❌ TX webhook critical error in {response_time:.1f}ms: {str(e)}")
        
        import traceback
        logger.error(f"❌ TX traceback: {traceback.format_exc()}")
        
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