"""Async database operations for Trust Gateway V2 - SQLAlchemy 2.0 + aiosqlite"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from sqlalchemy import Column, String, Float, Integer, Text, DateTime, Boolean, select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import structlog

Base = declarative_base()
logger = structlog.get_logger()


# ORM Models
class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    spiffe_id = Column(String, nullable=True)
    config_hash = Column(String, nullable=False)
    capabilities = Column(Text, nullable=False)  # JSON
    attestation_type = Column(String, nullable=True)
    attestation_data = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, nullable=False)
    identity_score = Column(Float, default=0.0)
    config_score = Column(Float, default=0.0)
    behavior_score = Column(Float, default=0.0)
    composite_score = Column(Float, default=0.1)
    tier = Column(Integer, default=0)
    config_changes = Column(Integer, default=0)
    last_config_hash = Column(String, nullable=True)


class ActionReceiptModel(Base):
    __tablename__ = "action_receipts"

    id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    result = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    signature = Column(String, nullable=False)
    previous_hash = Column(String, nullable=True)
    receipt_hash = Column(String, nullable=False)


class TrustTierModel(Base):
    __tablename__ = "trust_tiers"

    tier = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    min_score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    permissions = Column(Text, nullable=False)  # JSON


class WebhookConfigModel(Base):
    __tablename__ = "webhook_configs"

    id = Column(String, primary_key=True)
    url = Column(String, nullable=False)
    events = Column(Text, nullable=False)  # JSON
    secret = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False)


class TrustHistoryModel(Base):
    __tablename__ = "trust_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    composite_score = Column(Float, nullable=False)
    tier = Column(Integer, nullable=False)
    trigger = Column(String, nullable=False)


class Database:
    """Async SQLAlchemy database manager"""

    def __init__(self, db_url: str = "sqlite+aiosqlite:///trust_gateway.db"):
        self.db_url = db_url
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("database_initialized", db_url=db_url)

    async def init_db(self):
        """Initialize database schema"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("database_schema_created")

        # Initialize default tiers if not exists
        async with self.async_session() as session:
            result = await session.execute(select(func.count()).select_from(TrustTierModel))
            count = result.scalar()
            if count == 0:
                await self._init_default_tiers(session)
                await session.commit()
                logger.info("default_tiers_initialized")

    async def _init_default_tiers(self, session: AsyncSession):
        """Initialize default trust tiers"""
        default_tiers = [
            TrustTierModel(
                tier=0,
                name="Untrusted",
                min_score=0.0,
                max_score=0.2,
                description="Read-only access, no external actions",
                permissions=json.dumps(["read_config", "view_status"]),
            ),
            TrustTierModel(
                tier=1,
                name="Limited",
                min_score=0.2,
                max_score=0.5,
                description="Basic actions, rate-limited",
                permissions=json.dumps(
                    ["read_config", "view_status", "send_notification", "read_data"]
                ),
            ),
            TrustTierModel(
                tier=2,
                name="Trusted",
                min_score=0.5,
                max_score=0.8,
                description="Most actions with some restrictions",
                permissions=json.dumps(
                    [
                        "read_config",
                        "view_status",
                        "send_notification",
                        "read_data",
                        "write_data",
                        "call_api",
                        "send_email",
                    ]
                ),
            ),
            TrustTierModel(
                tier=3,
                name="Privileged",
                min_score=0.8,
                max_score=1.0,
                description="Full access, self-approval",
                permissions=json.dumps(["*"]),
            ),
        ]

        for tier in default_tiers:
            session.add(tier)

    @asynccontextmanager
    async def session(self):
        """Context manager for database sessions"""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_agent(
        self,
        agent_id: str,
        name: str,
        provider: str,
        spiffe_id: Optional[str],
        config_hash: str,
        capabilities: List[str],
        attestation: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create a new agent"""
        async with self.session() as session:
            agent = AgentModel(
                id=agent_id,
                name=name,
                provider=provider,
                spiffe_id=spiffe_id,
                config_hash=config_hash,
                capabilities=json.dumps(capabilities),
                attestation_type=attestation.get("type") if attestation else None,
                attestation_data=json.dumps(attestation) if attestation else None,
                created_at=datetime.utcnow(),
                composite_score=0.1,
                last_config_hash=config_hash,
            )
            session.add(agent)

        logger.info("agent_created", agent_id=agent_id, name=name, provider=provider)
        return await self.get_agent(agent_id)

    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent by ID"""
        async with self.session() as session:
            result = await session.execute(select(AgentModel).where(AgentModel.id == agent_id))
            agent = result.scalar_one_or_none()

            if agent:
                return {
                    "id": agent.id,
                    "name": agent.name,
                    "provider": agent.provider,
                    "spiffe_id": agent.spiffe_id,
                    "config_hash": agent.config_hash,
                    "capabilities": json.loads(agent.capabilities),
                    "attestation": (
                        json.loads(agent.attestation_data) if agent.attestation_data else None
                    ),
                    "created_at": agent.created_at,
                    "identity_score": agent.identity_score,
                    "config_score": agent.config_score,
                    "behavior_score": agent.behavior_score,
                    "composite_score": agent.composite_score,
                    "tier": agent.tier,
                    "config_changes": agent.config_changes,
                    "last_config_hash": agent.last_config_hash,
                }
            return None

    async def update_agent_scores(
        self,
        agent_id: str,
        identity: float,
        config: float,
        behavior: float,
        composite: float,
        tier: int,
    ):
        """Update agent trust scores"""
        async with self.session() as session:
            result = await session.execute(select(AgentModel).where(AgentModel.id == agent_id))
            agent = result.scalar_one_or_none()

            if agent:
                old_tier = agent.tier
                agent.identity_score = identity
                agent.config_score = config
                agent.behavior_score = behavior
                agent.composite_score = composite
                agent.tier = tier

                # Record history point
                history = TrustHistoryModel(
                    agent_id=agent_id,
                    timestamp=datetime.utcnow(),
                    composite_score=composite,
                    tier=tier,
                    trigger="score_update",
                )
                session.add(history)

                logger.info(
                    "agent_scores_updated",
                    agent_id=agent_id,
                    composite_score=composite,
                    tier=tier,
                    tier_changed=(old_tier != tier),
                )

    async def create_receipt(
        self,
        receipt_id: str,
        agent_id: str,
        action: str,
        result: str,
        timestamp: datetime,
        signature: str,
        previous_hash: Optional[str],
        receipt_hash: str,
    ):
        """Create action receipt"""
        async with self.session() as session:
            receipt = ActionReceiptModel(
                id=receipt_id,
                agent_id=agent_id,
                action=action,
                result=result,
                timestamp=timestamp,
                signature=signature,
                previous_hash=previous_hash,
                receipt_hash=receipt_hash,
            )
            session.add(receipt)

        logger.info(
            "receipt_created",
            receipt_id=receipt_id,
            agent_id=agent_id,
            action=action,
            result=result,
        )

    async def get_receipts(self, agent_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Get all receipts for an agent"""
        async with self.session() as session:
            query = (
                select(ActionReceiptModel)
                .where(ActionReceiptModel.agent_id == agent_id)
                .order_by(ActionReceiptModel.timestamp.desc())
            )
            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            receipts = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "agent_id": r.agent_id,
                    "action": r.action,
                    "result": r.result,
                    "timestamp": r.timestamp,
                    "signature": r.signature,
                    "previous_hash": r.previous_hash,
                    "receipt_hash": r.receipt_hash,
                }
                for r in receipts
            ]

    async def get_last_receipt(self, agent_id: str) -> Optional[Dict]:
        """Get last receipt for an agent"""
        receipts = await self.get_receipts(agent_id, limit=1)
        return receipts[0] if receipts else None

    async def get_tiers(self) -> List[Dict]:
        """Get all trust tiers"""
        async with self.session() as session:
            result = await session.execute(select(TrustTierModel).order_by(TrustTierModel.tier))
            tiers = result.scalars().all()

            return [
                {
                    "tier": t.tier,
                    "name": t.name,
                    "min_score": t.min_score,
                    "max_score": t.max_score,
                    "description": t.description,
                    "permissions": json.loads(t.permissions),
                }
                for t in tiers
            ]

    async def get_tier(self, tier_num: int) -> Optional[Dict]:
        """Get specific tier"""
        async with self.session() as session:
            result = await session.execute(
                select(TrustTierModel).where(TrustTierModel.tier == tier_num)
            )
            tier = result.scalar_one_or_none()

            if tier:
                return {
                    "tier": tier.tier,
                    "name": tier.name,
                    "min_score": tier.min_score,
                    "max_score": tier.max_score,
                    "description": tier.description,
                    "permissions": json.loads(tier.permissions),
                }
            return None

    async def update_tier(
        self,
        tier_num: int,
        name: str,
        min_score: float,
        max_score: float,
        description: str,
        permissions: List[str],
    ):
        """Update tier configuration"""
        async with self.session() as session:
            result = await session.execute(
                select(TrustTierModel).where(TrustTierModel.tier == tier_num)
            )
            tier = result.scalar_one_or_none()

            if tier:
                tier.name = name
                tier.min_score = min_score
                tier.max_score = max_score
                tier.description = description
                tier.permissions = json.dumps(permissions)

                logger.info("tier_updated", tier=tier_num, name=name)

    async def get_trust_history(
        self, agent_id: str, limit: Optional[int] = 100
    ) -> List[Dict]:
        """Get trust history for an agent"""
        async with self.session() as session:
            query = (
                select(TrustHistoryModel)
                .where(TrustHistoryModel.agent_id == agent_id)
                .order_by(TrustHistoryModel.timestamp.desc())
                .limit(limit)
            )

            result = await session.execute(query)
            history = result.scalars().all()

            return [
                {
                    "timestamp": h.timestamp,
                    "composite_score": h.composite_score,
                    "tier": h.tier,
                    "trigger": h.trigger,
                }
                for h in history
            ]

    async def create_webhook(
        self, webhook_id: str, url: str, events: List[str], secret: Optional[str]
    ):
        """Create webhook configuration"""
        async with self.session() as session:
            webhook = WebhookConfigModel(
                id=webhook_id,
                url=url,
                events=json.dumps(events),
                secret=secret,
                enabled=True,
                created_at=datetime.utcnow(),
            )
            session.add(webhook)

        logger.info("webhook_created", webhook_id=webhook_id, url=url)

    async def get_webhooks(self) -> List[Dict]:
        """Get all webhook configurations"""
        async with self.session() as session:
            result = await session.execute(select(WebhookConfigModel))
            webhooks = result.scalars().all()

            return [
                {
                    "id": w.id,
                    "url": w.url,
                    "events": json.loads(w.events),
                    "secret": w.secret,
                    "enabled": w.enabled,
                    "created_at": w.created_at,
                }
                for w in webhooks
            ]

    async def get_stats(self) -> Dict:
        """Get dashboard statistics"""
        async with self.session() as session:
            # Total agents
            total_agents_result = await session.execute(
                select(func.count()).select_from(AgentModel)
            )
            total_agents = total_agents_result.scalar()

            # Total actions
            total_actions_result = await session.execute(
                select(func.count()).select_from(ActionReceiptModel)
            )
            total_actions = total_actions_result.scalar()

            # Agents by tier
            agents_by_tier_result = await session.execute(
                select(AgentModel.tier, func.count()).group_by(AgentModel.tier)
            )
            agents_by_tier = {str(tier): count for tier, count in agents_by_tier_result}

            # Recent actions (last 24 hours)
            from datetime import timedelta

            recent_cutoff = datetime.utcnow() - timedelta(days=1)
            recent_actions_result = await session.execute(
                select(func.count())
                .select_from(ActionReceiptModel)
                .where(ActionReceiptModel.timestamp > recent_cutoff)
            )
            recent_actions = recent_actions_result.scalar()

            # Trust score distribution
            # SQLite doesn't support CASE in same way, so we'll do it in Python
            agents_result = await session.execute(select(AgentModel.composite_score))
            scores = agents_result.scalars().all()

            distribution = {"0.0-0.2": 0, "0.2-0.5": 0, "0.5-0.8": 0, "0.8-1.0": 0}
            for score in scores:
                if score < 0.2:
                    distribution["0.0-0.2"] += 1
                elif score < 0.5:
                    distribution["0.2-0.5"] += 1
                elif score < 0.8:
                    distribution["0.5-0.8"] += 1
                else:
                    distribution["0.8-1.0"] += 1

            return {
                "total_agents": total_agents,
                "total_actions": total_actions,
                "agents_by_tier": agents_by_tier,
                "recent_actions": recent_actions,
                "trust_score_distribution": distribution,
            }
