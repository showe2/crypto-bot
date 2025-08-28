import asyncio
import json
from app.services.ai.ai_service import analyze_token_with_ai

async def test_ai_integration():
    """Test AI integration with sample data"""
    
    # Sample token data
    test_data = {
        "service_responses": {
            "birdeye": {
                "price": {
                    "value": 0.000001234,
                    "market_cap": 500000,
                    "liquidity": 150000,
                    "volume_24h": 25000,
                    "price_change_24h": 15.5
                }
            }
        },
        "security_analysis": {
            "overall_safe": True,
            "critical_issues": [],
            "warnings": ["Low liquidity detected"]
        }
    }
    
    print("🧪 Testing AI integration...")
    
    try:
        result = await analyze_token_with_ai(
            token_address="So11111111111111111111111111111111111112",
            service_responses=test_data["service_responses"],
            security_analysis=test_data["security_analysis"],
            analysis_type="deep"
        )
        
        if result:
            print("✅ AI Analysis successful!")
            print(f"AI Score: {result.ai_score}")
            print(f"Recommendation: {result.recommendation}")
            print(f"Risk Assessment: {result.risk_assessment}")
            print(f"Processing Time: {result.processing_time:.2f}s")
            print("\nKey Insights:")
            for insight in result.key_insights:
                print(f"  • {insight}")
        else:
            print("❌ AI Analysis returned None")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_ai_integration())