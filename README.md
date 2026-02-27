# Trust Gateway

**AI Agent Trust Scoring and Graduated Authorization System**

Trust Gateway is a commercial security platform that provides dynamic trust scoring and graduated authorization for AI agents. Instead of binary allow/deny, agents earn privileges through proven behavior while remaining cryptographically accountable.

## 🎯 What It Does

Trust Gateway solves the **AI agent authorization problem**:

- **Trust Scoring**: Multi-factor scoring based on identity attestation, configuration stability, and behavioral history
- **Graduated Authorization**: Four trust tiers (Untrusted → Limited → Trusted → Privileged) with automatic progression
- **Sybil Resistance**: New agents start with minimal trust and must earn privileges through action history
- **Cryptographic Accountability**: HMAC-SHA256 signed action receipts with blockchain-style chaining
- **Real-time Authorization**: Fast authorization checks against current trust levels

### Core Algorithm

Trust score is a weighted combination of three factors:

```
composite_score = w_id × identity + w_cfg × config + w_beh × behavior
```

**Default weights**: identity=0.3, config=0.2, behavior=0.5

1. **Identity Score** (0-1): Completeness of attestation (name, provider, config hash, capabilities)
2. **Config Score** (0-1): Configuration stability (hash changes reduce score)
3. **Behavior Score** (0-1): Action history with exponential decay (recent actions weighted more)
   - Success: +1.0
   - Failure: +0.3 (partial penalty)
   - Violation: -1.0 (strong penalty)

### Trust Tiers

| Tier | Name | Score Range | Permissions |
|------|------|-------------|-------------|
| 0 | Untrusted | 0.0-0.2 | Read-only, no external actions |
| 1 | Limited | 0.2-0.5 | Basic actions, rate-limited |
| 2 | Trusted | 0.5-0.8 | Most actions, some restrictions |
| 3 | Privileged | 0.8-1.0 | Full access, self-approval |

**Sybil Resistance**: All new agents start at score 0.1 regardless of attestation, forcing them to earn trust through behavior.

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone repository
git clone <repo-url>
cd trust-gateway

# Configure environment
cp .env.example .env
# Edit .env with your SECRET_KEY and API_KEY

# Start service
docker-compose up -d

# Check health
curl http://localhost:8002/health
```

### Option 2: Local Python

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SECRET_KEY="your-secret-key"
export API_KEY="your-api-key"

# Run server
python -m uvicorn trust_gateway.main:app --host 0.0.0.0 --port 8002
```

### Run Example

```bash
# Install SDK
pip install -e .

# Run demo
python example.py
```

## 📚 API Reference

### Authentication

