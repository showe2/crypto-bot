from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from loguru import logger
import time

from app.services.service_manager import (
    api_manager, 
    get_token_analysis, 
    get_api_health_status,
    search_for_tokens,
    get_trending_analysis
)
from app.core.dependencies import rate_limit_per_ip
from app.models.token import TokenAnalysisRequest, TokenAnalysisResponse

router = APIRouter(prefix="/api", tags=["API Services"])


@router.get("/health", summary="API Services Health Check")
async def api_services_health():
    """
    Check health status of all external API services including GOplus
    """
    try:
        health_status = await get_api_health_status()
        
        # Determine HTTP status code based on overall health
        status_code = 200 if health_status.get("overall_healthy") else 503
        
        return JSONResponse(
            content=health_status,
            status_code=status_code
        )
    except Exception as e:
        logger.error(f"Error checking API health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/token", response_model=TokenAnalysisResponse, summary="Comprehensive Token Analysis")
async def analyze_token(
    request: TokenAnalysisRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(rate_limit_per_ip)
):
    """
    Perform comprehensive token analysis using all available data sources including GOplus
    
    This endpoint aggregates data from multiple APIs:
    - Helius: On-chain data and metadata
    - Chainbase: Holder analysis and smart contract data
    - Birdeye: Price data and market information
    - Blowfish: Security analysis and risk assessment
    - DataImpulse: Social sentiment analysis
    - Solscan: Additional on-chain metrics
    - GOplus: Transaction simulation, rugpull detection, and token security
    """
    start_time = time.time()
    
    try:
        # Check cache first
        from app.core.dependencies import get_cache_dependency
        cache = await get_cache_dependency()
        
        cache_key = f"token_analysis:{request.mint}:{request.priority}"
        cached_result = await cache.get(cache_key, namespace="analysis")
        
        if cached_result and not request.priority == "high":
            logger.info(f"📋 Returning cached analysis for {request.mint}")
            return cached_result
        
        # Perform comprehensive analysis
        logger.info(f"🔍 Starting comprehensive analysis for {request.mint}")
        
        comprehensive_data = await get_token_analysis(request.mint)
        
        if not comprehensive_data or "error" in comprehensive_data:
            raise HTTPException(
                status_code=422, 
                detail=f"Failed to analyze token: {comprehensive_data.get('error', 'Unknown error')}"
            )
        
        processing_time = time.time() - start_time
        
        # Transform to response format
        analysis_response = TokenAnalysisResponse(
            token=request.mint,
            analysis_id=f"analysis_{int(time.time())}",
            processing_time_total=processing_time,
            data_sources=comprehensive_data.get("data_sources", []),
            **_transform_comprehensive_data(comprehensive_data)
        )
        
        # Cache result
        cache_ttl = 300 if request.priority == "normal" else 60  # 5min normal, 1min high priority
        await cache.set(cache_key, analysis_response.dict(), ttl=cache_ttl, namespace="analysis")
        
        # Log analysis for monitoring
        logger.info(
            f"✅ Token analysis completed for {request.mint}",
            extra={
                "token_analysis": True,
                "token_mint": request.mint,
                "processing_time": processing_time,
                "data_sources": len(comprehensive_data.get("data_sources", [])),
                "priority": request.priority,
                "goplus_included": "goplus" in comprehensive_data.get("data_sources", [])
            }
        )
        
        return analysis_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Token analysis failed for {request.mint}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze/security/goplus", summary="GOplus Security Analysis")
async def analyze_token_security_goplus(
    token_address: str,
    _: None = Depends(rate_limit_per_ip)
):
    """
    Perform comprehensive security analysis using GOplus services
    
    Uses GOplus APIs for:
    - Token security analysis
    - Rugpull detection
    - Transaction simulation capabilities
    """
    try:
        # Get cache dependency
        from app.core.dependencies import get_cache_dependency
        cache = await get_cache_dependency()
        
        # Check cache
        cache_key = f"goplus_security:{token_address}"
        cached_results = await cache.get(cache_key, namespace="security")
        
        if cached_results:
            logger.info(f"📋 Returning cached GOplus security analysis for {token_address}")
            return cached_results
        
        # Perform GOplus analysis
        logger.info(f"🔒 Running GOplus security analysis for {token_address}")
        
        security_data = await api_manager.get_goplus_analysis(token_address)
        
        if not security_data or "error" in security_data:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to analyze token security with GOplus: {security_data.get('error', 'Unknown error')}"
            )
        
        # Cache for 1 hour (security data doesn't change frequently)
        await cache.set(cache_key, security_data, ttl=3600, namespace="security")
        
        return security_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ GOplus security analysis failed for {token_address}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"GOplus security analysis failed: {str(e)}")


