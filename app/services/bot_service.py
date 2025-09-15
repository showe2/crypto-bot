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
    amount: float
    slippage: float = 0.5  
    stop_loss: float = -20.0
    take_profit: float = 50.0
    priority: str = "normal"
    priority_fee: float = 0.00001
    security: bool = False

class OnChainData(BaseModel):
    currentPriceUSD: float
    liquidityUSD: float
    solReserve: float
    tokenReserve: float
    poolExists: bool
    poolAddress: str
    dexType: str
    volume24h: float
    lpLocked: bool
    topHolderPercent: float
    tokenTax: float

class SellRequest(BaseModel):
    mint: str
    percent: int


class BotService:
    """Bot service for handling trading operations"""
    
    def __init__(self):
        self.bot_url = settings.BOT_URL
        
    async def handle_buy(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle buy request with optional security check and onchain data
        
        Args:
            request_data: Buy request data
            
        Returns:
            Success response or error details
        """
        try:
            # Validate request
            buy_request = BuyRequest(**request_data)
            token_address = buy_request.mint
            
            logger.info(f"🤖 Enhanced buy request for {token_address} - {buy_request.amount} SOL")
            
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
            
            # Collect onchain data
            logger.info(f"📊 Collecting onchain data for {token_address}")
            onchain_data = await self._collect_onchain_data(token_address)
            
            # Generate order ID
            order_id = f"order_{int(time.time())}_{token_address[:8]}"
            
            # Prepare enhanced bot request
            bot_request = {
                "mint": buy_request.mint,
                "amount": buy_request.amount,
                "slippage": buy_request.slippage,
                "stop_loss": buy_request.stop_loss,
                "take_profit": buy_request.take_profit,
                "priority": buy_request.priority,
                "priority_fee": buy_request.priority_fee,
                "onChain": onchain_data
            }
            
            # Fire and forget bot call
            asyncio.create_task(
                self._call_bot_api(bot_request, order_id)
            )
            
            # Return immediate success response
            logger.info(f"✅ Enhanced buy order placed: {order_id}")
            return {
                "success": True,
                "message": "Buy order placed successfully",
                "orderId": order_id,
                "mint": token_address,
                "amount": buy_request.amount,
                "onChain": onchain_data  # Include onchain data in response
            }
            
        except Exception as e:
            logger.error(f"❌ Enhanced buy request failed: {str(e)}")
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
        
    async def _collect_onchain_data(self, token_address: str) -> Dict[str, Any]:
        """Collect onchain data from existing services"""
        try:
            from app.services.service_manager import api_manager
            
            # Initialize default data
            onchain_data = {
                "currentPriceUSD": 0.0,
                "liquidityUSD": 0.0,
                "solReserve": 0.0,
                "tokenReserve": 0.0,
                "poolExists": False,
                "poolAddress": "",
                "dexType": "unknown",
                "volume24h": 0.0,
                "lpLocked": False,
                "topHolderPercent": 0.0,
                "tokenTax": 0.0
            }
            
            # Get Birdeye data (price + liquidity)
            if api_manager.clients.get("birdeye"):
                try:
                    birdeye_data = await api_manager.clients["birdeye"].get_token_price(
                        token_address, include_liquidity=True
                    )
                    if birdeye_data:
                        # Safe float conversion with None checks
                        price_value = birdeye_data.get("value")
                        if price_value is not None:
                            onchain_data["currentPriceUSD"] = float(price_value)
                        
                        liquidity_value = birdeye_data.get("liquidity")
                        if liquidity_value is not None:
                            onchain_data["liquidityUSD"] = float(liquidity_value)
                        
                        volume_value = birdeye_data.get("volume_24h")
                        if volume_value is not None:
                            onchain_data["volume24h"] = float(volume_value)
                except Exception as e:
                    logger.warning(f"Birdeye data collection failed: {e}")
            
            # Get DexScreener data (reserves, pool info)
            if api_manager.clients.get("dexscreener"):
                try:
                    dex_data = await api_manager.clients["dexscreener"].get_token_pairs(
                        token_address, "solana"
                    )
                    if dex_data and dex_data.get("pairs"):
                        pairs = dex_data["pairs"]
                        if len(pairs) > 0:
                            pair = pairs[0]  # Use first pair
                            onchain_data["poolExists"] = True
                            onchain_data["poolAddress"] = pair.get("pairAddress", "")
                            onchain_data["dexType"] = pair.get("dexId", "unknown")
                            
                            # Get reserves from liquidity
                            liquidity = pair.get("liquidity", {})
                            onchain_data["solReserve"] = float(liquidity.get("quote", 0))
                            onchain_data["tokenReserve"] = float(liquidity.get("base", 0))
                            
                            # Fallback price/volume if Birdeye failed
                            if onchain_data["currentPriceUSD"] == 0:
                                onchain_data["currentPriceUSD"] = float(pair.get("priceUsd", 0))
                            if onchain_data["volume24h"] == 0:
                                onchain_data["volume24h"] = float(pair.get("volume", {}).get("h24", 0))
                except Exception as e:
                    logger.warning(f"DexScreener data collection failed: {e}")
            
            # Get security data (LP locked, top holder, tax)
            if api_manager.clients.get("goplus"):
                try:
                    security_data = await api_manager.clients["goplus"].analyze_token_security(token_address)
                    if security_data:
                        # LP locked
                        lp_locked = security_data.get("lp_locked")
                        onchain_data["lpLocked"] = lp_locked == "1" if lp_locked else False
                        
                        # Top holder percent
                        holders = security_data.get("holders", [])
                        if holders and len(holders) > 0:
                            top_holder = holders[0]
                            onchain_data["topHolderPercent"] = float(top_holder.get("percent", 0))
                        
                        # Token tax
                        buy_tax = security_data.get("buy_tax", "0")
                        sell_tax = security_data.get("sell_tax", "0")
                        max_tax = max(float(buy_tax), float(sell_tax))
                        onchain_data["tokenTax"] = max_tax
                except Exception as e:
                    logger.warning(f"Security data collection failed: {e}")
            
            logger.info(f"Collected onchain data for {token_address}: pool={onchain_data['poolExists']}, price=${onchain_data['currentPriceUSD']}")
            return onchain_data
            
        except Exception as e:
            logger.error(f"Onchain data collection failed: {e}")
            return onchain_data  # Return defaults
    
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