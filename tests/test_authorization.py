"""Test authorization checks"""
import pytest


class TestAuthorization:
    """Test authorization logic"""

    def test_authorization_allowed(self, trust_engine):
        """Test successful authorization"""
        allowed, reason = trust_engine.check_authorization(
            agent_tier=2, required_tier=1, agent_score=0.6, required_score=0.5
        )

        assert allowed is True
        assert reason == "Authorized"

    def test_authorization_denied_tier(self, trust_engine):
        """Test authorization denied due to tier"""
        allowed, reason = trust_engine.check_authorization(
            agent_tier=1, required_tier=3, agent_score=0.9, required_score=0.8
        )

        assert allowed is False
        assert "tier" in reason.lower()

    def test_authorization_denied_score(self, trust_engine):
        """Test authorization denied due to score"""
        allowed, reason = trust_engine.check_authorization(
            agent_tier=2, required_tier=2, agent_score=0.4, required_score=0.5
        )

        assert allowed is False
        assert "score" in reason.lower()

    def test_authorization_edge_case(self, trust_engine):
        """Test authorization at exact threshold"""
        allowed, reason = trust_engine.check_authorization(
            agent_tier=2, required_tier=2, agent_score=0.5, required_score=0.5
        )

        assert allowed is True