@router.post("/simulate/transaction", summary="Transaction Simulation with GOplus")
async def simulate_transaction(
    transaction_data: Dict[str, Any],
    _: None = Depends(rate_limit_per_ip)
):
    """
    Simulate a transaction before execution using GOplus
    
    Provides:
    - Gas estimation
    - Balance changes prediction
    - Risk assessment
    - Security warnings
    """
    try:
        logger.info("🎯 Simulating transaction with GOplus")
        
        simulation_result = await api_manager.simulate_transaction_goplus(transaction_data)
        
        if not simulation_result or "error" in simulation_result:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to simulate transaction: {simulation_result.get('error', 'Unknown error')}"
            )
        
        return simulation_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Transaction simulation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transaction simulation failed: {str(e)}")


@router.post("/detect/rugpull", summary="Rugpull Detection with GOplus")
async def detect_rugpull(
    token_address: str,
    _: None = Depends(rate_limit_per_ip)
):
    """
    Detect rugpull risks using GOplus analysis
    
    Analyzes:
    - Liquidity lock status
    - Ownership concentration
    - Suspicious trading patterns
    - Historical risk indicators
    """
    try:
        # Get cache dependency
        from app.core.dependencies import get_cache_dependency
        cache = await get_cache_dependency()
        
        # Check cache
        cache_key = f"goplus_rugpull:{token_address}"
        cached_results = await cache.get(cache_key, namespace="rugpull")
        
        if cached_results:
            logger.info(f"📋 Returning cached rugpull analysis for {token_address}")
            return cached_results
        
        # Perform rugpull detection
        logger.info(f"🚨 Detecting rugpull risk for {token_address} with GOplus")
        
        rugpull_data = await api_manager.detect_rugpull_goplus(token_address)
        
        if not rugpull_data or "error" in rugpull_data:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to detect rugpull risk: {rugpull_data.get('error', 'Unknown error')}"
            )
        
        # Cache for 30 minutes (rugpull risk can change)
        await cache.set(cache_key, rugpull_data, ttl=1800, namespace="rugpull")
        
        return rugpull_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Rugpull detection failed for {token_address}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Rugpull detection failed: {str(e)}")


@router.get("/goplus/health", summary="GOplus Services Health Check")
async def goplus_health_check():
    """
    Check health status of GOplus services
    """
    try:
        from app.services.goplus_client import check_goplus_health
        
        health_status = await check_goplus_health()
        
        # Determine HTTP status code based on health
        status_code = 200 if health_status.get("healthy") else 503
        
        return JSONResponse(
            content=health_status,
            status_code=status_code
        )
    except Exception as e:
        logger.error(f"Error checking GOplus health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/tokens", summary="Search Tokens Across Multiple Sources")
