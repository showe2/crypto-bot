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
    """Groq-powered Llama 3.0 service for token analysis with multi-source data aggregation"""
    
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model_name = "llama-3.3-70b-versatile"
        self.max_tokens = 4000
        self.temperature = 0.1
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt for token analysis"""
        return """You are an expert Solana token analyst specializing in cryptocurrency evaluation with multi-source data aggregation capabilities. Your task is to analyze token data from multiple sources and provide structured investment recommendations with realistic expectations about data availability.

CRITICAL: You must respond ONLY with valid JSON. No explanations, no markdown, no additional text.

ENHANCED MULTI-SOURCE ANALYSIS FRAMEWORK:
You will receive data aggregated from multiple sources. When multiple sources provide the same metric, trust has been established through cross-verification.

MARKET DATA ASSESSMENT (Multi-Source Enhanced):
- Price data from multiple sources = Higher confidence
- Single source price = Lower confidence but still usable
- Volume/Liquidity cross-confirmed = More reliable metrics
- Market cap verified across sources = Better accuracy assessment

CONFIDENCE SCALING WITH SOURCES:
- Multi-source confirmation: +20 confidence points
- Single reliable source: Baseline confidence
- Cross-source contradictions: -10 confidence points
- Source attribution provided: +5 confidence points

LIQUIDITY ASSESSMENT (Enhanced):
- Excellent: $500K+ confirmed across sources
- Good: $100K-$500K from reliable source
- Acceptable: $25K-$100K single source
- Poor: <$25K or conflicting data

HOLDER ANALYSIS (Multi-Source):
- Multiple holder data sources = Higher accuracy
- GOplus + RugCheck confirmation = Most reliable
- LP provider data supplements holder analysis
- Cross-reference distribution metrics when available

SECURITY PRIORITIES (Critical Only):
- Active mint authority - CRITICAL
- Active freeze authority - CRITICAL  
- Verified rug pull evidence - CRITICAL
- Multi-source security confirmation - CRITICAL

DATA QUALITY PHILOSOPHY:
- Aggregated data > Single source data
- Filtered dummy responses improve accuracy
- Source attribution builds confidence
- Multi-source gaps indicate genuine data unavailability

RESPONSE FORMAT (JSON ONLY):
{
  "ai_score": 0-100,
  "risk_assessment": "low|medium|high|critical", 
  "recommendation": "BUY|CONSIDER|HOLD|CAUTION|AVOID",
  "confidence": 0-100,
  "key_insights": ["positive factors with source attribution"],
  "risk_factors": ["actual concerns, not data gaps"],
  "stop_flags": ["critical security issues only"],
  "market_metrics": {
    "data_quality": 0-100,
    "multi_source_score": 0-100,
    "source_reliability": 0-100
  },
  "llama_reasoning": "Brief explanation emphasizing multi-source validation"
}

ENHANCED DECISION LOGIC:
- BUY: >85 score with multi-source confirmation
- CONSIDER: 70-85 score with good source coverage
- HOLD: 50-70 score or single-source limitations
- CAUTION: 30-50 score with some concerns
- AVOID: <30 score or critical security issues

