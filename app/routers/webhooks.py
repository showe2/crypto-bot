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


def extract_token_addresses(payload: Dict[str, Any]) -> list[str]:
    """Extract potential token addresses from webhook payload"""
    addresses = []
    
    # Solana address pattern (base58, 32-44 characters)
    solana_address_pattern = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')
    
    def extract_from_value(value):
        if isinstance(value, str):
            # Find addresses in string
            matches = solana_address_pattern.findall(value)
            addresses.extend(matches)
        elif isinstance(value, dict):
            # Recursively search in dictionaries
            for v in value.values():
                extract_from_value(v)
        elif isinstance(value, list):
            # Search in lists
            for item in value:
                extract_from_value(item)
    
    # Extract from payload
    extract_from_value(payload)
    
    # Remove duplicates and common non-token addresses
    unique_addresses = list(set(addresses))
    
    # Filter out common system addresses
    system_addresses = {
        "11111111111111111111111111111111",  # System Program
        "So11111111111111111111111111111111111112",  # Wrapped SOL
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # Token Program
    }
    
    filtered_addresses = [addr for addr in unique_addresses if addr not in system_addresses]
    
    return filtered_addresses[:5]  # Limit to 5 addresses to avoid overload


async def process_webhook_analysis(token_addresses: list[str], event_type: str, payload: Dict[str, Any]):
    """Process token analysis for webhook events in background"""
    for token_address in token_addresses:
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
        token_addresses = extract_token_addresses(payload)
        
        # Queue for background processing
        await queue_webhook_task("mint", payload, priority="normal")
        
        # Start analysis for detected tokens in background
        if token_addresses:
            logger.info(f"🎯 Detected {len(token_addresses)} token addresses in mint webhook")
            background_tasks.add_task(
                process_webhook_analysis, 
                token_addresses, 
                "mint", 
                payload
            )
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse({
            "status": "received",
            "message": "Processing in background",
            "response_time_ms": round(response_time, 1),
            "tokens_detected": len(token_addresses),
            "tokens": token_addresses[:3] if token_addresses else [],  # Return first 3 for confirmation
            "analysis_triggered": len(token_addresses) > 0
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


@router.post("/helius/pool", summary="Helius New Liquidity Pool WebHook")
async def helius_pool_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Ultra-fast pool webhook with automatic token analysis
    """
    start_time = time.time()
    
    try:
        raw_body = await request.body()
        
        if not raw_body:
            return JSONResponse({
                "status": "error", 
                "message": "Empty request body"
            }, status_code=400)
        
        # Parse JSON (same logic as mint webhook)
        try:
            body_str = raw_body.decode('utf-8')
            parsed_data = json.loads(body_str)
            
            if isinstance(parsed_data, dict):
                payload = parsed_data
            elif isinstance(parsed_data, str):
                try:
                    payload = json.loads(parsed_data)
                    if not isinstance(payload, dict):
                        payload = {"type": "HELIUS_POOL_STRING_DATA", "data": parsed_data}
                except json.JSONDecodeError:
                    payload = {"type": "HELIUS_POOL_STRING_DATA", "data": parsed_data}
            else:
                payload = {"type": "HELIUS_POOL_OTHER_DATA", "data": parsed_data}
        
        except json.JSONDecodeError as e:
            return JSONResponse({
                "status": "error",
                "message": f"Invalid JSON: {str(e)}"
            }, status_code=400)
        
        if not isinstance(payload, dict):
            return JSONResponse({
                "status": "error",
                "message": "Payload must be a JSON object"
            }, status_code=400)
        
        # Extract token addresses
        token_addresses = extract_token_addresses(payload)
        
        # Queue for background processing
        await queue_webhook_task("pool", payload, priority="normal")
        
        # Start analysis for detected tokens
        if token_addresses:
            logger.info(f"🏊 Detected {len(token_addresses)} token addresses in pool webhook")
            background_tasks.add_task(
                process_webhook_analysis, 
                token_addresses, 
                "pool", 
                payload
            )
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse({
            "status": "received",
            "message": "Processing in background",
            "response_time_ms": round(response_time, 1),
            "tokens_detected": len(token_addresses),
            "tokens": token_addresses[:3] if token_addresses else [],
            "analysis_triggered": len(token_addresses) > 0
        })
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Pool webhook critical error: {str(e)}")
        
        return JSONResponse({
            "status": "error",
            "message": "Internal server error",
            "error_type": type(e).__name__,
            "response_time_ms": round(response_time, 1)
        }, status_code=200)


@router.post("/helius/tx", summary="Helius Large Transaction WebHook")
async def helius_transaction_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Ultra-fast transaction webhook with token analysis
    """
    start_time = time.time()
    
    try:
        raw_body = await request.body()
        
        if not raw_body:
            return JSONResponse({
                "status": "error", 
                "message": "Empty request body"
            }, status_code=400)
        
        # Parse JSON (same logic as other webhooks)
        try:
            body_str = raw_body.decode('utf-8')
            parsed_data = json.loads(body_str)
            
            if isinstance(parsed_data, dict):
                payload = parsed_data
            elif isinstance(parsed_data, str):
                try:
                    payload = json.loads(parsed_data)
                    if not isinstance(payload, dict):
                        payload = {"type": "HELIUS_TX_STRING_DATA", "data": parsed_data}
                except json.JSONDecodeError:
                    payload = {"type": "HELIUS_TX_STRING_DATA", "data": parsed_data}
            else:
                payload = {"type": "HELIUS_TX_OTHER_DATA", "data": parsed_data}
        
        except json.JSONDecodeError as e:
            return JSONResponse({
                "status": "error",
                "message": f"Invalid JSON: {str(e)}"
            }, status_code=400)
        
        if not isinstance(payload, dict):
            return JSONResponse({
                "status": "error",
                "message": "Payload must be a JSON object"
            }, status_code=400)
        
        # Extract token addresses
        token_addresses = extract_token_addresses(payload)
        
        # Queue for background processing
        await queue_webhook_task("transaction", payload, priority="normal")
        
        # Start analysis for detected tokens
        if token_addresses:
            logger.info(f"💸 Detected {len(token_addresses)} token addresses in transaction webhook")
            background_tasks.add_task(
                process_webhook_analysis, 
                token_addresses, 
                "transaction", 
                payload
            )
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse({
            "status": "received",
            "message": "Processing in background",
            "response_time_ms": round(response_time, 1),
            "tokens_detected": len(token_addresses),
            "tokens": token_addresses[:3] if token_addresses else [],
            "analysis_triggered": len(token_addresses) > 0
        })
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"❌ TX webhook critical error: {str(e)}")
        
        return JSONResponse({
            "status": "error",
            "message": "Internal server error",
            "error_type": type(e).__name__,
            "response_time_ms": round(response_time, 1)
        }, status_code=200)

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