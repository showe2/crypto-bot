import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import ValidationError

from app.models.token import (
    TokenMetadata, PriceData, SocialData, OnChainMetrics,
    MistralAnalysis, LlamaAnalysis, AggregatedAnalysis,
    TokenAnalysisRequest, TokenAnalysisResponse, SocialAnalysisRequest,
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
        
        # Test all values are unique
        values = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert len(set(values)) == len(values)
    
    def test_recommendation_type_enum(self):
        """Test RecommendationType enum values"""
        assert RecommendationType.BUY == "BUY"
        assert RecommendationType.HOLD == "HOLD"
        assert RecommendationType.SELL == "SELL"
        assert RecommendationType.AVOID == "AVOID"
        
        # Test all values are unique
        values = [RecommendationType.BUY, RecommendationType.HOLD, 
                 RecommendationType.SELL, RecommendationType.AVOID]
        assert len(set(values)) == len(values)
    
    def test_social_platform_enum(self):
        """Test SocialPlatform enum values"""
        assert SocialPlatform.TWITTER == "twitter"
        assert SocialPlatform.TELEGRAM == "telegram"
        assert SocialPlatform.DISCORD == "discord"
        assert SocialPlatform.REDDIT == "reddit"
    
    def test_analysis_pattern_enum(self):
        """Test AnalysisPattern enum values"""
        assert AnalysisPattern.BREAKOUT == "breakout"
        assert AnalysisPattern.VOLUME_SPIKE == "volume_spike"
        assert AnalysisPattern.WHALE_MOVEMENT == "whale_movement"
        assert AnalysisPattern.SOCIAL_BUZZ == "social_buzz"
        assert AnalysisPattern.LIQUIDITY_INCREASE == "liquidity_increase"
        assert AnalysisPattern.DEV_ACTIVITY == "dev_activity"


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
    
    def test_token_metadata_with_urls(self):
        """Test token metadata with URLs"""
        metadata = TokenMetadata(
            mint="So11111111111111111111111111111111111112",
            image_uri="https://example.com/image.png",
            website="https://solana.com",
            twitter="https://twitter.com/solana",
            telegram="https://t.me/solana"
        )
        
        assert metadata.image_uri == "https://example.com/image.png"
        assert metadata.website == "https://solana.com"
        assert metadata.twitter == "https://twitter.com/solana"
        assert metadata.telegram == "https://t.me/solana"


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
    
    def test_price_data_timestamp_recent(self):
        """Test that timestamp is recent"""
        price_data = PriceData(current_price=Decimal("100.0"))
        
        now = datetime.utcnow()
        time_diff = abs((now - price_data.timestamp).total_seconds())
        assert time_diff < 1.0  # Should be within 1 second


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
        for invalid_score in [-1.5, 1.5, -2.0, 2.0]:
            with pytest.raises(ValidationError):
                SocialData(
                    platform=SocialPlatform.TWITTER,
                    content="Test content",
                    timestamp=timestamp,
                    sentiment_score=invalid_score
                )
    
    def test_social_data_with_minimal_data(self):
        """Test social data with minimal required fields"""
        timestamp = datetime.utcnow()
        social_data = SocialData(
            platform=SocialPlatform.TELEGRAM,
            content="Minimal data test",
            timestamp=timestamp
        )
        
        assert social_data.platform == SocialPlatform.TELEGRAM
        assert social_data.content == "Minimal data test"
        assert social_data.timestamp == timestamp
        assert social_data.author is None
        assert social_data.metrics == {}
        assert social_data.sentiment_score is None
        assert social_data.keywords == []


@pytest.mark.unit
class TestOnChainMetrics:
    """Test OnChainMetrics model"""
    
    def test_valid_onchain_metrics(self):
        """Test creating valid on-chain metrics"""
        metrics = OnChainMetrics(
            token_address="So11111111111111111111111111111111111112",
            tx_count_24h=5000,
            unique_traders_24h=500,
            liquidity_pools=[
                {"dex": "Raydium", "liquidity": "1000000"},
                {"dex": "Orca", "liquidity": "500000"}
            ],
            total_liquidity=Decimal("1500000"),
            top_holders=[
                {"address": "holder1", "percentage": 10.5},
                {"address": "holder2", "percentage": 8.2}
            ],
            holder_distribution={"1-10": 100, "10-100": 50, "100+": 10},
            is_verified=True,
            security_score=0.85
        )
        
        assert metrics.token_address == "So11111111111111111111111111111111111112"
        assert metrics.tx_count_24h == 5000
        assert metrics.unique_traders_24h == 500
        assert len(metrics.liquidity_pools) == 2
        assert metrics.total_liquidity == Decimal("1500000")
        assert len(metrics.top_holders) == 2
        assert metrics.holder_distribution == {"1-10": 100, "10-100": 50, "100+": 10}
        assert metrics.is_verified == True
        assert metrics.security_score == 0.85
        assert isinstance(metrics.timestamp, datetime)
    
    def test_onchain_metrics_security_score_validation(self):
        """Test security score validation"""
        # Valid security scores
        for score in [0.0, 0.5, 1.0]:
            metrics = OnChainMetrics(
                token_address="So11111111111111111111111111111111111112",
                security_score=score
            )
            assert metrics.security_score == score
        
        # Invalid security scores
        for invalid_score in [-0.1, 1.1, -1.0, 2.0]:
            with pytest.raises(ValidationError):
                OnChainMetrics(
                    token_address="So11111111111111111111111111111111111112",
                    security_score=invalid_score
                )


@pytest.mark.unit
class TestMistralAnalysis:
    """Test MistralAnalysis model"""
    
    def test_valid_mistral_analysis(self):
        """Test creating valid Mistral analysis"""
        analysis = MistralAnalysis(
            score=0.75,
            risk_level=RiskLevel.MEDIUM,
            is_scam_likely=False,
            key_points=["Good liquidity", "Active community", "Strong fundamentals"],
            notes="Overall positive outlook",
            processing_time=1.5,
            confidence=0.85
        )
        
        assert analysis.score == 0.75
        assert analysis.risk_level == RiskLevel.MEDIUM
        assert analysis.is_scam_likely == False
        assert len(analysis.key_points) == 3
        assert analysis.notes == "Overall positive outlook"
        assert analysis.processing_time == 1.5
        assert analysis.confidence == 0.85
    
    def test_mistral_analysis_score_validation(self):
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
        for invalid_score in [-0.1, 1.1, -1.0, 2.0]:
            with pytest.raises(ValidationError):
                MistralAnalysis(
                    score=invalid_score,
                    risk_level=RiskLevel.LOW,
                    processing_time=1.0,
                    confidence=0.5
                )
    
    def test_mistral_analysis_confidence_validation(self):
        """Test confidence validation boundaries"""
        # Valid confidence values
        for confidence in [0.0, 0.5, 1.0]:
            analysis = MistralAnalysis(
                score=0.5,
                risk_level=RiskLevel.MEDIUM,
                processing_time=1.0,
                confidence=confidence
            )
            assert analysis.confidence == confidence
        
        # Invalid confidence values
        for invalid_confidence in [-0.1, 1.1, -1.0, 2.0]:
            with pytest.raises(ValidationError):
                MistralAnalysis(
                    score=0.5,
                    risk_level=RiskLevel.MEDIUM,
                    processing_time=1.0,
                    confidence=invalid_confidence
                )
    
    def test_mistral_analysis_minimal_data(self):
        """Test Mistral analysis with minimal required fields"""
        analysis = MistralAnalysis(
            score=0.6,
            risk_level=RiskLevel.HIGH,
            processing_time=2.0,
            confidence=0.7
        )
        
        assert analysis.score == 0.6
        assert analysis.risk_level == RiskLevel.HIGH
        assert analysis.is_scam_likely == False  # Default value
        assert analysis.key_points == []  # Default empty list
        assert analysis.notes is None
        assert analysis.processing_time == 2.0
        assert analysis.confidence == 0.7


@pytest.mark.unit
class TestLlamaAnalysis:
    """Test LlamaAnalysis model"""
    
    def test_valid_llama_analysis(self):
        """Test creating valid LLaMA analysis"""
        analysis = LlamaAnalysis(
            pump_probability_1h=0.3,
            pump_probability_24h=0.6,
            patterns=[AnalysisPattern.VOLUME_SPIKE, AnalysisPattern.SOCIAL_BUZZ],
            price_targets={"1h": Decimal("105.0"), "24h": Decimal("120.0"), "7d": Decimal("150.0")},
            reasoning="Strong fundamentals with increasing volume and positive social sentiment",
            risk_factors=["Market volatility", "Regulatory uncertainty"],
            opportunities=["Growing adoption", "Technical breakout potential"],
            processing_time=5.2,
            confidence=0.9
        )
        
        assert analysis.pump_probability_1h == 0.3
        assert analysis.pump_probability_24h == 0.6
        assert len(analysis.patterns) == 2
        assert AnalysisPattern.VOLUME_SPIKE in analysis.patterns
        assert AnalysisPattern.SOCIAL_BUZZ in analysis.patterns
        assert analysis.price_targets["1h"] == Decimal("105.0")
        assert analysis.price_targets["24h"] == Decimal("120.0")
        assert len(analysis.reasoning) > 0
        assert len(analysis.risk_factors) == 2
        assert len(analysis.opportunities) == 2
        assert analysis.processing_time == 5.2
        assert analysis.confidence == 0.9
    
    def test_llama_analysis_probability_validation(self):
        """Test probability validation"""
        # Valid probabilities
        for prob in [0.0, 0.5, 1.0]:
            analysis = LlamaAnalysis(
                pump_probability_1h=prob,
                pump_probability_24h=prob,
                reasoning="Test reasoning",
                processing_time=1.0,
                confidence=0.5
            )
            assert analysis.pump_probability_1h == prob
            assert analysis.pump_probability_24h == prob
        
        # Invalid probabilities
        for invalid_prob in [-0.1, 1.1, -1.0, 2.0]:
            with pytest.raises(ValidationError):
                LlamaAnalysis(
                    pump_probability_1h=invalid_prob,
                    pump_probability_24h=0.5,
                    reasoning="Test reasoning",
                    processing_time=1.0,
                    confidence=0.5
                )
    
    def test_llama_analysis_minimal_data(self):
        """Test LLaMA analysis with minimal required fields"""
        analysis = LlamaAnalysis(
            pump_probability_1h=0.4,
            pump_probability_24h=0.7,
            reasoning="Basic analysis",
            processing_time=3.0,
            confidence=0.8
        )
        
        assert analysis.pump_probability_1h == 0.4
        assert analysis.pump_probability_24h == 0.7
        assert analysis.patterns == []  # Default empty list
        assert analysis.price_targets == {}  # Default empty dict
        assert analysis.reasoning == "Basic analysis"
        assert analysis.risk_factors == []  # Default empty list
        assert analysis.opportunities == []  # Default empty list
        assert analysis.processing_time == 3.0
        assert analysis.confidence == 0.8


@pytest.mark.unit
class TestAggregatedAnalysis:
    """Test AggregatedAnalysis model"""
    
    def test_valid_aggregated_analysis(self):
        """Test creating valid aggregated analysis"""
        analysis = AggregatedAnalysis(
            final_score=0.8,
            recommendation=RecommendationType.BUY,
            confidence=0.85,
            expected_return_1h=5.0,
            expected_return_24h=15.0,
            max_risk=0.3,
            summary="Strong buy signal with good fundamentals and positive market sentiment",
            action_plan=["Monitor volume closely", "Set stop loss at 95", "Take profits at 130"]
        )
        
        assert analysis.final_score == 0.8
        assert analysis.recommendation == RecommendationType.BUY
        assert analysis.confidence == 0.85
        assert analysis.expected_return_1h == 5.0
        assert analysis.expected_return_24h == 15.0
        assert analysis.max_risk == 0.3
        assert len(analysis.summary) > 0
        assert len(analysis.action_plan) == 3
    
    def test_aggregated_analysis_validation(self):
        """Test validation of aggregated analysis fields"""
        # Test final_score validation
        for invalid_score in [-0.1, 1.1, -1.0, 2.0]:
            with pytest.raises(ValidationError):
                AggregatedAnalysis(
                    final_score=invalid_score,
                    recommendation=RecommendationType.HOLD,
                    confidence=0.5,
                    max_risk=0.3,
                    summary="Test summary"
                )
        
        # Test confidence validation
        for invalid_confidence in [-0.1, 1.1]:
            with pytest.raises(ValidationError):
                AggregatedAnalysis(
                    final_score=0.5,
                    recommendation=RecommendationType.HOLD,
                    confidence=invalid_confidence,
                    max_risk=0.3,
                    summary="Test summary"
                )
        
        # Test max_risk validation
        for invalid_risk in [-0.1, 1.1]:
            with pytest.raises(ValidationError):
                AggregatedAnalysis(
                    final_score=0.5,
                    recommendation=RecommendationType.HOLD,
                    confidence=0.5,
                    max_risk=invalid_risk,
                    summary="Test summary"
                )


@pytest.mark.unit
class TestTokenAnalysisRequest:
    """Test TokenAnalysisRequest model"""
    
    def test_valid_token_analysis_request(self):
        """Test creating valid token analysis request"""
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
    
    def test_token_analysis_request_priority_validation(self):
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


@pytest.mark.unit
class TestTokenAnalysisResponse:
    """Test TokenAnalysisResponse model"""
    
    def test_valid_token_analysis_response(self):
        """Test creating valid token analysis response"""
        metadata = TokenMetadata(
            mint="So11111111111111111111111111111111111112",
            name="Test Token",
            symbol="TEST"
        )
        
        price_data = PriceData(current_price=Decimal("100.0"))
        
        mistral_analysis = MistralAnalysis(
            score=0.8,
            risk_level=RiskLevel.LOW,
            processing_time=1.5,
            confidence=0.9
        )
        
        response = TokenAnalysisResponse(
            token="So11111111111111111111111111111111111112",
            metadata=metadata,
            price_data=price_data,
            mistral_quick=mistral_analysis,
            analysis_id="test_analysis_123",
            processing_time_total=5.5,
            data_sources=["helius", "birdeye"],
            warnings=["Low liquidity warning"],
            errors=[]
        )
        
        assert response.token == "So11111111111111111111111111111111111112"
        assert response.metadata.name == "Test Token"
        assert response.price_data.current_price == Decimal("100.0")
        assert response.mistral_quick.score == 0.8
        assert response.analysis_id == "test_analysis_123"
        assert response.processing_time_total == 5.5
        assert len(response.data_sources) == 2
        assert len(response.warnings) == 1
        assert len(response.errors) == 0
        assert isinstance(response.timestamp, datetime)
    
    def test_token_analysis_response_minimal(self):
        """Test token analysis response with minimal data"""
        response = TokenAnalysisResponse(
            token="So11111111111111111111111111111111111112",
            analysis_id="minimal_test",
            processing_time_total=2.0
        )
        
        assert response.token == "So11111111111111111111111111111111111112"
        assert response.metadata is None
        assert response.price_data is None
        assert response.onchain_metrics is None
        assert response.social_data == []  # Default empty list
        assert response.analysis == {}  # Default empty dict
        assert response.mistral_quick is None
        assert response.llama_deep is None
        assert response.aggregated is None
        assert response.analysis_id == "minimal_test"
        assert response.processing_time_total == 2.0
        assert response.data_sources == []  # Default empty list
        assert response.warnings == []  # Default empty list
        assert response.errors == []  # Default empty list
        assert isinstance(response.timestamp, datetime)


@pytest.mark.unit
class TestSocialAnalysisRequest:
    """Test SocialAnalysisRequest model"""
    
    def test_valid_social_analysis_request(self):
        """Test creating valid social analysis request"""
        request = SocialAnalysisRequest(
            token_symbol="SOL",
            token_mint="So11111111111111111111111111111111111112",
            keywords=["solana", "crypto", "blockchain"],
            platforms=[SocialPlatform.TWITTER, SocialPlatform.TELEGRAM],
            time_range_hours=48
        )
        
        assert request.token_symbol == "SOL"
        assert request.token_mint == "So11111111111111111111111111111111111112"
        assert len(request.keywords) == 3
        assert len(request.platforms) == 2
        assert request.time_range_hours == 48
    
    def test_social_analysis_request_defaults(self):
        """Test default values in social analysis request"""
        request = SocialAnalysisRequest()
        
        assert request.token_symbol is None
        assert request.token_mint is None
        assert request.keywords == []  # Default empty list
        assert len(request.platforms) == 2  # Default Twitter and Telegram
        assert SocialPlatform.TWITTER in request.platforms
        assert SocialPlatform.TELEGRAM in request.platforms
        assert request.time_range_hours == 24  # Default
    
    def test_social_analysis_request_time_range_validation(self):
        """Test time range validation"""
        # Valid time ranges
        for hours in [1, 24, 72, 168]:  # 1 hour to 1 week
            request = SocialAnalysisRequest(time_range_hours=hours)
            assert request.time_range_hours == hours
        
        # Invalid time ranges
        for invalid_hours in [0, 169, -1, 200]:
            with pytest.raises(ValidationError):
                SocialAnalysisRequest(time_range_hours=invalid_hours)


@pytest.mark.unit
class TestModelRelationships:
    """Test relationships between models"""
    
    def test_complete_analysis_workflow(self):
        """Test complete analysis workflow with all models"""
        # 1. Create analysis request
        request = TokenAnalysisRequest(
            mint="So11111111111111111111111111111111111112",
            include_social=True,
            include_deep_analysis=True,
            priority="high"
        )
        
        # 2. Create token metadata
        metadata = TokenMetadata(
            mint=request.mint,
            name="Wrapped SOL",
            symbol="WSOL",
            decimals=9
        )
        
        # 3. Create price data
        price_data = PriceData(
            current_price=Decimal("100.0"),
            price_change_24h=Decimal("5.0"),
            volume_24h=Decimal("1000000")
        )
        
        # 4. Create social data
        social_data = [
            SocialData(
                platform=SocialPlatform.TWITTER,
                content="WSOL looking strong! 🚀",
                timestamp=datetime.utcnow(),
                sentiment_score=0.8
            ),
            SocialData(
                platform=SocialPlatform.TELEGRAM,
                content="Great project with solid fundamentals",
                timestamp=datetime.utcnow(),
                sentiment_score=0.7
            )
        ]
        
        # 5. Create analyses
        mistral_analysis = MistralAnalysis(
            score=0.8,
            risk_level=RiskLevel.LOW,
            key_points=["Strong price action", "Positive sentiment"],
            processing_time=1.5,
            confidence=0.9
        )
        
        llama_analysis = LlamaAnalysis(
            pump_probability_1h=0.3,
            pump_probability_24h=0.6,
            patterns=[AnalysisPattern.VOLUME_SPIKE, AnalysisPattern.SOCIAL_BUZZ],
            reasoning="Technical and fundamental analysis shows positive outlook",
            processing_time=5.0,
            confidence=0.85
        )
        
        aggregated_analysis = AggregatedAnalysis(
            final_score=0.82,
            recommendation=RecommendationType.BUY,
            confidence=0.87,
            expected_return_24h=12.0,
            max_risk=0.25,
            summary="Strong buy signal based on technical and social analysis"
        )
        
        # 6. Create final response
        response = TokenAnalysisResponse(
            token=request.mint,
            metadata=metadata,
            price_data=price_data,
            social_data=social_data,
            mistral_quick=mistral_analysis,
            llama_deep=llama_analysis,
            aggregated=aggregated_analysis,
            analysis_id="workflow_test_123",
            processing_time_total=7.5,
            data_sources=["helius", "birdeye", "twitter_api"],
            warnings=[],
            errors=[]
        )
        
        # Verify complete workflow
        assert response.token == request.mint
        assert response.metadata.mint == request.mint
        assert response.price_data.current_price > 0
        assert len(response.social_data) == 2
        assert response.mistral_quick.score > 0
        assert response.llama_deep.pump_probability_24h > 0
        assert response.aggregated.recommendation == RecommendationType.BUY
        assert response.processing_time_total > 0
        assert len(response.data_sources) == 3
    
    def test_model_serialization(self):
        """Test that models can be serialized/deserialized"""
        # Test with complex model
        analysis = LlamaAnalysis(
            pump_probability_1h=0.4,
            pump_probability_24h=0.7,
            patterns=[AnalysisPattern.BREAKOUT, AnalysisPattern.WHALE_MOVEMENT],
            price_targets={"1h": Decimal("110"), "24h": Decimal("125")},
            reasoning="Technical breakout with whale activity",
            risk_factors=["Market volatility"],
            opportunities=["Technical momentum"],
            processing_time=4.2,
            confidence=0.88
        )
        
        # Should be able to convert to dict
        analysis_dict = analysis.model_dump()
        assert isinstance(analysis_dict, dict)
        assert analysis_dict["pump_probability_1h"] == 0.4
        assert analysis_dict["patterns"] == ["breakout", "whale_movement"]
        
        # Should be able to recreate from dict
        recreated_analysis = LlamaAnalysis(**analysis_dict)
        assert recreated_analysis.pump_probability_1h == analysis.pump_probability_1h
        assert recreated_analysis.patterns == analysis.patterns
        assert recreated_analysis.confidence == analysis.confidence


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])