import asyncio
import time
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
        """Capture a single token snapshot - security responses + market metrics"""
        start_time = time.time()
        timestamp_unix = int(time.time())
        
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
        
        # Generate snapshot ID
        analysis_id = f"snapshot_{timestamp_unix}_{token_address[:8]}"
        
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
            "data_sources": list(service_responses.keys()),  # Only security services in data_sources
            "service_responses": service_responses,  # Only security responses stored
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
            # ALWAYS run market analysis to get fresh data (but don't store raw responses)
            logger.info(f"Fetching fresh market data for snapshot (not storing raw responses)")
            await self._run_market_analysis_services(token_address, snapshot_response)
            
            # Generate metrics from BOTH security and market data
            snapshot_response["metrics"] = await self._generate_combined_metrics(
                security_responses=service_responses,
                market_responses={},
                token_address=token_address
            )
            
            # Update metadata with market services attempted
            snapshot_response["metadata"]["data_sources_available"] = len(service_responses)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            snapshot_response["metadata"]["processing_time_seconds"] = round(processing_time, 3)
            
            # Cache and store
            try:
                await self.cache.set(key=analysis_id, value=snapshot_response, ttl=self.cache_ttl)
                snapshot_response["docx_cache_key"] = analysis_id
                snapshot_response["docx_expires_at"] = (datetime.utcnow() + timedelta(seconds=self.cache_ttl)).isoformat()
            except Exception as e:
                logger.warning(f"Failed to cache snapshot: {str(e)}")
                snapshot_response["warnings"].append(f"Caching failed: {str(e)}")
            
            # Store in ChromaDB
            asyncio.create_task(self._store_snapshot_async(snapshot_response))
            
            logger.info(f"✅ Snapshot captured for {token_address} in {processing_time:.2f}s (gen {snapshot_generation}, first: {is_first_snapshot}, security stored: {len(service_responses)})")
            return snapshot_response
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Snapshot failed for {token_address}: {str(e)}")
            
            snapshot_response["errors"].append(str(e))
            snapshot_response["metadata"]["processing_time_seconds"] = round(processing_time, 3)
            return snapshot_response
        
    async def _generate_combined_metrics(self, security_responses: Dict[str, Any], market_responses: Dict[str, Any], token_address: str) -> Dict[str, Any]:
        """Generate metrics from both security and market data"""
        try:
            # Market data from fresh API calls
            market_data = self._extract_market_data(market_responses)
            
            # Token info from security services
            token_info = self._extract_token_info_from_security(security_responses)
            
            # Enhanced metrics from security data
            volatility = self._calculate_simple_volatility(market_responses.get("birdeye", {}))
            whale_info = self._detect_simple_whales(security_responses.get("goplus", {}), security_responses.get("rugcheck", {}))
            sniper_info = self._detect_sniper_patterns(security_responses.get("goplus", {}))
            
            return {
                "market_data": market_data,
                "token_info": token_info,
                "volatility": {
                    "recent_volatility_percent": volatility,
                    "volatility_available": volatility is not None,
                    "volatility_risk": "high" if volatility and volatility > 30 else "medium" if volatility and volatility > 15 else "low",
                    "trades_analyzed": len(market_responses.get("birdeye", {}).get("trades", {}).get("items", []))
                },
                "whale_analysis": whale_info,
                "sniper_detection": sniper_info
            }
            
        except Exception as e:
            logger.warning(f"Error generating combined metrics: {e}")
            return {"market_data": {}, "token_info": {}, "volatility": {}, "whale_analysis": {}, "sniper_detection": {}}
    
    async def run_scheduled_snapshots(self) -> Dict[str, Any]:
        """Run scheduled snapshots for multiple tokens"""
        if self._running:
            logger.warning("Snapshot run already in progress")
            return {"status": "already_running"}
        
        self._running = True
        start_time = time.time()
        
        try:
            logger.info(f"🔄 Starting scheduled snapshot run (max {self.max_tokens_per_run} tokens)")
            
            # Get tokens for snapshot
            tokens = await self._get_tokens_for_snapshot()
            if not tokens:
                logger.info("No tokens found for snapshot")
                return {"status": "no_tokens", "tokens_processed": 0}
            
            # Limit tokens per run
            tokens = tokens[:self.max_tokens_per_run]
            logger.info(f"Processing {len(tokens)} tokens for snapshots")
            
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
                    else:
                        results["successful"] += 1
                    
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
                metadata = results[0].get("metadata", {})
                return {
                    "analysis_id": metadata.get("analysis_id"),
                    "snapshot_generation": metadata.get("snapshot_generation", 0),
                    "timestamp": metadata.get("timestamp", 0)
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting latest snapshot for {token_address}: {e}")
            return None
    
    async def _get_tokens_for_snapshot(self) -> List[str]:
        """Get list of tokens that need snapshots"""
        try:
            # Get tokens from existing analyses that need snapshots
            # This reuses the existing token discovery from comprehensive analyses
            results = await analysis_storage.search_analyses(
                query="token analysis",
                limit=self.max_tokens_per_run * 2,  # Get more to filter
                filters={"doc_type": "token_analysis"}
            )
            
            tokens = []
            seen = set()
            
            for result in results:
                metadata = result.get("metadata", {})
                token_address = metadata.get("token_address")
                
                if token_address and token_address not in seen:
                    tokens.append(token_address)
                    seen.add(token_address)
            
            logger.info(f"Found {len(tokens)} tokens for potential snapshots")
            return tokens
            
        except Exception as e:
            logger.error(f"Error getting tokens for snapshot: {e}")
            return []
    
    async def _run_market_analysis_services(self, token_address: str, snapshot_response: Dict[str, Any]) -> None:
        """Run market analysis services (same as comprehensive analysis but no security)"""
        print(snapshot_response)
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
            trades = birdeye_data.get("trades", []).get("items", [])
            if not trades or len(trades) < 5:
                return None
            
            token_address = birdeye_data.get("price", {}).get("address", None)

            if token_address is not None:
                # Extract prices from recent trades
                prices = []
                for trade in trades[:20]:  # Use up to 20 recent trades
                    source = "from" if trade["from"]["address"] == token_address else "to"
                    if isinstance(trade, dict) and source and trade.get(source):
                        try:
                            price = float(trade[source]["price"])
                            if price > 0:
                                prices.append(price)
                        except (ValueError, TypeError):
                            continue
                
                if len(prices) < 3:
                    return None
            else:
                raise Exception("Unable to extract token address from Birdeye data")
            
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

    def _detect_simple_whales(self, goplus_data: Dict[str, Any], rugcheck_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simple whale detection from existing holder data"""
        try:
            whale_info = {
                "whale_count": 0,
                "whale_control_percent": 0.0,
                "top_whale_percent": 0.0,
                "whale_risk_level": "low",
                "dev_whale_percent": 0.0
            }
            
            # Method 1: GOplus holders
            holders = goplus_data.get("holders", [])
            if holders and isinstance(holders, list):
                whales = []
                for holder in holders:
                    if isinstance(holder, dict):
                        try:
                            percent_raw = holder.get("percent", "0")
                            percent = float(percent_raw)
                            
                            # Whale threshold: >2% = whale
                            if percent > 2.0:
                                whales.append(percent)
                        except (ValueError, TypeError):
                            continue
                
                if whales:
                    whale_info["whale_count"] = len(whales)
                    whale_info["whale_control_percent"] = round(sum(whales), 2)
                    whale_info["top_whale_percent"] = round(max(whales), 2)
                    
                    # Simple risk assessment
                    if whale_info["whale_control_percent"] > 60:
                        whale_info["whale_risk_level"] = "high"
                    elif whale_info["whale_control_percent"] > 30:
                        whale_info["whale_risk_level"] = "medium"  
                    else:
                        whale_info["whale_risk_level"] = "low"
                    
                    logger.info(f"Whales detected: {whale_info['whale_count']} whales control {whale_info['whale_control_percent']}%")
            
            return whale_info
            
        except Exception as e:
            logger.warning(f"Whale detection failed: {e}")
            return {
                "whale_count": 0,
                "whale_control_percent": 0.0,
                "top_whale_percent": 0.0,
                "whale_risk_level": "unknown",
                "dev_whale_percent": 0.0
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

    def _extract_market_data(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Extract market data from service responses"""
        market_data = {
            "price_usd": None,
            "price_change_24h": None,
            "volume_24h": None,
            "volume_change_24h": None,
            "volume_7d": None,
            "volume_change_7d": None,
            "volume_5m": None,
            "volume_change_5m": None,
            "market_cap": None,
            "liquidity": None,
            "volume_liquidity_ratio": None,
            "data_completeness_percent": 0.0
        }
        
        try:
            birdeye_data = service_responses.get("birdeye", {})
            if birdeye_data and birdeye_data.get("price"):
                price_data = birdeye_data["price"]
                
                market_data.update({
                    "price_usd": price_data.get("value"),
                    "price_change_24h": price_data.get("price_change_24h"),
                    "volume_24h": price_data.get("volume_24h"),
                    "market_cap": price_data.get("market_cap"),
                    "liquidity": price_data.get("liquidity")
                })
                
                # Calculate volume/liquidity ratio
                if market_data["volume_24h"] and market_data["liquidity"]:
                    market_data["volume_liquidity_ratio"] = (market_data["volume_24h"] / market_data["liquidity"]) * 100
                
                # Calculate data completeness
                fields = [market_data["price_usd"], market_data["volume_24h"], market_data["market_cap"], market_data["liquidity"]]
                market_data["data_completeness_percent"] = (sum(1 for f in fields if f is not None) / len(fields)) * 100
            
            return market_data
            
        except Exception as e:
            logger.warning(f"Error extracting market data: {e}")
            return market_data
    
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