import asyncio
import time
import httpx
import json
from typing import Dict, Any, Optional, List
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
    # Basic price data
    currentPriceUSD: float
    priceChange24h: Optional[float] = None
    
    # Liquidity metrics
    liquidityUSD: float
    
    # Market cap
    marketCapUSD: Optional[float] = None
    
    # Volume metrics  
    volume24h: float
    volume1h: Optional[float] = None
    volume5min: Optional[float] = None
    
    # Trading activity
    txCount24h: Optional[int] = None
    txCount1h: Optional[int] = None
    txCount5min: Optional[int] = None
    
    # Pool/DEX data
    poolExists: bool
    poolAddress: str
    dexType: str
    poolAge: Optional[int] = None  # seconds since pool creation
    
    # Reserves
    solReserve: float
    tokenReserve: float
    
    # Whale analysis
    whales1h: Dict[str, Any] = {
        "whaleCount": 0,
        "whaleVolume": 0.0,
        "whaleVolumePercent": 0.0,
        "largestWhaleAmount": 0.0,
        "avgWhaleSize": 0.0,
        "whaleRisk": "unknown"  # "low", "medium", "high", "unknown"
    }
    
    # Security metrics
    lpLocked: bool
    lpLockedPercent: Optional[float] = None
    topHolderPercent: float
    holderCount: Optional[int] = None
    tokenTax: float
    
    # Token metadata
    name: Optional[str] = None
    symbol: Optional[str] = None
    decimals: Optional[int] = None
    supply: Optional[float] = None
    
    # AI Analysis
    aiReasoning: Optional[str] = None
    
    # Data quality indicators
    lastUpdated: float = 0.0  # Unix timestamp
    apiErrors: List[str] = []

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
        """
        try:
            # Validate request
            buy_request = BuyRequest(**request_data)
            token_address = buy_request.mint
            
            logger.info(f"🤖 Bot buy request for {token_address} - {buy_request.amount} SOL")
            
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
            onchain_data = await self._collect_onchain_data(token_address, ai_reasoning="Ручная покупка", is_manual=True)
            
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
            
            bot_response = await self._call_bot_buy_api(bot_request, order_id)
            
            # Check if bot API call was successful
            if not bot_response or not bot_response.get("success"):
                error_msg = bot_response.get("message", "Bot API call failed") if bot_response else "Bot service unavailable"
                logger.error(f"❌ Bot API failed for {order_id}: {error_msg}")
                return {
                    "success": False,
                    "error": "Bot execution failed",
                    "message": error_msg,
                    "mint": token_address
                }
            
            # Return success response with bot confirmation
            logger.info(f"✅ Bot buy order completed: {order_id}")
            return {
                "success": True,
                "message": "Buy order executed successfully",
                "orderId": order_id,
                "mint": token_address,
                "amount": buy_request.amount,
                "bot_response": bot_response,
                "onChain": onchain_data
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
            
            # Collect onchain data for sell
            logger.info(f"📊 Collecting onchain data for sell: {token_address}")
            try:
                onchain_data = await self._collect_onchain_data(token_address, ai_reasoning="Ручная продажа", is_manual=True)
            except Exception as e:
                logger.warning(f"Failed to collect onchain data for sell: {e}")
                onchain_data = None
            
            # Prepare bot request
            bot_request = {
                "mint": sell_request.mint,
                "percent": sell_request.percent,
                "onChain": onchain_data
            }
            
            bot_response = await self._call_bot_sell_api(bot_request, order_id)
            
            # Check if bot API call was successful
            if not bot_response or not bot_response.get("success"):
                error_msg = bot_response.get("message", "Bot API call failed") if bot_response else "Bot service unavailable"
                logger.error(f"❌ Bot API failed for {order_id}: {error_msg}")
                return {
                    "success": False,
                    "error": "Bot execution failed", 
                    "message": error_msg,
                    "mint": token_address
                }
            
            # Return success response with bot confirmation
            logger.info(f"✅ Sell order completed: {order_id}")
            return {
                "success": True,
                "message": "Sell order executed successfully",
                "orderId": order_id,
                "mint": token_address,
                "percent": sell_request.percent,
                "bot_response": bot_response,
                "onChain": onchain_data
            }
            
        except Exception as e:
            logger.error(f"❌ Bot sell request failed: {str(e)}")
            return {
                "success": False,
                "error": "Request processing failed",
                "message": str(e),
                "mint": request_data.get("mint", "unknown")
            }
        
    async def update_wallet(self, private_key: str):
        """
        Update wallet secret
        
        Args:
            private_key: new private key
            
        Returns:
            Success response or error details
        """
        try:
            logger.info(f"🤖 Bot wallet secret update request")

            # Prepare bot request
            bot_request = {"privateKey": private_key}

            update_task = asyncio.create_task(
                self._call_bot_update_api(bot_request)
            )

            response_raw = await update_task
            response = response_raw.json()

            if not response.get("success"):
                logger.error(f"❌ Failed to update wallet secret: {response.get('error', 'Unknown Error')}")
                return {
                    "success": False,
                    "message": response.get("error", "Unknown Error"),

                }

            logger.info(f"✅ Wallet secret updated for Bot")
            return {
                "success": True,
                "message": "Wallet secret updated for Bot successfully",

            }
            
        except Exception as e:
            logger.error(f"❌ Failed to update wallet secret for Bot: {str(e)}")
            return {
                "success": False,
                "error": "Request processing failed",
            }
        
    async def get_history(self) -> List[Dict[str, Any]]:
        """Get trading history from bot service and transform to frontend format"""
        try:
            logger.info("📊 Fetching bot trading history")
            
            # Get history from bot API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.bot_url}/api/history")
                
                if response.status_code != 200:
                    logger.warning(f"Bot history API returned {response.status_code}")
                    return []
                
                bot_data = response.json()
                
                if not bot_data.get("success") or not bot_data.get("data"):
                    logger.warning("Bot history API returned no data")
                    return []
            
            # Transform to frontend format
            transformed_history = []
            for trade in bot_data["data"]:
                try:
                    onchain = trade.get("on_chain_data") or {}  # Handle None
                    whales1h = onchain.get("whales1h") or {}     # Handle None
                    
                    transformed_trade = {
                        "ts": self._parse_timestamp(trade.get("created_at")),
                        "name": onchain.get("name") or onchain.get("symbol") or "Unknown Token",
                        "mint": trade.get("token_mint", ""),
                        "liq": int(onchain.get("liquidityUSD") or 0),
                        "mcap": int(onchain.get("marketCapUSD") or 0),
                        "vol5": int(onchain.get("volume5min") or 0),
                        "vol60": int(onchain.get("volume1h") or 0),
                        "whales1h": int(whales1h.get("whaleVolume") or 0),
                        "verdict": onchain.get("aiReasoning") or "Нет данных"
                    }
                    
                    transformed_history.append(transformed_trade)
                    
                except Exception as e:
                    logger.warning(f"Failed to transform trade: {e}")
                    continue
            
            logger.info(f"✅ Transformed {len(transformed_history)} trading records")
            return transformed_history
            
        except httpx.TimeoutException:
            logger.error("Bot history API timeout")
            return []
        except Exception as e:
            logger.error(f"❌ Bot history fetch failed: {str(e)}")
            return []

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
        
    async def _collect_onchain_data(self, token_address: str, ai_reasoning: str = None, is_manual: bool = True) -> Dict[str, Any]:
        """
        Collect onchain data - try recent snapshot first, create new if needed
        """
        try:
            # Set AI reasoning based on manual/automated context
            if ai_reasoning is None:
                if is_manual:
                    ai_reasoning = "Ручная покупка"
                else:
                    ai_reasoning = self._generate_mock_ai_reasoning()
            
            # 1. Try to get recent snapshot (15 min max age)
            recent_snapshot = await self._get_recent_snapshot(token_address, max_age_minutes=15)
            
            if recent_snapshot:
                logger.info(f"Using recent snapshot for {token_address}")
                full_snapshot = await self._get_full_snapshot(token_address)
                if full_snapshot:
                    onchain_data = self._extract_onchain_data_from_snapshot(full_snapshot)
                    if onchain_data and onchain_data.get("currentPriceUSD", 0) > 0:
                        # Set AI reasoning and return
                        onchain_data["aiReasoning"] = ai_reasoning
                        return onchain_data
                    else:
                        logger.warning(f"Snapshot data invalid, creating new snapshot")
                else:
                    logger.warning(f"Recent snapshot metadata found but full data missing, creating new snapshot")
            else:
                logger.info(f"Creating new snapshot for {token_address}")
            
            # 2. Create new snapshot if no recent snapshot OR snapshot data is invalid
            from app.services.snapshots.token_snapshot import token_snapshot_service
            
            # Create new snapshot
            new_snapshot = await token_snapshot_service.capture_token_snapshot(
                token_address=token_address,
                security_status="safe",
                update_existing=True
            )
            
            # Extract onchain data from new snapshot
            onchain_data = self._extract_onchain_data_from_snapshot(new_snapshot)
            
            # Set AI reasoning
            onchain_data["aiReasoning"] = ai_reasoning
            
            return onchain_data
            
        except Exception as e:
            logger.error(f"OnChain data collection failed: {e}")
        return self._get_fallback_onchain_data(ai_reasoning or "Ошибка", str(e))
        
    async def _get_recent_snapshot(self, token_address: str, max_age_minutes: int = 15) -> Optional[Dict[str, Any]]:
        """Get recent snapshot if fresh enough"""
        try:
            from app.services.snapshots.token_snapshot import token_snapshot_service
            
            latest_snapshot = await token_snapshot_service._get_latest_snapshot(token_address)
            if not latest_snapshot:
                return None
            
            # Check age
            snapshot_time = latest_snapshot.get("timestamp", 0)
            if isinstance(snapshot_time, str):
                from datetime import datetime, timezone
                try:
                    # Parse ISO format as UTC
                    dt = datetime.fromisoformat(snapshot_time).replace(tzinfo=timezone.utc)
                    snapshot_time = dt.timestamp()
                except ValueError as e:
                    logger.warning(f"Failed to parse timestamp {snapshot_time}: {e}")
                    return None

            age_minutes = (time.time() - snapshot_time) / 60
            
            if age_minutes <= max_age_minutes:
                logger.info(f"Found recent snapshot (age: {age_minutes:.1f} min)")
                # Get full snapshot data, not just metadata
                return await self._get_full_snapshot(token_address)
            else:
                logger.info(f"Snapshot too old (age: {age_minutes:.1f} min)")
                return None
                
        except Exception as e:
            logger.warning(f"Error checking snapshot: {e}")
            return None

    async def _get_full_snapshot(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Get full snapshot data from storage by token_address"""
        try:
            from app.services.analysis_storage import analysis_storage
            
            results = await analysis_storage.search_analyses(
                query=f"snapshot {token_address}",
                limit=1,
                filters={"token_address": token_address, "doc_type": "token_snapshot"}
            )
            
            if results and len(results) > 0:
                # Parse the full snapshot from the stored JSON content
                content = results[0].get("content", "{}")
                
                # Handle different content types
                if isinstance(content, list) and len(content) > 0:
                    content = content[0]  # Take first item if it's a list
                
                if isinstance(content, str):
                    try:
                        onchain_data = json.loads(content)
                        return onchain_data
                    except json.JSONDecodeError as e:
                        logger.error(f"🔍 SNAPSHOT DEBUG: JSON decode failed: {e}")
                        return None
                elif isinstance(content, dict):
                    return content
                
                else:
                    return None
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting full snapshot: {e}")
            return None
        
    def _extract_onchain_data_from_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Extract OnChainData from snapshot"""
        try:
            if not snapshot:
                logger.warning("Snapshot is None")
                return self._get_fallback_onchain_data("unknown", "Snapshot is None")
            
            # Case 1: Direct market data (from stored JSON)
            if "currentPriceUSD" in snapshot:
                logger.info(f"Snapshot IS the market_data")
                return snapshot
            
            # Case 2: New snapshot structure (from capture_token_snapshot)
            elif "metrics" in snapshot and "market_data" in snapshot["metrics"]:
                market_data = snapshot["metrics"]["market_data"]
                logger.info(f"Found market_data in new snapshot structure")
                return market_data
            
            else:
                logger.warning("No market_data found in any structure")
                logger.info(f"Available keys: {list(snapshot.keys())}")
                return self._get_fallback_onchain_data("unknown", "No market_data in snapshot")
                
        except Exception as e:
            logger.error(f"Error extracting from snapshot: {e}")
            return self._get_fallback_onchain_data("unknown", str(e))

    def _generate_mock_ai_reasoning(self) -> str:
        """Generate mock AI reasoning for automated trades"""
        import random
        
        mock_reasons = [
            "Высокий объем торгов (+156% за 1ч), ликвидность стабильна $45K, киты активны но не агрессивны.",
            "Социальная активность растёт, технические индикаторы показывают восходящий тренд.",
            "Объём покупок превышает продажи 3:1, ликвидность заблокирована на 95%.",
            "Whale активность минимальна, устойчивый рост цены без резких скачков.",
            "Превышены пороги по объёму 5мин ($8.5K) и активности трейдеров."
        ]
        
        return random.choice(mock_reasons)
    
    def _parse_timestamp(self, timestamp_str: str) -> int:
        """Parse ISO timestamp to milliseconds"""
        try:
            if not timestamp_str:
                return int(time.time() * 1000)
            
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except:
            return int(time.time() * 1000)
    
    async def _call_bot_buy_api(self, bot_request: Dict[str, Any], order_id: str) -> Optional[Dict[str, Any]]:
        """
        Make async call to bot API for buy orders
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
                    return response.json()
                else:
                    logger.warning(f"⚠️ Bot buy API call failed for order {order_id}: {response.status_code}")
                    return {"success": False, "message": f"HTTP {response.status_code}"}
                    
        except Exception as e:
            logger.error(f"❌ Bot buy API call error for order {order_id}: {str(e)}")
            return {"success": False, "message": str(e)}

    async def _call_bot_sell_api(self, bot_request: Dict[str, Any], order_id: str) -> Optional[Dict[str, Any]]:
        """
        Make async call to bot API for sell orders
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
                    return response.json()
                else:
                    logger.warning(f"⚠️ Bot sell API call failed for order {order_id}: {response.status_code}")
                    return {"success": False, "message": f"HTTP {response.status_code}"}
                    
        except Exception as e:
            logger.error(f"❌ Bot sell API call error for order {order_id}: {str(e)}")
            return {"success": False, "message": str(e)}

    async def _call_bot_update_api(self, bot_request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Make async call to bot API for wallet secret update
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.bot_url}/api/wallet",
                    json=bot_request,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    logger.info(f"✅ Bot update API call successful")
                    return response.json()
                else:
                    logger.warning(f"⚠️ Bot update API call failed: {response.status_code}")
                    return {"success": False, "message": f"HTTP {response.status_code}"}
                    
        except Exception as e:
            logger.error(f"❌ Bot update API call error: {str(e)}")
            return {"success": False, "message": str(e)}


# Global bot service instance
bot_service = BotService()