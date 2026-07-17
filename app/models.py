from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ParticipantStatus:
    AVAILABLE = "available"
    WINNER = "winner"
    BLOCKED = "blocked"


class ItemStatus:
    WAITING = "waiting"
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELED = "canceled"


class RoundStatus:
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELED = "canceled"


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, index=True)
    access_code = Column(String(5), nullable=False, unique=True, index=True)
    fixed_value = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default=ParticipantStatus.AVAILABLE, index=True)
    won_item_id = Column(ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    won_item = relationship("Item", foreign_keys=[won_item_id], post_update=True)
    bids = relationship("Bid", back_populates="participant", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    image_path = Column(String(260), nullable=True)
    display_order = Column(Integer, nullable=False, default=0, index=True)
    status = Column(String(20), nullable=False, default=ItemStatus.WAITING, index=True)
    winner_id = Column(ForeignKey("participants.id", ondelete="SET NULL"), nullable=True)
    winning_value = Column(Integer, nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    winner = relationship("Participant", foreign_keys=[winner_id])
    rounds = relationship("Round", back_populates="item", cascade="all, delete-orphan")


class Round(Base):
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True)
    item_id = Column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=RoundStatus.ACTIVE, index=True)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    winner_id = Column(ForeignKey("participants.id", ondelete="SET NULL"), nullable=True)

    item = relationship("Item", back_populates="rounds")
    winner = relationship("Participant")
    bids = relationship("Bid", back_populates="round", cascade="all, delete-orphan")


class Bid(Base):
    __tablename__ = "bids"
    __table_args__ = (Index("ix_bids_round_active", "round_id", "active"),)

    id = Column(Integer, primary_key=True)
    round_id = Column(ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    bid_value = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    canceled_at = Column(DateTime(timezone=True), nullable=True)

    round = relationship("Round", back_populates="bids")
    participant = relationship("Participant", back_populates="bids")


Index(
    "uq_active_bid_per_round_participant",
    Bid.round_id,
    Bid.participant_id,
    unique=True,
    sqlite_where=Bid.active.is_(True),
)


class AdminAction(Base):
    __tablename__ = "admin_actions"

    id = Column(Integer, primary_key=True)
    action = Column(String(80), nullable=False, index=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)