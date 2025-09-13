from typing import Dict, Any, Optional, List
from loguru import logger
import time
import json
import asyncio
from datetime import datetime

from app.services.analysis_storage import analysis_storage


class PumpAnalysisProfile:
    """Simplified pump analysis using existing snapshots"""
    
    def __init__(self):
        self.profile_name = "Pump Detection"
        self.analysis_type = "pump"

    async def analyze_snapshots_for_pumps(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze existing snapshots for pump patterns using filters"""
        start_time = time.time()
        
        try:
            logger.info("📊 Querying snapshots for pump analysis...")
            
            # Generate run_id here (consistent across method)
            run_id = f"run_{int(time.time())}"  # 🆕 GENERATE ONCE HERE
            
            # Get recent snapshots from ChromaDB
            snapshots = await self._get_recent_snapshots(limit=200)
            
            if not snapshots:
                return {
                    "candidates": [],
                    "total_found": 0,
                    "message": "No snapshots found for analysis",
                    "run_id": None  # No run_id if no data
                }
            
            logger.info(f"Found {len(snapshots)} snapshots to analyze")
            
            # Filter and score snapshots
            candidates = []
            for snapshot in snapshots:
                try:
                    candidate = self._analyze_snapshot_for_pump(snapshot, filters)
                    if candidate:
                        candidates.append(candidate)
                        logger.info(f"✅ Candidate found: {candidate['name']} - Score: {candidate['pump_score']}")
                except Exception as e:
                    logger.warning(f"Error analyzing snapshot: {e}")
                    continue
            
            # Sort by pump score (highest first)
            candidates.sort(key=lambda x: x.get("pump_score", 0), reverse=True)
            
            # Add ranks and generate AI messages for top candidates
            for i, candidate in enumerate(candidates[:5]):
                candidate["rank"] = i + 1
                try:
                    ai_message = await self._generate_pump_ai_message(candidate)
                    candidate["ai"] = ai_message
                    logger.info(f"Generated AI message for {candidate['name']}: {ai_message[:50]}...")
                except Exception as e:
                    logger.warning(f"AI message generation failed for {candidate['name']}: {e}")
                    candidate["ai"] = self._generate_fallback_message(candidate)
            
            # Return top 5
            top_candidates = candidates[:5]
            
            # Store run data only if we have candidates
            if len(candidates) > 0:
                run_data = {
                    "run_id": run_id,
                    "profile_type": "pump_filter",
                    "timestamp": int(time.time()),
                    "filters": filters,
                    "snapshots_analyzed": len(snapshots),
                    "candidates_found": len(candidates),
                    "results": top_candidates,
                    "processing_time": time.time() - start_time,
                    "status": "completed"
                }
                
                # Store run asynchronously
                asyncio.create_task(analysis_storage.store_analysis_run(run_data))
                logger.info(f"📊 Storing pump run: {run_id} with {len(candidates)} candidates")
            
            return {
                "candidates": top_candidates,
                "total_found": len(candidates),
                "snapshots_analyzed": len(snapshots),
                "run_id": run_id if len(candidates) > 0 else None
            }
            
        except Exception as e:
            logger.error(f"Snapshot pump analysis failed: {e}")
            return {
                "candidates": [],
                "total_found": 0,
                "error": str(e),
                "snapshots_analyzed": 0,
                "run_id": None
            }
    
    async def _get_recent_snapshots(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get recent snapshots from ChromaDB"""
        try:
            # Search for token snapshots
            results = await analysis_storage.search_analyses(
                query="token snapshot recent",
                limit=limit,
                filters={"doc_type": "token_snapshot"}
            )
            
            if not results:
                return []
            
            # Convert to snapshot format
            snapshots = []
            for result in results:
                metadata = result.get("metadata", {})
                if metadata.get("token_address"):
                    snapshots.append(metadata)
            
            logger.info(f"Retrieved {len(snapshots)} snapshots from ChromaDB")
            
            # Debug: show first snapshot data
            if snapshots:
                first = snapshots[0]
                logger.info(f"Sample snapshot fields: {list(first.keys())}")
                logger.info(f"Sample data: liq={first.get('liquidity')}, mcap={first.get('market_cap')}, vol={first.get('volume_24h')}")
            
            return snapshots
            
        except Exception as e:
            logger.error(f"Error getting snapshots: {e}")
            return []
    
    def _analyze_snapshot_for_pump(self, snapshot: Dict[str, Any], filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze a single snapshot for pump patterns"""
        try:
            # Extract data from snapshot metadata
            token_address = snapshot.get("token_address")
            if not token_address:
                return None
            
            # Parse numeric fields safely
            liquidity = self._parse_float(snapshot.get("liquidity", "0"))
            market_cap = self._parse_float(snapshot.get("market_cap", "0"))
            volume_1h = self._parse_float(snapshot.get("volume_1h", "0"))
            volume_5m = self._parse_float(snapshot.get("volume_5m", "0"))
            
            # Extract whale activity data
            whale_activity_raw = snapshot.get("whale_activity_1h", "{}")
            try:
                whale_activity = json.loads(whale_activity_raw)
            except:
                whale_activity = {"count": 0, "total_inflow_usd": 0, "addresses": []}
            
            # Calculate age from timestamp
            timestamp_str = snapshot.get("timestamp", "")
            age_minutes = self._calculate_age_minutes(timestamp_str)
            
            # Apply filters (using whale count instead of percentage)
            if not self._passes_filters(liquidity, market_cap, volume_5m, whale_activity["count"], age_minutes, filters):
                return None
            
            # Calculate pump score
            pump_score = self._calculate_pump_score(volume_5m, liquidity, age_minutes)
            
            # Extract token info
            token_name = snapshot.get("token_name", "Unknown")
            token_symbol = snapshot.get("token_symbol", "N/A")
            
            # Extract security data from snapshot
            security_issues = []
            security_details = {}
            
            # Check for security warnings in snapshot metadata
            critical_issues = snapshot.get("critical_issues_list", "[]")
            warnings_list = snapshot.get("warnings_list", "[]")
            
            try:
                if isinstance(critical_issues, str):
                    critical_issues = json.loads(critical_issues)
                if isinstance(warnings_list, str):
                    warnings_list = json.loads(warnings_list)
                
                # Add critical issues as security issues
                if critical_issues:
                    security_issues.extend(critical_issues)
                    security_details["critical_issues"] = critical_issues
                
                # Add warnings as security issues
                if warnings_list:
                    security_issues.extend(warnings_list)
                    security_details["warnings"] = warnings_list
                    
            except (json.JSONDecodeError, TypeError):
                pass
            
            # Determine security verdict
            sec_verdict = "CAUTION" if security_issues else "OK"
            
            return {
                "rank": 0,  # Will be set after sorting
                "name": f"{token_name} ({token_symbol})" if token_symbol != "N/A" else token_name,
                "mint": f"{token_address[:4]}...{token_address[-4:]}",
                "mint_full": token_address,
                "liq": int(liquidity),
                "vol5": int(volume_5m),
                "vol60": int(volume_1h),
                "whales1h": whale_activity,  # Full whale activity data
                "social": 0,  # Placeholder
                "mcap": int(market_cap),
                "ai": "",  # Will be filled with AI analysis
                "pump_score": round(pump_score, 2),
                "age_minutes": age_minutes,
                "timestamp": timestamp_str,
                "security": {
                    "ok": True,  # Always true since security check is completed
                    "issues": security_issues,
                    "details": security_details
                },
                "secVerdict": sec_verdict
            }
            
        except Exception as e:
            logger.warning(f"Error analyzing snapshot for {snapshot.get('token_address', 'unknown')}: {e}")
            return None
    
    def _passes_filters(self, liquidity: float, market_cap: float, 
                       volume_5m: float, whale_count: int, age_minutes: float, 
                       filters: Dict[str, Any]) -> bool:
        """Check if snapshot passes all filters"""
        try:
            # Skip if critical data is missing
            if market_cap <= 0:
                logger.debug(f"Skipping: market_cap={market_cap} (missing or zero)")
                return False
            
            # Liquidity filter
            if liquidity < filters.get("liqMin", 0) or liquidity > filters.get("liqMax", float('inf')):
                logger.debug(f"Liquidity filter failed: {liquidity} not in [{filters.get('liqMin')}, {filters.get('liqMax')}]")
                return False
            
            # Market cap filter
            if market_cap < filters.get("mcapMin", 0) or market_cap > filters.get("mcapMax", float('inf')):
                logger.debug(f"Market cap filter failed: {market_cap} not in [{filters.get('mcapMin')}, {filters.get('mcapMax')}]")
                return False
            
            # Volume filter
            if volume_5m < filters.get("volMin", 0) or volume_5m > filters.get("volMax", float('inf')):
                logger.debug(f"Volume filter failed: {volume_5m} not in [{filters.get('volMin')}, {filters.get('volMax')}]")
                return False
            
            # Age filter (filters are already in minutes, no conversion needed)
            time_min_minutes = filters.get("timeMin", 0)
            time_max_minutes = filters.get("timeMax", float('inf'))
            if age_minutes < time_min_minutes or age_minutes > time_max_minutes:
                logger.debug(f"Age filter failed: {age_minutes} min not in [{time_min_minutes}, {time_max_minutes}] min")
                return False
            
            # Whale filter (now using whale count instead of percentage)
            if whale_count < filters.get("whales1hMin", 0):
                logger.debug(f"Whale filter failed: {whale_count} < {filters.get('whales1hMin')}")
                return False
            
            # Social filter - commented out as requested
            # social_score = 0  # Not available in snapshots yet
            # if social_score < filters.get("socialMin", 0):
            #     return False
            
            logger.debug(f"✅ All filters passed!")
            return True
            
        except Exception as e:
            logger.warning(f"Filter check failed: {e}")
            return False
    
    def _calculate_pump_score(self, volume: float, liquidity: float, age_minutes: float) -> float:
        """Calculate pump score: volume * (volume/liquidity ratio) / age_minutes"""
        try:
            if age_minutes <= 0:
                age_minutes = 1.0  # Prevent division by zero
            
            # Calculate volume/liquidity ratio as buy_sell_ratio proxy
            volume_ratio = (volume / liquidity) if liquidity > 0 else 1.0
            volume_ratio = max(0.1, min(volume_ratio, 10.0))  # Cap between 0.1 and 10
            
            # Pump score formula: volume * ratio / age
            pump_score = (volume * volume_ratio) / age_minutes
            
            return max(0, pump_score)
            
        except Exception as e:
            logger.warning(f"Pump score calculation failed: {e}")
            return 0.0
    
    def _calculate_age_minutes(self, timestamp_str: str) -> float:
        """Calculate age in minutes from timestamp string"""
        try:
            if not timestamp_str:
                return 60.0  # Default 1 hour
            
            # Parse ISO timestamp
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            age_seconds = (datetime.utcnow() - dt.replace(tzinfo=None)).total_seconds()
            age_minutes = age_seconds / 60
            
            return max(1.0, age_minutes)  # Minimum 1 minute
            
        except Exception as e:
            logger.warning(f"Age calculation failed: {e}")
            return 60.0  # Default 1 hour
    
    async def _generate_pump_ai_message(self, candidate: Dict[str, Any]) -> str:
        """Generate Russian AI message for pump candidate"""
        try:
            # Import groq client directly for custom request
            from groq import AsyncGroq
            from app.core.config import get_settings
            
            settings = get_settings()
            client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            
            # Build comprehensive pump analysis prompt
            age_minutes = candidate.get('age_minutes', 0)
            liq_ratio = (candidate['vol5'] / candidate['liq']) if candidate['liq'] > 0 else 0
            vol_growth = (candidate['vol5'] / candidate['vol60']) if candidate['vol60'] > 0 else 0
            whale_data = candidate.get('whales1h', {})
            whale_count = whale_data.get('count', 0)
            whale_inflow = whale_data.get('total_inflow_usd', 0)
            
            prompt = f"""
ГЛУБОКИЙ АНАЛИЗ ПАМПА ТОКЕНА:

БАЗОВЫЕ МЕТРИКИ:
- Токен: {candidate['name']}
- Возраст пула: {age_minutes:.1f} минут
- Ликвидность: ${candidate['liq']:,}
- Объем 5м: ${candidate['vol5']:,} 
- Объем 60м: ${candidate['vol60']:,}
- Рыночная кап: ${candidate['mcap']:,}
- Активность китов: {whale_count} китов / ${whale_inflow:,}
- Итоговая оценка пампа: {candidate['pump_score']:.2f}

РАСЧЕТНЫЕ ИНДИКАТОРЫ:
- Коэффициент объем/ликвидность: {liq_ratio:.3f} ({liq_ratio*100:.1f}%)
- Рост объема (5м/60м): {vol_growth:.2f}x
- Приток китов за час: {whale_count} китов на ${whale_inflow:,}

ЗАДАЧА: Создай ЭКСПЕРТНОЕ сообщение на русском языке (2-3 предложения) для опытных трейдеров.

ПРИМЕРЫ:
"Окно 23м, объем/лик 8.5%: активная накачка. Киты 34% - риск дампа выше 60%. Вход 0.5% стека."
"Поздняя стадия 180м, momentum падает 2.1x→1.3x. Лик $890K хорошая, но upside ограничен."
"Ранний памп 18м: лик/объем 12% перегрев, но киты только 8%. Возможен x2-3 при прорыве."

Ответь ТОЛЬКО русским техническим анализом, БЕЗ объяснений структуры.
            """
            
            # Call Groq directly without JSON format
            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Ты эксперт по анализу криптовалют. Отвечай только на русском языке короткими техническими сообщениями."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            if response and response.choices:
                message = response.choices[0].message.content.strip()
                # Clean response
                message = message.replace('"', '').replace("'", '')
                # Limit length
                if len(message) > 200:
                    message = message[:197] + "..."
                
                return message
            
            # Fallback message
            return self._generate_fallback_message(candidate)
            
        except Exception as e:
            logger.warning(f"AI message generation failed: {e}")
            return self._generate_fallback_message(candidate)

    def _generate_fallback_message(self, candidate: Dict[str, Any]) -> str:
        """Generate fallback Russian message when AI fails"""
        try:
            liq = candidate['liq']
            vol5 = candidate['vol5'] 
            whale_data = candidate.get('whales1h', {})
            whale_count = whale_data.get('count', 0)
            whale_inflow = whale_data.get('total_inflow_usd', 0)
            score = candidate.get('pump_score', 0)
            
            if score > 80:
                if whale_count > 0:
                    return f"Сильный памп: {whale_count} китов +${whale_inflow/1000:.0f}K. Лик ${liq/1000:.0f}K. Следим."
                else:
                    return f"Памп без китов: лик ${liq/1000:.0f}K, объем ${vol5/1000:.0f}K. Осторожно."
            elif score > 60:
                if whale_count > 0:
                    return f"Умеренный рост: {whale_count} китов +${whale_inflow/1000:.0f}K. Вход при подтверждении."
                else:
                    return f"Средний потенциал: объем ${vol5/1000:.0f}K, китов нет."
            else:
                return f"Слабые сигналы: лик ${liq/1000:.0f}K, {whale_count} китов. Ждем импульса."
                
        except Exception:
            return "Анализ завершен, данные обрабатываются."
        
    def _parse_float(self, value) -> float:
        """Safely parse float from string or number"""
        try:
            if value is None or value == "unknown" or value == "":
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0