Remember: Multi-source data validation significantly improves analysis accuracy and confidence."""

    async def send_request(self, prompt: str) -> Optional[AIAnalysisResponse]:
        """Analyze token using Groq LLM with enhanced multi-source data processing"""
        try:
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
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Enhanced Groq Llama analysis failed: {str(e)}")

#     def _extract_comprehensive_market_data(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
#         """Extract market data from ALL available sources with smart aggregation"""
#         market_data = {}
        
#         # PRICE DATA - Check multiple sources
#         price_sources = []
        
#         # Birdeye price
#         birdeye = service_responses.get('birdeye', {})
#         if birdeye and birdeye.get('price', {}).get('value'):
#             try:
#                 price = float(birdeye['price']['value'])
#                 if price > 0:
#                     price_sources.append(('birdeye', price))
#             except (ValueError, TypeError):
#                 pass
        
#         # DexScreener price
#         dexscreener = service_responses.get('dexscreener', {})
#         if dexscreener and dexscreener.get('pairs', {}).get('pairs'):
#             pairs = dexscreener['pairs']['pairs']
#             if pairs and len(pairs) > 0:
#                 pair = pairs[0]
#                 price_usd = pair.get('priceUsd')
#                 if price_usd:
#                     try:
#                         price = float(price_usd)
#                         if price > 0:
#                             price_sources.append(('dexscreener', price))
#                     except (ValueError, TypeError):
#                         pass
        
#         # GOplus DEX data
#         goplus = service_responses.get('goplus', {})
#         if goplus and goplus.get('dex'):
#             dex_data = goplus['dex']
#             if isinstance(dex_data, list):
#                 for dex in dex_data:
#                     if isinstance(dex, dict) and dex.get('price'):
#                         try:
#                             price = float(dex['price'])
#                             if price > 0:
#                                 price_sources.append(('goplus_dex', price))
#                                 break  # Take first valid price
#                         except (ValueError, TypeError):
#                             continue
        
#         # Use best price (prefer Birdeye, then DexScreener, then GOplus)
#         if price_sources:
#             # Sort by preference: birdeye > dexscreener > goplus_dex
#             preference_order = {'birdeye': 1, 'dexscreener': 2, 'goplus_dex': 3}
#             price_sources.sort(key=lambda x: preference_order.get(x[0], 99))
            
#             best_price_source, best_price = price_sources[0]
#             market_data['price'] = best_price
#             market_data['price_display'] = f"${best_price:.8f}"
#             market_data['price_source'] = best_price_source
            
#             logger.info(f"Price extracted: ${best_price:.6f} from {best_price_source}")
#         else:
#             market_data['price_display'] = "Not available"
        
#         # MARKET CAP - Aggregate from multiple sources
#         market_cap_sources = []
        
#         # Birdeye market cap
#         if birdeye and birdeye.get('price', {}).get('market_cap'):
#             try:
#                 mc = float(birdeye['price']['market_cap'])
#                 if mc > 0:
#                     market_cap_sources.append(('birdeye', mc))
#             except (ValueError, TypeError):
#                 pass
        
#         # DexScreener market cap
#         if dexscreener and dexscreener.get('pairs', {}).get('pairs'):
#             pairs = dexscreener['pairs']['pairs']
#             if pairs and len(pairs) > 0:
#                 pair = pairs[0]
#                 mc = pair.get('marketCap')
#                 if mc:
#                     try:
#                         mc_val = float(mc)
#                         if mc_val > 0:
#                             market_cap_sources.append(('dexscreener', mc_val))
#                     except (ValueError, TypeError):
#                         pass
        
#         # SolSniffer market cap
#         solsniffer = service_responses.get('solsniffer', {})
#         if solsniffer and solsniffer.get('marketCap'):
#             try:
#                 mc = float(solsniffer['marketCap'])
#                 if mc > 0:
#                     market_cap_sources.append(('solsniffer', mc))
#             except (ValueError, TypeError):
#                 pass
        
#         # Use most reliable market cap
#         if market_cap_sources:
#             preference_order = {'birdeye': 1, 'dexscreener': 2, 'solsniffer': 3}
#             market_cap_sources.sort(key=lambda x: preference_order.get(x[0], 99))
            
#             best_mc_source, best_mc = market_cap_sources[0]
#             market_data['market_cap'] = best_mc
#             market_data['market_cap_display'] = f"${best_mc:,.0f}"
#             market_data['market_cap_source'] = best_mc_source
            
#             logger.info(f"Market cap extracted: ${best_mc:,.0f} from {best_mc_source}")
#         else:
#             market_data['market_cap_display'] = "Not available"
        
#         # VOLUME - Check multiple sources
#         volume_sources = []
        
#         # Birdeye volume
#         if birdeye and birdeye.get('price', {}).get('volume_24h'):
#             try:
#                 vol = float(birdeye['price']['volume_24h'])
#                 if vol > 0:
#                     volume_sources.append(('birdeye', vol))
#             except (ValueError, TypeError):
#                 pass
        
#         # DexScreener volume
#         if dexscreener and dexscreener.get('pairs', {}).get('pairs'):
#             pairs = dexscreener['pairs']['pairs']
#             if pairs and len(pairs) > 0:
#                 pair = pairs[0]
#                 volume_data = pair.get('volume', {})
#                 if volume_data and volume_data.get('h24'):
#                     try:
#                         vol = float(volume_data['h24'])
#                         if vol > 0:
#                             volume_sources.append(('dexscreener', vol))
#                     except (ValueError, TypeError):
#                         pass
        
#         # GOplus DEX volume
#         if goplus and goplus.get('dex'):
#             dex_data = goplus['dex']
#             if isinstance(dex_data, list):
#                 total_volume = 0
#                 for dex in dex_data:
#                     if isinstance(dex, dict) and dex.get('day', {}).get('volume'):
#                         try:
#                             vol = float(dex['day']['volume'])
#                             if vol > 0:
#                                 total_volume += vol
#                         except (ValueError, TypeError):
#                             continue
#                 if total_volume > 0:
#                     volume_sources.append(('goplus_dex', total_volume))
        
#         # Use best volume
#         if volume_sources:
#             preference_order = {'birdeye': 1, 'dexscreener': 2, 'goplus_dex': 3}
#             volume_sources.sort(key=lambda x: preference_order.get(x[0], 99))
            
#             best_vol_source, best_vol = volume_sources[0]
#             market_data['volume_24h'] = best_vol
#             market_data['volume_display'] = f"${best_vol:,.0f}"
#             market_data['volume_source'] = best_vol_source
            
#             logger.info(f"Volume extracted: ${best_vol:,.0f} from {best_vol_source}")
#         else:
#             market_data['volume_display'] = "Not available"
        
#         # LIQUIDITY - Aggregate from multiple sources
#         liquidity_sources = []
        
#         # Birdeye liquidity
#         if birdeye and birdeye.get('price', {}).get('liquidity'):
#             try:
#                 liq = float(birdeye['price']['liquidity'])
#                 if liq > 0:
#                     liquidity_sources.append(('birdeye', liq))
#             except (ValueError, TypeError):
#                 pass
        
#         # DexScreener liquidity
#         if dexscreener and dexscreener.get('pairs', {}).get('pairs'):
#             pairs = dexscreener['pairs']['pairs']
#             if pairs and len(pairs) > 0:
#                 pair = pairs[0]
#                 liquidity_data = pair.get('liquidity', {})
#                 if liquidity_data and liquidity_data.get('usd'):
#                     try:
#                         liq = float(liquidity_data['usd'])
#                         if liq > 0:
#                             liquidity_sources.append(('dexscreener', liq))
#                     except (ValueError, TypeError):
#                         pass
        
#         # RugCheck liquidity analysis
#         rugcheck = service_responses.get('rugcheck', {})
#         if rugcheck and rugcheck.get('liquidity_analysis'):
#             liq_analysis = rugcheck['liquidity_analysis']
#             total_liq = liq_analysis.get('total_market_liquidity')
#             if total_liq:
#                 try:
#                     liq = float(total_liq)
#                     if liq > 0:
#                         liquidity_sources.append(('rugcheck', liq))
#                 except (ValueError, TypeError):
#                     pass
        
#         # GOplus DEX TVL
#         if goplus and goplus.get('dex'):
#             dex_data = goplus['dex']
#             if isinstance(dex_data, list):
#                 total_tvl = 0
#                 for dex in dex_data:
#                     if isinstance(dex, dict) and dex.get('tvl'):
#                         try:
#                             tvl = float(dex['tvl'])
#                             if tvl > 0:
#                                 total_tvl += tvl
#                         except (ValueError, TypeError):
#                             continue
#                 if total_tvl > 0:
#                     liquidity_sources.append(('goplus_tvl', total_tvl))
        
#         # Use best liquidity
#         if liquidity_sources:
#             preference_order = {'birdeye': 1, 'dexscreener': 2, 'rugcheck': 3, 'goplus_tvl': 4}
#             liquidity_sources.sort(key=lambda x: preference_order.get(x[0], 99))
            
#             best_liq_source, best_liq = liquidity_sources[0]
#             market_data['liquidity'] = best_liq
#             market_data['liquidity_display'] = f"${best_liq:,.0f}"
#             market_data['liquidity_source'] = best_liq_source
            
#             logger.info(f"Liquidity extracted: ${best_liq:,.0f} from {best_liq_source}")
#         else:
#             market_data['liquidity_display'] = "Not available"
        
#         # PRICE CHANGE - Multiple sources
#         change_sources = []
        
#         # Birdeye price change
#         if birdeye and birdeye.get('price', {}).get('price_change_24h') is not None:
#             try:
#                 change = float(birdeye['price']['price_change_24h'])
#                 change_sources.append(('birdeye', change))
#             except (ValueError, TypeError):
#                 pass
        
#         # DexScreener price change
#         if dexscreener and dexscreener.get('pairs', {}).get('pairs'):
#             pairs = dexscreener['pairs']['pairs']
#             if pairs and len(pairs) > 0:
#                 pair = pairs[0]
#                 price_change = pair.get('priceChange', {})
#                 if price_change and price_change.get('h24') is not None:
#                     try:
#                         change = float(price_change['h24'])
#                         change_sources.append(('dexscreener', change))
#                     except (ValueError, TypeError):
#                         pass
        
#         # Use best price change
#         if change_sources:
#             preference_order = {'birdeye': 1, 'dexscreener': 2}
#             change_sources.sort(key=lambda x: preference_order.get(x[0], 99))
            
#             best_change_source, best_change = change_sources[0]
#             market_data['price_change_24h'] = best_change
#             market_data['change_display'] = f"{best_change:+.2f}%"
#             market_data['change_source'] = best_change_source
            
#             logger.info(f"Price change extracted: {best_change:+.2f}% from {best_change_source}")
#         else:
#             market_data['change_display'] = "Not available"
        
#         # Calculate volume/liquidity ratio if both available
#         if market_data.get('volume_24h') and market_data.get('liquidity'):
#             try:
#                 ratio = (market_data['volume_24h'] / market_data['liquidity']) * 100
#                 market_data['vol_liq_ratio'] = ratio
#                 market_data['vol_liq_ratio_display'] = f"{ratio:.1f}%"
#             except (ZeroDivisionError, TypeError):
#                 market_data['vol_liq_ratio_display'] = "Cannot calculate"
#         else:
#             market_data['vol_liq_ratio_display'] = "Cannot calculate - data not available"
        
#         return market_data

#     def _extract_comprehensive_holder_data(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
#         """Extract holder information from ALL available sources"""
#         holder_data = {}
        
#         # HOLDER COUNT - Check multiple sources
#         holder_count_sources = []
        
#         # GOplus holder count
#         goplus = service_responses.get('goplus', {})
#         if goplus and goplus.get('holder_count'):
#             holder_count = goplus['holder_count']
#             try:
#                 if isinstance(holder_count, str):
#                     clean_count = holder_count.replace(',', '').replace(' ', '')
#                     if 'k' in clean_count.lower():
#                         number = clean_count.lower().replace('k', '')
#                         count = int(float(number) * 1000)
#                     else:
#                         count = int(clean_count)
#                 else:
#                     count = int(holder_count)
                
#                 if count > 0:
#                     holder_count_sources.append(('goplus', count))
#                     logger.info(f"GOplus holder count: {count:,}")
#             except (ValueError, TypeError):
#                 pass
        
#         # RugCheck LP providers (different from holders but related metric)
#         rugcheck = service_responses.get('rugcheck', {})
#         if rugcheck and rugcheck.get('total_LP_providers'):
#             try:
#                 lp_providers = int(rugcheck['total_LP_providers'])
#                 if lp_providers > 0:
#                     holder_count_sources.append(('rugcheck_lp', lp_providers))
#                     logger.info(f"RugCheck LP providers: {lp_providers:,}")
#             except (ValueError, TypeError):
#                 pass
        
#         # Use best holder count (prefer GOplus over LP providers)
#         if holder_count_sources:
#             # Prefer actual holder count over LP providers
#             goplus_holders = [s for s in holder_count_sources if s[0] == 'goplus']
#             if goplus_holders:
#                 source, count = goplus_holders[0]
#                 holder_data['count'] = count
#                 holder_data['count_display'] = f"{count:,} holders"
#                 holder_data['count_source'] = source
#             else:
#                 # Fallback to LP providers with note
#                 source, count = holder_count_sources[0]
#                 holder_data['count'] = count
#                 holder_data['count_display'] = f"{count:,} LP providers (not total holders)"
#                 holder_data['count_source'] = source
#         else:
#             holder_data['count_display'] = "Holder count not available (very common - not a red flag)"
        
#         # HOLDER CONCENTRATION - Multiple sources
#         concentration_sources = []
        
#         # GOplus holders array
#         if goplus and goplus.get('holders'):
#             holders_array = goplus['holders']
#             if isinstance(holders_array, list) and len(holders_array) > 0:
#                 top_10_total = 0
#                 processed_count = 0
                
#                 for holder in holders_array[:10]:
#                     if isinstance(holder, dict):
#                         percent_raw = holder.get('percent', '0')
#                         try:
#                             percent = float(str(percent_raw).replace('%', ''))
#                             if 0 <= percent <= 100:
#                                 top_10_total += percent
#                                 processed_count += 1
#                         except (ValueError, TypeError):
#                             continue
                
#                 if processed_count > 0:
#                     concentration_sources.append(('goplus', top_10_total, processed_count))
#                     logger.info(f"GOplus top 10 concentration: {top_10_total:.1f}% ({processed_count} holders)")
        
#         # RugCheck market analysis holder data
#         if rugcheck and rugcheck.get('market_analysis', {}).get('markets'):
#             markets = rugcheck['market_analysis']['markets']
#             if isinstance(markets, list):
#                 for market in markets:
#                     if isinstance(market, dict) and market.get('lp', {}).get('holders'):
#                         lp_holders = market['lp']['holders']
#                         if isinstance(lp_holders, list) and len(lp_holders) > 0:
#                             # This is LP concentration, not token holder concentration
#                             top_holder = lp_holders[0]
#                             if isinstance(top_holder, dict) and top_holder.get('pct'):
#                                 try:
#                                     top_pct = float(top_holder['pct'])
#                                     if 0 <= top_pct <= 100:
#                                         concentration_sources.append(('rugcheck_lp', top_pct, 1))
#                                         logger.info(f"RugCheck LP concentration: {top_pct:.1f}%")
#                                         break  # Take first market data
#                                 except (ValueError, TypeError):
#                                     continue
        
#         # Use best concentration data
#         if concentration_sources:
#             # Prefer GOplus token holder concentration over LP concentration
#             goplus_concentration = [s for s in concentration_sources if s[0] == 'goplus']
#             if goplus_concentration:
#                 source, concentration, holder_count = goplus_concentration[0]
#                 holder_data['top_10_percent'] = concentration
                
#                 if concentration > 70:
#                     holder_data['concentration_display'] = f"{concentration:.1f}% (High concentration - monitor for dumps)"
#                 elif concentration > 50:
#                     holder_data['concentration_display'] = f"{concentration:.1f}% (Moderate concentration)"
#                 else:
#                     holder_data['concentration_display'] = f"{concentration:.1f}% (Good distribution)"
                
#                 holder_data['concentration_source'] = source
#             else:
#                 # Use LP concentration with appropriate note
#                 source, concentration, holder_count = concentration_sources[0]
#                 holder_data['lp_concentration'] = concentration
#                 holder_data['concentration_display'] = f"LP concentration: {concentration:.1f}% (not token holder concentration)"
#                 holder_data['concentration_source'] = source
#         else:
#             holder_data['concentration_display'] = "Distribution data not available"
        
#         return holder_data

#     def _extract_comprehensive_token_metadata(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
#         """Extract token metadata from ALL available sources"""
#         token_info = {'name': 'Unknown', 'symbol': 'N/A'}
#         sources_used = []
        
#         # SolSniffer (usually most reliable for basic info)
#         solsniffer = service_responses.get('solsniffer', {})
#         if solsniffer:
#             if solsniffer.get('tokenName'):
#                 token_info['name'] = solsniffer['tokenName']
#                 sources_used.append('solsniffer_name')
#             if solsniffer.get('tokenSymbol'):
#                 token_info['symbol'] = solsniffer['tokenSymbol']
#                 sources_used.append('solsniffer_symbol')
#             if token_info['name'] != 'Unknown' and token_info['symbol'] != 'N/A':
#                 token_info['metadata_source'] = 'solsniffer'
#                 return token_info
        
#         # GOplus metadata
#         goplus = service_responses.get('goplus', {})
#         if goplus and goplus.get('metadata'):
#             metadata = goplus['metadata']
#             if isinstance(metadata, dict):
#                 if metadata.get('name') and token_info['name'] == 'Unknown':
#                     token_info['name'] = metadata['name']
#                     sources_used.append('goplus_name')
#                 if metadata.get('symbol') and token_info['symbol'] == 'N/A':
#                     token_info['symbol'] = metadata['symbol']
#                     sources_used.append('goplus_symbol')
        
#         # Helius metadata
#         helius = service_responses.get('helius', {})
#         if helius and helius.get('metadata'):
#             metadata = helius['metadata']
            
#             # Try onchain metadata first
#             onchain = metadata.get('onChainMetadata', {})
#             if onchain and onchain.get('metadata'):
#                 token_meta = onchain['metadata']
#                 if isinstance(token_meta, dict) and token_meta.get('data'):
#                     data = token_meta['data']
#                     if data.get('name') and token_info['name'] == 'Unknown':
#                         token_info['name'] = data['name']
#                         sources_used.append('helius_onchain_name')
#                     if data.get('symbol') and token_info['symbol'] == 'N/A':
#                         token_info['symbol'] = data['symbol']
#                         sources_used.append('helius_onchain_symbol')
            
#             # Try legacy metadata if still missing
#             legacy = metadata.get('legacyMetadata', {})
#             if legacy:
#                 if legacy.get('name') and token_info['name'] == 'Unknown':
#                     token_info['name'] = legacy['name']
#                     sources_used.append('helius_legacy_name')
#                 if legacy.get('symbol') and token_info['symbol'] == 'N/A':
#                     token_info['symbol'] = legacy['symbol']
#                     sources_used.append('helius_legacy_symbol')
        
#         # SolanaFM
#         solanafm = service_responses.get('solanafm', {})
#         if solanafm and solanafm.get('token'):
#             token = solanafm['token']
#             if token.get('name') and token_info['name'] == 'Unknown':
#                 token_info['name'] = token['name']
#                 sources_used.append('solanafm_name')
#             if token.get('symbol') and token_info['symbol'] == 'N/A':
#                 token_info['symbol'] = token['symbol']
#                 sources_used.append('solanafm_symbol')
        
#         # DexScreener
#         dexscreener = service_responses.get('dexscreener', {})
#         if dexscreener and dexscreener.get('pairs', {}).get('pairs'):
#             pairs = dexscreener['pairs']['pairs']
#             if pairs and len(pairs) > 0:
#                 pair = pairs[0]
#                 base_token = pair.get('baseToken', {})
#                 if base_token.get('name') and token_info['name'] == 'Unknown':
#                     token_info['name'] = base_token['name']
#                     sources_used.append('dexscreener_name')
#                 if base_token.get('symbol') and token_info['symbol'] == 'N/A':
#                     token_info['symbol'] = base_token['symbol']
#                     sources_used.append('dexscreener_symbol')
        
#         # RugCheck verification
#         rugcheck = service_responses.get('rugcheck', {})
#         if rugcheck and rugcheck.get('verification'):
#             verification = rugcheck['verification']
#             if verification.get('name') and token_info['name'] == 'Unknown':
#                 token_info['name'] = verification['name']
#                 sources_used.append('rugcheck_name')
#             if verification.get('symbol') and token_info['symbol'] == 'N/A':
#                 token_info['symbol'] = verification['symbol']
#                 sources_used.append('rugcheck_symbol')
        
#         # Set metadata source summary
#         if sources_used:
#             primary_sources = list(set([s.split('_')[0] for s in sources_used]))
#             token_info['metadata_source'] = ', '.join(primary_sources)
#             logger.info(f"Token metadata from: {', '.join(primary_sources)}")
#         else:
#             token_info['metadata_source'] = 'none'
        
#         return token_info

#     def _extract_comprehensive_supply_data(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
#         """Extract supply data from multiple sources"""
#         supply_data = {}
        
#         # Helius supply
#         helius = service_responses.get('helius', {})
#         if helius and helius.get('supply'):
#             supply_info = helius['supply']
#             try:
#                 total_supply = float(supply_info.get('ui_amount', 0))
#                 if total_supply > 0:
#                     supply_data['total_supply'] = total_supply
#                     supply_data['supply_source'] = 'helius'
#                     supply_data['decimals'] = supply_info.get('decimals', 6)
#                     logger.info(f"Supply from Helius: {total_supply:,.0f}")
#             except (ValueError, TypeError):
#                 pass
        
#         # GOplus supply
#         if not supply_data.get('total_supply'):
#             goplus = service_responses.get('goplus', {})
#             if goplus and goplus.get('total_supply'):
#                 try:
#                     total_supply = float(goplus['total_supply'])
#                     if total_supply > 0:
#                         supply_data['total_supply'] = total_supply
#                         supply_data['supply_source'] = 'goplus'
#                         logger.info(f"Supply from GOplus: {total_supply:,.0f}")
#                 except (ValueError, TypeError):
#                     pass
        
#         # RugCheck supply
#         if not supply_data.get('total_supply'):
#             rugcheck = service_responses.get('rugcheck', {})
#             if rugcheck and rugcheck.get('token', {}).get('supply'):
#                 try:
#                     # RugCheck supply is usually in raw units, need to convert
#                     raw_supply = float(rugcheck['token']['supply'])
#                     decimals = rugcheck['token'].get('decimals', 6)
#                     total_supply = raw_supply / (10 ** decimals)
#                     if total_supply > 0:
#                         supply_data['total_supply'] = total_supply
#                         supply_data['supply_source'] = 'rugcheck'
#                         supply_data['decimals'] = decimals
#                         logger.info(f"Supply from RugCheck: {total_supply:,.0f}")
#                 except (ValueError, TypeError):
#                     pass
        
#         return supply_data

#     def _build_analysis_prompt_improved(self, data: Dict[str, Any]) -> str:
#         """Build analysis prompt with comprehensive multi-source data aggregation"""
        
#         service_responses = data.get('service_responses', {})
#         security_analysis = data.get('security_analysis', {})
        
#         # Filter out dummy responses before processing
#         filtered_responses = {}
#         for service_name, response_data in service_responses.items():
#             if not self._is_dummy_response(service_name, response_data):
#                 filtered_responses[service_name] = response_data
#             else:
#                 logger.info(f"Filtered out dummy response from {service_name}")
        
#         # Extract comprehensive data from all valid sources
#         market_data = self._extract_comprehensive_market_data(filtered_responses)
#         holder_info = self._extract_comprehensive_holder_data(filtered_responses)
#         token_metadata = self._extract_comprehensive_token_metadata(filtered_responses)
#         supply_data = self._extract_comprehensive_supply_data(filtered_responses)
        
#         # LP security assessment
#         lp_security = self._assess_lp_security_improved(filtered_responses)
        
#         # Critical security issues only
#         critical_flags = self._extract_critical_security_flags(security_analysis)
        
#         # Enhanced data quality calculation
#         data_quality = self._calculate_enhanced_data_quality(filtered_responses, market_data, holder_info)
        
#         prompt = f"""SOLANA TOKEN COMPREHENSIVE MULTI-SOURCE ANALYSIS

