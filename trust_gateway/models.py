"""Database models for Trust Gateway"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class Agent(BaseModel):
    """Agent registration model"""
    id: Optional[str] = None
    name: str
    provider: str
    config_hash: str
    capabilities: List[str]
    created_at: Optional[datetime] = None
    identity_score: float = 0.0
    config_score: float = 0.0
    behavior_score: float = 0.0
    composite_score: float = 0.0
    tier: int = 0
    config_changes: int = 0
    last_config_hash: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class AgentRegistration(BaseModel):
    """Agent registration request"""
    name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=50)
    config_hash: str = Field(..., min_length=32, max_length=128)
    capabilities: List[str]
    
    @validator('capabilities')
    def validate_capabilities(cls, v):
        if not v or len(v) < 1:
            raise ValueError('Must have at least one capability')
        return v


class ActionReceipt(BaseModel):
    """Action receipt model"""
    id: Optional[str] = None
    agent_id: str
    action: str
    result: str  # success, failure, violation
    timestamp: datetime
    signature: str
    previous_hash: Optional[str] = None
    receipt_hash: Optional[str] = None


class ActionRecord(BaseModel):
    """Action recording request"""
    agent_id: str
    action: str
    result: str
    timestamp: Optional[datetime] = None
    
    @validator('result')
    def validate_result(cls, v):
        if v not in ['success', 'failure', 'violation']:
            raise ValueError('Result must be success, failure, or violation')
        return v


class AuthorizationRequest(BaseModel):
    """Authorization check request"""
    agent_id: str
    action: str
    context: Optional[dict] = None


class AuthorizationResponse(BaseModel):
    """Authorization check response"""
    allowed: bool
    agent_id: str
    action: str
    current_tier: int
    required_tier: int
    current_score: float
    required_score: float
    reason: Optional[str] = None


class TrustTier(BaseModel):
    """Trust tier configuration"""
    tier: int
    name: str
    min_score: float
    max_score: float
    description: str
    permissions: List[str]


class TrustBreakdown(BaseModel):
    """Detailed trust score breakdown"""
    agent_id: str
    identity_score: float
    config_score: float
    behavior_score: float
    composite_score: float
    tier: int
    tier_name: str
    weights: dict
    factors: dict


class DashboardStats(BaseModel):
    """Dashboard statistics"""
    total_agents: int
    total_actions: int
    agents_by_tier: dict
    recent_actions: int
    trust_score_distribution: dict
