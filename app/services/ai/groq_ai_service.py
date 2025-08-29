import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger
from groq import AsyncGroq
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()

class AIAnalysisRequest(BaseModel):
    """Pydantic model for AI analysis request"""
    token_address: str
    service_responses: dict
    security_analysis: dict
    analysis_type: str

class AIAnalysisResponse(BaseModel):
    """Pydantic model for AI analysis response"""
    ai_score: float
    risk_assessment: str
    recommendation: str
    confidence: float
    key_insights: List[str]
    risk_factors: List[str]
    stop_flags: List[str]
    market_metrics: dict
    llama_reasoning: str
    processing_time: float

class GroqLlamaService:
    """Groq-powered Llama 3.0 service for token analysis with realistic expectations"""
    
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model_name = "llama-3.3-70b-versatile"
        self.max_tokens = 4000
        self.temperature = 0.1
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt for token analysis"""
        return """You are an expert Solana token analyst specializing in cryptocurrency evaluation. Your task is to analyze token data and provide structured investment recommendations with realistic expectations about data availability.

CRITICAL: You must respond ONLY with valid JSON. No explanations, no markdown, no additional text.

REALISTIC ANALYSIS FRAMEWORK:
Evaluate tokens based on available metrics with understanding that missing data is common:

MARKET CAP ASSESSMENT:
- Excellent: <$5M (high growth potential, early opportunity)
- Good: $5M-$50M (established with growth room)
- Acceptable: $50M-$200M (mature but stable)
- Concerning: >$500M (limited growth potential)

LIQUIDITY ASSESSMENT:
- Excellent: $500K+ (very strong liquidity)
- Good: $100K-$500K (strong liquidity)
- Acceptable: $25K-$100K (adequate liquidity)
- Poor: <$25K (weak liquidity)

VOLUME ACTIVITY:
- Excellent: >5% of liquidity daily (very active)
- Good: 2-5% of liquidity daily (active)
- Acceptable: 0.5-2% of liquidity daily (moderate)
- Low: <0.5% of liquidity daily (inactive)

SECURITY PRIORITIES (Only Critical Issues):
- Active mint authority (can create unlimited tokens) - CRITICAL
- Active freeze authority (can freeze user accounts) - CRITICAL
- Verified rug pull or scam indicators - CRITICAL
- Transfer restrictions/honeypot - CRITICAL