# TOKEN: {data.get('token_address')}
# NAME: {token_metadata.get('name', 'Unknown')} ({token_metadata.get('symbol', 'N/A')})
# METADATA SOURCES: {token_metadata.get('metadata_source', 'none')}

# === MARKET ANALYSIS (AGGREGATED FROM MULTIPLE SOURCES) ===
# Price: {market_data.get('price_display', 'Not available')}
# {f"  └─ Source: {market_data.get('price_source', 'N/A')}" if market_data.get('price_source') else ""}
# Market Cap: {market_data.get('market_cap_display', 'Not available')}
# {f"  └─ Source: {market_data.get('market_cap_source', 'N/A')}" if market_data.get('market_cap_source') else ""}
# 24h Volume: {market_data.get('volume_display', 'Not available')}
# {f"  └─ Source: {market_data.get('volume_source', 'N/A')}" if market_data.get('volume_source') else ""}
# Liquidity: {market_data.get('liquidity_display', 'Not available')}
# {f"  └─ Source: {market_data.get('liquidity_source', 'N/A')}" if market_data.get('liquidity_source') else ""}
# Price Change 24h: {market_data.get('change_display', 'Not available')}
# {f"  └─ Source: {market_data.get('change_source', 'N/A')}" if market_data.get('change_source') else ""}

