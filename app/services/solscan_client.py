# Updated app/services/solscan_client.py with latest v2.0 API endpoints

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
    """Solscan API client - Updated with v2.0 endpoints"""
    
    def __init__(self):
        self.api_key = settings.SOLSCAN_API_KEY
        self.base_url = "https://pro-api.solscan.io"  # Updated to pro-api
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
            "Accept": "application/json",
            "User-Agent": "Solana-Token-Analysis/1.0",
            **kwargs.pop("headers", {})
        }
        
        # Add API key if available - Solscan v2.0 uses Authorization header
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                content_type = response.headers.get('content-type', '').lower()
                
                logger.debug(f"Solscan {method} {endpoint} - Status: {response.status}, Content-Type: {content_type}")
                
                if response.status == 200:
                    if 'application/json' in content_type:
                        response_data = await response.json()
                        return response_data
                    else:
                        response_text = await response.text()
                        logger.warning(f"Unexpected content type from Solscan: {content_type}")
                        raise SolscanAPIError(f"Expected JSON, got {content_type}")
                        
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"Solscan rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                elif response.status == 401:
                    raise SolscanAPIError("Invalid Solscan API key or unauthorized access")
                elif response.status == 403:
                    raise SolscanAPIError("Forbidden - check API key permissions")
                elif response.status == 404:
                    # Endpoint not found
                    raise SolscanAPIError(f"Solscan endpoint not found: {endpoint}")
                else:
                    try:
                        error_text = await response.text()
                        raise SolscanAPIError(f"HTTP {response.status}: {error_text[:200]}")
                    except:
                        raise SolscanAPIError(f"HTTP {response.status}: Unknown error")
                    
        except asyncio.TimeoutError:
            raise SolscanAPIError("Solscan API request timeout")
        except aiohttp.ClientError as e:
            raise SolscanAPIError(f"Solscan client error: {str(e)}")
    
    async def get_account_detail(self, account_address: str) -> Dict[str, Any]:
        """Get account details using v2.0 API - UPDATED ENDPOINT"""
        try:
            # v2.0 endpoint: /v2.0/account/{account}
            endpoint = f"/v2.0/account/{account_address}"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                raise SolscanAPIError("No data returned from account detail endpoint")
            
            # Handle v2.0 response structure
            if isinstance(response, dict):
                # Check for success field in v2.0 API
                if response.get("success") == False:
                    error_msg = response.get("error", "Unknown API error")
                    raise SolscanAPIError(f"API error: {error_msg}")
                
                # Extract data from v2.0 response
                data = response.get("data", response)
                
                account_info = {
                    "address": account_address,
                    "lamports": data.get("lamports"),
                    "owner": data.get("owner"),
                    "executable": data.get("executable", False),
                    "rent_epoch": data.get("rentEpoch"),
                    "space": data.get("space"),
                    "account_type": data.get("type"),
                    "balance_sol": float(data.get("lamports", 0)) / 1e9 if data.get("lamports") else 0,
                    # v2.0 specific fields
                    "account_data": data.get("data"),
                    "parsed_data": data.get("parsedData")
                }
                
                return account_info
            else:
                raise SolscanAPIError("Unexpected response format")
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting account detail from Solscan for {account_address}: {str(e)}")
            raise SolscanAPIError(f"Failed to get account detail: {str(e)}")
    
    async def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """Get token information using v2.0 API - UPDATED ENDPOINT"""
        try:
            # v2.0 endpoint: /v2.0/token/{token}
            endpoint = f"/v2.0/token/{token_address}"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                raise SolscanAPIError("No data returned from token info endpoint")
            
            # Handle v2.0 response structure
            if isinstance(response, dict):
                if response.get("success") == False:
                    error_msg = response.get("error", "Unknown API error")
                    raise SolscanAPIError(f"API error: {error_msg}")
                
                data = response.get("data", response)
                
                token_info = {
                    "address": token_address,
                    "name": data.get("name"),
                    "symbol": data.get("symbol"),
                    "decimals": data.get("decimals"),
                    "supply": data.get("supply"),
                    "icon": data.get("icon"),
                    "website": data.get("website"),
                    "twitter": data.get("twitter"),
                    "discord": data.get("discord"),
                    "telegram": data.get("telegram"),
                    # Market data from v2.0 API
                    "price": data.get("price"),
                    "price_change_24h": data.get("priceChange24h"),
                    "volume_24h": data.get("volume24h"),
                    "market_cap": data.get("marketCap"),
                    "holder_count": data.get("holderCount"),
                    "created_time": data.get("createdTime"),
                    "updated_time": data.get("updatedTime"),
                    # v2.0 specific fields
                    "mint_authority": data.get("mintAuthority"),
                    "freeze_authority": data.get("freezeAuthority"),
                    "is_initialized": data.get("isInitialized"),
                    "tags": data.get("tags", [])
                }
                
                return token_info
            else:
                raise SolscanAPIError("Unexpected response format")
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting token info from Solscan for {token_address}: {str(e)}")
            raise SolscanAPIError(f"Failed to get token info: {str(e)}")
    
    async def get_token_holders(self, token_address: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get token holders using v2.0 API - UPDATED ENDPOINT"""
        try:
            # v2.0 endpoint: /v2.0/token/{token}/holders
            endpoint = f"/v2.0/token/{token_address}/holders"
            params = {
                "limit": min(limit, 1000),
                "offset": offset
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response:
                raise SolscanAPIError("No data returned from token holders endpoint")
            
            # Handle v2.0 response structure
            if isinstance(response, dict):
                if response.get("success") == False:
                    error_msg = response.get("error", "Unknown API error")
                    raise SolscanAPIError(f"API error: {error_msg}")
                
                data = response.get("data", response)
                
                holders = []
                holder_list = data.get("holders", data) if isinstance(data, dict) else data
                
                if isinstance(holder_list, list):
                    for holder in holder_list:
                        holder_info = {
                            "address": holder.get("address"),
                            "amount": holder.get("amount"),
                            "decimals": holder.get("decimals"),
                            "owner": holder.get("owner"),
                            "rank": holder.get("rank"),
                            "percentage": holder.get("percentage"),
                            # v2.0 specific fields
                            "ui_amount": holder.get("uiAmount"),
                            "ui_amount_string": holder.get("uiAmountString")
                        }
                        holders.append(holder_info)
                
                # Extract pagination info from v2.0 response
                pagination = data.get("pagination", {})
                total_count = pagination.get("total", len(holders))
                
                return {
                    "holders": holders,
                    "total": total_count,
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "total": total_count,
                        "has_next": offset + len(holders) < total_count
                    }
                }
            else:
                raise SolscanAPIError("Unexpected response format")
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting token holders from Solscan for {token_address}: {str(e)}")
            raise SolscanAPIError(f"Failed to get token holders: {str(e)}")
    
    async def search_tokens(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for tokens using v2.0 API - UPDATED ENDPOINT"""
        try:
            # v2.0 endpoint: /v2.0/token/search
            endpoint = "/v2.0/token/search"
            params = {
                "keyword": keyword,
                "limit": min(limit, 100)
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response:
                return []
            
            # Handle v2.0 response structure
            if isinstance(response, dict):
                if response.get("success") == False:
                    error_msg = response.get("error", "Unknown API error")
                    logger.warning(f"Token search API error: {error_msg}")
                    return []
                
                data = response.get("data", response)
                token_list = data.get("tokens", data) if isinstance(data, dict) else data
                
                if not isinstance(token_list, list):
                    return []
                
                tokens = []
                for token in token_list:
                    token_info = {
                        "address": token.get("address"),
                        "name": token.get("name"),
                        "symbol": token.get("symbol"),
                        "decimals": token.get("decimals"),
                        "icon": token.get("icon"),
                        "price": token.get("price"),
                        "volume_24h": token.get("volume24h"),
                        "market_cap": token.get("marketCap"),
                        "holder_count": token.get("holderCount"),
                        "verified": token.get("verified", False),
                        # v2.0 specific fields
                        "supply": token.get("supply"),
                        "tags": token.get("tags", []),
                        "created_time": token.get("createdTime")
                    }
                    tokens.append(token_info)
                
                return tokens
            else:
                return []
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.warning(f"Token search failed on Solscan for keyword '{keyword}': {str(e)}")
            raise SolscanAPIError(f"Failed to search tokens: {str(e)}")
    
    async def get_network_stats(self) -> Dict[str, Any]:
        """Get Solana network statistics using v2.0 API - UPDATED ENDPOINT"""
        try:
            # v2.0 endpoint: /v2.0/chaininfo
            endpoint = "/v2.0/chaininfo"
            
            logger.debug(f"Solscan network stats: trying {endpoint}")
            response = await self._request("GET", endpoint)
            
            if response:
                logger.info(f"✅ Solscan {endpoint} successful")
                
                # Handle v2.0 response structure
                if isinstance(response, dict):
                    if response.get("success") == False:
                        error_msg = response.get("error", "Unknown API error")
                        raise SolscanAPIError(f"API error: {error_msg}")
                    
                    data = response.get("data", response)
                    
                    network_stats = {
                        "endpoint_used": endpoint,
                        "response_keys": list(data.keys()) if isinstance(data, dict) else [],
                        "data_available": True
                    }
                    
                    # Extract v2.0 network information
                    field_mappings = {
                        "current_slot": ["currentSlot", "slot", "latestSlot"],
                        "current_epoch": ["currentEpoch", "epoch", "latestEpoch"],
                        "total_validators": ["totalValidators", "validators", "validatorCount"],
                        "total_stake": ["totalStake", "stake", "totalStakeAmount"],
                        "circulating_supply": ["circulatingSupply", "supply", "totalSupply"],
                        # v2.0 specific fields
                        "network_time": ["networkTime", "blockTime"],
                        "cluster": ["cluster"],
                        "version": ["version", "solanaVersion"]
                    }
                    
                    for standard_key, possible_fields in field_mappings.items():
                        for field in possible_fields:
                            if field in data:
                                network_stats[standard_key] = data[field]
                                break
                    
                    return network_stats
                else:
                    raise SolscanAPIError("Unexpected response format")
            else:
                raise SolscanAPIError("Empty response from chaininfo endpoint")
                
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting network stats from Solscan: {str(e)}")
            raise SolscanAPIError(f"Failed to get network stats: {str(e)}")
    
    async def get_token_transfers(self, token_address: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get token transfers using v2.0 API - NEW ENDPOINT"""
        try:
            # v2.0 endpoint: /v2.0/token/{token}/transfers
            endpoint = f"/v2.0/token/{token_address}/transfers"
            params = {
                "limit": min(limit, 100),
                "offset": offset
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response:
                return {"transfers": [], "total": 0}
            
            # Handle v2.0 response structure
            if isinstance(response, dict):
                if response.get("success") == False:
                    error_msg = response.get("error", "Unknown API error")
                    raise SolscanAPIError(f"API error: {error_msg}")
                
                data = response.get("data", response)
                
                transfers = []
                transfer_list = data.get("transfers", data) if isinstance(data, dict) else data
                
                if isinstance(transfer_list, list):
                    for transfer in transfer_list:
                        transfer_info = {
                            "signature": transfer.get("signature"),
                            "block_time": transfer.get("blockTime"),
                            "slot": transfer.get("slot"),
                            "from_address": transfer.get("fromAddress"),
                            "to_address": transfer.get("toAddress"),
                            "amount": transfer.get("amount"),
                            "decimals": transfer.get("decimals"),
                            "ui_amount": transfer.get("uiAmount"),
                            "status": transfer.get("status"),
                            "fee": transfer.get("fee")
                        }
                        transfers.append(transfer_info)
                
                pagination = data.get("pagination", {})
                total_count = pagination.get("total", len(transfers))
                
                return {
                    "transfers": transfers,
                    "total": total_count,
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "total": total_count,
                        "has_next": offset + len(transfers) < total_count
                    }
                }
            else:
                return {"transfers": [], "total": 0}
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting token transfers from Solscan for {token_address}: {str(e)}")
            raise SolscanAPIError(f"Failed to get token transfers: {str(e)}")
    
    async def get_market_data(self, token_address: str) -> Dict[str, Any]:
        """Get market data for a token using v2.0 API"""
        try:
            # Use get_token_info which includes market data in v2.0
            token_info = await self.get_token_info(token_address)
            
            if token_info:
                return {
                    "price": token_info.get("price"),
                    "volume_24h": token_info.get("volume_24h"),
                    "market_cap": token_info.get("market_cap"),
                    "price_change_24h": token_info.get("price_change_24h"),
                    "holder_count": token_info.get("holder_count"),
                    "supply": token_info.get("supply"),
                    "source": "solscan_v2"
                }
            else:
                raise SolscanAPIError("No token info available for market data")
            
        except SolscanAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting market data from Solscan for {token_address}: {str(e)}")
            raise SolscanAPIError(f"Failed to get market data: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Solscan API health using v2.0 endpoints"""
        try:
            start_time = time.time()
            
            if not self.api_key:
                return {
                    "healthy": False,
                    "api_key_configured": False,
                    "error": "Solscan API key not configured. Set SOLSCAN_API_KEY in .env file",
                    "base_url": self.base_url,
                    "response_time": 0.0,
                    "recommendation": "Get API key from https://pro.solscan.io"
                }
            
            # Test the v2.0 chaininfo endpoint
            logger.debug("Solscan health check: testing v2.0 /v2.0/chaininfo endpoint")
            
            try:
                network_stats = await self.get_network_stats()
                response_time = time.time() - start_time
                
                return {
                    "healthy": True,
                    "api_key_configured": True,
                    "base_url": self.base_url,
                    "response_time": response_time,
                    "test_data": network_stats,
                    "working_endpoint": "/v2.0/chaininfo",
                    "api_version": "v2.0"
                }
                
            except SolscanAPIError as e:
                response_time = time.time() - start_time
                error_msg = str(e)
                
                if "unauthorized" in error_msg.lower() or "forbidden" in error_msg.lower():
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": f"Authentication failed: {error_msg}",
                        "base_url": self.base_url,
                        "response_time": response_time,
                        "recommendation": "Check API key validity at https://pro.solscan.io"
                    }
                else:
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": f"API endpoint failed: {error_msg}",
                        "base_url": self.base_url,
                        "response_time": response_time,
                        "tested_endpoint": "/v2.0/chaininfo"
                    }
                
        except Exception as e:
            response_time = time.time() - start_time
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": f"Health check exception: {str(e)}",
                "base_url": self.base_url,
                "response_time": response_time
            }


# Convenience functions
async def get_solscan_client() -> SolscanClient:
    """Get configured Solscan client"""
    return SolscanClient()


async def check_solscan_health() -> Dict[str, Any]:
    """Check Solscan service health"""
    async with SolscanClient() as client:
        return await client.health_check()