import pytest
from datetime import datetime
from decimal import Decimal
from pydantic import ValidationError

from app.models.token import (
    TokenMetadata, PriceData, SocialData, OnChainMetrics,
    MistralAnalysis, LlamaAnalysis, AggregatedAnalysis,
    TokenAnalysisRequest, TokenAnalysisResponse,
    RiskLevel, RecommendationType, SocialPlatform, AnalysisPattern
)


@pytest.mark.unit
class TestEnums:
    """Test enum models"""
    
    def test_risk_level_enum(self):
        """Test RiskLevel enum values"""
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"
    
    def test_recommendation_type_enum(self):
        """Test RecommendationType enum values"""
        assert RecommendationType.BUY == "BUY"
        assert RecommendationType.HOLD == "HOLD"
        assert RecommendationType.SELL == "SELL"
        assert RecommendationType.AVOID == "AVOID"
    
    def test_social_platform_enum(self):
        """Test SocialPlatform enum values"""
        assert SocialPlatform.TWITTER == "twitter"
        assert SocialPlatform.TELEGRAM == "telegram"
        assert SocialPlatform.DISCORD == "discord"
        assert SocialPlatform.REDDIT == "reddit"


@pytest.mark.unit
class TestTokenMetadata:
    """Test TokenMetadata model"""
    
    def test_valid_token_metadata(self):
        """Test creating valid token metadata"""
        metadata = TokenMetadata(
            mint="So11111111111111111111111111111111111112",
            name="Wrapped SOL",
            symbol="WSOL",
            decimals=9,
            supply=Decimal("1000000"),
            description="Wrapped Solana token"
        )
        
        assert metadata.mint == "So11111111111111111111111111111111111112"
        assert metadata.name == "Wrapped SOL"
        assert metadata.symbol == "WSOL"
        assert metadata.decimals == 9
        assert metadata.supply == Decimal("1000000")
        assert metadata.description == "Wrapped Solana token"
    
    def test_token_metadata_with_minimal_data(self):
        """Test token metadata with only required fields"""
        metadata = TokenMetadata(
            mint="So11111111111111111111111111111111111112"
        )
        
        assert metadata.mint == "So11111111111111111111111111111111111112"
        assert metadata.name is None
        assert metadata.symbol is None
        assert metadata.decimals == 9  # Default value
        assert metadata.supply is None
    
    def test_token_metadata_mint_validation(self):
        """Test token metadata mint validation"""
        # Valid mint
        metadata = TokenMetadata(mint="So11111111111111111111111111111111111112")
        assert metadata.mint == "So11111111111111111111111111111111111112"
        
        # Invalid mint - too short
        with pytest.raises(ValueError, match="Invalid mint address"):
            TokenMetadata(mint="short")
        
        # Invalid mint - empty
        with pytest.raises(ValueError, match="Invalid mint address"):
            TokenMetadata(mint="")


@pytest.mark.unit
class TestPriceData:
    """Test PriceData model"""
    
    def test_valid_price_data(self):
        """Test creating valid price data"""
        price_data = PriceData(
            current_price=Decimal("100.50"),
            price_change_1h=Decimal("2.5"),
            price_change_24h=Decimal("5.2"),
            price_change_7d=Decimal("-1.8"),
            volume_24h=Decimal("1000000"),
            market_cap=Decimal("50000000"),
            liquidity=Decimal("5000000"),
            holders_count=1000
        )
        
        assert price_data.current_price == Decimal("100.50")
        assert price_data.price_change_1h == Decimal("2.5")
        assert price_data.price_change_24h == Decimal("5.2")
        assert price_data.price_change_7d == Decimal("-1.8")
        assert price_data.volume_24h == Decimal("1000000")
        assert price_data.market_cap == Decimal("50000000")
        assert price_data.liquidity == Decimal("5000000")
        assert price_data.holders_count == 1000
        assert isinstance(price_data.timestamp, datetime)
    
    def test_price_data_with_minimal_data(self):
        """Test price data with only required field"""
        price_data = PriceData(current_price=Decimal("50.25"))
        
        assert price_data.current_price == Decimal("50.25")
        assert price_data.price_change_1h is None
        assert price_data.price_change_24h is None
        assert price_data.volume_24h is None
        assert isinstance(price_data.timestamp, datetime)


@pytest.mark.unit
class TestSocialData:
    """Test SocialData model"""
    
    def test_valid_social_data(self):
        """Test creating valid social data"""
        timestamp = datetime.utcnow()
        social_data = SocialData(
            platform=SocialPlatform.TWITTER,
            content="Great token! 🚀 #crypto",
            author="crypto_user",
            timestamp=timestamp,
            metrics={"likes": 100, "retweets": 50, "replies": 25},
            sentiment_score=0.8,
            keywords=["great", "token", "crypto"]
        )
        
        assert social_data.platform == SocialPlatform.TWITTER
        assert social_data.content == "Great token! 🚀 #crypto"
        assert social_data.author == "crypto_user"
        assert social_data.timestamp == timestamp
        assert social_data.metrics == {"likes": 100, "retweets": 50, "replies": 25}
        assert social_data.sentiment_score == 0.8
        assert social_data.keywords == ["great", "token", "crypto"]
    
    def test_social_data_sentiment_validation(self):
        """Test sentiment score validation"""
        timestamp = datetime.utcnow()
        
        # Valid sentiment scores
        for score in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            social_data = SocialData(
                platform=SocialPlatform.TWITTER,
                content="Test content",
                timestamp=timestamp,
                sentiment_score=score
            )
            assert social_data.sentiment_score == score
        
        # Invalid sentiment scores
        for invalid_score in [-1.5, 1.5]:
            with pytest.raises(ValidationError):
                SocialData(
                    platform=SocialPlatform.TWITTER,
                    content="Test content",
                    timestamp=timestamp,
                    sentiment_score=invalid_score
                )