# Volume/Liquidity Ratio: {market_data.get('vol_liq_ratio_display', 'Cannot calculate - data not available')}

# === SUPPLY INFORMATION ===
# {f"Total Supply: {supply_data.get('total_supply', 0):,.0f}" if supply_data.get('total_supply') else "Total Supply: Not available"}
# {f"  └─ Source: {supply_data.get('supply_source', 'N/A')}" if supply_data.get('supply_source') else ""}

# === HOLDER DISTRIBUTION (MULTI-SOURCE) ===
# Holder Count: {holder_info.get('count_display', 'Data not available (very common)')}
# {f"  └─ Source: {holder_info.get('count_source', 'N/A')}" if holder_info.get('count_source') else ""}
# Top 10 Concentration: {holder_info.get('concentration_display', 'Distribution data not available')}
# {f"  └─ Source: {holder_info.get('concentration_source', 'N/A')}" if holder_info.get('concentration_source') else ""}

# === LIQUIDITY SECURITY ===
# Status: {lp_security['status']}
# Evidence: {lp_security['evidence']}
# Assessment Confidence: {lp_security['confidence']}%

# === SECURITY FLAGS ===
# Critical Issues: {len(critical_flags)}
# {chr(10).join(f"🚨 {flag}" for flag in critical_flags) if critical_flags else "✅ No critical security issues detected"}

