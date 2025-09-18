import asyncio
import time
import httpx
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
        
        Args:
            request_data: Buy request data
            
        Returns:
            Success response or error details
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
            
            # Fire and forget bot call
            asyncio.create_task(
                self._call_bot_buy_api(bot_request, order_id)
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
                "percent": sell_request.percent,
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
        Collect comprehensive onchain data
        
        Args:
            token_address: Token mint address
            ai_reasoning: Custom AI reasoning (if None, generates based on is_manual)
            is_manual: Whether this is a manual trade (affects AI reasoning)
        """
        try:
            from app.services.service_manager import api_manager
            
            # Determine AI reasoning
            if ai_reasoning is None:
                if is_manual:
                    ai_reasoning = "Ручная покупка/продажа"
                else:
                    # Mock AI reasoning for automated trades
                    ai_reasoning = self._generate_mock_ai_reasoning()
            
            # Initialize comprehensive default data
            onchain_data = {
                # Basic price data
                "currentPriceUSD": 0.0,
                "priceChange24h": None,
                
                # Liquidity metrics
                "liquidityUSD": 0.0,
                
                # Market cap
                "marketCapUSD": None,
                
                # Volume metrics
                "volume24h": 0.0,
                "volume1h": 0.0,
                "volume5min": 0.0,
                
                # Trading activity
                "txCount24h": None,
                "txCount1h": None,
                "txCount5min": None,
                
                # Pool/DEX data
                "poolExists": False,
                "poolAddress": "",
                "dexType": "unknown",
                "poolAge": None,
                
                # Reserves
                "solReserve": 0.0,
                "tokenReserve": 0.0,
                
                # Whale analysis
                "whales1h": {
                    "whaleCount": 0,
                    "whaleVolume": 0.0,
                    "whaleVolumePercent": 0.0,
                    "largestWhaleAmount": 0.0,
                    "avgWhaleSize": 0.0,
                    "whaleRisk": "unknown"
                },
                
                # Security metrics
                "lpLocked": False,
                "lpLockedPercent": None,
                "topHolderPercent": 0.0,
                "holderCount": None,
                "tokenTax": 0.0,
                
                # Token metadata
                "name": None,
                "symbol": None,
                "decimals": None,
                "supply": None,
                
                # AI Analysis
                "aiReasoning": ai_reasoning,
                
                # Data quality
                "lastUpdated": time.time(),
                "apiErrors": []
            }
            
            # 1. BIRDEYE DATA (comprehensive price/volume/liquidity)
            if api_manager.clients.get("birdeye"):
                try:
                    # Price data
                    price_data = await api_manager.clients["birdeye"].get_token_price(
                        token_address, include_liquidity=True
                    )
                    if price_data:
                        # Safe float conversion with None checks
                        if price_data.get("value") is not None:
                            onchain_data["currentPriceUSD"] = float(price_data["value"])
                        
                        if price_data.get("liquidity") is not None:
                            onchain_data["liquidityUSD"] = float(price_data["liquidity"])
                        
                        if price_data.get("volume_24h") is not None:
                            onchain_data["volume24h"] = float(price_data["volume_24h"])
                        
                        # Additional Birdeye metrics if available
                        if price_data.get("price_change_24h") is not None:
                            onchain_data["priceChange24h"] = float(price_data["price_change_24h"])
                        
                        if price_data.get("market_cap") is not None:
                            onchain_data["marketCapUSD"] = float(price_data["market_cap"])

                        if price_data.get("name"):
                            onchain_data["name"] = price_data["name"]

                        if price_data.get("symbol"):
                            onchain_data["symbol"] = price_data["symbol"]
                    
                    # Wait between Birdeye calls
                    await asyncio.sleep(1.0)
                    
                    # Trades data for whale analysis
                    trades_data = await api_manager.clients["birdeye"].get_token_trades(
                        token_address, sort_type="desc", limit=100
                    )
                    if trades_data:
                        onchain_data["whales1h"] = self._analyze_whales_1h(trades_data)
                        
                        # Calculate volume metrics from trades
                        volume_metrics = self._calculate_volume_metrics(trades_data)
                        onchain_data.update(volume_metrics)
                        
                except Exception as e:
                    onchain_data["apiErrors"].append(f"Birdeye: {str(e)}")
                    logger.warning(f"Birdeye data collection failed: {e}")
            
            # 2. DEXSCREENER DATA (pool info, reserves, additional metrics)
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
                            
                            # Pool age
                            if pair.get("pairCreatedAt"):
                                try:
                                    created_at = int(pair["pairCreatedAt"]) / 1000  # Convert to seconds
                                    onchain_data["poolAge"] = int(time.time() - created_at)
                                except:
                                    pass
                            
                            # Get reserves from liquidity
                            liquidity = pair.get("liquidity", {})
                            if liquidity.get("quote") is not None:
                                onchain_data["solReserve"] = float(liquidity["quote"])
                            
                            if liquidity.get("base") is not None:
                                onchain_data["tokenReserve"] = float(liquidity["base"])
                            
                            # Fallback price/volume/mcap if Birdeye failed
                            if onchain_data["currentPriceUSD"] == 0 and pair.get("priceUsd"):
                                onchain_data["currentPriceUSD"] = float(pair["priceUsd"])
                            
                            if onchain_data["volume24h"] == 0:
                                volume_data = pair.get("volume", {})
                                if volume_data and volume_data.get("h24") is not None:
                                    onchain_data["volume24h"] = float(volume_data["h24"])
                                
                                if volume_data and volume_data.get("h1") is not None:
                                    onchain_data["volume1h"] = float(volume_data["h1"])

                            if onchain_data["marketCapUSD"] is None:
                                onchain_data["marketCapUSD"] = float(pair["marketCap"])
                            
                            # Transaction counts
                            if pair.get("txns"):
                                txns = pair["txns"]
                                if txns.get("h24") and txns["h24"].get("buys") is not None and txns["h24"].get("sells") is not None:
                                    onchain_data["txCount24h"] = int(txns["h24"]["buys"]) + int(txns["h24"]["sells"])
                                
                                if txns.get("h1") and txns["h1"].get("buys") is not None and txns["h1"].get("sells") is not None:
                                    onchain_data["txCount1h"] = int(txns["h1"]["buys"]) + int(txns["h1"]["sells"])
                                
                                if txns.get("m5") and txns["m5"].get("buys") is not None and txns["m5"].get("sells") is not None:
                                    onchain_data["txCount5min"] = int(txns["m5"]["buys"]) + int(txns["m5"]["sells"])

                            # Extract token info from DexScreener
                            if not onchain_data.get("name") and pair.get("baseToken", {}).get("name"):
                                onchain_data["name"] = pair["baseToken"]["name"]

                            if not onchain_data.get("symbol") and pair.get("baseToken", {}).get("symbol"):
                                onchain_data["symbol"] = pair["baseToken"]["symbol"]
                            
                except Exception as e:
                    onchain_data["apiErrors"].append(f"DexScreener: {str(e)}")
                    logger.warning(f"DexScreener data collection failed: {e}")
            
            # 3. GOPLUS SECURITY DATA
            if api_manager.clients.get("goplus"):
                try:
                    security_data = await api_manager.clients["goplus"].analyze_token_security(token_address)
                    if security_data:
                        # LP locked
                        lp_locked = security_data.get("lp_locked")
                        onchain_data["lpLocked"] = lp_locked == "1" if lp_locked else False
                        
                        # LP locked percentage
                        lp_locked_percent = security_data.get("lp_locked_percent")
                        if lp_locked_percent is not None:
                            onchain_data["lpLockedPercent"] = float(lp_locked_percent)
                        
                        # Top holder percent
                        holders = security_data.get("holders", [])
                        if holders and len(holders) > 0:
                            top_holder = holders[0]
                            holder_percent = top_holder.get("percent")
                            if holder_percent is not None:
                                onchain_data["topHolderPercent"] = float(holder_percent)
                        
                        # Holder count
                        holder_count = security_data.get("holder_count")
                        if holder_count is not None:
                            onchain_data["holderCount"] = int(holder_count.replace(",", "") if isinstance(holder_count, str) else holder_count)
                        
                        # Token tax
                        buy_tax = security_data.get("buy_tax", "0") or "0"
                        sell_tax = security_data.get("sell_tax", "0") or "0"
                        try:
                            max_tax = max(float(buy_tax), float(sell_tax))
                            onchain_data["tokenTax"] = max_tax
                        except (ValueError, TypeError):
                            onchain_data["tokenTax"] = 0.0
                        
                except Exception as e:
                    onchain_data["apiErrors"].append(f"GOplus: {str(e)}")
                    logger.warning(f"Security data collection failed: {e}")
            
            logger.info(f"Collected enhanced onchain data for {token_address}: pool={onchain_data['poolExists']}, price=${onchain_data['currentPriceUSD']}")
            return onchain_data
        
        except Exception as e:
            logger.error(f"Enhanced onchain data collection failed: {e}")
            onchain_data["apiErrors"].append(f"General: {str(e)}")
            return onchain_data  # Return defaults with error

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

    def _analyze_whales_1h(self, trades_data: Dict) -> Dict[str, Any]:
        """Analyze whale activity in last 1 hour"""
        try:
            if not trades_data or not trades_data.get("items"):
                return {
                    "whaleCount": 0,
                    "whaleVolume": 0.0,
                    "whaleVolumePercent": 0.0,
                    "largestWhaleAmount": 0.0,
                    "avgWhaleSize": 0.0,
                    "whaleRisk": "unknown"
                }
            
            trades = trades_data["items"]
            current_time = time.time()
            one_hour_ago = current_time - 3600
            
            whales = []
            total_volume = 0.0
            
            for trade in trades:
                try:
                    trade_time = trade.get("block_timestamp", current_time)
                    if trade_time < one_hour_ago:
                        continue
                    
                    # Get trade size in USD
                    trade_size_usd = float(trade.get("from", {}).get("ui_amount", 0)) * float(trade.get("from", {}).get("price", 0))
                    total_volume += trade_size_usd
                    
                    # Whale threshold: $800+ (matching pump analysis)
                    if trade_size_usd >= 800:
                        whales.append(trade_size_usd)
                        
                except (ValueError, TypeError, KeyError):
                    continue
            
            whale_count = len(whales)
            whale_volume = sum(whales)
            whale_volume_percent = (whale_volume / total_volume * 100) if total_volume > 0 else 0
            largest_whale = max(whales) if whales else 0
            avg_whale_size = (whale_volume / whale_count) if whale_count > 0 else 0
            
            # Risk assessment
            if whale_volume_percent > 60:
                whale_risk = "high"
            elif whale_volume_percent > 30:
                whale_risk = "medium"
            else:
                whale_risk = "low"
            
            return {
                "whaleCount": whale_count,
                "whaleVolume": round(whale_volume, 2),
                "whaleVolumePercent": round(whale_volume_percent, 1),
                "largestWhaleAmount": round(largest_whale, 2),
                "avgWhaleSize": round(avg_whale_size, 2),
                "whaleRisk": whale_risk
            }
            
        except Exception as e:
            logger.warning(f"Whale analysis failed: {e}")
            return {
                "whaleCount": 0,
                "whaleVolume": 0.0,
                "whaleVolumePercent": 0.0,
                "largestWhaleAmount": 0.0,
                "avgWhaleSize": 0.0,
                "whaleRisk": "unknown"
            }

    def _calculate_volume_metrics(self, trades_data: Dict) -> Dict[str, Any]:
        """Calculate volume metrics from trades data"""
        try:
            if not trades_data or not trades_data.get("items"):
                return {"volume1h": None, "volume5min": None}
            
            trades = trades_data["items"]
            current_time = time.time()
            
            volume_1h = 0.0
            volume_5min = 0.0
            
            for trade in trades:
                try:
                    trade_time = trade.get("block_timestamp", current_time)
                    time_diff = current_time - trade_time
                    
                    trade_size_usd = float(trade.get("from", {}).get("ui_amount", 0)) * float(trade.get("from", {}).get("price", 0))
                    
                    if time_diff <= 300:  # 5 minutes
                        volume_5min += trade_size_usd
                    if time_diff <= 3600:  # 1 hour
                        volume_1h += trade_size_usd
                        
                except (ValueError, TypeError, KeyError):
                    continue
            
            return {
                "volume1h": round(volume_1h, 2) if volume_1h > 0 else None,
                "volume5min": round(volume_5min, 2) if volume_5min > 0 else None,
            }
            
        except Exception as e:
            logger.warning(f"Volume metrics calculation failed: {e}")
            return {"volume1h": None, "volume5min": None}
    
    async def _call_bot_buy_api(self, bot_request: Dict[str, Any], order_id: str) -> None:
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

    async def _call_bot_update_api(self, bot_request: Dict[str, Any]) -> None:
        """
        Make async call to bot API for wallet secret update
        
        Args:
            bot_request: Request data for bot
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
                    return response
                else:
                    logger.warning(f"⚠️ Bot update API call failed: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"❌ Bot update API call error: {str(e)}")


# Global bot service instance
bot_service = BotService()