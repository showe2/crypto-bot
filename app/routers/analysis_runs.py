from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from loguru import logger
import time

from app.core.dependencies import rate_limit_per_ip
from app.services.analysis_profiles.twitter_profile import TwitterAnalysisProfile
from app.services.analysis_profiles.pump_profile import PumpAnalysisProfile
from app.services.analysis_profiles.whale_profile import WhaleAnalysisProfile
from app.services.analysis_profiles.discovery_profile import TokenDiscoveryProfile
from app.services.analysis_profiles.listing_profile import ListingAnalysisProfile

router = APIRouter(prefix="/run", tags=["Analysis Runs"])

# Profile instances
profiles = {
    "twitter": TwitterAnalysisProfile(),
    "pump": PumpAnalysisProfile(),
    "whale": WhaleAnalysisProfile(),
    "discovery": TokenDiscoveryProfile(),
    "listing": ListingAnalysisProfile()
}


class AnalysisRequest(BaseModel):
    """Request model for analysis runs"""
    token_address: str = Field(..., description="Token mint address")
    json_filters: Optional[Dict[str, Any]] = Field(None, description="AI JSON filters")
    force_refresh: bool = Field(False, description="Force refresh cached data")
    additional_params: Optional[Dict[str, Any]] = Field(None, description="Profile-specific parameters")


@router.post("/twitter", summary="Twitter Social Analysis")
async def run_twitter_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(rate_limit_per_ip)
):
    """Run Twitter social media analysis for trending tokens"""
    try:
        profile = profiles["twitter"]
        result = await profile.analyze(
            token_address=request.token_address,
            filters=request.json_filters,
            **request.additional_params or {}
        )
        
        # Return frontend-compatible format
        return profile.format_for_frontend(result)
        
    except Exception as e:
        logger.error(f"Twitter analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Twitter analysis failed: {str(e)}")


@router.post("/pump", summary="Pump Detection Analysis")
async def run_pump_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(rate_limit_per_ip)
):
    """Run pump/volume spike detection analysis"""
    try:
        profile = profiles["pump"]
        result = await profile.analyze(
            token_address=request.token_address,
            filters=request.json_filters,
            **request.additional_params or {}
        )
        
        return profile.format_for_frontend(result)
        
    except Exception as e:
        logger.error(f"Pump analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pump analysis failed: {str(e)}")


@router.post("/whales30d", summary="Whale Distribution Analysis")
async def run_whale_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(rate_limit_per_ip)
):
    """Run whale holder distribution and risk analysis"""
    try:
        profile = profiles["whale"]
        result = await profile.analyze(
            token_address=request.token_address,
            filters=request.json_filters,
            **request.additional_params or {}
        )
        
        return profile.format_for_frontend(result)
        
    except Exception as e:
        logger.error(f"Whale analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Whale analysis failed: {str(e)}")


@router.post("/find_token", summary="Complete Token Discovery")
async def run_discovery_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(rate_limit_per_ip)
):
    """Run comprehensive token discovery analysis (wrapper around existing deep analysis)"""
    try:
        profile = profiles["discovery"]
        result = await profile.analyze(
            token_address=request.token_address,
            filters=request.json_filters,
            **request.additional_params or {}
        )
        
        return profile.format_for_frontend(result)
        
    except Exception as e:
        logger.error(f"Discovery analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Discovery analysis failed: {str(e)}")


@router.post("/listings", summary="New Listings Analysis")
async def run_listing_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(rate_limit_per_ip)
):
    """Run new token listings and early opportunity analysis"""
    try:
        profile = profiles["listing"]
        result = await profile.analyze(
            token_address=request.token_address,
            filters=request.json_filters,
            **request.additional_params or {}
        )
        
        return profile.format_for_frontend(result)
        
    except Exception as e:
        logger.error(f"Listing analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Listing analysis failed: {str(e)}")


@router.get("/status/{run_id}", summary="Get Analysis Run Status")
async def get_analysis_status(
    run_id: str,
    _: None = Depends(rate_limit_per_ip)
):
    """Get the status of a running analysis"""
    try:
        # Extract analysis type from run_id
        if "_twitter_" in run_id:
            analysis_type = "twitter"
        elif "_pump_" in run_id:
            analysis_type = "pump"
        elif "_whale_" in run_id:
            analysis_type = "whale"
        elif "_discovery_" in run_id:
            analysis_type = "discovery"
        elif "_listing_" in run_id:
            analysis_type = "listing"
        else:
            raise HTTPException(status_code=400, detail="Invalid run_id format")
        
        # For now, return completed status (since we don't have async analysis yet)
        return {
            "run_id": run_id,
            "status": "completed",
            "analysis_type": analysis_type,
            "progress": 100,
            "estimated_completion": None,
            "message": "Analysis completed"
        }
        
    except Exception as e:
        logger.error(f"Status check failed for {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")