# === ENHANCED DATA QUALITY ASSESSMENT ===
# Overall Data Quality: {data_quality['score']}/100
# Data Sources Available: {data_quality['source_count']} sources (filtered: {len(service_responses) - len(filtered_responses)} dummy responses removed)
# Market Data Coverage: {data_quality['market_coverage']:.0f}%
# Holder Data Coverage: {data_quality['holder_coverage']:.0f}%
# Metadata Completeness: {data_quality['metadata_completeness']:.0f}%

# Multi-Source Data Status:
# {chr(10).join(f"• {metric}: {'✓' if available else '✗'}" for metric, available in data_quality['data_coverage'].items())}

# Source Reliability Assessment:
# {chr(10).join(f"• {source}: {status}" for source, status in data_quality['source_reliability'].items())}

# === ANALYSIS INSTRUCTIONS ===

# ENHANCED MULTI-SOURCE CONTEXT:
# - Data has been aggregated from ALL available reliable sources
# - Dummy/null responses have been filtered out automatically  
# - Source attribution shows which services provided each metric
# - Missing data gaps have been filled where possible from alternative sources

# CONFIDENCE SCALING:
# - Multi-source confirmation = Higher confidence
# - Single-source data = Medium confidence  
# - No reliable sources = Lower confidence (but not negative)
# - Contradictory sources = Flag for manual review

