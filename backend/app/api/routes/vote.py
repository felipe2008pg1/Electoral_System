import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.redis_client import get_redis
from app.core.security import compute_voter_hash
from app.db.models import Candidate, VoterRegistry
from app.db.session import get_db
from app.schemas.vote import VoteAccepted, VoteRequest

router = APIRouter(prefix="/vote", tags=["vote"])
logger = logging.getLogger("electoral_system.vote")
settings = get_settings()

VOTE_STREAM_KEY = "votes:pending"


from app.main import limiter  # noqa: E402  (imported here to avoid circular import at module load)


@router.post("", response_model=VoteAccepted, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def submit_vote(
    payload: VoteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> VoteAccepted:
    voter_hash = compute_voter_hash(payload.cpf, settings.voter_hmac_secret)

    # Fast-path eligibility check. NOT the final enforcement point —
    # the `voter_hash` UNIQUE constraint in the worker's transaction is
    # what actually prevents double voting under concurrent requests.
    existing = await db.execute(
        select(VoterRegistry.id).where(VoterRegistry.voter_hash == voter_hash)
    )
    if existing.scalar_one_or_none() is not None:
        logger.warning("Duplicate vote attempt rejected", extra={"ip": request.client.host})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vote already registered")

    candidate = await db.execute(
        select(Candidate.id).where(Candidate.number == payload.candidate_number)
    )
    if candidate.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid candidate number")

    tracking_id = uuid.uuid4()
    queue_payload = {
        "tracking_id": str(tracking_id),
        "voter_hash": voter_hash,
        "candidate_number": payload.candidate_number,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    await redis.xadd(VOTE_STREAM_KEY, {"data": json.dumps(queue_payload)})

    logger.info("Vote queued", extra={"tracking_id": str(tracking_id)})
    return VoteAccepted(tracking_id=tracking_id)