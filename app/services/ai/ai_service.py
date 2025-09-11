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
        """Build comprehensive system prompt for token analysis in Russian"""
        return """Ты эксперт-аналитик Solana токенов, специализирующийся на оценке криптовалют. Твоя задача - анализировать данные токенов и предоставлять структурированные инвестиционные рекомендации с реалистичными ожиданиями о доступности данных.

    ФРЕЙМВОРК АНАЛИЗА:
    Оценивай токены на основе этих критических метрик, но учитывай доступность данных:

    РЫНОЧНАЯ КАПИТАЛИЗАЦИЯ (MCAP):
    - Отлично: <$1M (высокий потенциал роста)
    - Хорошо: $1M-$10M (умеренный рост)
    - Приемлемо: $10M-$50M (устоявшийся)
    - Плохо: >$50M (ограниченный рост)

    ЛИКВИДНОСТЬ:
    - Отлично: $500K+ (очень сильная)
    - Хорошо: $100K-$500K (сильная)
    - Приемлемо: $50K-$100K (умеренная)
    - Плохо: <$50K (слабая)

    ОТНОШЕНИЕ ОБЪЕМ/ЛИКВИДНОСТЬ:
    - Отлично: >10% (очень активно)
    - Хорошо: 5-10% (активно)
    - Приемлемо: 1-5% (умеренно)
    - Плохо: <1% (низкая активность)

    КОНЦЕНТРАЦИЯ ТОПОВЫХ ХОЛДЕРОВ:
    - Отлично: <20% (отличное распределение)
    - Хорошо: 20-35% (хорошее распределение)
    - Приемлемо: 35-50% (умеренный риск)
    - Плохо: >50% (высокий риск концентрации)

    СТАТУС LP (с реалистичными ожиданиями):
    - Отлично: Проверенно сожжен/заблокирован
    - Хорошо: Сильные доказательства блокировки
    - Приемлемо: Умеренные доказательства или концентрация
    - Неизвестно: Данные недоступны (нейтрально, не негативно)

    ФЛАГИ БЕЗОПАСНОСТИ (ТОЛЬКО КРИТИЧЕСКИЕ):
    - Активные полномочия минта (риск неограниченного предложения)
    - Активные полномочия заморозки (риск заморозки аккаунтов)
    - Ограничения переводов или поведение honeypot
    - Подтвержденный rug pull или скам

    ФИЛОСОФИЯ ДОСТУПНОСТИ ДАННЫХ:
    - Отсутствующие данные НЕ автоматически негативны
    - Фокусируйся на качестве доступных данных
    - Наказывай только за явно негативные индикаторы
    - Неизвестно ≠ Плохо (нейтральная позиция)

    ФОРМАТ ОТВЕТА:
    Предоставь анализ в JSON формате с:
    - ai_score (0-100): Общая оценка токена
    - risk_assessment: "low", "medium", "high", "critical"
    - recommendation: "BUY", "CONSIDER", "HOLD", "CAUTION", "AVOID"
    - confidence (0-100): Уверенность в анализе на основе доступных данных
    - key_insights: Список найденных положительных факторов
    - risk_factors: Список реальных проблем (не пробелов в данных)
    - stop_flags: Список только критических красных флагов
    - market_metrics: Ключевые рассчитанные метрики
    - llama_reasoning: Подробное объяснение

    ЛОГИКА ПРИНЯТИЯ РЕШЕНИЙ (Менее строгая):
    - BUY: Исключительные метрики с высокой уверенностью в данных
    - CONSIDER: Хорошие метрики с разумными данными
    - HOLD: Смешанные сигналы или умеренные метрики
    - CAUTION: Некоторые тревожные факторы присутствуют
    - AVOID: Явные красные флаги или критические проблемы безопасности

    РАСЧЕТ УВЕРЕННОСТИ:
    - Высокая (80-100%): Сильные данные из множественных источников
    - Средняя (60-79%): Хорошее покрытие данных с некоторыми пробелами
    - Низкая (40-59%): Ограниченные данные, но без красных флагов
    - Очень низкая (<40%): Минимальные доступные данные

    Будь реалистичен относительно ограничений данных на крипто рынках. Фокусируйся на реальных индикаторах риска, а не на пробелах в данных."""
    
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

        # === ENHANCED METRICS EXTRACTION ===
        goplus_data = request.service_responses.get("goplus", {})
        rugcheck_data = request.service_responses.get("rugcheck", {})
        
        # Extract whale data
        whale_data = self._extract_whale_data(goplus_data, rugcheck_data)
        data.update({
            "whale_count": whale_data["whale_count"],
            "whale_control_percent": whale_data["whale_control_percent"],
            "top_whale_percent": whale_data["top_whale_percent"]
        })
        
        # Extract sniper data
        sniper_data = self._analyze_sniper_patterns(goplus_data)
        data.update({
            "sniper_similar_holders": sniper_data["similar_holders"],
            "sniper_pattern_detected": sniper_data["pattern_detected"]
        })
        
        logger.info(f"Enhanced metrics: {whale_data['whale_count']} whales, {sniper_data['similar_holders']} sniper patterns")
        
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
                else:
                    # No whales = good distribution
                    whale_data["data_available"] = True
            
            return whale_data
            
        except Exception as e:
            logger.warning(f"Whale extraction failed: {e}")
            return whale_data

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
                    if abs(p1 - p2) < 0.05:  # Very similar percentages
                        similar_count += 1
            
            pattern_detected = similar_count > 5
            
            return {
                "similar_holders": similar_count,
                "pattern_detected": pattern_detected,
                "data_available": True
            }
            
        except Exception as e:
            logger.warning(f"Sniper pattern analysis failed: {e}")
            return {"similar_holders": 0, "pattern_detected": False, "data_available": False}
        
    async def analyze_token_timing(self, request: AIAnalysisRequest) -> Optional[Dict[str, Any]]:
        """Separate timing analysis with Russian predictions"""
        try:
            logger.info(f"⏰ Starting timing analysis for {request.token_address}")
            
            # Prepare data
            analysis_data = self._prepare_analysis_data(request)
            
            # Build timing-specific prompt
            timing_prompt = self._build_timing_analysis_prompt(analysis_data)
            
            # Call Groq
            response_text = await groq_llama_service.send_request(timing_prompt)
            
            if not response_text:
                return None
            
            # Parse timing response
            try:
                timing_data = json.loads(response_text)
                logger.info(f"✅ Timing analysis completed")
                return timing_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse timing JSON: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Timing analysis failed: {e}")
            return None

    def _build_timing_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Build timing-specific analysis prompt"""
        
        # Calculate additional timing indicators
        volume_24h = data.get('volume_24h', 0)
        market_cap = data.get('market_cap', 0)
        price_change_24h = data.get('price_change_24h', 0)
        volatility = data.get('recent_volatility_percent', 0)
        
        # Activity level assessment
        activity_level = "низкая"
        if volume_24h > 100000:
            activity_level = "высокая"
        elif volume_24h > 10000:
            activity_level = "средняя"
        
        # Market cap category
        mcap_category = "крупная"
        if market_cap < 1000000:
            mcap_category = "микро"
        elif market_cap < 10000000:
            mcap_category = "малая"
        elif market_cap < 50000000:
            mcap_category = "средняя"
        
        prompt = f"""АНАЛИЗ ВРЕМЕНИ СОЛАНА ТОКЕНА

    ТОКЕН: {data['token_address']}

    === ВРЕМЕННЫЕ ДАННЫЕ ===
    Недавняя волатильность: {data.get('recent_volatility_percent', 'Недоступно')}%
    Отношение объем/ликвидность: {data.get('volume_liquidity_ratio', 'Недоступно')}%
    Количество китов: {data.get('whale_count', 'Недоступно')}
    Контроль китов: {data.get('whale_control_percent', 'Недоступно')}%
    Схожие холдеры (боты): {data.get('sniper_similar_holders', 'Недоступно')}
    Объем 24ч: ${volume_24h:,.0f} ({activity_level} активность)
    Рыночная кап: ${market_cap:,.0f} ({mcap_category} кап)
    Ликвидность: ${data.get('liquidity', 0):,.0f}
    Изменение цены 24ч: {price_change_24h:+.2f}%

    === АНАЛИЗ ВРЕМЕННЫХ ПАТТЕРНОВ ===

    Проанализируй временные окна для этого токена на основе следующих факторов:

    1. ОПРЕДЕЛЕНИЕ ПОСЛЕДНЕГО ПАМПА:
    - Изменение цены 24ч {price_change_24h:+.2f}% (>20% = недавний памп)
    - Волатильность {volatility}% (>30% = недавняя активность)
    - Активность торговли: {activity_level}
    - Если высокие показатели = "Недавно" или "24ч назад"
    - Если низкие показатели = "Нет недавних пампов"

    2. ПРЕДСКАЗАНИЕ СЛЕДУЮЩЕГО ОКНА:
    - Микро кап (<$1M) + высокая активность = "Немедленно" или "1-2ч"
    - Малая кап ($1-10M) + средняя активность = "2-6ч" или "6-24ч"
    - Средняя/крупная кап + низкая активность = "1-3д" или "Неизвестно"
    - Высокая концентрация китов = более долгие окна
    - Много ботов = более быстрые окна

    3. ОПРЕДЕЛЕНИЕ ФАЗЫ РЫНКА:
    - Низкий объем + стабильная цена = "накопление"
    - Высокий объем + рост цены = "памп"
    - Высокий объем + падение цены = "распределение"
    - Низкий объем + боковик = "консолидация"
    - Недостаточно данных = "неизвестно"

    4. ОЦЕНКА ВЕРОЯТНОСТИ ПАМПА:
    - Учитывай возраст токена, активность, распределение
    - Новые токены + высокая активность = высокая вероятность
    - Устоявшиеся токены + низкая активность = низкая вероятность

    ВРЕМЕННЫЕ ПРАВИЛА:
    - Немедленно: Очень высокая активность, микро кап, свежие сигналы
    - 1-2ч: Высокая активность, небольшая кап, недавний импульс
    - 2-6ч: Средняя активность, умеренные сигналы
    - 6-24ч: Низкая активность, но потенциал есть
    - 1-3д: Долгосрочные сигналы, крупные капы
    - Неизвестно: Недостаточно данных или противоречивые сигналы

    ФОРМАТ ОТВЕТА (ТОЛЬКО JSON):
    {{
    "last_pump": "Недавно|24ч назад|2-3 дня назад|Неделю назад|Нет недавних пампов",
    "next_window": "Немедленно|1-2ч|2-6ч|6-24ч|1-3д|Неизвестно",
    "pump_probability": 0-100,
    "timing_confidence": 0-100,
    "market_phase": "накопление|памп|распределение|консолидация|неизвестно",
    "reasoning": "Краткое объяснение временного анализа на русском (1-2 предложения)",
    "signals": ["список конкретных временных сигналов"]
    }}

    ПРИНЦИПЫ АНАЛИЗА ВРЕМЕНИ:
    - Используй КОНКРЕТНЫЕ данные для предсказаний
    - Высокие изменения цены = недавняя активность
    - Малая кап + активность = быстрые окна
    - Большая кап + стабильность = медленные окна
    - Будь реалистичен с уверенностью

    ОТВЕЧАЙ ТОЛЬКО JSON."""

        return prompt
    
    def _build_main_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Build main analysis prompt without timing section"""
        
        # Helper function to format data availability
        def format_data_point(value, label, format_func=None):
            if value is not None:
                formatted = format_func(value) if format_func else str(value)
                return f"{label}: {formatted} ✓"
            return f"{label}: Недоступно"
        
        # Build market data section
        market_data_lines = [
            format_data_point(data.get('market_cap'), "Рыночная кап", lambda x: f"${x:,.0f}"),
            format_data_point(data.get('liquidity'), "Ликвидность", lambda x: f"${x:,.0f}"),
            format_data_point(data.get('volume_24h'), "Объем 24ч", lambda x: f"${x:,.0f}"),
            format_data_point(data.get('volume_liquidity_ratio'), "Объем/Ликвидность", lambda x: f"{x:.1f}%"),
            format_data_point(data.get('price_usd'), "Цена", lambda x: f"${x:.8f}"),
            format_data_point(data.get('price_change_24h'), "Изменение 24ч", lambda x: f"{x:+.2f}%")
        ]
        
        # Build enhanced metrics section
        enhanced_metrics_lines = [
            format_data_point(data.get('recent_volatility_percent'), "Недавняя волатильность", lambda x: f"{x}%"),
            format_data_point(data.get('whale_count'), "Количество китов", lambda x: f"{x} китов"),
            format_data_point(data.get('whale_control_percent'), "Контроль китов", lambda x: f"{x}%"),
            format_data_point(data.get('top_whale_percent'), "Топ кит", lambda x: f"{x}%"),
            format_data_point(data.get('sniper_similar_holders'), "Схожие холдеры", lambda x: f"{x} паттернов"),
            f"Обнаружен паттерн снайперов: {data.get('sniper_pattern_detected', False)}"
        ]
        
        # Build holder data section
        holder_data_lines = [
            format_data_point(data.get('holder_count'), "Всего холдеров", lambda x: f"{x:,}"),
            format_data_point(data.get('top_holders_percent'), "Контроль топ-10", lambda x: f"{x:.1f}%"),
            format_data_point(data.get('dev_percent'), "Холдинги разработчика", lambda x: f"{x:.1f}%")
        ]
        
        # Build LP section
        lp_status = data.get('lp_status', 'неизвестно')
        lp_confidence = data.get('lp_confidence', 0)
        lp_evidence = data.get('lp_evidence', [])
        
        lp_status_text = {
            'locked': 'ЗАЩИЩЕН (Заблокирован)',
            'burned': 'ЗАЩИЩЕН (Сожжен)', 
            'concentrated': 'ВЕРОЯТНО ЗАЩИЩЕН (Сконцентрирован)',
            'unknown': 'НЕИЗВЕСТНО (Данные недоступны)'
        }.get(lp_status, 'НЕИЗВЕСТНО')
        
        lp_info = f"Статус LP: {lp_status_text}"
        if lp_confidence > 0:
            lp_info += f" (Уверенность: {lp_confidence}%)"
        if lp_evidence:
            lp_info += f"\nДоказательства: {'; '.join(lp_evidence)}"
        
        # Security flags
        security_flags = data.get('security_flags', [])
        security_section = "Критические проблемы безопасности не обнаружены" if not security_flags else "\n".join(f"🚨 {flag}" for flag in security_flags)
        
        prompt = f"""РАСШИРЕННЫЙ АНАЛИЗ SOLANA ТОКЕНА - AI ОЦЕНКА РИСКОВ

    ТОКЕН: {data['token_address']}

    === РЫНОЧНЫЕ ПОКАЗАТЕЛИ ===
    {chr(10).join(market_data_lines)}

    === РАСШИРЕННЫЕ МЕТРИКИ РИСКОВ ===
    {chr(10).join(enhanced_metrics_lines)}

    === РАСПРЕДЕЛЕНИЕ ХОЛДЕРОВ ===  
    {chr(10).join(holder_data_lines)}

    === БЕЗОПАСНОСТЬ ЛИКВИДНОСТИ ===
    {lp_info}
    Полномочия минта: {'АКТИВНЫ 🚨' if data.get('mint_authority_active') else 'ОТКЛЮЧЕНЫ ✓'}
    Полномочия заморозки: {'АКТИВНЫ ⚠️' if data.get('freeze_authority_active') else 'ОТКЛЮЧЕНЫ ✓'}

    === АНАЛИЗ БЕЗОПАСНОСТИ ===
    {security_section}

    === ДОСТУПНОСТЬ ДАННЫХ ===
    Общая полнота: {data.get('data_completeness', 0):.1f}%
    Доступные точки данных: {sum(data.get('data_availability', {}).values())} / {len(data.get('data_availability', {}))}

    === ИНСТРУКЦИИ ДЛЯ AI АНАЛИЗА ===

    Ты анализируешь этот токен с РАСШИРЕННЫМИ МЕТРИКАМИ. Оцени уровень риска каждой метрики:

    1. ОЦЕНКА РИСКА РЫНОЧНОЙ КАПИТАЛИЗАЦИИ:
    - Оцени, указывает ли рыночная кап на риск пампа, потенциал роста или стабильность
    - Рассмотри рыночную кап в контексте ликвидности и объема

    2. ОЦЕНКА РИСКА ВОЛАТИЛЬНОСТИ:
    - Проанализируй процент недавней торговой волатильности
    - Высокая волатильность может указывать на нестабильность ИЛИ возможность
    - Рассмотри волатильность в контексте объема и активности китов

    3. ОЦЕНКА РИСКА КИТОВ:
    - Оцени концентрацию китов и риск дампа
    - 0 китов = ЛУЧШИЙ (идеальное распределение)
    - Рассмотри количество китов против процента контроля
    - Оцени потенциал координированных продаж

    4. ОЦЕНКА РИСКА СНАЙПЕРОВ/БОТОВ:
    - Проанализируй паттерны холдеров на искусственный спрос
    - Много схожих процентов холдеров = активность ботов
    - Обнаружение паттернов указывает на координированные покупки

    5. ОЦЕНКА ГЛУБИНЫ ЛИКВИДНОСТИ:
    - Оцени отношение объем/ликвидность для здоровья рынка
    - Высокое отношение = активная торговля, Низкое = тонкие рынки
    - Рассмотри глубину ликвидности для влияния на цену

    6. ОЦЕНКА РИСКА ХОЛДИНГОВ РАЗРАБОТЧИКА:
    - Оцени процент токенов разработчика
    - Высокие холдинги разработчика = риск дампа
    - Рассмотри, разумны ли холдинги разработчика для стадии проекта

    7. ОЦЕНКА БЕЗОПАСНОСТИ LP:
    - Оцени статус блокировки/сжигания поставщика ликвидности
    - Заблокирован/Сожжен = безопасно, Неизвестно = нейтрально (не негативно)
    - Рассмотри доказательства LP и уровень доверия

    КОМПЛЕКСНАЯ ОЦЕНКА РИСКОВ:
    - НЕ предварительно категоризируй риски - анализируй каждую метрику независимо
    - Рассматривай взаимодействия метрик (например, высокая волатильность + киты = дополнительный риск)
    - Взвешивай метрики на основе доверия к качеству данных
    - Отсутствующие данные = нейтральная оценка, не негативная

    ФОРМАТ JSON ОТВЕТА (ТОЛЬКО JSON):
    {{
    "ai_score": 0-100,
    "risk_assessment": "low|medium|high|critical",
    "recommendation": "BUY|CONSIDER|HOLD|CAUTION|AVOID", 
    "confidence": 0-100,
    "key_insights": ["конкретные положительные факторы с данными"],
    "risk_factors": ["конкретные проблемы с данными"],
    "stop_flags": ["только критические проблемы"],
    "market_metrics": {{
        "volatility_risk": "low|medium|high|unknown",
        "whale_risk": "low|medium|high|unknown", 
        "sniper_risk": "low|medium|high|unknown",
        "liquidity_health": "excellent|good|poor|unknown",
        "dev_risk": "low|medium|high|unknown",
        "lp_security": "secure|likely_secure|unknown|risky"
    }},
    "llama_reasoning": "Комплексный анализ всех доступных метрик"
    }}

    КРИТЕРИИ РЕШЕНИЙ:
    - BUY: Балл >85, все основные риски низкие, высокое доверие к данным
    - CONSIDER: Балл >70, приемлемые уровни рисков, хорошие данные
    - HOLD: Балл >55, смешанные сигналы или умеренные риски
    - CAUTION: Балл >40, некоторые тревожные факторы
    - AVOID: Балл <40 или любые критические флаги безопасности

    ОТВЕЧАЙ ТОЛЬКО ВАЛИДНЫМ JSON."""

        return prompt
    
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
    """AI analysis that runs main + timing analysis separately then combines"""
    logger.info(f"🚀 Running AI analysis for {request.token_address}")
    
    try:
        start_time = time.time()
        
        # Prepare data once for both analyses
        analysis_data = llama_ai_service._prepare_analysis_data(request)
        
        # Run both analyses concurrently
        main_task = run_main_analysis(analysis_data)
        timing_task = run_timing_analysis(analysis_data)
        
        main_result, timing_result = await asyncio.gather(main_task, timing_task, return_exceptions=True)
        
        # Handle main analysis result
        if isinstance(main_result, Exception) or not main_result:
            logger.error(f"Main analysis failed: {main_result}")
            return None
        
        # Handle timing analysis result
        if isinstance(timing_result, Exception) or not timing_result:
            logger.warning(f"Timing analysis failed: {timing_result}, using defaults")
            timing_result = {
                "last_pump": "Неизвестно",
                "next_window": "Неизвестно",
                "pump_probability": 50,
                "timing_confidence": 30,
                "market_phase": "неизвестно",
                "reasoning": "Временной анализ недоступен"
            }
        else:
            logger.info(f"✅ Timing analysis succeeded: {timing_result}")
        
        # Combine results - Add timing to market_metrics (FIXED APPROACH)
        logger.info(f"🔗 Combining main + timing results...")
        
        combined_market_metrics = main_result.market_metrics.copy()
        combined_market_metrics["timing_analysis"] = timing_result
        
        processing_time = time.time() - start_time
        
        combined_response = AIAnalysisResponse(
            ai_score=main_result.ai_score,
            risk_assessment=main_result.risk_assessment,
            recommendation=main_result.recommendation,
            confidence=main_result.confidence,
            key_insights=main_result.key_insights,
            risk_factors=main_result.risk_factors,
            stop_flags=main_result.stop_flags,
            market_metrics=combined_market_metrics,  # Contains timing_analysis
            llama_reasoning=main_result.llama_reasoning,
            processing_time=processing_time
        )
        
        logger.info(f"✅ Combined AI analysis completed: Score {combined_response.ai_score}, Timing: {timing_result.get('next_window', 'Unknown')}")
        
        return combined_response
        
    except Exception as e:
        logger.error(f"Combined AI analysis failed: {e}")
        return None
    