# REALISTIC MARKET ASSESSMENT:
# - Focus on data quality over quantity
# - Multi-source price data is more reliable than single-source
# - Holder data from multiple sources provides better distribution picture
# - Cross-reference liquidity data across DEX sources

# COMPREHENSIVE SCORING APPROACH:
# - Award extra points for multi-source data confirmation
# - Weight reliable sources higher (Birdeye > DexScreener > others)
# - Account for data freshness and source reputation
# - Don't penalize for missing data that no source provides

# SOURCE-SPECIFIC CONSIDERATIONS:
# - Birdeye: Most reliable for real-time price/volume data
# - GOplus: Best for holder analysis and security flags  
# - RugCheck: Valuable for LP analysis when data is meaningful
# - DexScreener: Good fallback for market data
# - SolSniffer: Useful for metadata when others lack it

# RESPOND WITH VALID JSON. Leverage the multi-source data for more accurate assessment."""

#         return prompt

#     def _calculate_enhanced_data_quality(self, service_responses: Dict[str, Any], market_data: Dict[str, Any], holder_info: Dict[str, Any]) -> Dict[str, Any]:
#         """Calculate enhanced data quality metrics considering multi-source aggregation"""
        
#         # Core data coverage assessment
#         data_coverage = {
#             'Price Data': bool(market_data.get('price')),
#             'Market Cap': bool(market_data.get('market_cap')),
#             'Volume Data': bool(market_data.get('volume_24h')),
#             'Liquidity Data': bool(market_data.get('liquidity')),
#             'Holder Count': bool(holder_info.get('count')),
#             'Holder Distribution': bool(holder_info.get('top_10_percent')),
#             'Price Change': bool(market_data.get('price_change_24h') is not None)
#         }
        
