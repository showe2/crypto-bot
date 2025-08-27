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
    
    def _extract_analysis_data(self, analysis_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract key data from analysis result for storage"""
        try:
            # Parse timestamp
            timestamp = analysis_result.get("timestamp")
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp_unix = int(dt.timestamp())
            else:
                dt = datetime.utcnow()
                timestamp_unix = int(dt.timestamp())
            
            # Extract token information
            token_name = self._extract_token_name(analysis_result)
            token_symbol = self._extract_token_symbol(analysis_result)
            
            # Extract price data
            price_data = self._extract_price_data(analysis_result)
            
            # Extract security analysis
            security_analysis = analysis_result.get("security_analysis", {})
            security_status = "unknown"
            if analysis_result.get("metadata", {}).get("analysis_stopped_at_security"):
                security_status = "failed"
            elif security_analysis.get("overall_safe"):
                critical_issues = len(security_analysis.get("critical_issues", []))
                warnings = len(security_analysis.get("warnings", []))
                if critical_issues == 0:
                    security_status = "passed" if warnings == 0 else "warning"
                else:
                    security_status = "failed"
            
            # Extract overall analysis
            overall_analysis = analysis_result.get("overall_analysis", {})
            
            # Compile extracted data
            doc_data = {
                # Identity
                "analysis_id": analysis_result.get("analysis_id"),
                "token_address": analysis_result.get("token_address"),
                "timestamp": timestamp or dt.isoformat(),
                "timestamp_unix": timestamp_unix,
                "source_event": analysis_result.get("source_event", "unknown"),
                
                # Core Results - safe extraction with defaults
                "security_status": security_status,
                "analysis_stopped_at_security": analysis_result.get("metadata", {}).get("analysis_stopped_at_security", False),
                "overall_score": float(overall_analysis.get("score", 0)),
                "risk_level": overall_analysis.get("risk_level", "unknown"),
                "recommendation": overall_analysis.get("recommendation", "unknown"),
                "confidence_score": float(overall_analysis.get("confidence_score", 0)),
                
                # Token Info
                "token_name": token_name,
                "token_symbol": token_symbol,
                
                # Price Data (at time of analysis) - already safe from _extract_price_data
                "price_usd": price_data.get("current_price", 0.0),
                "price_change_24h": price_data.get("price_change_24h", 0.0),
                "volume_24h": price_data.get("volume_24h", 0.0),
                "market_cap": price_data.get("market_cap", 0.0),
                "liquidity": price_data.get("liquidity", 0.0),
                
                # Security Summary
                "security_score": self._calculate_security_score(security_analysis),
                "critical_issues_count": len(security_analysis.get("critical_issues", [])),
                "warnings_count": len(security_analysis.get("warnings", [])),
                "security_sources": self._get_security_sources(security_analysis),
                
                # Analysis Metadata - safe extraction
                "data_sources": analysis_result.get("data_sources", []),
                "services_attempted": int(analysis_result.get("metadata", {}).get("services_attempted", 0)),
                "services_successful": int(analysis_result.get("metadata", {}).get("services_successful", 0)),
                "processing_time": float(analysis_result.get("metadata", {}).get("processing_time_seconds", 0.0)),
                
                # Store full result for complex queries
                "full_analysis_json": json.dumps(analysis_result, default=str)
            }
            
            return doc_data
            
        except Exception as e:
            logger.error(f"Error extracting analysis data: {str(e)}")
            return None
    
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
    
    def _extract_price_data(self, analysis_result: Dict[str, Any]) -> Dict[str, float]:
        """Extract price data from analysis result"""
        birdeye_price = (analysis_result
                        .get("service_responses", {})
                        .get("birdeye", {})
                        .get("price", {}))
        
        # Safe conversion with defaults
        def safe_float(value, default=0.0):
            try:
                if value is None:
                    return default
                return float(value)
            except (ValueError, TypeError):
                return default
        
        return {
            "current_price": safe_float(birdeye_price.get("value"), 0.0),
            "price_change_24h": safe_float(birdeye_price.get("price_change_24h"), 0.0),
            "volume_24h": safe_float(birdeye_price.get("volume_24h"), 0.0),
            "market_cap": safe_float(birdeye_price.get("market_cap"), 0.0),
            "liquidity": safe_float(birdeye_price.get("liquidity"), 0.0)
        }
    
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
        """Generate searchable content for vector search"""
        
        # Build searchable content
        content_parts = []
        
        # Token information
        if doc_data.get("token_name") != "Unknown Token":
            content_parts.append(f"Token: {doc_data['token_name']} ({doc_data['token_symbol']})")
        
        # Analysis results
        content_parts.append(f"Security status: {doc_data['security_status']}")
        content_parts.append(f"Risk level: {doc_data['risk_level']}")
        content_parts.append(f"Recommendation: {doc_data['recommendation']}")
        content_parts.append(f"Overall score: {doc_data['overall_score']}")
        
        # Security details
        if doc_data['critical_issues_count'] > 0:
            content_parts.append(f"Has {doc_data['critical_issues_count']} critical security issues")
        if doc_data['warnings_count'] > 0:
            content_parts.append(f"Has {doc_data['warnings_count']} security warnings")
        
        # Price information
        if doc_data.get('price_usd', 0) > 0:
            content_parts.append(f"Price: ${doc_data['price_usd']:.6f}")
            if doc_data.get('price_change_24h', 0) != 0:
                change_direction = "increased" if doc_data['price_change_24h'] > 0 else "decreased"
                content_parts.append(f"Price {change_direction} {abs(doc_data['price_change_24h']):.2f}% in 24h")
        
        # Market data
        if doc_data.get('volume_24h', 0) > 0:
            if doc_data['volume_24h'] >= 1000000:
                content_parts.append(f"High trading volume: ${doc_data['volume_24h']:,.0f}")
            elif doc_data['volume_24h'] >= 10000:
                content_parts.append(f"Moderate trading volume: ${doc_data['volume_24h']:,.0f}")
            else:
                content_parts.append(f"Low trading volume: ${doc_data['volume_24h']:,.0f}")
        
        # Data sources
        if doc_data.get('data_sources'):
            content_parts.append(f"Data from: {', '.join(doc_data['data_sources'])}")
        
        # Analysis source
        content_parts.append(f"Analysis source: {doc_data['source_event']}")
        
        # Timestamp
        dt = datetime.fromtimestamp(doc_data['timestamp_unix'])
        content_parts.append(f"Analyzed on: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return ". ".join(content_parts) + "."
    
    def _generate_metadata(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate metadata for filtering and exact searches"""
        
        dt = datetime.fromtimestamp(doc_data['timestamp_unix'])
        
        return {
            # Core identifiers
            "doc_type": "token_analysis",
            "analysis_id": doc_data["analysis_id"],
            "token_address": doc_data["token_address"],
            "token_symbol": doc_data["token_symbol"],
            
            # Analysis results (for filtering)
            "security_status": doc_data["security_status"],
            "risk_level": doc_data["risk_level"],
            "recommendation": doc_data["recommendation"],
            "analysis_stopped_at_security": doc_data["analysis_stopped_at_security"],
            
            # Scores (for range queries)
            "overall_score": float(doc_data["overall_score"]),
            "security_score": float(doc_data["security_score"]),
            "confidence_score": float(doc_data["confidence_score"]),
            
            # Counts
            "critical_issues_count": int(doc_data["critical_issues_count"]),
            "warnings_count": int(doc_data["warnings_count"]),
            
            # Time-based filtering
            "analysis_date": dt.strftime("%Y-%m-%d"),
            "analysis_year": str(dt.year),
            "analysis_month": dt.strftime("%Y-%m"),
            "timestamp_unix": int(doc_data["timestamp_unix"]),
            
            # Source and performance
            "source_event": doc_data["source_event"],
            "processing_time": float(doc_data["processing_time"]),
            "services_successful": int(doc_data["services_successful"]),
            
            # Market data ranges (for filtering)
            "price_range": self._get_price_range(doc_data.get("price_usd", 0)),
            "volume_range": self._get_volume_range(doc_data.get("volume_24h", 0)),
            
            # Security sources
            "has_goplus": "goplus" in doc_data.get("security_sources", []),
            "has_rugcheck": "rugcheck" in doc_data.get("security_sources", []),
            "has_solsniffer": "solsniffer" in doc_data.get("security_sources", [])
        }
    
    def _get_price_range(self, price) -> str:
        """Categorize price into ranges for filtering"""
        try:
            if price is None or price == 0:
                return "unknown"
            price_float = float(price)
            if price_float <= 0:
                return "unknown"
            elif price_float < 0.000001:
                return "micro"  # < $0.000001
            elif price_float < 0.0001:
                return "nano"   # < $0.0001
            elif price_float < 0.01:
                return "small"  # < $0.01
            elif price_float < 1.0:
                return "medium" # < $1.00
            elif price_float < 100.0:
                return "large"  # < $100
            else:
                return "huge"   # >= $100
        except (ValueError, TypeError):
            return "unknown"
    
    def _get_volume_range(self, volume) -> str:
        """Categorize volume into ranges for filtering"""
        try:
            if volume is None or volume == 0:
                return "none"
            volume_float = float(volume)
            if volume_float <= 0:
                return "none"
            elif volume_float < 1000:
                return "very_low"    # < $1K
            elif volume_float < 10000:
                return "low"         # < $10K
            elif volume_float < 100000:
                return "medium"      # < $100K
            elif volume_float < 1000000:
                return "high"        # < $1M
            else:
                return "very_high"   # >= $1M
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


# Global instance
analysis_storage = AnalysisStorageService()