async def run_main_analysis(analysis_data: Dict[str, Any]) -> Optional[AIAnalysisResponse]:
    """Run main risk analysis without timing"""
    try:
        # Build main analysis prompt (your existing prompt without timing section)
        prompt = llama_ai_service._build_main_analysis_prompt(analysis_data)
        
        # Call Groq
        response_text = await groq_llama_service.send_request(prompt)
        if not response_text:
            return None
        
        # Parse response
        response_data = json.loads(response_text)
        
        return AIAnalysisResponse(
            ai_score=float(response_data.get("ai_score", 60.0)),
            risk_assessment=response_data.get("risk_assessment", "medium"),
            recommendation=response_data.get("recommendation", "HOLD"),
            confidence=float(response_data.get("confidence", 70.0)),
            key_insights=response_data.get("key_insights", []),
            risk_factors=response_data.get("risk_factors", []),
            stop_flags=response_data.get("stop_flags", []),
            market_metrics=response_data.get("market_metrics", {}),
            llama_reasoning=response_data.get("llama_reasoning", "Analysis completed"),
            processing_time=0.0
        )
        
    except Exception as e:
        logger.error(f"Main analysis failed: {e}")
        return None

async def run_timing_analysis(analysis_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run timing analysis separately"""
    try:
        # Build timing-specific prompt using the new method
        timing_prompt = llama_ai_service._build_timing_analysis_prompt(analysis_data)
        
        # Call Groq
        response_text = await groq_llama_service.send_request(timing_prompt)
        if not response_text:
            return None
        
        # Parse timing response
        timing_data = json.loads(response_text)
        logger.info(f"✅ Timing analysis: {timing_data.get('next_window', 'Unknown')}")
        return timing_data
        
    except Exception as e:
        logger.error(f"Timing analysis failed: {e}")
        return None

async def generate_analysis_docx_from_cache(cache_key: str) -> Optional[bytes]:
    """Generate DOCX report from cached analysis data"""
    try:
        logger.info(f"📄 Generating DOCX from cache key: {cache_key}")
        
        from app.utils.cache import cache_manager
        
        # Try to get cached data
        try:
            cached_data = await cache_manager.get(key=cache_key)
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