#         # Calculate coverage percentages by category
#         market_metrics = ['Price Data', 'Market Cap', 'Volume Data', 'Liquidity Data', 'Price Change']
#         holder_metrics = ['Holder Count', 'Holder Distribution']
        
#         market_coverage = (sum(1 for m in market_metrics if data_coverage[m]) / len(market_metrics)) * 100
#         holder_coverage = (sum(1 for m in holder_metrics if data_coverage[m]) / len(holder_metrics)) * 100
        
#         # Metadata completeness
#         metadata_score = 0
#         if holder_info.get('name', 'Unknown') != 'Unknown':
#             metadata_score += 50
#         if holder_info.get('symbol', 'N/A') != 'N/A':
#             metadata_score += 50
        
#         # Source reliability assessment
#         source_reliability = {}
#         for service_name in service_responses.keys():
#             reliability = "Unknown"
            
#             # Check if service provided meaningful data
#             contributed_data = []
            
#             if service_name == 'birdeye':
#                 if market_data.get('price_source') == 'birdeye':
#                     contributed_data.append('price')
#                 if market_data.get('volume_source') == 'birdeye':
#                     contributed_data.append('volume')
#                 if market_data.get('liquidity_source') == 'birdeye':
#                     contributed_data.append('liquidity')
            
#             elif service_name == 'goplus':
#                 if holder_info.get('count_source') == 'goplus':
#                     contributed_data.append('holders')
#                 if holder_info.get('concentration_source') == 'goplus':
#                     contributed_data.append('distribution')
            
#             elif service_name == 'dexscreener':
#                 if market_data.get('price_source') == 'dexscreener':
#                     contributed_data.append('price')
#                 if market_data.get('market_cap_source') == 'dexscreener':
#                     contributed_data.append('market_cap')
            
#             elif service_name == 'rugcheck':
#                 if market_data.get('liquidity_source') == 'rugcheck':
#                     contributed_data.append('liquidity')
            
#             if len(contributed_data) >= 2:
#                 reliability = "High (multiple metrics)"
#             elif len(contributed_data) == 1:
#                 reliability = "Good (single metric)"
#             else:
#                 reliability = "Limited (metadata only)"
            
#             source_reliability[service_name] = reliability
        
#         # Overall quality score calculation
#         base_score = (sum(data_coverage.values()) / len(data_coverage)) * 60  # Up to 60 for basic coverage
        
#         # Multi-source bonus
#         multi_source_bonus = 0
#         if market_data.get('price_source') and market_data.get('volume_source'):
#             multi_source_bonus += 10  # Bonus for having multiple market data sources
        
#         if holder_info.get('count_source') and holder_info.get('concentration_source'):
#             multi_source_bonus += 10  # Bonus for having multiple holder data sources
        
#         # Source diversity bonus
#         source_diversity_bonus = min(15, len(service_responses) * 2)  # Up to 15 for having many sources
        
#         # Final quality score
#         quality_score = min(100, base_score + multi_source_bonus + source_diversity_bonus)
        
#         return {
#             'score': round(quality_score),
#             'source_count': len(service_responses),
#             'market_coverage': market_coverage,
#             'holder_coverage': holder_coverage,
#             'metadata_completeness': metadata_score,
#             'data_coverage': data_coverage,
#             'source_reliability': source_reliability,
#             'multi_source_bonus': multi_source_bonus,
#             'source_diversity_bonus': source_diversity_bonus
#         }

#     # Keep existing methods for LP security, critical flags, etc.
#     def _assess_lp_security_improved(self, service_responses: Dict[str, Any]) -> Dict[str, Any]:
#         """Assess LP security with realistic expectations and evidence-based approach"""
        
#         # Initialize with neutral stance
#         lp_assessment = {
#             'status': 'Unknown (data not available - common for many tokens)',
#             'evidence': 'No LP security data available from current sources',
#             'confidence': 0,
#             'risk_level': 'neutral'  # Not negative, just unknown
#         }
        
#         # Check RugCheck for LP evidence
#         rugcheck = service_responses.get('rugcheck', {})
#         if rugcheck:
#             # Method 1: Check lockers data
#             lockers_data = rugcheck.get('lockers_data', {})
#             if lockers_data and lockers_data.get('lockers'):
#                 lockers = lockers_data['lockers']
#                 if isinstance(lockers, dict):
#                     total_locked_value = 0
#                     locker_count = 0
                    
#                     for locker_id, locker_info in lockers.items():
#                         if isinstance(locker_info, dict):
#                             usd_locked = locker_info.get('usdcLocked', 0)
#                             try:
#                                 if isinstance(usd_locked, (int, float)) and usd_locked > 0:
#                                     total_locked_value += float(usd_locked)
#                                     locker_count += 1
#                             except Exception:
#                                 continue
                    
#                     if total_locked_value > 1000:  # Significant value locked
#                         lp_assessment = {
#                             'status': 'SECURED (Verified Locked)',
#                             'evidence': f"${total_locked_value:,.0f} USD locked in {locker_count} Raydium lockers",
#                             'confidence': 95,
#                             'risk_level': 'low'
#                         }
#                         return lp_assessment
            
#             # Method 2: Check market analysis for burn/lock evidence
#             market_analysis = rugcheck.get('market_analysis', {})
#             if market_analysis and market_analysis.get('markets'):
#                 markets = market_analysis['markets']
#                 for market in markets:
#                     if isinstance(market, dict) and market.get('lp'):
#                         lp_info = market['lp']
#                         holders = lp_info.get('holders', [])
                        
#                         for holder in holders:
#                             if isinstance(holder, dict):
#                                 owner = str(holder.get('owner', ''))
#                                 pct = holder.get('pct', 0)
                                
