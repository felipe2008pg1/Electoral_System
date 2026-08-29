import uuid

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    party: Mapped[str] = mapped_column(String, nullable=False)
    votes_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (CheckConstraint("votes_count >= 0", name="ck_votes_count_non_negative"),)


class VoterRegistry(Base):
    __tablename__ = "voters_registry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    voter_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    voted_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditChain(Base):
    __tablename__ = "audit_chain"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seq: Mapped[int] = mapped_column(BigInteger, autoincrement=True, unique=True, nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String, nullable=False)
    entry_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    timestamp = mapped_column(DateTime(timezone=True), server_default=func.now())