from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from loguru import logger
import json
import time

# Import the webhook utilities ONLY (remove duplicate processing)
from app.utils.webhooks import webhook_manager
from app.utils.webhook_tasks import queue_webhook_task

router = APIRouter(prefix="/webhooks", tags=["WebHooks"])


def extract_token_address(payload: Dict[str, Any]) -> str:
    """Extract token addresses from webhook payload"""
    
    if not payload or not payload.get("data"): 
        raise Exception("Payload is empty or has unexpected structure!")

    payload_data = payload["data"][0]

    if payload_data.get("accountData"):
        for data in payload_data["accountData"]:
            if data.get("mint"):
                return data["mint"]
            
    if payload_data.get("tokenTransfers") and len(payload_data.get("tokenTransfers")) > 0:
        if payload_data["tokenTransfers"][0].get("mint") and payload_data["tokenTransfers"][0].get("fromTokenAccount") == "":
            return payload_data["tokenTransfers"][0]["mint"]
        
    raise Exception("No mint address found!")


@router.post("/helius/mint", summary="Handle Helius mint webhook")
async def handle_mint_webhook(
    request: Request,
    webhook_secret: str = Header(None, alias="X-Webhook-Secret")
):
    """Handle mint webhook from Helius - SINGLE PROCESSING PATH ONLY"""
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
                logger.info("Mint: Received JSON object")
                
            elif isinstance(parsed_data, str):
                logger.info("Mint: Received JSON string, attempting double parse...")
                try:
                    payload = json.loads(parsed_data)
                    if isinstance(payload, dict):
                        logger.info("Mint: Double-parsed successfully")
                    else:
                        payload = {"type": "HELIUS_STRING_DATA", "data": parsed_data}
                except json.JSONDecodeError:
                    payload = {"type": "HELIUS_STRING_DATA", "data": parsed_data}
                    
            elif isinstance(parsed_data, list):
                payload = {"type": "HELIUS_ARRAY_DATA", "data": parsed_data}
            else:
                payload = {"type": "HELIUS_OTHER_DATA", "data": parsed_data}
        
        except json.JSONDecodeError as e:
            logger.error(f"Mint: JSON decode error: {str(e)}")
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
        try:
            token_address = extract_token_address(payload)
            tokens_detected = 1
        except Exception as e:
            logger.warning(f"Could not extract token address: {str(e)}")
            token_address = None
            tokens_detected = 0
        
        # SINGLE PROCESSING PATH: Queue for background processing ONLY
        # Remove the duplicate FastAPI background_tasks.add_task() call
        await queue_webhook_task("mint", payload, priority="high")
        
        if token_address:
            logger.info(f"Detected token in mint webhook: {token_address}")
            logger.info(f"Queued for deep AI-enhanced analysis via background workers")
        
        return JSONResponse({
            "status": "received",
            "message": "Queued for Security analysis",
            "tokens_detected": tokens_detected,
            "token": token_address[:16] + "..." if token_address else None,
            "analysis_type": "security_only",
            "processing_method": "background_queue",  # Indicate single processing path
            "analysis_triggered": tokens_detected > 0,
        })
        
    except Exception as e:
        logger.error(f"Mint webhook critical error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))