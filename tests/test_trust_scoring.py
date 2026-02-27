"""Test trust scoring algorithm"""
import pytest


class TestTrustScoring:
    """Test trust scoring calculations"""

    def test_identity_score_basic(self, trust_engine):
        """Test basic identity score calculation"""
        agent = {
            "name": "test-agent",
            "provider": "openai",
            "config_hash": "abc123",
            "capabilities": ["read", "write"],
        }

        score, factors = trust_engine.calculate_identity_score(agent)
        assert 0.0 <= score <= 1.0
        assert factors["has_name"] == 1.0
        assert factors["has_provider"] == 1.0
        assert factors["has_config_hash"] == 1.0
        assert factors["has_capabilities"] == 1.0

    def test_identity_score_with_spiffe(self, trust_engine):
        """Test identity score with SPIFFE ID"""
        agent = {
            "name": "test-agent",
            "provider": "openai",
            "spiffe_id": "spiffe://example.org/agent/test",
            "config_hash": "abc123",
            "capabilities": ["read", "write"],
            "attestation": {"type": "x509"},
        }

        score, factors = trust_engine.calculate_identity_score(agent)
        assert score > 0.7  # Should be high with SPIFFE + X.509
        assert factors["has_spiffe_id"] == 1.0
        assert factors["attestation_strength"] == 1.0

    def test_config_score_stable(self, trust_engine):
        """Test config score with stable config"""
        agent = {"config_changes": 0}

        score, factors = trust_engine.calculate_config_score(agent)
        assert score == 1.0
        assert factors["stability_score"] == 1.0

    def test_config_score_unstable(self, trust_engine):
        """Test config score with frequent changes"""
        agent = {"config_changes": 5}

        score, factors = trust_engine.calculate_config_score(agent)
        assert score < 1.0
        assert factors["config_changes"] == 5

    def test_behavior_score_empty(self, trust_engine):
        """Test behavior score with no history"""
        receipts = []

        score, factors = trust_engine.calculate_behavior_score(receipts)
        assert score == 0.0
        assert factors["total_actions"] == 0

    def test_behavior_score_all_success(self, trust_engine):
        """Test behavior score with all successes"""
        receipts = [
            {"result": "success"},
            {"result": "success"},
            {"result": "success"},
        ]

        score, factors = trust_engine.calculate_behavior_score(receipts)
        assert score > 0.9
        assert factors["success_rate"] == 1.0

    def test_behavior_score_with_violations(self, trust_engine):
        """Test behavior score with violations"""
        receipts = [
            {"result": "success"},
            {"result": "success"},
            {"result": "violation"},
        ]

        score, factors = trust_engine.calculate_behavior_score(receipts)
        assert score < 0.7
        assert factors["violations"] == 1

    def test_composite_score(self, trust_engine):
        """Test composite score calculation"""
        identity = 0.8
        config = 0.9
        behavior = 0.7

        composite = trust_engine.calculate_composite_score(identity, config, behavior)
        expected = 0.3 * 0.8 + 0.2 * 0.9 + 0.5 * 0.7
        assert abs(composite - expected) < 0.01

    def test_determine_tier(self, trust_engine):
        """Test tier determination"""
        tiers = [
            {"tier": 0, "min_score": 0.0, "max_score": 0.2},
            {"tier": 1, "min_score": 0.2, "max_score": 0.5},
            {"tier": 2, "min_score": 0.5, "max_score": 0.8},
            {"tier": 3, "min_score": 0.8, "max_score": 1.0},
        ]

        assert trust_engine.determine_tier(0.1, tiers) == 0
        assert trust_engine.determine_tier(0.3, tiers) == 1
        assert trust_engine.determine_tier(0.6, tiers) == 2
        assert trust_engine.determine_tier(0.9, tiers) == 3
