"""Database models for Trust Gateway V2 - Pydantic v2 + SPIFFE Identity"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict


class AttestationType(str, Enum):
    """Identity attestation types"""
    X509 = "x509"
    JWT = "jwt"
    API_KEY = "api_key"
    SELF_DECLARED = "self_declared"


class IdentityAttestation(BaseModel):
    """SPIFFE-compatible identity attestation"""
    type: AttestationType
    certificate: Optional[str] = None  # PEM encoded X.509 certificate
    chain: Optional[List[str]] = None  # Certificate chain
    jwt_token: Optional[str] = None  # JWT SVID
    api_key_hash: Optional[str] = None  # Hashed API key


class Agent(BaseModel):
    """Agent registration model - Pydantic v2"""
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    id: Optional[str] = None
    name: str
    provider: str
    spiffe_id: Optional[str] = None  # spiffe://domain/agent/name
    config_hash: str
    capabilities: List[str]
    attestation: Optional[IdentityAttestation] = None
    created_at: Optional[datetime] = None
    identity_score: float = 0.0
    config_score: float = 0.0
    behavior_score: float = 0.0
    composite_score: float = 0.0
    tier: int = 0
    config_changes: int = 0
    last_config_hash: Optional[str] = None


class AgentRegistration(BaseModel):
    """Agent registration request - Pydantic v2"""
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=50)
    spiffe_id: Optional[str] = Field(None, pattern=r"^spiffe://[a-zA-Z0-9\-\.]+/.*$")
    config_hash: str = Field(..., min_length=32, max_length=128)
    capabilities: List[str]
    attestation: Optional[IdentityAttestation] = None

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: List[str]) -> List[str]:
        if not v or len(v) < 1:
            raise ValueError("Must have at least one capability")
        return v


class ActionReceipt(BaseModel):
    """Action receipt model - Pydantic v2"""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    agent_id: str
    action: str
    result: str  # success, failure, violation
    timestamp: datetime
    signature: str
    previous_hash: Optional[str] = None
    receipt_hash: Optional[str] = None


class ActionRecord(BaseModel):
    """Action recording request - Pydantic v2"""
    agent_id: str
    action: str
    result: str
    timestamp: Optional[datetime] = None

    @field_validator("result")
    @classmethod
    def validate_result(cls, v: str) -> str:
        if v not in ["success", "failure", "violation"]:
            raise ValueError("Result must be success, failure, or violation")
        return v


class AuthorizationRequest(BaseModel):
    """Authorization check request"""
    agent_id: str
    action: str
    context: Optional[Dict[str, Any]] = None


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


class BatchAuthorizationRequest(BaseModel):
    """Batch authorization check request"""
    agent_id: str
    actions: List[str]


class BatchAuthorizationResponse(BaseModel):
    """Batch authorization check response"""
    agent_id: str
    results: Dict[str, AuthorizationResponse]


class JWTTokenResponse(BaseModel):
    """JWT token issuance response"""
    token: str
    expires_in: int
    tier: int
    permitted_actions: List[str]


class AgentCard(BaseModel):
    """A2A-compatible agent capability card"""
    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    name: str
    provider: str
    spiffe_id: Optional[str] = None
    capabilities: List[str]
    trust_score: float
    trust_tier: int
    tier_name: str
    created_at: datetime
    last_action_at: Optional[datetime] = None
    total_actions: int
    success_rate: float
    permitted_actions: List[str]
    metadata: Optional[Dict[str, Any]] = None


class TrustTier(BaseModel):
    """Trust tier configuration - Pydantic v2"""
    model_config = ConfigDict(from_attributes=True)

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
    weights: Dict[str, float]
    factors: Dict[str, Any]


class TrustHistoryPoint(BaseModel):
    """Trust score history point"""
    timestamp: datetime
    composite_score: float
    tier: int
    trigger: str  # action, config_change, violation, etc.


class TrustHistory(BaseModel):
    """Trust score history for an agent"""
    agent_id: str
    history: List[TrustHistoryPoint]


class WebhookEvent(str, Enum):
    """Webhook event types"""
    TRUST_CHANGED = "trust_changed"
    TIER_CHANGED = "tier_changed"
    AUTHORIZATION_DENIED = "authorization_denied"
    RECEIPT_CHAIN_BROKEN = "receipt_chain_broken"


class WebhookConfig(BaseModel):
    """Webhook configuration"""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    url: str = Field(..., pattern=r"^https?://.*$")
    events: List[WebhookEvent]
    secret: Optional[str] = None  # HMAC signing secret
    enabled: bool = True
    created_at: Optional[datetime] = None


class DashboardStats(BaseModel):
    """Dashboard statistics"""
    total_agents: int
    total_actions: int
    agents_by_tier: Dict[str, int]
    recent_actions: int
    trust_score_distribution: Dict[str, int]


class WebSocketMessage(BaseModel):
    """WebSocket dashboard message"""
    type: str  # trust_update, auth_event, receipt_recorded
    timestamp: datetime
    data: Dict[str, Any]
