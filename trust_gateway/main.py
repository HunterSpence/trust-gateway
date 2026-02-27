"""Trust Gateway V2 FastAPI application - Async + SPIFFE + JWT + A2A + WebSocket"""
import os
import uuid
import asyncio
from datetime import datetime
from typing import List, Optional, Set
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, HTTPException, Header, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .models import (
    Agent,
    AgentRegistration,
    ActionRecord,
    ActionReceipt,
    AuthorizationRequest,
    AuthorizationResponse,
    BatchAuthorizationRequest,
    BatchAuthorizationResponse,
    JWTTokenResponse,
    AgentCard,
    TrustTier,
    TrustBreakdown,
    TrustHistory,
    TrustHistoryPoint,
    WebhookConfig,
    WebhookEvent,
    DashboardStats,
    WebSocketMessage,
)
from .database import Database
from .trust_engine import TrustEngine

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

# Configure OpenTelemetry
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
tracer = trace.get_tracer(__name__)

# Environment configuration
DB_PATH = os.getenv("DB_PATH", "sqlite+aiosqlite:///trust_gateway.db")
SECRET_KEY = os.getenv("SECRET_KEY", "trust-gateway-secret-key-change-in-production")
JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
API_KEY = os.getenv("API_KEY", "dev-api-key-change-in-production")

# Global components
db: Database
trust_engine: TrustEngine
websocket_connections: Set[WebSocket] = set()


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    global db, trust_engine

    # Startup
    logger.info("trust_gateway_starting", version="2.0.0")
    db = Database(DB_PATH)
    await db.init_db()
    trust_engine = TrustEngine(SECRET_KEY, JWT_SECRET)
    logger.info("trust_gateway_started", db_path=DB_PATH)

    yield

    # Shutdown
    logger.info("trust_gateway_stopping")
    # Close websocket connections
    for ws in list(websocket_connections):
        await ws.close()
    logger.info("trust_gateway_stopped")


