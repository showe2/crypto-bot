import asyncio
import aiohttp
import time
import json
import base58
from typing import Dict, Any, List, Optional
from loguru import logger

from app.core.config import get_settings

settings = get_settings()

# Import Solana libraries for wallet signing
try:
    from solders.keypair import Keypair
    from solders.signature import Signature
    SOLANA_AVAILABLE = True
except ImportError:
    logger.warning("Solana libraries not available - RugCheck authentication will be limited")
    SOLANA_AVAILABLE = False


class RugCheckAPIError(Exception):
    """RugCheck API specific errors"""
    pass


class RugCheckClient:
    """RugCheck API client for token security analysis and rug pull detection"""
    
    def __init__(self):
        self.wallet_private_key = settings.WALLET_SECRET_KEY
        self.base_url = settings.RUGCHECK_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.3  # 300ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        # JWT token management
        self._access_token = None
        self._token_expiry = 0
        self._wallet = None
        
        if not self.wallet_private_key:
            logger.warning("RugCheck requires WALLET_SECRET_KEY for authentication")
        elif not SOLANA_AVAILABLE:
            logger.warning("Solana libraries not available - RugCheck authentication disabled")
    
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
    
    
    def _initialize_wallet(self):
        """Initialize Solana wallet from private key"""
        if not SOLANA_AVAILABLE or not self.wallet_private_key:
            return None
            
        try:
            self._wallet = Keypair.from_base58_string(self.wallet_private_key)
            logger.debug(f"RugCheck wallet initialized")
            return self._wallet
        except Exception as e:
            logger.error(f"Failed to initialize RugCheck wallet: {str(e)}")
            return None
    
    def _sign_message(self, message: str) -> Dict[str, Any]:
        """Sign a message using the wallet's private key"""
        if not self._wallet:
            raise RugCheckAPIError("Wallet not initialized for RugCheck authentication")
        
        try:
            # Create message bytes and sign
            message_bytes = message.encode("utf-8")
            signature = self._wallet.sign_message(message_bytes)
            
            # Convert signature to base58 string, then to list of integers
            signature_base58 = str(signature)
            signature_data = list(base58.b58decode(signature_base58))
            
            return {
                "data": signature_data,
                "type": "ed25519"
            }
        except Exception as e:
            raise RugCheckAPIError(f"Failed to sign message: {str(e)}")
    
    async def _get_access_token(self) -> str:
        """Get JWT access token using wallet signature authentication"""
        # Check if we have a valid cached token
        current_time = time.time()
        if self._access_token and current_time < self._token_expiry:
            return self._access_token
        
        if not self.wallet_private_key:
            raise RugCheckAPIError("RugCheck requires WALLET_SECRET_KEY for authentication")
        
        if not SOLANA_AVAILABLE:
            raise RugCheckAPIError("Solana libraries not available for RugCheck authentication")
        
        # Initialize wallet if not done
        if not self._wallet:
            self._wallet = self._initialize_wallet()
            if not self._wallet:
                raise RugCheckAPIError("Failed to initialize wallet for RugCheck")
        
        await self._ensure_session()
        
        try:
            # Prepare the message to be signed
            timestamp = int(time.time() * 1000)  # Current time in milliseconds
            message_data = {
                "message": "Sign-in to Rugcheck.xyz",
                "timestamp": timestamp,
                "publicKey": str(self._wallet.pubkey())
            }
            message_json = json.dumps(message_data, separators=(',', ':'))
            
            # Sign the message
            signature = self._sign_message(message_json)
            
            # Prepare the request payload
            payload = {
                "signature": signature,
                "wallet": str(self._wallet.pubkey()),
                "message": message_data
            }
            
            # Make the authentication request
            async with self.session.post(
                self.base_url+"/auth/login/solana",
                headers={"Content-Type": "application/json"},
                json=payload
            ) as response:
                
                if response.status == 200:
                    response_data = await response.json()
                    
                    # Extract access token from response
                    access_token = response_data.get("accessToken") or response_data.get("token")
                    if access_token:
                        self._access_token = access_token
                        # Set expiry time (assume 1 hour if not provided)
                        expires_in = response_data.get("expiresIn", 3600)
                        self._token_expiry = current_time + expires_in

                        logger.debug("RugCheck JWT token obtained successfully")
                        return self._access_token
                    else:
                        raise RugCheckAPIError("No access token in authentication response")
                        
                elif response.status == 401:
                    error_text = await response.text()
                    raise RugCheckAPIError(f"Authentication failed: {error_text}")
                else:
                    error_text = await response.text()
                    raise RugCheckAPIError(f"Authentication error {response.status}: {error_text}")
                    
        except aiohttp.ClientError as e:
            raise RugCheckAPIError(f"Authentication request failed: {str(e)}")
        except Exception as e:
            raise RugCheckAPIError(f"Authentication error: {str(e)}")
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with JWT bearer token authentication"""
        await self._ensure_session()
        await self._rate_limit()

        if self._access_token is None or time.time() >= self._token_expiry:
            # Get access token
            try:
                access_token = await self._get_access_token()
            except RugCheckAPIError as e:
                raise RugCheckAPIError(f"Authentication failed: {str(e)}")
        else:
            access_token = self._access_token
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            **kwargs.pop("headers", {})
        }
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                content_type = response.headers.get('content-type', '').lower()
                
                logger.debug(f"RugCheck {method} {endpoint} - Status: {response.status}, Content-Type: {content_type}")
                
                if response.status == 200:
                    if 'application/json' in content_type:
                        response_data = await response.json()
                        return response_data
                    else:
                        response_text = await response.text()
                        logger.warning(f"Unexpected content type from RugCheck: {response_text}")
                        raise RugCheckAPIError(f"Expected JSON, got {content_type}")
                        
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"RugCheck rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                elif response.status == 401:
                    # Token might be expired, clear cache and retry once
                    if self._access_token:
                        self._access_token = None
                        self._token_expiry = 0
                        logger.debug("401 error, clearing token cache")
                        return await self._request(method, endpoint, **kwargs)
                    else:
                        raise RugCheckAPIError("Invalid RugCheck authentication")
                elif response.status == 404:
                    logger.debug(f"RugCheck 404 for {endpoint} - token may not be found")
                    return None
                else:
                    try:
                        error_text = await response.text()
                        raise RugCheckAPIError(f"HTTP {response.status}: {error_text[:200]}")
                    except:
                        raise RugCheckAPIError(f"HTTP {response.status}: Unknown error")
                    
        except asyncio.TimeoutError:
            raise RugCheckAPIError("RugCheck API request timeout")
        except aiohttp.ClientError as e:
            raise RugCheckAPIError(f"RugCheck client error: {str(e)}")
    
    async def check_token(self, token_address: str) -> Dict[str, Any]:
        """Check token for rug pull risks and security issues"""
        try:
            endpoint = f"/v1/tokens/{token_address}/report"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                logger.debug(f"No RugCheck data found for {token_address}")
                return None
            
            # Standardize the response format
            token_report = {
                "token_address": token_address,
                "token_program": response.get("scoretokenProgram"),
                "score": response.get("score"),
                "risks": response.get("risks", []),
                "token": response.get("token"),
                "token_type": response.get("tokenType"),
                "total_LP_providers": response.get("totalLPProviders"),
                "known_accounts": response.get("knownAccounts"),
                "events": response.get("events"),
                "verification": response.get("verification"),
                "rugged": response.get("rugged", False),
                "metadata": {
                    "token_meta" : response.get("tokenMeta"),
                    "file_meta": response.get("fileMeta")
                },
                "creator_analysis": {
                    "creator": response.get("creator"),
                    "creator_balance": response.get("creatorBalance"),
                    "creator_tokens": response.get("creatorTokens")
                },
                "lockers_data": {
                    "lockers": response.get("lockers"),
                    "locker_owners": response.get("lockerOwners")
                },
                "mint_analysis": {
                    "mint_authority": response.get("mintAuthority"),
                    "freeze_authority": response.get("freezeAuthority"),
                },
                "liquidity_analysis": {
                    "total_market_liquidity": response.get("totalMarketLiquidity"),
                    "total_stable_liquidity": response.get("totalStableLiquidity"),
                },
                "market_analysis": {
                    "markets": response.get("markets"),
                    "price": response.get("price"),
                    "holder_count": response.get("totalHolders"),
                    "transfer_fee": response.get("transfer_fee")
                },
                "insiders_analysis": {
                    "graph_insiders_detected": response.get("graphInsidersDetected"),
                    "insider_networks": response.get("insiderNetworks")
                },
                "detected_at": response.get("detectedAt"),
                "launchpad": response.get("launchpad")
            }
            
            return token_report
            
        except RugCheckAPIError:
            raise
        except Exception as e:
            logger.error(f"Error checking token {token_address} with RugCheck: {str(e)}")
            return None
    
    async def get_trending_tokens(self) -> List[Dict[str, Any]]:
        """Get trending tokens"""
        try:
            endpoint = "/v1/stats/trending"
            
            response = await self._request("GET", endpoint)
            
            if not response:
                logger.debug(f"No RugCheck data found")
                return []
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting trending tokens from RugCheck: {str(e)}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Check RugCheck API health"""
        try:
            start_time = time.time()
            
            if not self.wallet_private_key:
                return {
                    "healthy": False,
                    "api_key_configured": False,
                    "error": "RugCheck requires WALLET_SECRET_KEY for authentication",
                    "base_url": self.base_url,
                    "response_time": 0.0,
                    "recommendation": "Set WALLET_SECRET_KEY environment variable with your Solana wallet private key"
                }
            
            if not SOLANA_AVAILABLE:
                return {
                    "healthy": False,
                    "api_key_configured": bool(self.wallet_private_key),
                    "error": "Solana libraries not available",
                    "base_url": self.base_url,
                    "response_time": 0.0,
                    "recommendation": "Install Solana libraries: pip install solders"
                }
            
            # Test authentication by getting an access token
            try:
                access_token = await self._get_access_token()
                response_time = time.time() - start_time
                
                if access_token:
                    return {
                        "healthy": True,
                        "api_key_configured": True,
                        "base_url": self.base_url,
                        "response_time": response_time,
                        "authentication": "JWT Bearer Token",
                        "wallet_address": str(self._wallet.pubkey()) if self._wallet else None
                    }
                else:
                    raise RugCheckAPIError("No access token received")
                    
            except RugCheckAPIError as e:
                response_time = time.time() - start_time
                error_msg = str(e)
                
                if "authentication" in error_msg.lower() or "401" in error_msg:
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": "Authentication failed - check wallet private key",
                        "base_url": self.base_url,
                        "response_time": response_time
                    }
                else:
                    return {
                        "healthy": False,
                        "api_key_configured": True,
                        "error": error_msg,
                        "base_url": self.base_url,
                        "response_time": response_time
                    }
            
        except Exception as e:
            return {
                "healthy": False,
                "api_key_configured": bool(self.wallet_private_key),
                "error": str(e),
                "base_url": self.base_url
            }


# Convenience functions
async def get_rugcheck_client() -> RugCheckClient:
    """Get configured RugCheck client"""
    return RugCheckClient()


async def check_rugcheck_health() -> Dict[str, Any]:
    """Check RugCheck service health"""
    async with RugCheckClient() as client:
        return await client.health_check()