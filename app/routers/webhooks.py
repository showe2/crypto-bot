from typing import Dict, Any
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
import json
import time

router = APIRouter(prefix="/webhooks", tags=["WebHooks"])

# Simple in-memory queue for ultra-fast processing
webhook_queue = []

@router.post("/helius/mint", summary="Helius New Token Mint WebHook")
async def helius_mint_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Fixed webhook that handles both JSON objects and JSON strings from Helius
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
                logger.info("✅ Received JSON object (normal case)")
                
            elif isinstance(parsed_data, str):
                # Helius case: JSON string that needs to be parsed again
                logger.info("🔧 Received JSON string, attempting double parse...")
                try:
                    payload = json.loads(parsed_data)
                    if isinstance(payload, dict):
                        logger.info("✅ Double-parsed JSON string to object successfully")
                    else:
                        logger.warning(f"⚠️ Double-parsed result is not an object: {type(payload)}")
                        # Wrap the string in an object
                        payload = {"type": "HELIUS_STRING_DATA", "data": parsed_data}
                except json.JSONDecodeError:
                    # If second parse fails, treat the string as data
                    logger.info("🔧 String is not JSON, wrapping in object")
                    payload = {"type": "HELIUS_STRING_DATA", "data": parsed_data}
                    
            elif isinstance(parsed_data, list):
                # Array case: wrap in object
                logger.info("🔧 Received JSON array, wrapping in object")
                payload = {"type": "HELIUS_ARRAY_DATA", "data": parsed_data}
                
            else:
                # Other types: wrap in object
                logger.info(f"🔧 Received JSON {type(parsed_data)}, wrapping in object")
                payload = {"type": "HELIUS_OTHER_DATA", "data": parsed_data}
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {str(e)}")
            logger.error(f"❌ Raw body that failed: {raw_body}")
            return JSONResponse({
                "status": "error",
                "message": f"Invalid JSON: {str(e)}",
                "raw_body_preview": raw_body.decode('utf-8', errors='replace')[:200]
            }, status_code=400)
        
        except UnicodeDecodeError as e:
            logger.error(f"❌ Unicode decode error: {str(e)}")
            return JSONResponse({
                "status": "error", 
                "message": f"Cannot decode request body: {str(e)}"
            }, status_code=400)
        
        # Validate that we now have a dictionary
        if not isinstance(payload, dict):
            logger.error(f"❌ Final payload is not a dict: {type(payload)}")
            return JSONResponse({
                "status": "error",
                "message": f"Payload must be a JSON object, got {type(payload).__name__}",
                "payload_type": str(type(payload)),
                "payload_value": str(payload)[:200]
            }, status_code=400)
        
        # Success - queue for background processing
        webhook_queue.append({
            "type": "mint",
            "payload": payload,
            "timestamp": time.time(),
            "headers": dict(request.headers),
            "client_ip": request.client.host,
            "raw_body": raw_body.decode('utf-8', errors='replace'),
            "processed_payload": payload
        })
        
        response_time = (time.time() - start_time) * 1000
        
        logger.info(f"✅ Mint webhook processed successfully in {response_time:.1f}ms")
        logger.info(f"   Final payload keys: {list(payload.keys())}")
        
        # Background processing
        background_tasks.add_task(process_queued_webhooks)
        
        return JSONResponse({
            "status": "received",
            "message": "Processing in background",
            "response_time_ms": round(response_time, 1),
            "queue_position": len(webhook_queue),
            "payload_type": type(payload).__name__,
            "payload_keys": list(payload.keys())
        })
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Webhook critical error in {response_time:.1f}ms: {str(e)}")
        
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        
        return JSONResponse({
            "status": "error",
            "message": "Internal server error",
            "error_type": type(e).__name__,
            "response_time_ms": round(response_time, 1)
        }, status_code=200)  # Return 200 to prevent Helius retries

