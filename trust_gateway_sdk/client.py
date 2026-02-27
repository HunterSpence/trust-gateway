"""Trust Gateway SDK V2 - Async + Sync + WebSocket + JWT"""
import asyncio
import json
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime

import httpx
import websockets


class TrustClientAsync:
    """Async client SDK for Trust Gateway V2 API"""

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize async Trust Gateway client

        Args:
            base_url: Base URL of Trust Gateway API (e.g., http://localhost:8002)
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(headers={"X-API-Key": api_key}, timeout=30.0)

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def register_agent(
        self,
        name: str,
        provider: str,
        config_hash: str,
        capabilities: List[str],
        spiffe_id: Optional[str] = None,
        attestation: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Register a new agent with SPIFFE-compatible identity"""
        response = await self.client.post(
            f"{self.base_url}/agents/register",
            json={
                "name": name,
                "provider": provider,
                "spiffe_id": spiffe_id,
                "config_hash": config_hash,
                "capabilities": capabilities,
                "attestation": attestation,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_agent(self, agent_id: str) -> Dict:
        """Get agent profile and current trust score"""
        response = await self.client.get(f"{self.base_url}/agents/{agent_id}")
        response.raise_for_status()
        return response.json()

    async def get_trust_breakdown(self, agent_id: str) -> Dict:
        """Get detailed trust score breakdown"""
        response = await self.client.get(f"{self.base_url}/agents/{agent_id}/trust")
        response.raise_for_status()
        return response.json()

    async def get_trust_history(self, agent_id: str, limit: int = 100) -> Dict:
        """Get trust score history"""
        response = await self.client.get(
            f"{self.base_url}/agents/{agent_id}/history", params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()

    async def get_agent_card(self, agent_id: str) -> Dict:
        """Get A2A-compatible agent capability card"""
        response = await self.client.get(f"{self.base_url}/agents/{agent_id}/card")
        response.raise_for_status()
        return response.json()

    async def issue_token(self, agent_id: str, expires_in: int = 3600) -> Dict:
        """Issue JWT token for agent"""
        response = await self.client.post(
            f"{self.base_url}/agents/{agent_id}/token", params={"expires_in": expires_in}
        )
        response.raise_for_status()
        return response.json()

    async def record_action(
        self, agent_id: str, action: str, result: str, timestamp: Optional[datetime] = None
    ) -> Dict:
        """Record an action receipt"""
        data = {"agent_id": agent_id, "action": action, "result": result}
        if timestamp:
            data["timestamp"] = timestamp.isoformat()

        response = await self.client.post(f"{self.base_url}/actions/record", json=data)
        response.raise_for_status()
        return response.json()

    async def authorize(self, agent_id: str, action: str, context: Optional[Dict] = None) -> Dict:
        """Check if agent is authorized for an action"""
        data = {"agent_id": agent_id, "action": action}
        if context:
            data["context"] = context

        response = await self.client.post(f"{self.base_url}/authorize", json=data)
        response.raise_for_status()
        return response.json()

    async def authorize_batch(self, agent_id: str, actions: List[str]) -> Dict:
        """Batch authorization check"""
        response = await self.client.post(
            f"{self.base_url}/authorize/batch", json={"agent_id": agent_id, "actions": actions}
        )
        response.raise_for_status()
        return response.json()

    async def get_tiers(self) -> List[Dict]:
        """Get all trust tiers"""
        response = await self.client.get(f"{self.base_url}/tiers")
        response.raise_for_status()
        return response.json()

    async def update_tier(
        self,
        tier: int,
        name: str,
        min_score: float,
        max_score: float,
        description: str,
        permissions: List[str],
    ) -> Dict:
        """Update tier configuration (admin only)"""
        response = await self.client.put(
            f"{self.base_url}/tiers/{tier}",
            json={
                "tier": tier,
                "name": name,
                "min_score": min_score,
                "max_score": max_score,
                "description": description,
                "permissions": permissions,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_receipts(self, agent_id: str) -> List[Dict]:
        """Get action receipt chain"""
        response = await self.client.get(f"{self.base_url}/receipts/{agent_id}")
        response.raise_for_status()
        return response.json()

    async def get_stats(self) -> Dict:
        """Get dashboard statistics"""
        response = await self.client.get(f"{self.base_url}/stats")
        response.raise_for_status()
        return response.json()

    async def create_webhook(
        self, url: str, events: List[str], secret: Optional[str] = None
    ) -> Dict:
        """Create webhook configuration"""
        response = await self.client.post(
            f"{self.base_url}/config/webhooks",
            json={"url": url, "events": events, "secret": secret},
        )
        response.raise_for_status()
        return response.json()

    async def list_webhooks(self) -> List[Dict]:
        """List all webhooks"""
        response = await self.client.get(f"{self.base_url}/config/webhooks")
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> Dict:
        """Check API health"""
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()


class TrustClient:
    """Synchronous client SDK for Trust Gateway V2 API"""

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize Trust Gateway client

        Args:
            base_url: Base URL of Trust Gateway API (e.g., http://localhost:8002)
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(headers={"X-API-Key": api_key}, timeout=30.0)

    def close(self):
        """Close the HTTP client"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def register_agent(
        self,
        name: str,
        provider: str,
        config_hash: str,
        capabilities: List[str],
        spiffe_id: Optional[str] = None,
        attestation: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Register a new agent with SPIFFE-compatible identity"""
        response = self.client.post(
            f"{self.base_url}/agents/register",
            json={
                "name": name,
                "provider": provider,
                "spiffe_id": spiffe_id,
                "config_hash": config_hash,
                "capabilities": capabilities,
                "attestation": attestation,
            },
        )
        response.raise_for_status()
        return response.json()

    def get_agent(self, agent_id: str) -> Dict:
        """Get agent profile and current trust score"""
        response = self.client.get(f"{self.base_url}/agents/{agent_id}")
        response.raise_for_status()
        return response.json()

    def get_trust_breakdown(self, agent_id: str) -> Dict:
        """Get detailed trust score breakdown"""
        response = self.client.get(f"{self.base_url}/agents/{agent_id}/trust")
        response.raise_for_status()
        return response.json()

    def get_trust_history(self, agent_id: str, limit: int = 100) -> Dict:
        """Get trust score history"""
        response = self.client.get(
            f"{self.base_url}/agents/{agent_id}/history", params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()

    def get_agent_card(self, agent_id: str) -> Dict:
        """Get A2A-compatible agent capability card"""
        response = self.client.get(f"{self.base_url}/agents/{agent_id}/card")
        response.raise_for_status()
        return response.json()

    def issue_token(self, agent_id: str, expires_in: int = 3600) -> Dict:
        """Issue JWT token for agent"""
        response = self.client.post(
            f"{self.base_url}/agents/{agent_id}/token", params={"expires_in": expires_in}
        )
        response.raise_for_status()
        return response.json()

    def record_action(
        self, agent_id: str, action: str, result: str, timestamp: Optional[datetime] = None
    ) -> Dict:
        """Record an action receipt"""
        data = {"agent_id": agent_id, "action": action, "result": result}
        if timestamp:
            data["timestamp"] = timestamp.isoformat()

        response = self.client.post(f"{self.base_url}/actions/record", json=data)
        response.raise_for_status()
        return response.json()

    def authorize(self, agent_id: str, action: str, context: Optional[Dict] = None) -> Dict:
        """Check if agent is authorized for an action"""
        data = {"agent_id": agent_id, "action": action}
        if context:
            data["context"] = context

        response = self.client.post(f"{self.base_url}/authorize", json=data)
        response.raise_for_status()
        return response.json()

    def authorize_batch(self, agent_id: str, actions: List[str]) -> Dict:
        """Batch authorization check"""
        response = self.client.post(
            f"{self.base_url}/authorize/batch", json={"agent_id": agent_id, "actions": actions}
        )
        response.raise_for_status()
        return response.json()

    def get_tiers(self) -> List[Dict]:
        """Get all trust tiers"""
        response = self.client.get(f"{self.base_url}/tiers")
        response.raise_for_status()
        return response.json()

    def update_tier(
        self,
        tier: int,
        name: str,
        min_score: float,
        max_score: float,
        description: str,
        permissions: List[str],
    ) -> Dict:
        """Update tier configuration (admin only)"""
        response = self.client.put(
            f"{self.base_url}/tiers/{tier}",
            json={
                "tier": tier,
                "name": name,
                "min_score": min_score,
                "max_score": max_score,
                "description": description,
                "permissions": permissions,
            },
        )
        response.raise_for_status()
        return response.json()

    def get_receipts(self, agent_id: str) -> List[Dict]:
        """Get action receipt chain"""
        response = self.client.get(f"{self.base_url}/receipts/{agent_id}")
        response.raise_for_status()
        return response.json()

    def get_stats(self) -> Dict:
        """Get dashboard statistics"""
        response = self.client.get(f"{self.base_url}/stats")
        response.raise_for_status()
        return response.json()

    def create_webhook(
        self, url: str, events: List[str], secret: Optional[str] = None
    ) -> Dict:
        """Create webhook configuration"""
        response = self.client.post(
            f"{self.base_url}/config/webhooks",
            json={"url": url, "events": events, "secret": secret},
        )
        response.raise_for_status()
        return response.json()

    def list_webhooks(self) -> List[Dict]:
        """List all webhooks"""
        response = self.client.get(f"{self.base_url}/config/webhooks")
        response.raise_for_status()
        return response.json()

    def health_check(self) -> Dict:
        """Check API health"""
        response = self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()


class WebSocketDashboard:
    """WebSocket client for real-time Trust Gateway dashboard"""

    def __init__(self, ws_url: str):
        """
        Initialize WebSocket dashboard client

        Args:
            ws_url: WebSocket URL (e.g., ws://localhost:8002/ws/dashboard)
        """
        self.ws_url = ws_url
        self.ws = None

    async def connect(self):
        """Connect to WebSocket"""
        self.ws = await websockets.connect(self.ws_url)

    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.ws:
            await self.ws.close()

    async def listen(self, callback: Callable[[Dict], None]):
        """
        Listen for real-time updates

        Args:
            callback: Async function to call with each message
        """
        if not self.ws:
            await self.connect()

        try:
            async for message in self.ws:
                data = json.loads(message)
                await callback(data)
        except websockets.exceptions.ConnectionClosed:
            pass

    async def send_ping(self):
        """Send keepalive ping"""
        if self.ws:
            await self.ws.send("ping")
            response = await self.ws.recv()
            return response == "pong"
        return False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
