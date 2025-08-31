import tempfile
import os
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger

try:
    from docx import Document
    from docx.shared import RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx not installed. Install with: pip install python-docx")

from app.utils.redis_client import get_redis_client


class DocxReportService:
    """Simple DOCX report generator for token analysis"""
    
    async def generate_analysis_docx_from_data(self, analysis_data: Dict[str, Any]) -> Optional[bytes]:
        """Generate DOCX report from analysis data directly - NEW METHOD"""
        
        if not DOCX_AVAILABLE:
            raise RuntimeError("python-docx not installed")
        
        try:
            logger.info(f"📄 Generating DOCX from analysis data")
            
            # Generate DOCX
            doc = Document()
            self._build_report(doc, analysis_data)
            
            # Convert to bytes
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                    temp_path = tmp.name
                    doc.save(temp_path)
                
                with open(temp_path, 'rb') as f:
                    docx_bytes = f.read()
                    logger.info(f"✅ DOCX generated ({len(docx_bytes)} bytes)")
                    return docx_bytes
                    
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            logger.error(f"❌ DOCX generation failed: {str(e)}")
            raise
    
    def _build_report(self, doc: Document, analysis_data: Dict[str, Any]):
        """Build the enhanced DOCX report structure with AI analysis"""
        
        try:
            # Extract token info with fallbacks
            token_symbol = self._get_token_symbol(analysis_data)
            token_name = self._get_token_name(analysis_data)
            token_address = analysis_data.get("token_address", "N/A")
            
            # Header
            heading = doc.add_heading(f'AI Token Analysis Report: {token_symbol}', 0)
            heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Token Info
            p = doc.add_paragraph()
            p.add_run('Token Name: ').bold = True
            p.add_run(f'{token_name}\n')
            p.add_run('Symbol: ').bold = True
            p.add_run(f'{token_symbol}\n')
            p.add_run('Contract Address: ').bold = True
            p.add_run(f'{token_address}\n')
            p.add_run('Generated: ').bold = True
            p.add_run(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
            
            # AI VERDICT SECTION
            self._add_ai_verdict_section(doc, analysis_data)
            
            # ENHANCED SCORING TABLE
            self._add_enhanced_scoring_table(doc, analysis_data)
            
            # TOP 3 PROS/CONS
            self._add_pros_cons_section(doc, analysis_data)
            
            # AI INVESTMENT REASONING
            self._add_ai_reasoning_section(doc, analysis_data)
            
            # Enhanced market data with sources
            self._add_market_data_safe(doc, analysis_data)
            
            # Security analysis  
            self._add_security_analysis_safe(doc, analysis_data)
            
            # LP analysis
            self._add_lp_analysis_safe(doc, analysis_data)
            
        except Exception as e:
            logger.error(f"Error building enhanced DOCX report: {e}")
            doc.add_paragraph(f"Error generating full report: {str(e)}")

    def _add_ai_verdict_section(self, doc: Document, analysis_data: Dict[str, Any]):
        """Add AI verdict section with GO/WATCH/NO decision"""
        try:
            doc.add_heading('AI Investment Verdict', level=1)
            
            # Get verdict from analysis
            overall_analysis = analysis_data.get("overall_analysis", {})
            ai_analysis = analysis_data.get("ai_analysis", {})
            
            # Determine verdict source and decision
            verdict_decision = "UNKNOWN"
            verdict_source = "Traditional Analysis"
            
            # Try to get verdict from AI analysis first (deep analysis)
            if ai_analysis and ai_analysis.get("verdict"):
                verdict_data = ai_analysis["verdict"]
                verdict_decision = verdict_data.get("decision", "UNKNOWN")
                verdict_source = "AI Enhanced Analysis"
            elif overall_analysis and overall_analysis.get("verdict"):
                verdict_data = overall_analysis["verdict"] 
                verdict_decision = verdict_data.get("decision", "UNKNOWN")
            else:
                # Fallback: calculate from score
                score = overall_analysis.get("score", 0)
                if score >= 80:
                    verdict_decision = "GO"
                elif score >= 60:
                    verdict_decision = "WATCH"
                else:
                    verdict_decision = "NO"
            
            # Create verdict display
            p = doc.add_paragraph()
            p.add_run('INVESTMENT VERDICT: ').bold = True
            
            verdict_run = p.add_run(verdict_decision)
            verdict_run.bold = True
            verdict_run.font.size = RGBColor(255, 255, 255)  # White text
            
            # Color coding
            if verdict_decision == "GO":
                verdict_run.font.color.rgb = RGBColor(34, 197, 94)  # Green
            elif verdict_decision == "WATCH":
                verdict_run.font.color.rgb = RGBColor(245, 158, 11)  # Yellow
            else:  # NO
                verdict_run.font.color.rgb = RGBColor(239, 68, 68)  # Red
            
            # Add score
            score = overall_analysis.get("score", 0)
            normalized_score = score / 100  # Convert to 0-1 scale
            
            p.add_run(f'\nAI Score: ').bold = True
            p.add_run(f'{normalized_score:.2f}/1.00 ({score}/100)')
            
            p.add_run(f'\nAnalysis Type: ').bold = True
            p.add_run(f'{verdict_source}')
            
        except Exception as e:
            logger.warning(f"Failed to add AI verdict section: {e}")
            doc.add_paragraph("AI verdict section unavailable")

    def _add_enhanced_scoring_table(self, doc: Document, analysis_data: Dict[str, Any]):
        """Add enhanced scoring table with risk metrics"""
        try:
            doc.add_heading('Risk Metrics Analysis', level=1)
            
            # Get enhanced metrics
            overall_analysis = analysis_data.get("overall_analysis", {})
            ai_analysis = analysis_data.get("ai_analysis", {})
            
            # Create enhanced metrics table
            table = doc.add_table(rows=1, cols=3)
            table.style = 'Table Grid'
            
            # Header row
            header_row = table.rows[0]
            header_row.cells[0].text = "Risk Metric"
            header_row.cells[1].text = "Value"
            header_row.cells[2].text = "AI Risk Level"
            
            # Collect metrics from various sources
            metrics_data = []
            
            # Volatility
            volatility = overall_analysis.get("volatility", {}).get("recent_volatility_percent")
            if volatility is not None:
                ai_volatility_risk = ai_analysis.get("market_metrics", {}).get("volatility_risk", "unknown")
                metrics_data.append(("Volatility", f"{volatility}%", ai_volatility_risk.upper()))
            
            # Whale Analysis
            whale_data = overall_analysis.get("whale_analysis", {})
            if whale_data.get("whale_count") is not None:
                whale_control = whale_data.get("whale_control_percent", 0)
                whale_count = whale_data.get("whale_count", 0)
                ai_whale_risk = ai_analysis.get("market_metrics", {}).get("whale_risk", "unknown")
                metrics_data.append(("Whale Control", f"{whale_count} whales ({whale_control}%)", ai_whale_risk.upper()))
            
            # Volume/Liquidity Ratio
            vol_liq_ratio = None
            if overall_analysis.get("volume_24h") and overall_analysis.get("liquidity"):
                try:
                    vol_liq_ratio = (overall_analysis["volume_24h"] / overall_analysis["liquidity"]) * 100
                except:
                    pass
            
            # Try to get from market data
            if vol_liq_ratio is None:
                service_responses = analysis_data.get("service_responses", {})
                birdeye = service_responses.get("birdeye", {}).get("price", {})
                if birdeye.get("volume_24h") and birdeye.get("liquidity"):
                    try:
                        vol_liq_ratio = (float(birdeye["volume_24h"]) / float(birdeye["liquidity"])) * 100
                    except:
                        pass
            
            if vol_liq_ratio is not None:
                ai_liquidity_health = ai_analysis.get("market_metrics", {}).get("liquidity_health", "unknown")
                metrics_data.append(("Volume/Liquidity", f"{vol_liq_ratio:.1f}%", ai_liquidity_health.upper()))
            
            # Sniper Risk
            sniper_data = overall_analysis.get("sniper_detection", {})
            if sniper_data.get("similar_holders") is not None:
                similar_holders = sniper_data.get("similar_holders", 0)
                pattern_detected = sniper_data.get("pattern_detected", False)
                ai_sniper_risk = ai_analysis.get("market_metrics", {}).get("sniper_risk", "unknown")
                metrics_data.append(("Sniper Patterns", f"{similar_holders} similar ({'Yes' if pattern_detected else 'No'})", ai_sniper_risk.upper()))
            
            # Dev Holdings
            dev_percent = self._extract_dev_percent(analysis_data)
            if dev_percent is not None:
                ai_dev_risk = ai_analysis.get("market_metrics", {}).get("dev_risk", "unknown")
                metrics_data.append(("Dev Holdings", f"{dev_percent:.1f}%", ai_dev_risk.upper()))
            
            # LP Security
            lp_status = self._extract_lp_status(analysis_data)
            ai_lp_security = ai_analysis.get("market_metrics", {}).get("lp_security", "unknown")
            metrics_data.append(("LP Security", lp_status, ai_lp_security.upper()))
            
            # Add rows to table
            for metric, value, ai_risk in metrics_data:
                row = table.add_row()
                row.cells[0].text = metric
                row.cells[1].text = str(value)
                row.cells[2].text = str(ai_risk)
                
                # Color code AI risk levels
                risk_cell = row.cells[2]
                if ai_risk.upper() == "LOW":
                    risk_cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(34, 197, 94)  # Green
                elif ai_risk.upper() == "HIGH":
                    risk_cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(239, 68, 68)  # Red
                elif ai_risk.upper() == "MEDIUM":
                    risk_cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(245, 158, 11)  # Yellow
            
            logger.info(f"Enhanced scoring table created with {len(metrics_data)} metrics")
            
        except Exception as e:
            logger.warning(f"Failed to add enhanced scoring table: {e}")
            doc.add_paragraph("Enhanced scoring section unavailable")

    def _add_ai_reasoning_section(self, doc: Document, analysis_data: Dict[str, Any]):
        """Add AI-generated investment reasoning section"""
        try:
            doc.add_heading('AI Investment Analysis', level=1)
            
            # Get AI reasoning
            ai_reasoning = self._extract_ai_reasoning(analysis_data)
            
            if ai_reasoning:
                # Add AI reasoning text
                reasoning_paragraph = doc.add_paragraph()
                reasoning_paragraph.add_run('AI Analysis: ').bold = True
                reasoning_paragraph.add_run(ai_reasoning)
                
                # Add confidence level
                confidence = self._extract_confidence(analysis_data)
                if confidence:
                    conf_paragraph = doc.add_paragraph()
                    conf_paragraph.add_run('Analysis Confidence: ').bold = True
                    conf_paragraph.add_run(f'{confidence}%')
                
                logger.info("AI reasoning section added successfully")
            else:
                doc.add_paragraph("AI reasoning not available - analysis may have used traditional methods only")
                
        except Exception as e:
            logger.warning(f"Failed to add AI reasoning section: {e}")
            doc.add_paragraph("AI reasoning section unavailable")

    def _extract_pros_cons(self, analysis_data: Dict[str, Any]) -> tuple:
        """Extract top 3 pros and cons from analysis data"""
        try:
            pros = []
            cons = []
            
            # Method 1: Try to get from AI analysis verdict reasoning (deep analysis)
            ai_analysis = analysis_data.get("ai_analysis", {})
            if ai_analysis and ai_analysis.get("verdict", {}).get("reasoning"):
                reasoning = ai_analysis["verdict"]["reasoning"]
                if isinstance(reasoning, dict):
                    pros = reasoning.get("pros", [])[:3]
                    cons = reasoning.get("cons", [])[:3]
                    logger.info("Pros/cons extracted from AI analysis reasoning")
                    return pros, cons
            
            # Method 2: Try to get from overall analysis verdict (quick analysis)
            overall_analysis = analysis_data.get("overall_analysis", {})
            if overall_analysis and overall_analysis.get("verdict", {}).get("reasoning"):
                reasoning = overall_analysis["verdict"]["reasoning"]
                if isinstance(reasoning, dict):
                    pros = reasoning.get("pros", [])[:3]
                    cons = reasoning.get("cons", [])[:3]
                    logger.info("Pros/cons extracted from overall analysis reasoning")
                    return pros, cons
            
            # Method 3: Fallback - extract from positive signals and risk factors
            positive_signals = overall_analysis.get("positive_signals", [])
            risk_factors = overall_analysis.get("risk_factors", [])
            
            # Use top 3 from each
            pros = positive_signals[:3] if positive_signals else ["Security checks passed"]
            cons = risk_factors[:3] if risk_factors else ["Limited analysis data"]
            
            logger.info("Pros/cons extracted from fallback method")
            return pros, cons
            
        except Exception as e:
            logger.warning(f"Failed to extract pros/cons: {e}")
            return ["Analysis completed"], ["Limited data available"]
        
    def _extract_ai_reasoning(self, analysis_data: Dict[str, Any]) -> str:
        """Extract AI reasoning from analysis data"""
        try:
            # Try AI analysis first
            ai_analysis = analysis_data.get("ai_analysis", {})
            if ai_analysis:
                # Try llama_reasoning field
                reasoning = ai_analysis.get("llama_reasoning")
                if reasoning and len(reasoning) > 50:  # Meaningful reasoning
                    return reasoning
                
                # Try to construct from AI metrics
                market_metrics = ai_analysis.get("market_metrics", {})
                if market_metrics:
                    risk_levels = []
                    for metric, risk_level in market_metrics.items():
                        if risk_level and risk_level != "unknown":
                            risk_levels.append(f"{metric}: {risk_level}")
                    
                    if risk_levels:
                        return f"AI assessment based on risk analysis: {'; '.join(risk_levels[:5])}"
            
            # Fallback to overall analysis summary
            overall_analysis = analysis_data.get("overall_analysis", {})
            if overall_analysis:
                summary = overall_analysis.get("summary", "")
                if summary and len(summary) > 20:
                    return f"Analysis summary: {summary}"
            
            return "AI analysis completed with available token data"
            
        except Exception as e:
            logger.warning(f"Failed to extract AI reasoning: {e}")
            return "AI reasoning extraction failed"
        
    def _extract_confidence(self, analysis_data: Dict[str, Any]) -> Optional[float]:
        """Extract confidence level from analysis"""
        try:
            # Try AI analysis confidence first
            ai_analysis = analysis_data.get("ai_analysis", {})
            if ai_analysis and ai_analysis.get("confidence"):
                return float(ai_analysis["confidence"])
            
            # Fallback to overall analysis confidence
            overall_analysis = analysis_data.get("overall_analysis", {})
            if overall_analysis and overall_analysis.get("confidence"):
                return float(overall_analysis["confidence"])
            
            return None
            
        except Exception:
            return None

    def _extract_dev_percent(self, analysis_data: Dict[str, Any]) -> Optional[float]:
        """Extract dev holdings percentage"""
        try:
            # Try from service responses
            rugcheck = analysis_data.get("service_responses", {}).get("rugcheck", {})
            if rugcheck and rugcheck.get("creator_analysis"):
                creator_analysis = rugcheck["creator_analysis"]
                creator_balance = creator_analysis.get("creator_balance", 0)
                
                # Try to get total supply
                helius = analysis_data.get("service_responses", {}).get("helius", {})
                if helius and helius.get("supply"):
                    total_supply = helius["supply"].get("ui_amount")
                    if total_supply and creator_balance:
                        return (float(creator_balance) / float(total_supply)) * 100
            
            return None
            
        except Exception:
            return None

    def _extract_lp_status(self, analysis_data: Dict[str, Any]) -> str:
        """Extract LP status description"""
        try:
            rugcheck = analysis_data.get("service_responses", {}).get("rugcheck", {})
            
            # Check for locked LP
            lockers_data = rugcheck.get('lockers_data', {})
            if lockers_data and lockers_data.get('lockers'):
                return "LOCKED"
            
            # Check for burned LP
            markets = rugcheck.get('market_analysis', {}).get('markets', [])
            for market in markets:
                if isinstance(market, dict) and market.get('lp'):
                    holders = market['lp'].get('holders', [])
                    for holder in holders:
                        if isinstance(holder, dict):
                            owner = str(holder.get('owner', ''))
                            pct = holder.get('pct', 0)
                            
                            burn_patterns = ['111111', 'dead', 'burn']
                            if any(pattern in owner.lower() for pattern in burn_patterns) and pct > 50:
                                return "BURNED"
            
            return "UNKNOWN"
            
        except Exception:
            return "UNKNOWN"
        
    def _calculate_rating(self, analysis_data: Dict[str, Any]) -> Dict[str, str]:
        """Calculate GO/WATCH/NO rating based on enhanced data"""
        
        security_data = analysis_data.get("security_analysis", {})
        overall_analysis = analysis_data.get("overall_analysis", {})
        
        # Critical security failure = NO
        if not security_data.get("overall_safe"):
            return {
                "decision": "NO",
                "reasoning": "Critical security issues detected"
            }
        
        # Try to get verdict from analysis
        verdict = None
        if overall_analysis.get("verdict"):
            verdict = overall_analysis["verdict"].get("decision")
        
        # If no verdict, calculate from score
        if not verdict:
            score = overall_analysis.get("score", 0)
            risk_level = overall_analysis.get("risk_level", "unknown")
            
            if score >= 80 and risk_level == "low":
                verdict = "GO"
            elif score >= 60:
                verdict = "WATCH"
            else:
                verdict = "NO"
        
        # Generate reasoning
        reasoning_parts = []
        
        # Add score component
        score = overall_analysis.get("score", 0)
        normalized_score = score / 100
        reasoning_parts.append(f"AI Score: {normalized_score:.2f}/1.00")
        
        # Add key factors
        if overall_analysis.get("whale_analysis", {}).get("whale_count") == 0:
            reasoning_parts.append("Perfect token distribution")
        elif overall_analysis.get("whale_analysis", {}).get("whale_control_percent", 0) > 50:
            reasoning_parts.append("High whale concentration risk")
        
        if overall_analysis.get("volatility", {}).get("recent_volatility_percent"):
            vol = overall_analysis["volatility"]["recent_volatility_percent"]
            if vol <= 10:
                reasoning_parts.append("Low volatility")
            elif vol > 30:
                reasoning_parts.append("High volatility")
        
        reasoning = " | ".join(reasoning_parts[:3]) if reasoning_parts else f"Score-based assessment ({normalized_score:.2f}/1.00)"
        
        return {
            "decision": verdict,
            "reasoning": reasoning
        }

    def _add_final_rating_safe(self, doc: Document, analysis_data: Dict[str, Any]):
        """Add final rating with enhanced verdict system"""
        try:
            doc.add_heading('Final Investment Rating', level=1)
            
            rating = self._calculate_rating(analysis_data)
            
            p = doc.add_paragraph()
            p.add_run('FINAL RATING: ').bold = True
            
            rating_run = p.add_run(rating["decision"])
            rating_run.bold = True
            if rating["decision"] == "GO":
                rating_run.font.color.rgb = RGBColor(34, 197, 94)  # Green
            elif rating["decision"] == "NO":
                rating_run.font.color.rgb = RGBColor(239, 68, 68)  # Red
            else:  # WATCH
                rating_run.font.color.rgb = RGBColor(245, 158, 11)  # Yellow
            
            # Add reasoning
            doc.add_paragraph(f"Reasoning: {rating['reasoning']}")
            
            # Add disclaimer
            disclaimer = doc.add_paragraph()
            disclaimer.add_run('Disclaimer: ').bold = True
            disclaimer.add_run('This analysis is for informational purposes only and does not constitute financial advice. Cryptocurrency investments carry significant risk.')
            
        except Exception as e:
            logger.warning(f"Failed to add final rating: {e}")
            doc.add_paragraph("Final rating section unavailable")

    def _add_security_analysis_safe(self, doc: Document, analysis_data: Dict[str, Any]):
        """Add security analysis with error handling"""
        try:
            doc.add_heading('Security Analysis', level=1)
            security_data = analysis_data.get("security_analysis", {})
            
            if security_data:
                sec_table = doc.add_table(rows=1, cols=2)
                sec_table.style = 'Table Grid'
                
                security_info = [
                    ("Security Status", "PASSED" if security_data.get("overall_safe") else "FAILED"),
                    ("Critical Issues", len(security_data.get("critical_issues", []))),
                    ("Warnings", len(security_data.get("warnings", []))),
                ]
                
                for key, value in security_info:
                    row = sec_table.add_row()
                    row.cells[0].text = key
                    row.cells[1].text = str(value)
            else:
                doc.add_paragraph("Security analysis data not available")
        except Exception as e:
            logger.warning(f"Failed to add security analysis: {e}")
            doc.add_paragraph("Security analysis section unavailable")

    def _add_market_data_safe(self, doc: Document, analysis_data: Dict[str, Any]):
        """Add market data with error handling - FIXED to use aggregated data"""
        try:
            doc.add_heading('Market Data', level=1)
            
            # Try to get aggregated market data from AI analysis first
            ai_analysis = analysis_data.get("ai_analysis", {})
            market_metrics = ai_analysis.get("market_metrics", {}) if ai_analysis else {}
            
            # Also check if comprehensive market data was calculated in Groq service
            service_responses = analysis_data.get("service_responses", {})
            
            # Initialize market data dict
            market_data = {}
            
            # Check DexScreener first (since your logs show it has the data)
            dexscreener = service_responses.get("dexscreener", {})
            if dexscreener and dexscreener.get("pairs", {}).get("pairs"):
                pairs = dexscreener["pairs"]["pairs"]
                if isinstance(pairs, list) and len(pairs) > 0:
                    pair = pairs[0]
                    
                    # Market cap from DexScreener
                    if not market_data.get("market_cap") and pair.get("marketCap"):
                        try:
                            market_data["market_cap"] = float(pair["marketCap"])
                            market_data["market_cap_source"] = "DexScreener"
                        except (ValueError, TypeError):
                            pass
                    
                    # Volume from DexScreener
                    if not market_data.get("volume_24h"):
                        vol_data = pair.get("volume", {})
                        if vol_data and vol_data.get("h24"):
                            try:
                                market_data["volume_24h"] = float(vol_data["h24"])
                                market_data["volume_source"] = "DexScreener"
                            except (ValueError, TypeError):
                                pass
                    
                    # Liquidity from DexScreener
                    if not market_data.get("liquidity"):
                        liq_data = pair.get("liquidity", {})
                        if liq_data and liq_data.get("usd"):
                            try:
                                market_data["liquidity"] = float(liq_data["usd"])
                                market_data["liquidity_source"] = "DexScreener"
                            except (ValueError, TypeError):
                                pass
                    
                    # Price from DexScreener
                    if not market_data.get("price") and pair.get("priceUsd"):
                        try:
                            market_data["price"] = float(pair["priceUsd"])
                            market_data["price_source"] = "DexScreener"
                        except (ValueError, TypeError):
                            pass
            
            # Birdeye fallback (if DexScreener didn't have everything)
            birdeye = service_responses.get("birdeye", {}).get("price", {})
            if birdeye:
                # Price from Birdeye
                if not market_data.get("price") and birdeye.get("value"):
                    try:
                        market_data["price"] = float(birdeye["value"])
                        market_data["price_source"] = "Birdeye"
                    except (ValueError, TypeError):
                        pass
                
                # Market cap from Birdeye
                if not market_data.get("market_cap") and birdeye.get("market_cap"):
                    try:
                        market_data["market_cap"] = float(birdeye["market_cap"])
                        market_data["market_cap_source"] = "Birdeye"
                    except (ValueError, TypeError):
                        pass
                
                # Volume from Birdeye
                if not market_data.get("volume_24h") and birdeye.get("volume_24h"):
                    try:
                        market_data["volume_24h"] = float(birdeye["volume_24h"])
                        market_data["volume_source"] = "Birdeye"
                    except (ValueError, TypeError):
                        pass
                
                # Liquidity from Birdeye
                if not market_data.get("liquidity") and birdeye.get("liquidity"):
                    try:
                        market_data["liquidity"] = float(birdeye["liquidity"])
                        market_data["liquidity_source"] = "Birdeye"
                    except (ValueError, TypeError):
                        pass
                
                # Price change from Birdeye
                if not market_data.get("price_change_24h") and birdeye.get("price_change_24h") is not None:
                    try:
                        market_data["price_change_24h"] = float(birdeye["price_change_24h"])
                        market_data["price_change_source"] = "Birdeye"
                    except (ValueError, TypeError):
                        pass
            
            # SolSniffer fallback
            if not market_data.get("market_cap"):
                solsniffer = service_responses.get("solsniffer", {})
                if solsniffer and isinstance(solsniffer, dict):
                    for field_name in ['marketCap', 'market_cap']:
                        mc_value = solsniffer.get(field_name)
                        if mc_value is not None:
                            try:
                                market_data["market_cap"] = float(mc_value)
                                market_data["market_cap_source"] = "SolSniffer"
                                break
                            except (ValueError, TypeError):
                                continue
            
            # Create table with extracted data
            if market_data:
                table = doc.add_table(rows=1, cols=3)  # Add source column
                table.style = 'Table Grid'
                
                # Header row
                header_row = table.rows[0]
                header_row.cells[0].text = "Metric"
                header_row.cells[1].text = "Value"
                header_row.cells[2].text = "Source"
                
                # Market data rows
                market_data_rows = [
                    ("Price", f"${market_data.get('price', 'N/A')}" if market_data.get('price') else "N/A", market_data.get('price_source', 'N/A')),
                    ("Market Cap", f"${market_data.get('market_cap', 0):,.0f}" if market_data.get('market_cap') else "N/A", market_data.get('market_cap_source', 'N/A')),
                    ("24h Volume", f"${market_data.get('volume_24h', 0):,.0f}" if market_data.get('volume_24h') else "N/A", market_data.get('volume_source', 'N/A')),
                    ("Liquidity", f"${market_data.get('liquidity', 0):,.0f}" if market_data.get('liquidity') else "N/A", market_data.get('liquidity_source', 'N/A')),
                    ("24h Change", f"{market_data.get('price_change_24h', 'N/A')}%" if market_data.get('price_change_24h') is not None else "N/A", market_data.get('price_change_source', 'N/A')),
                ]
                
                for metric, value, source in market_data_rows:
                    row = table.add_row()
                    row.cells[0].text = metric
                    row.cells[1].text = str(value)
                    row.cells[2].text = str(source)
                
                logger.info(f"DOCX market data table created with {len(market_data_rows)} rows")
            else:
                doc.add_paragraph("Market data not available from any source")
                logger.warning("No market data available for DOCX generation")
                
        except Exception as e:
            logger.warning(f"Failed to add market data: {e}")
            doc.add_paragraph("Market data section unavailable")
    
    def _get_token_symbol(self, analysis_data: Dict[str, Any]) -> str:
        """Extract token symbol from various sources - IMPROVED with fallbacks"""
        try:
            services = analysis_data.get("service_responses", {})
            
            # Try SolSniffer first
            if services.get("solsniffer", {}).get("tokenSymbol"):
                return services["solsniffer"]["tokenSymbol"]
            
            # Try Helius
            helius_meta = services.get("helius", {}).get("metadata", {})
            if helius_meta.get("onChainMetadata", {}).get("metadata", {}).get("data", {}).get("symbol"):
                return helius_meta["onChainMetadata"]["metadata"]["data"]["symbol"]
            
            # Try other sources
            for service_name, service_data in services.items():
                if isinstance(service_data, dict):
                    for key in ["symbol", "tokenSymbol", "token_symbol"]:
                        if service_data.get(key):
                            return service_data[key]
            
            return "Unknown"
        except Exception as e:
            logger.warning(f"Error extracting token symbol: {e}")
            return "Unknown"
        
    def _get_token_name(self, analysis_data: Dict[str, Any]) -> str:
        """Extract token name from various sources - IMPROVED with fallbacks"""
        try:
            services = analysis_data.get("service_responses", {})
            
            # Try SolSniffer first
            if services.get("solsniffer", {}).get("tokenName"):
                return services["solsniffer"]["tokenName"]
            
            # Try Helius
            helius_meta = services.get("helius", {}).get("metadata", {})
            if helius_meta.get("onChainMetadata", {}).get("metadata", {}).get("data", {}).get("name"):
                return helius_meta["onChainMetadata"]["metadata"]["data"]["name"]
            
            # Try other sources
            for service_name, service_data in services.items():
                if isinstance(service_data, dict):
                    for key in ["name", "tokenName", "token_name"]:
                        if service_data.get(key):
                            return service_data[key]
            
            return "Unknown Token"
        except Exception as e:
            logger.warning(f"Error extracting token name: {e}")
            return "Unknown Token"

# Global service instance
docx_service = DocxReportService()