@pytest.mark.unit
class TestAnalysisModels:
    """Test analysis models"""
    
    def test_mistral_analysis(self):
        """Test MistralAnalysis model"""
        analysis = MistralAnalysis(
            score=0.75,
            risk_level=RiskLevel.MEDIUM,
            is_scam_likely=False,
            key_points=["Good liquidity", "Active community"],
            processing_time=1.5,
            confidence=0.85
        )
        
        assert analysis.score == 0.75
        assert analysis.risk_level == RiskLevel.MEDIUM
        assert analysis.is_scam_likely == False
        assert len(analysis.key_points) == 2
        assert analysis.processing_time == 1.5
        assert analysis.confidence == 0.85
    
    def test_llama_analysis(self):
        """Test LlamaAnalysis model"""
        analysis = LlamaAnalysis(
            pump_probability_1h=0.3,
            pump_probability_24h=0.6,
            patterns=[AnalysisPattern.VOLUME_SPIKE, AnalysisPattern.SOCIAL_BUZZ],
            price_targets={"1h": Decimal("105.0"), "24h": Decimal("120.0")},
            reasoning="Strong fundamentals with increasing volume",
            processing_time=5.2,
            confidence=0.9
        )
        
        assert analysis.pump_probability_1h == 0.3
        assert analysis.pump_probability_24h == 0.6
        assert len(analysis.patterns) == 2
        assert AnalysisPattern.VOLUME_SPIKE in analysis.patterns
        assert analysis.price_targets["1h"] == Decimal("105.0")
        assert len(analysis.reasoning) > 0
        assert analysis.processing_time == 5.2
        assert analysis.confidence == 0.9
    
    def test_aggregated_analysis(self):
        """Test AggregatedAnalysis model"""
        analysis = AggregatedAnalysis(
            final_score=0.8,
            recommendation=RecommendationType.BUY,
            confidence=0.85,
            expected_return_1h=5.0,
            expected_return_24h=15.0,
            max_risk=0.3,
            summary="Strong buy signal with good fundamentals"
        )
        
        assert analysis.final_score == 0.8
        assert analysis.recommendation == RecommendationType.BUY
        assert analysis.confidence == 0.85
        assert analysis.expected_return_1h == 5.0
        assert analysis.expected_return_24h == 15.0
        assert analysis.max_risk == 0.3
        assert len(analysis.summary) > 0


@pytest.mark.unit
class TestRequestResponse:
    """Test request and response models"""
    
    def test_token_analysis_request(self):
        """Test TokenAnalysisRequest model"""
        request = TokenAnalysisRequest(
            mint="So11111111111111111111111111111111111112",
            include_social=True,
            include_deep_analysis=False,
            priority="high"
        )
        
        assert request.mint == "So11111111111111111111111111111111111112"
        assert request.include_social == True
        assert request.include_deep_analysis == False
        assert request.priority == "high"
    
    def test_token_analysis_request_defaults(self):
        """Test default values in token analysis request"""
        request = TokenAnalysisRequest(
            mint="So11111111111111111111111111111111111112"
        )
        
        assert request.mint == "So11111111111111111111111111111111111112"
        assert request.include_social == True  # Default
        assert request.include_deep_analysis == True  # Default
        assert request.priority == "normal"  # Default
    
    def test_token_analysis_response(self):
        """Test TokenAnalysisResponse model"""
        metadata = TokenMetadata(
            mint="So11111111111111111111111111111111111112",
            name="Test Token",
            symbol="TEST"
        )
        
        response = TokenAnalysisResponse(
            token="So11111111111111111111111111111111111112",
            metadata=metadata,
            analysis_id="test_analysis_123",
            processing_time_total=5.5,
            data_sources=["helius", "birdeye"],
            warnings=["Low liquidity warning"],
            errors=[]
        )
        
        assert response.token == "So11111111111111111111111111111111111112"
        assert response.metadata.name == "Test Token"
        assert response.analysis_id == "test_analysis_123"
        assert response.processing_time_total == 5.5
        assert len(response.data_sources) == 2
        assert len(response.warnings) == 1
        assert len(response.errors) == 0
        assert isinstance(response.timestamp, datetime)


@pytest.mark.unit
class TestValidation:
    """Test model validation"""
    
    def test_score_validation(self):
        """Test score validation boundaries"""
        # Valid scores
        for score in [0.0, 0.5, 1.0]:
            analysis = MistralAnalysis(
                score=score,
                risk_level=RiskLevel.LOW,
                processing_time=1.0,
                confidence=0.5
            )
            assert analysis.score == score
        
        # Invalid scores
        for invalid_score in [-0.1, 1.1]:
            with pytest.raises(ValidationError):
                MistralAnalysis(
                    score=invalid_score,
                    risk_level=RiskLevel.LOW,
                    processing_time=1.0,
                    confidence=0.5
                )
    
    def test_priority_validation(self):
        """Test priority validation"""
        # Valid priorities
        for priority in ["low", "normal", "high"]:
            request = TokenAnalysisRequest(
                mint="So11111111111111111111111111111111111112",
                priority=priority
            )
            assert request.priority == priority
        
        # Invalid priority
        with pytest.raises(ValidationError):
            TokenAnalysisRequest(
                mint="So11111111111111111111111111111111111112",
                priority="invalid"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])