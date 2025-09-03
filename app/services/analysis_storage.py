import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from app.utils.chroma_client import get_chroma_client
from app.core.config import get_settings

settings = get_settings()


class AnalysisStorageService:
    """Service for storing and retrieving token analysis results in ChromaDB"""
    
    def __init__(self):
        self.collection_name = "token_analyses"
    
    async def store_analysis(self, analysis_result: Dict[str, Any]) -> bool:
        """
        Store analysis result in ChromaDB (non-blocking)
        
        Args:
            analysis_result: Full analysis result from token_analyzer
            
        Returns:
            bool: True if stored successfully, False otherwise
        """
        try:
            # Get ChromaDB client
            chroma_client = await get_chroma_client()
            if not chroma_client.is_connected():
                logger.debug("ChromaDB not available, skipping analysis storage")
                return False
            
            # Extract and structure data for storage
            doc_data = self._extract_analysis_data(analysis_result)
            if not doc_data:
                logger.warning("Could not extract analysis data for storage")
                return False
            
            # Generate document content (for vector search)
            content = self._generate_searchable_content(doc_data)
            
            # Generate metadata (for filtering)
            metadata = self._generate_metadata(doc_data)
            
            # Store in ChromaDB
            doc_id = f"analysis_{doc_data['timestamp_unix']}_{doc_data['token_address'][:8]}"
            
            await chroma_client.add_document(
                content=content,
                metadata=metadata,
                doc_id=doc_id
            )
            
            logger.info(f"✅ Analysis stored in ChromaDB: {doc_id}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to store analysis in ChromaDB: {str(e)}")
            return False
    
    def _extract_token_name(self, analysis_result: Dict[str, Any]) -> str:
        """Extract token name from analysis result"""
        # Try Solsniffer info first
        solsniffer_name = (analysis_result
                        .get("service_responses", {})
                        .get("solsniffer", {})
                        .get("tokenName"))
        if solsniffer_name:
            return solsniffer_name

        # Try Helius metadata
        helius_name = (analysis_result
                      .get("service_responses", {})
                      .get("helius", {})
                      .get("metadata", {})
                      .get("onChainMetadata", {})
                      .get("metadata", {})
                      .get("data", {})
                      .get("name"))
        if helius_name:
            return helius_name
            
        # Try SolanaFM
        solanafm_name = (analysis_result
                        .get("service_responses", {})
                        .get("solanafm", {})
                        .get("token", {})
                        .get("name"))
        if solanafm_name:
            return solanafm_name
            
        return "Unknown Token"
    
    def _extract_token_symbol(self, analysis_result: Dict[str, Any]) -> str:
        """Extract token symbol from analysis result"""
        # Try Solsniffer info first
        solsniffer_symbol = (analysis_result
                        .get("service_responses", {})
                        .get("solsniffer", {})
                        .get("tokenSymbol"))
        if solsniffer_symbol:
            return solsniffer_symbol
        
        # Try Helius metadata
        helius_symbol = (analysis_result
                        .get("service_responses", {})
                        .get("helius", {})
                        .get("metadata", {})
                        .get("onChainMetadata", {})
                        .get("metadata", {})
                        .get("data", {})
                        .get("symbol"))
        if helius_symbol:
            return helius_symbol
            
        # Try SolanaFM
        solanafm_symbol = (analysis_result
                          .get("service_responses", {})
                          .get("solanafm", {})
                          .get("token", {})
                          .get("symbol"))
        if solanafm_symbol:
            return solanafm_symbol
            
        return "N/A"
    
    def _extract_market_data(self, analysis_result: Dict[str, Any]) -> Dict[str, float]:
        """Extract market data with fallback for volume and market cap only"""
        market_data = {
            "price_usd": 0.0,
            "price_change_24h": 0.0,
            "volume_24h": 0.0,
            "market_cap": 0.0,
            "liquidity": 0.0
        }
        
        try:
            service_responses = analysis_result.get("service_responses", {})
            
            # Primary source: Birdeye
            birdeye_data = service_responses.get("birdeye", {})
            
            if birdeye_data and birdeye_data.get("price"):
                birdeye_price = birdeye_data["price"]
                
                # Direct assignment with None checks (no conversion yet)
                if birdeye_price.get("value") is not None:
                    market_data["price_usd"] = birdeye_price["value"]
                
                if birdeye_price.get("price_change_24h") is not None:
                    market_data["price_change_24h"] = birdeye_price["price_change_24h"]
                
                if birdeye_price.get("volume_24h") is not None:
                    market_data["volume_24h"] = birdeye_price["volume_24h"]
                
                if birdeye_price.get("market_cap") is not None:
                    market_data["market_cap"] = birdeye_price["market_cap"]
                
                if birdeye_price.get("liquidity") is not None:
                    market_data["liquidity"] = birdeye_price["liquidity"]
            
            # Fallback for volume: DexScreener (only if volume is still 0.0 or None)
            if market_data["volume_24h"] in (0.0, None):
                dexscreener_data = service_responses.get("dexscreener", {})
                if dexscreener_data and dexscreener_data.get("pairs").get("pairs"):
                    pairs = dexscreener_data["pairs"]["pairs"]
                    if pairs and len(pairs) > 0:
                        pair = pairs[0]
                        volume_24h = pair.get("volume", {}).get("h24")
                        if volume_24h is not None and volume_24h != 0:
                            market_data["volume_24h"] = volume_24h
            
            # Fallback for market cap: Solsniffer, then DexScreener (only if market_cap is still 0.0 or None)
            if market_data["market_cap"] in (0.0, None):
                # Try Solsniffer first
                solsniffer_mc = service_responses.get("solsniffer", {}).get("marketCap")
                if solsniffer_mc is not None and solsniffer_mc != 0:
                    market_data["market_cap"] = solsniffer_mc
                else:
                    # Fallback to DexScreener
                    dexscreener_data = service_responses.get("dexscreener", {})
                    if dexscreener_data and dexscreener_data.get("pairs").get("pairs"):
                        pairs = dexscreener_data["pairs"]["pairs"]
                        if pairs and len(pairs) > 0:
                            pair = pairs[0]
                            market_cap = pair.get("marketCap")
                            if market_cap is not None and market_cap != 0:
                                market_data["market_cap"] = market_cap
            
            # Ensure all values are float at the end
            for key in market_data:
                if market_data[key] is None:
                    market_data[key] = 0.0
                elif not isinstance(market_data[key], (int, float)):
                    try:
                        market_data[key] = float(market_data[key])
                    except (ValueError, TypeError):
                        market_data[key] = 0.0
            
            return market_data
            
        except Exception as e:
            logger.warning(f"Error extracting market data: {e}")
            return market_data
    
    def _calculate_security_score(self, security_analysis: Dict[str, Any]) -> int:
        """Calculate a simple security score from security analysis"""
        if not security_analysis:
            return 0
            
        # Start with base score
        score = 100
        
        # Deduct for critical issues
        critical_count = len(security_analysis.get("critical_issues", []))
        score -= critical_count * 40
        
        # Deduct for warnings
        warning_count = len(security_analysis.get("warnings", []))
        score -= warning_count * 10
        
        return max(0, min(100, score))
    
    def _get_security_sources(self, security_analysis: Dict[str, Any]) -> List[str]:
        """Get list of security data sources used"""
        sources = []
        if security_analysis.get("goplus_result"):
            sources.append("goplus")
        if security_analysis.get("rugcheck_result"):
            sources.append("rugcheck")
        if security_analysis.get("solsniffer_result"):
            sources.append("solsniffer")
        return sources

    def _generate_searchable_content(self, doc_data: Dict[str, Any]) -> str:
        """Generate comprehensive searchable content for vector search"""
        try:
            content_parts = []
            
            # Token information
            token_info = doc_data.get("token_info", {})
            if token_info.get("name") != "Unknown Token":
                content_parts.append(f"Token: {token_info['name']} ({token_info['symbol']})")
            
            # Analysis type and AI enhancement
            analysis_type = doc_data.get("analysis_type", "quick")
            ai_analysis = doc_data.get("ai_analysis")
            if ai_analysis and ai_analysis.get("available"):
                content_parts.append(f"AI-Enhanced {analysis_type} analysis using {ai_analysis.get('model_used', 'Llama 3.0')}")
            else:
                content_parts.append(f"Traditional {analysis_type} analysis")
            
            # Analysis results
            analysis_results = doc_data.get("analysis_results", {})
            security_analysis = doc_data.get("security_analysis", {})
            content_parts.append(f"Security status: {security_analysis.get('security_summary', 'unknown')}")
            content_parts.append(f"Risk level: {analysis_results.get('risk_level', 'unknown')}")
            content_parts.append(f"Recommendation: {analysis_results.get('recommendation', 'HOLD')}")
            content_parts.append(f"Overall score: {analysis_results.get('overall_score', 0)}")
            
            # AI-specific information
            if ai_analysis and ai_analysis.get("available"):
                content_parts.append(f"AI analysis score: {ai_analysis.get('ai_score', 0)}")
                content_parts.append(f"AI recommendation: {ai_analysis.get('recommendation', 'unknown')}")
                
                # AI insights
                key_insights = ai_analysis.get("key_insights", [])
                if key_insights:
                    content_parts.append(f"AI insights: {'; '.join(key_insights[:3])}")
                
                # AI stop flags
                stop_flags = ai_analysis.get("stop_flags", [])
                if stop_flags:
                    content_parts.append(f"AI identified {len(stop_flags)} stop flags")
            
            # Market metrics
            metrics = doc_data.get("metrics", {})
            if metrics.get("price_usd"):
                content_parts.append(f"Price: ${metrics['price_usd']:.8f}")
            if metrics.get("market_cap"):
                content_parts.append(f"Market cap: ${metrics['market_cap']:,.0f}")
            if metrics.get("volume_24h"):
                volume_desc = "high" if metrics["volume_24h"] >= 100000 else "moderate" if metrics["volume_24h"] >= 10000 else "low"
                content_parts.append(f"{volume_desc} trading volume: ${metrics['volume_24h']:,.0f}")
            if metrics.get("liquidity"):
                liq_desc = "excellent" if metrics["liquidity"] >= 500000 else "good" if metrics["liquidity"] >= 100000 else "moderate"
                content_parts.append(f"{liq_desc} liquidity: ${metrics['liquidity']:,.0f}")
            
            # Enhanced metrics
            whale_analysis = metrics.get("whale_analysis", {})
            if whale_analysis.get("whale_count") is not None:
                whale_count = whale_analysis["whale_count"]
                if whale_count == 0:
                    content_parts.append("Perfect token distribution - no whales")
                else:
                    control_pct = whale_analysis.get("whale_control_percent", 0)
                    content_parts.append(f"Whale analysis: {whale_count} whales control {control_pct}%")
            
            volatility = metrics.get("volatility", {})
            if volatility.get("recent_volatility_percent") is not None:
                vol_pct = volatility["recent_volatility_percent"]
                vol_desc = "low" if vol_pct <= 15 else "moderate" if vol_pct <= 30 else "high"
                content_parts.append(f"{vol_desc} volatility: {vol_pct}%")
            
            sniper_detection = metrics.get("sniper_detection", {})
            if sniper_detection.get("pattern_detected"):
                content_parts.append(f"Sniper patterns detected: {sniper_detection.get('similar_holders', 0)} similar holders")
            
            # Security details
            critical_count = len(security_analysis.get("critical_issues", []))
            warning_count = len(security_analysis.get("warnings", []))
            if critical_count > 0:
                content_parts.append(f"Has {critical_count} critical security issues")
            if warning_count > 0:
                content_parts.append(f"Has {warning_count} security warnings")
            
            # Analysis summary and reasoning (ALWAYS AVAILABLE)
            summary = analysis_results.get("summary", "")
            if summary:
                content_parts.append(f"Summary: {summary}")
            
            reasoning = analysis_results.get("reasoning", "")
            if reasoning and len(reasoning) > 20:
                content_parts.append(f"Analysis reasoning: {reasoning[:200]}...")
            
            # Data sources
            data_sources_count = doc_data.get("metadata", {}).get("data_sources_count", 0)
            content_parts.append(f"Data from {data_sources_count} sources")
            
            # Analysis performance
            processing_time = doc_data.get("metadata", {}).get("processing_time_seconds", 0)
            ai_processing_time = doc_data.get("metadata", {}).get("ai_processing_time", 0)
            if ai_processing_time > 0:
                content_parts.append(f"Processing time: {processing_time:.2f}s total ({ai_processing_time:.2f}s AI)")
            else:
                content_parts.append(f"Processing time: {processing_time:.2f}s")
            
            # Timestamp
            dt = datetime.fromtimestamp(doc_data['timestamp_unix'])
            content_parts.append(f"Analyzed on: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            
            return ". ".join(content_parts) + "."
            
        except Exception as e:
            logger.warning(f"Error generating comprehensive searchable content: {e}")
            return f"Token analysis for {doc_data.get('token_address', 'unknown')} completed."
        
    def _extract_analysis_data(self, analysis_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract comprehensive data from analysis result for enhanced storage"""
        try:
            # Parse timestamp
            timestamp = analysis_result.get("timestamp")
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp_unix = int(dt.timestamp())
            else:
                dt = datetime.utcnow()
                timestamp_unix = int(dt.timestamp())
            
            # === BASIC INFO ===
            analysis_type = analysis_result.get("analysis_type", "quick")
            is_deep_analysis = analysis_type == "deep"
            
            # === TOKEN INFO ===
            token_info = self._extract_token_info(analysis_result)
            
            # === COMPREHENSIVE METRICS (merged market_data + enhanced_metrics) ===
            metrics = self._extract_comprehensive_metrics(analysis_result)
            
            # === SECURITY ANALYSIS ===
            security_analysis_enhanced = self._extract_comprehensive_security(analysis_result)
            
            # === AI ANALYSIS (null for quick analysis) ===
            ai_analysis = None
            if is_deep_analysis:
                ai_analysis = self._extract_ai_analysis(analysis_result)
            
            # === ANALYSIS RESULTS (always available with summary/reasoning) ===
            analysis_results = self._extract_analysis_results(analysis_result, is_deep_analysis)
            
            # === METADATA ===
            metadata_enhanced = self._extract_analysis_metadata(analysis_result)
            
            # Compile comprehensive data structure
            comprehensive_data = {
                # === EXISTING FIELDS (keep for compatibility) ===
                "analysis_id": analysis_result.get("analysis_id"),
                "token_address": analysis_result.get("token_address"),
                "timestamp": timestamp or dt.isoformat(),
                "timestamp_unix": timestamp_unix,
                "source_event": analysis_result.get("source_event", "unknown"),
                "analysis_type": analysis_type,
                
                # === LEGACY FIELDS (for backward compatibility) ===
                "token_name": token_info.get("name", "Unknown Token"),
                "token_symbol": token_info.get("symbol", "N/A"),
                "overall_score": float(analysis_results.get("overall_score", 0)),
                "risk_level": analysis_results.get("risk_level", "unknown"),
                "recommendation": analysis_results.get("recommendation", "HOLD"),
                "confidence_score": float(analysis_results.get("confidence_score", 0)),
                "security_status": "safe" if security_analysis_enhanced.get("overall_safe") else "unsafe",
                "critical_issues_count": len(security_analysis_enhanced.get("critical_issues", [])),
                "warnings_count": len(security_analysis_enhanced.get("warnings", [])),
                "processing_time": float(metadata_enhanced.get("processing_time_seconds", 0.0)),
                
                # === NEW COMPREHENSIVE STRUCTURE ===
                "token_info": token_info,
                "metrics": metrics,  # Merged market_data + enhanced_metrics
                "security_analysis": security_analysis_enhanced,
                "ai_analysis": ai_analysis,  # null for quick analysis
                "analysis_results": analysis_results,  # Always has summary/reasoning
                "metadata": metadata_enhanced,
                
                # === ADDITIONAL FIELDS FOR COMPATIBILITY ===
                "price_usd": float(metrics.get("price_usd") or 0),
                "price_change_24h": float(metrics.get("price_change_24h") or 0),
                "volume_24h": float(metrics.get("volume_24h") or 0),
                "market_cap": float(metrics.get("market_cap") or 0),
                "liquidity": float(metrics.get("liquidity") or 0),
                "security_score": security_analysis_enhanced.get("security_score", 0),
                "data_sources": analysis_result.get("data_sources", []),
                "services_attempted": metadata_enhanced.get("services_attempted", 0),
                "services_successful": metadata_enhanced.get("services_successful", 0),
                "analysis_stopped_at_security": metadata_enhanced.get("analysis_stopped_at_security", False),
                "has_ai_analysis": bool(ai_analysis and ai_analysis.get("available")),
                "ai_score": float(ai_analysis.get("ai_score", 0)) if ai_analysis else 0,
                "ai_recommendation": ai_analysis.get("recommendation") if ai_analysis else None,
                "ai_stop_flags_count": len(ai_analysis.get("stop_flags", [])) if ai_analysis else 0,
                
                # === FULL RESULT (for complex queries) ===
                "full_analysis_json": json.dumps(analysis_result, default=str)
            }
            
            return comprehensive_data
            
        except Exception as e:
            logger.error(f"Error extracting comprehensive analysis data: {str(e)}")
            return None
    
    def _extract_token_info(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive token metadata"""
        try:
            service_responses = analysis_result.get("service_responses", {})
            
            # Use existing methods but enhance with more fields
            token_name = self._extract_token_name(analysis_result)
            token_symbol = self._extract_token_symbol(analysis_result)
            
            # Extract total supply
            total_supply = None
            helius_supply = service_responses.get("helius", {}).get("supply", {})
            if helius_supply and helius_supply.get("ui_amount"):
                try:
                    total_supply = float(helius_supply["ui_amount"])
                except (ValueError, TypeError):
                    pass
            
            # Extract dev holdings
            dev_holdings_percent = None
            rugcheck_data = service_responses.get("rugcheck", {})
            if rugcheck_data and rugcheck_data.get("creator_analysis") and total_supply:
                try:
                    creator_balance = float(rugcheck_data["creator_analysis"].get("creator_balance") or 0)
                    if creator_balance > 0:
                        dev_holdings_percent = (creator_balance / total_supply) * 100
                except (ValueError, TypeError):
                    pass
            
            # Extract holder count
            holder_count = None
            goplus_data = service_responses.get("goplus", {})
            if goplus_data:
                holder_fields = ["holder_count", "holders_count", "holderCount", "totalHolders"]
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
                                break
                        except Exception:
                            continue
            
            return {
                "name": token_name,
                "symbol": token_symbol,
                "total_supply": total_supply,
                "dev_holdings_percent": dev_holdings_percent,
                "holder_count": holder_count,
                "metadata_completeness": bool(token_name != "Unknown Token" and token_symbol != "N/A")
            }
            
        except Exception as e:
            logger.warning(f"Error extracting enhanced token info: {e}")
            return {
                "name": "Unknown Token",
                "symbol": "N/A",
                "total_supply": None,
                "dev_holdings_percent": None,
                "holder_count": None,
                "metadata_completeness": False
            }
        
    
    def _extract_comprehensive_metrics(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive market and enhanced metrics"""
        try:
            service_responses = analysis_result.get("service_responses", {})
            overall_analysis = analysis_result.get("overall_analysis", {})
            
            # === MARKET FUNDAMENTALS ===
            # Use existing price data extraction but enhance it
            price_data = self._extract_market_data(analysis_result)
            
            # Calculate volume/liquidity ratio
            volume_liquidity_ratio = None
            if price_data.get("volume_24h") and price_data.get("liquidity"):
                if price_data["volume_24h"] > 0 and price_data["liquidity"] > 0:
                    volume_liquidity_ratio = (price_data["volume_24h"] / price_data["liquidity"]) * 100
            
            # Data completeness
            market_metrics = [
                price_data.get("price_usd"),
                price_data.get("price_change_24h"), 
                price_data.get("volume_24h"),
                price_data.get("market_cap"),
                price_data.get("liquidity")
            ]
            data_completeness_percent = (sum(1 for m in market_metrics if m is not None) / len(market_metrics)) * 100
            
            # === ENHANCED METRICS ===
            volatility_data = self._extract_volatility_data(overall_analysis)
            whale_data = self._extract_whale_data(overall_analysis)
            sniper_data = self._extract_sniper_data(overall_analysis)
            
            return {
                # Market fundamentals
                "price_usd": price_data.get("price_usd"),
                "price_change_24h": price_data.get("price_change_24h"),
                "volume_24h": price_data.get("volume_24h"),
                "market_cap": price_data.get("market_cap"),
                "liquidity": price_data.get("liquidity"),
                "volume_liquidity_ratio": volume_liquidity_ratio,
                "data_completeness_percent": round(data_completeness_percent, 1),
                
                # Enhanced metrics
                "volatility": volatility_data,
                "whale_analysis": whale_data,
                "sniper_detection": sniper_data
            }
            
        except Exception as e:
            logger.warning(f"Error extracting comprehensive metrics: {e}")
            return self._get_empty_metrics()
        
    def _extract_volatility_data(self, overall_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract volatility analysis data"""
        volatility_analysis = overall_analysis.get("volatility", {})
        if volatility_analysis:
            return {
                "recent_volatility_percent": volatility_analysis.get("recent_volatility_percent"),
                "volatility_risk": volatility_analysis.get("volatility_risk", "unknown"),
                "trades_analyzed": volatility_analysis.get("trades_analyzed", 0)
            }
        return {
            "recent_volatility_percent": None,
            "volatility_risk": "unknown",
            "trades_analyzed": 0
        }

    def _extract_whale_data(self, overall_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract whale analysis data"""
        whale_analysis = overall_analysis.get("whale_analysis", {})
        if whale_analysis:
            return {
                "whale_count": whale_analysis.get("whale_count", 0),
                "whale_control_percent": whale_analysis.get("whale_control_percent", 0.0),
                "top_whale_percent": whale_analysis.get("top_whale_percent", 0.0),
                "whale_risk_level": whale_analysis.get("whale_risk_level", "unknown"),
                "distribution_quality": self._assess_distribution_quality(whale_analysis)
            }
        return {
            "whale_count": 0,
            "whale_control_percent": 0.0,
            "top_whale_percent": 0.0,
            "whale_risk_level": "unknown",
            "distribution_quality": "unknown"
        }

    def _extract_sniper_data(self, overall_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract sniper detection data"""
        sniper_detection = overall_analysis.get("sniper_detection", {})
        if sniper_detection:
            return {
                "similar_holders": sniper_detection.get("similar_holders", 0),
                "pattern_detected": sniper_detection.get("pattern_detected", False),
                "sniper_risk": sniper_detection.get("sniper_risk", "unknown"),
                "bot_likelihood": self._assess_bot_likelihood(sniper_detection)
            }
        return {
            "similar_holders": 0,
            "pattern_detected": False,
            "sniper_risk": "unknown",
            "bot_likelihood": "unknown"
        }

    def _generate_metadata(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive metadata for filtering and exact searches"""
        try:
            dt = datetime.fromtimestamp(doc_data['timestamp_unix'])
            token_info = doc_data.get("token_info", {})
            metrics = doc_data.get("metrics", {})
            security_analysis = doc_data.get("security_analysis", {})
            ai_analysis = doc_data.get("ai_analysis")
            analysis_results = doc_data.get("analysis_results", {})
            metadata = doc_data.get("metadata", {})
            
            return {
                # === CORE IDENTIFIERS ===
                "doc_type": "token_analysis",
                "analysis_id": doc_data.get("analysis_id") or "unknown",
                "token_address": doc_data.get("token_address") or "unknown",
                "token_name": token_info.get("name") or "unknown",
                "token_symbol": token_info.get("symbol") or "unknown",
                
                # === ANALYSIS RESULTS ===
                "security_status": "safe" if security_analysis.get("overall_safe") else "unsafe",
                "risk_level": analysis_results.get("risk_level") or "unknown",
                "recommendation": analysis_results.get("recommendation") or "HOLD",
                "analysis_stopped_at_security": bool(metadata.get("analysis_stopped_at_security", False)),
                "analysis_type": doc_data.get("analysis_type") or "quick",
                
                # === SCORES ===
                "overall_score": float(analysis_results.get("overall_score") or 0),
                "security_score": int(security_analysis.get("security_score") or 0),
                "confidence_score": float(analysis_results.get("confidence_score") or 0),
                "ai_score": float(ai_analysis.get("ai_score") or 0) if ai_analysis else 0.0,
                
                # === MARKET DATA VALUES ===
                "price_usd": float(metrics.get("price_usd") or 0.0),
                "price_change_24h": float(metrics.get("price_change_24h") or 0.0),
                "volume_24h": float(metrics.get("volume_24h") or 0.0),
                "market_cap": float(metrics.get("market_cap") or 0.0),
                "liquidity": float(metrics.get("liquidity") or 0.0),
                "volume_liquidity_ratio": float(metrics.get("volume_liquidity_ratio") or 0.0),
                
                # === RISK METRICS ===
                "volatility_risk": metrics.get("volatility", {}).get("volatility_risk") or "unknown",
                "whale_risk": metrics.get("whale_analysis", {}).get("whale_risk_level") or "unknown",
                "sniper_risk": metrics.get("sniper_detection", {}).get("sniper_risk") or "unknown",
                "whale_count": int(metrics.get("whale_analysis", {}).get("whale_count") or 0),
                "whale_control_percent": float(metrics.get("whale_analysis", {}).get("whale_control_percent") or 0),
                
                # === SECURITY FLAGS ===
                "critical_issues_count": len(security_analysis.get("critical_issues") or []),
                "warnings_count": len(security_analysis.get("warnings") or []),
                "critical_issues_list": json.dumps(security_analysis.get("critical_issues") or []),
                "warnings_list": json.dumps(security_analysis.get("warnings") or []),
                "mint_authority_active": bool(security_analysis.get("authority_risks", {}).get("mint_authority_active", False)),
                "freeze_authority_active": bool(security_analysis.get("authority_risks", {}).get("freeze_authority_active", False)),
                "lp_status": security_analysis.get("lp_security", {}).get("status") or "unknown",
                
                # === AI ANALYSIS FLAGS ===
                "has_ai_analysis": bool(ai_analysis and ai_analysis.get("available")),
                "ai_risk_assessment": ai_analysis.get("risk_assessment") or "unknown" if ai_analysis else "unknown",
                "ai_stop_flags_count": len(ai_analysis.get("stop_flags") or []) if ai_analysis else 0,
                
                # === TOKEN METADATA ===
                "holder_count": int(token_info.get("holder_count") or 0),
                "dev_holdings_percent": float(token_info.get("dev_holdings_percent") or 0),
                "total_supply": float(token_info.get("total_supply") or 0),
                
                # === TIME-BASED FILTERING ===
                "analysis_date": dt.strftime("%Y-%m-%d"),
                "analysis_year": str(dt.year),
                "analysis_month": dt.strftime("%Y-%m"),
                "timestamp_unix": int(doc_data["timestamp_unix"]),
                
                # === SOURCE AND PERFORMANCE ===
                "source_event": doc_data.get("source_event") or "unknown",
                "processing_time": float(metadata.get("processing_time_seconds") or 0),
                "ai_processing_time": float(metadata.get("ai_processing_time") or 0),
                "services_successful": int(metadata.get("services_successful") or 0),
                "data_completeness": float(metrics.get("data_completeness_percent") or 0),
                
                # === SECURITY SOURCES ===
                "has_goplus": "goplus" in (security_analysis.get("security_sources") or []),
                "has_rugcheck": "rugcheck" in (security_analysis.get("security_sources") or []),
                "has_solsniffer": "solsniffer" in (security_analysis.get("security_sources") or [])
            }
            
        except Exception as e:
            logger.warning(f"Error generating metadata: {e}")
            return {
                "doc_type": "token_analysis", 
                "error": "metadata_extraction_failed",
                "token_address": doc_data.get("token_address") or "unknown",
                "analysis_type": doc_data.get("analysis_type") or "quick",
                "timestamp_unix": int(doc_data.get("timestamp_unix") or 0)
            }
    
    def _extract_comprehensive_security(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive security analysis"""
        try:
            security_analysis = analysis_result.get("security_analysis", {})
            service_responses = analysis_result.get("service_responses", {})
            
            # Basic security status
            overall_safe = security_analysis.get("overall_safe", False)
            critical_issues = security_analysis.get("critical_issues", [])
            warnings = security_analysis.get("warnings", [])
            
            # Calculate security score (enhanced version)
            security_score = self._calculate_comprehensive_security_score(security_analysis, analysis_result)
            
            # Authority risks from GOplus
            authority_risks = self._extract_authority_risks(service_responses.get("goplus", {}))
            
            # LP security analysis
            lp_security = self._extract_lp_security(service_responses.get("rugcheck", {}))
            
            # Security sources (reuse existing method)
            security_sources = self._get_security_sources(security_analysis)
            
            # Security summary
            security_summary = self._generate_security_summary(overall_safe, critical_issues, warnings)
            
            return {
                "overall_safe": overall_safe,
                "security_score": security_score,
                "critical_issues": critical_issues,
                "warnings": warnings,
                "authority_risks": authority_risks,
                "lp_security": lp_security,
                "security_sources": security_sources,
                "security_summary": security_summary
            }
            
        except Exception as e:
            logger.warning(f"Error extracting comprehensive security analysis: {e}")
            return self._get_empty_security()
        
    def _extract_authority_risks(self, goplus_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract authority risks from GOplus data"""
        mintable = goplus_data.get("mintable", {})
        freezable = goplus_data.get("freezable", {})
        balance_mutable = goplus_data.get("balance_mutable_authority", {})
        
        return {
            "mint_authority_active": isinstance(mintable, dict) and mintable.get("status") == "1",
            "freeze_authority_active": isinstance(freezable, dict) and freezable.get("status") == "1",
            "balance_mutable": isinstance(balance_mutable, dict) and balance_mutable.get("status") == "1"
        }

    def _extract_lp_security(self, rugcheck_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract LP security analysis from RugCheck data"""
        try:
            # Check for locked liquidity
            lockers_data = rugcheck_data.get("lockers_data", {})
            locked_value_usd = 0.0
            lp_status = "unknown"
            confidence = 0
            evidence = []
            
            if lockers_data and lockers_data.get("lockers"):
                lockers = lockers_data.get("lockers", {})
                if isinstance(lockers, dict):
                    for locker_id, locker_info in lockers.items():
                        if isinstance(locker_info, dict):
                            usd_locked = locker_info.get("usdcLocked", 0)
                            if isinstance(usd_locked, (int, float)) and usd_locked > 0:
                                locked_value_usd += usd_locked
                    
                    if locked_value_usd > 1000:
                        lp_status = "locked"
                        confidence = 90
                        evidence.append(f"${locked_value_usd:,.0f} locked in Raydium lockers")
            
            # Check for burn patterns if not locked
            if lp_status == "unknown":
                markets = rugcheck_data.get("market_analysis", {}).get("markets", [])
                for market in markets:
                    if isinstance(market, dict) and market.get("lp"):
                        holders = market["lp"].get("holders", [])
                        for holder in holders:
                            if isinstance(holder, dict):
                                owner = str(holder.get("owner", ""))
                                pct = holder.get("pct", 0)
                                
                                burn_patterns = ["111111", "dead", "burn", "lock"]
                                if any(pattern in owner.lower() for pattern in burn_patterns) and pct > 50:
                                    lp_status = "burned"
                                    confidence = 85
                                    evidence.append(f"{pct:.1f}% in burn address")
                                    break
            
            return {
                "status": lp_status,
                "confidence": confidence,
                "evidence": evidence,
                "locked_value_usd": locked_value_usd
            }
            
        except Exception as e:
            logger.warning(f"Error extracting LP security: {e}")
            return {
                "status": "unknown",
                "confidence": 0,
                "evidence": [],
                "locked_value_usd": 0.0
            }

    def _calculate_comprehensive_security_score(self, security_analysis: Dict[str, Any], analysis_result: Dict[str, Any]) -> int:
        """Calculate comprehensive security score"""
        try:
            # Start with base score
            score = 100
            
            # Critical penalty for stopped analysis
            if analysis_result.get("metadata", {}).get("analysis_stopped_at_security"):
                return max(5, 20 - len(security_analysis.get("critical_issues") or []) * 5)
            
            # Deduct for critical issues
            critical_count = len(security_analysis.get("critical_issues") or [])
            score -= critical_count * 30
            
            # Deduct for warnings (graduated)
            warning_count = len(security_analysis.get("warnings") or [])
            for i in range(warning_count):
                score -= (10 + i * 5)  # 10, 15, 20, 25...
            
            # Bonus for multiple security sources
            sources_count = len(self._get_security_sources(security_analysis))
            if sources_count >= 2:
                score += 5
            
            return max(0, min(100, score))
            
        except Exception:
            return 50

    def _generate_security_summary(self, overall_safe: bool, critical_issues: List[str], warnings: List[str]) -> str:
        """Generate brief security summary"""
        if not overall_safe:
            critical_count = len(critical_issues)
            if critical_count > 0:
                return f"UNSAFE: {critical_count} critical security issue{'s' if critical_count > 1 else ''} detected"
            else:
                return "UNSAFE: Security verification failed"
        
        warning_count = len(warnings)
        if warning_count == 0:
            return "SECURE: All security checks passed"
        else:
            return f"SECURE with {warning_count} warning{'s' if warning_count > 1 else ''}"
        
    def _extract_ai_analysis(self, analysis_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract AI analysis data"""
        try:
            ai_analysis = analysis_result.get("ai_analysis")
            if not ai_analysis:
                return None
            
            return {
                "available": True,
                "ai_score": float(ai_analysis.get("ai_score") or 0),
                "risk_assessment": ai_analysis.get("risk_assessment") or "unknown",
                "recommendation": ai_analysis.get("recommendation") or "HOLD",
                "confidence": float(ai_analysis.get("confidence") or 0),
                "key_insights": ai_analysis.get("key_insights") or [],
                "risk_factors": ai_analysis.get("risk_factors") or [],
                "stop_flags": ai_analysis.get("stop_flags") or [],
                "market_risk_breakdown": ai_analysis.get("market_metrics") or {},
                "reasoning": ai_analysis.get("llama_reasoning") or "",
                "model_used": ai_analysis.get("model_used") or "llama-3.3-70b-versatile",
                "processing_time": float(ai_analysis.get("processing_time") or 0)
            }
            
        except Exception as e:
            logger.warning(f"Error extracting AI analysis: {e}")
            return None

    def _extract_analysis_results(self, analysis_result: Dict[str, Any], is_deep_analysis: bool) -> Dict[str, Any]:
        """Extract analysis results"""
        try:
            overall_analysis = analysis_result.get("overall_analysis", {})
            ai_analysis = analysis_result.get("ai_analysis", {}) if is_deep_analysis else {}
            
            # Basic results
            overall_score = float(overall_analysis.get("score") or 0)
            traditional_score = float(overall_analysis.get("traditional_score") or overall_score)
            risk_level = overall_analysis.get("risk_level") or "unknown"
            recommendation = overall_analysis.get("recommendation") or "HOLD"
            confidence_score = float(overall_analysis.get("confidence_score") or 0)
            
            # Signals and factors
            positive_signals = overall_analysis.get("positive_signals") or []
            risk_factors = overall_analysis.get("risk_factors") or []
            
            # Verdict
            verdict = overall_analysis.get("verdict", {})
            if not verdict:
                verdict = {"decision": "WATCH", "reasoning": f"Score-based assessment ({overall_score}/100)"}
            
            # Summary and reasoning (ALWAYS AVAILABLE)
            summary = overall_analysis.get("summary")
            if not summary:
                summary = f"Analysis completed: {overall_score}/100 score from {len(analysis_result.get('service_responses', {}))} sources"
            
            # Reasoning: AI-enhanced for deep, traditional for quick
            reasoning = overall_analysis.get("reasoning")
            if not reasoning:
                if is_deep_analysis and ai_analysis.get("llama_reasoning"):
                    reasoning = ai_analysis["llama_reasoning"]
                else:
                    reasoning = self._generate_traditional_reasoning(overall_analysis, analysis_result)
            
            # Score breakdown
            score_breakdown = overall_analysis.get("score_breakdown", {
                "security_weight": 0.6,
                "market_weight": 0.4,
                "ai_weight": 0.0 if not is_deep_analysis else 0.4,
                "enhancement_applied": is_deep_analysis
            })
            
            return {
                "overall_score": overall_score,
                "traditional_score": traditional_score,
                "risk_level": risk_level,
                "recommendation": recommendation,
                "confidence_score": confidence_score,
                "positive_signals": positive_signals,
                "risk_factors": risk_factors,
                "verdict": verdict,
                "summary": summary,
                "reasoning": reasoning,
                "score_breakdown": score_breakdown
            }
            
        except Exception as e:
            logger.warning(f"Error extracting analysis results: {e}")
            return self._get_empty_analysis_results()
        
    def _extract_analysis_metadata(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract enhanced analysis metadata"""
        try:
            metadata = analysis_result.get("metadata", {})
            ai_analysis = analysis_result.get("ai_analysis", {})
            
            return {
                "processing_time_seconds": float(metadata.get("processing_time_seconds") or 0),
                "ai_processing_time": float(ai_analysis.get("processing_time") or 0),
                "data_sources_count": len(analysis_result.get("data_sources") or []),
                "services_attempted": int(metadata.get("services_attempted") or 0),
                "services_successful": int(metadata.get("services_successful") or 0),
                "security_check_passed": bool(metadata.get("security_check_passed", False)),
                "analysis_stopped_at_security": bool(metadata.get("analysis_stopped_at_security", False)),
                "ai_analysis_completed": bool(metadata.get("ai_analysis_completed", False)),
                "cache_available": bool(analysis_result.get("docx_cache_key"))
            }
            
        except Exception as e:
            logger.warning(f"Error extracting analysis metadata: {e}")
            return {
                "processing_time_seconds": 0.0,
                "ai_processing_time": 0.0,
                "data_sources_count": 0,
                "services_attempted": 0,
                "services_successful": 0,
                "security_check_passed": False,
                "analysis_stopped_at_security": False,
                "ai_analysis_completed": False,
                "cache_available": False
            }
        
    def _generate_traditional_reasoning(self, overall_analysis: Dict[str, Any], analysis_result: Dict[str, Any]) -> str:
        """Generate traditional reasoning for quick analysis"""
        try:
            reasoning_parts = []
            
            # Score component
            score = overall_analysis.get("score", 0)
            reasoning_parts.append(f"Analysis score: {score}/100")
            
            # Security status
            security_safe = analysis_result.get("security_analysis", {}).get("overall_safe", False)
            if security_safe:
                reasoning_parts.append("Security verification passed")
            else:
                reasoning_parts.append("Security concerns identified")
            
            # Key metrics
            whale_analysis = overall_analysis.get("whale_analysis", {})
            if whale_analysis.get("whale_count") == 0:
                reasoning_parts.append("Perfect token distribution")
            elif whale_analysis.get("whale_control_percent", 0) > 50:
                reasoning_parts.append("High whale concentration risk")
            
            # Data quality
            sources_count = len(analysis_result.get("data_sources", []))
            reasoning_parts.append(f"Analysis based on {sources_count} data sources")
            
            return ". ".join(reasoning_parts[:4]) + "."
            
        except Exception as e:
            logger.warning(f"Error generating traditional reasoning: {e}")
            return "Traditional analysis completed with available market data."

    def _assess_distribution_quality(self, whale_analysis: Dict[str, Any]) -> str:
        """Assess token distribution quality"""
        whale_count = whale_analysis.get("whale_count", 0)
        whale_control = whale_analysis.get("whale_control_percent", 0)
        
        if whale_count == 0:
            return "excellent"
        elif whale_control <= 20:
            return "good"
        elif whale_control <= 50:
            return "moderate"
        else:
            return "poor"

    def _assess_bot_likelihood(self, sniper_detection: Dict[str, Any]) -> str:
        """Assess bot activity likelihood"""
        similar_holders = sniper_detection.get("similar_holders", 0)
        pattern_detected = sniper_detection.get("pattern_detected", False)
        
        if not pattern_detected or similar_holders <= 2:
            return "low"
        elif similar_holders <= 8:
            return "moderate"
        else:
            return "high"

    def _get_price_range(self, price) -> str:
        """Categorize price into ranges for filtering"""
        try:
            if price is None or price == 0:
                return "unknown"
            price_float = float(price)
            if price_float <= 0:
                return "unknown"
            elif price_float < 0.000001:
                return "micro"
            elif price_float < 0.0001:
                return "nano"
            elif price_float < 0.01:
                return "small"
            elif price_float < 1.0:
                return "medium"
            elif price_float < 100.0:
                return "large"
            else:
                return "huge"
        except (ValueError, TypeError):
            return "unknown"

    def _get_volume_range(self, volume) -> str:
        """Categorize volume into ranges for filtering """
        try:
            if volume is None or volume == 0:
                return "none"
            volume_float = float(volume)
            if volume_float <= 0:
                return "none"
            elif volume_float < 1000:
                return "very_low"
            elif volume_float < 10000:
                return "low"
            elif volume_float < 100000:
                return "medium"
            elif volume_float < 1000000:
                return "high"
            else:
                return "very_high"
        except (ValueError, TypeError):
            return "none"

    def _get_market_cap_range(self, market_cap) -> str:
        """Categorize market cap into ranges"""
        try:
            if market_cap is None or market_cap == 0:
                return "unknown"
            mc_float = float(market_cap)
            if mc_float <= 0:
                return "unknown"
            elif mc_float < 100000:
                return "micro"  # < $100K
            elif mc_float < 1000000:
                return "small"  # < $1M
            elif mc_float < 10000000:
                return "medium" # < $10M
            elif mc_float < 100000000:
                return "large"  # < $100M
            else:
                return "mega"   # >= $100M
        except (ValueError, TypeError):
            return "unknown"

    def _get_liquidity_range(self, liquidity) -> str:
        """Categorize liquidity into ranges"""
        try:
            if liquidity is None or liquidity == 0:
                return "none"
            liq_float = float(liquidity)
            if liq_float <= 0:
                return "none"
            elif liq_float < 10000:
                return "very_low"   # < $10K
            elif liq_float < 50000:
                return "low"        # < $50K
            elif liq_float < 100000:
                return "medium"     # < $100K
            elif liq_float < 500000:
                return "high"       # < $500K
            else:
                return "very_high"  # >= $500K
        except (ValueError, TypeError):
            return "none"
    
    async def search_analyses(
        self, 
        query: str, 
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search token analyses using natural language query"""
        try:
            chroma_client = await get_chroma_client()
            if not chroma_client.is_connected():
                return []
            
            # Build where clause for filtering
            where_clause = {"doc_type": "token_analysis"}
            if filters:
                where_clause.update(filters)
            
            # Search with ChromaDB
            results = await chroma_client.search(
                query=query,
                n_results=limit,
                where=where_clause
            )
            
            # Parse and return results
            parsed_results = []
            if results and results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    
                    parsed_results.append({
                        "content": doc,
                        "metadata": metadata,
                        "similarity_score": 1 - distance  # Convert distance to similarity
                    })
            
            return parsed_results
            
        except Exception as e:
            logger.error(f"Error searching analyses: {str(e)}")
            return []
    
    async def get_token_history(
        self, 
        token_address: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get analysis history for a specific token"""
        try:
            chroma_client = await get_chroma_client()
            if not chroma_client.is_connected():
                return []
            
            # Search for all analyses of this token
            results = await chroma_client.search(
                query=f"Token analysis for {token_address}",
                n_results=limit,
                where={
                    "doc_type": "token_analysis",
                    "token_address": token_address
                }
            )
            
            # Parse results and sort by timestamp
            parsed_results = []
            if results and results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    
                    parsed_results.append({
                        "content": doc,
                        "metadata": metadata,
                        "timestamp": metadata.get("timestamp_unix", 0)
                    })
            
            # Sort by timestamp (most recent first)
            parsed_results.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return parsed_results
            
        except Exception as e:
            logger.error(f"Error getting token history: {str(e)}")
            return []
        
    async def get_analyses_paginated(self, page: int = 1, per_page: int = 20, filters: dict = None) -> dict:
        """
        Get paginated analyses with filtering
        """
        if not self.collection:
            logger.warning("ChromaDB collection not available for paginated query")
            return None
            
        try:
            # Calculate offset
            offset = (page - 1) * per_page
            
            # Build where clause for filtering
            where_clause = {}
            where_conditions = []
            
            if filters:
                # Source event filter
                if filters.get("source_event"):
                    where_conditions.append({"source_event": {"$eq": filters["source_event"]}})
                
                # Risk level filter
                if filters.get("risk_level"):
                    where_conditions.append({"risk_level": {"$eq": filters["risk_level"]}})
                
                # Security status filter
                if filters.get("security_status"):
                    where_conditions.append({"security_status": {"$eq": filters["security_status"]}})
                
                # Date range filters (using timestamp)
                if filters.get("date_from"):
                    try:
                        from datetime import datetime
                        date_from = datetime.strptime(filters["date_from"], "%Y-%m-%d").timestamp()
                        where_conditions.append({"timestamp": {"$gte": date_from}})
                    except ValueError:
                        logger.warning(f"Invalid date_from format: {filters['date_from']}")
                
                if filters.get("date_to"):
                    try:
                        from datetime import datetime
                        # Add 24 hours to include the entire day
                        date_to = datetime.strptime(filters["date_to"], "%Y-%m-%d").timestamp() + 86400
                        where_conditions.append({"timestamp": {"$lt": date_to}})
                    except ValueError:
                        logger.warning(f"Invalid date_to format: {filters['date_to']}")
            
            # Combine where conditions
            if where_conditions:
                if len(where_conditions) == 1:
                    where_clause = where_conditions[0]
                else:
                    where_clause = {"$and": where_conditions}
            
            # Query with pagination
            query_params = {
                "n_results": per_page,
                "offset": offset,
                "include": ["metadatas", "documents"]
            }
            
            if where_clause:
                query_params["where"] = where_clause
            
            # Handle search filter separately (text search)
            if filters and filters.get("search"):
                search_term = filters["search"]
                # Use query_texts for semantic/text search
                query_params["query_texts"] = [search_term]
                # Remove n_results limit for search, we'll handle it after
                search_results = self.collection.query(**query_params)
            else:
                search_results = self.collection.get(**query_params)
            
            if not search_results or not search_results.get("metadatas"):
                return {
                    "analyses": [],
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total_items": 0,
                        "total_pages": 0,
                        "has_next": False,
                        "has_prev": page > 1
                    }
                }
            
            # Get total count for pagination (separate query)
            count_params = {}
            if where_clause:
                count_params["where"] = where_clause
            
            try:
                # ChromaDB doesn't have a direct count method, so we get all IDs and count them
                total_results = self.collection.get(
                    include=["metadatas"],
                    **count_params
                )
                total_items = len(total_results.get("metadatas", []))
            except Exception as e:
                logger.warning(f"Could not get total count: {str(e)}")
                total_items = len(search_results.get("metadatas", []))
            
            # Process results
            analyses = []
            metadatas = search_results.get("metadatas", [])
            
            for i, metadata in enumerate(metadatas):
                if not metadata:
                    continue
                    
                # Apply search filter to metadata if provided
                if filters and filters.get("search"):
                    search_term = filters["search"].lower()
                    searchable_text = " ".join([
                        str(metadata.get("token_address", "")),
                        str(metadata.get("token_name", "")),
                        str(metadata.get("token_symbol", ""))
                    ]).lower()
                    
                    if search_term not in searchable_text:
                        continue
                
                analysis = {
                    "id": metadata.get("analysis_id", f"analysis_{i}"),
                    "token_address": metadata.get("token_address", ""),
                    "token_name": metadata.get("token_name", "Unknown Token"),
                    "token_symbol": metadata.get("token_symbol", "N/A"),
                    "mint": metadata.get("token_address", ""),
                    "timestamp": metadata.get("timestamp"),
                    "risk_level": metadata.get("risk_level", "unknown"),
                    "security_status": metadata.get("security_status", "unknown"),
                    "source_event": metadata.get("source_event", "unknown"),
                    "overall_score": metadata.get("overall_score"),
                    "critical_issues": metadata.get("critical_issues", 0),
                    "warnings": metadata.get("warnings", 0),
                    "processing_time": metadata.get("processing_time", 0),
                    "recommendation": metadata.get("recommendation", "HOLD"),
                    "time": self._format_relative_time(metadata.get("timestamp"))
                }
                analyses.append(analysis)
            
            # Calculate pagination info
            total_pages = (total_items + per_page - 1) // per_page
            has_next = page < total_pages
            has_prev = page > 1
            
            return {
                "analyses": analyses,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_prev": has_prev
                }
            }
            
        except Exception as e:
            logger.error(f"Error in paginated query: {str(e)}")
            return None

    def _format_relative_time(self, timestamp):
        """Format timestamp as relative time"""
        if not timestamp:
            return "Unknown"
        
        try:
            if isinstance(timestamp, str):
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.timestamp()
            
            from datetime import datetime
            now = datetime.now().timestamp()
            diff = now - float(timestamp)
            
            if diff < 60:
                return "Just now"
            elif diff < 3600:
                return f"{int(diff // 60)}m ago"
            elif diff < 86400:
                return f"{int(diff // 3600)}h ago"
            elif diff < 604800:
                return f"{int(diff // 86400)}d ago"
            else:
                dt = datetime.fromtimestamp(float(timestamp))
                return dt.strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Error formatting timestamp {timestamp}: {str(e)}")
            return "Unknown"
        
    def _get_empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure"""
        return {
            "price_usd": None,
            "price_change_24h": None,
            "volume_24h": None,
            "market_cap": None,
            "liquidity": None,
            "volume_liquidity_ratio": None,
            "data_completeness_percent": 0.0,
            "volatility": {
                "recent_volatility_percent": None,
                "volatility_risk": "unknown",
                "trades_analyzed": 0
            },
            "whale_analysis": {
                "whale_count": 0,
                "whale_control_percent": 0.0,
                "top_whale_percent": 0.0,
                "whale_risk_level": "unknown",
                "distribution_quality": "unknown"
            },
            "sniper_detection": {
                "similar_holders": 0,
                "pattern_detected": False,
                "sniper_risk": "unknown",
                "bot_likelihood": "unknown"
            }
        }

    def _get_empty_security(self) -> Dict[str, Any]:
        """Return empty security structure"""
        return {
            "overall_safe": False,
            "security_score": 0,
            "critical_issues": [],
            "warnings": [],
            "authority_risks": {
                "mint_authority_active": False,
                "freeze_authority_active": False,
                "balance_mutable": False
            },
            "lp_security": {
                "status": "unknown",
                "confidence": 0,
                "evidence": [],
                "locked_value_usd": 0.0
            },
            "security_sources": [],
            "security_summary": "Security analysis unavailable"
        }

    def _get_empty_analysis_results(self) -> Dict[str, Any]:
        """Return empty analysis results structure"""
        return {
            "overall_score": 0.0,
            "traditional_score": 0.0,
            "risk_level": "unknown",
            "recommendation": "HOLD",
            "confidence_score": 0.0,
            "positive_signals": [],
            "risk_factors": [],
            "verdict": {"decision": "WATCH", "reasoning": "Analysis data unavailable"},
            "summary": "Analysis completed with limited data",
            "reasoning": "Traditional analysis completed with available data.",
            "score_breakdown": {
                "security_weight": 0.6,
                "market_weight": 0.4,
                "ai_weight": 0.0,
                "enhancement_applied": False
            }
        }


# Global instance
analysis_storage = AnalysisStorageService()