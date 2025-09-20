import asyncio
import time
import json
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from app.services.trade.bot_service import bot_service

settings = get_settings()


class AutoTradeService:
    """Unified service for autotrade position management"""
    
    def __init__(self):
        self.positions_file = Path("shared_data/active_positions.json")
        self.positions_file.parent.mkdir(exist_ok=True)
        self.config = self._load_autotrade_config()
        
    def _load_autotrade_config(self) -> Dict[str, Any]:
        """Load autotrade configuration from master_config.json"""
        try:
            with open("app/services/trade/master_config.json", "r") as f:
                config = json.load(f)
            
            # Extract values from your existing config
            trading = config.get("trading", {})
            risk = config.get("risk", {})
            wallet = config.get("wallet", {})
            safety = config.get("safety", {})
            
            position_size = trading.get("entryPulse", {}).get("firstSol", 0.1)
            daily_limit = wallet.get("tradingDailyLimitSol", 5)
            
            autotrade_config = {
                "enabled": True,
                "position_size_sol": position_size,
                "max_positions": int(daily_limit / position_size) if position_size > 0 else 10,
                "stop_loss_percent": -20.0,  # Conservative default
                "take_profit_percent": trading.get("autoScalp", {}).get("targetProfitPercent", {}).get("default", 7),
                "trailing_stop_percent": trading.get("trailingStop", {}).get("percentRange", {}).get("chop", [8])[0],
                "liquidity_drain_threshold": safety.get("liquidityLimits", {}).get("slippageAbortPercent", 7) / 100,
                "max_hold_hours": 24
            }
            
            logger.info(f"📊 AutoTrade config loaded: {autotrade_config}")
            return autotrade_config
            
        except Exception as e:
            logger.error(f"Failed to load autotrade config: {e}")
            return {"enabled": False}
    
    # ==============================================
    # POSITION MANAGEMENT
    # ==============================================
    
    def track_position(self, token_address: str, buy_data: Dict[str, Any]) -> bool:
        """Track a new position after buy"""
        try:
            position = {
                "token_address": token_address,
                "entry_price": buy_data.get("entry_price", 0),
                "entry_time": time.time(),
                "amount_sol": buy_data.get("amount_sol", 0),
                "entry_market_cap": buy_data.get("market_cap", 0),
                "entry_liquidity": buy_data.get("liquidity", 0),
                "stop_loss_percent": self.config["stop_loss_percent"],
                "take_profit_percent": self.config["take_profit_percent"],
                "trailing_stop_percent": self.config["trailing_stop_percent"],
                "highest_price_seen": buy_data.get("entry_price", 0),
                "last_check_time": time.time(),
                "status": "active",
                "buy_order_id": buy_data.get("order_id"),
                "token_name": buy_data.get("token_name", "Unknown"),
                "source": buy_data.get("source", "manual")
            }
            
            positions = self._load_positions()
            positions[token_address] = position
            self._save_positions(positions)
            
            logger.info(f"📊 Position tracked: {position['token_name']} (${position['entry_price']:.6f})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to track position: {e}")
            return False
    
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Get all active positions"""
        try:
            positions = self._load_positions()
            return [pos for pos in positions.values() if pos.get("status") == "active"]
        except Exception as e:
            logger.error(f"Failed to get active positions: {e}")
            return []
    
    def close_position(self, token_address: str, sell_reason: str, sell_data: Dict[str, Any]) -> bool:
        """Close position by removing it from active positions"""
        try:
            positions = self._load_positions()
            if token_address in positions:
                position = positions[token_address]
                
                # Calculate P&L for logging
                entry_price = position["entry_price"]
                sell_price = sell_data.get("sell_price", 0)
                pnl_percent = (sell_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
                
                # Log the closure
                logger.info(f"📊 Position closed: {position['token_name']} - {sell_reason} (P&L: {pnl_percent:.2f}%)")
                
                # Remove from positions
                del positions[token_address]
                self._save_positions(positions)
                
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return False
    
    def _load_positions(self) -> Dict[str, Any]:
        """Load positions from JSON file"""
        try:
            if self.positions_file.exists():
                with open(self.positions_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")
            return {}
    
    def _save_positions(self, positions: Dict[str, Any]) -> bool:
        """Save positions to JSON file"""
        try:
            with open(self.positions_file, 'w') as f:
                json.dump(positions, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Failed to save positions: {e}")
            return False
    
    # ==============================================
    # SNAPSHOT-TRIGGERED POSITION CHECKING
    # ==============================================
    
    async def check_position_on_snapshot_update(self, token_address: str, fresh_market_data: Dict[str, Any]):
        """Check position when snapshot updates for this token"""
        try:
            if not self.config.get("enabled"):
                return
            
            # Get all positions and find this token
            positions = self._load_positions()
            if token_address not in positions or positions[token_address].get("status") != "active":
                return  # No active position for this token
            
            position = positions[token_address]
            
            # Check sell conditions
            should_sell, sell_reason = self._evaluate_sell_conditions(position, fresh_market_data)
            
            if should_sell:
                # Execute sell
                await self._execute_autosell(position, sell_reason, fresh_market_data)
            else:
                # Update highest price if needed
                current_price = fresh_market_data.get("currentPriceUSD", 0)
                if current_price > position["highest_price_seen"]:
                    positions[token_address]["highest_price_seen"] = current_price
                    positions[token_address]["last_check_time"] = time.time()
                    self._save_positions(positions)
                    
                    entry_price = position["entry_price"]
                    pnl = (current_price - entry_price) / entry_price * 100
                    logger.debug(f"📈 {position['token_name']}: ${current_price:.6f} (P&L: {pnl:.2f}%)")
                    
        except Exception as e:
            logger.error(f"Error checking position for {token_address}: {e}")
    
    def _evaluate_sell_conditions(self, position: Dict[str, Any], current_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Evaluate if position should be sold"""
        try:
            current_price = current_data.get("currentPriceUSD", 0)
            entry_price = position["entry_price"]
            
            if current_price <= 0 or entry_price <= 0:
                return False, None
            
            # Calculate P&L
            pnl_percent = (current_price - entry_price) / entry_price * 100
            
            # 1. STOP LOSS
            if pnl_percent <= position["stop_loss_percent"]:
                return True, "stop_loss"
            
            # 2. TAKE PROFIT
            if pnl_percent >= position["take_profit_percent"]:
                return True, "take_profit"
            
            # 3. TRAILING STOP
            highest_price = position["highest_price_seen"]
            trailing_stop_price = highest_price * (1 - position["trailing_stop_percent"] / 100)
            if (current_price <= trailing_stop_price and 
                highest_price > entry_price * 1.05):  # Only if 5%+ profit reached
                return True, "trailing_stop"
            
            # 4. LIQUIDITY DRAIN
            entry_liquidity = position.get("entry_liquidity", 0)
            current_liquidity = current_data.get("liquidityUSD", 0)
            if entry_liquidity > 0 and current_liquidity < entry_liquidity * self.config["liquidity_drain_threshold"]:
                return True, "liquidity_drain"
            
            # 5. MAX HOLD TIME
            hold_time_hours = (time.time() - position["entry_time"]) / 3600
            if hold_time_hours > self.config["max_hold_hours"]:
                return True, "max_hold_time"
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error evaluating sell conditions: {e}")
            return False, None
    
    async def _execute_autosell(self, position: Dict[str, Any], sell_reason: str, current_data: Dict[str, Any]):
        """Execute autosell via bot service"""
        try:
            token_address = position["token_address"]
            current_price = current_data.get("currentPriceUSD", 0)
            
            logger.info(f"🔴 AUTOSELL triggered: {position['token_name']} - {sell_reason} (${current_price:.6f})")
            
            # Execute sell via existing bot service
            sell_request = {
                "mint": token_address,
                "percent": 100  # Sell all
            }
            
            sell_result = await bot_service.handle_sell(sell_request)
            
            if sell_result.get("success"):
                sell_data = {
                    "sell_price": current_price,
                    "order_id": sell_result.get("orderId")
                }
                
                self.close_position(token_address, sell_reason, sell_data)
                logger.info(f"✅ AUTOSELL completed: {position['token_name']}")
            else:
                logger.error(f"❌ AUTOSELL failed: {position['token_name']} - {sell_result.get('message')}")
                
        except Exception as e:
            logger.error(f"Autosell execution error: {e}")
    
    def _update_position_tracking(self, position: Dict[str, Any], current_data: Dict[str, Any]):
        """Update position tracking data"""
        try:
            current_price = current_data.get("currentPriceUSD", 0)
            token_address = position["token_address"]
            
            # Update highest price for trailing stop
            if current_price > position["highest_price_seen"]:
                positions = self._load_positions()
                if token_address in positions:
                    positions[token_address]["highest_price_seen"] = current_price
                    positions[token_address]["last_check_time"] = time.time()
                    self._save_positions(positions)
                    
                    entry_price = position["entry_price"]
                    pnl = (current_price - entry_price) / entry_price * 100
                    logger.debug(f"📈 New high: {position['token_name']} ${current_price:.6f} (P&L: {pnl:.2f}%)")
                
        except Exception as e:
            logger.error(f"Error updating position tracking: {e}")
    
    # ==============================================
    # UTILITY METHODS
    # ==============================================
    
    def get_positions_summary(self) -> Dict[str, Any]:
        """Get summary of all positions"""
        try:
            positions = self._load_positions()
            active = [p for p in positions.values() if p.get("status") == "active"]
            closed = [p for p in positions.values() if p.get("status") == "closed"]
            
            total_pnl = sum(p.get("final_pnl_percent", 0) for p in closed)
            
            return {
                "total_positions": len(positions),
                "active_positions": len(active),
                "closed_positions": len(closed),
                "total_pnl_percent": round(total_pnl, 2),
                "config": self.config
            }
        except Exception as e:
            logger.error(f"Error getting positions summary: {e}")
            return {"total_positions": 0, "active_positions": 0, "closed_positions": 0}


# Global instance
autotrade_service = AutoTradeService()