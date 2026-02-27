"""
Trust Gateway Example
Demonstrates agent registration, trust building, and graduated authorization
"""
import time
import hashlib
from trust_gateway_sdk import TrustClient


def hash_config(config: str) -> str:
    """Generate config hash"""
    return hashlib.sha256(config.encode()).hexdigest()


def main():
    # Initialize client
    client = TrustClient("http://localhost:8002", api_key="dev-api-key-change-in-production")
    
    print("=" * 60)
    print("Trust Gateway Demo: Graduated Authorization System")
    print("=" * 60)
    print()
    
    # 1. Register new agent
    print("📝 Registering new agent: 'email-bot'...")
    agent = client.register_agent(
        name="email-bot",
        provider="openai",
        config_hash=hash_config("gpt-4-config-v1"),
        capabilities=["send_email", "read_inbox", "search_email"]
    )
    agent_id = agent["id"]
    print(f"✅ Agent registered: {agent_id}")
    print(f"   Initial trust score: {agent['composite_score']:.3f}")
    print(f"   Trust tier: {agent['tier']} (starts low due to Sybil resistance)")
    print()
    
    # 2. Show initial trust breakdown
    print("🔍 Initial trust breakdown:")
    breakdown = client.get_trust_breakdown(agent_id)
    print(f"   Identity score: {breakdown['identity_score']:.3f}")
    print(f"   Config score: {breakdown['config_score']:.3f}")
    print(f"   Behavior score: {breakdown['behavior_score']:.3f}")
    print(f"   → Composite: {breakdown['composite_score']:.3f}")
    print()
    
    # 3. Try high-privilege action (should fail)
    print("🚫 Attempting privileged action (delete_database)...")
    auth = client.authorize(agent_id, "delete_database")
    if auth["allowed"]:
        print("   ✅ Authorized")
    else:
        print(f"   ❌ DENIED: {auth['reason']}")
        print(f"   Current tier: {auth['current_tier']}, Required tier: {auth['required_tier']}")
        print(f"   Current score: {auth['current_score']:.3f}, Required score: {auth['required_score']:.3f}")
    print()
    
    # 4. Perform low-privilege actions
    print("✉️ Performing authorized actions to build trust...")
    actions = [
        ("read_inbox", "success"),
        ("search_email", "success"),
        ("read_inbox", "success"),
        ("send_email", "success"),
        ("send_email", "success"),
        ("read_inbox", "success"),
        ("send_email", "success"),
        ("search_email", "success"),
    ]
    
    for i, (action, result) in enumerate(actions, 1):
        receipt = client.record_action(agent_id, action, result)
        print(f"   {i}. {action}: {result}")
        time.sleep(0.1)  # Small delay to show progression
    print()
    
    # 5. Check trust after building history
    print("📈 Trust score after building history:")
    agent_updated = client.get_agent(agent_id)
    breakdown_updated = client.get_trust_breakdown(agent_id)
    print(f"   Identity score: {breakdown_updated['identity_score']:.3f}")
    print(f"   Config score: {breakdown_updated['config_score']:.3f}")
    print(f"   Behavior score: {breakdown_updated['behavior_score']:.3f} (improved!)")
    print(f"   → Composite: {breakdown_updated['composite_score']:.3f}")
    print(f"   Trust tier: {agent_updated['tier']}")
    print()
    
    # 6. Try moderate action
    print("📧 Attempting moderate action (send_email)...")
    auth = client.authorize(agent_id, "send_email")
    if auth["allowed"]:
        print(f"   ✅ Authorized (tier {auth['current_tier']} >= {auth['required_tier']})")
    else:
        print(f"   ❌ DENIED: {auth['reason']}")
    print()
    
    # 7. Continue building trust
    print("🔄 Continuing to build trust with more successful actions...")
    for i in range(15):
        action = ["send_email", "read_inbox", "search_email"][i % 3]
        client.record_action(agent_id, action, "success")
        if (i + 1) % 5 == 0:
            updated = client.get_agent(agent_id)
            print(f"   After {i+1} more actions: score={updated['composite_score']:.3f}, tier={updated['tier']}")
    print()
    
    # 8. Check if now authorized for higher actions
    print("🎯 Checking authorization after trust building:")
    final_agent = client.get_agent(agent_id)
    print(f"   Final trust score: {final_agent['composite_score']:.3f}")
    print(f"   Final tier: {final_agent['tier']}")
    print()
    
    test_actions = ["read_config", "send_email", "write_data", "delete_database"]
    for action in test_actions:
        auth = client.authorize(agent_id, action)
        status = "✅ ALLOWED" if auth["allowed"] else "❌ DENIED"
        print(f"   {action}: {status}")
    print()
    
    # 9. Show trust tiers
    print("🏆 Trust Tiers:")
    tiers = client.get_tiers()
    for tier in tiers:
        print(f"   Tier {tier['tier']}: {tier['name']} ({tier['min_score']:.1f}-{tier['max_score']:.1f})")
        print(f"      {tier['description']}")
    print()
    
    # 10. Demonstrate violation impact
    print("⚠️ Demonstrating violation impact on trust...")
    pre_violation = client.get_agent(agent_id)
    print(f"   Score before violation: {pre_violation['composite_score']:.3f}")
    
    client.record_action(agent_id, "unauthorized_action", "violation")
    client.record_action(agent_id, "policy_breach", "violation")
    
    post_violation = client.get_agent(agent_id)
    print(f"   Score after violations: {post_violation['composite_score']:.3f}")
    print(f"   Trust decreased by: {(pre_violation['composite_score'] - post_violation['composite_score']):.3f}")
    print()
    
    # 11. Show receipt chain
    print("🔗 Action receipt chain (last 5):")
    receipts = client.get_receipts(agent_id)
    for receipt in receipts[:5]:
        print(f"   {receipt['action']}: {receipt['result']}")
        print(f"      Signature: {receipt['signature'][:32]}...")
        print(f"      Chain hash: {receipt['receipt_hash'][:32]}...")
        if receipt['previous_hash']:
            print(f"      Previous: {receipt['previous_hash'][:32]}...")
    print()
    
    # 12. Dashboard stats
    print("📊 Dashboard Statistics:")
    stats = client.get_stats()
    print(f"   Total agents: {stats['total_agents']}")
    print(f"   Total actions: {stats['total_actions']}")
    print(f"   Recent actions (24h): {stats['recent_actions']}")
    print(f"   Agents by tier: {stats['agents_by_tier']}")
    print()
    
    print("=" * 60)
    print("Demo complete! Key takeaways:")
    print("  • New agents start with low trust (Sybil resistance)")
    print("  • Trust builds through successful action history")
    print("  • Authorization is graduated based on trust tiers")
    print("  • Violations quickly reduce trust scores")
    print("  • All actions are cryptographically signed and chained")
    print("=" * 60)


if __name__ == "__main__":
    main()