async def search_tokens(
    query: str = Query(..., description="Search query (token name, symbol, or address)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Search for tokens across multiple data sources including GOplus verification
    
    Searches through:
    - Birdeye token database
    - Chainbase token registry
    - Solscan token list
    - GOplus security database (when available)
    """
    try:
        # Get cache dependency
        from app.core.dependencies import get_cache_dependency
        cache = await get_cache_dependency()
        
        # Check cache
        cache_key = f"token_search:{query}:{limit}"
        cached_results = await cache.get(cache_key, namespace="search")
        
        if cached_results:
            logger.info(f"📋 Returning cached search results for '{query}'")
            return {
                "query": query,
                "results": cached_results,
                "total_results": len(cached_results),
                "cached": True
            }
        
        # Perform search
        logger.info(f"🔍 Searching for tokens: '{query}'")
        
        search_results = await search_for_tokens(query, limit)
        
        # Cache results for 10 minutes
        await cache.set(cache_key, search_results, ttl=600, namespace="search")
        
        return {
            "query": query,
            "results": search_results,
            "total_results": len(search_results),
            "cached": False,
            "enhanced_with_goplus": "goplus" in [r.get("source") for r in search_results if isinstance(r, dict)]
        }
        
    except Exception as e:
        logger.error(f"❌ Token search failed for '{query}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/trending", summary="Get Trending Tokens")
async def get_trending_tokens(
    limit: int = Query(20, ge=1, le=50, description="Maximum number of trending tokens"),
    sort_by: str = Query("volume", description="Sort by: volume, market_cap, social_buzz"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Get trending tokens from multiple sources with enhanced security data
    
    Aggregates trending data from:
    - Birdeye trending tokens
    - Solscan top tokens
    - DataImpulse social trending
    - GOplus security verification (when available)
    """
    try:
        # Get cache dependency
        from app.core.dependencies import get_cache_dependency
        cache = await get_cache_dependency()
        
        # Check cache
        cache_key = f"trending_tokens:{limit}:{sort_by}"
        cached_results = await cache.get(cache_key, namespace="trending")
        
        if cached_results:
            logger.info(f"📋 Returning cached trending tokens")
            return {
                "trending_tokens": cached_results,
                "total_results": len(cached_results),
                "sort_by": sort_by,
                "cached": True
            }
        
        # Get trending tokens
        logger.info(f"🔥 Getting trending tokens (limit: {limit}, sort: {sort_by})")
        
        trending_tokens = await get_trending_analysis(limit)
        
        # Sort results if needed
        if sort_by == "volume" and trending_tokens:
            trending_tokens.sort(
                key=lambda x: float(x.get("v24hUSD", 0) or x.get("volume_24h", 0) or 0), 
                reverse=True
            )
        elif sort_by == "market_cap" and trending_tokens:
            trending_tokens.sort(
                key=lambda x: float(x.get("mc", 0) or x.get("market_cap", 0) or 0), 
                reverse=True
            )
        
        # Cache for 5 minutes (trending data changes quickly)
        await cache.set(cache_key, trending_tokens, ttl=300, namespace="trending")
        
        return {
            "trending_tokens": trending_tokens,
            "total_results": len(trending_tokens),
            "sort_by": sort_by,
            "cached": False,
            "security_enhanced": True  # Indicates GOplus integration
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get trending tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get trending tokens: {str(e)}")


@router.post("/analyze/social", summary="Social Sentiment Analysis")
async def analyze_social_sentiment(
    token_symbol: str,
    token_name: Optional[str] = None,
    time_range: str = Query("24h", description="Time range: 1h, 24h, 7d"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Analyze social sentiment for a token using DataImpulse
    
    Analyzes sentiment across:
    - Twitter mentions and discussions
    - Telegram channel messages
    - Reddit posts and comments
    - Discord server messages
    """
    try:
        # Get cache dependency
        from app.core.dependencies import get_cache_dependency
        cache = await get_cache_dependency()
        
        # Check cache
        cache_key = f"social_sentiment:{token_symbol}:{time_range}"
        cached_results = await cache.get(cache_key, namespace="social")
        
        if cached_results:
            logger.info(f"📋 Returning cached social analysis for {token_symbol}")
            return cached_results
        
        # Perform social analysis
        logger.info(f"📱 Analyzing social sentiment for {token_symbol}")
        
        sentiment_data = await api_manager.get_social_sentiment(token_symbol, token_name)
        
        if not sentiment_data or "error" in sentiment_data:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to analyze social sentiment: {sentiment_data.get('error', 'Unknown error')}"
            )
        
        # Cache for 30 minutes
        await cache.set(cache_key, sentiment_data, ttl=1800, namespace="social")
        
        return sentiment_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Social sentiment analysis failed for {token_symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Social analysis failed: {str(e)}")


@router.get("/market-overview", summary="Market Overview")
async def get_market_overview(
    _: None = Depends(rate_limit_per_ip)
):
    """
    Get overall Solana market overview with enhanced security insights
    
    Provides:
    - Network statistics
    - Top performing tokens
    - Market trends
    - Volume analysis
    - Security landscape overview (via GOplus integration)
    """
    try:
        # Get cache dependency
        from app.core.dependencies import get_cache_dependency
        cache = await get_cache_dependency()
        
        # Check cache
        cache_key = "market_overview"
        cached_results = await cache.get(cache_key, namespace="market")
        
        if cached_results:
            logger.info("📋 Returning cached market overview")
            return cached_results
        
        # Get market overview data
        logger.info("📊 Getting market overview")
        
        # Gather data from multiple sources
        market_tasks = []
        
        # Solscan network stats
        if api_manager.clients.get("solscan"):
            market_tasks.append(api_manager.clients["solscan"].get_network_stats())
        
        # Birdeye trending tokens
        if api_manager.clients.get("birdeye"):
            market_tasks.append(api_manager.clients["birdeye"].get_trending_tokens(limit=10))
        
        # Execute tasks
        if market_tasks:
            import asyncio
            results = await asyncio.gather(*market_tasks, return_exceptions=True)
            
            network_stats = results[0] if len(results) > 0 and not isinstance(results[0], Exception) else None
            trending_tokens = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else []
        else:
            network_stats = None
            trending_tokens = []
        
        market_overview = {
            "network_stats": network_stats,
            "trending_tokens": trending_tokens[:10],
            "market_summary": {
                "active_tokens": len(trending_tokens),
                "network_healthy": bool(network_stats),
                "data_freshness": int(time.time()),
                "security_services_available": bool(api_manager.clients.get("goplus")),
                "enhanced_analysis": True
            }
        }
        
        # Cache for 10 minutes
        await cache.set(cache_key, market_overview, ttl=600, namespace="market")
        
        return market_overview
        
    except Exception as e:
        logger.error(f"❌ Market overview failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Market overview failed: {str(e)}")


def _transform_comprehensive_data(comprehensive_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform comprehensive API data to TokenAnalysisResponse format with GOplus integration"""
    
    # Extract standardized data
    standardized = comprehensive_data.get("standardized", {})
    
    # Build response components
    response_data = {
        "warnings": comprehensive_data.get("errors", []),
        "errors": []
    }
    
    # Extract metadata
    basic_info = standardized.get("basic_info", {})
    if basic_info:
        from app.models.token import TokenMetadata
        response_data["metadata"] = TokenMetadata(
            mint=comprehensive_data["token_address"],
            name=basic_info.get("name"),
            symbol=basic_info.get("symbol"),
            decimals=basic_info.get("decimals", 9)
        )
    
    # Extract price data
    price_info = standardized.get("price_info", {})
    if price_info:
        from app.models.token import PriceData
        from decimal import Decimal
        
        response_data["price_data"] = PriceData(
            current_price=Decimal(str(price_info.get("current_price", 0))),
            price_change_24h=Decimal(str(price_info.get("price_change_24h", 0))) if price_info.get("price_change_24h") else None
        )
    
    # Enhanced analysis with GOplus data
    goplus_summary = standardized.get("goplus_summary", {})
    if goplus_summary:
        # Add GOplus-specific analysis to the response
        response_data["goplus_analysis"] = {
            "risk_assessment": {
                "overall_risk_score": goplus_summary.get("risk_score", 0),
                "risk_level": goplus_summary.get("risk_level", "unknown"),
                "is_safe": goplus_summary.get("is_safe"),
                "confidence": goplus_summary.get("confidence", 0)
            },
            "security_details": goplus_summary.get("security_details", {}),
            "rugpull_risk": goplus_summary.get("rugpull_risk", {}),
            "services_used": goplus_summary.get("services_used", []),
            "major_risks": goplus_summary.get("major_risks", [])
        }
    
    # Mock AI analysis results for now (until AI integration is complete)
    if comprehensive_data.get("data_sources"):
        response_data["analysis"] = {
            "data_sources": comprehensive_data["data_sources"],
            "processing_time": comprehensive_data.get("processing_time", 0),
            "standardized_data": standardized,
            "goplus_enhanced": "goplus" in comprehensive_data.get("data_sources", [])
        }
    
    return response_data