"""Trust scoring engine"""
import hmac
import hashlib
from datetime import datetime
from typing import Optional, Dict, Tuple
import math


class TrustEngine:
    """Core trust scoring and authorization engine"""
    
    def __init__(self, secret_key: str, weights: Optional[Dict[str, float]] = None):
        self.secret_key = secret_key.encode()
        self.weights = weights or {
            "identity": 0.3,
            "config": 0.2,
            "behavior": 0.5
        }
    
    def calculate_identity_score(self, agent: Dict) -> Tuple[float, Dict]:
        """
        Calculate identity score based on attestation completeness
        Returns: (score, factors)
        """
        factors = {
            "has_name": 1.0 if agent.get("name") else 0.0,
            "has_provider": 1.0 if agent.get("provider") else 0.0,
            "has_config_hash": 1.0 if agent.get("config_hash") else 0.0,
            "has_capabilities": 1.0 if agent.get("capabilities") and len(agent["capabilities"]) > 0 else 0.0,
            "capabilities_count": min(len(agent.get("capabilities", [])) / 10.0, 1.0)
        }
        
        # Weighted average of completeness factors
        score = (
            factors["has_name"] * 0.2 +
            factors["has_provider"] * 0.2 +
            factors["has_config_hash"] * 0.2 +
            factors["has_capabilities"] * 0.2 +
            factors["capabilities_count"] * 0.2
        )
        
        return score, factors
    
    def calculate_config_score(self, agent: Dict) -> Tuple[float, Dict]:
        """
        Calculate configuration score based on hash stability
        Returns: (score, factors)
        """
        config_changes = agent.get("config_changes", 0)
        
        # Penalize frequent config changes (exponential decay)
        stability_score = math.exp(-config_changes * 0.1)
        
        # Bonus for stable configs (no changes)
        if config_changes == 0:
            stability_score = 1.0
        
        factors = {
            "config_changes": config_changes,
            "stability_score": stability_score,
            "known_good_boost": 0.0  # Could be enhanced with known-good config registry
        }
        
        score = stability_score
        
        return score, factors
    
    def calculate_behavior_score(self, receipts: list) -> Tuple[float, Dict]:
        """
        Calculate behavior score based on action history
        Uses exponential decay to weight recent actions more heavily
        Returns: (score, factors)
        """
        if not receipts:
            return 0.0, {"total_actions": 0, "success_rate": 0.0, "recent_weight": 1.0}
        
        # Count outcomes
        successes = sum(1 for r in receipts if r["result"] == "success")
        failures = sum(1 for r in receipts if r["result"] == "failure")
        violations = sum(1 for r in receipts if r["result"] == "violation")
        total = len(receipts)
        
        # Base success rate
        success_rate = successes / total if total > 0 else 0.0
        
        # Apply exponential decay weighting (recent actions weighted more)
        weighted_score = 0.0
        total_weight = 0.0
        decay_factor = 0.95  # Recent actions get higher weight
        
        for i, receipt in enumerate(receipts):
            weight = math.pow(decay_factor, i)  # More recent = higher weight
            
            if receipt["result"] == "success":
                weighted_score += weight * 1.0
            elif receipt["result"] == "failure":
                weighted_score += weight * 0.3  # Partial penalty
            elif receipt["result"] == "violation":
                weighted_score += weight * -1.0  # Strong penalty
            
            total_weight += weight
        
        # Normalize
        final_score = weighted_score / total_weight if total_weight > 0 else 0.0
        
        # Clamp to [0, 1]
        final_score = max(0.0, min(1.0, final_score))
        
        factors = {
            "total_actions": total,
            "successes": successes,
            "failures": failures,
            "violations": violations,
            "success_rate": success_rate,
            "weighted_score": final_score
        }
        
        return final_score, factors
    
    def calculate_composite_score(self, identity: float, config: float, behavior: float) -> float:
        """Calculate weighted composite trust score"""
        composite = (
            self.weights["identity"] * identity +
            self.weights["config"] * config +
            self.weights["behavior"] * behavior
        )
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, composite))
    
    def determine_tier(self, score: float, tiers: list) -> int:
        """Determine trust tier based on score"""
        for tier_data in sorted(tiers, key=lambda t: t["tier"], reverse=True):
            if score >= tier_data["min_score"]:
                return tier_data["tier"]
        return 0  # Default to lowest tier
    
    def sign_receipt(self, agent_id: str, action: str, result: str, 
                    timestamp: str, previous_hash: Optional[str] = None) -> str:
        """Generate HMAC-SHA256 signature for action receipt"""
        message = f"{agent_id}|{action}|{result}|{timestamp}|{previous_hash or ''}"
        signature = hmac.new(self.secret_key, message.encode(), hashlib.sha256).hexdigest()
        return signature
    
    def verify_receipt(self, agent_id: str, action: str, result: str,
                      timestamp: str, signature: str, previous_hash: Optional[str] = None) -> bool:
        """Verify receipt signature"""
        expected = self.sign_receipt(agent_id, action, result, timestamp, previous_hash)
        return hmac.compare_digest(signature, expected)
    
    def hash_receipt(self, receipt_id: str, signature: str) -> str:
        """Generate hash for receipt chaining"""
        return hashlib.sha256(f"{receipt_id}|{signature}".encode()).hexdigest()
    
    def check_authorization(self, agent_tier: int, required_tier: int, 
                           agent_score: float, required_score: float) -> Tuple[bool, str]:
        """Check if agent is authorized for action"""
        if agent_tier >= required_tier and agent_score >= required_score:
            return True, "Authorized"
        elif agent_tier < required_tier:
            return False, f"Insufficient trust tier (need tier {required_tier}, have {agent_tier})"
        else:
            return False, f"Insufficient trust score (need {required_score:.2f}, have {agent_score:.2f})"
