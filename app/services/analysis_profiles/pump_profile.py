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
            
            # Get recent snapshots from ChromaDB
            snapshots = await self._get_recent_snapshots(limit=200)
            
            if not snapshots:
                return {
                    "candidates": [],
                    "total_found": 0,
                    "message": "No snapshots found for analysis"
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
                    else:
                        # Debug why it failed
                        token_addr = snapshot.get("token_address", "unknown")[:8]
                        liq = self._parse_float(snapshot.get("liquidity", "0"))
                        mcap = self._parse_float(snapshot.get("market_cap", "0"))
                        vol = self._parse_float(snapshot.get("volume_24h", "0"))
                        logger.debug(f"❌ {token_addr} filtered out: liq={liq}, mcap={mcap}, vol={vol}")
                except Exception as e:
                    logger.warning(f"Error analyzing snapshot: {e}")
                    continue
            
            # Sort by pump score (highest first)
            candidates.sort(key=lambda x: x.get("pump_score", 0), reverse=True)
            
            # Add ranks
            for i, candidate in enumerate(candidates[:5]):
                candidate["rank"] = i + 1
            
            # Return top 5
            top_candidates = candidates[:5]
            
            # Store run data only if we have candidates
            if len(candidates) > 0:
                run_data = {
                    "run_id": f"run_{int(time.time())}",
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
            
            return {
                "candidates": top_candidates,
                "total_found": len(candidates),
                "snapshots_analyzed": len(snapshots),
                "run_id": f"filter_{int(time.time())}" if len(candidates) > 0 else None
            }
            
        except Exception as e:
            logger.error(f"Snapshot pump analysis failed: {e}")
            return {
                "candidates": [],
                "total_found": 0,
                "error": str(e),
                "snapshots_analyzed": 0
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
            whale_control = self._parse_float(snapshot.get("whale_control_percent", "0"))
            
            # Calculate age from timestamp
            timestamp_str = snapshot.get("timestamp", "")
            age_minutes = self._calculate_age_minutes(timestamp_str)
            
            # Apply filters
            if not self._passes_filters(liquidity, market_cap, volume_5m, whale_control, age_minutes, filters):
                return None
            
            # Calculate pump score
            pump_score = self._calculate_pump_score(volume_5m, liquidity, age_minutes)
            
            # Extract token info
            token_name = snapshot.get("token_name", "Unknown")
            token_symbol = snapshot.get("token_symbol", "N/A")
            
            return {
                "rank": 0,  # Will be set after sorting
                "name": f"{token_name} ({token_symbol})" if token_symbol != "N/A" else token_name,
                "mint": f"{token_address[:4]}...{token_address[-4:]}",
                "mint_full": token_address,
                "liq": int(liquidity),
                "vol5": int(volume_5m),  # Using 1h as proxy for 5min
                "vol60": int(volume_1h),
                "whales1h": int(whale_control * 100),  # Convert to basis points
                "social": 0,  # Placeholder
                "mcap": int(market_cap),
                "action": "",  # Leave blank for now
                "pump_score": round(pump_score, 2),
                "age_minutes": age_minutes,
                "timestamp": timestamp_str
            }
            
        except Exception as e:
            logger.warning(f"Error analyzing snapshot for {snapshot.get('token_address', 'unknown')}: {e}")
            return None
    
    def _passes_filters(self, liquidity: float, market_cap: float, 
                       volume_5m: float, whale_control: float, age_minutes: float, 
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
                logger.debug(f"Market cap filter failed: {market_cap} not in [{filters.get('volMin')}, {filters.get('volMax')}]")
                return False
            
            # Age filter (filters are already in minutes, no conversion needed)
            time_min_minutes = filters.get("timeMin", 0)  # Already in minutes
            time_max_minutes = filters.get("timeMax", float('inf'))  # Already in minutes
            if age_minutes < time_min_minutes or age_minutes > time_max_minutes:
                logger.debug(f"Age filter failed: {age_minutes} min not in [{time_min_minutes}, {time_max_minutes}] min")
                return False
            
            # Whale filter (convert percentage to basis points)
            whale_bp = whale_control * 100
            if whale_bp < filters.get("whales1hMin", 0):
                logger.debug(f"Whale filter failed: {whale_bp} < {filters.get('whales1hMin')}")
                return False
            
            # Social filter
            social_score = 0  # Not available in snapshots yet
            if social_score < filters.get("socialMin", 0):
                return False
            
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
    
    def _parse_float(self, value) -> float:
        """Safely parse float from string or number"""
        try:
            if value is None or value == "unknown" or value == "":
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0