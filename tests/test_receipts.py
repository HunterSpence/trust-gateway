"""Test action receipt signing and chaining"""
import pytest


class TestReceipts:
    """Test receipt signing and verification"""

    def test_sign_receipt(self, trust_engine):
        """Test receipt signing"""
        signature = trust_engine.sign_receipt(
            agent_id="test-agent",
            action="send_email",
            result="success",
            timestamp="2024-01-01T00:00:00Z",
            previous_hash=None,
        )

        assert len(signature) == 64  # SHA256 hex digest

    def test_verify_receipt(self, trust_engine):
        """Test receipt verification"""
        agent_id = "test-agent"
        action = "send_email"
        result = "success"
        timestamp = "2024-01-01T00:00:00Z"

        signature = trust_engine.sign_receipt(agent_id, action, result, timestamp, None)

        is_valid = trust_engine.verify_receipt(agent_id, action, result, timestamp, signature, None)
        assert is_valid is True

    def test_verify_receipt_invalid(self, trust_engine):
        """Test receipt verification with invalid signature"""
        is_valid = trust_engine.verify_receipt(
            agent_id="test-agent",
            action="send_email",
            result="success",
            timestamp="2024-01-01T00:00:00Z",
            signature="invalid-signature",
            previous_hash=None,
        )

        assert is_valid is False

    def test_receipt_chaining(self, trust_engine):
        """Test receipt hash chaining"""
        receipt_id = "receipt-1"
        signature = "test-signature"

        receipt_hash = trust_engine.hash_receipt(receipt_id, signature)
        assert len(receipt_hash) == 64

        # Second receipt uses first as previous
        signature2 = trust_engine.sign_receipt(
            agent_id="test-agent",
            action="read_data",
            result="success",
            timestamp="2024-01-01T00:01:00Z",
            previous_hash=receipt_hash,
        )

        assert signature2 != signature  # Should be different
