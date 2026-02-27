# Trust Gateway V2

**AI Agent Trust Scoring with SPIFFE Identity, JWT Tokens, and A2A Compatibility**

Trust Gateway V2 is a production-ready security platform providing dynamic trust scoring and graduated authorization for AI agents. New in V2: SPIFFE-compatible identity attestation, JWT token issuance, A2A agent cards, webhooks, WebSocket dashboard, and OpenTelemetry tracing.

## 🎯 What's New in V2

### Major Upgrades
- **Full Async Architecture**: SQLAlchemy 2.0 + aiosqlite for high-performance async operations
- **Pydantic v2**: Modern model configuration with enhanced validation
- **SPIFFE Identity**: RFC-compliant SPIFFE ID support with X.509/JWT SVID attestation
- **JWT Token Issuance**: Short-lived tokens encoding trust tier and permitted actions
- **A2A Agent Cards**: Agent-to-Agent compatible capability cards
- **Webhook Alerts**: Real-time notifications for trust/tier changes
- **WebSocket Dashboard**: Live trust score updates via WebSocket
- **Batch Authorization**: Check multiple actions in single request
- **Trust History**: Time-series tracking of trust score evolution
- **OpenTelemetry**: Distributed tracing on all trust operations
- **Structured Logging**: JSON logging with structlog

### Breaking Changes from V1
- All endpoints now async (requires `await` in SDK)
- Pydantic v2 model syntax (`model_config` instead of `Config`)
- Database uses async SQLAlchemy (not compatible with V1 SQLite files)
- SDK split into `TrustClient` (sync) and `TrustClientAsync` (async)

## 🚀 Quick Start

### Installation

```bash
# Install from source
git clone <repo-url>
cd trust-gateway
pip install -e .

# Or install from pyproject.toml
pip install .
```

### Run Server

```bash
# Set environment variables
export SECRET_KEY="your-secret-key"
export JWT_SECRET="your-jwt-secret"
export API_KEY="your-api-key"

# Run with uvicorn
python -m uvicorn trust_gateway.main:app --host 0.0.0.0 --port 8002

# Or run directly
python -m trust_gateway.main
```

### Docker Deployment

```bash
docker build -t trust-gateway-v2 .
docker run -p 8002:8002 \
  -e SECRET_KEY=your-secret-key \
  -e API_KEY=your-api-key \
  trust-gateway-v2
```

## 📚 API Reference

### SPIFFE Identity Attestation

Register agents with SPIFFE IDs and cryptographic attestation:

```bash
POST /agents/register
```

**Request:**
```json
{
  "name": "email-bot",
  "provider": "openai",
  "spiffe_id": "spiffe://example.org/agent/email-bot",
  "config_hash": "sha256-hash",
  "capabilities": ["send_email", "read_inbox"],
  "attestation": {
    "type": "x509",
    "certificate": "-----BEGIN CERTIFICATE-----\n...",
    "chain": ["-----BEGIN CERTIFICATE-----\n..."]
  }
}
```

**Attestation Types:**
- `x509` - X.509 SVID (strongest, score boost +1.0)
- `jwt` - JWT SVID (strong, score boost +0.9)
- `api_key` - API key hash (medium, score boost +0.6)
- `self_declared` - No attestation (weak, score boost +0.3)

### JWT Token Issuance

Issue short-lived tokens encoding agent's trust tier:

```bash
POST /agents/{agent_id}/token?expires_in=3600
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600,
  "tier": 2,
  "permitted_actions": ["read_data", "write_data", "send_email"]
}
```

**Token Payload:**
```json
{
  "sub": "agent-uuid",
  "name": "email-bot",
  "tier": 2,
  "trust_score": 0.65,
  "permitted_actions": ["read_data", "write_data"],
  "iat": 1234567890,
  "exp": 1234571490,
  "iss": "trust-gateway"
}
```

### A2A Agent Cards

Get Agent-to-Agent compatible capability cards:

```bash
GET /agents/{agent_id}/card
```

**Response:**
```json
{
  "agent_id": "uuid",
  "name": "email-bot",
  "provider": "openai",
  "spiffe_id": "spiffe://example.org/agent/email-bot",
  "capabilities": ["send_email", "read_inbox"],
  "trust_score": 0.65,
  "trust_tier": 2,
  "tier_name": "Trusted",
  "created_at": "2024-01-01T00:00:00Z",
  "last_action_at": "2024-01-15T12:30:00Z",
  "total_actions": 142,
  "success_rate": 0.96,
  "permitted_actions": ["read_data", "write_data", "send_email"],
  "metadata": {
    "identity_score": 0.85,
    "config_score": 1.0,
    "behavior_score": 0.72
  }
}
```

### Trust History

Track trust score evolution over time:

```bash
GET /agents/{agent_id}/history?limit=100
```

**Response:**
```json
{
  "agent_id": "uuid",
  "history": [
    {
      "timestamp": "2024-01-15T12:30:00Z",
      "composite_score": 0.65,
      "tier": 2,
      "trigger": "score_update"
    },
    {
      "timestamp": "2024-01-15T11:00:00Z",
      "composite_score": 0.58,
      "tier": 2,
      "trigger": "action_recorded"
    }
  ]
}
```

### Batch Authorization

Check multiple actions at once:

```bash
POST /authorize/batch
```

**Request:**
```json
{
  "agent_id": "uuid",
  "actions": ["send_email", "delete_file", "query_db"]
}
```

