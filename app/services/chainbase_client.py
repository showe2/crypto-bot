import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from decimal import Decimal
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class ChainbaseAPIError(Exception):
    """Chainbase API specific errors"""
    pass


class ChainbaseClient:
    """Chainbase API client for blockchain analytics and smart contract data"""
    
    def __init__(self):
        self.api_key = settings.CHAINBASE_API_KEY
        self.base_url = settings.CHAINBASE_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.2  # 200ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        if not self.api_key:
            logger.warning("Chainbase API key not configured")
    
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
            raise ChainbaseAPIError("Chainbase API key not configured")
        
        await self._ensure_session()
        await self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "x-api-key": self.api_key,
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
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"Chainbase rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                elif response.status == 401:
                    raise ChainbaseAPIError("Invalid Chainbase API key")
                else:
                    error_msg = response_data.get('message', f'HTTP {response.status}')
                    raise ChainbaseAPIError(f"Chainbase API error: {error_msg}")
                    
        except asyncio.TimeoutError:
            raise ChainbaseAPIError("Chainbase API request timeout")
        except aiohttp.ClientError as e:
            raise ChainbaseAPIError(f"Chainbase client error: {str(e)}")
    
    async def get_token_metadata(self, mint_address: str, chain_id: str = "solana-mainnet") -> Dict[str, Any]:
        """Get comprehensive token metadata"""
        try:
            endpoint = f"/solana/mainnet/token/{mint_address}/metadata"
            
            response = await self._request("GET", endpoint)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            metadata = {
                "mint": mint_address,
                "name": data.get("name"),
                "symbol": data.get("symbol"),
                "decimals": data.get("decimals"),
                "total_supply": data.get("total_supply"),
                "description": data.get("description"),
                "image": data.get("image"),
                "external_url": data.get("external_url"),
                "creator": data.get("creator"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "verified": data.get("verified", False),
                "tags": data.get("tags", [])
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting token metadata from Chainbase for {mint_address}: {str(e)}")
            return None
    
    async def get_token_holders(self, mint_address: str, limit: int = 100, page: int = 1) -> Dict[str, Any]:
        """Get token holders analysis"""
        try:
            endpoint = f"/solana/mainnet/token/{mint_address}/holders"
            params = {
                "limit": min(limit, 1000),  # API usually limits to 1000
                "page": page
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return {
                    "holders": [],
                    "total_holders": 0,
                    "distribution": {}
                }
            
            data = response["data"]
            holders = []
            
            for holder in data.get("holders", []):
                holder_info = {
                    "address": holder.get("address"),
                    "balance": holder.get("balance"),
                    "balance_usd": holder.get("balance_usd"),
                    "percentage": holder.get("percentage"),
                    "rank": holder.get("rank"),
                    "first_transaction": holder.get("first_transaction"),
                    "last_transaction": holder.get("last_transaction"),
                    "transaction_count": holder.get("transaction_count")
                }
                holders.append(holder_info)
            
            # Calculate distribution
            distribution = self._calculate_holder_distribution(holders)
            
            return {
                "holders": holders,
                "total_holders": data.get("total_holders", len(holders)),
                "distribution": distribution,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "has_next": len(holders) == limit
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting token holders from Chainbase for {mint_address}: {str(e)}")
            return {
                "holders": [],
                "total_holders": 0,
                "distribution": {}
            }
    
    def _calculate_holder_distribution(self, holders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate holder distribution statistics"""
        if not holders:
            return {}
        
        total_supply = sum(float(h.get("balance", 0)) for h in holders)
        
        # Categorize holders
        whales = [h for h in holders if float(h.get("percentage", 0)) >= 1.0]  # 1%+
        large_holders = [h for h in holders if 0.1 <= float(h.get("percentage", 0)) < 1.0]  # 0.1-1%
        medium_holders = [h for h in holders if 0.01 <= float(h.get("percentage", 0)) < 0.1]  # 0.01-0.1%
        small_holders = [h for h in holders if float(h.get("percentage", 0)) < 0.01]  # <0.01%
        
        return {
            "whales": {
                "count": len(whales),
                "total_percentage": sum(float(h.get("percentage", 0)) for h in whales)
            },
            "large_holders": {
                "count": len(large_holders),
                "total_percentage": sum(float(h.get("percentage", 0)) for h in large_holders)
            },
            "medium_holders": {
                "count": len(medium_holders),
                "total_percentage": sum(float(h.get("percentage", 0)) for h in medium_holders)
            },
            "small_holders": {
                "count": len(small_holders),
                "total_percentage": sum(float(h.get("percentage", 0)) for h in small_holders)
            },
            "concentration": {
                "top_10_percentage": sum(float(h.get("percentage", 0)) for h in holders[:10]),
                "top_100_percentage": sum(float(h.get("percentage", 0)) for h in holders[:100]),
                "gini_coefficient": self._calculate_gini_coefficient(holders)
            }
        }
    
    def _calculate_gini_coefficient(self, holders: List[Dict[str, Any]]) -> float:
        """Calculate Gini coefficient for wealth distribution"""
        if not holders:
            return 0.0
        
        balances = [float(h.get("balance", 0)) for h in holders]
        balances.sort()
        
        n = len(balances)
        cumsum = sum((i + 1) * balance for i, balance in enumerate(balances))
        total = sum(balances)
        
        if total == 0:
            return 0.0
        
        return (2 * cumsum) / (n * total) - (n + 1) / n
    
    async def get_smart_contract_info(self, contract_address: str) -> Dict[str, Any]:
        """Get smart contract information and analysis"""
        try:
            endpoint = f"/solana/mainnet/contract/{contract_address}/info"
            
            response = await self._request("GET", endpoint)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            contract_info = {
                "address": contract_address,
                "type": data.get("type"),
                "verified": data.get("verified", False),
                "compiler_version": data.get("compiler_version"),
                "creation_transaction": data.get("creation_transaction"),
                "creator": data.get("creator"),
                "creation_block": data.get("creation_block"),
                "creation_timestamp": data.get("creation_timestamp"),
                "source_code": data.get("source_code") if data.get("verified") else None,
                "abi": data.get("abi"),
                "proxy_type": data.get("proxy_type"),
                "implementation": data.get("implementation")
            }
            
            return contract_info
            
        except Exception as e:
            logger.error(f"Error getting smart contract info from Chainbase for {contract_address}: {str(e)}")
            return None
    
    async def get_token_transfers(self, mint_address: str, limit: int = 100, page: int = 1) -> Dict[str, Any]:
        """Get token transfer history"""
        try:
            endpoint = f"/solana/mainnet/token/{mint_address}/transfers"
            params = {
                "limit": min(limit, 1000),
                "page": page
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return {
                    "transfers": [],
                    "total_transfers": 0
                }
            
            data = response["data"]
            transfers = []
            
            for transfer in data.get("transfers", []):
                transfer_info = {
                    "transaction_hash": transfer.get("transaction_hash"),
                    "block_number": transfer.get("block_number"),
                    "timestamp": transfer.get("timestamp"),
                    "from_address": transfer.get("from_address"),
                    "to_address": transfer.get("to_address"),
                    "amount": transfer.get("amount"),
                    "amount_usd": transfer.get("amount_usd"),
                    "transaction_fee": transfer.get("transaction_fee"),
                    "status": transfer.get("status")
                }
                transfers.append(transfer_info)
            
            return {
                "transfers": transfers,
                "total_transfers": data.get("total_transfers", len(transfers)),
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "has_next": len(transfers) == limit
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting token transfers from Chainbase for {mint_address}: {str(e)}")
            return {
                "transfers": [],
                "total_transfers": 0
            }
    
    async def get_address_analysis(self, address: str) -> Dict[str, Any]:
        """Get comprehensive address analysis"""
        try:
            endpoint = f"/solana/mainnet/address/{address}/analysis"
            
            response = await self._request("GET", endpoint)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            analysis = {
                "address": address,
                "address_type": data.get("address_type"),  # wallet, contract, exchange, etc.
                "is_contract": data.get("is_contract", False),
                "first_transaction": data.get("first_transaction"),
                "last_transaction": data.get("last_transaction"),
                "transaction_count": data.get("transaction_count"),
                "balance_history": data.get("balance_history", []),
                "token_holdings": data.get("token_holdings", []),
                "interaction_patterns": data.get("interaction_patterns", {}),
                "risk_score": data.get("risk_score"),
                "labels": data.get("labels", []),
                "entity": data.get("entity")  # If address belongs to known entity
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error getting address analysis from Chainbase for {address}: {str(e)}")
            return None
    
    async def get_defi_protocols(self, token_address: str) -> List[Dict[str, Any]]:
        """Get DeFi protocols where token is used"""
        try:
            endpoint = f"/solana/mainnet/token/{token_address}/protocols"
            
            response = await self._request("GET", endpoint)
            
            if not response.get("data"):
                return []
            
            protocols = []
            for protocol in response["data"].get("protocols", []):
                protocol_info = {
                    "name": protocol.get("name"),
                    "type": protocol.get("type"),  # dex, lending, staking, etc.
                    "tvl": protocol.get("tvl"),
                    "volume_24h": protocol.get("volume_24h"),
                    "token_usage": protocol.get("token_usage"),  # How token is used in protocol
                    "pool_info": protocol.get("pool_info", {}),
                    "yield_info": protocol.get("yield_info", {})
                }
                protocols.append(protocol_info)
            
            return protocols
            
        except Exception as e:
            logger.warning(f"Error getting DeFi protocols from Chainbase for {token_address}: {str(e)}")
            return []
    
    async def get_whale_activity(self, token_address: str, threshold_usd: float = 10000) -> List[Dict[str, Any]]:
        """Get recent whale activity for a token"""
        try:
            endpoint = f"/solana/mainnet/token/{token_address}/whale-activity"
            params = {
                "threshold_usd": threshold_usd,
                "limit": 50
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return []
            
            whale_activities = []
            for activity in response["data"].get("activities", []):
                activity_info = {
                    "transaction_hash": activity.get("transaction_hash"),
                    "timestamp": activity.get("timestamp"),
                    "from_address": activity.get("from_address"),
                    "to_address": activity.get("to_address"),
                    "amount": activity.get("amount"),
                    "amount_usd": activity.get("amount_usd"),
                    "action_type": activity.get("action_type"),  # buy, sell, transfer
                    "whale_score": activity.get("whale_score"),
                    "exchange": activity.get("exchange"),
                    "price_impact": activity.get("price_impact")
                }
                whale_activities.append(activity_info)
            
            return whale_activities
            
        except Exception as e:
            logger.warning(f"Error getting whale activity from Chainbase for {token_address}: {str(e)}")
            return []
    
    async def search_tokens(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for tokens by name, symbol, or address"""
        try:
            endpoint = "/solana/mainnet/tokens/search"
            params = {
                "query": query,
                "limit": limit
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data"):
                return []
            
            tokens = []
            for token in response["data"].get("tokens", []):
                token_info = {
                    "mint": token.get("mint"),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "decimals": token.get("decimals"),
                    "verified": token.get("verified", False),
                    "market_cap": token.get("market_cap"),
                    "price": token.get("price"),
                    "volume_24h": token.get("volume_24h"),
                    "holders_count": token.get("holders_count"),
                    "created_at": token.get("created_at")
                }
                tokens.append(token_info)
            
            return tokens
            
        except Exception as e:
            logger.warning(f"Token search failed on Chainbase for query '{query}': {str(e)}")
            return []
    
    async def get_market_data(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive market data for token"""
        try:
            endpoint = f"/solana/mainnet/token/{token_address}/market"
            
            response = await self._request("GET", endpoint)
            
            if not response.get("data"):
                return None
            
            data = response["data"]
            market_data = {
                "price": data.get("price"),
                "price_change_24h": data.get("price_change_24h"),
                "price_change_7d": data.get("price_change_7d"),
                "volume_24h": data.get("volume_24h"),
                "volume_change_24h": data.get("volume_change_24h"),
                "market_cap": data.get("market_cap"),
                "market_cap_rank": data.get("market_cap_rank"),
                "circulating_supply": data.get("circulating_supply"),
                "total_supply": data.get("total_supply"),
                "max_supply": data.get("max_supply"),
                "ath": data.get("ath"),
                "ath_date": data.get("ath_date"),
                "atl": data.get("atl"),
                "atl_date": data.get("atl_date"),
                "liquidity": data.get("liquidity"),
                "fdv": data.get("fdv")  # Fully Diluted Valuation
            }
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error getting market data from Chainbase for {token_address}: {str(e)}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Chainbase API health"""
        try:
            start_time = time.time()
            
            # Simple API test
            endpoint = "/solana/mainnet/stats"
            response = await self._request("GET", endpoint)
            
            response_time = time.time() - start_time
            
            return {
                "healthy": True,
                "api_key_configured": bool(self.api_key),
                "base_url": self.base_url,
                "response_time": response_time,
                "status": "operational"
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": str(e),
                "base_url": self.base_url
            }


# Convenience functions
async def get_chainbase_client() -> ChainbaseClient:
    """Get configured Chainbase client"""
    return ChainbaseClient()


async def check_chainbase_health() -> Dict[str, Any]:
    """Check Chainbase service health"""
    async with ChainbaseClient() as client:
        return await client.health_check()