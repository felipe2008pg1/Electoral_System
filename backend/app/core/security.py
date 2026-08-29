import hashlib
import hmac
import re

_CPF_DIGITS_RE = re.compile(r"\D")


def _only_digits(value: str) -> str:
    return _CPF_DIGITS_RE.sub("", value or "")


def _calc_check_digit(digits: list[int]) -> int:
    weight = len(digits) + 1
    total = sum(d * (weight - i) for i, d in enumerate(digits))
    remainder = (total * 10) % 11
    return 0 if remainder == 10 else remainder


def normalize_and_validate_cpf(raw_cpf: str) -> str:
    """
    Validates a Brazilian CPF (format + check digits).
    Returns the normalized 11-digit string on success.
    Raises ValueError on any invalid input — never trust the caller.
    """
    cpf = _only_digits(raw_cpf)

    if len(cpf) != 11:
        raise ValueError("CPF must contain exactly 11 digits")

    if cpf == cpf[0] * 11:
        # All-same-digit CPFs (e.g. 111.111.111-11) pass the checksum math
        # but are never valid real documents — explicitly reject them.
        raise ValueError("Invalid CPF")

    digits = [int(c) for c in cpf]
    d1 = _calc_check_digit(digits[:9])
    d2 = _calc_check_digit(digits[:9] + [d1])

    if digits[9] != d1 or digits[10] != d2:
        raise ValueError("Invalid CPF check digits")

    return cpf


def compute_voter_hash(cpf: str, secret: str) -> str:
    """
    HMAC-SHA256(cpf, key=secret). Mitigates static-salt brute-force
    (secret is server-held, not derivable from the hash), but does NOT
    fully solve CPF's low-entropy problem if `secret` itself leaks
    alongside the database. See DECISIONS.md #4 for the accepted residual risk.
    """
    return hmac.new(secret.encode("utf-8"), cpf.encode("utf-8"), hashlib.sha256).hexdigest()