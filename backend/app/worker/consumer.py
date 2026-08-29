import asyncio
import json
import logging
import signal
from datetime import datetime, timezone

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError

from app.core.constants import RESULTS_CHANNEL
from app.core.redis_client import get_redis
from app.db.models import AuditChain, Candidate, VoterRegistry
from app.db.session import AsyncSessionLocal
from app.worker.audit import compute_entry_hash, compute_payload_hash

logger = logging.getLogger("electoral_system.worker")

STREAM_KEY = "votes:pending"
GROUP_NAME = "vote_processors"
CONSUMER_NAME = "worker-1"
DEADLETTER_STREAM = "votes:deadletter"
MAX_DELIVERIES = 5
BLOCK_MS = 5000
BATCH_SIZE = 10
CHAIN_LOCK_KEY = "audit_chain"  # postgres advisory-lock name, serializes chain appends


async def ensure_group(redis: Redis) -> None:
    try:
        await redis.xgroup_create(STREAM_KEY, GROUP_NAME, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def process_message(redis: Redis, data: dict) -> str:
    """Returns 'ok', 'duplicate', or 'invalid_candidate'. Raises on unexpected failure."""
    payload = json.loads(data["data"])
    voter_hash = payload["voter_hash"]
    candidate_number = payload["candidate_number"]
    tracking_id = payload["tracking_id"]

    updated_number = updated_name = updated_votes = None

    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                # Serializes audit_chain appends across concurrent worker processes,
                # preventing two workers from reading the same "last hash" and forking the chain.
                await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": CHAIN_LOCK_KEY})

                session.add(VoterRegistry(voter_hash=voter_hash))
                await session.flush()  # forces the UNIQUE constraint check now, not at commit

                result = await session.execute(
                    update(Candidate)
                    .where(Candidate.number == candidate_number)
                    .values(votes_count=Candidate.votes_count + 1)
                    .returning(Candidate.number, Candidate.name, Candidate.votes_count)
                )
                row = result.first()
                if row is None:
                    raise LookupError("invalid_candidate")
                updated_number, updated_name, updated_votes = row

                last = await session.execute(
                    select(AuditChain.entry_hash).order_by(AuditChain.seq.desc()).limit(1)
                )
                previous_hash = last.scalar_one_or_none()

                audit_payload = {
                    "voter_hash": voter_hash,
                    "candidate_number": candidate_number,
                    "tracking_id": tracking_id,
                }
                payload_hash = compute_payload_hash(audit_payload)
                ts = datetime.now(timezone.utc).isoformat()
                entry_hash = compute_entry_hash(previous_hash, "VOTE_REGISTERED", payload_hash, ts)

                session.add(
                    AuditChain(
                        previous_hash=previous_hash,
                        event_type="VOTE_REGISTERED",
                        payload_hash=payload_hash,
                        entry_hash=entry_hash,
                    )
                )
        except IntegrityError:
            logger.warning("Duplicate vote at commit time", extra={"tracking_id": tracking_id})
            return "duplicate"
        except LookupError:
            logger.error("Candidate vanished after acceptance", extra={"candidate_number": candidate_number})
            return "invalid_candidate"

    # Only reached after a successful commit. Broadcasts the aggregate tally —
    # never the voter_hash or tracking_id — to the public results channel.
    await redis.publish(
        RESULTS_CHANNEL,
        json.dumps({"candidate_number": updated_number, "candidate_name": updated_name, "votes_count": updated_votes}),
    )
    logger.info("Vote processed", extra={"tracking_id": tracking_id})
    return "ok"

async def deadletter(redis: Redis, message_id: str, data: dict, reason: str) -> None:
    await redis.xadd(DEADLETTER_STREAM, {**data, "reason": reason, "original_id": message_id})
    await redis.xack(STREAM_KEY, GROUP_NAME, message_id)
    logger.error("Message moved to dead-letter", extra={"message_id": message_id, "reason": reason})


async def reclaim_stale(redis: Redis) -> None:
    """On startup, reclaim messages left pending by a crashed worker; dead-letter poison messages."""
    try:
        pending = await redis.xpending_range(STREAM_KEY, GROUP_NAME, min="-", max="+", count=100)
    except ResponseError:
        return

    for entry in pending:
        message_id = entry["message_id"]
        deliveries = entry["times_delivered"]
        if deliveries >= MAX_DELIVERIES:
            claimed = await redis.xclaim(
                STREAM_KEY, GROUP_NAME, CONSUMER_NAME, min_idle_time=0, message_ids=[message_id]
            )
            for mid, data in claimed:
                await deadletter(redis, mid, data, reason="max_deliveries_exceeded")
        else:
            await redis.xclaim(
                STREAM_KEY, GROUP_NAME, CONSUMER_NAME, min_idle_time=30000, message_ids=[message_id]
            )


async def run() -> None:
    redis = await get_redis()
    await ensure_group(redis)
    await reclaim_stale(redis)

    stop = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    logger.info("Worker started, consuming %s", STREAM_KEY)

    while not stop.is_set():
        try:
            response = await redis.xreadgroup(
                GROUP_NAME, CONSUMER_NAME, {STREAM_KEY: ">"}, count=BATCH_SIZE, block=BLOCK_MS
            )
        except ResponseError:
            logger.exception("Redis read error, retrying in 2s")
            await asyncio.sleep(2)
            continue

        if not response:
            continue

        for _, messages in response:
            for message_id, data in messages:
                try:
                    await process_message(redis, data)
                    await redis.xack(STREAM_KEY, GROUP_NAME, message_id)
                except Exception:
                    logger.exception("Unexpected failure processing %s", message_id)
                    # Left un-acked on purpose: reclaim_stale() will retry it
                    # on next worker restart, up to MAX_DELIVERIES, then dead-letter it.

    logger.info("Worker shutting down")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())