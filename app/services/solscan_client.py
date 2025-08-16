import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class SolscanAPIError(Exception):
    """Solscan API specific errors"""
    pass


class SolscanClient:
    """Solscan API client for additional on-chain data and analytics"""
    
    def __init__(self):
        self.api_key = settings.SOLSCAN_API_KEY
        self.base_url = settings.SOLSCAN_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.2  # 200ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        if not self.api_key:
            logger.warning("Solscan API key not configured")
    
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
        await self._ensure_session()
        await self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            **kwargs.pop("headers", {})
        }
        
        # Add API key if available
        if self.api_key:
            headers["token"] = self.api_key
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                response_data = await response.json()
                
                if response.status == 200:
                    return response_data
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"Solscan rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                elif response.status == 401:
                    raise SolscanAPIError("Invalid Solscan API key")
                else:
                    error_msg = response_data.get('message', f'HTTP {response.status}')
                    raise SolscanAPIError(f"Solscan API error: {error_msg}")
                    
        except asyncio.TimeoutError:
            raise SolscanAPIError("Solscan API request timeout")
        except aiohttp.ClientError as e:
            raise SolscanAPIError(f"Solscan client error: {str(e)}")
    
    async def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive token information"""
        try:
            endpoint = f"/token/meta"
            params = {"tokenAddress": token_address}
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            token_info = {
                "address": token_address,
                "name": data.get("name"),
                "symbol": data.get("symbol"),
                "decimals": data.get("decimals"),
                "supply": data.get("supply"),
                "icon": data.get("icon"),
                "website": data.get("website"),
                "twitter": data.get("twitter"),
                "coingecko_id": data.get("coingecko_id"),
                "coinmarketcap_id": data.get("coinmarketcap_id"),
                "price": data.get("price"),
                "volume_24h": data.get("volume_24h"),
                "market_cap": data.get("market_cap"),
                "price_change_24h": data.get("price_change_24h"),
                "holder_count": data.get("holder_count"),
                "created_time": data.get("created_time"),
                "updated_time": data.get("updated_time")
            }
            
            return token_info
            
        except Exception as e:
            logger.error(f"Error getting token info from Solscan for {token_address}: {str(e)}")
            return None
    
    async def get_token_holders(self, token_address: str, limit: int = 100, 
                              offset: int = 0) -> Dict[str, Any]:
        """Get token holders list"""
        try:
            endpoint = f"/token/holders"
            params = {
                "tokenAddress": token_address,
                "limit": min(limit, 1000),
                "offset": offset
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return {
                    "holders": [],
                    "total": 0
                }
            
            data = response["data"]
            holders = []
            
            for holder in data.get("data", []):
                holder_info = {
                    "address": holder.get("address"),
                    "amount": holder.get("amount"),
                    "decimals": holder.get("decimals"),
                    "owner": holder.get("owner"),
                    "rank": holder.get("rank"),
                    "percentage": holder.get("percentage")
                }
                holders.append(holder_info)
            
            return {
                "holders": holders,
                "total": data.get("total", len(holders))
            }
            
        except Exception as e:
            logger.error(f"Error getting token holders from Solscan for {token_address}: {str(e)}")
            return {
                "holders": [],
                "total": 0
            }
    
    async def get_token_transfers(self, token_address: str, limit: int = 100, 
                                offset: int = 0, flow: str = "all") -> List[Dict[str, Any]]:
        """Get token transfer history"""
        try:
            endpoint = f"/token/transfer"
            params = {
                "token": token_address,
                "limit": min(limit, 1000),
                "offset": offset,
                "flow": flow  # in, out, all
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data") or not response["data"].get("data"):
                return []
            
            transfers = []
            for transfer in response["data"]["data"]:
                transfer_info = {
                    "signature": transfer.get("signature"),
                    "block_time": transfer.get("block_time"),
                    "slot": transfer.get("slot"),
                    "from_address": transfer.get("from_address"),
                    "to_address": transfer.get("to_address"),
                    "amount": transfer.get("amount"),
                    "decimals": transfer.get("decimals"),
                    "flow": transfer.get("flow"),
                    "token_address": transfer.get("token_address"),
                    "balance_change": transfer.get("balance_change")
                }
                transfers.append(transfer_info)
            
            return transfers
            
        except Exception as e:
            logger.error(f"Error getting token transfers from Solscan for {token_address}: {str(e)}")
            return []
    
    async def get_account_info(self, account_address: str) -> Dict[str, Any]:
        """Get detailed account information"""
        try:
            endpoint = f"/account/{account_address}"
            
            response = await self._request("GET", endpoint)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            account_info = {
                "address": account_address,
                "lamports": data.get("lamports"),
                "owner": data.get("owner"),
                "executable": data.get("executable"),
                "rent_epoch": data.get("rent_epoch"),
                "account_type": data.get("account_type"),
                "sol_balance": data.get("sol_balance"),
                "token_accounts": data.get("token_accounts", []),
                "nft_count": data.get("nft_count", 0),
                "token_count": data.get("token_count", 0),
                "transaction_count": data.get("transaction_count", 0),
                "created_time": data.get("created_time"),
                "updated_time": data.get("updated_time")
            }
            
            return account_info
            
        except Exception as e:
            logger.error(f"Error getting account info from Solscan for {account_address}: {str(e)}")
            return None
    
    async def get_account_transactions(self, account_address: str, limit: int = 100, 
                                     before: str = None, until: str = None) -> List[Dict[str, Any]]:
        """Get account transaction history"""
        try:
            endpoint = f"/account/transactions"
            params = {
                "account": account_address,
                "limit": min(limit, 1000)
            }
            
            if before:
                params["before"] = before
            if until:
                params["until"] = until
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return []
            
            transactions = []
            for tx in response["data"]:
                tx_info = {
                    "signature": tx.get("signature"),
                    "block_time": tx.get("block_time"),
                    "slot": tx.get("slot"),
                    "status": tx.get("status"),
                    "fee": tx.get("fee"),
                    "signer": tx.get("signer"),
                    "parsed_instruction": tx.get("parsed_instruction", []),
                    "program_ids": tx.get("program_ids", []),
                    "inner_instructions": tx.get("inner_instructions", [])
                }
                transactions.append(tx_info)
            
            return transactions
            
        except Exception as e:
            logger.error(f"Error getting account transactions from Solscan for {account_address}: {str(e)}")
            return []
    
    async def get_transaction_details(self, signature: str) -> Dict[str, Any]:
        """Get detailed transaction information"""
        try:
            endpoint = f"/transaction/{signature}"
            
            response = await self._request("GET", endpoint)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            transaction = {
                "signature": signature,
                "block_time": data.get("block_time"),
                "slot": data.get("slot"),
                "status": data.get("status"),
                "fee": data.get("fee"),
                "recent_block_hash": data.get("recent_block_hash"),
                "signer": data.get("signer"),
                "instructions": data.get("instructions", []),
                "inner_instructions": data.get("inner_instructions", []),
                "log_messages": data.get("log_messages", []),
                "balance_changes": data.get("balance_changes", []),
                "token_transfers": data.get("token_transfers", []),
                "pre_balances": data.get("pre_balances", []),
                "post_balances": data.get("post_balances", [])
            }
            
            return transaction
            
        except Exception as e:
            logger.error(f"Error getting transaction details from Solscan for {signature}: {str(e)}")
            return None
    
    async def get_block_info(self, block_number: int) -> Dict[str, Any]:
        """Get block information"""
        try:
            endpoint = f"/block/{block_number}"
            
            response = await self._request("GET", endpoint)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            block_info = {
                "block_number": block_number,
                "block_hash": data.get("block_hash"),
                "parent_slot": data.get("parent_slot"),
                "block_time": data.get("block_time"),
                "block_height": data.get("block_height"),
                "transaction_count": data.get("transaction_count"),
                "successful_transactions": data.get("successful_transactions"),
                "failed_transactions": data.get("failed_transactions"),
                "fee_total": data.get("fee_total"),
                "previous_block_hash": data.get("previous_block_hash"),
                "transactions": data.get("transactions", [])
            }
            
            return block_info
            
        except Exception as e:
            logger.error(f"Error getting block info from Solscan for block {block_number}: {str(e)}")
            return None
    
    async def get_market_data(self, token_address: str = None) -> Dict[str, Any]:
        """Get market data for tokens or SOL"""
        try:
            endpoint = "/market"
            params = {}
            
            if token_address:
                params["tokenAddress"] = token_address
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            market_data = {
                "price_sol": data.get("price_sol"),
                "price_usdt": data.get("price_usdt"),
                "volume_24h": data.get("volume_24h"),
                "market_cap": data.get("market_cap"),
                "price_change_24h": data.get("price_change_24h"),
                "price_change_7d": data.get("price_change_7d"),
                "market_cap_rank": data.get("market_cap_rank"),
                "updated_time": data.get("updated_time")
            }
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error getting market data from Solscan: {str(e)}")
            return None
    
    async def search_tokens(self, keyword: str) -> List[Dict[str, Any]]:
        """Search for tokens by name or symbol"""
        try:
            endpoint = "/token/search"
            params = {"keyword": keyword}
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return []
            
            tokens = []
            for token in response["data"]:
                token_info = {
                    "address": token.get("address"),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "decimals": token.get("decimals"),
                    "icon": token.get("icon"),
                    "price": token.get("price"),
                    "volume_24h": token.get("volume_24h"),
                    "market_cap": token.get("market_cap"),
                    "holder_count": token.get("holder_count"),
                    "verified": token.get("verified", False)
                }
                tokens.append(token_info)
            
            return tokens
            
        except Exception as e:
            logger.warning(f"Token search failed on Solscan for keyword '{keyword}': {str(e)}")
            return []
    
    async def get_top_tokens(self, sort_by: str = "market_cap", limit: int = 50) -> List[Dict[str, Any]]:
        """Get top tokens by various metrics"""
        try:
            endpoint = "/token/list"
            params = {
                "sortBy": sort_by,  # market_cap, volume_24h, price_change_24h, holder_count
                "limit": min(limit, 100)
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return []
            
            tokens = []
            for token in response["data"]:
                token_info = {
                    "address": token.get("address"),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "decimals": token.get("decimals"),
                    "icon": token.get("icon"),
                    "price": token.get("price"),
                    "volume_24h": token.get("volume_24h"),
                    "market_cap": token.get("market_cap"),
                    "price_change_24h": token.get("price_change_24h"),
                    "holder_count": token.get("holder_count"),
                    "rank": token.get("rank")
                }
                tokens.append(token_info)
            
            return tokens
            
        except Exception as e:
            logger.warning(f"Error getting top tokens from Solscan: {str(e)}")
            return []
    
    async def get_token_price_history(self, token_address: str, timeframe: str = "1d") -> List[Dict[str, Any]]:
        """Get token price history"""
        try:
            endpoint = f"/token/price"
            params = {
                "tokenAddress": token_address,
                "timeframe": timeframe  # 1h, 4h, 1d, 7d, 30d
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data") or not response["data"].get("data"):
                return []
            
            price_history = []
            for price_point in response["data"]["data"]:
                price_data = {
                    "timestamp": price_point.get("timestamp"),
                    "price": price_point.get("price"),
                    "volume": price_point.get("volume"),
                    "market_cap": price_point.get("market_cap")
                }
                price_history.append(price_data)
            
            return price_history
            
        except Exception as e:
            logger.error(f"Error getting token price history from Solscan for {token_address}: {str(e)}")
            return []
    
    async def get_dex_activities(self, token_address: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get DEX trading activities for a token"""
        try:
            endpoint = f"/token/activities"
            params = {
                "tokenAddress": token_address,
                "activity[]": ["swap", "add_liquidity", "remove_liquidity"],
                "limit": min(limit, 500)
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return []
            
            activities = []
            for activity in response["data"]:
                activity_info = {
                    "signature": activity.get("signature"),
                    "block_time": activity.get("block_time"),
                    "activity_type": activity.get("activity_type"),
                    "amount": activity.get("amount"),
                    "source": activity.get("source"),  # DEX name
                    "price": activity.get("price"),
                    "volume_usd": activity.get("volume_usd"),
                    "from_token": activity.get("from_token"),
                    "to_token": activity.get("to_token"),
                    "signer": activity.get("signer")
                }
                activities.append(activity_info)
            
            return activities
            
        except Exception as e:
            logger.error(f"Error getting DEX activities from Solscan for {token_address}: {str(e)}")
            return []
    
    async def get_nft_activities(self, collection_address: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get NFT trading activities"""
        try:
            endpoint = "/nft/activities"
            params = {"limit": min(limit, 500)}
            
            if collection_address:
                params["collection"] = collection_address
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return []
            
            activities = []
            for activity in response["data"]:
                activity_info = {
                    "signature": activity.get("signature"),
                    "block_time": activity.get("block_time"),
                    "activity_type": activity.get("activity_type"),  # listing, sale, bid, etc.
                    "nft_address": activity.get("nft_address"),
                    "collection_address": activity.get("collection_address"),
                    "price": activity.get("price"),
                    "currency": activity.get("currency"),
                    "marketplace": activity.get("marketplace"),
                    "seller": activity.get("seller"),
                    "buyer": activity.get("buyer")
                }
                activities.append(activity_info)
            
            return activities
            
        except Exception as e:
            logger.warning(f"Error getting NFT activities from Solscan: {str(e)}")
            return []
    
    async def get_program_accounts(self, program_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get accounts owned by a specific program"""
        try:
            endpoint = f"/account/program/{program_id}"
            params = {"limit": min(limit, 1000)}
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return []
            
            accounts = []
            for account in response["data"]:
                account_info = {
                    "address": account.get("address"),
                    "lamports": account.get("lamports"),
                    "data_size": account.get("data_size"),
                    "owner": account.get("owner"),
                    "executable": account.get("executable"),
                    "rent_epoch": account.get("rent_epoch")
                }
                accounts.append(account_info)
            
            return accounts
            
        except Exception as e:
            logger.error(f"Error getting program accounts from Solscan for {program_id}: {str(e)}")
            return []
    
    async def get_defi_protocols(self) -> List[Dict[str, Any]]:
        """Get list of DeFi protocols on Solana"""
        try:
            endpoint = "/defi/protocols"
            
            response = await self._request("GET", endpoint)
            
            if not response.get("data"):
                return []
            
            protocols = []
            for protocol in response["data"]:
                protocol_info = {
                    "name": protocol.get("name"),
                    "website": protocol.get("website"),
                    "description": protocol.get("description"),
                    "category": protocol.get("category"),
                    "tvl": protocol.get("tvl"),
                    "volume_24h": protocol.get("volume_24h"),
                    "change_24h": protocol.get("change_24h"),
                    "program_id": protocol.get("program_id"),
                    "logo": protocol.get("logo")
                }
                protocols.append(protocol_info)
            
            return protocols
            
        except Exception as e:
            logger.warning(f"Error getting DeFi protocols from Solscan: {str(e)}")
            return []
    
    async def get_validator_info(self, validator_address: str) -> Dict[str, Any]:
        """Get validator information"""
        try:
            endpoint = f"/validator/{validator_address}"
            
            response = await self._request("GET", endpoint)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            validator_info = {
                "address": validator_address,
                "name": data.get("name"),
                "website": data.get("website"),
                "details": data.get("details"),
                "keybase_id": data.get("keybase_id"),
                "avatar_url": data.get("avatar_url"),
                "activated_stake": data.get("activated_stake"),
                "total_score": data.get("total_score"),
                "root_distance_score": data.get("root_distance_score"),
                "vote_distance_score": data.get("vote_distance_score"),
                "skipped_slot_score": data.get("skipped_slot_score"),
                "software_version": data.get("software_version"),
                "stake_concentration": data.get("stake_concentration"),
                "data_center_concentration": data.get("data_center_concentration"),
                "published_information": data.get("published_information"),
                "security_report": data.get("security_report")
            }
            
            return validator_info
            
        except Exception as e:
            logger.error(f"Error getting validator info from Solscan for {validator_address}: {str(e)}")
            return None
    
    async def get_network_stats(self) -> Dict[str, Any]:
        """Get Solana network statistics"""
        try:
            endpoint = "/network/stats"
            
            response = await self._request("GET", endpoint)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            network_stats = {
                "current_slot": data.get("current_slot"),
                "current_epoch": data.get("current_epoch"),
                "epoch_progress": data.get("epoch_progress"),
                "slots_in_epoch": data.get("slots_in_epoch"),
                "block_time": data.get("block_time"),
                "total_validators": data.get("total_validators"),
                "active_validators": data.get("active_validators"),
                "total_stake": data.get("total_stake"),
                "circulating_supply": data.get("circulating_supply"),
                "inflation_rate": data.get("inflation_rate"),
                "transaction_count_24h": data.get("transaction_count_24h"),
                "tps_current": data.get("tps_current"),
                "tps_24h_avg": data.get("tps_24h_avg")
            }
            
            return network_stats
            
        except Exception as e:
            logger.error(f"Error getting network stats from Solscan: {str(e)}")
            return None
    
    async def analyze_token_comprehensive(self, token_address: str) -> Dict[str, Any]:
        """Comprehensive token analysis using multiple Solscan endpoints"""
        try:
            # Gather data from multiple endpoints
            tasks = [
                self.get_token_info(token_address),
                self.get_token_holders(token_address, 50),
                self.get_token_transfers(token_address, 100),
                self.get_dex_activities(token_address, 100),
                self.get_token_price_history(token_address, "7d")
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            token_info = results[0] if not isinstance(results[0], Exception) else None
            holders_data = results[1] if not isinstance(results[1], Exception) else {"holders": [], "total": 0}
            transfers = results[2] if not isinstance(results[2], Exception) else []
            dex_activities = results[3] if not isinstance(results[3], Exception) else []
            price_history = results[4] if not isinstance(results[4], Exception) else []
            
            # Compile comprehensive analysis
            analysis = {
                "token_address": token_address,
                "basic_info": token_info,
                "holder_analysis": self._analyze_holders(holders_data),
                "trading_analysis": self._analyze_trading(dex_activities),
                "transfer_analysis": self._analyze_transfers(transfers),
                "price_analysis": self._analyze_price_history(price_history),
                "risk_indicators": self._calculate_risk_indicators(token_info, holders_data, transfers),
                "analysis_timestamp": int(time.time())
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in comprehensive token analysis for {token_address}: {str(e)}")
            return {"error": str(e), "token_address": token_address}
    
    def _analyze_holders(self, holders_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze holder distribution"""
        holders = holders_data.get("holders", [])
        total_holders = holders_data.get("total", 0)
        
        if not holders:
            return {"total_holders": 0, "distribution": {}, "concentration": {}}
        
        # Calculate concentration
        top_10_percentage = sum(float(h.get("percentage", 0)) for h in holders[:10])
        top_100_percentage = sum(float(h.get("percentage", 0)) for h in holders[:100])
        
        # Categorize holders
        whale_count = len([h for h in holders if float(h.get("percentage", 0)) >= 1])
        large_holder_count = len([h for h in holders if 0.1 <= float(h.get("percentage", 0)) < 1])
        
        return {
            "total_holders": total_holders,
            "distribution": {
                "whales": whale_count,
                "large_holders": large_holder_count,
                "regular_holders": total_holders - whale_count - large_holder_count
            },
            "concentration": {
                "top_10_percentage": top_10_percentage,
                "top_100_percentage": top_100_percentage,
                "concentration_risk": "high" if top_10_percentage > 50 else "medium" if top_10_percentage > 30 else "low"
            }
        }
    
    def _analyze_trading(self, activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze trading activities"""
        if not activities:
            return {"volume_24h": 0, "trade_count": 0, "avg_trade_size": 0}
        
        total_volume = sum(float(a.get("volume_usd", 0)) for a in activities)
        trade_count = len(activities)
        avg_trade_size = total_volume / trade_count if trade_count > 0 else 0
        
        # Analyze by DEX
        dex_breakdown = {}
        for activity in activities:
            dex = activity.get("source", "unknown")
            if dex not in dex_breakdown:
                dex_breakdown[dex] = {"volume": 0, "trades": 0}
            dex_breakdown[dex]["volume"] += float(activity.get("volume_usd", 0))
            dex_breakdown[dex]["trades"] += 1
        
        return {
            "volume_24h": total_volume,
            "trade_count": trade_count,
            "avg_trade_size": avg_trade_size,
            "dex_breakdown": dex_breakdown,
            "trading_activity": "high" if trade_count > 100 else "medium" if trade_count > 20 else "low"
        }
    
    def _analyze_transfers(self, transfers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze transfer patterns"""
        if not transfers:
            return {"transfer_count": 0, "unique_addresses": 0}
        
        unique_from = set(t.get("from_address") for t in transfers if t.get("from_address"))
        unique_to = set(t.get("to_address") for t in transfers if t.get("to_address"))
        unique_addresses = len(unique_from.union(unique_to))
        
        # Analyze transfer patterns
        large_transfers = [t for t in transfers if float(t.get("amount", 0)) > 1000000]  # 1M tokens
        
        return {
            "transfer_count": len(transfers),
            "unique_addresses": unique_addresses,
            "large_transfers": len(large_transfers),
            "activity_level": "high" if len(transfers) > 500 else "medium" if len(transfers) > 100 else "low"
        }
    
    def _analyze_price_history(self, price_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze price history"""
        if not price_history:
            return {"volatility": 0, "trend": "unknown", "price_changes": {}}
        
        prices = [float(p.get("price", 0)) for p in price_history if p.get("price")]
        
        if len(prices) < 2:
            return {"volatility": 0, "trend": "unknown", "price_changes": {}}
        
        # Calculate volatility
        price_changes = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        volatility = sum(abs(change) for change in price_changes) / len(price_changes) if price_changes else 0
        
        # Calculate trend
        overall_change = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
        trend = "bullish" if overall_change > 0.05 else "bearish" if overall_change < -0.05 else "sideways"
        
        return {
            "volatility": volatility,
            "trend": trend,
            "price_changes": {
                "overall_change": overall_change,
                "max_price": max(prices),
                "min_price": min(prices),
                "current_price": prices[-1]
            }
        }
    
    def _calculate_risk_indicators(self, token_info: Dict[str, Any], holders_data: Dict[str, Any], 
                                  transfers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate risk indicators based on collected data"""
        risk_score = 0
        risk_factors = []
        
        if not token_info:
            return {"risk_score": 100, "risk_level": "critical", "factors": ["No token information available"]}
        
        # Holder concentration risk
        holders = holders_data.get("holders", [])
        if holders:
            top_holder_percentage = float(holders[0].get("percentage", 0)) if holders else 0
            if top_holder_percentage > 50:
                risk_score += 30
                risk_factors.append("Extremely high holder concentration")
            elif top_holder_percentage > 20:
                risk_score += 15
                risk_factors.append("High holder concentration")
        
        # Low holder count risk
        holder_count = token_info.get("holder_count", 0)
        if holder_count < 100:
            risk_score += 20
            risk_factors.append("Very low holder count")
        elif holder_count < 1000:
            risk_score += 10
            risk_factors.append("Low holder count")
        
        # Low trading activity
        if len(transfers) < 10:
            risk_score += 15
            risk_factors.append("Very low trading activity")
        
        # New token risk
        created_time = token_info.get("created_time")
        if created_time and (time.time() - created_time) < 86400 * 7:  # Less than 7 days
            risk_score += 25
            risk_factors.append("Very new token")
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = "critical"
        elif risk_score >= 50:
            risk_level = "high"
        elif risk_score >= 30:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        return {
            "risk_score": min(risk_score, 100),
            "risk_level": risk_level,
            "factors": risk_factors
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Solscan API health"""
        try:
            start_time = time.time()
            
            # Simple API test
            network_stats = await self.get_network_stats()
            
            response_time = time.time() - start_time
            
            return {
                "healthy": network_stats is not None,
                "api_key_configured": bool(self.api_key),
                "base_url": self.base_url,
                "response_time": response_time,
                "test_data": network_stats
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": str(e),
                "base_url": self.base_url
            }


# Convenience functions
async def get_solscan_client() -> SolscanClient:
    """Get configured Solscan client"""
    return SolscanClient()


async def check_solscan_health() -> Dict[str, Any]:
    """Check Solscan service health"""
    async with SolscanClient() as client:
        return await client.health_check()