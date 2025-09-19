import asyncio
import time
import json
from typing import Dict, Any, List, Optional
from loguru import logger
from datetime import datetime, timedelta

from app.services.service_manager import api_manager
from app.core.config import get_settings
from app.utils.cache import cache_manager
from app.services.analysis_storage import analysis_storage

settings = get_settings()


class TokenSnapshotService:
    """Token snapshot service - captures market data without security checks"""
    
    def __init__(self):
        self.cache = cache_manager
        self.cache_ttl = settings.REPORT_TTL_SECONDS
        self.snapshot_interval = getattr(settings, 'SNAPSHOT_INTERVAL_SECONDS', 3600)
        self.max_tokens_per_run = getattr(settings, 'SNAPSHOT_MAX_TOKENS_PER_RUN', 100)
        self.rate_limit_delay = getattr(settings, 'SNAPSHOT_RATE_LIMIT_DELAY', 1.0)
        self.default_security_status = getattr(settings, 'SNAPSHOT_SECURITY_STATUS', 'safe')
        self._running = False
        
    async def capture_token_snapshot(
        self, 
        token_address: str, 
        security_status: str = "safe", 
        security_data: Optional[Dict[str, Any]] = None,
        security_service_responses: Optional[Dict[str, Any]] = None,
        update_existing: bool = True
    ) -> Dict[str, Any]:
        """Capture a single token snapshot with enhanced data"""
        start_time = time.time()
        
        # Use consistent analysis_id based on token address only (NO TIMESTAMP)
        analysis_id = f"snapshot_{token_address[:8]}"
        
        # Check for existing snapshot
        existing_snapshot = None
        snapshot_generation = 1
        is_first_snapshot = True
        
        if update_existing:
            existing_snapshot = await self._get_latest_snapshot(token_address)
            if existing_snapshot:
                snapshot_generation = existing_snapshot.get("snapshot_generation", 0) + 1
                is_first_snapshot = False
                logger.info(f"Updating existing snapshot for {token_address} (generation {snapshot_generation})")
        
        # Initialize service responses (ONLY security services stored)
        service_responses = {}
        
        # Include security services ONLY on first snapshot
        if is_first_snapshot and security_service_responses:
            logger.info(f"First snapshot - storing security service responses: {list(security_service_responses.keys())}")
            service_responses.update(security_service_responses)
        else:
            if not is_first_snapshot:
                logger.info(f"Update snapshot - skipping security services storage (generation {snapshot_generation})")
        
        # Initialize response structure
        snapshot_response = {
            "analysis_id": analysis_id,
            "token_address": token_address,
            "timestamp": datetime.utcnow().isoformat(),
            "source_event": "snapshot_scheduled",
            "analysis_type": "snapshot",
            "snapshot_generation": snapshot_generation,
            "warnings": [],
            "errors": [],
            "data_sources": list(service_responses.keys()),
            "service_responses": service_responses,
            "security_analysis": {
                "security_status": security_status,
                "overall_safe": security_status == "safe",
                "critical_issues": security_data.get("critical_issues", []) if security_data else [],
                "warnings": security_data.get("warnings", []) if security_data else [],
                "note": "Security validation bypassed for snapshot"
            },
            "metadata": {
                "processing_time_seconds": 0,
                "data_sources_available": 0,
                "services_attempted": 0,
                "services_successful": len(service_responses),
                "security_check_passed": True,
                "analysis_stopped_at_security": False,
                "ai_analysis_completed": False,
                "snapshot_update": update_existing,
                "is_first_snapshot": is_first_snapshot,
                "previous_snapshot_id": existing_snapshot.get("analysis_id") if existing_snapshot else None
            }
        }
        
        try:
            # ALWAYS run market analysis to get fresh data
            logger.info(f"Fetching fresh market data for snapshot")
            await self._run_market_analysis_services(token_address, snapshot_response)
            
            # Extract base OnChainData
            onchain_data = self._extract_market_data(snapshot_response["service_responses"])
            
            # ADD whales/volatility/snipers analysis
            volatility_data = self._calculate_simple_volatility(snapshot_response["service_responses"].get("birdeye", {}))
            whale_activity_1h = self._analyze_whale_activity_1h(snapshot_response["service_responses"].get("birdeye", {}))
            sniper_data = self._detect_sniper_patterns(snapshot_response["service_responses"].get("goplus", {}))
            
            # Enhance OnChainData with analysis results
            onchain_data.update({
                # Volatility analysis
                "volatility_percent": volatility_data,
                "volatility_risk": "high" if volatility_data and volatility_data > 30 else "medium" if volatility_data and volatility_data > 15 else "low",
                
                # Whale activity (exact format you requested)
                "whale_activity_1h": {
                    "count": whale_activity_1h.get("count", 0),
                    "total_inflow_usd": whale_activity_1h.get("total_inflow_usd", 0),
                    "addresses": whale_activity_1h.get("addresses", [])
                },
                
                # Sniper detection
                "sniper_detection": {
                    "pattern_detected": sniper_data.get("pattern_detected", False),
                    "similar_holders": sniper_data.get("similar_holders", 0),
                    "sniper_risk": sniper_data.get("sniper_risk", "unknown")
                }
            })
            
            # Store enhanced OnChainData
            snapshot_response["metrics"] = {
                "market_data": onchain_data  # Complete OnChainData with all analysis
            }
            
            # Update metadata
            snapshot_response["metadata"]["data_sources_available"] = len(service_responses)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            snapshot_response["metadata"]["processing_time_seconds"] = round(processing_time, 3)
            
            # Store in ChromaDB
            asyncio.create_task(self._store_snapshot_async(snapshot_response))
            
            logger.info(f"✅ Snapshot captured for {token_address} in {processing_time:.2f}s (gen {snapshot_generation}, ID: {analysis_id})")
            return snapshot_response
            
        except Exception as e:
            # Calculate processing time here too
            processing_time = time.time() - start_time
            logger.error(f"❌ Snapshot failed for {token_address}: {str(e)}")
            
            snapshot_response["errors"].append(str(e))
            snapshot_response["metadata"]["processing_time_seconds"] = round(processing_time, 3)
            return snapshot_response
        
    async def _generate_combined_metrics(self, security_responses: Dict[str, Any], market_responses: Dict[str, Any], token_address: str) -> Dict[str, Any]:
        """Generate complete metrics - clean structure with backward compatibility"""
        try:
            # Extract OnChainData structure from all services
            onchain_data = self._extract_market_data({**security_responses, **market_responses})
            
            # Add whale analysis to OnChainData whales1h field
            whale_activity_1h = self._analyze_whale_activity_1h(market_responses.get("birdeye", {}))
            onchain_data["whales1h"] = {
                "whaleCount": whale_activity_1h.get("count", 0),
                "whaleVolume": float(whale_activity_1h.get("total_inflow_usd", 0)),
                "whaleVolumePercent": 0.0,
                "largestWhaleAmount": 0.0,
                "avgWhaleSize": float(whale_activity_1h.get("total_inflow_usd", 0)) / max(whale_activity_1h.get("count", 1), 1),
                "whaleRisk": "high" if whale_activity_1h.get("count", 0) > 5 else "medium" if whale_activity_1h.get("count", 0) > 2 else "low"
            }
            
            # Use existing analysis methods
            volatility = self._calculate_simple_volatility(market_responses.get("birdeye", {}))
            sniper_detection = self._detect_sniper_patterns(security_responses.get("goplus", {}))
            token_info = self._extract_token_info_from_security(security_responses)
            
            return {
                "market_data": onchain_data,  # Complete OnChainData with security fields inside
                "token_info": token_info,
                "volatility": {
                    "recent_volatility_percent": volatility,
                    "volatility_available": volatility is not None,
                    "volatility_risk": "high" if volatility and volatility > 30 else "medium" if volatility and volatility > 15 else "low",
                    "trades_analyzed": len(market_responses.get("birdeye", {}).get("trades", {}).get("items", []))
                },
                "whale_activity_1h": whale_activity_1h,
                "sniper_detection": sniper_detection
            }
            
        except Exception as e:
            logger.warning(f"Error generating combined metrics: {e}")
            return {
                "market_data": {},
                "token_info": {},
                "volatility": {},
                "whale_activity_1h": {"count": 0, "total_inflow_usd": 0, "addresses": []},
                "sniper_detection": {}
            }
    
    async def run_scheduled_snapshots(self) -> Dict[str, Any]:
        """Run scheduled snapshots for multiple tokens"""
        if self._running:
            logger.warning("Snapshot run already in progress")
            return {"status": "already_running"}
        
        self._running = True
        start_time = time.time()
        
        try:
            logger.info(f"🔄 Starting scheduled snapshot run (max {self.max_tokens_per_run} tokens)")
            
            # Get tokens for snapshot (sorted by oldest first)
            tokens = await self._get_tokens_for_snapshot()
            if not tokens:
                logger.info("No tokens found for snapshot - this is normal if no snapshots exist yet")
                return {"status": "no_tokens", "tokens_processed": 0, "message": "No existing snapshots to update"}
            
            logger.info(f"Processing {len(tokens)} tokens for snapshots (oldest snapshots first)")
            
            results = {
                "status": "completed",
                "tokens_processed": 0,
                "successful": 0,
                "failed": 0,
                "errors": [],
                "processing_time": 0
            }
            
            # Process each token
            for i, token_address in enumerate(tokens):
                try:
                    logger.debug(f"Processing token {i+1}/{len(tokens)}: {token_address}")
                    
                    snapshot = await self.capture_token_snapshot(token_address, update_existing=True)
                    results["tokens_processed"] += 1
                    
                    if snapshot.get("errors"):
                        results["failed"] += 1
                        results["errors"].extend(snapshot["errors"])
                        logger.warning(f"Snapshot failed for {token_address}: {snapshot['errors']}")
                    else:
                        results["successful"] += 1
                        logger.debug(f"Snapshot successful for {token_address}")
                    
                    # Rate limiting
                    if i < len(tokens) - 1:  # Don't delay after last token
                        await asyncio.sleep(self.rate_limit_delay)
                        
                except Exception as e:
                    logger.error(f"Error processing token {token_address}: {str(e)}")
                    results["failed"] += 1
                    results["errors"].append(f"{token_address}: {str(e)}")
            
            processing_time = time.time() - start_time
            results["processing_time"] = round(processing_time, 2)
            
            logger.info(
                f"✅ Snapshot run completed in {processing_time:.2f}s: "
                f"{results['successful']} successful, {results['failed']} failed"
            )
            
            return results
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Scheduled snapshot run failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "processing_time": round(processing_time, 2)
            }
        finally:
            self._running = False
    
    async def _get_latest_snapshot(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Get latest snapshot for a token from ChromaDB"""
        try:
            results = await analysis_storage.search_analyses(
                query=f"token snapshot {token_address}",
                limit=1,
                filters={"token_address": token_address, "doc_type": "token_snapshot"}
            )
            
            if results and len(results) > 0:
                document = results[0]
                metadata = document.get("metadata", {})
                analysis_id = metadata.get("analysis_id")
                
                # CONVERT TO INT - metadata stores as string
                snapshot_generation = int(metadata.get("snapshot_generation", "0"))
                timestamp = metadata.get("timestamp", 0)
                
                if not analysis_id:
                    analysis_id = f"snapshot_{token_address[:8]}"
                    logger.info(f"Generated fallback analysis_id: {analysis_id}")
                
                return {
                    "analysis_id": analysis_id,
                    "snapshot_generation": snapshot_generation,  # Now it's an int
                    "timestamp": timestamp
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting latest snapshot for {token_address}: {e}")
            return None
    
    async def _get_tokens_for_snapshot(self) -> List[str]:
        """Get list of tokens that need snapshots, sorted by oldest first"""
        try:
            logger.info("Searching for existing snapshots in ChromaDB...")
            
            # Search for existing snapshots, not analyses
            results = await analysis_storage.search_analyses(
                query="snapshot",
                limit=self.max_tokens_per_run * 3,  # Get more to sort and filter
                filters={"doc_type": "token_snapshot"}
            )
            
            logger.info(f"Found {len(results)} snapshot results from ChromaDB")
            
            if not results:
                logger.info("No existing snapshots found")
                return []
            
            # Extract tokens with their timestamps for sorting
            token_data = []
            seen = set()
            
            for result in results:
                metadata = result.get("metadata", {})
                token_address = metadata.get("token_address")
                timestamp = metadata.get("timestamp", "")
                
                if token_address and token_address not in seen:
                    token_data.append({
                        "token_address": token_address,
                        "timestamp": timestamp
                    })
                    seen.add(token_address)
            
            # Sort by timestamp (oldest first) so oldest snapshots get updated first
            token_data.sort(key=lambda x: x["timestamp"])
            
            # Extract just the token addresses, limited by max_tokens_per_run
            tokens = [item["token_address"] for item in token_data[:self.max_tokens_per_run]]
            
            logger.info(f"Returning {len(tokens)} tokens for snapshot updates (oldest first)")
            for i, token in enumerate(tokens[:3]):  # Log first 3 for debugging
                logger.debug(f"Token {i+1}: {token}")
            
            return tokens
            
        except Exception as e:
            logger.warning(f"Error getting tokens for snapshot (non-fatal): {e}")
            return []  # Return empty list instead of throwing error
    
    async def _run_market_analysis_services(self, token_address: str, snapshot_response: Dict[str, Any]) -> None:
        """Run market analysis services (same as comprehensive analysis but no security)"""

        # BIRDEYE - Sequential processing
        birdeye_data = {}
        if api_manager.clients.get("birdeye"):
            try:
                birdeye_client = api_manager.clients["birdeye"]
                
                # Price data
                price_data = await birdeye_client.get_token_price(
                    token_address, include_liquidity=True, check_liquidity=100
                )
                if price_data:
                    birdeye_data["price"] = price_data
                
                await asyncio.sleep(1.0)  # Rate limiting
                
                # Trades data
                trades_data = await birdeye_client.get_token_trades(
                    token_address, sort_type="desc", limit=20
                )
                if trades_data:
                    birdeye_data["trades"] = trades_data
                
                if birdeye_data:
                    snapshot_response["service_responses"]["birdeye"] = birdeye_data
                    snapshot_response["data_sources"].append("birdeye")
                    snapshot_response["metadata"]["services_attempted"] += 1
                    snapshot_response["metadata"]["services_successful"] += 1
                    
            except Exception as e:
                logger.warning(f"Birdeye failed: {str(e)}")
                snapshot_response["warnings"].append(f"Birdeye failed: {str(e)}")
        
        # OTHER SERVICES - Parallel
        other_tasks = {}
        
        if api_manager.clients.get("helius"):
            other_tasks["helius_supply"] = self._safe_service_call(
                api_manager.clients["helius"].get_token_supply, token_address
            )
            snapshot_response["metadata"]["services_attempted"] += 1
        
        if api_manager.clients.get("solanafm"):
            other_tasks["solanafm_token"] = self._safe_service_call(
                api_manager.clients["solanafm"].get_token_info, token_address
            )
            snapshot_response["metadata"]["services_attempted"] += 1
        
        if api_manager.clients.get("dexscreener"):
            other_tasks["dexscreener_pairs"] = self._safe_service_call(
                api_manager.clients["dexscreener"].get_token_pairs, token_address, "solana"
            )
            snapshot_response["metadata"]["services_attempted"] += 1
        
        # Execute other services
        if other_tasks:
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*other_tasks.values(), return_exceptions=True),
                    timeout=20.0
                )
                
                task_names = list(other_tasks.keys())
                for i, task_name in enumerate(task_names):
                    try:
                        result = results[i] if i < len(results) else None
                        service_name = task_name.split("_")[0]
                        
                        if isinstance(result, Exception) or result is None:
                            continue
                        
                        if service_name not in snapshot_response["service_responses"]:
                            snapshot_response["service_responses"][service_name] = {}
                        
                        snapshot_response["service_responses"][service_name][task_name.split("_", 1)[1]] = result
                        
                        if service_name not in snapshot_response["data_sources"]:
                            snapshot_response["data_sources"].append(service_name)
                            snapshot_response["metadata"]["services_successful"] += 1
                        
                    except Exception as e:
                        logger.warning(f"Error processing {task_name}: {str(e)}")
                        
            except asyncio.TimeoutError:
                logger.warning("Market analysis services timed out")
                snapshot_response["warnings"].append("Some market services timed out")
    
    def _calculate_simple_volatility(self, birdeye_data: Dict[str, Any]) -> Optional[float]:
        """Calculate simple volatility from recent trades"""
        try:
            trades_data = birdeye_data.get("trades", {})
            if isinstance(trades_data, dict):
                trades = trades_data.get("items", [])
            else:
                trades = trades_data if isinstance(trades_data, list) else []
                
            if not trades or len(trades) < 5:
                return None
            
            # Get token address from price data
            price_data = birdeye_data.get("price", {})
            token_address = price_data.get("address") if price_data else None
            
            if not token_address:
                logger.warning("Unable to extract token address from Birdeye data")
                return None

            # Extract prices from recent trades
            prices = []
            for trade in trades[:20]:  # Use up to 20 recent trades
                if not isinstance(trade, dict):
                    continue
                    
                # Determine which side of the trade contains our token
                source = "from" if trade.get("from", {}).get("address") == token_address else "to"
                
                if source in trade and isinstance(trade[source], dict):
                    try:
                        price = float(trade[source].get("price", 0))
                        if price > 0:
                            prices.append(price)
                    except (ValueError, TypeError):
                        continue
            
            if len(prices) < 3:
                logger.warning(f"Insufficient price data: only {len(prices)} valid prices found")
                return None
            
            # Simple volatility = (max_price - min_price) / avg_price * 100
            max_price = max(prices)
            min_price = min(prices)
            avg_price = sum(prices) / len(prices)
            
            volatility = ((max_price - min_price) / avg_price) * 100 if avg_price > 0 else 0
            
            logger.info(f"Simple volatility calculated: {volatility:.2f}% from {len(prices)} trades")
            return round(volatility, 2)
            
        except Exception as e:
            logger.warning(f"Volatility calculation failed: {e}")
            return None

    def _analyze_whale_activity_1h(self, birdeye_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze whale activity in last 60 minutes from Birdeye trades - using bot service logic"""
        try:
            trades_data = birdeye_data.get("trades", {})
            trades = trades_data.get("items", []) if isinstance(trades_data, dict) else trades_data
            
            if not trades:
                return {
                    "count": 0,
                    "total_inflow_usd": 0,
                    "addresses": []
                }
            
            current_time = time.time()
            one_hour_ago = current_time - 3600
            
            whales = []
            total_volume = 0.0
            whale_addresses = []
            
            for trade in trades:
                try:
                    # Get trade timestamp
                    trade_time = trade.get("block_timestamp", current_time)
                    if trade_time < one_hour_ago:
                        continue
                    
                    # Only analyze BUY transactions
                    if trade.get("tx_type") != "buy" and trade.get("side") != "buy":
                        continue
                    
                    # Get trade size in USD (same logic as bot service)
                    trade_size_usd = float(trade.get("from", {}).get("ui_amount", 0)) * float(trade.get("from", {}).get("price", 0))
                    total_volume += trade_size_usd
                    
                    # Whale threshold: $800+ (matching bot service)
                    if trade_size_usd >= 800:
                        whales.append(trade_size_usd)
                        
                        # Get wallet address
                        wallet = trade.get("owner")
                        if wallet and wallet not in [w["wallet"] for w in whale_addresses]:
                            whale_addresses.append({
                                "wallet": f"{wallet[:6]}...{wallet[-4:]}" if len(wallet) > 10 else wallet,
                                "amount_usd": int(trade_size_usd)
                            })
                            
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Error processing trade: {e}")
                    continue
            
            # Calculate totals
            whale_count = len(whales)
            whale_volume = sum(whales)
            
            # Sort addresses by amount (highest first) and limit to top 10
            whale_addresses.sort(key=lambda x: x["amount_usd"], reverse=True)
            whale_addresses = whale_addresses[:10]
            
            return {
                "count": whale_count,
                "total_inflow_usd": int(whale_volume),
                "addresses": whale_addresses
            }
            
        except Exception as e:
            logger.warning(f"Whale activity analysis failed: {e}")
            return {
                "count": 0,
                "total_inflow_usd": 0,
                "addresses": []
            }

    def _detect_sniper_patterns(self, goplus_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simple sniper pattern detection from holder distribution"""
        try:
            holders = goplus_data.get("holders", [])
            if not holders or len(holders) < 10:
                return {"sniper_risk": "unknown", "pattern_detected": False, "similar_holders": 0}
            
            # Simple pattern: many holders with very similar percentages
            percentages = []
            for holder in holders[:50]:  # Check top 50 holders
                if isinstance(holder, dict):
                    try:
                        percent_raw = holder.get("percent", "0")
                        percent = float(percent_raw)
                        if 0.1 <= percent <= 5.0:  # Sniper range
                            percentages.append(percent)
                    except (ValueError, TypeError):
                        continue
            
            if len(percentages) < 5:
                return {"sniper_risk": "low", "pattern_detected": False, "similar_holders": 0}
            
            # Simple pattern detection: count very similar percentages
            similar_count = 0
            for i, p1 in enumerate(percentages):
                for p2 in percentages[i+1:]:
                    if abs(p1 - p2) < 0.05:  # Very similar percentages (within 0.05%)
                        similar_count += 1
            
            # Risk assessment based on similar holder count
            if similar_count > 10:
                sniper_risk = "high"
                pattern_detected = True
            elif similar_count > 5:
                sniper_risk = "medium" 
                pattern_detected = True
            else:
                sniper_risk = "low"
                pattern_detected = False
            
            logger.info(f"Sniper analysis: {similar_count} similar holder pairs, risk: {sniper_risk}")
            
            return {
                "sniper_risk": sniper_risk,
                "pattern_detected": pattern_detected,
                "similar_holders": similar_count
            }
            
        except Exception as e:
            logger.warning(f"Sniper pattern detection failed: {e}")
            return {"sniper_risk": "unknown", "pattern_detected": False, "similar_holders": 0}
        
    def _extract_token_name_symbol(self, snapshot_response: Dict[str, Any]) -> tuple[str, str]:
        """Extract token name and symbol from snapshot service responses"""
        try:
            service_responses = snapshot_response.get("service_responses", {})
            
            # Try Solsniffer first (most reliable for token metadata)
            solsniffer_data = service_responses.get("solsniffer", {})
            if solsniffer_data:
                name = solsniffer_data.get("tokenName")
                symbol = solsniffer_data.get("tokenSymbol")
                if name and symbol:
                    return name, symbol
            
            # Try Helius metadata
            helius_data = service_responses.get("helius", {})
            if helius_data:
                metadata = helius_data.get("metadata", {})
                if metadata:
                    onchain = metadata.get("onChainMetadata", {})
                    if onchain:
                        meta_data = onchain.get("metadata", {})
                        if meta_data:
                            data = meta_data.get("data", {})
                            name = data.get("name")
                            symbol = data.get("symbol")
                            if name and symbol:
                                return name, symbol
            
            # Try SolanaFM
            solanafm_data = service_responses.get("solanafm", {})
            if solanafm_data:
                token_data = solanafm_data.get("token", {})
                if token_data:
                    name = token_data.get("name")
                    symbol = token_data.get("symbol")
                    if name and symbol:
                        return name, symbol
            
            # Try DexScreener
            dexscreener_data = service_responses.get("dexscreener", {})
            if dexscreener_data:
                pairs_data = dexscreener_data.get("pairs", {})
                if pairs_data:
                    pairs = pairs_data.get("pairs", [])
                    if pairs and len(pairs) > 0:
                        pair = pairs[0]
                        base_token = pair.get("baseToken", {})
                        name = base_token.get("name")
                        symbol = base_token.get("symbol")
                        if name and symbol:
                            return name, symbol
            
            # Fallback defaults
            token_address = snapshot_response.get("token_address", "")
            return "Unknown Token", token_address[:4].upper() if token_address else "N/A"
            
        except Exception as e:
            logger.warning(f"Error extracting token name/symbol: {e}")
            token_address = snapshot_response.get("token_address", "")
            return "Unknown Token", token_address[:4].upper() if token_address else "N/A"

    def _extract_market_data(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Extract market data from service responses"""
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
            "volume1h": None,
            "volume5min": None,
            
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
            
            # Data quality
            "lastUpdated": time.time(),
            "apiErrors": []
        }

        try:
            # 1. BIRDEYE DATA
            birdeye_data = service_responses.get("birdeye", {})
            if birdeye_data and birdeye_data.get("price"):
                price_data = birdeye_data["price"]
                
                if price_data.get("value") is not None:
                    onchain_data["currentPriceUSD"] = float(price_data["value"])
                
                if price_data.get("liquidity") is not None:
                    onchain_data["liquidityUSD"] = float(price_data["liquidity"])
                
                if price_data.get("volume_24h") is not None:
                    onchain_data["volume24h"] = float(price_data["volume_24h"])
                
                if price_data.get("price_change_24h") is not None:
                    onchain_data["priceChange24h"] = float(price_data["price_change_24h"])
                
                if price_data.get("market_cap") is not None:
                    onchain_data["marketCapUSD"] = float(price_data["market_cap"])
            
            # 2. DEXSCREENER DATA
            dexscreener_data = service_responses.get("dexscreener", {})
            if dexscreener_data and dexscreener_data.get("pairs", {}).get("pairs"):
                pairs = dexscreener_data["pairs"]["pairs"]
                if len(pairs) > 0:
                    pair = pairs[0]
                    
                    onchain_data["poolExists"] = True
                    onchain_data["poolAddress"] = pair.get("pairAddress", "")
                    onchain_data["dexType"] = pair.get("dexId", "unknown")
                    
                    # Pool age
                    if pair.get("pairCreatedAt"):
                        try:
                            created_at = int(pair["pairCreatedAt"]) / 1000
                            onchain_data["poolAge"] = int(time.time() - created_at)
                        except:
                            pass
                    
                    # Reserves
                    liquidity = pair.get("liquidity", {})
                    if liquidity.get("quote") is not None:
                        onchain_data["solReserve"] = float(liquidity["quote"])
                    if liquidity.get("base") is not None:
                        onchain_data["tokenReserve"] = float(liquidity["base"])
                    
                    # Volume data
                    volume_data = pair.get("volume", {})
                    if volume_data:
                        if volume_data.get("h24") is not None and onchain_data["volume24h"] == 0:
                            onchain_data["volume24h"] = float(volume_data["h24"])
                        if volume_data.get("h1") is not None:
                            onchain_data["volume1h"] = float(volume_data["h1"])
                        if volume_data.get("m5") is not None:
                            onchain_data["volume5min"] = float(volume_data["m5"])
                    
                    # Transaction counts
                    if pair.get("txns"):
                        txns = pair["txns"]
                        if txns.get("h24") and txns["h24"].get("buys") is not None:
                            onchain_data["txCount24h"] = int(txns["h24"]["buys"]) + int(txns["h24"]["sells"])
                        if txns.get("h1") and txns["h1"].get("buys") is not None:
                            onchain_data["txCount1h"] = int(txns["h1"]["buys"]) + int(txns["h1"]["sells"])
                        if txns.get("m5") and txns["m5"].get("buys") is not None:
                            onchain_data["txCount5min"] = int(txns["m5"]["buys"]) + int(txns["m5"]["sells"])
                    
                    # Fallback price/volume/mcap
                    if onchain_data["currentPriceUSD"] is None and pair.get("priceUsd"):
                        onchain_data["currentPriceUSD"] = float(pair["priceUsd"])
                    if onchain_data["marketCapUSD"] is None and pair.get("marketCap"):
                        onchain_data["marketCapUSD"] = float(pair["marketCap"])

            # 3. GOPLUS SECURITY DATA
            goplus_data = service_responses.get("goplus", {})
            if goplus_data:
                # LP locked
                lp_locked = goplus_data.get("lp_locked")
                onchain_data["lpLocked"] = lp_locked == "1" if lp_locked else False
                
                # LP locked percentage
                if goplus_data.get("lp_locked_percent") is not None:
                    onchain_data["lpLockedPercent"] = float(goplus_data["lp_locked_percent"])
                
                # Top holder
                holders = goplus_data.get("holders", [])
                if holders and len(holders) > 0:
                    top_holder = holders[0]
                    if top_holder.get("percent") is not None:
                        onchain_data["topHolderPercent"] = float(top_holder["percent"])
                
                # Holder count
                if goplus_data.get("holder_count"):
                    try:
                        holder_count = goplus_data["holder_count"]
                        if isinstance(holder_count, str):
                            holder_count = holder_count.replace(",", "")
                        onchain_data["holderCount"] = int(holder_count)
                    except:
                        pass
                
                # Token tax
                buy_tax = goplus_data.get("buy_tax", "0") or "0"
                sell_tax = goplus_data.get("sell_tax", "0") or "0"
                try:
                    max_tax = max(float(buy_tax), float(sell_tax))
                    onchain_data["tokenTax"] = max_tax
                except:
                    onchain_data["tokenTax"] = 0.0
            
            # 4. TOKEN METADATA (multiple sources)
            # Try DexScreener first
            if dexscreener_data and dexscreener_data.get("pairs", {}).get("pairs"):
                pair = dexscreener_data["pairs"]["pairs"][0]
                base_token = pair.get("baseToken", {})
                if base_token.get("name"):
                    onchain_data["name"] = base_token["name"]
                if base_token.get("symbol"):
                    onchain_data["symbol"] = base_token["symbol"]
            
            # Try SolSniffer if no name/symbol yet
            if not onchain_data["name"] or not onchain_data["symbol"]:
                solsniffer_data = service_responses.get("solsniffer", {})
                if solsniffer_data:
                    if not onchain_data["name"] and solsniffer_data.get("tokenName"):
                        onchain_data["name"] = solsniffer_data["tokenName"]
                    if not onchain_data["symbol"] and solsniffer_data.get("tokenSymbol"):
                        onchain_data["symbol"] = solsniffer_data["tokenSymbol"]
            
            # 5. HELIUS SUPPLY DATA
            helius_data = service_responses.get("helius", {})
            if helius_data and helius_data.get("supply"):
                supply_data = helius_data["supply"]
                supply_value = supply_data.get("value", {})
                if supply_value.get("amount") and supply_value.get("decimals") is not None:
                    raw_supply = int(supply_value["amount"])
                    decimals = int(supply_value["decimals"])
                    onchain_data["supply"] = raw_supply / (10 ** decimals)
                    onchain_data["decimals"] = decimals
                    
                    # Calculate fully diluted market cap
                    if onchain_data["currentPriceUSD"] > 0:
                        onchain_data["fullyDilutedMarketCap"] = onchain_data["supply"] * onchain_data["currentPriceUSD"]
            
            logger.info(f"OnChain data extracted: price=${onchain_data['currentPriceUSD']}, liquidity=${onchain_data['liquidityUSD']}, pool={onchain_data['poolExists']}")
            return onchain_data
            
        except Exception as e:
            logger.error(f"Error extracting onchain data: {e}")
            onchain_data["apiErrors"].append(f"Extraction error: {str(e)}")
            return onchain_data
    
    def _extract_token_info_from_security(self, security_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Extract token info from security service responses"""
        token_info = {
            "holders_count": None,
            "dev_holdings_percent": None,
            "total_supply": None,
            "metadata_completeness": False
        }
        
        try:
            # Get holders from GOplus
            goplus_data = security_responses.get("goplus", {})
            if goplus_data and goplus_data.get("holder_count"):
                try:
                    holder_count_raw = goplus_data["holder_count"]
                    if isinstance(holder_count_raw, str):
                        clean = holder_count_raw.replace(",", "").replace(" ", "")
                        token_info["holders_count"] = int(clean)
                    else:
                        token_info["holders_count"] = int(holder_count_raw)
                except (ValueError, TypeError):
                    pass
            
            # Get dev holdings from RugCheck
            rugcheck_data = security_responses.get("rugcheck", {})
            if rugcheck_data and rugcheck_data.get("creator_analysis"):
                creator_balance = rugcheck_data["creator_analysis"].get("creator_balance")
                total_supply = rugcheck_data.get("total_supply")
                if creator_balance and total_supply:
                    try:
                        token_info["dev_holdings_percent"] = (float(creator_balance) / float(total_supply)) * 100
                        token_info["total_supply"] = float(total_supply)
                    except (ValueError, TypeError):
                        pass
            
            return token_info
            
        except Exception as e:
            logger.warning(f"Error extracting token info from security: {e}")
            return token_info
        
    async def _safe_service_call(self, service_func, *args, **kwargs):
        """Execute service call with error handling"""
        try:
            result = await service_func(*args, **kwargs) if kwargs else await service_func(*args)
            return result if result is not None else None
        except Exception as e:
            logger.error(f"{service_func.__name__} failed: {str(e)}")
            return None
        
    async def _store_snapshot_async(self, snapshot_response: Dict[str, Any]) -> None:
        """Store snapshot in ChromaDB with OnChainData as JSON content"""
        try:
            analysis_id = snapshot_response["analysis_id"]
            token_address = snapshot_response["token_address"]
            
            from app.utils.chroma_client import get_chroma_client
            chroma_client = await get_chroma_client()
            
            if not chroma_client.is_connected():
                logger.warning("ChromaDB not available")
                return
                
            doc_id = f"snapshot_{token_address[:8]}"
            
            # Store the OnChainData as JSON content
            onchain_data = snapshot_response.get("metrics", {}).get("market_data", {})
            content = json.dumps(onchain_data, default=str)
            
            # Basic metadata for searching
            metadata = {
                "doc_type": "token_snapshot",
                "analysis_id": analysis_id,
                "token_address": token_address,
                "timestamp": snapshot_response.get("timestamp", ""),
                "snapshot_generation": str(snapshot_response.get("snapshot_generation", 1))
            }
            
            # Update or create
            existing = chroma_client._collection.get(ids=[doc_id])
            if existing and existing.get('ids'):
                chroma_client._collection.update(ids=[doc_id], documents=[content], metadatas=[metadata])
                logger.info(f"✅ UPDATED snapshot: {doc_id}")
            else:
                await chroma_client.add_document(content=content, metadata=metadata, doc_id=doc_id)
                logger.info(f"✅ CREATED snapshot: {doc_id}")
                
        except Exception as e:
            logger.error(f"Failed to store snapshot: {str(e)}")


# Global snapshot service instance
token_snapshot_service = TokenSnapshotService()


async def capture_single_snapshot(
    token_address: str, 
    security_status: str = "safe", 
    security_data: Optional[Dict[str, Any]] = None,
    security_service_responses: Optional[Dict[str, Any]] = None,
    update_existing: bool = True
) -> Dict[str, Any]:
    """Capture a single token snapshot"""
    return await token_snapshot_service.capture_token_snapshot(
        token_address=token_address,
        security_status=security_status,
        security_data=security_data,
        security_service_responses=security_service_responses,
        update_existing=update_existing
    )


async def run_scheduled_snapshots() -> Dict[str, Any]:
    """Run scheduled snapshots for multiple tokens"""
    return await token_snapshot_service.run_scheduled_snapshots()