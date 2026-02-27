"""Trust Gateway FastAPI application"""
import os
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    Agent, AgentRegistration, ActionRecord, ActionReceipt,
    AuthorizationRequest, AuthorizationResponse, TrustTier,
    TrustBreakdown, DashboardStats
)
from .database import Database
from .trust_engine import TrustEngine

# Initialize app
app = FastAPI(
    title="Trust Gateway",
    description="AI Agent Trust Scoring and Graduated Authorization System",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
DB_PATH = os.getenv("DB_PATH", "trust_gateway.db")
SECRET_KEY = os.getenv("SECRET_KEY", "trust-gateway-secret-key-change-in-production")
API_KEY = os.getenv("API_KEY", "dev-api-key-change-in-production")

db = Database(DB_PATH)
trust_engine = TrustEngine(SECRET_KEY)


def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key authentication"""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "0.1.0"}


@app.post("/agents/register", response_model=Agent)
async def register_agent(
    registration: AgentRegistration,
    api_key: str = Depends(verify_api_key)
):
    """Register a new agent with identity attestation"""
    agent_id = str(uuid.uuid4())
    
    # Create agent with Sybil resistance (start at 0.1 score)
    agent_data = db.create_agent(
        agent_id=agent_id,
        name=registration.name,
        provider=registration.provider,
        config_hash=registration.config_hash,
        capabilities=registration.capabilities
    )
    
    # Calculate initial scores
    identity_score, _ = trust_engine.calculate_identity_score(agent_data)
    config_score, _ = trust_engine.calculate_config_score(agent_data)
    behavior_score = 0.0  # No history yet
    
    # Composite with Sybil resistance (minimum 0.1)
    composite = trust_engine.calculate_composite_score(identity_score, config_score, behavior_score)
    composite = max(0.1, composite)  # Sybil resistance
    
    # Determine tier
    tiers = db.get_tiers()
    tier = trust_engine.determine_tier(composite, tiers)
    
    # Update scores
    db.update_agent_scores(agent_id, identity_score, config_score, behavior_score, composite, tier)
    
    # Return updated agent
    agent_data = db.get_agent(agent_id)
    return Agent(**agent_data)


@app.get("/agents/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str, api_key: str = Depends(verify_api_key)):
    """Get agent profile and current trust score"""
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return Agent(**agent)


@app.get("/agents/{agent_id}/trust", response_model=TrustBreakdown)
async def get_trust_breakdown(agent_id: str, api_key: str = Depends(verify_api_key)):
    """Get detailed trust score breakdown"""
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    receipts = db.get_receipts(agent_id)
    
    # Recalculate scores for detailed breakdown
    identity_score, identity_factors = trust_engine.calculate_identity_score(agent)
    config_score, config_factors = trust_engine.calculate_config_score(agent)
    behavior_score, behavior_factors = trust_engine.calculate_behavior_score(receipts)
    
    # Get tier info
    tier = db.get_tier(agent["tier"])
    
    return TrustBreakdown(
        agent_id=agent_id,
        identity_score=identity_score,
        config_score=config_score,
        behavior_score=behavior_score,
        composite_score=agent["composite_score"],
        tier=agent["tier"],
        tier_name=tier["name"] if tier else "Unknown",
        weights=trust_engine.weights,
        factors={
            "identity": identity_factors,
            "config": config_factors,
            "behavior": behavior_factors
        }
    )


@app.post("/actions/record", response_model=ActionReceipt)
async def record_action(
    record: ActionRecord,
    api_key: str = Depends(verify_api_key)
):
    """Record a signed action receipt"""
    agent = db.get_agent(record.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    timestamp = record.timestamp or datetime.utcnow()
    receipt_id = str(uuid.uuid4())
    
    # Get previous receipt for chaining
    last_receipt = db.get_last_receipt(record.agent_id)
    previous_hash = last_receipt["receipt_hash"] if last_receipt else None
    
    # Sign receipt
    signature = trust_engine.sign_receipt(
        record.agent_id,
        record.action,
        record.result,
        timestamp.isoformat(),
        previous_hash
    )
    
    # Generate receipt hash for chaining
    receipt_hash = trust_engine.hash_receipt(receipt_id, signature)
    
    # Store receipt
    db.create_receipt(
        receipt_id=receipt_id,
        agent_id=record.agent_id,
        action=record.action,
        result=record.result,
        timestamp=timestamp,
        signature=signature,
        previous_hash=previous_hash,
        receipt_hash=receipt_hash
    )
    
    # Recalculate trust scores
    receipts = db.get_receipts(record.agent_id)
    identity_score, _ = trust_engine.calculate_identity_score(agent)
    config_score, _ = trust_engine.calculate_config_score(agent)
    behavior_score, _ = trust_engine.calculate_behavior_score(receipts)
    
    composite = trust_engine.calculate_composite_score(identity_score, config_score, behavior_score)
    composite = max(0.1, composite)  # Sybil resistance
    
    tiers = db.get_tiers()
    tier = trust_engine.determine_tier(composite, tiers)
    
    db.update_agent_scores(record.agent_id, identity_score, config_score, behavior_score, composite, tier)
    
    return ActionReceipt(
        id=receipt_id,
        agent_id=record.agent_id,
        action=record.action,
        result=record.result,
        timestamp=timestamp,
        signature=signature,
        previous_hash=previous_hash,
        receipt_hash=receipt_hash
    )


@app.post("/authorize", response_model=AuthorizationResponse)
async def authorize_action(
    request: AuthorizationRequest,
    api_key: str = Depends(verify_api_key)
):
    """Check if agent is authorized for an action"""
    agent = db.get_agent(request.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Map common actions to required tiers (simple policy for demo)
    action_policies = {
        "read_config": (0, 0.0),
        "view_status": (0, 0.0),
        "send_notification": (1, 0.2),
        "read_data": (1, 0.2),
        "write_data": (2, 0.5),
        "call_api": (2, 0.5),
        "send_email": (2, 0.5),
        "delete_data": (3, 0.8),
        "delete_database": (3, 0.9),
        "admin_action": (3, 0.85)
    }
    
    # Default policy for unknown actions
    required_tier, required_score = action_policies.get(request.action, (1, 0.3))
    
    # Check authorization
    allowed, reason = trust_engine.check_authorization(
        agent["tier"], required_tier,
        agent["composite_score"], required_score
    )
    
    return AuthorizationResponse(
        allowed=allowed,
        agent_id=request.agent_id,
        action=request.action,
        current_tier=agent["tier"],
        required_tier=required_tier,
        current_score=agent["composite_score"],
        required_score=required_score,
        reason=reason
    )


@app.get("/tiers", response_model=List[TrustTier])
async def get_tiers(api_key: str = Depends(verify_api_key)):
    """List authorization tiers"""
    tiers = db.get_tiers()
    return [TrustTier(**tier) for tier in tiers]


@app.put("/tiers/{tier_num}", response_model=TrustTier)
async def update_tier(
    tier_num: int,
    tier: TrustTier,
    api_key: str = Depends(verify_api_key)
):
    """Configure authorization tier (admin only)"""
    existing = db.get_tier(tier_num)
    if not existing:
        raise HTTPException(status_code=404, detail="Tier not found")
    
    db.update_tier(
        tier_num=tier_num,
        name=tier.name,
        min_score=tier.min_score,
        max_score=tier.max_score,
        description=tier.description,
        permissions=tier.permissions
    )
    
    updated = db.get_tier(tier_num)
    return TrustTier(**updated)


@app.get("/receipts/{agent_id}", response_model=List[ActionReceipt])
async def get_receipts(agent_id: str, api_key: str = Depends(verify_api_key)):
    """Get action receipt chain for an agent"""
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    receipts = db.get_receipts(agent_id)
    return [ActionReceipt(**receipt) for receipt in receipts]


@app.get("/stats", response_model=DashboardStats)
async def get_stats(api_key: str = Depends(verify_api_key)):
    """Get dashboard statistics"""
    stats = db.get_stats()
    return DashboardStats(**stats)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
