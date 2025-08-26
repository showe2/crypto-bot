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


@router.post("/analyze/batch", summary="Batch Token Analysis")
async def analyze_tokens_batch(
    token_addresses: List[str],
    max_concurrent: int = Query(3, ge=1, le=5, description="Max concurrent analyses"),
    _: None = Depends(rate_limit_per_ip)
):
    """
    Analyze multiple tokens in batch (limited to prevent API abuse)
    """
    start_time = time.time()
    
    try:
        # Validate input
        if len(token_addresses) > 10:
            raise HTTPException(
                status_code=422,
                detail="Maximum 10 tokens allowed per batch request"
            )
        
        if len(token_addresses) == 0:
            raise HTTPException(
                status_code=422,
                detail="At least one token address required"
            )
        
        # Validate each address
        valid_addresses = []
        invalid_addresses = []
        
        for addr in token_addresses:
            if addr and len(addr) >= 32 and len(addr) <= 44:
                valid_addresses.append(addr)
            else:
                invalid_addresses.append(addr)
        
        if invalid_addresses:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid token addresses: {invalid_addresses}"
            )
        
        logger.info(f"🔍 Batch analysis request for {len(valid_addresses)} tokens")
        
        # Process tokens with concurrency limit
        import asyncio
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_single_token(token_addr: str):
            async with semaphore:
                try:
                    result = await token_analyzer.analyze_token_comprehensive(token_addr, "api_batch")
                    return {"token_address": token_addr, "analysis": result, "success": True}
                except Exception as e:
                    logger.error(f"❌ Batch analysis failed for {token_addr}: {str(e)}")
                    return {
                        "token_address": token_addr, 
                        "error": str(e), 
                        "success": False
                    }
        
        # Execute batch analysis
        results = await asyncio.gather(
            *[analyze_single_token(addr) for addr in valid_addresses],
            return_exceptions=True
        )
        
        # Process results
        successful_analyses = []
        failed_analyses = []
        
        for result in results:
            if isinstance(result, Exception):
                failed_analyses.append({
                    "error": str(result),
                    "success": False
                })
            elif result.get("success"):
                successful_analyses.append(result)
            else:
                failed_analyses.append(result)
        
        processing_time = time.time() - start_time
        
        batch_response = {
            "batch_id": f"batch_{int(time.time())}",
            "processing_time_seconds": round(processing_time, 3),
            "total_requested": len(valid_addresses),
            "successful_analyses": len(successful_analyses),
            "failed_analyses": len(failed_analyses),
            "results": {
                "successful": successful_analyses,
                "failed": failed_analyses
            },
            "summary": {
                "success_rate": round((len(successful_analyses) / len(valid_addresses)) * 100, 1),
                "average_time_per_token": round(processing_time / len(valid_addresses), 3)
            }
        }
        
        logger.info(
            f"✅ Batch analysis completed: {len(successful_analyses)}/{len(valid_addresses)} successful "
            f"in {processing_time:.2f}s"
        )
        
        return batch_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Batch analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")