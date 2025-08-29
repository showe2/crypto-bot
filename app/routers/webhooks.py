from typing import Dict, Any
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Header
from fastapi.responses import JSONResponse
from loguru import logger
import json
import time
import re

# Import the webhook utilities and enhanced token analyzer
from app.utils.webhooks import webhook_manager
from app.utils.webhook_tasks import queue_webhook_task
from app.services.ai.ai_token_analyzer import analyze_token_deep_comprehensive  # Updated import

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


async def process_webhook_analysis(token_address: str, event_type: str, payload: Dict[str, Any]):
    """Process AI-enhanced token analysis for webhook events in background"""
    try:
        logger.info(f"🤖 Starting DEEP analysis for webhook token: {token_address}")
        
        # Use deep analysis with AI enhancement for webhook events
        analysis_result = await analyze_token_deep_comprehensive(
            token_address, 
            f"webhook_{event_type}"
        )
        
        # Log enhanced results
        overall_analysis = analysis_result.get("overall_analysis", {})
        ai_analysis = analysis_result.get("ai_analysis", {})
        
        if ai_analysis:
            logger.info(
                f"✅ Webhook DEEP analysis completed for {token_address}: "
                f"Score: {overall_analysis.get('score', 'N/A')}, "
                f"Risk: {overall_analysis.get('risk_level', 'N/A')}, "
                f"AI Score: {ai_analysis.get('ai_score', 'N/A')}, "
                f"AI Recommendation: {ai_analysis.get('recommendation', 'N/A')}"
            )
        else:
            logger.info(
                f"✅ Webhook analysis completed for {token_address}: "
                f"Score: {overall_analysis.get('score', 'N/A')}, "
                f"Risk: {overall_analysis.get('risk_level', 'N/A')} "
                f"(AI analysis not available)"
            )
        
        # Store result in Redis for later retrieval
        from app.utils.redis_client import get_redis_client
        redis_client = await get_redis_client()
        
        cache_key = f"webhook_deep_analysis:{token_address}:{int(time.time())}"
        await redis_client.set(
            cache_key, 
            json.dumps(analysis_result, default=str), 
            ex=7200  # Store for 2 hours (longer for deep analysis)
        )
        
    except Exception as e:
        logger.error(f"❌ Webhook deep analysis failed for {token_address}: {str(e)}")


@router.post("/helius/mint", summary="Handle Helius mint webhook")
async def handle_mint_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    webhook_secret: str = Header(None, alias="X-Webhook-Secret")
):
    """Handle mint webhook from Helius"""
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
        try:
            token_address = extract_token_address(payload)
            tokens_detected = 1
        except Exception as e:
            logger.warning(f"⚠️ Could not extract token address: {str(e)}")
            token_address = None
            tokens_detected = 0
        
        # Queue for background processing
        await queue_webhook_task("mint", payload, priority="high")  # High priority for mint events
        
        # Start DEEP analysis for detected tokens in background
        if token_address:
            logger.info(f"🎯 Detected token in mint webhook: {token_address}")
            logger.info(f"🤖 Triggering DEEP AI-enhanced analysis")
            
            background_tasks.add_task(
                process_webhook_analysis, 
                token_address, 
                "mint", 
                payload
            )
        
        return JSONResponse({
            "status": "received",
            "message": "Processing with AI-enhanced deep analysis",
            "tokens_detected": tokens_detected,
            "token": token_address[:16] + "..." if token_address else None,
            "analysis_type": "deep_ai_enhanced",
            "analysis_triggered": tokens_detected > 0,
            "ai_analysis": True
        })
        
    except Exception as e:
        logger.error(f"❌ Mint webhook critical error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))