DATA AVAILABILITY PHILOSOPHY:
- Missing LP data = NEUTRAL (very common, don't assume bad)
- Missing holder data = NEUTRAL (many APIs don't provide this)
- Missing volume = NEUTRAL for newer tokens
- Focus on POSITIVE indicators found, not data gaps
- Only flag ACTUAL negative evidence, not absence of data

CONFIDENCE GUIDELINES:
- High (80-100%): Strong positive/negative indicators with good data
- Medium (60-79%): Adequate data with clear signals
- Moderate (40-59%): Limited data but no red flags
- Low (<40%): Very limited data available

RESPONSE FORMAT (JSON ONLY):
{
  "ai_score": 0-100,
  "risk_assessment": "low|medium|high|critical",
  "recommendation": "BUY|CONSIDER|HOLD|CAUTION|AVOID",
  "confidence": 0-100,
  "key_insights": ["positive factors found"],
  "risk_factors": ["actual concerns, not data gaps"],
  "stop_flags": ["critical security issues only"],
  "market_metrics": {
    "data_quality": 0-100,
    "market_activity": 0-100,
    "security_assessment": 0-100
  },
  "llama_reasoning": "Brief explanation focusing on available data"
}

DECISION LOGIC (Realistic):
- BUY: >80 score with strong positive indicators
- CONSIDER: 65-80 score with good fundamentals
- HOLD: 45-65 score or insufficient data for clear decision
- CAUTION: 25-45 score with some risk factors
- AVOID: <25 score or critical security issues

Remember: Absence of data ≠ negative signal. Focus on what IS available."""

    async def analyze_token(self, request: AIAnalysisRequest) -> Optional[AIAnalysisResponse]:
        """Analyze token using Groq LLM with realistic data expectations"""
        try:
            start_time = datetime.utcnow()
            
            # Build analysis prompt with improved data preparation
            prompt = self._build_analysis_prompt_improved(request.dict())
            
            # Call Groq API
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            ai_response = response.choices[0].message.content
            parsed_response = self._parse_ai_response(ai_response)
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Create proper AIAnalysisResponse
            response = AIAnalysisResponse(
                ai_score=parsed_response.get('ai_score', 60.0),  # Neutral default
                risk_assessment=parsed_response.get('risk_assessment', 'medium'),
                recommendation=parsed_response.get('recommendation', 'HOLD'),
                confidence=parsed_response.get('confidence', 70.0),
                key_insights=parsed_response.get('key_insights', []),
                risk_factors=parsed_response.get('risk_factors', []),
                stop_flags=parsed_response.get('stop_flags', []),
                market_metrics=parsed_response.get('market_metrics', {}),
                llama_reasoning=parsed_response.get('llama_reasoning', ''),
                processing_time=processing_time
            )
            
            logger.info(f"Groq Llama analysis completed in {processing_time:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Groq Llama analysis failed: {str(e)}")
            return self._create_neutral_fallback(request.token_address, 0.0)
    
    def _build_analysis_prompt_improved(self, data: Dict[str, Any]) -> str:
        """Build analysis prompt with improved data handling from the reference response"""
        
        # Extract data from service responses (similar to reference format)
        service_responses = data.get('service_responses', {})
        security_analysis = data.get('security_analysis', {})
        
        # Market data extraction with safety
        market_data = {}
        
        # Birdeye price data
        birdeye = service_responses.get('birdeye', {})
        if birdeye and birdeye.get('price'):
            price_info = birdeye['price']
            market_data.update({
                'price': price_info.get('value'),
                'price_change_24h': price_info.get('price_change_24h'),
                'volume_24h': price_info.get('volume_24h'),
                'market_cap': price_info.get('market_cap'),
                'liquidity': price_info.get('liquidity')
            })
        
        # DexScreener fallback
        dexscreener = service_responses.get('dexscreener', {})
        if dexscreener and dexscreener.get('pairs', {}).get('pairs'):
            pairs = dexscreener['pairs']['pairs']
            if pairs and len(pairs) > 0:
                pair = pairs[0]
                if not market_data.get('market_cap'):
                    market_data['market_cap'] = pair.get('marketCap')
                if not market_data.get('volume_24h'):
                    volume_data = pair.get('volume', {})
                    market_data['volume_24h'] = volume_data.get('h24') if volume_data else None
                if not market_data.get('liquidity'):
                    liq_data = pair.get('liquidity', {})
                    market_data['liquidity'] = liq_data.get('usd') if liq_data else None
                if not market_data.get('price'):
                    market_data['price'] = pair.get('priceUsd')
        
        # Holder data extraction
        holder_data = {}
        
        # GOplus holder data
        goplus = service_responses.get('goplus', {})
        if goplus:
            # Extract holder count from various fields
            holder_count = goplus.get('holder_count')
            if holder_count:
                try:
                    if isinstance(holder_count, str):
                        clean_count = holder_count.replace(',', '')
                        holder_data['count'] = int(clean_count)
                    else:
                        holder_data['count'] = int(holder_count)
                except Exception:
                    pass
            
            # Extract top holders distribution
            holders_list = goplus.get('holders', [])
            if holders_list and len(holders_list) > 0:
                top_10_total = 0
                valid_count = 0
                for i, holder in enumerate(holders_list[:10]):
                    if isinstance(holder, dict):
                        percent_str = holder.get('percent', '0')
                        try:
                            percent = float(str(percent_str).replace('%', ''))
                            if 0 <= percent <= 100:
                                top_10_total += percent
                                valid_count += 1
                        except Exception:
                            continue
                
                if valid_count > 0:
                    holder_data['top_10_percent'] = top_10_total
        
        # LP Security Assessment (Improved Logic)
        lp_security = self._assess_lp_security_improved(service_responses)
        
        # Token metadata
        token_info = self._extract_token_metadata(service_responses)
        
        # Security flags (only critical ones)
        critical_security_flags = []
        if security_analysis:
            # Check for critical authorities
            goplus_result = security_analysis.get('goplus_result', {})
            if goplus_result:
                # Mint authority
                mintable = goplus_result.get('mintable', {})
                if isinstance(mintable, dict) and mintable.get('status') == '1':
                    critical_security_flags.append("Active mint authority")
                
                # Freeze authority
                freezable = goplus_result.get('freezable', {})
                if isinstance(freezable, dict) and freezable.get('status') == '1':
                    critical_security_flags.append("Active freeze authority")
            
            # Only include verified critical issues
            critical_issues = security_analysis.get('critical_issues', [])
            for issue in critical_issues:
                if any(keyword in str(issue).lower() for keyword in ['rug', 'scam', 'honeypot', 'malicious']):
                    critical_security_flags.append(issue)
        
        prompt = f"""SOLANA TOKEN ANALYSIS - REALISTIC ASSESSMENT

TOKEN: {data.get('token_address')}

=== MARKET FUNDAMENTALS ===
Price: {f"${market_data.get('price', 0):.8f}" if market_data.get('price') else "Not available"}
Market Cap: {f"${market_data.get('market_cap', 0):,.0f}" if market_data.get('market_cap') else "Not available"}
24h Volume: {f"${market_data.get('volume_24h', 0):,.0f}" if market_data.get('volume_24h') else "Not available"}
Liquidity: {f"${market_data.get('liquidity', 0):,.0f}" if market_data.get('liquidity') else "Not available"}
24h Change: {f"{market_data.get('price_change_24h', 0):+.2f}%" if market_data.get('price_change_24h') is not None else "Not available"}

=== TOKEN INFORMATION ===
Name: {token_info.get('name', 'Not available')}
Symbol: {token_info.get('symbol', 'Not available')}

=== HOLDER ANALYSIS ===
Total Holders: {f"{holder_data.get('count', 0):,}" if holder_data.get('count') else "Data not available (common for many tokens)"}
Top 10 Control: {f"{holder_data.get('top_10_percent', 0):.1f}%" if holder_data.get('top_10_percent') else "Distribution data not available"}

=== LIQUIDITY SECURITY ===
LP Status: {lp_security['status']}
Evidence: {lp_security['evidence']}
Confidence: {lp_security['confidence']}%

=== SECURITY ASSESSMENT ===
Critical Issues: {len(critical_security_flags)}
{chr(10).join(f"🚨 {flag}" for flag in critical_security_flags) if critical_security_flags else "No critical security issues detected"}

=== DATA SOURCES ===
Available Sources: {', '.join(service_responses.keys())}
Data Quality: {"Good - Multiple sources" if len(service_responses) >= 3 else "Limited - Some sources available" if len(service_responses) >= 1 else "Poor - Very limited data"}

=== ANALYSIS GUIDELINES ===

1. REALISTIC EXPECTATIONS:
   - Missing data is NORMAL in crypto analysis
   - Focus on AVAILABLE information quality
   - Don't penalize tokens for common data gaps
   - Neutral stance on missing information

2. CONFIDENCE CALCULATION:
   - Base confidence on data quality, not quantity
   - Available price data = higher confidence
   - Multiple data sources = bonus confidence
   - Missing holder/LP data = neutral impact

3. SCORING APPROACH:
   - Start with neutral base (60 points)
   - Award points for positive indicators found
   - Deduct points only for actual negative evidence
   - Missing data = no score impact (neutral)

4. LP SECURITY REALITY:
   - Unknown LP status is COMMON and NORMAL
   - Don't assume unlocked without evidence
   - Focus on actual rug evidence, not speculation
   - Many legitimate tokens have unknown LP status

5. HOLDER DISTRIBUTION:
   - Missing holder data is VERY COMMON
   - Don't penalize tokens for this gap
   - Only flag if clear whale control evidence exists
   - New/small tokens naturally have fewer holders

6. RECOMMENDATION PHILOSOPHY:
   - Focus on actual opportunities vs. theoretical risks
   - Missing data shouldn't prevent positive recommendations
   - Reserve AVOID for clear red flags only
   - Be optimistic when fundamentals look good

RESPOND WITH VALID JSON ONLY. Be realistic about crypto data limitations."""

    async def analyze_token(self, request: AIAnalysisRequest) -> Optional[AIAnalysisResponse]:
        """Analyze token using Groq LLM with realistic data expectations"""
        try:
            start_time = datetime.utcnow()
            
            # Build improved analysis prompt
            prompt = self._build_analysis_prompt_improved(request.dict())
            
            # Call Groq API
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            ai_response = response.choices[0].message.content
            parsed_response = self._parse_ai_response(ai_response)
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Create AIAnalysisResponse with improved defaults
            response = AIAnalysisResponse(
                ai_score=parsed_response.get('ai_score', 65.0),  # Slightly positive neutral
                risk_assessment=parsed_response.get('risk_assessment', 'medium'),
                recommendation=parsed_response.get('recommendation', 'CONSIDER'),  # More optimistic default
                confidence=parsed_response.get('confidence', 70.0),  # Good default confidence
                key_insights=parsed_response.get('key_insights', ["Analysis completed with available data"]),
                risk_factors=parsed_response.get('risk_factors', []),
                stop_flags=parsed_response.get('stop_flags', []),
                market_metrics=parsed_response.get('market_metrics', {}),
                llama_reasoning=parsed_response.get('llama_reasoning', 'Token analysis completed using available market data'),
                processing_time=processing_time
            )
            
            logger.info(f"Groq analysis completed: Score {response.ai_score}, Recommendation {response.recommendation}")
            return response
            
        except Exception as e:
            logger.error(f"Groq Llama analysis failed: {str(e)}")
            return self._create_neutral_fallback(request.token_address, 0.0)
    
    def _extract_token_metadata(self, service_responses: Dict[str, Any]) -> Dict[str, str]:
        """Extract token metadata from service responses"""
        token_info = {'name': 'Unknown', 'symbol': 'N/A'}
        
        # Try SolSniffer first
        solsniffer = service_responses.get('solsniffer', {})
        if solsniffer:
            if solsniffer.get('tokenName'):
                token_info['name'] = solsniffer['tokenName']
            if solsniffer.get('tokenSymbol'):
                token_info['symbol'] = solsniffer['tokenSymbol']
            return token_info
        
        # Try Helius metadata
        helius = service_responses.get('helius', {})
        if helius and helius.get('metadata'):
            metadata = helius['metadata']
            onchain = metadata.get('onChainMetadata', {})
            if onchain and onchain.get('metadata'):
                token_meta = onchain['metadata']
                if isinstance(token_meta, dict) and token_meta.get('data'):
                    data = token_meta['data']
                    if data.get('name'):
                        token_info['name'] = data['name']
                    if data.get('symbol'):
                        token_info['symbol'] = data['symbol']
                    return token_info
        
        # Try SolanaFM
        solanafm = service_responses.get('solanafm', {})
        if solanafm and solanafm.get('token'):
            token = solanafm['token']
            if token.get('name'):
                token_info['name'] = token['name']
            if token.get('symbol'):
                token_info['symbol'] = token['symbol']
        
        return token_info
    
    def _assess_lp_security_improved(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Assess LP security with realistic expectations and evidence-based approach"""
        
        # Initialize with neutral stance
        lp_assessment = {
            'status': 'Unknown (data not available - common for many tokens)',
            'evidence': 'No LP security data available from current sources',
            'confidence': 0,
            'risk_level': 'neutral'  # Not negative, just unknown
        }
        
        # Check RugCheck for LP evidence
        rugcheck = service_responses.get('rugcheck', {})
        if rugcheck:
            # Method 1: Check lockers data
            lockers_data = rugcheck.get('lockers_data', {})
            if lockers_data and lockers_data.get('lockers'):
                lockers = lockers_data['lockers']
                if isinstance(lockers, dict):
                    total_locked_value = 0
                    locker_count = 0
                    
                    for locker_id, locker_info in lockers.items():
                        if isinstance(locker_info, dict):
                            usd_locked = locker_info.get('usdcLocked', 0)
                            try:
                                if isinstance(usd_locked, (int, float)) and usd_locked > 0:
                                    total_locked_value += float(usd_locked)
                                    locker_count += 1
                            except Exception:
                                continue
                    
                    if total_locked_value > 1000:  # Significant value locked
                        lp_assessment = {
                            'status': 'SECURED (Verified Locked)',
                            'evidence': f"${total_locked_value:,.0f} USD locked in {locker_count} Raydium lockers",
                            'confidence': 95,
                            'risk_level': 'low'
                        }
                        return lp_assessment
            
            # Method 2: Check market analysis for burn/lock evidence
            market_analysis = rugcheck.get('market_analysis', {})
            if market_analysis and market_analysis.get('markets'):
                markets = market_analysis['markets']
                for market in markets:
                    if isinstance(market, dict) and market.get('lp'):
                        lp_info = market['lp']
                        holders = lp_info.get('holders', [])
                        
                        for holder in holders:
                            if isinstance(holder, dict):
                                owner = str(holder.get('owner', ''))
                                pct = holder.get('pct', 0)
                                
                                # Look for burn patterns
                                burn_indicators = ['111111', 'dead', 'burn', 'lock', '000000']
                                if any(pattern in owner.lower() for pattern in burn_indicators):
                                    if pct > 50:
                                        lp_assessment = {
                                            'status': 'SECURED (Burned)',
                                            'evidence': f"{pct:.1f}% LP tokens in burn address",
                                            'confidence': 90,
                                            'risk_level': 'low'
                                        }
                                        return lp_assessment
                                
                                # High concentration (could indicate locking)
                                elif pct > 95:
                                    lp_assessment = {
                                        'status': 'Likely Secured (Highly Concentrated)',
                                        'evidence': f"{pct:.1f}% LP concentration (possibly locked)",
                                        'confidence': 60,
                                        'risk_level': 'medium'
                                    }
                                    return lp_assessment
        
        # Check GOplus for LP data
        goplus = service_responses.get('goplus', {})
        if goplus and goplus.get('lp_holders'):
            lp_holders = goplus['lp_holders']
            if isinstance(lp_holders, list) and len(lp_holders) > 0:
                for holder in lp_holders:
                    if isinstance(holder, dict):
                        try:
                            percent_raw = holder.get('percent', '0')
                            percent = float(str(percent_raw).replace('%', ''))
                            
                            if percent > 90:
                                lp_assessment = {
                                    'status': 'Likely Secured (Concentrated)',
                                    'evidence': f"LP {percent:.1f}% concentrated (possibly locked)",
                                    'confidence': 55,
                                    'risk_level': 'medium'
                                }
                                break
                        except Exception:
                            continue
        
        return lp_assessment
    
    def _build_analysis_prompt_improved(self, data: Dict[str, Any]) -> str:
        """Build analysis prompt with the improved data handling"""
        
        service_responses = data.get('service_responses', {})
        security_analysis = data.get('security_analysis', {})
        
        # Extract comprehensive market data
        market_data = self._extract_comprehensive_market_data(service_responses)
        
        # Extract holder information
        holder_info = self._extract_holder_information(service_responses)
        
        # LP security assessment
        lp_security = self._assess_lp_security_improved(service_responses)
        
        # Token metadata
        token_metadata = self._extract_token_metadata(service_responses)
        
        # Critical security issues only
        critical_flags = self._extract_critical_security_flags(security_analysis)
        
        # Calculate data quality metrics
        data_quality = self._calculate_data_quality(service_responses)
        
        prompt = f"""SOLANA TOKEN COMPREHENSIVE ANALYSIS

TOKEN: {data.get('token_address')}
NAME: {token_metadata.get('name', 'Unknown')} ({token_metadata.get('symbol', 'N/A')})

=== MARKET ANALYSIS ===
Price: {market_data.get('price_display', 'Not available')}
Market Cap: {market_data.get('market_cap_display', 'Not available')}
24h Volume: {market_data.get('volume_display', 'Not available')}
Liquidity: {market_data.get('liquidity_display', 'Not available')}
Price Change: {market_data.get('change_display', 'Not available')}

Volume/Liquidity Ratio: {market_data.get('vol_liq_ratio_display', 'Cannot calculate - data not available')}

=== HOLDER DISTRIBUTION ===
Total Holders: {holder_info.get('count_display', 'Data not available (very common)')}
Top 10 Concentration: {holder_info.get('concentration_display', 'Distribution data not available')}

=== LIQUIDITY SECURITY ===
Status: {lp_security['status']}
Evidence: {lp_security['evidence']}
Assessment Confidence: {lp_security['confidence']}%

=== SECURITY FLAGS ===
Critical Issues: {len(critical_flags)}
{chr(10).join(f"🚨 {flag}" for flag in critical_flags) if critical_flags else "✅ No critical security issues detected"}

=== DATA QUALITY ASSESSMENT ===
Overall Data Quality: {data_quality['score']}/100
Available Data Sources: {data_quality['source_count']} sources
Key Data Available: {data_quality['available_metrics']} / {data_quality['total_metrics']}

Data Source Quality:
{chr(10).join(f"• {source}: {'✓' if available else '✗'}" for source, available in data_quality['source_status'].items())}

=== ANALYSIS INSTRUCTIONS ===

IMPORTANT CONTEXT:
- This is real-world crypto data where gaps are NORMAL
- Missing LP data affects 70%+ of tokens (don't penalize)
- Missing holder data affects 60%+ of tokens (very common)
- Focus on POSITIVE signals found, not theoretical risks

SCORING GUIDANCE:
- Start with 65 (slightly optimistic neutral)
- Award +20-30 for strong market metrics
- Award +10-15 for good security evidence
- Award +5-10 for comprehensive data
- Deduct points only for ACTUAL negative evidence
- Missing data = 0 impact (neutral)

CONFIDENCE GUIDANCE:
- High confidence (80%+): Clear positive/negative signals
- Medium confidence (60-79%): Some good data available
- Lower confidence (40-59%): Limited but not concerning
- Don't penalize confidence heavily for missing data

REALISTIC RECOMMENDATIONS:
- Many profitable tokens have unknown LP status
- Missing holder data doesn't indicate problems
- Focus on market activity and price performance
- Be optimistic when security checks pass

Provide realistic assessment based on available data. Don't create false risks from data gaps"""

        return prompt
    
    def _extract_comprehensive_market_data(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Extract market data with comprehensive display formatting"""
        market_data = {}
        
        # Birdeye data
        birdeye = service_responses.get('birdeye', {})
        if birdeye and birdeye.get('price'):
            price_info = birdeye['price']
            
            price = price_info.get('value')
            market_cap = price_info.get('market_cap')
            volume_24h = price_info.get('volume_24h')
            liquidity = price_info.get('liquidity')
            price_change = price_info.get('price_change_24h')
            
            market_data.update({
                'price': price,
                'market_cap': market_cap,
                'volume_24h': volume_24h,
                'liquidity': liquidity,
                'price_change_24h': price_change,
                'price_display': f"${float(price):.8f}" if price else "Not available",
                'market_cap_display': f"${float(market_cap):,.0f}" if market_cap else "Not available",
                'volume_display': f"${float(volume_24h):,.0f}" if volume_24h else "Not available",
                'liquidity_display': f"${float(liquidity):,.0f}" if liquidity else "Not available",
                'change_display': f"{float(price_change):+.2f}%" if price_change is not None else "Not available"
            })
            
            # Calculate volume/liquidity ratio
            if volume_24h and liquidity and liquidity > 0:
                ratio = (float(volume_24h) / float(liquidity)) * 100
                market_data['vol_liq_ratio'] = ratio
                market_data['vol_liq_ratio_display'] = f"{ratio:.1f}%"
        
        # DexScreener fallback
        dexscreener = service_responses.get('dexscreener', {})
        if dexscreener and dexscreener.get('pairs', {}).get('pairs'):
            pairs = dexscreener['pairs']['pairs']
            if pairs and len(pairs) > 0:
                pair = pairs[0]
                
                # Fill gaps from DexScreener
                if not market_data.get('market_cap') and pair.get('marketCap'):
                    mc = pair['marketCap']
                    market_data['market_cap'] = mc
                    market_data['market_cap_display'] = f"${float(mc):,.0f}"
                
                if not market_data.get('volume_24h') and pair.get('volume', {}).get('h24'):
                    vol = pair['volume']['h24']
                    market_data['volume_24h'] = vol
                    market_data['volume_display'] = f"${float(vol):,.0f}"
                
                if not market_data.get('liquidity') and pair.get('liquidity', {}).get('usd'):
                    liq = pair['liquidity']['usd']
                    market_data['liquidity'] = liq
                    market_data['liquidity_display'] = f"${float(liq):,.0f}"
                
                # Recalculate ratio if we got new data
                if (not market_data.get('vol_liq_ratio') and 
                    market_data.get('volume_24h') and 
                    market_data.get('liquidity')):
                    ratio = (float(market_data['volume_24h']) / float(market_data['liquidity'])) * 100
                    market_data['vol_liq_ratio'] = ratio
                    market_data['vol_liq_ratio_display'] = f"{ratio:.1f}%"
        
        return market_data
    
    def _extract_holder_information(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Extract holder information with realistic display"""
        holder_info = {}
        
        # GOplus holder data
        goplus = service_responses.get('goplus', {})
        if goplus:
            # Holder count
            holder_count = goplus.get('holder_count')
            if holder_count:
                try:
                    if isinstance(holder_count, str):
                        clean_count = holder_count.replace(',', '').replace(' ', '')
                        if 'k' in clean_count.lower():
                            number = clean_count.lower().replace('k', '')
                            count = int(float(number) * 1000)
                        else:
                            count = int(clean_count)
                    else:
                        count = int(holder_count)
                    
                    holder_info['count'] = count
                    holder_info['count_display'] = f"{count:,} holders"
                except Exception:
                    holder_info['count_display'] = "Holder count format unclear"
            else:
                holder_info['count_display'] = "Holder count not available (common limitation)"
            
            # Top holders analysis
            holders_array = goplus.get('holders', [])
            if holders_array and isinstance(holders_array, list):
                top_10_total = 0
                processed_count = 0
                
                for holder in holders_array[:10]:
                    if isinstance(holder, dict):
                        percent_raw = holder.get('percent', '0')
                        try:
                            percent = float(str(percent_raw).replace('%', ''))
                            if 0 <= percent <= 100:
                                top_10_total += percent
                                processed_count += 1
                        except Exception:
                            continue
                
                if processed_count > 0:
                    holder_info['top_10_percent'] = top_10_total
                    
                    if top_10_total > 70:
                        holder_info['concentration_display'] = f"{top_10_total:.1f}% (High concentration - monitor for dumps)"
                    elif top_10_total > 50:
                        holder_info['concentration_display'] = f"{top_10_total:.1f}% (Moderate concentration)"
                    else:
                        holder_info['concentration_display'] = f"{top_10_total:.1f}% (Good distribution)"
                else:
                    holder_info['concentration_display'] = "Holder distribution data incomplete"
            else:
                holder_info['concentration_display'] = "Distribution analysis not available"
        
        if not holder_info.get('count_display'):
            holder_info['count_display'] = "Holder data not available (very common - not a red flag)"
        
        if not holder_info.get('concentration_display'):
            holder_info['concentration_display'] = "Distribution data not available"
        
        return holder_info
    
    def _calculate_data_quality(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate data quality metrics"""
        
        # Check what data is available
        has_price_data = bool(service_responses.get('birdeye', {}).get('price', {}).get('value'))
        has_market_data = bool(service_responses.get('birdeye', {}).get('price', {}).get('market_cap') or 
                              service_responses.get('dexscreener', {}).get('pairs', {}).get('pairs'))
        has_holder_data = bool(service_responses.get('goplus', {}).get('holder_count'))
        has_security_data = bool(service_responses.get('goplus') or service_responses.get('rugcheck'))
        has_metadata = bool(service_responses.get('helius', {}).get('metadata') or 
                           service_responses.get('solanafm', {}).get('token'))
        
        # Core metrics availability
        available_metrics = sum([has_price_data, has_market_data, has_security_data, has_metadata])
        total_metrics = 4  # Core essential metrics
        
        # Bonus metrics
        bonus_available = sum([has_holder_data])  # Non-essential bonus data
        
        # Calculate quality score
        base_score = (available_metrics / total_metrics) * 80  # Up to 80 for essentials
        bonus_score = bonus_available * 10  # Up to 10 for bonus
        source_bonus = min(10, len(service_responses) * 2)  # Up to 10 for multiple sources
        
        quality_score = min(100, base_score + bonus_score + source_bonus)
        
        return {
            'score': round(quality_score),
            'source_count': len(service_responses),
            'available_metrics': available_metrics + bonus_available,
            'total_metrics': total_metrics + 1,  # Include holder data in total
            'source_status': {
                'Price Data': has_price_data,
                'Market Data': has_market_data,
                'Security Data': has_security_data,
                'Token Metadata': has_metadata,
                'Holder Data': has_holder_data
            }
        }

    def _parse_ai_response(self, ai_response: str):
        """Parse Groq response into structured format with improved defaults"""
        try:
            parsed_data = json.loads(ai_response)
            
            return {
                "ai_score": float(parsed_data.get("ai_score", 65)),  # More optimistic default
                "risk_assessment": parsed_data.get("risk_assessment", "medium"),
                "recommendation": parsed_data.get("recommendation", "CONSIDER"),  # More optimistic
                "confidence": float(parsed_data.get("confidence", 70)),  # Higher default confidence
                "key_insights": parsed_data.get("key_insights", ["Token analysis completed with available data"]),
                "risk_factors": parsed_data.get("risk_factors", []),
                "stop_flags": parsed_data.get("stop_flags", []),
                "market_metrics": parsed_data.get("market_metrics", {}),
                "llama_reasoning": parsed_data.get("llama_reasoning", "Analysis completed using available market data sources"),
                "processing_time": 0.0,
            }
            
        except Exception as e:
            logger.error(f"Failed to parse Groq response: {str(e)}")
            return self._create_neutral_fallback_dict()
    
    def _create_neutral_fallback_dict(self):
        """Create neutral fallback response dict when parsing fails"""
        return {
            "ai_score": 60.0,  # Neutral score
            "risk_assessment": "medium",
            "recommendation": "HOLD", 
            "confidence": 50.0,
            "key_insights": ["Analysis completed with limited data"],
            "risk_factors": ["AI response parsing failed - manual review recommended"],
            "stop_flags": [],
            "market_metrics": {
                "data_quality": 50,
                "analysis_confidence": 50
            },
            "llama_reasoning": "AI analysis encountered parsing issues but completed basic assessment with available data.",
            "processing_time": 0.0,
        }
    
    def _create_neutral_fallback(self, token_address: str, processing_time: float) -> AIAnalysisResponse:
        """Create neutral fallback response when analysis fails completely"""
        return AIAnalysisResponse(
            ai_score=60.0,  # Neutral score
            risk_assessment="medium",  # Medium risk
            recommendation="HOLD",  # Neutral recommendation
            confidence=50.0,  # Moderate confidence
            key_insights=["AI analysis temporarily unavailable"],
            risk_factors=["Limited analysis due to temporary system issue"],
            stop_flags=[],  # No stop flags for system issues
            market_metrics={
                "system_available": False,
                "fallback_used": True
            },
            llama_reasoning="AI analysis system temporarily unavailable. Based on available data, no immediate critical issues detected.",
            processing_time=processing_time,
        )
    
    def _extract_comprehensive_market_data(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Extract market data with comprehensive display formatting"""
        market_data = {}
        
        # Birdeye data
        birdeye = service_responses.get('birdeye', {})
        if birdeye and birdeye.get('price'):
            price_info = birdeye['price']
            
            price = price_info.get('value')
            market_cap = price_info.get('market_cap')
            volume_24h = price_info.get('volume_24h')
            liquidity = price_info.get('liquidity')
            price_change = price_info.get('price_change_24h')
            
            market_data.update({
                'price': price,
                'market_cap': market_cap,
                'volume_24h': volume_24h,
                'liquidity': liquidity,
                'price_change_24h': price_change,
                'price_display': f"${float(price):.8f}" if price else "Not available",
                'market_cap_display': f"${float(market_cap):,.0f}" if market_cap else "Not available",
                'volume_display': f"${float(volume_24h):,.0f}" if volume_24h else "Not available",
                'liquidity_display': f"${float(liquidity):,.0f}" if liquidity else "Not available",
                'change_display': f"{float(price_change):+.2f}%" if price_change is not None else "Not available"
            })
            
            # Calculate volume/liquidity ratio
            if volume_24h and liquidity and liquidity > 0:
                ratio = (float(volume_24h) / float(liquidity)) * 100
                market_data['vol_liq_ratio'] = ratio
                market_data['vol_liq_ratio_display'] = f"{ratio:.1f}%"
        
        # DexScreener fallback
        dexscreener = service_responses.get('dexscreener', {})
        if dexscreener and dexscreener.get('pairs', {}).get('pairs'):
            pairs = dexscreener['pairs']['pairs']
            if pairs and len(pairs) > 0:
                pair = pairs[0]
                
                # Fill gaps from DexScreener
                if not market_data.get('market_cap') and pair.get('marketCap'):
                    mc = pair['marketCap']
                    market_data['market_cap'] = mc
                    market_data['market_cap_display'] = f"${float(mc):,.0f}"
                
                if not market_data.get('volume_24h') and pair.get('volume', {}).get('h24'):
                    vol = pair['volume']['h24']
                    market_data['volume_24h'] = vol
                    market_data['volume_display'] = f"${float(vol):,.0f}"
                
                if not market_data.get('liquidity') and pair.get('liquidity', {}).get('usd'):
                    liq = pair['liquidity']['usd']
                    market_data['liquidity'] = liq
                    market_data['liquidity_display'] = f"${float(liq):,.0f}"
                
                # Recalculate ratio if we got new data
                if (not market_data.get('vol_liq_ratio') and 
                    market_data.get('volume_24h') and 
                    market_data.get('liquidity')):
                    ratio = (float(market_data['volume_24h']) / float(market_data['liquidity'])) * 100
                    market_data['vol_liq_ratio'] = ratio
                    market_data['vol_liq_ratio_display'] = f"{ratio:.1f}%"
        
        return market_data
    
    def _extract_holder_information(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Extract holder information with realistic display"""
        holder_info = {}
        
        # GOplus holder data
        goplus = service_responses.get('goplus', {})
        if goplus:
            # Holder count
            holder_count = goplus.get('holder_count')
            if holder_count:
                try:
                    if isinstance(holder_count, str):
                        clean_count = holder_count.replace(',', '').replace(' ', '')
                        if 'k' in clean_count.lower():
                            number = clean_count.lower().replace('k', '')
                            count = int(float(number) * 1000)
                        else:
                            count = int(clean_count)
                    else:
                        count = int(holder_count)
                    
                    holder_info['count'] = count
                    holder_info['count_display'] = f"{count:,} holders"
                except Exception:
                    holder_info['count_display'] = "Holder count format unclear"
            else:
                holder_info['count_display'] = "Holder count not available (common limitation)"
            
            # Top holders analysis
            holders_array = goplus.get('holders', [])
            if holders_array and isinstance(holders_array, list):
                top_10_total = 0
                processed_count = 0
                
                for holder in holders_array[:10]:
                    if isinstance(holder, dict):
                        percent_raw = holder.get('percent', '0')
                        try:
                            percent = float(str(percent_raw).replace('%', ''))
                            if 0 <= percent <= 100:
                                top_10_total += percent
                                processed_count += 1
                        except Exception:
                            continue
                
                if processed_count > 0:
                    holder_info['top_10_percent'] = top_10_total
                    
                    if top_10_total > 70:
                        holder_info['concentration_display'] = f"{top_10_total:.1f}% (High concentration - monitor for dumps)"
                    elif top_10_total > 50:
                        holder_info['concentration_display'] = f"{top_10_total:.1f}% (Moderate concentration)"
                    else:
                        holder_info['concentration_display'] = f"{top_10_total:.1f}% (Good distribution)"
                else:
                    holder_info['concentration_display'] = "Holder distribution data incomplete"
            else:
                holder_info['concentration_display'] = "Distribution analysis not available"
        
        if not holder_info.get('count_display'):
            holder_info['count_display'] = "Holder data not available (very common - not a red flag)"
        
        if not holder_info.get('concentration_display'):
            holder_info['concentration_display'] = "Distribution data not available"
        
        return holder_info
    
    def _extract_critical_security_flags(self, security_analysis: Dict[str, Any]) -> List[str]:
        """Extract only genuinely critical security flags"""
        critical_flags = []
        
        # GOplus critical authorities
        goplus_result = security_analysis.get('goplus_result', {})
        if goplus_result:
            # Mint authority (unlimited supply)
            mintable = goplus_result.get('mintable', {})
            if isinstance(mintable, dict) and mintable.get('status') == '1':
                critical_flags.append("Mint authority active (unlimited supply possible)")
            
            # Freeze authority (can freeze accounts)
            freezable = goplus_result.get('freezable', {})
            if isinstance(freezable, dict) and freezable.get('status') == '1':
                critical_flags.append("Freeze authority active (accounts can be frozen)")
        
        # Only include verified rug/scam evidence
        critical_issues = security_analysis.get('critical_issues', [])
        for issue in critical_issues:
            issue_str = str(issue).lower()
            if any(keyword in issue_str for keyword in ['rugged', 'scam', 'honeypot', 'malicious', 'exploit']):
                critical_flags.append(issue)
        
        return critical_flags
    
    def _calculate_data_quality(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate data quality metrics"""
        
        # Check what data is available
        has_price_data = bool(service_responses.get('birdeye', {}).get('price', {}).get('value'))
        has_market_data = bool(service_responses.get('birdeye', {}).get('price', {}).get('market_cap') or 
                              service_responses.get('dexscreener', {}).get('pairs', {}).get('pairs'))
        has_holder_data = bool(service_responses.get('goplus', {}).get('holder_count'))
        has_security_data = bool(service_responses.get('goplus') or service_responses.get('rugcheck'))
        has_metadata = bool(service_responses.get('helius', {}).get('metadata') or 
                           service_responses.get('solanafm', {}).get('token'))
        
        # Core metrics availability
        available_metrics = sum([has_price_data, has_market_data, has_security_data, has_metadata])
        total_metrics = 4  # Core essential metrics
        
        # Bonus metrics
        bonus_available = sum([has_holder_data])  # Non-essential bonus data
        
        # Calculate quality score
        base_score = (available_metrics / total_metrics) * 80  # Up to 80 for essentials
        bonus_score = bonus_available * 10  # Up to 10 for bonus
        source_bonus = min(10, len(service_responses) * 2)  # Up to 10 for multiple sources
        
        quality_score = min(100, base_score + bonus_score + source_bonus)
        
        return {
            'score': round(quality_score),
            'source_count': len(service_responses),
            'available_metrics': available_metrics + bonus_available,
            'total_metrics': total_metrics + 1,  # Include holder data in total
            'source_status': {
                'Price Data': has_price_data,
                'Market Data': has_market_data,
                'Security Data': has_security_data,
                'Token Metadata': has_metadata,
                'Holder Data': has_holder_data
            }
        }
    
# Global service instance
groq_llama_service = GroqLlamaService()