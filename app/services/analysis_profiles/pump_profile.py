from typing import Dict, Any, Optional, List
from loguru import logger
import statistics
import time

from .base_profile import BaseAnalysisProfile
from app.models.analysis_models import AnalysisRunResponse


class PumpAnalysisProfile(BaseAnalysisProfile):
    """Volume/price spike analysis profile"""
    
    profile_name = "Pump Detection"
    analysis_type = "pump"
    required_services = ["dexscreener", "goplus", "rugcheck"]
    ai_focus_areas = ["pump_indicators", "volume_analysis", "momentum_metrics"]
    
    async def analyze(self, token_address: str, filters: Optional[Dict] = None, **kwargs) -> AnalysisRunResponse:
        """Analyze token for pump/spike patterns"""
        self.start_time = time.time()
        
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
    
    def _detect_pump_signals(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect pump/spike indicators from market data"""
        pump_data = {
            "volume_spike_percent": 0.0,
            "price_momentum": 0.0,
            "pump_probability": 0.0,
            "sustainability_score": 50.0,
            "warnings": [],
            "unsustainable_pump": False
        }
        
        # Analyze Birdeye data
        birdeye_data = service_data.get("birdeye", {})
        if birdeye_data:
            # Volume analysis
            price_data = birdeye_data.get("price", {})
            if price_data:
                volume_24h = price_data.get("volume_24h")
                price_change_24h = price_data.get("price_change_24h")
                
                if volume_24h and price_change_24h:
                    # Detect volume spikes
                    volume_val = float(volume_24h)
                    if volume_val > 1000000:  # High volume
                        pump_data["volume_spike_percent"] = min(100, (volume_val / 1000000) * 50)
                    
                    # Price momentum
                    price_change = float(price_change_24h)
                    if abs(price_change) > 20:
                        pump_data["price_momentum"] = min(100, abs(price_change) * 2)
                        if price_change > 50:
                            pump_data["warnings"].append(f"Extreme price spike: +{price_change:.1f}%")
                            pump_data["unsustainable_pump"] = price_change > 100
            
            # Trade pattern analysis
            trades_data = birdeye_data.get("trades")
            if trades_data and isinstance(trades_data, list):
                pump_data.update(self._analyze_trade_patterns(trades_data))
        
        # Calculate pump probability
        volume_factor = pump_data["volume_spike_percent"] / 100
        momentum_factor = pump_data["price_momentum"] / 100
        pump_data["pump_probability"] = round((volume_factor * 0.6 + momentum_factor * 0.4) * 100, 1)
        
        # Sustainability assessment
        if pump_data["pump_probability"] > 80:
            pump_data["sustainability_score"] = 20.0
            pump_data["warnings"].append("High pump probability - unsustainable")
        elif pump_data["pump_probability"] > 60:
            pump_data["sustainability_score"] = 40.0
            pump_data["warnings"].append("Moderate pump detected")
        
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
        """Calculate score focusing on pump indicators"""
        pump_analysis = service_data.get("pump_analysis", {})
        
        # Base score from pump probability
        pump_prob = pump_analysis.get("pump_probability", 0)
        sustainability = pump_analysis.get("sustainability_score", 50)
        
        # Score based on pump characteristics
        if pump_prob > 70:
            base_score = 30.0  # High pump = lower score (risky)
        elif pump_prob > 40:
            base_score = 50.0  # Moderate pump
        else:
            base_score = 70.0  # No pump = higher score (stable)
        
        # Adjust for sustainability
        base_score = (base_score + sustainability) / 2
        
        # AI enhancement
        if ai_data and ai_data.get("ai_score"):
            ai_score = float(ai_data["ai_score"])
            base_score = (base_score * 0.7) + (ai_score * 0.3)  # 70/30 blend
        
        return round(base_score, 1)
    
    def _determine_pump_risk(self, service_data: Dict[str, Any], ai_data: Optional[Dict[str, Any]]) -> str:
        """Determine risk level based on pump indicators"""
        pump_analysis = service_data.get("pump_analysis", {})
        pump_prob = pump_analysis.get("pump_probability", 0)
        
        if pump_analysis.get("unsustainable_pump"):
            return "critical"
        elif pump_prob > 80:
            return "high"
        elif pump_prob > 50:
            return "medium"
        else:
            return "low"
    
    async def build_ai_prompt(self, token_address: str, service_data: Dict[str, Any]) -> str:
        """Build pump-focused AI prompt with safe formatting"""
        pump_data = service_data.get("pump_analysis", {})
        price_data = service_data.get("birdeye", {}).get("price", {}) if service_data.get("birdeye") else {}
        
        # Safe value extraction with defaults
        volume_spike = pump_data.get('volume_spike_percent', 0) or 0
        price_momentum = pump_data.get('price_momentum', 0) or 0
        pump_probability = pump_data.get('pump_probability', 0) or 0
        sustainability = pump_data.get('sustainability_score', 50) or 50
        
        price_value = price_data.get('value', 0) or 0
        volume_24h = price_data.get('volume_24h', 0) or 0
        price_change_24h = price_data.get('price_change_24h', 0) or 0
        
        prompt = f"""
    PUMP DETECTION ANALYSIS for {token_address}

    PUMP INDICATORS:
    - Volume Spike: {volume_spike:.1f}%
    - Price Momentum: {price_momentum:.1f}%
    - Pump Probability: {pump_probability:.1f}%
    - Sustainability Score: {sustainability:.1f}

    MARKET DATA:
    - Price: ${price_value:.8f}
    - 24h Volume: ${volume_24h:,.0f}
    - 24h Change: {price_change_24h:+.2f}%

    Focus on pump detection and momentum analysis. Assess if this is a sustainable move or artificial pump.

    Respond ONLY with JSON matching this structure:
    {{
    "pump_score": 0-100,
    "sustainability": "low|medium|high",
    "momentum_strength": "weak|moderate|strong",
    "recommendation": "BUY|CONSIDER|HOLD|CAUTION|AVOID",
    "key_insights": ["list of pump insights"],
    "pump_risks": ["list of pump risks"]
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