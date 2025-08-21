import hashlib
import hmac
import json
import time
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, Request
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class WebhookValidator:
    """WebHook signature validation and security"""
    
    @staticmethod
    def verify_helius_signature(
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """Verify Helius webhook signature"""
        if not secret:
            logger.warning("No webhook secret configured - skipping signature verification")
            return True
        
        try:
            # Helius uses HMAC-SHA256
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Remove 'sha256=' prefix if present
            if signature.startswith('sha256='):
                signature = signature[7:]
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Signature verification failed: {str(e)}")
            return False
    
    @staticmethod
    def validate_webhook_payload(payload: Dict[str, Any]) -> bool:
        """Basic webhook payload validation"""
        try:
            # Check required fields
            if not isinstance(payload, dict):
                return False
            
            # Check for basic Helius webhook structure
            required_fields = ['type']
            for field in required_fields:
                if field not in payload:
                    logger.warning(f"Missing required field: {field}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Payload validation failed: {str(e)}")
            return False


class WebhookProcessor:
    """Process different types of webhook events"""
    
    def __init__(self):
        self.validator = WebhookValidator()
    
    async def process_mint_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process new token mint events"""
        try:
            logger.info(f"Processing mint event: {payload.get('type', 'unknown')}")
            
            # Extract mint information
            mint_data = {
                "event_type": "new_mint",
                "mint_address": payload.get("mint"),
                "timestamp": payload.get("blockTime", int(time.time())),
                "slot": payload.get("slot"),
                "signature": payload.get("signature"),
                "raw_payload": payload
            }
            
            # Log the event
            logger.info(
                f"New token mint detected: {mint_data['mint_address']}",
                extra={
                    "webhook": True,
                    "event_type": "mint",
                    "mint_address": mint_data['mint_address'],
                    "signature": mint_data['signature']
                }
            )
            
            # Queue for background processing
            from app.utils.webhook_tasks import queue_webhook_task
            await queue_webhook_task("mint", payload)
            
            return {
                "status": "processed",
                "event": "mint",
                "data": mint_data
            }
            
        except Exception as e:
            logger.error(f"Error processing mint event: {str(e)}")
            return {
                "status": "error",
                "event": "mint",
                "error": str(e)
            }
            
            # Queue for background processing
            from app.utils.webhook_tasks import queue_webhook_task
            await queue_webhook_task("mint", payload)
            
            return {
                "status": "processed",
                "event": "mint",
                "data": mint_data
            }
            
        except Exception as e:
            logger.error(f"Error processing mint event: {str(e)}")
            return {
                "status": "error",
                "event": "mint",
                "error": str(e)
            }
    
    async def process_pool_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process new liquidity pool events"""
        try:
            logger.info(f"Processing pool event: {payload.get('type', 'unknown')}")
            
            # Extract pool information
            pool_data = {
                "event_type": "new_pool",
                "pool_address": payload.get("pool"),
                "token_a": payload.get("tokenA"),
                "token_b": payload.get("tokenB"),
                "timestamp": payload.get("blockTime", int(time.time())),
                "slot": payload.get("slot"),
                "signature": payload.get("signature"),
                "raw_payload": payload
            }
            
            # Log the event
            logger.info(
                f"New liquidity pool detected: {pool_data['pool_address']}",
                extra={
                    "webhook": True,
                    "event_type": "pool",
                    "pool_address": pool_data['pool_address'],
                    "token_a": pool_data['token_a'],
                    "token_b": pool_data['token_b']
                }
            )
            
            # Queue for background processing
            from app.utils.webhook_tasks import queue_webhook_task
            await queue_webhook_task("pool", payload)
            
            return {
                "status": "processed",
                "event": "pool",
                "data": pool_data
            }
            
        except Exception as e:
            logger.error(f"Error processing pool event: {str(e)}")
            return {
                "status": "error",
                "event": "pool",
                "error": str(e)
            }
    
    async def process_transaction_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process large transaction events"""
        try:
            logger.info(f"Processing transaction event: {payload.get('type', 'unknown')}")
            
            # Extract transaction information
            tx_data = {
                "event_type": "large_transaction",
                "signature": payload.get("signature"),
                "timestamp": payload.get("blockTime", int(time.time())),
                "slot": payload.get("slot"),
                "fee": payload.get("fee"),
                "accounts": payload.get("accountKeys", []),
                "amount": payload.get("amount"),
                "token": payload.get("mint"),
                "raw_payload": payload
            }
            
            # Log the event
            logger.info(
                f"Large transaction detected: {tx_data['signature']}",
                extra={
                    "webhook": True,
                    "event_type": "transaction",
                    "signature": tx_data['signature'],
                    "amount": tx_data['amount'],
                    "token": tx_data['token']
                }
            )
            
            # Queue for background processing
            from app.utils.webhook_tasks import queue_webhook_task
            await queue_webhook_task("transaction", payload)
            
            return {
                "status": "processed",
                "event": "transaction",
                "data": tx_data
            }
            
        except Exception as e:
            logger.error(f"Error processing transaction event: {str(e)}")
            return {
                "status": "error",
                "event": "transaction",
                "error": str(e)
            }


class WebhookManager:
    """Main webhook management class"""
    
    def __init__(self):
        self.processor = WebhookProcessor()
        self.validator = WebhookValidator()
    
    async def handle_webhook(
        self,
        request: Request,
        webhook_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle incoming webhook with validation and processing"""
        start_time = time.time()
        
        try:
            # Get raw body for signature verification
            body = await request.body()
            
            # Get signature from headers
            signature = request.headers.get('x-helius-signature') or request.headers.get('x-signature')
            
            # Verify signature if secret is configured
            if settings.HELIUS_WEBHOOK_SECRET:
                if not signature:
                    raise HTTPException(status_code=401, detail="Missing webhook signature")
                
                if not self.validator.verify_helius_signature(
                    body, 
                    signature, 
                    settings.HELIUS_WEBHOOK_SECRET
                ):
                    raise HTTPException(status_code=401, detail="Invalid webhook signature")
            
            # Validate payload structure
            if not self.validator.validate_webhook_payload(payload):
                raise HTTPException(status_code=400, detail="Invalid webhook payload")
            
            # Process based on webhook type
            if webhook_type == "mint":
                result = await self.processor.process_mint_event(payload)
            elif webhook_type == "pool":
                result = await self.processor.process_pool_event(payload)
            elif webhook_type == "tx":
                result = await self.processor.process_transaction_event(payload)
            else:
                raise HTTPException(status_code=400, detail=f"Unknown webhook type: {webhook_type}")
            
            processing_time = time.time() - start_time
            
            # Log webhook processing
            from app.core.logging import log_webhook_event
            log_webhook_event(
                webhook_type=f"helius_{webhook_type}",
                event_data=payload,
                processing_time=processing_time,
                success=result.get("status") == "processed"
            )
            
            return {
                "status": "success",
                "webhook_type": webhook_type,
                "processing_time": round(processing_time, 3),
                "result": result
            }
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            processing_time = time.time() - start_time
            
            logger.error(f"Webhook processing failed: {str(e)}")
            
            # Log failed webhook
            from app.core.logging import log_webhook_event
            log_webhook_event(
                webhook_type=f"helius_{webhook_type}",
                event_data=payload,
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )
            
            raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


# Global webhook manager instance
webhook_manager = WebhookManager()


# Convenience functions
async def process_helius_webhook(
    request: Request,
    webhook_type: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Process Helius webhook"""
    return await webhook_manager.handle_webhook(request, webhook_type, payload)


def create_webhook_urls(base_url: str) -> Dict[str, str]:
    """Generate webhook URLs for Helius configuration"""
    return {
        "mint_webhook": f"{base_url}/webhooks/helius/mint",
        "pool_webhook": f"{base_url}/webhooks/helius/pool", 
        "transaction_webhook": f"{base_url}/webhooks/helius/tx"
    }


async def get_webhook_stats() -> Dict[str, Any]:
    """Get webhook processing statistics"""
    # This would normally query a database or cache
    # For now, return basic info
    return {
        "webhooks_configured": bool(settings.HELIUS_WEBHOOK_SECRET),
        "webhook_secret_set": bool(settings.HELIUS_WEBHOOK_SECRET),
        "base_url": settings.WEBHOOK_BASE_URL,
        "supported_types": ["mint", "pool", "tx"],
        "security_enabled": bool(settings.HELIUS_WEBHOOK_SECRET)
    }