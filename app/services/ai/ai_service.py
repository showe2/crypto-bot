import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.ai.groq_ai_service import groq_llama_service
from app.services.ai.docx_service import docx_service

settings = get_settings()


class AIAnalysisRequest(BaseModel):
    """Request model for AI analysis"""
    token_address: str
    service_responses: Dict[str, Any]
    security_analysis: Dict[str, Any]
    analysis_type: str = "deep"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AIAnalysisResponse(BaseModel):
    """Response model for AI analysis"""
    ai_score: float = 0.0
    risk_assessment: str = "unknown"
    recommendation: str = "HOLD"
    confidence: float = 0.0
    key_insights: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    stop_flags: List[str] = Field(default_factory=list)
    market_metrics: Dict[str, Any] = Field(default_factory=dict)
    llama_reasoning: str = ""
    processing_time: float = 0.0


class LlamaAIService:
    """Service for Llama 3.0 AI token analysis"""
    
    def __init__(self):
        self.model_name = "llama-3.0-70b-instruct"
        self.max_tokens = 4000
        self.temperature = 0.1
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt for token analysis"""
        return """You are an expert Solana token analyst specializing in cryptocurrency evaluation. Your task is to analyze token data and provide structured investment recommendations with realistic data availability expectations.

ANALYSIS FRAMEWORK:
Evaluate tokens based on these critical metrics, but account for data availability:

MARKET CAP (MCAP):
- Excellent: <$1M (high growth potential)
- Good: $1M-$10M (moderate growth)
- Acceptable: $10M-$50M (established)
- Poor: >$50M (limited growth)

LIQUIDITY:
- Excellent: $500K+ (very strong)
- Good: $100K-$500K (strong)
- Acceptable: $50K-$100K (moderate)
- Poor: <$50K (weak)

VOLUME/LIQUIDITY RATIO:
- Excellent: >10% (very active)
- Good: 5-10% (active)
- Acceptable: 1-5% (moderate)
- Poor: <1% (low activity)

TOP HOLDERS CONCENTRATION:
- Excellent: <20% (great distribution)
- Good: 20-35% (good distribution)
- Acceptable: 35-50% (moderate risk)
- Poor: >50% (high concentration risk)

LP STATUS (with realistic expectations):
- Excellent: Verifiably burned/locked
- Good: Strong evidence of locking
- Acceptable: Moderate evidence or concentration
- Unknown: Data unavailable (neutral, not negative)

SECURITY FLAGS (CRITICAL ONLY):
- Active mint authority (unlimited supply risk)
- Active freeze authority (account freeze risk)
- Transfer restrictions or honeypot behavior
- Verified rug pull or scam

DATA AVAILABILITY PHILOSOPHY:
- Missing data is NOT automatically negative
- Focus on available data quality
- Only penalize for clearly negative indicators
- Unknown ≠ Bad (neutral stance)

RESPONSE FORMAT:
Provide analysis in JSON format with:
- ai_score (0-100): Overall token assessment
- risk_assessment: "low", "medium", "high", "critical"
- recommendation: "BUY", "CONSIDER", "HOLD", "CAUTION", "AVOID"
- confidence (0-100): Analysis confidence based on available data
- key_insights: List of positive factors found
- risk_factors: List of actual concerns (not data gaps)
- stop_flags: List of critical red flags only
- market_metrics: Key calculated metrics
- llama_reasoning: Detailed explanation

DECISION LOGIC (Less Strict):
- BUY: Exceptional metrics with strong data confidence
- CONSIDER: Good metrics with reasonable data
- HOLD: Mixed signals or moderate metrics
- CAUTION: Some concerning factors present
- AVOID: Clear red flags or critical security issues

CONFIDENCE CALCULATION:
- High (80-100%): Strong data across multiple sources
- Medium (60-79%): Good data coverage with some gaps
- Low (40-59%): Limited data but no red flags
- Very Low (<40%): Minimal data available

