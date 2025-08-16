import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class BirdeyeAPIError(Exception):
    """Birdeye API specific errors"""
    pass


class BirdeyeClient:
    """Birdeye API client for price data, volumes, and historical data"""
    
    def __init__(self):
        self.api_key = settings.BIRDEYE_API_KEY
        self.base_url = settings.BIRDEYE_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.15  # 150ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        if not self.api_key:
            logger.warning("Birdeye API key not configured")
    
    async def __aenter__(self):
        """Async context manager entry"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _ensure_session(self):
        """Ensure session is available"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)
        
        self._last_request_time = time.time()
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling and rate limiting"""
        if not self.api_key:
            raise BirdeyeAPIError("Birdeye API key not configured")
        
        await self._ensure_session()
        await self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
            **kwargs.pop("headers", {})
        }
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                response_data = await response.json()
                
                if response.status == 200:
                    return response_data
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 1))
                    logger.warning(f"Birdeye rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                elif response.status == 401:
                    raise BirdeyeAPIError("Invalid Birdeye API key")
                else:
                    error_msg = response_data.get('message', f'HTTP {response.status}')
                    raise BirdeyeAPIError(f"Birdeye API error: {error_msg}")
                    
        except asyncio.TimeoutError:
            raise BirdeyeAPIError("Birdeye API request timeout")
        except aiohttp.ClientError as e:
            raise BirdeyeAPIError(f"Birdeye client error: {str(e)}")
    
    async def get_token_price(self, token_address: str, include_liquidity: bool = True) -> Dict[str, Any]:
        """Get current token price and basic info"""
        try:
            endpoint = f"/defi/price"
            params = {
                "address": token_address,
                "include_liquidity": str(include_liquidity).lower()
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            price_info = {
                "address": token_address,
                "value": data.get("value"),  # Price in USD
                "updateUnixTime": data.get("updateUnixTime"),
                "updateHumanTime": data.get("updateHumanTime"),
                "priceChange24h": data.get("priceChange24h"),
                "priceChange24hPercent": data.get("priceChange24hPercent"),
                "liquidity": data.get("liquidity") if include_liquidity else None
            }
            
            return price_info
            
        except Exception as e:
            logger.error(f"Error getting token price from Birdeye for {token_address}: {str(e)}")
            return None
    
    async def get_token_metadata(self, token_address: str) -> Dict[str, Any]:
        """Get token metadata from Birdeye"""
        try:
            endpoint = f"/defi/token_overview"
            params = {"address": token_address}
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            metadata = {
                "address": token_address,
                "name": data.get("name"),
                "symbol": data.get("symbol"),
                "decimals": data.get("decimals"),
                "logoURI": data.get("logoURI"),
                "mc": data.get("mc"),  # Market cap
                "v24hUSD": data.get("v24hUSD"),  # 24h volume in USD
                "v24hChangePercent": data.get("v24hChangePercent"),
                "liquidity": data.get("liquidity"),
                "lastTradeUnixTime": data.get("lastTradeUnixTime"),
                "lastTradeHumanTime": data.get("lastTradeHumanTime"),
                "buy24h": data.get("buy24h"),
                "sell24h": data.get("sell24h"),
                "holder": data.get("holder"),
                "supply": data.get("supply"),
                "extensions": data.get("extensions", {})
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting token metadata from Birdeye for {token_address}: {str(e)}")
            return None
    
    async def get_price_history(self, token_address: str, address_type: str = "token", 
                               time_from: int = None, time_to: int = None, 
                               type_interval: str = "1h") -> List[Dict[str, Any]]:
        """Get historical price data"""
        try:
            endpoint = f"/defi/history_price"
            
            # Default to last 7 days if no time range specified
            if time_to is None:
                time_to = int(datetime.utcnow().timestamp())
            if time_from is None:
                time_from = int((datetime.utcnow() - timedelta(days=7)).timestamp())
            
            params = {
                "address": token_address,
                "address_type": address_type,
                "type": type_interval,  # 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d
                "time_from": time_from,
                "time_to": time_to
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data") or not response["data"].get("items"):
                return []
            
            history = []
            for item in response["data"]["items"]:
                price_point = {
                    "unixTime": item.get("unixTime"),
                    "value": item.get("value"),
                    "address": token_address,
                    "type": type_interval
                }
                history.append(price_point)
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting price history from Birdeye for {token_address}: {str(e)}")
            return []
    
    async def get_volume_history(self, token_address: str, address_type: str = "token",
                                time_from: int = None, time_to: int = None,
                                type_interval: str = "1h") -> List[Dict[str, Any]]:
        """Get historical volume data"""
        try:
            endpoint = f"/defi/ohlcv"
            
            # Default to last 7 days if no time range specified
            if time_to is None:
                time_to = int(datetime.utcnow().timestamp())
            if time_from is None:
                time_from = int((datetime.utcnow() - timedelta(days=7)).timestamp())
            
            params = {
                "address": token_address,
                "address_type": address_type,
                "type": type_interval,
                "time_from": time_from,
                "time_to": time_to
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data") or not response["data"].get("items"):
                return []
            
            volume_history = []
            for item in response["data"]["items"]:
                volume_point = {
                    "unixTime": item.get("unixTime"),
                    "open": item.get("o"),
                    "high": item.get("h"),
                    "low": item.get("l"),
                    "close": item.get("c"),
                    "volume": item.get("v"),
                    "address": token_address,
                    "type": type_interval
                }
                volume_history.append(volume_point)
            
            return volume_history
            
        except Exception as e:
            logger.error(f"Error getting volume history from Birdeye for {token_address}: {str(e)}")
            return []
    
    async def get_token_trades(self, token_address: str, limit: int = 100, 
                              offset: int = 0, tx_type: str = "all") -> List[Dict[str, Any]]:
        """Get recent trades for a token"""
        try:
            endpoint = f"/defi/txs/{token_address}"
            params = {
                "limit": min(limit, 100),  # API usually limits to 100
                "offset": offset,
                "tx_type": tx_type  # all, swap, add_liquidity, remove_liquidity
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data") or not response["data"].get("items"):
                return []
            
            trades = []
            for trade in response["data"]["items"]:
                trade_info = {
                    "txHash": trade.get("txHash"),
                    "blockUnixTime": trade.get("blockUnixTime"),
                    "txType": trade.get("txType"),
                    "source": trade.get("source"),
                    "from": trade.get("from"),
                    "to": trade.get("to"),
                    "changeAmount": trade.get("changeAmount"),
                    "balanceChange": trade.get("balanceChange"),
                    "side": trade.get("side"),  # buy or sell
                    "volumeInUSD": trade.get("volumeInUSD"),
                    "price": trade.get("price"),
                    "fee": trade.get("fee")
                }
                trades.append(trade_info)
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting token trades from Birdeye for {token_address}: {str(e)}")
            return []
    
    async def get_top_traders(self, token_address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get top traders for a token"""
        try:
            endpoint = f"/defi/top_traders/{token_address}"
            params = {"limit": min(limit, 100)}
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data") or not response["data"].get("items"):
                return []
            
            traders = []
            for trader in response["data"]["items"]:
                trader_info = {
                    "address": trader.get("address"),
                    "totalVolumeInUSD": trader.get("totalVolumeInUSD"),
                    "totalTxns": trader.get("totalTxns"),
                    "totalBuyInUSD": trader.get("totalBuyInUSD"),
                    "totalSellInUSD": trader.get("totalSellInUSD"),
                    "buyTxns": trader.get("buyTxns"),
                    "sellTxns": trader.get("sellTxns"),
                    "avgBuyPrice": trader.get("avgBuyPrice"),
                    "avgSellPrice": trader.get("avgSellPrice"),
                    "pnl": trader.get("pnl"),
                    "pnlPercent": trader.get("pnlPercent"),
                    "winRate": trader.get("winRate")
                }
                traders.append(trader_info)
            
            return traders
            
        except Exception as e:
            logger.warning(f"Error getting top traders from Birdeye for {token_address}: {str(e)}")
            return []
    
    async def get_token_security(self, token_address: str) -> Dict[str, Any]:
        """Get token security information"""
        try:
            endpoint = f"/defi/token_security"
            params = {"address": token_address}
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            security_info = {
                "address": token_address,
                "ownerBalance": data.get("ownerBalance"),
                "creatorBalance": data.get("creatorBalance"),
                "ownerPercentage": data.get("ownerPercentage"),
                "creatorPercentage": data.get("creatorPercentage"),
                "top10HolderBalance": data.get("top10HolderBalance"),
                "top10HolderPercent": data.get("top10HolderPercent"),
                "metaplexUpdate": data.get("metaplexUpdate"),
                "metaplexUpdateAuth": data.get("metaplexUpdateAuth"),
                "freezeable": data.get("freezeable"),
                "frozen": data.get("frozen"),
                "mintable": data.get("mintable"),
                "supply": data.get("supply"),
                "decimals": data.get("decimals"),
                "nonCirculatingSupply": data.get("nonCirculatingSupply"),
                "circulatingSupply": data.get("circulatingSupply")
            }
            
            return security_info
            
        except Exception as e:
            logger.warning(f"Error getting token security from Birdeye for {token_address}: {str(e)}")
            return None
    
    async def get_trending_tokens(self, sort_by: str = "v24hUSD", sort_type: str = "desc", 
                                 offset: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """Get trending tokens"""
        try:
            endpoint = "/defi/tokenlist"
            params = {
                "sort_by": sort_by,  # v24hUSD, mc, liquidity, etc.
                "sort_type": sort_type,  # asc, desc
                "offset": offset,
                "limit": min(limit, 50)
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data") or not response["data"].get("tokens"):
                return []
            
            trending = []
            for token in response["data"]["tokens"]:
                token_info = {
                    "address": token.get("address"),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "decimals": token.get("decimals"),
                    "logoURI": token.get("logoURI"),
                    "mc": token.get("mc"),
                    "v24hUSD": token.get("v24hUSD"),
                    "v24hChangePercent": token.get("v24hChangePercent"),
                    "priceChange24hPercent": token.get("priceChange24hPercent"),
                    "liquidity": token.get("liquidity"),
                    "price": token.get("price"),
                    "holder": token.get("holder"),
                    "supply": token.get("supply")
                }
                trending.append(token_info)
            
            return trending
            
        except Exception as e:
            logger.warning(f"Error getting trending tokens from Birdeye: {str(e)}")
            return []
    
    async def search_tokens(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search tokens by keyword"""
        try:
            endpoint = "/defi/search"
            params = {
                "keyword": keyword,
                "limit": min(limit, 50)
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data") or not response["data"].get("tokens"):
                return []
            
            tokens = []
            for token in response["data"]["tokens"]:
                token_info = {
                    "address": token.get("address"),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "decimals": token.get("decimals"),
                    "logoURI": token.get("logoURI"),
                    "mc": token.get("mc"),
                    "price": token.get("price"),
                    "v24hUSD": token.get("v24hUSD"),
                    "liquidity": token.get("liquidity")
                }
                tokens.append(token_info)
            
            return tokens
            
        except Exception as e:
            logger.warning(f"Token search failed on Birdeye for keyword '{keyword}': {str(e)}")
            return []
    
    async def get_multi_price(self, token_addresses: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get prices for multiple tokens at once"""
        try:
            endpoint = "/defi/multi_price"
            params = {
                "list_address": ",".join(token_addresses[:100])  # Limit to 100 addresses
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return {}
            
            prices = {}
            for address, price_data in response["data"].items():
                prices[address] = {
                    "value": price_data.get("value"),
                    "updateUnixTime": price_data.get("updateUnixTime"),
                    "updateHumanTime": price_data.get("updateHumanTime"),
                    "priceChange24h": price_data.get("priceChange24h"),
                    "priceChange24hPercent": price_data.get("priceChange24hPercent")
                }
            
            return prices
            
        except Exception as e:
            logger.error(f"Error getting multi-price from Birdeye: {str(e)}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Birdeye API health"""
        try:
            start_time = time.time()
            
            # Simple API test - get SOL price
            sol_address = "So11111111111111111111111111111111111112"
            price_data = await self.get_token_price(sol_address, include_liquidity=False)
            
            response_time = time.time() - start_time
            
            return {
                "healthy": price_data is not None,
                "api_key_configured": bool(self.api_key),
                "base_url": self.base_url,
                "response_time": response_time,
                "test_data": price_data
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": str(e),
                "base_url": self.base_url
            }


# Convenience functions
async def get_birdeye_client() -> BirdeyeClient:
    """Get configured Birdeye client"""
    return BirdeyeClient()


async def check_birdeye_health() -> Dict[str, Any]:
    """Check Birdeye service health"""
    async with BirdeyeClient() as client:
        return await client.health_check()