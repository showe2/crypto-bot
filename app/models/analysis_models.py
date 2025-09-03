"""
Analysis Models for Profile-based Token Analysis

This module contains the data models used by Analysis Profiles to ensure
compatibility with the existing frontend and database systems.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import time


class AnalysisRunResponse(BaseModel):
    """
    Unified response format for all analysis profiles
    
    This model ensures compatibility with the existing frontend dashboard,
    popup system, and ChromaDB storage while adding profile-specific data.
    """
    
    # Core identifiers
    run_id: str = Field(..., description="Unique analysis run ID")
    status: str = Field(default="completed", description="completed|running|failed")
    analysis_type: str = Field(..., description="twitter|pump|whale|discovery|listing")
    token_address: str = Field(..., description="Token mint address")
    processing_time: float = Field(default=0.0, description="Processing time in seconds")
    estimated_completion: Optional[str] = Field(None, description="ISO datetime for completion")
    
    # Frontend compatibility fields (same as existing dashboard format)
    token_symbol: str = Field(default="Unknown", description="Token symbol")
    token_name: str = Field(default="Unknown Token", description="Token name")
    mint: str = Field(..., description="Same as token_address for backward compatibility")
    timestamp: int = Field(..., description="Unix timestamp")
    risk_level: str = Field(default="medium", description="low|medium|high|critical")
    security_status: str = Field(default="unknown", description="passed|failed|warning")
    overall_score: float = Field(default=0.0, description="0-100 overall score")
    recommendation: str = Field(default="caution", description="consider|caution|avoid")
    critical_issues: int = Field(default=0, description="Number of critical issues")
    warnings: int = Field(default=0, description="Number of warnings")
    source_event: str = Field(..., description="profile_twitter|profile_pump|etc")
    
    # Profile-specific data
    profile_data: Dict[str, Any] = Field(default_factory=dict, description="Profile-specific results")
    
    # Links and actions
    links: Dict[str, str] = Field(default_factory=dict, description="API links")
    
    def __init__(self, **data):
        """Initialize with auto-generated fields"""
        
        # Auto-generate fields that depend on others
        if "mint" not in data and "token_address" in data:
            data["mint"] = data["token_address"]
            
        if "timestamp" not in data:
            data["timestamp"] = int(time.time())
            
        if "run_id" not in data:
            token_addr = data.get("token_address", "unknown")
            token_short = token_addr[:8] if token_addr and len(token_addr) >= 8 else "unknown"
            analysis_type = data.get("analysis_type", "unknown")
            timestamp = data.get("timestamp", int(time.time()))
            data["run_id"] = f"analysis_{analysis_type}_{timestamp}_{token_short}"
            
        if "source_event" not in data:
            analysis_type = data.get("analysis_type", "unknown")
            data["source_event"] = f"profile_{analysis_type}"
        
        # Ensure status is always set
        if "status" not in data:
            data["status"] = "completed"
        
        # Initialize parent
        super().__init__(**data)
        
        # Auto-generate links after initialization
        self.links = {
            "results": f"/api/results/{self.run_id}",
            "logs": f"/api/logs/{self.run_id}",
            "download": f"/document/{self.run_id}"
        }
    
    class Config:
        """Pydantic configuration"""
        validate_assignment = True
        extra = "allow"  # Allow extra fields for extensibility


class ProfileAnalysisMetrics(BaseModel):
    """Common metrics structure for profile analyses"""
    
    # Service execution metrics
    services_attempted: int = 0
    services_successful: int = 0
    data_completeness: float = 0.0
    
    # Analysis quality metrics
    confidence_score: float = 0.0
    data_sources: List[str] = Field(default_factory=list)
    
    # Processing metrics
    ai_analysis_completed: bool = False
    ai_processing_time: float = 0.0
    
    # Profile-specific metrics (extensible)
    profile_specific_metrics: Dict[str, Any] = Field(default_factory=dict)


class TwitterAnalysisMetrics(ProfileAnalysisMetrics):
    """Twitter-specific analysis metrics"""
    
    # Social metrics
    social_score: float = 0.0
    viral_potential: str = "unknown"
    community_strength: str = "unknown"
    
    # Engagement metrics
    followers_count: int = 0
    mentions_24h: int = 0
    sentiment_score: float = 0.0
    viral_score: float = 0.0


class PumpAnalysisMetrics(ProfileAnalysisMetrics):
    """Pump detection specific metrics"""
    
    # Pump indicators
    pump_probability: float = 0.0
    volume_spike_percent: float = 0.0
    price_momentum: float = 0.0
    sustainability_score: float = 50.0
    
    # Risk assessment
    unsustainable_pump: bool = False
    pump_warnings: List[str] = Field(default_factory=list)


class WhaleAnalysisMetrics(ProfileAnalysisMetrics):
    """Whale analysis specific metrics"""
    
    # Whale distribution
    whale_count: int = 0
    whale_control_percent: float = 0.0
    top_whale_percent: float = 0.0
    concentration_risk: str = "unknown"
    
    # Risk assessment
    distribution_score: float = 50.0
    dump_risk: str = "medium"
    whale_warnings: List[str] = Field(default_factory=list)


class ListingAnalysisMetrics(ProfileAnalysisMetrics):
    """New listing analysis specific metrics"""
    
    # Listing characteristics
    listing_age_hours: float = 0.0
    early_opportunity: str = "unknown"
    growth_potential: str = "medium"
    listing_quality: str = "unknown"
    
    # Initial metrics
    initial_liquidity: float = 0.0
    early_volume: float = 0.0