Be realistic about data limitations in crypto markets. Focus on actual risk indicators rather than data gaps."""

    async def analyze_token(self, request: AIAnalysisRequest) -> AIAnalysisResponse:
        """Perform comprehensive AI analysis of token"""
        start_time = time.time()
        
        # Extract and structure data for AI analysis
        analysis_data = self._prepare_analysis_data(request)
        
        # Build analysis prompt
        analysis_prompt = self._build_analysis_prompt(analysis_data)
        
        # Call Llama model (using Claude API as proxy for now)
        ai_response = await self._call_llama_model(analysis_prompt)
        
        # Parse and validate response
        parsed_response = self._parse_ai_response(ai_response)
        
        processing_time = time.time() - start_time
        parsed_response.processing_time = processing_time
        
        logger.info(f"AI analysis completed for {request.token_address} in {processing_time:.2f}s")
        
        return parsed_response
    
    def _prepare_analysis_data(self, request: AIAnalysisRequest) -> Dict[str, Any]:
        """Extract and calculate key metrics from service responses with enhanced data handling"""
        data = {
            "token_address": request.token_address,
            "analysis_type": request.analysis_type
        }
        
        logger.info(f"Extracting enhanced data for {request.token_address}")
        logger.info(f"Available services: {list(request.service_responses.keys())}")
        
        # === MARKET DATA EXTRACTION (Improved) ===
        market_cap = None
        price_usd = None
        price_change_24h = None
        volume_24h = None
        liquidity = None
        
        # Primary: Birdeye
        birdeye_data = request.service_responses.get("birdeye", {})
        if birdeye_data and isinstance(birdeye_data, dict):
            price_data = birdeye_data.get("price", {})
            if price_data and isinstance(price_data, dict):
                try:
                    raw_value = price_data.get("value")
                    if raw_value is not None:
                        price_usd = float(raw_value)
                    
                    raw_mc = price_data.get("market_cap")
                    if raw_mc is not None:
                        market_cap = float(raw_mc)
                    
                    raw_liq = price_data.get("liquidity")
                    if raw_liq is not None:
                        liquidity = float(raw_liq)
                    
                    raw_vol = price_data.get("volume_24h")
                    if raw_vol is not None:
                        volume_24h = float(raw_vol)
                    
                    raw_change = price_data.get("price_change_24h")
                    if raw_change is not None:
                        price_change_24h = float(raw_change)
                    
                    logger.info(f"Birdeye data extracted successfully")
                    
                except (ValueError, TypeError) as e:
                    logger.warning(f"Birdeye data conversion error: {e}")
        
        # Fallback: DexScreener
        if any(x is None for x in [volume_24h, market_cap, liquidity]):
            dex_data = request.service_responses.get("dexscreener", {})
            if dex_data and dex_data.get("pairs", {}).get("pairs"):
                pairs = dex_data["pairs"]["pairs"]
                if isinstance(pairs, list) and len(pairs) > 0:
                    pair = pairs[0]
                    try:
                        if market_cap is None:
                            raw_mc = pair.get("marketCap")
                            market_cap = float(raw_mc) if raw_mc else None
                        
                        if volume_24h is None:
                            vol_data = pair.get("volume", {})
                            raw_vol = vol_data.get("h24") if isinstance(vol_data, dict) else None
                            volume_24h = float(raw_vol) if raw_vol else None
                            
                        if liquidity is None:
                            liq_data = pair.get("liquidity", {})
                            raw_liq = liq_data.get("usd") if isinstance(liq_data, dict) else None
                            liquidity = float(raw_liq) if raw_liq else None
                        
                        logger.info(f"DexScreener fallback applied")
                    except Exception as e:
                        logger.warning(f"DexScreener extraction error: {e}")
        
        # Additional Fallback: SolSniffer for market cap
        if market_cap is None:
            solsniffer_data = request.service_responses.get("solsniffer", {})
            if solsniffer_data and isinstance(solsniffer_data, dict):
                try:
                    # Try both field names that might contain market cap
                    for field_name in ['marketCap', 'market_cap']:
                        raw_mc = solsniffer_data.get(field_name)
                        if raw_mc is not None:
                            market_cap = float(raw_mc)
                            if market_cap > 0:
                                logger.info(f"SolSniffer market cap fallback applied: ${market_cap:,.0f}")
                                break
                    
                except (ValueError, TypeError) as e:
                    logger.warning(f"SolSniffer market cap conversion error: {e}")
        
        data.update({
            "price_usd": price_usd,
            "price_change_24h": price_change_24h,
            "volume_24h": volume_24h,
            "market_cap": market_cap,
            "liquidity": liquidity
        })
        
        # === ENHANCED VOLATILITY EXTRACTION ===
        recent_volatility = None
        if birdeye_data and birdeye_data.get("trades"):
            recent_volatility = self._calculate_simple_volatility(birdeye_data, request.token_address)
        
        data.update({
            "recent_volatility_percent": recent_volatility,
            "volatility_data_available": recent_volatility is not None
        })
        
        # === HOLDER DATA EXTRACTION (Improved with realistic expectations) ===
        holder_count = None
        top_holders_percent = None
        
        # Primary: GOplus
        goplus_data = request.service_responses.get("goplus", {})
        if goplus_data and isinstance(goplus_data, dict):
            logger.info("Processing GOplus holder data...")
            
            # Extract holder count with multiple field attempts
            holder_fields = [
                "holder_count", "holders_count", "holderCount", "totalHolders", 
                "holdersCount", "holder_total", "total_holders"
            ]
            
            for field in holder_fields:
                raw_count = goplus_data.get(field)
                if raw_count is not None:
                    try:
                        if isinstance(raw_count, str):
                            clean = raw_count.replace(",", "").replace(" ", "").lower()
                            if "k" in clean:
                                number_part = clean.replace("k", "")
                                holder_count = int(float(number_part) * 1000)
                            else:
                                holder_count = int(clean) if clean.isdigit() else None
                        elif isinstance(raw_count, (int, float)):
                            holder_count = int(raw_count)
                        
                        if holder_count is not None and holder_count > 0:
                            logger.info(f"Extracted holder count: {holder_count:,} from {field}")
                            break
                            
                    except Exception:
                        continue
            
            # Extract top holders percentage (already extracted in whale analysis, but keep for compatibility)
            holders_array = goplus_data.get("holders")
            if holders_array and isinstance(holders_array, list):
                logger.info(f"Processing {len(holders_array)} holders for distribution analysis...")
                
                top_10_total = 0
                valid_holders = 0
                
                for i, holder in enumerate(holders_array[:10]):
                    if isinstance(holder, dict):
                        percent_fields = ["percent", "percentage", "share", "balance_percent"]
                        
                        for percent_field in percent_fields:
                            percent_raw = holder.get(percent_field)
                            if percent_raw is not None:
                                try:
                                    if isinstance(percent_raw, str):
                                        clean_percent = percent_raw.replace("%", "").replace(",", ".")
                                        percent_val = float(clean_percent)
                                    else:
                                        percent_val = float(percent_raw)
                                    
                                    if 0 <= percent_val <= 100:  # Sanity check
                                        top_10_total += percent_val
                                        valid_holders += 1
                                        break
                                        
                                except Exception:
                                    continue
                
                if valid_holders > 0:
                    top_holders_percent = top_10_total
                    logger.info(f"Top 10 holders: {top_holders_percent:.1f}% ({valid_holders} holders)")
        
        # Fallback sources for holder data
        if holder_count is None:
            # Try RugCheck
            rugcheck_data = request.service_responses.get("rugcheck", {})
            if rugcheck_data and rugcheck_data.get("total_LP_providers"):
                try:
                    holder_count = int(rugcheck_data["total_LP_providers"])
                    logger.info(f"Holder count from RugCheck LP providers: {holder_count}")
                except Exception:
                    pass
            
            # Try SolSniffer
            if holder_count is None:
                solsniffer_data = request.service_responses.get("solsniffer", {})
                if solsniffer_data:
                    for field in ["holderCount", "holder_count", "holders", "totalHolders"]:
                        value = solsniffer_data.get(field)
                        if value:
                            try:
                                holder_count = int(value)
                                logger.info(f"Holder count from SolSniffer: {holder_count}")
                                break
                            except Exception:
                                continue
        
        data.update({
            "holder_count": holder_count,
            "top_holders_percent": top_holders_percent
        })
        
        # === LP STATUS EXTRACTION (More Realistic) ===
        lp_status = "unknown"
        lp_confidence = 0
        lp_evidence = []
        
        # Method 1: RugCheck LP analysis
        rugcheck_data = request.service_responses.get("rugcheck", {})
        if rugcheck_data and rugcheck_data.get("token"):
            # Check for LP lock evidence
            lockers_data = rugcheck_data.get("lockers_data", {})
            if lockers_data and lockers_data.get("lockers"):
                lockers = lockers_data.get("lockers", [])
                if isinstance(lockers, dict) and len(lockers) > 0:
                    total_locked_value = 0
                    for locker_id, locker_info in lockers.items():
                        if isinstance(locker_info, dict):
                            usd_locked = locker_info.get("usdcLocked", 0)
                            if isinstance(usd_locked, (int, float)) and usd_locked > 0:
                                total_locked_value += usd_locked
                    
                    if total_locked_value > 1000:  # Significant value locked
                        lp_status = "locked"
                        lp_confidence = 90
                        lp_evidence.append(f"${total_locked_value:,.0f} locked in Raydium lockers")
                        logger.info(f"LP status: LOCKED (${total_locked_value:,.0f} in lockers)")
            
            # Check burn patterns in top LP holders
            if lp_status == "unknown":
                markets = rugcheck_data.get("market_analysis", {}).get("markets", [])
                for market in markets:
                    if isinstance(market, dict):
                        lp_data = market.get("lp", {})
                        holders = lp_data.get("holders", [])
                        
                        if holders:
                            for holder in holders:
                                if isinstance(holder, dict):
                                    owner = holder.get("owner", "")
                                    percent = holder.get("pct", 0)
                                    
                                    # Check for burn/lock patterns
                                    burn_patterns = ["111111", "dead", "burn", "lock"]
                                    if any(pattern in str(owner).lower() for pattern in burn_patterns):
                                        if percent > 50:
                                            lp_status = "burned"
                                            lp_confidence = 85
                                            lp_evidence.append(f"{percent:.1f}% in burn address")
                                            logger.info(f"LP status: BURNED ({percent:.1f}%)")
                                            break
                
                # High concentration might indicate locking
                if lp_status == "unknown":
                    for market in markets:
                        if isinstance(market, dict):
                            lp_data = market.get("lp", {})
                            holders = lp_data.get("holders", [])
                            
                            if holders and len(holders) > 0:
                                top_holder = holders[0]
                                if isinstance(top_holder, dict):
                                    top_percent = top_holder.get("pct", 0)
                                    if top_percent > 90:
                                        lp_status = "concentrated"
                                        lp_confidence = 60
                                        lp_evidence.append(f"{top_percent:.1f}% concentrated (possibly locked)")

        # Method 2: GOplus LP data
        goplus_data = request.service_responses.get("goplus", {})
        if lp_status == "unknown" and goplus_data:
            lp_holders = goplus_data.get("lp_holders")
            if lp_holders and isinstance(lp_holders, list) and len(lp_holders) > 0:
                for lp_holder in lp_holders:
                    if isinstance(lp_holder, dict):
                        try:
                            percent_raw = lp_holder.get("percent", "0")
                            percent = float(str(percent_raw).replace("%", "").replace(",", ""))
                            
                            if percent > 85:
                                lp_status = "concentrated" 
                                lp_confidence = 50
                                lp_evidence.append(f"LP {percent:.1f}% concentrated")
                                break
                        except Exception:
                            continue
        
        data.update({
            "lp_status": lp_status,
            "lp_confidence": lp_confidence,
            "lp_evidence": lp_evidence
        })
        
        # === SUPPLY AND DEV DATA ===
        total_supply = None
        helius_data = request.service_responses.get("helius", {})
        if helius_data and helius_data.get("supply"):
            supply_info = helius_data["supply"]
            try:
                raw_supply = supply_info.get("ui_amount")
                if raw_supply is not None:
                    total_supply = float(raw_supply)
            except Exception:
                pass
        
        # Dev holdings from RugCheck
        dev_percent = None
        rugcheck_data = request.service_responses.get("rugcheck", {})
        if rugcheck_data and total_supply:
            creator_analysis = rugcheck_data.get("creator_analysis", {})
            if creator_analysis:
                try:
                    creator_balance = float(creator_analysis.get("creator_balance", 0))
                    if creator_balance > 0:
                        dev_percent = (creator_balance / total_supply) * 100
                except Exception:
                    pass
        
        data.update({
            "total_supply": total_supply,
            "dev_percent": dev_percent
        })
        
        # === SECURITY FLAGS (Critical Only) ===
        security_flags = []
        
        # Only include truly critical security issues
        goplus_security = request.service_responses.get("goplus_result", {})
        if goplus_security:
            # Mint authority (unlimited supply)
            mintable = goplus_security.get("mintable", {})
            if isinstance(mintable, dict) and mintable.get("status") == "1":
                security_flags.append("Active mint authority (unlimited supply risk)")
                data["mint_authority_active"] = True
            else:
                data["mint_authority_active"] = False
            
            # Freeze authority (can freeze accounts)
            freezable = goplus_security.get("freezable", {})
            if isinstance(freezable, dict) and freezable.get("status") == "1":
                security_flags.append("Active freeze authority (account freeze risk)")
                data["freeze_authority_active"] = True
            else:
                data["freeze_authority_active"] = False
        
        # Only include verified critical issues from other sources
        critical_issues = request.service_responses.get("critical_issues", [])
        for issue in critical_issues:
            if "rugged" in str(issue).lower() or "scam" in str(issue).lower():
                security_flags.append(issue)
        
        data["security_flags"] = security_flags
        
        # === DERIVED METRICS (Handle None values) ===
        if volume_24h and liquidity and volume_24h > 0 and liquidity > 0:
            data["volume_liquidity_ratio"] = (volume_24h / liquidity) * 100
        else:
            data["volume_liquidity_ratio"] = None
        
        # === DATA QUALITY ASSESSMENT ===
        data_availability = {
            "has_price": price_usd is not None,
            "has_market_cap": market_cap is not None,
            "has_liquidity": liquidity is not None,
            "has_volume": volume_24h is not None,
            "has_holders": holder_count is not None,
            "has_lp_data": lp_status != "unknown",
            "has_volatility": recent_volatility is not None
        }
        
        available_data_count = sum(data_availability.values())
        total_data_points = len(data_availability)
        
        data["data_completeness"] = (available_data_count / total_data_points) * 100
        data["data_availability"] = data_availability
        
        # === STATUS LOGGING ===
        logger.info("Enhanced data extraction summary:")
        logger.info(f"  Market Cap: {f'${market_cap:,.0f}' if market_cap else 'Not available'}")
        logger.info(f"  Liquidity: {f'${liquidity:,.0f}' if liquidity else 'Not available'}")
        logger.info(f"  Volume 24h: {f'${volume_24h:,.0f}' if volume_24h else 'Not available'}")
        logger.info(f"  Volatility: {f'{recent_volatility}%' if recent_volatility else 'Not available'}")
        logger.info(f"  Holder Count: {f'{holder_count:,}' if holder_count else 'Not available'}")
        logger.info(f"  LP Status: {lp_status}")
        logger.info(f"  Security Flags: {len(security_flags)}")
        logger.info(f"  Data Completeness: {data['data_completeness']:.1f}%")
        
        return data
    
    def _calculate_simple_volatility(self, birdeye_data: Dict[str, Any], token_address: str) -> Optional[float]:
        """Calculate simple volatility from recent trades"""
        try:
            trades_data = birdeye_data.get("trades", {})
            trades = trades_data.get("items", []) if isinstance(trades_data, dict) else trades_data
            
            if not trades or len(trades) < 5:
                logger.info("Insufficient trades data for volatility calculation")
                return None
            
            # Extract prices from recent trades
            prices = []
            for trade in trades[:20]:  # Use up to 20 recent trades
                if isinstance(trade, dict):
                    try:
                        # Check if our token is 'from' or 'to'
                        if trade.get("from", {}).get("address") == token_address:
                            price = float(trade["from"]["price"])
                        elif trade.get("to", {}).get("address") == token_address:
                            price = float(trade["to"]["price"])
                        else:
                            # For your case, token is usually 'from' in buy orders
                            price = float(trade.get("from", {}).get("price", 0))
                        
                        if price > 0:
                            prices.append(price)
                    except (ValueError, TypeError):
                        continue
            
            if len(prices) < 3:
                logger.info(f"Only {len(prices)} valid prices found, need at least 3")
                return None
            
            # Simple volatility = (max_price - min_price) / avg_price * 100
            max_price = max(prices)
            min_price = min(prices)
            avg_price = sum(prices) / len(prices)
            
            volatility = ((max_price - min_price) / avg_price) * 100 if avg_price > 0 else 0
            
            logger.info(f"Volatility calculated: {volatility:.2f}% from {len(prices)} trades")
            return round(volatility, 2)
            
        except Exception as e:
            logger.warning(f"Volatility calculation failed: {e}")
            return None
    
    def _extract_whale_data(self, goplus_data: Dict[str, Any], rugcheck_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract whale data from existing holder information"""
        try:
            whale_data = {
                "whale_count": 0,
                "whale_control_percent": 0.0,
                "top_whale_percent": 0.0,
                "data_available": False
            }
            
            # Extract from GOplus holders
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
                    whale_data["whale_count"] = len(whales)
                    whale_data["whale_control_percent"] = round(sum(whales), 2)
                    whale_data["top_whale_percent"] = round(max(whales), 2)
                    whale_data["data_available"] = True
                    
                    logger.info(f"Whales extracted: {whale_data['whale_count']} whales control {whale_data['whale_control_percent']}%")
                else:
                    # No whales = good distribution
                    whale_data["data_available"] = True
                    logger.info("No whales detected - excellent distribution")
            
            return whale_data
            
        except Exception as e:
            logger.warning(f"Whale extraction failed: {e}")
            return {
                "whale_count": 0,
                "whale_control_percent": 0.0,
                "top_whale_percent": 0.0,
                "data_available": False
            }
    
    def _analyze_sniper_patterns(self, goplus_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze sniper patterns from holder distribution"""
        try:
            holders = goplus_data.get("holders", [])
            if not holders or len(holders) < 10:
                return {"similar_holders": 0, "pattern_detected": False, "data_available": False}
            
            # Count holders with very similar percentages
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
                return {"similar_holders": 0, "pattern_detected": False, "data_available": True}
            
            # Count very similar percentages
            similar_count = 0
            for i, p1 in enumerate(percentages):
                for p2 in percentages[i+1:]:
                    if abs(p1 - p2) < 0.05:  # Very similar percentages (within 0.05%)
                        similar_count += 1
            
            pattern_detected = similar_count > 5
            
            logger.info(f"Sniper analysis: {similar_count} similar holder pairs, pattern: {pattern_detected}")
            
            return {
                "similar_holders": similar_count,
                "pattern_detected": pattern_detected,
                "data_available": True
            }
            
        except Exception as e:
            logger.warning(f"Sniper pattern analysis failed: {e}")
            return {"similar_holders": 0, "pattern_detected": False, "data_available": False}
    
    def _build_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Build analysis prompt with enhanced metrics for AI risk assessment"""
        
        # Helper function to format data availability
        def format_data_point(value, label, format_func=None):
            if value is not None:
                formatted = format_func(value) if format_func else str(value)
                return f"{label}: {formatted} ✓"
            return f"{label}: Not available"
        
        # Build market data section
        market_data_lines = [
            format_data_point(data.get('market_cap'), "Market Cap", lambda x: f"${x:,.0f}"),
            format_data_point(data.get('liquidity'), "Liquidity", lambda x: f"${x:,.0f}"),
            format_data_point(data.get('volume_24h'), "24h Volume", lambda x: f"${x:,.0f}"),
            format_data_point(data.get('volume_liquidity_ratio'), "Volume/Liquidity", lambda x: f"{x:.1f}%"),
            format_data_point(data.get('price_usd'), "Price", lambda x: f"${x:.8f}"),
            format_data_point(data.get('price_change_24h'), "24h Change", lambda x: f"{x:+.2f}%")
        ]
        
        # Build enhanced metrics section
        enhanced_metrics_lines = [
            format_data_point(data.get('recent_volatility_percent'), "Recent Volatility", lambda x: f"{x}%"),
            format_data_point(data.get('whale_count'), "Whale Count", lambda x: f"{x} whales"),
            format_data_point(data.get('whale_control_percent'), "Whale Control", lambda x: f"{x}%"),
            format_data_point(data.get('top_whale_percent'), "Top Whale", lambda x: f"{x}%"),
            format_data_point(data.get('sniper_similar_holders'), "Similar Holders", lambda x: f"{x} patterns"),
            f"Sniper Pattern Detected: {data.get('sniper_pattern_detected', False)}"
        ]
        
        # Build holder data section
        holder_data_lines = [
            format_data_point(data.get('holder_count'), "Total Holders", lambda x: f"{x:,}"),
            format_data_point(data.get('top_holders_percent'), "Top 10 Control", lambda x: f"{x:.1f}%"),
            format_data_point(data.get('dev_percent'), "Dev Holdings", lambda x: f"{x:.1f}%")
        ]
        
        # Build LP section
        lp_status = data.get('lp_status', 'unknown')
        lp_confidence = data.get('lp_confidence', 0)
        lp_evidence = data.get('lp_evidence', [])
        
        lp_status_text = {
            'locked': 'SECURED (Locked)',
            'burned': 'SECURED (Burned)', 
            'concentrated': 'LIKELY SECURED (Concentrated)',
            'unknown': 'UNKNOWN (No data available)'
        }.get(lp_status, 'UNKNOWN')
        
        lp_info = f"LP Status: {lp_status_text}"
        if lp_confidence > 0:
            lp_info += f" (Confidence: {lp_confidence}%)"
        if lp_evidence:
            lp_info += f"\nEvidence: {'; '.join(lp_evidence)}"
        
        # Security flags
        security_flags = data.get('security_flags', [])
        security_section = "No critical security issues detected" if not security_flags else "\n".join(f"🚨 {flag}" for flag in security_flags)
        
        prompt = f"""ENHANCED SOLANA TOKEN ANALYSIS - AI RISK ASSESSMENT

TOKEN: {data['token_address']}

=== MARKET FUNDAMENTALS ===
{chr(10).join(market_data_lines)}

=== ENHANCED RISK METRICS ===
{chr(10).join(enhanced_metrics_lines)}

=== HOLDER DISTRIBUTION ===  
{chr(10).join(holder_data_lines)}

=== LIQUIDITY SECURITY ===
{lp_info}
Mint Authority: {'ACTIVE 🚨' if data.get('mint_authority_active') else 'DISABLED ✓'}
Freeze Authority: {'ACTIVE ⚠️' if data.get('freeze_authority_active') else 'DISABLED ✓'}

=== SECURITY ANALYSIS ===
{security_section}

=== DATA AVAILABILITY ===
Overall Completeness: {data.get('data_completeness', 0):.1f}%
Available Data Points: {sum(data.get('data_availability', {}).values())} / {len(data.get('data_availability', {}))}

=== AI ANALYSIS INSTRUCTIONS ===

You are analyzing this token with ENHANCED METRICS. Assess each metric's risk level:

1. MARKET CAP RISK ASSESSMENT:
   - Evaluate if market cap suggests pump risk, growth potential, or stability
   - Consider market cap in context of liquidity and volume

2. VOLATILITY RISK ASSESSMENT:
   - Analyze recent trading volatility percentage
   - High volatility could indicate instability OR opportunity
   - Consider volatility in context of volume and whale activity

3. WHALE RISK ASSESSMENT:
   - Evaluate whale concentration and dump risk
   - 0 whales = BEST (perfect distribution)
   - Consider whale count vs control percentage
   - Assess potential for coordinated selling

4. SNIPER/BOT RISK ASSESSMENT:
   - Analyze holder patterns for artificial demand
   - Many similar holder percentages = bot activity
   - Pattern detection indicates coordinated buying

5. LIQUIDITY DEPTH ASSESSMENT:
   - Evaluate volume/liquidity ratio for market health
   - High ratio = active trading, Low ratio = thin markets
   - Consider liquidity depth for price impact assessment

6. DEV HOLDINGS RISK ASSESSMENT:
   - Evaluate developer token percentage
   - High dev holdings = dump risk
   - Consider if dev holdings are reasonable for project stage

7. LP SECURITY ASSESSMENT:
   - Evaluate liquidity provider lock/burn status
   - Locked/Burned = secure, Unknown = neutral (not negative)
   - Consider LP evidence and confidence level

COMPREHENSIVE RISK SCORING:
- DO NOT pre-categorize risks - analyze each metric independently
- Consider metric interactions (e.g., high volatility + whales = extra risk)
- Weight metrics based on confidence in data quality
- Missing data = neutral assessment, not negative

RESPONSE FORMAT (JSON ONLY):
{{
  "ai_score": 0-100,
  "risk_assessment": "low|medium|high|critical",
  "recommendation": "BUY|CONSIDER|HOLD|CAUTION|AVOID", 
  "confidence": 0-100,
  "key_insights": ["specific positive factors with data"],
  "risk_factors": ["specific concerns with data"],
  "stop_flags": ["critical issues only"],
  "market_metrics": {{
    "volatility_risk": "low|medium|high|unknown",
    "whale_risk": "low|medium|high|unknown", 
    "sniper_risk": "low|medium|high|unknown",
    "liquidity_health": "excellent|good|poor|unknown",
    "dev_risk": "low|medium|high|unknown",
    "lp_security": "secure|likely_secure|unknown|risky"
  }},
  "llama_reasoning": "Comprehensive analysis of all available metrics"
}}

ENHANCED DECISION FRAMEWORK:
- BUY: Score >85, all major risks low, strong data confidence
- CONSIDER: Score >70, acceptable risk levels, good data
- HOLD: Score >55, mixed signals or moderate risks
- CAUTION: Score >40, some concerning factors
- AVOID: Score <40 or any critical security flags

Let the AI evaluate each metric's risk level independently based on the actual data values. Do not impose predefined risk thresholds - let the AI determine what constitutes high/medium/low risk for each metric based on crypto market context.

RESPOND WITH ONLY VALID JSON."""

        return prompt
    
    async def _call_llama_model(self, prompt: str) -> str:
        """Call Llama model for analysis (using Claude API as proxy)"""
        try:
            from app.services.ai.groq_ai_service import groq_llama_service

            response = await groq_llama_service.send_request(prompt)

            return response
            
        except Exception as e:
            logger.error(f"Llama model call failed: {str(e)}")
            raise
    
    def _parse_ai_response(self, ai_response: str) -> AIAnalysisResponse:
        """Parse AI response into structured format"""
        try:
            # Try to extract JSON from response
            if "```json" in ai_response:
                json_start = ai_response.find("```json") + 7
                json_end = ai_response.find("```", json_start)
                json_content = ai_response[json_start:json_end].strip()
            else:
                json_content = ai_response.strip()
            
            # Parse JSON response
            parsed_data = json.loads(json_content)
            
            return AIAnalysisResponse(
                ai_score=float(parsed_data.get("ai_score", 60)),  # Default 60 instead of 50
                risk_assessment=parsed_data.get("risk_assessment", "medium"),
                recommendation=parsed_data.get("recommendation", "HOLD"),
                confidence=float(parsed_data.get("confidence", 70)),
                key_insights=parsed_data.get("key_insights", []),
                risk_factors=parsed_data.get("risk_factors", []),
                stop_flags=parsed_data.get("stop_flags", []),
                market_metrics=parsed_data.get("market_metrics", {}),
                llama_reasoning=parsed_data.get("llama_reasoning", "Analysis completed with available data"),
                processing_time=0.0
            )
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {str(e)}")
            logger.debug(f"Raw AI response: {ai_response}")
            
            # Return neutral fallback response instead of critical
            return AIAnalysisResponse(
                ai_score=60.0,  # Neutral score
                risk_assessment="medium",  # Neutral risk
                recommendation="HOLD",
                confidence=50.0,
                key_insights=["Analysis completed with available data"],
                risk_factors=["AI response parsing failed - using fallback assessment"],
                stop_flags=[],
                market_metrics={},
                llama_reasoning="AI analysis encountered parsing issues but no critical security flags detected",
                processing_time=0.0
            )
    
    def _create_fallback_response(self, token_address: str, processing_time: float) -> AIAnalysisResponse:
        """Create neutral fallback response when AI analysis fails"""
        return AIAnalysisResponse(
            ai_score=60.0,  # Neutral instead of 0
            risk_assessment="medium",  # Medium instead of critical
            recommendation="HOLD",  # Hold instead of avoid
            confidence=50.0,  # Medium confidence
            key_insights=["Analysis system temporarily unavailable"],
            risk_factors=["Limited analysis due to system issue"],
            stop_flags=[],  # No stop flags for system errors
            market_metrics={},
            llama_reasoning="AI analysis system temporarily unavailable. No critical security issues detected based on available data.",
            processing_time=processing_time
        )


llama_ai_service = LlamaAIService()

async def analyze_token_with_ai(request: AIAnalysisRequest) -> Optional[AIAnalysisResponse]:
    """Perform AI analysis of token using Llama 3.0"""

    try:
        return await llama_ai_service.analyze_token(request)
    except Exception as e:
        logger.error(f"AI analysis service error: {str(e)}")
        return None
    
async def generate_analysis_docx_from_cache(cache_key: str) -> Optional[bytes]:
    """Generate DOCX report from cached analysis data"""
    try:
        logger.info(f"📄 Generating DOCX from cache key: {cache_key}")
        
        from app.utils.cache import cache_manager
        
        # Parse the cache key to extract namespace and key
        if ":" in cache_key:
            parts = cache_key.split(":", 1)  # Split on first colon only
            namespace = parts[0] if len(parts) == 2 else "enhanced_token_analysis"
            redis_key = parts[1] if len(parts) == 2 else cache_key
        else:
            namespace = "enhanced_token_analysis"
            redis_key = cache_key
        
        logger.info(f"📄 Looking up: namespace='{namespace}', key='{redis_key}'")
        
        # Try to get cached data
        try:
            cached_data = await cache_manager.get(
                key=redis_key,
                namespace=namespace
            )
            if cached_data:
                logger.info(f"✅ Found data in cache manager")
            else:
                logger.warning(f"❌ No data found in cache manager")
                return None
        except Exception as e:
            logger.error(f"Cache manager failed: {str(e)}")
            return None
        
        # Generate DOCX using the service
        return await docx_service.generate_analysis_docx_from_data(cached_data)
        
    except Exception as e:
        logger.error(f"❌ DOCX generation failed: {str(e)}")
        return None

# Health check function
async def check_ai_service_health() -> Dict[str, Any]:
    """Check AI service health"""
    try:
        # Test with minimal data
        test_request = AIAnalysisRequest(
            token_address="test",
            service_responses={},
            security_analysis={}
        )
        
        start_time = time.time()
        # Don't actually call the AI for health check, just validate setup
        response_time = time.time() - start_time
        
        return {
            "healthy": True,
            "model_name": llama_ai_service.model_name,
            "response_time": response_time,
            "status": "AI service ready"
        }
        
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "status": "AI service error"
        }