"""Quick test to verify Trust Gateway works"""
import sys
import hashlib
import os

# Cleanup old test database
if os.path.exists("test.db"):
    os.remove("test.db")

# Test imports
try:
    from trust_gateway.database import Database
    from trust_gateway.trust_engine import TrustEngine
    from trust_gateway_sdk import TrustClient
    print("[OK] All imports successful")
except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    sys.exit(1)

# Test database
try:
    db = Database("test.db")
    print("[OK] Database initialized")
    
    # Create test agent
    agent = db.create_agent(
        agent_id="test-001",
        name="test-agent",
        provider="test",
        config_hash=hashlib.sha256(b"test-config").hexdigest(),
        capabilities=["test_action"]
    )
    print(f"[OK] Agent created: {agent['id']}")
    
    # Retrieve agent
    retrieved = db.get_agent("test-001")
    assert retrieved is not None
    print("[OK] Agent retrieval works")
    
    # Get tiers
    tiers = db.get_tiers()
    assert len(tiers) == 4
    print(f"[OK] Default tiers initialized: {len(tiers)} tiers")
    
except Exception as e:
    print(f"[FAIL] Database test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test trust engine
try:
    engine = TrustEngine("test-secret")
    
    # Test identity score
    identity_score, factors = engine.calculate_identity_score(agent)
    assert 0 <= identity_score <= 1
    print(f"[OK] Identity score: {identity_score:.3f}")
    
    # Test config score
    config_score, factors = engine.calculate_config_score(agent)
    assert 0 <= config_score <= 1
    print(f"[OK] Config score: {config_score:.3f}")
    
    # Test behavior score (empty history)
    behavior_score, factors = engine.calculate_behavior_score([])
    assert behavior_score == 0.0
    print(f"[OK] Behavior score (empty): {behavior_score:.3f}")
    
    # Test composite
    composite = engine.calculate_composite_score(identity_score, config_score, behavior_score)
    assert 0 <= composite <= 1
    print(f"[OK] Composite score: {composite:.3f}")
    
    # Test signing
    signature = engine.sign_receipt("test-001", "test_action", "success", "2024-01-01T00:00:00", None)
    assert len(signature) == 64  # SHA256 hex
    print(f"[OK] Receipt signing works")
    
    # Test verification
    verified = engine.verify_receipt("test-001", "test_action", "success", "2024-01-01T00:00:00", signature, None)
    assert verified
    print("[OK] Receipt verification works")
    
    # Test tier determination
    tier = engine.determine_tier(composite, tiers)
    assert tier in [0, 1, 2, 3]
    print(f"[OK] Tier determination: tier {tier}")
    
except Exception as e:
    print(f"[FAIL] Trust engine test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test SDK client structure
try:
    # Don't actually connect, just verify it's importable and instantiable
    assert hasattr(TrustClient, 'register_agent')
    assert hasattr(TrustClient, 'authorize')
    assert hasattr(TrustClient, 'record_action')
    print("[OK] SDK client structure valid")
except Exception as e:
    print(f"[FAIL] SDK test failed: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("[PASS] ALL TESTS PASSED - Trust Gateway is working!")
print("="*60)
print("\nNext steps:")
print("1. Start server: python -m uvicorn trust_gateway.main:app --port 8002")
print("2. Run example: python example.py")
print("3. Or use Docker: docker-compose up -d")

# Cleanup
import os
if os.path.exists("test.db"):
    os.remove("test.db")
