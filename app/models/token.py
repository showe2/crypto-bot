from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, validator


class RiskLevel(str, Enum):
    """Token risk levels"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


class RecommendationType(str, Enum):
    """Recommendation types"""
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    AVOID = "AVOID"


class SocialPlatform(str, Enum):
    """Social platforms"""
    TWITTER = "twitter"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    REDDIT = "reddit"


class AnalysisPattern(str, Enum):
    """Analysis patterns"""
    BREAKOUT = "breakout"
    VOLUME_SPIKE = "volume_spike"
    WHALE_MOVEMENT = "whale_movement"
    SOCIAL_BUZZ = "social_buzz"
    LIQUIDITY_INCREASE = "liquidity_increase"
    DEV_ACTIVITY = "dev_activity"


# ==============================================
# BASE DATA MODELS
# ==============================================

class TokenMetadata(BaseModel):
    """Token metadata"""
    mint: str = Field(..., description="Token mint address")
    name: Optional[str] = Field(None, description="Token name")
    symbol: Optional[str] = Field(None, description="Token symbol")
    decimals: int = Field(default=9, description="Number of decimals")
    supply: Optional[Decimal] = Field(None, description="Total token supply")
    description: Optional[str] = Field(None, description="Token description")
    image_uri: Optional[str] = Field(None, description="Image URL")
    website: Optional[str] = Field(None, description="Official website")
    twitter: Optional[str] = Field(None, description="Twitter account")
    telegram: Optional[str] = Field(None, description="Telegram channel")
    
    @validator('mint')
    def validate_mint(cls, v):
        """Mint address validation"""
        if not v or len(v) < 32:
            raise ValueError('Invalid mint address')
        return v


class PriceData(BaseModel):
    """Token price data"""
    current_price: Decimal = Field(..., description="Current price in USD")
    price_change_1h: Optional[Decimal] = Field(None, description="1-hour price change (%)")
    price_change_24h: Optional[Decimal] = Field(None, description="24-hour price change (%)")
    price_change_7d: Optional[Decimal] = Field(None, description="7-day price change (%)")
    volume_24h: Optional[Decimal] = Field(None, description="24-hour trading volume")
    market_cap: Optional[Decimal] = Field(None, description="Market capitalization")
    liquidity: Optional[Decimal] = Field(None, description="Liquidity")
    holders_count: Optional[int] = Field(None, description="Number of holders")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SocialData(BaseModel):
    """Social media data"""
    platform: SocialPlatform = Field(..., description="Platform")
    content: str = Field(..., description="Post/message content")
    author: Optional[str] = Field(None, description="Author")
    timestamp: datetime = Field(..., description="Publication time")
    metrics: Dict[str, Union[int, float]] = Field(default_factory=dict, description="Metrics (likes, reposts etc.)")
    sentiment_score: Optional[float] = Field(None, ge=-1, le=1, description="Sentiment score from -1 to 1")
    keywords: List[str] = Field(default_factory=list, description="Keywords")


class OnChainMetrics(BaseModel):
    """Token on-chain metrics"""
    token_address: str = Field(..., description="Token address")
    
    # Transactions
    tx_count_24h: Optional[int] = Field(None, description="24-hour transaction count")
    unique_traders_24h: Optional[int] = Field(None, description="Unique traders in 24h")
    
    # Liquidity
    liquidity_pools: List[Dict[str, Any]] = Field(default_factory=list, description="Liquidity pools")
    total_liquidity: Optional[Decimal] = Field(None, description="Total liquidity")
    
    # Holders
    top_holders: List[Dict[str, Any]] = Field(default_factory=list, description="Top holders")
    holder_distribution: Dict[str, int] = Field(default_factory=dict, description="Holder distribution")
    
    # Security
    is_verified: Optional[bool] = Field(None, description="Whether token is verified")
    security_score: Optional[float] = Field(None, ge=0, le=1, description="Security score")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ==============================================
# ANALYSIS MODELS
# ==============================================

class MistralAnalysis(BaseModel):
    """Mistral 7B quick analysis results"""
    score: float = Field(..., ge=0, le=1, description="Overall token score")
    risk_level: RiskLevel = Field(..., description="Risk level")
    is_scam_likely: bool = Field(default=False, description="Scam likelihood")
    key_points: List[str] = Field(default_factory=list, description="Key points")
    notes: Optional[str] = Field(None, description="Additional notes")
    processing_time: float = Field(..., description="Processing time in seconds")
    confidence: float = Field(..., ge=0, le=1, description="Analysis confidence")


class LlamaAnalysis(BaseModel):
    """LLaMA 3 70B deep analysis results"""
    pump_probability_1h: float = Field(..., ge=0, le=1, description="1-hour pump probability")
    pump_probability_24h: float = Field(..., ge=0, le=1, description="24-hour pump probability")
    patterns: List[AnalysisPattern] = Field(default_factory=list, description="Detected patterns")
    price_targets: Dict[str, Decimal] = Field(default_factory=dict, description="Price targets")
    reasoning: str = Field(..., description="Detailed reasoning")
    risk_factors: List[str] = Field(default_factory=list, description="Risk factors")
    opportunities: List[str] = Field(default_factory=list, description="Opportunities")
    processing_time: float = Field(..., description="Processing time in seconds")
    confidence: float = Field(..., ge=0, le=1, description="Analysis confidence")


class AggregatedAnalysis(BaseModel):
    """Aggregated analysis result"""
    final_score: float = Field(..., ge=0, le=1, description="Final score")
    recommendation: RecommendationType = Field(..., description="Recommendation")
    confidence: float = Field(..., ge=0, le=1, description="Overall confidence")
    expected_return_1h: Optional[float] = Field(None, description="Expected 1-hour return (%)")
    expected_return_24h: Optional[float] = Field(None, description="Expected 24-hour return (%)")
    max_risk: float = Field(..., ge=0, le=1, description="Maximum risk")
    summary: str = Field(..., description="Brief summary")
    action_plan: List[str] = Field(default_factory=list, description="Action plan")


# ==============================================
# MAIN TOKEN ANALYSIS MODEL
# ==============================================

class TokenAnalysisRequest(BaseModel):
    """Token analysis request"""
    mint: str = Field(..., description="Token mint address to analyze")
    include_social: bool = Field(default=True, description="Include social data analysis")
    include_deep_analysis: bool = Field(default=True, description="Include deep LLaMA analysis")
    priority: str = Field(default="normal", description="Analysis priority (low/normal/high)")
    
    @validator('priority')
    def validate_priority(cls, v):
        allowed = ['low', 'normal', 'high']
        if v not in allowed:
            raise ValueError(f'priority must be one of: {allowed}')
        return v


class TokenAnalysisResponse(BaseModel):
    """Complete token analysis result"""
    token: str = Field(..., description="Token mint address")
    metadata: Optional[TokenMetadata] = Field(None, description="Token metadata")
    price_data: Optional[PriceData] = Field(None, description="Price data")
    onchain_metrics: Optional[OnChainMetrics] = Field(None, description="On-chain metrics")
    social_data: List[SocialData] = Field(default_factory=list, description="Social data")
    
    # AI analysis results
    analysis: Dict[str, Any] = Field(default_factory=dict, description="Analysis results")
    mistral_quick: Optional[MistralAnalysis] = Field(None, description="Mistral quick analysis")
    llama_deep: Optional[LlamaAnalysis] = Field(None, description="LLaMA deep analysis")
    aggregated: Optional[AggregatedAnalysis] = Field(None, description="Aggregated result")
    
    # Meta information
    analysis_id: str = Field(..., description="Analysis ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Analysis time")
    processing_time_total: float = Field(..., description="Total processing time")
    data_sources: List[str] = Field(default_factory=list, description="Data sources used")
    warnings: List[str] = Field(default_factory=list, description="Warnings")
    errors: List[str] = Field(default_factory=list, description="Analysis errors")


# ==============================================
# SOCIAL ANALYSIS MODELS  
# ==============================================

class SocialAnalysisRequest(BaseModel):
    """Social signals analysis request"""
    token_symbol: Optional[str] = Field(None, description="Token symbol")
    token_mint: Optional[str] = Field(None, description="Token mint address")
    keywords: List[str] = Field(default_factory=list, description="Additional keywords")
    platforms: List[SocialPlatform] = Field(default_factory=lambda: [SocialPlatform.TWITTER, SocialPlatform.TELEGRAM])
    time_range_hours: int = Field(default=24, ge=1, le=168, description="Time range in hours")


class SocialAnalysisResponse(BaseModel):
    """Social signals analysis result"""
    token_info: Dict[str, str] = Field(default_factory=dict, description="Token information")
    social_data: List[SocialData] = Field(default_factory=list, description="Collected social data")
    
    # Analytics
    total_mentions: int = Field(default=0, description="Total mentions count")
    sentiment_average: float = Field(default=0.0, ge=-1, le=1, description="Average sentiment")
    viral_score: float = Field(default=0.0, ge=0, le=1, description="Virality score")
    top_keywords: List[str] = Field(default_factory=list, description="Top keywords")
    platform_breakdown: Dict[str, int] = Field(default_factory=dict, description="Platform breakdown")
    
    # Temporal dynamics
    hourly_activity: Dict[str, int] = Field(default_factory=dict, description="Hourly activity")
    trend_direction: str = Field(default="neutral", description="Trend direction")
    
    # Meta information
    analysis_id: str = Field(..., description="Analysis ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time: float = Field(..., description="Processing time")