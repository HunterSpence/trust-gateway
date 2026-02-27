"""Trust scoring engine V2 with JWT token issuance"""
import hmac
import hashlib
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, List
from jose import jwt
import structlog

logger = structlog.get_logger()


class TrustEngine:
    """Core trust scoring and authorization engine"""

    def __init__(
        self,
        secret_key: str,
        jwt_secret: Optional[str] = None,
        weights: Optional[Dict[str, float]] = None,
    ):
        self.secret_key = secret_key.encode()
        self.jwt_secret = jwt_secret or secret_key
        self.weights = weights or {"identity": 0.3, "config": 0.2, "behavior": 0.5}

    def calculate_identity_score(self, agent: Dict) -> Tuple[float, Dict]:
        """
        Calculate identity score based on attestation completeness + SPIFFE
        Returns: (score, factors)
        """
        factors = {
            "has_name": 1.0 if agent.get("name") else 0.0,
            "has_provider": 1.0 if agent.get("provider") else 0.0,
            "has_config_hash": 1.0 if agent.get("config_hash") else 0.0,
            "has_capabilities": (
                1.0 if agent.get("capabilities") and len(agent["capabilities"]) > 0 else 0.0
            ),
            "capabilities_count": min(len(agent.get("capabilities", [])) / 10.0, 1.0),
            "has_spiffe_id": 1.0 if agent.get("spiffe_id") else 0.0,
            "has_attestation": 1.0 if agent.get("attestation") else 0.0,
        }

        # Bonus for SPIFFE identity and attestation
        attestation = agent.get("attestation")
        if attestation:
            attestation_type = attestation.get("type")
            if attestation_type == "x509":
                factors["attestation_strength"] = 1.0  # Strongest
            elif attestation_type == "jwt":
                factors["attestation_strength"] = 0.9
            elif attestation_type == "api_key":
                factors["attestation_strength"] = 0.6
            else:
                factors["attestation_strength"] = 0.3  # Self-declared
        else:
            factors["attestation_strength"] = 0.0

        # Weighted average with SPIFFE/attestation bonus
        base_score = (
            factors["has_name"] * 0.15
            + factors["has_provider"] * 0.15
            + factors["has_config_hash"] * 0.15
            + factors["has_capabilities"] * 0.15
            + factors["capabilities_count"] * 0.10
            + factors["has_spiffe_id"] * 0.15
            + factors["attestation_strength"] * 0.15
        )

        score = min(1.0, base_score)
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
            "known_good_boost": 0.0,
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
            "weighted_score": final_score,
        }

        return final_score, factors

    def calculate_composite_score(
        self, identity: float, config: float, behavior: float
    ) -> float:
        """Calculate weighted composite trust score"""
        composite = (
            self.weights["identity"] * identity
            + self.weights["config"] * config
            + self.weights["behavior"] * behavior
        )

        # Clamp to [0, 1]
        return max(0.0, min(1.0, composite))

    def determine_tier(self, score: float, tiers: list) -> int:
        """Determine trust tier based on score"""
        for tier_data in sorted(tiers, key=lambda t: t["tier"], reverse=True):
            if score >= tier_data["min_score"]:
                return tier_data["tier"]
        return 0  # Default to lowest tier

    def sign_receipt(
        self,
        agent_id: str,
        action: str,
        result: str,
        timestamp: str,
        previous_hash: Optional[str] = None,
    ) -> str:
        """Generate HMAC-SHA256 signature for action receipt"""
        message = f"{agent_id}|{action}|{result}|{timestamp}|{previous_hash or ''}"
        signature = hmac.new(self.secret_key, message.encode(), hashlib.sha256).hexdigest()
        return signature

    def verify_receipt(
        self,
        agent_id: str,
        action: str,
        result: str,
        timestamp: str,
        signature: str,
        previous_hash: Optional[str] = None,
    ) -> bool:
        """Verify receipt signature"""
        expected = self.sign_receipt(agent_id, action, result, timestamp, previous_hash)
        return hmac.compare_digest(signature, expected)

    def hash_receipt(self, receipt_id: str, signature: str) -> str:
        """Generate hash for receipt chaining"""
        return hashlib.sha256(f"{receipt_id}|{signature}".encode()).hexdigest()

    def check_authorization(
        self,
        agent_tier: int,
        required_tier: int,
        agent_score: float,
        required_score: float,
    ) -> Tuple[bool, str]:
        """Check if agent is authorized for action"""
        if agent_tier >= required_tier and agent_score >= required_score:
            return True, "Authorized"
        elif agent_tier < required_tier:
            return (
                False,
                f"Insufficient trust tier (need tier {required_tier}, have {agent_tier})",
            )
        else:
            return (
                False,
                f"Insufficient trust score (need {required_score:.2f}, have {agent_score:.2f})",
            )

    def issue_jwt_token(
        self,
        agent_id: str,
        agent_name: str,
        tier: int,
        composite_score: float,
        permitted_actions: List[str],
        expires_in: int = 3600,
    ) -> str:
        """
        Issue JWT token encoding agent's trust tier and permitted actions
        
        Args:
            agent_id: Agent ID
            agent_name: Agent name
            tier: Current trust tier
            composite_score: Current composite trust score
            permitted_actions: List of permitted actions
            expires_in: Token expiration in seconds (default 3600 = 1 hour)
            
        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        payload = {
            "sub": agent_id,
            "name": agent_name,
            "tier": tier,
            "trust_score": round(composite_score, 3),
            "permitted_actions": permitted_actions,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
            "iss": "trust-gateway",
        }

        token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
        logger.info(
            "jwt_token_issued",
            agent_id=agent_id,
            tier=tier,
            score=composite_score,
            expires_in=expires_in,
        )

        return token

    def verify_jwt_token(self, token: str) -> Dict:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
            
        Raises:
            jose.JWTError: If token is invalid or expired
        """
        payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
        return payload

    def get_permitted_actions_for_tier(self, tier: int, tiers_config: List[Dict]) -> List[str]:
        """
        Get permitted actions for a given tier
        
        Args:
            tier: Trust tier number
            tiers_config: List of tier configurations
            
        Returns:
            List of permitted actions
        """
        for tier_data in tiers_config:
            if tier_data["tier"] == tier:
                permissions = tier_data["permissions"]
                if "*" in permissions:
                    return ["*"]  # Full access
                return permissions

        return []  # No permissions
