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
        """Build the DOCX report structure - IMPROVED error handling"""
        
        try:
            # Extract token info with fallbacks
            token_symbol = self._get_token_symbol(analysis_data)
            token_name = self._get_token_name(analysis_data)
            token_address = analysis_data.get("token_address", "N/A")
            
            # Header
            heading = doc.add_heading(f'Token Analysis Report: {token_symbol}', 0)
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
            
            # Analysis Summary
            self._add_analysis_summary_safe(doc, analysis_data)
            
            # Security Analysis  
            self._add_security_analysis_safe(doc, analysis_data)
            
            # Market Data
            self._add_market_data_safe(doc, analysis_data)
            
            # LP Analysis
            self._add_lp_analysis_safe(doc, analysis_data)
            
            # Final Rating
            self._add_final_rating_safe(doc, analysis_data)
            
        except Exception as e:
            logger.error(f"Error building DOCX report: {e}")
            # Add error message to document
            doc.add_paragraph(f"Error generating full report: {str(e)}")

    def _add_analysis_summary_safe(self, doc: Document, analysis_data: Dict[str, Any]):
        """Add analysis summary with error handling"""
        try:
            doc.add_heading('Analysis Summary', level=1)
            analysis_results = analysis_data.get("overall_analysis", {})
            
            if analysis_results:
                table = doc.add_table(rows=1, cols=2)
                table.style = 'Table Grid'
                
                summary_data = [
                    ("Overall Score", f"{analysis_results.get('score', 'N/A')}/100"),
                    ("Risk Level", str(analysis_results.get('risk_level', 'Unknown')).upper()),
                    ("Recommendation", str(analysis_results.get('recommendation', 'HOLD')).upper()),
                    ("Confidence", f"{analysis_results.get('confidence', 'N/A')}%"),
                ]
                
                for key, value in summary_data:
                    row = table.add_row()
                    row.cells[0].text = key
                    row.cells[1].text = str(value)
            else:
                doc.add_paragraph("Analysis summary not available in cached data")
        except Exception as e:
            logger.warning(f"Failed to add analysis summary: {e}")
            doc.add_paragraph("Analysis summary section unavailable")

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
        """Add market data with error handling"""
        try:
            doc.add_heading('Market Data', level=1)
            
            birdeye = analysis_data.get("service_responses", {}).get("birdeye", {}).get("price", {})
            
            if birdeye:
                table = doc.add_table(rows=1, cols=2)
                table.style = 'Table Grid'
                
                market_data = [
                    ("Price", f"${birdeye.get('value', 'N/A')}"),
                    ("Market Cap", f"${birdeye.get('market_cap', 'N/A'):,.0f}" if birdeye.get('market_cap') else "N/A"),
                    ("24h Volume", f"${birdeye.get('volume_24h', 'N/A'):,.0f}" if birdeye.get('volume_24h') else "N/A"),
                    ("Liquidity", f"${birdeye.get('liquidity', 'N/A'):,.0f}" if birdeye.get('liquidity') else "N/A"),
                    ("24h Change", f"{birdeye.get('price_change_24h', 'N/A')}%" if birdeye.get('price_change_24h') else "N/A"),
                ]
                
                for key, value in market_data:
                    row = table.add_row()
                    row.cells[0].text = key
                    row.cells[1].text = str(value)
            else:
                doc.add_paragraph("Market data not available")
        except Exception as e:
            logger.warning(f"Failed to add market data: {e}")
            doc.add_paragraph("Market data section unavailable")

    def _add_lp_analysis_safe(self, doc: Document, analysis_data: Dict[str, Any]):
        """Add LP analysis with error handling"""
        try:
            doc.add_heading('Liquidity Provider Analysis', level=1)
            
            rugcheck = analysis_data.get("service_responses", {}).get("rugcheck", {})
            
            if rugcheck:
                table = doc.add_table(rows=1, cols=2)
                table.style = 'Table Grid'
                
                lp_data = [
                    ("LP Status", self._determine_lp_status(rugcheck)),
                    ("LP Providers", rugcheck.get('total_LP_providers', 'N/A')),
                    ("Locked Value", self._get_locked_value(rugcheck)),
                ]
                
                for key, value in lp_data:
                    row = table.add_row()
                    row.cells[0].text = key
                    row.cells[1].text = str(value)
            else:
                doc.add_paragraph("LP analysis data not available")
        except Exception as e:
            logger.warning(f"Failed to add LP analysis: {e}")
            doc.add_paragraph("LP analysis section unavailable")

    def _add_final_rating_safe(self, doc: Document, analysis_data: Dict[str, Any]):
        """Add final rating with error handling"""
        try:
            doc.add_heading('Final Rating', level=1)
            
            rating = self._calculate_rating(analysis_data)
            
            p = doc.add_paragraph()
            p.add_run('FINAL RATING: ').bold = True
            
            rating_run = p.add_run(rating["decision"])
            rating_run.bold = True
            if rating["decision"] == "GO":
                rating_run.font.color.rgb = RGBColor(34, 197, 94)  # Green
            elif rating["decision"] == "NO":
                rating_run.font.color.rgb = RGBColor(239, 68, 68)  # Red
            else:
                rating_run.font.color.rgb = RGBColor(245, 158, 11)  # Yellow
            
            # Add reasoning
            doc.add_paragraph(f"Reasoning: {rating['reasoning']}")
        except Exception as e:
            logger.warning(f"Failed to add final rating: {e}")
            doc.add_paragraph("Final rating section unavailable")
    
    def _calculate_rating(self, analysis_data: Dict[str, Any]) -> Dict[str, str]:
        """Calculate GO/WATCH/NO rating based on data"""
        
        security_data = analysis_data.get("security_analysis", {})
        overall_analysis = analysis_data.get("overall_analysis", {})
        
        # Critical security failure = NO
        if not security_data.get("overall_safe"):
            return {
                "decision": "NO",
                "reasoning": "Critical security issues detected"
            }
        
        # Check score thresholds
        score = overall_analysis.get("score", 0)
        risk_level = overall_analysis.get("risk_level", "unknown")
        
        if score >= 80 and risk_level == "low":
            return {
                "decision": "GO", 
                "reasoning": f"High score ({score}/100) with low risk"
            }
        elif score >= 60 or risk_level in ["low", "medium"]:
            return {
                "decision": "WATCH",
                "reasoning": f"Moderate score ({score}/100) with {risk_level} risk - monitor closely"
            }
        else:
            return {
                "decision": "NO",
                "reasoning": f"Low score ({score}/100) with {risk_level} risk"
            }
    
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
    
    def _determine_lp_status(self, rugcheck_data: Dict[str, Any]) -> str:
        """Determine LP status from RugCheck data"""
        
        lockers_data = rugcheck_data.get('lockers_data', {})
        if lockers_data and lockers_data.get('lockers'):
            return "LOCKED"
        
        # Check for burn patterns
        markets = rugcheck_data.get('market_analysis', {}).get('markets', [])
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
    
    def _get_locked_value(self, rugcheck_data: Dict[str, Any]) -> str:
        """Get total locked value from RugCheck"""
        
        lockers_data = rugcheck_data.get('lockers_data', {})
        if lockers_data and lockers_data.get('lockers'):
            total_value = 0
            for locker_info in lockers_data['lockers'].values():
                if isinstance(locker_info, dict):
                    usd_locked = locker_info.get('usdcLocked', 0)
                    if isinstance(usd_locked, (int, float)):
                        total_value += usd_locked
            
            return f"${total_value:,.0f}" if total_value > 0 else "N/A"
        
        return "N/A"


# Global service instance
docx_service = DocxReportService()