**Response:**
```json
{
  "agent_id": "uuid",
  "results": {
    "send_email": {
      "allowed": true,
      "current_tier": 2,
      "required_tier": 2,
      "reason": "Authorized"
    },
    "delete_file": {
      "allowed": false,
      "current_tier": 2,
      "required_tier": 3,
      "reason": "Insufficient trust tier"
    }
  }
}
```

### Webhooks

Configure webhooks for real-time alerts:

```bash
POST /config/webhooks
```

**Request:**
```json
{
  "url": "https://your-service.com/webhook",
  "events": ["trust_changed", "tier_changed", "authorization_denied"],
  "secret": "webhook-signing-secret"
}
```

**Webhook Payload:**
```json
{
  "event": "tier_changed",
  "timestamp": "2024-01-15T12:30:00Z",
  "data": {
    "agent_id": "uuid",
    "old_tier": 1,
    "new_tier": 2,
    "score": 0.65
  }
}
```

**Events:**
- `trust_changed` - Trust score changed significantly
- `tier_changed` - Agent moved to different tier
- `authorization_denied` - Authorization check failed
- `receipt_chain_broken` - Receipt chain verification failed

### WebSocket Dashboard

Real-time trust updates via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8002/ws/dashboard');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch (message.type) {
    case 'initial_stats':
      console.log('Stats:', message.data);
      break;
    case 'agent_registered':
      console.log('New agent:', message.data.name);
      break;
    case 'receipt_recorded':
      console.log('Action:', message.data.action, 'New score:', message.data.new_score);
      break;
    case 'auth_denied':
      console.log('Auth denied:', message.data.reason);
      break;
  }
};

// Keepalive
setInterval(() => ws.send('ping'), 30000);
```

## 🐍 Python SDK V2

### Async Client

```python
from trust_gateway_sdk import TrustClientAsync
import asyncio

async def main():
    async with TrustClientAsync("http://localhost:8002", api_key="your-api-key") as client:
        # Register agent with SPIFFE identity
        agent = await client.register_agent(
            name="email-bot",
            provider="openai",
            spiffe_id="spiffe://example.org/agent/email-bot",
            config_hash="abc123",
            capabilities=["send_email", "read_inbox"],
            attestation={"type": "x509", "certificate": "..."}
        )
        
        # Issue JWT token
        token_response = await client.issue_token(agent["id"], expires_in=3600)
        print(f"Token: {token_response['token']}")
        
        # Get A2A agent card
        card = await client.get_agent_card(agent["id"])
        print(f"Trust score: {card['trust_score']}")
        
        # Record actions
        await client.record_action(agent["id"], "send_email", "success")
        
        # Batch authorization
        batch = await client.authorize_batch(
            agent["id"],
            actions=["send_email", "delete_file", "query_db"]
        )
        
        # Get trust history
        history = await client.get_trust_history(agent["id"])
        print(f"History: {len(history['history'])} points")
        
        # Configure webhook
        webhook = await client.create_webhook(
            url="https://example.com/webhook",
            events=["tier_changed", "authorization_denied"],
            secret="webhook-secret"
        )

asyncio.run(main())
```

### Sync Client

```python
from trust_gateway_sdk import TrustClient

with TrustClient("http://localhost:8002", api_key="your-api-key") as client:
    agent = client.register_agent(
        name="email-bot",
        provider="openai",
        config_hash="abc123",
        capabilities=["send_email"]
    )
    
    token = client.issue_token(agent["id"])
    print(f"Token: {token['token']}")
```

### WebSocket Client

```python
from trust_gateway_sdk import WebSocketDashboard
import asyncio

async def handle_message(data):
    print(f"Event: {data['type']}, Data: {data['data']}")

async def main():
    async with WebSocketDashboard("ws://localhost:8002/ws/dashboard") as dashboard:
        await dashboard.listen(handle_message)

asyncio.run(main())
```

## 🔐 Security Features

1. **SPIFFE Identity**: RFC-compliant SPIFFE IDs with X.509/JWT SVID attestation
2. **JWT Tokens**: Short-lived tokens with trust tier and permitted actions
3. **HMAC-SHA256 Signatures**: All action receipts cryptographically signed
4. **Receipt Chaining**: Blockchain-style chaining prevents tampering
5. **Webhook Signing**: HMAC signatures on webhook payloads
6. **Sybil Resistance**: New agents start at 0.1 score regardless of attestation
7. **API Key Authentication**: All endpoints require valid API key
8. **OpenTelemetry**: Distributed tracing for audit trails

## 🧪 Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run with coverage
pytest --cov=trust_gateway tests/

# Run specific test file
pytest tests/test_trust_scoring.py -v
```

**Test Coverage:**
- Trust scoring algorithm (identity + config + behavior)
- Authorization checks (tier + score requirements)
- Receipt signing and chain verification
- JWT token issuance and verification
- Async database operations
- Webhook delivery
- WebSocket connections

## 📊 OpenTelemetry Tracing

All trust operations are instrumented with OpenTelemetry:

```python
# Traces include:
# - register_agent
# - get_trust_breakdown
# - get_trust_history
# - get_agent_card
# - issue_token
# - record_action
# - authorize_action
# - authorize_batch
```

View traces in Jaeger, Zipkin, or any OTLP-compatible backend.

## 📜 License

**Proprietary Software**

Copyright © 2024-2026 Hunter Spence. All rights reserved.

Patent Pending.

## 📞 Support

- **Email**: hspence21190@gmail.com
- **Version**: 2.0.0
- **API Docs**: http://localhost:8002/docs (Swagger UI)

---

**Trust Gateway V2** - Production-ready AI agent trust scoring with SPIFFE identity and JWT tokens.
