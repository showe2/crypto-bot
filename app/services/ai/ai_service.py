import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.ai.groq_ai_service import groq_llama_service

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
        self.model_name = "llama-3.0-70b-instruct"  # Configure based on your setup
        self.max_tokens = 4000
        self.temperature = 0.1  # Low temperature for consistent analysis
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt for token analysis"""
        return """You are an expert Solana token analyst specializing in meme coin evaluation. Your task is to analyze token data and provide structured investment recommendations.

ANALYSIS FRAMEWORK:
You must evaluate tokens based on these critical metrics with specific thresholds:

MARKET CAP (MCAP):
- Excellent: <$1M (high growth potential)
- Acceptable: $1M-$10M (moderate growth)
- Poor: >$50M (limited growth)

LIQUIDITY:
- Excellent: $200K-$2M (optimal for pumps)
- Acceptable: $50K-$200K or $2M-$5M
- Poor: <$50K (rug risk) or >$10M (too heavy)

VOLUME/LIQUIDITY RATIO:
- Excellent: >20% (active trading)
- Acceptable: 5-20%
- Poor: <5% (dead token)

TOP 10 HOLDERS:
- Excellent: <15% (fair distribution)
- Acceptable: 15-30%
- Poor: >30% (dump risk)

DEV HOLDINGS:
- Excellent: <5% (safe)
- Acceptable: 5-10% (with vesting)
- Poor: >10% (rug risk)

SNIPERS/BUNDLERS:
- Excellent: <5% (clean launch)
- Acceptable: 5-10%
- Poor: >10% (manipulated)

LP STATUS:
- Excellent: 100% burned/locked
- Acceptable: Locked >6 months
- Poor: Unlocked (rug risk)

HOLDERS COUNT:
- Excellent: >1000 (strong community)
- Acceptable: 300-1000
- Poor: <300 (dead token)

SECURITY FLAGS (STOP FLAGS):
- Tax >5%
- LP not locked
- Mint/freeze authority active
- Transfer restrictions
- Honeypot indicators

RESPONSE FORMAT:
Provide analysis in JSON format with:
- ai_score (0-100): Overall token score
- risk_assessment: "low", "medium", "high", "critical"
- recommendation: "BUY", "CONSIDER", "HOLD", "CAUTION", "AVOID"
- confidence (0-100): Analysis confidence
- key_insights: List of positive factors
- risk_factors: List of concerns
- stop_flags: List of critical red flags
- market_metrics: Key calculated metrics
- llama_reasoning: Detailed explanation of your analysis

DECISION LOGIC:
- BUY: >70% metrics excellent, MCAP <$1M, no stop flags
- CONSIDER: 50-70% metrics good, manageable risks
- HOLD: Mixed signals, wait for better entry
- CAUTION: Multiple risk factors present
- AVOID: Stop flags present or >50% poor metrics

