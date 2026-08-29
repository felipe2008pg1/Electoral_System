import uuid
from pydantic import BaseModel, field_validator
from app.core.security import normalize_and_validate_cpf

class VoteRequest(BaseModel):
    cpf: str
    candidate_number: int

    @field_validator("cpf")
    @classmethod
    def validate_cpf_format(cls, v: str) -> str:
        try:
            return normalize_and_validate_cpf(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("candidate_number")
    @classmethod
    def validate_candidate_number(cls, v: int) -> int:
        if v <= 0 or v > 999999:
            raise ValueError("candidate_number out of valid range")
        return v

class VoteAccepted(BaseModel):
    status: str = "accepted"
    tracking_id: uuid.UUID