@router.post("/helius/pool", summary="Helius New Liquidity Pool WebHook")
async def helius_pool_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Fixed pool webhook that handles both JSON objects and JSON strings from Helius
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
                # Helius case: JSON string that needs to be parsed again
                logger.info("🔧 Pool: Received JSON string, attempting double parse...")
                try:
                    payload = json.loads(parsed_data)
                    if isinstance(payload, dict):
                        logger.info("✅ Pool: Double-parsed JSON string to object successfully")
                    else:
                        logger.warning(f"⚠️ Pool: Double-parsed result is not an object: {type(payload)}")
                        # Wrap the string in an object
                        payload = {"type": "HELIUS_POOL_STRING_DATA", "data": parsed_data}
                except json.JSONDecodeError:
                    # If second parse fails, treat the string as data
                    logger.info("🔧 Pool: String is not JSON, wrapping in object")
                    payload = {"type": "HELIUS_POOL_STRING_DATA", "data": parsed_data}
                    
            elif isinstance(parsed_data, list):
                # Array case: wrap in object
                logger.info("🔧 Pool: Received JSON array, wrapping in object")
                payload = {"type": "HELIUS_POOL_ARRAY_DATA", "data": parsed_data}
                
            else:
                # Other types: wrap in object
                logger.info(f"🔧 Pool: Received JSON {type(parsed_data)}, wrapping in object")
                payload = {"type": "HELIUS_POOL_OTHER_DATA", "data": parsed_data}
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ Pool: JSON decode error: {str(e)}")
            logger.error(f"❌ Pool: Raw body that failed: {raw_body}")
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
        
        # Validate that we now have a dictionary
        if not isinstance(payload, dict):
            logger.error(f"❌ Pool: Final payload is not a dict: {type(payload)}")
            return JSONResponse({
                "status": "error",
                "message": f"Payload must be a JSON object, got {type(payload).__name__}",
                "payload_type": str(type(payload)),
                "payload_value": str(payload)[:200]
            }, status_code=400)
        
        # Success - queue for background processing
        webhook_queue.append({
            "type": "pool",
            "payload": payload,
            "timestamp": time.time(),
            "headers": dict(request.headers),
            "client_ip": request.client.host,
            "raw_body": raw_body.decode('utf-8', errors='replace'),
            "processed_payload": payload
        })
        
        response_time = (time.time() - start_time) * 1000
        
        logger.info(f"✅ Pool webhook processed successfully in {response_time:.1f}ms")
        logger.info(f"   Final payload keys: {list(payload.keys())}")
        
        # Background processing
        background_tasks.add_task(process_queued_webhooks)
        
        return JSONResponse({
            "status": "received",
            "message": "Processing in background",
            "response_time_ms": round(response_time, 1),
            "queue_position": len(webhook_queue),
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
    Fixed transaction webhook that handles both JSON objects and JSON strings from Helius
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
                # Helius case: JSON string that needs to be parsed again
                logger.info("🔧 TX: Received JSON string, attempting double parse...")
                try:
                    payload = json.loads(parsed_data)
                    if isinstance(payload, dict):
                        logger.info("✅ TX: Double-parsed JSON string to object successfully")
                    else:
                        logger.warning(f"⚠️ TX: Double-parsed result is not an object: {type(payload)}")
                        # Wrap the string in an object
                        payload = {"type": "HELIUS_TX_STRING_DATA", "data": parsed_data}
                except json.JSONDecodeError:
                    # If second parse fails, treat the string as data
                    logger.info("🔧 TX: String is not JSON, wrapping in object")
                    payload = {"type": "HELIUS_TX_STRING_DATA", "data": parsed_data}
                    
            elif isinstance(parsed_data, list):
                # Array case: wrap in object
                logger.info("🔧 TX: Received JSON array, wrapping in object")
                payload = {"type": "HELIUS_TX_ARRAY_DATA", "data": parsed_data}
                
            else:
                # Other types: wrap in object
                logger.info(f"🔧 TX: Received JSON {type(parsed_data)}, wrapping in object")
                payload = {"type": "HELIUS_TX_OTHER_DATA", "data": parsed_data}
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ TX: JSON decode error: {str(e)}")
            logger.error(f"❌ TX: Raw body that failed: {raw_body}")
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
        
        # Validate that we now have a dictionary
        if not isinstance(payload, dict):
            logger.error(f"❌ TX: Final payload is not a dict: {type(payload)}")
            return JSONResponse({
                "status": "error",
                "message": f"Payload must be a JSON object, got {type(payload).__name__}",
                "payload_type": str(type(payload)),
                "payload_value": str(payload)[:200]
            }, status_code=400)
        
        # Success - queue for background processing
        webhook_queue.append({
            "type": "tx",
            "payload": payload,
            "timestamp": time.time(),
            "headers": dict(request.headers),
            "client_ip": request.client.host,
            "raw_body": raw_body.decode('utf-8', errors='replace'),
            "processed_payload": payload
        })
        
        response_time = (time.time() - start_time) * 1000
        
        logger.info(f"✅ TX webhook processed successfully in {response_time:.1f}ms")
        logger.info(f"   Final payload keys: {list(payload.keys())}")
        
        # Background processing
        background_tasks.add_task(process_queued_webhooks)
        
        return JSONResponse({
            "status": "received",
            "message": "Processing in background",
            "response_time_ms": round(response_time, 1),
            "queue_position": len(webhook_queue),
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

async def process_queued_webhooks():
    """
    Process queued webhooks in background
    This runs AFTER the response is sent to Helius
    """
    if not webhook_queue:
        return
    
    # Process up to 10 webhooks at once
    batch = webhook_queue[:10]
    del webhook_queue[:10]
    
    logger.info(f"🔄 Processing {len(batch)} queued webhooks")
    
    for webhook_data in batch:
        try:
            await process_single_webhook_background(webhook_data)
        except Exception as e:
            logger.error(f"Background processing error: {str(e)}")


async def process_single_webhook_background(webhook_data: Dict[str, Any]):
    """Process a single webhook in background with full validation"""
    webhook_type = webhook_data["type"]
    payload = webhook_data["payload"]
    signature = webhook_data.get("signature")
    
    try:
        # Now do the heavy lifting (signature verification, validation, etc.)
        from app.core.config import get_settings
        settings = get_settings()
        
        # Signature verification (if configured)
        if settings.HELIUS_WEBHOOK_SECRET and signature:
            # Reconstruct body for signature verification
            import json
            import hashlib
            import hmac
            
            body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
            expected_signature = hmac.new(
                settings.HELIUS_WEBHOOK_SECRET.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()
            
            if signature.startswith('sha256='):
                signature = signature[7:]
            
            if not hmac.compare_digest(expected_signature, signature):
                logger.warning(f"Invalid signature for {webhook_type} webhook")
                return
        
        # Process the webhook with your existing logic
        if webhook_type == "mint":
            await process_mint_background(payload)
        elif webhook_type == "pool":
            await process_pool_background(payload)
        elif webhook_type == "tx":
            await process_transaction_background(payload)
            
        logger.info(f"✅ Background processing completed for {webhook_type}")
        
    except Exception as e:
        logger.error(f"❌ Background processing failed for {webhook_type}: {str(e)}")


async def process_mint_background(payload: Dict[str, Any]):
    """Background mint processing"""
    mint_address = payload.get("mint")
    logger.info(f"Processing mint in background: {mint_address}")
    
    # Your existing mint processing logic here
    # This can be slow since it runs after response
    pass


async def process_pool_background(payload: Dict[str, Any]):
    """Background pool processing"""
    pool_address = payload.get("pool")
    logger.info(f"Processing pool in background: {pool_address}")
    
    # Your existing pool processing logic here
    pass


async def process_transaction_background(payload: Dict[str, Any]):
    """Background transaction processing"""
    signature = payload.get("signature")
    logger.info(f"Processing transaction in background: {signature}")
    
    # Your existing transaction processing logic here
    pass


@router.get("/status/fast", summary="Fast Webhook Status")
async def webhook_status_fast():
    """Get webhook status and queue info"""
    return {
        "webhook_system": "ultra-fast",
        "queue_size": len(webhook_queue),
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