Be strict with security analysis. Any critical security issues should result in AVOID recommendation regardless of other metrics."""

    async def analyze_token(self, request: AIAnalysisRequest) -> AIAnalysisResponse:
        """Perform comprehensive AI analysis of token"""
        start_time = time.time()
        
        try:
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
            
        except Exception as e:
            logger.error(f"AI analysis failed for {request.token_address}: {str(e)}")
            
            # Return fallback analysis
            return self._create_fallback_response(request.token_address, time.time() - start_time)
    
    def _prepare_analysis_data(self, request: AIAnalysisRequest) -> Dict[str, Any]:
        """Extract and calculate key metrics from service responses"""
        data = {
            "token_address": request.token_address,
            "analysis_type": request.analysis_type
        }
        
        logger.info(f"🔧 ENHANCED DATA EXTRACTION for {request.token_address}")
        logger.info(f"Available services: {list(request.service_responses.keys())}")
        
        # === MARKET DATA EXTRACTION ===
        market_cap = 0
        price_usd = 0
        price_change_24h = 0
        volume_24h = 0
        liquidity = 0
        
        # Try Birdeye (primary source)
        birdeye_data = request.service_responses.get("birdeye", {})
        if birdeye_data:
            price_data = birdeye_data.get("price", {})
            if price_data and isinstance(price_data, dict):
                # Extract with null safety and type conversion
                try:
                    raw_value = price_data.get("value")
                    price_usd = float(raw_value) if raw_value is not None else 0
                    
                    raw_mc = price_data.get("market_cap") 
                    market_cap = float(raw_mc) if raw_mc is not None else 0
                    
                    raw_liq = price_data.get("liquidity")
                    liquidity = float(raw_liq) if raw_liq is not None else 0
                    
                    raw_vol = price_data.get("volume_24h")
                    volume_24h = float(raw_vol) if raw_vol is not None else 0
                    
                    raw_change = price_data.get("price_change_24h")
                    price_change_24h = float(raw_change) if raw_change is not None else 0
                    
                    logger.info(f"✅ Birdeye: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Liq=${liquidity:,.0f}")
                    
                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Birdeye data conversion error: {e}")
            else:
                logger.warning("❌ Birdeye has no price data or wrong format")
        
        # Try DexScreener fallback for missing market data
        if volume_24h == 0 or market_cap == 0:
            dex_data = request.service_responses.get("dexscreener", {})
            if dex_data and dex_data.get("pairs"):
                pairs = dex_data["pairs"]
                if isinstance(pairs, list) and len(pairs) > 0:
                    pair = pairs[0]
                    try:
                        if market_cap == 0:
                            raw_mc = pair.get("marketCap")
                            market_cap = float(raw_mc) if raw_mc else 0
                        
                        if volume_24h == 0:
                            vol_data = pair.get("volume", {})
                            raw_vol = vol_data.get("h24") if isinstance(vol_data, dict) else None
                            volume_24h = float(raw_vol) if raw_vol else 0
                        
                        logger.info(f"✅ DexScreener fallback: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}")
                    except Exception as e:
                        logger.error(f"❌ DexScreener extraction error: {e}")
        
        data.update({
            "price_usd": price_usd,
            "price_change_24h": price_change_24h,
            "volume_24h": volume_24h,
            "market_cap": market_cap,
            "liquidity": liquidity
        })
        
        # === HOLDER DATA EXTRACTION ===
        holder_count = 0
        top_10_holders_percent = 0
        
        # Primary: GOplus
        goplus_data = request.service_responses.get("goplus", {})
        if goplus_data and isinstance(goplus_data, dict):
            logger.info("👥 Processing GOplus holder data...")
            
            # Log full GOplus structure for debugging (first time only)
            logger.debug(f"GOplus full structure: {json.dumps(goplus_data, indent=2, default=str)[:1000]}...")
            
            # Try ALL possible holder count field names
            holder_fields = [
                "holder_count", "holders_count", "holderCount", "totalHolders", 
                "holdersCount", "holder_total", "total_holders"
            ]
            
            for field in holder_fields:
                raw_count = goplus_data.get(field)
                if raw_count is not None:
                    logger.info(f"  Found {field}: '{raw_count}' ({type(raw_count)})")
                    
                    try:
                        if isinstance(raw_count, str):
                            # Handle formats: "1,234", "1234", "1.2k", "1.2K"
                            clean = raw_count.replace(",", "").replace(" ", "").lower()
                            if "k" in clean:
                                number_part = clean.replace("k", "")
                                holder_count = int(float(number_part) * 1000)
                            else:
                                holder_count = int(clean) if clean.isdigit() else 0
                        elif isinstance(raw_count, (int, float)):
                            holder_count = int(raw_count)
                        
                        if holder_count > 0:
                            logger.info(f"  ✅ Extracted holder count: {holder_count:,} from {field}")
                            break
                            
                    except Exception as e:
                        logger.debug(f"  Failed to parse {field}: {e}")
                        continue
            
            # Extract top holders percentage
            holders_array = goplus_data.get("holders")
            if holders_array and isinstance(holders_array, list) and len(holders_array) > 0:
                logger.info(f"  Processing {len(holders_array)} holders for top 10 analysis...")
                
                top_10_total = 0
                valid_holders = 0
                
                for i, holder in enumerate(holders_array[:10]):
                    if isinstance(holder, dict):
                        # Try multiple percent field names
                        percent_fields = ["percent", "percentage", "share", "balance_percent"]
                        
                        for percent_field in percent_fields:
                            percent_raw = holder.get(percent_field)
                            if percent_raw is not None:
                                try:
                                    # Handle formats: "5.5%", "5.5", "5,5"
                                    if isinstance(percent_raw, str):
                                        clean_percent = percent_raw.replace("%", "").replace(",", ".")
                                        percent_val = float(clean_percent)
                                    else:
                                        percent_val = float(percent_raw)
                                    
                                    top_10_total += percent_val
                                    valid_holders += 1
                                    logger.debug(f"    Holder {i+1}: {percent_val:.2f}%")
                                    break
                                    
                                except Exception as e:
                                    logger.debug(f"    Failed to parse holder {i+1} {percent_field}: {e}")
                                    continue
                
                top_10_holders_percent = top_10_total
                logger.info(f"  ✅ Top 10 holders total: {top_10_holders_percent:.1f}% ({valid_holders} valid)")
            
            else:
                logger.warning("  ❌ No holders array or empty array in GOplus")
        
        else:
            logger.warning("❌ No GOplus data available for holder analysis")
        
        # Fallback: Try other services for holder count
        if holder_count == 0:
            logger.info("🔍 Trying fallback services for holder count...")
            
            # Try SolSniffer
            solsniffer_data = request.service_responses.get("solsniffer", {})
            if solsniffer_data:
                for field in ["holderCount", "holder_count", "holders", "totalHolders"]:
                    value = solsniffer_data.get(field)
                    if value:
                        try:
                            holder_count = int(value)
                            logger.info(f"  ✅ SolSniffer fallback: {holder_count:,} from {field}")
                            break
                        except Exception:
                            continue
            
            # Try any other service with holder data
            if holder_count == 0:
                for service_name, service_data in request.service_responses.items():
                    if service_name not in ["goplus", "solsniffer"] and isinstance(service_data, dict):
                        for key, value in service_data.items():
                            if "holder" in key.lower() and value:
                                try:
                                    holder_count = int(value)
                                    logger.info(f"  ✅ Emergency fallback: {holder_count:,} from {service_name}.{key}")
                                    break
                                except Exception:
                                    continue
                        if holder_count > 0:
                            break
        
        data.update({
            "holder_count": holder_count,
            "top_10_holders_percent": top_10_holders_percent
        })
        
        # === LP STATUS EXTRACTION ===
        lp_burned_locked = False
        lp_status_details = "Unknown - no data available"
        lp_confidence = 0  # 0-100 confidence in LP assessment
        
        rugcheck_data = request.service_responses.get("rugcheck", {})
        if rugcheck_data and isinstance(rugcheck_data, dict):
            logger.info("🔒 Analyzing LP security from RugCheck...")
            
            # Method 1: Direct LP lockers check
            lockers_data = rugcheck_data.get("lockers_data")
            if lockers_data and isinstance(lockers_data, dict):
                lockers = lockers_data.get("lockers", [])
                if isinstance(lockers, list) and len(lockers) > 0:
                    logger.info(f"  Found {len(lockers)} LP lockers")
                    
                    total_locked = 0
                    for locker in lockers:
                        if isinstance(locker, dict):
                            try:
                                percent = float(locker.get("percent", 0))
                                total_locked += percent
                                logger.debug(f"    Locker: {percent}%")
                            except Exception:
                                continue
                    
                    if total_locked > 70:  # Majority locked
                        lp_burned_locked = True
                        lp_status_details = f"LP {total_locked:.1f}% locked via lockers"
                        lp_confidence = 95
                        logger.info(f"✅ LP SECURED via lockers: {total_locked:.1f}%")
            
            # Method 2: Check top LP providers for concentration/burns
            if not lp_burned_locked:
                top_lp = rugcheck_data.get("top_LP_providers", [])
                if isinstance(top_lp, list) and len(top_lp) > 0:
                    logger.info(f"  Analyzing {len(top_lp)} LP providers...")
                    
                    max_concentration = 0
                    burn_detected = False
                    
                    for provider in top_lp:
                        if isinstance(provider, dict):
                            address = str(provider.get("address", ""))
                            try:
                                percent = float(provider.get("percent", 0))
                                max_concentration = max(max_concentration, percent)
                                
                                logger.debug(f"    LP Provider: {address[:20]}... ({percent}%)")
                                
                                # Check for burn address patterns (more comprehensive)
                                burn_patterns = [
                                    "1nc1nerator11111111111111111111111111111111",  # Full incinerator
                                    "11111111111111111111111111111111",             # System program  
                                    "1111111QLbz7VHgHozwV9qY1YDrCXK8",             # Common burn
                                    "dead", "burn", "lock", "vault"
                                ]
                                
                                address_lower = address.lower()
                                is_burn_or_lock = any(pattern in address_lower for pattern in burn_patterns)
                                
                                if is_burn_or_lock and percent > 50:
                                    lp_burned_locked = True
                                    lp_status_details = f"LP {percent:.1f}% in burn/lock address"
                                    lp_confidence = 90
                                    burn_detected = True
                                    logger.info(f"✅ LP BURNED/LOCKED: {percent:.1f}% in {address[:20]}...")
                                    break
                            
                            except Exception as e:
                                logger.debug(f"    Error processing LP provider: {e}")
                                continue
                    
                    # High concentration check (if not burn detected)
                    if not burn_detected and max_concentration > 85:
                        lp_burned_locked = True
                        lp_status_details = f"LP {max_concentration:.1f}% highly concentrated (likely locked)"
                        lp_confidence = 70
                        logger.info(f"✅ LP LIKELY SECURED: {max_concentration:.1f}% concentrated")
            
            # Method 3: Infer from RugCheck score (if high score, likely secure)
            if not lp_burned_locked:
                score = rugcheck_data.get("score")
                if score is not None:
                    try:
                        score_val = float(score)
                        logger.info(f"  RugCheck score: {score_val}")
                        
                        if score_val > 80:
                            lp_burned_locked = True
                            lp_status_details = f"Inferred secure from high RugCheck score ({score_val})"
                            lp_confidence = 60
                            logger.info(f"✅ LP INFERRED SECURE: High RugCheck score {score_val}")
                        elif score_val < 20:
                            lp_status_details = f"Low RugCheck score ({score_val}) - LP likely insecure"
                            lp_confidence = 80
                            logger.warning(f"❌ LP LIKELY INSECURE: Low RugCheck score {score_val}")
                    
                    except Exception as e:
                        logger.debug(f"Error processing RugCheck score: {e}")
        
        # Fallback: Check GOplus LP data
        if not lp_burned_locked:
            goplus_data = request.service_responses.get("goplus", {})
            if goplus_data and goplus_data.get("lp_holders"):
                lp_holders = goplus_data["lp_holders"]
                if isinstance(lp_holders, list) and len(lp_holders) > 0:
                    logger.info(f"  GOplus LP holders fallback: {len(lp_holders)} holders")
                    
                    for lp_holder in lp_holders:
                        if isinstance(lp_holder, dict):
                            try:
                                percent_raw = lp_holder.get("percent", "0")
                                percent = float(str(percent_raw).replace("%", "").replace(",", ""))
                                
                                if percent > 80:
                                    lp_burned_locked = True
                                    lp_status_details = f"LP {percent:.1f}% concentrated (GOplus)"
                                    lp_confidence = 65
                                    logger.info(f"✅ GOplus LP concentration: {percent:.1f}%")
                                    break
                                    
                            except Exception:
                                continue
        
        # Final LP status assignment
        if not lp_burned_locked and lp_confidence == 0:
            lp_status_details = "LP security could not be verified - assume not locked"
            lp_confidence = 30  # Low confidence when no data
        
        data.update({
            "lp_burned_locked": lp_burned_locked,
            "lp_status_details": lp_status_details,
            "lp_confidence": lp_confidence
        })
        
        # === SUPPLY DATA ===
        total_supply = 0
        helius_data = request.service_responses.get("helius", {})
        if helius_data and helius_data.get("supply"):
            supply_info = helius_data["supply"]
            raw_supply = supply_info.get("ui_amount")
            try:
                total_supply = float(raw_supply) if raw_supply is not None else 0
            except Exception:
                total_supply = 0
        
        data["total_supply"] = total_supply
        
        # === DEV HOLDINGS ===
        dev_percent = 0
        if rugcheck_data:
            creator_analysis = rugcheck_data.get("creator_analysis", {})
            if creator_analysis and total_supply > 0:
                try:
                    creator_balance = float(creator_analysis.get("creator_balance", 0))
                    dev_percent = (creator_balance / total_supply) * 100 if creator_balance > 0 else 0
                except Exception:
                    dev_percent = 0
        
        data["dev_percent"] = dev_percent
        
        # === SECURITY FLAGS ===
        security_flags = []
        
        # Extract from security analysis
        critical_issues = request.security_analysis.get("critical_issues", [])
        warnings = request.security_analysis.get("warnings", [])
        
        security_flags.extend(critical_issues)
        security_flags.extend(warnings)
        
        # Add specific checks
        goplus_security = request.security_analysis.get("goplus_result", {})
        if goplus_security:
            mintable = goplus_security.get("mintable", {})
            if isinstance(mintable, dict) and mintable.get("status") == "1":
                security_flags.append("Mint authority active")
                data["mint_authority_active"] = True
            else:
                data["mint_authority_active"] = False
            
            freezable = goplus_security.get("freezable", {}) 
            if isinstance(freezable, dict) and freezable.get("status") == "1":
                security_flags.append("Freeze authority active")
                data["freeze_authority_active"] = True
            else:
                data["freeze_authority_active"] = False
        
        data["security_flags"] = security_flags
        
        # === DERIVED METRICS ===
        if volume_24h > 0 and liquidity > 0:
            data["volume_liquidity_ratio"] = (volume_24h / liquidity) * 100
        else:
            data["volume_liquidity_ratio"] = 0
            
        # === COMPREHENSIVE STATUS LOGGING ===
        logger.info("\n" + "🎯 EXTRACTION RESULTS SUMMARY")
        logger.info("="*50)
        logger.info(f"💰 Market Cap: ${market_cap:,.0f} {'✅' if market_cap > 0 else '❌'}")
        logger.info(f"💧 Liquidity: ${liquidity:,.0f} {'✅' if liquidity > 0 else '❌'}")
        logger.info(f"📊 Volume 24h: ${volume_24h:,.0f} {'✅' if volume_24h > 0 else '❌'}")
        logger.info(f"👥 Holders: {holder_count:,} {'✅' if holder_count > 0 else '❌'}")
        logger.info(f"🔗 Top 10%: {top_10_holders_percent:.1f}% {'✅' if top_10_holders_percent > 0 else '❌'}")
        logger.info(f"🔒 LP Status: {lp_status_details} {'✅' if lp_burned_locked else '❌'}")
        logger.info(f"👨‍💻 Dev Holdings: {dev_percent:.1f}% {'✅' if dev_percent >= 0 else '❌'}")
        logger.info(f"🚨 Security Flags: {len(security_flags)}")
        
        # Calculate data completeness score
        completeness_factors = [
            market_cap > 0,           # Has market cap
            liquidity > 0,            # Has liquidity  
            volume_24h > 0,           # Has volume
            holder_count > 0,         # Has holder count
            lp_confidence > 50,       # LP status confident
            len(security_flags) >= 0  # Has security analysis
        ]
        
        completeness_score = (sum(completeness_factors) / len(completeness_factors)) * 100
        data["data_completeness"] = completeness_score
        
        logger.info(f"📈 Data Completeness: {completeness_score:.1f}%")
        logger.info("="*50)
        
        return data
    
    def _build_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Build analysis prompt that properly handles missing data"""
        
        # Calculate data availability
        has_market_data = data.get('market_cap', 0) > 0 and data.get('liquidity', 0) > 0
        has_volume_data = data.get('volume_24h', 0) > 0
        has_holder_data = data.get('holder_count', 0) > 0
        has_lp_data = data.get('lp_confidence', 0) > 50
        
        prompt = f"""COMPREHENSIVE SOLANA TOKEN ANALYSIS

    TOKEN: {data['token_address']}

    === MARKET FUNDAMENTALS ===
    Market Cap: ${data.get('market_cap', 0):,.0f} {'✅' if has_market_data else '❌ NO DATA'}
    Liquidity: ${data.get('liquidity', 0):,.0f} {'✅' if data.get('liquidity', 0) > 0 else '❌ NO DATA'}
    24h Volume: ${data.get('volume_24h', 0):,.0f} {'✅' if has_volume_data else '❌ NO ACTIVITY'}
    Volume/Liquidity: {data.get('volume_liquidity_ratio', 0):.1f}% {'✅' if data.get('volume_liquidity_ratio', 0) > 0 else '❌'}
    Price: ${data.get('price_usd', 0):.8f}
    24h Change: {data.get('price_change_24h', 0):+.2f}%

    === HOLDER ANALYSIS ===
    Total Holders: {data.get('holder_count', 0):,} {'✅' if has_holder_data else '❌ NO DATA - MAJOR CONCERN'}
    Top 10 Control: {data.get('top_10_holders_percent', 0):.1f}% {'✅' if data.get('top_10_holders_percent', 0) > 0 else '❌'}
    Dev Holdings: {data.get('dev_percent', 0):.1f}%
    Total Supply: {data.get('total_supply', 0):,.0f}

    === LIQUIDITY SECURITY ===
    LP Status: {data.get('lp_status_details', 'Unknown')} 
    LP Secured: {'YES ✅' if data.get('lp_burned_locked') else 'NO ❌ - MAJOR RED FLAG'}
    LP Confidence: {data.get('lp_confidence', 0)}%
    Mint Authority: {'ACTIVE 🚨' if data.get('mint_authority_active') else 'DISABLED ✅'}
    Freeze Authority: {'ACTIVE ⚠️' if data.get('freeze_authority_active') else 'DISABLED ✅'}

    === SECURITY ISSUES ===
    Total Security Flags: {len(data.get('security_flags', []))}
    {chr(10).join(f"🚨 {flag}" for flag in data.get('security_flags', []))}

    === DATA QUALITY ASSESSMENT ===
    Overall Completeness: {data.get('data_completeness', 0):.1f}%
    Market Data: {'Available' if has_market_data else 'MISSING'}
    Volume Data: {'Available' if has_volume_data else 'MISSING - Token likely inactive'}
    Holder Data: {'Available' if has_holder_data else 'MISSING - Cannot assess distribution risk'}
    LP Security: {'Verified' if has_lp_data else 'UNVERIFIED - Assume high risk'}

    === CRITICAL ANALYSIS INSTRUCTIONS ===

    1. DATA PENALTIES:
    - NO volume data → Deduct 30 points (inactive token)
    - NO holder data → Deduct 25 points + set confidence <50%
    - NO LP security verification → Deduct 40 points (rug risk)
    - NO market data → Deduct 20 points

    2. AUTOMATIC RISK ESCALATION:
    - Missing LP security data → Minimum "high" risk, recommend CAUTION/AVOID
    - Missing holder data → Minimum "medium" risk, low confidence
    - No trading activity → Maximum "medium" risk

    3. SCORING FRAMEWORK:
    - Start with 100 points
    - Apply data penalties above
    - Apply security deductions for active authorities
    - Apply market penalties for poor metrics
    - Final score determines recommendation

    4. CONFIDENCE RULES:
    - High confidence (80-100%) only if all critical data available
    - Medium confidence (50-79%) if some data missing but core metrics available  
    - Low confidence (<50%) if critical data missing

    5. RECOMMENDATION LOGIC:
    - AVOID: LP not secured OR no holder data OR critical security issues
    - CAUTION: Missing key data OR moderate risks
    - HOLD: Mixed signals OR data limitations prevent clear assessment
    - CONSIDER: Good data completeness AND favorable metrics
    - BUY: Excellent data AND exceptional metrics AND no red flags

    RESPOND WITH ONLY VALID JSON in the specified format. Be conservative when data is missing."""

        return prompt
    
    async def _call_llama_model(self, prompt: str) -> str:
        """Call Llama model for analysis (using Claude API as proxy)"""
        try:
            # For now, using Claude API as a proxy - replace with actual Llama API call
            response = await self._call_claude_api(prompt)
            return response
            
        except Exception as e:
            logger.error(f"Lamma model call failed: {str(e)}")
            raise
    
    async def _call_claude_api(self, prompt: str) -> str:
        """Call Claude API as proxy for Llama (replace with actual Llama integration)"""
        try:
            import aiohttp
            
            # This is a placeholder - replace with your actual Llama API endpoint
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": self.max_tokens,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                }
                
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"Content-Type": "application/json"},
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["content"][0]["text"]
                    else:
                        raise Exception(f"API call failed: {response.status}")
                        
        except Exception as e:
            logger.error(f"Claude API call failed: {str(e)}")
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
                json_content = ai_response
            
            # Parse JSON response
            parsed_data = json.loads(json_content)
            
            return AIAnalysisResponse(
                ai_score=float(parsed_data.get("ai_score", 50)),
                risk_assessment=parsed_data.get("risk_assessment", "medium"),
                recommendation=parsed_data.get("recommendation", "HOLD"),
                confidence=float(parsed_data.get("confidence", 70)),
                key_insights=parsed_data.get("key_insights", []),
                risk_factors=parsed_data.get("risk_factors", []),
                stop_flags=parsed_data.get("stop_flags", []),
                market_metrics=parsed_data.get("market_metrics", {}),
                llama_reasoning=parsed_data.get("llama_reasoning", "Analysis completed"),
                processing_time=0.0  # Will be set by caller
            )
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {str(e)}")
            logger.debug(f"Raw AI response: {ai_response}")
            
            # Return fallback response
            return AIAnalysisResponse(
                ai_score=50.0,
                risk_assessment="medium",
                recommendation="HOLD",
                confidence=50.0,
                key_insights=["Analysis parsing failed"],
                risk_factors=["Unable to parse AI response"],
                stop_flags=[],
                market_metrics={},
                llama_reasoning=f"Failed to parse AI response: {str(e)}",
                processing_time=0.0
            )
    
    def _create_fallback_response(self, token_address: str, processing_time: float) -> AIAnalysisResponse:
        """Create fallback response when AI analysis fails"""
        return AIAnalysisResponse(
            ai_score=0.0,
            risk_assessment="critical",
            recommendation="AVOID",
            confidence=0.0,
            key_insights=[],
            risk_factors=["AI analysis failed"],
            stop_flags=["Analysis system error"],
            market_metrics={},
            llama_reasoning="AI analysis system encountered an error and could not complete the analysis.",
            processing_time=processing_time
        )
    
llama_ai_service = groq_llama_service

async def analyze_token_with_ai(
    token_address: str,
    service_responses: Dict[str, Any],
    security_analysis: Dict[str, Any],
    analysis_type: str = "deep"
) -> Optional[AIAnalysisResponse]:
    """Perform AI analysis of token using Llama 3.0"""
    try:
        # Create proper AIAnalysisRequest instance
        request = AIAnalysisRequest(
            token_address=token_address,
            service_responses=service_responses,
            security_analysis=security_analysis,
            analysis_type=analysis_type,
            timestamp=datetime.utcnow()
        )
        
        return await llama_ai_service.analyze_token(request)
        
    except Exception as e:
        logger.error(f"AI analysis service error: {str(e)}")
        return None

# Health check function
async def check_ai_service_health() -> Dict[str, Any]:
    """Check AI service health"""
    try:
        # Test with minimal data
        test_request = AIAnalysisRequest(
            token_address="test",
            service_responses={},
            security_analysis={},
            market_data={}
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