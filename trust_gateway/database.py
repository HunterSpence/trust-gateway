"""Database operations for Trust Gateway"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import contextmanager


class Database:
    """SQLite database manager"""
    
    def __init__(self, db_path: str = "trust_gateway.db"):
        self.db_path = db_path
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def init_db(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    capabilities TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    identity_score REAL DEFAULT 0.0,
                    config_score REAL DEFAULT 0.0,
                    behavior_score REAL DEFAULT 0.0,
                    composite_score REAL DEFAULT 0.1,
                    tier INTEGER DEFAULT 0,
                    config_changes INTEGER DEFAULT 0,
                    last_config_hash TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS action_receipts (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    signature TEXT NOT NULL,
                    previous_hash TEXT,
                    receipt_hash TEXT NOT NULL,
                    FOREIGN KEY (agent_id) REFERENCES agents (id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trust_tiers (
                    tier INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    min_score REAL NOT NULL,
                    max_score REAL NOT NULL,
                    description TEXT NOT NULL,
                    permissions TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS known_configs (
                    config_hash TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    trust_boost REAL DEFAULT 0.0,
                    added_at TIMESTAMP NOT NULL
                )
            """)
            
            # Initialize default tiers if not exists
            cursor = conn.execute("SELECT COUNT(*) as count FROM trust_tiers")
            if cursor.fetchone()["count"] == 0:
                self._init_default_tiers(conn)
    
    def _init_default_tiers(self, conn):
        """Initialize default trust tiers"""
        default_tiers = [
            (0, "Untrusted", 0.0, 0.2, "Read-only access, no external actions", 
             json.dumps(["read_config", "view_status"])),
            (1, "Limited", 0.2, 0.5, "Basic actions, rate-limited", 
             json.dumps(["read_config", "view_status", "send_notification", "read_data"])),
            (2, "Trusted", 0.5, 0.8, "Most actions with some restrictions", 
             json.dumps(["read_config", "view_status", "send_notification", "read_data", 
                        "write_data", "call_api", "send_email"])),
            (3, "Privileged", 0.8, 1.0, "Full access, self-approval", 
             json.dumps(["*"]))
        ]
        
        conn.executemany(
            "INSERT INTO trust_tiers (tier, name, min_score, max_score, description, permissions) VALUES (?, ?, ?, ?, ?, ?)",
            default_tiers
        )
    
    def create_agent(self, agent_id: str, name: str, provider: str, config_hash: str, 
                     capabilities: List[str]) -> Dict:
        """Create a new agent"""
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO agents (id, name, provider, config_hash, capabilities, created_at, 
                   composite_score, last_config_hash) 
                   VALUES (?, ?, ?, ?, ?, ?, 0.1, ?)""",
                (agent_id, name, provider, config_hash, json.dumps(capabilities), 
                 datetime.utcnow().isoformat(), config_hash)
            )
        return self.get_agent(agent_id)
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Get agent by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
            row = cursor.fetchone()
            if row:
                agent = dict(row)
                agent["capabilities"] = json.loads(agent["capabilities"])
                return agent
            return None
    
    def update_agent_scores(self, agent_id: str, identity: float, config: float, 
                           behavior: float, composite: float, tier: int):
        """Update agent trust scores"""
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE agents 
                   SET identity_score = ?, config_score = ?, behavior_score = ?, 
                       composite_score = ?, tier = ?
                   WHERE id = ?""",
                (identity, config, behavior, composite, tier, agent_id)
            )
    
    def update_agent_config(self, agent_id: str, new_hash: str):
        """Update agent config hash and increment change counter"""
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE agents 
                   SET config_hash = ?, config_changes = config_changes + 1, last_config_hash = config_hash
                   WHERE id = ?""",
                (new_hash, agent_id)
            )
    
    def create_receipt(self, receipt_id: str, agent_id: str, action: str, result: str,
                      timestamp: datetime, signature: str, previous_hash: Optional[str],
                      receipt_hash: str):
        """Create action receipt"""
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO action_receipts 
                   (id, agent_id, action, result, timestamp, signature, previous_hash, receipt_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (receipt_id, agent_id, action, result, timestamp.isoformat(), 
                 signature, previous_hash, receipt_hash)
            )
    
    def get_receipts(self, agent_id: str) -> List[Dict]:
        """Get all receipts for an agent"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM action_receipts WHERE agent_id = ? ORDER BY timestamp DESC",
                (agent_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_last_receipt(self, agent_id: str) -> Optional[Dict]:
        """Get last receipt for an agent"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM action_receipts WHERE agent_id = ? ORDER BY timestamp DESC LIMIT 1",
                (agent_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_tiers(self) -> List[Dict]:
        """Get all trust tiers"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM trust_tiers ORDER BY tier")
            tiers = []
            for row in cursor.fetchall():
                tier = dict(row)
                tier["permissions"] = json.loads(tier["permissions"])
                tiers.append(tier)
            return tiers
    
    def get_tier(self, tier_num: int) -> Optional[Dict]:
        """Get specific tier"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM trust_tiers WHERE tier = ?", (tier_num,))
            row = cursor.fetchone()
            if row:
                tier = dict(row)
                tier["permissions"] = json.loads(tier["permissions"])
                return tier
            return None
    
    def update_tier(self, tier_num: int, name: str, min_score: float, max_score: float,
                   description: str, permissions: List[str]):
        """Update tier configuration"""
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE trust_tiers 
                   SET name = ?, min_score = ?, max_score = ?, description = ?, permissions = ?
                   WHERE tier = ?""",
                (name, min_score, max_score, description, json.dumps(permissions), tier_num)
            )
    
    def get_stats(self) -> Dict:
        """Get dashboard statistics"""
        with self.get_connection() as conn:
            # Total agents
            cursor = conn.execute("SELECT COUNT(*) as count FROM agents")
            total_agents = cursor.fetchone()["count"]
            
            # Total actions
            cursor = conn.execute("SELECT COUNT(*) as count FROM action_receipts")
            total_actions = cursor.fetchone()["count"]
            
            # Agents by tier
            cursor = conn.execute("SELECT tier, COUNT(*) as count FROM agents GROUP BY tier")
            agents_by_tier = {str(row["tier"]): row["count"] for row in cursor.fetchall()}
            
            # Recent actions (last 24 hours)
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM action_receipts WHERE timestamp > datetime('now', '-1 day')"
            )
            recent_actions = cursor.fetchone()["count"]
            
            # Trust score distribution
            cursor = conn.execute("""
                SELECT 
                    CASE 
                        WHEN composite_score < 0.2 THEN '0.0-0.2'
                        WHEN composite_score < 0.5 THEN '0.2-0.5'
                        WHEN composite_score < 0.8 THEN '0.5-0.8'
                        ELSE '0.8-1.0'
                    END as range,
                    COUNT(*) as count
                FROM agents
                GROUP BY range
            """)
            trust_distribution = {row["range"]: row["count"] for row in cursor.fetchall()}
            
            return {
                "total_agents": total_agents,
                "total_actions": total_actions,
                "agents_by_tier": agents_by_tier,
                "recent_actions": recent_actions,
                "trust_score_distribution": trust_distribution
            }
