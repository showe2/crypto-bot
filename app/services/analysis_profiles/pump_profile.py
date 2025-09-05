from typing import Dict, Any, Optional, List
from loguru import logger
import statistics
import time
from datetime import datetime, timedelta

from .base_profile import BaseAnalysisProfile
from app.models.analysis_models import AnalysisRunResponse


class PumpAnalysisProfile(BaseAnalysisProfile):
    """Volume/price spike analysis profile"""
    
    profile_name = "Pump Detection"
    analysis_type = "pump"
    required_services = ["dexscreener", "goplus", "birdeye"]  # DexScreener for age, GOplus for security, Birdeye for trades
    ai_focus_areas = ["pump_indicators", "volume_analysis", "momentum_metrics", "age_analysis", "security_assessment"]
    
    async def analyze(self, token_address: str, filters: Optional[Dict] = None, **kwargs) -> AnalysisRunResponse:
        """Analyze token for pump/spike patterns"""
        self.start_time = time.time()
        
        # Check if this is automated scanning request
        if token_address == "*":
            logger.info("🔄 Starting automated pump scanning for security-checked tokens")
            return await self._run_automated_pump_scan(filters, **kwargs)
        
        logger.info(f"📈 Starting Pump analysis for {token_address}")
        
        # Gather service data
        service_data = await self._gather_service_data(token_address)
        
        # Detect pump signals
        pump_data = self._detect_pump_signals(service_data)
        service_data["pump_analysis"] = pump_data
        
        # Run AI analysis
        ai_data = await self._run_ai_analysis(token_address, service_data)
        
        # Extract token info
        token_info = self._extract_token_info(service_data)
        
        # Calculate metrics
        overall_score = self._calculate_pump_score(service_data, ai_data)
        risk_level = self._determine_pump_risk(service_data, ai_data)
        recommendation = self._determine_recommendation(overall_score, risk_level, ai_data)
        
        # Determine security status based on pump characteristics
        security_status = "warning" if pump_data.get("pump_probability", 0) > 70 else "passed"
        
        # Build response
        response = AnalysisRunResponse(
            analysis_type=self.analysis_type,
            token_address=token_address,
            token_symbol=token_info["symbol"],
            token_name=token_info["name"],
            overall_score=overall_score,
            risk_level=risk_level,
            recommendation=recommendation,
            security_status=security_status,
            critical_issues=1 if pump_data.get("unsustainable_pump") else 0,
            warnings=len([w for w in pump_data.get("warnings", [])]),
            processing_time=round(time.time() - self.start_time, 2),
            profile_data={
                "pump_metrics": pump_data,
                "ai_analysis": ai_data,
                "services_data": {k: v for k, v in service_data.items() if not k.startswith("services_")}
            }
        )
        
        # Store analysis with comprehensive format
        await self._store_analysis(response, service_data, ai_data)
        
        logger.info(f"✅ Pump analysis completed: {overall_score}% score, pump probability {pump_data.get('pump_probability', 0):.1f}%")
        return response
    
    def _calculate_pump_score_formula(self, pump_data: Dict[str, Any], market_data: Dict[str, Any]) -> float:
        """Calculate THE pump score: vol_5m * buy_sell_ratio / age_minutes"""
        try:
            # Get the three components of the formula
            vol_5m = pump_data.get("volume_recent", 0)  # This is our vol_5m
            buy_sell_ratio = pump_data.get("buy_sell_ratio", 1.0)
            age_hours = pump_data.get("pool_age_hours", 1.0)
            
            # Convert age to minutes, minimum 1 minute to avoid division by zero
            age_minutes = max(age_hours * 60, 1.0)
            
            # Calculate the formula: vol_5m * buy_sell_ratio / age_minutes
            pump_score = (vol_5m * buy_sell_ratio) / age_minutes
            
            return round(pump_score, 4)
            
        except Exception as e:
            logger.warning(f"Error calculating pump score formula: {e}")
            return 0.0

    def _extract_market_data_for_scan(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract market data for pump scanning"""
        market_data = {
            "liquidity": 0,
            "price_usd": 0,
            "volume_24h": 0,
            "market_cap": 0
        }
        
        try:
            # Get from Birdeye first
            birdeye_data = service_data.get("birdeye", {})
            if birdeye_data and birdeye_data.get("price"):
                price_data = birdeye_data["price"]
                market_data.update({
                    "liquidity": price_data.get("liquidity", 0) or 0,
                    "price_usd": price_data.get("value", 0) or 0,
                    "volume_24h": price_data.get("volume_24h", 0) or 0,
                    "market_cap": price_data.get("market_cap", 0) or 0
                })
            
            # Fallback to DexScreener for missing data
            if not market_data["liquidity"]:
                dex_data = service_data.get("dexscreener", {})
                if dex_data and dex_data.get("pairs", {}).get("pairs"):
                    pair = dex_data["pairs"]["pairs"][0]
                    market_data["liquidity"] = pair.get("liquidity", {}).get("usd", 0) or 0
            
        except Exception as e:
            logger.warning(f"Error extracting market data for scan: {e}")
        
        return market_data

    def _assess_pump_risk_level(self, pump_data: Dict[str, Any]) -> str:
        """Assess pump risk level"""
        try:
            if not pump_data.get("security_gate_passed"):
                return "critical"
            
            pump_prob = pump_data.get("pump_probability", 0)
            age_hours = pump_data.get("pool_age_hours", 24)
            
            if pump_prob > 80 and age_hours < 1:
                return "critical"
            elif pump_prob > 60 or age_hours < 2:
                return "high"
            elif pump_prob > 30:
                return "medium"
            else:
                return "low"
                
        except Exception:
            return "unknown"

    def _get_pump_recommendation(self, pump_data: Dict[str, Any], pump_score: float) -> str:
        """Get pump recommendation based on data"""
        try:
            if not pump_data.get("security_gate_passed"):
                return "AVOID"
            
            pump_prob = pump_data.get("pump_probability", 0)
            sustainability = pump_data.get("sustainability_score", 50)
            
            if pump_prob > 70 and sustainability < 30:
                return "CAUTION"
            elif pump_prob > 50 and pump_score > 1000:
                return "CONSIDER"
            elif pump_prob > 30:
                return "HOLD"
            elif pump_score > 500:
                return "CONSIDER"
            else:
                return "HOLD"
                
        except Exception:
            return "HOLD"
    
    async def _run_automated_pump_scan(self, filters: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Run automated pump scanning on tokens"""
        # Generate unique run ID with "run_" prefix
        run_id = f"run_{int(time.time())}_{hash(str(filters)) % 10000}"
        scan_results = []
        
        try:
            # Get tokens that haven't been pump-analyzed yet
            from app.services.analysis_storage import analysis_storage
            eligible_tokens = await analysis_storage.get_tokens_for_profile_analysis("pump", limit=30)
            
            if not eligible_tokens:
                logger.warning("No eligible tokens found for pump scanning")
                
                # Store empty run
                run_data = {
                    "run_id": run_id,
                    "profile_type": "pump",
                    "timestamp": int(time.time()),
                    "status": "completed",
                    "tokens_analyzed": 0,
                    "processing_time": round(time.time() - self.start_time, 2),
                    "filters": filters or {},
                    "results": [],
                    "summary": "No tokens available for pump analysis (all already analyzed or don't meet criteria)"
                }
                
                await analysis_storage.store_analysis_run(run_data)
                
                return {
                    "run_id": run_id,
                    "status": "completed",
                    "tokens_scanned": 0,
                    "pumps_found": 0,
                    "results": [],
                    "processing_time": round(time.time() - self.start_time, 2),
                    "message": "No tokens available for pump analysis"
                }
            
            logger.info(f"🔍 Starting pump scan run {run_id}: {len(eligible_tokens)} tokens")
            
            scanned_addresses = []
            
            # Analyze each token for pump signals
            for i, token_data in enumerate(eligible_tokens):
                token_address = token_data["token_address"]
                
                try:
                    logger.debug(f"Scanning token {i+1}/{len(eligible_tokens)}: {token_data['token_symbol']} ({token_address[:8]}...)")
                    
                    # Run pump analysis on this token
                    service_data = await self._gather_service_data(token_address)
                    pump_data = self._detect_pump_signals(service_data)
                    
                    # Extract market data for ranking
                    market_data = self._extract_market_data_for_scan(service_data)
                    
                    # Calculate THE pump score: vol_5m * buy_sell / age_min
                    pump_score = self._calculate_pump_score_formula(pump_data, market_data)
                    
                    # Build result entry with comprehensive data
                    result = {
                        # Basic token info
                        "token_address": token_address,
                        "token_name": token_data["token_name"],
                        "token_symbol": token_data["token_symbol"],
                        "success": True,
                        
                        # THE MAIN PUMP SCORE (vol_5m * buy_sell / age_min) - This is the ranking score
                        "pump_score": pump_score,
                        
                        # Raw pump metrics for display and calculations
                        "pump_probability": pump_data.get("pump_probability", 0),
                        "pool_age_hours": pump_data.get("pool_age_hours", 0),
                        "pool_age_minutes": max(pump_data.get("pool_age_hours", 1) * 60, 1),  # For the formula
                        "buy_sell_ratio": pump_data.get("buy_sell_ratio", 1.0),
                        "volume_5m": pump_data.get("volume_recent", 0),  # This is vol_5m for the formula
                        "volume_recent": pump_data.get("volume_recent", 0),  # Alias for compatibility
                        "trade_count_recent": pump_data.get("trade_count_recent", 0),
                        "security_gate_passed": pump_data.get("security_gate_passed", False),
                        "new_pool": pump_data.get("new_pool", False),
                        "sustainability_score": pump_data.get("sustainability_score", 50),
                        "volume_spike_percent": pump_data.get("volume_spike_percent", 0),
                        
                        # Market data
                        "liquidity": market_data.get("liquidity", 0),
                        "price_usd": market_data.get("price_usd", 0),
                        "volume_24h": market_data.get("volume_24h", 0),
                        "market_cap": market_data.get("market_cap", 0),
                        
                        # Risk assessment
                        "risk_level": self._assess_pump_risk_level(pump_data),
                        "recommendation": self._get_pump_recommendation(pump_data, pump_score),
                        
                        # Profile tracking
                        "profiles_before": token_data.get("profiles_status", {}),
                        
                        # Metadata
                        "analysis_timestamp": int(time.time()),
                        "warnings": pump_data.get("warnings", []),
                        "scan_run_id": run_id
                    }
                    
                    scan_results.append(result)
                    scanned_addresses.append(token_address)
                    
                except Exception as e:
                    logger.warning(f"Failed to scan token {token_address}: {e}")
                    
                    # Add failed result but still mark as attempted
                    scan_results.append({
                        "token_address": token_address,
                        "token_name": token_data["token_name"],
                        "token_symbol": token_data["token_symbol"],
                        "success": False,
                        "error": str(e),
                        "pump_score": 0,
                        "scan_run_id": run_id
                    })
                    scanned_addresses.append(token_address)  # Still mark as attempted
                    continue
            
            # Sort results by pump score (vol_5m * buy_sell / age_min)
            scan_results.sort(key=lambda x: x.get("pump_score", 0), reverse=True)
            
            # Count successful analyses and pumps
            successful_analyses = len([r for r in scan_results if r.get("success", False)])
            pumps_found = len([r for r in scan_results if r.get("success", False) and r.get("pump_probability", 0) > 50])
            
            # Mark tokens as analyzed for pump profile (even failed ones to avoid retrying immediately)
            if scanned_addresses:
                await analysis_storage.mark_tokens_analyzed(scanned_addresses, "pump", run_id)
            
            # Prepare comprehensive run data
            run_data = {
                "run_id": run_id,
                "profile_type": "pump",
                "timestamp": int(time.time()),
                "status": "completed",
                "tokens_analyzed": len(scan_results),
                "successful_analyses": successful_analyses,
                "processing_time": round(time.time() - self.start_time, 2),
                "filters": filters or {},
                "results": scan_results,
                "summary": f"Pump scan completed: {pumps_found} pumps found from {successful_analyses} successful analyses"
            }
            
            # Store run data using reusable storage
            await analysis_storage.store_analysis_run(run_data)
            
            logger.info(f"✅ Pump scan run {run_id} completed: {successful_analyses} tokens analyzed, {pumps_found} pumps detected")
            
            return {
                "run_id": run_id,
                "status": "completed",
                "tokens_scanned": successful_analyses,
                "pumps_found": pumps_found,
                "results": scan_results[:20],  # Return top 20 results for frontend
                "processing_time": round(time.time() - self.start_time, 2),
                "total_results": len(scan_results)
            }
            
        except Exception as e:
            logger.error(f"Automated pump scan failed: {e}")
            
            # Store failed run
            run_data = {
                "run_id": run_id,
                "profile_type": "pump",
                "timestamp": int(time.time()),
                "status": "error",
                "tokens_analyzed": 0,
                "successful_analyses": 0,
                "processing_time": round(time.time() - self.start_time, 2),
                "filters": filters or {},
                "results": [],
                "summary": f"Pump scan failed: {str(e)}"
            }
            
            await analysis_storage.store_analysis_run(run_data)
            
            return {
                "run_id": run_id,
                "status": "error",
                "error": str(e),
                "tokens_scanned": 0,
                "pumps_found": 0,
                "results": [],
                "processing_time": round(time.time() - self.start_time, 2)
            }
    
    def _detect_pump_signals(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect pump/spike indicators with age, buy/sell ratio, and ranking"""
        pump_data = {
            "volume_spike_percent": 0.0,
            "price_momentum": 0.0,
            "pump_probability": 0.0,
            "sustainability_score": 50.0,
            "pool_age_hours": 0.0,
            "buy_sell_ratio": 1.0,
            "trade_count_recent": 0,
            "volume_recent": 0.0,
            "ranking_score": 0.0,
            "new_pool": False,
            "security_gate_passed": False,
            "warnings": [],
            "unsustainable_pump": False
        }
        
        # === POOL AGE ANALYSIS ===
        pool_age_hours = self._calculate_pool_age(service_data)
        pump_data["pool_age_hours"] = pool_age_hours
        pump_data["new_pool"] = pool_age_hours <= 24  # New pool if ≤ 24 hours
        
        if pool_age_hours <= 1:
            pump_data["warnings"].append(f"Very new pool: {pool_age_hours:.1f} hours old")
        
        # === VOLUME ANALYSIS ===
        volume_data = self._analyze_volume_data(service_data)
        pump_data.update(volume_data)
        
        # === BUY/SELL RATIO ANALYSIS ===
        buy_sell_ratio = self._calculate_buy_sell_ratio(service_data)
        pump_data["buy_sell_ratio"] = buy_sell_ratio
        
        if buy_sell_ratio > 2.0:
            pump_data["warnings"].append(f"High buy pressure: {buy_sell_ratio:.2f}")
        elif buy_sell_ratio < 0.8:
            pump_data["warnings"].append(f"High sell pressure: {buy_sell_ratio:.2f}")
        
        # === SECURITY GATE ===
        security_passed = self._simple_security_gate(service_data)
        pump_data["security_gate_passed"] = security_passed
        
        if not security_passed:
            pump_data["warnings"].append("Failed security gate checks")
        
        # === PRICE MOMENTUM (existing logic) ===
        birdeye_data = service_data.get("birdeye", {})
        if birdeye_data:
            price_data = birdeye_data.get("price", {})
            if price_data:
                price_change_24h = price_data.get("price_change_24h")
                if price_change_24h:
                    try:
                        price_change = float(price_change_24h)
                        if abs(price_change) > 20:
                            pump_data["price_momentum"] = min(100, abs(price_change) * 2)
                            if price_change > 50:
                                pump_data["warnings"].append(f"Extreme price spike: +{price_change:.1f}%")
                                pump_data["unsustainable_pump"] = price_change > 100
                    except (ValueError, TypeError):
                        pass
        
        # === PUMP PROBABILITY CALCULATION ===
        # Factor in age, volume spike, price momentum, and buy/sell pressure
        age_factor = min(1.0, 48 / max(pool_age_hours, 0.1))  # Higher score for newer pools
        volume_factor = pump_data["volume_spike_percent"] / 100
        momentum_factor = pump_data["price_momentum"] / 100
        ratio_factor = min(1.0, max(0, (buy_sell_ratio - 1) / 2))  # Boost for buy pressure
        
        pump_probability = (
            volume_factor * 0.3 + 
            momentum_factor * 0.3 + 
            age_factor * 0.2 + 
            ratio_factor * 0.2
        ) * 100
        
        pump_data["pump_probability"] = round(pump_probability, 1)
        
        # === RANKING SCORE ===
        ranking_score = self._calculate_ranking_score(pump_data)
        pump_data["ranking_score"] = ranking_score
        
        # === SUSTAINABILITY ASSESSMENT ===
        if pump_data["pump_probability"] > 80 and pool_age_hours < 2:
            pump_data["sustainability_score"] = 20.0
            pump_data["unsustainable_pump"] = True
            pump_data["warnings"].append("High pump probability on very new pool - high risk")
        elif pump_data["pump_probability"] > 60:
            pump_data["sustainability_score"] = 40.0
            pump_data["warnings"].append("Moderate pump detected")
        else:
            pump_data["sustainability_score"] = 70.0
        
        # Security gate affects sustainability
        if not security_passed:
            pump_data["sustainability_score"] = min(pump_data["sustainability_score"], 30.0)
        
        return pump_data
    
    def _analyze_trade_patterns(self, trades_data: List[Dict]) -> Dict[str, Any]:
        """Analyze trading patterns for pump indicators"""
        try:
            if not trades_data or len(trades_data) < 5:
                return {}
            
            # Extract trade volumes and timestamps
            volumes = []
            for trade in trades_data[:20]:  # Analyze recent 20 trades
                if isinstance(trade, dict):
                    # Extract volume data (this might need adjustment based on actual Birdeye format)
                    volume = trade.get("amount_usd") or trade.get("volume")
                    if volume:
                        try:
                            volumes.append(float(volume))
                        except (ValueError, TypeError):
                            continue
            
            if len(volumes) < 3:
                return {}
            
            # Calculate trade pattern indicators
            avg_volume = statistics.mean(volumes)
            max_volume = max(volumes)
            
            # Detect volume concentration
            large_trades = [v for v in volumes if v > avg_volume * 3]
            volume_concentration = len(large_trades) / len(volumes) * 100
            
            return {
                "trade_pattern_score": min(100, volume_concentration * 2),
                "large_trade_ratio": round(volume_concentration, 2),
                "avg_trade_volume": round(avg_volume, 2),
                "max_trade_volume": round(max_volume, 2)
            }
            
        except Exception as e:
            logger.warning(f"Trade pattern analysis failed: {e}")
            return {}
    
    def _calculate_pump_score(self, service_data: Dict[str, Any], ai_data: Optional[Dict[str, Any]]) -> float:
        """Calculate score with age, security, and buy/sell factors"""
        pump_analysis = service_data.get("pump_analysis", {})
        
        # Start with base score
        base_score = 50.0
        
        # === AGE FACTOR ===
        pool_age_hours = pump_analysis.get("pool_age_hours", 168)
        if pool_age_hours <= 1:  # Very new pool
            base_score += 20  # Bonus for early opportunity
        elif pool_age_hours <= 24:  # New pool
            base_score += 10
        elif pool_age_hours <= 168:  # Week old
            base_score += 5
        else:  # Old pool
            base_score -= 10  # Penalty for old tokens with sudden activity
        
        # === SECURITY GATE ===
        security_passed = pump_analysis.get("security_gate_passed", False)
        if security_passed:
            base_score += 15  # Security bonus
        else:
            base_score -= 20  # Security penalty
        
        # === BUY/SELL PRESSURE ===
        buy_sell_ratio = pump_analysis.get("buy_sell_ratio", 1.0)
        if buy_sell_ratio >= 2.0:  # Strong buy pressure
            base_score += 15
        elif buy_sell_ratio >= 1.5:  # Moderate buy pressure
            base_score += 10
        elif buy_sell_ratio >= 1.2:  # Slight buy pressure
            base_score += 5
        elif buy_sell_ratio < 0.8:  # Sell pressure
            base_score -= 15
        
        # === VOLUME FACTOR ===
        volume_recent = pump_analysis.get("volume_recent", 0)
        if volume_recent >= 100000:  # $100K+
            base_score += 15
        elif volume_recent >= 10000:  # $10K+
            base_score += 10
        elif volume_recent >= 1000:  # $1K+
            base_score += 5
        else:  # Low volume
            base_score -= 10
        
        # === SUSTAINABILITY ===
        sustainability = pump_analysis.get("sustainability_score", 50)
        if sustainability >= 70:
            base_score += 10
        elif sustainability <= 30:
            base_score -= 15
        
        # === AI ENHANCEMENT ===
        if ai_data and ai_data.get("ai_score"):
            ai_score = float(ai_data["ai_score"])
            # 70/30 blend: traditional logic gets more weight
            base_score = (base_score * 0.7) + (ai_score * 0.3)
        
        return round(min(100.0, max(0.0, base_score)), 1)
    
    def _determine_pump_risk(self, service_data: Dict[str, Any], ai_data: Optional[Dict[str, Any]]) -> str:
        """Determine risk level with security and age factors"""
        pump_analysis = service_data.get("pump_analysis", {})
        
        # Security gate failure = high risk
        if not pump_analysis.get("security_gate_passed", False):
            return "high"
        
        # Unsustainable pump = high risk
        if pump_analysis.get("unsustainable_pump", False):
            return "critical"
        
        # Very new pool with high pump = medium risk
        pool_age_hours = pump_analysis.get("pool_age_hours", 168)
        pump_prob = pump_analysis.get("pump_probability", 0)
        
        if pool_age_hours <= 2 and pump_prob > 70:
            return "medium"
        elif pump_prob > 80:
            return "medium"
        else:
            return "low"
    
    async def build_ai_prompt(self, token_address: str, service_data: Dict[str, Any]) -> str:
        """Build pump-focused AI prompt with age and buy/sell analysis"""
        pump_data = service_data.get("pump_analysis", {})
        price_data = service_data.get("birdeye", {}).get("price", {}) if service_data.get("birdeye") else {}
        
        # Check Birdeye liquidity
        birdeye_liquidity = price_data.get('liquidity', 0) or 0
        
        # Check DexScreener liquidity
        dex_data = service_data.get("dexscreener", {})
        dex_liquidity = 0
        if dex_data and dex_data.get("pairs", {}).get("pairs"):
            pairs = dex_data["pairs"]["pairs"]
            if pairs and len(pairs) > 0:
                main_pair = pairs[0]
                liq_data = main_pair.get("liquidity", {})
                dex_liquidity = liq_data.get("usd", 0) or 0
        
        # Use the higher value
        actual_liquidity = max(birdeye_liquidity, dex_liquidity)
        
        # Safe value extraction with defaults
        volume_spike = pump_data.get('volume_spike_percent', 0) or 0
        price_momentum = pump_data.get('price_momentum', 0) or 0
        pump_probability = pump_data.get('pump_probability', 0) or 0
        sustainability = pump_data.get('sustainability_score', 50) or 50
        pool_age_hours = pump_data.get('pool_age_hours', 0) or 0
        buy_sell_ratio = pump_data.get('buy_sell_ratio', 1.0) or 1.0
        volume_recent = pump_data.get('volume_recent', 0) or 0
        trade_count = pump_data.get('trade_count_recent', 0) or 0
        ranking_score = pump_data.get('ranking_score', 0) or 0
        new_pool = pump_data.get('new_pool', False)
        security_passed = pump_data.get('security_gate_passed', False)
        
        price_value = price_data.get('value', 0) or 0
        price_change_24h = price_data.get('price_change_24h', 0) or 0
        
        # FIXED PROMPT with actual liquidity data
        prompt = f"""
    PUMP DETECTION ANALYSIS for {token_address}

    POOL DATA:
    - Pool Age: {pool_age_hours:.1f} hours (New Pool: {new_pool})
    - Buy/Sell Ratio: {buy_sell_ratio:.2f} (>1 = buy pressure, <1 = sell pressure)
    - Security Gate: {'PASSED' if security_passed else 'FAILED'}
    - Ranking Score: {ranking_score:.2f} (volume*ratio/age formula)

    PUMP INDICATORS:
    - Volume Spike: {volume_spike:.1f}%
    - Price Momentum: {price_momentum:.1f}%
    - Pump Probability: {pump_probability:.1f}%
    - Sustainability Score: {sustainability:.1f}

    MARKET DATA:
    - Price: ${price_value:.8f}
    - Recent Volume: ${volume_recent:,.0f}
    - Liquidity: ${actual_liquidity:,.0f}  ← FIXED: Use actual liquidity
    - 24h Change: {price_change_24h:+.2f}%
    - Trade Count: {trade_count}

    LIQUIDITY ASSESSMENT:
    {f"EXCELLENT liquidity (${actual_liquidity/1000000:.1f}M)" if actual_liquidity >= 1000000 else f"GOOD liquidity (${actual_liquidity/1000:.0f}K)" if actual_liquidity >= 100000 else f"MODERATE liquidity (${actual_liquidity:,.0f})" if actual_liquidity >= 10000 else "LOW liquidity - HIGH RISK"}

    ANALYSIS FOCUS:
    1. AGE ANALYSIS: Is this a new pool opportunity or established token?
    2. PUMP TYPE: Organic growth vs artificial pump vs bot activity?
    3. BUY PRESSURE: Is the buy/sell ratio indicating real demand?
    4. LIQUIDITY DEPTH: ${actual_liquidity:,.0f} liquidity - can handle volume without slippage?
    5. SUSTAINABILITY: Can this momentum continue or is it a quick pump?
    6. RISK ASSESSMENT: What are the main risks for pump trading?
    7. TIMING: Is this early, peak, or late stage of movement?

    IMPORTANT: With ${actual_liquidity:,.0f} liquidity, this token has {"EXCELLENT" if actual_liquidity >= 1000000 else "GOOD" if actual_liquidity >= 100000 else "MODERATE" if actual_liquidity >= 10000 else "POOR"} liquidity depth.

    Respond ONLY with JSON matching this structure:
    {{
    "pump_score": 0-100,
    "pump_type": "organic|artificial|bot_driven|unknown",
    "sustainability": "low|medium|high",
    "momentum_strength": "weak|moderate|strong",
    "age_factor": "new_pool|young|established",
    "buy_pressure": "low|moderate|high",
    "liquidity_assessment": "excellent|good|moderate|poor",
    "recommendation": "BUY|CONSIDER|HOLD|CAUTION|AVOID",
    "key_insights": ["list of pump insights"],
    "pump_risks": ["list of specific risks"],
    "timing_assessment": "early|peak|late|unknown"
    }}
    """
        return prompt
    
    def get_json_filters(self) -> Dict[str, Any]:
        """Get JSON filters for pump analysis"""
        return {
            "focus": ["pump_indicators", "volume_analysis", "momentum_metrics"],
            "required_fields": ["pump_score", "sustainability", "momentum_strength"],
            "format": "pump_analysis"
        }
    
    def _calculate_pool_age(self, service_data: Dict[str, Any]) -> float:
        """Get raw pool creation time - no parsing bullshit"""
        try:
            dex_data = service_data.get("dexscreener", {})
            pairs_container = dex_data.get("pairs", {})
            pairs_list = pairs_container.get("pairs", [])
            
            if pairs_list and len(pairs_list) > 0:
                main_pair = pairs_list[0]
                created_at = main_pair.get("pairCreatedAt")
                current_time = round(time.time())

                created_at_hours = (current_time-created_at/1000)/3600
                
                return round(created_at_hours) if created_at_hours else 0
            
            return 0
            
        except Exception as e:
            logger.warning(f"Failed to get creation time: {e}")
            return 0

    def _analyze_volume_data(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze volume data with REAL spike calculation"""
        volume_data = {
            "volume_recent": 0.0,
            "volume_spike_percent": 0.0,
            "trade_count_recent": 0,
            "volume_category": "unknown"
        }
        
        try:
            # === GET VOLUME FROM DEXSCREENER ===
            dex_data = service_data.get("dexscreener", {})
            
            pairs_data = None
            if isinstance(dex_data, dict):
                if dex_data.get("pairs"):
                    pairs_data = dex_data["pairs"]
                    if isinstance(pairs_data, dict) and pairs_data.get("pairs"):
                        pairs_data = pairs_data["pairs"]
                elif dex_data.get("pair"):
                    pairs_data = [dex_data["pair"]]
            
            if pairs_data and isinstance(pairs_data, list) and len(pairs_data) > 0:
                main_pair = pairs_data[0]
                if isinstance(main_pair, dict):
                    volume_info = main_pair.get("volume", {})
                    if isinstance(volume_info, dict):
                        # Get current 24h volume
                        volume_24h = volume_info.get("h24", 0)
                        if volume_24h:
                            volume_data["volume_recent"] = float(volume_24h)
                        
                        # Compare different timeframes
                        volume_1h = volume_info.get("h1", 0) or 0
                        volume_6h = volume_info.get("h6", 0) or 0
                        
                        # Calculate spike based on timeframe comparison
                        if volume_1h > 0 and volume_24h > 0:
                            # Projected 24h volume from 1h data
                            projected_24h = volume_1h * 24
                            if projected_24h > volume_24h:
                                spike_percent = ((projected_24h - volume_24h) / volume_24h) * 100
                                volume_data["volume_spike_percent"] = min(200, max(0, spike_percent))
                            else:
                                volume_data["volume_spike_percent"] = 0
                        elif volume_6h > 0 and volume_24h > 0:
                            # Projected 24h volume from 6h data
                            projected_24h = volume_6h * 4
                            if projected_24h > volume_24h:
                                spike_percent = ((projected_24h - volume_24h) / volume_24h) * 100
                                volume_data["volume_spike_percent"] = min(200, max(0, spike_percent))
                            else:
                                volume_data["volume_spike_percent"] = 0
                        else:
                            # No spike data available - categorize volume level instead
                            if volume_24h >= 1000000:  # $1M+
                                volume_data["volume_spike_percent"] = 80  # High volume but no spike calc
                            elif volume_24h >= 100000:  # $100K+
                                volume_data["volume_spike_percent"] = 60
                            elif volume_24h >= 10000:  # $10K+
                                volume_data["volume_spike_percent"] = 40
                            elif volume_24h >= 1000:  # $1K+
                                volume_data["volume_spike_percent"] = 20
                            else:
                                volume_data["volume_spike_percent"] = 5
                        
                        # Volume category for clarity
                        if volume_24h >= 1000000:
                            volume_data["volume_category"] = "very_high"
                        elif volume_24h >= 100000:
                            volume_data["volume_category"] = "high"
                        elif volume_24h >= 10000:
                            volume_data["volume_category"] = "medium"
                        elif volume_24h >= 1000:
                            volume_data["volume_category"] = "low"
                        else:
                            volume_data["volume_category"] = "very_low"
            
            # === GET TRADE COUNT FROM BIRDEYE ===
            birdeye_data = service_data.get("birdeye", {})
            if isinstance(birdeye_data, list) and len(birdeye_data) > 0:
                birdeye_data = birdeye_data[0]
            
            if birdeye_data and isinstance(birdeye_data, dict):
                trades_data = birdeye_data.get("trades")
                if trades_data:
                    if isinstance(trades_data, list):
                        volume_data["trade_count_recent"] = len(trades_data)
                    elif isinstance(trades_data, dict) and trades_data.get("items"):
                        items = trades_data["items"]
                        volume_data["trade_count_recent"] = len(items) if isinstance(items, list) else 0
            
            return volume_data
            
        except Exception as e:
            logger.warning(f"Volume analysis failed: {e}")
            return volume_data

    def _calculate_buy_sell_ratio(self, service_data: Dict[str, Any]) -> float:
        """Calculate buy/sell ratio - FIXED for actual API responses"""
        try:
            birdeye_data = service_data.get("birdeye", {})
            
            # Handle Birdeye being a list
            if isinstance(birdeye_data, list) and len(birdeye_data) > 0:
                birdeye_data = birdeye_data[0]
            
            if not isinstance(birdeye_data, dict):
                return 1.0
            
            trades_data = birdeye_data.get("trades")
            if not trades_data:
                return 1.0  # Neutral if no trade data
            
            # Handle both list and dict formats
            trades = []
            if isinstance(trades_data, list):
                trades = trades_data
            elif isinstance(trades_data, dict) and trades_data.get("items"):
                trades = trades_data["items"]
            
            if not trades or len(trades) < 5:
                return 1.0
            
            # Simple approach: count buy vs sell indicators
            buy_count = 0
            sell_count = 0
            
            for trade in trades[:20]:  # Recent 20 trades
                if not isinstance(trade, dict):
                    continue
                
                try:
                    # Look for buy/sell indicators in the trade data
                    trade_type = str(trade.get("type", "")).lower()
                    side = str(trade.get("side", "")).lower()
                    
                    # Check various fields that might indicate direction
                    if "buy" in trade_type or "buy" in side:
                        buy_count += 1
                    elif "sell" in trade_type or "sell" in side:
                        sell_count += 1
                    else:
                        # Fallback: simple alternating assumption
                        if len(trades) % 2 == 0:
                            buy_count += 1
                        else:
                            sell_count += 1
                            
                except Exception:
                    continue
            
            if sell_count == 0:
                return 2.0  # High buy pressure if no sells
            
            ratio = buy_count / sell_count
            return round(min(5.0, max(0.1, ratio)), 2)  # Cap between 0.1 and 5.0
            
        except Exception as e:
            logger.warning(f"Buy/sell ratio calculation failed: {e}")
            return 1.0

    def _simple_security_gate(self, service_data: Dict[str, Any]) -> bool:
        """Simple security gate check"""
        try:
            goplus_data = service_data.get("goplus", {})
            if not goplus_data:
                return False  # No security data = fail
            
            # Check mint authority
            mintable = goplus_data.get("mintable", {})
            if isinstance(mintable, dict) and mintable.get("status") == "1":
                return False  # Mint authority active = fail
            
            # Check freeze authority
            freezable = goplus_data.get("freezable", {})
            if isinstance(freezable, dict) and freezable.get("status") == "1":
                return False  # Freeze authority active = fail
            
            # Check top holders concentration
            holders = goplus_data.get("holders", [])
            if holders and isinstance(holders, list):
                try:
                    top_10_total = 0.0
                    count = 0
                    for holder in holders[:10]:
                        if isinstance(holder, dict):
                            percent_str = holder.get("percent", "0")
                            percent = float(percent_str)
                            top_10_total += percent
                            count += 1
                            if count >= 10:
                                break
                    
                    if top_10_total > 30.0:  # Top 10 holders > 30%
                        return False
                        
                except Exception as e:
                    logger.warning(f"Holder concentration check failed: {e}")
                    return False
            
            return True  # Passed all checks
            
        except Exception as e:
            logger.warning(f"Security gate check failed: {e}")
            return False

    def _calculate_ranking_score(self, pump_data: Dict[str, Any]) -> float:
        """Calculate ranking score for pump comparison"""
        try:
            volume_recent = pump_data.get("volume_recent", 0)
            buy_sell_ratio = pump_data.get("buy_sell_ratio", 1.0)
            age_hours = pump_data.get("pool_age_hours", 168)
            
            # Formula: volume * buy_sell_ratio / age_hours
            safe_age = max(age_hours, 0.1)  # Prevent division by zero
            ranking_score = (volume_recent * buy_sell_ratio) / safe_age
            
            return round(ranking_score, 2)
            
        except Exception as e:
            logger.warning(f"Ranking score calculation failed: {e}")
            return 0.0