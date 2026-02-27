"""Test JWT token issuance and verification"""
import pytest
from jose import JWTError


class TestJWT:
    """Test JWT token functionality"""

    def test_issue_token(self, trust_engine):
        """Test JWT token issuance"""
        token = trust_engine.issue_jwt_token(
            agent_id="test-agent",
            agent_name="Test Agent",
            tier=2,
            composite_score=0.65,
            permitted_actions=["read_data", "write_data"],
            expires_in=3600,
        )

        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token(self, trust_engine):
        """Test JWT token verification"""
        token = trust_engine.issue_jwt_token(
            agent_id="test-agent",
            agent_name="Test Agent",
            tier=2,
            composite_score=0.65,
            permitted_actions=["read_data", "write_data"],
            expires_in=3600,
        )

        payload = trust_engine.verify_jwt_token(token)

        assert payload["sub"] == "test-agent"
        assert payload["name"] == "Test Agent"
        assert payload["tier"] == 2
        assert payload["trust_score"] == 0.65
        assert "read_data" in payload["permitted_actions"]
        assert "write_data" in payload["permitted_actions"]

    def test_verify_invalid_token(self, trust_engine):
        """Test verification of invalid token"""
        with pytest.raises(JWTError):
            trust_engine.verify_jwt_token("invalid-token")

    def test_get_permitted_actions(self, trust_engine):
        """Test getting permitted actions for tier"""
        tiers = [
            {"tier": 0, "permissions": ["read_config"]},
            {"tier": 1, "permissions": ["read_config", "read_data"]},
            {"tier": 2, "permissions": ["read_config", "read_data", "write_data"]},
            {"tier": 3, "permissions": ["*"]},
        ]

        actions_tier_0 = trust_engine.get_permitted_actions_for_tier(0, tiers)
        assert actions_tier_0 == ["read_config"]

        actions_tier_2 = trust_engine.get_permitted_actions_for_tier(2, tiers)
        assert "write_data" in actions_tier_2

        actions_tier_3 = trust_engine.get_permitted_actions_for_tier(3, tiers)
        assert actions_tier_3 == ["*"]
