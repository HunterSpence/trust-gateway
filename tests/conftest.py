"""Pytest configuration and fixtures"""
import pytest
import asyncio
from trust_gateway.database import Database
from trust_gateway.trust_engine import TrustEngine


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create test database"""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.init_db()
    yield db
    await db.engine.dispose()


@pytest.fixture
def trust_engine():
    """Create trust engine"""
    return TrustEngine("test-secret-key", "test-jwt-secret")