All endpoints require API key authentication:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8002/health
```

### Endpoints

#### `POST /agents/register`

Register a new agent with identity attestation.

**Request:**
```json
{
  "name": "email-bot",
  "provider": "openai",
  "config_hash": "sha256-hash-of-config",
  "capabilities": ["send_email", "read_inbox"]
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "email-bot",
  "provider": "openai",
  "composite_score": 0.1,
  "tier": 0,
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### `GET /agents/{agent_id}`

Get agent profile and current trust score.

#### `GET /agents/{agent_id}/trust`

Get detailed trust breakdown with factor scores.

**Response:**
```json
{
  "agent_id": "uuid",
  "identity_score": 0.85,
  "config_score": 1.0,
  "behavior_score": 0.72,
  "composite_score": 0.79,
  "tier": 2,
  "tier_name": "Trusted",
  "weights": {"identity": 0.3, "config": 0.2, "behavior": 0.5},
  "factors": {
    "identity": {"has_name": 1.0, "has_provider": 1.0, ...},
    "config": {"config_changes": 0, "stability_score": 1.0},
    "behavior": {"total_actions": 25, "success_rate": 0.96, ...}
  }
}
```

#### `POST /actions/record`

Record a signed action receipt.

**Request:**
```json
{
  "agent_id": "uuid",
  "action": "send_email",
  "result": "success"  // or "failure", "violation"
}
```

**Response:**
```json
{
  "id": "receipt-uuid",
  "agent_id": "uuid",
  "action": "send_email",
  "result": "success",
  "timestamp": "2024-01-01T00:00:00Z",
  "signature": "hmac-sha256-signature",
  "previous_hash": "hash-of-previous-receipt",
  "receipt_hash": "hash-for-chaining"
}
```

#### `POST /authorize`

Check if agent is authorized for an action.

**Request:**
```json
{
  "agent_id": "uuid",
  "action": "delete_database"
}
```

**Response:**
```json
{
  "allowed": false,
  "agent_id": "uuid",
  "action": "delete_database",
  "current_tier": 1,
  "required_tier": 3,
  "current_score": 0.35,
  "required_score": 0.9,
  "reason": "Insufficient trust tier (need tier 3, have 1)"
}
```

#### `GET /tiers`

List all trust tiers and their configurations.

#### `PUT /tiers/{tier}`

Update tier configuration (admin only).

#### `GET /receipts/{agent_id}`

Get action receipt chain for an agent (newest first).

#### `GET /stats`

Get dashboard statistics.

**Response:**
```json
{
  "total_agents": 42,
  "total_actions": 1337,
  "agents_by_tier": {"0": 5, "1": 15, "2": 18, "3": 4},
  "recent_actions": 89,
  "trust_score_distribution": {
    "0.0-0.2": 5,
    "0.2-0.5": 15,
    "0.5-0.8": 18,
    "0.8-1.0": 4
  }
}
```

## 🐍 Python SDK

```python
from trust_gateway_sdk import TrustClient
import hashlib

# Initialize client
client = TrustClient("http://localhost:8002", api_key="your-api-key")

# Register agent
agent = client.register_agent(
    name="email-bot",
    provider="openai",
    config_hash=hashlib.sha256(b"config-v1").hexdigest(),
    capabilities=["send_email", "read_inbox"]
)

# Record action
receipt = client.record_action(
    agent_id=agent["id"],
    action="send_email",
    result="success"
)

# Check authorization
auth = client.authorize(agent_id=agent["id"], action="delete_database")
if not auth["allowed"]:
    print(f"Denied: {auth['reason']}")
    print(f"Need tier {auth['required_tier']}, have tier {auth['current_tier']}")

# Get trust breakdown
breakdown = client.get_trust_breakdown(agent["id"])
print(f"Trust score: {breakdown['composite_score']:.2f}")
print(f"  Identity: {breakdown['identity_score']:.2f}")
print(f"  Config: {breakdown['config_score']:.2f}")
print(f"  Behavior: {breakdown['behavior_score']:.2f}")

# View receipt chain
receipts = client.get_receipts(agent["id"])
for r in receipts[:5]:
    print(f"{r['action']}: {r['result']} (hash: {r['receipt_hash'][:16]}...)")
```

## 🔐 Security Features

1. **HMAC-SHA256 Signatures**: All action receipts are cryptographically signed
2. **Receipt Chaining**: Each receipt includes hash of previous receipt (blockchain-style)
3. **Sybil Resistance**: New agents must earn trust through behavior, can't claim high trust
4. **API Key Authentication**: All endpoints require valid API key
5. **Configurable Secret Key**: HMAC signing key is environment-configurable

## 📊 Use Cases

- **AI Agent Orchestration**: Gradual privilege escalation for autonomous agents
- **Multi-Agent Systems**: Trust-based coordination between heterogeneous agents
- **Human-in-the-Loop**: Automatic approval for trusted agents, manual for untrusted
- **Compliance & Audit**: Complete cryptographic audit trail of all agent actions
- **Sandboxing**: Limit untrusted/new agents to read-only until they prove reliability

## 💰 Pricing

| Tier | Price | Agents | Features |
|------|-------|--------|----------|
| **Free** | $0/mo | 5 | Basic trust scoring, 3 tiers, SQLite storage |
| **Pro** | $99/mo | 50 | Custom tiers, receipt chains, analytics dashboard |
| **Enterprise** | $499/mo | Unlimited | SSO, audit logs, custom scoring models, PostgreSQL |

Contact: hspence21190@gmail.com

## 📜 License

**Proprietary Software**

Copyright © 2024 Hunter Spence. All rights reserved.

This software is protected by US Patent Application (pending).

**Evaluation License**: You may use this software for evaluation purposes only. Commercial use, modification, or redistribution requires a paid license. See LICENSE file for full terms.

## 🛠️ Development

```bash
# Install in development mode
pip install -e .

# Run tests (when available)
pytest

# Format code
black trust_gateway trust_gateway_sdk

# Lint
flake8 trust_gateway trust_gateway_sdk
```

## 📞 Support

- **Email**: hspence21190@gmail.com
- **Issues**: File issues for bugs or feature requests
- **Documentation**: See `/docs` for extended documentation

## 🚧 Roadmap

- [ ] PostgreSQL support for production deployments
- [ ] Web dashboard for trust visualization
- [ ] Webhook notifications for trust tier changes
- [ ] Multi-tenancy support
- [ ] Advanced analytics and anomaly detection
- [ ] Integration with popular agent frameworks (LangChain, AutoGPT, etc.)

---

**Trust Gateway** - Because AI agents should earn their privileges.
