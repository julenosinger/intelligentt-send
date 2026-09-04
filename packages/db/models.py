import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, Index, JSON, BigInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


def uuid4_str():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=uuid4_str)
    address = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())


class Transfer(Base):
    __tablename__ = "transfers"
    
    id = Column(String, primary_key=True, default=uuid4_str)
    user_id = Column(String, nullable=False)
    mode = Column(String, nullable=False)  # basic, intelligent, advanced
    from_address = Column(String, nullable=False)
    to_address = Column(String, nullable=False)
    amount = Column(String, nullable=False)
    token = Column(String, nullable=False)
    chain_id = Column(Integer, nullable=False)
    gas_fee = Column(String)
    total_cost = Column(String)
    tx_hash = Column(String, unique=True)
    status = Column(String, default="pending")  # pending, confirmed, failed
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    finalized_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("ix_transfers_user_id", "user_id"),
        Index("ix_transfers_chain_id", "chain_id"),
        Index("ix_transfers_status", "status"),
    )


class Template(Base):
    __tablename__ = "templates"
    
    id = Column(String, primary_key=True, default=uuid4_str)
    name = Column(String, unique=True, nullable=False)
    from_address = Column(String, nullable=False)
    to_address = Column(String, nullable=False)
    amount = Column(String, nullable=False)
    interval = Column(String, nullable=False, default="Monthly")  # None, Daily, Weekly, Monthly
    oracle_condition = Column(Text, nullable=True)
    is_recurring = Column(Boolean, default=False)
    execute_at_utc = Column(String, nullable=True)  # ISO UTC
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class Allowlist(Base):
    __tablename__ = "allowlists"
    
    id = Column(String, primary_key=True, default=uuid4_str)
    user_id = Column(String, nullable=False)
    recipient = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class History(Base):
    __tablename__ = "history"
    
    id = Column(String, primary_key=True, default=uuid4_str)
    address = Column(String, nullable=False)
    chain_id = Column(Integer, nullable=False)
    type = Column(String, nullable=False)  # out, in, pend, fail
    amount = Column(String, nullable=False)
    token = Column(String, nullable=False)
    time = Column(DateTime, default=lambda: datetime.utcnow())
    status = Column(String, nullable=False)  # confirmed, pending, failed
    hash = Column(String, nullable=True)
    explorer_url = Column(String, nullable=True)