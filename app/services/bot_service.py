import asyncio
import time
import httpx
from typing import Dict, Any, Optional
from loguru import logger
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()


class BuyRequest(BaseModel):
    mint: str
    amountSol: float
    slippage: float = 0.5
    priority: str = "normal"
    security: bool = False

class SellRequest(BaseModel):
    mint: str
    percent: int


class BotService:
    """Bot service for handling trading operations"""
    
    def __init__(self):
        self.bot_url = settings.BOT_URL
        
    async def handle_buy(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle buy request with optional security check
        
        Args:
            request_data: Buy request data
            
        Returns:
            Success response or error details
        """
        try:
            # Validate request
            buy_request = BuyRequest(**request_data)
            token_address = buy_request.mint
            
            logger.info(f"🤖 Bot buy request for {token_address} - {buy_request.amountSol} SOL")
            
            # Run security check if required
            if not buy_request.security:
                logger.info(f"🛡️ Running security check for {token_address}")
                
                security_passed = await self._run_security_check(token_address)
                if not security_passed:
                    logger.warning(f"❌ Security check failed for {token_address}")
                    return {
                        "success": False,
                        "error": "Security check failed",
                        "message": "Token failed security validation",
                        "mint": token_address
                    }
                
                logger.info(f"✅ Security check passed for {token_address}")
            else:
                logger.info(f"⚠️ Security check skipped for {token_address}")
            
            # Generate order ID
            order_id = f"order_{int(time.time())}_{token_address[:8]}"
            
            # Prepare bot request (remove security field)
            bot_request = {
                "mint": buy_request.mint,
                "amountSol": buy_request.amountSol,
                "slippage": buy_request.slippage,
                "priority": buy_request.priority
            }
            
            # Fire and forget bot call
            asyncio.create_task(
                self._call_bot_api(bot_request, order_id)
            )
            
            # Return immediate success response
            logger.info(f"✅ Buy order placed: {order_id}")
            return {
                "success": True,
                "message": "Buy order placed successfully",
                "orderId": order_id,
                "mint": token_address,
                "amountSol": buy_request.amountSol
            }
            
        except Exception as e:
            logger.error(f"❌ Bot buy request failed: {str(e)}")
            return {
                "success": False,
                "error": "Request processing failed",
                "message": str(e),
                "mint": request_data.get("mint", "unknown")
            }
        
    async def handle_sell(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle sell request
        
        Args:
            request_data: Sell request data
            
        Returns:
            Success response or error details
        """
        try:
            # Validate request
            sell_request = SellRequest(**request_data)
            token_address = sell_request.mint
            
            logger.info(f"🤖 Bot sell request for {token_address} - {sell_request.percent}%")
            
            # Validate percent range
            if not 1 <= sell_request.percent <= 100:
                return {
                    "success": False,
                    "error": "Invalid percent value",
                    "message": "Percent must be between 1 and 100",
                    "mint": token_address
                }
            
            # Generate order ID
            order_id = f"sell_{int(time.time())}_{token_address[:8]}"
            
            # Prepare bot request
            bot_request = {
                "mint": sell_request.mint,
                "percent": sell_request.percent
            }
            
            # Fire and forget bot call
            asyncio.create_task(
                self._call_bot_sell_api(bot_request, order_id)
            )
            
            # Return immediate success response
            logger.info(f"✅ Sell order placed: {order_id}")
            return {
                "success": True,
                "message": "Sell order placed successfully",
                "orderId": order_id,
                "mint": token_address,
                "percent": sell_request.percent
            }
            
        except Exception as e:
            logger.error(f"❌ Bot sell request failed: {str(e)}")
            return {
                "success": False,
                "error": "Request processing failed",
                "message": str(e),
                "mint": request_data.get("mint", "unknown")
            }
    
    async def _run_security_check(self, token_address: str) -> bool:
        """
        Run security check using existing token analyzer logic
        
        Args:
            token_address: Token mint address
            
        Returns:
            True if security check passed, False otherwise
        """
        try:
            from app.services.token_analyzer import token_analyzer
            
            # Create minimal analysis response structure
            analysis_response = {
                "warnings": [],
                "errors": [],
                "data_sources": [],
                "service_responses": {},
                "metadata": {
                    "services_attempted": 0,
                    "services_successful": 0
                }
            }
            
            # Run security checks using existing logic
            security_passed, security_data = await token_analyzer._run_security_checks(
                token_address, analysis_response
            )
            
            if security_passed:
                logger.info(f"Security check passed for {token_address}")
                return True
            else:
                critical_issues = security_data.get("critical_issues", [])
                logger.warning(f"Security check failed for {token_address}: {critical_issues}")
                return False
                
        except Exception as e:
            logger.error(f"Security check error for {token_address}: {str(e)}")
            return False
    
    async def _call_bot_api(self, bot_request: Dict[str, Any], order_id: str) -> None:
        """
        Make async call to bot API for buy orders (fire and forget)
        
        Args:
            bot_request: Request data for bot
            order_id: Order identifier for logging
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.bot_url}/api/buy",
                    json=bot_request,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Bot buy API call successful for order {order_id}")
                else:
                    logger.warning(f"⚠️ Bot buy API call failed for order {order_id}: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"❌ Bot buy API call error for order {order_id}: {str(e)}")
    
    async def _call_bot_sell_api(self, bot_request: Dict[str, Any], order_id: str) -> None:
            """
            Make async call to bot API for sell orders (fire and forget)
            
            Args:
                bot_request: Request data for bot
                order_id: Order identifier for logging
            """
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.bot_url}/api/sell",
                        json=bot_request,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Bot sell API call successful for order {order_id}")
                    else:
                        logger.warning(f"⚠️ Bot sell API call failed for order {order_id}: {response.status_code}")
                        
            except Exception as e:
                logger.error(f"❌ Bot sell API call error for order {order_id}: {str(e)}")


# Global bot service instance
bot_service = BotService()