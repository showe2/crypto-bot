import json
import time
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, Request
from loguru import logger

# Import settings with fallback
try:
    from app.core.config import get_settings
    settings = get_settings()
except ImportError:
    logger.error("Could not import settings - WEBHOOK_BASE_URL is required!")
    raise RuntimeError("Settings configuration is required for webhook system")


class WebhookValidator:
    """WebHook payload validation"""
    
    @staticmethod
    def validate_webhook_payload(payload: Dict[str, Any]) -> bool:
        """Basic webhook payload validation"""
        try:
            # Check if payload is a dictionary
            if not isinstance(payload, dict):
                logger.warning("Payload is not a dictionary")
                return False
            
            # Allow empty payloads for now - Helius might send various formats
            if not payload:
                logger.warning("Empty payload received")
                return True  # Allow empty payloads
            
            # Check for wrapped data types from our parsing
            if payload.get("type") in ["HELIUS_STRING_DATA", "HELIUS_ARRAY_DATA", "HELIUS_OTHER_DATA"]:
                logger.info(f"Webhook payload is wrapped type: {payload.get('type')}")
                return True
            
            # For normal payloads, just check if it's a dict - no strict validation
            logger.debug("Webhook payload validation passed")
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
            logger.info("Processing mint event")
            
            # Extract mint information with flexible handling
            mint_data = {
                "event_type": "new_mint",
                "mint_address": payload.get("mint"),
                "timestamp": payload.get("blockTime", int(time.time())),
                "slot": payload.get("slot"),
                "signature": payload.get("signature"),
                "wrapped_type": payload.get("type"),
                "raw_payload": payload
            }
            
            # Handle wrapped data types
            if payload.get("type") in ["HELIUS_STRING_DATA", "HELIUS_ARRAY_DATA"]:
                mint_data["original_data"] = payload.get("data")
            
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
            # Validate payload structure
            if not self.validator.validate_webhook_payload(payload):
                raise HTTPException(status_code=400, detail="Invalid webhook payload")
            
            # Process based on webhook type
            if webhook_type == "mint":
                result = await self.processor.process_mint_event(payload)
            else:
                raise HTTPException(status_code=400, detail=f"Unknown webhook type: {webhook_type}")
            
            processing_time = time.time() - start_time
            
            # Log webhook processing (with fallback if logging module not available)
            try:
                from app.core.logging import log_webhook_event
                log_webhook_event(
                    webhook_type=f"helius_{webhook_type}",
                    event_data=payload,
                    processing_time=processing_time,
                    success=result.get("status") == "processed"
                )
            except ImportError:
                logger.info(f"Webhook processed: {webhook_type} in {processing_time:.3f}s")
            
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
            
            # Log failed webhook (with fallback)
            try:
                from app.core.logging import log_webhook_event
                log_webhook_event(
                    webhook_type=f"helius_{webhook_type}",
                    event_data=payload,
                    processing_time=processing_time,
                    success=False,
                    error_message=str(e)
                )
            except ImportError:
                logger.error(f"Webhook failed: {webhook_type} - {str(e)}")
            
            raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


# Global webhook manager instance
webhook_manager = WebhookManager()


# Convenience functions for easy integration
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
        "mint_webhook": f"{base_url}/webhooks/helius/mint"
    }


async def get_webhook_stats() -> Dict[str, Any]:
    """Get webhook processing statistics"""
    try:
        base_url = settings.WEBHOOK_BASE_URL
        webhook_urls = settings.get_webhook_urls()
    except AttributeError:
        # Fallback for older config
        base_url = getattr(settings, 'WEBHOOK_BASE_URL', None)
        if not base_url:
            raise ValueError("WEBHOOK_BASE_URL is required but not configured")
        webhook_urls = create_webhook_urls(base_url)
    
    return {
        "base_url": base_url,
        "supported_types": ["mint"],
        "webhook_urls": webhook_urls
    }


# Additional utility functions
def get_webhook_health() -> Dict[str, Any]:
    """Get webhook system health status"""
    return {
        "status": "healthy",
        "components": {
            "validator": "operational",
            "processor": "operational", 
            "manager": "operational"
        },
        "timestamp": time.time()
    }


async def validate_webhook_config() -> Dict[str, Any]:
    """Validate webhook configuration"""
    issues = []
    warnings = []
    
    # Check if base URL is configured (now required)
    if not hasattr(settings, 'WEBHOOK_BASE_URL') or not settings.WEBHOOK_BASE_URL:
        issues.append("WEBHOOK_BASE_URL is required but not configured")
    elif not (settings.WEBHOOK_BASE_URL.startswith('http://') or settings.WEBHOOK_BASE_URL.startswith('https://')):
        issues.append("WEBHOOK_BASE_URL must start with http:// or https://")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "status": "valid" if len(issues) == 0 else "invalid"
    }