"""Test async database operations"""
import pytest


class TestDatabase:
    """Test database operations"""

    @pytest.mark.asyncio
    async def test_create_agent(self, test_db):
        """Test agent creation"""
        agent = await test_db.create_agent(
            agent_id="test-1",
            name="Test Agent",
            provider="openai",
            spiffe_id="spiffe://example.org/agent/test",
            config_hash="abc123",
            capabilities=["read", "write"],
            attestation={"type": "x509"},
        )

        assert agent["id"] == "test-1"
        assert agent["name"] == "Test Agent"
        assert agent["spiffe_id"] == "spiffe://example.org/agent/test"

    @pytest.mark.asyncio
    async def test_get_agent(self, test_db):
        """Test agent retrieval"""
        await test_db.create_agent(
            agent_id="test-2",
            name="Test Agent 2",
            provider="anthropic",
            spiffe_id=None,
            config_hash="def456",
            capabilities=["read"],
            attestation=None,
        )

        agent = await test_db.get_agent("test-2")
        assert agent is not None
        assert agent["name"] == "Test Agent 2"
        assert agent["provider"] == "anthropic"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, test_db):
        """Test agent not found"""
        agent = await test_db.get_agent("nonexistent")
        assert agent is None

    @pytest.mark.asyncio
    async def test_update_agent_scores(self, test_db):
        """Test updating agent scores"""
        await test_db.create_agent(
            agent_id="test-3",
            name="Test Agent 3",
            provider="openai",
            spiffe_id=None,
            config_hash="ghi789",
            capabilities=["read"],
            attestation=None,
        )

        await test_db.update_agent_scores("test-3", 0.8, 0.9, 0.7, 0.75, 2)

        agent = await test_db.get_agent("test-3")
        assert agent["identity_score"] == 0.8
        assert agent["config_score"] == 0.9
        assert agent["behavior_score"] == 0.7
        assert agent["composite_score"] == 0.75
        assert agent["tier"] == 2

    @pytest.mark.asyncio
    async def test_create_and_get_receipt(self, test_db):
        """Test receipt creation and retrieval"""
        from datetime import datetime

        await test_db.create_agent(
            agent_id="test-4",
            name="Test Agent 4",
            provider="openai",
            spiffe_id=None,
            config_hash="jkl012",
            capabilities=["read"],
            attestation=None,
        )

        await test_db.create_receipt(
            receipt_id="receipt-1",
            agent_id="test-4",
            action="read_data",
            result="success",
            timestamp=datetime.utcnow(),
            signature="test-signature",
            previous_hash=None,
            receipt_hash="test-hash",
        )

        receipts = await test_db.get_receipts("test-4")
        assert len(receipts) == 1
        assert receipts[0]["action"] == "read_data"
        assert receipts[0]["result"] == "success"

    @pytest.mark.asyncio
    async def test_get_trust_history(self, test_db):
        """Test trust history retrieval"""
        await test_db.create_agent(
            agent_id="test-5",
            name="Test Agent 5",
            provider="openai",
            spiffe_id=None,
            config_hash="mno345",
            capabilities=["read"],
            attestation=None,
        )

        # Update scores (creates history)
        await test_db.update_agent_scores("test-5", 0.5, 0.6, 0.4, 0.45, 1)
        await test_db.update_agent_scores("test-5", 0.6, 0.7, 0.5, 0.55, 2)

        history = await test_db.get_trust_history("test-5")
        assert len(history) >= 2
        assert history[0]["composite_score"] == 0.55  # Most recent
        assert history[1]["composite_score"] == 0.45

    @pytest.mark.asyncio
    async def test_get_stats(self, test_db):
        """Test dashboard stats"""
        # Create a few agents
        await test_db.create_agent(
            "test-6", "Agent 6", "openai", None, "hash1", ["read"], None
        )
        await test_db.create_agent(
            "test-7", "Agent 7", "anthropic", None, "hash2", ["write"], None
        )

        stats = await test_db.get_stats()
        assert stats["total_agents"] >= 2
        assert "agents_by_tier" in stats
        assert "trust_score_distribution" in stats
