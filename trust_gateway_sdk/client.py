"""Trust Gateway SDK Client"""
import requests
from typing import List, Optional, Dict
from datetime import datetime


class TrustClient:
    """Client SDK for Trust Gateway API"""
    
    def __init__(self, base_url: str, api_key: str):
        """
        Initialize Trust Gateway client
        
        Args:
            base_url: Base URL of Trust Gateway API (e.g., http://localhost:8002)
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})
    
    def register_agent(self, name: str, provider: str, config_hash: str,
                      capabilities: List[str]) -> Dict:
        """
        Register a new agent
        
        Args:
            name: Agent name
            provider: Provider name (e.g., "openai", "anthropic")
            config_hash: SHA256 hash of agent configuration
            capabilities: List of agent capabilities
            
        Returns:
            Agent registration response with ID and initial trust score
        """
        response = self.session.post(
            f"{self.base_url}/agents/register",
            json={
                "name": name,
                "provider": provider,
                "config_hash": config_hash,
                "capabilities": capabilities
            }
        )
        response.raise_for_status()
        return response.json()
    
    def get_agent(self, agent_id: str) -> Dict:
        """
        Get agent profile and current trust score
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent profile with trust scores
        """
        response = self.session.get(f"{self.base_url}/agents/{agent_id}")
        response.raise_for_status()
        return response.json()
    
    def get_trust_breakdown(self, agent_id: str) -> Dict:
        """
        Get detailed trust score breakdown
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Detailed breakdown of identity, config, and behavior scores
        """
        response = self.session.get(f"{self.base_url}/agents/{agent_id}/trust")
        response.raise_for_status()
        return response.json()
    
    def record_action(self, agent_id: str, action: str, result: str,
                     timestamp: Optional[datetime] = None) -> Dict:
        """
        Record an action receipt
        
        Args:
            agent_id: Agent ID
            action: Action name
            result: Action result ("success", "failure", or "violation")
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            Signed action receipt with chain hash
        """
        data = {
            "agent_id": agent_id,
            "action": action,
            "result": result
        }
        if timestamp:
            data["timestamp"] = timestamp.isoformat()
        
        response = self.session.post(f"{self.base_url}/actions/record", json=data)
        response.raise_for_status()
        return response.json()
    
    def authorize(self, agent_id: str, action: str, context: Optional[Dict] = None) -> Dict:
        """
        Check if agent is authorized for an action
        
        Args:
            agent_id: Agent ID
            action: Action to authorize
            context: Optional context data
            
        Returns:
            Authorization response with allowed/denied status
        """
        data = {
            "agent_id": agent_id,
            "action": action
        }
        if context:
            data["context"] = context
        
        response = self.session.post(f"{self.base_url}/authorize", json=data)
        response.raise_for_status()
        return response.json()
    
    def get_tiers(self) -> List[Dict]:
        """
        Get all trust tiers and their configurations
        
        Returns:
            List of trust tiers
        """
        response = self.session.get(f"{self.base_url}/tiers")
        response.raise_for_status()
        return response.json()
    
    def update_tier(self, tier: int, name: str, min_score: float, max_score: float,
                   description: str, permissions: List[str]) -> Dict:
        """
        Update tier configuration (admin only)
        
        Args:
            tier: Tier number
            name: Tier name
            min_score: Minimum trust score
            max_score: Maximum trust score
            description: Tier description
            permissions: List of allowed permissions
            
        Returns:
            Updated tier configuration
        """
        response = self.session.put(
            f"{self.base_url}/tiers/{tier}",
            json={
                "tier": tier,
                "name": name,
                "min_score": min_score,
                "max_score": max_score,
                "description": description,
                "permissions": permissions
            }
        )
        response.raise_for_status()
        return response.json()
    
    def get_receipts(self, agent_id: str) -> List[Dict]:
        """
        Get action receipt chain for an agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of action receipts
        """
        response = self.session.get(f"{self.base_url}/receipts/{agent_id}")
        response.raise_for_status()
        return response.json()
    
    def get_stats(self) -> Dict:
        """
        Get dashboard statistics
        
        Returns:
            Dashboard statistics including agent counts and trust distribution
        """
        response = self.session.get(f"{self.base_url}/stats")
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> Dict:
        """
        Check API health status
        
        Returns:
            Health status
        """
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