#                                 # Look for burn patterns
#                                 burn_indicators = ['111111', 'dead', 'burn', 'lock', '000000']
#                                 if any(pattern in owner.lower() for pattern in burn_indicators):
#                                     if pct > 50:
#                                         lp_assessment = {
#                                             'status': 'SECURED (Burned)',
#                                             'evidence': f"{pct:.1f}% LP tokens in burn address",
#                                             'confidence': 90,
#                                             'risk_level': 'low'
#                                         }
#                                         return lp_assessment
                                
#                                 # High concentration (could indicate locking)
#                                 elif pct > 95:
#                                     lp_assessment = {
#                                         'status': 'Likely Secured (Highly Concentrated)',
#                                         'evidence': f"{pct:.1f}% LP concentration (possibly locked)",
#                                         'confidence': 60,
#                                         'risk_level': 'medium'
#                                     }
#                                     return lp_assessment
        
#         # Check GOplus for LP data
#         goplus = service_responses.get('goplus', {})
#         if goplus and goplus.get('lp_holders'):
#             lp_holders = goplus['lp_holders']
#             if isinstance(lp_holders, list) and len(lp_holders) > 0:
#                 for holder in lp_holders:
#                     if isinstance(holder, dict):
#                         try:
#                             percent_raw = holder.get('percent', '0')
#                             percent = float(str(percent_raw).replace('%', ''))
                            
#                             if percent > 90:
#                                 lp_assessment = {
#                                     'status': 'Likely Secured (Concentrated)',
#                                     'evidence': f"LP {percent:.1f}% concentrated (possibly locked)",
#                                     'confidence': 55,
#                                     'risk_level': 'medium'
#                                 }
#                                 break
#                         except Exception:
#                             continue
        
#         return lp_assessment

#     def _extract_critical_security_flags(self, security_analysis: Dict[str, Any]) -> List[str]:
#         """Extract only genuinely critical security flags"""
#         critical_flags = []
        
#         # GOplus critical authorities
#         goplus_result = security_analysis.get('goplus_result', {})
#         if goplus_result:
#             # Mint authority (unlimited supply)
#             mintable = goplus_result.get('mintable', {})
#             if isinstance(mintable, dict) and mintable.get('status') == '1':
#                 critical_flags.append("Mint authority active (unlimited supply possible)")
            
#             # Freeze authority (can freeze accounts)
#             freezable = goplus_result.get('freezable', {})
#             if isinstance(freezable, dict) and freezable.get('status') == '1':
#                 critical_flags.append("Freeze authority active (accounts can be frozen)")
        
#         # Only include verified rug/scam evidence
#         critical_issues = security_analysis.get('critical_issues', [])
#         for issue in critical_issues:
#             issue_str = str(issue).lower()
#             if any(keyword in issue_str for keyword in ['rugged', 'scam', 'honeypot', 'malicious', 'exploit']):
#                 critical_flags.append(issue)
        
#         return critical_flags

#     def _parse_ai_response(self, ai_response: str):
#         """Parse Groq response into structured format with improved defaults"""
#         try:
#             parsed_data = json.loads(ai_response)
            
#             return {
#                 "ai_score": float(parsed_data.get("ai_score", 65)),  # More optimistic default
#                 "risk_assessment": parsed_data.get("risk_assessment", "medium"),
#                 "recommendation": parsed_data.get("recommendation", "CONSIDER"),  # More optimistic
#                 "confidence": float(parsed_data.get("confidence", 70)),  # Higher default confidence
#                 "key_insights": parsed_data.get("key_insights", ["Multi-source token analysis completed with available data"]),
#                 "risk_factors": parsed_data.get("risk_factors", []),
#                 "stop_flags": parsed_data.get("stop_flags", []),
#                 "market_metrics": parsed_data.get("market_metrics", {}),
#                 "llama_reasoning": parsed_data.get("llama_reasoning", "Multi-source analysis completed using aggregated market data sources"),
#                 "processing_time": 0.0,
#             }
            
#         except Exception as e:
#             logger.error(f"Failed to parse Groq response: {str(e)}")
#             return self._create_neutral_fallback_dict()
    
#     def _create_neutral_fallback_dict(self):
#         """Create neutral fallback response dict when parsing fails"""
#         return {
#             "ai_score": 60.0,  # Neutral score
#             "risk_assessment": "medium",
#             "recommendation": "HOLD", 
#             "confidence": 50.0,
#             "key_insights": ["Analysis completed with limited data"],
#             "risk_factors": ["AI response parsing failed - manual review recommended"],
#             "stop_flags": [],
#             "market_metrics": {
#                 "data_quality": 50,
#                 "analysis_confidence": 50
#             },
#             "llama_reasoning": "AI analysis encountered parsing issues but completed basic assessment with available data.",
#             "processing_time": 0.0,
#         }
    
#     def _create_neutral_fallback(self, token_address: str, processing_time: float) -> AIAnalysisResponse:
#         """Create neutral fallback response when analysis fails completely"""
#         return AIAnalysisResponse(
#             ai_score=60.0,  # Neutral score
#             risk_assessment="medium",  # Medium risk
#             recommendation="HOLD",  # Neutral recommendation
#             confidence=50.0,  # Moderate confidence
#             key_insights=["AI analysis temporarily unavailable"],
#             risk_factors=["Limited analysis due to temporary system issue"],
#             stop_flags=[],  # No stop flags for system issues
#             market_metrics={
#                 "system_available": False,
#                 "fallback_used": True
#             },
#             llama_reasoning="AI analysis system temporarily unavailable. Based on available data, no immediate critical issues detected.",
#             processing_time=processing_time,
#         )

# Global service instance
groq_llama_service = GroqLlamaService()