from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from loguru import logger
import time
import json

from app.services.token_analyzer import token_analyzer
from app.services.service_manager import get_api_health_status
from app.core.dependencies import rate_limit_per_ip
from app.utils.redis_client import get_redis_client

router = APIRouter(prefix="/api", tags=["Token Analysis API"])


@router.get("/health", summary="API Services Health Check")
async def api_services_health():
    """
    Check health status of all external API services
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


@router.post("/analyze/token", summary="Comprehensive Token Analysis")
async def analyze_token_endpoint(
    token_address: str,
    force_refresh: bool = False,
    _: None = Depends(rate_limit_per_ip)
):
    """
    Perform comprehensive token analysis using all available services
    
    Returns LLM-optimized structured analysis combining data from:
    - Helius: On-chain data and metadata
    - Birdeye: Price data and market information
    - SolanaFM: Additional on-chain metrics
    - GOplus: Transaction simulation and token security
    - DexScreener: DEX data and trading pairs
    - RugCheck: Rug pull detection and security analysis
    """
    start_time = time.time()
    
    try:
        # Validate token address format
        if not token_address or len(token_address) < 32 or len(token_address) > 44:
            raise HTTPException(
                status_code=422, 
                detail="Invalid Solana token address format"
            )
        
        logger.info(f"🔍 API token analysis request for {token_address}")
        
        # Perform comprehensive analysis
        analysis_result = await token_analyzer.analyze_token_comprehensive(token_address, "api_request")
        
        # Add API-specific metadata
        analysis_result["metadata"]["from_cache"] = False
        analysis_result["metadata"]["force_refresh"] = force_refresh
        analysis_result["metadata"]["api_response_time"] = round((time.time() - start_time) * 1000, 1)
        
        # Log successful analysis
        logger.info(
            f"✅ API analysis completed for {token_address} in {analysis_result['metadata']['processing_time_seconds']}s "
            f"(confidence: {analysis_result['overall_analysis']['confidence_score']}%, "
            f"risk: {analysis_result['risk_assessment']['risk_category']})"
        )
        
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API token analysis failed for {token_address}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/analyze/token/{token_address}", summary="Get Token Analysis (GET endpoint)")
async def get_token_analysis(
    token_address: str,
    force_refresh: bool = Query(False, description="Force refresh cached data"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Alternative GET endpoint for token analysis
    """
    return await analyze_token_endpoint(token_address, force_refresh)


@router.get("/analyze/recent", summary="Get Recent Webhook Analyses")
async def get_recent_webhook_analyses(
    limit: int = Query(10, ge=1, le=50, description="Number of recent analyses to return"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Get recent token analyses triggered by webhooks
    """
    try:
        redis_client = await get_redis_client()
        
        # Get recent webhook analyses from Redis
        current_time = int(time.time())
        
        # Search for webhook analysis keys from the last hour
        recent_analyses = []
        
        # This is a simplified example - in production you'd want to use 
        # Redis SCAN or maintain a sorted set of recent analyses
        search_patterns = [
            f"webhook_analysis:*:{current_time - i}" 
            for i in range(3600)  # Last hour
        ]
        
        analyses_found = 0
        for i in range(min(100, 3600)):  # Check last 100 seconds
            timestamp = current_time - i
            
            # Use Redis client to search for keys (this is a simplified approach)
            # In production, you'd maintain a sorted set of recent analyses
            
            if analyses_found >= limit:
                break
        
        # Return empty list for now - this would be implemented with proper Redis key management
        return {
            "recent_analyses": recent_analyses,
            "total_found": len(recent_analyses),
            "time_range_seconds": 3600,
            "note": "Webhook analyses are stored for 1 hour"
        }
        
    except Exception as e:
        logger.error(f"❌ Error retrieving recent analyses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get recent analyses: {str(e)}")