# Initialize app
app = FastAPI(
    title="Trust Gateway V2",
    description="AI Agent Trust Scoring with SPIFFE Identity, JWT Tokens, and A2A Compatibility",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


# Dependencies
def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key authentication"""
    if x_api_key != API_KEY:
        logger.warning("invalid_api_key_attempt")
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


async def broadcast_websocket(message: WebSocketMessage):
    """Broadcast message to all WebSocket clients"""
    for ws in list(websocket_connections):
        try:
            await ws.send_json(message.model_dump(mode="json"))
        except Exception as e:
            logger.error("websocket_broadcast_error", error=str(e))
            websocket_connections.discard(ws)


async def trigger_webhooks(event: WebhookEvent, data: dict):
    """Trigger webhooks for an event"""
    webhooks = await db.get_webhooks()

    for webhook in webhooks:
        if not webhook["enabled"]:
            continue

        if event.value not in webhook["events"]:
            continue

        try:
            async with httpx.AsyncClient() as client:
                payload = {"event": event.value, "timestamp": datetime.utcnow().isoformat(), "data": data}
                
                headers = {}
                if webhook["secret"]:
                    # Sign webhook with HMAC
                    import hmac
                    import hashlib
                    import json
                    signature = hmac.new(
                        webhook["secret"].encode(),
                        json.dumps(payload).encode(),
                        hashlib.sha256
                    ).hexdigest()
                    headers["X-Webhook-Signature"] = signature

                await client.post(webhook["url"], json=payload, headers=headers, timeout=10.0)
                logger.info("webhook_triggered", url=webhook["url"], event=event.value)
        except Exception as e:
            logger.error("webhook_error", url=webhook["url"], error=str(e))


# Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "2.0.0"}


@app.post("/agents/register", response_model=Agent)
async def register_agent(registration: AgentRegistration, api_key: str = Depends(verify_api_key)):
    """Register a new agent with SPIFFE-compatible identity attestation"""
    with tracer.start_as_current_span("register_agent"):
        agent_id = str(uuid.uuid4())

        # Create agent
        agent_data = await db.create_agent(
            agent_id=agent_id,
            name=registration.name,
            provider=registration.provider,
            spiffe_id=registration.spiffe_id,
            config_hash=registration.config_hash,
            capabilities=registration.capabilities,
            attestation=registration.attestation.model_dump() if registration.attestation else None,
        )

        # Calculate initial scores
        identity_score, _ = trust_engine.calculate_identity_score(agent_data)
        config_score, _ = trust_engine.calculate_config_score(agent_data)
        behavior_score = 0.0

        # Composite with Sybil resistance
        composite = trust_engine.calculate_composite_score(identity_score, config_score, behavior_score)
        composite = max(0.1, composite)

        # Determine tier
        tiers = await db.get_tiers()
        tier = trust_engine.determine_tier(composite, tiers)

        # Update scores
        await db.update_agent_scores(agent_id, identity_score, config_score, behavior_score, composite, tier)

        # Broadcast to WebSocket clients
        await broadcast_websocket(
            WebSocketMessage(
                type="agent_registered",
                timestamp=datetime.utcnow(),
                data={"agent_id": agent_id, "name": registration.name, "tier": tier, "score": composite},
            )
        )

        logger.info("agent_registered", agent_id=agent_id, name=registration.name, tier=tier)

        agent_data = await db.get_agent(agent_id)
        return Agent(**agent_data)


@app.get("/agents/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str, api_key: str = Depends(verify_api_key)):
    """Get agent profile and current trust score"""
    with tracer.start_as_current_span("get_agent"):
        agent = await db.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return Agent(**agent)


@app.get("/agents/{agent_id}/trust", response_model=TrustBreakdown)
async def get_trust_breakdown(agent_id: str, api_key: str = Depends(verify_api_key)):
    """Get detailed trust score breakdown"""
    with tracer.start_as_current_span("get_trust_breakdown"):
        agent = await db.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        receipts = await db.get_receipts(agent_id)

        # Recalculate scores for detailed breakdown
        identity_score, identity_factors = trust_engine.calculate_identity_score(agent)
        config_score, config_factors = trust_engine.calculate_config_score(agent)
        behavior_score, behavior_factors = trust_engine.calculate_behavior_score(receipts)

        # Get tier info
        tier_data = await db.get_tier(agent["tier"])

        return TrustBreakdown(
            agent_id=agent_id,
            identity_score=identity_score,
            config_score=config_score,
            behavior_score=behavior_score,
            composite_score=agent["composite_score"],
            tier=agent["tier"],
            tier_name=tier_data["name"] if tier_data else "Unknown",
            weights=trust_engine.weights,
            factors={
                "identity": identity_factors,
                "config": config_factors,
                "behavior": behavior_factors,
            },
        )


@app.get("/agents/{agent_id}/history", response_model=TrustHistory)
async def get_trust_history(agent_id: str, limit: int = 100, api_key: str = Depends(verify_api_key)):
    """Get trust score history for an agent"""
    with tracer.start_as_current_span("get_trust_history"):
        agent = await db.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        history = await db.get_trust_history(agent_id, limit=limit)
        
        return TrustHistory(
            agent_id=agent_id,
            history=[TrustHistoryPoint(**h) for h in history],
        )


@app.get("/agents/{agent_id}/card", response_model=AgentCard)
async def get_agent_card(agent_id: str, api_key: str = Depends(verify_api_key)):
    """Get A2A-compatible agent capability card"""
    with tracer.start_as_current_span("get_agent_card"):
        agent = await db.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        receipts = await db.get_receipts(agent_id)
        tier_data = await db.get_tier(agent["tier"])

        # Calculate success rate
        total_actions = len(receipts)
        successes = sum(1 for r in receipts if r["result"] == "success")
        success_rate = successes / total_actions if total_actions > 0 else 0.0

        # Get last action timestamp
        last_action_at = receipts[0]["timestamp"] if receipts else None

        # Get permitted actions
        tiers = await db.get_tiers()
        permitted_actions = trust_engine.get_permitted_actions_for_tier(agent["tier"], tiers)

        return AgentCard(
            agent_id=agent_id,
            name=agent["name"],
            provider=agent["provider"],
            spiffe_id=agent.get("spiffe_id"),
            capabilities=agent["capabilities"],
            trust_score=agent["composite_score"],
            trust_tier=agent["tier"],
            tier_name=tier_data["name"] if tier_data else "Unknown",
            created_at=agent["created_at"],
            last_action_at=last_action_at,
            total_actions=total_actions,
            success_rate=success_rate,
            permitted_actions=permitted_actions,
            metadata={"identity_score": agent["identity_score"], "config_score": agent["config_score"], "behavior_score": agent["behavior_score"]},
        )


@app.post("/agents/{agent_id}/token", response_model=JWTTokenResponse)
async def issue_token(agent_id: str, expires_in: int = 3600, api_key: str = Depends(verify_api_key)):
    """Issue JWT token based on agent's current trust tier"""
    with tracer.start_as_current_span("issue_token"):
        agent = await db.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Get permitted actions for tier
        tiers = await db.get_tiers()
        permitted_actions = trust_engine.get_permitted_actions_for_tier(agent["tier"], tiers)

        # Issue JWT token
        token = trust_engine.issue_jwt_token(
            agent_id=agent_id,
            agent_name=agent["name"],
            tier=agent["tier"],
            composite_score=agent["composite_score"],
            permitted_actions=permitted_actions,
            expires_in=expires_in,
        )

        logger.info("jwt_token_issued", agent_id=agent_id, tier=agent["tier"])

        return JWTTokenResponse(
            token=token,
            expires_in=expires_in,
            tier=agent["tier"],
            permitted_actions=permitted_actions,
        )


@app.post("/actions/record", response_model=ActionReceipt)
async def record_action(record: ActionRecord, api_key: str = Depends(verify_api_key)):
    """Record a signed action receipt"""
    with tracer.start_as_current_span("record_action"):
        agent = await db.get_agent(record.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        timestamp = record.timestamp or datetime.utcnow()
        receipt_id = str(uuid.uuid4())

        # Get previous receipt for chaining
        last_receipt = await db.get_last_receipt(record.agent_id)
        previous_hash = last_receipt["receipt_hash"] if last_receipt else None

        # Sign receipt
        signature = trust_engine.sign_receipt(
            record.agent_id, record.action, record.result, timestamp.isoformat(), previous_hash
        )

        # Generate receipt hash for chaining
        receipt_hash = trust_engine.hash_receipt(receipt_id, signature)

        # Store receipt
        await db.create_receipt(
            receipt_id=receipt_id,
            agent_id=record.agent_id,
            action=record.action,
            result=record.result,
            timestamp=timestamp,
            signature=signature,
            previous_hash=previous_hash,
            receipt_hash=receipt_hash,
        )

        # Recalculate trust scores
        receipts = await db.get_receipts(record.agent_id)
        identity_score, _ = trust_engine.calculate_identity_score(agent)
        config_score, _ = trust_engine.calculate_config_score(agent)
        behavior_score, _ = trust_engine.calculate_behavior_score(receipts)

        composite = trust_engine.calculate_composite_score(identity_score, config_score, behavior_score)
        composite = max(0.1, composite)

        old_tier = agent["tier"]
        tiers = await db.get_tiers()
        tier = trust_engine.determine_tier(composite, tiers)

        await db.update_agent_scores(record.agent_id, identity_score, config_score, behavior_score, composite, tier)

        # Broadcast to WebSocket
        await broadcast_websocket(
            WebSocketMessage(
                type="receipt_recorded",
                timestamp=datetime.utcnow(),
                data={
                    "agent_id": record.agent_id,
                    "action": record.action,
                    "result": record.result,
                    "new_score": composite,
                    "new_tier": tier,
                },
            )
        )

        # Trigger webhooks
        if old_tier != tier:
            await trigger_webhooks(
                WebhookEvent.TIER_CHANGED,
                {"agent_id": record.agent_id, "old_tier": old_tier, "new_tier": tier, "score": composite},
            )

        if record.result == "violation":
            await trigger_webhooks(
                WebhookEvent.AUTHORIZATION_DENIED,
                {"agent_id": record.agent_id, "action": record.action, "reason": "violation"},
            )

        logger.info("action_recorded", agent_id=record.agent_id, action=record.action, result=record.result)

        return ActionReceipt(
            id=receipt_id,
            agent_id=record.agent_id,
            action=record.action,
            result=record.result,
            timestamp=timestamp,
            signature=signature,
            previous_hash=previous_hash,
            receipt_hash=receipt_hash,
        )


@app.post("/authorize", response_model=AuthorizationResponse)
async def authorize_action(request: AuthorizationRequest, api_key: str = Depends(verify_api_key)):
    """Check if agent is authorized for an action"""
    with tracer.start_as_current_span("authorize_action"):
        agent = await db.get_agent(request.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Map common actions to required tiers
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
            "admin_action": (3, 0.85),
        }

        # Default policy for unknown actions
        required_tier, required_score = action_policies.get(request.action, (1, 0.3))

        # Check authorization
        allowed, reason = trust_engine.check_authorization(
            agent["tier"], required_tier, agent["composite_score"], required_score
        )

        # Broadcast denied authorization
        if not allowed:
            await broadcast_websocket(
                WebSocketMessage(
                    type="auth_denied",
                    timestamp=datetime.utcnow(),
                    data={
                        "agent_id": request.agent_id,
                        "action": request.action,
                        "reason": reason,
                        "tier": agent["tier"],
                        "score": agent["composite_score"],
                    },
                )
            )

            await trigger_webhooks(
                WebhookEvent.AUTHORIZATION_DENIED,
                {"agent_id": request.agent_id, "action": request.action, "reason": reason},
            )

        logger.info(
            "authorization_check",
            agent_id=request.agent_id,
            action=request.action,
            allowed=allowed,
            reason=reason,
        )

        return AuthorizationResponse(
            allowed=allowed,
            agent_id=request.agent_id,
            action=request.action,
            current_tier=agent["tier"],
            required_tier=required_tier,
            current_score=agent["composite_score"],
            required_score=required_score,
            reason=reason,
        )


@app.post("/authorize/batch", response_model=BatchAuthorizationResponse)
async def authorize_batch(request: BatchAuthorizationRequest, api_key: str = Depends(verify_api_key)):
    """Batch authorization check for multiple actions"""
    with tracer.start_as_current_span("authorize_batch"):
        results = {}

        for action in request.actions:
            auth_request = AuthorizationRequest(agent_id=request.agent_id, action=action)
            auth_response = await authorize_action(auth_request, api_key)
            results[action] = auth_response

        return BatchAuthorizationResponse(agent_id=request.agent_id, results=results)


@app.get("/tiers", response_model=List[TrustTier])
async def get_tiers(api_key: str = Depends(verify_api_key)):
    """List authorization tiers"""
    tiers = await db.get_tiers()
    return [TrustTier(**tier) for tier in tiers]


@app.put("/tiers/{tier_num}", response_model=TrustTier)
async def update_tier(tier_num: int, tier: TrustTier, api_key: str = Depends(verify_api_key)):
    """Configure authorization tier (admin only)"""
    existing = await db.get_tier(tier_num)
    if not existing:
        raise HTTPException(status_code=404, detail="Tier not found")

    await db.update_tier(
        tier_num=tier_num,
        name=tier.name,
        min_score=tier.min_score,
        max_score=tier.max_score,
        description=tier.description,
        permissions=tier.permissions,
    )

    updated = await db.get_tier(tier_num)
    return TrustTier(**updated)


@app.get("/receipts/{agent_id}", response_model=List[ActionReceipt])
async def get_receipts(agent_id: str, api_key: str = Depends(verify_api_key)):
    """Get action receipt chain for an agent"""
    agent = await db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    receipts = await db.get_receipts(agent_id)
    return [ActionReceipt(**receipt) for receipt in receipts]


@app.get("/stats", response_model=DashboardStats)
async def get_stats(api_key: str = Depends(verify_api_key)):
    """Get dashboard statistics"""
    stats = await db.get_stats()
    return DashboardStats(**stats)


@app.post("/config/webhooks", response_model=WebhookConfig)
async def create_webhook(webhook: WebhookConfig, api_key: str = Depends(verify_api_key)):
    """Configure webhook for trust events"""
    webhook_id = str(uuid.uuid4())
    
    await db.create_webhook(
        webhook_id=webhook_id,
        url=webhook.url,
        events=[e.value for e in webhook.events],
        secret=webhook.secret,
    )

    logger.info("webhook_created", webhook_id=webhook_id, url=webhook.url)

    webhook_data = {
        "id": webhook_id,
        "url": webhook.url,
        "events": webhook.events,
        "secret": webhook.secret,
        "enabled": True,
        "created_at": datetime.utcnow(),
    }

    return WebhookConfig(**webhook_data)


@app.get("/config/webhooks", response_model=List[WebhookConfig])
async def list_webhooks(api_key: str = Depends(verify_api_key)):
    """List all webhook configurations"""
    webhooks = await db.get_webhooks()
    return [WebhookConfig(**w) for w in webhooks]


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates"""
    await websocket.accept()
    websocket_connections.add(websocket)
    logger.info("websocket_connected", client=websocket.client)

    try:
        # Send initial stats
        stats = await db.get_stats()
        await websocket.send_json(
            WebSocketMessage(
                type="initial_stats",
                timestamp=datetime.utcnow(),
                data=stats,
            ).model_dump(mode="json")
        )

        # Keep connection alive
        while True:
            # Wait for messages (keepalive)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        logger.info("websocket_disconnected", client=websocket.client)
    except Exception as e:
        logger.error("websocket_error", error=str(e))
    finally:
        websocket_connections.discard(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
