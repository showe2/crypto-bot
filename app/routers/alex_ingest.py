from typing import Dict, List, Optional, Union, Literal
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import uuid4
from loguru import logger

from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/ingest", tags=["Social Ingestion"])

class EngagementMetrics(BaseModel):
    likes: int
    reposts: int
    followers: int
    eng_per_min: float
    influencer_mass: float

class AIModelResults(BaseModel):
    aegis: Dict[str, float]
    deepseek: Dict[str, float]
    mythomax: Dict[str, float]
    intent_classification: str
    social_score: float

class FilterMetadata(BaseModel):
    ai_results: AIModelResults
    ai_processing_time_ms: float
    intent_classification: str
    social_score: float

    @field_validator('intent_classification')
    @classmethod
    def validate_intent(cls, v: str) -> str:
        valid_intents = ['noise', 'has_token', 'will_token']
        if v not in valid_intents:
            logger.warning(f"Invalid intent received: {v}, defaulting to 'noise'")
            return 'noise'
        return v

class SocialAlert(BaseModel):
    message_id: str
    platform: str
    content: str
    timestamp: datetime
    author_id: str
    author_username: Optional[str]
    engagement_metrics: EngagementMetrics
    zscore: float
    memeability_score: float = Field(ge=0.0, le=1.0)
    decision: str = Field(pattern="^(WATCH|BUY_CANDIDATE|HOLD|NO)$")
    confidence: float = Field(ge=0.0, le=1.0)
    ticker_hints: List[str]
    ticker_confidence: Dict[str, float]
    keyword_matches: List[str]
    filter_metadata: FilterMetadata
    processing_timestamp: datetime
    pipeline_version: str

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }

async def verify_ingest_token(authorization: str = Header(None)) -> bool:
    """Verify the internal token for ingestion endpoints"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        token = authorization.replace("Bearer ", "")
        if token != settings.INTERNAL_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid token")
        return True
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authorization header")

@router.post("/social_alert", 
            summary="Ingest social alert",
            status_code=202,
            dependencies=[Depends(verify_ingest_token)])
async def ingest_social_alert(alert: SocialAlert):
    """Ingest social alerts with comprehensive metadata"""
    try:
        alert_id = alert.message_id or "N/A"
        logger.info(f"📨 Received {alert.platform} alert {alert_id} from {alert.author_username or alert.author_id}")
        
        # Log important metrics
        logger.debug(
            f"Alert metrics: zscore={alert.zscore:.2f}, "
            f"confidence={alert.confidence:.2f}, "
            f"decision={alert.decision}, "
            f"intent={alert.filter_metadata.intent_classification}"
        )
        
        return {
            "ok": True,
            "id": alert_id
        }
        
    except Exception as e:
        logger.error(f"Failed to process social alert: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process alert")